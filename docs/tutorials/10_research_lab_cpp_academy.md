# Tutorial 10 — Regimes, the Strategy Lab, the C++ engine and the Academy

This tutorial covers the v0.3 tools. Every number comes from real market data.

## 1. Market regimes with a Hidden Markov Model

```python
from quantforge.data import MarketData
from quantforge.timeseries.regimes import fit_hmm

md = MarketData("yahoo")
spy = md.returns("SPY", start="2007-01-01")["SPY"]
hmm = fit_hmm(spy, n_states=2)
print(hmm.summary())                       # annual return & vol of each regime, durations
print(hmm.filtered.iloc[-1])               # today's probabilities, using past data only
```

`filtered` probabilities use only information available at each date — use them for
decisions. `smoothed` ones use the whole sample: fine to describe history, never to trade.

## 2. How the distribution of returns changes

```python
from quantforge.timeseries.distribution import rolling_density_surface, rolling_moments

dates, grid, density = rolling_density_surface(spy, window=63, step=5)
print(density.shape)                       # (number of dates, grid points)
print(rolling_moments(spy).tail())         # rolling vol, skewness, excess kurtosis
```

## 3. The Strategy Lab: many strategies, one book

```python
from quantforge.backtest import STRATEGIES
from quantforge.backtest.lab import (StrategySpec, run_lab, diversity_report,
                                     greedy_portfolio, trade_monte_carlo)

px = md.prices(["SPY", "TLT", "GLD"], start="2012-01-01")
specs = [StrategySpec(name, t) for name in list(STRATEGIES)[:3] for t in px.columns]
lab = run_lab(px, specs, cost_bps=5)
print(lab.metrics.sort_values("Sharpe", ascending=False).head())

report = diversity_report(lab.returns)
print(report["score"], report["grade"])    # 0-100, A-D
book = greedy_portfolio(lab.returns, size=4, objective="diversity", min_sharpe=None)
print(book)

best = lab.metrics["Sharpe"].idxmax()
mc = trade_monte_carlo(lab.trades[best], n_sims=2000) if len(lab.trades[best]) >= 5 else None
print(mc and (mc["p_profit"], mc["verdict"]))
```

`trade_monte_carlo` reshuffles the real trades thousands of times: if the result depends on a
lucky order of trades, P(profit) drops.

## 4. The C++ engine

Build it once from a terminal (needs a C++ compiler; on macOS `xcode-select --install`):

```bash
quantforge-build-native
```

```python
from quantforge import native

if native.available():
    print(native.bs_price(42, 40, 0.5, 0.10, 0.20, "call"))       # 4.7594…
    print(native.binomial(50, 50, 5 / 12, 0.10, 0.40, "put", "american", steps=2001))
    print(native.mc_european(100, 100, 1, 0.05, 0.2, n_paths=2_000_000, seed=1))
else:
    print(native.status().message)
```

Results agree with `quantforge.pricing` to about 1e-10; Monte-Carlo is reproducible for a given
seed whatever the number of threads.

## 5. The Academy from Python

```python
from quantforge.academy import load_curriculum, make_certificate_id, verify_certificate
from quantforge.academy.exercises import load_exercises

chapters = load_curriculum()
print(len(chapters), chapters[12].title)
print(len(load_exercises()), "coding exercises")

cid = make_certificate_id("Ada Lovelace", 13)
print(cid, verify_certificate(cid, "Ada Lovelace").valid)
```

In the web app, open **Learn → Academy**, enter your name once, and work through the chapters.
**Learn → Code Lab** lists every exercise; on your own computer both Python and C++ are graded
automatically.
