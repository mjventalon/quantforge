"""C++ engine: status, build, accuracy check and speed benchmark on real inputs."""

import time
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from quantforge import native
from quantforge.app.common import (
    cached_chain,
    chart,
    guard,
    history,
    page_setup,
    risk_free,
    source_note,
    ticker_input,
)
from quantforge.pricing import implied_volatility
from quantforge.viz.theme import apply as apply_theme


def iv_or_nan(price: float, spot: float, strike: float, maturity: float, rate: float,
              option_type: str) -> float:
    """Python implied vol with the C++ engine's convention: NaN for an unsolvable quote.

    Real chains contain quotes outside the no-arbitrage bounds (stale prices, or dividends,
    which this comparison ignores); one of them must not stop the whole comparison.
    """
    try:
        return float(implied_volatility(price, spot, strike, maturity, rate, option_type))
    except ValueError:
        return float("nan")

HOW_TO = """1. Check the **status** box. If the engine is not built, press **Build the C++ engine**
   (needs a C++ compiler: on a Mac run `xcode-select --install` once).
2. Pick a ticker: the inputs (spot, 1-year historical volatility, 3-month Treasury rate) are real.
3. Press **Run benchmark**: the same calculations run in C++ and in NumPy. The table shows both
   results, their difference (should be ~0) and the speed-up.
4. **Live option chain**: computes the implied volatility of every quote in the real chain in
   C++ and in Python, and checks they agree."""

page_setup("C++ engine", "⚙️", HOW_TO)

st_ = native.status()
with st.container(border=True):
    c = st.columns([1, 3])
    c[0].metric("Engine", "C++ ready" if st_.available else "Python only")
    c[1].markdown(f"**Compiler:** `{st_.compiler}`  \n**Library:** `{st_.library}`  \n"
                  f"**Status:** {st_.message}")
    if not st_.available:
        if st.button("🔨 Build the C++ engine", type="primary"):
            with st.spinner("Compiling C++17 sources…"):
                try:
                    native.build()
                    st.success("Built. The fast path is now active.")
                    st.rerun()
                except native.NativeError as exc:
                    st.error(str(exc))
        st.stop()

st.markdown("""The C++17 engine (`src/quantforge/native/cpp`, header-only, no dependencies) implements
Black-Scholes and Greeks, safeguarded Newton implied volatility, Leisen-Reimer and CRR trees, and
multithreaded Monte-Carlo with antithetic and control variates. Every function is tested against
the Python reference to ~1e-10.""")

c1, c2, c3 = st.columns(3)
with c1:
    ticker = ticker_input(default="SPY", key="engine_ticker")
n_opts = c2.select_slider("Options to price", [10_000, 100_000, 1_000_000], 100_000,
                          format_func=lambda x: f"{x:,}")
n_paths = c3.select_slider("Monte-Carlo paths", [100_000, 1_000_000, 4_000_000], 1_000_000,
                           format_func=lambda x: f"{x:,}")

hist = history(ticker, date.today().replace(year=date.today().year - 1), date.today())
spot = float(hist["close"].iloc[-1])
vol = float(np.log(hist["close"]).diff().dropna().std() * np.sqrt(252))
r = risk_free("3M")
m = st.columns(3)
m[0].metric(f"{ticker} spot", f"{spot:,.2f}")
m[1].metric("1-year historical vol", f"{vol:.1%}")
m[2].metric("3-month Treasury", f"{r:.2%}")
st.caption(source_note("Strike = spot (at the money), maturity 1 year."))

if st.button("▶️ Run benchmark", type="primary"):
    with st.spinner("Running both engines…"):
        rows = native.benchmark(spot, spot, 1.0, r, vol, n_options=n_opts, n_paths=n_paths,
                                tree_steps=2001)
    df = pd.DataFrame(rows)
    show = pd.DataFrame({
        "Task": df["task"], "Python result": df["python"], "C++ result": df["cpp"],
        "Difference": df["max_abs_diff"], "Python (ms)": df["python_s"] * 1e3,
        "C++ (ms)": df["cpp_s"] * 1e3, "Speed-up": df["speedup"]})
    st.dataframe(show.style.format({"Python result": "{:.6f}", "C++ result": "{:.6f}",
                                    "Difference": "{:.2e}", "Python (ms)": "{:.1f}",
                                    "C++ (ms)": "{:.1f}", "Speed-up": "×{:.1f}"}),
                 hide_index=True, width="stretch")
    st.caption("Monte-Carlo results differ only by random sampling (different generators); "
               f"{rows[2].get('note', '')}. Timings depend on your CPU cores.")
    fig = go.Figure([go.Bar(name="Python / NumPy", x=df["task"], y=df["python_s"] * 1e3),
                     go.Bar(name="C++", x=df["task"], y=df["cpp_s"] * 1e3)])
    fig.update_layout(barmode="group", yaxis_title="milliseconds (lower is faster)")
    chart(apply_theme(fig, "Run time on identical inputs"), key="engine_bench")

st.subheader("Live option chain — implied volatility of every quote")
if st.button("Compute the chain's implied vols in both engines"):
    chain = guard(cached_chain, st.session_state.get("provider", "yahoo"), ticker, None,
                  what="option chain")
    chain = chain[(chain["bid"] > 0) & (chain["ask"] > chain["bid"])].copy()
    chain["mid"] = 0.5 * (chain["bid"] + chain["ask"])
    t = ((pd.to_datetime(chain["expiry"]) - pd.Timestamp(date.today())).dt.days
         .clip(lower=1) / 365).to_numpy()
    res = {}
    for typ in ("call", "put"):
        mask = (chain["type"] == typ).to_numpy()
        args = (chain["mid"].to_numpy()[mask], spot, chain["strike"].to_numpy()[mask], t[mask],
                r)
        t0 = time.perf_counter()
        cpp = native.implied_vol(*args, typ)
        tc = time.perf_counter() - t0
        t0 = time.perf_counter()
        py = np.array([iv_or_nan(p, spot, k, tt, r, typ)
                       for p, k, tt in zip(args[0], args[2], args[3])], dtype=float)
        tp = time.perf_counter() - t0
        res[typ] = (cpp, py, tc, tp)
    rows = []
    for typ, (cpp, py, tc, tp) in res.items():
        both = np.isfinite(cpp) & np.isfinite(py)
        rows.append({"Type": typ, "Quotes": len(cpp), "Solved": int(both.sum()),
                     "Outside bounds": int((~np.isfinite(py)).sum()),
                     "Max |C++ − Python|": float(np.abs(cpp[both] - py[both]).max())
                     if both.any() else np.nan,
                     "C++ (ms)": tc * 1e3, "Python (ms)": tp * 1e3,
                     "Speed-up": tp / max(tc, 1e-9)})
    st.dataframe(pd.DataFrame(rows).style.format({"Max |C++ − Python|": "{:.1e}",
                                                  "C++ (ms)": "{:.2f}", "Python (ms)": "{:.1f}",
                                                  "Speed-up": "×{:.0f}"}),
                 hide_index=True, width="stretch")
    st.caption(source_note(f"{len(chain)} quotes with a valid bid/ask across "
                           f"{chain['expiry'].nunique()} expiries; mid prices; "
                           "no dividend adjustment. Quotes outside the no-arbitrage bounds "
                           "(stale prices, or dividends) have no implied vol and are skipped "
                           "by both engines."))
