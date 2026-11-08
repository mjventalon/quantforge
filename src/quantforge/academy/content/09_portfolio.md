---
id: 9
level: 3
level_name: Portfolio Construction
title: Modern Portfolio Theory and the efficient frontier
minutes: 30
objectives:
  - Build the efficient frontier from expected returns and a covariance matrix
  - Compute and interpret the Sharpe ratio
  - Explain the minimum-variance and maximum-Sharpe portfolios and their weaknesses
widgets: [frontier_builder]
sources:
  - title: "Portfolio Selection, Journal of Finance 7(1), 1952"
    by: "Harry Markowitz (paper — Nobel Prize 1990)"
    url: ""
  - title: "18.S096 — Lecture 14: Portfolio Theory"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "15.401 Finance Theory I — Portfolio Theory"
    by: "Andrew W. Lo — MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/"
quiz:
  - q: "A portfolio returns 10% a year with 15% volatility; the risk-free rate is 4%. Its Sharpe ratio is:"
    options: ["0.67", "0.40", "0.27", "1.50"]
    answer: 1
    why: "(10% − 4%) / 15% = 0.40."
  - q: "The efficient frontier is the set of portfolios that:"
    options: ["Have zero risk", "Give the highest expected return for each level of risk", "Hold one asset each", "Have equal weights"]
    answer: 1
    why: "Any portfolio below the frontier is dominated: another portfolio has more return for the same risk."
  - q: "The tangency (maximum-Sharpe) portfolio is where:"
    options: ["The frontier meets the y-axis", "A line from the risk-free rate touches the frontier", "Volatility is maximum", "All weights are equal"]
    answer: 1
    why: "The capital market line from r_f is tangent to the frontier at the max-Sharpe portfolio."
  - q: "Why do practitioners distrust raw mean-variance weights?"
    options: ["The maths is wrong", "Weights are extremely sensitive to errors in expected returns", "It ignores volatility", "It only works for bonds"]
    answer: 1
    why: "Small changes in estimated means swing the optimal weights a lot ('error maximization'). Shrinkage, constraints and Black-Litterman help."
  - q: "The minimum-variance portfolio needs which input?"
    options: ["Expected returns only", "The covariance matrix only", "Neither", "Option prices"]
    answer: 1
    why: "It minimizes w'Σw and does not use expected returns — one reason it is more robust out of sample."
  - q: "Risk parity sets weights so that:"
    options: ["Each asset has the same weight", "Each asset contributes the same share of portfolio risk", "Return is maximized", "Bonds are excluded"]
    answer: 1
    why: "Risk contribution_i = w_i (Σw)_i / σ_p²; risk parity equalizes them."
---

## Inputs

For $n$ assets you need:

- expected returns $\mu$ (a vector),
- the covariance matrix $\Sigma$ (volatilities and correlations).

A portfolio with weights $w$ (summing to 1) has

$$\mu_p = w^\top\mu, \qquad \sigma_p = \sqrt{w^\top\Sigma w}$$

## The efficient frontier

For each target return, find the weights with the **lowest** volatility. Plotting these
portfolios gives a curve — the **efficient frontier**. Everything below it is inefficient.

Two special portfolios:

- **Minimum variance** — the leftmost point. Uses only $\Sigma$.
- **Maximum Sharpe (tangency)** — where a line from the risk-free rate touches the frontier:

$$\text{Sharpe} = \frac{\mu_p - r_f}{\sigma_p}$$

**Example.** 10% return, 15% volatility, $r_f$ = 4% → Sharpe = 0.40.

Mixing the tangency portfolio with cash gives the **capital market line**: every investor,
whatever their risk appetite, should hold that same risky mix (in theory) and adjust only
the cash proportion.

{{widget:frontier_builder}}

## Why the textbook answer breaks in practice

Expected returns are estimated with large errors, and the optimizer *maximizes* those errors:
it piles into assets that happened to do well in the sample. Professionals therefore use:

- **covariance shrinkage** (Ledoit-Wolf) — the default in quantforge,
- **weight bounds** (e.g. max 30% per asset),
- **minimum-variance** or **risk parity** (no expected returns needed),
- **Black-Litterman** — start from market-implied returns, add your views with confidence.

And they test allocation rules **out of sample** (walk-forward, chapter 11).

## Summary

Diversification math produces a frontier of best risk/return trade-offs. Max-Sharpe is the
theory's answer; robust estimation and honest testing make it usable.
