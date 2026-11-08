"""Classic single-asset trading rules. Each returns a target-position series
decided at each close (use with :func:`quantforge.backtest.run_backtest`)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..timeseries.indicators import bollinger_bands, rsi

__all__ = ["buy_and_hold", "sma_crossover", "time_series_momentum", "rsi_reversion",
           "bollinger_reversion", "volatility_target", "STRATEGIES"]


def buy_and_hold(prices: pd.Series) -> pd.Series:
    return pd.Series(1.0, index=prices.index)


def sma_crossover(prices: pd.Series, fast: int = 50, slow: int = 200,
                  allow_short: bool = False) -> pd.Series:
    """Long when the fast moving average is above the slow one (trend following)."""
    if fast >= slow:
        raise ValueError("fast must be shorter than slow")
    f = prices.rolling(fast).mean()
    s = prices.rolling(slow).mean()
    pos = np.where(f > s, 1.0, -1.0 if allow_short else 0.0)
    return pd.Series(pos, index=prices.index).where(s.notna(), 0.0)


def time_series_momentum(prices: pd.Series, lookback: int = 252, allow_short: bool = False
                         ) -> pd.Series:
    """Long if the trailing ``lookback`` return is positive (Moskowitz, Ooi & Pedersen 2012)."""
    r = prices / prices.shift(lookback) - 1
    pos = np.where(r > 0, 1.0, -1.0 if allow_short else 0.0)
    return pd.Series(pos, index=prices.index).where(r.notna(), 0.0)


def rsi_reversion(prices: pd.Series, period: int = 14, lower: float = 30,
                  upper: float = 70) -> pd.Series:
    """Buy when RSI drops below ``lower``, sell when it rises above ``upper`` (mean reversion)."""
    if lower >= upper:
        raise ValueError("lower must be below upper")
    r = rsi(prices, period)
    sig = pd.Series(np.nan, index=prices.index)
    sig[r < lower] = 1.0
    sig[r > upper] = 0.0
    return sig.ffill().fillna(0.0)


def bollinger_reversion(prices: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Series:
    """Buy below the lower band, exit when price crosses back above the middle band."""
    bb = bollinger_bands(prices, window, n_std)
    sig = pd.Series(np.nan, index=prices.index)
    sig[prices < bb["lower"]] = 1.0
    sig[prices > bb["middle"]] = 0.0
    return sig.ffill().fillna(0.0)


def volatility_target(prices: pd.Series, target_vol: float = 0.15, window: int = 21,
                      max_leverage: float = 2.0) -> pd.Series:
    """Scale exposure so realized volatility matches ``target_vol`` (risk management overlay)."""
    vol = prices.pct_change().rolling(window).std() * np.sqrt(252)
    return (target_vol / vol).clip(upper=max_leverage).fillna(0.0)


#: Display name -> (function, {parameter: (default, min, max, step)})
STRATEGIES = {
    "SMA crossover (trend)": (sma_crossover, {"fast": (50, 5, 150, 5),
                                              "slow": (200, 20, 400, 10)}),
    "Time-series momentum": (time_series_momentum, {"lookback": (252, 21, 504, 21)}),
    "RSI mean reversion": (rsi_reversion, {"period": (14, 2, 30, 1), "lower": (30, 5, 45, 5),
                                           "upper": (70, 55, 95, 5)}),
    "Bollinger mean reversion": (bollinger_reversion, {"window": (20, 5, 60, 5),
                                                       "n_std": (2.0, 1.0, 3.0, 0.5)}),
    "Volatility targeting": (volatility_target, {"target_vol": (0.15, 0.05, 0.40, 0.01),
                                                 "window": (21, 5, 126, 1)}),
    "Buy & hold": (buy_and_hold, {}),
}
