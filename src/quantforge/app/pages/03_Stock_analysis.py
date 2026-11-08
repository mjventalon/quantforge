import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    cached_curve,
    chart,
    date_range,
    download_csv,
    history,
    page_setup,
    pct,
    source_note,
    ticker_input,
)
from quantforge.portfolio import performance_summary
from quantforge.timeseries import atr, realized_vol_table, rsi, volatility_cone
from quantforge.viz import drawdown_chart, technical_chart, vol_cone_chart, yield_curve_chart

HOW_TO = """1. Type any **ticker** (stocks, ETFs, indices like `^GSPC`, crypto like `BTC-USD` on Yahoo).
2. Pick the **date range**. The big chart shows candles, moving averages and Bollinger bands,
   with **volume**, **RSI** and **MACD** underneath — switch each one on or off.
3. The **signals** box summarizes what the indicators say today, in plain English.
4. Tabs: performance statistics, 6 volatility estimators, the volatility cone and the
   Treasury yield curve."""

page_setup("Stock analysis", "📊", HOW_TO)

c1, c2 = st.columns([1, 2])
with c1:
    ticker = ticker_input()
with c2:
    start, end = date_range(5, "mkt")

df = history(ticker, start, end)
src = source_note(f"fetched {df.attrs.get('fetched_at', '')}")
ret = df["adj_close"].pct_change().dropna()
close = df["close"]

last, prev = close.iloc[-1], close.iloc[-2]
m = st.columns(6)
m[0].metric("Last close", f"{last:,.2f}", f"{last / prev - 1:+.2%}")
m[1].metric("Period return", pct(df["adj_close"].iloc[-1] / df["adj_close"].iloc[0] - 1, 1))
m[2].metric("52w high", f"{df['high'].iloc[-252:].max():,.2f}",
            f"{last / df['high'].iloc[-252:].max() - 1:+.1%} from high", delta_color="off")
m[3].metric("52w low", f"{df['low'].iloc[-252:].min():,.2f}")
m[4].metric("1y realized vol", pct(ret.iloc[-252:].std() * np.sqrt(252), 1))
m[5].metric("Last date", f"{df.index[-1]:%d %b %y}")

with st.container(border=True):
    o = st.columns(6)
    sma_sel = o[0].multiselect("Moving averages", [10, 20, 50, 100, 200], [50, 200],
                               help="Average price over the last N days. Price above the "
                                    "200-day line is usually read as an uptrend.")
    show_bb = o[1].toggle("Bollinger bands", True, help="±2 standard deviations around the "
                                                         "20-day average.")
    show_vol = o[2].toggle("Volume", True)
    show_rsi = o[3].toggle("RSI", True, help="Momentum oscillator 0-100. Above 70 = "
                                             "overbought, below 30 = oversold.")
    show_macd = o[4].toggle("MACD", True, help="Trend/momentum: MACD line crossing above "
                                               "its signal line is a bullish sign.")
    span = o[5].selectbox("Initial zoom", ["6M", "1Y", "2Y", "3Y", "All"], 4,
                          help="The whole period is always loaded: drag left or use the 1M…All "
                               "buttons to see older history.")
n = {"6M": 126, "1Y": 252, "2Y": 504, "3Y": 756, "All": len(df)}[span]
fig = technical_chart(df, ticker, sma_sel, show_bb, show_rsi, show_macd, show_vol, src)
fig.update_xaxes(range=[df.index[-min(n, len(df))], df.index[-1]])
chart(fig)

# ---- plain-English signal summary
r14 = float(rsi(close).iloc[-1])
sma50 = close.rolling(50).mean().iloc[-1]
sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
atr14 = float(atr(df).iloc[-1])
sig = []
if np.isfinite(sma200):
    sig.append(("🟢" if last > sma200 else "🔴") +
               f" Price is **{'above' if last > sma200 else 'below'}** its 200-day average "
               f"({sma200:,.2f}) → long-term trend {'up' if last > sma200 else 'down'}.")
    sig.append(("🟢" if sma50 > sma200 else "🔴") +
               f" 50-day average is {'above' if sma50 > sma200 else 'below'} the 200-day "
               f"({'golden cross' if sma50 > sma200 else 'death cross'} regime).")
sig.append(("🔴" if r14 > 70 else "🟢" if r14 < 30 else "⚪") +
           f" RSI is **{r14:.0f}** → " + ("overbought" if r14 > 70 else "oversold"
                                         if r14 < 30 else "neutral") + ".")
sig.append(f"📏 Average daily range (ATR 14): **{atr14:,.2f}** ({atr14 / last:.1%} of price).")
with st.container(border=True):
    st.markdown("**Signals today** (descriptive, not advice)")
    for s in sig:
        st.markdown(s)

t1, t2, t3, t4 = st.tabs(["Performance", "Realized volatility", "Volatility cone",
                          "Treasury curve"])
with t1:
    perf = performance_summary(ret.rename(ticker))
    fmt = perf.copy().astype(object)
    for r in fmt.index:
        if r not in ("Sharpe", "Sortino", "Calmar", "Skewness", "Excess kurtosis", "Observations"):
            fmt.loc[r] = [pct(v) for v in perf.loc[r]]
        else:
            fmt.loc[r] = [f"{v:,.2f}" if r != "Observations" else f"{int(v)}" for v in perf.loc[r]]
    st.dataframe(fmt, width="stretch")
    chart(drawdown_chart(ret, ticker))
    download_csv(df, f"{ticker}_prices", "⬇️ Download price history (CSV)")
with t2:
    w = st.slider("Window (days)", 10, 126, 21)
    rv = realized_vol_table(df, w).dropna()
    st.line_chart(rv)
    st.dataframe(rv.iloc[[-1]].T.rename(columns=lambda c: "latest").map(pct), width="stretch")
    st.caption("Yang-Zhang is the most efficient estimator when opening gaps exist.")
with t3:
    cone = volatility_cone(df["adj_close"])
    chart(vol_cone_chart(cone, name=ticker))
    st.dataframe(cone.map(pct), width="stretch")
with t4:
    try:
        curve = cached_curve()
        chart(yield_curve_chart(curve))
        st.dataframe(pd.DataFrame({"maturity (y)": curve.index, "yield": [pct(v) for v in curve]}),
                     hide_index=True)
    except Exception as exc:  # noqa: BLE001
        st.error(f"FRED unavailable: {exc}")
