"""Strategy Lab: many strategies on many assets, combined into one diversified book."""

import io
from itertools import product

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    chart,
    date_range,
    download_csv,
    heat,
    page_setup,
    prices,
    risk_free,
    source_note,
    tickers_input,
)
from quantforge.backtest import (
    STRATEGIES,
    StrategySpec,
    combine,
    diversity_report,
    export_strategy_code,
    fold_analysis,
    greedy_portfolio,
    grid_search,
    run_lab,
    trade_monte_carlo,
)
from quantforge.viz import (
    diversity_heatmap,
    folds_chart,
    lab_equity_chart,
    param_surface_3d,
    trade_mc_chart,
)

HOW_TO = """**The idea:** one strategy is fragile; several *genuinely different* strategies combined
are much more robust. Different tickers or names do not guarantee different behaviour — only the
correlation of their daily profits does.

1. Pick assets and strategies, plus how many parameter variants to try. The Lab backtests every
   combination on real prices (with costs, no look-ahead).
2. **Auto-build** picks, one at a time, the strategy that most improves the book's
   **diversity score** (or Sharpe) — not just the top performers, which are often near-clones.
3. Check the **heatmap** (green = diversifying, orange = unrelated, red = redundant), the
   **folds** (does it work in every period?) and the **Monte-Carlo of trades** (how much is luck?).
4. Export any strategy as a standalone Python script."""

page_setup("Strategy Lab", "🧪", HOW_TO)

tickers = tickers_input(default="SPY, QQQ, TLT, GLD, XLE, EFA", key="lab_tickers")
c = st.columns([2, 1, 1, 1])
strats = c[0].multiselect("Strategies", [s for s in STRATEGIES if s != "Buy & hold"],
                          ["SMA crossover (trend)", "Time-series momentum", "RSI mean reversion",
                           "Bollinger mean reversion"])
variants = c[1].slider("Parameter variants each", 1, 6, 3,
                       help="Evenly spaced settings around the defaults.")
cost = c[2].number_input("Cost (bps)", 0.0, 50.0, 5.0)
seed = c[3].number_input("Seed", 0, 9999, 0, help="Makes the Monte-Carlo reproducible.")
start, end = date_range(15, "lab")


def variant_params(name: str, n: int) -> list[dict]:
    _, params = STRATEGIES[name]
    if not params or n == 1:
        return [{k: v[0] for k, v in params.items()}]
    axes = {}
    for k, (default, lo, hi, step) in params.items():
        span = np.linspace(max(lo, default * 0.5), min(hi, default * 1.5), n)
        axes[k] = sorted({type(default)(round(v / step) * step) for v in span})
    combos = [dict(zip(axes, vals)) for vals in product(*axes.values())]
    rng = np.random.default_rng(len(name))
    if len(combos) > n:
        combos = [combos[i] for i in sorted(rng.choice(len(combos), n, replace=False))]
    return combos


if not tickers or not strats:
    st.info("Choose at least one ticker and one strategy.")
    st.stop()

specs = [StrategySpec(s, t, p) for s in strats for t in tickers for p in variant_params(s, variants)]
px = prices(tickers, start, end)
rf = risk_free("3M")


@st.cache_data(show_spinner="Backtesting every strategy…")
def run(spec_keys: tuple, px_json: str, cost: float, rf: float):
    p = pd.read_json(io.StringIO(px_json), orient="split")
    sp = [StrategySpec(s, t, dict(pp)) for s, t, pp in spec_keys]
    valid = []
    for x in sp:
        try:
            STRATEGIES[x.strategy][0](p[x.ticker], **x.params)
            valid.append(x)
        except ValueError:
            continue
    return run_lab(p, valid, cost, rf)


lab = run(tuple((s.strategy, s.ticker, tuple(sorted(s.params.items()))) for s in specs),
          px.to_json(orient="split", date_format="iso"), cost, rf)
st.caption(f"{len(lab.returns.columns)} strategies backtested on {len(px)} days · {source_note()}")

tab = st.tabs(["Leaderboard", "Auto-build portfolio", "Robustness", "Parameter landscape 3-D",
               "Export code"])
with tab[0]:
    mt = lab.metrics[["CAGR", "Sharpe", "Max drawdown", "Volatility", "Trades", "Win rate",
                      "Profit factor"]].sort_values("Sharpe", ascending=False)
    st.dataframe(mt.style.format({"CAGR": "{:.2%}", "Sharpe": "{:.2f}", "Max drawdown": "{:.1%}",
                                  "Volatility": "{:.1%}", "Trades": "{:.0f}", "Win rate": "{:.0%}",
                                  "Profit factor": "{:.2f}"}).apply(
        heat, subset=["Sharpe"]), width="stretch", height=420)
    download_csv(mt, "strategy_lab_leaderboard")
    st.warning("These are in-sample results over the whole period. Picking the top of this "
               "table is exactly how backtests get overfitted — use the Robustness tab.")

with tab[1]:
    c = st.columns(3)
    size = c[0].slider("Target size", 2, min(20, len(lab.returns.columns)),
                       min(8, len(lab.returns.columns)))
    objective = c[1].radio("Objective", ["diversity", "sharpe"], horizontal=True,
                           help="Diversity: least correlated set. Sharpe: best combined Sharpe.")
    min_sr = c[2].number_input("Min stand-alone Sharpe", -1.0, 2.0, 0.0, 0.1)
    try:
        chosen = greedy_portfolio(lab.returns, size, objective, min_sr)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    port, weights = combine(lab.returns[chosen], "equal_risk")
    rep = diversity_report(lab.returns[chosen])
    m = st.columns(5)
    m[0].metric("Strategies", len(chosen))
    m[1].metric("Diversity", f"{rep['score']:.0f}/100", f"Grade {rep['grade']}", delta_color="off")
    sr = port.mean() / port.std() * np.sqrt(252)
    m[2].metric("Book Sharpe", f"{sr:.2f}")
    eq = (1 + port).cumprod()
    m[3].metric("Book CAGR", f"{eq.iloc[-1] ** (252 / len(port)) - 1:.2%}")
    m[4].metric("Book max DD", f"{(eq / eq.cummax() - 1).min():.1%}")
    if rep["worst_pair"]:
        a, b, v = rep["worst_pair"]
        st.caption(f"Most similar pair: {a} ↔ {b} (ρ = {v:.2f})")
    chart(lab_equity_chart(lab.returns[chosen], port), key="lab_eq")
    chart(diversity_heatmap(rep), key="lab_heat")
    st.dataframe(pd.DataFrame({"weight (equal risk)": weights}).style.format("{:.1%}"),
                 width="stretch")
    st.session_state["lab_book"] = (chosen, port)

with tab[2]:
    target = st.selectbox("Analyse", ["Combined book"] + list(lab.returns.columns))
    if target == "Combined book" and "lab_book" in st.session_state:
        series = st.session_state["lab_book"][1]
        trades = np.concatenate([lab.trades[c] for c in st.session_state["lab_book"][0]])
    else:
        series = lab.returns[target] if target != "Combined book" else lab.returns.mean(axis=1)
        trades = lab.trades.get(target, np.concatenate(list(lab.trades.values())))
    k = st.slider("Folds", 2, 6, 3)
    chart(folds_chart(fold_analysis(series, k)), key="lab_folds")
    if len(trades) >= 5:
        mc = trade_monte_carlo(trades, 1000, 10_000, int(seed))
        chart(trade_mc_chart(mc, 10_000), key="lab_mc")
        st.caption("Each simulation redraws the realized trades in random order (with "
                   "replacement). PASS = profitable in ≥90% of simulations with a median above "
                   "the start.")
    else:
        st.info("Not enough trades for a Monte-Carlo.")

with tab[3]:
    c = st.columns(3)
    s_name = c[0].selectbox("Strategy", [s for s in strats if len(STRATEGIES[s][1]) >= 2] or strats)
    t_name = c[1].selectbox("Ticker", tickers)
    n = c[2].slider("Grid size", 4, 12, 8)
    fn, params = STRATEGIES[s_name]
    keys = list(params)[:2]
    if len(keys) < 2:
        st.info("This strategy has fewer than two parameters.")
    else:
        grid = {}
        for k_ in keys:
            d, lo, hi, step = params[k_]
            grid[k_] = sorted({type(d)(round(v / step) * step) for v in np.linspace(lo, hi, n)})
        with st.spinner("Exploring the parameter space…"):
            table, best = grid_search(px[t_name], fn, grid, cost, 0.6, "Sharpe", rf)
        which = st.radio("Show", ["train_Sharpe", "test_Sharpe"], horizontal=True)
        chart(param_surface_3d(table, keys[0], keys[1], which), key="lab_surface")
        st.caption("A robust strategy sits on a broad plateau. A lone spike that disappears in "
                   "the test surface is overfitting.")

with tab[4]:
    pick = st.selectbox("Strategy to export", list(lab.returns.columns))
    code = export_strategy_code(lab.specs[pick], start=str(start), cost_bps=cost)
    st.code(code, language="python")
    st.download_button("⬇️ Download .py", code.encode(), file_name="quantforge_strategy.py")
