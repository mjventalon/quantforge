r"""GARCH-family volatility models estimated by maximum likelihood.

Model (GJR-GARCH(1,1); plain GARCH(1,1) when ``asymmetric=False``):

.. math::
    r_t = \mu + \varepsilon_t,\quad \varepsilon_t = \sigma_t z_t,\\
    \sigma_t^2 = \omega + (\alpha + \gamma\,\mathbb 1_{\varepsilon_{t-1}<0})\,
                 \varepsilon_{t-1}^2 + \beta\,\sigma_{t-1}^2

with ``z_t`` standard normal or standardized Student-t.

Returns are internally scaled to percent for numerical stability; reported
``omega`` and volatilities are converted back to decimal units.

References
----------
Bollerslev, T. (1986). Generalized Autoregressive Conditional Heteroskedasticity.
*Journal of Econometrics*, 31(3).
Glosten, L., Jagannathan, R. & Runkle, D. (1993). On the Relation between the
Expected Value and the Volatility of the Nominal Excess Return on Stocks.
*Journal of Finance*, 48(5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.special import gammaln

from ._numdiff import standard_errors

__all__ = ["GARCHResult", "fit_garch"]


@dataclass
class GARCHResult:
    """Fitted GARCH model."""

    params: pd.Series
    std_errors: pd.Series
    loglik: float
    aic: float
    bic: float
    conditional_vol: pd.Series      # per-period, decimal
    std_residuals: pd.Series
    distribution: str
    asymmetric: bool
    periods_per_year: int = 252
    _last_eps: float = field(default=0.0, repr=False)
    _last_var: float = field(default=0.0, repr=False)

    @property
    def persistence(self) -> float:
        p = self.params
        return float(p["alpha"] + p["beta"] + 0.5 * p.get("gamma", 0.0))

    @property
    def half_life(self) -> float:
        """Periods for a volatility shock to decay by half."""
        ph = self.persistence
        return float(np.log(0.5) / np.log(ph)) if 0 < ph < 1 else np.inf

    @property
    def long_run_vol(self) -> float:
        """Unconditional annualized volatility."""
        ph = self.persistence
        if ph >= 1:
            return np.inf
        return float(np.sqrt(self.params["omega"] / (1 - ph) * self.periods_per_year))

    def summary(self) -> pd.DataFrame:
        t = self.params / self.std_errors
        return pd.DataFrame({
            "estimate": self.params, "std_error": self.std_errors, "t_stat": t,
            "p_value": 2 * stats.norm.sf(np.abs(t)),
        })

    def forecast(self, horizon: int = 21) -> pd.DataFrame:
        """Variance forecasts for 1..horizon steps ahead.

        Returns per-period and annualized vol, plus the annualized vol of the
        cumulative return over the next h periods (for option pricing / VaR).
        """
        p = self.params
        ph = self.persistence
        omega = p["omega"]
        g = p.get("gamma", 0.0)
        eps2 = self._last_eps**2
        neg = 1.0 if self._last_eps < 0 else 0.0
        var1 = omega + (p["alpha"] + g * neg) * eps2 + p["beta"] * self._last_var
        lr = omega / (1 - ph) if ph < 1 else var1
        h = np.arange(1, horizon + 1)
        var_h = lr + ph ** (h - 1) * (var1 - lr)
        cum = np.cumsum(var_h)
        return pd.DataFrame({
            "vol": np.sqrt(var_h),
            "vol_annualized": np.sqrt(var_h * self.periods_per_year),
            "term_vol_annualized": np.sqrt(cum / h * self.periods_per_year),
        }, index=pd.Index(h, name="horizon"))


def _filter(params: np.ndarray, eps: np.ndarray, asym: bool, var0: float) -> np.ndarray:
    omega, alpha, beta = params[0], params[1], params[2]
    gamma = params[3] if asym else 0.0
    n = eps.size
    sig2 = np.empty(n)
    sig2[0] = var0
    for t in range(1, n):
        e = eps[t - 1]
        sig2[t] = omega + (alpha + (gamma if e < 0 else 0.0)) * e * e + beta * sig2[t - 1]
    return sig2


def fit_garch(
    returns: pd.Series | np.ndarray,
    distribution: Literal["normal", "t"] = "normal",
    asymmetric: bool = False,
    mean: Literal["constant", "zero"] = "constant",
    periods_per_year: int = 252,
) -> GARCHResult:
    """Fit GARCH(1,1) or GJR-GARCH(1,1) by maximum likelihood.

    Parameters
    ----------
    returns
        Periodic simple or log returns in **decimal** (0.01 = 1%).
    distribution
        ``"normal"`` or ``"t"`` (estimates degrees of freedom ``nu``).
    asymmetric
        Add the GJR leverage term ``gamma``.
    """
    s = pd.Series(returns).dropna()
    if len(s) < 100:
        raise ValueError("need at least 100 observations to fit a GARCH model")
    y = s.to_numpy(dtype=float) * 100.0
    n = y.size
    var0 = float(np.var(y))
    use_t = distribution == "t"

    names = (["mu"] if mean == "constant" else []) + ["omega", "alpha", "beta"]
    names += ["gamma"] if asymmetric else []
    names += ["nu"] if use_t else []

    def unpack(x: np.ndarray) -> tuple[float, np.ndarray, float]:
        i = 0
        mu = 0.0
        if mean == "constant":
            mu = x[0]
            i = 1
        k = 4 if asymmetric else 3
        g = x[i:i + k]
        nu = x[i + k] if use_t else np.inf
        return mu, g, nu

    def nll(x: np.ndarray) -> float:
        mu, g, nu = unpack(x)
        eps = y - mu
        sig2 = _filter(g, eps, asymmetric, var0)
        if np.any(sig2 <= 0) or not np.all(np.isfinite(sig2)):
            return 1e12
        if use_t:
            c = gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2))
            ll = c - 0.5 * np.log(sig2) - (nu + 1) / 2 * np.log1p(eps**2 / (sig2 * (nu - 2)))
        else:
            ll = -0.5 * (np.log(2 * np.pi) + np.log(sig2) + eps**2 / sig2)
        return float(-ll.sum())

    x0 = [float(y.mean())] if mean == "constant" else []
    bounds = [(-10 * abs(y.mean()) - 1, 10 * abs(y.mean()) + 1)] if mean == "constant" else []
    # starting point: omega, alpha, beta (, gamma)
    x0 += [0.05 * var0, 0.03, 0.88, 0.08] if asymmetric else [0.05 * var0, 0.08, 0.88]
    bounds += [(1e-8, 10 * var0), (0.0, 1.0), (0.0, 1.0)]
    if asymmetric:
        bounds += [(0.0, 1.0)]
    if use_t:
        x0 += [8.0]
        bounds += [(2.05, 200.0)]
    off = 1 if mean == "constant" else 0

    def stationarity(x: np.ndarray) -> float:
        a, b = x[off + 1], x[off + 2]
        g = x[off + 3] if asymmetric else 0.0
        return 0.99999 - (a + b + 0.5 * g)

    res = minimize(nll, np.array(x0), method="SLSQP", bounds=bounds,
                   constraints=[{"type": "ineq", "fun": stationarity}],
                   options={"maxiter": 2000, "ftol": 1e-10})
    x = res.x
    se = standard_errors(nll, x)
    mu, g, nu = unpack(x)
    eps = y - mu
    sig2 = _filter(g, eps, asymmetric, var0)

    # convert back to decimal units
    scale = np.ones(len(names))
    if mean == "constant":
        scale[0] = 0.01
    scale[off] = 1e-4  # omega is a variance
    params = pd.Series(x * scale, index=names)
    ses = pd.Series(se * scale, index=names)
    loglik = -res.fun + n * np.log(100.0)  # Jacobian of the scaling
    k = len(names)
    idx = s.index
    return GARCHResult(
        params=params, std_errors=ses, loglik=float(loglik),
        aic=float(2 * k - 2 * loglik), bic=float(k * np.log(n) - 2 * loglik),
        conditional_vol=pd.Series(np.sqrt(sig2) / 100.0, index=idx, name="sigma"),
        std_residuals=pd.Series(eps / np.sqrt(sig2), index=idx, name="z"),
        distribution=distribution, asymmetric=asymmetric, periods_per_year=periods_per_year,
        _last_eps=float(eps[-1] / 100.0), _last_var=float(sig2[-1] / 1e4),
    )
