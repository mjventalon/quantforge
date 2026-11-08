"""Beyond Black-Scholes: stochastic volatility (Heston), SABR and jump-diffusion (Merton).

References
----------
* Heston, S. (1993). A closed-form solution for options with stochastic volatility.
  *Review of Financial Studies* 6(2). Characteristic function in the "little trap" form of
  Albrecher, Mayer, Schoutens & Tistaert (2007), *Wilmott Magazine*, which avoids branch-cut
  discontinuities; prices by the single-integral formula of Lewis (2000), *Option Valuation
  under Stochastic Volatility*.
* Hagan, P., Kumar, D., Lesniewski, A. & Woodward, D. (2002). Managing smile risk.
  *Wilmott Magazine*, 84-108 (lognormal implied-volatility expansion).
* Merton, R. (1976). Option pricing when underlying stock returns are discontinuous.
  *Journal of Financial Economics* 3, 125-144.

Conventions follow :mod:`quantforge.pricing.black_scholes`: continuous rates and dividend
yield, maturity in years, volatility as a decimal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize
from scipy.special import gammaln

from .black_scholes import bs_price, implied_volatility

__all__ = ["HestonParams", "heston_cf", "heston_price", "heston_mc", "sabr_vol",
           "SABRParams", "calibrate_sabr", "merton_jump_price", "MertonParams",
           "calibrate_heston", "calibrate_merton", "model_implied_vols"]

# Gauss-Legendre nodes on [0, 1) mapped to [0, ∞) by u = t / (1 − t)
_GL_X, _GL_W = np.polynomial.legendre.leggauss(256)
_T = 0.5 * (_GL_X + 1.0)
_U = _T / (1.0 - _T)
_W = 0.5 * _GL_W / (1.0 - _T) ** 2


# ------------------------------------------------------------------ Heston
@dataclass(frozen=True)
class HestonParams:
    v0: float        # initial variance
    kappa: float     # mean-reversion speed
    theta: float     # long-run variance
    sigma: float     # volatility of variance ("vol of vol")
    rho: float       # correlation between price and variance shocks

    @property
    def feller(self) -> bool:
        """Feller condition 2κθ ≥ σ² (variance stays strictly positive)."""
        return 2 * self.kappa * self.theta >= self.sigma ** 2


def heston_cf(u: np.ndarray, t: float, p: HestonParams) -> np.ndarray:
    """Characteristic function E[exp(iu·X_T)] of X_T = ln(S_T/S_0) − (r − q)T."""
    u = np.asarray(u, dtype=complex)
    k, th, s, r, v0 = p.kappa, p.theta, p.sigma, p.rho, p.v0
    b = k - r * s * 1j * u
    d = np.sqrt(b * b + s * s * (1j * u + u * u))
    g = (b - d) / (b + d)
    e = np.exp(-d * t)
    c = k * th / s ** 2 * ((b - d) * t - 2.0 * np.log((1.0 - g * e) / (1.0 - g)))
    dd = (b - d) / s ** 2 * (1.0 - e) / (1.0 - g * e)
    return np.exp(c + dd * v0)


def heston_price(spot, strike, maturity: float, rate: float, params: HestonParams,
                 option_type: str = "call", dividend_yield: float = 0.0):
    """European option under Heston (Lewis single-integral formula). Vectorised in strike."""
    k_arr = np.atleast_1d(np.asarray(strike, dtype=float))
    s, t, r, q = float(spot), float(maturity), float(rate), float(dividend_yield)
    if t <= 0 or s <= 0 or np.any(k_arr <= 0):
        raise ValueError("spot, strikes and maturity must be positive")
    phi = heston_cf(_U - 0.5j, t, params)                           # (n_nodes,)
    kap = np.log(s / k_arr) + (r - q) * t                           # (n_strikes,)
    integrand = np.real(np.exp(1j * np.outer(kap, _U)) * phi) / (_U ** 2 + 0.25)
    integral = integrand @ _W
    call = s * np.exp(-q * t) - np.sqrt(s * k_arr) * np.exp(-0.5 * (r + q) * t) / np.pi * integral
    out = call if option_type == "call" else call - s * np.exp(-q * t) + k_arr * np.exp(-r * t)
    return float(out[0]) if np.ndim(strike) == 0 else out


def heston_mc(spot: float, strike: float, maturity: float, rate: float, params: HestonParams,
              option_type: str = "call", dividend_yield: float = 0.0, n_paths: int = 200_000,
              n_steps: int = 200, seed: int | None = 0) -> tuple[float, float]:
    """Monte-Carlo check of :func:`heston_price` (full-truncation Euler on the variance,
    exact log-Euler on the price; antithetic). Returns (price, standard error)."""
    rng = np.random.default_rng(seed)
    dt = maturity / n_steps
    half = n_paths // 2
    x = np.full(2 * half, np.log(spot))
    v = np.full(2 * half, params.v0)
    for _ in range(n_steps):
        z1 = rng.standard_normal(half)
        z2 = params.rho * z1 + np.sqrt(1 - params.rho ** 2) * rng.standard_normal(half)
        z1, z2 = np.concatenate([z1, -z1]), np.concatenate([z2, -z2])
        vp = np.maximum(v, 0.0)
        x += (rate - dividend_yield - 0.5 * vp) * dt + np.sqrt(vp * dt) * z1
        v += params.kappa * (params.theta - vp) * dt + params.sigma * np.sqrt(vp * dt) * z2
    st = np.exp(x)
    pay = np.maximum(st - strike, 0) if option_type == "call" else np.maximum(strike - st, 0)
    pay = np.exp(-rate * maturity) * pay
    pairs = 0.5 * (pay[:half] + pay[half:])
    return float(pairs.mean()), float(pairs.std(ddof=1) / np.sqrt(half))


# ------------------------------------------------------------------ SABR
@dataclass(frozen=True)
class SABRParams:
    alpha: float
    beta: float
    rho: float
    nu: float


def sabr_vol(forward: float, strike, maturity: float, p: SABRParams):
    """Hagan et al. (2002) lognormal (Black) implied volatility. Vectorised in strike."""
    f = float(forward)
    k = np.atleast_1d(np.asarray(strike, dtype=float))
    a, b, r, n, t = p.alpha, p.beta, p.rho, p.nu, maturity
    fk = f * k
    lfk = np.log(f / k)
    omb = 1.0 - b
    fkb = fk ** (omb / 2)
    z = n / a * fkb * lfk
    with np.errstate(divide="ignore", invalid="ignore"):
        xz = np.log((np.sqrt(1 - 2 * r * z + z * z) + z - r) / (1 - r))
        zx = np.where(np.abs(z) < 1e-7, 1.0 - 0.5 * r * z, z / xz)
    denom = fkb * (1 + omb ** 2 / 24 * lfk ** 2 + omb ** 4 / 1920 * lfk ** 4)
    corr = 1 + (omb ** 2 / 24 * a * a / fk ** omb + 0.25 * r * b * n * a / fkb
                + (2 - 3 * r * r) / 24 * n * n) * t
    vol = a / denom * zx * corr
    return float(vol[0]) if np.ndim(strike) == 0 else vol


def calibrate_sabr(forward: float, strikes, vols, maturity: float, beta: float = 1.0,
                   weights=None) -> tuple[SABRParams, float]:
    """Fit α, ρ, ν (β fixed) to market implied vols. Returns (params, RMSE in vol)."""
    k, iv = np.asarray(strikes, float), np.asarray(vols, float)
    w = np.ones_like(iv) if weights is None else np.asarray(weights, float)
    atm = float(np.interp(forward, k, iv)) if k.min() < forward < k.max() else float(np.median(iv))
    a0 = atm * forward ** (1 - beta)

    def resid(x):
        return w * (sabr_vol(forward, k, maturity, SABRParams(x[0], beta, x[1], x[2])) - iv)

    best = None
    for rho0 in (-0.5, 0.0, 0.3):
        sol = optimize.least_squares(resid, [a0, rho0, 0.5],
                                     bounds=([1e-6, -0.999, 1e-4], [10 * a0 + 5, 0.999, 10.0]))
        if best is None or sol.cost < best.cost:
            best = sol
    p = SABRParams(best.x[0], beta, best.x[1], best.x[2])
    rmse = float(np.sqrt(np.mean((sabr_vol(forward, k, maturity, p) - iv) ** 2)))
    return p, rmse


# ------------------------------------------------------------------ Merton jump-diffusion
@dataclass(frozen=True)
class MertonParams:
    sigma: float     # diffusion volatility
    lam: float       # jump intensity (jumps per year)
    mu_j: float      # mean of log jump size
    delta: float     # std of log jump size


def merton_jump_price(spot, strike, maturity: float, rate: float, p: MertonParams,
                      option_type: str = "call", dividend_yield: float = 0.0,
                      n_terms: int = 80):
    """Merton (1976) series: Poisson-weighted Black-Scholes prices."""
    k = np.asarray(strike, dtype=float)
    kbar = np.exp(p.mu_j + 0.5 * p.delta ** 2) - 1.0
    lam2 = p.lam * (1 + kbar)
    total = np.zeros_like(k, dtype=float)
    for n in range(n_terms):
        w = np.exp(-lam2 * maturity + n * np.log(lam2 * maturity + 1e-300) - gammaln(n + 1))
        if n > 5 and w < 1e-16:
            break
        sig_n = np.sqrt(p.sigma ** 2 + n * p.delta ** 2 / maturity)
        r_n = rate - p.lam * kbar + n * np.log1p(kbar) / maturity
        total = total + w * bs_price(spot, k, maturity, r_n, sig_n, option_type,
                                     dividend_yield)
    return float(total) if np.ndim(strike) == 0 else total


# ------------------------------------------------------------------ calibration helpers
def model_implied_vols(prices, spot: float, strikes, maturity: float, rate: float,
                       option_type: str = "call", dividend_yield: float = 0.0) -> np.ndarray:
    """Black-Scholes implied vols of model prices (NaN where not invertible)."""
    out = []
    for pr, k in zip(np.atleast_1d(prices), np.atleast_1d(strikes)):
        try:
            out.append(implied_volatility(float(pr), spot, float(k), maturity, rate,
                                          option_type, dividend_yield))
        except (ValueError, RuntimeError):
            out.append(np.nan)
    return np.array(out, dtype=float)


def _slices(quotes, spot, rate, dividend_yield):
    """Normalise quote slices: (T, strikes, vols[, forward]) -> (T, K, iv, carry q).
    With a forward (e.g. parity-implied) the carry is q = r − ln(F/S)/T for that slice."""
    for item in quotes:
        t, k, iv = float(item[0]), np.asarray(item[1], float), np.asarray(item[2], float)
        q = (rate - np.log(float(item[3]) / spot) / t) if len(item) > 3 and item[3] else \
            dividend_yield
        yield t, k, iv, float(q)


def _vega(spot, k, t, r, iv, q):
    from .black_scholes import bs_greeks
    return np.maximum(np.asarray(bs_greeks(spot, k, t, r, iv, "call", q).vega), 1e-4)


def calibrate_heston(spot: float, quotes: list[tuple[float, np.ndarray, np.ndarray]],
                     rate: float, dividend_yield: float = 0.0,
                     x0: HestonParams | None = None) -> tuple[HestonParams, float]:
    """Fit Heston to several maturities at once.

    ``quotes`` is a list of ``(maturity, strikes, market_implied_vols[, forward])``. The
    objective is the vega-weighted price error, a fast first-order proxy for the error in
    volatility points.
    Returns (params, RMSE in implied-vol units)."""
    data = []
    for t, k, iv, q in _slices(quotes, spot, rate, dividend_yield):
        mkt = bs_price(spot, k, t, rate, iv, "call", q)
        data.append((t, k, iv, mkt, _vega(spot, k, t, rate, iv, q), q))
    all_iv = np.concatenate([d[2] for d in data])
    v_atm = float(np.median(all_iv)) ** 2
    start = x0 or HestonParams(v_atm, 2.0, v_atm, 0.6, -0.6)

    def resid(x):
        p = HestonParams(*x)
        out = []
        for t, k, _, mkt, vega, q in data:
            out.append((heston_price(spot, k, t, rate, p, "call", q) - mkt) / vega)
        return np.concatenate(out)

    sol = optimize.least_squares(
        resid, [start.v0, start.kappa, start.theta, start.sigma, start.rho],
        bounds=([1e-4, 0.05, 1e-4, 0.01, -0.99], [2.0, 15.0, 2.0, 3.0, 0.99]),
        x_scale=[0.02, 1.0, 0.02, 0.3, 0.3], max_nfev=400)
    p = HestonParams(*sol.x)
    rmse = float(np.sqrt(np.mean(sol.fun ** 2)))
    return p, rmse


def calibrate_merton(spot: float, quotes: list[tuple[float, np.ndarray, np.ndarray]],
                     rate: float, dividend_yield: float = 0.0) -> tuple[MertonParams, float]:
    """Fit Merton jump-diffusion (σ, λ, μ_J, δ) to several maturities (vega-weighted)."""
    data = []
    for t, k, iv, q in _slices(quotes, spot, rate, dividend_yield):
        mkt = bs_price(spot, k, t, rate, iv, "call", q)
        data.append((t, k, mkt, _vega(spot, k, t, rate, iv, q), q))
    sig0 = float(np.median(np.concatenate([np.asarray(x[2], float) for x in quotes])))

    def resid(x):
        p = MertonParams(*x)
        return np.concatenate([(merton_jump_price(spot, k, t, rate, p, "call", q)
                                - mkt) / vega for t, k, mkt, vega, q in data])

    sol = optimize.least_squares(resid, [0.8 * sig0, 0.5, -0.1, 0.15],
                                 bounds=([0.01, 0.0, -1.0, 0.01], [2.0, 10.0, 0.5, 1.0]),
                                 max_nfev=400)
    return MertonParams(*sol.x), float(np.sqrt(np.mean(sol.fun ** 2)))
