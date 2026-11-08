"""How the *shape* of the return distribution changes through time.

:func:`rolling_density_surface` estimates, for each date, the density of the
returns observed over the trailing window (Gaussian kernel density, past data
only). Stacking the densities gives a time × return × density surface: fat
tails, skew and volatility bursts become visible as the surface widens, tilts
and flattens.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

__all__ = ["rolling_density_surface", "rolling_moments"]


def rolling_density_surface(returns: pd.Series, window: int = 63, step: int = 5,
                            grid_points: int = 80, clip_quantile: float = 0.995,
                            ) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """Return ``(dates, grid, density)`` with ``density.shape == (len(dates), grid_points)``.

    The return grid spans the ``clip_quantile`` range of the full sample so every
    slice shares the same axis.
    """
    r = pd.Series(returns).dropna()
    if len(r) < window + step:
        raise ValueError("series shorter than the window")
    lo, hi = np.quantile(r, [1 - clip_quantile, clip_quantile])
    pad = 0.15 * (hi - lo)
    grid = np.linspace(lo - pad, hi + pad, grid_points)
    ends = list(range(window, len(r) + 1, step))
    if ends[-1] != len(r):
        ends.append(len(r))
    dens = np.empty((len(ends), grid_points))
    x = r.to_numpy()
    for i, e in enumerate(ends):
        sample = x[e - window:e]
        if np.std(sample) == 0:
            dens[i] = 0.0
            continue
        dens[i] = stats.gaussian_kde(sample)(grid)
    return pd.DatetimeIndex(r.index[np.array(ends) - 1]), grid, dens


def rolling_moments(returns: pd.Series, window: int = 63, periods: int = 252) -> pd.DataFrame:
    """Rolling annualized volatility, skewness and excess kurtosis (past data only)."""
    r = pd.Series(returns).dropna()
    return pd.DataFrame({
        "volatility": r.rolling(window).std() * np.sqrt(periods),
        "skewness": r.rolling(window).skew(),
        "excess_kurtosis": r.rolling(window).kurt(),
    })
