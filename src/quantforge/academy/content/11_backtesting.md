---
id: 11
level: 3
level_name: Portfolio Construction
title: Backtesting without fooling yourself
minutes: 30
objectives:
  - Identify look-ahead bias, survivorship bias, overfitting and missing costs
  - Use train/test splits and walk-forward analysis
  - Read a backtest report critically (Sharpe, drawdown, turnover, robustness)
widgets: [mini_backtest, overfit_demo]
sources:
  - title: "The Probability of Backtest Overfitting, Journal of Computational Finance 20(4), 2017"
    by: "D. Bailey, J. Borwein, M. López de Prado & Q. J. Zhu (paper)"
    url: ""
  - title: "Advances in Financial Machine Learning (2018), chapters on backtesting"
    by: "Marcos López de Prado (book)"
    url: ""
  - title: "Time Series Momentum, Journal of Financial Economics 104(2), 2012"
    by: "T. Moskowitz, Y. H. Ooi & L. H. Pedersen (paper)"
    url: ""
quiz:
  - q: "A strategy uses today's closing price to decide to buy at today's open. This is:"
    options: ["Fine", "Look-ahead bias", "Survivorship bias", "Transaction costs"]
    answer: 1
    why: "The close is not known at the open. In quantforge, a decision at close t only earns the return from t to t+1."
  - q: "Testing only on stocks that are in today's S&P 500 introduces:"
    options: ["Survivorship bias — failed companies are missing", "Look-ahead in prices", "No bias", "Higher costs"]
    answer: 0
    why: "Companies that went bankrupt or were removed are excluded, which flatters historical results."
  - q: "You try 1,000 parameter combinations and report the best Sharpe. The main danger is:"
    options: ["Overfitting / data mining", "Too much diversification", "Low turnover", "Negative skew"]
    answer: 0
    why: "With enough trials, some look great by chance. Test the chosen parameters on data not used to pick them."
  - q: "A strategy's Sharpe is 2.1 on the training period and 0.1 on the test period. Most likely:"
    options: ["It is robust", "It was overfitted", "Costs are too low", "The test period is wrong"]
    answer: 1
    why: "A collapse out of sample is the classic signature of overfitting."
  - q: "Walk-forward analysis means:"
    options: ["Testing on the full sample once", "Re-estimating the model periodically using only past data and testing on the next period", "Walking through trades manually", "Ignoring the first year"]
    answer: 1
    why: "It mimics real life: decide with the past, live through the future, repeat."
  - q: "A strategy trades 50 times its capital per year at 5 bps per trade. Annual cost drag is about:"
    options: ["0.05%", "0.25%", "2.5%", "25%"]
    answer: 2
    why: "Turnover 50 × 5 bps = 250 bps = 2.5% per year — often enough to kill a modest edge."
---

## A backtest is an experiment

It answers: *had I followed this rule in the past, with the information available at the
time, net of costs, what would have happened?* Every word in that sentence is a trap.

## The four classic errors

1. **Look-ahead bias** — using information not yet available (tomorrow's close, restated
   data, the final list of index members). quantforge's engine applies a decision made at the
   close of day *t* to the return of day *t+1* only; a unit test checks that a
   "perfect foresight" signal cannot profit through the engine.
2. **Survivorship bias** — testing only on assets that still exist today.
3. **Overfitting (data snooping)** — trying many rules or parameters and keeping the best.
   With 100 random strategies, the best in-sample Sharpe will look impressive by chance alone.
4. **Ignoring costs** — spreads, commissions, slippage, borrow fees. High-turnover strategies
   die here: turnover 50×/year at 5 bps = 2.5% per year of drag.

{{widget:overfit_demo}}

## Honest protocols

- **Train / test split**: choose parameters on the first part, report results on the untouched
  second part (the Backtester's *parameter search*).
- **Walk-forward**: re-fit periodically on past data only, then trade the next period.
- **Robustness**: neighbors of the best parameters should also work (look at the heatmap, not
  one cell); results should hold in several markets and periods.
- **Monte-Carlo of trades**: reshuffle realized trades to see how much the result depends on
  luck and ordering (Strategy Lab).

## Reading a report

| Metric | Question it answers |
|---|---|
| CAGR, Sharpe, Sortino | Was the return worth the risk? |
| Max drawdown, Calmar | Could I have survived the worst period? |
| Trades, turnover, time in market | Is the result from many independent bets or a few? Are costs realistic? |
| Train vs test Sharpe | Is it overfitted? |

{{widget:mini_backtest}}

## Summary

Backtests are easy to fool. Use only past information, include costs, test out of sample,
check robustness — and stay skeptical of anything that looks too good.
