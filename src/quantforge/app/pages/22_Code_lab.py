"""Code Lab — every "rewrite it yourself" exercise in one place."""

import streamlit as st

from quantforge.academy import load_curriculum
from quantforge.academy.exercises import cpp_compiler, execution_allowed, load_exercises
from quantforge.app.code_exercises import STARS, render_exercise

st.title("💻 Code Lab")
st.markdown("Rewrite the core formulas of quantitative finance yourself — in **Python** and "
            "**C++** — and let the grader test them against textbook values. Start with ★, finish "
            "with a C++ Monte-Carlo pricer and an implied-volatility solver.")

prog = st.session_state.setdefault("academy", {"passed": {}, "read": [], "exercises": [],
                                               "name": ""})
prog.setdefault("exercises", [])
exercises = load_exercises()
chapters = {c.id: c for c in load_curriculum()}

c = st.columns(4)
c[0].metric("Exercises", len(exercises))
c[1].metric("Python", sum(e.language == "python" for e in exercises))
c[2].metric("C++", sum(e.language == "cpp" for e in exercises))
c[3].metric("Solved (this session)", len(prog["exercises"]))

if execution_allowed():
    st.success("Grading runs on this computer" + (f" — C++ compiler: `{cpp_compiler()}`."
                                                  if cpp_compiler() else
                                                  " (no C++ compiler found: on macOS run "
                                                  "`xcode-select --install`)."))
else:
    st.info("On this website, **Python** exercises run safely inside your browser; **C++** "
            "exercises download as a ready-to-compile file. Run quantforge on your own computer "
            "(`quantforge-app`) to have C++ graded automatically.")

f = st.columns([2, 4, 1])
lang = f[0].segmented_control("Language", ["All", "Python", "C++"], default="All")
level = f[1].segmented_control("Difficulty", ["All", *STARS.values()], default="All")
hide = f[2].toggle("Hide solved", False)

for ex in exercises:
    if lang not in (None, "All") and ex.label.split(" · ")[0] != lang:
        continue
    if level not in (None, "All") and STARS[ex.difficulty] != level:
        continue
    if hide and ex.id in prog["exercises"]:
        continue
    ch = chapters.get(ex.chapter)
    st.caption(f"Chapter {ex.chapter} — {ch.title}" if ch else "")
    render_exercise(ex, f"lab_{ex.id}", prog)
