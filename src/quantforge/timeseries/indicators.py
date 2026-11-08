"""Technical indicators on price series (pandas in, pandas out).

All indicators use only past and current data at each date (no look-ahead).

References
----------
Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*. (RSI, ATR)
Appel, G. (1979). *The Moving Average Convergence-Divergence Method*. (MACD)
Bollinger, J. (2001). *Bollinger on Bollinger Bands*. McGraw-Hill.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["sma", "ema", "rsi", "macd", "bollinger_bands", "atr", "momentum", "rolling_zscore"]


def sma(close: pd.Series, window: int = 20) -> pd.Series:
    """Simple moving average."""
    return close.rolling(window, min_periods=window).mean().rename(f"SMA {window}")


def ema(close: pd.Series, span: int = 20) -> pd.Series:
    """Exponential moving average (alpha = 2 / (span + 1))."""
    return close.ewm(span=span, adjust=False, min_periods=span).mean().rename(f"EMA {span}")


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index in [0, 100]."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss > 0, 100.0).where(avg_gain.notna())
    return out.rename(f"RSI {period}")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line (EMA fast − EMA slow), signal line and histogram."""
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    df = pd.DataFrame({"macd": line, "signal": sig, "histogram": line - sig})
    df.iloc[: slow - 1] = np.nan
    return df


def bollinger_bands(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    """Middle band (SMA), upper/lower bands at ±n_std rolling standard deviations,
    %B (position inside the bands) and bandwidth."""
    mid = close.rolling(window, min_periods=window).mean()
    sd = close.rolling(window, min_periods=window).std(ddof=0)
    upper, lower = mid + n_std * sd, mid - n_std * sd
    return pd.DataFrame({"middle": mid, "upper": upper, "lower": lower,
                         "percent_b": (close - lower) / (upper - lower),
                         "bandwidth": (upper - lower) / mid})


def atr(ohlc: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's Average True Range."""
    prev_close = ohlc["close"].shift(1)
    tr = pd.concat([ohlc["high"] - ohlc["low"], (ohlc["high"] - prev_close).abs(),
                    (ohlc["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean().rename(
        f"ATR {period}")


def momentum(close: pd.Series, lookback: int = 252, skip: int = 21) -> pd.Series:
    """Total return from ``lookback`` to ``skip`` periods ago (12-1 momentum by default)."""
    return (close.shift(skip) / close.shift(lookback) - 1).rename(f"MOM {lookback}-{skip}")


def rolling_zscore(x: pd.Series, window: int = 60) -> pd.Series:
    m = x.rolling(window, min_periods=window).mean()
    s = x.rolling(window, min_periods=window).std()
    return ((x - m) / s).rename("z")
