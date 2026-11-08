import pandas as pd
import streamlit as st

from quantforge.app.common import (
    chart,
    date_range,
    download_csv,
    history,
    page_setup,
    prices,
    risk_free,
    source_note,
    ticker_input,
    tickers_input,
)
from quantforge.backtest import (
    OPTIMIZERS,
    STRATEGIES,
    grid_search,
    run_backtest,
    walk_forward_portfolio,
)
from quantforge.viz import (
    backtest_chart,
    cumulative_returns,
    param_heatmap,
    walk_forward_weights_chart,
)

HOW_TO = """**Strategy on one asset**
1. Pick a ticker and a **strategy** (trend following, momentum, mean reversion…), then tune its
   parameters with the sliders.
2. Signals are computed at each close and traded at that close, so the strategy only earns
   **the next day's** move: no peeking into the future. Costs are charged on every trade.
3. Compare with **buy & hold** in the table: return, Sharpe, max drawdown.
4. **Parameter search** tries every combination on the first 60% of the data and shows how it
   did on the last 40% it never saw. A big drop = the parameters were overfitted.

**Walk-forward portfolio** re-optimizes a portfolio every month using only past data — the
honest way to test the optimizers from the Portfolio page."""

page_setup("Backtester", "🔁", HOW_TO)
mode = st.segmented_control("Mode", ["Strategy on one asset", "Walk-forward portfolio"],
                            default="Strategy on one asset")

if mode == "Walk-forward portfolio":
    tickers = tickers_input(default="SPY, TLT, GLD, EFA, VNQ", key="wf_tickers")
    c = st.columns(4)
    lookback = c[0].select_slider("Estimation window", [63, 126, 252, 504], 252,
                                  help="Days of past returns used at each rebalance.")
    rebal = c[1].selectbox("Rebalance", ["ME", "QE"], format_func={"ME": "Monthly",
                                                                    "QE": "Quarterly"}.get)
    cost = c[2].number_input("Cost per trade (bps)", 0.0, 100.0, 5.0)
    max_w = c[3].slider("Max weight", 0.1, 1.0, 1.0, 0.05)
    start, end = date_range(12, "wf")
    methods = st.multiselect("Methods", list(OPTIMIZERS), list(OPTIMIZERS))
    px = prices(tickers, start, end)
    rf = risk_free("3M")
    with st.spinner("Re-optimizing at every rebalance date…"):
        rets, wh, metrics = walk_forward_portfolio(px, methods, lookback, rebal, cost,
                                                   (0.0, max_w), rf)
    st.caption(f"Out-of-sample from {rets.index[0]:%Y-%m-%d} · {source_note()}")
    chart(cumulative_returns(rets, source=source_note()), key="wf_cum")
    st.dataframe(metrics.style.format("{:.3f}"), width="stretch")
    pick = st.selectbox("Weights history of", methods)
    chart(walk_forward_weights_chart(wh[pick], pick), key="wf_w")
    download_csv(rets, "walk_forward_returns")
    st.stop()

c1, c2 = st.columns([1, 2])
with c1:
    ticker = ticker_input(default="SPY", key="bt_ticker")
with c2:
    start, end = date_range(15, "bt")
px = history(ticker, start, end)["adj_close"]

c = st.columns([2, 1, 1])
name = c[0].selectbox("Strategy", list(STRATEGIES))
cost = c[1].number_input("Cost per trade (bps)", 0.0, 100.0, 5.0,
                         help="Commission + half the bid-ask spread, per unit traded.")
allow_short = c[2].toggle("Allow short", False, help="Trend strategies only: go short instead "
                                                     "of flat.")
fn, params = STRATEGIES[name]
vals = {}
if params:
    cols = st.columns(len(params))
    for col, (p, (default, lo, hi, step)) in zip(cols, params.items()):
        vals[p] = col.slider(p, lo, hi, default, step)
kwargs = dict(vals)
if "allow_short" in fn.__code__.co_varnames:
    kwargs["allow_short"] = allow_short
try:
    pos = fn(px, **kwargs)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
rf = risk_free("3M")
res = run_backtest(px, pos, cost, rf, vals)

mt = res.metrics
m = st.columns(5)
for i, (k, f) in enumerate([("CAGR", "{:.2%}"), ("Sharpe", "{:.2f}"), ("Max drawdown", "{:.1%}"),
                            ("Volatility", "{:.1%}")]):
    m[i].metric(k, f.format(mt.loc[k, "Strategy"]),
                f"buy & hold {f.format(mt.loc[k, 'Buy & hold'])}", delta_color="off")
m[4].metric("Trades", f"{int(mt.loc['Trades', 'Strategy'])}",
            f"in market {mt.loc['Time in market', 'Strategy']:.0%}", delta_color="off")

chart(backtest_chart(px, res, f"{ticker} — {name}"), key="bt")
with st.expander("All statistics and trades"):
    st.dataframe(mt.style.format("{:.4f}"), width="stretch")
    st.dataframe(res.trades, width="stretch")
    download_csv(pd.DataFrame({"strategy": res.returns, "position": res.positions}),
                 f"{ticker}_backtest")

st.subheader("Parameter search (train / test)")
if len(params) >= 1:
    keys = list(params)[:2]
    grids = {}
    gc = st.columns(len(keys))
    for col, k in zip(gc, keys):
        default, lo, hi, step = params[k]
        n = col.slider(f"{k}: values to try", 3, 10, 6, key=f"n_{k}")
        raw = [lo + i * (hi - lo) / (n - 1) for i in range(n)]
        grids[k] = sorted({type(default)(round(v / step) * step) for v in raw})
    fixed = {k: v for k, v in kwargs.items() if k not in keys}
    if st.button("Run parameter search"):
        with st.spinner("Backtesting every combination…"):
            table, best = grid_search(px, lambda p, **kw: fn(p, **kw, **fixed), grids, cost,
                                      0.6, "Sharpe", rf)
        split = table.attrs["split_date"]
        st.caption(f"Train: start → {split:%Y-%m-%d} · Test: {split:%Y-%m-%d} → end")
        if len(keys) == 2:
            c1, c2 = st.columns(2)
            with c1:
                chart(param_heatmap(table, keys[0], keys[1], "train_Sharpe", best), key="h1")
            with c2:
                chart(param_heatmap(table, keys[0], keys[1], "test_Sharpe", best), key="h2")
        b = table.loc[(table[keys] == pd.Series(best)).all(axis=1)].iloc[0]
        st.info(f"Best on train: {best} → Sharpe {b['train_Sharpe']:.2f} on train, "
                f"**{b['test_Sharpe']:.2f} on unseen test data**.")
        shown = table.sort_values("train_Sharpe", ascending=False)
        shown.attrs = {}
        st.dataframe(shown, width="stretch", hide_index=True)
st.caption("Backtests describe the past and ignore taxes, slippage on large orders and "
           "dividends timing. Not investment advice.")
