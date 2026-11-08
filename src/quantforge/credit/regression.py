"""Linear and logistic regression with full inference, built for credit modelling.

* :func:`ols` — ordinary least squares with classical or heteroskedasticity-
  robust (HC1 / White) standard errors.
* :func:`logistic_regression` — binary logit by Newton-Raphson / IRLS, with
  standard errors, z-tests, odds ratios, McFadden pseudo-R² and optional L2
  penalty. Predicts probabilities of default (PD).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

__all__ = ["OLSResult", "LogitResult", "ols", "logistic_regression"]


def _design(X: pd.DataFrame | np.ndarray, add_const: bool) -> tuple[np.ndarray, list[str]]:
    if isinstance(X, pd.Series):
        X = X.to_frame()
    if isinstance(X, pd.DataFrame):
        names = [str(c) for c in X.columns]
        A = X.to_numpy(dtype=float)
    else:
        A = np.asarray(X, dtype=float)
        if A.ndim == 1:
            A = A[:, None]
        names = [f"x{i + 1}" for i in range(A.shape[1])]
    if add_const:
        A = np.column_stack([np.ones(A.shape[0]), A])
        names = ["const"] + names
    return A, names


@dataclass
class OLSResult:
    params: pd.Series
    std_errors: pd.Series
    t_stats: pd.Series
    p_values: pd.Series
    r_squared: float
    adj_r_squared: float
    f_stat: float
    f_pvalue: float
    sigma: float
    n_obs: int
    residuals: np.ndarray
    cov_type: str

    def summary(self) -> pd.DataFrame:
        ci = stats.t.ppf(0.975, self.n_obs - len(self.params)) * self.std_errors
        return pd.DataFrame({"coef": self.params, "std_err": self.std_errors, "t": self.t_stats,
                             "p_value": self.p_values, "ci_low": self.params - ci,
                             "ci_high": self.params + ci})

    def predict(self, X: pd.DataFrame | np.ndarray, add_const: bool = True) -> np.ndarray:
        A, _ = _design(X, add_const)
        return A @ self.params.to_numpy()


def ols(y: pd.Series | np.ndarray, X: pd.DataFrame | np.ndarray, add_const: bool = True,
        cov_type: str = "nonrobust") -> OLSResult:
    """Ordinary least squares. ``cov_type``: ``"nonrobust"`` or ``"HC1"``."""
    A, names = _design(X, add_const)
    yv = np.asarray(y, dtype=float).ravel()
    mask = np.isfinite(yv) & np.all(np.isfinite(A), axis=1)
    A, yv = A[mask], yv[mask]
    n, k = A.shape
    beta, *_ = np.linalg.lstsq(A, yv, rcond=None)
    resid = yv - A @ beta
    dof = n - k
    sse = resid @ resid
    xtx_inv = np.linalg.inv(A.T @ A)
    if cov_type == "nonrobust":
        cov = sse / dof * xtx_inv
    elif cov_type.upper() == "HC1":
        meat = A.T @ (A * resid[:, None] ** 2)
        cov = n / dof * xtx_inv @ meat @ xtx_inv
    else:
        raise ValueError("cov_type must be 'nonrobust' or 'HC1'")
    se = np.sqrt(np.diag(cov))
    t = beta / se
    sst = np.sum((yv - yv.mean()) ** 2) if add_const else yv @ yv
    r2 = 1 - sse / sst
    k_reg = k - 1 if add_const else k
    adj = 1 - (1 - r2) * (n - 1) / dof
    f = (r2 / k_reg) / ((1 - r2) / dof) if k_reg > 0 else np.nan
    return OLSResult(
        params=pd.Series(beta, index=names), std_errors=pd.Series(se, index=names),
        t_stats=pd.Series(t, index=names),
        p_values=pd.Series(2 * stats.t.sf(np.abs(t), dof), index=names),
        r_squared=float(r2), adj_r_squared=float(adj), f_stat=float(f),
        f_pvalue=float(stats.f.sf(f, k_reg, dof)) if k_reg > 0 else np.nan,
        sigma=float(np.sqrt(sse / dof)), n_obs=n, residuals=resid, cov_type=cov_type,
    )


@dataclass
class LogitResult:
    params: pd.Series
    std_errors: pd.Series
    z_stats: pd.Series
    p_values: pd.Series
    loglik: float
    loglik_null: float
    pseudo_r2: float
    aic: float
    bic: float
    n_obs: int
    converged: bool
    iterations: int
    add_const: bool

    @property
    def odds_ratios(self) -> pd.Series:
        return np.exp(self.params).rename("odds_ratio")

    def summary(self) -> pd.DataFrame:
        z = stats.norm.ppf(0.975)
        return pd.DataFrame({
            "coef": self.params, "std_err": self.std_errors, "z": self.z_stats,
            "p_value": self.p_values, "odds_ratio": self.odds_ratios,
            "ci_low": self.params - z * self.std_errors,
            "ci_high": self.params + z * self.std_errors,
        })

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Probability of the positive class (default = 1)."""
        A, _ = _design(X, self.add_const)
        return 1.0 / (1.0 + np.exp(-(A @ self.params.to_numpy())))


def logistic_regression(
    y: pd.Series | np.ndarray,
    X: pd.DataFrame | np.ndarray,
    add_const: bool = True,
    l2: float = 0.0,
    max_iter: int = 100,
    tol: float = 1e-10,
) -> LogitResult:
    """Binary logistic regression by Newton-Raphson (IRLS).

    ``y`` must be 0/1 (1 = default). ``l2`` adds a ridge penalty
    ``l2/2 * ||beta||²`` (intercept not penalized), useful under separation.
    """
    A, names = _design(X, add_const)
    yv = np.asarray(y, dtype=float).ravel()
    if not set(np.unique(yv)) <= {0.0, 1.0}:
        raise ValueError("y must contain only 0 and 1")
    mask = np.all(np.isfinite(A), axis=1)
    A, yv = A[mask], yv[mask]
    n, k = A.shape
    pen = np.full(k, l2)
    if add_const:
        pen[0] = 0.0
    beta = np.zeros(k)
    if add_const:
        pbar = np.clip(yv.mean(), 1e-6, 1 - 1e-6)
        beta[0] = np.log(pbar / (1 - pbar))
    converged = False
    it = 0
    for it in range(1, max_iter + 1):  # noqa: B007 (it is reported)
        eta = A @ beta
        p = 1 / (1 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-12, None)
        grad = A.T @ (yv - p) - pen * beta
        H = A.T @ (A * w[:, None]) + np.diag(pen)
        step = np.linalg.solve(H, grad)
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            converged = True
            break
    eta = A @ beta
    p = np.clip(1 / (1 + np.exp(-eta)), 1e-15, 1 - 1e-15)
    w = p * (1 - p)
    cov = np.linalg.inv(A.T @ (A * w[:, None]) + np.diag(pen))
    se = np.sqrt(np.diag(cov))
    ll = float(np.sum(yv * np.log(p) + (1 - yv) * np.log(1 - p)))
    pbar = np.clip(yv.mean(), 1e-15, 1 - 1e-15)
    ll0 = float(n * (pbar * np.log(pbar) + (1 - pbar) * np.log(1 - pbar)))
    z = beta / se
    return LogitResult(
        params=pd.Series(beta, index=names), std_errors=pd.Series(se, index=names),
        z_stats=pd.Series(z, index=names),
        p_values=pd.Series(2 * stats.norm.sf(np.abs(z)), index=names),
        loglik=ll, loglik_null=ll0, pseudo_r2=1 - ll / ll0 if ll0 != 0 else np.nan,
        aic=2 * k - 2 * ll, bic=k * np.log(n) - 2 * ll, n_obs=n,
        converged=converged, iterations=it, add_const=add_const,
    )
