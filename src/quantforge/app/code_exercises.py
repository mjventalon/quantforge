"""Streamlit UI for the Academy's "rewrite it yourself" coding exercises."""

from __future__ import annotations

import json

import streamlit as st

from quantforge.academy.exercises import (
    RESULT_MARK,
    Exercise,
    cpp_compiler,
    cpp_source,
    execution_allowed,
    python_harness,
    run_exercise,
)

PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/"
STARS = {1: "★☆☆ beginner", 2: "★★☆ intermediate", 3: "★★★ advanced"}


def embed_html(html: str, height: int) -> None:
    """Render trusted HTML+JS in an iframe (st.iframe on recent Streamlit, components before)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:                                         # Streamlit < 1.5x
        import streamlit.components.v1 as components
        components.html(html, height=height, scrolling=True)


def _js(value: str) -> str:
    """JSON-encode for safe embedding inside a <script> block."""
    return json.dumps(value).replace("</", "<\\/")


def _browser_python(ex: Exercise, key: str) -> None:
    """Editor + grader that runs entirely in the visitor's browser (Pyodide/WebAssembly)."""
    html = f"""
<div style="font-family: ui-sans-serif, system-ui; color: #EDEDED">
<textarea id="code" spellcheck="false" style="width:100%; height:300px; background:#0B0B0C;
 color:#F2F2F2; border:1px solid #333; border-radius:8px; padding:10px;
 font: 13px/1.45 ui-monospace, Menlo, Consolas, monospace; tab-size:4"></textarea>
<div style="margin:8px 0; display:flex; gap:8px">
 <button id="run" style="background:#E4141D; color:white; border:0; border-radius:8px;
  padding:8px 16px; font-weight:600; cursor:pointer">▶ Run the tests</button>
 <button id="reset" style="background:#222; color:#ddd; border:1px solid #444; border-radius:8px;
  padding:8px 12px; cursor:pointer">Reset</button>
</div>
<div id="out" style="white-space:pre-wrap; font: 13px/1.5 ui-monospace, Menlo, monospace"></div>
</div>
<script src="{PYODIDE}pyodide.js"></script>
<script>
const STARTER = {_js(ex.starter)}, HARNESS = {_js(python_harness(ex))}, MARK = {_js(RESULT_MARK)};
const KEY = "qf_ex_" + {_js(ex.id)};
const ta = document.getElementById("code"), out = document.getElementById("out");
try {{ ta.value = localStorage.getItem(KEY) || STARTER; }} catch (e) {{ ta.value = STARTER; }}
ta.addEventListener("input", () => {{ try {{ localStorage.setItem(KEY, ta.value); }} catch (e) {{}} }});
ta.addEventListener("keydown", e => {{ if (e.key === "Tab") {{ e.preventDefault();
  const s = ta.selectionStart; ta.setRangeText("    ", s, ta.selectionEnd, "end"); }} }});
document.getElementById("reset").onclick = () => {{ ta.value = STARTER;
  try {{ localStorage.removeItem(KEY); }} catch (e) {{}} out.textContent = ""; }};
let py = null;
document.getElementById("run").onclick = async () => {{
  try {{
    if (!py) {{ out.textContent = "Loading Python in your browser (first time only, ~10 s)…";
      py = await loadPyodide({{ indexURL: "{PYODIDE}" }}); await py.loadPackage("numpy"); }}
    out.textContent = "Running…";
    let printed = "";
    py.setStdout({{ batched: s => printed += s + "\\n" }});
    py.setStderr({{ batched: s => printed += s + "\\n" }});
    py.globals.set("LEARNER_CODE", ta.value);
    await py.runPythonAsync(HARNESS);
    const line = printed.split("\\n").find(l => l.startsWith(MARK));
    const res = JSON.parse(line.slice(MARK.length));
    const ok = res.filter(r => r.ok).length;
    out.innerHTML = res.map(r => (r.ok ? "✅ " : "❌ ") + r.name.replace(/</g, "&lt;") +
      (r.message ? "<br><span style='opacity:.75'>   " + r.message.replace(/</g, "&lt;") + "</span>" : "")).join("<br>") +
      "<br><br><b>" + (ok === res.length ? "🎉 All " + ok + " tests pass!" : ok + " / " + res.length + " tests pass") + "</b>";
  }} catch (err) {{ out.textContent = "Error: " + err; }}
}};
</script>"""
    embed_html(html, 560)
    st.caption("Runs privately in your browser with Pyodide (Python compiled to WebAssembly). "
               "Your code is saved in this browser and never sent to the server.")


def _editor(ex: Exercise, key: str) -> str:
    st.session_state.setdefault(f"{key}_code", ex.starter)
    return st.text_area("Your code", height=320, key=f"{key}_code", label_visibility="collapsed")


def _server_editor(ex: Exercise, key: str, prog: dict | None) -> None:
    code = _editor(ex, key)
    c = st.columns([1, 1, 4])
    run = c[0].button("▶ Run the tests", key=f"{key}_run", type="primary")
    if c[1].button("Reset", key=f"{key}_reset"):
        st.session_state[f"{key}_code"] = ex.starter
        st.rerun()
    if run:
        with st.spinner("Compiling and testing…" if ex.language == "cpp" else "Testing…"):
            results = run_exercise(ex, code)
        for r in results:
            if r.ok:
                st.markdown(f"✅ {r.name}")
            else:
                st.markdown(f"❌ **{r.name}**")
                if r.message:
                    st.code(r.message, language=None)
        n_ok = sum(r.ok for r in results)
        if results and n_ok == len(results):
            st.success(f"🎉 All {n_ok} tests pass!")
            if prog is not None and ex.id not in prog.setdefault("exercises", []):
                prog["exercises"].append(ex.id)
        else:
            st.warning(f"{n_ok} / {len(results)} tests pass — keep going.")


def _cpp_offline(ex: Exercise, key: str) -> None:
    code = _editor(ex, key)
    st.info("C++ is compiled on your own computer. Download the file — it already contains the "
            "tests — then run:\n\n`c++ -std=c++17 -O2 exercise.cpp -o exercise && ./exercise`\n\n"
            "Or run quantforge locally (`quantforge-app`): the grader then compiles it for you.")
    st.download_button("⬇️ Download exercise.cpp (with tests)", cpp_source(ex, code),
                       f"{ex.id}.cpp", "text/x-c++src", key=f"{key}_dl")


def render_exercise(ex: Exercise, key: str, prog: dict | None = None) -> None:
    done = prog is not None and ex.id in prog.get("exercises", [])
    head = f"{'✅' if done else '💻'} {ex.label}  ·  {STARS.get(ex.difficulty, '')}"
    with st.expander(head, expanded=False):
        st.markdown(ex.prompt)
        if execution_allowed() and (ex.language == "python" or cpp_compiler()):
            _server_editor(ex, key, prog)
        elif ex.language == "python":
            _browser_python(ex, key)
        else:
            _cpp_offline(ex, key)
        if ex.hints:
            with st.popover("💡 Hints"):
                for h in ex.hints:
                    st.markdown(f"- {h}")
        with st.popover("👀 Reference solution"):
            st.caption("Try first — you learn by struggling a little.")
            st.code(ex.solution, language="cpp" if ex.language == "cpp" else "python")
