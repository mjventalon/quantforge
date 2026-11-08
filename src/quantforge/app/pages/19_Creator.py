"""About the creator."""

import streamlit as st

from quantforge import __version__
from quantforge.app import branding as B

c1, c2 = st.columns([1, 3], vertical_alignment="center")
c1.image(str(B.ICON), width=180)
with c2:
    st.title(B.AUTHOR)
    st.markdown(f"**{B.AUTHOR_ROLE} of {B.APP_NAME}**")
    links = []
    if B.LINKEDIN_URL:
        links.append(f"[🔗 LinkedIn]({B.LINKEDIN_URL})")
    if B.GITHUB_URL:
        links.append(f"[💻 GitHub]({B.GITHUB_URL})")
    if B.CONTACT_EMAIL:
        links.append(f"[✉️ {B.CONTACT_EMAIL}](mailto:{B.CONTACT_EMAIL})")
    st.markdown(" · ".join(links))

st.markdown(f"""
### Why I built {B.APP_NAME}

Professional quantitative tools — option pricers, risk engines, backtesters, regime models —
usually sit behind expensive terminals, and the courses that teach them are scattered across
textbooks and university lectures. {B.APP_NAME} brings both together in one free, open-source
platform:

- **a research workbench** that runs real models on real market data, and
- **an academy** that takes anyone from zero to running those models, with verifiable
  certificates.

### Principles

1. **Real data only** — nothing is invented; failures are shown, not hidden.
2. **Validated maths** — every model is tested against textbooks and reference libraries.
3. **Honest research** — no look-ahead, costs included, out-of-sample tests by default.
4. **Explained** — every page has a how-to, every chapter cites its sources.

### Built with

Python · NumPy · SciPy · pandas · Plotly · Streamlit · data from Yahoo Finance, Massive
(Polygon.io), Financial Modeling Prep, Alpha Vantage and FRED.

---
{B.APP_NAME} v{__version__} · open source under the MIT license · *conçu avec soin* 🇫🇷
""")
st.caption("Research and education only — nothing on this site is investment advice.")
