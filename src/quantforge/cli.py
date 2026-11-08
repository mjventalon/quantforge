"""Command-line entry points."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

THEME = ["--theme.base", "dark", "--theme.primaryColor", "#E4141D",
         "--theme.backgroundColor", "#0B0B0C", "--theme.secondaryBackgroundColor", "#16161A",
         "--browser.gatherUsageStats", "false",
         "--server.headless", "false"]          # open the browser automatically


def app() -> None:
    """Launch the web app: ``quantforge-app [streamlit options]``."""
    entry = Path(__file__).parent / "app" / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(entry), *THEME, *sys.argv[1:]]
    from quantforge.data.base import _load_dotenv_once

    _load_dotenv_once()                      # a value in .env wins over the default below
    env = dict(os.environ)
    # On your own computer the Academy may run your exercise code (Python and C++).
    # Never set this on a public server.
    env.setdefault("QUANTFORGE_ALLOW_CODE_EXECUTION", "1")
    raise SystemExit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    app()
