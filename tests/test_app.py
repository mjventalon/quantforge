"""Smoke tests: every dashboard page runs end to end without raising.

The provider is replaced by a *test double* that serves fixture data, so the pages
can be exercised offline in CI. The real app has no such provider.
"""

import importlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from quantforge.data import DataProvider, FredProvider  # noqa: E402
from quantforge.pricing import bs_price  # noqa: E402

APP = Path(__file__).parents[1] / "src" / "quantforge" / "app"


class FixtureProvider(DataProvider):
    name = "yahoo"

    def _fetch_history(self, ticker, start, end):
        seed = sum(map(ord, ticker))
        idx = pd.bdate_range("1990-01-02", end)
        rng = np.random.default_rng(seed)
        common = np.random.default_rng(0).standard_normal(len(idx))
        r = 0.0003 + 0.008 * common + 0.01 * rng.standard_normal(len(idx))
        c = 50 * np.exp(np.cumsum(r))
        o = c * np.exp(0.002 * rng.standard_normal(len(idx)))
        return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01,
                             "low": np.minimum(o, c) * 0.99, "close": c, "adj_close": c,
                             "volume": 1e6}, index=idx)

    def _fetch_expiries(self, ticker):
        return [(date.today() + timedelta(days=d)).isoformat() for d in (9, 30, 65, 120, 250)]

    def _fetch_option_chain(self, ticker, expiry):
        s = float(self._fetch_history(ticker, date.today(), date.today())["close"].iloc[-1])
        exps = [expiry] if expiry is not None else [pd.Timestamp(e) for e in
                                                     self._fetch_expiries(ticker)]
        rows = []
        for e in exps:
            t = max((e - pd.Timestamp(date.today())).days, 1) / 365
            for k in np.round(np.linspace(0.7, 1.3, 25) * s, 2):
                iv = 0.25 - 0.1 * np.log(k / s)
                for typ in ("call", "put"):
                    p = bs_price(s, k, t, 0.04, iv, typ)
                    rows.append(dict(contract=f"{typ}{k}", expiry=e, strike=k, type=typ,
                                     bid=p * 0.98, ask=p * 1.02 + 0.01, last=p, volume=1,
                                     open_interest=1, implied_vol=iv))
        return pd.DataFrame(rows)

    def _fetch_fundamentals(self, ticker):
        return {"name": ticker, "market_cap": 5e10, "short_term_debt": 4e10,
                "long_term_debt": 1e11, "total_assets": 2.6e11, "total_liabilities": 2.2e11,
                "working_capital": 2e10, "retained_earnings": 3e10, "ebit": 6e9,
                "revenue": 1.7e11}

    def _fetch_intraday(self, ticker, period, interval):
        if interval in ("1d", "1wk"):
            h = self._fetch_history(ticker, date.today() - timedelta(days=3650), date.today())
            return h if interval == "1d" else h.resample("W-FRI").last().dropna()
        step = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}[interval]
        days = 5 if period == "5d" else 1
        idx = pd.DatetimeIndex([d + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(minutes=m)
                                for d in pd.bdate_range(end=date.today(), periods=days)
                                for m in range(0, 390, step)])
        rng = np.random.default_rng(sum(map(ord, ticker)))
        c = 100 * np.exp(np.cumsum(0.0008 * rng.standard_normal(len(idx))))
        return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
                             "volume": 1e4}, index=idx)


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr("quantforge.app.common.make_provider", lambda *a, **k: FixtureProvider())
    monkeypatch.setattr(FredProvider, "risk_free_rate", lambda self, tenor="3M", as_of=None: 0.043)
    monkeypatch.setattr(FredProvider, "yield_curve", lambda self, as_of=None: pd.Series(
        {0.25: 0.043, 1.0: 0.041, 2.0: 0.039, 10.0: 0.042, 30.0: 0.045}))
    monkeypatch.setattr(FredProvider, "inflation_yoy",
                        lambda self, as_of=None: (0.029, pd.Timestamp("2026-09-01")))
    monkeypatch.setenv("HOME", str(tmp_path))
    uni = importlib.import_module("quantforge.data.universe")
    monkeypatch.setattr(uni, "sec_universe", lambda *a, **k: {})
    yf = pytest.importorskip("yfinance")

    def no_network(*a, **k):
        raise ConnectionError("offline test")
    monkeypatch.setattr(yf, "Search", no_network)


from quantforge.app.navigation import SECTIONS  # noqa: E402

PAGES = [f for items in SECTIONS.values() for f, *_ in items]


def test_navigation_matches_files():
    on_disk = sorted(p.name for p in (APP / "pages").glob("*.py"))
    assert sorted(PAGES) == on_disk


def _open(page: str, timeout: int = 240) -> AppTest:
    """Run the real entry point (router + sidebar) and navigate to ``page``."""
    at = AppTest.from_file(str(APP / "app.py"), default_timeout=timeout)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    if page != "00_Home.py":
        at.switch_page(f"pages/{page}").run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = _open(page)
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_backtester_interactions():
    at = _open("09_Backtester.py", 300)
    at.button[0].click().run()            # parameter search
    assert not at.exception, [e.message for e in at.exception]
    assert any("unseen test data" in i.value for i in at.info)
    at.segmented_control[0].set_value("Walk-forward portfolio").run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.dataframe) >= 1


def test_portfolio_factor_and_bl_buttons():
    at = _open("07_Portfolio.py", 300)
    at.button[0].click().run()            # load real market caps
    assert not at.exception, [e.message for e in at.exception]


def test_market_pulse_watchlist_and_options_oi():
    at = _open("02_Market_pulse.py")
    at.radio[0].set_value("My watchlist").run()
    assert not at.exception, [e.message for e in at.exception]
    at = _open("04_Options_pricer.py")
    assert any("Expected move" in m.label for m in at.metric)


def test_academy_quiz_to_certificate():
    from quantforge.academy import load_curriculum
    ch = load_curriculum()[0]
    at = _open("16_Academy.py", 300)
    for i, q in enumerate(ch.quiz):
        at.radio(key=f"q_{ch.id}_{i}").set_value(q.answer)
    at.button(key="FormSubmitter:quiz_1-Submit answers").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("Passed" in s.value for s in at.success)
    at.text_input(key="name_field").input("Ada Lovelace")
    at.button(key="save_name").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("Ada Lovelace" in m.value for m in at.markdown)
    assert any(c.value.startswith("QF-01-") for c in at.code)
    # the name can be changed afterwards
    at.button(key="change_name").click().run()
    at.text_input(key="name_field").input("Grace Hopper")
    at.button(key="save_name").click().run()
    assert any("Grace Hopper" in m.value for m in at.markdown)


def test_academy_exercise_grading(monkeypatch):
    monkeypatch.setenv("QUANTFORGE_ALLOW_CODE_EXECUTION", "1")
    from quantforge.academy.exercises import load_exercises
    ex = next(e for e in load_exercises() if e.id == "py_cagr")
    at = _open("22_Code_lab.py", 300)
    at.text_area(key=f"lab_{ex.id}_code").input(ex.solution)
    at.button(key=f"lab_{ex.id}_run").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("All 3 tests pass" in s.value for s in at.success)


def test_verify_page_accepts_valid_id():
    from quantforge.academy import make_certificate_id
    cid = make_certificate_id("Ada Lovelace", 3)
    at = _open("17_Verify.py")
    at.text_input[0].input(cid)
    at.text_input[1].input("ada  lovelace")
    at.button[0].click().run()
    assert any("Valid" in s.value for s in at.success)
    at.text_input[1].input("Someone Else")
    at.button[0].click().run()
    assert any("Not valid" in e.value for e in at.error)


def test_paper_trading_account_and_order():
    at = _open("23_Paper_trading.py", 300)
    assert any("Open your paper trading account" in m.value for m in at.markdown)
    at.button(key="pt_open").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any(m.label == "Equity" and m.value == "$1.000M" for m in at.metric)
    assert not at.error, [e.value for e in at.error]
    at.number_input(key="pt_qty").set_value(10).run()
    at.button(key="pt_submit").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert any("accepted" in s.value for s in at.success)
    # saved on disk: a new session with the same wallet sees the order
    from quantforge.paper import load_wallet
    wid = at.session_state["pt_wallet"]
    assert load_wallet(wid)[0].open_orders()[0].qty == 10


def test_paper_trading_every_widget_renders():
    from quantforge.app.paper_widgets import WIDGETS
    at = _open("23_Paper_trading.py", 300)
    at.button(key="pt_open").click().run()
    at.multiselect(key="pt_widgets_0").set_value(list(WIDGETS)).run()
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    at.button(key="pt_inv_go").click().run()            # model portfolio plan
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    at.button(key="pt_inv_place").click().run()
    assert any("orders sent" in s.value for s in at.success)


def test_advanced_models_calibration():
    at = _open("24_Advanced_models.py", 400)
    btn = [b for b in at.button if "Calibrate" in b.label]
    if not btn:
        pytest.skip("fixture has too few expiries")
    btn[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert any("Heston" in m.value for m in at.markdown), [i.value for i in at.info]


def test_live_market_long_history():
    at = _open("01_Live_market.py")
    next(s for s in at.selectbox if s.label == "Range").set_value("All history · weekly").run()
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
