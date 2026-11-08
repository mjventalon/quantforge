"""Market regimes (hidden Markov model) and 3-D views of the return distribution."""

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    chart,
    date_range,
    download_csv,
    history,
    md,
    page_setup,
    pct,
    source_note,
    ticker_input,
)
from quantforge.timeseries import fit_hmm, rolling_density_surface, rolling_moments
from quantforge.viz import distribution_surface_chart, regime_chart, regime_probability_chart

HOW_TO = """**Regimes.** Markets switch between calm and stormy phases. A hidden Markov model
learns these phases from returns alone: each regime has its own average return and volatility,
and a probability of switching.
- **Filtered** probabilities use only data up to each day — what you could have known live.
- **Smoothed** probabilities use the whole history — clearer, but they peek into the future, so
  never use them to judge a trading rule.

**3-D distribution surface.** For each date, the shape of the last 3 months of returns. Wide,
flat ridges = turbulence; tall, narrow ridges = calm. Rotate with the mouse. Turn on **live** to
watch today's intraday distribution build up.

**Please be patient: ⏳ allow 2–3 minutes** the first time (or after changing the ticker, the
period or a setting). The regime model and the 3-D surface are recalculated from scratch on
real data — up to 20 years of daily returns. Results are then kept in memory for an hour, so
coming back to the page is instant."""

page_setup("Regimes & 3-D", "🌀", HOW_TO)
st.info("⏳ **Heavy models — allow 2–3 minutes to load** the first time, or after changing the "
        "ticker, the period or a setting: the regime model and the 3-D surface are recalculated "
        "on real data. Results are then cached for an hour.")


@st.cache_data(ttl=3600, show_spinner=False, max_entries=20)
def _hmm(returns: pd.Series, k: int):
    return fit_hmm(returns, k, n_starts=4)


@st.cache_data(ttl=3600, show_spinner=False, max_entries=20)
def _surface(returns: pd.Series, window: int, step: int, pts: int):
    return rolling_density_surface(returns, window, step, pts)

c1, c2 = st.columns([1, 2])
with c1:
    ticker = ticker_input(default="SPY", key="reg_ticker")
with c2:
    start, end = date_range(20, "reg")
px = history(ticker, start, end)["adj_close"]
lr = np.log(px).diff().dropna()

tab = st.tabs(["Regimes", "Distribution surface 3-D", "Live intraday 3-D"])
with tab[0]:
    c = st.columns(3)
    k = c[0].radio("Regimes", [2, 3], horizontal=True)
    mode = c[1].radio("Probabilities", ["filtered", "smoothed"], horizontal=True)
    c[2].caption(f"{len(lr):,} daily log returns · {source_note()}")
    with st.spinner("Fitting the hidden Markov model (EM, 4 random starts) — this can take "
                    "1–2 minutes on 20 years of data…"):
        res = _hmm(lr, k)
    today = res.filtered.iloc[-1]
    m = st.columns(k + 1)
    m[0].metric("Most likely regime today (filtered)", today.idxmax(), f"{today.max():.0%}",
                delta_color="off")
    summ = res.summary()
    for i, lab in enumerate(summ.index):
        m[i + 1].metric(lab, f"vol {pct(summ.loc[lab, 'annual_vol'], 0)}",
                        f"lasts ~{summ.loc[lab, 'expected_duration']:.0f} days", delta_color="off")
    chart(regime_chart(px, res, mode), key="reg_main")
    c1, c2 = st.columns([3, 2])
    c1.dataframe(summ.style.format({"annual_return": "{:.1%}", "annual_vol": "{:.1%}",
                                    "expected_duration": "{:.0f} d", "long_run_share": "{:.0%}",
                                    "share_of_sample": "{:.0%}"}), width="stretch")
    with c2:
        chart(regime_probability_chart(res), key="reg_trans")
    st.caption(f"Log-likelihood {res.loglik:,.1f} · BIC {res.bic:,.1f} · "
               f"{'converged' if res.converged else 'not converged'} in {res.n_iter} iterations. "
               "Estimator validated against the hmmlearn library.")
    download_csv(res.filtered.join(res.smoothed, lsuffix=" (filtered)", rsuffix=" (smoothed)"),
                 f"{ticker}_regimes")

with tab[1]:
    c = st.columns(3)
    window = c[0].select_slider("Window (days)", [21, 42, 63, 126, 252], 63)
    step = c[1].select_slider("Step (days)", [1, 5, 10, 21], 5)
    pts = c[2].slider("Resolution", 40, 120, 70)
    with st.spinner("Building the 3-D surface (one density per date) — please wait…"):
        d, g, dens = _surface(lr, window, step, pts)
        if len(d) > 400:          # keep the 3-D view fluid: at most ~400 slices on screen
            keep = np.unique(np.linspace(0, len(d) - 1, 400).round().astype(int))
            d, dens = d[keep], dens[keep]
        chart(distribution_surface_chart(d, g, dens, ticker), key="dist3d")
    st.caption(f"{len(d):,} dates drawn. Drag to rotate in any direction, scroll to zoom.")
    mom = rolling_moments(lr, window).dropna()
    st.line_chart(mom)
    st.caption("Rolling volatility (annualized), skewness and excess kurtosis — the same "
               "information as the surface, in 2-D.")

with tab[2]:
    live = st.toggle("Live (refresh every 30 s)", False)

    @st.fragment(run_every=30 if live else None)
    def live_surface() -> None:
        import plotly.graph_objects as go

        from quantforge.viz import theme as T
        try:
            bars = md().intraday(ticker, "5d", "5m")
        except Exception as exc:  # noqa: BLE001
            st.error(f"No intraday data: {exc}")
            return
        r = np.log(bars["close"]).diff().dropna()
        if len(r) < 60:
            st.info("Not enough intraday bars yet.")
            return
        d2, g2, dens2 = rolling_density_surface(r, 48, 3, 60)
        x = np.arange(len(d2))
        fig = go.Figure(go.Surface(x=g2 * 1e4, y=x, z=dens2, colorscale="Turbo",
                                   colorbar=dict(title="Density"),
                                   customdata=np.array([[str(t)] * len(g2) for t in d2]),
                                   hovertemplate="%{customdata}<br>return %{x:.1f} bp"
                                                 "<extra></extra>"))
        fig.update_layout(scene=dict(xaxis_title="5-min return (bp)", yaxis_title="Bar #",
                                     zaxis_title="Density"), height=640, uirevision="live3d")
        chart(T.apply(fig, f"{ticker}: 5-minute return distribution, rolling 4-hour window over "
                           f"the last 5 sessions (updated {pd.Timestamp.now():%H:%M:%S})"), key="live3d")

    live_surface()
