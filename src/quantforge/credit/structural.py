r"""Structural credit models: Merton (1974) distance to default and Altman Z-score.

Merton treats equity as a call option on the firm's assets ``V`` struck at the
face value of debt ``D`` due at ``T``:

.. math:: E = V N(d_1) - D e^{-rT} N(d_2),\qquad
          \sigma_E E = N(d_1)\,\sigma_V V

Given observed equity value ``E`` and equity volatility ``σ_E`` the two
equations are solved jointly for the unobservable ``V`` and ``σ_V``. The
risk-neutral PD is ``N(-d_2)``; the distance to default ``DD = d_2``.

Following the KMV convention, the default point is commonly set to
short-term debt + ½ long-term debt (see :func:`kmv_default_point`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import fsolve
from scipy.stats import norm

__all__ = ["MertonResult", "merton_model", "kmv_default_point", "altman_z_score"]


@dataclass(frozen=True)
class MertonResult:
    asset_value: float
    asset_vol: float
    distance_to_default: float
    default_probability: float           # risk-neutral, N(-d2)
    physical_default_probability: float | None  # using asset drift mu if given
    leverage: float                      # D / V
    credit_spread: float                 # implied spread on risky debt (decimal)
    converged: bool

    def __str__(self) -> str:
        return (f"V={self.asset_value:,.0f}, σV={self.asset_vol:.2%}, "
                f"DD={self.distance_to_default:.2f}, PD={self.default_probability:.4%}, "
                f"spread={self.credit_spread * 1e4:.0f} bp")


def kmv_default_point(short_term_debt: float, long_term_debt: float) -> float:
    return short_term_debt + 0.5 * long_term_debt


def merton_model(
    equity_value: float,
    equity_vol: float,
    debt: float,
    rate: float,
    maturity: float = 1.0,
    asset_drift: float | None = None,
) -> MertonResult:
    """Solve the Merton system for asset value/volatility and default metrics.

    Parameters
    ----------
    equity_value
        Market capitalisation.
    equity_vol
        Annualized equity volatility (e.g. 1-year historical).
    debt
        Default point / face value of debt (same currency as equity).
    rate
        Risk-free rate (decimal).
    asset_drift
        Optional expected asset return for a real-world PD.
    """
    if min(equity_value, equity_vol, debt, maturity) <= 0:
        raise ValueError("equity_value, equity_vol, debt and maturity must be positive")
    sqrt_t = np.sqrt(maturity)
    df = np.exp(-rate * maturity)

    def d1d2(v: float, sv: float) -> tuple[float, float]:
        d1 = (np.log(v / debt) + (rate + 0.5 * sv**2) * maturity) / (sv * sqrt_t)
        return d1, d1 - sv * sqrt_t

    def equations(x: np.ndarray) -> list[float]:
        v, sv = np.exp(x[0]), np.exp(x[1])
        d1, d2 = d1d2(v, sv)
        e_model = v * norm.cdf(d1) - debt * df * norm.cdf(d2)
        return [(e_model - equity_value) / equity_value,
                (norm.cdf(d1) * sv * v - equity_vol * equity_value) / (equity_vol * equity_value)]

    v0 = equity_value + debt * df
    sv0 = equity_vol * equity_value / v0
    sol, info, ier, _ = fsolve(equations, [np.log(v0), np.log(sv0)], full_output=True)
    v, sv = float(np.exp(sol[0])), float(np.exp(sol[1]))
    _, d2 = d1d2(v, sv)
    pd_rn = float(norm.cdf(-d2))
    pd_phys = None
    if asset_drift is not None:
        dd_p = (np.log(v / debt) + (asset_drift - 0.5 * sv**2) * maturity) / (sv * sqrt_t)
        pd_phys = float(norm.cdf(-dd_p))
    debt_value = v - equity_value
    spread = -np.log(debt_value / debt) / maturity - rate if debt_value > 0 else np.nan
    return MertonResult(
        asset_value=v, asset_vol=sv, distance_to_default=float(d2),
        default_probability=pd_rn, physical_default_probability=pd_phys,
        leverage=debt / v, credit_spread=float(max(spread, 0.0)),
        converged=bool(ier == 1 and np.max(np.abs(info["fvec"])) < 1e-8),
    )


def altman_z_score(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    market_value_equity: float,
    sales: float,
    total_assets: float,
    total_liabilities: float,
) -> dict[str, float | str]:
    """Original Altman (1968) Z-score for public manufacturers.

    Zones: Z > 2.99 safe, 1.81-2.99 grey, < 1.81 distress.
    """
    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = market_value_equity / total_liabilities
    x5 = sales / total_assets
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    zone = "safe" if z > 2.99 else "grey" if z >= 1.81 else "distress"
    return {"z_score": z, "zone": zone, "x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5}
