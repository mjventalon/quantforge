import streamlit as st

from quantforge.app.common import (
    chart,
    date_range,
    download_csv,
    page_setup,
    pct,
    prices,
    risk_free,
    source_note,
)
from quantforge.backtest import pairs_backtest
from quantforge.timeseries import engle_granger
from quantforge.viz import pairs_chart

HOW_TO = """1. Choose two assets that should move together (same industry: KO / PEP, XOM / CVX,
   GLD / GDX, two share classes like GOOGL / GOOG…).
2. The **cointegration test** says whether the gap between them tends to close again
   (p-value below 0.05 = yes, statistically).
3. The **z-score** measures how stretched the gap is today. When it goes above the entry
   level the strategy sells the expensive one and buys the cheap one, then closes when the
   gap is back to normal.
4. Everything uses only past data (rolling hedge ratio)."""

page_setup("Pairs trading", "🔗", HOW_TO)

c = st.columns(3)
a = c[0].text_input("Asset Y", "KO").upper().strip()
b = c[1].text_input("Asset X", "PEP").upper().strip()
with c[2]:
    start, end = date_range(8, "pairs")
px = prices([a, b], start, end)

ct = engle_granger(px[a], px[b])
m = st.columns(4)
m[0].metric("Hedge ratio β", f"{ct.hedge_ratio:.3f}", help="Units of X per unit of Y "
                                                           "(log prices).")
m[1].metric("Cointegration p-value", "—" if ct.p_value is None else f"{ct.p_value:.3f}",
            "cointegrated" if ct.cointegrated_5pct else "not cointegrated",
            delta_color="normal" if ct.cointegrated_5pct else "inverse")
m[2].metric("Half-life of the gap", f"{ct.half_life:.0f} days" if ct.half_life < 1e4 else "∞")
m[3].metric("Correlation of returns", f"{px.pct_change().corr().iloc[0, 1]:.2f}")
if not ct.cointegrated_5pct:
    st.warning("The test does not find a stable long-run link over this period: a pairs "
               "strategy is risky here. Try another pair or period.")

c = st.columns(4)
window = c[0].slider("Rolling window (days)", 40, 252, 120)
entry = c[1].slider("Entry |z|", 1.0, 3.5, 2.0, 0.25)
exit_ = c[2].slider("Exit |z|", 0.0, 1.5, 0.5, 0.25)
cost = c[3].number_input("Cost per leg (bps)", 0.0, 50.0, 5.0)
if exit_ >= entry:
    st.error("Exit must be below entry.")
    st.stop()
res = pairs_backtest(px[a], px[b], window, entry, exit_, cost, risk_free("3M"))
mt = res.metrics["Pairs strategy"]
m = st.columns(5)
m[0].metric("Today's z-score", f"{res.zscore.iloc[-1]:+.2f}")
m[1].metric("CAGR", pct(mt["CAGR"]))
m[2].metric("Sharpe", f"{mt['Sharpe']:.2f}")
m[3].metric("Max drawdown", pct(mt["Max drawdown"], 1))
m[4].metric("Trades", f"{int(mt['Trades'])}", f"in market {mt['Time in market']:.0%}",
            delta_color="off")
chart(pairs_chart(px[a], px[b], res, entry, exit_), key="pairs")
download_csv(res.zscore.to_frame().join(res.position), f"pairs_{a}_{b}")
st.caption(f"{source_note()} · Static full-sample test shown above; the strategy itself uses "
           "rolling estimates only.")
