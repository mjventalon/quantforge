"""The C++ engine must reproduce the Python reference implementation."""

import numpy as np
import pytest

from quantforge import native
from quantforge.pricing import (
    binomial_price,
    bs_greeks,
    bs_price,
    geometric_asian_price,
    implied_volatility,
    mc_asian,
)


@pytest.fixture(scope="module", autouse=True)
def engine():
    if not native.available():
        try:
            native.build()
        except native.NativeError as exc:
            pytest.skip(f"no C++ toolchain: {exc}")
    if not native.available():
        pytest.skip(f"C++ engine built but could not be loaded: {native.status().message}")


def test_status_and_version():
    st = native.status()
    assert st.available and st.version == "0.3.0"


@pytest.mark.parametrize("typ", ["call", "put"])
def test_black_scholes_matches_python(typ):
    rng = np.random.default_rng(0)
    n = 5000
    s, k = rng.uniform(20, 300, n), rng.uniform(20, 300, n)
    t, r = rng.uniform(0.01, 3, n), rng.uniform(-0.01, 0.08, n)
    v, q = rng.uniform(0.05, 1.2, n), rng.uniform(0, 0.05, n)
    np.testing.assert_allclose(native.bs_price(s, k, t, r, v, typ, q),
                               bs_price(s, k, t, r, v, typ, q), rtol=1e-10, atol=1e-11)
    g, ref = native.bs_greeks(s, k, t, r, v, typ, q), bs_greeks(s, k, t, r, v, typ, q)
    for name in ("delta", "gamma", "vega", "theta", "rho"):
        np.testing.assert_allclose(g[name], getattr(ref, name), rtol=1e-9, atol=1e-11,
                                   err_msg=name)


def test_hull_values_and_scalar_return():
    assert native.bs_price(42, 40, 0.5, 0.10, 0.20, "call") == pytest.approx(4.7594, abs=5e-5)
    assert isinstance(native.bs_price(42, 40, 0.5, 0.10, 0.20, "put"), float)


def test_implied_vol_matches_python():
    k = np.linspace(70, 140, 30)
    prices = bs_price(100, k, 0.5, 0.03, 0.27, "call")
    np.testing.assert_allclose(native.implied_vol(prices, 100, k, 0.5, 0.03, "call"), 0.27,
                               atol=1e-8)
    assert native.implied_vol(0.01, 100, 50, 1, 0.0, "call") != native.implied_vol(
        0.01, 100, 50, 1, 0.0, "call")    # below intrinsic -> NaN
    assert native.implied_vol(5.0, 100, 100, 1, 0.02, "put") == pytest.approx(
        implied_volatility(5.0, 100, 100, 1, 0.02, "put"), abs=1e-8)


@pytest.mark.parametrize("method", ["lr", "crr"])
@pytest.mark.parametrize("ex", ["european", "american"])
def test_binomial_matches_python(method, ex):
    for typ in ("call", "put"):
        a = native.binomial(50, 52, 5 / 12, 0.10, 0.40, typ, ex, 0.02, 301, method)
        b = binomial_price(50, 52, 5 / 12, 0.10, 0.40, typ, ex, 0.02, 301, method)
        assert a["steps"] == b.steps
        for name in ("price", "delta", "gamma", "theta"):
            assert a[name] == pytest.approx(getattr(b, name), rel=1e-9, abs=1e-10), name


def test_monte_carlo_is_unbiased_and_reproducible():
    a = native.mc_european(100, 110, 1.0, 0.05, 0.25, "put", n_paths=400_000, seed=11, threads=1)
    b = native.mc_european(100, 110, 1.0, 0.05, 0.25, "put", n_paths=400_000, seed=11, threads=4)
    assert a == b                                     # independent of the thread count
    exact = bs_price(100, 110, 1.0, 0.05, 0.25, "put")
    assert abs(a["price"] - exact) < 4 * a["std_error"]
    plain = native.mc_european(100, 110, 1.0, 0.05, 0.25, "put", n_paths=400_000, seed=11,
                               antithetic=False, control_variate=False)
    assert plain["std_error"] > a["std_error"]        # variance reduction works
    assert abs(plain["price"] - exact) < 4 * plain["std_error"]


def test_asian_matches_python():
    assert native.geometric_asian(100, 95, 1, 0.04, 0.3, 12, "call") == pytest.approx(
        geometric_asian_price(100, 95, 1, 0.04, 0.3, 12, "call"), rel=1e-12)
    c = native.mc_asian(100, 95, 1, 0.04, 0.3, 12, "call", n_paths=200_000, seed=5)
    p = mc_asian(100, 95, 1, 0.04, 0.3, 12, "call", n_paths=200_000, seed=5)
    assert abs(c["price"] - p.price) < 4 * np.hypot(c["std_error"], p.std_error)
    assert c["std_error"] == pytest.approx(p.std_error, rel=0.2)


def test_errors_are_raised_not_crashes():
    with pytest.raises(native.NativeError, match="volatility"):
        native.bs_price(100, 100, 1, 0.01, -0.2)
    with pytest.raises(ValueError):
        native.binomial(100, 100, 1, 0.01, 0.2, "call", "bermudan")


def test_benchmark_rows():
    rows = native.benchmark(n_options=2000, n_paths=20_000, tree_steps=101)
    assert len(rows) == 3
    assert rows[0]["max_abs_diff"] < 1e-9 and rows[1]["max_abs_diff"] < 1e-9
