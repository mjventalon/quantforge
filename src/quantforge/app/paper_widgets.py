"""Mini-widgets for the Paper trading page. Every widget uses real market data."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from quantforge.app.common import chart, md
from quantforge.paper import ORDER_TYPES, Account, Order, OrderError, Quote, target_orders
from quantforge.viz.theme import GAIN, LOSS
from quantforge.viz.theme import apply as themed

# ------------------------------------------------------------------ real prices


@st.cache_data(ttl=15, show_spinner=False)
def live_quote(provider: str, symbol: str) -> tuple[float, str, str]:
    """Latest price, its UTC timestamp and its exchange session date."""
    try:
        bars = md().intraday(symbol, "5d", "1m").dropna(subset=["close"])
        if bars.empty:
            raise ValueError("no intraday bars")
        ts = pd.Timestamp(bars.index[-1])
        local = ts if ts.tzinfo else ts.tz_localize("UTC")
        return (float(bars["close"].iloc[-1]), local.tz_convert("UTC").isoformat(),
                local.strftime("%Y-%m-%d"))
    except Exception:  # noqa: BLE001 - fall back to the last daily close
        h = md().history(symbol, date.today() - timedelta(days=14), date.today())
        d = pd.Timestamp(h.index[-1])
        return (float(h["close"].iloc[-1]), d.strftime("%Y-%m-%dT21:00:00+00:00"),
                d.strftime("%Y-%m-%d"))


@st.cache_data(ttl=900, show_spinner=False)
def previous_close(provider: str, symbol: str, session: str) -> float | None:
    h = md().history(symbol, date.today() - timedelta(days=20), date.today())["close"]
    h = h[h.index < pd.Timestamp(session)]
    return float(h.iloc[-1]) if len(h) else None


@st.cache_data(ttl=3600, show_spinner=False)
def daily_returns(provider: str, symbols: tuple[str, ...], years: int = 3) -> pd.DataFrame:
    px = md().prices(list(symbols), date.today() - timedelta(days=365 * years + 10), date.today())
    return px.pct_change().dropna()


def get_quotes(symbols: list[str]) -> tuple[dict[str, Quote], dict[str, str]]:
    prov = st.session_state.get("provider", "yahoo")
    quotes, errors = {}, {}
    for s in symbols:
        try:
            p, ts, sess = live_quote(prov, s)
            quotes[s] = Quote(p, ts, sess)
        except Exception as exc:  # noqa: BLE001
            errors[s] = str(exc)[:120]
    return quotes, errors


def day_pnl(acc: Account, quotes: dict[str, Quote]) -> float:
    prov = st.session_state.get("provider", "yahoo")
    total = 0.0
    for s, p in acc.positions.items():
        if abs(p.qty) < 1e-12 or s not in quotes:
            continue
        try:
            pc = previous_close(prov, s, quotes[s].session)
        except Exception:  # noqa: BLE001
            pc = None
        if pc:
            total += p.qty * (quotes[s].price - pc)
    return total


# ------------------------------------------------------------------ widgets
def w_order_ticket(acc: Account, quotes: dict[str, Quote], save) -> None:
    symbols = sorted(set(acc.watchlist) | set(acc.positions))
    c = st.columns([2, 1, 1])
    sym = c[0].selectbox("Symbol", symbols + ["Other…"], key="pt_sym")
    if sym == "Other…":
        sym = st.text_input("Ticker (Yahoo symbol)", key="pt_sym_other").strip().upper()
    side = c[1].segmented_control("Side", ["Buy", "Sell"], default="Buy", key="pt_side")
    otype = c[2].selectbox("Type", ORDER_TYPES, format_func=lambda t: t.replace("_", " "),
                           key="pt_type")
    if not sym:
        return
    q = quotes.get(sym)
    if q is None:
        try:
            p, ts, sess = live_quote(st.session_state.get("provider", "yahoo"), sym)
            q = Quote(p, ts, sess)
        except Exception as exc:  # noqa: BLE001
            st.error(f"No price for {sym}: {exc}")
            return
    st.caption(f"Last **{q.price:,.4g}** · {pd.Timestamp(q.ts):%Y-%m-%d %H:%M} UTC")
    c = st.columns(3)
    mode = c[0].radio("Size in", ["Shares", "Dollars"], horizontal=True, key="pt_mode")
    if mode == "Shares":
        qty = c[1].number_input("Quantity", 0.0, value=1.0, step=1.0, key="pt_qty")
    else:
        dollars = c[1].number_input("Amount ($)", 0.0, value=1000.0, step=100.0, key="pt_usd")
        qty = round(dollars / q.price, 6)
        c[1].caption(f"≈ {qty:,.4f} shares")
    tif = c[2].selectbox("Time in force", ["gtc", "day"],
                         format_func=lambda x: {"gtc": "Good till cancelled",
                                                "day": "Day"}[x], key="pt_tif")
    lim = stp = trail = None
    c = st.columns(3)
    if otype in ("limit", "stop_limit"):
        lim = c[0].number_input("Limit price", 0.0, value=float(f"{q.price:.4g}"), key="pt_lim")
    if otype in ("stop", "stop_limit"):
        stp = c[1].number_input("Stop price", 0.0, value=float(f"{q.price:.4g}"), key="pt_stp")
    if otype == "trailing_stop":
        trail = c[2].number_input("Trail (%)", 0.1, 50.0, 5.0, 0.5, key="pt_trail")
    est = qty * (lim or q.price)
    st.caption(f"Estimated {'cost' if side == 'Buy' else 'proceeds'}: **${est:,.2f}** · "
               f"buying power ${acc.buying_power():,.2f}")
    if st.button(f"{side} {qty:,.4g} {sym}", type="primary", key="pt_submit",
                 disabled=qty <= 0):
        try:
            o = acc.submit(Order(sym, side.lower(), qty, otype, lim, stp, trail, tif), q)
            save()
            st.success(f"Order {o.id} accepted — it executes on the next real price update "
                       "(market closed: at the next session).")
        except OrderError as exc:
            st.error(str(exc))


def w_positions(acc: Account, quotes, save) -> None:
    df = acc.positions_frame({s: q.price for s, q in quotes.items()})
    if df.empty:
        st.info("No positions yet — place an order with the ticket.")
        return
    st.dataframe(df.style.format({"Qty": "{:,.4g}", "Avg cost": "{:,.4f}", "Last": "{:,.4f}",
                                  "Market value": "${:,.2f}", "Unrealized P&L": "${:+,.2f}",
                                  "Unrealized %": "{:+.2%}", "Realized P&L": "${:+,.2f}",
                                  "Weight": "{:.1%}"})
                 .map(lambda v: f"color: {GAIN if v > 0 else LOSS}" if isinstance(v, float)
                      and v != 0 else "", subset=["Unrealized P&L", "Unrealized %"]),
                 hide_index=True, width="stretch")
    c = st.columns([2, 1])
    s = c[0].selectbox("Close a position", df["Symbol"], key="pt_close_sym")
    if c[1].button("Close at market", key="pt_close"):
        qty = acc.positions[s].qty
        acc.submit(Order(s, "sell" if qty > 0 else "buy", abs(qty), note="close"), quotes.get(s))
        save()
        st.success(f"Closing order for {s} sent.")


def w_open_orders(acc: Account, quotes, save) -> None:
    oo = acc.open_orders()
    if not oo:
        st.caption("No open orders.")
        return
    st.dataframe(pd.DataFrame([{
        "ID": o.id, "Symbol": o.symbol, "Side": o.side, "Qty": o.qty,
        "Type": o.type.replace("_", " "), "Limit": o.limit, "Stop": o.stop,
        "Trail %": o.trail_pct, "TIF": o.tif, "Submitted (UTC)": o.submitted[:16]}
        for o in oo]), hide_index=True, width="stretch")
    c = st.columns([2, 1, 1])
    oid = c[0].selectbox("Order", [o.id for o in oo], key="pt_cancel_id")
    if c[1].button("Cancel", key="pt_cancel"):
        acc.cancel(oid)
        save()
        st.rerun()
    if c[2].button("Cancel all", key="pt_cancel_all"):
        for o in oo:
            acc.cancel(o.id)
        save()
        st.rerun()


def w_history(acc: Account, quotes, save) -> None:
    done = [o for o in acc.orders if o.status != "open"][-200:][::-1]
    if not done:
        st.caption("No order history yet.")
        return
    st.dataframe(pd.DataFrame([{
        "Time (UTC)": (o.filled_ts or o.submitted)[:16].replace("T", " "), "Symbol": o.symbol,
        "Side": o.side, "Qty": o.qty, "Type": o.type.replace("_", " "), "Status": o.status,
        "Fill price": o.fill_price, "Note": o.reason or o.note} for o in done]),
        hide_index=True, width="stretch", height=320)


def w_equity(acc: Account, quotes, save) -> None:
    eq = acc.equity_series()
    if len(eq) < 2:
        st.caption("The equity curve fills in as prices update (one point per minute).")
        return
    fig = go.Figure(go.Scatter(x=eq.index, y=eq.values, name="Your account",
                               line=dict(color=GAIN if eq.iloc[-1] >= acc.starting_cash
                                         else LOSS, width=2), fill="tozeroy",
                               fillcolor="rgba(128,128,128,0.06)"))
    try:
        spy = md().history("SPY", eq.index[0].date() - timedelta(days=5), date.today())["close"]
        spy = spy[spy.index >= pd.Timestamp(eq.index[0].date())]
        if len(spy) >= 2:
            fig.add_trace(go.Scatter(x=spy.index, y=acc.starting_cash * spy / spy.iloc[0],
                                     name="SPY (same start)", line=dict(dash="dot")))
    except Exception:  # noqa: BLE001
        pass
    fig.add_hline(y=acc.starting_cash, line_dash="dash", line_color="gray")
    fig.update_layout(height=320, yaxis_title="$", uirevision="equity",
                      yaxis_range=[eq.min() * 0.995, eq.max() * 1.005])
    chart(themed(fig, "Equity"), key="pt_eq")


def w_live_chart(acc: Account, quotes, save) -> None:
    syms = sorted(set(acc.positions) | set(acc.watchlist)) or ["SPY"]
    c = st.columns([2, 1])
    s = c[0].selectbox("Chart", syms, key="pt_chart_sym")
    iv = c[1].segmented_control("Bars", ["1m", "5m", "15m"], default="5m", key="pt_chart_iv")
    try:
        bars = md().intraday(s, "5d", iv or "5m").dropna(subset=["close"])
    except Exception as exc:  # noqa: BLE001
        st.error(f"No intraday data for {s}: {exc}")
        return
    fig = go.Figure(go.Candlestick(x=bars.index, open=bars["open"], high=bars["high"],
                                   low=bars["low"], close=bars["close"], name=s,
                                   increasing_line_color=GAIN, decreasing_line_color=LOSS))
    fl = [f for f in acc.fills if f.symbol == s]
    if fl:
        t = pd.to_datetime([f.ts for f in fl], utc=True)
        if bars.index.tz is not None:
            t = t.tz_convert(bars.index.tz)
        for side, sym, col in (("buy", "triangle-up", GAIN), ("sell", "triangle-down", LOSS)):
            m = [i for i, f in enumerate(fl) if f.side == side]
            if m:
                fig.add_trace(go.Scatter(x=t[m], y=[fl[i].price for i in m], mode="markers",
                                         marker=dict(symbol=sym, size=13, color=col),
                                         name=f"your {side}s"))
    p = acc.positions.get(s)
    if p and abs(p.qty) > 1e-12:
        fig.add_hline(y=p.avg_cost, line_dash="dot", annotation_text="avg cost")
    fig.update_layout(height=380, xaxis_rangeslider_visible=False, uirevision=f"pt_{s}_{iv}",
                      xaxis=dict(rangebreaks=[dict(bounds=["sat", "mon"])])
                      if not s.endswith("-USD") else {})
    chart(themed(fig, f"{s} — {iv} bars (real, may be delayed)"), key="pt_live")


def w_watchlist(acc: Account, quotes, save) -> None:
    prov = st.session_state.get("provider", "yahoo")
    rows = []
    for s in acc.watchlist:
        q = quotes.get(s)
        if q is None:
            continue
        try:
            pc = previous_close(prov, s, q.session)
        except Exception:  # noqa: BLE001
            pc = None
        rows.append({"Symbol": s, "Last": q.price, "Change": q.price - pc if pc else np.nan,
                     "Change %": q.price / pc - 1 if pc else np.nan,
                     "Time (UTC)": q.ts[11:16]})
    if rows:
        st.dataframe(pd.DataFrame(rows).style.format({"Last": "{:,.4f}", "Change": "{:+,.4f}",
                                                      "Change %": "{:+.2%}"})
                     .map(lambda v: f"color: {GAIN if v > 0 else LOSS}"
                          if isinstance(v, float) and v == v and v != 0 else "",
                          subset=["Change", "Change %"]),
                     hide_index=True, width="stretch")
    c = st.columns([3, 1, 1])
    new = c[0].text_input("Add symbol", key="pt_wl_add", placeholder="e.g. TSLA").strip().upper()
    if c[1].button("Add", key="pt_wl_btn") and new and new not in acc.watchlist:
        acc.watchlist.append(new)
        save()
        st.rerun()
    rm = c[2].selectbox("Remove", [""] + acc.watchlist, key="pt_wl_rm")
    if rm:
        acc.watchlist.remove(rm)
        save()
        st.rerun()


def w_allocation(acc: Account, quotes, save) -> None:
    df = acc.positions_frame({s: q.price for s, q in quotes.items()})
    labels = (list(df["Symbol"]) if not df.empty else []) + ["Cash"]
    vals = (list(df["Market value"].abs()) if not df.empty else []) + [max(acc.cash, 0)]
    fig = go.Figure(go.Pie(labels=labels, values=vals, hole=0.55, sort=False))
    fig.update_layout(height=320, showlegend=True)
    chart(themed(fig, "Allocation (gross)"), key="pt_alloc")


def _holdings_weights(acc: Account, quotes) -> pd.Series:
    df = acc.positions_frame({s: q.price for s, q in quotes.items()})
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("Symbol")["Weight"]


def w_risk(acc: Account, quotes, save) -> None:
    from quantforge.risk import historical_var, student_t_var
    w = _holdings_weights(acc, quotes)
    if w.empty:
        st.caption("Risk appears once you hold positions.")
        return
    try:
        r = daily_returns(st.session_state.get("provider", "yahoo"), tuple(w.index))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load history: {exc}")
        return
    port = r[w.index] @ w.values
    eq = acc.equity()
    h, t = historical_var(port, 0.99), student_t_var(port, 0.99)
    c = st.columns(3)
    c[0].metric("1-day VaR 99 % (historical)", f"${h.var * eq:,.0f}")
    c[1].metric("Expected shortfall 99 %", f"${h.es * eq:,.0f}")
    c[2].metric("VaR 99 % (Student-t)", f"${t.var * eq:,.0f}")
    vol = port.std() * np.sqrt(252)
    st.caption(f"Today's weights applied to {len(port)} real daily returns since "
               f"{port.index[0]:%Y-%m-%d}. Annualized volatility of the book: {vol:.1%}.")


@st.cache_data(ttl=3600, show_spinner=False)
def _garch(provider: str, s: str) -> tuple[float, float, float]:
    from quantforge.timeseries import fit_garch
    r = md().returns(s, start=date.today() - timedelta(days=365 * 4))[s]
    res = fit_garch(r, "t")
    f = res.forecast(21)
    return (float(f["vol_annualized"].iloc[0]), float(f["term_vol_annualized"].iloc[-1]),
            float(r.iloc[-63:].std() * np.sqrt(252)))


def w_garch(acc: Account, quotes, save) -> None:
    syms = sorted(set(acc.positions) | set(acc.watchlist)) or ["SPY"]
    s = st.selectbox("Asset", syms, key="pt_garch_sym")
    try:
        nxt, month, realized = _garch(st.session_state.get("provider", "yahoo"), s)
    except Exception as exc:  # noqa: BLE001
        st.error(f"GARCH could not be fitted for {s}: {exc}")
        return
    c = st.columns(3)
    c[0].metric("Tomorrow (annualized)", f"{nxt:.1%}")
    c[1].metric("Next 21 days", f"{month:.1%}")
    c[2].metric("Realized, last 3 months", f"{realized:.1%}")
    st.caption("GARCH(1,1) with Student-t errors fitted on 4 years of real daily returns.")


@st.cache_data(ttl=3600, show_spinner=False)
def _regime(provider: str, s: str) -> tuple[float, float, float]:
    from quantforge.timeseries.regimes import fit_hmm
    r = md().returns(s, start=date.today() - timedelta(days=365 * 10))[s]
    res = fit_hmm(r, 2, n_starts=3)
    hi = int(np.argmax(res.variances))
    return (float(res.filtered.iloc[-1, hi]), float(np.sqrt(res.variances[hi] * 252)),
            float(np.sqrt(res.variances[1 - hi] * 252)))


def w_regime(acc: Account, quotes, save) -> None:
    s = st.selectbox("Market", ["SPY", "QQQ", "IWM", "BTC-USD"], key="pt_reg_sym")
    try:
        p, hv, lv = _regime(st.session_state.get("provider", "yahoo"), s)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Regime model failed for {s}: {exc}")
        return
    st.metric("Probability of the turbulent regime today", f"{p:.0%}")
    st.progress(p)
    st.caption(f"2-state Gaussian HMM on 10 years of {s} daily returns, filtered (uses only "
               f"past data). Calm ≈ {lv:.0%} vol, turbulent ≈ {hv:.0%} vol.")


def w_signals(acc: Account, quotes, save) -> None:
    from quantforge.backtest import STRATEGIES
    name = st.selectbox("Strategy", list(STRATEGIES), key="pt_sig_strat")
    fn, params = STRATEGIES[name]
    rows = []
    for s in acc.watchlist[:12]:
        try:
            px = md().history(s, date.today() - timedelta(days=700), date.today())["adj_close"]
            sig = float(fn(px, **{k: v[0] for k, v in params.items()}).iloc[-1])
            rows.append({"Symbol": s, "Signal": "LONG" if sig > 0 else ("SHORT" if sig < 0
                                                                        else "FLAT"),
                         "Target exposure": sig})
        except Exception:  # noqa: BLE001
            continue
    if rows:
        st.dataframe(pd.DataFrame(rows).style.format({"Target exposure": "{:+.2f}"}),
                     hide_index=True, width="stretch")
    st.caption("Signals from yesterday's real close with default parameters. Research only.")


def w_invest(acc: Account, quotes, save) -> None:
    from quantforge.portfolio import estimate_inputs, max_sharpe, min_variance, risk_parity
    c = st.columns([3, 2])
    syms = c[0].multiselect("Assets", sorted(set(acc.watchlist) | {"SPY", "TLT", "GLD", "QQQ"}),
                            default=["SPY", "TLT", "GLD"], key="pt_inv_syms",
                            accept_new_options=True)
    method = c[1].selectbox("Model", ["Equal weight", "Minimum variance", "Maximum Sharpe",
                                      "Risk parity"], key="pt_inv_method")
    frac = st.slider("Invest this share of equity", 0.05, 1.0, 0.5, 0.05, key="pt_inv_frac")
    if len(syms) < 2 or not st.button("Compute target portfolio", key="pt_inv_go"):
        if "pt_plan" in st.session_state:
            _show_plan(acc, save)
        return
    syms = [s.upper() for s in syms]
    try:
        r = daily_returns(st.session_state.get("provider", "yahoo"), tuple(syms))
        mu, cov = estimate_inputs(r)
        w = {"Equal weight": lambda: pd.Series(1 / len(syms), index=syms),
             "Minimum variance": lambda: min_variance(mu, cov).weights,
             "Maximum Sharpe": lambda: max_sharpe(mu, cov).weights,
             "Risk parity": lambda: risk_parity(cov).weights}[method]()
        qs, _ = get_quotes(syms)
        prices = {s: q.price for s, q in qs.items()}
        keep = {s: float(x) for s, x in w.items() if x > 1e-4}
        # keep existing holdings outside the plan untouched
        for s, p in acc.positions.items():
            if abs(p.qty) > 1e-12 and s not in keep and s not in syms:
                keep[s] = p.qty * acc.last_prices.get(s, p.avg_cost) / acc.equity() / frac
                prices.setdefault(s, acc.last_prices.get(s, p.avg_cost))
        orders = target_orders(acc, keep, {**acc.last_prices, **prices}, frac)
        st.session_state["pt_plan"] = (method, w, orders, {s: qs[s] for s in qs})
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not build the portfolio: {exc}")
        return
    _show_plan(acc, save)


def _show_plan(acc: Account, save) -> None:
    method, w, orders, qs = st.session_state["pt_plan"]
    st.markdown(f"**{method}** weights (3 years of real daily returns):")
    st.dataframe(w.rename("weight").to_frame().T.style.format("{:.1%}"), width="stretch")
    if not orders:
        st.info("Already at target.")
        return
    st.dataframe(pd.DataFrame([{"Side": o.side, "Symbol": o.symbol, "Qty": o.qty}
                               for o in orders]).style.format({"Qty": "{:,.4f}"}),
                 hide_index=True, width="stretch")
    if st.button(f"Place {len(orders)} market orders", type="primary", key="pt_inv_place"):
        ok = 0
        for o in orders:
            q = qs.get(o.symbol) or Quote(acc.last_prices[o.symbol], "1970-01-01T00:00:00+00:00")
            try:
                acc.submit(o, q)
                ok += 1
            except OrderError as exc:
                st.error(f"{o.symbol}: {exc}")
        save()
        del st.session_state["pt_plan"]
        st.success(f"{ok} orders sent; they fill on the next real price update.")


def w_stats(acc: Account, quotes, save) -> None:
    eq = acc.equity_series()
    total = acc.equity() / acc.starting_cash - 1
    sells = [f for f in acc.fills if abs(f.realized) > 0]
    wins = sum(f.realized > 0 for f in sells)
    c = st.columns(4)
    c[0].metric("Total return", f"{total:+.2%}")
    c[1].metric("Fills", len(acc.fills))
    c[2].metric("Win rate (closing trades)", f"{wins / len(sells):.0%}" if sells else "—")
    c[3].metric("Commissions paid", f"${acc.total_commissions():,.2f}")
    if len(eq) > 30:
        daily = eq.resample("1D").last().dropna().pct_change().dropna()
        dd = (eq / eq.cummax() - 1).min()
        c = st.columns(3)
        c[0].metric("Max drawdown", f"{dd:.2%}")
        if len(daily) > 5 and daily.std() > 0:
            c[1].metric("Sharpe (daily, annualized)",
                        f"{daily.mean() / daily.std() * np.sqrt(252):.2f}")
        c[2].metric("Days tracked", len(daily))


WIDGETS = {
    "Order ticket": w_order_ticket,
    "Positions": w_positions,
    "Open orders": w_open_orders,
    "Live chart": w_live_chart,
    "Watchlist & quotes": w_watchlist,
    "Equity curve": w_equity,
    "Allocation": w_allocation,
    "Invest in a model portfolio": w_invest,
    "Portfolio risk (VaR / ES)": w_risk,
    "Volatility forecast (GARCH)": w_garch,
    "Market regime (HMM)": w_regime,
    "Strategy signals": w_signals,
    "Performance stats": w_stats,
    "Order history": w_history,
}
DEFAULT_WIDGETS = ["Order ticket", "Live chart", "Positions", "Watchlist & quotes",
                   "Open orders", "Equity curve", "Allocation", "Portfolio risk (VaR / ES)",
                   "Invest in a model portfolio", "Order history"]
