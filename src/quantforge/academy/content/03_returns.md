---
id: 3
level: 1
level_name: Market Foundations
title: Returns, compounding and annualizing
minutes: 25
objectives:
  - Compute simple and log returns and know when to use each
  - Compound returns over time and annualize them (CAGR)
  - Annualize volatility with the square-root-of-time rule
widgets: [compound_calculator, returns_explorer]
sources:
  - title: "15.401 Finance Theory I — Present Value Relations (Lecture notes & recitation 1)"
    by: "Andrew W. Lo — MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/"
  - title: "Compound Interest Calculator"
    by: "U.S. Securities and Exchange Commission (Investor.gov)"
    url: "https://www.investor.gov/introduction-investing"
quiz:
  - q: "A stock goes from $80 to $100. What is the simple return?"
    options: ["20%", "25%", "80%", "−20%"]
    answer: 1
    why: "(100 − 80) / 80 = 0.25 = 25%."
  - q: "A portfolio gains 50% one year and loses 50% the next. Overall it is:"
    options: ["Flat (0%)", "Down 25%", "Up 25%", "Down 50%"]
    answer: 1
    why: "1.5 × 0.5 = 0.75 → −25%. Losses hurt more than equal-sized gains help."
  - q: "$1,000 grows at 7% per year for 10 years (compounded annually). Closest value?"
    options: ["$1,700", "$1,967", "$2,000", "$1,070"]
    answer: 1
    why: "1,000 × 1.07^10 = $1,967.15."
  - q: "Why are log returns convenient?"
    options: ["They are always larger", "Multi-period log returns simply add up", "They remove risk", "They equal dividends"]
    answer: 1
    why: "ln(P_T/P_0) = Σ ln(P_t/P_{t-1}). Simple returns compound multiplicatively instead."
  - q: "Daily volatility is 1%. Approximate annual volatility (252 trading days)?"
    options: ["2.52%", "15.9%", "252%", "1%"]
    answer: 1
    why: "σ_annual = σ_daily × √252 = 1% × 15.87 ≈ 15.9% (assumes independent days)."
  - q: "An investment doubles in 5 years. Its CAGR is closest to:"
    options: ["20%", "14.9%", "10%", "100%"]
    answer: 1
    why: "CAGR = 2^(1/5) − 1 = 14.87%."
  - q: "Total return differs from price return because it includes:"
    options: ["Taxes", "Dividends (reinvested)", "Inflation", "Trading volume"]
    answer: 1
    why: "Adjusted close prices include dividends and splits, which is why quantforge uses adjusted closes for returns."
---

## Simple return

$$R_t = \frac{P_t - P_{t-1}}{P_{t-1}} = \frac{P_t}{P_{t-1}} - 1$$

From \$80 to \$100: $R = 100/80 - 1 = 25\%$. Simple returns **aggregate across assets**: a
portfolio's return is the weighted average of its assets' simple returns.

## Compounding

Returns multiply, they do not add:

$$1 + R_{0\to T} = (1+R_1)(1+R_2)\cdots(1+R_T)$$

+50% then −50% gives $1.5 \times 0.5 = 0.75$, a **−25%** loss. This asymmetry is why
drawdowns are so damaging: after −50% you need **+100%** to get back to even.

**Example.** \$1,000 at 7% a year for 10 years: $1{,}000 \times 1.07^{10} = \$1{,}967.15$.
The *rule of 72* estimates the doubling time: $72/7 \approx 10.3$ years (exact:
$\ln 2/\ln 1.07 = 10.24$).

## Log returns

$$r_t = \ln\frac{P_t}{P_{t-1}} = \ln(1+R_t)$$

Log returns **add over time**: $r_{0\to T} = \sum r_t$. That makes them the natural choice
for time-series models (GARCH, ARMA) and for volatility. For small moves $r \approx R$
(a +10% move is a log return of 0.0953).

| Use simple returns for | Use log returns for |
|---|---|
| Portfolio returns across assets | Adding returns over time |
| Reporting performance | Statistical models, volatility |

## Annualizing

**Average growth** — the compound annual growth rate:

$$\text{CAGR} = \left(\frac{V_{end}}{V_{start}}\right)^{1/\text{years}} - 1$$

Doubling in 5 years: $2^{1/5}-1 = 14.87\%$ per year.

**Volatility** grows with the square root of time if returns are independent:

$$\sigma_{annual} = \sigma_{daily}\sqrt{252}$$

1% daily volatility ≈ 15.9% annual. (252 ≈ trading days in a year.)

## Price return vs total return

Companies pay dividends and split shares. **Adjusted close** prices correct for both, so
returns computed from them are **total returns**. quantforge always uses adjusted closes for
return calculations.

{{widget:compound_calculator}}

{{widget:returns_explorer}}

## Summary

Simple returns for portfolios and reporting, log returns for time and models. Returns
compound; losses are asymmetric; volatility scales with √time.
