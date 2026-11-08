"""Tests for v0.3: regimes, distribution surfaces, Strategy Lab, ticker search, Academy,
certificates and coding exercises. Simulated data is used only here, to test the maths."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from quantforge.academy import (
    LEVELS,
    PASS_MARK,
    certificate_pdf,
    load_curriculum,
    make_certificate_id,
    sign_progress,
    verify_certificate,
    verify_progress,
)
from quantforge.academy.exercises import (
    cpp_compiler,
    cpp_source,
    load_exercises,
    python_harness,
    run_exercise,
)
from quantforge.backtest import STRATEGIES
from quantforge.backtest.lab import (
    StrategySpec,
    diversity_report,
    export_strategy_code,
    fold_analysis,
    greedy_portfolio,
    run_lab,
    trade_monte_carlo,
)
from quantforge.timeseries.distribution import rolling_density_surface, rolling_moments
from quantforge.timeseries.regimes import fit_hmm


def _regime_series(n=3000, seed=3):
    rng = np.random.default_rng(seed)
    state, out, states = 0, [], []
    for _ in range(n):
        if rng.random() < (0.01 if state == 0 else 0.04):
            state = 1 - state
        out.append(rng.normal(0.0006, 0.007) if state == 0 else rng.normal(-0.001, 0.025))
        states.append(state)
    idx = pd.bdate_range("2010-01-01", periods=n)
    return pd.Series(out, index=idx), np.array(states)


# ------------------------------------------------------------------ regimes
def test_hmm_recovers_regimes():
    r, truth = _regime_series()
    res = fit_hmm(r, 2, n_starts=4)
    assert res.converged
    vol = np.sqrt(res.variances)
    assert vol[0] == pytest.approx(0.007, rel=0.1) and vol[1] == pytest.approx(0.025, rel=0.1)
    acc = (res.viterbi.to_numpy() == truth).mean()
    assert acc > 0.93
    np.testing.assert_allclose(res.transition.sum(axis=1), 1, atol=1e-12)
    np.testing.assert_allclose(res.filtered.sum(axis=1), 1, atol=1e-9)
    assert res.stationary.sum() == pytest.approx(1)


def test_hmm_matches_hmmlearn_loglik():
    hmm = pytest.importorskip("hmmlearn.hmm")
    r, _ = _regime_series(1500, 9)
    ours = fit_hmm(r, 2, n_starts=4)
    m = hmm.GaussianHMM(2, covariance_type="diag", n_iter=500, tol=1e-9, random_state=0)
    m.fit(r.to_numpy().reshape(-1, 1))
    assert ours.loglik >= m.score(r.to_numpy().reshape(-1, 1)) - 1e-3


def test_filtered_probabilities_are_causal():
    r, _ = _regime_series(1200, 5)
    full = fit_hmm(r, 2, n_starts=2)
    from quantforge.timeseries.regimes import hmm_forward
    a1, *_ = hmm_forward(r.to_numpy()[:600], full.means, full.variances, full.transition,
                         full.initial)
    a2, *_ = hmm_forward(r.to_numpy(), full.means, full.variances, full.transition, full.initial)
    np.testing.assert_allclose(a1, a2[:600], atol=1e-12)   # future data does not leak back


# ------------------------------------------------------------------ distributions
def test_density_surface_integrates_to_one():
    r, _ = _regime_series(800, 1)
    dates, grid, dens = rolling_density_surface(r, window=63, step=10, grid_points=120,
                                                clip_quantile=0.9999)
    assert dens.shape == (len(dates), len(grid))
    mass = dens.sum(axis=1) * (grid[1] - grid[0])
    assert np.all(mass > 0.97) and np.all(mass < 1.01)
    assert dates[0] == r.index[62]                # first slice uses only the first 63 days


def test_rolling_moments():
    r, _ = _regime_series(500, 2)
    m = rolling_moments(r, window=100)
    last = r.iloc[-100:]
    assert m["volatility"].iloc[-1] == pytest.approx(last.std() * np.sqrt(252), rel=1e-9)
    assert m["skewness"].iloc[-1] == pytest.approx(last.skew(), rel=1e-9)


# ------------------------------------------------------------------ Strategy Lab
@pytest.fixture(scope="module")
def lab():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2012-01-02", periods=1500)
    px = pd.DataFrame({t: 100 * np.exp(np.cumsum(0.0003 + 0.012 * rng.standard_normal(1500)))
                       for t in ("AAA", "BBB", "CCC")}, index=idx)
    names = list(STRATEGIES)[:3]
    specs = [StrategySpec(s, t) for s in names for t in px.columns]
    return run_lab(px, specs, cost_bps=5), px


def test_lab_runs_every_spec(lab):
    run, _ = lab
    assert run.returns.shape[1] == len(run.specs)
    assert np.isfinite(run.returns.to_numpy()).all()


def test_diversity_report_and_greedy(lab):
    run, _ = lab
    rep = diversity_report(run.returns)
    assert 0 <= rep["score"] <= 100 and rep["grade"] in "ABCD"
    c = rep["corr"].to_numpy()
    assert rep["mean_corr"] == pytest.approx(c[np.triu_indices(len(c), 1)].mean())
    pick = greedy_portfolio(run.returns, size=3, objective="diversity", min_sharpe=None)
    assert len(pick) == 3 and len(set(pick)) == 3


def test_folds_and_trade_monte_carlo(lab):
    run, _ = lab
    col = run.returns.columns[0]
    folds = fold_analysis(run.returns[col], 3)
    total = (1 + run.returns[col].dropna()).prod() - 1
    assert (1 + folds["return"]).prod() - 1 == pytest.approx(total, rel=1e-9)
    trades = np.random.default_rng(1).normal(0.01, 0.05, 60)
    mc = trade_monte_carlo(trades, n_sims=2000, seed=0)
    exp_final = 10_000 * np.prod(1 + trades)
    assert mc["final"].min() <= exp_final <= mc["final"].max()
    assert 0 <= mc["p_profit"] <= 1 and mc["p95_max_drawdown"] <= 0


def test_exported_code_compiles():
    spec = StrategySpec(next(iter(STRATEGIES)), "SPY")
    code = export_strategy_code(spec)
    compile(code, "export.py", "exec")
    assert "SPY" in code


# ------------------------------------------------------------------ ticker search
def test_search_falls_back_to_local_universe(monkeypatch):
    import importlib
    uni = importlib.import_module("quantforge.data.universe")
    monkeypatch.setattr(uni, "sec_universe", lambda *a, **k: {})
    yf = pytest.importorskip("yfinance")

    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(yf, "Search", boom)
    res = uni.search_tickers("AAP")
    assert res and res[0]["symbol"].startswith("AAP")
    assert any(r["symbol"] == "AAPL" for r in uni.search_tickers("apple"))


# ------------------------------------------------------------------ Academy
def test_curriculum_structure():
    chs = load_curriculum()
    assert [c.id for c in chs] == list(range(1, len(chs) + 1)) and len(chs) == 23
    assert set(c.level for c in chs) == set(LEVELS)
    from quantforge.app.academy_widgets import WIDGETS
    for c in chs:
        assert len(c.quiz) >= 5, c.id
        assert c.sources, c.id
        for kind, name in c.blocks():
            if kind == "widget":
                assert name in WIDGETS, (c.id, name)
        for s in c.sources:
            assert not s.url or s.url.startswith("https://"), s.url


def test_certificates_verify_and_reject_tampering():
    cid = make_certificate_id("Ada  Lovelace", 13, date(2026, 11, 7))
    assert verify_certificate(cid, "ada lovelace").valid
    assert not verify_certificate(cid, "Ada Byron").valid
    bad = cid[:-1] + ("0" if cid[-1] != "0" else "1")
    assert not verify_certificate(bad, "Ada Lovelace").valid
    assert not verify_certificate("QF-xx", "Ada").valid
    pdf = certificate_pdf("Ada Lovelace", "Chapter 13", "Level 4", cid, 0.9, date(2026, 11, 7),
                          pass_mark=PASS_MARK)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 2000


def test_progress_file_is_sealed():
    prog = {"passed": {"1": {"score": 1.0, "date": "2026-11-07"}}, "read": [1, 2],
            "exercises": ["py_cagr"], "name": "Ada Lovelace"}
    sealed = json.loads(json.dumps(sign_progress(prog)))
    assert verify_progress(sealed)["name"] == "Ada Lovelace"
    forged = dict(sealed, passed={str(i): {"score": 1.0, "date": "2026-11-07"}
                                  for i in range(1, 24)})
    assert verify_progress(forged) is None
    assert verify_progress({"passed": {}}) is None


# ------------------------------------------------------------------ coding exercises
def test_exercise_bank():
    exs = load_exercises()
    assert len(exs) >= 20
    assert {e.language for e in exs} == {"python", "cpp"}
    chapters = {c.id for c in load_curriculum()}
    assert all(e.chapter in chapters for e in exs)


@pytest.mark.parametrize("ex", [e for e in load_exercises() if e.language == "python"],
                         ids=lambda e: e.id)
def test_python_solutions_pass_and_starters_fail(ex):
    assert all(r.ok for r in run_exercise(ex, ex.solution, force=True))
    assert not all(r.ok for r in run_exercise(ex, ex.starter, force=True))


@pytest.mark.parametrize("ex", [e for e in load_exercises() if e.language == "cpp"],
                         ids=lambda e: e.id)
def test_cpp_solutions_pass_and_starters_fail(ex):
    if cpp_compiler() is None:
        pytest.skip("no C++ compiler")
    res = run_exercise(ex, ex.solution, force=True)
    assert all(r.ok for r in res), [r for r in res if not r.ok]
    assert not all(r.ok for r in run_exercise(ex, ex.starter, force=True))


def test_execution_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("QUANTFORGE_ALLOW_CODE_EXECUTION", raising=False)
    ex = load_exercises()[0]
    with pytest.raises(PermissionError):
        run_exercise(ex, ex.solution)


def test_grader_reports_errors_cleanly():
    ex = next(e for e in load_exercises() if e.id == "py_cagr")
    res = run_exercise(ex, "def cagr(:\n", force=True)
    assert len(res) == 1 and not res[0].ok and "SyntaxError" in res[0].message
    res = run_exercise(ex, "while True:\n    pass\n", timeout=2, force=True)
    assert not res[0].ok and "longer" in res[0].message
    assert "LEARNER_CODE" in python_harness(ex)
    cpp = next(e for e in load_exercises() if e.language == "cpp")
    assert "int main()" in cpp_source(cpp, cpp.starter)


def test_empty_secret_means_development_mode(monkeypatch):
    from quantforge.academy import is_development_mode
    monkeypatch.setenv("QUANTFORGE_CERT_SECRET", "   ")
    assert is_development_mode()
    dev = make_certificate_id("Ada", 1, date(2026, 1, 1))
    monkeypatch.delenv("QUANTFORGE_CERT_SECRET")
    assert make_certificate_id("Ada", 1, date(2026, 1, 1)) == dev
    monkeypatch.setenv("QUANTFORGE_CERT_SECRET", "s3cret")
    assert not is_development_mode() and make_certificate_id("Ada", 1, date(2026, 1, 1)) != dev
