"""Home page."""

import streamlit as st

from quantforge import __version__
from quantforge.app import branding as B
from quantforge.app.common import md
from quantforge.app.navigation import PAGES_DIR, SECTIONS

c1, c2 = st.columns([1, 4], vertical_alignment="center")
c1.image(str(B.ICON), width=150)
c2.markdown(f"<p class='qf-hero'>{B.APP_NAME}</p>", unsafe_allow_html=True)
c2.markdown(f"#### {B.TAGLINE}")
c2.caption(f"v{__version__} · Built by **{B.AUTHOR}**")

st.markdown("""
Every number comes from a real source — Yahoo Finance, Massive (Polygon), FMP or Alpha Vantage
for markets, FRED for interest rates and inflation. Nothing is made up: if a source fails, you
see the error. Every model is validated against textbooks and reference libraries.
""")

c1, c2, c3 = st.columns([2, 2, 2])
with c1, st.container(border=True):
    st.markdown("##### 🎓 New to finance?")
    st.markdown("Start the **Academy**: 23 chapters from *what is a stock* to Monte-Carlo, GARCH "
                "and VaR, with interactive tools, quizzes and certificates.")
    st.page_link(str(PAGES_DIR / "16_Academy.py"), label="Open the Academy", icon="🎓")
with c2, st.container(border=True):
    st.markdown("##### ⚡ Want to see the market now?")
    st.markdown("Live intraday charts that update by themselves, plus heatmaps of sectors and "
                "asset classes.")
    st.page_link(str(PAGES_DIR / "01_Live_market.py"), label="Live market", icon="⚡")
with c3, st.container(border=True):
    st.markdown("##### 🔌 Connection check")
    if st.button("Test data source", type="primary"):
        m = md()
        try:
            st.success(f"{m.source}: SPY last price **{m.quote('SPY'):,.2f}**")
        except Exception as exc:  # noqa: BLE001
            st.error(f"{m.source}: {exc}")
        try:
            st.success(f"FRED: 3-month Treasury yield **{m.risk_free_rate('3M'):.2%}**")
        except Exception as exc:  # noqa: BLE001
            st.error(f"FRED: {exc}")

st.divider()
st.markdown("### All tools")
sections = [s for s in SECTIONS if s not in ("Start", "About")]
for row in range(0, len(sections), 3):
    cols = st.columns(3)
    for col, section in zip(cols, sections[row:row + 3]):
        with col:
            st.markdown(f"**{section}**")
            for f, title, icon, desc in SECTIONS[section]:
                with st.container(border=True):
                    st.page_link(str(PAGES_DIR / f), label=title, icon=icon)
                    st.caption(desc)

st.caption("🖱️ On every chart: scroll = zoom · click-drag = move · double-click = reset · "
           "camera = save PNG.")
st.caption(f"© 2026 {B.AUTHOR} · MIT license · Research and educational software, not investment "
           "advice · see Policies.")
