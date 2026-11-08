# 2 · Pricing options and Greeks on live data

We price a real listed option three ways (closed form, tree, Monte-Carlo), compare with the
market, and read the Greeks.

## 2.1 The theory in one paragraph

Black-Scholes-Merton assumes the stock follows a geometric Brownian motion with constant
volatility σ. A European call is then worth

$$C = S e^{-qT}N(d_1) - K e^{-rT}N(d_2),\quad d_{1,2} = \frac{\ln(S/K) + (r - q \pm \tfrac12\sigma^2)T}{\sigma\sqrt T}$$

US single-stock options are **American** (exercisable any day), so we also need a binomial
tree, which checks at every node whether exercising beats holding.

## 2.2 Get the market inputs

```python
import numpy as np
from quantforge.data import MarketData
from quantforge.pricing import implied_forward

md = MarketData("yahoo")
ticker = "AAPL"
spot = md.quote(ticker)

expiries = md.option_expiries(ticker)
expiry = expiries[3]                         # ~1 month out
chain = md.option_chain(ticker, expiry)      # columns: strike, type, bid, ask, mid, days, ...
T = chain["days"].iloc[0] / 365

# Risk-free rate: Treasury curve interpolated at the option's maturity
curve = md.yield_curve()
r = float(np.interp(T, curve.index, curve.values))

# Dividend / carry implied by put-call parity on the live chain
F = implied_forward(chain, spot, r, T)
q = r - np.log(F / spot) / T
print(f"S={spot:.2f}  T={T*365:.0f}d  r={r:.2%}  q={q:.2%}")
```

## 2.3 Pick a contract and back out its implied vol

```python
from quantforge.pricing import implied_volatility

puts = chain[chain["type"] == "put"]
atm = puts.iloc[(puts["strike"] - spot).abs().argmin()]
K, mid = atm["strike"], atm["mid"]

iv = implied_volatility(mid, spot, K, T, r, "put", q)
print(f"{ticker} {expiry:%Y-%m-%d} {K} put: mid {mid:.2f}, implied vol {iv:.2%}")
```

`implied_volatility` uses Brent's method, which always converges because the option price
increases with volatility. A price outside the no-arbitrage bounds raises an error instead of
returning nonsense.

## 2.4 Three pricers

```python
from quantforge.pricing import bs_price, binomial_price, mc_european

euro = bs_price(spot, K, T, r, iv, "put", q)
amer = binomial_price(spot, K, T, r, iv, "put", "american", q, steps=1001)   # Leisen-Reimer
mc = mc_european(spot, K, T, r, iv, "put", q, n_paths=200_000, seed=1)

print(f"Black-Scholes (European): {euro:.4f}")
print(f"Binomial (American):      {amer.price:.4f}   early-exercise premium {amer.price - euro:.4f}")
print(mc)   # price, standard error and 95% confidence interval
```

Monte-Carlo always reports its standard error: if the market price sits outside the
confidence interval, the gap is real and not simulation noise.

## 2.5 Greeks

```python
from quantforge.pricing import bs_greeks

g = bs_greeks(spot, K, T, r, iv, "put", q)
print(f"delta {g.delta:.4f}")
print(f"gamma {g.gamma:.5f}")
print(f"vega  {g.vega/100:.4f} per vol point")
print(f"theta {g.theta/365:.4f} per day")
print(f"rho   {g.rho/100:.4f} per 1% rate move")
```

Units: vega and rho are per 1.00 change; divide by 100 for "per point". Theta is per year;
divide by 365 for "per day".

## 2.6 Exotic options

```python
from quantforge.pricing import mc_asian, mc_barrier, barrier_price

# Average-price (Asian) call on the daily closes until expiry
print(mc_asian(spot, spot, T, r, iv, n_fixings=max(int(T*252), 1), dividend_yield=q, seed=0))

# Down-and-out call, barrier 15% below spot: closed form vs Monte-Carlo
H = 0.85 * spot
print(barrier_price(spot, spot, H, T, r, iv, "down-and-out", "call", q))
print(mc_barrier(spot, spot, H, T, r, iv, "down-and-out", "call", q, seed=0))
```

The Monte-Carlo barrier uses the Broadie-Glasserman-Kou shift so daily monitoring matches the
continuous closed form.

## 2.7 Charts

```python
from quantforge.viz import greek_profile, mc_paths_fan
from quantforge.pricing import simulate_gbm_paths

grid = np.linspace(0.7 * spot, 1.3 * spot, 300)
gg = bs_greeks(grid, K, T, r, iv, "put", q)
greek_profile(grid, {k: np.asarray(getattr(gg, k)) for k in
              ("price", "delta", "gamma", "vega", "theta", "rho")}, spot).show()

paths = simulate_gbm_paths(spot, T, r, iv, 3000, 60, q, seed=1)
mc_paths_fan(paths, T, K).show()
```

Next: [the implied volatility surface](03_vol_surface.md).
