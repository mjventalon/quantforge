// Minimal example: price an option three ways.
//   c++ -std=c++17 -O2 -I../include price_option.cpp -o price_option -pthread && ./price_option
// SPDX-License-Identifier: MIT
#include <cstdio>

#include "quantforge/quantforge.hpp"

int main() {
    const double s = 100, k = 100, t = 0.5, r = 0.04, v = 0.25;
    const auto g = qf::bs_greeks(s, k, t, r, v, qf::OptionType::Call);
    const auto tree = qf::binomial(s, k, t, r, v, qf::OptionType::Call, false);
    const auto mc = qf::mc_european(s, k, t, r, v, qf::OptionType::Call, 0.0, 2'000'000);
    std::printf("Black-Scholes : %.6f  (delta %.4f, vega %.4f)\n", g.price, g.delta, g.vega);
    std::printf("Leisen-Reimer : %.6f  (%d steps)\n", tree.price, tree.steps);
    std::printf("Monte-Carlo   : %.6f  +/- %.6f (%lld paths)\n", mc.price, 1.96 * mc.std_error,
                mc.n_paths);
}
