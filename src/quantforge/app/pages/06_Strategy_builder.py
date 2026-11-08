from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    cached_chain,
    cached_expiries,
    chart,
    guard,
    history,
    page_setup,
    pct,
    risk_free,
    source_note,
    ticker_input,
)
from quantforge.pricing import implied_forward, implied_volatility
from quantforge.pricing.strategies import PRESETS, OptionLeg, StockLeg, Strategy
from quantforge.viz import greek_profile, payoff_diagram

HOW_TO = """1. Pick a ticker, an expiry and a **template** (straddle, iron condor…).
2. Edit the legs in the table: change strikes, quantities (+ buy / − sell), add or delete rows.
3. Premiums are the **live bid/ask mids**. Read net cost, max profit/loss and break-evens.
4. Green zone = profit at expiry, red zone = loss. The dashed line is the value *today*."""

page_setup("Option strategy builder", "🧩", HOW_TO)
prov = st.session_state.get("provider", "yahoo")

c1, c2, c3 = st.columns(3)
with c1:
    ticker = ticker_input()
expiries = guard(cached_expiries, prov, ticker, what="option expiries")
expiry = c2.selectbox("Expiry", expiries, index=min(3, len(expiries) - 1))
preset = c3.selectbox("Template", list(PRESETS))
contracts = st.number_input("Contracts (×100 shares)", 1, 1000, 1)

hist = history(ticker, date.today().replace(year=date.today().year - 1), date.today())
spot = float(hist["close"].iloc[-1])
chain = guard(cached_chain, prov, ticker, expiry, what="option chain")
T = max((pd.Timestamp(expiry) - pd.Timestamp(date.today())).days, 1) / 365
r = risk_free("3M")
q = r - np.log(implied_forward(chain, spot, r, T) / spot) / T

strikes = np.array(sorted(chain["strike"].unique()))


def nearest(k: float) -> float:
    return float(strikes[np.argmin(np.abs(strikes - k))])


st.subheader("Legs (premiums = live mid prices)")
template = PRESETS[preset](spot)
rows = []
for leg in template:
    if isinstance(leg, StockLeg):
        rows.append({"instrument": "stock", "strike": None, "quantity": leg.quantity})
    else:
        rows.append({"instrument": leg.option_type, "strike": nearest(leg.strike),
                     "quantity": leg.quantity})
legs_df = st.data_editor(pd.DataFrame(rows), num_rows="dynamic", width="stretch",
                         column_config={
                             "instrument": st.column_config.SelectboxColumn(
                                 options=["call", "put", "stock"], required=True),
                             "strike": st.column_config.SelectboxColumn(options=list(strikes)),
                             "quantity": st.column_config.NumberColumn(step=1.0),
                         }, key=f"legs_{preset}_{ticker}")

legs, quotes = [], []
for _, row in legs_df.dropna(subset=["instrument"]).iterrows():
    if row["instrument"] == "stock":
        legs.append(StockLeg(float(row["quantity"]), spot))
        quotes.append({"leg": "stock", "price": spot, "iv": None})
        continue
    c = chain[(chain["type"] == row["instrument"]) & (chain["strike"] == row["strike"])]
    if c.empty:
        st.error(f"No {row['instrument']} at strike {row['strike']} for {expiry}")
        st.stop()
    c = c.iloc[0]
    try:
        iv = float(implied_volatility(c["mid"], spot, c["strike"], T, r, row["instrument"], q))
    except ValueError:
        st.error(f"Quote for {row['instrument']} {row['strike']} violates arbitrage bounds")
        st.stop()
    legs.append(OptionLeg(row["instrument"], float(c["strike"]), float(row["quantity"]),
                          volatility=iv, premium=float(c["mid"])))
    quotes.append({"leg": f"{row['quantity']:+g} {row['instrument']} {c['strike']:g}",
                   "bid": c["bid"], "ask": c["ask"], "mid": c["mid"], "iv": iv})

strat = Strategy(legs, name=preset, multiplier=100 * contracts)
cost = strat.entry_cost(spot, T, r, 0.3, q)
grid = np.linspace(spot * 0.6, spot * 1.4, 600)
pnl_exp = strat.profit_at_expiry(grid, spot, T, r, 0.3, q)
today = strat.value(grid, T, r, 0.3, q)["price"] - cost
bes = strat.breakevens(spot, T, r, 0.3, q)

m = st.columns(5)
m[0].metric("Net debit / credit", f"{cost:,.2f}", help="Positive = you pay")
m[1].metric("Max profit (in range)", f"{pnl_exp.max():,.2f}")
m[2].metric("Max loss (in range)", f"{pnl_exp.min():,.2f}")
m[3].metric("Break-evens", ", ".join(f"{b:,.2f}" for b in bes) or "—")
now = strat.value(spot, T, r, 0.3, q)
m[4].metric("Position delta", f"{now['delta'][0]:,.1f} sh")

chart(payoff_diagram(grid, pnl_exp, today, spot, bes,
                               f"{ticker} {preset} — {expiry} ({contracts} contract(s))"),
                width="stretch")
st.dataframe(pd.DataFrame(quotes).style.format({"bid": "{:.2f}", "ask": "{:.2f}",
                                                "mid": "{:.2f}", "iv": "{:.2%}"}, na_rep="—"),
             width="stretch", hide_index=True)
vals = strat.value(grid, T, r, 0.3, q)
vals["price"] = vals["price"] - cost
chart(greek_profile(grid, vals, spot, "Position Greeks (each leg at its own market IV)"),
                width="stretch")
st.caption(f"Quotes: {source_note()} · r = {pct(r)} (FRED) · carry q = {pct(q)} "
           "(from put-call parity). Excludes commissions and early-assignment risk.")
