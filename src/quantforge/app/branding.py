"""Brand and creator settings. Override any value with an environment variable
(e.g. on your hosting platform) without touching the code."""

from __future__ import annotations

import os
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"

APP_NAME = os.environ.get("QUANTFORGE_APP_NAME", "quantforge")
TAGLINE = "Professional quantitative finance — on real market data"
AUTHOR = os.environ.get("QUANTFORGE_AUTHOR", "Marin J. Ventalon")
AUTHOR_ROLE = "Founder & developer"
LINKEDIN_URL = os.environ.get("QUANTFORGE_LINKEDIN", "https://www.linkedin.com/in/marin-ventalon")
GITHUB_URL = os.environ.get("QUANTFORGE_GITHUB", "")          # e.g. https://github.com/<you>/quantforge
CONTACT_EMAIL = os.environ.get("QUANTFORGE_CONTACT_EMAIL", "")  # a dedicated project address
SITE_URL = os.environ.get("QUANTFORGE_SITE_URL", "")            # e.g. https://quantforge.app

BRAND_RED = "#E4141D"
LOGO = ASSETS / "logo.png"
ICON = ASSETS / "icon-512.png"
ICON_SMALL = ASSETS / "icon-64.png"
FAVICON = ASSETS / "icon-64.png"

LAST_UPDATED = "2026-11-07"
