r"""Monte-Carlo pricing under geometric Brownian motion.

Features
--------
* Exact log-normal path simulation (no discretization bias for GBM).
* Variance reduction: antithetic variates and control variates.
* European, arithmetic/geometric Asian, and barrier options.
* Every estimator returns a :class:`MCResult` with the standard error and a
  confidence interval, so users can see how much to trust the number.
* Reproducible: pass ``seed`` (int) or a ``numpy.random.Generator``.

References
----------
Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*. Springer.
Kemna, A. & Vorst, A. (1990). A Pricing Method for Options Based on Average
Asset Values. *Journal of Banking and Finance*, 14(1).
Broadie, M., Glasserman, P. & Kou, S. (1997). A Continuity Correction for
Discrete Barrier Options. *Mathematical Finance*, 7(4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import norm

from ._common import FloatArray, OptionType, intrinsic_value

__all__ = [
    "MCResult",
    "simulate_gbm_paths",
    "mc_european",
    "mc_asian",
    "geometric_asian_price",
    "mc_barrier",
]

BarrierKind = Literal["up-and-out", "up-and-in", "down-and-out", "down-and-in"]
SeedLike = int | np.random.Generator | None

# Broadie-Glasserman-Kou constant: -zeta(1/2) / sqrt(2*pi)
_BGK_BETA = 0.5825971579390106


@dataclass(frozen=True)
class MCResult:
    """Monte-Carlo estimate with its statistical uncertainty."""

    price: float
    std_error: float
    n_paths: int
    confidence: float = 0.95

    @property
    def conf_interval(self) -> tuple[float, float]:
        z = norm.ppf(0.5 + self.confidence / 2.0)
        return (self.price - z * self.std_error, self.price + z * self.std_error)

    def __str__(self) -> str:
        lo, hi = self.conf_interval
        return (
            f"MCResult(price={self.price:.6f}, se={self.std_error:.6f}, "
            f"{self.confidence:.0%} CI=[{lo:.6f}, {hi:.6f}], paths={self.n_paths})"
        )


def _rng(seed: SeedLike) -> np.random.Generator:
    return seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)


def simulate_gbm_paths(
    spot: float,
    maturity: float,
    rate: float,
    volatility: float,
    n_paths: int,
    n_steps: int,
    dividend_yield: float = 0.0,
    antithetic: bool = False,
    seed: SeedLike = None,
) -> FloatArray:
    """Simulate GBM price paths using the exact log-normal transition.

    Returns
    -------
    ndarray of shape ``(n_paths, n_steps + 1)``
        Column 0 is the spot; column ``i`` is the price at ``t_i = i * T / n_steps``.
        With ``antithetic=True`` the second half of the rows mirror the first half.
    """
    if n_paths < 1 or n_steps < 1:
        raise ValueError("n_paths and n_steps must be >= 1")
    if antithetic and n_paths % 2:
        raise ValueError("n_paths must be even when antithetic=True")
    rng = _rng(seed)
    dt = maturity / n_steps
    drift = (rate - dividend_yield - 0.5 * volatility**2) * dt
    diffusion = volatility * np.sqrt(dt)

    half = n_paths // 2 if antithetic else n_paths
    z = rng.standard_normal((half, n_steps))
    if antithetic:
        z = np.vstack([z, -z])
    log_increments = drift + diffusion * z
    log_paths = np.concatenate(
        [np.zeros((n_paths, 1)), np.cumsum(log_increments, axis=1)], axis=1
    )
    return spot * np.exp(log_paths)


def _summarize(samples: FloatArray, antithetic: bool, confidence: float) -> MCResult:
    """Mean and standard error; antithetic pairs are averaged first (they are not i.i.d.)."""
    n = samples.size
    if antithetic:
        half = n // 2
        samples = 0.5 * (samples[:half] + samples[half:])
    se = float(samples.std(ddof=1) / np.sqrt(samples.size))
    return MCResult(price=float(samples.mean()), std_error=se, n_paths=n, confidence=confidence)


def _apply_control_variate(
    target: FloatArray, control: FloatArray, control_mean: float
) -> FloatArray:
    """Optimal linear control variate: Y - b*(X - E[X]) with b = Cov(Y,X)/Var(X)."""
    var_x = control.var(ddof=1)
    if var_x <= 0:
        return target
    b = np.cov(target, control, ddof=1)[0, 1] / var_x
    return target - b * (control - control_mean)


def mc_european(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: float = 0.0,
    n_paths: int = 100_000,
    antithetic: bool = True,
    control_variate: bool = True,
    confidence: float = 0.95,
    seed: SeedLike = None,
) -> MCResult:
    """European option by Monte-Carlo.

    The control variate is the discounted terminal stock price, whose
    risk-neutral expectation ``S0 * exp(-qT)`` is known exactly.
    """
    opt = OptionType.parse(option_type)
    if antithetic and n_paths % 2:
        n_paths += 1
    paths = simulate_gbm_paths(spot, maturity, rate, volatility, n_paths, 1, dividend_yield,
                               antithetic, seed)
    s_t = paths[:, -1]
    disc = np.exp(-rate * maturity)
    payoff = disc * intrinsic_value(s_t, strike, opt)
    if control_variate:
        forward_pv = spot * np.exp(-dividend_yield * maturity)
        payoff = _apply_control_variate(payoff, disc * s_t, forward_pv)
    return _summarize(payoff, antithetic, confidence)


def geometric_asian_price(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    n_fixings: int,
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: float = 0.0,
) -> float:
    r"""Closed-form price of a discretely monitored geometric-average Asian option.

    Fixings are equally spaced at ``t_i = i*T/n`` for ``i = 1..n``. The geometric
    average of log-normal variables is log-normal with

    .. math::
        \mu_G = \ln S_0 + (r - q - \tfrac12\sigma^2)\,T\,\frac{n+1}{2n},\qquad
        \sigma_G^2 = \sigma^2 T\,\frac{(n+1)(2n+1)}{6n^2}.
    """
    opt = OptionType.parse(option_type)
    n = n_fixings
    mu = np.log(spot) + (rate - dividend_yield - 0.5 * volatility**2) * maturity * (n + 1) / (2 * n)
    var = volatility**2 * maturity * (n + 1) * (2 * n + 1) / (6 * n**2)
    sd = np.sqrt(var)
    d1 = (mu - np.log(strike) + var) / sd
    d2 = d1 - sd
    disc = np.exp(-rate * maturity)
    forward_g = np.exp(mu + 0.5 * var)
    if opt is OptionType.CALL:
        return float(disc * (forward_g * norm.cdf(d1) - strike * norm.cdf(d2)))
    return float(disc * (strike * norm.cdf(-d2) - forward_g * norm.cdf(-d1)))


def mc_asian(
    spot: float,
    strike: float,
    maturity: float,
    rate: float,
    volatility: float,
    n_fixings: int = 252,
    option_type: OptionType | str = OptionType.CALL,
    average: Literal["arithmetic", "geometric"] = "arithmetic",
    dividend_yield: float = 0.0,
    n_paths: int = 100_000,
    antithetic: bool = True,
    control_variate: bool = True,
    confidence: float = 0.95,
    seed: SeedLike = None,
) -> MCResult:
    """Fixed-strike Asian option on the average of ``n_fixings`` equally spaced prices.

    For the arithmetic average, the geometric Asian (known in closed form) is used
    as control variate (Kemna & Vorst, 1990), typically cutting the standard
    error by one to two orders of magnitude.
    """
    opt = OptionType.parse(option_type)
    if antithetic and n_paths % 2:
        n_paths += 1
    paths = simulate_gbm_paths(spot, maturity, rate, volatility, n_paths, n_fixings,
                               dividend_yield, antithetic, seed)[:, 1:]
    disc = np.exp(-rate * maturity)
    geo = np.exp(np.log(paths).mean(axis=1))
    geo_payoff = disc * intrinsic_value(geo, strike, opt)
    if average == "geometric":
        return _summarize(geo_payoff, antithetic, confidence)
    if average != "arithmetic":
        raise ValueError("average must be 'arithmetic' or 'geometric'")
    arith_payoff = disc * intrinsic_value(paths.mean(axis=1), strike, opt)
    if control_variate:
        exact = geometric_asian_price(spot, strike, maturity, rate, volatility, n_fixings, opt,
                                      dividend_yield)
        arith_payoff = _apply_control_variate(arith_payoff, geo_payoff, exact)
    return _summarize(arith_payoff, antithetic, confidence)


def mc_barrier(
    spot: float,
    strike: float,
    barrier: float,
    maturity: float,
    rate: float,
    volatility: float,
    kind: BarrierKind = "down-and-out",
    option_type: OptionType | str = OptionType.CALL,
    dividend_yield: float = 0.0,
    rebate: float = 0.0,
    n_steps: int = 252,
    n_paths: int = 100_000,
    continuous_correction: bool = True,
    antithetic: bool = True,
    confidence: float = 0.95,
    seed: SeedLike = None,
) -> MCResult:
    """Knock-in / knock-out barrier option.

    The barrier is checked at each of the ``n_steps`` simulation dates. With
    ``continuous_correction=True`` the barrier is shifted by the
    Broadie-Glasserman-Kou factor ``exp(∓0.5826 σ √dt)`` so that the discrete
    simulation approximates a *continuously* monitored contract.

    ``rebate`` is paid at maturity when a knock-out option is knocked out, or
    when a knock-in option never knocks in.
    """
    opt = OptionType.parse(option_type)
    if kind not in ("up-and-out", "up-and-in", "down-and-out", "down-and-in"):
        raise ValueError(f"unknown barrier kind {kind!r}")
    is_up = kind.startswith("up")
    is_out = kind.endswith("out")
    if (is_up and spot >= barrier) or (not is_up and spot <= barrier):
        raise ValueError("spot is already beyond the barrier")
    if antithetic and n_paths % 2:
        n_paths += 1

    h = barrier
    if continuous_correction:
        shift = np.exp(_BGK_BETA * volatility * np.sqrt(maturity / n_steps))
        h = barrier / shift if is_up else barrier * shift

    paths = simulate_gbm_paths(spot, maturity, rate, volatility, n_paths, n_steps,
                               dividend_yield, antithetic, seed)
    hit = (paths.max(axis=1) >= h) if is_up else (paths.min(axis=1) <= h)
    alive = ~hit if is_out else hit
    payoff = np.where(alive, intrinsic_value(paths[:, -1], strike, opt), rebate)
    return _summarize(np.exp(-rate * maturity) * payoff, antithetic, confidence)
