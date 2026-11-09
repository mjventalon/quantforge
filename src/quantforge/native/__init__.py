"""quantforge C++ engine (optional, multithreaded) with a pure-Python fallback.

The C++17 sources ship inside the package (``quantforge/native/cpp``). Build once with::

    quantforge-build-native          # or: python -m quantforge.native

which needs a C++ compiler (macOS: ``xcode-select --install``; Linux: ``g++``; Windows:
MSVC/MinGW). The shared library is cached under ``~/.cache/quantforge/native``. Nothing
else changes: every function here has the same results as its ``quantforge.pricing``
counterpart, and :func:`available` tells you whether the fast path is active.

>>> from quantforge import native
>>> native.bs_price(42, 40, 0.5, 0.10, 0.20, "call")       # doctest: +SKIP
4.759422392871532
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

__all__ = ["available", "build", "library_path", "bs_price", "bs_greeks", "implied_vol",
           "binomial", "mc_european", "mc_asian", "geometric_asian", "NativeError",
           "SOURCE_DIR", "benchmark", "status"]

SOURCE_DIR = Path(__file__).parent / "cpp"
_SOURCES = [SOURCE_DIR / "src" / "capi.cpp", *sorted((SOURCE_DIR / "include").rglob("*.hpp"))]
_lib: ctypes.CDLL | None = None
_load_error = ""


class NativeError(RuntimeError):
    """The C++ engine is missing or reported an error."""


def _suffix() -> str:
    return {"Darwin": ".dylib", "Windows": ".dll"}.get(platform.system(), ".so")


def _source_hash() -> str:
    h = hashlib.sha256()
    for p in _SOURCES:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def library_path() -> Path:
    """Where the compiled library lives (override with ``QUANTFORGE_NATIVE_LIB``)."""
    if os.environ.get("QUANTFORGE_NATIVE_LIB"):
        return Path(os.environ["QUANTFORGE_NATIVE_LIB"])
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "quantforge" / "native" / _source_hash() / f"libquantforge_native{_suffix()}"


def _compiler() -> str | None:
    for c in (os.environ.get("CXX"), "c++", "clang++", "g++"):
        if c and shutil.which(c):
            return c
    return None


def build(verbose: bool = False) -> Path:
    """Compile the C++ engine. Returns the library path; raises :class:`NativeError`."""
    out = library_path()
    cxx = _compiler()
    if cxx is None:
        raise NativeError("no C++ compiler found (macOS: run `xcode-select --install`; "
                          "Linux: install g++; or set CXX)")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [cxx, "-std=c++17", "-O3", "-shared", "-fPIC", "-fvisibility=hidden",
           f"-I{SOURCE_DIR / 'include'}", str(SOURCE_DIR / "src" / "capi.cpp"), "-o",
           str(out) + ".tmp", "-pthread"]
    if platform.system() == "Windows":
        # MinGW: bundle the C++ runtime so the DLL loads without extra DLLs on the PATH
        cmd += ["-static", "-static-libgcc", "-static-libstdc++"]
    if verbose:
        print(" ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise NativeError(f"compilation failed:\n{proc.stderr.strip()}")
    os.replace(str(out) + ".tmp", out)
    global _lib, _load_error
    _lib, _load_error = None, ""
    _load()
    return out


def _load() -> ctypes.CDLL | None:
    global _lib, _load_error
    if _lib is not None:
        return _lib
    path = library_path()
    if not path.exists():
        _load_error = "not built yet — run `quantforge-build-native`"
        return None
    if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
        cxx = _compiler()                     # runtime DLLs of the compiler, if any
        if cxx and shutil.which(cxx):
            try:
                os.add_dll_directory(str(Path(shutil.which(cxx)).parent))
            except OSError:
                pass
    try:
        lib = ctypes.CDLL(str(path))
    except OSError as exc:
        _load_error = str(exc)
        return None
    d, i, ll, u64 = ctypes.c_double, ctypes.c_int, ctypes.c_longlong, ctypes.c_ulonglong
    pd, pi = ctypes.POINTER(d), ctypes.POINTER(i)
    lib.qf_version.restype = ctypes.c_char_p
    lib.qf_last_error.restype = ctypes.c_char_p
    for name in ("qf_bs_price", "qf_bs_greeks"):
        getattr(lib, name).argtypes = [pd] * 6 + [pi, ll, pd]
    lib.qf_implied_vol.argtypes = [pd] * 6 + [pi, ll, pd]
    lib.qf_binomial.argtypes = [d] * 6 + [i, i, i, i, pd]
    lib.qf_mc_european.argtypes = [d] * 6 + [i, ll, i, i, u64, i, pd]
    lib.qf_mc_asian.argtypes = [d] * 6 + [i, i, ll, i, i, u64, i, pd]
    lib.qf_geometric_asian.argtypes = [d] * 6 + [i, i, pd]
    for name in ("qf_bs_price", "qf_bs_greeks", "qf_implied_vol", "qf_binomial",
                 "qf_mc_european", "qf_mc_asian", "qf_geometric_asian"):
        getattr(lib, name).restype = i
    _lib = lib
    return lib


def available() -> bool:
    """True when the compiled C++ engine is loaded."""
    return _load() is not None


@dataclass(frozen=True)
class Status:
    available: bool
    version: str
    library: str
    compiler: str
    message: str


def status() -> Status:
    lib = _load()
    return Status(lib is not None, lib.qf_version().decode() if lib else "",
                  str(library_path()), _compiler() or "none found",
                  "ready" if lib else _load_error)


def _lib_or_raise() -> ctypes.CDLL:
    lib = _load()
    if lib is None:
        raise NativeError(f"C++ engine unavailable: {_load_error}")
    return lib


def _check(code: int) -> None:
    if code:
        raise NativeError(_lib_or_raise().qf_last_error().decode())


def _call_flag(option_type) -> int:
    t = str(getattr(option_type, "value", option_type)).lower()
    if t not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")
    return int(t == "call")


def _vec(*arrays):
    b = np.broadcast_arrays(*[np.asarray(a, dtype=float) for a in arrays])
    shape = b[0].shape
    return shape, [np.ascontiguousarray(x.ravel()) for x in b]


def _ptr(a: np.ndarray, ctype=ctypes.c_double):
    return a.ctypes.data_as(ctypes.POINTER(ctype))


def bs_price(spot, strike, maturity, rate, volatility, option_type="call", dividend_yield=0.0):
    """Vectorised Black-Scholes price (same result as :func:`quantforge.pricing.bs_price`)."""
    lib = _lib_or_raise()
    shape, (s, k, t, r, v, q) = _vec(spot, strike, maturity, rate, volatility, dividend_yield)
    flags = np.full(s.size, _call_flag(option_type), dtype=np.intc)
    out = np.empty(s.size)
    _check(lib.qf_bs_price(_ptr(s), _ptr(k), _ptr(t), _ptr(r), _ptr(v), _ptr(q),
                           _ptr(flags, ctypes.c_int), s.size, _ptr(out)))
    return float(out[0]) if shape == () else out.reshape(shape)


def bs_greeks(spot, strike, maturity, rate, volatility, option_type="call", dividend_yield=0.0):
    """Price, delta, gamma, vega, theta (per year), rho — dict of arrays (or floats)."""
    lib = _lib_or_raise()
    shape, (s, k, t, r, v, q) = _vec(spot, strike, maturity, rate, volatility, dividend_yield)
    flags = np.full(s.size, _call_flag(option_type), dtype=np.intc)
    out = np.empty((s.size, 6))
    _check(lib.qf_bs_greeks(_ptr(s), _ptr(k), _ptr(t), _ptr(r), _ptr(v), _ptr(q),
                            _ptr(flags, ctypes.c_int), s.size, _ptr(out)))
    names = ("price", "delta", "gamma", "vega", "theta", "rho")
    return {n: (float(out[0, j]) if shape == () else out[:, j].reshape(shape))
            for j, n in enumerate(names)}


def implied_vol(price, spot, strike, maturity, rate, option_type="call", dividend_yield=0.0):
    """Vectorised implied volatility; NaN where the price breaks no-arbitrage bounds."""
    lib = _lib_or_raise()
    shape, (p, s, k, t, r, q) = _vec(price, spot, strike, maturity, rate, dividend_yield)
    flags = np.full(s.size, _call_flag(option_type), dtype=np.intc)
    out = np.empty(s.size)
    _check(lib.qf_implied_vol(_ptr(p), _ptr(s), _ptr(k), _ptr(t), _ptr(r), _ptr(q),
                              _ptr(flags, ctypes.c_int), s.size, _ptr(out)))
    return float(out[0]) if shape == () else out.reshape(shape)


def binomial(spot, strike, maturity, rate, volatility, option_type="call", exercise="european",
             dividend_yield=0.0, steps=501, method="lr") -> dict:
    """Binomial tree (``method`` "lr" or "crr"): price, delta, gamma, theta, steps."""
    lib = _lib_or_raise()
    if method not in ("lr", "crr"):
        raise ValueError("method must be 'lr' or 'crr'")
    ex = str(getattr(exercise, "value", exercise)).lower()
    if ex not in ("european", "american"):
        raise ValueError("exercise must be 'european' or 'american'")
    out = np.empty(5)
    _check(lib.qf_binomial(spot, strike, maturity, rate, volatility, dividend_yield,
                           _call_flag(option_type), int(ex == "american"), int(steps),
                           int(method == "lr"), _ptr(out)))
    return {"price": out[0], "delta": out[1], "gamma": out[2], "theta": out[3],
            "steps": int(out[4])}


def _seed(seed) -> int:
    return int(np.random.SeedSequence(seed).generate_state(1, np.uint64)[0]) if seed is None \
        else int(seed) & 0xFFFFFFFFFFFFFFFF


def mc_european(spot, strike, maturity, rate, volatility, option_type="call", dividend_yield=0.0,
                n_paths=1_000_000, antithetic=True, control_variate=True, seed=None,
                threads=0) -> dict:
    """Multithreaded Monte-Carlo European option: price, std_error, n_paths."""
    lib = _lib_or_raise()
    out = np.empty(3)
    _check(lib.qf_mc_european(spot, strike, maturity, rate, volatility, dividend_yield,
                              _call_flag(option_type), int(n_paths), int(antithetic),
                              int(control_variate), _seed(seed), int(threads), _ptr(out)))
    return {"price": out[0], "std_error": out[1], "n_paths": int(out[2])}


def mc_asian(spot, strike, maturity, rate, volatility, n_fixings=252, option_type="call",
             dividend_yield=0.0, n_paths=200_000, antithetic=True, control_variate=True,
             seed=None, threads=0) -> dict:
    """Arithmetic Asian by Monte-Carlo with the geometric Asian as control variate."""
    lib = _lib_or_raise()
    out = np.empty(3)
    _check(lib.qf_mc_asian(spot, strike, maturity, rate, volatility, dividend_yield,
                           int(n_fixings), _call_flag(option_type), int(n_paths),
                           int(antithetic), int(control_variate), _seed(seed), int(threads),
                           _ptr(out)))
    return {"price": out[0], "std_error": out[1], "n_paths": int(out[2])}


def geometric_asian(spot, strike, maturity, rate, volatility, n_fixings=252, option_type="call",
                    dividend_yield=0.0) -> float:
    lib = _lib_or_raise()
    out = np.empty(1)
    _check(lib.qf_geometric_asian(spot, strike, maturity, rate, volatility, dividend_yield,
                                  int(n_fixings), _call_flag(option_type), _ptr(out)))
    return float(out[0])


def benchmark(spot=100.0, strike=100.0, maturity=1.0, rate=0.04, volatility=0.2,
              n_options=200_000, n_paths=1_000_000, tree_steps=2001) -> list[dict]:
    """Time C++ against the NumPy implementation on identical inputs; returns rows with
    both results, their difference and the speed-up."""
    from quantforge.pricing import binomial_price
    from quantforge.pricing import bs_price as py_bs
    from quantforge.pricing import mc_european as py_mc

    rows = []

    def timed(f):
        t0 = time.perf_counter()
        val = f()
        return val, time.perf_counter() - t0

    k = np.linspace(0.5, 1.5, n_options) * strike
    py, tp = timed(lambda: py_bs(spot, k, maturity, rate, volatility, "call"))
    cc, tc = timed(lambda: bs_price(spot, k, maturity, rate, volatility, "call"))
    rows.append({"task": f"Black-Scholes, {n_options:,} strikes", "python": float(py.mean()),
                 "cpp": float(cc.mean()), "max_abs_diff": float(np.abs(py - cc).max()),
                 "python_s": tp, "cpp_s": tc})
    py, tp = timed(lambda: binomial_price(spot, strike, maturity, rate, volatility, "put",
                                          "american", steps=tree_steps).price)
    cc, tc = timed(lambda: binomial(spot, strike, maturity, rate, volatility, "put", "american",
                                    steps=tree_steps)["price"])
    rows.append({"task": f"American put, {tree_steps:,}-step tree", "python": py, "cpp": cc,
                 "max_abs_diff": abs(py - cc), "python_s": tp, "cpp_s": tc})
    py, tp = timed(lambda: py_mc(spot, strike, maturity, rate, volatility, "call",
                                 n_paths=n_paths, seed=1))
    cc, tc = timed(lambda: mc_european(spot, strike, maturity, rate, volatility, "call",
                                       n_paths=n_paths, seed=1))
    rows.append({"task": f"Monte-Carlo call, {n_paths:,} paths", "python": py.price,
                 "cpp": cc["price"], "max_abs_diff": abs(py.price - cc["price"]),
                 "python_s": tp, "cpp_s": tc,
                 "note": f"different random draws; both ±{1.96 * cc['std_error']:.4f} (95%)"})
    for r in rows:
        r["speedup"] = r["python_s"] / max(r["cpp_s"], 1e-9)
    return rows


def main() -> None:  # console script: quantforge-build-native
    try:
        path = build(verbose="-v" in sys.argv)
    except NativeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"✓ quantforge C++ engine {status().version} built: {path}")
    for r in benchmark(n_options=100_000, n_paths=500_000, tree_steps=1001):
        print(f"  {r['task']:<38} C++ {r['cpp_s'] * 1e3:8.1f} ms   NumPy "
              f"{r['python_s'] * 1e3:8.1f} ms   ×{r['speedup']:.0f}")


if __name__ == "__main__":
    main()
