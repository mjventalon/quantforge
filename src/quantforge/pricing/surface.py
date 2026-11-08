r"""Implied volatility surfaces from listed option chains.

Pipeline
--------
1. :func:`chain_implied_vols` cleans a real chain (drops zero bids, wide
   spreads, stale or far-OTM quotes), keeps out-of-the-money options and
   computes Black-Scholes implied vols from bid/ask mid prices with our own
   solver (provider-reported IVs are kept separately for comparison).
2. :func:`fit_svi` fits Gatheral's raw SVI smile to each expiry:

   .. math:: w(k) = a + b\,\big(\rho\,(k-m) + \sqrt{(k-m)^2 + \sigma^2}\big)

   where ``w = σ_imp² T`` is total implied variance and ``k = ln(K/F)``.
3. :func:`surface_grid` interpolates the SVI fits on a regular
   (log-moneyness × maturity) grid for 3-D plotting.

References
----------
Gatheral, J. (2004). A parsimonious arbitrage-free implied volatility
parameterization. Global Derivatives & Risk Management, Madrid.
Gatheral, J. & Jacquier, A. (2014). Arbitrage-free SVI volatility surfaces.
*Quantitative Finance*, 14(1).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .black_scholes import implied_volatility

__all__ = ["chain_implied_vols", "fit_svi", "svi_total_variance", "surface_grid",
           "implied_forward"]


def implied_forward(chain: pd.DataFrame, spot: float, rate: float, maturity: float) -> float:
    """Forward price implied by put-call parity at the strike nearest the money.

    ``F = K + e^{rT} (C - P)``. Falls back to ``spot * e^{rT}`` if no pair exists.
    """
    calls = chain[chain["type"] == "call"].set_index("strike")["mid"]
    puts = chain[chain["type"] == "put"].set_index("strike")["mid"]
    common = calls.index.intersection(puts.index)
    common = [k for k in common if calls[k] > 0 and puts[k] > 0]
    if not common:
        return spot * np.exp(rate * maturity)
    k = min(common, key=lambda x: abs(x - spot))
    return float(k + np.exp(rate * maturity) * (calls[k] - puts[k]))


def chain_implied_vols(
    chain: pd.DataFrame,
    spot: float,
    rate: float,
    dividend_yield: float = 0.0,
    min_days: int = 2,
    moneyness: tuple[float, float] = (0.6, 1.6),
    max_rel_spread: float = 0.5,
    otm_only: bool = True,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Compute implied vols for a cleaned option chain.

    Returns the input rows that passed the filters, with added columns
    ``T`` (years), ``forward``, ``log_moneyness`` (ln K/F), ``iv`` (ours) and
    ``provider_iv`` (as reported).
    """
    df = chain.copy()
    today = pd.Timestamp(as_of or date.today())
    df["days"] = (pd.to_datetime(df["expiry"]) - today).dt.days
    if "mid" not in df:
        df["mid"] = 0.5 * (df["bid"] + df["ask"])
    df = df[(df["days"] >= min_days) & (df["bid"] > 0) & (df["ask"] >= df["bid"])]
    df = df[(df["ask"] - df["bid"]) / df["mid"] <= max_rel_spread]
    df = df[(df["strike"] >= moneyness[0] * spot) & (df["strike"] <= moneyness[1] * spot)]
    out = []
    for _, g in df.groupby("expiry"):
        t = g["days"].iloc[0] / 365.0
        fwd = implied_forward(g, spot, rate, t)
        q_eff = rate - np.log(fwd / spot) / t  # carry implied by parity (dividends, borrow)
        if otm_only:
            g = g[((g["type"] == "call") & (g["strike"] >= fwd)) |
                  ((g["type"] == "put") & (g["strike"] < fwd))]
        for _, row in g.iterrows():
            try:
                iv = implied_volatility(row["mid"], spot, row["strike"], t, rate, row["type"],
                                        q_eff if np.isfinite(q_eff) else dividend_yield)
            except ValueError:
                continue
            if not 0.01 < iv < 4.0:
                continue
            out.append({**row.to_dict(), "T": t, "forward": fwd,
                        "log_moneyness": float(np.log(row["strike"] / fwd)), "iv": float(iv),
                        "provider_iv": row.get("implied_vol")})
    if not out:
        raise ValueError("no option passed the quality filters")
    return pd.DataFrame(out).sort_values(["T", "strike"]).reset_index(drop=True)


def svi_total_variance(k: np.ndarray, a: float, b: float, rho: float, m: float,
                       sigma: float) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma**2))


def fit_svi(slice_df: pd.DataFrame, weights: str | None = "vega") -> dict[str, float]:
    """Fit raw SVI to one expiry (columns ``log_moneyness``, ``iv``, ``T``).

    Constraints keep the slice free of butterfly arbitrage at first order:
    ``b ≥ 0``, ``|ρ| < 1``, ``σ > 0`` and ``a + bσ√(1-ρ²) ≥ 0``.
    """
    k = slice_df["log_moneyness"].to_numpy()
    t = float(slice_df["T"].iloc[0])
    w = slice_df["iv"].to_numpy() ** 2 * t
    if k.size < 5:
        raise ValueError("need at least 5 quotes to fit SVI")
    wt = np.exp(-0.5 * (k / 0.25) ** 2) + 0.1 if weights == "vega" else np.ones_like(k)

    def loss(x: np.ndarray) -> float:
        return float(np.sum(wt * (svi_total_variance(k, *x) - w) ** 2))

    x0 = np.array([max(w.min() * 0.9, 1e-4), 0.1, -0.3, 0.0, 0.1])
    bounds = [(-1.0, max(w.max(), 1e-3)), (1e-6, 5.0), (-0.999, 0.999),
              (k.min() - 1, k.max() + 1), (1e-4, 5.0)]
    cons = [{"type": "ineq", "fun": lambda x: x[0] + x[1] * x[4] * np.sqrt(1 - x[2] ** 2)}]
    best = None
    for rho0 in (-0.6, -0.3, 0.0):
        x0[2] = rho0
        res = minimize(loss, x0, method="SLSQP", bounds=bounds, constraints=cons,
                       options={"maxiter": 2000, "ftol": 1e-14})
        if best is None or res.fun < best.fun:
            best = res
    a, b, rho, m, sig = best.x
    fitted = np.sqrt(np.maximum(svi_total_variance(k, *best.x), 1e-12) / t)
    rmse = float(np.sqrt(np.mean((fitted - slice_df["iv"].to_numpy()) ** 2)))
    return {"a": a, "b": b, "rho": rho, "m": m, "sigma": sig, "T": t, "rmse_vol": rmse}


def surface_grid(
    ivs: pd.DataFrame,
    k_range: tuple[float, float] = (-0.4, 0.4),
    n_k: int = 41,
    min_quotes: int = 5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    """SVI-smoothed implied vol surface.

    Returns ``(k_grid, T_grid, iv_matrix[len(T), len(k)], svi_params)``. Between
    expiries total variance is interpolated linearly in T (calendar-consistent).
    """
    params = []
    for _, g in ivs.groupby("T"):
        if len(g) < min_quotes:
            continue
        try:
            params.append(fit_svi(g))
        except ValueError:
            continue
    if len(params) < 2:
        raise ValueError("need at least two expiries with enough quotes")
    p = pd.DataFrame(params).sort_values("T").reset_index(drop=True)
    k_grid = np.linspace(*k_range, n_k)
    t_nodes = p["T"].to_numpy()
    w_nodes = np.array([svi_total_variance(k_grid, r.a, r.b, r.rho, r.m, r.sigma)
                        for r in p.itertuples()])
    w_nodes = np.maximum.accumulate(np.maximum(w_nodes, 1e-8), axis=0)  # no calendar arbitrage
    t_grid = np.linspace(t_nodes[0], t_nodes[-1], 30)
    w_grid = np.array([[np.interp(t, t_nodes, w_nodes[:, j]) for j in range(n_k)]
                       for t in t_grid])
    iv = np.sqrt(w_grid / t_grid[:, None])
    return k_grid, t_grid, iv, p
