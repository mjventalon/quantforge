r"""Cointegration and pairs analysis (Engle-Granger two-step).

1. Regress ``y`` on ``x`` (with constant): ``y_t = α + β x_t + u_t``.
2. Test the residual ``u_t`` for a unit root with an ADF regression without
   constant. Critical values come from MacKinnon (2010) for two variables —
   they are more negative than ordinary ADF values because β is estimated.

If the residual is stationary the pair is cointegrated: the spread tends to
revert, with half-life estimated from an AR(1) fit (Ornstein-Uhlenbeck).

References
----------
Engle, R. & Granger, C. (1987). Co-integration and error correction.
*Econometrica*, 55(2).
MacKinnon, J. (2010). Critical values for cointegration tests. Queen's
Economics Department Working Paper 1227.
Gatev, E., Goetzmann, W. & Rouwenhorst, K. (2006). Pairs Trading.
*Review of Financial Studies*, 19(3).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .arma import _adf_core

__all__ = ["CointegrationResult", "engle_granger", "spread_half_life", "rolling_hedge_ratio"]

# MacKinnon (2010) table 2, N = 2 variables, constant term: (b_inf, b1, b2, b3)
_EG_CRIT = {0.01: (-3.89644, -10.9519, -22.527, 0.0),
            0.05: (-3.33613, -6.1101, -6.823, 0.0),
            0.10: (-3.04445, -4.2412, -2.720, 0.0)}


@dataclass
class CointegrationResult:
    hedge_ratio: float
    intercept: float
    statistic: float
    p_value: float | None
    critical_values: dict[str, float]
    cointegrated_5pct: bool
    half_life: float
    spread: pd.Series
    lags: int

    def __str__(self) -> str:
        p = f"{self.p_value:.4f}" if self.p_value is not None else "n/a"
        return (f"β={self.hedge_ratio:.4f}, ADF={self.statistic:.3f} (p={p}), "
                f"cointegrated at 5%: {self.cointegrated_5pct}, half-life {self.half_life:.1f}")


def spread_half_life(spread: pd.Series) -> float:
    """Half-life of mean reversion from Δs_t = a + b s_{t-1} + e: ``-ln 2 / ln(1 + b)``."""
    s = spread.dropna()
    lag = s.shift(1).iloc[1:]
    d = s.diff().iloc[1:]
    X = np.column_stack([np.ones(len(lag)), lag.to_numpy()])
    b = np.linalg.lstsq(X, d.to_numpy(), rcond=None)[0][1]
    return float(-np.log(2) / np.log(1 + b)) if -1 < b < 0 else np.inf


def engle_granger(y: pd.Series, x: pd.Series, max_lags: int | None = None,
                  log_prices: bool = True) -> CointegrationResult:
    """Engle-Granger cointegration test of ``y`` on ``x`` (prices, aligned by date)."""
    df = pd.concat([y, x], axis=1, join="inner").dropna()
    if len(df) < 60:
        raise ValueError("need at least 60 overlapping observations")
    a, b = (np.log(df.iloc[:, 0]), np.log(df.iloc[:, 1])) if log_prices else \
        (df.iloc[:, 0], df.iloc[:, 1])
    X = np.column_stack([np.ones(len(b)), b.to_numpy()])
    alpha, beta = np.linalg.lstsq(X, a.to_numpy(), rcond=None)[0]
    resid = a - alpha - beta * b
    stat, lag, nobs = _adf_core(resid.to_numpy(), max_lags, regression="n")
    crit = {f"{int(k * 100)}%": c[0] + c[1] / nobs + c[2] / nobs**2 for k, c in _EG_CRIT.items()}
    try:
        from statsmodels.tsa.adfvalues import mackinnonp
        p = float(mackinnonp(stat, regression="c", N=2))
    except ImportError:
        p = None
    return CointegrationResult(
        hedge_ratio=float(beta), intercept=float(alpha), statistic=float(stat), p_value=p,
        critical_values=crit, cointegrated_5pct=bool(stat < crit["5%"]),
        half_life=spread_half_life(resid), spread=resid.rename("spread"), lags=lag,
    )


def rolling_hedge_ratio(y: pd.Series, x: pd.Series, window: int = 120,
                        log_prices: bool = True) -> pd.Series:
    """Rolling OLS β of y on x using only the past ``window`` observations."""
    df = pd.concat([y, x], axis=1, join="inner").dropna()
    a, b = (np.log(df.iloc[:, 0]), np.log(df.iloc[:, 1])) if log_prices else \
        (df.iloc[:, 0], df.iloc[:, 1])
    return (a.rolling(window).cov(b) / b.rolling(window).var()).rename("hedge_ratio")
