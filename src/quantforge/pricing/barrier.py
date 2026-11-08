r"""Closed-form prices for continuously monitored single-barrier options.

Implements the Merton (1973) / Reiner & Rubinstein (1991) formulas for all
eight standard knock-in and knock-out calls and puts, with no rebate.
In-out parity holds exactly: ``knock_in + knock_out = vanilla``.

References
----------
Reiner, E. & Rubinstein, M. (1991). Breaking Down the Barriers. *Risk*, 4(8).
Hull, J. C. *Options, Futures, and Other Derivatives*, ch. 26.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from ._common import OptionType
from .black_scholes import bs_price

__all__ = ["barrier_price"]


def barrier_price(
    spot: float,
    strike: float,
    barrier: float,
    maturity: float,
    rate: float,
    volatility: float,
    kind: str = "down-and-out",
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: float = 0.0,
) -> float:
    """Analytic price of a continuously monitored barrier option (no rebate).

    Examples
    --------
    >>> round(barrier_price(100, 100, 90, 1.0, 0.05, 0.2, "down-and-out", "call"), 4)
    8.6655
    """
    opt = OptionType.parse(option_type)
    s, k, h, t, r = spot, strike, barrier, maturity, rate
    q, sig = dividend_yield, volatility
    is_up = kind.startswith("up")
    is_out = kind.endswith("out")
    if kind not in ("up-and-out", "up-and-in", "down-and-out", "down-and-in"):
        raise ValueError(f"unknown barrier kind {kind!r}")
    vanilla = bs_price(s, k, t, r, sig, opt, q)
    if (is_up and s >= h) or (not is_up and s <= h):
        # already knocked: out is worthless, in is vanilla
        return 0.0 if is_out else float(vanilla)

    srt = sig * np.sqrt(t)
    lam = (r - q + 0.5 * sig**2) / sig**2
    dq, dr = np.exp(-q * t), np.exp(-r * t)
    hs = h / s
    x1 = np.log(s / h) / srt + lam * srt
    y = np.log(h * h / (s * k)) / srt + lam * srt
    y1 = np.log(h / s) / srt + lam * srt

    def n(x: float) -> float:
        return float(norm.cdf(x))

    if opt is OptionType.CALL:
        if not is_up:  # down barrier
            if h <= k:
                c_di = s * dq * hs ** (2 * lam) * n(y) - k * dr * hs ** (2 * lam - 2) * n(y - srt)
            else:
                c_do = (
                    s * n(x1) * dq - k * dr * n(x1 - srt)
                    - s * dq * hs ** (2 * lam) * n(y1)
                    + k * dr * hs ** (2 * lam - 2) * n(y1 - srt)
                )
                c_di = vanilla - c_do
            return float(vanilla - c_di) if is_out else float(c_di)
        # up barrier
        if h <= k:
            c_ui = vanilla
        else:
            c_ui = (
                s * n(x1) * dq - k * dr * n(x1 - srt)
                - s * dq * hs ** (2 * lam) * (n(-y) - n(-y1))
                + k * dr * hs ** (2 * lam - 2) * (n(-y + srt) - n(-y1 + srt))
            )
        return float(vanilla - c_ui) if is_out else float(c_ui)

    # puts
    if is_up:
        if h >= k:
            p_ui = -s * dq * hs ** (2 * lam) * n(-y) + k * dr * hs ** (2 * lam - 2) * n(-y + srt)
        else:
            p_uo = (
                -s * n(-x1) * dq + k * dr * n(-x1 + srt)
                + s * dq * hs ** (2 * lam) * n(-y1)
                - k * dr * hs ** (2 * lam - 2) * n(-y1 + srt)
            )
            p_ui = vanilla - p_uo
        return float(vanilla - p_ui) if is_out else float(p_ui)
    # down barrier put
    if h >= k:
        p_di = vanilla
    else:
        p_di = (
            -s * n(-x1) * dq + k * dr * n(-x1 + srt)
            + s * dq * hs ** (2 * lam) * (n(y) - n(y1))
            - k * dr * hs ** (2 * lam - 2) * (n(y - srt) - n(y1 - srt))
        )
    return float(vanilla - p_di) if is_out else float(p_di)
