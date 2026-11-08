"""The AI copilot panel: chat with Claude, ChatGPT or Gemini about the current page and, with
your permission, let it fill fields, press buttons and open pages."""

from __future__ import annotations

import os

import streamlit as st

from . import registry as R
from .providers import PROVIDERS, ProviderError, call, list_models

MODES = {
    "Explain only": "explain",
    "Suggest — I approve": "suggest",
    "Autopilot": "auto",
}
MAX_AUTO_STEPS = 4


def _state() -> dict:
    return st.session_state.setdefault("qfai_chat", {"messages": [], "pending": [],
                                                     "steps": 0, "followup": False})


def apply_pending_changes() -> list[str]:
    """Run at the top of the app, before the page draws: apply queued field values."""
    queued = st.session_state.pop("_qf_apply", None) or []
    done = []
    for key, value, label in queued:
        st.session_state[key] = value
        done.append(label)
    return done


def _system(page: str, how_to: str, pages: dict, mode: str) -> str:
    reg = st.session_state.get(R.REG, {})
    fields, buttons = R.describe_for_ai(reg)
    metrics = st.session_state.get(R.METRICS, [])[:30]
    page_list = "\n".join(f"- {t}: {d}" for t, d in pages.items())
    rights = {"explain": "You may ONLY explain and advise. Do not call tools.",
              "suggest": "You may propose actions with the tools; the user approves them "
                         "before anything changes.",
              "auto": "You may act directly with the tools: fill fields, press buttons and open "
                      "pages to complete the user's request, then explain what you did."}[mode]
    return f"""You are the quantforge copilot, an assistant built into quantforge, an
open-source quantitative-finance web app (research, education, paper trading; real market data).

Your job: make the app easy. Explain in plain words what each tool, field and result means,
recommend sensible settings for the user's goal, and operate the page when allowed.
{rights}

Rules
- Use only the field keys, button keys and page titles listed below. Never invent keys.
- To run a calculation: set the fields, then press the page's action button if it has one.
- Never invent market data, prices or results: numbers come from the app. If the results are
  not on the page yet, say what to run.
- Nothing is investment advice; paper trading uses virtual money. Say so if the user asks what
  to buy.
- Reply in the user's language, short and friendly (max ~120 words unless asked). Explain
  jargon simply. If the request is ambiguous, ask one short question.

Current page: {page}
How the page works:
{how_to or '(no guide for this page)'}

Fields on this page:
{chr(10).join(fields) or '(none)'}

Buttons on this page:
{chr(10).join(buttons) or '(none)'}

Results currently shown (metrics):
{chr(10).join(f'- {a}: {b}' for a, b in metrics) or '(none yet)'}

Pages of the app:
{page_list}
"""


def _execute(actions: list[dict], pages_by_title: dict, mode: str) -> tuple[list[str], list[str]]:
    """Validate actions; queue them for the next run. Returns (done, errors)."""
    reg = st.session_state.get(R.REG, {})
    queued, done, errors, click, goto = [], [], [], None, None
    for a in actions:
        name, args = a.get("name"), a.get("args") or {}
        if name == "set_fields":
            for ch in args.get("changes") or []:
                key, raw = str(ch.get("key", "")), ch.get("value", "")
                info = reg.get(key)
                if info is None or info["kind"] == "button" or info.get("secret"):
                    errors.append(f"unknown field {key}")
                    continue
                try:
                    val = R.convert(info, raw)
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                queued.append((key, val, f"{info['label']} → {raw}"))
                done.append(f"✏️ {info['label']} → {raw}")
        elif name == "click_button":
            key = str(args.get("key", ""))
            info = reg.get(key)
            if info is None or info["kind"] != "button" or info.get("blocked"):
                errors.append(f"button {key} is not available")
            else:
                click = key
                done.append(f"👆 {info['label']}")
        elif name == "go_to_page":
            title = str(args.get("page", ""))
            match = next((t for t in pages_by_title if t.lower() == title.lower()), None)
            if match is None:
                errors.append(f"no page called {title}")
            else:
                goto = match
                done.append(f"➡️ open {match}")
    if queued:
        st.session_state["_qf_apply"] = queued
    if click:
        st.session_state[R.CLICK] = click
    st.session_state["_qfai_goto"] = goto
    return done, errors


def _proceed(pages_by_title: dict) -> None:
    goto = st.session_state.pop("_qfai_goto", None)
    if goto:
        st.switch_page(pages_by_title[goto])
    st.rerun()


def _ask(prov: str, key: str, model: str, mode: str, page: str, how_to: str, pages: dict,
         pages_by_title: dict, user_text: str | None) -> None:
    chat = _state()
    if user_text:
        chat["messages"].append({"role": "user", "content": user_text})
        chat["steps"] = 0
    msgs = chat["messages"][-14:]
    if msgs and msgs[0]["role"] != "user":
        msgs = msgs[1:]
    with st.spinner(f"{prov} is thinking…"):
        try:
            rep = call(prov, key, model, _system(page, how_to, pages, mode), msgs,
                       use_tools=mode != "explain")
        except ProviderError as exc:
            chat["messages"].append({"role": "assistant", "content": f"⚠️ {prov}: {exc}"})
            chat["followup"] = False
            return
    text = rep.text.strip()
    if not rep.actions or mode == "explain":
        chat["messages"].append({"role": "assistant", "content": text or "(no answer)"})
        chat["followup"] = False
        return
    if mode == "suggest":
        chat["pending"] = rep.actions
        chat["messages"].append({"role": "assistant",
                                 "content": (text + "\n\n" if text else "")
                                 + "I propose the changes below — press **Apply** to accept."})
        chat["followup"] = False
        return
    done, errors = _execute(rep.actions, pages_by_title, mode)
    summary = "\n".join(done + [f"⚠️ {e}" for e in errors])
    chat["messages"].append({"role": "assistant", "content": (text + "\n\n" if text else "")
                             + (summary or "")})
    chat["steps"] += 1
    acted = bool(done)
    chat["followup"] = acted and chat["steps"] < MAX_AUTO_STEPS
    if acted:
        _proceed(pages_by_title)


def render(page: str, how_to: str, pages: dict, pages_by_title: dict) -> None:
    """Draw the panel (call after the page has run, inside a sidebar container)."""
    chat = _state()
    with st.expander("🤖 AI copilot", expanded=bool(chat["messages"])):
        c = st.columns([1, 1])
        prov = c[0].selectbox("Assistant", list(PROVIDERS), key="qfai_provider")
        p = PROVIDERS[prov]
        mode_label = c[1].selectbox("Permission", list(MODES), key="qfai_mode",
                                    help="Explain only: answers questions. Suggest: proposes "
                                         "changes you approve. Autopilot: fills the page and "
                                         "presses buttons for you.")
        mode = MODES[mode_label]
        env_key = os.environ.get(p.env_key, "")
        key = st.text_input(f"{p.vendor} API key", type="password", key=f"qfai_key_{prov}",
                            placeholder="found in .env" if env_key else "paste your key",
                            help=f"Get one at {p.key_url}. {p.note} Kept only in this session.")
        key = key or env_key
        model = st.text_input("Model", key=f"qfai_model_{prov}", value=p.default_model,
                              placeholder="auto", help="Leave as is, or list your models.")
        if key and st.button("List my models", key="qfai_list"):
            try:
                st.session_state["qfai_models"] = list_models(prov, key)[:60]
            except ProviderError as exc:
                st.error(str(exc))
        if st.session_state.get("qfai_models"):
            pick = st.selectbox("Available models", st.session_state["qfai_models"],
                                key="qfai_model_pick")
            if pick != model and st.button("Use this model", key="qfai_use_model"):
                st.session_state[f"qfai_model_{prov}"] = pick
                st.rerun()
        consent = st.checkbox(
            f"I allow {prov} to read this page (field names, values, results)"
            + ("" if mode == "explain" else " and to change it as allowed above"),
            key=f"qfai_consent_{prov}_{mode}")
        st.caption(f"Sent to {p.vendor}: the page's fields, values and results plus your "
                   "messages — never your API keys. Responses can be wrong: check them.")
        if not key:
            st.info(f"Add a {p.vendor} API key to start ([get one]({p.key_url})).")
            return
        if not consent:
            return

        for m in chat["messages"][-12:]:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

        if chat["pending"]:
            reg = st.session_state.get(R.REG, {})
            st.markdown("**Proposed changes**")
            for a in chat["pending"]:
                if a["name"] == "set_fields":
                    for ch in a["args"].get("changes") or []:
                        lab = reg.get(str(ch.get("key")), {}).get("label", ch.get("key"))
                        st.markdown(f"- {lab} → `{ch.get('value')}`")
                elif a["name"] == "click_button":
                    lab = reg.get(str(a["args"].get("key")), {}).get("label", "?")
                    st.markdown(f"- press **{lab}**")
                else:
                    st.markdown(f"- open **{a['args'].get('page')}**")
            b = st.columns(2)
            if b[0].button("✅ Apply", key="qfai_apply", type="primary"):
                actions, chat["pending"] = chat["pending"], []
                done, errors = _execute(actions, pages_by_title, "auto")
                chat["messages"].append({"role": "assistant", "content": "\n".join(
                    done + [f"⚠️ {e}" for e in errors]) or "Nothing to apply."})
                _proceed(pages_by_title)
            if b[1].button("✖️ Dismiss", key="qfai_dismiss"):
                chat["pending"] = []
                st.rerun()

        if chat.get("followup"):
            chat["followup"] = False
            chat["messages"].append({"role": "user", "content":
                                     "(The actions were applied and the page refreshed. Look at "
                                     "the updated page: continue the task if needed, otherwise "
                                     "explain the results briefly.)"})
            _ask(prov, key, model, mode, page, how_to, pages, pages_by_title, None)
            chat["messages"] = [m for m in chat["messages"]
                                if not m["content"].startswith("(The actions were applied")]
            st.rerun()

        with st.form("qfai_form", clear_on_submit=True, border=False):
            text = st.text_area("Ask the copilot", key="qfai_input", height=80,
                                placeholder="e.g. Price a 3-month AAPL call at the money and "
                                            "explain the Greeks")
            c = st.columns([1, 1])
            send = c[0].form_submit_button("Send", type="primary")
            clear = c[1].form_submit_button("New chat")
        if clear:
            st.session_state["qfai_chat"] = {"messages": [], "pending": [], "steps": 0,
                                             "followup": False}
            st.rerun()
        if send and text.strip():
            _ask(prov, key, model, mode, page, how_to, pages, pages_by_title, text.strip())
            st.rerun()
