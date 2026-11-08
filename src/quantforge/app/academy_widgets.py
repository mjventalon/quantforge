"""Interactive widgets embedded in Academy lessons. Data-driven widgets use real
market data from the selected provider; formula widgets use the library's models."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from quantforge.app.common import cached_curve, chart, history, md, pct, prices
from quantforge.viz import theme as T

WIDGETS: dict[str, Callable[[str], None]] = {}


def widget(name: str):
    def deco(fn: Callable[[str], None]):
        WIDGETS[name] = fn
        return fn
    return deco


def render(name: str, key: str) -> None:
    fn = WIDGETS.get(name)
    if fn is None:
        st.info(f"Interactive widget `{name}` is not available in this version.")
        return
    with st.container(border=True):
        st.markdown("🧪 **Try it**")
        try:
            fn(f"{key}_{name}")
        except Exception as exc:  # noqa: BLE001 - keep the lesson readable if data fails
            st.error(f"This widget could not load real data right now: {exc}")


def _years(n: int) -> date:
    return date.today() - timedelta(days=int(365.25 * n))


def _fig(fig: go.Figure, title: str, x: str = "", y: str = "") -> go.Figure:
    return T.apply(fig, title, x, y)


# ------------------------------------------------------------------ level 1
@widget("market_snapshot")
def _market_snapshot(key: str) -> None:
    sym = {"Stock — Apple": "AAPL", "ETF — S&P 500 (SPY)": "SPY", "Index — S&P 500": "^GSPC",
           "Paris — LVMH": "MC.PA", "Crypto — Bitcoin": "BTC-USD", "FX — EUR/USD": "EURUSD=X",
           "Future — Gold": "GC=F"}
    pick = st.selectbox("Instrument", list(sym), key=key)
    df = history(sym[pick], _years(1), date.today())
    r = df["close"].iloc[-1] / df["close"].iloc[0] - 1
    c = st.columns(3)
    c[0].metric("Ticker", sym[pick])
    c[1].metric("Last close", f"{df['close'].iloc[-1]:,.4g}")
    c[2].metric("1-year change", pct(r, 1))
    fig = go.Figure(go.Scatter(x=df.index, y=df["close"], line=dict(color=T.ACCENT)))
    chart(_fig(fig, f"{pick} — last 12 months (real data)", "Date", "Price"), key=f"{key}_c")


@widget("spread_calculator")
def _spread(key: str) -> None:
    c = st.columns(4)
    bid = c[0].number_input("Bid", value=99.98, key=f"{key}b")
    ask = c[1].number_input("Ask", value=100.02, key=f"{key}a")
    qty = c[2].number_input("Shares", value=1000, step=100, key=f"{key}q")
    trips = c[3].number_input("Round trips per year", value=50, key=f"{key}t")
    if ask <= bid:
        st.warning("Ask must be above bid.")
        return
    mid = (bid + ask) / 2
    bps = (ask - bid) / mid * 1e4
    st.markdown(f"Spread **{ask - bid:.4f}** = **{bps:.2f} bp** of mid · cost of one round trip "
                f"(buy at ask, sell at bid): **${(ask - bid) * qty:,.2f}** · yearly drag at "
                f"{trips} round trips: **{bps * trips / 1e4:.2%}** of the position.")


@widget("compound_calculator")
def _compound(key: str) -> None:
    c = st.columns(4)
    p0 = c[0].number_input("Start ($)", value=1000.0, key=f"{key}p")
    rate = c[1].number_input("Annual return (%)", value=7.0, key=f"{key}r") / 100
    yrs = c[2].slider("Years", 1, 50, 10, key=f"{key}y")
    add = c[3].number_input("Added yearly ($)", value=0.0, key=f"{key}a")
    v, vals = p0, [p0]
    for _ in range(yrs):
        v = v * (1 + rate) + add
        vals.append(v)
    st.metric("Final value", f"${vals[-1]:,.2f}",
              f"doubling time ≈ {np.log(2) / np.log(1 + rate):.1f} yrs" if rate > 0 else None)
    fig = go.Figure(go.Bar(x=list(range(yrs + 1)), y=vals, marker_color=T.ACCENT))
    chart(_fig(fig, "Compounding", "Year", "Value ($)"), key=f"{key}c")


@widget("returns_explorer")
def _returns(key: str) -> None:
    t = st.text_input("Ticker", "SPY", key=key).upper()
    df = history(t, _years(5), date.today())
    px = df["adj_close"]
    simple = px.pct_change().dropna()
    logr = np.log(px).diff().dropna()
    yrs = (px.index[-1] - px.index[0]).days / 365.25
    c = st.columns(4)
    c[0].metric("Total return", pct(px.iloc[-1] / px.iloc[0] - 1, 1))
    c[1].metric("CAGR", pct((px.iloc[-1] / px.iloc[0]) ** (1 / yrs) - 1))
    c[2].metric("Sum of log returns", f"{logr.sum():.4f}",
                help="Equals ln(final/initial) exactly.")
    c[3].metric("Annualized vol", pct(simple.std() * np.sqrt(252), 1))
    st.caption(f"Check: ln(P_end/P_start) = {np.log(px.iloc[-1] / px.iloc[0]):.4f} — identical "
               "to the sum of daily log returns. Real data, adjusted closes.")


@widget("candle_reader")
def _candles(key: str) -> None:
    t = st.text_input("Ticker", "AAPL", key=key).upper()
    df = history(t, date.today() - timedelta(days=60), date.today()).iloc[-25:]
    fig = go.Figure(go.Candlestick(x=df.index, open=df["open"], high=df["high"], low=df["low"],
                                   close=df["close"], increasing_line_color=T.GAIN,
                                   decreasing_line_color=T.LOSS))
    fig.update_layout(xaxis_rangeslider_visible=False)
    chart(_fig(fig, f"{t} — last 25 sessions", "Date", "Price"), key=f"{key}c")
    d = st.selectbox("Read one candle", list(df.index.strftime("%Y-%m-%d"))[::-1], key=f"{key}d")
    row = df.loc[d]
    up = row["close"] >= row["open"]
    st.markdown(
        f"**{d}** — Open {row['open']:,.2f} · High {row['high']:,.2f} · Low {row['low']:,.2f} · "
        f"Close {row['close']:,.2f} → **{'up (green)' if up else 'down (red)'}** candle, body "
        f"{abs(row['close'] - row['open']):,.2f}, upper wick "
        f"{row['high'] - max(row['open'], row['close']):,.2f}, lower wick "
        f"{min(row['open'], row['close']) - row['low']:,.2f}, volume {row['volume']:,.0f}.")


@widget("indicator_lab")
def _indicators(key: str) -> None:
    from quantforge.viz import technical_chart
    t = st.text_input("Ticker", "MSFT", key=key).upper()
    df = history(t, _years(3), date.today())
    fig = technical_chart(df, t, (50, 200), True, True, True, False)
    fig.update_xaxes(range=[df.index[-252], df.index[-1]])
    chart(fig, key=f"{key}c")


# ------------------------------------------------------------------ level 2
@widget("drawdown_explorer")
def _drawdown(key: str) -> None:
    from quantforge.viz import drawdown_chart
    t = st.text_input("Ticker", "QQQ", key=key).upper()
    yrs = st.slider("Years of history", 3, 25, 20, key=f"{key}y")
    r = history(t, _years(yrs), date.today())["adj_close"].pct_change().dropna()
    chart(drawdown_chart(r, t), key=f"{key}c")
    dd = (1 + r).cumprod()
    dd = dd / dd.cummax() - 1
    st.caption(f"Max drawdown {pct(dd.min(), 1)} — to recover you needed "
               f"{pct(1 / (1 + dd.min()) - 1, 0)}.")


@widget("two_asset_risk")
def _two_asset(key: str) -> None:
    c = st.columns(4)
    s1 = c[0].slider("σ asset 1 (%)", 5, 60, 20, key=f"{key}1") / 100
    s2 = c[1].slider("σ asset 2 (%)", 5, 60, 20, key=f"{key}2") / 100
    rho = c[2].slider("Correlation ρ", -1.0, 1.0, 0.3, 0.05, key=f"{key}r")
    w = c[3].slider("Weight in asset 1", 0.0, 1.0, 0.5, 0.05, key=f"{key}w")
    ws = np.linspace(0, 1, 101)
    vol = np.sqrt(ws**2 * s1**2 + (1 - ws) ** 2 * s2**2 + 2 * ws * (1 - ws) * rho * s1 * s2)
    v = float(np.sqrt(w**2 * s1**2 + (1 - w) ** 2 * s2**2 + 2 * w * (1 - w) * rho * s1 * s2))
    fig = go.Figure(go.Scatter(x=ws, y=vol, line=dict(color=T.ACCENT, width=3), name="Portfolio σ"))
    fig.add_trace(go.Scatter(x=[w], y=[v], mode="markers+text", text=[pct(v, 1)],
                             textposition="top center", marker=dict(size=12, color=T.LOSS),
                             name="Your mix"))
    fig.add_trace(go.Scatter(x=[0, 1], y=[s2, s1], line=dict(dash="dot", color=T.NEUTRAL),
                             name="No diversification (ρ = 1)"))
    fig.update_yaxes(tickformat=".0%")
    chart(_fig(fig, "Diversification", "Weight in asset 1", "Volatility"), key=f"{key}c")


@widget("normal_vs_real")
def _normal_real(key: str) -> None:
    t = st.text_input("Ticker", "SPY", key=key).upper()
    r = history(t, date(1995, 1, 1), date.today())["adj_close"].pct_change().dropna()
    z = (r - r.mean()) / r.std()
    xs = np.linspace(-8, 8, 400)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=z, nbinsx=200, histnorm="probability density",
                               marker_color=T.ACCENT, opacity=0.7, name="Real daily returns"))
    fig.add_trace(go.Scatter(x=xs, y=stats.norm.pdf(xs), line=dict(color=T.LOSS, width=2),
                             name="Normal curve"))
    fig.update_xaxes(range=[-8, 8])
    chart(_fig(fig, f"{t}: standardized daily returns vs the normal curve", "Standard deviations",
               "Density"), key=f"{key}c")
    beyond = float((z.abs() > 3).mean())
    c = st.columns(4)
    c[0].metric("Days observed", f"{len(z):,}")
    c[1].metric("Beyond ±3σ (real)", f"{beyond:.2%}")
    c[2].metric("Beyond ±3σ (normal)", "0.27%")
    c[3].metric("Excess kurtosis", f"{stats.kurtosis(r):.1f}")
    st.caption(f"Worst day: {pct(r.min(), 1)} on {r.idxmin():%Y-%m-%d} = {z.min():.1f}σ.")


@widget("distribution_surface_mini")
def _dist_surface(key: str) -> None:
    from quantforge.timeseries.distribution import rolling_density_surface
    t = st.text_input("Ticker", "SPY", key=key).upper()
    r = history(t, date(2005, 1, 1), date.today())["adj_close"].pct_change().dropna()
    d, g, dens = rolling_density_surface(r, 63, 10, 60)
    fig = go.Figure(go.Surface(x=g * 100, y=d, z=dens, colorscale="Turbo", showscale=False))
    fig.update_layout(scene=dict(xaxis_title="Daily return (%)", yaxis_title="Date",
                                 zaxis_title="Density"), height=520)
    chart(_fig(fig, f"{t}: shape of the 3-month return distribution through time"), key=f"{key}c")
    st.caption("Low, wide ridges = high-volatility periods (2008, 2020). Rotate with the mouse.")


@widget("beta_scatter")
def _beta(key: str) -> None:
    from quantforge.portfolio import capm_regression
    t = st.text_input("Stock", "NVDA", key=key).upper()
    px = prices([t, "SPY"], _years(3), date.today())
    r = px.pct_change().dropna()
    res = capm_regression(r[t], r["SPY"])
    xs = np.linspace(r["SPY"].min(), r["SPY"].max(), 50)
    fig = go.Figure(go.Scatter(x=r["SPY"], y=r[t], mode="markers",
                               marker=dict(size=4, color=T.ACCENT, opacity=0.5), name="Days"))
    fig.add_trace(go.Scatter(x=xs, y=res.alpha / 252 + res.beta * xs,
                             line=dict(color=T.LOSS, width=3), name=f"β = {res.beta:.2f}"))
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    chart(_fig(fig, f"{t} vs S&P 500 (SPY), daily returns, 3 years", "SPY return",
               f"{t} return"), key=f"{key}c")
    st.markdown(f"β = **{res.beta:.2f}** (± {1.96 * res.beta_se:.2f}) · R² = "
                f"**{res.r_squared:.2f}** · α = {res.alpha:+.1%}/yr (t = {res.alpha_t:.2f})")


@widget("rolling_correlation")
def _rollcorr(key: str) -> None:
    c = st.columns(3)
    a = c[0].text_input("Asset A", "SPY", key=f"{key}a").upper()
    b = c[1].text_input("Asset B", "TLT", key=f"{key}b").upper()
    w = c[2].slider("Window (days)", 21, 252, 126, key=f"{key}w")
    r = prices([a, b], date(2005, 1, 1), date.today()).pct_change().dropna()
    rc = r[a].rolling(w).corr(r[b])
    fig = go.Figure(go.Scatter(x=rc.index, y=rc, line=dict(color=T.ACCENT)))
    fig.add_hline(y=0, line_color=T.NEUTRAL)
    chart(_fig(fig, f"Rolling {w}-day correlation {a} / {b}", "Date", "ρ"), key=f"{key}c")
    st.caption(f"Full-period correlation {r[a].corr(r[b]):.2f} — but look how much it moves.")


@widget("bond_calculator")
def _bond(key: str) -> None:
    c = st.columns(4)
    face = c[0].number_input("Face value", value=100.0, key=f"{key}f")
    cpn = c[1].number_input("Coupon (%)", value=4.0, key=f"{key}c") / 100
    yrs = c[2].slider("Years to maturity", 1, 30, 10, key=f"{key}y")
    y = c[3].slider("Market yield (%)", 0.0, 12.0, 5.0, 0.25, key=f"{key}r") / 100
    t = np.arange(1, yrs + 1)

    def price(yy: float) -> float:
        return float((cpn * face / (1 + yy) ** t).sum() + face / (1 + yy) ** yrs)

    p = price(y)
    dur = float((t * cpn * face / (1 + y) ** t).sum() + yrs * face / (1 + y) ** yrs) / p
    st.metric("Price", f"{p:,.2f}", f"Macaulay duration {dur:.2f} years", delta_color="off")
    ys = np.linspace(0.0, 0.12, 100)
    fig = go.Figure(go.Scatter(x=ys, y=[price(v) for v in ys], line=dict(color=T.ACCENT, width=3)))
    fig.add_trace(go.Scatter(x=[y], y=[p], mode="markers", marker=dict(size=12, color=T.LOSS)))
    fig.add_hline(y=face, line_dash="dot", line_color=T.NEUTRAL, annotation_text="Par")
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(showlegend=False)
    chart(_fig(fig, "Price falls when yield rises", "Yield", "Price"), key=f"{key}g")


@widget("live_yield_curve")
def _curve(key: str) -> None:
    from quantforge.viz import yield_curve_chart
    chart(yield_curve_chart(cached_curve()), key=f"{key}c")


# ------------------------------------------------------------------ level 3
@widget("frontier_builder")
def _frontier(key: str) -> None:
    from quantforge.portfolio import efficient_frontier, estimate_inputs, max_sharpe, min_variance
    from quantforge.viz import efficient_frontier_chart
    raw = st.text_input("Tickers", "SPY, TLT, GLD, EFA, QQQ", key=key)
    tk = [x.strip().upper() for x in raw.split(",") if x.strip()]
    r = prices(tk, _years(10), date.today()).pct_change().dropna()
    mu, cov = estimate_inputs(r)
    rf = md().risk_free_rate("3M")
    ms, mv = max_sharpe(mu, cov, rf), min_variance(mu, cov)
    fig = efficient_frontier_chart(efficient_frontier(mu, cov, 40), mu,
                                   pd.Series(np.sqrt(np.diag(cov)), index=mu.index),
                                   {"Max Sharpe": (ms.volatility, ms.expected_return),
                                    "Min variance": (mv.volatility, mv.expected_return)}, rf)
    chart(fig, key=f"{key}c")
    st.caption("Max-Sharpe weights: " + ", ".join(f"{k} {v:.0%}" for k, v in
                                                   ms.weights.items() if v > 0.005))


@widget("capm_regression_live")
def _capm(key: str) -> None:
    from quantforge.portfolio import security_market_line
    from quantforge.viz import sml_chart
    raw = st.text_input("Stocks", "AAPL, JPM, XOM, JNJ, NVDA, KO", key=key)
    tk = [x.strip().upper() for x in raw.split(",") if x.strip()]
    r = prices(tk + ["SPY"], _years(5), date.today()).pct_change().dropna()
    rf = md().risk_free_rate("3M")
    sml = security_market_line(r[tk], r["SPY"], rf)
    chart(sml_chart(sml, r["SPY"].mean() * 252, rf), key=f"{key}c")
    st.dataframe(sml[["beta", "alpha", "alpha_pvalue", "r_squared"]].style.format(
        {"beta": "{:.2f}", "alpha": "{:+.2%}", "alpha_pvalue": "{:.3f}", "r_squared": "{:.2f}"}),
        width="stretch")


@widget("factor_live")
def _factors(key: str) -> None:
    from quantforge.portfolio import FACTOR_PROXIES, build_factor_returns, factor_regression
    from quantforge.viz import factor_chart
    t = st.text_input("Stock or fund", "BRK-B", key=key).upper()
    etfs = sorted({e for v in FACTOR_PROXIES.values() for e in v if e})
    px = prices(etfs + [t], _years(5), date.today())
    r = px.pct_change().dropna()
    f = build_factor_returns(r[etfs], md().risk_free_rate("3M"))
    chart(factor_chart(factor_regression(r[t], f), t), key=f"{key}c")


@widget("mini_backtest")
def _mini_bt(key: str) -> None:
    from quantforge.backtest import run_backtest, sma_crossover
    from quantforge.viz import cumulative_returns
    c = st.columns(3)
    t = c[0].text_input("Ticker", "SPY", key=key).upper()
    f = c[1].slider("Fast SMA", 10, 100, 50, 5, key=f"{key}f")
    s = c[2].slider("Slow SMA", 50, 300, 200, 10, key=f"{key}s")
    if f >= s:
        st.warning("Fast must be shorter than slow.")
        return
    px = history(t, date(2000, 1, 1), date.today())["adj_close"]
    res = run_backtest(px, sma_crossover(px, f, s), 5)
    chart(cumulative_returns(pd.DataFrame({"SMA strategy": res.returns,
                                           "Buy & hold": res.benchmark}).iloc[1:], log_scale=True),
          key=f"{key}c")
    st.dataframe(res.metrics.loc[["CAGR", "Volatility", "Sharpe", "Max drawdown", "Trades"]]
                 .style.format("{:.3f}"), width="stretch")


@widget("overfit_demo")
def _overfit(key: str) -> None:
    st.markdown("Generate **N random strategies** (coin-flip positions) on real SPY returns and "
                "look at the best one. None has any skill — by construction.")
    n = st.slider("Number of random strategies", 10, 1000, 200, key=key)
    r = history("SPY", _years(10), date.today())["adj_close"].pct_change().dropna().to_numpy()
    rng = np.random.default_rng(int(st.number_input("Seed", value=1, key=f"{key}s")))
    pos = rng.choice([-1.0, 1.0], size=(n, r.size))
    sr = (pos * r).mean(axis=1) / (pos * r).std(axis=1) * np.sqrt(252)
    fig = go.Figure(go.Histogram(x=sr, nbinsx=40, marker_color=T.ACCENT))
    fig.add_vline(x=sr.max(), line_color=T.LOSS, annotation_text=f"Best: {sr.max():.2f}")
    chart(_fig(fig, "Sharpe ratios of random strategies (in sample)", "Sharpe", "Count"),
          key=f"{key}c")
    st.caption(f"The best of {n} random strategies shows Sharpe {sr.max():.2f} — pure luck. "
               "This is why out-of-sample testing is mandatory.")


# ------------------------------------------------------------------ level 4
@widget("payoff_lab")
def _payoff(key: str) -> None:
    from quantforge.pricing.strategies import PRESETS, Strategy
    from quantforge.viz import payoff_diagram
    c = st.columns(3)
    name = c[0].selectbox("Strategy", list(PRESETS), key=key)
    vol = c[1].slider("Volatility (%)", 5, 100, 25, key=f"{key}v") / 100
    days = c[2].slider("Days to expiry", 5, 365, 45, key=f"{key}d")
    s = Strategy(PRESETS[name](100.0), name)
    T_ = days / 365
    g = np.linspace(60, 140, 400)
    pe = s.profit_at_expiry(g, 100, T_, 0.04, vol)
    today = s.value(g, T_, 0.04, vol)["price"] - s.entry_cost(100, T_, 0.04, vol)
    chart(payoff_diagram(g, pe, today, 100, s.breakevens(100, T_, 0.04, vol), name), key=f"{key}c")
    st.caption("Premiums from Black-Scholes on a $100 stock. Use the Strategy Builder page for "
               "live market premiums.")


@widget("bs_sliders")
def _bs(key: str) -> None:
    from quantforge.pricing import bs_greeks
    c = st.columns(6)
    S = c[0].number_input("Spot", value=100.0, key=f"{key}s")
    K = c[1].number_input("Strike", value=100.0, key=f"{key}k")
    T_ = c[2].number_input("Years", value=1.0, min_value=0.01, key=f"{key}t")
    r = c[3].number_input("Rate (%)", value=5.0, key=f"{key}r") / 100
    v = c[4].number_input("Vol (%)", value=20.0, min_value=1.0, key=f"{key}v") / 100
    typ = c[5].radio("Type", ["call", "put"], key=f"{key}y")
    g = bs_greeks(S, K, T_, r, v, typ)
    m = st.columns(6)
    m[0].metric("Price", f"{g.price:.4f}")
    m[1].metric("Delta", f"{g.delta:.4f}")
    m[2].metric("Gamma", f"{g.gamma:.4f}")
    m[3].metric("Vega /1pt", f"{g.vega / 100:.4f}")
    m[4].metric("Theta /day", f"{g.theta / 365:.4f}")
    m[5].metric("Rho /1%", f"{g.rho / 100:.4f}")


@widget("greek_surface_live")
def _greek_surf(key: str) -> None:
    from quantforge.pricing import bs_greeks
    from quantforge.viz import greek_surface
    greek = st.selectbox("Greek", ["gamma", "delta", "vega", "theta", "price"], key=key)
    s = np.linspace(60, 140, 60)
    t = np.linspace(0.02, 1.0, 40)
    S, TT = np.meshgrid(s, t)
    z = np.asarray(getattr(bs_greeks(S, 100, TT, 0.04, 0.25, "call"), greek))
    chart(greek_surface(s, t, z, greek, f"Call {greek}: strike 100, σ 25%"), key=f"{key}c")


@widget("tree_viewer")
def _tree(key: str) -> None:
    c = st.columns(5)
    n = c[0].slider("Steps", 1, 8, 3, key=key)
    S = c[1].number_input("Spot", value=100.0, key=f"{key}s")
    K = c[2].number_input("Strike", value=100.0, key=f"{key}k")
    v = c[3].number_input("Vol (%)", value=20.0, key=f"{key}v") / 100
    style = c[4].radio("Style", ["european", "american"], key=f"{key}x")
    typ = st.radio("Type", ["call", "put"], horizontal=True, key=f"{key}t")
    T_, r = 1.0, 0.05
    dt = T_ / n
    u = np.exp(v * np.sqrt(dt))
    d = 1 / u
    p = (np.exp(r * dt) - d) / (u - d)
    disc = np.exp(-r * dt)
    val = {}
    for j in range(n + 1):
        sp = S * u**j * d ** (n - j)
        val[(n, j)] = max(sp - K, 0) if typ == "call" else max(K - sp, 0)
    for i in range(n - 1, -1, -1):
        for j in range(i + 1):
            cont = disc * (p * val[(i + 1, j + 1)] + (1 - p) * val[(i + 1, j)])
            sp = S * u**j * d ** (i - j)
            ex = max(sp - K, 0) if typ == "call" else max(K - sp, 0)
            val[(i, j)] = max(cont, ex) if style == "american" else cont
    fig = go.Figure()
    for i in range(n):
        for j in range(i + 1):
            for jj in (j, j + 1):
                fig.add_trace(go.Scatter(x=[i, i + 1], y=[S * u**j * d ** (i - j),
                                                           S * u**jj * d ** (i + 1 - jj)],
                                         mode="lines", line=dict(color=T.NEUTRAL, width=1),
                                         hoverinfo="skip", showlegend=False))
    xs, ys, txt = [], [], []
    for (i, j), vv in val.items():
        xs.append(i)
        ys.append(S * u**j * d ** (i - j))
        txt.append(f"S={ys[-1]:.1f}<br>V={vv:.2f}")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=txt, textposition="top center",
                             marker=dict(size=10, color=T.ACCENT), showlegend=False))
    chart(_fig(fig, f"{n}-step CRR tree — u={u:.4f}, d={d:.4f}, p={p:.4f} → price "
                    f"{val[(0, 0)]:.4f}", "Step", "Stock price"), key=f"{key}c")


@widget("mc_convergence")
def _mc(key: str) -> None:
    from quantforge.pricing import bs_price, mc_european
    anti = st.toggle("Antithetic + control variate", False, key=key)
    ns = [500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]
    exact = bs_price(100, 100, 1, 0.05, 0.2, "call")
    res = [mc_european(100, 100, 1, 0.05, 0.2, "call", n_paths=n, antithetic=anti,
                       control_variate=anti, seed=7) for n in ns]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ns, y=[r.conf_interval[1] for r in res], line=dict(width=0),
                             showlegend=False))
    fig.add_trace(go.Scatter(x=ns, y=[r.conf_interval[0] for r in res], fill="tonexty",
                             fillcolor=T.BAND_FILL, line=dict(width=0), name="95% CI"))
    fig.add_trace(go.Scatter(x=ns, y=[r.price for r in res], mode="lines+markers",
                             name="Monte-Carlo", line=dict(color=T.ACCENT)))
    fig.add_hline(y=exact, line_color=T.LOSS, line_dash="dash",
                  annotation_text=f"Black-Scholes {exact:.4f}")
    fig.update_xaxes(type="log")
    chart(_fig(fig, "Monte-Carlo convergence (S=K=100, T=1, r=5%, σ=20%)", "Paths", "Price"),
          key=f"{key}c")


@widget("live_smile")
def _smile(key: str) -> None:
    from quantforge.app.common import cached_chain, cached_expiries
    from quantforge.pricing import chain_implied_vols
    from quantforge.viz import vol_smile
    prov = st.session_state.get("provider", "yahoo")
    t = st.text_input("Ticker with options", "SPY", key=key).upper()
    exps = [e for e in cached_expiries(prov, t)
            if (pd.Timestamp(e) - pd.Timestamp(date.today())).days >= 7][:4]
    chain = pd.concat([cached_chain(prov, t, e) for e in exps], ignore_index=True)
    spot = float(history(t, date.today() - timedelta(days=10), date.today())["close"].iloc[-1])
    ivs = chain_implied_vols(chain, spot, md().risk_free_rate("3M"))
    chart(vol_smile(ivs), key=f"{key}c")


# ------------------------------------------------------------------ level 5
@widget("var_live")
def _var(key: str) -> None:
    from quantforge.risk import var_report
    from quantforge.viz import var_distribution
    c = st.columns(3)
    t = c[0].text_input("Ticker", "SPY", key=key).upper()
    conf = c[1].select_slider("Confidence", [0.95, 0.975, 0.99], 0.99, key=f"{key}c")
    val = c[2].number_input("Position ($)", value=1_000_000.0, key=f"{key}v")
    r = history(t, _years(10), date.today())["adj_close"].pct_change().dropna()
    rep = var_report(r, conf, 1, val)
    st.dataframe(rep.style.format({"VaR": "{:.3%}", "ES": "{:.3%}", "VaR ($)": "${:,.0f}",
                                   "ES ($)": "${:,.0f}"}), width="stretch")
    h = rep.loc["Historical"]
    chart(var_distribution(r, h["VaR"], h["ES"], conf), key=f"{key}g")


@widget("stress_live")
def _stress(key: str) -> None:
    from quantforge.risk import historical_stress_test
    from quantforge.viz import stress_chart
    raw = st.text_input("Portfolio (equal weights)", "SPY, TLT, GLD", key=key)
    tk = [x.strip().upper() for x in raw.split(",") if x.strip()]
    px = prices(list(dict.fromkeys(tk + ["SPY"])), date(1990, 1, 1), date.today(), dropna=False)
    res = historical_stress_test(px, {t: 1 / len(tk) for t in tk}, px["SPY"].dropna())
    if not res.empty:
        chart(stress_chart(res), key=f"{key}c")


@widget("acf_live")
def _acf(key: str) -> None:
    from quantforge.timeseries import acf, pacf
    from quantforge.viz import acf_chart
    t = st.text_input("Ticker", "SPY", key=key).upper()
    lr = np.log(history(t, _years(10), date.today())["adj_close"]).diff().dropna()
    c1, c2 = st.columns(2)
    with c1:
        chart(acf_chart(acf(lr, 20), pacf(lr, 20), len(lr), "Returns"), key=f"{key}a")
    with c2:
        chart(acf_chart(acf(lr**2, 20), None, len(lr), "Squared returns"), key=f"{key}b")


@widget("garch_live")
def _garch(key: str) -> None:
    from quantforge.timeseries import fit_garch
    from quantforge.viz import garch_chart
    t = st.text_input("Ticker", "SPY", key=key).upper()
    lr = np.log(history(t, _years(10), date.today())["adj_close"]).diff().dropna()
    g = fit_garch(lr, "t", True)
    m = st.columns(3)
    m[0].metric("Persistence α+β+γ/2", f"{g.persistence:.4f}")
    m[1].metric("Half-life", f"{g.half_life:.0f} days")
    m[2].metric("Long-run vol", pct(g.long_run_vol, 1))
    chart(garch_chart(lr, g.conditional_vol, forecast=g.forecast(63), name=t), key=f"{key}c")


@widget("regime_live")
def _regime(key: str) -> None:
    from quantforge.timeseries.regimes import fit_hmm
    from quantforge.viz.pro import regime_chart
    t = st.text_input("Ticker", "SPY", key=key).upper()
    px = history(t, date(2005, 1, 1), date.today())["adj_close"]
    res = fit_hmm(np.log(px).diff().dropna(), 2)
    chart(regime_chart(px, res, "filtered"), key=f"{key}c")
    st.dataframe(res.summary().style.format({"annual_return": "{:.1%}", "annual_vol": "{:.1%}",
                                             "expected_duration": "{:.0f}",
                                             "long_run_share": "{:.0%}",
                                             "share_of_sample": "{:.0%}"}), width="stretch")


@widget("pairs_live")
def _pairs(key: str) -> None:
    from quantforge.backtest import pairs_backtest
    from quantforge.timeseries import engle_granger
    from quantforge.viz import pairs_chart
    c = st.columns(2)
    a = c[0].text_input("Y", "KO", key=f"{key}a").upper()
    b = c[1].text_input("X", "PEP", key=f"{key}b").upper()
    px = prices([a, b], _years(8), date.today())
    eg = engle_granger(px[a], px[b])
    st.markdown(f"Engle-Granger p-value **{eg.p_value:.3f}** → "
                f"{'cointegrated ✅' if eg.cointegrated_5pct else 'not cointegrated ⚠️'} · "
                f"half-life {eg.half_life:.0f} days")
    res = pairs_backtest(px[a], px[b])
    chart(pairs_chart(px[a], px[b], res, 2.0, 0.5), key=f"{key}c")


@widget("merton_live")
def _merton(key: str) -> None:
    from quantforge.app.common import cached_fundamentals
    from quantforge.credit import kmv_default_point, merton_model
    t = st.text_input("Company", "F", key=key).upper()
    f = cached_fundamentals(st.session_state.get("provider", "yahoo"), t)
    if not all(f.get(k) for k in ("market_cap", "short_term_debt", "long_term_debt")):
        st.warning("The provider does not report all items for this company.")
        return
    sig = float(np.log(history(t, _years(1), date.today())["adj_close"]).diff().std()
                * np.sqrt(252))
    res = merton_model(f["market_cap"], sig, kmv_default_point(f["short_term_debt"],
                                                               f["long_term_debt"]),
                       md().risk_free_rate("1Y"))
    m = st.columns(4)
    m[0].metric("Distance to default", f"{res.distance_to_default:.2f}")
    m[1].metric("PD (1y, risk-neutral)", pct(res.default_probability, 3))
    m[2].metric("Equity vol (1y)", pct(sig, 1))
    m[3].metric("Asset vol", pct(res.asset_vol, 1))
    st.caption(f"{f.get('name') or t} · fiscal {f.get('fiscal_date')} · source {f['source']}")


@widget("logit_demo")
def _logit(key: str) -> None:
    st.markdown("Upload a loan CSV with a 0/1 default column on the **Credit** page to fit and "
                "validate a real scorecard. Here: how AUC relates to separation between the "
                "score distributions of defaulters and non-defaulters.")
    sep = st.slider("Separation between groups (in standard deviations)", 0.0, 3.0, 1.0, 0.1,
                    key=key)
    auc = float(stats.norm.cdf(sep / np.sqrt(2)))
    xs = np.linspace(-4, 4 + sep, 300)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=stats.norm.pdf(xs), fill="tozeroy", fillcolor=T.GAIN_FILL,
                             line=dict(color=T.GAIN), name="Non-defaulters"))
    fig.add_trace(go.Scatter(x=xs, y=stats.norm.pdf(xs - sep), fill="tozeroy",
                             fillcolor=T.LOSS_FILL, line=dict(color=T.LOSS), name="Defaulters"))
    chart(_fig(fig, f"AUC = Φ(d/√2) = {auc:.3f} · Gini = {2 * auc - 1:.3f}", "Risk score",
               "Density"), key=f"{key}c")


# ------------------------------------------------------------------ capstone
@widget("capstone_checklist")
def _checklist(key: str) -> None:
    steps = ["Question and refutation criterion written down", "Data, period and provider chosen",
             "Method, parameters, costs and benchmark fixed", "In-sample design done",
             "Out-of-sample / walk-forward test run", "Risk: drawdown, VaR/ES, stress, regimes",
             "Robustness: parameters, markets, periods, costs, trade Monte-Carlo",
             "One-page write-up with limitations"]
    done = [st.checkbox(s, key=f"{key}_{i}") for i, s in enumerate(steps)]
    st.progress(sum(done) / len(steps), f"{sum(done)}/{len(steps)} steps")
    note = st.text_area("Draft your research note", height=200, key=f"{key}_note")
    if note:
        st.download_button("⬇️ Download note (.md)", note.encode(), "research_note.md",
                           key=f"{key}_dl")


# ------------------------------------------------------------------ level 7
@widget("vectorization_race")
def _vectorization_race(key: str) -> None:
    import time
    tick = st.text_input("Ticker (10 years of real daily closes)", "SPY", key=key + "_t").upper()
    p = history(tick, _years(10), date.today())["close"].to_numpy()
    if st.button("Race: Python loop vs NumPy", key=key + "_go"):
        t0 = time.perf_counter()
        for _ in range(20):
            loop = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
        t_loop = (time.perf_counter() - t0) / 20
        t0 = time.perf_counter()
        for _ in range(20):
            vec = p[1:] / p[:-1] - 1
        t_vec = (time.perf_counter() - t0) / 20
        c = st.columns(3)
        c[0].metric("Python loop", f"{t_loop * 1e3:.2f} ms")
        c[1].metric("NumPy", f"{t_vec * 1e3:.3f} ms")
        c[2].metric("Speed-up", f"×{t_loop / max(t_vec, 1e-9):.0f}")
        st.caption(f"{len(p):,} real closes of {tick}. Same answers: "
                   f"max difference {np.abs(np.array(loop) - vec).max():.1e}.")


@widget("engine_benchmark")
def _engine_benchmark(key: str) -> None:
    from quantforge import native
    if not native.available():
        st.info("The C++ engine is not built on this server. On your computer run "
                "`quantforge-build-native` (or open **Options → C++ engine** and press Build).")
        return
    n = st.select_slider("Monte-Carlo paths", [100_000, 1_000_000, 4_000_000], 1_000_000,
                         key=key + "_n")
    if st.button("Run C++ vs NumPy", key=key + "_go"):
        rows = native.benchmark(n_options=100_000, n_paths=n, tree_steps=1001)
        st.dataframe(pd.DataFrame({
            "Task": [r["task"] for r in rows],
            "NumPy (ms)": [round(r["python_s"] * 1e3, 2) for r in rows],
            "C++ (ms)": [round(r["cpp_s"] * 1e3, 2) for r in rows],
            "Speed-up": [f"×{r['speedup']:.1f}" for r in rows],
            "Difference": [f"{r['max_abs_diff']:.1e}" for r in rows]}),
            hide_index=True, width="stretch")
        st.caption("Measured live on this machine. Monte-Carlo values differ only by sampling "
                   "noise.")
