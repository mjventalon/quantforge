import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    cached_fundamentals,
    chart,
    date_range,
    download_csv,
    page_setup,
    pct,
    prices,
    risk_free,
    source_note,
    tickers_input,
)
from quantforge.portfolio import (
    FACTOR_PROXIES,
    black_litterman,
    build_factor_returns,
    capm_regression,
    efficient_frontier,
    estimate_inputs,
    factor_regression,
    max_sharpe,
    min_variance,
    performance_summary,
    risk_contributions,
    risk_parity,
    security_market_line,
)
from quantforge.viz import (
    correlation_heatmap,
    cumulative_returns,
    efficient_frontier_chart,
    factor_chart,
    rolling_beta_chart,
    sml_chart,
    weights_chart,
)

HOW_TO = """1. Enter your **tickers** and a **benchmark**. Set a max weight per asset to avoid putting everything in one stock.
2. **Frontier** tab: every dot is a possible portfolio; the blue line is the best return for each risk level. ★ = best risk-adjusted (max Sharpe).
3. **Weights & risk**: how much to hold of each asset and how much risk each one brings.
4. **Factors**: what really drives each asset (market, size, value, momentum…).
5. ⚠️ Expected returns come from the past. For an honest test, use **Backtester → Walk-forward portfolio**."""

page_setup("Portfolio optimization", "🎯", HOW_TO)

tickers = tickers_input()
c1, c2, c3, c4 = st.columns(4)
with c1:
    benchmark = st.text_input("Benchmark", "SPY").upper().strip()
with c2:
    estimator = st.selectbox("Covariance estimator", ["ledoit_wolf", "historical", "ewma"])
with c3:
    max_w = st.slider("Max weight per asset", 0.05, 1.0, 1.0, 0.05)
with c4:
    allow_short = st.checkbox("Allow shorting (−30%)", False)
start, end = date_range(5, "pf")

if len(tickers) < 2:
    st.info("Enter at least two tickers.")
    st.stop()
px = prices(list(dict.fromkeys(tickers + [benchmark])), start, end)
rets = px.pct_change().dropna()
asset_rets = rets[tickers]
rf = risk_free("3M")
mu, cov = estimate_inputs(asset_rets, method=estimator)
bounds = (-0.3 if allow_short else 0.0, max_w)
if max_w * len(tickers) < 1:
    st.error("Max weight × number of assets must be ≥ 100%.")
    st.stop()

st.caption(f"{len(rets)} daily observations {rets.index[0]:%Y-%m-%d} → {rets.index[-1]:%Y-%m-%d} "
           f"· {source_note()} · rf = {pct(rf)} (FRED 3M). Expected returns are historical "
           "means: they are noisy estimates, not predictions.")

ms = max_sharpe(mu, cov, rf, bounds)
mv = min_variance(mu, cov, bounds, rf)
rp = risk_parity(cov, mu=mu, risk_free_rate=rf)
ew_w = np.full(len(tickers), 1 / len(tickers))
ew = pd.Series(ew_w, index=tickers)
front = efficient_frontier(mu, cov, 60, bounds)

rng = np.random.default_rng(0)
rw = rng.dirichlet(np.ones(len(tickers)), 4000)
rv = np.sqrt(np.einsum("ij,jk,ik->i", rw, cov.values, rw))
rr = rw @ mu.values
special = {"Max Sharpe": (ms.volatility, ms.expected_return),
           "Min variance": (mv.volatility, mv.expected_return),
           "Risk parity": (rp.volatility, float(rp.weights @ mu)),
           "Equal weight": (float(np.sqrt(ew_w @ cov.values @ ew_w)), float(ew_w @ mu))}

tab = st.tabs(["Frontier", "Weights & risk", "Backtest (in-sample)", "CAPM", "Factors",
               "Black-Litterman", "Correlation"])
with tab[0]:
    chart(efficient_frontier_chart(front, mu, pd.Series(np.sqrt(np.diag(cov)),
                                                                  index=tickers),
                                             special, rf, (rv, rr), source_note()),
                    width="stretch")
    summary = pd.DataFrame({k: {"Expected return": v[1], "Volatility": v[0],
                                "Sharpe": (v[1] - rf) / v[0]} for k, v in special.items()}).T
    st.dataframe(summary.style.format({"Expected return": "{:.2%}", "Volatility": "{:.2%}",
                                       "Sharpe": "{:.3f}"}), width="stretch")
with tab[1]:
    W = pd.DataFrame({"Max Sharpe": ms.weights, "Min variance": mv.weights,
                      "Risk parity": rp.weights, "Equal weight": ew})
    chart(weights_chart(W), width="stretch")
    RC = pd.DataFrame({c: risk_contributions(W[c], cov) for c in W.columns})
    chart(weights_chart(RC, "Share of portfolio risk by asset"),
                    width="stretch")
    download_csv(W, "portfolio_weights", "⬇️ Download weights (CSV)")
with tab[2]:
    st.warning("In-sample backtest: the weights were optimized on this same period, so "
               "results are optimistic. Use it to compare behaviour, not to predict.")
    port = pd.DataFrame({c: asset_rets @ W[c] for c in W.columns})
    port[benchmark] = rets[benchmark]
    chart(cumulative_returns(port, source=source_note()), width="stretch")
    perf = performance_summary(port, rf)
    st.dataframe(perf.style.format("{:.3f}"), width="stretch")
with tab[3]:
    sml = security_market_line(asset_rets, rets[benchmark], rf)
    mkt = rets[benchmark].mean() * 252
    chart(sml_chart(sml, mkt, rf), width="stretch")
    st.dataframe(sml.style.format({"beta": "{:.3f}", "realized_return": "{:.2%}",
                                   "capm_return": "{:.2%}", "alpha": "{:+.2%}",
                                   "alpha_pvalue": "{:.3f}", "r_squared": "{:.3f}"}),
                 width="stretch")
    pick = st.selectbox("Rolling beta for", tickers)
    chart(rolling_beta_chart(rets[pick], rets[benchmark], 126, pick),
                    width="stretch")
    st.text(str(capm_regression(rets[pick], rets[benchmark], rf)))
with tab[4]:
    st.markdown("Which hidden **factors** drive each asset? Factors are built from real ETF "
                "prices: Market (SPY), Size (IWM−SPY), Value (IWD−IWF), Momentum (MTUM−SPY), "
                "Quality (QUAL−SPY), Low vol (USMV−SPY), Rates (IEF).")
    sel = st.multiselect("Factors", list(FACTOR_PROXIES), list(FACTOR_PROXIES)[:5])
    etfs = sorted({e for f in sel for e in FACTOR_PROXIES[f] if e})
    if sel:
        etf_px = prices(etfs, start, end)
        fac = build_factor_returns(etf_px.pct_change().dropna(), rf, sel)
        who = st.selectbox("Asset", tickers + ["Max Sharpe portfolio"])
        y = asset_rets @ ms.weights if who == "Max Sharpe portfolio" else asset_rets[who]
        res = factor_regression(y, fac, rf)
        chart(factor_chart(res, who), key="factors")
        st.dataframe(res.table.style.format({"coef": "{:.4f}", "std_err": "{:.4f}", "t": "{:.2f}",
                                       "p_value": "{:.3f}"}), width="stretch")
        share = res.variance_share
        st.caption("Share of daily variance explained: " + ", ".join(
            f"{k} {v:.0%}" for k, v in share.items()) +
            f" · unexplained (stock-specific) {1 - res.r_squared:.0%}")
with tab[5]:
    st.markdown("Start from equilibrium returns implied by **market weights** and add your "
                "views with a confidence level.")
    if st.button("Load real market caps", help="Fetches each company's market cap from the "
                                               "data provider. ETFs usually have none."):
        caps0 = {}
        for t in tickers:
            try:
                caps0[t] = cached_fundamentals(st.session_state.get("provider", "yahoo"),
                                               t).get("market_cap")
            except Exception:  # noqa: BLE001
                caps0[t] = None
        st.session_state["bl_caps0"] = caps0
    caps0 = st.session_state.get("bl_caps0", {})
    caps_df = pd.DataFrame({"market_cap": [caps0.get(t) or 1.0 for t in tickers]}, index=tickers)
    if caps0 and any(caps0.get(t) is None for t in tickers):
        st.warning("No market cap reported for: " +
                   ", ".join(t for t in tickers if caps0.get(t) is None) + " — set to 1, edit.")
    caps = st.data_editor(caps_df, width="stretch", key=f"bl_caps_{len(caps0)}")
    w_mkt = (caps["market_cap"] / caps["market_cap"].sum()).to_numpy()
    views = st.data_editor(pd.DataFrame({"long": [tickers[0]], "short": [""],
                                         "expected_return_%": [5.0], "confidence": [0.5]}),
                           num_rows="dynamic", width="stretch", key="bl_views",
                           column_config={"long": st.column_config.SelectboxColumn(
                               options=tickers), "short": st.column_config.SelectboxColumn(
                               options=[""] + tickers)})
    views = views.dropna(subset=["long"])
    if len(views):
        P = np.zeros((len(views), len(tickers)))
        for i, v in enumerate(views.itertuples()):
            P[i, tickers.index(v.long)] = 1
            if v.short:
                P[i, tickers.index(v.short)] = -1
        mu_bl, cov_bl = black_litterman(cov, w_mkt, P, views["expected_return_%"] / 100,
                                        views["confidence"].clip(0.01, 1), risk_free_rate=rf)
        bl = max_sharpe(mu_bl, cov_bl, rf, bounds)
        comp = pd.DataFrame({"Historical μ": mu, "Black-Litterman μ": mu_bl,
                             "BL weights": bl.weights})
        st.dataframe(comp.style.format("{:.2%}"), width="stretch")
        chart(weights_chart(pd.DataFrame({"BL max Sharpe": bl.weights,
                                                    "Historical max Sharpe": ms.weights})),
                        width="stretch")
with tab[6]:
    chart(correlation_heatmap(rets, source_note()), width="stretch")
