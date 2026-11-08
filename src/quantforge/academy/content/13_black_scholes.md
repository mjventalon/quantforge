---
id: 13
level: 4
level_name: Derivatives
title: Black-Scholes and the Greeks
minutes: 35
objectives:
  - State the Black-Scholes assumptions and formula
  - Price a European option by hand and with the tool
  - Interpret delta, gamma, vega, theta and rho and use delta for hedging
widgets: [bs_sliders, greek_surface_live]
sources:
  - title: "The Pricing of Options and Corporate Liabilities, Journal of Political Economy 81(3), 1973"
    by: "Fischer Black & Myron Scholes (paper)"
    url: ""
  - title: "Theory of Rational Option Pricing, Bell Journal of Economics and Management Science 4(1), 1973"
    by: "Robert C. Merton (paper — Nobel Prize 1997 with Scholes)"
    url: ""
  - title: "18.S096 — Lecture 19: Black-Scholes Formula, Risk-neutral Valuation"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
quiz:
  - q: "S = 100, K = 100, T = 1 year, r = 5%, σ = 20%. The Black-Scholes call price is closest to:"
    options: ["5.57", "8.02", "10.45", "12.34"]
    answer: 2
    why: "d1 = 0.35, d2 = 0.15 → C = 100·N(0.35) − 100e^(−0.05)·N(0.15) = 10.45."
  - q: "Same inputs: the put price is closest to:"
    options: ["5.57", "10.45", "4.88", "0.00"]
    answer: 0
    why: "Put-call parity: P = C − S + K e^(−rT) = 10.45 − 100 + 95.12 = 5.57."
  - q: "A call has delta 0.64. You own 10 contracts (1,000 options). To be delta-neutral you:"
    options: ["Buy 640 shares", "Sell 640 shares", "Sell 1,000 shares", "Do nothing"]
    answer: 1
    why: "Position delta = 0.64 × 1,000 = +640 shares-equivalent; sell 640 shares to offset."
  - q: "Which Greek measures sensitivity to implied volatility?"
    options: ["Delta", "Gamma", "Vega", "Rho"]
    answer: 2
    why: "Vega = ∂V/∂σ. Long options have positive vega."
  - q: "Theta of a long at-the-money option is usually:"
    options: ["Positive", "Negative — the option loses value as time passes", "Zero", "Equal to delta"]
    answer: 1
    why: "Time decay works against option buyers, all else equal."
  - q: "Which is NOT a Black-Scholes assumption?"
    options: ["Constant volatility", "Log-normal stock prices (GBM)", "Frictionless trading and continuous hedging", "Volatility depends on the strike"]
    answer: 3
    why: "Black-Scholes uses one constant σ. The fact that markets imply different σ per strike (the smile) shows the model's limits — chapter 15."
  - q: "Gamma is highest for:"
    options: ["Deep in-the-money long-dated options", "At-the-money options close to expiry", "Deep out-of-the-money options", "Stocks"]
    answer: 1
    why: "Delta changes fastest near the strike when little time is left."
---

## Assumptions

The stock follows a geometric Brownian motion $dS = \mu S\,dt + \sigma S\,dW$ with constant
volatility $\sigma$; rates are constant; trading is continuous and frictionless; no
arbitrage. Under these assumptions an option can be **perfectly hedged** by trading the stock,
so its price does not depend on investors' risk preferences or on $\mu$ (risk-neutral
valuation).

## The formula

$$C = S e^{-qT}N(d_1) - K e^{-rT}N(d_2), \qquad P = K e^{-rT}N(-d_2) - S e^{-qT}N(-d_1)$$

$$d_1 = \frac{\ln(S/K) + (r - q + \tfrac12\sigma^2)T}{\sigma\sqrt T}, \qquad d_2 = d_1 - \sigma\sqrt T$$

$N$ is the standard normal CDF, $q$ the dividend yield.

**Worked example.** $S=K=100$, $T=1$, $r=5\%$, $\sigma=20\%$, $q=0$:
$d_1 = (0 + 0.07)/0.2 = 0.35$, $d_2 = 0.15$, $N(0.35)=0.6368$, $N(0.15)=0.5596$.
$C = 100(0.6368) - 95.123(0.5596) = \mathbf{10.45}$; by parity $P = \mathbf{5.57}$.

{{widget:bs_sliders}}

## The Greeks

| Greek | Definition | Example above (call) | Meaning |
|---|---|---|---|
| Delta Δ | ∂V/∂S | 0.637 | Hedge ratio; ~shares equivalent |
| Gamma Γ | ∂²V/∂S² | 0.0188 | How fast delta changes |
| Vega ν | ∂V/∂σ | 37.5 (0.375 per vol point) | Exposure to implied volatility |
| Theta Θ | ∂V/∂t | −6.41 per year (−0.018 per day) | Time decay |
| Rho ρ | ∂V/∂r | 53.2 (0.53 per 1%) | Rate sensitivity |

**Delta hedging.** Long 1,000 calls with Δ = 0.64 behave like +640 shares; selling 640 shares
makes the position insensitive to small stock moves — until gamma changes delta and you must
rebalance. That rebalancing cost is what the option premium pays for.

{{widget:greek_surface_live}}

## Limits

Real volatility is not constant, prices jump, hedging is discrete and costly. The market
"fixes" Black-Scholes by quoting a different implied volatility per strike and maturity — the
volatility surface (chapter 15).

## Summary

Black-Scholes prices European options from five observable inputs and one unobservable
(σ). The Greeks measure risk and drive hedging. Know the formula, and know where it breaks.
