"""Tests for v0.2 modules: indicators, cointegration, backtesting, wealth simulation,
factor regression, option-chain analytics. Inputs with known properties are
simulated here only to validate the estimators."""

import numpy as np
import pandas as pd
import pytest

from quantforge.backtest import (
    STRATEGIES,
    grid_search,
    run_backtest,
    sma_crossover,
    time_series_momentum,
    walk_forward_portfolio,
)
from quantforge.portfolio import (
    build_factor_returns,
    factor_regression,
    monthly_portfolio_returns,
    period_returns,
    simulate_wealth,
)
from quantforge.pricing import bs_price, expected_move, max_pain, prob_in_the_money, put_call_ratios
from quantforge.timeseries import (
    atr,
    bollinger_bands,
    ema,
    engle_granger,
    macd,
    rolling_hedge_ratio,
    rsi,
    sma,
    spread_half_life,
)

IDX = pd.bdate_range("2015-01-01", periods=2000)


def gbm(seed=0, mu=0.08, vol=0.2, n=2000):
    r = np.random.default_rng(seed).normal(mu / 252, vol / np.sqrt(252), n)
    return pd.Series(100 * np.exp(np.cumsum(r)), index=IDX[:n])


# ------------------------------------------------------------------ indicators
def test_indicators_basic_properties():
    px = gbm()
    assert sma(px, 20).iloc[19] == pytest.approx(px.iloc[:20].mean())
    assert ema(px, 10).notna().sum() == len(px) - 9
    r = rsi(px)
    assert r.dropna().between(0, 100).all()
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert rsi(up).iloc[-1] == 100.0
    m = macd(px)
    assert np.allclose((m["macd"] - m["signal"]).dropna(), m["histogram"].dropna())
    bb = bollinger_bands(px)
    bb = bb.dropna()
    assert (bb["upper"] >= bb["lower"]).all()
    ohlc = pd.DataFrame({"high": px * 1.01, "low": px * 0.99, "close": px})
    assert (atr(ohlc).dropna() > 0).all()


def test_rsi_matches_reference_definition():
    px = gbm(3).iloc[:300]
    d = px.diff()
    g, l = d.clip(lower=0), -d.clip(upper=0)
    ag = g.iloc[1:15].mean()  # Wilder seed differs from EWMA seed; compare late values
    ref = 100 - 100 / (1 + g.ewm(alpha=1 / 14, adjust=False).mean() /
                       l.ewm(alpha=1 / 14, adjust=False).mean())
    assert rsi(px).iloc[-1] == pytest.approx(ref.iloc[-1], rel=1e-10)
    assert ag >= 0


# ------------------------------------------------------------------ cointegration
def _coint_pair(seed=1, n=1500):
    rng = np.random.default_rng(seed)
    x = np.exp(np.cumsum(rng.normal(0, 0.01, n)) + 4)
    u = np.zeros(n)
    for t in range(1, n):
        u[t] = 0.9 * u[t - 1] + rng.normal(0, 0.01)
    y = np.exp(0.2 + 1.3 * np.log(x) + u)
    return pd.Series(y, IDX[:n]), pd.Series(x, IDX[:n])


def test_engle_granger_matches_statsmodels():
    st = pytest.importorskip("statsmodels.tsa.stattools")
    y, x = _coint_pair()
    ours = engle_granger(y, x)
    t, p, crit = st.coint(np.log(y), np.log(x))
    assert ours.statistic == pytest.approx(t, rel=1e-8)
    assert ours.p_value == pytest.approx(p, rel=1e-6)
    np.testing.assert_allclose(list(ours.critical_values.values()), crit, atol=0.02)
    assert ours.cointegrated_5pct
    assert ours.hedge_ratio == pytest.approx(1.3, abs=0.1)
    assert ours.half_life == pytest.approx(np.log(0.5) / np.log(0.9), rel=0.35)


def test_independent_random_walks_not_cointegrated():
    rng = np.random.default_rng(7)
    a = pd.Series(np.exp(np.cumsum(rng.normal(0, .01, 1500))), IDX[:1500])
    b = pd.Series(np.exp(np.cumsum(rng.normal(0, .01, 1500))), IDX[:1500])
    assert not engle_granger(a, b).cointegrated_5pct
    assert rolling_hedge_ratio(a, b, 100).iloc[:99].isna().all()
    assert spread_half_life(pd.Series(np.cumsum(rng.normal(size=500)))) > 20


# ------------------------------------------------------------------ backtest engine
def test_no_lookahead_and_costs():
    px = pd.Series([100, 110, 99, 120, 120.0], index=IDX[:5])
    pos = pd.Series([1, 1, 0, 0, 0.0], index=px.index)
    res = run_backtest(px, pos, cost_bps=0)
    # position decided at close 0 earns return 0->1 (+10%), held into 1->2 (-10%), flat after
    np.testing.assert_allclose(res.returns.values, [0, 0.10, -0.10, 0, 0])
    res_c = run_backtest(px, pos, cost_bps=100)
    np.testing.assert_allclose(res_c.returns.values, [-0.01, 0.10, -0.10 - 0.01, 0, 0])
    assert len(res.trades) == 2


def test_buy_and_hold_equals_asset():
    px = gbm(4)
    res = run_backtest(px, STRATEGIES["Buy & hold"][0](px), cost_bps=0)
    assert res.equity.iloc[-1] == pytest.approx(px.iloc[-1] / px.iloc[0], rel=1e-12)
    assert res.metrics.loc["Total return", "Strategy"] == pytest.approx(
        res.metrics.loc["Total return", "Buy & hold"], rel=1e-12)


def test_future_information_cannot_help():
    """A strategy that 'knows' tomorrow's return only profits if the engine leaks the future."""
    px = gbm(5)
    cheat = np.sign(px.pct_change().shift(-1)).fillna(0)  # perfect foresight signal
    honest = np.sign(px.pct_change()).fillna(0)           # same idea using today's info
    assert run_backtest(px, cheat, 0).equity.iloc[-1] > 100   # foresight is (correctly) huge
    assert run_backtest(px, honest, 0).equity.iloc[-1] < 5    # no edge on a random walk


def test_strategies_run_and_grid_search_split():
    px = gbm(6)
    for name, (fn, params) in STRATEGIES.items():
        pos = fn(px, **{k: v[0] for k, v in params.items()})
        assert pos.index.equals(px.index), name
        assert np.isfinite(run_backtest(px, pos).equity.iloc[-1])
    table, best = grid_search(px, sma_crossover, {"fast": [10, 20], "slow": [50, 100]})
    assert len(table) == 4 and set(best) == {"fast", "slow"}
    assert "test_Sharpe" in table and table.attrs["split_date"] in px.index
    with pytest.raises(ValueError):
        sma_crossover(px, 50, 20)
    assert time_series_momentum(px, 252).iloc[:252].eq(0).all()


def test_walk_forward_uses_only_past():
    rng = np.random.default_rng(8)
    prices = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(3e-4, 0.01, (700, 3)), axis=0)),
                          index=IDX[:700], columns=list("ABC"))
    rets, w, metrics = walk_forward_portfolio(prices, lookback=252, cost_bps=0)
    assert rets.index[0] > prices.index[252]
    assert set(metrics.columns) == {"Equal weight", "Minimum variance", "Maximum Sharpe",
                                    "Risk parity"}
    first = w["Minimum variance"].index[0]
    # weights at the first rebalance must equal those computed from data up to that day only
    from quantforge.portfolio import estimate_inputs, min_variance
    window = prices.pct_change().dropna().loc[:first].iloc[-252:]
    mu, cov = estimate_inputs(window)
    np.testing.assert_allclose(w["Minimum variance"].iloc[0], min_variance(mu, cov).weights,
                               atol=1e-8)


# ------------------------------------------------------------------ wealth simulation
def test_wealth_simulation_deterministic_case():
    sim = simulate_wealth(np.full(60, 0.01), initial=1000, monthly_contribution=100, years=2,
                          n_sims=50, seed=0)
    expected = 1000.0
    for _ in range(24):
        expected = expected * 1.01 + 100
    np.testing.assert_allclose(sim.final, expected)
    assert sim.contributions[-1] == 1000 + 2400


def test_wealth_simulation_inflation_goal_and_portfolio_returns():
    r = np.random.default_rng(1).normal(0.006, 0.04, 240)
    nominal = simulate_wealth(r, 10_000, 0, 10, 2000, seed=3)
    real = simulate_wealth(r, 10_000, 0, 10, 2000, annual_inflation=0.03, goal=15_000, seed=3)
    assert np.median(real.final) < np.median(nominal.final)
    assert 0 <= real.prob_goal <= 1 and real.summary()["median_max_drawdown"] < 0
    px = pd.DataFrame({"A": gbm(1), "B": gbm(2)})
    m = monthly_portfolio_returns(px, {"A": 3, "B": 1})
    ma = px.resample("ME").last().pct_change().dropna()
    np.testing.assert_allclose(m, 0.75 * ma["A"] + 0.25 * ma["B"])
    with pytest.raises(ValueError):
        simulate_wealth(r[:10])


# ------------------------------------------------------------------ factors & periods
def test_factor_regression_recovers_loadings():
    rng = np.random.default_rng(2)
    etf = pd.DataFrame(rng.normal(3e-4, 0.01, (2000, 5)), index=IDX,
                       columns=["SPY", "IWM", "IWD", "IWF", "IEF"])
    f = build_factor_returns(etf, factors=["Market", "Size", "Value", "Rates"])
    y = 0.0001 + 1.1 * f["Market"] + 0.5 * f["Size"] - 0.3 * f["Value"] + rng.normal(
        0, 0.002, 2000)
    fr = factor_regression(y, f)
    res = fr.table
    assert res.loc["Market", "coef"] == pytest.approx(1.1, abs=0.02)
    assert res.loc["Size", "coef"] == pytest.approx(0.5, abs=0.02)
    assert res.loc["Value", "coef"] == pytest.approx(-0.3, abs=0.02)
    assert abs(res.loc["Rates", "t"]) < 3
    assert fr.r_squared > 0.9
    assert fr.variance_share.sum() == pytest.approx(fr.r_squared, rel=0.02)


def test_period_returns():
    idx = pd.bdate_range("2023-01-02", "2025-06-30")
    px = pd.DataFrame({"X": np.linspace(100, 200, len(idx))}, index=idx)
    t = period_returns(px)
    assert t.loc["X", "1D"] == pytest.approx(px["X"].iloc[-1] / px["X"].iloc[-2] - 1)
    ytd_base = px.loc[:"2024-12-31", "X"].iloc[-1]
    assert t.loc["X", "YTD"] == pytest.approx(px["X"].iloc[-1] / ytd_base - 1)


# ------------------------------------------------------------------ option analytics
def _chain():
    rows = []
    for k in (90, 95, 100, 105, 110):
        for typ, oi in (("call", 1000 if k >= 100 else 200), ("put", 1500 if k <= 100 else 100)):
            p = bs_price(100, k, 30 / 365, 0.04, 0.25, typ)
            rows.append(dict(strike=float(k), type=typ, mid=p, volume=oi / 10, open_interest=oi))
    return pd.DataFrame(rows)


def test_expected_move_and_probabilities():
    ch = _chain()
    em = expected_move(ch, 100, 30 / 365, atm_iv=0.25)
    c, p = (bs_price(100, 100, 30 / 365, 0.04, 0.25, t) for t in ("call", "put"))
    assert em["straddle"] == pytest.approx(c + p)
    assert em["one_sigma"] == pytest.approx(100 * 0.25 * np.sqrt(30 / 365))
    pc = prob_in_the_money(100, 105, 0.5, 0.03, 0.2, "call")
    pp = prob_in_the_money(100, 105, 0.5, 0.03, 0.2, "put")
    assert pc + pp == pytest.approx(1.0)
    r = put_call_ratios(ch)
    assert r["oi_pcr"] == pytest.approx(ch[ch.type == "put"].open_interest.sum() /
                                        ch[ch.type == "call"].open_interest.sum())


def test_max_pain_brute_force():
    ch = _chain()
    k, curve = max_pain(ch)
    brute = {s: sum(max(s - r.strike, 0) * r.open_interest for r in ch[ch.type == "call"].itertuples())
             + sum(max(r.strike - s, 0) * r.open_interest for r in ch[ch.type == "put"].itertuples())
             for s in ch.strike.unique()}
    assert k == min(brute, key=brute.get)
    assert curve.loc[k] == pytest.approx(brute[k])


def test_pairs_backtest_profits_on_cointegrated_pair_and_is_causal():
    from quantforge.backtest import pairs_backtest
    y, x = _coint_pair(seed=11, n=1500)
    res = pairs_backtest(y, x, window=120, entry=1.5, exit=0.25, cost_bps=0)
    assert res.metrics.loc["Sharpe", "Pairs strategy"] > 1.0
    assert res.metrics.loc["Trades", "Pairs strategy"] > 5
    # changing future prices must not change past positions
    y2 = y.copy()
    y2.iloc[1000:] *= 1.5
    res2 = pairs_backtest(y2, x, window=120, entry=1.5, exit=0.25, cost_bps=0)
    pd.testing.assert_series_equal(res.position.iloc[:1000], res2.position.iloc[:1000])
    with pytest.raises(ValueError):
        pairs_backtest(y, x, entry=1, exit=2)
