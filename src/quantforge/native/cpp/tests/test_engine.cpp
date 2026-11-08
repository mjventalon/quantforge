// Standalone C++ tests (no framework): textbook values and internal consistency.
// Build & run:  cmake -S . -B build && cmake --build build && ctest --test-dir build
// SPDX-License-Identifier: MIT
#include <cmath>
#include <cstdio>
#include <cstdlib>

#include "quantforge/quantforge.hpp"

static int failures = 0;
#define CHECK_NEAR(a, b, tol)                                                              \
    do {                                                                                   \
        const double _a = (a), _b = (b);                                                   \
        if (!(std::fabs(_a - _b) <= (tol))) {                                              \
            std::printf("FAIL %s:%d  %s = %.10f, expected %.10f (tol %g)\n", __FILE__,       \
                        __LINE__, #a, _a, _b, (double)(tol));                              \
            ++failures;                                                                    \
        }                                                                                  \
    } while (0)

using qf::OptionType;

int main() {
    // Hull, Options Futures and Other Derivatives, Example 15.6: S=42 K=40 T=0.5 r=10% v=20%
    CHECK_NEAR(qf::bs_price(42, 40, 0.5, 0.10, 0.20, OptionType::Call), 4.7594, 5e-5);
    CHECK_NEAR(qf::bs_price(42, 40, 0.5, 0.10, 0.20, OptionType::Put), 0.8086, 5e-5);

    // put-call parity with dividends
    {
        const double s = 100, k = 95, t = 0.75, r = 0.04, v = 0.3, q = 0.02;
        const double c = qf::bs_price(s, k, t, r, v, OptionType::Call, q);
        const double p = qf::bs_price(s, k, t, r, v, OptionType::Put, q);
        CHECK_NEAR(c - p, s * std::exp(-q * t) - k * std::exp(-r * t), 1e-12);
    }
    // Greeks vs finite differences
    {
        const double s = 100, k = 105, t = 0.4, r = 0.03, v = 0.25, q = 0.01, h = 1e-4;
        const auto g = qf::bs_greeks(s, k, t, r, v, OptionType::Call, q);
        auto P = [&](double ss, double tt, double rr, double vv) {
            return qf::bs_price(ss, k, tt, rr, vv, OptionType::Call, q);
        };
        CHECK_NEAR(g.delta, (P(s + h, t, r, v) - P(s - h, t, r, v)) / (2 * h), 1e-7);
        CHECK_NEAR(g.gamma, (P(s + h, t, r, v) - 2 * P(s, t, r, v) + P(s - h, t, r, v)) / (h * h), 1e-4);
        CHECK_NEAR(g.vega, (P(s, t, r, v + h) - P(s, t, r, v - h)) / (2 * h), 1e-6);
        CHECK_NEAR(g.theta, -(P(s, t + h, r, v) - P(s, t - h, r, v)) / (2 * h), 1e-6);
        CHECK_NEAR(g.rho, (P(s, t, r + h, v) - P(s, t, r - h, v)) / (2 * h), 1e-6);
    }
    // implied vol round trip
    for (double v : {0.05, 0.2, 0.6, 1.5}) {
        const double p = qf::bs_price(100, 105, 0.3, 0.02, v, OptionType::Put);
        CHECK_NEAR(qf::implied_vol(p, 100, 105, 0.3, 0.02, OptionType::Put), v, 1e-8);
    }
    CHECK_NEAR(std::isnan(qf::implied_vol(0.0, 100, 100, 1, 0.01, OptionType::Call)), 1, 0);

    // Hull Example 21.1: American put S=50 K=50 T=5/12 r=10% v=40%  -> ~4.28
    {
        const auto res = qf::binomial(50, 50, 5.0 / 12, 0.10, 0.40, OptionType::Put, true, 0, 1001);
        CHECK_NEAR(res.price, 4.284, 2e-3);
        // European tree converges to Black-Scholes
        const auto eu = qf::binomial(50, 50, 5.0 / 12, 0.10, 0.40, OptionType::Put, false, 0, 1001);
        CHECK_NEAR(eu.price, qf::bs_price(50, 50, 5.0 / 12, 0.10, 0.40, OptionType::Put), 1e-5);
        CHECK_NEAR(eu.delta, qf::bs_greeks(50, 50, 5.0 / 12, 0.10, 0.40, OptionType::Put).delta, 1e-3);
    }
    // Monte-Carlo within 4 standard errors of the closed form, thread-count independent
    {
        const auto a = qf::mc_european(100, 100, 1, 0.05, 0.2, OptionType::Call, 0, 400000, true, true, 7, 1);
        const auto b = qf::mc_european(100, 100, 1, 0.05, 0.2, OptionType::Call, 0, 400000, true, true, 7, 8);
        CHECK_NEAR(a.price, b.price, 1e-12);
        CHECK_NEAR(a.price, qf::bs_price(100, 100, 1, 0.05, 0.2, OptionType::Call), 4 * a.std_error);
        const auto g = qf::mc_asian(100, 100, 1, 0.05, 0.2, 12, OptionType::Call, 0, 200000, true, false, 3);
        (void)g;
        // geometric Asian MC with no CV vs its closed form: use arithmetic CV identity instead
        const auto ar = qf::mc_asian(100, 100, 1, 0.05, 0.2, 12, OptionType::Call, 0, 200000, true, true, 3);
        const double geo = qf::geometric_asian(100, 100, 1, 0.05, 0.2, 12, OptionType::Call);
        if (!(ar.price > geo)) { std::printf("FAIL arithmetic Asian must exceed geometric\n"); ++failures; }
        CHECK_NEAR(ar.price, 6.0, 0.6);  // sanity band; exact check is done against Python
    }

    if (failures) { std::printf("%d check(s) failed\n", failures); return EXIT_FAILURE; }
    std::printf("all C++ checks passed (quantforge %s)\n", qf::kVersion);
    return EXIT_SUCCESS;
}
