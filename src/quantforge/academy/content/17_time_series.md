---
id: 17
level: 5
level_name: Advanced Risk & Econometrics
title: Time series — stationarity, ARMA and GARCH
minutes: 35
objectives:
  - Test for stationarity (ADF) and read ACF/PACF plots
  - Fit and forecast ARMA models with honest intervals
  - Model volatility clustering with GARCH and compute its long-run level and half-life
widgets: [acf_live, garch_live]
sources:
  - title: "18.S096 — Lectures 8, 11, 12: Time Series Analysis I–III; Lecture 9: Volatility Modeling"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "Autoregressive Conditional Heteroscedasticity…, Econometrica 50(4), 1982"
    by: "Robert F. Engle (paper — Nobel Prize 2003)"
    url: ""
  - title: "Generalized Autoregressive Conditional Heteroskedasticity, Journal of Econometrics 31(3), 1986"
    by: "Tim Bollerslev (paper)"
    url: ""
  - title: "Time Series Analysis (1994)"
    by: "James D. Hamilton (textbook)"
    url: ""
quiz:
  - q: "A time series is (weakly) stationary if:"
    options: ["It never changes", "Its mean, variance and autocovariances do not depend on time", "It trends upward", "It is normally distributed"]
    answer: 1
    why: "Stationarity means stable statistical properties; prices usually fail, returns usually pass."
  - q: "The ADF test on a stock's log price typically:"
    options: ["Rejects a unit root", "Fails to reject a unit root (non-stationary)", "Proves predictability", "Measures volatility"]
    answer: 1
    why: "Prices behave like random walks; returns are stationary."
  - q: "Squared daily returns show strong positive autocorrelation. This is evidence of:"
    options: ["Predictable returns", "Volatility clustering (ARCH effects)", "Mean reversion in prices", "Data errors"]
    answer: 1
    why: "Big moves follow big moves — the motivation for GARCH."
  - q: "In GARCH(1,1), σ²_t = ω + α ε²_{t−1} + β σ²_{t−1}, the persistence is:"
    options: ["ω", "α + β", "α − β", "β / α"]
    answer: 1
    why: "α + β close to 1 means shocks to volatility decay slowly."
  - q: "With persistence 0.98, the half-life of a volatility shock is about:"
    options: ["2 days", "34 days", "98 days", "500 days"]
    answer: 1
    why: "ln(0.5) / ln(0.98) = 34.3 days."
  - q: "The long-run (unconditional) variance of a stationary GARCH(1,1) is:"
    options: ["ω", "ω / (1 − α − β)", "α + β", "σ²_0"]
    answer: 1
    why: "Volatility forecasts converge to this level as the horizon grows."
  - q: "An AR(1) with coefficient φ = 0.7: the theoretical autocorrelation at lag 2 is:"
    options: ["0.7", "0.49", "1.4", "0.35"]
    answer: 1
    why: "ρ_k = φ^k → 0.7² = 0.49."
---

## Stationarity

A series is (weakly) **stationary** when its mean, variance and autocorrelations do not change
over time. Statistical models assume it. **Prices are not stationary** (they wander like a
random walk); **returns usually are**. The **Augmented Dickey-Fuller** test checks for a unit
root: rejecting it (statistic below the critical value) means stationary.

## Autocorrelation

The **ACF** at lag $k$ is the correlation of the series with itself $k$ periods earlier; the
**PACF** removes the effect of intermediate lags. Rules of thumb: an AR($p$) process has a
PACF that cuts off after lag $p$; an MA($q$) has an ACF that cuts off after $q$.

Daily stock returns show almost no autocorrelation (hard to predict), but **squared returns**
are strongly autocorrelated: **volatility clusters**.

{{widget:acf_live}}

## ARMA models for the mean

$$y_t = c + \sum_{i=1}^p \phi_i y_{t-i} + \varepsilon_t + \sum_{j=1}^q \theta_j\varepsilon_{t-j}$$

Choose $(p, q)$ by information criteria (AIC/BIC), check residuals with Ljung-Box, and always
report forecast **intervals**. For AR(1) with $\phi = 0.7$ the autocorrelations decay as
$0.7, 0.49, 0.343, \dots$

## GARCH models for volatility

Engle (1982) and Bollerslev (1986):

$$r_t = \mu + \varepsilon_t,\quad \varepsilon_t = \sigma_t z_t,\quad
\sigma_t^2 = \omega + \alpha\,\varepsilon_{t-1}^2 + \beta\,\sigma_{t-1}^2$$

- **Persistence** $\alpha + \beta$ (typically 0.95–0.99 for equities),
- **long-run variance** $\omega/(1-\alpha-\beta)$,
- **half-life** $\ln 0.5 / \ln(\alpha+\beta)$ — with 0.98, about **34 days**.

**GJR-GARCH** adds $\gamma\,\varepsilon_{t-1}^2\mathbb 1_{\varepsilon_{t-1}<0}$: bad news raises
volatility more than good news (leverage effect). **Student-t** innovations capture fat tails.
quantforge's estimator is validated against the `arch` library.

{{widget:garch_live}}

## Summary

Model returns, not prices. Returns are nearly unpredictable in direction but strongly
predictable in volatility — GARCH turns that into forecasts you can compare with option
implied vol and use in risk management.
