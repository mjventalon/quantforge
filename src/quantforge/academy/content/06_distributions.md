---
id: 6
level: 2
level_name: Risk & Statistics
title: Distributions and fat tails
minutes: 25
objectives:
  - Describe a return distribution with mean, standard deviation, skewness and kurtosis
  - Use the normal distribution and know its probabilities
  - Recognize fat tails in real market data and why they matter for risk
widgets: [normal_vs_real, distribution_surface_mini]
sources:
  - title: "18.S096 Topics in Mathematics with Applications in Finance — Lecture 3: Probability Theory"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "The Variation of Certain Speculative Prices, Journal of Business 36(4), 1963"
    by: "Benoit Mandelbrot (paper)"
    url: ""
quiz:
  - q: "Under a normal distribution, roughly what share of observations lies within ±2 standard deviations of the mean?"
    options: ["68%", "95%", "99.7%", "50%"]
    answer: 1
    why: "68% within ±1σ, about 95% within ±2σ (exactly 95.45%), 99.7% within ±3σ."
  - q: "Under a normal distribution, the probability of a move beyond ±3σ is about:"
    options: ["3%", "0.27%", "0.0001%", "10%"]
    answer: 1
    why: "2 × (1 − Φ(3)) = 0.27%. Real daily stock returns exceed ±3σ noticeably more often."
  - q: "Excess kurtosis above 0 means:"
    options: ["Thinner tails than normal", "Fatter tails and a sharper peak than normal", "The mean is negative", "Returns are independent"]
    answer: 1
    why: "Excess kurtosis = kurtosis − 3. Daily equity returns typically show large positive excess kurtosis."
  - q: "Negative skewness in returns means:"
    options: ["Large gains are more common than large losses", "The left tail (large losses) is longer", "Volatility is zero", "The distribution is symmetric"]
    answer: 1
    why: "Negative skew = a long left tail: occasional large losses."
  - q: "On 19 October 1987 the S&P 500 fell about 20% in one day. Under a normal model with ~1% daily volatility this would be roughly a:"
    options: ["2-sigma event", "5-sigma event", "20-sigma event", "Normal day"]
    answer: 2
    why: "20% / 1% ≈ 20 standard deviations — essentially impossible under normality, yet it happened. Hence fat tails."
  - q: "What is the practical consequence of fat tails for risk models?"
    options: ["Normal-based VaR tends to understate extreme losses", "Volatility is always overstated", "Correlations become zero", "None"]
    answer: 0
    why: "Normal models put too little probability on extreme moves; use historical, Student-t or Expected Shortfall measures as well."
---

## Four numbers that describe a distribution

| Moment | Formula | Meaning |
|---|---|---|
| Mean | $\bar R = \frac1N\sum R_t$ | Center |
| Standard deviation | $\sigma$ | Typical size of moves |
| Skewness | $\frac1N\sum\left(\frac{R_t-\bar R}{\sigma}\right)^3$ | Asymmetry (negative = long left tail) |
| Excess kurtosis | $\frac1N\sum\left(\frac{R_t-\bar R}{\sigma}\right)^4 - 3$ | Tail thickness (0 for a normal) |

## The normal distribution

The bell curve is fully described by its mean and standard deviation:

- about **68%** of outcomes within ±1σ,
- about **95%** within ±2σ,
- about **99.7%** within ±3σ — so a move beyond 3σ has probability **0.27%**.

It is the default assumption of many classic models (Markowitz, Black-Scholes, parametric
VaR) because it is mathematically convenient.

## Real returns have fat tails

Daily stock returns are **not** normal. They show **excess kurtosis** (many tiny moves, and
more extreme moves than the bell curve predicts) and often **negative skew** (crashes are
sharper than rallies). Mandelbrot documented this in commodity prices in 1963.

The 19 October 1987 crash — the S&P 500 fell about 20% in one day — was roughly a
**20-sigma** event for an index with ~1% daily volatility. Under a normal distribution the
probability is so small it should never happen in the history of the universe. It happened.

The widget below overlays the normal curve on real returns: look at the tails.

{{widget:normal_vs_real}}

## Distributions change over time

Volatility clusters (chapter 17): calm periods follow calm periods, storms follow storms.
The shape of the distribution is not fixed — the 3-D surface below shows how it widened in
real crises.

{{widget:distribution_surface_mini}}

## Summary

Mean, volatility, skew and kurtosis summarize a distribution. Markets have fatter tails than
the normal model: always check risk numbers with methods that respect the real data.
