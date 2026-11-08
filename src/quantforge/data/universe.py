"""Ticker discovery: a curated list of liquid instruments, the full SEC list of US
listed companies (downloaded on demand), and live Yahoo search by symbol or name.

Symbols use Yahoo Finance conventions (``^GSPC`` index, ``BTC-USD`` crypto,
``EURUSD=X`` FX, ``GC=F`` futures, ``MC.PA`` Paris listing).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

__all__ = ["POPULAR", "search_tickers", "sec_universe", "universe"]

#: Curated liquid instruments: symbol -> (name, asset type)
POPULAR: dict[str, tuple[str, str]] = {
    # US mega caps
    "AAPL": ("Apple Inc.", "Equity"), "MSFT": ("Microsoft Corp.", "Equity"),
    "NVDA": ("NVIDIA Corp.", "Equity"), "AMZN": ("Amazon.com Inc.", "Equity"),
    "GOOGL": ("Alphabet Inc. Class A", "Equity"), "GOOG": ("Alphabet Inc. Class C", "Equity"),
    "META": ("Meta Platforms Inc.", "Equity"), "TSLA": ("Tesla Inc.", "Equity"),
    "BRK-B": ("Berkshire Hathaway Inc. Class B", "Equity"), "AVGO": ("Broadcom Inc.", "Equity"),
    "LLY": ("Eli Lilly and Co.", "Equity"), "JPM": ("JPMorgan Chase & Co.", "Equity"),
    "V": ("Visa Inc.", "Equity"), "MA": ("Mastercard Inc.", "Equity"),
    "UNH": ("UnitedHealth Group Inc.", "Equity"), "XOM": ("Exxon Mobil Corp.", "Equity"),
    "CVX": ("Chevron Corp.", "Equity"), "JNJ": ("Johnson & Johnson", "Equity"),
    "PG": ("Procter & Gamble Co.", "Equity"), "HD": ("Home Depot Inc.", "Equity"),
    "COST": ("Costco Wholesale Corp.", "Equity"), "WMT": ("Walmart Inc.", "Equity"),
    "KO": ("Coca-Cola Co.", "Equity"), "PEP": ("PepsiCo Inc.", "Equity"),
    "MRK": ("Merck & Co. Inc.", "Equity"), "ABBV": ("AbbVie Inc.", "Equity"),
    "PFE": ("Pfizer Inc.", "Equity"), "BAC": ("Bank of America Corp.", "Equity"),
    "WFC": ("Wells Fargo & Co.", "Equity"), "GS": ("Goldman Sachs Group Inc.", "Equity"),
    "MS": ("Morgan Stanley", "Equity"), "C": ("Citigroup Inc.", "Equity"),
    "BLK": ("BlackRock Inc.", "Equity"), "AXP": ("American Express Co.", "Equity"),
    "ORCL": ("Oracle Corp.", "Equity"), "CRM": ("Salesforce Inc.", "Equity"),
    "ADBE": ("Adobe Inc.", "Equity"), "AMD": ("Advanced Micro Devices Inc.", "Equity"),
    "INTC": ("Intel Corp.", "Equity"), "QCOM": ("Qualcomm Inc.", "Equity"),
    "CSCO": ("Cisco Systems Inc.", "Equity"), "IBM": ("International Business Machines", "Equity"),
    "NFLX": ("Netflix Inc.", "Equity"), "DIS": ("Walt Disney Co.", "Equity"),
    "NKE": ("Nike Inc.", "Equity"), "MCD": ("McDonald's Corp.", "Equity"),
    "SBUX": ("Starbucks Corp.", "Equity"), "BA": ("Boeing Co.", "Equity"),
    "CAT": ("Caterpillar Inc.", "Equity"), "GE": ("GE Aerospace", "Equity"),
    "F": ("Ford Motor Co.", "Equity"), "GM": ("General Motors Co.", "Equity"),
    "T": ("AT&T Inc.", "Equity"), "VZ": ("Verizon Communications Inc.", "Equity"),
    "UBER": ("Uber Technologies Inc.", "Equity"), "PLTR": ("Palantir Technologies Inc.", "Equity"),
    "COIN": ("Coinbase Global Inc.", "Equity"), "PYPL": ("PayPal Holdings Inc.", "Equity"),
    "SHOP": ("Shopify Inc.", "Equity"), "TSM": ("Taiwan Semiconductor Mfg. (ADR)", "Equity"),
    "ASML": ("ASML Holding N.V. (ADR)", "Equity"),
    # Europe (Yahoo suffixes)
    "MC.PA": ("LVMH (Paris)", "Equity"), "OR.PA": ("L'Oréal (Paris)", "Equity"),
    "TTE.PA": ("TotalEnergies (Paris)", "Equity"), "AIR.PA": ("Airbus (Paris)", "Equity"),
    "SAN.PA": ("Sanofi (Paris)", "Equity"), "BNP.PA": ("BNP Paribas (Paris)", "Equity"),
    "SAP.DE": ("SAP SE (Xetra)", "Equity"), "NESN.SW": ("Nestlé (SIX)", "Equity"),
    # ETFs
    "SPY": ("SPDR S&P 500 ETF", "ETF"), "VOO": ("Vanguard S&P 500 ETF", "ETF"),
    "QQQ": ("Invesco QQQ (Nasdaq-100)", "ETF"), "IWM": ("iShares Russell 2000 ETF", "ETF"),
    "DIA": ("SPDR Dow Jones Industrial Average ETF", "ETF"),
    "VTI": ("Vanguard Total Stock Market ETF", "ETF"), "VT": ("Vanguard Total World Stock ETF", "ETF"),
    "EFA": ("iShares MSCI EAFE ETF", "ETF"), "EEM": ("iShares MSCI Emerging Markets ETF", "ETF"),
    "AGG": ("iShares Core US Aggregate Bond ETF", "ETF"), "BND": ("Vanguard Total Bond Market ETF", "ETF"),
    "TLT": ("iShares 20+ Year Treasury Bond ETF", "ETF"), "IEF": ("iShares 7-10 Year Treasury ETF", "ETF"),
    "SHY": ("iShares 1-3 Year Treasury ETF", "ETF"), "LQD": ("iShares iBoxx IG Corporate Bond ETF", "ETF"),
    "HYG": ("iShares iBoxx High Yield Corporate Bond ETF", "ETF"), "TIP": ("iShares TIPS Bond ETF", "ETF"),
    "GLD": ("SPDR Gold Shares", "ETF"), "SLV": ("iShares Silver Trust", "ETF"),
    "USO": ("United States Oil Fund", "ETF"), "VNQ": ("Vanguard Real Estate ETF", "ETF"),
    "XLK": ("Technology Select Sector SPDR", "ETF"), "XLF": ("Financial Select Sector SPDR", "ETF"),
    "XLE": ("Energy Select Sector SPDR", "ETF"), "XLV": ("Health Care Select Sector SPDR", "ETF"),
    "XLY": ("Consumer Discretionary Select Sector SPDR", "ETF"),
    "XLP": ("Consumer Staples Select Sector SPDR", "ETF"), "XLI": ("Industrial Select Sector SPDR", "ETF"),
    "XLU": ("Utilities Select Sector SPDR", "ETF"), "XLB": ("Materials Select Sector SPDR", "ETF"),
    "XLRE": ("Real Estate Select Sector SPDR", "ETF"),
    "XLC": ("Communication Services Select Sector SPDR", "ETF"),
    "SMH": ("VanEck Semiconductor ETF", "ETF"), "ARKK": ("ARK Innovation ETF", "ETF"),
    "MTUM": ("iShares MSCI USA Momentum Factor ETF", "ETF"),
    "QUAL": ("iShares MSCI USA Quality Factor ETF", "ETF"),
    "USMV": ("iShares MSCI USA Min Vol Factor ETF", "ETF"),
    "IWD": ("iShares Russell 1000 Value ETF", "ETF"), "IWF": ("iShares Russell 1000 Growth ETF", "ETF"),
    "IBIT": ("iShares Bitcoin Trust ETF", "ETF"),
    # Indices
    "^GSPC": ("S&P 500 Index", "Index"), "^NDX": ("Nasdaq-100 Index", "Index"),
    "^IXIC": ("Nasdaq Composite", "Index"), "^DJI": ("Dow Jones Industrial Average", "Index"),
    "^RUT": ("Russell 2000 Index", "Index"), "^VIX": ("CBOE Volatility Index (VIX)", "Index"),
    "^FCHI": ("CAC 40", "Index"), "^GDAXI": ("DAX", "Index"), "^FTSE": ("FTSE 100", "Index"),
    "^STOXX50E": ("Euro Stoxx 50", "Index"), "^N225": ("Nikkei 225", "Index"),
    "^HSI": ("Hang Seng Index", "Index"), "^TNX": ("CBOE 10-Year Treasury Yield Index", "Index"),
    # Crypto, FX, futures
    "BTC-USD": ("Bitcoin / US dollar", "Crypto"), "ETH-USD": ("Ether / US dollar", "Crypto"),
    "SOL-USD": ("Solana / US dollar", "Crypto"),
    "EURUSD=X": ("Euro / US dollar", "FX"), "USDJPY=X": ("US dollar / Japanese yen", "FX"),
    "GBPUSD=X": ("British pound / US dollar", "FX"),
    "GC=F": ("Gold futures (COMEX)", "Future"), "CL=F": ("WTI crude oil futures (NYMEX)", "Future"),
    "ES=F": ("E-mini S&P 500 futures (CME)", "Future"), "NQ=F": ("E-mini Nasdaq-100 futures (CME)", "Future"),
}

SEC_URL = "https://www.sec.gov/files/company_tickers.json"


def _cache_dir() -> Path:
    d = Path(os.environ.get("QUANTFORGE_CACHE", Path.home() / ".cache" / "quantforge"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def sec_universe(max_age_days: float = 7.0, user_agent: str | None = None) -> dict[str, str]:
    """All US-listed companies from the SEC's public ticker file (symbol -> name).

    The SEC asks automated clients to identify themselves: set
    ``QUANTFORGE_SEC_USER_AGENT="YourApp your@email"``. Returns ``{}`` if the file
    cannot be downloaded (never fails the caller).
    """
    path = _cache_dir() / "sec_company_tickers.json"
    if path.exists() and time.time() - path.stat().st_mtime < max_age_days * 86400:
        try:
            return json.loads(path.read_text())
        except ValueError:
            pass
    ua = user_agent or os.environ.get("QUANTFORGE_SEC_USER_AGENT")
    if not ua:
        return {}
    try:
        import requests

        r = requests.get(SEC_URL, headers={"User-Agent": ua}, timeout=15)
        r.raise_for_status()
        raw = r.json()
        out = {v["ticker"].upper().replace(".", "-"): v["title"] for v in raw.values()}
        path.write_text(json.dumps(out))
        return out
    except Exception:  # noqa: BLE001
        return {}


def universe() -> dict[str, str]:
    """Curated instruments first, then every SEC-listed company if available."""
    out = {k: f"{v[0]} · {v[1]}" for k, v in POPULAR.items()}
    for k, v in sec_universe().items():
        out.setdefault(k, v)
    return out


def search_tickers(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search by symbol prefix or company name.

    Uses Yahoo Finance's search (needs ``yfinance``) and falls back to a local
    prefix/name match on :func:`universe`. Each result has ``symbol``, ``name``,
    ``type`` and ``exchange``.
    """
    q = query.strip()
    if not q:
        return []
    results: list[dict[str, Any]] = []
    try:
        import yfinance as yf

        for it in yf.Search(q, max_results=limit, news_count=0, lists_count=0,
                            include_cb=False, recommended=0, timeout=8,
                            raise_errors=False).quotes:
            if "symbol" not in it:
                continue
            results.append({"symbol": it["symbol"],
                            "name": it.get("shortname") or it.get("longname") or "",
                            "type": it.get("typeDisp") or it.get("quoteType") or "",
                            "exchange": it.get("exchDisp") or it.get("exchange") or ""})
    except Exception:  # noqa: BLE001
        results = []
    if results:
        return results[:limit]
    qu = q.upper()
    uni = universe()
    starts = [s for s in uni if s.startswith(qu)]
    names = [s for s, n in uni.items() if q.lower() in n.lower() and s not in starts]
    return [{"symbol": s, "name": uni[s], "type": POPULAR.get(s, ("", "Equity"))[1],
             "exchange": ""} for s in (sorted(starts, key=len) + names)[:limit]]
