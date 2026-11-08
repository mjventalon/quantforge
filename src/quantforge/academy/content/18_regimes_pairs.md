---
id: 18
level: 5
level_name: Advanced Risk & Econometrics
title: Market regimes, cointegration and pairs trading
minutes: 35
objectives:
  - Explain hidden Markov regime models and the difference between filtered and smoothed probabilities
  - Test two price series for cointegration (Engle-Granger)
  - Design a pairs-trading rule on a z-scored spread without look-ahead
widgets: [regime_live, pairs_live]
sources:
  - title: "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle, Econometrica 57(2), 1989"
    by: "James D. Hamilton (paper)"
    url: ""
  - title: "Co-integration and Error Correction, Econometrica 55(2), 1987"
    by: "Robert F. Engle & C. W. J. Granger (paper — Nobel Prize 2003)"
    url: ""
  - title: "Pairs Trading: Performance of a Relative-Value Arbitrage Rule, Review of Financial Studies 19(3), 2006"
    by: "E. Gatev, W. Goetzmann & K. G. Rouwenhorst (paper)"
    url: ""
quiz:
  - q: "In a 2-state Gaussian HMM for returns, the states differ by:"
    options: ["Their tickers", "Their mean and volatility", "Their dividends", "Nothing"]
    answer: 1
    why: "Each hidden regime has its own return distribution; a Markov chain governs switches."
  - q: "Which regime probabilities may be used in a backtest?"
    options: ["Smoothed (uses the whole sample)", "Filtered (uses data up to each date only)", "Both", "Neither"]
    answer: 1
    why: "Smoothed probabilities use future data — fine for describing history, look-ahead in a backtest."
  - q: "A regime's transition probability of staying is 0.98 per day. Expected duration?"
    options: ["2 days", "50 days", "98 days", "0.98 days"]
    answer: 1
    why: "1 / (1 − 0.98) = 50 days."
  - q: "Two price series are cointegrated when:"
    options: ["Their returns are correlated", "Each is non-stationary but a linear combination is stationary", "They have the same price", "They are both stationary"]
    answer: 1
    why: "The spread mean-reverts even though each price wanders."
  - q: "Why are high correlations between two price *levels* misleading?"
    options: ["Correlation is always wrong", "Two independent random walks often show high spurious correlation", "Prices cannot be correlated", "They are never misleading"]
    answer: 1
    why: "Granger & Newbold's spurious regression problem: test returns or test cointegration."
  - q: "In a pairs strategy, the spread's z-score is +2.5 with entry at 2. You should:"
    options: ["Buy the spread", "Sell (short) the spread: short the expensive leg, buy the cheap leg", "Do nothing", "Close everything"]
    answer: 1
    why: "The spread is unusually wide; bet on reversion."
---

## Regimes

Markets alternate between calm, rising periods and volatile, falling ones. A **hidden Markov
model** formalizes this: each day the market is in one of $K$ unobserved states; each state
has its own mean and volatility; the state switches according to a transition matrix $A$
($A_{ij}$ = probability of moving from $i$ to $j$). The expected time spent in a state is
$1/(1-A_{ii})$ — with $A_{ii}=0.98$, about **50 days**.

Estimation uses the Baum-Welch (EM) algorithm. Two kinds of probabilities come out:

- **filtered** $P(s_t\mid r_1..r_t)$ — what you could know in real time;
- **smoothed** $P(s_t\mid r_1..r_T)$ — uses the future; great for describing history, but
  **look-ahead** in any trading rule.

{{widget:regime_live}}

## Cointegration

Two prices can each wander randomly yet stay tied together: Coca-Cola and PepsiCo, two share
classes of the same company, an ETF and its basket. Formally, $y_t$ and $x_t$ are
**cointegrated** if the spread

$$s_t = \ln y_t - \beta \ln x_t$$

is stationary. **Engle-Granger** test: estimate β by regression, then run an ADF test on the
residual using special critical values (β was estimated, so ordinary ADF values are too
lenient). quantforge's implementation matches `statsmodels` exactly.

Beware **spurious correlation**: two independent random walks frequently show high
correlation of levels. Test cointegration, or work with returns.

## Pairs trading

1. Estimate a hedge ratio on a rolling past window.
2. Standardize the spread: $z_t = (s_t - \bar s)/\sigma_s$ using past data only.
3. $z > +$entry → short the spread; $z < -$entry → buy it; close when $|z| <$ exit.
4. Charge costs on both legs; check the **half-life** of mean reversion.

{{widget:pairs_live}}

## Summary

Regime models describe how markets change character; use filtered probabilities for
decisions. Cointegration finds relationships that pull prices back together — the basis of
statistical arbitrage — but such links can break.
