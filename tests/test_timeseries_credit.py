"""Time series & credit tests. Inputs are simulated from known processes so the
estimators can be checked against the true parameters and reference libraries."""

import numpy as np
import pandas as pd
import pytest

from quantforge.credit import (
    altman_z_score,
    auc_score,
    calibration_table,
    classification_report,
    ks_statistic,
    logistic_regression,
    merton_model,
    ols,
    roc_curve,
    scorecard_points,
    woe_iv,
)
from quantforge.timeseries import (
    acf,
    adf_test,
    fit_arma,
    fit_garch,
    garman_klass_vol,
    ljung_box,
    pacf,
    parkinson_vol,
    select_arma_order,
    volatility_cone,
    yang_zhang_vol,
)


def simulate_gjr(n=3000, w=2e-6, a=0.05, b=0.88, g=0.08, nu=6, seed=3):
    rng = np.random.default_rng(seed)
    e = np.zeros(n)
    s2 = np.full(n, w / (1 - a - b - g / 2))
    z = rng.standard_t(nu, n) / np.sqrt(nu / (nu - 2))
    for t in range(1, n):
        s2[t] = w + (a + g * (e[t - 1] < 0)) * e[t - 1] ** 2 + b * s2[t - 1]
        e[t] = np.sqrt(s2[t]) * z[t]
    return pd.Series(e + 3e-4, index=pd.bdate_range("2010-01-01", periods=n))


def simulate_arma(n=2000, seed=4):
    rng = np.random.default_rng(seed)
    y, eps = np.zeros(n), rng.standard_normal(n)
    for t in range(2, n):
        y[t] = 0.5 + 0.6 * y[t - 1] - 0.2 * y[t - 2] + eps[t] + 0.3 * eps[t - 1]
    return y


# ------------------------------------------------------------------ GARCH
@pytest.mark.parametrize("asym,dist", [(False, "normal"), (True, "t")])
def test_garch_matches_arch_package(asym, dist):
    arch = pytest.importorskip("arch")
    r = simulate_gjr()
    ours = fit_garch(r, dist, asym)
    ref = arch.arch_model(r * 100, mean="Constant", vol="GARCH", p=1, o=int(asym), q=1,
                          dist="t" if dist == "t" else "normal").fit(disp="off")
    assert ours.params["alpha"] == pytest.approx(ref.params["alpha[1]"], abs=3e-3)
    assert ours.params["beta"] == pytest.approx(ref.params["beta[1]"], abs=3e-3)
    if asym:
        assert ours.params["gamma"] == pytest.approx(ref.params["gamma[1]"], abs=3e-3)
        assert ours.params["nu"] == pytest.approx(ref.params["nu"], abs=0.1)
    assert ours.loglik == pytest.approx(ref.loglikelihood + len(r) * np.log(100), abs=2.0)
    assert ours.std_errors["beta"] == pytest.approx(ref.std_err["beta[1]"], rel=0.5)


def test_garch_forecast_converges_to_long_run():
    g = fit_garch(simulate_gjr(), "t", True)
    fc = g.forecast(5000)
    assert fc["vol_annualized"].iloc[-1] == pytest.approx(g.long_run_vol, rel=1e-3)
    assert 0 < g.persistence < 1 and g.half_life > 0


def test_garch_needs_enough_data():
    with pytest.raises(ValueError):
        fit_garch(np.zeros(50))


# ------------------------------------------------------------------ ARMA
def test_arma_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.tsa.arima.model")
    y = simulate_arma()
    ours = fit_arma(y, 2, 1)
    ref = sm.ARIMA(y, order=(2, 0, 1)).fit()
    np.testing.assert_allclose(ours.ar, ref.arparams, atol=5e-3)
    np.testing.assert_allclose(ours.ma, ref.maparams, atol=5e-3)
    fc = ours.forecast(3)
    np.testing.assert_allclose(fc["mean"], ref.get_forecast(3).predicted_mean, atol=5e-3)
    np.testing.assert_allclose(fc["std_error"], ref.get_forecast(3).se_mean, rtol=5e-3)
    assert ours.is_stationary


def test_order_selection_finds_true_order():
    rng = np.random.default_rng(9)
    eps = rng.standard_normal(5000)
    y = np.zeros(5000)
    for t in range(1, 5000):  # ARMA(1,1) with a strong MA term: no short AR mimics it
        y[t] = 0.5 * y[t - 1] + eps[t] + 0.7 * eps[t - 1]
    best, table = select_arma_order(y, 3, 2, "bic")
    assert best.order == (1, 1)
    assert len(table) == 12


def test_acf_pacf_ar1():
    rng = np.random.default_rng(0)
    y = np.zeros(20000)
    for t in range(1, y.size):
        y[t] = 0.7 * y[t - 1] + rng.standard_normal()
    a, p = acf(y, 5), pacf(y, 5)
    np.testing.assert_allclose(a[1:4], [0.7, 0.49, 0.343], atol=0.02)
    assert p[1] == pytest.approx(0.7, abs=0.02) and abs(p[2]) < 0.03


def test_adf_and_ljung_box():
    rng = np.random.default_rng(1)
    rw = np.cumsum(rng.standard_normal(1500))
    wn = rng.standard_normal(1500)
    assert not adf_test(rw)["stationary_5pct"]
    assert adf_test(wn)["stationary_5pct"]
    assert ljung_box(wn, 10)[1] > 0.01
    assert ljung_box(simulate_arma(), 10)[1] < 1e-6


# ------------------------------------------------------------------ realized vol
def test_range_estimators_recover_true_vol():
    rng = np.random.default_rng(2)
    n, steps, sigma = 2000, 390, 0.3
    dt = 1 / 252 / steps
    z = rng.standard_normal((n, steps))
    day = np.cumsum(-0.5 * sigma**2 * dt + sigma * np.sqrt(dt) * z, axis=1)  # starts at 0
    close_log = np.cumsum(day[:, -1])
    open_log = np.r_[0.0, close_log[:-1]]
    df = pd.DataFrame({"open": np.exp(open_log),
                       "high": np.exp(open_log + np.maximum(day.max(1), 0)),
                       "low": np.exp(open_log + np.minimum(day.min(1), 0)),
                       "close": np.exp(close_log)},
                      index=pd.bdate_range("2015-01-01", periods=n))
    for f in (parkinson_vol, garman_klass_vol, yang_zhang_vol):
        assert f(df, 252).dropna().mean() == pytest.approx(sigma, rel=0.07), f.__name__
    cone = volatility_cone(df["close"])
    assert (cone["min"] <= cone["median"]).all() and (cone["median"] <= cone["max"]).all()


# ------------------------------------------------------------------ regression
@pytest.fixture
def credit_data():
    rng = np.random.default_rng(7)
    n = 20000
    X = pd.DataFrame({"dti": rng.normal(0, 1, n), "fico": rng.normal(0, 1, n),
                      "util": rng.normal(0, 1, n)})
    eta = -2.5 + 0.8 * X["dti"] - 1.2 * X["fico"] + 0.3 * X["util"]
    y = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(int)
    return X, y


def test_logit_matches_statsmodels(credit_data):
    sm = pytest.importorskip("statsmodels.api")
    X, y = credit_data
    ours = logistic_regression(y, X)
    ref = sm.Logit(y, sm.add_constant(X)).fit(disp=0)
    np.testing.assert_allclose(ours.params.values, ref.params.values, atol=1e-8)
    np.testing.assert_allclose(ours.std_errors.values, ref.bse.values, rtol=1e-6)
    assert ours.loglik == pytest.approx(ref.llf, rel=1e-10)
    assert ours.pseudo_r2 == pytest.approx(ref.prsquared, rel=1e-8)
    np.testing.assert_allclose(ours.params.values, [-2.5, 0.8, -1.2, 0.3], atol=0.1)


def test_ols_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(3)
    X = rng.normal(size=(500, 2))
    y = 1 + X @ [2.0, -1.0] + rng.normal(size=500) * (1 + np.abs(X[:, 0]))
    for cov in ("nonrobust", "HC1"):
        ours = ols(y, X, cov_type=cov)
        ref = sm.OLS(y, sm.add_constant(X)).fit(cov_type=cov)
        np.testing.assert_allclose(ours.params.values, ref.params, atol=1e-10)
        np.testing.assert_allclose(ours.std_errors.values, ref.bse, rtol=1e-8)
        assert ours.r_squared == pytest.approx(ref.rsquared)


def test_scoring_metrics(credit_data):
    X, y = credit_data
    fit = logistic_regression(y, X)
    p = fit.predict_proba(X)
    sk = pytest.importorskip("sklearn.metrics")
    assert auc_score(y, p) == pytest.approx(sk.roc_auc_score(y, p), abs=1e-12)
    fpr, tpr, _ = roc_curve(y, p)
    sk_fpr, sk_tpr, _ = sk.roc_curve(y, p, drop_intermediate=False)
    assert ks_statistic(y, p) == pytest.approx(np.max(sk_tpr - sk_fpr), abs=1e-12)
    rep = classification_report(y, p, 0.2)
    assert rep.gini == pytest.approx(2 * rep.auc - 1)
    assert rep.confusion.values.sum() == len(y)
    cal = calibration_table(y, p)
    assert len(cal) == 10 and (cal["observed_dr"].diff().dropna() > -0.02).all()
    tbl, iv = woe_iv(X["fico"], y)
    assert iv > 0.3  # strong predictor by construction
    assert scorecard_points(np.log(50)) == pytest.approx(600)
    assert scorecard_points(np.log(100)) == pytest.approx(620)


def test_auc_simple_cases():
    assert auc_score([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc_score([0, 1], [0.5, 0.5]) == 0.5


# ------------------------------------------------------------------ structural
def test_merton_solution_reprices_equity():
    from scipy.stats import norm

    res = merton_model(3e9, 0.45, 5e9, 0.04, 1.0)
    v, sv, d = res.asset_value, res.asset_vol, 5e9
    d1 = (np.log(v / d) + (0.04 + 0.5 * sv**2)) / sv
    d2 = d1 - sv
    assert v * norm.cdf(d1) - d * np.exp(-0.04) * norm.cdf(d2) == pytest.approx(3e9, rel=1e-8)
    assert norm.cdf(d1) * sv * v == pytest.approx(0.45 * 3e9, rel=1e-8)
    assert res.default_probability == pytest.approx(norm.cdf(-d2))
    assert res.converged and res.credit_spread > 0


def test_merton_riskier_with_more_leverage():
    low = merton_model(10e9, 0.3, 2e9, 0.04)
    high = merton_model(10e9, 0.3, 20e9, 0.04)
    assert high.default_probability > low.default_probability
    assert high.distance_to_default < low.distance_to_default


def test_altman_zones():
    z = altman_z_score(0.2, 0.3, 0.15, 2.0, 1.2, 1.0, 0.5)
    assert z["z_score"] == pytest.approx(1.2 * .2 + 1.4 * .3 + 3.3 * .15 + 0.6 * 4 + 1.2)
    assert z["zone"] == "safe"
    assert altman_z_score(-0.1, -0.2, -0.05, 0.1, 0.5, 1.0, 0.9)["zone"] == "distress"
