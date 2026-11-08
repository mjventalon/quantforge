---
id: 14
level: 4
level_name: Derivatives
title: Binomial trees and Monte-Carlo simulation
minutes: 35
objectives:
  - Build a binomial tree and price European and American options by backward induction
  - Simulate stock paths under geometric Brownian motion
  - Estimate an option price by Monte-Carlo with a confidence interval and variance reduction
widgets: [tree_viewer, mc_convergence]
sources:
  - title: "Option Pricing: A Simplified Approach, Journal of Financial Economics 7(3), 1979"
    by: "John Cox, Stephen Ross & Mark Rubinstein (paper)"
    url: ""
  - title: "Monte Carlo Methods in Financial Engineering (2003)"
    by: "Paul Glasserman (book)"
    url: ""
  - title: "18.S096 — Lectures 5 & 17: Stochastic Processes I and II"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
quiz:
  - q: "In a Cox-Ross-Rubinstein tree, the up factor u equals:"
    options: ["1 + σ", "e^(σ√Δt)", "e^(rΔt)", "σ²"]
    answer: 1
    why: "u = e^(σ√Δt), d = 1/u."
  - q: "The risk-neutral up probability p equals:"
    options: ["0.5 always", "(e^(rΔt) − d)/(u − d)", "u − d", "N(d1)"]
    answer: 1
    why: "Chosen so the expected stock growth equals the risk-free rate."
  - q: "How is an American put priced on a tree?"
    options: ["Same as European", "At each node take max(continuation value, exercise value)", "Using only the last node", "With Black-Scholes"]
    answer: 1
    why: "Early exercise is checked at every node during backward induction."
  - q: "Monte-Carlo standard error falls with the number of paths N like:"
    options: ["1/N", "1/√N", "1/N²", "It does not fall"]
    answer: 1
    why: "Quadrupling paths halves the error."
  - q: "Antithetic variates means:"
    options: ["Using negative interest rates", "Pairing each random draw Z with −Z", "Removing outliers", "Using real historical returns"]
    answer: 1
    why: "Negatively correlated pairs reduce variance at no extra cost."
  - q: "Why use Monte-Carlo rather than a formula?"
    options: ["It is always faster", "It handles path-dependent and complex payoffs (Asian, barrier, baskets)", "It is exact", "It needs no volatility"]
    answer: 1
    why: "Any payoff you can compute on a simulated path can be priced."
  - q: "S = 100, K = 100, T = 1, r = 5%, σ = 20%, 3-step CRR tree: u is closest to"
    options: ["1.0513", "1.1224", "1.2000", "0.8909"]
    answer: 1
    why: "Δt = 1/3, u = e^(0.2·√(1/3)) = e^(0.1155) = 1.1224, d = 0.8909."
---

## The binomial tree

Split time to expiry into $n$ steps of length $\Delta t$. At each step the stock goes up by
$u$ or down by $d$:

$$u = e^{\sigma\sqrt{\Delta t}},\quad d = 1/u,\quad p = \frac{e^{r\Delta t} - d}{u - d}$$

$p$ is the **risk-neutral probability**: it makes the expected stock return equal the
risk-free rate. Price by **backward induction**: payoffs at the last step, then each node is
the discounted average of its two children

$$V = e^{-r\Delta t}\,[p V_u + (1-p) V_d]$$

For **American** options, at every node take $\max(V, \text{intrinsic value})$ — that is how
early exercise is valued. As $n$ grows the price converges to Black-Scholes for European
options. quantforge also implements the Leisen-Reimer tree, which converges much faster.

**Example.** $S=K=100$, $T=1$, $r=5\%$, $\sigma=20\%$, 3 steps: $u = 1.1224$, $d = 0.8909$,
$p = 0.5438$; the 3-step call price is 11.04 versus 10.45 for Black-Scholes. With 1,000 steps
the difference vanishes.

{{widget:tree_viewer}}

## Monte-Carlo

Simulate many possible futures of the stock under the risk-neutral measure:

$$S_{t+\Delta t} = S_t\exp\!\left[(r - \tfrac12\sigma^2)\Delta t + \sigma\sqrt{\Delta t}\,Z\right],\quad Z\sim N(0,1)$$

then average the discounted payoffs:

$$\hat V = e^{-rT}\frac1N\sum_{i=1}^N \text{payoff}(S^{(i)}), \qquad SE = \frac{s}{\sqrt N}$$

The **standard error** tells you how precise the estimate is; the 95% confidence interval is
$\hat V \pm 1.96\,SE$. Error shrinks like $1/\sqrt N$, so variance reduction matters:

- **antithetic variates** — use $Z$ and $-Z$;
- **control variates** — subtract a correlated quantity with a known mean (quantforge uses
  the geometric Asian option, known in closed form, to price arithmetic Asians).

{{widget:mc_convergence}}

## When to use which

| Method | Strength | Weakness |
|---|---|---|
| Closed form (BS) | Instant, exact under assumptions | Few payoffs |
| Tree | American exercise, intuitive | Path-dependence is hard |
| Monte-Carlo | Any payoff, many assets | Slow convergence; American needs extra methods |

## Summary

Trees discretize the future and handle early exercise; Monte-Carlo samples it and handles
complex payoffs. Both are numerical versions of the same risk-neutral idea.
