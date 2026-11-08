"""Risk-free rates and the US Treasury yield curve from FRED.

Works **without** an API key through FRED's public CSV endpoint; if
``FRED_API_KEY`` is set the official JSON API is used instead.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Any

import pandas as pd

from .base import DataError, DataProvider, get_api_key

__all__ = ["FredProvider", "TREASURY_SERIES"]

#: FRED series for constant-maturity Treasury yields (percent), tenor in years.
TREASURY_SERIES: dict[str, tuple[str, float]] = {
    "1M": ("DGS1MO", 1 / 12),
    "3M": ("DGS3MO", 0.25),
    "6M": ("DGS6MO", 0.5),
    "1Y": ("DGS1", 1.0),
    "2Y": ("DGS2", 2.0),
    "3Y": ("DGS3", 3.0),
    "5Y": ("DGS5", 5.0),
    "7Y": ("DGS7", 7.0),
    "10Y": ("DGS10", 10.0),
    "20Y": ("DGS20", 20.0),
    "30Y": ("DGS30", 30.0),
}


class FredProvider(DataProvider):
    """Federal Reserve Economic Data (St. Louis Fed)."""

    name = "fred"
    api_url = "https://api.stlouisfed.org/fred/series/observations"
    csv_url = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    def __init__(self, api_key: str | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = get_api_key("FRED_API_KEY", api_key, required=False)

    def series(self, series_id: str, start: Any = None, end: Any = None) -> pd.Series:
        """Any FRED series as a float Series indexed by date (missing values dropped)."""
        end_d = pd.Timestamp(end or date.today()).date()
        start_d = pd.Timestamp(start or end_d - timedelta(days=365 * 5)).date()
        if self.api_key:
            data = self._get_json(self.api_url, {
                "series_id": series_id, "api_key": self.api_key, "file_type": "json",
                "observation_start": start_d.isoformat(), "observation_end": end_d.isoformat(),
            })
            obs = data.get("observations", [])
            s = pd.Series({o["date"]: o["value"] for o in obs}, dtype="object")
        else:
            s = self._csv_series(series_id, start_d, end_d)
        s.index = pd.to_datetime(s.index)
        s = pd.to_numeric(s.replace(".", None), errors="coerce").dropna()
        s.name = series_id
        if s.empty:
            raise DataError(f"fred: no observations for {series_id}")
        return s.loc[str(start_d):str(end_d)]

    def _csv_series(self, series_id: str, start: date, end: date) -> pd.Series:
        import requests

        resp = requests.get(self.csv_url, params={"id": series_id, "cosd": start.isoformat(),
                                                  "coed": end.isoformat()},
                            timeout=self.timeout)
        if resp.status_code != 200:
            raise DataError(f"fred: HTTP {resp.status_code} for {series_id}")
        df = pd.read_csv(io.StringIO(resp.text))
        return pd.Series(df.iloc[:, 1].values, index=df.iloc[:, 0].values, dtype="object")

    def risk_free_rate(self, tenor: str = "3M", as_of: Any = None) -> float:
        """Latest Treasury yield for ``tenor`` as a decimal (e.g. 0.043)."""
        sid, _ = TREASURY_SERIES[tenor.upper()]
        end = pd.Timestamp(as_of or date.today()).date()
        s = self.series(sid, end - timedelta(days=30), end)
        return float(s.iloc[-1]) / 100.0

    def yield_curve(self, as_of: Any = None) -> pd.Series:
        """Treasury curve: index = maturity in years, values = yield (decimal)."""
        end = pd.Timestamp(as_of or date.today()).date()
        out = {}
        for sid, years in TREASURY_SERIES.values():
            try:
                out[years] = float(self.series(sid, end - timedelta(days=30), end).iloc[-1]) / 100
            except DataError:
                continue
        if not out:
            raise DataError("fred: could not build a yield curve")
        return pd.Series(out, name="yield").sort_index()

    def inflation_yoy(self, as_of: Any = None) -> tuple[float, pd.Timestamp]:
        """Latest year-over-year US CPI inflation (CPIAUCSL) and the month it refers to."""
        end = pd.Timestamp(as_of or date.today()).date()
        s = self.series("CPIAUCSL", end - timedelta(days=500), end)
        if len(s) < 13:
            raise DataError("fred: not enough CPI observations")
        return float(s.iloc[-1] / s.iloc[-13] - 1), s.index[-1]

    def _fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        s = self.series(ticker, start, end)
        return pd.DataFrame({"close": s})
