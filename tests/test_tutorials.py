"""Execute every Python block in docs/tutorials so the documentation never goes stale.

Runs offline: the market data provider is swapped for the fixture test double from
``test_app`` (tutorial code itself is unchanged)."""

import re
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402
from test_app import FixtureProvider  # noqa: E402

from quantforge.data import FredProvider  # noqa: E402

DOCS = Path(__file__).parents[1] / "docs" / "tutorials"
TUTORIALS = sorted(DOCS.glob("[0-9]*.md"))


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    import quantforge.data.market as market

    monkeypatch.setitem(market.PROVIDERS, "yahoo", FixtureProvider)
    monkeypatch.setattr(market, "YahooProvider", FixtureProvider)
    monkeypatch.setattr(FredProvider, "risk_free_rate", lambda self, tenor="3M", as_of=None: 0.043)
    monkeypatch.setattr(FredProvider, "yield_curve", lambda self, as_of=None: pd.Series(
        {1 / 12: 0.044, 0.25: 0.043, 1.0: 0.041, 2.0: 0.039, 10.0: 0.042, 30.0: 0.045}))
    monkeypatch.setattr(go.Figure, "show", lambda self, *a, **k: None)
    monkeypatch.setattr(FredProvider, "inflation_yoy",
                        lambda self, as_of=None: (0.029, pd.Timestamp("2026-09-01")))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("QUANTFORGE_PROVIDER", raising=False)
    for k in ("POLYGON_API_KEY", "FMP_API_KEY", "ALPHAVANTAGE_API_KEY"):
        monkeypatch.delenv(k, raising=False)


@pytest.mark.parametrize("path", TUTORIALS, ids=lambda p: p.stem)
def test_tutorial_code_runs(path):
    blocks = re.findall(r"```python\n(.*?)```", path.read_text(), flags=re.S)
    ns: dict = {}
    for block in blocks:
        if "read_csv(" in block:  # needs the reader's own loan file
            continue
        exec(compile(block, f"{path.name}", "exec"), ns)  # noqa: S102
