"""quantforge Academy — lessons, coding exercises, quizzes and certificates."""

import json
from datetime import date
from urllib.parse import quote, unquote

import streamlit as st

from quantforge.academy import (
    LEVELS,
    PASS_MARK,
    certificate_pdf,
    is_development_mode,
    load_curriculum,
    make_certificate_id,
    sign_progress,
    verify_progress,
)
from quantforge.academy.exercises import exercises_for, load_exercises
from quantforge.app import branding as B
from quantforge.app.academy_widgets import render
from quantforge.app.code_exercises import embed_html, render_exercise

st.title("🎓 quantforge Academy")
chapters = load_curriculum()
by_id = {c.id: c for c in chapters}
prog = st.session_state.setdefault("academy", {"passed": {}, "read": [], "exercises": [],
                                               "name": ""})
prog.setdefault("exercises", [])
prog.setdefault("name", "")
n_ex = len(load_exercises())


def _remember_name(name: str) -> None:
    """Keep the learner's name in a first-party cookie for one year (this device only)."""
    v = json.dumps(quote(name))
    embed_html(
        "<script>const c = 'qf_learner=' + " + v + " + '; path=/; max-age=31536000; "
        "SameSite=Lax';try { window.parent.document.cookie = c; } catch (e) {}"
        "try { document.cookie = c; } catch (e) {}</script>", 1)


if not prog["name"]:
    try:
        cookie = st.context.cookies.get("qf_learner")
    except Exception:  # noqa: BLE001 - cookies unavailable (tests, old browsers)
        cookie = None
    if isinstance(cookie, str) and cookie.strip():
        prog["name"] = " ".join(unquote(cookie).split())[:80]

st.markdown("From **zero** — what a stock is — to running **Monte-Carlo, GARCH, VaR and regime "
            "models** on real data, then **rewriting them yourself in Python and C++**. Each "
            "chapter: a lesson, interactive tools on live data, coding exercises, a quiz (pass mark "
            f"**{PASS_MARK:.0%}**) and a **certificate** with a verifiable ID.")

# ---------------------------------------------------------------- learner profile
with st.container(border=True):
    editing = st.session_state.get("edit_name", not prog["name"])
    if prog["name"] and not editing:
        c = st.columns([5, 1], vertical_alignment="center")
        c[0].markdown(f"👤 Certificates are issued to **{prog['name']}**")
        if c[1].button("Change", key="change_name"):
            st.session_state["edit_name"] = True
            st.rerun()
    else:
        c = st.columns([4, 1], vertical_alignment="bottom")
        new = c[0].text_input("Your full name, as it should appear on your certificates",
                              value=prog["name"], max_chars=80, key="name_field",
                              placeholder="e.g. Ada Lovelace")
        if c[1].button("Save", type="primary", key="save_name") and new.strip():
            prog["name"] = " ".join(new.split())
            st.session_state["edit_name"] = False
            st.session_state["name_saved"] = True
            st.rerun()
        st.caption("Saved in this browser (cookie on this device) and in your progress file. "
                   "You can change it at any time; certificate IDs are tied to the exact name.")
    if st.session_state.pop("name_saved", False):
        _remember_name(prog["name"])
        st.toast(f"Saved — welcome, {prog['name'].split()[0]}!", icon="✅")

done = len(prog["passed"])
c = st.columns([3, 1, 1, 1, 1])
c[0].progress(done / len(chapters), f"Progress: {done}/{len(chapters)} chapters passed")
c[1].metric("Chapters", len(chapters))
c[2].metric("Quiz questions", sum(len(ch.quiz) for ch in chapters))
c[3].metric("Coding exercises", f"{len(prog['exercises'])}/{n_ex}")
c[4].metric("Study time", f"~{sum(ch.minutes for ch in chapters) / 60:.0f} h")

with st.expander("💾 Save or restore your progress"):
    st.caption("Progress lives in this browser session. Download it to continue later or on "
               "another device. The file is sealed: edited files are rejected.")
    st.download_button("Download progress (.json)", json.dumps(sign_progress(prog)).encode(),
                       "quantforge_academy_progress.json")
    up = st.file_uploader("Restore progress", type=["json"])
    if up is not None and st.session_state.get("academy_restored") != up.file_id:
        try:
            restored = verify_progress(json.loads(up.read()))
        except ValueError:
            restored = None
        if restored is None:
            st.error("This file is not a valid quantforge progress file (it was edited or comes "
                     "from another deployment).")
        else:
            st.session_state["academy"] = restored
            st.session_state["academy_restored"] = up.file_id
            st.success("Progress restored.")
            st.rerun()

# ---------------------------------------------------------------- syllabus
tabs = st.tabs([f"L{lv} · {name}" for lv, name in LEVELS.items()])
for tab, lv in zip(tabs, LEVELS):
    with tab:
        for ch in [c for c in chapters if c.level == lv]:
            passed = prog["passed"].get(str(ch.id))
            badge = f"✅ {passed['score']:.0%}" if passed else ("📖" if ch.id in prog["read"]
                                                               else "⬜")
            exs = exercises_for(ch.id)
            code = ""
            if exs:
                langs = sorted({"Python" if e.language == "python" else "C++" for e in exs},
                               reverse=True)
                code = (f" · 💻 {len(exs)} exercise{'s' if len(exs) > 1 else ''} "
                        f"({', '.join(langs)})")
            cols = st.columns([6, 1])
            cols[0].markdown(f"{badge} **Chapter {ch.id} — {ch.title}**  \n"
                             f"<span style='opacity:.7'>{ch.minutes} min{code} · "
                             f"{ch.objectives[0]}</span>", unsafe_allow_html=True)
            if cols[1].button("Open", key=f"open_{ch.id}"):
                st.session_state["academy_ch"] = ch.id
                st.rerun()

st.divider()
cid = st.session_state.get("academy_ch", 1)
cid = st.selectbox("Chapter", [c.id for c in chapters], index=cid - 1,
                   format_func=lambda i: f"{i:02d} · {by_id[i].title}  (L{by_id[i].level})")
ch = by_id[cid]
st.session_state["academy_ch"] = cid
if cid not in prog["read"]:
    prog["read"].append(cid)

# ---------------------------------------------------------------- lesson
st.markdown(f"<span style='color:{B.BRAND_RED};font-weight:700'>LEVEL {ch.level} · "
            f"{ch.level_name.upper()} · CHAPTER {ch.id}</span>", unsafe_allow_html=True)
st.header(ch.title)
st.caption(f"⏱️ about {ch.minutes} minutes")
with st.container(border=True):
    st.markdown("**You will learn to**")
    for o in ch.objectives:
        st.markdown(f"- {o}")

for kind, content in ch.blocks():
    if kind == "md":
        st.markdown(content)
    else:
        render(content, f"ch{ch.id}")

exs = exercises_for(ch.id)
if exs:
    st.subheader("💻 Rewrite it yourself")
    st.caption("Reading a formula is not the same as knowing it. Rewrite it in code — the grader "
               "runs real tests, including textbook values.")
    for ex in exs:
        render_exercise(ex, f"ex_{ex.id}", prog)

with st.expander("📚 Sources and further reading", expanded=True):
    for s in ch.sources:
        link = f" — [{s.url}]({s.url})" if s.url else ""
        st.markdown(f"- **{s.title}** · {s.by}{link}")
    st.caption("quantforge lessons are original texts. The references above are where to go "
               "deeper; quantforge is not affiliated with these institutions or authors.")

# ---------------------------------------------------------------- quiz
st.subheader(f"📝 Chapter {ch.id} quiz")
with st.form(f"quiz_{ch.id}"):
    answers = []
    for i, q in enumerate(ch.quiz):
        answers.append(st.radio(f"**{i + 1}. {q.q}**", range(len(q.options)), index=None,
                                format_func=lambda j, q=q: q.options[j], key=f"q_{ch.id}_{i}"))
    submitted = st.form_submit_button("Submit answers", type="primary")

if submitted:
    if any(a is None for a in answers):
        st.warning("Answer every question first.")
    else:
        correct = [a == q.answer for a, q in zip(answers, ch.quiz)]
        score = sum(correct) / len(correct)
        for i, (ok, q) in enumerate(zip(correct, ch.quiz)):
            (st.success if ok else st.error)(
                f"{i + 1}. {'Correct' if ok else 'Incorrect'} — answer: "
                f"**{q.options[q.answer]}**. {q.why}")
        if score >= PASS_MARK:
            st.balloons()
            prev = prog["passed"].get(str(ch.id), {}).get("score", 0)
            prog["passed"][str(ch.id)] = {"score": max(score, prev),
                                          "date": date.today().isoformat()}
            st.success(f"Passed with {score:.0%}! Your certificate is ready below.")
        else:
            st.info(f"Score {score:.0%}. You need {PASS_MARK:.0%} — reread the sections linked to "
                    "the questions you missed and try again.")


# ---------------------------------------------------------------- certificates
def _issue(chapter: int, title: str, subtitle: str, score: float, day: date, fname: str,
           label: str) -> None:
    name = prog["name"]
    if not name:
        st.info("Enter your name at the top of the page to receive your certificate.")
        return
    cert = make_certificate_id(name, chapter, day)
    verify = f"{B.SITE_URL.rstrip('/')}/verify" if B.SITE_URL else ""
    pdf = certificate_pdf(name, title, subtitle, cert, score, day, B.ICON,
                          f"{B.APP_NAME} Academy", f"{B.AUTHOR}, {B.AUTHOR_ROLE}", verify,
                          PASS_MARK)
    st.markdown(f"Issued to **{name}** · {day:%B %d, %Y}")
    st.download_button(label, pdf, fname, "application/pdf", type="primary",
                       key=f"dl_{chapter}")
    st.code(cert, language=None)


passed = prog["passed"].get(str(ch.id))
if passed:
    st.subheader("🏅 Your certificate")
    _issue(ch.id, f"Chapter {ch.id} — {ch.title}", f"Level {ch.level} · {ch.level_name}",
           passed["score"], date.fromisoformat(passed["date"]),
           f"quantforge_certificate_ch{ch.id:02d}.pdf", "⬇️ Download certificate (PDF)")
    if is_development_mode():
        st.caption("⚠️ This deployment has no certificate secret configured: certificates are "
                   "marked DEVELOPMENT. The site owner sets QUANTFORGE_CERT_SECRET for official "
                   "ones.")

if len(prog["passed"]) == len(chapters):
    st.divider()
    st.subheader("🏆 Program certificate — Quantitative Finance Program")
    day = max(date.fromisoformat(v["date"]) for v in prog["passed"].values())
    avg = sum(v["score"] for v in prog["passed"].values()) / len(prog["passed"])
    _issue(0, f"Quantitative Finance Program — all {len(chapters)} chapters",
           f"Levels 1–{max(LEVELS)} · Foundations to Quant Programming", avg, day,
           "quantforge_program_certificate.pdf", "⬇️ Download program certificate")
