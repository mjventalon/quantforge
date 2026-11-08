// quantforge C++ core — common definitions.
// Header-only, C++17, no dependencies beyond the standard library.
// SPDX-License-Identifier: MIT
#pragma once

#include <cmath>
#include <stdexcept>
#include <string>

namespace qf {

enum class OptionType { Call, Put };

inline constexpr double kSqrt2 = 1.41421356237309504880;
inline constexpr double kInvSqrt2Pi = 0.39894228040143267794;

/// Standard normal probability density.
inline double norm_pdf(double x) noexcept { return kInvSqrt2Pi * std::exp(-0.5 * x * x); }

/// Standard normal cumulative distribution, accurate to machine precision in both tails
/// (uses erfc, so N(-10) is not rounded to zero).
inline double norm_cdf(double x) noexcept { return 0.5 * std::erfc(-x / kSqrt2); }

/// Payoff at expiry.
inline double intrinsic(double spot, double strike, OptionType type) noexcept {
    return type == OptionType::Call ? std::fmax(spot - strike, 0.0)
                                    : std::fmax(strike - spot, 0.0);
}

inline void require_positive(double v, const char* what) {
    if (!(v > 0.0)) throw std::invalid_argument(std::string(what) + " must be strictly positive");
}

}  // namespace qf
