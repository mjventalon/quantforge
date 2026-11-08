# Architecture

```
src/quantforge/
├── data/          providers (Yahoo, Massive/Polygon, FMP, Alpha Vantage), FRED, SEC universe,
│                  MarketData facade, disk cache, ticker search
├── pricing/       Black-Scholes & Greeks, trees, Monte-Carlo, barriers, SVI surfaces, strategies
├── portfolio/     Markowitz, Ledoit-Wolf, risk parity, Black-Litterman, CAPM, factors, wealth sim
├── risk/          VaR/ES (5 methods), backtests (Kupiec, Christoffersen, Basel), stress tests
├── timeseries/    ARMA, GARCH/GJR, ADF, cointegration, indicators, HMM regimes, density surfaces
├── backtest/      engine (no look-ahead), strategies, grid search, walk-forward, pairs, Strategy Lab
├── credit/        logistic/OLS, scorecards, Merton/KMV, Altman Z
├── native/        C++17 engine (header-only) + ctypes wrapper, CMake project and C++ tests
├── academy/       curriculum (Markdown + YAML), quizzes, certificates (HMAC), coding exercises
├── viz/           Plotly theme and ~40 charts
└── app/           Streamlit web app: router (app.py), pages/, widgets, branding, assets
```

## Principles

1. **Real data, explicit provenance.** Providers return frames tagged with `source` and
   `retrieved_at` in `DataFrame.attrs`. Failures raise `DataError`; nothing is filled in.
2. **Library first.** Every number in the app comes from a public, tested function in the
   library; pages only gather inputs and draw results.
3. **No look-ahead.** Backtests decide at the close of day *t* and earn day *t+1*; regime
   probabilities shown for trading are *filtered* (causal); rolling estimates use past data only.
4. **Reproducibility.** Monte-Carlo takes seeds; the C++ engine is deterministic regardless of
   thread count and platform (own xoshiro256** generator and Box-Muller).
5. **Validation.** Each model has tests against textbooks or reference libraries
   (`arch`, `statsmodels`, `scikit-learn`, `hmmlearn`); the C++ engine is tested against the
   Python implementation.

## C++ engine

`native/cpp/include/quantforge/*.hpp` is header-only C++17. `native/cpp/src/capi.cpp` exposes a
plain C ABI (`extern "C"`), compiled into a shared library by `quantforge-build-native` (or
CMake) and loaded with `ctypes`. Vectorised calls are split across threads; Monte-Carlo paths
are split into 64 fixed blocks with independent random streams and summed in a fixed order.

## Academy

Chapters are `academy/content/NN_slug.md`: YAML front matter (level, objectives, sources,
quiz) + Markdown body with `{{widget:name}}` placeholders rendered by `app/academy_widgets.py`.
Exercises live in `academy/exercise_bank/*.yaml`. Certificates are
`QF-<chapter>-<yyyymmdd>-<HMAC-SHA256(name|chapter|date)[:10]>`; verification recomputes the
signature, so no database of holders is needed. Progress files are sealed with the same key.

### Code execution model

| Where | Python exercises | C++ exercises |
|---|---|---|
| Your computer (`quantforge-app`) | subprocess, isolated interpreter, CPU/time limits | compiled with your C++ compiler |
| Public server | **in the visitor's browser** (Pyodide/WebAssembly) | downloaded as a ready-to-compile file |

The server never executes visitor code unless `QUANTFORGE_ALLOW_CODE_EXECUTION=1`.

## Web app

`app/app.py` builds the navigation from `app/navigation.py` (one source of truth for sections,
titles, icons and clean URL slugs), renders the sidebar (provider, keys, credits) and runs the
selected page. Live views use `st.fragment(run_every=…)`; charts keep zoom across refreshes with
Plotly `uirevision`.
