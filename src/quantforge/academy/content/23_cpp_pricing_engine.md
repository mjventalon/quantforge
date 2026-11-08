---
id: 23
level: 7
level_name: Quant Programming
title: Build a pricing engine in C++ and call it from Python
minutes: 50
objectives:
  - Implement Black-Scholes, a binomial tree, Newton implied volatility and Monte-Carlo in C++
  - Verify a C++ implementation against a reference to 1e-10 and against textbook values
  - Understand how a compiled C++ library is called from Python and why results must be reproducible
widgets: [engine_benchmark, bs_sliders]
sources:
  - title: "C++ Design Patterns and Derivatives Pricing, 2nd ed. (2008)"
    by: "Mark S. Joshi (book)"
    url: ""
  - title: "Monte Carlo Methods in Financial Engineering (2003)"
    by: "Paul Glasserman (book)"
    url: ""
  - title: "ctypes — A foreign function library for Python"
    by: "Python Software Foundation"
    url: "https://docs.python.org/3/library/ctypes.html"
  - title: "Pseudorandom number generation (<random>)"
    by: "cppreference.com"
    url: "https://en.cppreference.com/w/cpp/numeric/random"
  - title: "6.S096 Introduction to C and C++ — Lecture 5: classes and templates"
    by: "MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/6-s096-introduction-to-c-and-c-january-iap-2013/"
quiz:
  - q: "Why use std::erfc to compute the normal CDF, N(x) = ½·erfc(−x/√2)?"
    options: ["It is the only function in <cmath>", "It stays accurate far in the tails, where 1 − something would round to 0", "It is random", "It is faster than addition"]
    answer: 1
    why: "Deep out-of-the-money options need N(−8) ≈ 6e−16, which a naive 1 − N(8) loses entirely."
  - q: "Newton's method for implied volatility updates σ by:"
    options: ["σ − (price(σ) − market)/vega(σ)", "σ + vega", "σ × 2", "market / price"]
    answer: 0
    why: "Vega is the derivative of the price with respect to σ, so Newton divides the error by it."
  - q: "In a one-pass Monte-Carlo you accumulate Σpayoff and Σpayoff². Why the second sum?"
    options: ["To make the price larger", "To compute the variance and therefore the standard error", "It is required by the compiler", "To remove antithetic pairs"]
    answer: 1
    why: "Var = E[X²] − E[X]²; the standard error is √(Var/n)."
  - q: "quantforge's C++ Monte-Carlo gives the same result with 1 or 8 threads because:"
    options: ["Threads are ignored", "Paths are split into fixed blocks, each with its own seeded random stream, and summed in a fixed order", "It uses no random numbers", "Luck"]
    answer: 1
    why: "Reproducibility must not depend on the machine — otherwise results cannot be audited."
  - q: "How should you validate a new C++ pricer?"
    options: ["If it compiles, it is right", "Compare with textbook values, identities (put-call parity) and a trusted reference implementation", "Check it is fast", "Ask a colleague to read it"]
    answer: 1
    why: "Compiling only proves the syntax; correctness needs independent checks."
  - q: "What does `extern \"C\"` on a C++ function exported to Python achieve?"
    options: ["Makes it run in C", "Gives it a plain, unmangled symbol name that ctypes can find", "Makes it faster", "Converts it to Python"]
    answer: 1
    why: "C++ mangles names to support overloading; the C ABI keeps a simple, stable name."
---

## The plan

In this chapter you build, piece by piece, the core of a real pricing engine — the same design as
quantforge's own C++ engine:

| Piece | What it does | Checked against |
|---|---|---|
| `norm_cdf` | the normal distribution N(x) | known values, deep tails |
| `bs_call`, `bs_put` | Black-Scholes closed form | Hull Example 15.6, put-call parity |
| `crr_put` | American options on a tree | Hull Example 21.1 (≈ 4.28) |
| `implied_vol` | Newton's method on vega | round trips |
| `mc_call` | Monte-Carlo with a standard error | Black-Scholes within 4 standard errors |

## 1. Accuracy first: the normal CDF

The textbook writes N(x) = ½(1 + erf(x/√2)). In code, prefer **N(x) = ½·erfc(−x/√2)**: for very
negative x, `1 + erf(...)` subtracts two nearly equal numbers and loses every digit, while `erfc`
stays accurate. This matters for deep out-of-the-money options and for risk on tail events.

## 2. From formula to function

```cpp
double bs_call(double S, double K, double T, double r, double sigma) {
    const double sq = sigma * std::sqrt(T);
    const double d1 = (std::log(S / K) + (r + 0.5 * sigma * sigma) * T) / sq;
    const double d2 = d1 - sq;
    return S * norm_cdf(d1) - K * std::exp(-r * T) * norm_cdf(d2);
}
```

`const` documents that a value never changes and lets the compiler optimise. Notice that we compute
`σ√T` once — engines are full of such small savings.

{{widget:bs_sliders}}

## 3. Monte-Carlo in one pass

```cpp
std::mt19937_64 gen(seed);                     // 64-bit Mersenne Twister
std::normal_distribution<double> z(0.0, 1.0);
double sum = 0.0, sumsq = 0.0;
for (long i = 0; i < n; ++i) {
    double st  = S * std::exp(drift + vol * z(gen));
    double pay = disc * std::max(st - K, 0.0);
    sum += pay;  sumsq += pay * pay;
}
double price = sum / n;
double se = std::sqrt((sumsq / n - price * price) * n / (n - 1.0) / n);
```

Storing a million payoffs is unnecessary: two running sums give the price **and** its standard
error. A price without an error bar is not a Monte-Carlo result.

**Reproducibility.** `std::normal_distribution` is implemented differently by different compilers
(libstdc++ vs libc++), so the same seed can give different numbers on Linux and macOS. quantforge's
engine therefore ships its **own** generator (xoshiro256\*\*) and Box-Muller transform, and splits
the paths into fixed blocks so the answer never depends on the number of threads.

## 4. Calling C++ from Python

A compiled library exposes functions with a plain C interface:

```cpp
extern "C" int qf_bs_price(const double* s, const double* k, /* ... */ long long n, double* out);
```

Python loads it with `ctypes` and passes pointers to NumPy arrays — no copy. quantforge wraps
this in `quantforge.native`, which you can use directly:

```python
from quantforge import native
native.build()                                   # once: compiles the C++ sources
native.bs_price(42, 40, 0.5, 0.10, 0.20, "call") # 4.759422392871532
native.mc_european(100, 100, 1, 0.05, 0.2, n_paths=4_000_000)
```

Every function is tested to agree with the Python implementation to about 1e-10 (the test file is
`tests/test_native.py`).

{{widget:engine_benchmark}}

## 5. Validation checklist for any pricer

1. Textbook values (Hull, Wilmott) to the published precision.
2. Identities: put-call parity, American ≥ European, prices within no-arbitrage bounds.
3. Convergence: tree → Black-Scholes as steps grow; Monte-Carlo error ∝ 1/√N.
4. A second, independent implementation — the one you write in Python, or quantforge's.

## Your turn

Write the Monte-Carlo pricer and the Newton implied-vol solver below. When everything passes you
have written, in C++, the core of what every derivatives desk runs.
