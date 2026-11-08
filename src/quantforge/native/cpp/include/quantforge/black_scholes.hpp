// Black-Scholes-Merton closed forms, Greeks and implied volatility.
// Conventions match quantforge.pricing (Python): maturity in years, continuous rates and
// dividend yield, theta per year, vega and rho per 1.00 change (not per 1%).
// SPDX-License-Identifier: MIT
#pragma once

#include <cmath>
#include <limits>

#include "core.hpp"

namespace qf {

struct Greeks {
    double price, delta, gamma, vega, theta, rho;
};

/// d1 and d2 of Black-Scholes-Merton.
inline void bs_d1_d2(double s, double k, double t, double r, double v, double q, double& d1,
                     double& d2) {
    require_positive(s, "spot");
    require_positive(k, "strike");
    require_positive(t, "maturity");
    require_positive(v, "volatility");
    const double vst = v * std::sqrt(t);
    d1 = (std::log(s / k) + (r - q + 0.5 * v * v) * t) / vst;
    d2 = d1 - vst;
}

/// European option price.
inline double bs_price(double s, double k, double t, double r, double v, OptionType type,
                       double q = 0.0) {
    double d1, d2;
    bs_d1_d2(s, k, t, r, v, q, d1, d2);
    const double dr = std::exp(-r * t), dq = std::exp(-q * t);
    return type == OptionType::Call ? s * dq * norm_cdf(d1) - k * dr * norm_cdf(d2)
                                    : k * dr * norm_cdf(-d2) - s * dq * norm_cdf(-d1);
}

/// Price and all first-order Greeks (plus gamma) in one pass.
inline Greeks bs_greeks(double s, double k, double t, double r, double v, OptionType type,
                        double q = 0.0) {
    double d1, d2;
    bs_d1_d2(s, k, t, r, v, q, d1, d2);
    const double dr = std::exp(-r * t), dq = std::exp(-q * t), sq = std::sqrt(t);
    const double pdf = norm_pdf(d1);
    Greeks g{};
    g.gamma = dq * pdf / (s * v * sq);
    g.vega = s * dq * pdf * sq;
    if (type == OptionType::Call) {
        g.price = s * dq * norm_cdf(d1) - k * dr * norm_cdf(d2);
        g.delta = dq * norm_cdf(d1);
        g.theta = -s * dq * pdf * v / (2 * sq) - r * k * dr * norm_cdf(d2) +
                  q * s * dq * norm_cdf(d1);
        g.rho = k * t * dr * norm_cdf(d2);
    } else {
        g.price = k * dr * norm_cdf(-d2) - s * dq * norm_cdf(-d1);
        g.delta = -dq * norm_cdf(-d1);
        g.theta = -s * dq * pdf * v / (2 * sq) + r * k * dr * norm_cdf(-d2) -
                  q * s * dq * norm_cdf(-d1);
        g.rho = -k * t * dr * norm_cdf(-d2);
    }
    return g;
}

/// Implied volatility by safeguarded Newton (falls back to bisection when a Newton step
/// leaves the bracket). Returns NaN when the price violates no-arbitrage bounds.
inline double implied_vol(double price, double s, double k, double t, double r, OptionType type,
                          double q = 0.0, double tol = 1e-10, int max_iter = 200) {
    const double nan = std::numeric_limits<double>::quiet_NaN();
    const double dr = std::exp(-r * t), dq = std::exp(-q * t);
    const double lower = type == OptionType::Call ? std::fmax(s * dq - k * dr, 0.0)
                                                  : std::fmax(k * dr - s * dq, 0.0);
    const double upper = type == OptionType::Call ? s * dq : k * dr;
    if (!(price > lower) || !(price < upper)) return nan;
    double lo = 1e-6, hi = 10.0;
    if (bs_price(s, k, t, r, hi, type, q) < price) return nan;
    double v = 0.3;
    for (int i = 0; i < max_iter; ++i) {
        const Greeks g = bs_greeks(s, k, t, r, v, type, q);
        const double diff = g.price - price;
        if (std::fabs(diff) < tol) return v;
        if (diff > 0) hi = v; else lo = v;
        double next = g.vega > 1e-12 ? v - diff / g.vega : 0.5 * (lo + hi);
        if (!(next > lo && next < hi)) next = 0.5 * (lo + hi);
        if (std::fabs(next - v) < 1e-14) return next;
        v = next;
    }
    return v;
}

}  // namespace qf
