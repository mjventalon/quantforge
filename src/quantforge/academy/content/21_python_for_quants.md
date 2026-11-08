---
id: 21
level: 7
level_name: Quant Programming
title: Python for quants — arrays, functions and tests
minutes: 40
objectives:
  - Write small, pure functions that do one calculation and can be tested
  - Replace slow Python loops by vectorised NumPy operations
  - Check your own code with assert-based tests, the way professional libraries do
widgets: [vectorization_race]
sources:
  - title: "6.0001 Introduction to Computer Science and Programming in Python (Fall 2016)"
    by: "MIT OpenCourseWare (Ana Bell, Eric Grimson, John Guttag)"
    url: "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/"
  - title: "The Python Tutorial"
    by: "Python Software Foundation"
    url: "https://docs.python.org/3/tutorial/"
  - title: "NumPy: the absolute basics for beginners"
    by: "NumPy developers"
    url: "https://numpy.org/doc/stable/user/absolute_beginners.html"
  - title: "Python for Data Analysis, 3rd ed. (2022)"
    by: "Wes McKinney (book)"
    url: ""
quiz:
  - q: "Why do quants prefer small 'pure' functions (same input → same output, no hidden state)?"
    options: ["They run on GPUs automatically", "They are easy to test and to reuse", "Python requires it", "They use less memory"]
    answer: 1
    why: "A pure function can be checked in isolation with a few known inputs and outputs."
  - q: "`p[1:] / p[:-1] - 1` on a NumPy price array computes:"
    options: ["Log returns", "Simple daily returns, without a loop", "The moving average", "The maximum drawdown"]
    answer: 1
    why: "Each price is divided by the previous one, element by element, in compiled code."
  - q: "Why is vectorised NumPy code usually much faster than a Python for-loop?"
    options: ["It skips some numbers", "The loop runs inside compiled C code instead of the Python interpreter", "It uses less precise numbers", "It runs on another computer"]
    answer: 1
    why: "The interpreter overhead is paid once per array, not once per element."
  - q: "What does `assert abs(x - 4.7594) < 1e-4` do if the condition is false?"
    options: ["Prints a warning and continues", "Raises an AssertionError — the test fails", "Rounds x", "Nothing"]
    answer: 1
    why: "assert stops the program with an AssertionError when its condition is false."
  - q: "Why compare floating-point results with a tolerance instead of `==`?"
    options: ["Python cannot compare floats", "Tiny rounding differences make exact equality unreliable", "Tolerances make code faster", "== only works for strings"]
    answer: 1
    why: "0.1 + 0.2 is 0.30000000000000004 in binary floating point."
  - q: "`np.random.default_rng(42)` is used in tests because:"
    options: ["42 gives better random numbers", "A fixed seed makes the 'random' results reproducible", "It is faster", "It removes fat tails"]
    answer: 1
    why: "Same seed, same draws — so a test gives the same answer every run."
---

## Why programming is part of quant finance

Every model in this Academy — Black-Scholes, GARCH, VaR — is, in the end, **code**. Spreadsheets
break down when you need a million Monte-Carlo paths, ten years of daily data for 500 stocks, or a
result someone else can reproduce. That is why quant teams write Python for research and **C++**
for the parts that must be extremely fast.

You already know the finance. This level teaches you to **rewrite the formulas yourself**, so that
you understand them completely and can check any library — including quantforge.

## 1. Functions: one calculation, clearly named

```python
def simple_return(p0, p1):
    """Percentage change from p0 to p1, as a decimal."""
    return p1 / p0 - 1
```

A good function has a precise name, documented inputs and outputs, and **no hidden state**: give it
the same numbers and it always gives the same answer. That property is what makes it *testable*.

## 2. NumPy arrays: think in whole columns

Python loops are flexible but slow, because the interpreter does work for **every** element.
NumPy stores numbers in one contiguous block of memory and runs the loop in compiled C:

```python
import numpy as np
p = np.array([100.0, 101.5, 99.8, 102.3])
r = p[1:] / p[:-1] - 1          # all daily returns at once
vol = r.std(ddof=1) * np.sqrt(252)
```

Useful building blocks: slicing `p[1:]`, `np.diff`, `np.log`, `np.cumprod`, `np.maximum.accumulate`,
boolean masks `r[r < 0]`, and the matrix product `w @ cov @ w`.

{{widget:vectorization_race}}

## 3. Tests: prove your code is right

Professionals never trust a formula they have not checked. Three kinds of checks catch most errors:

1. **Known values** — Hull's call price 4.7594 for S=42, K=40, T=0.5, r=10 %, σ=20 %.
2. **Identities** — put-call parity, log returns that add up, weights that sum to one.
3. **Limits and comparisons** — zero volatility, deep in-the-money options, an American option
   worth at least the European one.

```python
def test_simple_return():
    assert abs(simple_return(100, 110) - 0.10) < 1e-12
    assert simple_return(50, 40) < 0
```

The quantforge library itself has more than 200 such tests, run automatically on every change.

## 4. Floating point: why `==` is dangerous

Computers store numbers in binary, so `0.1 + 0.2 == 0.3` is **False**. Always compare with a
tolerance: `abs(a - b) < 1e-12` (or `math.isclose`). Choose the tolerance from the problem — 1e-12
for a closed formula, *a few standard errors* for a Monte-Carlo estimate.

## Your turn

Below are coding exercises: the editor starts with a skeleton, you **rewrite the function**, and
the grader runs real tests. Then go back to earlier chapters — each one has its own "Rewrite it
yourself" exercises (returns, volatility, beta, bonds, Black-Scholes, trees, Monte-Carlo, VaR…).
