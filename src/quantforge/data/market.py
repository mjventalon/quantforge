"""High-level market data facade used by the rest of quantforge and the web app.

Every frame returned carries its provenance in ``df.attrs``:
``source`` (provider name) and ``fetched_at`` (UTC timestamp), so numbers can
always be traced back to where they came from. quantforge never fabricates
or fills in market data: if a source fails, an exception is raised.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .base import DataError, DataProvider, get_api_key
from .providers import AlphaVantageProvider, FMPProvider, PolygonProvider, YahooProvider
from .rates import FredProvider

__all__ = ["MarketData", "PROVIDERS", "make_provider"]

PROVIDERS: dict[str, type[DataProvider]] = {
    "yahoo": YahooProvider,
    "alphavantage": AlphaVantageProvider,
    "polygon": PolygonProvider,
    "fmp": FMPProvider,
}


def make_provider(name: str, **kwargs: Any) -> DataProvider:
    try:
        cls = PROVIDERS[name.lower()]
    except KeyError as exc:
        raise ValueError(f"unknown provider {name!r}; choose from {sorted(PROVIDERS)}") from exc
    return cls(**kwargs)


def _auto_provider() -> DataProvider:
    """Pick a provider: QUANTFORGE_PROVIDER env var, else a keyed provider, else Yahoo."""
    explicit = os.environ.get("QUANTFORGE_PROVIDER")
    if explicit:
        return make_provider(explicit)
    for env, name in (("POLYGON_API_KEY", "polygon"), ("FMP_API_KEY", "fmp"),
                      ("ALPHAVANTAGE_API_KEY", "alphavantage")):
        if get_api_key(env, required=False):
            return make_provider(name)
    return YahooProvider()


class _DiskCache:
    """Tiny pickle cache so repeated runs do not burn API quota."""

    def __init__(self, directory: Path, ttl_seconds: float) -> None:
        self.dir = directory
        self.ttl = ttl_seconds
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.dir / (hashlib.sha1(key.encode()).hexdigest() + ".pkl")

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists() or time.time() - p.stat().st_mtime > self.ttl:
            return None
        try:
            with p.open("rb") as fh:
                return pickle.load(fh)
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        with self._path(key).open("wb") as fh:
            pickle.dump(value, fh)


class MarketData:
    """One object for prices, returns, quotes, option chains and rates.

    Parameters
    ----------
    provider
        A provider name (``"yahoo"``, ``"alphavantage"``, ``"polygon"``, ``"fmp"``),
        a :class:`DataProvider` instance, or ``None`` to auto-select.
    cache
        Cache downloaded data on disk (``~/.cache/quantforge``) for ``cache_ttl`` seconds.

    Examples
    --------
    >>> md = MarketData("yahoo")                         # doctest: +SKIP
    >>> prices = md.prices(["AAPL", "MSFT", "SPY"], start="2020-01-01")   # doctest: +SKIP
    >>> md.risk_free_rate()                              # doctest: +SKIP
    0.0431
    """

    def __init__(
        self,
        provider: str | DataProvider | None = None,
        *,
        fred: FredProvider | None = None,
        cache: bool = True,
        cache_ttl: float = 6 * 3600,
        cache_dir: str | Path | None = None,
        **provider_kwargs: Any,
    ) -> None:
        if isinstance(provider, DataProvider):
            self.provider = provider
        elif provider is None:
            self.provider = _auto_provider()
        else:
            self.provider = make_provider(provider, **provider_kwargs)
        self.fred = fred or FredProvider()
        directory = Path(cache_dir or Path.home() / ".cache" / "quantforge")
        self._cache = _DiskCache(directory, cache_ttl) if cache else None

    @property
    def source(self) -> str:
        return self.provider.name

    # ------------------------------------------------------------------ helpers
    def _cached(self, key: str, fn: Any) -> Any:
        full_key = f"{self.provider.name}|{key}"
        if self._cache is not None:
            hit = self._cache.get(full_key)
            if hit is not None:
                return hit
        value = fn()
        if self._cache is not None:
            self._cache.set(full_key, value)
        return value

    @staticmethod
    def _stamp(obj: Any, source: str) -> Any:
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            obj.attrs["source"] = source
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            obj.attrs.setdefault("fetched_at", now)
        return obj

    # --------------------------------------------------------------- equities
    def history(self, ticker: str, start: Any = None, end: Any = None) -> pd.DataFrame:
        """Daily OHLCV for one ticker."""
        key = f"hist|{ticker.upper()}|{start}|{end or date.today()}"
        df = self._cached(key, lambda: self.provider.get_history(ticker, start, end))
        return self._stamp(df.copy(), self.source)

    def prices(
        self,
        tickers: str | list[str],
        start: Any = None,
        end: Any = None,
        field: str = "adj_close",
        dropna: bool = True,
    ) -> pd.DataFrame:
        """Wide frame of one price field (default adjusted close), one column per ticker.

        Rows where any ticker is missing are dropped when ``dropna=True`` so the
        result is ready for covariance / regression work.
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        tickers = list(dict.fromkeys(t.upper().strip() for t in tickers if t.strip()))
        if not tickers:
            raise ValueError("no tickers given")
        cols, errors = {}, {}
        for t in tickers:
            try:
                cols[t] = self.history(t, start, end)[field]
            except DataError as exc:
                errors[t] = str(exc)
        if errors:
            msg = "; ".join(f"{t}: {e}" for t, e in errors.items())
            raise DataError(f"could not load {len(errors)} ticker(s) — {msg}")
        df = pd.DataFrame(cols)
        if dropna:
            df = df.dropna()
        return self._stamp(df, self.source)

    def returns(
        self,
        tickers: str | list[str],
        start: Any = None,
        end: Any = None,
        log: bool = False,
        frequency: str = "D",
    ) -> pd.DataFrame:
        """Periodic returns (``"D"``, ``"W"``, ``"M"``) from adjusted closes."""
        px = self.prices(tickers, start, end)
        if frequency.upper() != "D":
            rule = {"W": "W-FRI", "M": "ME"}.get(frequency.upper(), frequency)
            px = px.resample(rule).last()
        rets = np.log(px / px.shift(1)) if log else px.pct_change()
        return self._stamp(rets.dropna(how="all").dropna(), self.source)

    def intraday(self, ticker: str, period: str = "1d", interval: str = "1m") -> pd.DataFrame:
        """Intraday bars, never cached (for live charts)."""
        return self._stamp(self.provider.get_intraday(ticker, period, interval), self.source)

    def quote(self, ticker: str) -> float:
        """Latest price from the provider (not cached)."""
        return self.provider.get_quote(ticker)

    def historical_volatility(self, ticker: str, window: int = 63, end: Any = None) -> float:
        """Annualized close-to-close volatility over the last ``window`` trading days."""
        start = pd.Timestamp(end or date.today()) - timedelta(days=int(window * 1.6) + 10)
        px = self.history(ticker, start, end)["adj_close"]
        lr = np.log(px / px.shift(1)).dropna().iloc[-window:]
        if len(lr) < max(10, window // 2):
            raise DataError(f"not enough history for {ticker} to estimate volatility")
        return float(lr.std(ddof=1) * np.sqrt(252))

    # ---------------------------------------------------------------- options
    def option_expiries(self, ticker: str) -> list[pd.Timestamp]:
        return self._cached(f"exp|{ticker.upper()}|{date.today()}",
                            lambda: self.provider.get_expiries(ticker))

    def option_chain(self, ticker: str, expiry: Any = None) -> pd.DataFrame:
        """Listed option chain. Adds ``mid`` and ``days`` (calendar days to expiry)."""
        key = f"chain|{ticker.upper()}|{expiry}|{datetime.now():%Y-%m-%d %H}"
        df = self._cached(key, lambda: self.provider.get_option_chain(ticker, expiry)).copy()
        bid, ask = df["bid"], df["ask"]
        df["mid"] = np.where((bid > 0) & (ask > 0) & (ask >= bid), 0.5 * (bid + ask), df["last"])
        df["days"] = (df["expiry"] - pd.Timestamp(date.today())).dt.days
        return self._stamp(df, self.source)

    # ----------------------------------------------------------- fundamentals
    def fundamentals(self, ticker: str) -> dict[str, Any]:
        """Latest annual fundamentals (market cap, debt, assets, EBIT...). Missing = None."""
        return self._cached(f"fund|{ticker.upper()}|{date.today()}",
                            lambda: self.provider.get_fundamentals(ticker))

    # ------------------------------------------------------------------ rates
    def risk_free_rate(self, tenor: str = "3M") -> float:
        """Latest US Treasury constant-maturity yield (decimal) from FRED."""
        return self._cached(f"rf|{tenor}|{date.today()}", lambda: self.fred.risk_free_rate(tenor))

    def inflation(self) -> tuple[float, pd.Timestamp]:
        """Latest US CPI inflation, year over year (FRED CPIAUCSL)."""
        return self._cached(f"cpi|{date.today()}", self.fred.inflation_yoy)

    def yield_curve(self) -> pd.Series:
        s = self._cached(f"curve|{date.today()}", self.fred.yield_curve)
        return self._stamp(s, "fred")

    def __repr__(self) -> str:
        return f"MarketData(provider={self.provider.name!r})"
