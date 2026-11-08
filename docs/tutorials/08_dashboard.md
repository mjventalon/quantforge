# 8 · Using the dashboard

```bash
quantforge-app                    # or: streamlit run src/quantforge/app/app.py
quantforge-app --server.port 8600 # any Streamlit option works
```

## Sidebar

1. Pick the **market data provider**.
2. Paste your **API key** if the provider needs one (kept in the browser session only), or
   put it in `.env` before launching.
3. FRED needs no key. Add one only if you hit rate limits.

Use **Connection check** on the home page: it downloads the last SPY price and the 3-month
T-bill to confirm everything works.

## Pages

| Page | Try this |
|---|---|
| **Market** | `NVDA`, 5 years. Look at Yang-Zhang vs close-to-close vol, then where current vol sits in the cone. |
| **Options pricer** | `AAPL`, an expiry ~1 month out, ATM put, *American*. Compare the binomial price with the market mid. Switch volatility to *Historical 63d* and see the gap. |
| **Vol surface** | `SPY`, 8 expiries. Note the negative skew (ρ < 0) and the term structure table. |
| **Strategy builder** | `QQQ`, *Iron condor*. Edit strikes in the table; premiums are live mids. Read max loss and break-evens. |
| **Portfolio** | Default tickers, max weight 30%. Compare Max Sharpe vs Risk parity weights and their share of risk. Add a Black-Litterman view. |
| **Risk** | `SPY, TLT, GLD, QQQ`, $1M, 99%. Check the backtest zone, then the COVID-19 and 2022 rate-shock scenarios. |
| **Time series** | `SPY`. ADF on price vs returns, ACF of squared returns, then GARCH-t with GJR. |
| **Credit** | `F` or `BA`: distance to default. Upload a loan CSV in the PD tab. |

## Good to know

* Data is cached 1 hour in the app and 6 hours on disk, so reloading is fast and saves quota.
* Every chart is interactive: hover for values, drag to zoom, double-click to reset, camera
  icon to save a PNG.
* If a provider fails, the page shows the exact error and stops. It never shows estimated or
  placeholder numbers in place of market data.
* Quotes from free sources can be delayed by 15 minutes or more.

## Deploy for others

* **Streamlit Community Cloud** (free): push the repo to GitHub, create an app pointing to
  `src/quantforge/app/app.py`, and add keys under *Secrets* as environment variables.
* **Docker / a server**: `pip install ".[app]" && quantforge-app --server.address 0.0.0.0`.
