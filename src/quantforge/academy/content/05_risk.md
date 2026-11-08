---
id: 5
level: 2
level_name: Risk & Statistics
title: Risk — volatility, drawdowns and diversification
minutes: 25
objectives:
  - Measure volatility and maximum drawdown
  - Compute the volatility of a two-asset portfolio
  - Explain why diversification reduces risk without necessarily reducing return
widgets: [drawdown_explorer, two_asset_risk]
sources:
  - title: "What is Risk? — Investing Basics"
    by: "U.S. Securities and Exchange Commission (Investor.gov)"
    url: "https://www.investor.gov/introduction-investing"
  - title: "15.401 Finance Theory I — Portfolio Theory (Recitation 6)"
    by: "Andrew W. Lo — MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/"
  - title: "Portfolio Selection, Journal of Finance 7(1), 1952"
    by: "Harry Markowitz (paper)"
    url: ""
quiz:
  - q: "A portfolio falls 50%. What gain is needed to get back to the starting value?"
    options: ["50%", "75%", "100%", "150%"]
    answer: 2
    why: "0.5 × (1 + g) = 1 → g = 100%."
  - q: "Volatility in finance usually means:"
    options: ["The average return", "The standard deviation of returns", "The biggest loss ever", "Trading volume"]
    answer: 1
    why: "Volatility is the standard deviation of returns, usually annualized."
  - q: "Two assets, each with 20% volatility, correlation 0.3, held 50/50. Portfolio volatility is closest to:"
    options: ["20%", "16.1%", "10%", "28%"]
    answer: 1
    why: "σ² = 0.25·0.04 + 0.25·0.04 + 2·0.25·0.3·0.04 = 0.026 → σ = 16.1%."
  - q: "With correlation exactly +1 in the previous setup, portfolio volatility would be:"
    options: ["0%", "10%", "20%", "28.3%"]
    answer: 2
    why: "Perfectly correlated assets give no diversification: σ = 0.5·20% + 0.5·20% = 20%."
  - q: "Maximum drawdown measures:"
    options: ["The worst single-day loss", "The largest peak-to-trough fall of the value", "Average volatility", "The number of losing days"]
    answer: 1
    why: "Max drawdown = min over time of (value / running peak − 1)."
  - q: "Which risk can diversification across many stocks NOT remove?"
    options: ["Company-specific risk", "Market (systematic) risk", "A single CEO scandal", "One factory fire"]
    answer: 1
    why: "Idiosyncratic risk diversifies away; market-wide risk affects all stocks and remains."
---

## Two ways to see risk

**Volatility** — how much returns jump around:

$$\sigma = \sqrt{\frac{1}{N-1}\sum_{t=1}^{N}(R_t - \bar R)^2}, \qquad \sigma_{annual} = \sigma_{daily}\sqrt{252}$$

**Drawdown** — how far you are below your previous peak:

$$DD_t = \frac{V_t}{\max_{s\le t} V_s} - 1, \qquad \text{MaxDD} = \min_t DD_t$$

Volatility treats up and down moves alike; drawdown captures the pain an investor actually
lives through. Because losses compound asymmetrically (chapter 3), a −50% drawdown requires
+100% to recover; −20% requires +25%.

{{widget:drawdown_explorer}}

## Diversification: the only free lunch

For two assets with weights $w_1, w_2$, volatilities $\sigma_1, \sigma_2$ and correlation
$\rho$:

$$\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1w_2\rho\,\sigma_1\sigma_2$$

**Example.** Two assets with 20% volatility each, 50/50, correlation 0.3:
$\sigma_p^2 = 0.25(0.04) + 0.25(0.04) + 2(0.25)(0.3)(0.04) = 0.026$, so
$\sigma_p = 16.1\%$ — **lower than either asset**, while the expected return is simply the
average of the two. With $\rho = 1$ the portfolio would stay at 20%; with $\rho = -1$ it
could fall to 0%.

{{widget:two_asset_risk}}

## Systematic vs specific risk

Adding more stocks removes **specific (idiosyncratic) risk** — the news that affects one
company. It cannot remove **systematic risk** — recessions, interest-rate shocks, crises —
that hits everything at once. In crises correlations tend to rise, so diversification
weakens exactly when it is most needed. This is why stress tests (chapter 16) matter.

## Summary

Volatility measures dispersion; drawdown measures pain. Mixing assets that are not
perfectly correlated lowers risk without lowering the average return — Markowitz's insight
and the foundation of portfolio construction.
