# 5 · VaR, Expected Shortfall, backtesting & stress tests

## 5.1 Definitions

* **VaR 99% 1-day = $25,000** → on 99% of days the loss should not exceed $25,000.
* **Expected Shortfall (ES)** → the *average* loss on the 1% worst days. ES looks inside the
  tail, VaR only at its edge. Basel's FRTB uses ES at 97.5%.

## 5.2 A real portfolio

```python
import numpy as np
from quantforge.data import MarketData

md = MarketData("yahoo")
w = {"SPY": 0.5, "TLT": 0.3, "GLD": 0.2}
rets = md.returns(list(w), start="2010-01-01")
port = rets @ np.array(list(w.values()))
value = 1_000_000
```

## 5.3 Five methods side by side

```python
from quantforge.risk import var_report
print(var_report(port, confidence=0.99, horizon=1, position_value=value))
```

| Method | Idea | Weak spot |
|---|---|---|
| Historical | empirical quantile of past returns | only knows what already happened |
| Parametric normal | mean ± z·σ | underestimates fat tails |
| Student-t | fitted fat-tailed distribution | symmetric |
| Cornish-Fisher | adjusts the normal quantile for skew and kurtosis | unstable for extreme kurtosis |
| Monte-Carlo bootstrap | resamples real days | same as historical, smoother |

When the methods disagree a lot, the tails are not normal: trust historical/Student-t/ES more
than the normal VaR.

## 5.4 Where the risk comes from

```python
from quantforge.risk import portfolio_var_decomposition
print(portfolio_var_decomposition(rets, list(w.values()), 0.99))
```

`pct_of_total` shows each asset's share of portfolio VaR (Euler allocation). A 30% weight
can carry 60% of the risk.

## 5.5 Backtest: was the model right?

```python
from quantforge.risk import rolling_var, backtest_var
from quantforge.viz import var_backtest_chart

forecast = rolling_var(port, window=250, confidence=0.99)   # uses only past data each day
bt = backtest_var(port, forecast, 0.99)
print(bt)
var_backtest_chart(port, forecast).show()
```

* **Kupiec**: is the *number* of exceptions consistent with 1%? (p < 0.05 → reject)
* **Christoffersen**: are exceptions *independent*, or do they cluster in crises?
* **Basel zone**: green / yellow / red over the last 250 days.

## 5.6 Historical stress tests

Replays what your assets **actually did** during real crises:

```python
from quantforge.risk import historical_stress_test, HISTORICAL_SCENARIOS
from quantforge.viz import stress_chart

px = md.prices(list(w) + ["SPY"], start="1990-01-01", dropna=False)
res = historical_stress_test(px, w, px["SPY"].dropna(), portfolio_value=value)
print(res[["start", "end", "portfolio_return", "pnl", "proxied_assets"]])
stress_chart(res).show()
```

If an asset did not exist yet (GLD started in 2004), its move is estimated as
`beta × benchmark move` and listed in `proxied_assets`, so you always know what was observed
and what was estimated. Add your own scenario with
`Scenario("My crisis", "2024-07-10", "2024-08-05", "description")`.

## 5.7 Hypothetical shocks

```python
from quantforge.risk import hypothetical_stress_test
print(hypothetical_stress_test(rets, w, rets["SPY"], market_shocks=(-0.1, -0.2, -0.3),
                               portfolio_value=value))
```

Next: [ARMA & GARCH](06_time_series.md).
