"""Realized volatility estimators from daily OHLC data (all annualized).

References
----------
Parkinson, M. (1980). *Journal of Business*, 53(1).
Garman, M. & Klass, M. (1980). *Journal of Business*, 53(1).
Rogers, L. & Satchell, S. (1991). *Annals of Applied Probability*, 1(4).
Yang, D. & Zhang, Q. (2000). *Journal of Business*, 73(3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "close_to_close_vol",
    "parkinson_vol",
    "garman_klass_vol",
    "rogers_satchell_vol",
    "yang_zhang_vol",
    "ewma_vol",
    "volatility_cone",
    "realized_vol_table",
]


def close_to_close_vol(close: pd.Series, window: int = 21, periods: int = 252) -> pd.Series:
    lr = np.log(close / close.shift(1))
    return (lr.rolling(window).std() * np.sqrt(periods)).rename("close_to_close")


def parkinson_vol(ohlc: pd.DataFrame, window: int = 21, periods: int = 252) -> pd.Series:
    hl = np.log(ohlc["high"] / ohlc["low"]) ** 2
    return np.sqrt(hl.rolling(window).mean() / (4 * np.log(2)) * periods).rename("parkinson")


def garman_klass_vol(ohlc: pd.DataFrame, window: int = 21, periods: int = 252) -> pd.Series:
    hl = np.log(ohlc["high"] / ohlc["low"]) ** 2
    co = np.log(ohlc["close"] / ohlc["open"]) ** 2
    v = 0.5 * hl - (2 * np.log(2) - 1) * co
    return np.sqrt(v.rolling(window).mean() * periods).rename("garman_klass")


def _rs_term(ohlc: pd.DataFrame) -> pd.Series:
    h, l, o, c = (np.log(ohlc[k]) for k in ("high", "low", "open", "close"))
    return (h - c) * (h - o) + (l - c) * (l - o)


def rogers_satchell_vol(ohlc: pd.DataFrame, window: int = 21, periods: int = 252) -> pd.Series:
    return np.sqrt(_rs_term(ohlc).rolling(window).mean() * periods).rename("rogers_satchell")


def yang_zhang_vol(ohlc: pd.DataFrame, window: int = 21, periods: int = 252) -> pd.Series:
    """Drift-independent, handles opening jumps; most efficient of the OHLC estimators."""
    o = np.log(ohlc["open"] / ohlc["close"].shift(1))
    c = np.log(ohlc["close"] / ohlc["open"])
    k = 0.34 / (1.34 + (window + 1) / (window - 1))
    var_o = o.rolling(window).var()
    var_c = c.rolling(window).var()
    var_rs = _rs_term(ohlc).rolling(window).mean()
    return np.sqrt((var_o + k * var_c + (1 - k) * var_rs) * periods).rename("yang_zhang")


def ewma_vol(returns: pd.Series, lam: float = 0.94, periods: int = 252) -> pd.Series:
    """RiskMetrics exponentially weighted volatility (lambda = 0.94 for daily data)."""
    var = (returns**2).ewm(alpha=1 - lam, adjust=False).mean()
    return np.sqrt(var * periods).rename("ewma")


def realized_vol_table(ohlc: pd.DataFrame, window: int = 21) -> pd.DataFrame:
    """All estimators side by side over a rolling window."""
    lr = np.log(ohlc["close"] / ohlc["close"].shift(1))
    return pd.concat([
        close_to_close_vol(ohlc["close"], window),
        parkinson_vol(ohlc, window),
        garman_klass_vol(ohlc, window),
        rogers_satchell_vol(ohlc, window),
        yang_zhang_vol(ohlc, window),
        ewma_vol(lr.dropna()),
    ], axis=1)


def volatility_cone(close: pd.Series, windows: tuple[int, ...] = (10, 21, 42, 63, 126, 252),
                    periods: int = 252) -> pd.DataFrame:
    """Distribution of realized vol by window length (min, quartiles, max, current)."""
    rows = {}
    for w in windows:
        v = close_to_close_vol(close, w, periods).dropna()
        if v.empty:
            continue
        rows[w] = {"min": v.min(), "p10": v.quantile(0.1), "p25": v.quantile(0.25),
                   "median": v.median(), "p75": v.quantile(0.75), "p90": v.quantile(0.9),
                   "max": v.max(), "current": v.iloc[-1]}
    return pd.DataFrame(rows).T.rename_axis("window")
