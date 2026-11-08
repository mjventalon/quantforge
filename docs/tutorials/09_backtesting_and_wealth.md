# 9 · Backtesting, pairs trading and wealth projection

## 9.1 Backtest a trading rule (no look-ahead)

```python
from quantforge.data import MarketData
from quantforge.backtest import run_backtest, sma_crossover, grid_search

md = MarketData("yahoo")
px = md.history("SPY", start="2005-01-01")["adj_close"]

pos = sma_crossover(px, fast=50, slow=200)          # +1 long / 0 flat, decided at each close
res = run_backtest(px, pos, cost_bps=5, risk_free_rate=md.risk_free_rate())
print(res.metrics.round(3))                          # strategy vs buy & hold
print(res.trades.tail())
```

The engine applies today's decision to **tomorrow's** return and charges costs on every
change of position. A test in the suite checks that a "perfect foresight" signal only works
if the future leaks in — it can't here.

## 9.2 Is the "best" parameter just luck?

```python
table, best = grid_search(px, sma_crossover, {"fast": [20, 50, 100], "slow": [150, 200, 300]},
                          cost_bps=5, train_fraction=0.6)
print(best)
print(table.sort_values("train_Sharpe", ascending=False).head())
```

Compare `train_Sharpe` with `test_Sharpe` (the last 40% of history, never used to choose).

## 9.3 Walk-forward portfolio

```python
from quantforge.backtest import walk_forward_portfolio

prices = md.prices(["SPY", "TLT", "GLD", "EFA", "VNQ"], start="2008-01-01")
rets, weights, metrics = walk_forward_portfolio(prices, lookback=252, rebalance="ME")
print(metrics.round(3))
```

Every month the optimizer only sees the previous 252 days.

## 9.4 Pairs trading

```python
from quantforge.timeseries import engle_granger
from quantforge.backtest import pairs_backtest

p = md.prices(["XOM", "CVX"], start="2015-01-01")
print(engle_granger(p["XOM"], p["CVX"]))
res = pairs_backtest(p["XOM"], p["CVX"], window=120, entry=2.0, exit=0.5)
print(res.metrics.round(3))
```

## 9.5 Wealth projection from real history

```python
from quantforge.portfolio import monthly_portfolio_returns, simulate_wealth

px = md.prices(["SPY", "AGG"], start="2004-01-01")
monthly = monthly_portfolio_returns(px, {"SPY": 0.6, "AGG": 0.4})
inflation, month = md.inflation()                     # latest US CPI y/y from FRED
sim = simulate_wealth(monthly, initial=10_000, monthly_contribution=500, years=20,
                      annual_inflation=inflation, goal=300_000, seed=0)
print(sim.summary())
```

## 9.6 Charts with zoom & pan

```python
from quantforge.viz import backtest_chart, wealth_fan_chart, show
spy = md.history("SPY", start="2005-01-01")["adj_close"]
show(backtest_chart(spy, run_backtest(spy, sma_crossover(spy))))
show(wealth_fan_chart(sim))
```

`show()` turns on mouse-wheel zoom and drag-to-pan in notebooks and scripts.
