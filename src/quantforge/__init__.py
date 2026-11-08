"""quantforge — professional-grade quantitative finance in Python.

Subpackages
-----------
pricing      Black-Scholes, binomial trees, Monte-Carlo, barriers, IV surfaces, strategies
portfolio    Markowitz, risk parity, Black-Litterman, CAPM, performance analytics
risk         VaR / ES, backtesting, historical and hypothetical stress tests
timeseries   ARMA, GARCH, cointegration, indicators, realized volatility
backtest     Strategy backtests, parameter search, walk-forward portfolios
academy      Zero-to-advanced curriculum, quizzes, verifiable certificates
credit       Logistic PD models, scorecards, Merton / KMV, Altman Z
data         Real market data: Yahoo, Polygon, FMP, Alpha Vantage, FRED
viz          Interactive Plotly charts for every model
"""

__version__ = "1.0.0"

from . import (  # noqa: E402
           academy,
           backtest,
           credit,
           data,
           paper,
           portfolio,
           pricing,
           risk,
           timeseries,
)

__all__ = ["academy", "pricing", "portfolio", "backtest", "risk", "timeseries", "credit", "data",
           "paper",
           "__version__"]

__author__ = "Marin J. Ventalon"
