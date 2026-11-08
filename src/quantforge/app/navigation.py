"""Single source of truth for the app's pages: used by the router and the home page."""

from __future__ import annotations

import re
from pathlib import Path

PAGES_DIR = Path(__file__).parent / "pages"

#: section -> list of (file, title, icon, one-line description)
SECTIONS: dict[str, list[tuple[str, str, str, str]]] = {
    "Start": [
        ("00_Home.py", "Home", "🏠", "Overview and connection check"),
        ("01_Live_market.py", "Live market", "⚡", "Intraday charts that refresh on their own"),
    ],
    "Trade": [
        ("23_Paper_trading.py", "Paper trading", "💼", "Virtual money, real prices: orders, P&L, widgets — saved"),
    ],
    "Markets": [
        ("02_Market_pulse.py", "Market pulse", "🌡️", "Heatmaps of sectors, asset classes, watchlists"),
        ("03_Stock_analysis.py", "Stock analysis", "📊", "Candles, RSI, MACD, Bollinger, volatility"),
    ],
    "Options": [
        ("04_Options_pricer.py", "Options pricer", "🧮", "3 models vs the live price, Greeks, open interest"),
        ("05_Vol_surface.py", "Volatility surface", "🌋", "Live smiles and a 3-D SVI surface"),
        ("06_Strategy_builder.py", "Strategy builder", "🧩", "Multi-leg strategies with live premiums"),
        ("24_Advanced_models.py", "Heston · SABR · jumps", "🧠", "Stochastic vol, SABR and jump models fitted to live options"),
        ("21_Cpp_engine.py", "C++ engine", "⚙️", "Multithreaded C++ pricing, benchmarked on real inputs"),
    ],
    "Investing": [
        ("07_Portfolio.py", "Portfolio", "🎯", "Frontier, risk parity, factors, Black-Litterman"),
        ("08_Wealth_simulator.py", "Wealth simulator", "🌱", "Real-history Monte-Carlo of your savings"),
    ],
    "Research lab": [
        ("09_Backtester.py", "Backtester", "🔁", "Look-ahead-free backtests, walk-forward"),
        ("10_Strategy_lab.py", "Strategy Lab", "🧪", "Many strategies, one book: diversity, Monte-Carlo"),
        ("11_Pairs_trading.py", "Pairs trading", "🔗", "Cointegration and spread trading"),
        ("12_Regimes_3D.py", "Regimes & 3-D", "🌀", "Hidden Markov regimes, live distribution surfaces"),
    ],
    "Risk & models": [
        ("13_Risk.py", "Risk", "🛡️", "VaR, Expected Shortfall, backtests, crisis replays"),
        ("14_Time_series.py", "Time series", "〰️", "ARMA, GARCH volatility forecasts"),
        ("15_Credit.py", "Credit", "🏦", "Distance to default, Altman Z, PD models"),
    ],
    "Learn": [
        ("16_Academy.py", "Academy", "🎓", "From zero to quant: 23 chapters, quizzes, certificates"),
        ("22_Code_lab.py", "Code Lab", "💻", "Rewrite the formulas yourself in Python and C++"),
        ("17_Verify.py", "Verify a certificate", "✅", "Check that a certificate is genuine"),
        ("18_Guide.py", "Guide", "📘", "Every tool explained simply"),
    ],
    "About": [
        ("19_Creator.py", "Creator", "👤", "Who built quantforge"),
        ("20_Legal.py", "Policies", "⚖️", "Terms, privacy, disclaimer, data sources"),
    ],
}


def url_slug(title: str) -> str:
    """Clean URL path for a page title: "C++ engine" -> "cpp-engine", "Regimes & 3-D" ->
    "regimes-3d"."""
    special = {"Verify a certificate": "verify"}
    if title in special:
        return special[title]
    t = title.lower().replace("++", "pp").replace("3-d", "3d")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")
