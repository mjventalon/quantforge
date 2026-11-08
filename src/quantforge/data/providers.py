"""Concrete market data providers.

========================  ==========  =========  ========  ============================
Provider                  API key     History    Quotes    Options
========================  ==========  =========  ========  ============================
:class:`YahooProvider`    no          yes        yes       yes (needs ``yfinance``)
:class:`AlphaVantage...`  yes         yes        yes       no
:class:`PolygonProvider`  yes         yes        yes       yes (options plan) — Massive
:class:`FMPProvider`      yes         yes        yes       no
========================  ==========  =========  ========  ============================

Keys are read from ``ALPHAVANTAGE_API_KEY``, ``POLYGON_API_KEY`` (or ``MASSIVE_API_KEY``) and
``FMP_API_KEY`` (environment or ``.env``), or passed as ``api_key=...``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .base import (
    CapabilityError,
    DataError,
    DataProvider,
    RateLimitError,
    get_api_key,
)

__all__ = [
    "YahooProvider",
    "AlphaVantageProvider",
    "PolygonProvider",
    "FMPProvider",
]


# =============================================================================
# Yahoo Finance (via yfinance)
# =============================================================================
class YahooProvider(DataProvider):
    """Yahoo Finance through the community ``yfinance`` package. Free, no key.

    Install with ``pip install "quantforge[yahoo]"``. Yahoo's data is unofficial
    and intended for personal/research use.
    """

    name = "yahoo"

    def _yf(self) -> Any:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise DataError(
                "YahooProvider needs the 'yfinance' package: pip install \"quantforge[yahoo]\""
            ) from exc
        return yf

    def _fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        yf = self._yf()
        raw = yf.Ticker(ticker).history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
            interval="1d", auto_adjust=False, actions=False,
        )
        if raw is None or raw.empty:
            raise DataError(f"yahoo: no data for {ticker!r} (check the symbol)")
        return raw.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close",
            "Adj Close": "adj_close", "Volume": "volume",
        })

    def _fetch_intraday(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        raw = self._yf().Ticker(ticker).history(period=period, interval=interval,
                                                 auto_adjust=False, actions=False, prepost=False)
        if raw is None or raw.empty:
            return pd.DataFrame()
        if raw.index.tz is not None:
            raw.index = raw.index.tz_convert("America/New_York") if not ticker.endswith(
                ("-USD", "=X")) else raw.index.tz_convert("UTC")
        return raw.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                   "Close": "close", "Volume": "volume"})

    def _fetch_quote(self, ticker: str) -> float:
        info = self._yf().Ticker(ticker).fast_info
        if hasattr(info, "get"):
            price = info.get("last_price")
        else:
            price = getattr(info, "last_price", None)
        if price is None or not np.isfinite(price):
            raise CapabilityError("no live quote")
        return float(price)

    def _fetch_expiries(self, ticker: str) -> list[Any]:
        return list(self._yf().Ticker(ticker).options)

    def _fetch_option_chain(self, ticker: str, expiry: pd.Timestamp | None) -> pd.DataFrame:
        tk = self._yf().Ticker(ticker)
        expiries = list(tk.options)
        if not expiries:
            raise DataError(f"yahoo: {ticker!r} has no listed options")
        if expiry is not None:
            wanted = expiry.strftime("%Y-%m-%d")
            if wanted not in expiries:
                raise DataError(f"yahoo: expiry {wanted} not listed; available: {expiries[:8]}...")
            expiries = [wanted]
        frames = []
        for exp in expiries:
            chain = tk.option_chain(exp)
            for kind, df in (("call", chain.calls), ("put", chain.puts)):
                if df is None or df.empty:
                    continue
                frames.append(pd.DataFrame({
                    "contract": df["contractSymbol"], "expiry": exp, "strike": df["strike"],
                    "type": kind, "bid": df["bid"], "ask": df["ask"], "last": df["lastPrice"],
                    "volume": df.get("volume"), "open_interest": df.get("openInterest"),
                    "implied_vol": df.get("impliedVolatility"),
                }))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _fetch_fundamentals(self, ticker: str) -> dict[str, Any]:
        tk = self._yf().Ticker(ticker)
        info = tk.info or {}
        bs, inc = tk.balance_sheet, tk.income_stmt

        def item(df: pd.DataFrame | None, *names: str) -> float | None:
            if df is None or df.empty:
                return None
            for n in names:
                if n in df.index:
                    v = df.loc[n].iloc[0]
                    if pd.notna(v):
                        return float(v)
            return None

        return {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"), "currency": info.get("financialCurrency"),
            "fiscal_date": str(bs.columns[0].date()) if bs is not None and not bs.empty else None,
            "market_cap": info.get("marketCap"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "short_term_debt": item(bs, "Current Debt",
                                    "Current Debt And Capital Lease Obligation"),
            "long_term_debt": item(bs, "Long Term Debt",
                                   "Long Term Debt And Capital Lease Obligation"),
            "total_debt": item(bs, "Total Debt") or info.get("totalDebt"),
            "total_assets": item(bs, "Total Assets"),
            "total_liabilities": item(bs, "Total Liabilities Net Minority Interest"),
            "working_capital": item(bs, "Working Capital"),
            "retained_earnings": item(bs, "Retained Earnings"),
            "ebit": item(inc, "EBIT", "Operating Income"),
            "revenue": item(inc, "Total Revenue", "Operating Revenue"),
        }


# =============================================================================
# Alpha Vantage
# =============================================================================
class AlphaVantageProvider(DataProvider):
    """Alpha Vantage (https://www.alphavantage.co). Free key, ~25 requests/day.

    Uses ``TIME_SERIES_DAILY`` (free tier). ``adj_close`` equals ``close`` unless
    ``adjusted=True`` (premium ``TIME_SERIES_DAILY_ADJUSTED``).
    """

    name = "alphavantage"
    requires_key = True
    base_url = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, adjusted: bool = False, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = get_api_key("ALPHAVANTAGE_API_KEY", api_key)
        self.adjusted = adjusted

    def _call(self, **params: Any) -> dict[str, Any]:
        data = self._get_json(self.base_url, {**params, "apikey": self.api_key})
        if not isinstance(data, dict):
            raise DataError("alphavantage: unexpected response")
        for k in ("Note", "Information"):
            if k in data and len(data) <= 2:
                raise RateLimitError(f"alphavantage: {data[k]}")
        if "Error Message" in data:
            raise DataError(f"alphavantage: {data['Error Message']}")
        return data

    def _fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        func = "TIME_SERIES_DAILY_ADJUSTED" if self.adjusted else "TIME_SERIES_DAILY"
        full = (date.today() - start).days > 140
        data = self._call(function=func, symbol=ticker,
                          outputsize="full" if full else "compact")
        series = data.get("Time Series (Daily)")
        if not series:
            raise DataError(f"alphavantage: no data for {ticker!r}")
        df = pd.DataFrame.from_dict(series, orient="index")
        df.columns = [c.split(". ", 1)[-1].replace(" ", "_") for c in df.columns]
        df = df.rename(columns={"adjusted_close": "adj_close"})
        return df

    def _fetch_quote(self, ticker: str) -> float:
        q = self._call(function="GLOBAL_QUOTE", symbol=ticker).get("Global Quote", {})
        if "05. price" not in q:
            raise CapabilityError("no quote")
        return float(q["05. price"])


# =============================================================================
# Polygon.io
# =============================================================================
class PolygonProvider(DataProvider):
    """Massive (formerly Polygon.io, rebranded Oct 2025) REST API.

    A free key gives end-of-day stock aggregates; option snapshots need an options
    plan. Keys work on both ``api.massive.com`` (default) and the legacy
    ``api.polygon.io`` base (pass ``base_url=`` to choose).
    """

    name = "polygon"
    requires_key = True
    base_url = "https://api.massive.com"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = api_key or get_api_key("MASSIVE_API_KEY", required=False) \
            or get_api_key("POLYGON_API_KEY")
        if base_url:
            self.base_url = base_url.rstrip("/")

    def _call(self, path_or_url: str, **params: Any) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else self.base_url + path_or_url
        data = self._get_json(url, {**params, "apiKey": self.api_key})
        if isinstance(data, dict) and data.get("status") == "ERROR":
            raise DataError(f"polygon: {data.get('error') or data.get('message')}")
        return data

    def _fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        data = self._call(f"/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
                          adjusted="true", sort="asc", limit=50000)
        rows = data.get("results") or []
        if not rows:
            raise DataError(f"polygon: no data for {ticker!r}")
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["t"], unit="ms")
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        df["adj_close"] = df["close"]  # aggregates requested with adjusted=true
        return df

    def _fetch_intraday(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        mult, span = {"1m": (1, "minute"), "5m": (5, "minute"), "15m": (15, "minute"),
                      "1h": (1, "hour"), "1d": (1, "day"), "1wk": (1, "week")
                      }.get(interval, (1, "minute"))
        days = {"1d": 4, "5d": 8, "1mo": 35, "3mo": 95, "1y": 370, "5y": 1830, "10y": 3660,
                "max": 365 * 30}.get(period, 4)   # cover weekends, then trim to the period
        end = date.today()
        data = self._call(f"/v2/aggs/ticker/{ticker}/range/{mult}/{span}/"
                          f"{end - timedelta(days=days)}/{end}", adjusted="true", sort="asc",
                          limit=50000)
        rows = data.get("results") or []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.index = pd.to_datetime(df["t"], unit="ms", utc=True).tz_convert("America/New_York")
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        if period not in ("1d", "5d"):
            return df
        sessions = sorted(set(df.index.date))
        keep = sessions[-1:] if period == "1d" else sessions[-5:]
        return df[[d in keep for d in df.index.date]]

    def _fetch_quote(self, ticker: str) -> float:
        data = self._call(f"/v2/aggs/ticker/{ticker}/prev")
        rows = data.get("results") or []
        if not rows:
            raise CapabilityError("no quote")
        return float(rows[0]["c"])

    def _snapshot(self, ticker: str, expiry: pd.Timestamp | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": 250}
        if expiry is not None:
            params["expiration_date"] = expiry.strftime("%Y-%m-%d")
        data = self._call(f"/v3/snapshot/options/{ticker}", **params)
        rows = list(data.get("results") or [])
        pages = 0
        while data.get("next_url") and pages < 40:
            data = self._call(data["next_url"])
            rows.extend(data.get("results") or [])
            pages += 1
        return rows

    def _fetch_expiries(self, ticker: str) -> list[Any]:
        return sorted({r["details"]["expiration_date"] for r in self._snapshot(ticker, None)})

    def _fetch_option_chain(self, ticker: str, expiry: pd.Timestamp | None) -> pd.DataFrame:
        out = []
        for r in self._snapshot(ticker, expiry):
            det, quote, day = r.get("details", {}), r.get("last_quote", {}), r.get("day", {})
            out.append({
                "contract": det.get("ticker"), "expiry": det.get("expiration_date"),
                "strike": det.get("strike_price"), "type": det.get("contract_type"),
                "bid": quote.get("bid"), "ask": quote.get("ask"),
                "last": (r.get("last_trade") or {}).get("price", day.get("close")),
                "volume": day.get("volume"), "open_interest": r.get("open_interest"),
                "implied_vol": r.get("implied_volatility"),
            })
        return pd.DataFrame(out)


# =============================================================================
# Financial Modeling Prep
# =============================================================================
class FMPProvider(DataProvider):
    """Financial Modeling Prep (https://financialmodelingprep.com). Free key available.

    Also exposes :meth:`get_profile` (sector, beta, market cap...).
    """

    name = "fmp"
    requires_key = True
    base_url = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.api_key = get_api_key("FMP_API_KEY", api_key)
        if base_url:
            self.base_url = base_url.rstrip("/")

    def _call(self, path: str, **params: Any) -> Any:
        data = self._get_json(self.base_url + path, {**params, "apikey": self.api_key})
        if isinstance(data, dict) and "Error Message" in data:
            raise DataError(f"fmp: {data['Error Message']}")
        return data

    def _fetch_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        rng = {"from": start.isoformat(), "to": end.isoformat()}
        data = self._call("/historical-price-eod/full", symbol=ticker, **rng)
        rows = data.get("historical", []) if isinstance(data, dict) else data
        if not rows:
            raise DataError(f"fmp: no data for {ticker!r}")
        df = pd.DataFrame(rows).set_index("date").rename(columns={"adjClose": "adj_close"})
        if "adj_close" not in df.columns:
            # The EOD endpoint is split-adjusted only; total-return closes come from
            # the dividend-adjusted endpoint. If unavailable, adj_close stays = close.
            try:
                adj = self._call("/historical-price-eod/dividend-adjusted", symbol=ticker, **rng)
                adj_df = pd.DataFrame(adj).set_index("date")
                if "adjClose" in adj_df.columns:
                    df["adj_close"] = adj_df["adjClose"].reindex(df.index)
            except DataError:
                pass
        return df

    def _fetch_quote(self, ticker: str) -> float:
        data = self._call("/quote", symbol=ticker)
        if not data:
            raise CapabilityError("no quote")
        return float(data[0]["price"])

    def _fetch_fundamentals(self, ticker: str) -> dict[str, Any]:
        prof = self.get_profile(ticker)
        bs = self._call("/balance-sheet-statement", symbol=ticker, limit=1)
        inc = self._call("/income-statement", symbol=ticker, limit=1)
        b = bs[0] if bs else {}
        i = inc[0] if inc else {}
        ca, cl = b.get("totalCurrentAssets"), b.get("totalCurrentLiabilities")
        return {
            "name": prof.get("companyName"), "sector": prof.get("sector"),
            "currency": b.get("reportedCurrency") or prof.get("currency"),
            "fiscal_date": b.get("date"),
            "market_cap": prof.get("marketCap", prof.get("mktCap")),
            "shares_outstanding": i.get("weightedAverageShsOut"),
            "short_term_debt": b.get("shortTermDebt"), "long_term_debt": b.get("longTermDebt"),
            "total_debt": b.get("totalDebt"), "total_assets": b.get("totalAssets"),
            "total_liabilities": b.get("totalLiabilities"),
            "working_capital": ca - cl if ca is not None and cl is not None else None,
            "retained_earnings": b.get("retainedEarnings"),
            "ebit": i.get("ebit", i.get("operatingIncome")), "revenue": i.get("revenue"),
        }

    def get_profile(self, ticker: str) -> dict[str, Any]:
        data = self._call("/profile", symbol=ticker.upper())
        if not data:
            raise DataError(f"fmp: no profile for {ticker!r}")
        return dict(data[0])
