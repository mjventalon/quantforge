"""Public certificate verification."""

import streamlit as st

from quantforge.academy import is_development_mode, load_curriculum, verify_certificate

st.title("✅ Verify a certificate")
st.markdown("Enter the certificate ID and the holder's name exactly as printed. The ID is a "
            "cryptographic signature of the name, chapter and date: it cannot be forged without "
            "the site's private key.")

c = st.columns([2, 2, 1])
cid = c[0].text_input("Certificate ID", placeholder="QF-03-20261107-XXXXXXXXXX")
name = c[1].text_input("Holder's name")
go = c[2].button("Verify", type="primary")

if go:
    if not cid or not name:
        st.warning("Enter both the ID and the name.")
    else:
        info = verify_certificate(cid, name)
        if info.valid:
            chapters = {c.id: c for c in load_curriculum()}
            what = ("the full Quantitative Finance Program" if info.chapter == 0 else
                    f"Chapter {info.chapter} — {chapters[info.chapter].title}"
                    if info.chapter in chapters else f"chapter {info.chapter}")
            st.success(f"✅ Valid. **{name.strip()}** completed **{what}** on "
                       f"**{info.issued:%B %d, %Y}**.")
        else:
            st.error(f"❌ Not valid: {info.reason}")
if is_development_mode():
    st.caption("This deployment runs in development mode (no private key configured); it can "
               "only verify development certificates.")
st.caption("quantforge certificates attest completion of quantforge Academy content and quizzes. "
           "They are not academic degrees, professional licenses or regulatory qualifications.")
