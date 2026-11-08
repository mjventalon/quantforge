"""Records every input widget, button and metric a page draws, so an AI copilot can read the
page and (with permission) fill it in.

Streamlit widgets created without a ``key`` cannot be set from code. The wrapper gives such a
widget a key derived from its label and parameters — the same information Streamlit itself
uses to identify an unkeyed widget — so behaviour does not change: when a default changes
(say, a strike that follows the live spot) the key changes too and the widget resets exactly
as before.
"""

from __future__ import annotations

import datetime as dt
import functools
import hashlib
import inspect
import re

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

INPUTS = ("selectbox", "multiselect", "radio", "select_slider", "slider", "number_input",
          "text_input", "text_area", "toggle", "checkbox", "segmented_control", "pills",
          "date_input")
REG = "_qf_reg"            # session key: {widget key: info}
METRICS = "_qf_metrics"    # session key: [(label, value)]
CLICK = "_qf_click"        # session key: button key to "press" on the next run
PREFIX = "qfa_"            # auto-generated keys
PRIVATE = ("qfai_",)       # the copilot's own widgets are never exposed
_ADDR = re.compile(r" at 0x[0-9a-fA-F]+")
DANGEROUS = re.compile(r"delete|reset|sign out|remove|clear|danger|export|download",
                       re.IGNORECASE)


def _stable(v) -> str:
    if callable(v):
        return "<fn>"
    return _ADDR.sub("", repr(v))[:2000]


def _auto_key(kind: str, bound: dict) -> str:
    parts = [st.session_state.get("_qf_page", ""), kind]
    for name, v in bound.items():
        if name in ("self", "key", "on_change", "on_click", "args", "kwargs", "help",
                    "label_visibility", "width"):
            continue
        parts.append(f"{name}={_stable(v)}")
    return PREFIX + hashlib.sha1("|".join(parts).encode()).hexdigest()[:14]


def _fmt(bound: dict):
    f = bound.get("format_func")
    return f if callable(f) else str


def _describe(kind: str, bound: dict, value) -> dict:
    info = {"kind": kind, "label": str(bound.get("label", "")).replace("\n", " ")[:120],
            "help": str(bound.get("help") or "")[:200]}
    if "options" in bound and bound["options"] is not None:
        opts = list(bound["options"])
        fmt = _fmt(bound)
        info["options"] = opts
        try:
            info["option_labels"] = [str(fmt(o)) for o in opts]
        except Exception:  # noqa: BLE001
            info["option_labels"] = [str(o) for o in opts]
        info["multi"] = kind == "multiselect" or bound.get("selection_mode") == "multi"
    for k in ("min_value", "max_value", "step"):
        if bound.get(k) is not None:
            info[k] = bound[k]
    if kind == "text_input" and bound.get("type") == "password":
        info["secret"] = True
    info["value"] = value
    return info


def _wrap(kind: str, orig):
    sig = inspect.signature(orig)

    @functools.wraps(orig)
    def wrapper(self, *args, **kwargs):
        try:
            bound = sig.bind_partial(self, *args, **kwargs).arguments
        except TypeError:
            return orig(self, *args, **kwargs)
        key = bound.get("key")
        if key is None:
            key = _auto_key(kind, bound)
            kwargs["key"] = key
        value = orig(self, *args, **kwargs)
        if not str(key).startswith(PRIVATE):
            try:
                st.session_state.setdefault(REG, {})[str(key)] = _describe(kind, bound, value)
            except Exception:  # noqa: BLE001 - never break a page for the copilot
                pass
        return value

    wrapper.__qf_wrapped__ = True
    return wrapper


def _wrap_button(orig):
    sig = inspect.signature(orig)

    @functools.wraps(orig)
    def wrapper(self, *args, **kwargs):
        try:
            bound = sig.bind_partial(self, *args, **kwargs).arguments
        except TypeError:
            return orig(self, *args, **kwargs)
        key = bound.get("key")
        if key is None:
            key = _auto_key("button", bound)
            kwargs["key"] = key
        pressed = orig(self, *args, **kwargs)
        key = str(key)
        if key.startswith(PRIVATE):
            return pressed
        label = str(bound.get("label", ""))
        try:
            st.session_state.setdefault(REG, {})[key] = {
                "kind": "button", "label": label[:120], "help": str(bound.get("help") or ""),
                "blocked": bool(DANGEROUS.search(label)) or bool(bound.get("disabled"))}
        except Exception:  # noqa: BLE001
            pass
        if not pressed and st.session_state.get(CLICK) == key:
            st.session_state.pop(CLICK, None)
            return True
        return pressed

    wrapper.__qf_wrapped__ = True
    return wrapper


def _wrap_metric(orig):
    @functools.wraps(orig)
    def wrapper(self, label, value, *args, **kwargs):
        out = orig(self, label, value, *args, **kwargs)
        try:
            st.session_state.setdefault(METRICS, []).append((str(label), str(value)))
        except Exception:  # noqa: BLE001
            pass
        return out

    wrapper.__qf_wrapped__ = True
    return wrapper


def install() -> None:
    """Patch Streamlit once per process (idempotent)."""
    if getattr(DeltaGenerator.selectbox, "__qf_wrapped__", False):
        return
    for name in INPUTS:
        setattr(DeltaGenerator, name, _wrap(name, getattr(DeltaGenerator, name)))
    DeltaGenerator.button = _wrap_button(DeltaGenerator.button)
    DeltaGenerator.metric = _wrap_metric(DeltaGenerator.metric)
    main = st._main
    for name in (*INPUTS, "button", "metric"):
        setattr(st, name, getattr(main, name))


def start_run(page_title: str) -> None:
    """Call at the top of every full run, before the page draws."""
    st.session_state["_qf_page"] = page_title
    st.session_state[REG] = {}
    st.session_state[METRICS] = []


# ------------------------------------------------------------------ value conversion
class ValueError_(ValueError):
    pass


def _match_option(info: dict, text: str):
    t = str(text).strip().lower()
    for o, lab in zip(info["options"], info["option_labels"]):
        if t in (str(o).strip().lower(), lab.strip().lower()):
            return o
    for o, lab in zip(info["options"], info["option_labels"]):   # unique prefix match
        if lab.strip().lower().startswith(t) or str(o).lower().startswith(t):
            return o
    raise ValueError_(f"'{text}' is not an option of '{info['label']}'")


def _split(text: str) -> list[str]:
    s = str(text).strip()
    if s.startswith("["):
        import json
        try:
            return [str(x) for x in json.loads(s)]
        except ValueError:
            s = s.strip("[]")
    return [p.strip().strip("'\"") for p in s.split(",") if p.strip()]


def _num(info: dict, text: str):
    ref = info.get("value")
    if isinstance(ref, (list, tuple)) and ref:
        ref = ref[0]
    x = float(str(text).replace(",", "").replace("%", "").strip())
    lo, hi = info.get("min_value"), info.get("max_value")
    if isinstance(lo, (int, float)) and x < lo or isinstance(hi, (int, float)) and x > hi:
        raise ValueError_(f"{x} is outside [{lo}, {hi}] for '{info['label']}'")
    return int(round(x)) if isinstance(ref, int) and not isinstance(ref, bool) else x


def convert(info: dict, text) -> object:
    """Turn the AI's text into a value of the right type for the widget."""
    kind = info["kind"]
    if kind == "button":
        raise ValueError_("buttons are clicked, not set")
    if "options" in info:
        if info.get("multi"):
            return [_match_option(info, p) for p in _split(text)]
        if kind == "select_slider" and isinstance(info.get("value"), tuple):
            a, b = _split(text)[:2]
            return (_match_option(info, a), _match_option(info, b))
        return _match_option(info, text)
    if kind in ("toggle", "checkbox"):
        return str(text).strip().lower() in ("true", "yes", "on", "1", "oui", "vrai")
    if kind in ("number_input", "slider"):
        if isinstance(info.get("value"), tuple):
            a, b = _split(text)[:2]
            return (_num(info, a), _num(info, b))
        if isinstance(info.get("value"), (dt.date, dt.datetime)):
            return dt.date.fromisoformat(str(text).strip())
        return _num(info, text)
    if kind == "date_input":
        if isinstance(info.get("value"), tuple):
            a, b = _split(text)[:2]
            return (dt.date.fromisoformat(a), dt.date.fromisoformat(b))
        return dt.date.fromisoformat(str(text).strip())
    return str(text)


def describe_for_ai(reg: dict) -> tuple[list[str], list[str]]:
    """Text lines describing the page's fields and buttons (secrets hidden)."""
    fields, buttons = [], []
    for key, info in reg.items():
        if info["kind"] == "button":
            if not info.get("blocked"):
                buttons.append(f"- key={key} | button \"{info['label']}\""
                               + (f" | {info['help']}" if info["help"] else ""))
            continue
        if info.get("secret") or "api" in info["label"].lower() and "key" in \
                info["label"].lower():
            continue
        val = info.get("value")
        if "options" in info:
            labels = info["option_labels"]
            shown = ", ".join(labels[:25]) + (f", … (+{len(labels) - 25})" if len(labels) > 25
                                               else "")
            try:
                fmt = dict(zip(map(repr, info["options"]), labels))
                cur = ([fmt.get(repr(v), str(v)) for v in val] if isinstance(val, (list, tuple))
                       else fmt.get(repr(val), str(val)))
            except Exception:  # noqa: BLE001
                cur = val
            extra = f"options: [{shown}]" + (" (several allowed)" if info.get("multi") else "")
        else:
            bounds = [f"{k.split('_')[0]}={info[k]}" for k in ("min_value", "max_value")
                      if k in info]
            extra = info["kind"] + (f" ({', '.join(bounds)})" if bounds else "")
            cur = val
        fields.append(f"- key={key} | \"{info['label']}\" | {extra} | current: {cur!s:.120}"
                      + (f" | help: {info['help']}" if info["help"] else ""))
    return fields, buttons
