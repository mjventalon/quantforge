"""Heston, SABR and Merton jump-diffusion: limits, identities and Monte-Carlo checks."""

import numpy as np
import pytest
from scipy import integrate

from quantforge.pricing import bs_price
from quantforge.pricing.stochastic import (
    HestonParams,
    MertonParams,
    SABRParams,
    calibrate_heston,
    calibrate_merton,
    calibrate_sabr,
    heston_cf,
    heston_mc,
    heston_price,
    merton_jump_price,
    model_implied_vols,
    sabr_vol,
)

P = HestonParams(v0=0.04, kappa=1.5, theta=0.05, sigma=0.6, rho=-0.7)


def test_heston_reduces_to_black_scholes():
    p = HestonParams(0.04, 2.0, 0.04, 1e-4, 0.0)
    k = np.array([80, 100, 120.0])
    np.testing.assert_allclose(heston_price(100, k, 1.0, 0.03, p, "call", 0.01),
                               bs_price(100, k, 1.0, 0.03, 0.2, "call", 0.01), atol=1e-6)


def test_heston_quadrature_matches_adaptive_integration():
    s, k, t, r = 100.0, 110.0, 0.5, 0.02
    kap = np.log(s / k) + r * t

    def f(u):
        return np.real(np.exp(1j * u * kap) * heston_cf(u - 0.5j, t, P)) / (u * u + 0.25)

    ref = s - np.sqrt(s * k) * np.exp(-0.5 * r * t) / np.pi * integrate.quad(f, 0, np.inf,
                                                                          limit=500)[0]
    assert heston_price(s, k, t, r, P) == pytest.approx(ref, abs=1e-8)


def test_heston_put_call_parity_and_cf_at_zero():
    k = np.linspace(60, 140, 9)
    c = heston_price(100, k, 1.0, 0.03, P, "call", 0.02)
    p = heston_price(100, k, 1.0, 0.03, P, "put", 0.02)
    np.testing.assert_allclose(c - p, 100 * np.exp(-0.02) - k * np.exp(-0.03), atol=1e-10)
    assert abs(heston_cf(np.array([0.0]), 1.0, P)[0] - 1) < 1e-14
    # martingale: E[S_T] = forward  <=>  phi(-i) = 1
    assert abs(heston_cf(np.array([-1j]), 1.0, P)[0] - 1) < 1e-12


@pytest.mark.parametrize("k", [80.0, 100.0, 125.0])
def test_heston_matches_monte_carlo(k):
    exact = heston_price(100, k, 1.0, 0.03, P)
    mc, se = heston_mc(100, k, 1.0, 0.03, P, n_paths=200_000, n_steps=250, seed=1)
    assert abs(mc - exact) < 4 * se + 0.02          # + small Euler discretisation bias


def test_heston_skew_negative_rho():
    k = np.array([80.0, 100.0, 120.0])
    iv = model_implied_vols(heston_price(100, k, 0.5, 0.0, P), 100, k, 0.5, 0.0)
    assert iv[0] > iv[1] > iv[2]                   # negative correlation → downward skew


def test_sabr_limits_and_calibration():
    assert sabr_vol(100, 120, 1.0, SABRParams(0.25, 1.0, 0.0, 1e-8)) == pytest.approx(0.25,
                                                                                     rel=1e-6)
    f, t = 100.0, 0.75
    k = np.linspace(70, 140, 15)
    true = SABRParams(0.22, 1.0, -0.45, 0.8)
    vols = sabr_vol(f, k, t, true)
    assert np.isfinite(sabr_vol(f, f, t, true))    # ATM limit is smooth
    near = sabr_vol(f, [f * (1 - 1e-9), f * (1 + 1e-9)], t, true)
    assert abs(near[0] - near[1]) < 1e-8
    fit, rmse = calibrate_sabr(f, k, vols, t, beta=1.0)
    assert rmse < 1e-6
    assert fit.rho == pytest.approx(true.rho, abs=1e-3) and fit.nu == pytest.approx(true.nu,
                                                                                   abs=1e-3)


def test_merton_limits_and_monte_carlo():
    k = np.array([90.0, 100.0, 110.0])
    no_jump = MertonParams(0.2, 0.0, -0.1, 0.1)
    np.testing.assert_allclose(merton_jump_price(100, k, 1.0, 0.03, no_jump),
                               bs_price(100, k, 1.0, 0.03, 0.2), atol=1e-12)
    p = MertonParams(0.15, 0.8, -0.12, 0.2)
    c = merton_jump_price(100, k, 1.0, 0.03, p)
    put = merton_jump_price(100, k, 1.0, 0.03, p, "put")
    np.testing.assert_allclose(c - put, 100 - k * np.exp(-0.03), atol=1e-9)
    rng = np.random.default_rng(3)
    n = 400_000
    kbar = np.exp(p.mu_j + 0.5 * p.delta ** 2) - 1
    nj = rng.poisson(p.lam, n)
    logs = ((0.03 - p.lam * kbar - 0.5 * p.sigma ** 2) + p.sigma * rng.standard_normal(n)
            + nj * p.mu_j + np.sqrt(nj) * p.delta * rng.standard_normal(n))
    pay = np.exp(-0.03) * np.maximum(100 * np.exp(logs) - 100, 0)
    assert abs(pay.mean() - c[1]) < 4 * pay.std() / np.sqrt(n)


def test_heston_and_merton_calibration_recover_parameters():
    s, r = 100.0, 0.02
    quotes = []
    for t in (0.25, 0.5, 1.0):
        k = np.linspace(80, 120, 9)
        quotes.append((t, k, model_implied_vols(heston_price(s, k, t, r, P), s, k, t, r)))
    fit, rmse = calibrate_heston(s, quotes, r)
    assert rmse < 2e-3
    assert fit.rho == pytest.approx(P.rho, abs=0.1) and fit.v0 == pytest.approx(P.v0, abs=0.005)
    mp, mrmse = calibrate_merton(s, quotes, r)
    assert mrmse < 0.02 and mp.mu_j < 0                 # skew explained by negative jumps
