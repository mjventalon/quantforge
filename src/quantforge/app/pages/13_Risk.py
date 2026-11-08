from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    chart,
    date_range,
    page_setup,
    pct,
    prices,
    source_note,
    tickers_input,
)
from quantforge.risk import (
    HISTORICAL_SCENARIOS,
    backtest_var,
    historical_stress_test,
    hypothetical_stress_test,
    portfolio_var_decomposition,
    rolling_var,
    var_report,
)
from quantforge.viz import stress_chart, var_backtest_chart, var_distribution

HOW_TO = """1. Enter tickers, **weights** (table), portfolio value and confidence level.
2. **VaR** = loss you should not exceed on 99% of days. **ES** = average loss on the worst 1% of days.
3. **Backtest** checks if the VaR model would have been right in the past (green zone = good).
4. **Historical stress** replays real crises (2008, Covid, 2022…) on *your* portfolio."""

page_setup("Market risk", "🛡️", HOW_TO)

tickers = tickers_input(default="SPY, TLT, GLD, QQQ")
c1, c2, c3, c4 = st.columns(4)
value = c1.number_input("Portfolio value ($)", 1_000.0, 1e10, 1_000_000.0, 10_000.0)
conf = c2.select_slider("Confidence", [0.90, 0.95, 0.975, 0.99, 0.995], 0.99)
horizon = c3.number_input("Horizon (trading days)", 1, 60, 1)
benchmark = c4.text_input("Benchmark (stress proxy)", "SPY").upper()
start, end = date_range(10, "risk")

st.markdown("**Weights** (normalized to 100%)")
w_df = st.data_editor(pd.DataFrame({"weight": [1 / len(tickers)] * len(tickers)}, index=tickers),
                      width="stretch", key=f"w_{'_'.join(tickers)}")
w = (w_df["weight"] / w_df["weight"].sum()).reindex(tickers)

px = prices(list(dict.fromkeys(tickers + [benchmark])), start, end)
rets = px.pct_change().dropna()
port = (rets[tickers] @ w.values).rename("Portfolio")
st.caption(f"{len(port)} daily returns {port.index[0]:%Y-%m-%d} → {port.index[-1]:%Y-%m-%d} · "
           f"{source_note()}")

rep = var_report(port, conf, horizon, value)
hist_row = rep.loc["Historical"]
m = st.columns(4)
m[0].metric(f"Historical VaR {conf:.1%}", f"${hist_row['VaR ($)']:,.0f}", pct(hist_row["VaR"]))
m[1].metric("Historical ES", f"${hist_row['ES ($)']:,.0f}", pct(hist_row["ES"]))
m[2].metric("Worst day in sample", pct(port.min()), f"{port.idxmin():%Y-%m-%d}")
m[3].metric("Annualized vol", pct(port.std() * np.sqrt(252)))

tabs = st.tabs(["VaR & ES", "Contributions", "Backtest", "Historical stress", "Hypothetical"])
with tabs[0]:
    st.dataframe(rep.style.format({"VaR": "{:.3%}", "ES": "{:.3%}", "VaR ($)": "${:,.0f}",
                                   "ES ($)": "${:,.0f}"}), width="stretch")
    h = port if horizon == 1 else np.expm1(np.log1p(port).rolling(horizon).sum()).dropna()
    chart(var_distribution(h, hist_row["VaR"], hist_row["ES"], conf,
                                     f"{horizon}-day portfolio returns"),
                    width="stretch")
with tabs[1]:
    dec = portfolio_var_decomposition(rets[tickers], w, conf, horizon)
    dec["component_var_$"] = dec["component_var"] * value
    st.dataframe(dec.style.format({"weight": "{:.1%}", "marginal_var": "{:.4f}",
                                   "component_var": "{:.3%}", "pct_of_total": "{:.1%}",
                                   "component_var_$": "${:,.0f}"}), width="stretch")
    st.bar_chart(dec["pct_of_total"])
with tabs[2]:
    method = st.radio("Forecast model", ["historical", "normal"], horizontal=True)
    window = st.slider("Estimation window (days)", 100, 1000, 250, 50)
    vf = rolling_var(port, window, conf, method)
    bt = backtest_var(port, vf, conf)
    zone_color = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[bt.basel_zone]
    c = st.columns(4)
    c[0].metric("Exceptions", f"{bt.n_exceptions}", f"expected {bt.expected_exceptions:.1f}")
    c[1].metric("Kupiec p-value", f"{bt.kupiec_pvalue:.3f}")
    c[2].metric("Christoffersen p-value", f"{bt.christoffersen_pvalue:.3f}")
    c[3].metric("Basel zone (last 250d)", f"{zone_color} {bt.basel_zone}")
    chart(var_backtest_chart(port, vf, f"1-day {conf:.1%} VaR backtest ({method})"),
                    width="stretch")
with tabs[3]:
    names = st.multiselect("Scenarios", [s.name for s in HISTORICAL_SCENARIOS],
                           [s.name for s in HISTORICAL_SCENARIOS])
    st.caption("Uses each asset's actual price moves inside each window. Before an asset existed, "
               "its move is estimated as beta × benchmark move and flagged.")
    full = st.checkbox("Load full history for older crises", True)
    longer = prices(list(dict.fromkeys(tickers + [benchmark])), date(1985, 1, 1), end,
                    dropna=False) if full else px
    res = historical_stress_test(longer, w, longer[benchmark].dropna(),
                                 [s for s in HISTORICAL_SCENARIOS if s.name in names], value)
    if res.empty:
        st.info("No scenario overlaps the loaded data.")
    else:
        chart(stress_chart(res), width="stretch")
        show = res[["start", "end", "portfolio_return", "pnl", "benchmark_return",
                    "proxied_assets"]]
        st.dataframe(show.style.format({"portfolio_return": "{:.2%}", "pnl": "${:,.0f}",
                                        "benchmark_return": "{:.2%}"}),
                     width="stretch")
with tabs[4]:
    vm = st.slider("Idiosyncratic stress multiplier", 1.0, 3.0, 1.0, 0.25)
    hyp = hypothetical_stress_test(rets[tickers], w, rets[benchmark], vol_multiplier=vm,
                                   portfolio_value=value)
    st.dataframe(hyp.style.format("{:.2%}").format({"pnl": "${:,.0f}"}),
                 width="stretch")
    st.caption("Each asset moves beta × the market shock (betas estimated on the data above).")
