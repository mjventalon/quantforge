# 6 · Time series: ARMA & GARCH

## 6.1 Prices are not stationary, returns are

```python
import numpy as np
from quantforge.data import MarketData
from quantforge.timeseries import adf_test

md = MarketData("yahoo")
px = md.history("SPY", start="2015-01-01")["adj_close"]
lr = np.log(px).diff().dropna()

print(adf_test(np.log(px)))   # unit root not rejected → non-stationary
print(adf_test(lr))           # strongly stationary
```

Models must be fitted on a stationary series, so we work with log returns.

## 6.2 Is there memory in returns? In volatility?

```python
from quantforge.timeseries import acf, pacf, ljung_box
from quantforge.viz import acf_chart

acf_chart(acf(lr, 30), pacf(lr, 30), len(lr)).show()        # returns: almost no memory
acf_chart(acf(lr**2, 30), None, len(lr)).show()             # squared returns: strong memory
print(ljung_box(lr**2, 10))                                 # tiny p-value → ARCH effects
```

This is the key stylized fact: **direction is hard to predict, volatility is not**. Calm and
stormy periods cluster.

## 6.3 ARMA for the mean

```python
from quantforge.timeseries import select_arma_order
from quantforge.viz import forecast_chart

best, table = select_arma_order(lr * 100, max_p=3, max_q=3, criterion="bic")
print(best.order); print(best.summary())
fc = best.forecast(10)
forecast_chart(lr * 100, fc, "SPY daily return (%)").show()
```

Expect small coefficients and wide intervals. Honest models say "I don't know much".

## 6.4 GARCH for volatility

GJR-GARCH(1,1) with Student-t shocks:

$$\sigma_t^2 = \omega + (\alpha + \gamma\,\mathbb 1_{\varepsilon_{t-1}<0})\,\varepsilon_{t-1}^2 + \beta\,\sigma_{t-1}^2$$

* `α` reaction to yesterday's shock, `β` persistence, `γ` extra reaction to *negative* shocks
  (leverage effect), `ν` tail thickness.

```python
from quantforge.timeseries import fit_garch
from quantforge.viz import garch_chart

g = fit_garch(lr, distribution="t", asymmetric=True)
print(g.summary())
print(f"persistence {g.persistence:.4f}, half-life {g.half_life:.0f} days, "
      f"long-run vol {g.long_run_vol:.2%}")

fc = g.forecast(63)
garch_chart(lr, g.conditional_vol, forecast=fc, name="SPY").show()
print(fc.loc[[1, 21, 63], ["vol_annualized", "term_vol_annualized"]])
```

`term_vol_annualized` at h=21 is the model's average vol over the next month: compare it with
the 1-month ATM implied vol from [tutorial 3](03_vol_surface.md). Implied above GARCH →
options look expensive (or the market expects an event).

The estimator matches the reference `arch` package to about three decimals (see tests).

## 6.5 Realized volatility from OHLC

```python
from quantforge.timeseries import realized_vol_table, volatility_cone
from quantforge.viz import vol_cone_chart

ohlc = md.history("SPY", start="2015-01-01")
print(realized_vol_table(ohlc, 21).tail())
vol_cone_chart(volatility_cone(ohlc["adj_close"]), name="SPY").show()
```

Yang-Zhang uses open/high/low/close and is up to ~7× more efficient than close-to-close.

Next: [credit risk](07_credit.md).
