"""quantforge web app — entry point.

Run with ``quantforge-app`` (or ``streamlit run src/quantforge/app/app.py``).
"""

import streamlit as st

from quantforge.app import branding as B
from quantforge.app import copilot
from quantforge.app.common import sidebar
from quantforge.app.navigation import PAGES_DIR, SECTIONS, url_slug
from quantforge.app.smooth_zoom import install as smooth_zoom

copilot.install()          # records widgets so the AI copilot can read and fill pages

st.set_page_config(page_title=f"{B.APP_NAME} — quantitative finance", page_icon=str(B.FAVICON),
                   layout="wide", initial_sidebar_state="expanded",
                   menu_items={"About": f"**{B.APP_NAME}** — built by {B.AUTHOR}. "
                                        "Research and education only; not investment advice."})
st.logo(str(B.ICON), size="large", link=B.SITE_URL or None, icon_image=str(B.ICON_SMALL))

st.markdown(f"""
<style>
  [data-testid="stSidebarNav"] span {{ font-size: 0.92rem; }}
  p.qf-hero, .stMarkdown p.qf-hero {{ font-size: 2.8rem !important; font-weight: 800;
                                      letter-spacing: -0.02em; margin: 0; line-height: 1.1; }}
  .qf-red {{ color: {B.BRAND_RED}; }}
  div[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
  .stTextArea textarea {{ font-family: ui-monospace, Menlo, Consolas, monospace;
                          font-size: 0.85rem; line-height: 1.45; tab-size: 4; }}
</style>
""", unsafe_allow_html=True)

pages = {
    section: [st.Page(str(PAGES_DIR / f), title=title, icon=icon, url_path=url_slug(title),
                      default=(f == "00_Home.py"))
              for f, title, icon, _ in items]
    for section, items in SECTIONS.items()
}
nav = st.navigation(pages, expanded=True)
copilot.start_run(nav.title)
applied = copilot.apply_pending_changes()
copilot_slot = st.sidebar.container()
sidebar()
with st.sidebar:
    smooth_zoom(st.session_state.get("zoom_speed", "Normal"))
st.session_state["_qf_howto"] = ""
if applied:
    st.toast("🤖 Copilot filled: " + "; ".join(applied[:4]), icon="✏️")
nav.run()
with copilot_slot:
    copilot.render(
        nav.title, st.session_state.get("_qf_howto", ""),
        {t: d for items in SECTIONS.values() for _, t, _, d in items},
        {p.title: p for group in pages.values() for p in group})
