# Changelog

## Unreleased

* Paper trading: the live chart failed with "Cannot compare tz-naive and tz-aware timestamps"
  once an order had filled. Fill markers are now placed on the chart's exchange-time bars.
* C++ engine page: comparing implied vols on a live chain crashed when one quote was outside
  the no-arbitrage bounds (stale price, or dividends). Such quotes are now skipped by both
  engines and counted in an "Outside bounds" column.
* Paper trading: the order ticket showed New York time labelled as UTC (for example
  09:50 instead of 14:50 UTC). Intraday bar times are now converted to UTC correctly.

## 1.0.0 — 2026-11-07

First public release.

* New README with screenshots of every tool, a quick start and English | Français links.
* Double-click launchers: `Start quantforge.command` (macOS) and `Start quantforge.bat`
  (Windows). They install everything on first launch, so no terminal is needed.
* Python 3.11 or newer is now required (Python 3.10 reached end of life in October 2026, and
  Streamlit, pandas and scikit-learn no longer support it).
* C++ engine: added missing standard headers so it compiles with Apple Clang (macOS).
* GitHub project setup: release workflow (tag `v*` to publish a release with the package),
  support page, code owners, Discussions link for questions.

## 0.5.2 — 2026-11-07

* Regimes & 3-D: notice to allow 2–3 minutes for heavy models, results cached for an hour,
  regime model fitted with 4 random starts instead of 8, 3-D surface capped at 400 slices so it
  rotates smoothly.

## 0.5.1 — 2026-11-07

* Fix: Strategy Lab leaderboard crashed without matplotlib (pandas gradient). Colours are now
  computed by quantforge itself; the test suite blocks matplotlib so this cannot come back.

## 0.5.0 — 2026-11-07

* **AI copilot** in the sidebar: connect Claude, ChatGPT or Gemini with your own API key. It
  reads the current page (fields, values, results, page guide) and, with your permission,
  explains, suggests changes you approve, or runs the page itself (fill fields, press buttons,
  open pages, then explain). Per-AI consent, no keys or passwords sent, destructive buttons
  never exposed. Model list fetched from each provider.
* **Long history everywhere**: period presets 1Y…20Y and **Max** (whole history from the
  source), full history drawn on the stock chart with 1M/6M/YTD/1Y/5Y/All buttons on every
  long time-series chart; Live market ranges from 1 day (1-minute bars) to all history (weekly).
* **3-D models rotate freely** (orbit, 360° in every direction) instead of panning.

## 0.4.0 — 2026-11-07

* **Paper trading** (`quantforge.paper` + new *Trade* page): virtual accounts ($1,000,000 by
  default) on real prices, saved between visits (several accounts, account code to reopen on
  another device). Market, limit, stop, stop-limit and trailing-stop orders, day/GTC, short
  selling with 150 % margin, slippage and commissions, cancel, close position, rebalance to a
  model portfolio (equal weight, minimum variance, max Sharpe, risk parity). Customisable board
  of live widgets: ticket, positions, chart with your fills, watchlist, equity vs SPY,
  allocation, VaR/ES, GARCH, HMM regime, strategy signals, performance.
* **New models** (`quantforge.pricing.stochastic`): Heston stochastic volatility (Lewis
  integral, "little trap" characteristic function, Monte-Carlo check), SABR (Hagan 2002),
  Merton jump-diffusion; calibration to live option chains; new page with fitted smiles and an
  interactive Heston 3-D surface.
* **Gentler chart zoom**: mouse-wheel/trackpad zoom is damped (Slow / Normal / Fast in the
  sidebar); click-and-drag still pans.
* `quantforge-app` opens the browser automatically.

## 0.3.0 — 2026-11-07

**Academy & certificates**
* 23-chapter curriculum in 7 levels (Market Foundations → Quant Programming), 143 quiz
  questions, cited sources (MIT OpenCourseWare, Yale, Investor.gov, FRED, BIS, textbooks),
  36 interactive widgets on live data.
* **Code Lab**: 22 "rewrite it yourself" exercises in Python and C++ with automatic grading —
  in the browser (Pyodide) on public sites, locally (Python + C++ compiler) with `quantforge-app`.
* PDF certificates (black/red/white design, logo, HMAC-signed IDs), program certificate,
  public verification page, sealed progress files, learner name remembered and editable.

**C++ engine** (`quantforge.native`)
* Header-only C++17: Black-Scholes & Greeks, Newton implied vol, LR/CRR trees, multithreaded
  deterministic Monte-Carlo (European, Asian). ctypes bindings, CMake project, C++ tests,
  `quantforge-build-native`, benchmark page on real inputs.

**Research & live data**
* Live market page (auto-refreshing intraday charts, market board) and live 3-D surfaces.
* Strategy Lab: multi-strategy books, diversity score & heatmap, greedy auto-build, folds,
  trade Monte-Carlo, 3-D parameter landscapes, code export.
* Gaussian HMM regimes (filtered vs smoothed), rolling return-distribution surfaces.
* Ticker autocomplete (curated list + SEC universe + Yahoo search).

**App & project**
* New navigation with sections and clean URLs, app icon and logo, Creator and Policies pages
  (terms, risk disclaimer, privacy, data attribution, certification policy).
* Docker image, docker-compose, deployment guide (custom domain), architecture doc, roadmap,
  security policy, code of conduct, citation file, issue/PR templates, Dependabot, CI for C++.
* Fixes: pandas copy-on-write read-only arrays, `read_json` on literal strings, `.env` now
  loaded before branding settings.

## 0.2.0 — 2026-11-07

* **Charts**: mouse-wheel zoom and drag-to-pan everywhere; readable labels in dark mode.
* **New pages**: Market pulse (sector / asset-class / watchlist heatmaps), Wealth simulator,
  Backtester (single asset + walk-forward portfolio), Pairs trading, Guide, About.
* **Stock analysis**: RSI, MACD, Bollinger bands, ATR, plain-English signals.
* **Options**: expected move, probability ITM, put/call ratios, open-interest walls, max pain.
* **Portfolio**: factor exposures (ETF proxies), real market caps for Black-Litterman,
  CSV exports.
* **Library**: `quantforge.backtest` (engine, strategies, grid search, walk-forward, pairs),
  `timeseries.indicators`, `timeseries.cointegration`, `portfolio.simulation`,
  `portfolio.factors`, `pricing.analytics`; FRED CPI inflation.
* "How to use this page" on every page; author credit in the sidebar.

## 0.1.0 — 2026-11-06

First public release.

* **pricing**: Black-Scholes-Merton & Greeks, Black-76, implied volatility; CRR and
  Leisen-Reimer trees (European/American); Monte-Carlo (European, Asian, barrier) with
  variance reduction; closed-form barriers; IV surface from live chains with SVI; strategies.
* **portfolio**: Markowitz family, Ledoit-Wolf, risk parity, Black-Litterman, CAPM, performance.
* **risk**: 5 VaR/ES methods, component VaR, Kupiec/Christoffersen, Basel zones, historical
  and hypothetical stress tests.
* **timeseries**: ARMA with order selection, GARCH/GJR-GARCH (normal, t), ADF, ACF/PACF,
  Ljung-Box, OHLC volatility estimators, volatility cone.
* **credit**: logistic PD with inference, OLS (HC1), AUC/Gini/KS, WoE/IV, calibration,
  scorecards, Merton/KMV, Altman Z.
* **data**: Yahoo, Polygon, FMP, Alpha Vantage, FRED; disk cache; provenance on every frame.
* **viz**: 25 Plotly charts. **app**: 8-page Streamlit dashboard.
* 8 step-by-step tutorials, executed in CI.
