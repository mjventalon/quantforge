"""Shared state, data access and widgets for the Streamlit dashboard."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from quantforge import __version__
from quantforge.app import branding as B
from quantforge.data import DataError, MarketData, make_provider
from quantforge.viz.theme import PLOTLY_CONFIG

AUTHOR = B.AUTHOR

PROVIDER_LABELS = {
    "yahoo": "Yahoo Finance (free, no key)",
    "polygon": "Massive / Polygon.io (API key)",
    "fmp": "Financial Modeling Prep (API key)",
    "alphavantage": "Alpha Vantage (API key)",
}
KEY_ENV = {"polygon": "POLYGON_API_KEY", "fmp": "FMP_API_KEY",
           "alphavantage": "ALPHAVANTAGE_API_KEY"}


def page_setup(title: str, icon: str = "📈", how_to: str | None = None) -> None:
    """Standard page header: title and a 'How to use this page' box.

    Page config, navigation and the sidebar are set once in ``app.py``.
    """
    st.title(f"{icon} {title}")
    st.session_state["_qf_howto"] = how_to or ""
    if how_to:
        with st.expander("📘 How to use this page", expanded=False):
            st.markdown(how_to)
            st.caption("Charts: **scroll to zoom**, **click and drag to move**, double-click to "
                       "reset, camera icon to save a PNG. Full explanations in the **Guide** page.")


def chart(fig, key: str | None = None, **_: object) -> None:
    """Render a Plotly figure: wheel zoom + drag-to-pan for 2-D charts, free 360° rotation for
    3-D models, and range buttons (1M … All) on long time series."""
    if any(getattr(t, "type", "") in ("surface", "scatter3d", "mesh3d", "isosurface", "cone",
                                      "volume") for t in fig.data):
        ax = dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(128,128,128,0.35)",
                  zerolinecolor="rgba(128,128,128,0.5)")
        fig.update_scenes(bgcolor="rgba(0,0,0,0)", xaxis=ax, yaxis=ax, zaxis=ax,
                          dragmode="orbit")   # drag = rotate freely in every direction
    else:
        _range_buttons(fig)
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG, key=key)


def _range_buttons(fig) -> None:
    """Add 1M / 6M / YTD / 1Y / 5Y / All buttons when the x-axis is a long date series."""
    try:
        xs = [pd.to_datetime(pd.Series(t.x)) for t in fig.data
              if getattr(t, "x", None) is not None and len(t.x) > 0]
        xs = [x for x in xs if x.notna().all()]
    except (ValueError, TypeError):
        return
    if not xs:
        return
    span = max(x.max() for x in xs) - min(x.min() for x in xs)
    if span < pd.Timedelta(days=120):
        return
    buttons = [dict(count=1, label="1M", step="month", stepmode="backward"),
               dict(count=6, label="6M", step="month", stepmode="backward"),
               dict(count=1, label="YTD", step="year", stepmode="todate"),
               dict(count=1, label="1Y", step="year", stepmode="backward")]
    if span > pd.Timedelta(days=5 * 365):
        buttons.append(dict(count=5, label="5Y", step="year", stepmode="backward"))
    buttons.append(dict(step="all", label="All"))
    fig.update_layout(xaxis=dict(rangeselector=dict(
        buttons=buttons, x=0, y=1.02, xanchor="left", yanchor="bottom",
        bgcolor="rgba(128,128,128,0.15)", activecolor="#E4141D", font=dict(size=11))))


def heat(col: pd.Series) -> list[str]:
    """Red → neutral → green cell backgrounds for a numeric column (no matplotlib needed).
    Use with ``df.style.apply(heat, subset=[...])``."""
    x = pd.to_numeric(col, errors="coerce")
    lo, hi = x.min(), x.max()
    out = []
    for v in x:
        if pd.isna(v) or hi == lo:
            out.append("")
            continue
        t = (v - lo) / (hi - lo)                      # 0 … 1
        a = abs(t - 0.5) * 2 * 0.55                   # opacity grows away from the middle
        rgb = "46, 160, 67" if t >= 0.5 else "228, 20, 29"
        out.append(f"background-color: rgba({rgb}, {a:.2f})")
    return out


def download_csv(df: pd.DataFrame, name: str, label: str = "⬇️ Download CSV") -> None:
    st.download_button(label, df.to_csv().encode(), file_name=f"{name}.csv", mime="text/csv",
                       key=f"dl_{name}")


def sidebar() -> None:
    with st.sidebar:
        st.segmented_control("🖱️ Chart zoom speed", ["Slow", "Normal", "Fast"],
                             default=st.session_state.get("zoom_speed", "Normal"),
                             key="zoom_speed",
                             help="Mouse wheel / trackpad zoom on every chart. Click and drag "
                                  "to move; double-click to reset.")
        st.markdown("### ⚙️ Data source")
        default = st.session_state.get("provider", os.environ.get("QUANTFORGE_PROVIDER", "yahoo"))
        names = list(PROVIDER_LABELS)
        provider = st.selectbox("Market data provider", names, index=names.index(default)
                                if default in names else 0, format_func=PROVIDER_LABELS.get)
        st.session_state["provider"] = provider
        if provider in KEY_ENV:
            env = KEY_ENV[provider]
            key = st.text_input(f"{env}", type="password",
                                value=st.session_state.get(env, ""),
                                help="Kept in this browser session only. You can also put it "
                                     "in a .env file next to where you launch the app.")
            if key:
                st.session_state[env] = key
            elif not os.environ.get(env):
                st.warning(f"Enter your key or set {env} in .env")
        fred = st.text_input("FRED_API_KEY (optional)", type="password",
                             value=st.session_state.get("FRED_API_KEY", ""),
                             help="Treasury yields work without a key via FRED's public CSV.")
        if fred:
            st.session_state["FRED_API_KEY"] = fred
        st.caption("All numbers come from the selected provider and FRED. "
                   "quantforge never invents or fills in market data.")
        st.divider()
        links = [f"[LinkedIn]({B.LINKEDIN_URL})"] if B.LINKEDIN_URL else []
        if B.GITHUB_URL:
            links.append(f"[GitHub]({B.GITHUB_URL})")
        st.markdown(f"**{B.APP_NAME}** v{__version__}  \nBuilt by **{AUTHOR}**  \n"
                    + " · ".join(links))
        st.caption("Research & education only — not investment advice.")


@st.cache_resource(show_spinner=False)
def _market(provider: str, key: str | None, fred_key: str | None) -> MarketData:
    from quantforge.data import FredProvider
    kwargs = {"api_key": key} if key else {}
    return MarketData(make_provider(provider, **kwargs), fred=FredProvider(api_key=fred_key))


def md() -> MarketData:
    provider = st.session_state.get("provider", "yahoo")
    env = KEY_ENV.get(provider)
    key = st.session_state.get(env) if env else None
    try:
        return _market(provider, key or None, st.session_state.get("FRED_API_KEY") or None)
    except DataError as exc:
        st.error(str(exc))
        st.stop()


def guard(fn: Any, *args: Any, what: str = "data", **kwargs: Any) -> Any:
    """Run a data call; on failure show the real error and stop the page (never fake data)."""
    try:
        return fn(*args, **kwargs)
    except (DataError, ValueError, KeyError) as exc:
        st.error(f"Could not load {what}: {exc}")
        st.stop()


@st.cache_data(ttl=3600, show_spinner="Downloading prices…")
def cached_history(provider: str, ticker: str, start: date, end: date) -> pd.DataFrame:
    return md().history(ticker, start, end)


@st.cache_data(ttl=3600, show_spinner="Downloading prices…")
def cached_prices(provider: str, tickers: tuple[str, ...], start: date, end: date,
                  dropna: bool = True) -> pd.DataFrame:
    return md().prices(list(tickers), start, end, dropna=dropna)


@st.cache_data(ttl=900, show_spinner="Downloading option chain…")
def cached_chain(provider: str, ticker: str, expiry: str | None) -> pd.DataFrame:
    return md().option_chain(ticker, expiry)


@st.cache_data(ttl=900, show_spinner=False)
def cached_expiries(provider: str, ticker: str) -> list[str]:
    return [e.strftime("%Y-%m-%d") for e in md().option_expiries(ticker)]


@st.cache_data(ttl=3600, show_spinner="Fetching Treasury yields from FRED…")
def cached_rf(tenor: str = "3M") -> float:
    return md().risk_free_rate(tenor)


@st.cache_data(ttl=3600, show_spinner="Fetching Treasury curve from FRED…")
def cached_curve() -> pd.Series:
    return md().yield_curve()


@st.cache_data(ttl=86400, show_spinner="Fetching fundamentals…")
def cached_fundamentals(provider: str, ticker: str) -> dict[str, Any]:
    return md().fundamentals(ticker)


def history(ticker: str, start: date, end: date) -> pd.DataFrame:
    return guard(cached_history, st.session_state.get("provider", "yahoo"), ticker.upper(), start,
                 end, what=f"prices for {ticker}")


def prices(tickers: list[str], start: date, end: date, dropna: bool = True) -> pd.DataFrame:
    return guard(cached_prices, st.session_state.get("provider", "yahoo"),
                 tuple(t.upper() for t in tickers), start, end, dropna, what="prices")


def risk_free(tenor: str = "3M") -> float:
    """Real Treasury yield; if FRED is unreachable the user must type it (no silent default)."""
    try:
        return cached_rf(tenor)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"FRED is unreachable ({exc}). "
                   f"Enter today's {tenor} Treasury yield to continue.")
        val = st.number_input(f"{tenor} risk-free rate (%)", value=None, placeholder="e.g. 4.30",
                              key=f"rf_manual_{tenor}")
        if val is None:
            st.stop()
        return float(val) / 100.0


def source_note(extra: str = "") -> str:
    p = st.session_state.get("provider", "yahoo")
    return f"{PROVIDER_LABELS[p].split(' (')[0]}{' · ' + extra if extra else ''}"


@st.cache_data(ttl=86400, show_spinner=False)
def cached_universe() -> dict[str, str]:
    from quantforge.data import universe
    if B.CONTACT_EMAIL and "QUANTFORGE_SEC_USER_AGENT" not in os.environ:
        os.environ["QUANTFORGE_SEC_USER_AGENT"] = f"{B.APP_NAME} {B.CONTACT_EMAIL}"
    return universe()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_search(query: str) -> list[dict[str, Any]]:
    from quantforge.data import search_tickers
    return search_tickers(query, 8)


def _label(sym: str, uni: dict[str, str]) -> str:
    return f"{sym} — {uni[sym]}" if sym in uni else sym


def ticker_input(label: str = "Ticker", default: str = "AAPL", key: str = "ticker") -> str:
    """Searchable ticker box: type the first letters of a symbol **or** a company name.

    Suggestions come from a curated list, the SEC list of US companies (when configured)
    and live Yahoo search for anything else (any exchange, crypto, FX, futures).
    """
    uni = cached_universe()
    current = st.session_state.get(key, default).upper()
    options = list(dict.fromkeys([_label(current, uni)] + [_label(s, uni) for s in uni]))
    choice = st.selectbox(label, options, index=0, accept_new_options=True, key=f"{key}_sel",
                          placeholder="Type a symbol or a company name…",
                          help="Start typing: e.g. 'AP' → AAPL, 'tesla' → TSLA. Any Yahoo symbol "
                               "works (MC.PA, BTC-USD, ^GSPC, EURUSD=X…).")
    choice = (choice or current).strip()
    if choice in options:
        sym = choice.split(" — ")[0].strip().upper()
    else:
        hits = cached_search(choice)
        exact = [h for h in hits if h["symbol"].upper() == choice.upper()]
        if exact or not hits:
            sym = choice.upper()
        else:
            labels = [f"{h['symbol']} — {h['name']} ({h['type']}, {h['exchange']})".strip()
                      for h in hits]
            pick = st.radio(f"Matches for “{choice}”", labels, key=f"{key}_hits")
            sym = pick.split(" — ")[0].strip().upper()
    st.session_state[key] = sym
    return sym


def tickers_input(default: str = "AAPL, MSFT, NVDA, JPM, XOM, JNJ",
                  key: str = "tickers") -> list[str]:
    """Multi-ticker picker with autocomplete; any typed symbol is accepted."""
    uni = cached_universe()
    current = st.session_state.get(key, default)
    cur = [t.strip().upper() for t in current.replace(";", ",").split(",") if t.strip()]
    options = list(dict.fromkeys([_label(t, uni) for t in cur] + [_label(s, uni) for s in uni]))
    chosen = st.multiselect("Tickers", options, default=[_label(t, uni) for t in cur],
                            accept_new_options=True, key=f"{key}_ms",
                            placeholder="Type symbols or company names…",
                            help="Start typing to search. Any Yahoo symbol is accepted.")
    syms = [c.split(" — ")[0].strip().upper() for c in chosen]
    st.session_state[key] = ", ".join(syms)
    return syms


PRESETS = {"1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10, "20Y": 20, "Max": None}


def date_range(years: int = 5, key: str = "dates") -> tuple[date, date]:
    """Start/end pickers with one-click presets. "Max" asks the source for everything it has
    (back to the 1960s–1990s for many US stocks)."""
    default = next((k for k, v in PRESETS.items() if v == years), "Custom")
    preset = st.segmented_control("Period", [*PRESETS, "Custom"], default=default,
                                  key=f"{key}_preset")
    c1, c2 = st.columns(2)
    end = c2.date_input("End", value=date.today(), key=f"{key}_end")
    if preset in PRESETS:
        y = PRESETS[preset]
        start_default = date(1970, 1, 1) if y is None else end - timedelta(days=int(365.25 * y))
        start = c1.date_input("Start", value=start_default, min_value=date(1950, 1, 1),
                              key=f"{key}_start_{preset}", disabled=True)
    else:
        start = c1.date_input("Start", value=end - timedelta(days=int(365.25 * years)),
                              min_value=date(1950, 1, 1), key=f"{key}_start")
    if start >= end:
        st.error("Start must be before end")
        st.stop()
    return start, end


def pct(x: float, d: int = 2) -> str:
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{d}f}%"
