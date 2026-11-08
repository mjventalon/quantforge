"""Live intraday market view with automatic refresh."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from quantforge.app.common import chart, md, page_setup, source_note, ticker_input
from quantforge.viz import live_chart

HOW_TO = """1. Pick any ticker (type a few letters or a company name).
2. Choose how often to refresh. The chart **updates by itself** without reloading the page and
   keeps your zoom.
3. The board below follows several instruments at once.

**About "live":** prices come from your data provider. Yahoo Finance is near real time for US
stocks but may be delayed for some exchanges; Massive (Polygon) depends on your plan. Outside
market hours you see the last session."""

page_setup("Live market", "⚡", HOW_TO)

c = st.columns([2, 1, 1, 1])
with c[0]:
    ticker = ticker_input(default="SPY", key="live_ticker")
refresh = c[1].selectbox("Refresh", [5, 10, 30, 60], index=1, format_func=lambda s: f"every {s}s")
RANGES = {  # label: (period, bar size) — Yahoo keeps 1-minute bars ~7 days, 1-hour ~2 years
    "1 day · 1m": ("1d", "1m"), "5 days · 5m": ("5d", "5m"), "1 month · 15m": ("1mo", "15m"),
    "3 months · 1h": ("3mo", "1h"), "1 year · daily": ("1y", "1d"),
    "5 years · daily": ("5y", "1d"), "10 years · weekly": ("10y", "1wk"),
    "All history · weekly": ("max", "1wk")}
rng = c[2].selectbox("Range", list(RANGES), index=0,
                     help="Short ranges refresh live; long ranges show the whole history.")
period, interval = RANGES[rng]
style = c[3].radio("Style", ["candles", "line"], horizontal=True)


@st.cache_data(ttl=3600, show_spinner=False)
def prev_close(provider: str, t: str) -> float | None:
    try:
        h = md().history(t, date.today() - timedelta(days=10), date.today())
        last_day = h.index[-1].date()
        return float(h["close"].iloc[-2] if last_day == date.today() else h["close"].iloc[-1])
    except Exception:  # noqa: BLE001
        return None


@st.fragment(run_every=refresh)
def live_view() -> None:
    try:
        bars = md().intraday(ticker, period, interval)
    except Exception as exc:  # noqa: BLE001
        st.error(f"No intraday data for {ticker}: {exc}")
        return
    pc = prev_close(st.session_state.get("provider", "yahoo"), ticker)
    last = float(bars["close"].iloc[-1])
    m = st.columns(5)
    m[0].metric(ticker, f"{last:,.4g}", f"{last / pc - 1:+.2%}" if pc else None)
    m[1].metric("High (range)", f"{bars['high'].max():,.4g}")
    m[2].metric("Low (range)", f"{bars['low'].min():,.4g}")
    m[3].metric("Volume", f"{bars['volume'].sum():,.0f}")
    m[4].metric("Last bar", f"{bars.index[-1]:%Y-%m-%d %H:%M}"[:16 if interval in
                ("1m", "5m", "15m", "1h") else 10], f"{len(bars):,} bars", delta_color="off")
    chart(live_chart(bars, ticker, pc if period in ("1d", "5d") else None, style,
                     title=f"{ticker} — {rng}"), key="live_main")
    st.caption(f"{source_note()} · updated {pd.Timestamp.now():%H:%M:%S} · refresh {refresh}s")


live_view()

st.divider()
st.markdown("#### Market board")
board = st.multiselect("Instruments", ["SPY", "QQQ", "IWM", "DIA", "^VIX", "TLT", "GLD", "USO",
                                       "BTC-USD", "ETH-USD", "EURUSD=X", "AAPL", "MSFT", "NVDA",
                                       "AMZN", "TSLA"],
                       ["SPY", "QQQ", "^VIX", "TLT", "GLD", "BTC-USD"], accept_new_options=True)


@st.fragment(run_every=max(refresh, 15))
def board_view() -> None:
    import plotly.graph_objects as go

    from quantforge.viz import theme as T
    cols = st.columns(3)
    for i, t in enumerate(board):
        with cols[i % 3], st.container(border=True):
            try:
                b = md().intraday(t, "1d", "5m")
            except Exception as exc:  # noqa: BLE001
                st.caption(f"{t}: {exc}")
                continue
            pc = prev_close(st.session_state.get("provider", "yahoo"), t)
            last = float(b["close"].iloc[-1])
            ch = last / pc - 1 if pc else None
            st.metric(t, f"{last:,.4g}", f"{ch:+.2%}" if ch is not None else None)
            col = T.GAIN if (ch or 0) >= 0 else T.LOSS
            fig = go.Figure(go.Scatter(x=b.index, y=b["close"], line=dict(color=col, width=1.6)))
            if pc:
                fig.add_hline(y=pc, line_dash="dot", line_color=T.NEUTRAL)
            fig.update_layout(height=120, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                              xaxis=dict(visible=False), yaxis=dict(visible=False),
                              template=T.TEMPLATE, uirevision=t)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False},
                            key=f"board_{t}")
    st.caption(f"Board refreshed {pd.Timestamp.now():%H:%M:%S} · change vs previous close · "
               "dotted line = previous close.")


board_view()
st.caption("Tip: the Volatility surface and Regimes & 3-D pages also have live 3-D modes.")
