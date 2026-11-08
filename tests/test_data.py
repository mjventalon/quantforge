"""Data-layer tests. HTTP is mocked with responses shaped exactly like each provider's
documented JSON, so parsing, normalization, errors and caching are tested offline."""

import sys
import types

import pandas as pd
import pytest

from quantforge.data import (
    AlphaVantageProvider,
    DataError,
    FMPProvider,
    FredProvider,
    MarketData,
    MissingAPIKeyError,
    PolygonProvider,
    RateLimitError,
    YahooProvider,
)
from quantforge.data.base import PRICE_COLUMNS


class FakeResponse:
    def __init__(self, payload=None, status=200, text=None):
        self._payload, self.status_code = payload, status
        self.text = text if text is not None else str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


@pytest.fixture
def http(monkeypatch):
    """Route requests.get to a list of (url_substring, response) rules; record calls."""
    rules, calls = [], []

    def fake_get(url, params=None, timeout=None, headers=None):
        calls.append((url, dict(params or {})))
        for sub, resp in rules:
            if sub in url:
                return resp(url, params) if callable(resp) else resp
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return types.SimpleNamespace(rules=rules, calls=calls)


@pytest.fixture(autouse=True)
def no_env_keys(monkeypatch):
    for k in ("POLYGON_API_KEY", "MASSIVE_API_KEY", "FMP_API_KEY", "ALPHAVANTAGE_API_KEY", "FRED_API_KEY",
              "QUANTFORGE_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("quantforge.data.base._ENV_LOADED", True)


# ------------------------------------------------------------------ Alpha Vantage
AV_DAILY = {"Meta Data": {"2. Symbol": "IBM"}, "Time Series (Daily)": {
    "2024-01-03": {"1. open": "161.0", "2. high": "162.0", "3. low": "160.0",
                   "4. close": "161.5", "5. volume": "4000000"},
    "2024-01-02": {"1. open": "160.0", "2. high": "161.2", "3. low": "159.1",
                   "4. close": "160.9", "5. volume": "3500000"}}}


def test_alphavantage_history(http):
    http.rules.append(("alphavantage", FakeResponse(AV_DAILY)))
    df = AlphaVantageProvider(api_key="k").get_history("ibm", "2024-01-01", "2024-01-05")
    assert list(df.columns) == PRICE_COLUMNS
    assert df.index.is_monotonic_increasing and len(df) == 2
    assert df.loc["2024-01-03", "close"] == 161.5
    assert http.calls[0][1]["symbol"] == "IBM" and http.calls[0][1]["apikey"] == "k"


def test_alphavantage_rate_limit_message(http):
    http.rules.append(("alphavantage", FakeResponse({"Information": "25 requests per day"})))
    with pytest.raises(RateLimitError, match="25 requests"):
        AlphaVantageProvider(api_key="k").get_history("IBM", "2024-01-01", "2024-01-05")


def test_missing_key_raises():
    with pytest.raises(MissingAPIKeyError, match="POLYGON_API_KEY"):
        PolygonProvider()


def test_key_from_environment(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "envkey")
    assert FMPProvider().api_key == "envkey"


# ------------------------------------------------------------------ Polygon
def test_polygon_history_and_chain(http):
    ms = int(pd.Timestamp("2024-03-01").timestamp() * 1000)
    http.rules.append(("/v2/aggs/ticker/AAPL/range", FakeResponse({"status": "OK", "results": [
        {"t": ms, "o": 179.5, "h": 180.5, "l": 177.4, "c": 179.7, "v": 7.3e7},
        {"t": ms + 3 * 86400000, "o": 176.1, "h": 176.9, "l": 173.8, "c": 175.1, "v": 8.1e7}]})))
    page2 = "https://api.massive.com/v3/snapshot/options/AAPL?cursor=abc"
    snap = lambda strike, typ: {
        "details": {"ticker": f"O:AAPL240419{typ[0].upper()}{strike}", "expiration_date":
                    "2024-04-19", "strike_price": strike, "contract_type": typ},
        "last_quote": {"bid": 5.0, "ask": 5.2}, "day": {"volume": 10, "close": 5.1},
        "open_interest": 100, "implied_volatility": 0.25}
    http.rules.append(("cursor=abc", FakeResponse({"results": [snap(180, "put")]})))
    http.rules.append(("/v3/snapshot/options/AAPL", FakeResponse(
        {"results": [snap(180, "call")], "next_url": page2})))
    p = PolygonProvider(api_key="k")
    df = p.get_history("AAPL", "2024-02-28", "2024-03-10")
    assert df["close"].tolist() == [179.7, 175.1]
    chain = p.get_option_chain("AAPL")
    assert set(chain["type"]) == {"call", "put"} and len(chain) == 2
    assert chain["bid"].iloc[0] == 5.0
    assert chain["expiry"].iloc[0] == pd.Timestamp("2024-04-19")


def test_polygon_error_status(http):
    http.rules.append(("massive", FakeResponse({"status": "ERROR", "error": "Unknown API Key"})))
    with pytest.raises(DataError, match="Unknown API Key"):
        PolygonProvider(api_key="bad").get_history("AAPL", "2024-01-01", "2024-02-01")


def test_http_401_and_429(http):
    http.rules.append(("massive", FakeResponse({}, status=401)))
    with pytest.raises(MissingAPIKeyError):
        PolygonProvider(api_key="bad").get_history("AAPL", "2024-01-01", "2024-02-01")
    http.rules[:] = [("massive", FakeResponse({}, status=429))]
    with pytest.raises(RateLimitError):
        PolygonProvider(api_key="k").get_history("AAPL", "2024-01-01", "2024-02-01")


# ------------------------------------------------------------------ FMP
def test_fmp_history_both_shapes_and_fundamentals(http):
    rows = [{"date": "2024-01-03", "open": 1, "high": 2, "low": 0.5, "close": 1.5,
             "adjClose": 1.4, "volume": 10},
            {"date": "2024-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.2,
             "adjClose": 1.1, "volume": 10}]
    http.rules.append(("historical-price-eod", FakeResponse(rows)))
    df = FMPProvider(api_key="k").get_history("F", "2024-01-01", "2024-01-05")
    assert df["adj_close"].tolist() == [1.1, 1.4]
    http.rules[:] = [("historical-price-eod", FakeResponse({"symbol": "F", "historical": rows}))]
    assert len(FMPProvider(api_key="k").get_history("F", "2024-01-01", "2024-01-05")) == 2
    # stable EOD rows without adjClose -> dividend-adjusted endpoint supplies it
    plain = [{k: v for k, v in r.items() if k != "adjClose"} for r in rows]
    http.rules[:] = [
        ("dividend-adjusted", FakeResponse([{"date": "2024-01-03", "adjClose": 1.45},
                                            {"date": "2024-01-02", "adjClose": 1.15}])),
        ("historical-price-eod/full", FakeResponse(plain)),
    ]
    df = FMPProvider(api_key="k").get_history("F", "2024-01-01", "2024-01-05")
    assert df["adj_close"].tolist() == [1.15, 1.45] and df["close"].tolist() == [1.2, 1.5]

    http.rules[:] = [
        ("/profile", FakeResponse([{"companyName": "Ford Motor", "sector": "Consumer Cyclical",
                                    "marketCap": 4.5e10, "currency": "USD"}])),
        ("/balance-sheet-statement", FakeResponse([{
            "date": "2023-12-31", "reportedCurrency": "USD", "shortTermDebt": 5e10,
            "longTermDebt": 1e11, "totalDebt": 1.5e11, "totalAssets": 2.7e11,
            "totalLiabilities": 2.3e11, "totalCurrentAssets": 1.2e11,
            "totalCurrentLiabilities": 1e11, "retainedEarnings": 3e10}])),
        ("/income-statement", FakeResponse([{"revenue": 1.76e11, "operatingIncome": 5e9,
                                             "weightedAverageShsOut": 4e9}])),
    ]
    f = FMPProvider(api_key="k").get_fundamentals("F")
    assert f["market_cap"] == 4.5e10 and f["working_capital"] == 2e10
    assert f["ebit"] == 5e9 and f["source"] == "fmp"


# ------------------------------------------------------------------ FRED
def test_fred_csv_without_key(http):
    csv = "observation_date,DGS3MO\n2024-05-01,5.45\n2024-05-02,.\n2024-05-03,5.40\n"
    http.rules.append(("fredgraph.csv", FakeResponse(text=csv)))
    fred = FredProvider()
    assert fred.api_key is None
    s = fred.series("DGS3MO", "2024-05-01", "2024-05-03")
    assert len(s) == 2  # missing "." dropped, never filled
    assert fred.risk_free_rate("3M", as_of="2024-05-03") == pytest.approx(0.054)


def test_fred_api_with_key_and_curve(http):
    def handler(url, params):
        v = {"DGS1MO": "5.5", "DGS3MO": "5.4", "DGS2": "4.8", "DGS10": "4.5"}.get(
            params["series_id"])
        if v is None:
            return FakeResponse({"observations": []})
        return FakeResponse({"observations": [{"date": "2024-05-03", "value": v}]})
    http.rules.append(("api.stlouisfed.org", handler))
    curve = FredProvider(api_key="k").yield_curve("2024-05-03")
    assert list(curve.index) == [1 / 12, 0.25, 2.0, 10.0]
    assert curve[10.0] == pytest.approx(0.045)


# ------------------------------------------------------------------ Yahoo (fake yfinance)
@pytest.fixture
def fake_yf(monkeypatch):
    idx = pd.date_range("2024-01-02", periods=5, freq="B", tz="America/New_York")
    hist = pd.DataFrame({"Open": [1, 2, 3, 4, 5.0], "High": [2, 3, 4, 5, 6.0],
                         "Low": [0.5] * 5, "Close": [1.5, 2.5, 3.5, 4.5, 5.5],
                         "Adj Close": [1.4, 2.4, 3.4, 4.4, 5.4], "Volume": [100] * 5}, index=idx)
    calls = pd.DataFrame({"contractSymbol": ["X240119C100"], "strike": [100.0], "bid": [1.0],
                          "ask": [1.2], "lastPrice": [1.1], "volume": [5], "openInterest": [50],
                          "impliedVolatility": [0.3]})
    puts = calls.assign(contractSymbol=["X240119P100"])

    class Ticker:
        def __init__(self, sym):
            self.sym = sym
            self.options = ("2024-01-19",)
            self.fast_info = {"last_price": 5.55}
            self.info = {"longName": "Example", "marketCap": 1e9, "sector": "Tech"}
            self.balance_sheet = pd.DataFrame({pd.Timestamp("2023-12-31"): {
                "Current Debt": 1e8, "Long Term Debt": 3e8, "Total Assets": 2e9}})
            self.income_stmt = pd.DataFrame({pd.Timestamp("2023-12-31"): {"EBIT": 2e8}})

        def history(self, **kw):
            return hist

        def option_chain(self, exp):
            return types.SimpleNamespace(calls=calls, puts=puts)

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))


def test_yahoo_provider(fake_yf):
    y = YahooProvider()
    df = y.get_history("x", "2024-01-01", "2024-01-31")
    assert df.index.tz is None and df["adj_close"].iloc[-1] == 5.4
    assert y.get_quote("x") == 5.55
    ch = y.get_option_chain("x", "2024-01-19")
    assert set(ch["type"]) == {"call", "put"} and ch["implied_vol"].iloc[0] == 0.3
    with pytest.raises(DataError, match="not listed"):
        y.get_option_chain("x", "2024-02-16")
    f = y.get_fundamentals("x")
    assert f["total_debt"] == 4e8 and f["ebit"] == 2e8 and f["total_liabilities"] is None


# ------------------------------------------------------------------ MarketData facade
def test_marketdata_prices_returns_cache_and_provenance(fake_yf, tmp_path):
    md = MarketData("yahoo", cache_dir=tmp_path)
    px = md.prices(["AAA", "BBB"], "2024-01-01", "2024-01-31")
    assert list(px.columns) == ["AAA", "BBB"]
    assert px.attrs["source"] == "yahoo" and "fetched_at" in px.attrs
    r = md.returns("AAA", "2024-01-01", "2024-01-31")
    assert r["AAA"].iloc[0] == pytest.approx(2.4 / 1.4 - 1)
    assert len(list(tmp_path.iterdir())) >= 2  # cached on disk
    chain = md.option_chain("AAA", "2024-01-19")
    assert chain["mid"].iloc[0] == pytest.approx(1.1)


def test_marketdata_reports_failed_tickers(fake_yf, tmp_path, monkeypatch):
    md = MarketData("yahoo", cache=False)

    def boom(self, t, s, e):
        if t == "BAD":
            raise DataError("no data for 'BAD'")
        return YahooProvider._orig(self, t, s, e)

    YahooProvider._orig = YahooProvider._fetch_history
    monkeypatch.setattr(YahooProvider, "_fetch_history", boom)
    with pytest.raises(DataError, match="BAD"):
        md.prices(["AAA", "BAD"], "2024-01-01", "2024-01-31")


def test_auto_provider_prefers_keyed(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    assert MarketData(cache=False).source == "fmp"
    monkeypatch.setenv("QUANTFORGE_PROVIDER", "yahoo")
    assert MarketData(cache=False).source == "yahoo"
    with pytest.raises(ValueError):
        MarketData("bloomberg")
