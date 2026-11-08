r"""Value at Risk and Expected Shortfall.

Conventions
-----------
* Inputs are periodic **simple returns** (e.g. daily).
* VaR and ES are reported as **positive loss fractions**: ``var = 0.023``
  means "with probability ``confidence`` the loss will not exceed 2.3%".
* Multiply by the position value for a currency amount.
* ``horizon`` scales parametric results by ``sqrt(horizon)`` (i.i.d. assumption);
  historical results use overlapping ``horizon``-period returns.

Methods
-------
historical, parametric normal, Student-t (fitted dof), Cornish-Fisher
(skew/kurtosis-adjusted), Monte-Carlo (multivariate normal or bootstrap),
plus component/marginal VaR for portfolios.

References
----------
Jorion, P. (2006). *Value at Risk*, 3rd ed. McGraw-Hill.
Acerbi, C. & Tasche, D. (2002). On the coherence of expected shortfall.
*Journal of Banking & Finance*, 26(7).
Basel Committee (2019). Minimum capital requirements for market risk (FRTB).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "RiskEstimate",
    "historical_var",
    "parametric_var",
    "cornish_fisher_var",
    "student_t_var",
    "monte_carlo_var",
    "var_report",
    "portfolio_var_decomposition",
]

Method = Literal["historical", "normal", "student_t", "cornish_fisher", "monte_carlo"]


@dataclass(frozen=True)
class RiskEstimate:
    var: float
    es: float
    confidence: float
    horizon: int
    method: str

    def in_currency(self, position_value: float) -> tuple[float, float]:
        return self.var * position_value, self.es * position_value

    def __str__(self) -> str:
        return (f"{self.method}: {self.confidence:.1%} {self.horizon}-period "
                f"VaR {self.var:.3%}, ES {self.es:.3%}")


def _clean(returns: object) -> np.ndarray:
    r = np.asarray(returns, dtype=float).ravel()
    r = r[np.isfinite(r)]
    if r.size < 30:
        raise ValueError("need at least 30 return observations")
    return r


def _check_conf(confidence: float) -> None:
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be in (0.5, 1)")


def historical_var(returns: object, confidence: float = 0.99, horizon: int = 1) -> RiskEstimate:
    """Empirical quantile of (overlapping ``horizon``-period compounded) returns."""
    _check_conf(confidence)
    r = _clean(returns)
    if horizon > 1:
        logr = np.log1p(r)
        csum = np.concatenate([[0.0], np.cumsum(logr)])
        r = np.expm1(csum[horizon:] - csum[:-horizon])
    q = np.quantile(r, 1 - confidence, method="lower")
    tail = r[r <= q]
    return RiskEstimate(float(-q), float(-tail.mean()), confidence, horizon, "Historical")


def parametric_var(returns: object, confidence: float = 0.99, horizon: int = 1) -> RiskEstimate:
    """Gaussian (variance-covariance) VaR/ES."""
    _check_conf(confidence)
    r = _clean(returns)
    mu, sd = r.mean() * horizon, r.std(ddof=1) * np.sqrt(horizon)
    z = stats.norm.ppf(1 - confidence)
    var = -(mu + z * sd)
    es = -(mu - sd * stats.norm.pdf(z) / (1 - confidence))
    return RiskEstimate(float(var), float(es), confidence, horizon, "Parametric normal")


def student_t_var(returns: object, confidence: float = 0.99, horizon: int = 1) -> RiskEstimate:
    """VaR/ES from a location-scale Student-t fitted by maximum likelihood."""
    _check_conf(confidence)
    r = _clean(returns)
    nu, loc, scale = stats.t.fit(r)
    nu = max(nu, 2.05)
    a = 1 - confidence
    tq = stats.t.ppf(a, nu)
    loc_h, scale_h = loc * horizon, scale * np.sqrt(horizon)
    var = -(loc_h + scale_h * tq)
    es_std = stats.t.pdf(tq, nu) / a * (nu + tq**2) / (nu - 1)
    es = -(loc_h - scale_h * es_std)
    return RiskEstimate(float(var), float(es), confidence, horizon, f"Student-t (ν={nu:.1f})")


def cornish_fisher_var(returns: object, confidence: float = 0.99,
                       horizon: int = 1) -> RiskEstimate:
    """Modified VaR using the Cornish-Fisher expansion (skewness & excess kurtosis).

    ES is computed by numerically averaging the CF quantile over the tail.
    """
    _check_conf(confidence)
    r = _clean(returns)
    mu, sd = r.mean() * horizon, r.std(ddof=1) * np.sqrt(horizon)
    s = stats.skew(r) / np.sqrt(horizon)
    k = stats.kurtosis(r) / horizon

    def cf(z: np.ndarray) -> np.ndarray:
        return (z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24
                - (2 * z**3 - 5 * z) * s**2 / 36)

    a = 1 - confidence
    var = -(mu + sd * cf(np.array(stats.norm.ppf(a))))
    us = (np.arange(2000) + 0.5) / 2000 * a
    es = -(mu + sd * cf(stats.norm.ppf(us)).mean())
    return RiskEstimate(float(var), float(es), confidence, horizon, "Cornish-Fisher")


def monte_carlo_var(
    returns: pd.DataFrame | pd.Series | np.ndarray,
    weights: np.ndarray | None = None,
    confidence: float = 0.99,
    horizon: int = 1,
    n_sims: int = 100_000,
    model: Literal["normal", "bootstrap"] = "normal",
    seed: int | None = None,
) -> RiskEstimate:
    """Monte-Carlo VaR/ES for a single asset or a weighted portfolio.

    ``model="normal"`` draws multivariate normal returns with the sample
    mean/covariance; ``"bootstrap"`` resamples historical return vectors
    (keeps fat tails and cross-correlations). Horizon returns are compounded.
    """
    _check_conf(confidence)
    x = np.asarray(returns, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    x = x[np.all(np.isfinite(x), axis=1)]
    n_assets = x.shape[1]
    w = np.ones(1) if weights is None and n_assets == 1 else np.asarray(weights, dtype=float)
    if w.size != n_assets:
        raise ValueError("weights length must match number of assets")
    rng = np.random.default_rng(seed)
    if model == "normal":
        sims = rng.multivariate_normal(x.mean(0), np.cov(x, rowvar=False).reshape(n_assets,
                                       n_assets), size=(n_sims, horizon))
    elif model == "bootstrap":
        sims = x[rng.integers(0, len(x), size=(n_sims, horizon))]
    else:
        raise ValueError("model must be 'normal' or 'bootstrap'")
    asset_h = np.prod(1 + sims, axis=1) - 1
    port = asset_h @ w
    q = np.quantile(port, 1 - confidence)
    return RiskEstimate(float(-q), float(-port[port <= q].mean()), confidence, horizon,
                        f"Monte-Carlo ({model})")


def var_report(returns: object, confidence: float = 0.99, horizon: int = 1,
               position_value: float | None = None, seed: int | None = 0) -> pd.DataFrame:
    """Compare all single-series methods side by side."""
    r = _clean(returns)
    ests = [
        historical_var(r, confidence, horizon),
        parametric_var(r, confidence, horizon),
        student_t_var(r, confidence, horizon),
        cornish_fisher_var(r, confidence, horizon),
        monte_carlo_var(r, None, confidence, horizon, model="bootstrap", seed=seed),
    ]
    df = pd.DataFrame([{"method": e.method, "VaR": e.var, "ES": e.es} for e in ests])
    if position_value is not None:
        df["VaR ($)"] = df["VaR"] * position_value
        df["ES ($)"] = df["ES"] * position_value
    return df.set_index("method")


def portfolio_var_decomposition(
    returns: pd.DataFrame,
    weights: np.ndarray | pd.Series,
    confidence: float = 0.99,
    horizon: int = 1,
) -> pd.DataFrame:
    """Parametric marginal and component VaR (Euler allocation).

    Component VaRs sum to the total portfolio (zero-mean) normal VaR.
    """
    w = np.asarray(weights, dtype=float)
    cov = returns.cov().to_numpy() * horizon
    sigma_p = np.sqrt(w @ cov @ w)
    z = -stats.norm.ppf(1 - confidence)
    marginal = z * (cov @ w) / sigma_p
    component = w * marginal
    return pd.DataFrame({
        "weight": w,
        "marginal_var": marginal,
        "component_var": component,
        "pct_of_total": component / component.sum(),
    }, index=returns.columns)
