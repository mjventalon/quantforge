r"""ARMA(p, q) models by conditional maximum likelihood, order selection and
stationarity tests.

.. math::
    y_t = c + \sum_{i=1}^p \phi_i y_{t-i} + \varepsilon_t
          + \sum_{j=1}^q \theta_j \varepsilon_{t-j}

Estimation conditions on the first ``p`` observations and on pre-sample
innovations equal to zero (Box-Jenkins conditional sum of squares), which is
asymptotically equivalent to exact MLE.

References
----------
Box, G., Jenkins, G., Reinsel, G. & Ljung, G. (2015). *Time Series Analysis:
Forecasting and Control*, 5th ed. Wiley.
Hamilton, J. (1994). *Time Series Analysis*. Princeton.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

from ._numdiff import standard_errors

__all__ = ["ARMAResult", "fit_arma", "select_arma_order", "adf_test", "ljung_box", "acf", "pacf"]


@dataclass
class ARMAResult:
    order: tuple[int, int]
    params: pd.Series
    std_errors: pd.Series
    sigma2: float
    loglik: float
    aic: float
    bic: float
    residuals: pd.Series
    fitted: pd.Series
    _y: np.ndarray
    _eps: np.ndarray

    @property
    def ar(self) -> np.ndarray:
        return self.params[[f"ar{i + 1}" for i in range(self.order[0])]].to_numpy()

    @property
    def ma(self) -> np.ndarray:
        return self.params[[f"ma{j + 1}" for j in range(self.order[1])]].to_numpy()

    @property
    def is_stationary(self) -> bool:
        if self.order[0] == 0:
            return True
        roots = np.roots(np.r_[1, -self.ar][::-1])
        return bool(np.all(np.abs(roots) > 1))

    def summary(self) -> pd.DataFrame:
        t = self.params / self.std_errors
        return pd.DataFrame({"estimate": self.params, "std_error": self.std_errors,
                             "t_stat": t, "p_value": 2 * stats.norm.sf(np.abs(t))})

    def forecast(self, steps: int = 10, alpha: float = 0.05) -> pd.DataFrame:
        """Point forecasts and (1-alpha) prediction intervals."""
        p, q = self.order
        c = self.params["const"]
        phi, theta = self.ar, self.ma
        y = list(self._y[-p:]) if p else []
        e = list(self._eps[-q:]) if q else []
        out = []
        for h in range(steps):
            val = c + sum(phi[i] * y[-1 - i] for i in range(p))
            val += sum(theta[j] * e[-1 - j] for j in range(q) if j - h >= 0)
            out.append(val)
            if p:
                y.append(val)
            if q:
                e.append(0.0)
        # psi weights for forecast variance
        psi = np.zeros(steps)
        psi[0] = 1.0
        for k in range(1, steps):
            s = theta[k - 1] if k - 1 < q else 0.0
            s += sum(phi[i] * psi[k - 1 - i] for i in range(min(p, k)))
            psi[k] = s
        se = np.sqrt(self.sigma2 * np.cumsum(psi**2))
        z = stats.norm.ppf(1 - alpha / 2)
        mean = np.array(out)
        return pd.DataFrame({"mean": mean, "lower": mean - z * se, "upper": mean + z * se,
                             "std_error": se}, index=pd.Index(range(1, steps + 1), name="step"))


def _residuals(params: np.ndarray, y: np.ndarray, p: int, q: int) -> np.ndarray:
    c, phi, theta = params[0], params[1:1 + p], params[1 + p:1 + p + q]
    n = y.size
    eps = np.zeros(n)
    for t in range(p, n):
        pred = c
        for i in range(p):
            pred += phi[i] * y[t - 1 - i]
        for j in range(q):
            if t - 1 - j >= p:
                pred += theta[j] * eps[t - 1 - j]
        eps[t] = y[t] - pred
    return eps


def fit_arma(series: pd.Series | np.ndarray, p: int = 1, q: int = 0) -> ARMAResult:
    """Fit ARMA(p, q) with a constant by conditional Gaussian MLE."""
    s = pd.Series(series).dropna()
    y = s.to_numpy(dtype=float)
    n = y.size
    if n < 10 + 2 * (p + q):
        raise ValueError("series too short for this order")
    m = n - p

    def css(x: np.ndarray) -> float:
        if q and np.any(np.abs(np.roots(np.r_[x[1 + p:][::-1], 1.0])) <= 1.0):
            return 1e300  # non-invertible MA polynomial
        with np.errstate(all="ignore"):
            e = _residuals(x, y, p, q)[p:]
            val = float(e @ e)
        return val if np.isfinite(val) else 1e300

    # start: OLS AR fit for AR part, zeros for MA
    x0 = np.zeros(1 + p + q)
    x0[0] = y.mean()
    if p:
        X = np.column_stack([np.ones(m)] + [y[p - 1 - i:n - 1 - i] for i in range(p)])
        beta, *_ = np.linalg.lstsq(X, y[p:], rcond=None)
        x0[:1 + p] = beta
    res = minimize(css, x0, method="L-BFGS-B",
                   bounds=[(None, None)] + [(-0.9999, 0.9999)] * (p + q))
    x = res.x
    sigma2 = css(x) / m

    se = standard_errors(lambda z: 0.5 * css(z) / sigma2, x)
    eps = _residuals(x, y, p, q)
    loglik = -0.5 * m * (np.log(2 * np.pi * sigma2) + 1)
    k = 2 + p + q
    names = ["const"] + [f"ar{i + 1}" for i in range(p)] + [f"ma{j + 1}" for j in range(q)]
    idx = s.index
    resid = pd.Series(eps, index=idx).iloc[p:]
    return ARMAResult(
        order=(p, q), params=pd.Series(x, index=names), std_errors=pd.Series(se, index=names),
        sigma2=float(sigma2), loglik=float(loglik), aic=float(2 * k - 2 * loglik),
        bic=float(k * np.log(m) - 2 * loglik), residuals=resid,
        fitted=pd.Series(y, index=idx).iloc[p:] - resid, _y=y, _eps=eps,
    )


def select_arma_order(series: pd.Series | np.ndarray, max_p: int = 3, max_q: int = 3,
                      criterion: str = "bic") -> tuple[ARMAResult, pd.DataFrame]:
    """Grid-search (p, q) by AIC or BIC. Returns the best fit and the full table."""
    rows, best = [], None
    for p in range(max_p + 1):
        for q in range(max_q + 1):
            try:
                r = fit_arma(series, p, q)
            except (ValueError, np.linalg.LinAlgError):
                continue
            rows.append({"p": p, "q": q, "aic": r.aic, "bic": r.bic})
            if best is None or getattr(r, criterion) < getattr(best, criterion):
                best = r
    if best is None:
        raise RuntimeError("no ARMA model could be fitted")
    return best, pd.DataFrame(rows).sort_values(criterion).reset_index(drop=True)


def acf(x: pd.Series | np.ndarray, nlags: int = 20) -> np.ndarray:
    """Sample autocorrelation function, lags 0..nlags."""
    y = np.asarray(pd.Series(x).dropna(), dtype=float)
    y = y - y.mean()
    denom = y @ y
    return np.array([1.0] + [float(y[k:] @ y[:-k] / denom) for k in range(1, nlags + 1)])


def pacf(x: pd.Series | np.ndarray, nlags: int = 20) -> np.ndarray:
    """Partial autocorrelation via Durbin-Levinson recursion."""
    r = acf(x, nlags)
    out = np.zeros(nlags + 1)
    out[0] = 1.0
    phi_prev = np.zeros(0)
    for k in range(1, nlags + 1):
        if k == 1:
            phi_kk = r[1]
            phi = np.array([phi_kk])
        else:
            num = r[k] - phi_prev @ r[1:k][::-1]
            den = 1 - phi_prev @ r[1:k]
            phi_kk = num / den
            phi = np.r_[phi_prev - phi_kk * phi_prev[::-1], phi_kk]
        out[k] = phi_kk
        phi_prev = phi
    return out


def ljung_box(residuals: pd.Series | np.ndarray, lags: int = 10,
              dof: int = 0) -> tuple[float, float]:
    """Ljung-Box Q statistic and p-value for residual autocorrelation."""
    y = np.asarray(pd.Series(residuals).dropna(), dtype=float)
    n = y.size
    r = acf(y, lags)[1:]
    qstat = n * (n + 2) * np.sum(r**2 / (n - np.arange(1, lags + 1)))
    return float(qstat), float(stats.chi2.sf(qstat, lags - dof))


# MacKinnon (2010) response-surface coefficients, constant-only regression
_MACKINNON_C = {0.01: (-3.43035, -6.5393, -16.786, -79.433),
                0.05: (-2.86154, -2.8903, -4.234, -40.040),
                0.10: (-2.56677, -1.5384, -2.809, 0.0)}


def _adf_regression(y: np.ndarray, lag: int, start: int, regression: str) -> tuple:
    dy = np.diff(y)
    rows = dy.size - start
    cols = ([np.ones(rows)] if regression == "c" else []) + [y[start:-1]]
    cols += [dy[start - i:dy.size - i] for i in range(1, lag + 1)]
    X = np.column_stack(cols)
    Y = dy[start:]
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    k = 1 if regression == "c" else 0
    s2 = resid @ resid / (rows - X.shape[1])
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[k, k])
    aic = rows * np.log(resid @ resid / rows) + 2 * X.shape[1]
    return beta[k] / se, aic, rows


def _adf_core(y: np.ndarray, max_lags: int | None = None,
              regression: str = "c") -> tuple[float, int, int]:
    """ADF t-statistic with AIC lag selection (same procedure as statsmodels' adfuller):
    lags are compared on a common sample, then the chosen lag is refit on all data."""
    y = np.asarray(y, dtype=float)
    y = y[np.isfinite(y)]
    n = y.size
    max_lags = max_lags if max_lags is not None else int(np.ceil(12 * (n / 100) ** 0.25))
    max_lags = min(max_lags, n // 2 - 3)
    best_lag = min(range(max_lags + 1),
                   key=lambda lag: _adf_regression(y, lag, max_lags, regression)[1])
    stat, _, nobs = _adf_regression(y, best_lag, best_lag, regression)
    return float(stat), best_lag, nobs


def adf_test(series: pd.Series | np.ndarray, max_lags: int | None = None) -> dict[str, object]:
    """Augmented Dickey-Fuller unit-root test (constant, lag order by AIC).

    Returns the statistic, chosen lag, MacKinnon critical values and, if
    ``statsmodels`` is installed, the MacKinnon approximate p-value.
    """
    stat, lag, nobs = _adf_core(np.asarray(pd.Series(series).dropna(), dtype=float), max_lags)
    crit = {f"{int(k * 100)}%": c[0] + c[1] / nobs + c[2] / nobs**2 + c[3] / nobs**3
            for k, c in _MACKINNON_C.items()}
    out: dict[str, object] = {"statistic": float(stat), "lags": lag, "n_obs": nobs,
                              "critical_values": crit,
                              "stationary_5pct": bool(stat < crit["5%"])}
    try:
        from statsmodels.tsa.adfvalues import mackinnonp
        out["p_value"] = float(mackinnonp(stat, regression="c", N=1))
    except ImportError:
        out["p_value"] = None
    return out
