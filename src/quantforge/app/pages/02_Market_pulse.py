from datetime import date, timedelta

import pandas as pd
import streamlit as st

from quantforge.app.common import chart, download_csv, page_setup, pct, prices, source_note
from quantforge.portfolio import ASSET_CLASS_ETFS, SECTOR_ETFS, period_returns
from quantforge.viz import cumulative_returns, period_bar_chart, returns_heatmap

HOW_TO = """1. Choose a **universe**: US sectors, asset classes (stocks, bonds, gold, oil, bitcoin…)
   or your own **watchlist**.
2. The **heatmap** shows real trailing returns: green = up, red = down. Hover any cell.
3. Pick a period for the **ranking** bar chart (best to worst).
4. The bottom chart compares everything rebased to 100 over the last year."""

page_setup("Market pulse", "🌡️", HOW_TO)

UNIVERSES = {"US sectors (SPDR ETFs)": SECTOR_ETFS, "Asset classes": ASSET_CLASS_ETFS,
             "My watchlist": None}
c1, c2 = st.columns([1, 2])
uni = c1.radio("Universe", list(UNIVERSES), horizontal=False)
labels = UNIVERSES[uni]
if labels is None:
    raw = c2.text_input("Watchlist tickers", st.session_state.get(
        "watchlist", "AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, JPM, V, LLY"),
        help="Any tickers your provider knows, separated by commas.")
    st.session_state["watchlist"] = raw
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    labels = {}
else:
    tickers = list(labels)
    c2.markdown("  \n".join(f"`{k}` {v}" for k, v in labels.items()))

px = prices(tickers, date.today() - timedelta(days=4 * 365 + 10), date.today(), dropna=False)
px = px.dropna(axis=1, how="all")
missing = sorted(set(tickers) - set(px.columns))
if missing:
    st.warning("No data for: " + ", ".join(missing))
table = period_returns(px.ffill(limit=3))
st.caption(f"As of close {table.attrs['as_of']} · {source_note()}")

chart(returns_heatmap(table, labels, source=source_note()), key="heat")

c1, c2 = st.columns([1, 3])
period = c1.radio("Rank by", ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y ann."], 5)
with c2:
    chart(period_bar_chart(table, period, labels), key="bars")

last_year = px.loc[px.index[-1] - pd.DateOffset(years=1):].dropna(axis=1, how="any")
chart(cumulative_returns(last_year.pct_change().dropna(), source=source_note()), key="rel")

fmt = table.copy()
st.dataframe(fmt.style.format(lambda v: pct(v, 1)), width="stretch")
download_csv(table, "market_pulse", "⬇️ Download table (CSV)")
