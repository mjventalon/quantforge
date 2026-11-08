# Contributing to quantforge

Thanks for helping! The bar for this project is **correct numbers on real data**.

## Ground rules

1. **Every model needs a reference.** Cite the paper or textbook in the module docstring.
2. **Every model needs a validation test** against a published value, a closed-form limit,
   an identity (e.g. put-call parity), or an established library.
3. **Never fabricate market data.** Library code must raise an error when data is missing
   instead of filling it in. Simulated data is allowed **only in tests**, to check
   estimators against known parameters.
4. Keep functions vectorized where it makes sense, typed, and documented (units!).

## Setup

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/quantforge && cd quantforge
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
quantforge-build-native          # C++ engine (needs a C++ compiler)
pytest -q
ruff check src tests
cmake -S src/quantforge/native/cpp -B build && cmake --build build && ctest --test-dir build
```

## C++ engine

* Header-only C++17 in `src/quantforge/native/cpp/include/quantforge`, no dependencies.
* Expose new functions through `src/capi.cpp` (plain C ABI) and wrap them in
  `quantforge/native/__init__.py`.
* Add a C++ test in `cpp/tests/test_engine.cpp` **and** a Python test comparing with the
  Python implementation in `tests/test_native.py`. Results must not depend on thread count.

## Academy content

* Chapters: `src/quantforge/academy/content/NN_slug.md` (YAML front matter + Markdown).
  Lessons must be original text; cite sources with working `https://` links.
* Exercises: `src/quantforge/academy/exercise_bank/*.yaml`. The reference solution must pass
  every test and the starter must fail at least one (enforced by `tests/test_v03_modules.py`).

## Pull requests

* One feature or fix per PR, with tests.
* Update the relevant tutorial if the public API changes (tutorial code is executed by
  `tests/test_tutorials.py`).
* Add a line to `CHANGELOG.md`.

## Ideas welcome

Heston and SABR calibration, local volatility, interest-rate models (Vasicek, Hull-White),
CVA, factor models (Fama-French), more data providers, new Academy chapters and
exercises, translations. See [ROADMAP.md](ROADMAP.md).
