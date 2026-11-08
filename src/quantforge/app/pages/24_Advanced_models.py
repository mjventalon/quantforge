"""Heston, SABR and Merton jump-diffusion calibrated to a live option chain."""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
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
from quantforge.pricing import (
    HestonParams,
    calibrate_heston,
    calibrate_merton,
    calibrate_sabr,
    chain_implied_vols,
    heston_price,
    merton_jump_price,
    sabr_vol,
)
from quantforge.pricing.stochastic import model_implied_vols
from quantforge.viz.theme import PALETTE
from quantforge.viz.theme import apply as themed

HOW_TO = """1. Pick a ticker with liquid options (SPY, QQQ, AAPL…) and 2–4 expiries.
2. Press **Calibrate**: three models are fitted to the **real implied volatilities**:
   * **SABR** — one smile per expiry (what rates and FX desks quote),
   * **Heston** — stochastic volatility, one parameter set for **all** expiries,
   * **Merton jump-diffusion** — Black-Scholes plus random jumps.
3. Compare the fitted curves with the market dots and the error (RMSE in vol points).
4. Explore the **Heston 3-D surface** and move its parameters to see what each one does."""

page_setup("Advanced models: Heston · SABR · jumps", "🧠", HOW_TO)
prov = st.session_state.get("provider", "yahoo")

c = st.columns([2, 1, 1, 1])
with c[0]:
    ticker = ticker_input(default="SPY", key="adv_ticker")
expiries = guard(cached_expiries, prov, ticker, what="option expiries")
usable = [e for e in expiries if 14 <= (pd.Timestamp(e) - pd.Timestamp(date.today())).days
          <= 400]
if len(usable) < 2:
    st.error("This ticker has fewer than two expiries between 2 weeks and 13 months.")
    st.stop()
pick = c[1].multiselect("Expiries", usable, default=usable[: min(3, len(usable))][:3],
                        max_selections=4)
beta = c[2].select_slider("SABR β", [0.0, 0.5, 0.7, 1.0], 1.0,
                          help="β = 1 lognormal (equities), 0.5 common in rates.")
band = c[3].slider("Moneyness band (±%)", 10, 40, 25) / 100

hist = history(ticker, date.today().replace(year=date.today().year - 1), date.today())
spot = float(hist["close"].iloc[-1])
r = risk_free("3M")

if not pick or not st.button("🎯 Calibrate to the live chain", type="primary"):
    st.info("Choose expiries and press **Calibrate** (about 5–20 seconds).")
    st.stop()

frames = [cached_chain(prov, ticker, e) for e in pick]
ivs = guard(chain_implied_vols, pd.concat(frames, ignore_index=True), spot, r,
            moneyness=(1 - band, 1 + band), max_rel_spread=0.35, what="implied vols")
slices = []
for t, g in ivs.groupby("T"):
    g = g.sort_values("strike")
    if len(g) >= 5:
        slices.append((float(t), g["strike"].to_numpy(), g["iv"].to_numpy(),
                       float(g["forward"].iloc[0])))
if len(slices) < 1:
    st.error("Not enough clean quotes. Widen the band or choose more liquid expiries.")
    st.stop()

with st.spinner("Calibrating SABR, Heston and Merton…"):
    sabr = [calibrate_sabr(f, k, iv, t, beta) for t, k, iv, f in slices]
    hp, h_rmse = calibrate_heston(spot, slices, r)
    mp, m_rmse = calibrate_merton(spot, slices, r)

st.markdown(f"Spot **{spot:,.2f}** · r = **{pct(r)}** (FRED 3M) · "
            f"**{sum(len(s[1]) for s in slices)}** OTM quotes on {len(slices)} expiries.")

fig = go.Figure()
rows = []
for i, ((t, k, iv, f), (sp, s_rmse)) in enumerate(zip(slices, sabr)):
    col = PALETTE[i % len(PALETTE)]
    q = r - np.log(f / spot) / t
    kk = np.linspace(k.min(), k.max(), 60)
    days = round(t * 365)
    fig.add_trace(go.Scatter(x=k, y=iv, mode="markers", marker=dict(color=col, size=7),
                             name=f"{days}d market"))
    fig.add_trace(go.Scatter(x=kk, y=sabr_vol(f, kk, t, sp), line=dict(color=col),
                             name=f"{days}d SABR"))
    hv = model_implied_vols(heston_price(spot, kk, t, r, hp, "call", q), spot, kk, t, r, "call", q)
    fig.add_trace(go.Scatter(x=kk, y=hv, line=dict(color=col, dash="dash"),
                             name=f"{days}d Heston"))
    mv = model_implied_vols(merton_jump_price(spot, kk, t, r, mp, "call", q), spot, kk, t, r,
                            "call", q)
    fig.add_trace(go.Scatter(x=kk, y=mv, line=dict(color=col, dash="dot"),
                             name=f"{days}d Merton", visible="legendonly"))
    rows.append({"Expiry (days)": days, "Quotes": len(k), "SABR α": sp.alpha, "SABR ρ": sp.rho,
                 "SABR ν": sp.nu, "SABR RMSE (vol pts)": s_rmse * 100})
fig.add_vline(x=spot, line_dash="dot", line_color="gray", annotation_text="spot")
fig.update_layout(height=560, xaxis_title="Strike", yaxis_title="Implied volatility",
                  yaxis_tickformat=".0%", hovermode="closest",
                  legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, xanchor="left"))
chart(themed(fig, f"{ticker} smiles — dots: market · solid: SABR · dashed: Heston · "
                  "dotted: Merton (click legend)"), key="adv_smiles")
st.caption(source_note("Market dots: implied vols of real mid prices (out-of-the-money options, "
                       "carry implied by put-call parity)."))

c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.markdown("**Heston (one set for all expiries)**")
    st.dataframe(pd.DataFrame({
        "Parameter": ["v₀ (spot variance)", "κ (mean reversion)", "θ (long-run variance)",
                      "σ (vol of vol)", "ρ (spot–vol correlation)"],
        "Value": [hp.v0, hp.kappa, hp.theta, hp.sigma, hp.rho],
        "Meaning": [f"spot vol ≈ {np.sqrt(hp.v0):.1%}", f"half-life ≈ {np.log(2) / hp.kappa:.2f} y",
                    f"long-run vol ≈ {np.sqrt(hp.theta):.1%}", "smile curvature",
                    "skew (negative = puts dearer)"]}).style.format({"Value": "{:.4f}"}),
        hide_index=True, width="stretch")
    st.caption(f"Fit error ≈ {h_rmse * 100:.2f} vol points · Feller condition "
               f"{'satisfied' if hp.feller else 'not satisfied (variance can touch 0)'}.")
with c2, st.container(border=True):
    st.markdown("**Merton jump-diffusion**")
    st.dataframe(pd.DataFrame({
        "Parameter": ["σ (diffusion vol)", "λ (jumps per year)", "μⱼ (mean log jump)",
                      "δ (jump size std)"],
        "Value": [mp.sigma, mp.lam, mp.mu_j, mp.delta]}).style.format({"Value": "{:.4f}"}),
        hide_index=True, width="stretch")
    st.caption(f"Fit error ≈ {m_rmse * 100:.2f} vol points. Average jump "
               f"{np.exp(mp.mu_j) - 1:+.1%}, about {mp.lam:.2f} per year (risk-neutral).")
    if mp.lam >= 9.99 or mp.delta <= 0.0101 or mp.sigma <= 0.0101:
        st.caption("⚠️ A parameter sits on its bound: this smile is better described by "
                   "Heston/SABR than by rare jumps (many tiny jumps ≈ extra diffusion).")
st.markdown("**SABR, expiry by expiry**")
st.dataframe(pd.DataFrame(rows).style.format({"SABR α": "{:.4f}", "SABR ρ": "{:+.3f}",
                                              "SABR ν": "{:.3f}",
                                              "SABR RMSE (vol pts)": "{:.2f}"}),
             hide_index=True, width="stretch")
st.session_state["adv_heston"] = (hp, spot, r)

st.subheader("Heston implied-volatility surface — play with the parameters")
hp0, s0, r0 = st.session_state["adv_heston"]
c = st.columns(5)
v0 = c[0].slider("spot vol √v₀", 0.05, 0.8, float(np.sqrt(hp0.v0)), 0.01)
th = c[1].slider("long-run vol √θ", 0.05, 0.8, float(np.clip(np.sqrt(hp0.theta), 0.05, 0.8)), 0.01)
ka = c[2].slider("κ", 0.1, 10.0, float(np.clip(hp0.kappa, 0.1, 10)), 0.1)
sg = c[3].slider("σ (vol of vol)", 0.05, 2.0, float(np.clip(hp0.sigma, 0.05, 2)), 0.05)
rh = c[4].slider("ρ", -0.95, 0.95, float(hp0.rho), 0.05)
pp = HestonParams(v0 ** 2, ka, th ** 2, sg, rh)
ts = np.linspace(0.08, 1.5, 14)
ks = np.linspace(0.75, 1.25, 21) * s0
z = np.array([model_implied_vols(heston_price(s0, ks, t, r0, pp), s0, ks, t, r0) for t in ts])
fig = go.Figure(go.Surface(x=ks / s0, y=ts, z=z, colorscale="RdBu_r", showscale=False,
                           hovertemplate="K/S %{x:.2f}<br>T %{y:.2f}y<br>IV %{z:.1%}"))
fig.update_layout(height=560, scene=dict(xaxis_title="Strike / spot", yaxis_title="Years",
                                         zaxis_title="Implied vol", zaxis_tickformat=".0%"),
                  uirevision="heston3d")
chart(themed(fig, "Heston implied volatility surface"), key="adv_surface")

