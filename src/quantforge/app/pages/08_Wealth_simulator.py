from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import chart, md, page_setup, pct, prices, source_note, tickers_input
from quantforge.portfolio import monthly_portfolio_returns, simulate_wealth
from quantforge.viz import final_wealth_histogram, wealth_fan_chart

HOW_TO = """1. Build a portfolio: tickers + weights (e.g. 60% SPY / 40% AGG).
2. Enter what you start with, what you add **every month**, and for **how many years**.
3. The simulator replays **real historical months** of your portfolio in random order
   (in 12-month blocks), thousands of times. Nothing is assumed to be "normal".
4. Read the fan: the middle line is the typical outcome, the light band covers 90% of outcomes.
5. Tick **inflation** to see results in today's money (uses the latest US CPI from FRED)."""

page_setup("Wealth simulator", "🌱", HOW_TO)

tickers = tickers_input(default="SPY, AGG", key="ws_tickers")
w_df = st.data_editor(pd.DataFrame({"weight": ([0.6, 0.4] if tickers == ["SPY", "AGG"] else
                                               [1 / len(tickers)] * len(tickers))},
                                   index=tickers), width="stretch", key=f"ws_w_{tickers}")
c = st.columns(4)
initial = c[0].number_input("Starting amount ($)", 0.0, 1e9, 10_000.0, 1_000.0)
monthly = c[1].number_input("Added every month ($)", 0.0, 1e7, 500.0, 50.0)
years = c[2].slider("Years", 1, 50, 20)
fee = c[3].number_input("Annual fees (%)", 0.0, 3.0, 0.1, 0.05,
                        help="Fund expense ratios + advisory fees.") / 100
c = st.columns(4)
hist_years = c[0].slider("History used (years)", 5, 40, 20,
                         help="More history = more crises included. Limited by the youngest "
                              "ticker.")
block = c[1].select_slider("Block length (months)", [1, 3, 6, 12, 24], 12,
                           help="Keeps runs of consecutive real months together "
                                "(crashes and recoveries stay realistic).")
goal = c[2].number_input("Goal ($, optional)", 0.0, 1e10, 0.0, 10_000.0)
real = c[3].toggle("Today's dollars (inflation)", True)

px = prices(tickers, date(date.today().year - hist_years, 1, 1), date.today())
w = (w_df["weight"] / w_df["weight"].sum()).reindex(tickers)
monthly_r = monthly_portfolio_returns(px, w)
infl = None
if real:
    try:
        infl, cpi_month = md().inflation()
        st.caption(f"Inflation: {infl:.2%} = latest US CPI year-over-year (FRED, "
                   f"{cpi_month:%b %Y}).")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"FRED CPI unavailable ({exc}); enter today's inflation to continue.")
        v = st.number_input("Annual inflation (%)", 0.0, 20.0, None, placeholder="e.g. 3.0")
        if v is None:
            st.stop()
        infl = v / 100

st.caption(f"Using {len(monthly_r)} real months {monthly_r.index[0]:%b %Y} → "
           f"{monthly_r.index[-1]:%b %Y} · {source_note()} · historical: "
           f"{pct(float((1 + monthly_r).prod() ** (12 / len(monthly_r)) - 1))} per year, "
           f"vol {pct(float(monthly_r.std() * np.sqrt(12)))}")

sim = simulate_wealth(monthly_r, initial, monthly, years, 10_000, block, infl, fee,
                      goal or None, seed=None)
sm = sim.summary()
m = st.columns(5)
m[0].metric("Typical outcome (median)", f"${sm['median_final']:,.0f}")
m[1].metric("Bad case (5%)", f"${sm['p5_final']:,.0f}")
m[2].metric("Good case (95%)", f"${sm['p95_final']:,.0f}")
m[3].metric("You put in", f"${sm['total_contributed']:,.0f}")
if goal:
    m[4].metric("Chance to reach goal", f"{sm['prob_goal']:.0%}")
else:
    m[4].metric("Chance of losing money", f"{sm['prob_loss_vs_contributed']:.0%}",
                help="Share of simulations ending below the total amount you put in.")

chart(wealth_fan_chart(sim, pd.Timestamp.today().normalize()), key="fan")
c1, c2 = st.columns(2)
with c1:
    chart(final_wealth_histogram(sim), key="hist")
with c2:
    st.markdown("**Worst peak-to-trough fall along the way** (investment performance)")
    dd = pd.Series(sim.max_drawdowns)
    st.dataframe(pd.DataFrame({"Drawdown": [dd.quantile(q) for q in (0.5, 0.25, 0.05)]},
                              index=["Typical", "1 in 4", "1 in 20"]).style.format("{:.0%}"),
                 width="stretch")
    st.caption("Expect to live through these drops. Staying invested through them is what "
               "the projection assumes.")
st.caption("Past returns are not a forecast. The bootstrap only reuses months that already "
           "happened in your chosen history window.")
