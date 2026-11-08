r"""Capital Asset Pricing Model and performance analytics.

CAPM (Sharpe 1964, Lintner 1965):

.. math:: E[R_i] = r_f + \beta_i\,(E[R_m] - r_f), \qquad
          \beta_i = \frac{\operatorname{Cov}(R_i, R_m)}{\operatorname{Var}(R_m)}

:func:`capm_regression` estimates the market model by OLS on excess returns
and reports alpha, beta, their standard errors, t-stats, p-values and R².
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "CAPMResult",
    "capm_regression",
    "capm_expected_return",
    "security_market_line",
    "performance_summary",
    "drawdowns",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
]


@dataclass(frozen=True)
class CAPMResult:
    """OLS estimate of ``R_i - r_f = alpha + beta (R_m - r_f) + e``."""

    alpha: float              # annualized
    beta: float
    alpha_se: float           # annualized
    beta_se: float
    alpha_t: float
    beta_t: float
    alpha_pvalue: float
    beta_pvalue: float
    r_squared: float
    residual_vol: float       # annualized idiosyncratic volatility
    n_obs: int
    treynor: float
    information_ratio: float

    def __str__(self) -> str:
        return (f"alpha {self.alpha:+.2%}/yr (t={self.alpha_t:.2f}, p={self.alpha_pvalue:.3f}), "
                f"beta {self.beta:.3f} (se {self.beta_se:.3f}), R² {self.r_squared:.3f}, "
                f"n={self.n_obs}")


def _rf_per_period(risk_free_rate: float | pd.Series, periods_per_year: int,
                   index: pd.Index) -> pd.Series:
    if isinstance(risk_free_rate, pd.Series):
        return risk_free_rate.reindex(index).ffill().bfill() / periods_per_year
    return pd.Series(risk_free_rate / periods_per_year, index=index)


def capm_regression(
    asset_returns: pd.Series,
    market_returns: pd.Series,
    risk_free_rate: float | pd.Series = 0.0,
    periods_per_year: int = 252,
) -> CAPMResult:
    """Estimate CAPM alpha and beta from periodic simple returns.

    ``risk_free_rate`` is annualized (scalar, or a Series aligned to the dates).
    """
    df = pd.concat([asset_returns, market_returns], axis=1, join="inner").dropna()
    if len(df) < 10:
        raise ValueError("need at least 10 overlapping observations")
    rf = _rf_per_period(risk_free_rate, periods_per_year, df.index)
    y = (df.iloc[:, 0] - rf).to_numpy()
    x = (df.iloc[:, 1] - rf).to_numpy()
    n = y.size
    X = np.column_stack([np.ones(n), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = n - 2
    s2 = resid @ resid / dof
    cov_b = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov_b))
    t = coef / se
    p = 2 * stats.t.sf(np.abs(t), dof)
    r2 = 1 - resid @ resid / np.sum((y - y.mean()) ** 2)
    alpha_ann = coef[0] * periods_per_year
    resid_vol = np.sqrt(s2 * periods_per_year)
    excess_mean_ann = y.mean() * periods_per_year
    return CAPMResult(
        alpha=float(alpha_ann), beta=float(coef[1]),
        alpha_se=float(se[0] * periods_per_year), beta_se=float(se[1]),
        alpha_t=float(t[0]), beta_t=float(t[1]),
        alpha_pvalue=float(p[0]), beta_pvalue=float(p[1]),
        r_squared=float(r2), residual_vol=float(resid_vol), n_obs=int(n),
        treynor=float(excess_mean_ann / coef[1]) if coef[1] != 0 else np.nan,
        information_ratio=float(alpha_ann / resid_vol) if resid_vol > 0 else np.nan,
    )


def capm_expected_return(beta: float, market_return: float, risk_free_rate: float) -> float:
    """CAPM required return ``rf + beta (E[Rm] - rf)``."""
    return risk_free_rate + beta * (market_return - risk_free_rate)


def security_market_line(
    asset_returns: pd.DataFrame,
    market_returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """Beta, realized and CAPM-implied return for each asset (for SML charts)."""
    mkt_ann = market_returns.mean() * periods_per_year
    rows = {}
    for col in asset_returns.columns:
        res = capm_regression(asset_returns[col], market_returns, risk_free_rate, periods_per_year)
        realized = asset_returns[col].mean() * periods_per_year
        rows[col] = {
            "beta": res.beta, "realized_return": realized,
            "capm_return": capm_expected_return(res.beta, mkt_ann, risk_free_rate),
            "alpha": res.alpha, "alpha_pvalue": res.alpha_pvalue, "r_squared": res.r_squared,
        }
    return pd.DataFrame(rows).T


# ----------------------------------------------------------------------------- performance
def drawdowns(returns: pd.Series) -> pd.Series:
    """Drawdown from running peak of the compounded wealth curve (≤ 0)."""
    wealth = (1 + returns.fillna(0)).cumprod()
    return wealth / wealth.cummax() - 1


def max_drawdown(returns: pd.Series) -> float:
    return float(drawdowns(returns).min())


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0,
                 periods_per_year: int = 252) -> float:
    ex = returns - risk_free_rate / periods_per_year
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else np.nan


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0,
                  periods_per_year: int = 252) -> float:
    ex = returns - risk_free_rate / periods_per_year
    downside = np.sqrt(np.mean(np.minimum(ex, 0) ** 2))
    return float(ex.mean() / downside * np.sqrt(periods_per_year)) if downside > 0 else np.nan


def performance_summary(
    returns: pd.DataFrame | pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """Standard performance table: CAGR, vol, Sharpe, Sortino, max drawdown, Calmar,
    skew, excess kurtosis, best/worst period, hit rate."""
    df = returns.to_frame() if isinstance(returns, pd.Series) else returns
    out = {}
    for col in df.columns:
        r = df[col].dropna()
        years = len(r) / periods_per_year
        total = float((1 + r).prod())
        cagr = total ** (1 / years) - 1 if years > 0 and total > 0 else np.nan
        mdd = max_drawdown(r)
        out[col] = {
            "Total return": total - 1,
            "CAGR": cagr,
            "Volatility": r.std(ddof=1) * np.sqrt(periods_per_year),
            "Sharpe": sharpe_ratio(r, risk_free_rate, periods_per_year),
            "Sortino": sortino_ratio(r, risk_free_rate, periods_per_year),
            "Max drawdown": mdd,
            "Calmar": cagr / abs(mdd) if mdd < 0 else np.nan,
            "Skewness": float(stats.skew(r)),
            "Excess kurtosis": float(stats.kurtosis(r)),
            "Best period": r.max(),
            "Worst period": r.min(),
            "Hit rate": float((r > 0).mean()),
            "Observations": len(r),
        }
    return pd.DataFrame(out)
