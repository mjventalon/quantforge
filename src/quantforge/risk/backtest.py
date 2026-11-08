"""VaR model backtesting: Kupiec (1995) POF and Christoffersen (1998) tests,
plus the Basel traffic-light zone."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

__all__ = ["VaRBacktest", "rolling_var", "backtest_var", "basel_zone"]


@dataclass(frozen=True)
class VaRBacktest:
    n_obs: int
    n_exceptions: int
    expected_exceptions: float
    exception_rate: float
    kupiec_lr: float
    kupiec_pvalue: float
    christoffersen_lr: float
    christoffersen_pvalue: float
    conditional_lr: float
    conditional_pvalue: float
    basel_zone: str

    def passed(self, alpha: float = 0.05) -> bool:
        return self.conditional_pvalue > alpha


def rolling_var(returns: pd.Series, window: int = 250, confidence: float = 0.99,
                method: str = "historical") -> pd.Series:
    """Out-of-sample one-step VaR forecast using the previous ``window`` returns."""
    r = returns.dropna()
    a = 1 - confidence
    if method == "historical":
        f = r.rolling(window).quantile(a).shift(1)
    elif method == "normal":
        f = (r.rolling(window).mean() + stats.norm.ppf(a) * r.rolling(window).std()).shift(1)
    else:
        raise ValueError("method must be 'historical' or 'normal'")
    return (-f).rename("VaR")


def _xlogy(x: float, y: float) -> float:
    return 0.0 if x == 0 else x * np.log(y)


def basel_zone(n_exceptions: int, n_obs: int = 250, confidence: float = 0.99) -> str:
    """Basel traffic light: cumulative binomial probability < 95% green, < 99.99% yellow."""
    p = stats.binom.cdf(n_exceptions, n_obs, 1 - confidence)
    return "green" if p < 0.95 else "yellow" if p < 0.9999 else "red"


def backtest_var(returns: pd.Series, var_forecasts: pd.Series,
                 confidence: float = 0.99) -> VaRBacktest:
    """Test whether realized losses exceed VaR at the right frequency and independently."""
    df = pd.concat([returns, var_forecasts], axis=1, join="inner").dropna()
    hits = (df.iloc[:, 0] < -df.iloc[:, 1]).astype(int).to_numpy()
    n, x = hits.size, int(hits.sum())
    p = 1 - confidence
    pi = x / n if n else 0.0
    lr_pof = -2 * (_xlogy(n - x, 1 - p) + _xlogy(x, p) - _xlogy(n - x, 1 - pi) - _xlogy(x, pi))

    prev, cur = hits[:-1], hits[1:]
    n00 = int(np.sum((prev == 0) & (cur == 0)))
    n01 = int(np.sum((prev == 0) & (cur == 1)))
    n10 = int(np.sum((prev == 1) & (cur == 0)))
    n11 = int(np.sum((prev == 1) & (cur == 1)))
    pi0 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi1 = n11 / (n10 + n11) if n10 + n11 else 0.0
    pi_all = (n01 + n11) / (n00 + n01 + n10 + n11) if n > 1 else 0.0
    lr_ind = -2 * (
        _xlogy(n00 + n10, 1 - pi_all) + _xlogy(n01 + n11, pi_all)
        - _xlogy(n00, 1 - pi0) - _xlogy(n01, pi0) - _xlogy(n10, 1 - pi1) - _xlogy(n11, pi1)
    )
    lr_ind = max(lr_ind, 0.0)
    lr_cc = lr_pof + lr_ind
    last = hits[-250:]
    return VaRBacktest(
        n_obs=n, n_exceptions=x, expected_exceptions=n * p, exception_rate=pi,
        kupiec_lr=float(lr_pof), kupiec_pvalue=float(stats.chi2.sf(lr_pof, 1)),
        christoffersen_lr=float(lr_ind), christoffersen_pvalue=float(stats.chi2.sf(lr_ind, 1)),
        conditional_lr=float(lr_cc), conditional_pvalue=float(stats.chi2.sf(lr_cc, 2)),
        basel_zone=basel_zone(int(last.sum()), len(last), confidence),
    )
