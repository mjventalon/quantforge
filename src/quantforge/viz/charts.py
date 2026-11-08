"""Plotly charts for every quantforge model.

Every function returns a ``plotly.graph_objects.Figure`` (call ``.show()`` in a
notebook or ``st.plotly_chart(fig)`` in Streamlit). Charts follow one style:
labelled axes with units, coloured named zones, and annotated key points with
their values.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from . import theme as T

__all__ = [
    "candlestick", "payoff_diagram", "greek_profile", "greek_surface", "vol_smile",
    "vol_surface_3d", "mc_paths_fan", "convergence_chart", "efficient_frontier_chart",
    "weights_chart", "correlation_heatmap", "cumulative_returns", "drawdown_chart",
    "var_distribution", "var_backtest_chart", "stress_chart", "garch_chart",
    "forecast_chart", "acf_chart", "vol_cone_chart", "sml_chart", "roc_chart",
    "calibration_chart", "yield_curve_chart", "rolling_beta_chart",
]


def _pct(x: float, d: int = 2) -> str:
    return f"{x * 100:.{d}f}%"


# ============================================================================ market
def candlestick(ohlcv: pd.DataFrame, ticker: str = "", ma: Sequence[int] = (50, 200),
                source: str | None = None) -> go.Figure:
    """OHLC candles with moving averages and a volume panel."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25],
                        vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=ohlcv.index, open=ohlcv["open"], high=ohlcv["high"],
                                 low=ohlcv["low"], close=ohlcv["close"], name=ticker or "Price",
                                 increasing_line_color=T.GAIN, decreasing_line_color=T.LOSS),
                  row=1, col=1)
    for i, w in enumerate(ma):
        if len(ohlcv) > w:
            fig.add_trace(go.Scatter(x=ohlcv.index, y=ohlcv["close"].rolling(w).mean(),
                                     name=f"SMA {w}", line=dict(width=1.4,
                                     color=T.PALETTE[(i + 1) % len(T.PALETTE)])), row=1, col=1)
    colors = np.where(ohlcv["close"] >= ohlcv["open"], T.GAIN, T.LOSS)
    fig.add_trace(go.Bar(x=ohlcv.index, y=ohlcv["volume"], marker_color=colors, name="Volume",
                         opacity=0.6, showlegend=False), row=2, col=1)
    last = ohlcv["close"].iloc[-1]
    fig.add_hline(y=last, line_dash="dot", line_color=T.NEUTRAL, row=1, col=1,
                  annotation_text=f"Last {last:,.2f}", annotation_position="right")
    fig.update_layout(xaxis_rangeslider_visible=False, height=600)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return T.apply(fig, f"{ticker} price history", source=source)


# ============================================================================ options
def payoff_diagram(spots: np.ndarray, pnl_expiry: np.ndarray, pnl_today: np.ndarray | None = None,
                   entry_spot: float | None = None, breakevens: Sequence[float] = (),
                   title: str = "Strategy P&L") -> go.Figure:
    """P&L at expiry (and today) with profit/loss zones and break-even points."""
    fig = go.Figure()
    pos = np.where(pnl_expiry >= 0, pnl_expiry, 0)
    neg = np.where(pnl_expiry < 0, pnl_expiry, 0)
    fig.add_trace(go.Scatter(x=spots, y=pos, fill="tozeroy", fillcolor=T.GAIN_FILL,
                             line=dict(width=0), name="Profit zone", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=spots, y=neg, fill="tozeroy", fillcolor=T.LOSS_FILL,
                             line=dict(width=0), name="Loss zone", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=spots, y=pnl_expiry, name="At expiry",
                             line=dict(color=T.ACCENT, width=3)))
    if pnl_today is not None:
        fig.add_trace(go.Scatter(x=spots, y=pnl_today, name="Today (model)",
                                 line=dict(color=T.PALETTE[1], width=2, dash="dash")))
    fig.add_hline(y=0, line_color=T.NEUTRAL, line_width=1)
    if entry_spot is not None:
        fig.add_vline(x=entry_spot, line_dash="dot", line_color=T.NEUTRAL,
                      annotation_text=f"Spot {entry_spot:,.2f}",
                      annotation_position="bottom right")
    for be in breakevens:
        fig.add_trace(go.Scatter(x=[be], y=[0], mode="markers+text", text=[f"BE {be:,.2f}"],
                                 textposition="top center", marker=dict(size=10, color="black",
                                 symbol="diamond"), showlegend=False))
    i_max, i_min = int(np.argmax(pnl_expiry)), int(np.argmin(pnl_expiry))
    for i, label, col in ((i_max, "Max profit", T.GAIN), (i_min, "Max loss", T.LOSS)):
        fig.add_annotation(x=spots[i], y=pnl_expiry[i], text=f"{label}: {pnl_expiry[i]:,.2f}",
                           showarrow=True, arrowhead=2, arrowcolor=col, font=dict(color=col))
    return T.apply(fig, title, "Underlying price at expiry", "Profit / loss")


def greek_profile(spots: np.ndarray, values: dict[str, np.ndarray], spot: float,
                  title: str = "Greeks vs underlying") -> go.Figure:
    names = [k for k in ("price", "delta", "gamma", "vega", "theta", "rho") if k in values]
    fig = make_subplots(rows=2, cols=3, subplot_titles=[n.capitalize() for n in names])
    for i, n in enumerate(names):
        r, c = divmod(i, 3)
        fig.add_trace(go.Scatter(x=spots, y=values[n], name=n.capitalize(),
                                 line=dict(color=T.PALETTE[i], width=2.5), showlegend=False),
                      row=r + 1, col=c + 1)
        j = int(np.argmin(np.abs(spots - spot)))
        fig.add_trace(go.Scatter(x=[spots[j]], y=[values[n][j]], mode="markers+text",
                                 text=[f"{values[n][j]:.4g}"], textposition="top center",
                                 marker=dict(size=9, color="black"), showlegend=False),
                      row=r + 1, col=c + 1)
        fig.add_vline(x=spot, line_dash="dot", line_color=T.NEUTRAL, row=r + 1, col=c + 1)
    fig.update_layout(height=620, hovermode="closest")
    return T.apply(fig, title)


def greek_surface(spots: np.ndarray, maturities: np.ndarray, z: np.ndarray, greek: str,
                  title: str | None = None) -> go.Figure:
    """3-D surface of a Greek over (underlying, time to expiry)."""
    fig = go.Figure(go.Surface(x=spots, y=maturities, z=z, colorscale="Viridis",
                               colorbar=dict(title=greek.capitalize()),
                               contours=dict(z=dict(show=True, usecolormap=True, project_z=True))))
    fig.update_layout(scene=dict(xaxis_title="Underlying", yaxis_title="Years to expiry",
                                 zaxis_title=greek.capitalize()), height=620)
    return T.apply(fig, title or f"{greek.capitalize()} surface")


def vol_smile(ivs: pd.DataFrame, svi_params: pd.DataFrame | None = None,
              source: str | None = None) -> go.Figure:
    """Market implied vols per expiry (points) with fitted SVI smiles (lines)."""
    from ..pricing.surface import svi_total_variance

    fig = go.Figure()
    for i, (t, g) in enumerate(ivs.groupby("T")):
        col = T.PALETTE[i % len(T.PALETTE)]
        label = f"{pd.Timestamp(g['expiry'].iloc[0]):%Y-%m-%d} ({t * 365:.0f}d)"
        fig.add_trace(go.Scatter(x=g["strike"], y=g["iv"], mode="markers", name=label,
                                 marker=dict(color=col, size=6), legendgroup=label,
                                 customdata=g[["type", "bid", "ask"]],
                                 hovertemplate="K=%{x}<br>IV=%{y:.2%}<br>%{customdata[0]} "
                                               "bid %{customdata[1]:.2f} / "
                                               "ask %{customdata[2]:.2f}"))
        if svi_params is not None:
            row = svi_params.iloc[(svi_params["T"] - t).abs().argmin()]
            if abs(row["T"] - t) < 1e-9:
                f = g["forward"].iloc[0]
                kk = np.linspace(g["log_moneyness"].min(), g["log_moneyness"].max(), 200)
                w = svi_total_variance(kk, row.a, row.b, row.rho, row.m, row.sigma)
                fig.add_trace(go.Scatter(x=f * np.exp(kk), y=np.sqrt(np.maximum(w, 0) / t),
                                         mode="lines", line=dict(color=col, width=2),
                                         name=f"SVI {label}", legendgroup=label,
                                         showlegend=False))
    fig.update_layout(hovermode="closest", height=560)
    fig.update_yaxes(tickformat=".0%")
    return T.apply(fig, "Implied volatility smiles", "Strike", "Implied volatility",
                   source=source)


def vol_surface_3d(k_grid: np.ndarray, t_grid: np.ndarray, iv: np.ndarray,
                   points: pd.DataFrame | None = None, source: str | None = None) -> go.Figure:
    fig = go.Figure(go.Surface(x=k_grid, y=t_grid * 365, z=iv * 100, colorscale="Turbo",
                               colorbar=dict(title="IV %"), opacity=0.92,
                               contours=dict(z=dict(show=True, usecolormap=True,
                                                    project_z=True))))
    if points is not None:
        fig.add_trace(go.Scatter3d(x=points["log_moneyness"], y=points["T"] * 365,
                                   z=points["iv"] * 100, mode="markers", name="Market quotes",
                                   marker=dict(size=2.5, color="black")))
    fig.update_layout(scene=dict(xaxis_title="Log-moneyness ln(K/F)", yaxis_title="Days",
                                 zaxis_title="Implied vol (%)"), height=680)
    return T.apply(fig, "Implied volatility surface (SVI)", source=source)


def mc_paths_fan(paths: np.ndarray, maturity: float, strike: float | None = None,
                 n_show: int = 60, title: str = "Monte-Carlo price paths") -> go.Figure:
    """Sample paths, percentile bands and the terminal distribution."""
    n_steps = paths.shape[1] - 1
    t = np.linspace(0, maturity, n_steps + 1)
    q = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    fig = make_subplots(rows=1, cols=2, column_widths=[0.78, 0.22], shared_yaxes=True,
                        horizontal_spacing=0.02)
    for p in paths[: min(n_show, len(paths))]:
        fig.add_trace(go.Scatter(x=t, y=p, mode="lines", line=dict(width=0.6, color=T.NEUTRAL),
                                 opacity=0.35, showlegend=False, hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=q[4], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=q[0], fill="tonexty", fillcolor=T.BAND_FILL,
                             line=dict(width=0), name="5–95% band"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=q[3], line=dict(width=0), showlegend=False,
                             hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=q[1], fill="tonexty", fillcolor=T.BAND_FILL_2,
                             line=dict(width=0), name="25–75% band"), row=1, col=1)
    fig.add_trace(go.Scatter(x=t, y=q[2], line=dict(color=T.ACCENT, width=3), name="Median"),
                  row=1, col=1)
    fig.add_trace(go.Histogram(y=paths[:, -1], nbinsy=80, marker_color=T.ACCENT, opacity=0.7,
                               name="Terminal", showlegend=False), row=1, col=2)
    if strike is not None:
        fig.add_hline(y=strike, line_dash="dash", line_color=T.LOSS,
                      annotation_text=f"Strike {strike:,.2f}", row=1, col="all")
    for val, lbl in ((q[0, -1], "P5"), (q[2, -1], "Median"), (q[4, -1], "P95")):
        fig.add_annotation(x=maturity, y=val, text=f"{lbl}: {val:,.2f}", showarrow=False,
                           xanchor="left", row=1, col=1)
    fig.update_layout(height=560, hovermode="closest")
    fig.update_xaxes(title_text="Years", row=1, col=1)
    fig.update_xaxes(title_text="Count", row=1, col=2)
    return T.apply(fig, title, y="Underlying price")


def convergence_chart(steps: Sequence[int], prices: Sequence[float], reference: float,
                      label: str = "Binomial", ref_label: str = "Black-Scholes") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(steps), y=list(prices), mode="lines+markers", name=label,
                             line=dict(color=T.ACCENT)))
    fig.add_hline(y=reference, line_color=T.LOSS, line_dash="dash",
                  annotation_text=f"{ref_label} {reference:.4f}")
    return T.apply(fig, f"{label} convergence", "Number of steps / paths", "Price")


# ============================================================================ portfolio
def efficient_frontier_chart(frontier: pd.DataFrame, asset_mu: pd.Series, asset_vol: pd.Series,
                             special: dict[str, tuple[float, float]] | None = None,
                             risk_free_rate: float | None = None,
                             random_portfolios: tuple[np.ndarray, np.ndarray] | None = None,
                             source: str | None = None) -> go.Figure:
    """Frontier, individual assets, highlighted portfolios and the capital market line."""
    fig = go.Figure()
    if random_portfolios is not None:
        rv, rr = random_portfolios
        sharpe = (rr - (risk_free_rate or 0)) / rv
        fig.add_trace(go.Scatter(x=rv, y=rr, mode="markers", name="Random portfolios",
                                 marker=dict(size=4, color=sharpe, colorscale="Viridis",
                                             opacity=0.5, colorbar=dict(title="Sharpe", x=1.02)),
                                 hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=frontier["volatility"], y=frontier["return"], mode="lines",
                             name="Efficient frontier", line=dict(color=T.ACCENT, width=3.5)))
    fig.add_trace(go.Scatter(x=asset_vol, y=asset_mu, mode="markers+text", name="Assets",
                             text=list(asset_mu.index), textposition="top center",
                             marker=dict(size=10, color=T.PALETTE[1], symbol="circle")))
    if special:
        symbols = ["star", "diamond", "square", "triangle-up", "cross"]
        for i, (name, (vol, ret)) in enumerate(special.items()):
            fig.add_trace(go.Scatter(x=[vol], y=[ret], mode="markers", name=name,
                                     marker=dict(size=18, symbol=symbols[i % 5],
                                                 color=T.PALETTE[(i + 2) % 10],
                                                 line=dict(width=1, color="black"))))
            ax, ay = [(-70, -45), (-80, 35), (60, 45), (70, -30), (0, 60)][i % 5]
            fig.add_annotation(x=vol, y=ret, text=f"<b>{name}</b><br>σ {_pct(vol)} · μ {_pct(ret)}",
                               showarrow=True, arrowhead=2, ax=ax, ay=ay,
                               bgcolor=T.ANNOTATION_BG, bordercolor=T.NEUTRAL)
        if risk_free_rate is not None and "Max Sharpe" in special:
            v, r = special["Max Sharpe"]
            xs = np.array([0, max(frontier["volatility"].max(), v) * 1.1])
            fig.add_trace(go.Scatter(x=xs, y=risk_free_rate + (r - risk_free_rate) / v * xs,
                                     mode="lines", name="Capital market line",
                                     line=dict(color=T.GAIN, dash="dash")))
            fig.add_annotation(x=0, y=risk_free_rate, text=f"rf {_pct(risk_free_rate)}",
                               showarrow=False, xanchor="left", yanchor="bottom")
    fig.update_xaxes(tickformat=".0%", rangemode="tozero")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(hovermode="closest", height=600)
    return T.apply(fig, "Efficient frontier", "Annualized volatility", "Annualized expected return",
                   source=source)


def weights_chart(weights: pd.DataFrame | pd.Series, title: str = "Portfolio weights") -> go.Figure:
    df = weights.to_frame() if isinstance(weights, pd.Series) else weights
    fig = go.Figure()
    for i, col in enumerate(df.columns):
        fig.add_trace(go.Bar(x=df.index, y=df[col], name=str(col), marker_color=T.PALETTE[i % 10],
                             text=[_pct(v, 1) for v in df[col]], textposition="outside"))
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(barmode="group", hovermode="closest")
    return T.apply(fig, title, "Asset", "Weight")


def correlation_heatmap(returns: pd.DataFrame, source: str | None = None) -> go.Figure:
    c = returns.corr()
    fig = go.Figure(go.Heatmap(z=c.values, x=c.columns, y=c.index, zmin=-1, zmax=1,
                               colorscale="RdBu_r", text=np.round(c.values, 2),
                               texttemplate="%{text}", colorbar=dict(title="ρ")))
    fig.update_layout(height=max(420, 40 * len(c)), hovermode="closest")
    fig.update_yaxes(autorange="reversed")
    return T.apply(fig, "Return correlation matrix", source=source)


def cumulative_returns(returns: pd.DataFrame | pd.Series, log_scale: bool = False,
                       source: str | None = None) -> go.Figure:
    df = returns.to_frame() if isinstance(returns, pd.Series) else returns
    wealth = (1 + df.fillna(0)).cumprod()
    fig = go.Figure()
    for i, col in enumerate(wealth.columns):
        fig.add_trace(go.Scatter(x=wealth.index, y=wealth[col], name=str(col),
                                 line=dict(width=2, color=T.PALETTE[i % 10])))
        fig.add_annotation(x=wealth.index[-1], y=wealth[col].iloc[-1],
                           text=f"{col}: {_pct(wealth[col].iloc[-1] - 1, 1)}", showarrow=False,
                           xanchor="left", font=dict(color=T.PALETTE[i % 10]))
    fig.add_hline(y=1, line_color=T.NEUTRAL, line_width=1)
    if log_scale:
        fig.update_yaxes(type="log")
    return T.apply(fig, "Growth of $1", "Date", "Wealth", source=source)


def drawdown_chart(returns: pd.Series, name: str = "Portfolio") -> go.Figure:
    wealth = (1 + returns.fillna(0)).cumprod()
    dd = wealth / wealth.cummax() - 1
    fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", fillcolor=T.LOSS_FILL,
                               line=dict(color=T.LOSS, width=1.5), name="Drawdown"))
    i = dd.idxmin()
    fig.add_annotation(x=i, y=dd.min(), text=f"Max drawdown {_pct(dd.min(), 1)}<br>{i:%Y-%m-%d}",
                       showarrow=True, arrowhead=2, font=dict(color=T.LOSS))
    fig.update_yaxes(tickformat=".0%")
    return T.apply(fig, f"{name} drawdown", "Date", "Drawdown from peak")


def sml_chart(sml: pd.DataFrame, market_return: float, risk_free_rate: float) -> go.Figure:
    """Security market line with each asset's realized return and alpha."""
    betas = np.linspace(0, max(2.0, sml["beta"].max() * 1.15), 50)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=betas, y=risk_free_rate + betas * (market_return - risk_free_rate),
                             name="Security market line", line=dict(color=T.ACCENT, width=3)))
    colors = np.where(sml["realized_return"] >= sml["capm_return"], T.GAIN, T.LOSS)
    fig.add_trace(go.Scatter(x=sml["beta"], y=sml["realized_return"], mode="markers+text",
                             text=[f"{n} (α {_pct(a, 1)})"
                                   for n, a in zip(sml.index, sml["alpha"])],
                             textposition="top center", marker=dict(size=12, color=colors),
                             name="Assets (green = above SML)"))
    fig.add_trace(go.Scatter(x=[1], y=[market_return], mode="markers", name="Market",
                             marker=dict(size=16, symbol="star", color="black")))
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(hovermode="closest")
    return T.apply(fig, "CAPM — security market line", "Beta", "Annualized return")


def rolling_beta_chart(asset: pd.Series, market: pd.Series, window: int = 126,
                       name: str = "") -> go.Figure:
    df = pd.concat([asset, market], axis=1).dropna()
    beta = df.iloc[:, 0].rolling(window).cov(df.iloc[:, 1]) / df.iloc[:, 1].rolling(window).var()
    fig = go.Figure(go.Scatter(x=beta.index, y=beta, line=dict(color=T.ACCENT, width=2),
                               name=f"{window}-day beta"))
    fig.add_hline(y=1, line_dash="dot", line_color=T.NEUTRAL, annotation_text="β = 1")
    return T.apply(fig, f"Rolling beta {name}", "Date", "Beta")


# ============================================================================ risk
def var_distribution(returns: pd.Series | np.ndarray, var: float, es: float, confidence: float,
                     title: str | None = None, fit_normal: bool = True) -> go.Figure:
    """Return histogram with the VaR line, ES line and shaded loss tail."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    fig = go.Figure()
    bins = np.linspace(r.min(), r.max(), 121)
    width = bins[1] - bins[0]
    tail = r[r <= -var]
    body = r[r > -var]
    xb = dict(start=bins[0], end=bins[-1], size=width)
    fig.add_trace(go.Histogram(x=body, xbins=xb, marker_color=T.ACCENT, opacity=0.75,
                               name="Returns"))
    fig.add_trace(go.Histogram(x=tail, xbins=xb, marker_color=T.LOSS, opacity=0.9,
                               name=f"Tail beyond VaR ({len(tail)} obs)"))
    if fit_normal:
        xs = np.linspace(r.min(), r.max(), 400)
        fig.add_trace(go.Scatter(x=xs, y=stats.norm.pdf(xs, r.mean(), r.std()) * r.size * width,
                                 name="Normal fit (same mean/vol)",
                                 line=dict(color=T.NEUTRAL, dash="dot")))
    fig.add_vrect(x0=float(r.min()), x1=-var, fillcolor=T.LOSS_FILL, line_width=0, layer="below",
                  annotation_text="Loss tail", annotation_position="top left",
                  annotation_font_color=T.LOSS)
    fig.add_vline(x=-var, line_color=T.LOSS, line_width=2.5,
                  annotation_text=f"VaR {confidence:.1%}: {_pct(var)}",
                  annotation_position="top right")
    fig.add_vline(x=-es, line_color="#7B241C", line_width=2, line_dash="dash",
                  annotation_text=f"ES: {_pct(es)}", annotation_position="bottom left")
    fig.update_layout(barmode="overlay", hovermode="closest")
    fig.update_xaxes(tickformat=".1%")
    return T.apply(fig, title or "Return distribution and tail risk", "Period return",
                   "Number of observations")


def var_backtest_chart(returns: pd.Series, var_series: pd.Series,
                       title: str = "VaR backtest") -> go.Figure:
    df = pd.concat([returns.rename("r"), var_series.rename("v")], axis=1).dropna()
    hit = df["r"] < -df["v"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df.index, y=df["r"], name="Daily return", marker_color=T.NEUTRAL,
                         opacity=0.6))
    fig.add_trace(go.Scatter(x=df.index, y=-df["v"], name="−VaR forecast",
                             line=dict(color=T.LOSS, width=2)))
    fig.add_trace(go.Scatter(x=df.index[hit], y=df["r"][hit], mode="markers",
                             name=f"Exceptions ({int(hit.sum())})",
                             marker=dict(color=T.LOSS, size=8, symbol="x")))
    fig.update_yaxes(tickformat=".1%")
    return T.apply(fig, title, "Date", "Return")


def stress_chart(results: pd.DataFrame, title: str = "Historical stress tests") -> go.Figure:
    df = results.sort_values("portfolio_return")
    colors = np.where(df["portfolio_return"] < 0, T.LOSS, T.GAIN)
    fig = go.Figure(go.Bar(y=df.index, x=df["portfolio_return"], orientation="h",
                           marker_color=colors, name="Portfolio",
                           text=[_pct(v, 1) + (" *" if p else "") for v, p in
                                 zip(df["portfolio_return"],
                                     df.get("proxied_assets", [""] * len(df)))],
                           textposition="outside"))
    if "benchmark_return" in df and df["benchmark_return"].notna().any():
        fig.add_trace(go.Scatter(y=df.index, x=df["benchmark_return"], mode="markers",
                                 name="Benchmark", marker=dict(symbol="line-ns-open", size=16,
                                                               color="black", line_width=3)))
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(height=max(420, 34 * len(df)), hovermode="closest")
    return T.apply(fig, title + " (* = beta proxy for some assets)", "Return over scenario", "")


# ============================================================================ time series
def garch_chart(returns: pd.Series, cond_vol: pd.Series, periods: int = 252,
                forecast: pd.DataFrame | None = None, name: str = "") -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.45, 0.55],
                        vertical_spacing=0.05)
    fig.add_trace(go.Bar(x=returns.index, y=returns, marker_color=T.NEUTRAL, name="Returns",
                         opacity=0.7), row=1, col=1)
    ann = cond_vol * np.sqrt(periods)
    fig.add_trace(go.Scatter(x=ann.index, y=ann, name="GARCH conditional vol (ann.)",
                             line=dict(color=T.ACCENT, width=2)), row=2, col=1)
    realized = returns.rolling(21).std() * np.sqrt(periods)
    fig.add_trace(go.Scatter(x=realized.index, y=realized, name="21-day realized vol",
                             line=dict(color=T.PALETTE[1], width=1, dash="dot")), row=2, col=1)
    if forecast is not None:
        idx = pd.bdate_range(returns.index[-1], periods=len(forecast) + 1)[1:]
        fig.add_trace(go.Scatter(x=idx, y=forecast["vol_annualized"], name="Forecast",
                                 line=dict(color=T.LOSS, width=2.5)), row=2, col=1)
    fig.add_annotation(x=ann.index[-1], y=ann.iloc[-1], text=f"Now {_pct(ann.iloc[-1], 1)}",
                       showarrow=True, arrowhead=2, row=2, col=1)
    fig.update_yaxes(tickformat=".1%", row=1, col=1, title_text="Return")
    fig.update_yaxes(tickformat=".0%", row=2, col=1, title_text="Volatility")
    fig.update_layout(height=650)
    return T.apply(fig, f"{name} volatility clustering — GARCH")


def forecast_chart(history: pd.Series, fc: pd.DataFrame, name: str = "Series",
                   n_hist: int = 120) -> go.Figure:
    h = history.iloc[-n_hist:]
    if isinstance(h.index, pd.DatetimeIndex):
        idx = pd.bdate_range(h.index[-1], periods=len(fc) + 1)[1:]
    else:
        idx = np.arange(len(history), len(history) + len(fc))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h.index, y=h, name="History", line=dict(color=T.NEUTRAL)))
    fig.add_trace(go.Scatter(x=idx, y=fc["upper"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=idx, y=fc["lower"], fill="tonexty", fillcolor=T.BAND_FILL,
                             line=dict(width=0), name="95% interval"))
    fig.add_trace(go.Scatter(x=idx, y=fc["mean"], name="Forecast",
                             line=dict(color=T.ACCENT, width=3)))
    return T.apply(fig, f"{name} forecast", "Date", name)


def acf_chart(acf_vals: np.ndarray, pacf_vals: np.ndarray | None, n_obs: int,
              title: str = "Autocorrelation") -> go.Figure:
    band = 1.96 / np.sqrt(n_obs)
    cols = 2 if pacf_vals is not None else 1
    fig = make_subplots(rows=1, cols=cols, subplot_titles=["ACF", "PACF"][:cols])
    for c, vals in enumerate([acf_vals] + ([pacf_vals] if pacf_vals is not None else [])):
        lags = np.arange(1, len(vals))
        colors = np.where(np.abs(vals[1:]) > band, T.LOSS, T.ACCENT)
        fig.add_trace(go.Bar(x=lags, y=vals[1:], marker_color=colors, showlegend=False),
                      row=1, col=c + 1)
        for s in (band, -band):
            fig.add_hline(y=s, line_dash="dash", line_color=T.NEUTRAL, row=1, col=c + 1)
    fig.update_layout(hovermode="closest")
    return T.apply(fig, title + " (red = significant at 5%)", "Lag")


def vol_cone_chart(cone: pd.DataFrame, implied: dict[int, float] | None = None,
                   name: str = "") -> go.Figure:
    x = cone.index.to_numpy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=cone["max"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=cone["min"], fill="tonexty", fillcolor="rgba(127,140,141,.15)",
                             line=dict(width=0), name="Min–max"))
    fig.add_trace(go.Scatter(x=x, y=cone["p90"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=cone["p10"], fill="tonexty", fillcolor=T.BAND_FILL,
                             line=dict(width=0), name="10–90%"))
    fig.add_trace(go.Scatter(x=x, y=cone["median"], name="Median",
                             line=dict(color=T.NEUTRAL, dash="dash")))
    fig.add_trace(go.Scatter(x=x, y=cone["current"], name="Current realized", mode="lines+markers",
                             line=dict(color=T.ACCENT, width=3)))
    if implied:
        fig.add_trace(go.Scatter(x=list(implied), y=list(implied.values()), mode="markers",
                                 name="ATM implied", marker=dict(size=12, symbol="diamond",
                                                                 color=T.LOSS)))
    fig.update_yaxes(tickformat=".0%")
    return T.apply(fig, f"{name} volatility cone", "Window (trading days)", "Annualized volatility")


# ============================================================================ credit
def roc_chart(fpr: np.ndarray, tpr: np.ndarray, auc: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fpr, y=tpr, fill="tozeroy", fillcolor=T.BAND_FILL,
                             line=dict(color=T.ACCENT, width=3), name=f"Model (AUC {auc:.3f})"))
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], line=dict(color=T.NEUTRAL, dash="dash"),
                             name="Random"))
    ks_i = int(np.argmax(tpr - fpr))
    fig.add_trace(go.Scatter(x=[fpr[ks_i], fpr[ks_i]], y=[fpr[ks_i], tpr[ks_i]], mode="lines",
                             line=dict(color=T.LOSS, width=2),
                             name=f"KS {tpr[ks_i] - fpr[ks_i]:.3f}"))
    fig.update_layout(hovermode="closest")
    return T.apply(fig, f"ROC curve — Gini {2 * auc - 1:.3f}", "False positive rate",
                   "True positive rate")


def calibration_chart(table: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    m = max(table["predicted_pd"].max(), table["observed_dr"].max()) * 1.1
    fig.add_trace(go.Scatter(x=[0, m], y=[0, m], line=dict(color=T.NEUTRAL, dash="dash"),
                             name="Perfect calibration"))
    fig.add_trace(go.Scatter(x=table["predicted_pd"], y=table["observed_dr"],
                             mode="markers+lines+text", text=[f"n={n}" for n in table["n"]],
                             textposition="top center", marker=dict(size=10, color=T.ACCENT),
                             name="Buckets"))
    fig.update_xaxes(tickformat=".1%")
    fig.update_yaxes(tickformat=".1%")
    fig.update_layout(hovermode="closest")
    return T.apply(fig, "PD calibration", "Predicted PD", "Observed default rate")


def yield_curve_chart(curve: pd.Series, compare: dict[str, pd.Series] | None = None,
                      source: str = "FRED") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve.index, y=curve, mode="lines+markers+text",
                             text=[_pct(v) for v in curve], textposition="top center",
                             line=dict(color=T.ACCENT, width=3), name="Today"))
    for i, (lbl, c) in enumerate((compare or {}).items()):
        fig.add_trace(go.Scatter(x=c.index, y=c, mode="lines+markers", name=lbl,
                                 line=dict(color=T.PALETTE[i + 1], dash="dot")))
    if 2.0 in curve.index and 10.0 in curve.index:
        sp = curve[10.0] - curve[2.0]
        fig.add_annotation(x=10, y=curve[10.0], text=f"10Y–2Y: {sp * 1e4:+.0f} bp",
                           showarrow=True, arrowhead=2, ay=-50,
                           font=dict(color=T.LOSS if sp < 0 else T.GAIN))
    fig.update_xaxes(type="log", tickvals=list(curve.index),
                     ticktext=[f"{x:g}Y" if x >= 1 else f"{x * 12:.0f}M" for x in curve.index])
    fig.update_yaxes(tickformat=".1%")
    return T.apply(fig, "US Treasury yield curve", "Maturity", "Yield", source=source)
