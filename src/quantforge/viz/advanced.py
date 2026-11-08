"""Charts for v0.2 features: technical analysis, option open interest, backtests,
parameter heatmaps, wealth projections, market heatmaps, pairs and factors."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..timeseries.indicators import bollinger_bands, macd, rsi
from . import theme as T

__all__ = ["technical_chart", "open_interest_chart", "backtest_chart", "param_heatmap",
           "wealth_fan_chart", "final_wealth_histogram", "returns_heatmap", "period_bar_chart",
           "pairs_chart", "factor_chart", "walk_forward_weights_chart", "max_pain_chart"]


def _pct(x: float, d: int = 1) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x * 100:.{d}f}%"


def _money(x: float) -> str:
    return f"${x:,.0f}"


# ------------------------------------------------------------------ technical analysis
def technical_chart(ohlcv: pd.DataFrame, ticker: str = "", sma_windows: Sequence[int] = (50, 200),
                    show_bollinger: bool = True, show_rsi: bool = True, show_macd: bool = True,
                    show_volume: bool = True, source: str | None = None) -> go.Figure:
    """Candles + moving averages + Bollinger bands, with RSI / MACD / volume panels."""
    panels = ["price"] + [p for p, on in (("volume", show_volume), ("rsi", show_rsi),
                                          ("macd", show_macd)) if on]
    heights = {"price": 0.55, "volume": 0.12, "rsi": 0.16, "macd": 0.17}
    h = [heights[p] for p in panels]
    fig = make_subplots(rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[x / sum(h) for x in h])
    close = ohlcv["close"]
    fig.add_trace(go.Candlestick(x=ohlcv.index, open=ohlcv["open"], high=ohlcv["high"],
                                 low=ohlcv["low"], close=close, name=ticker or "Price",
                                 increasing_line_color=T.GAIN, decreasing_line_color=T.LOSS),
                  row=1, col=1)
    for i, w in enumerate(sma_windows):
        if len(ohlcv) > w:
            fig.add_trace(go.Scatter(x=ohlcv.index, y=close.rolling(w).mean(), name=f"SMA {w}",
                                     line=dict(width=1.5, color=T.PALETTE[(i + 1) % 10])),
                          row=1, col=1)
    if show_bollinger:
        bb = bollinger_bands(close)
        fig.add_trace(go.Scatter(x=ohlcv.index, y=bb["upper"], line=dict(width=0.8,
                                 color=T.PALETTE[4]), name="Bollinger upper", showlegend=False),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=ohlcv.index, y=bb["lower"], line=dict(width=0.8,
                                 color=T.PALETTE[4]), fill="tonexty",
                                 fillcolor="rgba(142,68,173,0.08)",
                                 name="Bollinger bands (20, 2σ)"),
                      row=1, col=1)
    last = float(close.iloc[-1])
    fig.add_hline(y=last, line_dash="dot", line_color=T.NEUTRAL, row=1, col=1,
                  annotation_text=f"Last {last:,.2f}", annotation_position="right")
    row = 2
    if show_volume:
        colors = np.where(close >= ohlcv["open"], T.GAIN, T.LOSS)
        fig.add_trace(go.Bar(x=ohlcv.index, y=ohlcv["volume"], marker_color=colors, opacity=0.6,
                             name="Volume", showlegend=False), row=row, col=1)
        fig.update_yaxes(title_text="Volume", row=row, col=1)
        row += 1
    if show_rsi:
        r = rsi(close)
        fig.add_trace(go.Scatter(x=r.index, y=r, name="RSI 14", line=dict(color=T.ACCENT)),
                      row=row, col=1)
        # shapes must be added after the subplot has a trace, or Plotly skips them
        fig.add_hrect(y0=70, y1=100, fillcolor=T.LOSS_FILL, line_width=0, row=row, col=1,
                      layer="below", annotation_text="Overbought >70",
                      annotation_position="top left")
        fig.add_hrect(y0=0, y1=30, fillcolor=T.GAIN_FILL, line_width=0, row=row, col=1,
                      layer="below", annotation_text="Oversold <30",
                      annotation_position="bottom left")
        fig.update_yaxes(title_text=f"RSI {r.iloc[-1]:.0f}", range=[0, 100], row=row, col=1)
        row += 1
    if show_macd:
        m = macd(close)
        fig.add_trace(go.Bar(x=m.index, y=m["histogram"], name="MACD histogram",
                             marker_color=np.where(m["histogram"] >= 0, T.GAIN, T.LOSS),
                             opacity=0.6), row=row, col=1)
        fig.add_trace(go.Scatter(x=m.index, y=m["macd"], name="MACD",
                                 line=dict(color=T.ACCENT, width=1.4)), row=row, col=1)
        fig.add_trace(go.Scatter(x=m.index, y=m["signal"], name="Signal",
                                 line=dict(color=T.PALETTE[1], width=1.4)), row=row, col=1)
        fig.update_yaxes(title_text="MACD", row=row, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False, height=360 + 150 * (len(panels) - 1))
    fig.update_yaxes(title_text="Price", row=1, col=1)
    return T.apply(fig, f"{ticker} technical analysis", source=source)


# ------------------------------------------------------------------ options
def open_interest_chart(chain: pd.DataFrame, spot: float, max_pain_strike: float | None = None,
                        field: str = "open_interest", window: float = 0.3) -> go.Figure:
    """Calls above the axis, puts below, per strike; spot and max-pain markers."""
    c = chain[(chain["strike"] > spot * (1 - window)) & (chain["strike"] < spot * (1 + window))]
    calls = c[c["type"] == "call"].groupby("strike")[field].sum()
    puts = c[c["type"] == "put"].groupby("strike")[field].sum()
    label = "Open interest" if field == "open_interest" else "Volume"
    fig = go.Figure()
    fig.add_trace(go.Bar(x=calls.index, y=calls.values, name=f"Call {label.lower()}",
                         marker_color=T.GAIN))
    fig.add_trace(go.Bar(x=puts.index, y=-puts.values, name=f"Put {label.lower()}",
                         marker_color=T.LOSS, customdata=puts.values,
                         hovertemplate="K=%{x}<br>puts %{customdata:,.0f}<extra></extra>"))
    fig.add_vline(x=spot, line_color=T.ACCENT, line_width=2, annotation_text=f"Spot {spot:,.2f}",
                  annotation_position="top")
    if max_pain_strike is not None:
        fig.add_vline(x=max_pain_strike, line_dash="dash", line_color=T.PALETTE[4],
                      annotation_text=f"Max pain {max_pain_strike:,.2f}",
                      annotation_position="bottom")
    if len(calls):
        k = calls.idxmax()
        fig.add_annotation(x=k, y=calls.max(), text=f"Call wall {k:g}", showarrow=True,
                           arrowhead=2, font=dict(color=T.GAIN))
    if len(puts):
        k = puts.idxmax()
        fig.add_annotation(x=k, y=-puts.max(), text=f"Put wall {k:g}", showarrow=True,
                           arrowhead=2, ay=30, font=dict(color=T.LOSS))
    fig.update_layout(barmode="relative", hovermode="closest")
    return T.apply(fig, f"{label} by strike (calls up, puts down)", "Strike", label)


def max_pain_chart(curve: pd.Series, strike: float, spot: float) -> go.Figure:
    fig = go.Figure(go.Scatter(x=curve.index, y=curve.values * 100 / 1e6, mode="lines",
                               line=dict(color=T.ACCENT, width=2.5), name="Holder payout"))
    fig.add_vline(x=strike, line_dash="dash", line_color=T.PALETTE[4],
                  annotation_text=f"Max pain {strike:g}")
    fig.add_vline(x=spot, line_color=T.NEUTRAL, line_dash="dot", annotation_text=f"Spot {spot:g}",
                  annotation_position="bottom right")
    return T.apply(fig, "Total option payout to holders if the stock expires at each strike",
                   "Price at expiry", "Payout to holders ($ millions, 100 shares/contract)")


# ------------------------------------------------------------------ backtests
def backtest_chart(prices: pd.Series, result, title: str = "Strategy backtest") -> go.Figure:
    """Price with trade markers, equity vs buy & hold, drawdown and position."""
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.38, 0.32, 0.15, 0.15],
                        subplot_titles=["Price & trades", "Growth of $1", "Drawdown",
                                        "Position"])
    fig.add_trace(go.Scatter(x=prices.index, y=prices, name="Price",
                             line=dict(color=T.NEUTRAL, width=1.3)), row=1, col=1)
    tr = result.trades
    buys = tr[tr["to"] > tr["from"]]
    sells = tr[tr["to"] < tr["from"]]
    fig.add_trace(go.Scatter(x=buys.index, y=buys["price"], mode="markers", name="Buy",
                             marker=dict(symbol="triangle-up", size=11, color=T.GAIN)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=sells.index, y=sells["price"], mode="markers", name="Sell",
                             marker=dict(symbol="triangle-down", size=11, color=T.LOSS)),
                  row=1, col=1)
    eq = result.equity
    bh = (1 + result.benchmark.fillna(0)).cumprod()
    fig.add_trace(go.Scatter(x=eq.index, y=eq, name="Strategy", line=dict(color=T.ACCENT,
                                                                          width=2.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=bh.index, y=bh, name="Buy & hold",
                             line=dict(color=T.PALETTE[1], width=1.8, dash="dot")), row=2, col=1)
    for s, col in ((eq, T.ACCENT), (bh, T.PALETTE[1])):
        fig.add_annotation(x=s.index[-1], y=s.iloc[-1], text=_pct(s.iloc[-1] - 1, 0),
                           showarrow=False, xanchor="left", font=dict(color=col), row=2, col=1)
    dd = eq / eq.cummax() - 1
    fig.add_trace(go.Scatter(x=dd.index, y=dd, fill="tozeroy", fillcolor=T.LOSS_FILL,
                             line=dict(color=T.LOSS, width=1), name="Strategy drawdown",
                             showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=result.positions.index, y=result.positions, line_shape="hv",
                             fill="tozeroy", line=dict(color=T.PALETTE[2], width=1),
                             name="Position", showlegend=False), row=4, col=1)
    fig.update_yaxes(tickformat=".0%", row=3, col=1)
    fig.update_layout(height=900)
    return T.apply(fig, title)


def param_heatmap(table: pd.DataFrame, x: str, y: str, value: str,
                  best: dict | None = None) -> go.Figure:
    pv = table.pivot_table(index=y, columns=x, values=value)
    fig = go.Figure(go.Heatmap(z=pv.values, x=pv.columns.astype(str), y=pv.index.astype(str),
                               colorscale="RdYlGn", zmid=0, text=np.round(pv.values, 2),
                               texttemplate="%{text}", colorbar=dict(title=value)))
    if best:
        fig.add_annotation(x=str(best[x]), y=str(best[y]), text="★ best on train",
                           showarrow=True, arrowhead=2, bgcolor=T.ANNOTATION_BG)
    fig.update_layout(hovermode="closest")
    return T.apply(fig, f"{value} by parameters", x, y)


def walk_forward_weights_chart(weights: pd.DataFrame, method: str) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(weights.columns):
        fig.add_trace(go.Scatter(x=weights.index, y=weights[col], stackgroup="w", name=str(col),
                                 line=dict(width=0.5, color=T.PALETTE[i % 10])))
    fig.update_yaxes(tickformat=".0%", range=[0, 1])
    return T.apply(fig, f"{method}: weights chosen at each rebalance", "Date", "Weight")


# ------------------------------------------------------------------ wealth
def wealth_fan_chart(sim, start: pd.Timestamp | None = None, title: str | None = None
                     ) -> go.Figure:
    p = sim.percentiles
    x = pd.date_range(start or pd.Timestamp.today().normalize(), periods=len(p), freq="MS")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=p["p95"], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=p["p5"], fill="tonexty", fillcolor=T.BAND_FILL,
                             line=dict(width=0), name="5–95% of outcomes"))
    fig.add_trace(go.Scatter(x=x, y=p["p75"], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=p["p25"], fill="tonexty", fillcolor=T.BAND_FILL_2,
                             line=dict(width=0), name="25–75% of outcomes"))
    fig.add_trace(go.Scatter(x=x, y=p["p50"], name="Median", line=dict(color=T.ACCENT, width=3)))
    fig.add_trace(go.Scatter(x=x, y=sim.contributions, name="Money put in",
                             line=dict(color=T.NEUTRAL, dash="dash")))
    for col, lbl in (("p5", "Bad case (5%)"), ("p50", "Median"), ("p95", "Good case (95%)")):
        fig.add_annotation(x=x[-1], y=p[col].iloc[-1], text=f"{lbl}: {_money(p[col].iloc[-1])}",
                           showarrow=False, xanchor="left", bgcolor=T.ANNOTATION_BG)
    if sim.goal is not None:
        fig.add_hline(y=sim.goal, line_color=T.GAIN, line_dash="dot",
                      annotation_text=f"Goal {_money(sim.goal)} — reached in "
                                      f"{sim.prob_goal:.0%} of simulations")
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    unit = " (today's dollars)" if sim.real else ""
    return T.apply(fig, title or f"Projected portfolio value{unit}", "Date", "Value")


def final_wealth_histogram(sim) -> go.Figure:
    f = sim.final
    cap = np.percentile(f, 99.5)          # keep the far tail from squashing the chart
    fig = go.Figure(go.Histogram(x=f[f <= cap], nbinsx=80, marker_color=T.ACCENT, opacity=0.8,
                                 name="Final value"))
    marks = [(np.percentile(f, 5), "Bad case (5%)", T.LOSS),
             (np.percentile(f, 50), "Median", T.ACCENT),
             (np.percentile(f, 95), "Good case (95%)", T.GAIN),
             (sim.contributions[-1], "Money put in", T.NEUTRAL)]
    for i, (v, lbl, col) in enumerate(marks):
        fig.add_vline(x=v, line_color=col, line_dash="dash")
        fig.add_annotation(x=v, y=1.0 - 0.09 * i, yref="paper", text=f"{lbl}: {_money(v)}",
                           showarrow=False, xanchor="left", bgcolor=T.ANNOTATION_BG,
                           font=dict(color=col if col != T.NEUTRAL else None))
    fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    fig.update_layout(hovermode="closest", showlegend=False)
    return T.apply(fig, "Distribution of the final value", "Final value", "Simulations")


# ------------------------------------------------------------------ market
def returns_heatmap(table: pd.DataFrame, labels: dict[str, str] | None = None,
                    columns: Sequence[str] = ("1D", "1W", "1M", "3M", "6M", "YTD", "1Y"),
                    source: str | None = None) -> go.Figure:
    t = table[list(columns)]
    names = [f"{i} · {labels[i]}" if labels and i in labels else i for i in t.index]
    z = t.to_numpy()
    zmax = np.nanpercentile(np.abs(z), 95) or 0.01
    fig = go.Figure(go.Heatmap(z=z, x=list(t.columns), y=names, colorscale="RdYlGn", zmid=0,
                               zmin=-zmax, zmax=zmax,
                               text=np.vectorize(lambda v: _pct(v))(z), texttemplate="%{text}",
                               colorbar=dict(title="Return", tickformat=".0%"),
                               hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=max(380, 34 * len(t)), hovermode="closest")
    return T.apply(fig, "Performance heatmap", source=source)


def period_bar_chart(table: pd.DataFrame, period: str,
                     labels: dict[str, str] | None = None) -> go.Figure:
    s = table[period].dropna().sort_values()
    names = [f"{labels[i]} ({i})" if labels and i in labels else i for i in s.index]
    fig = go.Figure(go.Bar(x=s.values, y=names, orientation="h",
                           marker_color=np.where(s.values >= 0, T.GAIN, T.LOSS),
                           text=[_pct(v) for v in s.values], textposition="outside"))
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(height=max(380, 30 * len(s)), hovermode="closest", dragmode="pan")
    return T.apply(fig, f"{period} return — best to worst", "Return", "")


# ------------------------------------------------------------------ pairs & factors
def pairs_chart(y: pd.Series, x: pd.Series, result, entry: float, exit: float) -> go.Figure:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.35, 0.35, 0.30],
                        subplot_titles=["Prices rebased to 100", "Spread z-score",
                                        "Growth of $1 (pairs strategy)"])
    for s, col in ((y, T.ACCENT), (x, T.PALETTE[1])):
        fig.add_trace(go.Scatter(x=s.index, y=100 * s / s.dropna().iloc[0], name=s.name,
                                 line=dict(color=col)), row=1, col=1)
    z = result.zscore
    fig.add_trace(go.Scatter(x=z.index, y=z, name="z-score", line=dict(color=T.PALETTE[4])),
                  row=2, col=1)
    zmax = float(np.nanmax(np.abs(z.to_numpy()))) if z.notna().any() else entry + 1
    top = max(entry + 1, zmax + 0.5)
    fig.add_hrect(y0=entry, y1=top, fillcolor=T.LOSS_FILL, line_width=0, row=2, col=1,
                  layer="below", annotation_text="Short spread zone",
                  annotation_position="top left")
    fig.add_hrect(y0=-top, y1=-entry, fillcolor=T.GAIN_FILL, line_width=0, row=2, col=1,
                  layer="below", annotation_text="Long spread zone",
                  annotation_position="bottom left")
    fig.add_hrect(y0=-exit, y1=exit, fillcolor="rgba(127,140,141,0.15)", line_width=0, row=2,
                  col=1, layer="below", annotation_text="Exit zone",
                  annotation_position="top right")
    eq = (1 + result.returns).cumprod()
    fig.add_trace(go.Scatter(x=eq.index, y=eq, name="Pairs strategy",
                             line=dict(color=T.GAIN, width=2.5)), row=3, col=1)
    fig.update_layout(height=820)
    return T.apply(fig, f"Pairs trading: {y.name} vs {x.name}")


def factor_chart(res, name: str = "") -> go.Figure:
    """Bar chart of factor betas from :func:`quantforge.portfolio.factor_regression`."""
    f = res.table.drop(index="Alpha (annual)")
    ci = 1.96 * f["std_err"]
    sig = f["p_value"] < 0.05
    fig = go.Figure(go.Bar(x=f.index, y=f["coef"], error_y=dict(type="data", array=ci),
                           marker_color=np.where(sig, T.ACCENT, T.NEUTRAL),
                           text=[f"{v:+.2f}" for v in f["coef"]], textposition="outside"))
    fig.add_hline(y=0, line_color=T.NEUTRAL)
    fig.update_layout(hovermode="closest")
    r2 = res.r_squared
    return T.apply(fig, f"{name} factor exposures (bars ±95% CI; grey = not significant) — "
                        f"R² {r2:.2f}", "Factor", "Beta")
