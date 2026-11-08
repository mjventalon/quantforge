---
id: 16
level: 5
level_name: Advanced Risk & Econometrics
title: Value at Risk, Expected Shortfall and stress tests
minutes: 30
objectives:
  - Compute VaR and ES by historical, parametric and Monte-Carlo methods
  - Backtest a VaR model with the Kupiec and Christoffersen tests
  - Design historical and hypothetical stress tests
widgets: [var_live, stress_live]
sources:
  - title: "18.S096 — Lecture 7: Value at Risk (VaR) Models"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "Minimum capital requirements for market risk (FRTB), January 2019"
    by: "Basel Committee on Banking Supervision — Bank for International Settlements"
    url: "https://www.bis.org/bcbs/publ/d457.htm"
  - title: "Value at Risk: The New Benchmark for Managing Financial Risk (3rd ed.)"
    by: "Philippe Jorion (book)"
    url: ""
quiz:
  - q: "A 1-day 99% VaR of $28,000 means:"
    options: ["You will lose $28,000 tomorrow", "On about 99 days in 100, the loss should not exceed $28,000", "The maximum possible loss is $28,000", "The average loss is $28,000"]
    answer: 1
    why: "VaR is a quantile, not a maximum. 1 day in 100 can be (much) worse."
  - q: "Daily volatility 1.2%, $1M portfolio, normal model, zero mean. The 1-day 99% VaR is closest to:"
    options: ["$12,000", "$23,500", "$27,900", "$36,000"]
    answer: 2
    why: "2.326 × 1.2% × $1M = $27,916."
  - q: "Using the square-root-of-time rule, the 10-day VaR is about:"
    options: ["$27,900", "$88,300", "$279,000", "$55,800"]
    answer: 1
    why: "$27,916 × √10 = $88,279 (assumes i.i.d. returns)."
  - q: "Expected Shortfall (ES) at 99% is:"
    options: ["The 99% quantile", "The average loss in the worst 1% of cases", "The maximum loss", "The median loss"]
    answer: 1
    why: "ES looks inside the tail; it is always ≥ VaR and is sub-additive (coherent)."
  - q: "Over 250 days a 99% VaR model had 9 exceptions. Basel's traffic light says:"
    options: ["Green", "Yellow", "Red", "Not enough data"]
    answer: 1
    why: "Expected ≈ 2.5. Basel: 0–4 green, 5–9 yellow, 10+ red."
  - q: "The Christoffersen test checks that exceptions are:"
    options: ["Exactly 1%", "Independent (not clustered in time)", "Normally distributed", "Positive"]
    answer: 1
    why: "Kupiec tests the frequency; Christoffersen tests independence; together = conditional coverage."
  - q: "Why run stress tests in addition to VaR?"
    options: ["They are required for retail investors", "VaR is calibrated on recent normal data and can miss extreme scenarios", "VaR is always too high", "They replace volatility"]
    answer: 1
    why: "Stress tests ask 'what if 2008 happened again?' regardless of recent calm."
---

## Value at Risk

The $\alpha$-level VaR over horizon $h$ is the loss that is exceeded with probability
$1-\alpha$:

$$P(\text{Loss} > \text{VaR}_\alpha) = 1 - \alpha$$

**Methods**

| Method | How | Watch out |
|---|---|---|
| Historical | Empirical quantile of past returns | Only knows the window you chose |
| Parametric normal | $\text{VaR} = -(\mu + z_{1-\alpha}\sigma)$ | Underestimates fat tails |
| Student-t / Cornish-Fisher | Adjust for fat tails / skew | Estimation noise |
| Monte-Carlo | Simulate the portfolio | Model risk in the simulator |

**Example.** Daily σ = 1.2%, $1M, 99%, zero mean: $2.326 \times 1.2\% \times \$1M =
\$27{,}916$. Over 10 days with i.i.d. returns: $\times\sqrt{10} = \$88{,}279$.

## Expected Shortfall

VaR says nothing about *how bad* the tail is. **Expected Shortfall** (CVaR) is the average
loss beyond VaR:

$$ES_\alpha = E[\text{Loss}\mid\text{Loss}>\text{VaR}_\alpha]$$

For the normal example, $ES_{99\%} = \sigma\,\phi(z)/(1-\alpha) \times \$1M \approx \$31{,}983$.
ES is sub-additive (diversification never increases it) — one reason the Basel Committee's
FRTB moved bank capital from 99% VaR to 97.5% ES.

{{widget:var_live}}

## Backtesting VaR

Count **exceptions** (days when the loss exceeded the forecast):

- **Kupiec** (proportion of failures): is the count consistent with $1-\alpha$?
- **Christoffersen**: are exceptions independent, or do they cluster in crises?
- **Basel traffic light** (99%, 250 days): 0–4 green, 5–9 yellow, 10+ red.

## Stress testing

VaR is calibrated on recent history and assumes the future resembles it. Stress tests ask
what happens in extreme but plausible scenarios:

- **historical** — replay real crises (1987, 2000–02, 2008, March 2020, 2022, SVB 2023,
  April 2025) on today's portfolio;
- **hypothetical** — shock factors (market −30%, rates +200 bp) and propagate through betas.

{{widget:stress_live}}

## Summary

VaR gives a threshold, ES the depth of the tail, backtests keep models honest, and stress
tests cover what statistics cannot see.
