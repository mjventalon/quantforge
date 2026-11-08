import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    chart,
    date_range,
    history,
    page_setup,
    pct,
    source_note,
    ticker_input,
)
from quantforge.timeseries import acf, adf_test, fit_garch, ljung_box, pacf, select_arma_order
from quantforge.viz import acf_chart, forecast_chart, garch_chart

HOW_TO = """1. Pick a ticker and a date range.
2. **Stationarity & ACF**: prices wander (unit root); returns don't. Squared returns show volatility clustering.
3. **ARMA**: tries to forecast returns — expect wide intervals.
4. **GARCH**: models volatility — current level, long-run level, half-life and a forecast you can compare with option implied vol."""

page_setup("Time series & volatility models", "〰️", HOW_TO)

c1, c2 = st.columns([1, 2])
with c1:
    ticker = ticker_input(default="SPY")
with c2:
    start, end = date_range(8, "ts")
df = history(ticker, start, end)
lr = np.log(df["adj_close"]).diff().dropna().rename(f"{ticker} log return")
st.caption(f"{len(lr)} daily log returns · {source_note()}")

tabs = st.tabs(["Stationarity & ACF", "ARMA", "GARCH"])
with tabs[0]:
    c = st.columns(2)
    for col, (label, s) in zip(c, [("Log price", np.log(df["adj_close"])), ("Log return", lr)]):
        res = adf_test(s)
        col.markdown(f"**ADF — {label}**")
        col.metric("Statistic", f"{res['statistic']:.3f}",
                   "stationary at 5%" if res["stationary_5pct"] else "unit root not rejected",
                   delta_color="normal" if res["stationary_5pct"] else "inverse")
        pv = f" · p-value {res['p_value']:.4f}" if res["p_value"] is not None else ""
        col.caption(f"lags {res['lags']}{pv}")
        col.caption("Critical values: " + ", ".join(f"{k} {v:.2f}" for k, v in
                                                    res["critical_values"].items()))
    nl = st.slider("Lags", 5, 60, 30)
    chart(acf_chart(acf(lr, nl), pacf(lr, nl), len(lr), "Returns ACF / PACF"),
                    width="stretch")
    chart(acf_chart(acf(lr**2, nl), None, len(lr),
                              "Squared returns ACF — volatility clustering"),
                    width="stretch")
    q, p = ljung_box(lr**2, 10)
    st.write(f"Ljung-Box on squared returns (10 lags): Q = {q:.1f}, p = {p:.2e} "
             f"→ {'ARCH effects present' if p < 0.05 else 'no ARCH effects'}")

with tabs[1]:
    c = st.columns(3)
    max_p = c[0].slider("Max p", 0, 4, 2)
    max_q = c[1].slider("Max q", 0, 4, 2)
    crit = c[2].radio("Criterion", ["bic", "aic"], horizontal=True)
    sample = lr.iloc[-1500:]
    with st.spinner("Fitting ARMA grid…"):
        best, table = select_arma_order(sample * 100, max_p, max_q, crit)
    st.markdown(f"**Selected ARMA{best.order}** on the last {len(sample)} returns (in %).")
    st.dataframe(best.summary().style.format("{:.4f}"), width="stretch")
    q, p = ljung_box(best.residuals, 10, sum(best.order))
    st.write(f"Residual Ljung-Box (10 lags): p = {p:.3f}")
    st.dataframe(table.head(8).style.format({"aic": "{:.1f}", "bic": "{:.1f}"}),
                 hide_index=True)
    fc = best.forecast(10)
    chart(forecast_chart(sample * 100, fc, f"{ticker} daily return (%)"),
                    width="stretch")
    st.caption("Daily equity returns are close to unpredictable; wide intervals are the honest "
               "answer.")

with tabs[2]:
    c = st.columns(3)
    dist = c[0].radio("Innovations", ["t", "normal"], horizontal=True)
    asym = c[1].checkbox("GJR leverage term", True)
    horizon = c[2].slider("Forecast horizon (days)", 5, 252, 63)
    with st.spinner("Maximum likelihood…"):
        g = fit_garch(lr, dist, asym)
    m = st.columns(4)
    m[0].metric("Current vol (ann.)", pct(g.conditional_vol.iloc[-1] * np.sqrt(252), 1))
    m[1].metric("Long-run vol", pct(g.long_run_vol, 1))
    m[2].metric("Persistence", f"{g.persistence:.4f}")
    m[3].metric("Half-life", f"{g.half_life:.0f} days")
    fc = g.forecast(horizon)
    chart(garch_chart(lr, g.conditional_vol, forecast=fc, name=ticker),
                    width="stretch")
    st.dataframe(g.summary().style.format("{:.6g}"), width="stretch")
    st.write(f"Log-likelihood {g.loglik:,.1f} · AIC {g.aic:,.1f} · BIC {g.bic:,.1f}")
    pts = [h for h in (5, 21, 63, 126, 252) if h <= horizon]
    st.dataframe(pd.DataFrame({"horizon (days)": pts,
                               "expected avg vol (ann.)": [pct(fc.loc[h, "term_vol_annualized"])
                                                           for h in pts]}), hide_index=True)
    st.caption("Term volatility is the GARCH forecast of average volatility until the horizon — "
               "compare it with option implied vols of the same maturity.")
