---
id: 15
level: 4
level_name: Derivatives
title: Implied volatility and the volatility surface
minutes: 30
objectives:
  - Back out implied volatility from a market price
  - Read the smile/skew and the term structure on live data
  - Understand how a surface is cleaned and fitted (SVI) and why arbitrage constraints matter
widgets: [live_smile]
sources:
  - title: "The Volatility Surface: A Practitioner's Guide (2006)"
    by: "Jim Gatheral (book)"
    url: ""
  - title: "Arbitrage-free SVI volatility surfaces, Quantitative Finance 14(1), 2014"
    by: "Jim Gatheral & Antoine Jacquier (paper)"
    url: ""
  - title: "18.S096 — Lecture 9: Volatility Modeling"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
quiz:
  - q: "Implied volatility is:"
    options: ["The historical volatility of the stock", "The σ that makes the model price equal the market price", "Always 20%", "The VIX"]
    answer: 1
    why: "It is solved numerically from the observed option price."
  - q: "Why can implied volatility always be solved uniquely (for prices within arbitrage bounds)?"
    options: ["Because σ is constant", "Because the BS price increases strictly with σ (positive vega)", "Because rates are zero", "It cannot"]
    answer: 1
    why: "A monotone function has at most one root; Brent's method finds it."
  - q: "For equity indices, low-strike puts usually have:"
    options: ["Lower implied vol than ATM", "Higher implied vol than ATM (skew)", "The same vol", "No vol"]
    answer: 1
    why: "Demand for crash protection and the leverage effect make downside strikes more expensive — the skew, visible since 1987."
  - q: "An inverted volatility term structure (short-dated vol above long-dated) often signals:"
    options: ["Calm markets", "Current stress or an imminent event", "Higher interest rates", "Nothing"]
    answer: 1
    why: "Near-term uncertainty is priced above long-term uncertainty."
  - q: "Why does quantforge use out-of-the-money options and the bid-ask mid?"
    options: ["They are cheaper to trade", "They are the most liquid and avoid early-exercise and stale-price distortions", "It is required by law", "To hide data"]
    answer: 1
    why: "Clean inputs give a reliable surface; deep ITM quotes are illiquid and contaminated by early-exercise value."
  - q: "Total implied variance w = σ²T must not decrease with maturity at a fixed moneyness because otherwise:"
    options: ["The chart looks bad", "There would be a calendar-spread arbitrage", "Rates would be negative", "Vega would be zero"]
    answer: 1
    why: "Non-decreasing total variance is the no-calendar-arbitrage condition."
---

## From price to volatility

Every input of Black-Scholes is observable except σ. Turn the formula around: find the
$\sigma_{imp}$ such that

$$BS(S, K, T, r, q, \sigma_{imp}) = \text{market price}$$

Because the price rises strictly with σ (vega > 0), the solution is unique when the price
respects the no-arbitrage bounds. quantforge solves it with Brent's method.

## The smile and the skew

If Black-Scholes were right, every strike would give the same $\sigma_{imp}$. It does not.
For equity indices, implied volatility is higher for **low strikes** — the **skew** — a
pattern that became permanent after the 1987 crash: investors pay up for crash protection,
and volatility tends to rise when prices fall (leverage effect). Single stocks and FX often
show a more symmetric **smile**.

## The term structure

Plotting at-the-money implied vol against maturity gives the **term structure**. Normally
upward sloping (more uncertainty further out); **inverted** in stress or before events
(earnings, elections).

## Building a clean surface

Raw chains are messy. quantforge's pipeline:

1. drop zero bids, wide spreads and illiquid far strikes;
2. keep **out-of-the-money** options (puts below the forward, calls above);
3. infer the **forward** from put-call parity (captures dividends and borrow costs);
4. solve implied vols from **mid prices**;
5. fit each expiry with **SVI** (Gatheral, 2004):

$$w(k) = a + b\left(\rho(k-m) + \sqrt{(k-m)^2+\sigma^2}\right),\quad k = \ln(K/F),\ w = \sigma_{imp}^2 T$$

6. interpolate total variance in maturity, keeping it non-decreasing (no calendar arbitrage).

{{widget:live_smile}}

## Summary

Implied volatility is the market's price of uncertainty, strike by strike and maturity by
maturity. The surface encodes fear (skew) and timing (term structure); building it well is
mostly about data cleaning and arbitrage constraints.
