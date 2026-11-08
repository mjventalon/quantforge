r"""Mean-variance portfolio construction (Markowitz, 1952) and extensions.

All optimizers take **annualized** expected returns ``mu`` (length *n*) and an
annualized covariance matrix ``cov`` (*n × n*), as NumPy arrays or pandas
objects. Use :func:`estimate_inputs` to build them from a returns frame.

Constraints supported everywhere: long-only or bounded weights
(``bounds=(lo, hi)``, per-asset bounds allowed) and full investment
(weights sum to 1).

References
----------
Markowitz, H. (1952). Portfolio Selection. *Journal of Finance*, 7(1).
Ledoit, O. & Wolf, M. (2004). A well-conditioned estimator for large-dimensional
covariance matrices. *Journal of Multivariate Analysis*, 88(2).
Maillard, S., Roncalli, T. & Teïletche, J. (2010). The Properties of Equally
Weighted Risk Contribution Portfolios. *Journal of Portfolio Management*, 36(4).
He, G. & Litterman, R. (1999). The Intuition Behind Black-Litterman Model Portfolios.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

__all__ = [
    "PortfolioResult",
    "estimate_inputs",
    "ledoit_wolf_shrinkage",
    "min_variance",
    "max_sharpe",
    "efficient_return",
    "efficient_risk",
    "efficient_frontier",
    "risk_parity",
    "risk_contributions",
    "black_litterman",
    "implied_equilibrium_returns",
]

Bounds = tuple[float, float] | Sequence[tuple[float, float]]


@dataclass(frozen=True)
class PortfolioResult:
    """Optimal weights and their ex-ante statistics (annualized)."""

    weights: pd.Series
    expected_return: float
    volatility: float
    sharpe: float
    risk_free_rate: float = 0.0
    method: str = ""
    extra: dict = field(default_factory=dict)

    def __str__(self) -> str:
        w = ", ".join(f"{k}: {v:.1%}" for k, v in self.weights.items() if abs(v) > 1e-4)
        return (f"{self.method}: return {self.expected_return:.2%}, vol {self.volatility:.2%}, "
                f"Sharpe {self.sharpe:.3f} | {w}")


# ----------------------------------------------------------------------------- inputs
def ledoit_wolf_shrinkage(returns: pd.DataFrame | np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage of the sample covariance toward a scaled identity.

    Returns the shrunk (per-period) covariance and the shrinkage intensity in [0, 1].
    """
    x = np.asarray(returns, dtype=float)
    t, n = x.shape
    x = x - x.mean(axis=0)
    s = x.T @ x / t
    mu = np.trace(s) / n
    target = mu * np.eye(n)
    d2 = np.sum((s - target) ** 2)
    b2 = sum(np.sum((np.outer(row, row) - s) ** 2) for row in x) / t**2
    b2 = min(b2, d2)
    delta = 0.0 if d2 == 0 else b2 / d2
    shrunk = delta * target + (1 - delta) * s
    return shrunk * t / (t - 1), float(delta)


def estimate_inputs(
    returns: pd.DataFrame,
    periods_per_year: int = 252,
    method: Literal["historical", "ewma", "ledoit_wolf"] = "ledoit_wolf",
    ewma_halflife: float = 63.0,
) -> tuple[pd.Series, pd.DataFrame]:
    """Annualized expected returns and covariance from periodic simple returns.

    ``method`` selects the covariance estimator; expected returns are the
    arithmetic mean (``historical``/``ledoit_wolf``) or EWMA mean (``ewma``).
    """
    r = returns.dropna()
    if len(r) < r.shape[1] + 2:
        raise ValueError("not enough observations for the number of assets")
    cols = r.columns
    if method == "historical":
        mu = r.mean()
        cov = r.cov()
    elif method == "ledoit_wolf":
        mu = r.mean()
        cov = pd.DataFrame(ledoit_wolf_shrinkage(r)[0], index=cols, columns=cols)
    elif method == "ewma":
        mu = r.ewm(halflife=ewma_halflife).mean().iloc[-1]
        cov = r.ewm(halflife=ewma_halflife).cov().iloc[-len(cols):]
        cov.index = cols
    else:
        raise ValueError(f"unknown method {method!r}")
    return mu * periods_per_year, cov * periods_per_year


def _prep(mu: object, cov: object) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if isinstance(cov, pd.DataFrame):
        names = [str(c) for c in cov.columns]
    elif isinstance(mu, pd.Series):
        names = [str(i) for i in mu.index]
    else:
        names = [f"asset_{i}" for i in range(np.asarray(cov).shape[0])]
    m = np.asarray(mu, dtype=float).ravel()
    c = np.asarray(cov, dtype=float)
    if c.shape != (m.size, m.size):
        raise ValueError("cov must be n x n with n = len(mu)")
    c = 0.5 * (c + c.T)
    return m, c, names


def _bounds(bounds: Bounds, n: int) -> list[tuple[float, float]]:
    if len(bounds) == 2 and np.isscalar(bounds[0]):
        return [tuple(map(float, bounds))] * n  # type: ignore[list-item]
    b = [tuple(map(float, x)) for x in bounds]  # type: ignore[union-attr]
    if len(b) != n:
        raise ValueError("need one (lo, hi) pair per asset")
    return b  # type: ignore[return-value]


def _solve(objective, n: int, bounds: Bounds, extra_cons: list | None = None,
           x0: np.ndarray | None = None) -> np.ndarray:
    b = _bounds(bounds, n)
    lo = np.array([x[0] for x in b])
    hi = np.array([x[1] for x in b])
    if lo.sum() > 1 + 1e-9 or hi.sum() < 1 - 1e-9:
        raise ValueError("bounds make a fully invested portfolio impossible")
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}] + (extra_cons or [])
    if x0 is None:
        x0 = np.clip(np.full(n, 1.0 / n), lo, hi)
    res = minimize(objective, x0, method="SLSQP", bounds=b, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-12})
    if not res.success:
        raise RuntimeError(f"optimization failed: {res.message}")
    w = res.x
    w[np.abs(w) < 1e-10] = 0.0
    return w / w.sum()


def _result(w: np.ndarray, m: np.ndarray, c: np.ndarray, names: list[str], rf: float,
            method: str, **extra: object) -> PortfolioResult:
    ret = float(w @ m)
    vol = float(np.sqrt(w @ c @ w))
    return PortfolioResult(pd.Series(w, index=names, name="weight"), ret, vol,
                           (ret - rf) / vol if vol > 0 else np.nan, rf, method, dict(extra))


# ----------------------------------------------------------------------------- optimizers
def min_variance(mu: object, cov: object, bounds: Bounds = (0.0, 1.0),
                 risk_free_rate: float = 0.0) -> PortfolioResult:
    """Global minimum-variance portfolio."""
    m, c, names = _prep(mu, cov)
    w = _solve(lambda w: w @ c @ w, m.size, bounds)
    return _result(w, m, c, names, risk_free_rate, "Minimum variance")


def max_sharpe(mu: object, cov: object, risk_free_rate: float = 0.0,
               bounds: Bounds = (0.0, 1.0)) -> PortfolioResult:
    """Tangency portfolio: maximizes ``(w'mu - rf) / sqrt(w'Σw)``."""
    m, c, names = _prep(mu, cov)
    if np.all(m <= risk_free_rate):
        raise ValueError("no asset has an expected return above the risk-free rate")

    def neg_sharpe(w: np.ndarray) -> float:
        vol = np.sqrt(w @ c @ w)
        return -(w @ m - risk_free_rate) / vol

    best = None
    starts = [None, np.eye(m.size)[int(np.argmax((m - risk_free_rate) / np.sqrt(np.diag(c))))]]
    for x0 in starts:
        try:
            w = _solve(neg_sharpe, m.size, bounds, x0=x0)
        except RuntimeError:
            continue
        if best is None or neg_sharpe(w) < neg_sharpe(best):
            best = w
    if best is None:
        raise RuntimeError("max Sharpe optimization failed")
    return _result(best, m, c, names, risk_free_rate, "Maximum Sharpe")


def efficient_return(mu: object, cov: object, target_return: float,
                     bounds: Bounds = (0.0, 1.0), risk_free_rate: float = 0.0) -> PortfolioResult:
    """Minimum-variance portfolio achieving ``target_return``."""
    m, c, names = _prep(mu, cov)
    cons = [{"type": "eq", "fun": lambda w: w @ m - target_return}]
    w = _solve(lambda w: w @ c @ w, m.size, bounds, cons)
    return _result(w, m, c, names, risk_free_rate, f"Target return {target_return:.2%}")


def efficient_risk(mu: object, cov: object, target_volatility: float,
                   bounds: Bounds = (0.0, 1.0), risk_free_rate: float = 0.0) -> PortfolioResult:
    """Maximum-return portfolio with volatility at most ``target_volatility``."""
    m, c, names = _prep(mu, cov)
    cons = [{"type": "ineq", "fun": lambda w: target_volatility**2 - w @ c @ w}]
    w = _solve(lambda w: -(w @ m), m.size, bounds, cons)
    return _result(w, m, c, names, risk_free_rate, f"Target vol {target_volatility:.2%}")


def efficient_frontier(mu: object, cov: object, n_points: int = 50,
                       bounds: Bounds = (0.0, 1.0)) -> pd.DataFrame:
    """Trace the efficient frontier from the min-variance portfolio to the max-return one.

    Returns a frame with ``return``, ``volatility`` and one weight column per asset.
    """
    m, c, names = _prep(mu, cov)
    gmv = min_variance(m, c, bounds)
    b = _bounds(bounds, m.size)
    # highest reachable return: fill best assets up to their upper bounds
    order = np.argsort(-m)
    w_max, left = np.array([x[0] for x in b]), 1 - sum(x[0] for x in b)
    for i in order:
        add = min(b[i][1] - w_max[i], left)
        w_max[i] += add
        left -= add
    targets = np.linspace(gmv.expected_return, float(w_max @ m), n_points)
    rows = []
    for tr in targets:
        try:
            p = efficient_return(m, c, tr, bounds)
        except RuntimeError:
            continue
        rows.append({"return": p.expected_return, "volatility": p.volatility,
                     **dict(zip(names, p.weights.values))})
    return pd.DataFrame(rows)


def risk_contributions(weights: object, cov: object) -> pd.Series:
    """Share of portfolio variance contributed by each asset (sums to 1)."""
    w = np.asarray(weights, dtype=float)
    c = np.asarray(cov, dtype=float)
    rc = w * (c @ w)
    idx = cov.columns if isinstance(cov, pd.DataFrame) else range(w.size)
    return pd.Series(rc / rc.sum(), index=idx, name="risk_contribution")


def risk_parity(cov: object, budget: Sequence[float] | None = None,
                mu: object | None = None, risk_free_rate: float = 0.0) -> PortfolioResult:
    """Equal (or budgeted) risk contribution portfolio, long-only.

    Solved with the convex formulation of Spinu (2013):
    ``min ½ y'Σy − Σ b_i ln y_i``, then ``w = y / Σy``.
    """
    c = np.asarray(cov, dtype=float)
    n = c.shape[0]
    b = np.full(n, 1.0 / n) if budget is None else np.asarray(budget, float) / np.sum(budget)
    names = [str(x) for x in cov.columns] if isinstance(cov, pd.DataFrame) else \
        [f"asset_{i}" for i in range(n)]
    y0 = 1.0 / np.sqrt(np.diag(c))
    res = minimize(lambda y: 0.5 * y @ c @ y - b @ np.log(y), y0,
                   jac=lambda y: c @ y - b / y, method="L-BFGS-B",
                   bounds=[(1e-12, None)] * n, options={"maxiter": 5000, "gtol": 1e-12})
    y = res.x
    for _ in range(50):  # Newton polish: the objective is strictly convex
        grad = c @ y - b / y
        step = np.linalg.solve(c + np.diag(b / y**2), grad)
        t = 1.0
        while np.any(y - t * step <= 0):
            t *= 0.5
        y = y - t * step
        if np.max(np.abs(step)) < 1e-14 * np.max(y):
            break
    w = y / y.sum()
    m = np.zeros(n) if mu is None else np.asarray(mu, dtype=float)
    return _result(w, m, c, names, risk_free_rate, "Risk parity",
                   risk_contributions=risk_contributions(w, c).values)


# ----------------------------------------------------------------------------- Black-Litterman
def implied_equilibrium_returns(cov: object, market_weights: object, risk_aversion: float = 2.5,
                                risk_free_rate: float = 0.0) -> pd.Series:
    """Reverse optimization: ``Π = δ Σ w_mkt`` (+ rf)."""
    c = np.asarray(cov, dtype=float)
    w = np.asarray(market_weights, dtype=float)
    pi = risk_aversion * c @ w + risk_free_rate
    idx = cov.columns if isinstance(cov, pd.DataFrame) else None
    return pd.Series(pi, index=idx, name="equilibrium_return")


def black_litterman(
    cov: object,
    market_weights: object,
    views_p: np.ndarray,
    views_q: Sequence[float],
    view_confidences: Sequence[float] | None = None,
    risk_aversion: float = 2.5,
    tau: float = 0.05,
    risk_free_rate: float = 0.0,
) -> tuple[pd.Series, pd.DataFrame]:
    """Black-Litterman posterior expected returns and covariance.

    Parameters
    ----------
    views_p
        *k × n* pick matrix (each row is a view: absolute ``[0,1,0]`` or relative ``[1,-1,0]``).
    views_q
        Expected return of each view (annualized).
    view_confidences
        Optional confidence in (0, 1] per view (Idzorek-style scaling of Ω).
        Default: Ω = diag(P τΣ P').
    """
    c = np.asarray(cov, dtype=float)
    p = np.atleast_2d(np.asarray(views_p, dtype=float))
    q = np.asarray(views_q, dtype=float)
    pi = implied_equilibrium_returns(c, market_weights, risk_aversion, 0.0).values
    ts = tau * c
    omega = np.diag(np.diag(p @ ts @ p.T))
    if view_confidences is not None:
        conf = np.clip(np.asarray(view_confidences, float), 1e-6, 1.0)
        omega = omega * (1 - conf) / conf
        omega += np.eye(len(q)) * 1e-12
    inv_ts = np.linalg.inv(ts)
    inv_om = np.linalg.inv(omega)
    post_prec = inv_ts + p.T @ inv_om @ p
    post_cov_mean = np.linalg.inv(post_prec)
    mu_bl = post_cov_mean @ (inv_ts @ pi + p.T @ inv_om @ q) + risk_free_rate
    sigma_bl = c + post_cov_mean
    idx = cov.columns if isinstance(cov, pd.DataFrame) else None
    return (pd.Series(mu_bl, index=idx, name="bl_return"),
            pd.DataFrame(sigma_bl, index=idx, columns=idx))
