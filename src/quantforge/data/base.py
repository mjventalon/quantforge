"""Provider interface, shared schemas and HTTP plumbing for market data."""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

__all__ = [
    "DataProvider",
    "DataError",
    "MissingAPIKeyError",
    "RateLimitError",
    "CapabilityError",
    "PRICE_COLUMNS",
    "OPTION_COLUMNS",
    "FUNDAMENTAL_KEYS",
    "get_api_key",
    "to_date",
]

#: Columns every ``get_history`` result has, in this order (index = DatetimeIndex named "date").
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]

#: Columns every ``get_option_chain`` result has.
OPTION_COLUMNS = [
    "contract", "expiry", "strike", "type", "bid", "ask", "last",
    "volume", "open_interest", "implied_vol",
]

#: Keys returned by ``get_fundamentals`` (currency units of the filing).
FUNDAMENTAL_KEYS = [
    "name", "sector", "currency", "fiscal_date", "market_cap", "shares_outstanding",
    "short_term_debt", "long_term_debt", "total_debt", "total_assets", "total_liabilities",
    "working_capital", "retained_earnings", "ebit", "revenue",
]

USER_AGENT = "quantforge/0.1 (+https://github.com/)"


class DataError(RuntimeError):
    """A data request failed or returned something unusable."""


class MissingAPIKeyError(DataError):
    """The provider needs an API key that was not supplied."""


class RateLimitError(DataError):
    """The provider refused the request because of a quota or rate limit."""


class CapabilityError(DataError):
    """The provider does not offer this kind of data."""


_ENV_LOADED = False


def _load_dotenv_once() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def get_api_key(env_var: str, explicit: str | None = None, *, required: bool = True) -> str | None:
    """Return an API key from the argument, the environment, or a ``.env`` file."""
    if explicit:
        return explicit
    _load_dotenv_once()
    key = os.environ.get(env_var)
    if not key and required:
        raise MissingAPIKeyError(
            f"No API key found. Set the {env_var} environment variable, add it to a .env file "
            f"in your working directory, or pass api_key=... explicitly."
        )
    return key


def to_date(value: str | date | datetime | pd.Timestamp | None, default: date) -> date:
    if value is None:
        return default
    return pd.Timestamp(value).date()


def default_range(start: Any, end: Any, years: float = 5.0) -> tuple[date, date]:
    end_d = to_date(end, date.today())
    start_d = to_date(start, end_d - timedelta(days=int(365.25 * years)))
    if start_d >= end_d:
        raise ValueError("start must be before end")
    return start_d, end_d


def normalize_history(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a provider frame into the canonical PRICE_COLUMNS schema."""
    df = df.copy()
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index)).tz_localize(None).normalize()
    df.index.name = "date"
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]
    if "volume" not in df.columns:
        df["volume"] = float("nan")
    for col in PRICE_COLUMNS:
        if col not in df.columns:
            df[col] = df["close"]
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[PRICE_COLUMNS].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.dropna(subset=["close"])


def normalize_chain(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in OPTION_COLUMNS:
        if col not in df.columns:
            df[col] = float("nan")
    df["expiry"] = pd.to_datetime(df["expiry"]).dt.normalize()
    df["type"] = df["type"].str.lower().map({"c": "call", "p": "put", "call": "call", "put": "put"})
    for col in ("strike", "bid", "ask", "last", "volume", "open_interest", "implied_vol"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[OPTION_COLUMNS].sort_values(["expiry", "type", "strike"]).reset_index(drop=True)


class DataProvider(ABC):
    """Base class for all market data sources.

    Subclasses implement :meth:`_fetch_history` (required) and optionally
    :meth:`_fetch_quote`, :meth:`_fetch_option_chain` and :meth:`_fetch_expiries`.
    """

    name: str = "base"
    requires_key: bool = False

    def __init__(self, timeout: float = 20.0, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.max_retries = max_retries

    # ---- HTTP -----------------------------------------------------------------
    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        import requests

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, params=params, timeout=self.timeout,
                                    headers={"User-Agent": USER_AGENT})
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(0.5 * 2**attempt)
                continue
            if resp.status_code == 429:
                if attempt < self.max_retries - 1:
                    time.sleep(1.0 * 2**attempt)
                    continue
                raise RateLimitError(f"{self.name}: rate limit reached (HTTP 429)")
            if resp.status_code in (401, 403):
                raise MissingAPIKeyError(
                    f"{self.name}: access denied (HTTP {resp.status_code}). "
                    "Check your API key and plan."
                )
            if resp.status_code >= 500 and attempt < self.max_retries - 1:
                time.sleep(0.5 * 2**attempt)
                continue
            if resp.status_code >= 400:
                raise DataError(f"{self.name}: HTTP {resp.status_code} — {resp.text[:200]}")
            try:
                return resp.json()
            except ValueError as exc:
                raise DataError(f"{self.name}: response is not JSON") from exc
        raise DataError(
            f"{self.name}: request failed after {self.max_retries} attempts: {last_exc}"
        )

    # ---- public API -----------------------------------------------------------
    def get_history(self, ticker: str, start: Any = None, end: Any = None) -> pd.DataFrame:
        """Daily OHLCV history. Columns: :data:`PRICE_COLUMNS`."""
        start_d, end_d = default_range(start, end)
        df = self._fetch_history(ticker.upper().strip(), start_d, end_d)
        df = normalize_history(df)
        df = df.loc[(df.index >= pd.Timestamp(start_d)) & (df.index <= pd.Timestamp(end_d))]
        if df.empty:
            raise DataError(f"{self.name}: no price data for {ticker!r} in {start_d}..{end_d}")
        return df

    def get_quote(self, ticker: str) -> float:
        """Latest available price."""
        try:
            return float(self._fetch_quote(ticker.upper().strip()))
        except CapabilityError:
            hist = self.get_history(ticker, start=date.today() - timedelta(days=14))
            return float(hist["close"].iloc[-1])

    def get_expiries(self, ticker: str) -> list[pd.Timestamp]:
        return sorted(pd.Timestamp(x) for x in self._fetch_expiries(ticker.upper().strip()))

    def get_option_chain(self, ticker: str, expiry: Any = None) -> pd.DataFrame:
        """Listed options. Columns: :data:`OPTION_COLUMNS`. ``expiry=None`` means all expiries."""
        exp = None if expiry is None else pd.Timestamp(expiry).normalize()
        df = self._fetch_option_chain(ticker.upper().strip(), exp)
        if df.empty:
            raise DataError(f"{self.name}: no options found for {ticker!r}")
        return normalize_chain(df)

    def get_intraday(self, ticker: str, period: str = "1d", interval: str = "1m") -> pd.DataFrame:
        """Intraday OHLCV bars (most recent session by default), exchange-local timestamps.

        ``period``: ``"1d"``, ``"5d"``, ``"1mo"``, ``"3mo"``, ``"1y"``, ``"5y"``, ``"10y"``,
        ``"max"``; ``interval``: ``"1m"``, ``"5m"``, ``"15m"``, ``"1h"``, ``"1d"``, ``"1wk"``.
        Free sources limit fine bars to recent dates (Yahoo: 1-minute ≈ 7 days, 1-hour ≈ 2 years).
        """
        df = self._fetch_intraday(ticker.upper().strip(), period, interval)
        if df is None or df.empty:
            raise DataError(f"{self.name}: no intraday data for {ticker!r} (market closed "
                            "or symbol not covered)")
        df = df.copy()
        idx = pd.DatetimeIndex(df.index)
        df.index = idx.tz_localize(None) if idx.tz is not None else idx
        df.index.name = "time"
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])

    def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Latest annual balance-sheet / income items, keys in :data:`FUNDAMENTAL_KEYS`.

        Missing items are ``None`` (never estimated).
        """
        raw = self._fetch_fundamentals(ticker.upper().strip())
        out = {k: raw.get(k) for k in FUNDAMENTAL_KEYS}
        for k, v in out.items():
            if k not in ("name", "sector", "currency", "fiscal_date") and v is not None:
                try:
                    f = float(v)
                    out[k] = f if f == f else None
                except (TypeError, ValueError):
                    out[k] = None
        if out.get("total_debt") is None and out.get("short_term_debt") is not None \
                and out.get("long_term_debt") is not None:
            out["total_debt"] = out["short_term_debt"] + out["long_term_debt"]
        out["source"] = self.name
        return out

    # ---- hooks ----------------------------------------------------------------
    @abstractmethod
    def _fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame: ...

    def _fetch_quote(self, ticker: str) -> float:
        raise CapabilityError(f"{self.name} does not provide quotes")

    def _fetch_expiries(self, ticker: str) -> list[Any]:
        raise CapabilityError(f"{self.name} does not provide option data")

    def _fetch_option_chain(self, ticker: str, expiry: pd.Timestamp | None) -> pd.DataFrame:
        raise CapabilityError(f"{self.name} does not provide option data")

    def _fetch_fundamentals(self, ticker: str) -> dict[str, Any]:
        raise CapabilityError(f"{self.name} does not provide fundamentals")

    def _fetch_intraday(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        raise CapabilityError(f"{self.name} does not provide intraday data")

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
