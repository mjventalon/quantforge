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
from quantforge.pricing import chain_implied_vols, surface_grid
from quantforge.viz import vol_smile, vol_surface_3d

HOW_TO = """1. Type a ticker with liquid options (SPY, QQQ, AAPL…).
2. Choose how many **expiries** to load and how strict the **spread filter** is (lower = cleaner but fewer quotes).
3. Read the **smiles** (one curve per expiry), then rotate the **3-D surface** with the mouse.
4. The table shows the SVI fit and the **ATM volatility term structure**."""

page_setup("Implied volatility surface", "🌋", HOW_TO)
prov = st.session_state.get("provider", "yahoo")

c1, c2, c3 = st.columns(3)
with c1:
    ticker = ticker_input(default="SPY")
expiries = guard(cached_expiries, prov, ticker, what="option expiries")
n_exp = c2.slider("Number of expiries", 2, min(16, max(len(expiries), 2)), min(8, len(expiries)))
max_spread = c3.slider("Max bid-ask spread (% of mid)", 5, 100, 40) / 100

hist = history(ticker, date.today().replace(year=date.today().year - 1), date.today())
spot = float(hist["close"].iloc[-1])
r = risk_free("3M")

frames = []
prog = st.progress(0.0, "Loading expiries…")
selected = [e for e in expiries if (pd.Timestamp(e) - pd.Timestamp(date.today())).days >= 3][:n_exp]
for i, e in enumerate(selected):
    try:
        frames.append(cached_chain(prov, ticker, e))
    except Exception as exc:  # noqa: BLE001
        st.warning(f"{e}: {exc}")
    prog.progress((i + 1) / len(selected), f"Loaded {e}")
prog.empty()
if not frames:
    st.error("No option data loaded.")
    st.stop()
chain = pd.concat(frames, ignore_index=True)

ivs = guard(chain_implied_vols, chain, spot, r, max_rel_spread=max_spread, what="implied vols")
st.markdown(f"Spot **{spot:,.2f}** · r = **{pct(r)}** (FRED 3M) · **{len(ivs)}** OTM quotes "
            f"passed quality filters out of {len(chain)} contracts.")

try:
    k, t, surf, params = surface_grid(ivs)
except ValueError as exc:
    st.warning(f"SVI surface unavailable: {exc}")
    params = None

chart(vol_smile(ivs, params, source=source_note()), width="stretch")
if params is not None:
    chart(vol_surface_3d(k, t, surf, ivs, source=source_note()),
                    width="stretch")
    atm = params.assign(days=(params["T"] * 365).round(),
                        atm_vol=np.sqrt(np.maximum(params["a"] + params["b"] * (
                            -params["rho"] * params["m"] + np.sqrt(params["m"] ** 2 +
                                                                   params["sigma"] ** 2)), 0)
                                        / params["T"]))
    st.subheader("SVI parameters and ATM term structure")
    st.dataframe(atm[["days", "atm_vol", "a", "b", "rho", "m", "sigma", "rmse_vol"]]
                 .style.format({"atm_vol": "{:.2%}", "rmse_vol": "{:.3%}", "days": "{:.0f}"},
                               precision=4), width="stretch", hide_index=True)
    st.line_chart(atm.set_index("days")["atm_vol"])

with st.expander("Raw implied vols"):
    st.dataframe(ivs[["expiry", "type", "strike", "bid", "ask", "mid", "iv", "provider_iv",
                      "log_moneyness"]], width="stretch", hide_index=True)
