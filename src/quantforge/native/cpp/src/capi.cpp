// C ABI used by the Python wrapper (quantforge.native, via ctypes).
// Every function returns 0 on success, or a non-zero code with a message in qf_last_error().
// SPDX-License-Identifier: MIT
#include <algorithm>
#include <cstring>
#include <exception>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "quantforge/quantforge.hpp"

#if defined(_WIN32)
#define QF_API extern "C" __declspec(dllexport)
#else
#define QF_API extern "C" __attribute__((visibility("default")))
#endif

namespace {
thread_local std::string g_error;
qf::OptionType opt(int is_call) { return is_call ? qf::OptionType::Call : qf::OptionType::Put; }

// Split [0, n) over hardware threads for large vectorised calls.
template <class F>
void parallel_for(long long n, F f) {
    const long long min_chunk = 20000;
    int nt = static_cast<int>(std::max(1u, std::thread::hardware_concurrency()));
    nt = static_cast<int>(std::min<long long>(nt, std::max(1LL, n / min_chunk)));
    if (nt <= 1) { for (long long i = 0; i < n; ++i) f(i); return; }
    std::vector<std::thread> pool;
    std::exception_ptr err = nullptr;
    std::mutex m;
    for (int t = 0; t < nt; ++t)
        pool.emplace_back([&, t] {
            try {
                for (long long i = n * t / nt; i < n * (t + 1) / nt; ++i) f(i);
            } catch (...) {
                std::lock_guard<std::mutex> lock(m);
                if (!err) err = std::current_exception();
            }
        });
    for (auto& th : pool) th.join();
    if (err) std::rethrow_exception(err);
}

template <class F>
int guarded(F f) {
    try {
        f();
        return 0;
    } catch (const std::exception& e) {
        g_error = e.what();
        return 1;
    } catch (...) {
        g_error = "unknown C++ error";
        return 2;
    }
}
}  // namespace

QF_API const char* qf_version() { return qf::kVersion; }
QF_API const char* qf_last_error() { return g_error.c_str(); }

QF_API int qf_bs_price(const double* s, const double* k, const double* t, const double* r,
                       const double* v, const double* q, const int* is_call, long long n,
                       double* out) {
    return guarded([&] {
        parallel_for(n, [&](long long i) {
            out[i] = qf::bs_price(s[i], k[i], t[i], r[i], v[i], opt(is_call[i]), q[i]);
        });
    });
}

// out: n x 6 row-major (price, delta, gamma, vega, theta, rho)
QF_API int qf_bs_greeks(const double* s, const double* k, const double* t, const double* r,
                        const double* v, const double* q, const int* is_call, long long n,
                        double* out) {
    return guarded([&] {
        parallel_for(n, [&](long long i) {
            const auto g = qf::bs_greeks(s[i], k[i], t[i], r[i], v[i], opt(is_call[i]), q[i]);
            double* o = out + 6 * i;
            o[0] = g.price; o[1] = g.delta; o[2] = g.gamma; o[3] = g.vega; o[4] = g.theta;
            o[5] = g.rho;
        });
    });
}

QF_API int qf_implied_vol(const double* price, const double* s, const double* k, const double* t,
                          const double* r, const double* q, const int* is_call, long long n,
                          double* out) {
    return guarded([&] {
        parallel_for(n, [&](long long i) {
            out[i] = qf::implied_vol(price[i], s[i], k[i], t[i], r[i], opt(is_call[i]), q[i]);
        });
    });
}

// out: price, delta, gamma, theta, steps
QF_API int qf_binomial(double s, double k, double t, double r, double v, double q, int is_call,
                       int american, int steps, int lr, double* out) {
    return guarded([&] {
        const auto res = qf::binomial(s, k, t, r, v, opt(is_call), american != 0, q, steps,
                                      lr ? qf::TreeMethod::LR : qf::TreeMethod::CRR);
        out[0] = res.price; out[1] = res.delta; out[2] = res.gamma; out[3] = res.theta;
        out[4] = res.steps;
    });
}

// out: price, std_error, n_paths
QF_API int qf_mc_european(double s, double k, double t, double r, double v, double q, int is_call,
                          long long n_paths, int antithetic, int cv, unsigned long long seed,
                          int threads, double* out) {
    return guarded([&] {
        const auto res = qf::mc_european(s, k, t, r, v, opt(is_call), q, n_paths, antithetic != 0,
                                         cv != 0, seed, threads);
        out[0] = res.price; out[1] = res.std_error; out[2] = static_cast<double>(res.n_paths);
    });
}

QF_API int qf_mc_asian(double s, double k, double t, double r, double v, double q, int n_fixings,
                       int is_call, long long n_paths, int antithetic, int cv,
                       unsigned long long seed, int threads, double* out) {
    return guarded([&] {
        const auto res = qf::mc_asian(s, k, t, r, v, n_fixings, opt(is_call), q, n_paths,
                                      antithetic != 0, cv != 0, seed, threads);
        out[0] = res.price; out[1] = res.std_error; out[2] = static_cast<double>(res.n_paths);
    });
}

QF_API int qf_geometric_asian(double s, double k, double t, double r, double v, double q,
                              int n_fixings, int is_call, double* out) {
    return guarded([&] { out[0] = qf::geometric_asian(s, k, t, r, v, n_fixings, opt(is_call), q); });
}
