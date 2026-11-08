# 4 · Portfolio optimization & CAPM

## 4.1 Inputs from real prices

```python
from quantforge.data import MarketData
from quantforge.portfolio import estimate_inputs

md = MarketData("yahoo")
tickers = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "JNJ", "GLD", "TLT"]
rets = md.returns(tickers, start="2019-01-01")
rf = md.risk_free_rate("3M")

mu, cov = estimate_inputs(rets, method="ledoit_wolf")   # annualized
```

**Why Ledoit-Wolf?** The sample covariance of many assets is noisy, and the optimizer
exploits that noise. Shrinking toward a simple target gives more stable weights.

**A warning about `mu`.** Historical average returns are very noisy estimates of future
returns. Treat optimized weights as a starting point, not as truth. Black-Litterman (4.5) is
one way to temper them.

## 4.2 Classic portfolios

```python
from quantforge.portfolio import max_sharpe, min_variance, risk_parity, efficient_frontier

ms = max_sharpe(mu, cov, rf, bounds=(0, 0.30))   # long-only, max 30% per name
mv = min_variance(mu, cov, bounds=(0, 0.30))
rp = risk_parity(cov, mu=mu, risk_free_rate=rf)
print(ms)
print(mv)
print(rp)

frontier = efficient_frontier(mu, cov, n_points=60, bounds=(0, 0.30))
```

* **Max Sharpe** (tangency): best return per unit of risk above the risk-free rate.
* **Min variance**: lowest volatility; ignores expected returns (more robust).
* **Risk parity**: each asset contributes the same share of total risk.

## 4.3 Chart

```python
import numpy as np, pandas as pd
from quantforge.viz import efficient_frontier_chart, weights_chart

special = {"Max Sharpe": (ms.volatility, ms.expected_return),
           "Min variance": (mv.volatility, mv.expected_return)}
vols = pd.Series(np.sqrt(np.diag(cov)), index=mu.index)
efficient_frontier_chart(frontier, mu, vols, special, rf).show()
weights_chart(pd.DataFrame({"Max Sharpe": ms.weights, "Risk parity": rp.weights})).show()
```

## 4.4 CAPM

```python
from quantforge.portfolio import capm_regression, security_market_line

spy = md.returns("SPY", start="2019-01-01")["SPY"]
res = capm_regression(rets["NVDA"], spy, risk_free_rate=rf)
print(res)              # alpha (annualized) with t-stat and p-value, beta, R²
sml = security_market_line(rets, spy, rf)
print(sml.round(3))
```

* **Beta**: sensitivity to the market. 1.5 means the stock tends to move 1.5% when the market
  moves 1%.
* **Alpha**: return not explained by beta. Look at the p-value: an alpha with p > 0.05 is
  not statistically different from zero.

## 4.5 Black-Litterman

Start from the returns the market *implies* (reverse optimization on market-cap weights) and
blend in your own views with a confidence level.

```python
import numpy as np
from quantforge.portfolio import black_litterman

caps = {t: md.fundamentals(t)["market_cap"] for t in ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "JNJ"]}
sub = list(caps)
w_mkt = np.array([caps[t] for t in sub]); w_mkt = w_mkt / w_mkt.sum()
cov_s = cov.loc[sub, sub]

# View 1: JPM will outperform XOM by 3% a year (60% confident)
P = np.zeros((1, len(sub))); P[0, sub.index("JPM")] = 1; P[0, sub.index("XOM")] = -1
mu_bl, cov_bl = black_litterman(cov_s, w_mkt, P, [0.03], [0.6], risk_free_rate=rf)
print(max_sharpe(mu_bl, cov_bl, rf, (0, 0.4)))
```

## 4.6 Performance

```python
from quantforge.portfolio import performance_summary
port = rets @ ms.weights
print(performance_summary(port.to_frame("Max Sharpe"), rf))
```

Remember: this backtest is **in-sample** (weights chosen with the same data). For an honest
test, estimate on one period and evaluate on the next.

Next: [risk](05_risk.md).
