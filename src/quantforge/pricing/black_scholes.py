r"""Black-Scholes-Merton closed-form pricing for European options.

The model assumes the underlying follows a geometric Brownian motion

.. math:: dS_t = (r - q) S_t\,dt + \sigma S_t\,dW_t

under the risk-neutral measure, with constant risk-free rate ``r``,
continuous dividend yield ``q`` and volatility ``sigma``.

All functions are vectorized: any argument may be a NumPy array and the
usual broadcasting rules apply. Scalar inputs return Python floats.

Units
-----
* ``rate``, ``dividend_yield`` and ``volatility`` are annualized decimals
  (5% -> ``0.05``).
* ``maturity`` is in years.
* ``vega`` and ``rho`` are per 1.00 change (multiply by 0.01 for "per 1%").
* ``theta`` is per year (divide by 365 for "per calendar day").

References
----------
Black, F. & Scholes, M. (1973). The Pricing of Options and Corporate
Liabilities. *Journal of Political Economy*, 81(3).
Merton, R. C. (1973). Theory of Rational Option Pricing. *Bell Journal of
Economics and Management Science*, 4(1).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike
from scipy.optimize import brentq
from scipy.stats import norm

from ._common import (
    FloatArray,
    OptionType,
    as_float_array,
    maybe_scalar,
    require_non_negative,
    require_positive,
)

__all__ = [
    "Greeks",
    "bs_price",
    "bs_delta",
    "bs_gamma",
    "bs_vega",
    "bs_theta",
    "bs_rho",
    "bs_greeks",
    "black76_price",
    "implied_volatility",
]


@dataclass(frozen=True)
class Greeks:
    """Price and first/second-order sensitivities of an option."""

    price: float | FloatArray
    delta: float | FloatArray
    gamma: float | FloatArray
    vega: float | FloatArray
    theta: float | FloatArray
    rho: float | FloatArray


def _d1_d2(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    dividend_yield: ArrayLike,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    s = require_positive(spot, "spot")
    k = require_positive(strike, "strike")
    t = require_positive(maturity, "maturity")
    sig = require_positive(volatility, "volatility")
    r = as_float_array(rate, "rate")
    q = as_float_array(dividend_yield, "dividend_yield")
    vol_sqrt_t = sig * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sig**2) * t) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return s, k, t, r, q, d1, d2


def bs_price(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: ArrayLike = 0.0,
) -> float | FloatArray:
    """Black-Scholes-Merton price of a European call or put.

    Examples
    --------
    >>> round(bs_price(42, 40, 0.5, 0.10, 0.20, "call"), 4)  # Hull, Example 15.6
    4.7594
    """
    opt = OptionType.parse(option_type)
    s, k, t, r, q, d1, d2 = _d1_d2(spot, strike, maturity, rate, volatility, dividend_yield)
    df_r = np.exp(-r * t)
    df_q = np.exp(-q * t)
    if opt is OptionType.CALL:
        value = s * df_q * norm.cdf(d1) - k * df_r * norm.cdf(d2)
    else:
        value = k * df_r * norm.cdf(-d2) - s * df_q * norm.cdf(-d1)
    return maybe_scalar(value)


def bs_delta(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: ArrayLike = 0.0,
) -> float | FloatArray:
    """dV/dS."""
    opt = OptionType.parse(option_type)
    _, _, t, _, q, d1, _ = _d1_d2(spot, strike, maturity, rate, volatility, dividend_yield)
    df_q = np.exp(-q * t)
    value = df_q * norm.cdf(d1) if opt is OptionType.CALL else df_q * (norm.cdf(d1) - 1.0)
    return maybe_scalar(value)


def bs_gamma(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    dividend_yield: ArrayLike = 0.0,
) -> float | FloatArray:
    """d²V/dS² (identical for calls and puts)."""
    s, _, t, _, q, d1, _ = _d1_d2(spot, strike, maturity, rate, volatility, dividend_yield)
    sig = np.asarray(volatility, dtype=np.float64)
    value = np.exp(-q * t) * norm.pdf(d1) / (s * sig * np.sqrt(t))
    return maybe_scalar(value)


def bs_vega(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    dividend_yield: ArrayLike = 0.0,
) -> float | FloatArray:
    """dV/dsigma per 1.00 of volatility (identical for calls and puts)."""
    s, _, t, _, q, d1, _ = _d1_d2(spot, strike, maturity, rate, volatility, dividend_yield)
    value = s * np.exp(-q * t) * norm.pdf(d1) * np.sqrt(t)
    return maybe_scalar(value)


def bs_theta(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: ArrayLike = 0.0,
) -> float | FloatArray:
    """dV/dt per year (calendar time passing, i.e. -dV/dT)."""
    opt = OptionType.parse(option_type)
    s, k, t, r, q, d1, d2 = _d1_d2(spot, strike, maturity, rate, volatility, dividend_yield)
    sig = np.asarray(volatility, dtype=np.float64)
    df_r = np.exp(-r * t)
    df_q = np.exp(-q * t)
    decay = -s * df_q * norm.pdf(d1) * sig / (2.0 * np.sqrt(t))
    if opt is OptionType.CALL:
        value = decay - r * k * df_r * norm.cdf(d2) + q * s * df_q * norm.cdf(d1)
    else:
        value = decay + r * k * df_r * norm.cdf(-d2) - q * s * df_q * norm.cdf(-d1)
    return maybe_scalar(value)


def bs_rho(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: ArrayLike = 0.0,
) -> float | FloatArray:
    """dV/dr per 1.00 of rate."""
    opt = OptionType.parse(option_type)
    _, k, t, r, _, _, d2 = _d1_d2(spot, strike, maturity, rate, volatility, dividend_yield)
    df_r = np.exp(-r * t)
    if opt is OptionType.CALL:
        value = k * t * df_r * norm.cdf(d2)
    else:
        value = -k * t * df_r * norm.cdf(-d2)
    return maybe_scalar(value)


def bs_greeks(
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: ArrayLike = 0.0,
) -> Greeks:
    """Price and all standard Greeks in one call."""
    args = (spot, strike, maturity, rate, volatility)
    return Greeks(
        price=bs_price(*args, option_type, dividend_yield),
        delta=bs_delta(*args, option_type, dividend_yield),
        gamma=bs_gamma(*args, dividend_yield),
        vega=bs_vega(*args, dividend_yield),
        theta=bs_theta(*args, option_type, dividend_yield),
        rho=bs_rho(*args, option_type, dividend_yield),
    )


def black76_price(
    forward: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    volatility: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
) -> float | FloatArray:
    """Black (1976) price of a European option on a forward or futures contract.

    Equivalent to Black-Scholes-Merton with ``spot=forward`` and ``dividend_yield=rate``.
    """
    return bs_price(forward, strike, maturity, rate, volatility, option_type, dividend_yield=rate)


def _implied_vol_scalar(
    price: float,
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    option_type: OptionType,
    dividend_yield: float,
    lower: float,
    upper: float,
    tol: float,
) -> float:
    df_r = np.exp(-rate * maturity)
    df_q = np.exp(-dividend_yield * maturity)
    if option_type is OptionType.CALL:
        lo_bound = max(spot * df_q - strike * df_r, 0.0)
        hi_bound = spot * df_q
    else:
        lo_bound = max(strike * df_r - spot * df_q, 0.0)
        hi_bound = strike * df_r
    if not (lo_bound - tol <= price <= hi_bound + tol):
        raise ValueError(
            f"price {price:.6g} violates no-arbitrage bounds [{lo_bound:.6g}, {hi_bound:.6g}]"
        )

    def objective(sig: float) -> float:
        return bs_price(spot, strike, maturity, rate, sig, option_type, dividend_yield) - price

    f_lo, f_hi = objective(lower), objective(upper)
    if f_lo > 0:
        return lower
    if f_hi < 0:
        raise ValueError(f"implied volatility above upper search bound {upper}")
    return float(brentq(objective, lower, upper, xtol=tol, maxiter=200))


def implied_volatility(
    price: ArrayLike,
    spot: ArrayLike,
    strike: ArrayLike,
    maturity: ArrayLike,
    rate: ArrayLike,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: ArrayLike = 0.0,
    *,
    lower: float = 1e-6,
    upper: float = 5.0,
    tol: float = 1e-10,
) -> float | FloatArray:
    """Volatility that reproduces an observed European option price.

    Uses Brent's method on ``[lower, upper]``, which is guaranteed to converge
    because the Black-Scholes price is strictly increasing in volatility.

    Raises
    ------
    ValueError
        If the price lies outside the no-arbitrage bounds.
    """
    opt = OptionType.parse(option_type)
    p, s, k, t, r, q = np.broadcast_arrays(
        require_non_negative(price, "price"),
        require_positive(spot, "spot"),
        require_positive(strike, "strike"),
        require_positive(maturity, "maturity"),
        as_float_array(rate, "rate"),
        as_float_array(dividend_yield, "dividend_yield"),
    )
    out = np.empty(p.shape, dtype=np.float64)
    for idx in np.ndindex(p.shape):
        out[idx] = _implied_vol_scalar(
            float(p[idx]), float(s[idx]), float(k[idx]), float(t[idx]),
            float(r[idx]), opt, float(q[idx]), lower, upper, tol,
        )
    return maybe_scalar(out)
