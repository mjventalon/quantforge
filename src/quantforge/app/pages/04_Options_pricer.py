from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    cached_chain,
    cached_curve,
    cached_expiries,
    chart,
    download_csv,
    guard,
    history,
    page_setup,
    pct,
    risk_free,
    source_note,
    ticker_input,
)
from quantforge.pricing import (
    binomial_price,
    bs_greeks,
    expected_move,
    implied_forward,
    implied_volatility,
    max_pain,
    mc_european,
    prob_in_the_money,
    put_call_ratios,
    simulate_gbm_paths,
)
from quantforge.viz import (
    convergence_chart,
    greek_profile,
    greek_surface,
    max_pain_chart,
    mc_paths_fan,
    open_interest_chart,
)

HOW_TO = """1. Type a **ticker** (e.g. AAPL) and pick an **expiry** from the real option chain.
2. Choose **call or put**, a **strike**, and **American** (US stock options) or European.
3. Compare the three model prices with the **market mid** at the top. Gaps tell you if the option looks rich or cheap *for the volatility you chose*.
4. Tabs below: Greeks, 3-D Greek surface, Monte-Carlo paths, convergence, and **open interest / expected move / max pain** for the whole expiry."""

page_setup("Options pricer", "🧮", HOW_TO)
prov = st.session_state.get("provider", "yahoo")

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    ticker = ticker_input()
hist = history(ticker, date.today().replace(year=date.today().year - 2), date.today())
spot = float(hist["close"].iloc[-1])
c2.metric("Spot (last close)", f"{spot:,.2f}", help=f"{hist.index[-1]:%Y-%m-%d}, {source_note()}")

expiries = guard(cached_expiries, prov, ticker, what="option expiries")
if not expiries:
    st.error(f"{ticker} has no listed options at this provider.")
    st.stop()
with c3:
    expiry = st.selectbox("Expiry", expiries, index=min(3, len(expiries) - 1))
chain = guard(cached_chain, prov, ticker, expiry, what="option chain")
T = max((pd.Timestamp(expiry) - pd.Timestamp(date.today())).days, 1) / 365.0

# --- risk-free rate interpolated on the real Treasury curve ---
try:
    curve = cached_curve()
    r = float(np.interp(T, curve.index.to_numpy(), curve.to_numpy()))
    r_src = f"FRED Treasury curve interpolated at {T * 365:.0f} days"
except Exception:  # noqa: BLE001
    r = risk_free("3M")
    r_src = "3M Treasury"

fwd = implied_forward(chain, spot, r, T)
q_implied = r - np.log(fwd / spot) / T

c1, c2, c3, c4 = st.columns(4)
opt_type = c1.radio("Type", ["call", "put"], horizontal=True)
strikes = sorted(chain.loc[chain["type"] == opt_type, "strike"].unique())
atm_i = int(np.argmin(np.abs(np.array(strikes) - spot)))
K = c2.selectbox("Strike", strikes, index=atm_i)
style = c3.radio("Exercise", ["american", "european"], horizontal=True,
                 help="US single-stock options are American.")
q = c4.number_input("Dividend yield / carry (%)", value=round(q_implied * 100, 3),
                    help="Default: carry implied by put-call parity on the live chain.") / 100

row = chain[(chain["type"] == opt_type) & (chain["strike"] == K)].iloc[0]
mid = float(row["mid"])
try:
    iv_mkt = float(implied_volatility(mid, spot, K, T, r, opt_type, q))
except ValueError:
    iv_mkt = np.nan

lr = np.log(hist["adj_close"]).diff().dropna()
hv = float(lr.iloc[-63:].std() * np.sqrt(252))
vol_choice = st.radio("Volatility input", ["Market implied (this contract)", "Historical 63d",
                                           "Custom"], horizontal=True)
if vol_choice.startswith("Market") and np.isfinite(iv_mkt):
    sigma = iv_mkt
elif vol_choice.startswith("Historical"):
    sigma = hv
else:
    sigma = st.slider("σ (%)", 5.0, 200.0, round((iv_mkt if np.isfinite(iv_mkt) else hv) * 100,
                                                  1)) / 100

st.markdown(f"**Inputs** — S = {spot:,.2f} · K = {K:,.2f} · T = {T * 365:.0f} days · "
            f"r = {pct(r)} ({r_src}) · q = {pct(q)} · σ = {pct(sigma)}")

g = bs_greeks(spot, K, T, r, sigma, opt_type, q)
tree = binomial_price(spot, K, T, r, sigma, opt_type, style, q, steps=801)
mc = mc_european(spot, K, T, r, sigma, opt_type, q, n_paths=200_000, seed=None)

m = st.columns(5)
m[0].metric("Market mid", f"{mid:,.3f}", help=f"bid {row['bid']:.2f} / ask {row['ask']:.2f}")
m[1].metric("Black-Scholes (Euro)", f"{g.price:,.3f}", f"{g.price - mid:+.3f} vs mid")
m[2].metric(f"Binomial LR ({style})", f"{tree.price:,.3f}", f"{tree.price - mid:+.3f} vs mid")
lo, hi = mc.conf_interval
m[3].metric("Monte-Carlo (Euro)", f"{mc.price:,.3f}", help=f"95% CI [{lo:.3f}, {hi:.3f}]")
m[4].metric("Implied vol (mid)", pct(iv_mkt), help=f"Provider IV: {pct(row['implied_vol'])}")

greeks_tbl = pd.DataFrame({
    "Delta": [g.delta, tree.delta], "Gamma": [g.gamma, tree.gamma],
    "Vega (per 1 vol pt)": [g.vega / 100, np.nan],
    "Theta (per day)": [g.theta / 365, tree.theta / 365],
    "Rho (per 1%)": [g.rho / 100, np.nan],
}, index=["Black-Scholes", f"Binomial ({style})"])
st.dataframe(greeks_tbl.map(lambda v: "—" if pd.isna(v) else f"{v:.5f}"), width="stretch")

t0, t1, t2, t3, t4 = st.tabs(["Open interest & expected move", "Greeks vs spot",
                              "Greek surface", "Monte-Carlo paths",
                          "Convergence"])
with t1:
    s_grid = np.linspace(spot * 0.6, spot * 1.4, 300)
    gg = bs_greeks(s_grid, K, T, r, sigma, opt_type, q)
    chart(greek_profile(s_grid, {k: np.asarray(getattr(gg, k)) for k in
                                           ("price", "delta", "gamma", "vega", "theta", "rho")},
                                  spot, f"{ticker} {expiry} {K:g} {opt_type} — Greeks"),
                    width="stretch")
with t2:
    greek = st.selectbox("Greek", ["delta", "gamma", "vega", "theta", "price"])
    s_ax = np.linspace(spot * 0.7, spot * 1.3, 60)
    t_ax = np.linspace(max(T, 0.02) / 30, max(T, 0.02) * 1.5, 40)
    S, TT = np.meshgrid(s_ax, t_ax)
    z = np.asarray(getattr(bs_greeks(S, K, TT, r, sigma, opt_type, q), greek))
    chart(greek_surface(s_ax, t_ax, z, greek), width="stretch")
with t3:
    paths = simulate_gbm_paths(spot, T, r, sigma, 4000, max(int(T * 252), 10), q)
    chart(mc_paths_fan(paths, T, K, title=f"{ticker} risk-neutral GBM paths "
                                 f"(σ = {pct(sigma, 1)})"), width="stretch")
    st.caption("Risk-neutral simulation with the inputs above: this shows the model's "
               "distribution, not a forecast.")
with t4:
    steps = [10, 25, 50, 100, 200, 400, 800]
    eu = [binomial_price(spot, K, T, r, sigma, opt_type, "european", q, n, "crr").price
          for n in steps]
    chart(convergence_chart(steps, eu, float(g.price), "CRR binomial (European)"),
                    width="stretch")
with t0:
    atm_iv = iv_mkt if np.isfinite(iv_mkt) else sigma
    try:
        em = expected_move(chain, spot, T, atm_iv)
        c = st.columns(4)
        c[0].metric("Expected move (ATM straddle)", f"±{em['straddle']:,.2f}",
                    f"±{em['straddle_pct']:.1%}", delta_color="off",
                    help="Price of the at-the-money call + put. Traders read it as the move "
                         "the market is pricing by expiry.")
        c[1].metric("1-σ range (≈68%)", f"{em['low_1sd']:,.2f} – {em['high_1sd']:,.2f}",
                    help="spot × implied vol × √T")
        p_itm = prob_in_the_money(spot, K, T, r, sigma, opt_type, q)
        c[2].metric(f"P(finish in the money) — {K:g} {opt_type}", f"{p_itm:.1%}",
                    help="Risk-neutral probability from the model (not a forecast).")
        pcr = put_call_ratios(chain)
        c[3].metric("Put/call ratio (open interest)", f"{pcr['oi_pcr']:.2f}",
                    f"volume {pcr['volume_pcr']:.2f}", delta_color="off",
                    help="Above 1 = more puts than calls outstanding (more hedging/bearish).")
    except ValueError as exc:
        st.warning(str(exc))
    if chain["open_interest"].fillna(0).sum() > 0:
        mp, curve = max_pain(chain)
        field = st.radio("Show", ["open_interest", "volume"], horizontal=True,
                         format_func=lambda f: "Open interest" if f == "open_interest" else
                         "Today's volume")
        chart(open_interest_chart(chain, spot, mp, field), key="oi")
        chart(max_pain_chart(curve, mp, spot), key="mp")
        st.caption("Max pain is where option holders as a group would collect the least at "
                   "expiry. It is a curiosity, not a reliable predictor.")
    else:
        st.info("This provider returned no open interest for this expiry.")
    download_csv(chain, f"{ticker}_{expiry}_chain", "⬇️ Download this option chain (CSV)")

st.caption(f"Option data: {source_note()} · expiry {expiry} · quotes may be delayed.")
