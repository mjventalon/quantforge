"""Test-wide settings.

matplotlib is NOT a dependency of quantforge. Some tools (e.g. pandas' Styler gradients)
silently need it, so block it here: a page that relies on it fails in the tests instead of on
a user's machine."""

import sys

for _mod in ("matplotlib", "seaborn"):
    sys.modules[_mod] = None  # type: ignore[assignment]
