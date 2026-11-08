# 3 · Building an implied volatility surface

Black-Scholes uses one σ, but the market prices every strike and maturity with a different
implied volatility. Plotting them gives the **smile** (one expiry) and the **surface** (all
expiries). Equity indices show a *skew*: low strikes (crash protection) are expensive.

## 3.1 Download several expiries

```python
import pandas as pd
from quantforge.data import MarketData

md = MarketData("yahoo")
ticker = "SPY"
spot, r = md.quote(ticker), md.risk_free_rate("3M")

expiries = [e for e in md.option_expiries(ticker)
            if (e - pd.Timestamp.today().normalize()).days >= 7][:8]
chain = pd.concat([md.option_chain(ticker, e) for e in expiries], ignore_index=True)
print(len(chain), "contracts")
```

## 3.2 Clean the quotes and compute implied vols

```python
from quantforge.pricing import chain_implied_vols

ivs = chain_implied_vols(chain, spot, r, max_rel_spread=0.4)
print(ivs[["expiry", "type", "strike", "mid", "iv", "provider_iv"]].head())
```

What the cleaning does, and why:

* drops quotes with **zero bid** (no real market) or **spread above 40%** of mid;
* keeps strikes between 60% and 160% of spot;
* keeps only **out-of-the-money** options (puts below the forward, calls above): they are the
  liquid ones and avoid early-exercise distortions;
* uses the **forward implied by put-call parity** for each expiry, so dividends and borrow
  costs are taken from the market itself.

`iv` is computed by quantforge from the mid price. `provider_iv` is what the data vendor
reports, kept for comparison.

## 3.3 Fit SVI smiles

The raw SVI model (Gatheral, 2004) describes total implied variance `w = σ²T` as a function
of log-moneyness `k = ln(K/F)`:

$$w(k) = a + b\left(\rho(k-m) + \sqrt{(k-m)^2 + \sigma^2}\right)$$

* `a` level, `b` wings, `ρ` skew (negative for equities), `m` shift, `σ` ATM curvature.

```python
from quantforge.pricing import surface_grid

k, T, iv_grid, params = surface_grid(ivs)
print(params.round(4))       # one row per expiry + RMSE of the fit in vol points
```

The fit keeps `a + bσ√(1-ρ²) ≥ 0` (no negative variance) and the surface is built so total
variance never decreases with maturity (no calendar arbitrage).

## 3.4 Plot

```python
from quantforge.viz import vol_smile, vol_surface_3d

vol_smile(ivs, params, source="Yahoo Finance").show()
vol_surface_3d(k, T, iv_grid, ivs).show()
```

## 3.5 Reading the surface

* **ATM term structure**: is short-dated vol above long-dated (stress) or below (calm)?
* **Skew** (`ρ`): how much more you pay for downside protection.
* **Compare with history**: put the ATM vols next to the volatility cone
  (`quantforge.timeseries.volatility_cone`) and a GARCH forecast
  ([tutorial 6](06_time_series.md)) to judge if options are rich or cheap.

Next: [portfolio optimization](04_portfolio.md).
