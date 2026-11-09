// Multithreaded Monte-Carlo pricing under geometric Brownian motion.
//
// Reproducibility: the paths are split into a fixed number of blocks, each with its own
// random stream derived from (seed, block). Results therefore depend only on the seed and the
// number of paths — never on the number of threads or on the platform's standard library
// (we use our own xoshiro256** generator and Box-Muller transform rather than
// std::normal_distribution, whose algorithm differs between libstdc++ and libc++).
//
// Estimators match quantforge.pricing.mc_european / mc_asian: antithetic pairs are averaged
// before computing the standard error, and the optimal linear control variate
// b = Cov(Y, X) / Var(X) is estimated on the individual samples.
// SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <random>
#include <stdexcept>
#include <thread>
#include <vector>

#include "core.hpp"

namespace qf {

// ------------------------------------------------------------------ random numbers
class Xoshiro256 {
  public:
    explicit Xoshiro256(std::uint64_t seed) {
        for (auto& v : s_) v = splitmix(seed);
    }
    std::uint64_t next() noexcept {
        const std::uint64_t result = rotl(s_[1] * 5, 7) * 9, t = s_[1] << 17;
        s_[2] ^= s_[0]; s_[3] ^= s_[1]; s_[1] ^= s_[2]; s_[0] ^= s_[3];
        s_[2] ^= t; s_[3] = rotl(s_[3], 45);
        return result;
    }
    /// Uniform in the open interval (0, 1).
    double uniform() noexcept { return ((next() >> 11) + 0.5) * 0x1.0p-53; }
    /// Standard normal via Box-Muller (both outputs used).
    double normal() noexcept {
        if (has_spare_) { has_spare_ = false; return spare_; }
        const double u1 = uniform(), u2 = uniform();
        const double rad = std::sqrt(-2.0 * std::log(u1)), ang = 6.283185307179586477 * u2;
        spare_ = rad * std::sin(ang);
        has_spare_ = true;
        return rad * std::cos(ang);
    }

  private:
    static std::uint64_t rotl(std::uint64_t x, int k) noexcept { return (x << k) | (x >> (64 - k)); }
    static std::uint64_t splitmix(std::uint64_t& x) noexcept {
        std::uint64_t z = (x += 0x9E3779B97F4A7C15ULL);
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
    std::uint64_t s_[4]{};
    double spare_ = 0.0;
    bool has_spare_ = false;
};

struct MCResult {
    double price, std_error;
    long long n_paths;
};

// Sufficient statistics: individual samples (Y target, X control) and antithetic-pair means.
struct Moments {
    double n = 0, sy = 0, sx = 0, syy = 0, sxx = 0, sxy = 0;          // individual
    double m = 0, py = 0, px = 0, pyy = 0, pxx = 0, pxy = 0;          // pairs (or singles)
    void add(double y, double x) {
        n += 1; sy += y; sx += x; syy += y * y; sxx += x * x; sxy += x * y;
    }
    void add_pair(double y, double x) {
        m += 1; py += y; px += x; pyy += y * y; pxx += x * x; pxy += x * y;
    }
    void merge(const Moments& o) {
        n += o.n; sy += o.sy; sx += o.sx; syy += o.syy; sxx += o.sxx; sxy += o.sxy;
        m += o.m; py += o.py; px += o.px; pyy += o.pyy; pxx += o.pxx; pxy += o.pxy;
    }
};

inline MCResult summarize(const Moments& mo, bool use_cv, double control_mean) {
    double b = 0.0;
    if (use_cv) {
        const double var_x = (mo.sxx - mo.sx * mo.sx / mo.n) / (mo.n - 1);
        const double cov = (mo.sxy - mo.sx * mo.sy / mo.n) / (mo.n - 1);
        if (var_x > 0) b = cov / var_x;
    }
    // adjusted pair sample: Yp - b (Xp - mu)
    const double mean = (mo.py - b * (mo.px - mo.m * control_mean)) / mo.m;
    const double vy = (mo.pyy - mo.py * mo.py / mo.m) / (mo.m - 1);
    const double vx = (mo.pxx - mo.px * mo.px / mo.m) / (mo.m - 1);
    const double cxy = (mo.pxy - mo.px * mo.py / mo.m) / (mo.m - 1);
    const double var = std::fmax(vy - 2 * b * cxy + b * b * vx, 0.0);
    return {mean, std::sqrt(var / mo.m), static_cast<long long>(mo.n)};
}

// Runs body(block_index, rng, moments) for each block on a pool of threads.
template <class Body>
Moments run_blocks(long long n_units, std::uint64_t seed, int n_threads, Body body) {
    constexpr int kBlocks = 64;
    std::vector<Moments> part(kBlocks);
    auto worker = [&](int tid, int nt) {
        for (int b = tid; b < kBlocks; b += nt) {
            const long long lo = n_units * b / kBlocks, hi = n_units * (b + 1) / kBlocks;
            Xoshiro256 rng(seed * 0x9E3779B97F4A7C15ULL + static_cast<std::uint64_t>(b) + 1);
            for (long long i = lo; i < hi; ++i) body(rng, part[b]);
        }
    };
    if (n_threads <= 0) n_threads = static_cast<int>(std::max(1u, std::thread::hardware_concurrency()));
    n_threads = std::min(n_threads, kBlocks);
    std::vector<std::thread> pool;
    for (int t = 1; t < n_threads; ++t) pool.emplace_back(worker, t, n_threads);
    worker(0, n_threads);
    for (auto& th : pool) th.join();
    Moments total;
    for (const auto& p : part) total.merge(p);  // fixed order -> deterministic sum
    return total;
}

/// European option. Control variate: discounted terminal price (mean S0 e^{-qT}).
inline MCResult mc_european(double s, double k, double t, double r, double v, OptionType type,
                            double q = 0.0, long long n_paths = 1'000'000, bool antithetic = true,
                            bool control_variate = true, std::uint64_t seed = 42,
                            int n_threads = 0) {
    require_positive(s, "spot"); require_positive(k, "strike");
    require_positive(t, "maturity"); require_positive(v, "volatility");
    if (n_paths < 4) throw std::invalid_argument("n_paths must be >= 4");
    if (antithetic && n_paths % 2) ++n_paths;
    const double drift = (r - q - 0.5 * v * v) * t, vol = v * std::sqrt(t), disc = std::exp(-r * t);
    const long long units = antithetic ? n_paths / 2 : n_paths;
    Moments mo = run_blocks(units, seed, n_threads, [&](Xoshiro256& rng, Moments& m) {
        const double z = rng.normal();
        const double st1 = s * std::exp(drift + vol * z);
        const double y1 = disc * intrinsic(st1, k, type), x1 = disc * st1;
        if (antithetic) {
            const double st2 = s * std::exp(drift - vol * z);
            const double y2 = disc * intrinsic(st2, k, type), x2 = disc * st2;
            m.add(y1, x1); m.add(y2, x2);
            m.add_pair(0.5 * (y1 + y2), 0.5 * (x1 + x2));
        } else {
            m.add(y1, x1); m.add_pair(y1, x1);
        }
    });
    return summarize(mo, control_variate, s * std::exp(-q * t));
}

/// Closed form for the discretely monitored geometric-average Asian option.
inline double geometric_asian(double s, double k, double t, double r, double v, int n,
                              OptionType type, double q = 0.0) {
    const double mu = std::log(s) + (r - q - 0.5 * v * v) * t * (n + 1) / (2.0 * n);
    const double var = v * v * t * (n + 1) * (2.0 * n + 1) / (6.0 * n * n), sd = std::sqrt(var);
    const double d1 = (mu - std::log(k) + var) / sd, d2 = d1 - sd;
    const double disc = std::exp(-r * t), fg = std::exp(mu + 0.5 * var);
    return type == OptionType::Call ? disc * (fg * norm_cdf(d1) - k * norm_cdf(d2))
                                    : disc * (k * norm_cdf(-d2) - fg * norm_cdf(-d1));
}

/// Arithmetic-average Asian option with the geometric Asian as control (Kemna-Vorst 1990).
inline MCResult mc_asian(double s, double k, double t, double r, double v, int n_fixings,
                         OptionType type, double q = 0.0, long long n_paths = 200'000,
                         bool antithetic = true, bool control_variate = true,
                         std::uint64_t seed = 42, int n_threads = 0) {
    require_positive(s, "spot"); require_positive(k, "strike");
    require_positive(t, "maturity"); require_positive(v, "volatility");
    if (n_fixings < 1) throw std::invalid_argument("n_fixings must be >= 1");
    if (n_paths < 4) throw std::invalid_argument("n_paths must be >= 4");
    if (antithetic && n_paths % 2) ++n_paths;
    const double dt = t / n_fixings, drift = (r - q - 0.5 * v * v) * dt, vol = v * std::sqrt(dt);
    const double disc = std::exp(-r * t), ls = std::log(s);
    const long long units = antithetic ? n_paths / 2 : n_paths;
    Moments mo = run_blocks(units, seed, n_threads, [&](Xoshiro256& rng, Moments& m) {
        double la = ls, lb = ls, sa = 0, sb = 0, ga = 0, gb = 0;
        for (int i = 0; i < n_fixings; ++i) {
            const double z = rng.normal();
            la += drift + vol * z; sa += std::exp(la); ga += la;
            if (antithetic) { lb += drift - vol * z; sb += std::exp(lb); gb += lb; }
        }
        const double y1 = disc * intrinsic(sa / n_fixings, k, type);
        const double x1 = disc * intrinsic(std::exp(ga / n_fixings), k, type);
        if (antithetic) {
            const double y2 = disc * intrinsic(sb / n_fixings, k, type);
            const double x2 = disc * intrinsic(std::exp(gb / n_fixings), k, type);
            m.add(y1, x1); m.add(y2, x2);
            m.add_pair(0.5 * (y1 + y2), 0.5 * (x1 + x2));
        } else {
            m.add(y1, x1); m.add_pair(y1, x1);
        }
    });
    return summarize(mo, control_variate,
                     geometric_asian(s, k, t, r, v, n_fixings, type, q));
}

}  // namespace qf
