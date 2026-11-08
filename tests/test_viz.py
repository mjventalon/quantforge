"""Every chart builds a valid Plotly figure from model outputs."""

import numpy as np
import pandas as pd
import pytest

go = pytest.importorskip("plotly.graph_objects")

from quantforge import viz  # noqa: E402
from quantforge.credit import calibration_table, logistic_regression, roc_curve  # noqa: E402
from quantforge.portfolio import efficient_frontier, max_sharpe, min_variance  # noqa: E402
from quantforge.pricing import bs_greeks, simulate_gbm_paths  # noqa: E402
from quantforge.pricing.strategies import PRESETS, Strategy  # noqa: E402
from quantforge.risk import historical_var, rolling_var  # noqa: E402
from quantforge.timeseries import acf, fit_arma, fit_garch, pacf, volatility_cone  # noqa: E402

rng = np.random.default_rng(0)
IDX = pd.bdate_range("2018-01-01", periods=1500)
RETS = pd.DataFrame(rng.normal(3e-4, 0.01, (1500, 3)), IDX, columns=list("ABC"))
PX = 100 * (1 + RETS).cumprod()


def ok(fig):
    assert isinstance(fig, go.Figure) and len(fig.data) > 0
    fig.to_json()  # must serialize


def test_market_and_options_charts():
    ohlc = pd.DataFrame({"open": PX["A"], "high": PX["A"] * 1.01, "low": PX["A"] * 0.99,
                         "close": PX["A"], "volume": 1e6})
    ok(viz.candlestick(ohlc, "A", source="test"))
    s = Strategy(PRESETS["Iron condor"](100))
    grid = np.linspace(60, 140, 200)
    ok(viz.payoff_diagram(grid, s.profit_at_expiry(grid, 100, 0.2, 0.03, 0.25),
                          s.value(grid, 0.2, 0.03, 0.25)["price"], 100,
                          s.breakevens(100, 0.2, 0.03, 0.25)))
    g = bs_greeks(grid, 100, 0.5, 0.03, 0.2)
    ok(viz.greek_profile(grid, {k: np.asarray(getattr(g, k)) for k in
                                ("price", "delta", "gamma", "vega", "theta", "rho")}, 100))
    S, T = np.meshgrid(grid[::10], np.linspace(0.05, 1, 10))
    ok(viz.greek_surface(grid[::10], np.linspace(0.05, 1, 10),
                         np.asarray(bs_greeks(S, 100, T, 0.03, 0.2).gamma), "gamma"))
    ok(viz.mc_paths_fan(simulate_gbm_paths(100, 1, 0.03, 0.2, 500, 50, seed=1), 1, 100))
    ok(viz.convergence_chart([10, 20], [5.1, 5.0], 5.02))


def test_portfolio_charts():
    mu, cov = RETS.mean() * 252, RETS.cov() * 252
    f = efficient_frontier(mu, cov, 10)
    ms, mv = max_sharpe(mu, cov, 0.01), min_variance(mu, cov)
    ok(viz.efficient_frontier_chart(f, mu, pd.Series(np.sqrt(np.diag(cov)), mu.index),
                                    {"Max Sharpe": (ms.volatility, ms.expected_return),
                                     "Min variance": (mv.volatility, mv.expected_return)},
                                    0.01, (np.array([0.2]), np.array([0.05]))))
    ok(viz.weights_chart(pd.DataFrame({"x": ms.weights})))
    ok(viz.correlation_heatmap(RETS))
    ok(viz.cumulative_returns(RETS))
    ok(viz.drawdown_chart(RETS["A"]))
    sml = pd.DataFrame({"beta": [0.8, 1.2], "realized_return": [0.05, 0.1],
                        "capm_return": [0.06, 0.08], "alpha": [-0.01, 0.02]}, index=["A", "B"])
    ok(viz.sml_chart(sml, 0.07, 0.02))
    ok(viz.rolling_beta_chart(RETS["A"], RETS["B"]))


def test_risk_ts_credit_charts():
    e = historical_var(RETS["A"], 0.99)
    ok(viz.var_distribution(RETS["A"], e.var, e.es, 0.99))
    ok(viz.var_backtest_chart(RETS["A"], rolling_var(RETS["A"])))
    stress = pd.DataFrame({"portfolio_return": [-0.3, 0.05], "benchmark_return": [-0.34, 0.02],
                           "proxied_assets": ["", "B"]}, index=["Crash", "Rally"])
    ok(viz.stress_chart(stress))
    g = fit_garch(RETS["A"])
    ok(viz.garch_chart(RETS["A"], g.conditional_vol, forecast=g.forecast(20)))
    a = fit_arma(RETS["A"] * 100, 1, 0)
    ok(viz.forecast_chart(RETS["A"] * 100, a.forecast(10)))
    ok(viz.acf_chart(acf(RETS["A"], 10), pacf(RETS["A"], 10), 1500))
    ok(viz.vol_cone_chart(volatility_cone(PX["A"]), {21: 0.2}))
    X = pd.DataFrame({"x": rng.normal(size=2000)})
    y = (rng.random(2000) < 1 / (1 + np.exp(-(X["x"] - 2)))).astype(int)
    p = logistic_regression(y, X).predict_proba(X)
    fpr, tpr, _ = roc_curve(y, p)
    ok(viz.roc_chart(fpr, tpr, 0.8))
    ok(viz.calibration_chart(calibration_table(y, p, 5)))
    ok(viz.yield_curve_chart(pd.Series({0.25: 0.043, 2.0: 0.039, 10.0: 0.042})))
