// Recombining binomial trees: Cox-Ross-Rubinstein and Leisen-Reimer (Peizer-Pratt 2).
// Same algorithm and outputs as quantforge.pricing.binomial_price.
// SPDX-License-Identifier: MIT
#pragma once

#include <cmath>
#include <stdexcept>
#include <vector>

#include "core.hpp"

namespace qf {

enum class TreeMethod { CRR, LR };

struct TreeResult {
    double price, delta, gamma, theta;
    int steps;
};

inline double peizer_pratt(double z, int n) {
    const double denom = n + 1.0 / 3.0 + 0.1 / (n + 1.0);
    return 0.5 + std::copysign(0.5, z) *
                     std::sqrt(1.0 - std::exp(-(z / denom) * (z / denom) * (n + 1.0 / 6.0)));
}

inline TreeResult binomial(double s, double k, double t, double r, double v, OptionType type,
                           bool american, double q = 0.0, int steps = 501,
                           TreeMethod method = TreeMethod::LR) {
    require_positive(s, "spot");
    require_positive(k, "strike");
    require_positive(t, "maturity");
    require_positive(v, "volatility");
    if (steps < 2) throw std::invalid_argument("steps must be >= 2");
    if (method == TreeMethod::LR && steps % 2 == 0) ++steps;

    const double dt = t / steps, growth = std::exp((r - q) * dt);
    double u, d, p;
    if (method == TreeMethod::CRR) {
        u = std::exp(v * std::sqrt(dt));
        d = 1.0 / u;
        p = (growth - d) / (u - d);
    } else {
        const double vst = v * std::sqrt(t);
        const double d1 = (std::log(s / k) + (r - q + 0.5 * v * v) * t) / vst, d2 = d1 - vst;
        p = peizer_pratt(d2, steps);
        const double ps = peizer_pratt(d1, steps);
        u = growth * ps / p;
        d = (growth - p * u) / (1.0 - p);
    }
    if (!(p > 0.0 && p < 1.0))
        throw std::invalid_argument("risk-neutral probability outside (0,1); increase steps");
    const double disc = std::exp(-r * dt), pu = disc * p, pd = disc * (1.0 - p);

    // Node price s * d^n * (u/d)^j, built by multiplication along each time slice.
    const double ratio = u / d;
    std::vector<double> val(steps + 1);
    {
        double x = s * std::pow(d, steps);
        for (int j = 0; j <= steps; ++j, x *= ratio) val[j] = intrinsic(x, k, type);
    }

    double s1[2] = {0, 0}, s2[3] = {0, 0, 0};
    for (int n = steps - 1; n >= 0; --n) {
        if (american) {
            double x = s * std::pow(d, n);
            for (int j = 0; j <= n; ++j, x *= ratio)
                val[j] = std::fmax(pu * val[j + 1] + pd * val[j], intrinsic(x, k, type));
        } else {
            for (int j = 0; j <= n; ++j) val[j] = pu * val[j + 1] + pd * val[j];
        }
        if (n == 2) for (int j = 0; j < 3; ++j) s2[j] = val[j];
        if (n == 1) for (int j = 0; j < 2; ++j) s1[j] = val[j];
    }
    TreeResult res{};
    res.steps = steps;
    res.price = val[0];
    const double su = s * u, sd = s * d;
    res.delta = (s1[1] - s1[0]) / (su - sd);
    const double suu = s * u * u, sud = s * u * d, sdd = s * d * d;
    const double du = (s2[2] - s2[1]) / (suu - sud), dd = (s2[1] - s2[0]) / (sud - sdd);
    res.gamma = (du - dd) / (0.5 * (suu - sdd));
    res.theta = (s2[1] - res.price) / (2.0 * dt);
    return res;
}

}  // namespace qf
