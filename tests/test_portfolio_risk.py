"""Portfolio and risk tests. Random returns are generated here only as test inputs
with known statistical properties; the library itself never generates market data."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from quantforge.portfolio import (
    black_litterman,
    capm_regression,
    efficient_frontier,
    estimate_inputs,
    implied_equilibrium_returns,
    ledoit_wolf_shrinkage,
    max_drawdown,
    max_sharpe,
    min_variance,
    performance_summary,
    risk_contributions,
    risk_parity,
    security_market_line,
)
from quantforge.risk import (
    HISTORICAL_SCENARIOS,
    Scenario,
    backtest_var,
    basel_zone,
    cornish_fisher_var,
    historical_stress_test,
    historical_var,
    hypothetical_stress_test,
    monte_carlo_var,
    parametric_var,
    portfolio_var_decomposition,
    rolling_var,
    student_t_var,
    var_report,
)

MU = np.array([0.08, 0.10, 0.12, 0.07])
VOL = np.array([0.15, 0.20, 0.25, 0.12])
CORR = np.array([[1, .3, .2, .1], [.3, 1, .4, .2], [.2, .4, 1, .3], [.1, .2, .3, 1]])
COV = np.outer(VOL, VOL) * CORR
NAMES = ["A", "B", "C", "D"]


@pytest.fixture
def returns():
    rng = np.random.default_rng(0)
    x = rng.multivariate_normal(MU / 252, COV / 252, size=3000)
    return pd.DataFrame(x, columns=NAMES, index=pd.bdate_range("2014-01-01", periods=3000))


# ------------------------------------------------------------------ optimization
def test_min_variance_matches_closed_form():
    inv = np.linalg.inv(COV)
    w_exact = inv @ np.ones(4) / (np.ones(4) @ inv @ np.ones(4))
    res = min_variance(MU, COV, bounds=(-5, 5))
    np.testing.assert_allclose(res.weights.values, w_exact, atol=1e-6)


def test_max_sharpe_matches_tangency():
    rf = 0.03
    w = np.linalg.inv(COV) @ (MU - rf)
    w /= w.sum()
    res = max_sharpe(MU, COV, rf, bounds=(-5, 5))
    np.testing.assert_allclose(res.weights.values, w, atol=1e-5)
    assert res.sharpe == pytest.approx((w @ MU - rf) / np.sqrt(w @ COV @ w), rel=1e-6)


def test_long_only_bounds_respected():
    res = max_sharpe(MU, COV, 0.02, bounds=(0.0, 0.4))
    assert res.weights.min() >= -1e-9 and res.weights.max() <= 0.4 + 1e-9
    assert res.weights.sum() == pytest.approx(1)


def test_efficient_frontier_is_monotone():
    f = efficient_frontier(MU, COV, 25)
    assert np.all(np.diff(f["return"]) > 0)
    assert np.all(np.diff(f["volatility"]) > -1e-9)
    assert f["volatility"].iloc[0] == pytest.approx(min_variance(MU, COV).volatility, rel=1e-5)


def test_risk_parity_equal_contributions():
    res = risk_parity(COV)
    rc = risk_contributions(res.weights, COV)
    np.testing.assert_allclose(rc.values, 0.25, atol=1e-6)


def test_ledoit_wolf_matches_sklearn(returns):
    sk = pytest.importorskip("sklearn.covariance")
    ours, delta = ledoit_wolf_shrinkage(returns.values)
    lw = sk.LedoitWolf().fit(returns.values)
    n = len(returns)
    np.testing.assert_allclose(ours * (n - 1) / n, lw.covariance_, rtol=1e-6)
    assert delta == pytest.approx(lw.shrinkage_, rel=1e-6)


def test_estimate_inputs_recovers_parameters(returns):
    mu, cov = estimate_inputs(returns, method="historical")
    np.testing.assert_allclose(np.sqrt(np.diag(cov)), VOL, rtol=0.05)
    assert list(mu.index) == NAMES


def test_black_litterman_no_view_confidence_returns_equilibrium():
    w_mkt = np.array([0.25] * 4)
    pi = implied_equilibrium_returns(COV, w_mkt).values
    mu_bl, _ = black_litterman(COV, w_mkt, np.array([[1, 0, 0, 0]]), [0.5], [1e-6])
    np.testing.assert_allclose(mu_bl.values, pi, atol=1e-4)
    mu_bl2, _ = black_litterman(COV, w_mkt, np.array([[1, 0, 0, 0]]), [0.5], [0.999999])
    assert mu_bl2.values[0] == pytest.approx(0.5, abs=1e-3)


# ------------------------------------------------------------------ CAPM & performance
def test_capm_recovers_beta_and_alpha():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2015-01-01", periods=5000)
    m = pd.Series(rng.normal(0.0004, 0.01, 5000), idx)
    a = 0.0002 + 1.3 * m + rng.normal(0, 0.005, 5000)
    res = capm_regression(a, m)
    assert res.beta == pytest.approx(1.3, abs=0.02)
    assert res.alpha == pytest.approx(0.0002 * 252, abs=0.03)
    sm = pytest.importorskip("statsmodels.api")
    ols = sm.OLS(a.values, sm.add_constant(m.values)).fit()
    assert res.beta_se == pytest.approx(ols.bse[1], rel=1e-8)
    assert res.r_squared == pytest.approx(ols.rsquared, rel=1e-10)


def test_sml_and_performance(returns):
    sml = security_market_line(returns[["A", "B"]], returns["C"])
    assert set(sml.columns) >= {"beta", "alpha", "capm_return"}
    perf = performance_summary(returns)
    assert perf.loc["Volatility"].values == pytest.approx(VOL, rel=0.06)
    assert max_drawdown(pd.Series([0.1, -0.5, 0.2])) == pytest.approx(-0.5)


# ------------------------------------------------------------------ VaR
@pytest.fixture
def normal_returns():
    return np.random.default_rng(5).normal(0.0005, 0.012, 200_000)


def test_parametric_var_formula(normal_returns):
    r = normal_returns
    est = parametric_var(r, 0.99, 10)
    mu, sd = r.mean() * 10, r.std(ddof=1) * np.sqrt(10)
    assert est.var == pytest.approx(-(mu + stats.norm.ppf(0.01) * sd), rel=1e-12)
    assert est.es > est.var


def test_all_methods_agree_on_normal_data(normal_returns):
    r = normal_returns
    ref = parametric_var(r, 0.99)
    for f in (historical_var, student_t_var, cornish_fisher_var):
        e = f(r, 0.99)
        assert e.var == pytest.approx(ref.var, rel=0.03), f.__name__
        assert e.es == pytest.approx(ref.es, rel=0.05), f.__name__
    mc = monte_carlo_var(r, confidence=0.99, seed=0)
    assert mc.var == pytest.approx(ref.var, rel=0.03)


def test_historical_var_is_empirical_quantile():
    r = np.linspace(-0.05, 0.05, 1001)
    e = historical_var(r, 0.95)
    assert e.var == pytest.approx(0.045, abs=1e-3)
    assert e.es >= e.var


def test_student_t_fatter_than_normal():
    r = stats.t.rvs(3, size=50_000, random_state=2) * 0.01
    assert student_t_var(r, 0.995).var > parametric_var(r, 0.995).var


def test_var_report_and_decomposition(returns):
    rep = var_report(returns["A"], 0.99, 1, 1e6)
    assert {"VaR", "ES", "VaR ($)"} <= set(rep.columns) and len(rep) == 5
    w = np.array([0.4, 0.3, 0.2, 0.1])
    dec = portfolio_var_decomposition(returns, w, 0.99)
    sig = np.sqrt(w @ returns.cov().values @ w)
    assert dec["component_var"].sum() == pytest.approx(stats.norm.ppf(0.99) * sig, rel=1e-10)


def test_monte_carlo_portfolio_var(returns):
    w = np.array([0.25] * 4)
    mc = monte_carlo_var(returns, w, 0.99, n_sims=200_000, seed=1)
    port = returns.values @ w
    assert mc.var == pytest.approx(parametric_var(port, 0.99).var, rel=0.05)


# ------------------------------------------------------------------ backtests
def test_kupiec_known_values():
    idx = pd.RangeIndex(1000)
    var = pd.Series(1.0, idx)
    r = pd.Series(0.0, idx)
    r.iloc[::100] = -2.0  # exactly 10 exceptions = expected at 99%
    bt = backtest_var(r, var, 0.99)
    assert bt.n_exceptions == 10 and bt.kupiec_lr == pytest.approx(0.0, abs=1e-10)
    r.iloc[:40] = -2.0
    assert backtest_var(r, var, 0.99).kupiec_pvalue < 0.001


def test_christoffersen_detects_clustering():
    idx = pd.RangeIndex(1000)
    var = pd.Series(1.0, idx)
    r = pd.Series(0.0, idx)
    r.iloc[500:510] = -2.0  # 10 exceptions all in a row
    bt = backtest_var(r, var, 0.99)
    assert bt.kupiec_pvalue > 0.9 and bt.christoffersen_pvalue < 0.01


def test_basel_zones():
    assert basel_zone(2) == "green"
    assert basel_zone(6) == "yellow"
    assert basel_zone(12) == "red"


def test_rolling_var_is_out_of_sample(normal_returns):
    s = pd.Series(normal_returns[:3000])
    v = rolling_var(s, 250, 0.99)
    assert v.iloc[:250].isna().all()
    bt = backtest_var(s, v, 0.99)
    assert 0.003 < bt.exception_rate < 0.02


# ------------------------------------------------------------------ stress
def test_historical_stress_uses_actual_moves_and_flags_proxy():
    idx = pd.bdate_range("2020-01-01", "2020-04-30")
    bench = pd.Series(100.0, idx)
    bench.loc["2020-02-19":"2020-03-23"] = np.linspace(100, 66, len(bench.loc["2020-02-19":
                                                                               "2020-03-23"]))
    bench.loc["2020-03-24":] = 66
    a = bench * 2  # moves exactly like the benchmark
    b = pd.Series(np.nan, idx)  # no history: must be proxied
    b.loc["2020-04-01":] = 50
    prices = pd.DataFrame({"A": a, "B": b})
    covid = [s for s in HISTORICAL_SCENARIOS if s.name == "COVID-19 crash"]
    res = historical_stress_test(prices, {"A": 0.5, "B": 0.5}, bench, covid, 1e6)
    row = res.loc["COVID-19 crash"]
    assert row["ret_A"] == pytest.approx(-0.34, abs=1e-9)
    assert row["proxied_assets"] == "B"
    assert row["pnl"] == pytest.approx(row["portfolio_return"] * 1e6)


def test_stress_skips_windows_without_data():
    idx = pd.bdate_range("2021-01-01", periods=300)
    px = pd.DataFrame({"A": np.linspace(100, 120, 300)}, idx)
    res = historical_stress_test(px, {"A": 1.0}, None,
                                 [Scenario("Old", "1990-01-01", "1990-02-01", "")])
    assert res.empty


def test_hypothetical_stress_beta_scaling(returns):
    res = hypothetical_stress_test(returns[["A", "B"]], {"A": 1.0, "B": 0.0}, returns["C"],
                                   market_shocks=(-0.1,))
    beta = returns["A"].cov(returns["C"]) / returns["C"].var()
    assert res.loc[-0.1, "portfolio_return"] == pytest.approx(beta * -0.1)
