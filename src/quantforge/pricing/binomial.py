r"""Recombining binomial trees for European and American options.

Two lattice parameterizations are provided:

* ``"crr"`` — Cox, Ross & Rubinstein (1979). Symmetric ``u = 1/d``; simple and
  standard, but converges to Black-Scholes with an oscillating error.
* ``"lr"`` — Leisen & Reimer (1996). Centres the tree on the strike using the
  Peizer-Pratt inversion; converges smoothly at roughly second order and is the
  better default for production use. Requires an odd number of steps (an even
  value is bumped up by one).

Backward induction is vectorized over the nodes of each time slice, so a
2,000-step tree prices in milliseconds.

References
----------
Cox, J., Ross, S. & Rubinstein, M. (1979). Option Pricing: A Simplified
Approach. *Journal of Financial Economics*, 7(3).
Leisen, D. & Reimer, M. (1996). Binomial Models for Option Valuation —
Examining and Improving Convergence. *Applied Mathematical Finance*, 3(4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from ._common import ExerciseStyle, OptionType, intrinsic_value

__all__ = ["BinomialResult", "binomial_price"]

TreeMethod = Literal["crr", "lr"]


@dataclass(frozen=True)
class BinomialResult:
    """Tree price and the Greeks read directly off the lattice."""

    price: float
    delta: float
    gamma: float
    theta: float
    steps: int
    method: str


def _peizer_pratt(z: float, n: int) -> float:
    """Peizer-Pratt method 2 inversion: binomial probability matching N(z)."""
    denom = n + 1.0 / 3.0 + 0.1 / (n + 1.0)
    return 0.5 + np.copysign(0.5, z) * np.sqrt(1.0 - np.exp(-((z / denom) ** 2) * (n + 1.0 / 6.0)))


def _tree_parameters(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    dividend_yield: float,
    steps: int,
    method: TreeMethod,
) -> tuple[float, float, float]:
    dt = maturity / steps
    growth = np.exp((rate - dividend_yield) * dt)
    if method == "crr":
        u = np.exp(volatility * np.sqrt(dt))
        d = 1.0 / u
        p = (growth - d) / (u - d)
    elif method == "lr":
        vol_sqrt_t = volatility * np.sqrt(maturity)
        d1 = (np.log(spot / strike) + (rate - dividend_yield + 0.5 * volatility**2) * maturity) / (
            vol_sqrt_t
        )
        d2 = d1 - vol_sqrt_t
        p = _peizer_pratt(d2, steps)
        p_star = _peizer_pratt(d1, steps)
        u = growth * p_star / p
        d = (growth - p * u) / (1.0 - p)
    else:
        raise ValueError(f"method must be 'crr' or 'lr', got {method!r}")
    if not 0.0 < p < 1.0:
        raise ValueError(
            f"risk-neutral probability {p:.4f} is outside (0, 1); increase the number of steps"
        )
    return float(u), float(d), float(p)


def binomial_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: OptionType | str = OptionType.CALL,
    exercise: ExerciseStyle | str = ExerciseStyle.EUROPEAN,
    dividend_yield: float = 0.0,
    steps: int = 501,
    method: TreeMethod = "lr",
) -> BinomialResult:
    """Price a vanilla option on a recombining binomial tree.

    Parameters
    ----------
    spot, strike, maturity, rate, volatility, dividend_yield
        Same conventions as :func:`quantforge.pricing.bs_price`.
    option_type
        ``"call"`` or ``"put"``.
    exercise
        ``"european"`` or ``"american"``.
    steps
        Number of time steps (must be >= 2).
    method
        ``"lr"`` (Leisen-Reimer, default) or ``"crr"`` (Cox-Ross-Rubinstein).

    Returns
    -------
    BinomialResult
        Price plus delta, gamma and theta estimated from the first two
        time slices of the tree (theta is per year).

    Examples
    --------
    >>> res = binomial_price(50, 50, 5/12, 0.10, 0.40, "put", "american", steps=1001)
    >>> round(res.price, 2)  # Hull, Example 21.1 (true value ~4.28)
    4.28
    """
    opt = OptionType.parse(option_type)
    style = ExerciseStyle.parse(exercise)
    for name, val in (("spot", spot), ("strike", strike), ("maturity", maturity),
                      ("volatility", volatility)):
        if not val > 0:
            raise ValueError(f"{name} must be strictly positive")
    if steps < 2:
        raise ValueError("steps must be >= 2")
    if method == "lr" and steps % 2 == 0:
        steps += 1

    u, d, p = _tree_parameters(spot, strike, maturity, rate, volatility, dividend_yield, steps,
                               method)
    dt = maturity / steps
    disc = np.exp(-rate * dt)
    pu, pd = disc * p, disc * (1.0 - p)

    # Terminal nodes: j up-moves, j = 0..steps
    j = np.arange(steps + 1)
    values = intrinsic_value(spot * u**j * d ** (steps - j), strike, opt)

    slice1 = slice2 = None
    for n in range(steps - 1, -1, -1):
        values = pu * values[1:] + pd * values[:-1]
        if style is ExerciseStyle.AMERICAN:
            jn = np.arange(n + 1)
            values = np.maximum(values, intrinsic_value(spot * u**jn * d ** (n - jn), strike, opt))
        if n == 2:
            slice2 = values.copy()
        elif n == 1:
            slice1 = values.copy()

    price = float(values[0])
    assert slice1 is not None and slice2 is not None

    s_u, s_d = spot * u, spot * d
    delta = (slice1[1] - slice1[0]) / (s_u - s_d)

    s_uu, s_ud, s_dd = spot * u * u, spot * u * d, spot * d * d
    delta_up = (slice2[2] - slice2[1]) / (s_uu - s_ud)
    delta_dn = (slice2[1] - slice2[0]) / (s_ud - s_dd)
    gamma = (delta_up - delta_dn) / (0.5 * (s_uu - s_dd))

    # Mid node of slice 2 sits at S*u*d; exactly S for CRR, ~S for LR.
    theta = (slice2[1] - price) / (2.0 * dt)

    return BinomialResult(
        price=price,
        delta=float(delta),
        gamma=float(gamma),
        theta=float(theta),
        steps=steps,
        method=method,
    )
