"""Charts for v0.3 pro features: live intraday, regimes, distribution surfaces,
Strategy Lab (diversity heatmap, trade Monte-Carlo, folds) and 3-D parameter surfaces."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import theme as T

__all__ = ["live_chart", "regime_chart", "distribution_surface_chart", "diversity_heatmap",
           "trade_mc_chart", "folds_chart", "param_surface_3d", "lab_equity_chart",
           "regime_probability_chart"]

REGIME_COLORS = ["rgba(39,174,96,0.16)", "rgba(230,126,34,0.16)", "rgba(192,57,43,0.20)",
                 "rgba(142,68,173,0.18)"]


def live_chart(bars: pd.DataFrame, ticker: str, prev_close: float | None = None,
               style: str = "candles", vwap: bool = True, title: str | None = None) -> go.Figure:
    """Price chart with volume, VWAP (intraday only) and the previous close.

    Works for intraday bars (minutes, hours) and for long daily/weekly histories."""
    step = pd.Series(bars.index).diff().median() if len(bars) > 2 else pd.Timedelta(minutes=1)
    intraday = step < pd.Timedelta(hours=20)
    vwap = vwap and intraday
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22],
                        vertical_spacing=0.02)
    if style == "candles":
        fig.add_trace(go.Candlestick(x=bars.index, open=bars["open"], high=bars["high"],
                                     low=bars["low"], close=bars["close"], name=ticker,
                                     increasing_line_color=T.GAIN, decreasing_line_color=T.LOSS),
                      row=1, col=1)
    else:
        up = prev_close is None or bars["close"].iloc[-1] >= prev_close
        fig.add_trace(go.Scatter(x=bars.index, y=bars["close"], name=ticker, mode="lines",
                                 line=dict(color=T.GAIN if up else T.LOSS, width=2)),
                      row=1, col=1)
    if vwap and bars["volume"].sum() > 0:
        tp = (bars["high"] + bars["low"] + bars["close"]) / 3
        v = (tp * bars["volume"]).cumsum() / bars["volume"].cumsum()
        fig.add_trace(go.Scatter(x=bars.index, y=v, name="VWAP",
                                 line=dict(color=T.PALETTE[4], width=1.4, dash="dot")),
                      row=1, col=1)
    if prev_close is not None:
        fig.add_hline(y=prev_close, line_dash="dash", line_color=T.NEUTRAL, row=1, col=1,
                      annotation_text=f"Prev. close {prev_close:,.2f}",
                      annotation_position="bottom right")
    last = float(bars["close"].iloc[-1])
    fig.add_hline(y=last, line_color=T.ACCENT, line_width=1, row=1, col=1,
                  annotation_text=f"{last:,.2f}", annotation_position="right")
    colors = np.where(bars["close"] >= bars["open"], T.GAIN, T.LOSS)
    fig.add_trace(go.Bar(x=bars.index, y=bars["volume"], marker_color=colors, opacity=0.6,
                         name="Volume", showlegend=False), row=2, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False, height=560,
                      uirevision=f"{ticker}-{step}",
                      transition=dict(duration=300, easing="cubic-in-out"))
    if ticker.endswith(("-USD", "=X")):
        breaks = []
    elif intraday:
        breaks = [dict(bounds=["sat", "mon"]), dict(bounds=[16, 9.5], pattern="hour")]
    elif step < pd.Timedelta(days=6):
        breaks = [dict(bounds=["sat", "mon"])]
    else:
        breaks = []
    fig.update_xaxes(rangebreaks=breaks)
    return T.apply(fig, title or f"{ticker} — {'intraday' if intraday else 'history'}")


def _shade_regimes(fig: go.Figure, states: pd.Series, labels: list[str], row: int | None = None
                   ) -> None:
    s = states.to_numpy()
    idx = states.index
    start = 0
    for i in range(1, len(s) + 1):
        if i == len(s) or s[i] != s[start]:
            kw = dict(row=row, col=1) if row else {}
            fig.add_vrect(x0=idx[start], x1=idx[i - 1], fillcolor=REGIME_COLORS[s[start] % 4],
                          line_width=0, layer="below", **kw)
            start = i


def regime_chart(prices: pd.Series, res, probs: str = "filtered", threshold: float = 0.5
                 ) -> go.Figure:
    """Price (log scale) shaded by the most likely regime + regime probability panel."""
    p = res.filtered if probs == "filtered" else res.smoothed
    labels = list(p.columns)
    states = pd.Series(p.to_numpy().argmax(axis=1), index=p.index)
    px = prices.reindex(p.index)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.68, 0.32],
                        vertical_spacing=0.04,
                        subplot_titles=["Price, shaded by regime",
                                        f"{probs.capitalize()} probability of each regime"])
    fig.add_trace(go.Scatter(x=px.index, y=px, line=dict(color=T.ACCENT, width=1.6),
                             name="Price"), row=1, col=1)
    _shade_regimes(fig, states, labels, row=1)
    cols = [T.GAIN, T.PALETTE[1], T.LOSS, T.PALETTE[4]]
    for i, lab in enumerate(labels):
        fig.add_trace(go.Scatter(x=p.index, y=p[lab], name=lab, stackgroup="p",
                                 line=dict(width=0.5, color=cols[i % 4])), row=2, col=1)
    fig.update_yaxes(type="log", row=1, col=1)
    fig.update_yaxes(range=[0, 1], tickformat=".0%", row=2, col=1)
    fig.update_layout(height=680)
    note = ("filtered = real-time information only" if probs == "filtered"
            else "smoothed = uses future data, for description only")
    return T.apply(fig, f"Market regimes (hidden Markov model, {len(labels)} states) — {note}")


def regime_probability_chart(res) -> go.Figure:
    a = res.transition
    labels = list(res.filtered.columns)
    fig = go.Figure(go.Heatmap(z=a, x=labels, y=labels, colorscale="Blues", zmin=0, zmax=1,
                               text=np.round(a, 3), texttemplate="%{text}",
                               colorbar=dict(title="P")))
    fig.update_yaxes(autorange="reversed", title_text="From")
    fig.update_xaxes(title_text="To")
    fig.update_layout(hovermode="closest", height=360)
    return T.apply(fig, "Daily transition probabilities")


def distribution_surface_chart(dates: pd.DatetimeIndex, grid: np.ndarray, dens: np.ndarray,
                               ticker: str = "", highlight: dict[str, str] | None = None
                               ) -> go.Figure:
    fig = go.Figure(go.Surface(x=grid * 100, y=dates, z=dens, colorscale="Turbo",
                               colorbar=dict(title="Density"),
                               contours=dict(z=dict(show=True, usecolormap=True,
                                                    project_z=True))))
    fig.update_layout(scene=dict(xaxis_title="Return (%)", yaxis_title="Date",
                                 zaxis_title="Density",
                                 camera=dict(eye=dict(x=1.6, y=-1.6, z=0.9))), height=700)
    return T.apply(fig, f"{ticker} — distribution of returns through time (rolling kernel "
                        "density, past data only)")


def diversity_heatmap(report: dict) -> go.Figure:
    c = report["corr"]
    cls = report["classes"]
    code = cls.replace({"diversifying": 0, "unrelated": 1, "redundant": 2}).astype(float)
    z = code.to_numpy(dtype=float, copy=True)   # pandas copy-on-write views are read-only
    np.fill_diagonal(z, np.nan)
    code = pd.DataFrame(z, index=code.index, columns=code.columns)
    scale = [[0, "#27AE60"], [0.33, "#27AE60"], [0.34, "#B9770E"], [0.66, "#B9770E"],
             [0.67, "#C0392B"], [1, "#C0392B"]]
    short = [s if len(s) < 28 else s[:26] + "…" for s in c.columns]
    fig = go.Figure(go.Heatmap(z=code.values, x=short, y=short, colorscale=scale, zmin=0, zmax=2,
                               customdata=np.round(c.values, 2), showscale=False,
                               hovertemplate="%{y}<br>%{x}<br>ρ = %{customdata}<extra></extra>",
                               text=np.round(c.values, 2), texttemplate="%{text}"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=max(420, 36 * len(c)), hovermode="closest")
    return T.apply(fig, f"Return correlation — 🟩 diversifying · 🟧 unrelated · 🟥 redundant "
                        f"· Diversity {report['score']:.0f}/100 (grade {report['grade']})")


def trade_mc_chart(mc: dict, initial: float) -> go.Figure:
    p = mc["percentiles"]
    x = np.arange(len(p))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=p["p95"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=p["p5"], fill="tonexty", fillcolor=T.BAND_FILL,
                             line=dict(width=0), name="5–95%"))
    fig.add_trace(go.Scatter(x=x, y=p["p75"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=p["p25"], fill="tonexty", fillcolor=T.BAND_FILL_2,
                             line=dict(width=0), name="25–75%"))
    fig.add_trace(go.Scatter(x=x, y=p["p50"], line=dict(color=T.ACCENT, width=3), name="Median"))
    fig.add_hline(y=initial, line_dash="dot", line_color=T.NEUTRAL, annotation_text="Start")
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    v = mc["verdict"]
    return T.apply(fig, f"Monte-Carlo of {mc['n_trades']} resampled trades — {v} · "
                        f"P(profit) {mc['p_profit']:.0%} · median ${mc['median_final']:,.0f} · "
                        f"p95 max DD {mc['p95_max_drawdown']:.1%}", "Trade #", "Equity")


def folds_chart(folds: pd.DataFrame) -> go.Figure:
    colors = np.where(folds["return"] > 0, T.GAIN, T.LOSS)
    labels = [f"Fold {i}<br>{r.start:%Y-%m}→{r.end:%Y-%m}" for i, r in folds.iterrows()]
    fig = go.Figure(go.Bar(x=labels, y=folds["return"], marker_color=colors,
                           text=[f"{v:+.1%} · SR {s:.2f}" for v, s in
                                 zip(folds["return"], folds["sharpe"])], textposition="outside"))
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(hovermode="closest")
    return T.apply(fig, f"Chronological folds — profitable {folds.attrs.get('profitable_folds')}"
                        f"/{len(folds)}", "", "Return")


def lab_equity_chart(returns: pd.DataFrame, portfolio: pd.Series | None = None) -> go.Figure:
    fig = go.Figure()
    for i, c in enumerate(returns.columns):
        eq = (1 + returns[c]).cumprod()
        fig.add_trace(go.Scatter(x=eq.index, y=eq, name=c, opacity=0.55,
                                 line=dict(width=1, color=T.PALETTE[i % 10])))
    if portfolio is not None:
        eq = (1 + portfolio).cumprod()
        fig.add_trace(go.Scatter(x=eq.index, y=eq, name="Combined portfolio",
                                 line=dict(width=4, color="#E4141D")))
        fig.add_annotation(x=eq.index[-1], y=eq.iloc[-1], text=f"{eq.iloc[-1] - 1:+.0%}",
                           showarrow=False, xanchor="left", font=dict(color="#E4141D"))
    fig.update_yaxes(type="log")
    fig.update_layout(legend=dict(orientation="v", x=1.02, y=1, xanchor="left"))
    return T.apply(fig, "Every strategy (thin) and the combined book (bold)", "Date",
                   "Growth of $1")


def param_surface_3d(table: pd.DataFrame, x: str, y: str, z: str) -> go.Figure:
    pv = table.pivot_table(index=y, columns=x, values=z)
    fig = go.Figure(go.Surface(x=pv.columns.astype(float), y=pv.index.astype(float), z=pv.values,
                               colorscale="RdYlGn", cmid=0, colorbar=dict(title=z),
                               contours=dict(z=dict(show=True, usecolormap=True,
                                                    project_z=True))))
    fig.update_layout(scene=dict(xaxis_title=x, yaxis_title=y, zaxis_title=z), height=640)
    return T.apply(fig, f"{z} across the parameter space — look for plateaus, not peaks")
