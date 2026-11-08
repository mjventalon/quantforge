---
id: 7
level: 2
level_name: Risk & Statistics
title: Correlation, regression and beta
minutes: 25
objectives:
  - Compute and interpret covariance and correlation
  - Run a linear regression and read its coefficients, t-statistics and R²
  - Estimate a stock's beta against the market
widgets: [beta_scatter, rolling_correlation]
sources:
  - title: "18.S096 Topics in Mathematics with Applications in Finance — Lecture 6: Regression Analysis"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "Introductory Econometrics: A Modern Approach"
    by: "Jeffrey M. Wooldridge (textbook)"
    url: ""
quiz:
  - q: "A correlation of −0.8 between two assets means:"
    options: ["They tend to move in opposite directions", "They are unrelated", "One causes the other", "They have the same volatility"]
    answer: 0
    why: "Correlation ranges from −1 to +1; −0.8 is a strong tendency to move in opposite directions."
  - q: "Correlation = 0 implies:"
    options: ["The assets are independent", "No *linear* relationship, though a non-linear link may exist", "Both returns are zero", "Prices are equal"]
    answer: 1
    why: "Zero correlation only rules out a linear relationship."
  - q: "A stock has beta 1.5. If the market rises 2% (excess return), the regression predicts the stock's excess return around:"
    options: ["1.5%", "2%", "3%", "0.75%"]
    answer: 2
    why: "Predicted excess return ≈ β × market excess = 1.5 × 2% = 3% (plus alpha, plus noise)."
  - q: "Beta is computed as:"
    options: ["Cov(asset, market) / Var(market)", "Var(asset) / Var(market)", "Correlation × 100", "Mean(asset) / Mean(market)"]
    answer: 0
    why: "β = Cov(R_i, R_m) / Var(R_m) — the OLS slope of the asset on the market."
  - q: "R² = 0.25 in a regression of a stock on the market means:"
    options: ["The stock rises 25% with the market", "25% of the stock's return variance is explained by the market", "Beta is 0.25", "The regression is wrong"]
    answer: 1
    why: "R² is the share of variance explained; the remaining 75% is stock-specific."
  - q: "A coefficient with t-statistic 0.8 is:"
    options: ["Strongly significant", "Not statistically different from zero at usual levels", "Exactly zero", "Proof of causality"]
    answer: 1
    why: "|t| below about 2 means we cannot reject a true value of zero at the 5% level."
---

## Covariance and correlation

$$\text{Cov}(X,Y) = \frac1{N-1}\sum (X_t-\bar X)(Y_t-\bar Y), \qquad
\rho_{XY} = \frac{\text{Cov}(X,Y)}{\sigma_X\sigma_Y}\in[-1,1]$$

Correlation is unit-free: +1 move together perfectly, −1 perfectly opposite, 0 no **linear**
relation. **Correlation is not causation**, and it **changes over time** — the rolling
correlation widget shows it.

{{widget:rolling_correlation}}

## Linear regression (ordinary least squares)

We fit $y_t = \alpha + \beta x_t + \varepsilon_t$ by choosing $\alpha, \beta$ to minimize
$\sum \varepsilon_t^2$. The slope is

$$\hat\beta = \frac{\text{Cov}(x,y)}{\text{Var}(x)}$$

Read every regression with three numbers:

- the **coefficient** (effect size),
- its **t-statistic** = coefficient / standard error (|t| > ~2 ≈ significant at 5%),
- **R²** = share of the variance of $y$ explained by $x$.

## Beta

Regress a stock's excess return on the market's excess return:

$$R_i - r_f = \alpha_i + \beta_i (R_m - r_f) + \varepsilon_i$$

- **β = 1**: moves like the market. **β = 1.5**: amplifies market moves by 50%. **β = 0.5**:
  defensive.
- **α**: average return not explained by market exposure (chapter 10).
- **R²**: how much of the stock is "market" vs "company-specific".

{{widget:beta_scatter}}

## Pitfalls

Outliers can dominate a regression; relationships change across regimes; and a high R²
between two trending price series can be spurious — always regress **returns**, not prices
(chapter 18 explains why).

## Summary

Correlation measures co-movement; regression quantifies it with uncertainty; beta is the
regression slope of an asset on the market and the language of systematic risk.
