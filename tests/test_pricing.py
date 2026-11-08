import numpy as np
import pandas as pd
import pytest

from quantforge.pricing import (
    barrier_price,
    binomial_price,
    black76_price,
    bs_delta,
    bs_gamma,
    bs_greeks,
    bs_price,
    bs_rho,
    bs_theta,
    bs_vega,
    chain_implied_vols,
    geometric_asian_price,
    implied_volatility,
    mc_asian,
    mc_barrier,
    mc_european,
    simulate_gbm_paths,
    surface_grid,
    svi_total_variance,
)
from quantforge.pricing.strategies import PRESETS, OptionLeg, StockLeg, Strategy

ARGS = (42.0, 40.0, 0.5, 0.10, 0.20)


# ------------------------------------------------------------------ Black-Scholes
def test_hull_example():
    assert bs_price(*ARGS, "call") == pytest.approx(4.7594, abs=1e-4)
    assert bs_price(*ARGS, "put") == pytest.approx(0.8086, abs=1e-4)


@pytest.mark.parametrize("q", [0.0, 0.03])
def test_put_call_parity(q):
    s, k, t, r, v = ARGS
    c, p = bs_price(*ARGS, "call", q), bs_price(*ARGS, "put", q)
    assert c - p == pytest.approx(s * np.exp(-q * t) - k * np.exp(-r * t), abs=1e-12)


@pytest.mark.parametrize("opt", ["call", "put"])
def test_greeks_match_finite_differences(opt):
    s, k, t, r, v = ARGS
    q, h = 0.02, 1e-4
    f = lambda **kw: bs_price(**{**dict(spot=s, strike=k, maturity=t, rate=r, volatility=v,
                                        option_type=opt, dividend_yield=q), **kw})
    assert bs_delta(s, k, t, r, v, opt, q) == pytest.approx(
        (f(spot=s + h) - f(spot=s - h)) / (2 * h), rel=1e-6)
    assert bs_gamma(s, k, t, r, v, q) == pytest.approx(
        (f(spot=s + h) - 2 * f() + f(spot=s - h)) / h**2, rel=1e-4)
    assert bs_vega(s, k, t, r, v, q) == pytest.approx(
        (f(volatility=v + h) - f(volatility=v - h)) / (2 * h), rel=1e-6)
    assert bs_rho(s, k, t, r, v, opt, q) == pytest.approx(
        (f(rate=r + h) - f(rate=r - h)) / (2 * h), rel=1e-6)
    assert bs_theta(s, k, t, r, v, opt, q) == pytest.approx(
        -(f(maturity=t + h) - f(maturity=t - h)) / (2 * h), rel=1e-5)


def test_vectorized_and_greeks_bundle():
    strikes = np.array([30.0, 40.0, 50.0])
    px = bs_price(42, strikes, 0.5, 0.1, 0.2)
    assert px.shape == (3,) and np.all(np.diff(px) < 0)
    g = bs_greeks(*ARGS)
    assert g.price == pytest.approx(bs_price(*ARGS))
    assert 0 < g.delta < 1 and g.gamma > 0 and g.vega > 0


@pytest.mark.parametrize("opt", ["call", "put"])
@pytest.mark.parametrize("vol", [0.05, 0.2, 0.8, 2.0])
def test_implied_vol_round_trip(opt, vol):
    px = bs_price(100, 110, 0.75, 0.04, vol, opt, 0.01)
    assert implied_volatility(px, 100, 110, 0.75, 0.04, opt, 0.01) == pytest.approx(vol, abs=1e-7)


def test_implied_vol_array_and_bounds():
    vols = np.array([0.1, 0.3, 0.6])
    pxs = bs_price(100, 100, 1.0, 0.03, vols)
    np.testing.assert_allclose(implied_volatility(pxs, 100, 100, 1.0, 0.03), vols, atol=1e-7)
    with pytest.raises(ValueError, match="no-arbitrage"):
        implied_volatility(150.0, 100, 100, 1.0, 0.03)


def test_black76_equals_bs_on_forward():
    f, k, t, r, v = 105.0, 100.0, 1.0, 0.05, 0.25
    assert black76_price(f, k, t, r, v) == pytest.approx(
        np.exp(-r * t) * bs_price(f, k, t, 0.0, v), rel=1e-12)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        bs_price(-1, 40, 0.5, 0.1, 0.2)
    with pytest.raises(ValueError):
        bs_price(42, 40, 0.5, 0.1, 0.2, "straddle")


# ------------------------------------------------------------------ binomial
@pytest.mark.parametrize("method", ["crr", "lr"])
@pytest.mark.parametrize("opt", ["call", "put"])
def test_binomial_european_converges(method, opt):
    res = binomial_price(*ARGS, opt, "european", steps=1001, method=method)
    assert res.price == pytest.approx(bs_price(*ARGS, opt), abs=2e-3 if method == "crr" else 1e-5)
    assert res.delta == pytest.approx(bs_delta(*ARGS, opt), abs=2e-3)
    assert res.gamma == pytest.approx(bs_gamma(*ARGS), rel=2e-2)


def test_hull_american_put():
    res = binomial_price(50, 50, 5 / 12, 0.10, 0.40, "put", "american", steps=2001)
    assert res.price == pytest.approx(4.284, abs=2e-3)
    euro = binomial_price(50, 50, 5 / 12, 0.10, 0.40, "put", "european", steps=2001)
    assert res.price > euro.price  # early-exercise premium


def test_american_call_without_dividends_equals_european():
    a = binomial_price(*ARGS, "call", "american", steps=501).price
    e = binomial_price(*ARGS, "call", "european", steps=501).price
    assert a == pytest.approx(e, abs=1e-10)


def test_american_call_with_dividends_worth_more():
    a = binomial_price(100, 90, 1, 0.03, 0.2, "call", "american", 0.08, steps=501).price
    e = binomial_price(100, 90, 1, 0.03, 0.2, "call", "european", 0.08, steps=501).price
    assert a > e + 0.1


# ------------------------------------------------------------------ Monte-Carlo
def test_gbm_paths_shape_and_mean():
    p = simulate_gbm_paths(100, 1.0, 0.05, 0.2, 200_000, 4, antithetic=True, seed=1)
    assert p.shape == (200_000, 5)
    assert p[:, -1].mean() == pytest.approx(100 * np.exp(0.05), rel=2e-3)


@pytest.mark.parametrize("opt", ["call", "put"])
def test_mc_european_within_3se(opt):
    res = mc_european(*ARGS, opt, n_paths=200_000, seed=42)
    assert abs(res.price - bs_price(*ARGS, opt)) < 3 * res.std_error
    lo, hi = res.conf_interval
    assert lo < res.price < hi


def test_mc_reproducible():
    assert mc_european(*ARGS, seed=7).price == mc_european(*ARGS, seed=7).price


def test_control_variate_reduces_error():
    plain = mc_european(*ARGS, n_paths=50_000, antithetic=False, control_variate=False, seed=3)
    cv = mc_european(*ARGS, n_paths=50_000, antithetic=True, control_variate=True, seed=3)
    assert cv.std_error < plain.std_error / 2


def test_geometric_asian_closed_form_vs_mc():
    exact = geometric_asian_price(100, 100, 1, 0.05, 0.25, 12)
    mc = mc_asian(100, 100, 1, 0.05, 0.25, 12, average="geometric", n_paths=200_000, seed=5)
    assert abs(mc.price - exact) < 3 * mc.std_error


def test_arithmetic_asian_above_geometric_and_below_vanilla():
    arith = mc_asian(100, 100, 1, 0.05, 0.25, 52, seed=2).price
    geo = geometric_asian_price(100, 100, 1, 0.05, 0.25, 52)
    assert geo < arith < bs_price(100, 100, 1, 0.05, 0.25)


@pytest.mark.parametrize("kind,h", [("down-and-out", 90), ("down-and-in", 90),
                                    ("up-and-out", 115), ("up-and-in", 115)])
@pytest.mark.parametrize("opt", ["call", "put"])
def test_mc_barrier_matches_closed_form(kind, h, opt):
    exact = barrier_price(100, 100, h, 1, 0.05, 0.2, kind, opt, 0.01)
    mc = mc_barrier(100, 100, h, 1, 0.05, 0.2, kind, opt, 0.01, n_steps=500,
                    n_paths=200_000, seed=11)
    assert abs(mc.price - exact) < 4 * mc.std_error + 0.01


@pytest.mark.parametrize("opt", ["call", "put"])
@pytest.mark.parametrize("h,k", [(90, 100), (95, 90), (110, 100), (105, 110)])
def test_barrier_in_out_parity(opt, h, k):
    up = h > 100
    kinds = ("up-and-in", "up-and-out") if up else ("down-and-in", "down-and-out")
    total = sum(barrier_price(100, k, h, 1, 0.05, 0.25, kd, opt, 0.02) for kd in kinds)
    assert total == pytest.approx(bs_price(100, k, 1, 0.05, 0.25, opt, 0.02), abs=1e-10)


def test_barrier_reference_value():
    assert barrier_price(100, 100, 90, 1, 0.05, 0.2, "down-and-out", "call") == pytest.approx(
        8.6655, abs=1e-4)


# ------------------------------------------------------------------ surface
def _synthetic_chain(today):
    """Quotes generated from a known SVI surface — used only to test the round trip."""
    s, r, rows = 100.0, 0.04, []
    for d in (30, 60, 120, 250):
        t = d / 365
        f = s * np.exp(r * t)
        for k in np.arange(70, 135, 2.5):
            w = svi_total_variance(np.log(k / f), 0.02 * t, 0.15 * np.sqrt(t), -0.5, 0.0, 0.15)
            iv = np.sqrt(w / t)
            for typ in ("call", "put"):
                px = bs_price(s, k, t, r, iv, typ)
                rows.append(dict(expiry=today + pd.Timedelta(days=d), strike=k, type=typ,
                                 bid=px * 0.995, ask=px * 1.005, last=px, implied_vol=iv))
    df = pd.DataFrame(rows)
    df["mid"] = (df.bid + df.ask) / 2
    return df, s, r


def test_iv_surface_round_trip():
    today = pd.Timestamp("2026-01-02")
    chain, s, r = _synthetic_chain(today)
    ivs = chain_implied_vols(chain, s, r, as_of=today.date())
    np.testing.assert_allclose(ivs["iv"], ivs["provider_iv"], atol=1e-8)
    k, t, iv, params = surface_grid(ivs)
    assert iv.shape == (len(t), len(k))
    np.testing.assert_allclose(params["rho"], -0.5, atol=1e-3)
    assert params["rmse_vol"].max() < 1e-4


# ------------------------------------------------------------------ strategies
def test_bull_call_spread_payoff_and_breakeven():
    s = Strategy([OptionLeg("call", 100, 1), OptionLeg("call", 110, -1)])
    assert s.payoff(90) == 0 and s.payoff(105) == 5 and s.payoff(150) == 10
    cost = s.entry_cost(100, 0.5, 0.03, 0.25)
    be = s.breakevens(100, 0.5, 0.03, 0.25)
    assert len(be) == 1 and be[0] == pytest.approx(100 + cost, abs=1e-3)


def test_covered_call_delta_and_presets_build():
    s = Strategy([StockLeg(1), OptionLeg("call", 105, -1)])
    d = s.value(100.0, 0.5, 0.03, 0.25)["delta"][0]
    assert 0 < d < 1
    for name, f in PRESETS.items():
        st = Strategy(f(100.0), name)
        assert np.isfinite(st.entry_cost(100, 0.25, 0.03, 0.3))
