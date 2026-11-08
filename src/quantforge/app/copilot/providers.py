"""Minimal clients for Claude (Anthropic), ChatGPT (OpenAI) and Gemini (Google) with tool use.

Plain HTTPS with ``requests`` — no SDKs. Each call returns the assistant's text and a list of
tool calls ``{"name": ..., "args": {...}}``. Keys come from the user (their own API key) and are
sent only to the provider they belong to.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests

__all__ = ["PROVIDERS", "Reply", "call", "list_models", "ProviderError", "TOOLS"]

TIMEOUT = 90


class ProviderError(RuntimeError):
    pass


@dataclass
class Provider:
    name: str
    vendor: str
    default_model: str
    env_key: str
    key_url: str
    note: str


PROVIDERS = {
    "Claude": Provider("Claude", "Anthropic", "claude-sonnet-5-5", "ANTHROPIC_API_KEY",
                       "https://console.anthropic.com/settings/keys",
                       "API usage is billed by Anthropic, separately from a Claude.ai plan."),
    "ChatGPT": Provider("ChatGPT", "OpenAI", "gpt-5.6", "OPENAI_API_KEY",
                        "https://platform.openai.com/api-keys",
                        "API usage is billed by OpenAI, separately from a ChatGPT plan."),
    "Gemini": Provider("Gemini", "Google", "", "GEMINI_API_KEY",
                       "https://aistudio.google.com/apikey",
                       "Google AI Studio keys include a limited free tier."),
}


@dataclass
class Reply:
    text: str = ""
    actions: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------ tool definitions
TOOLS = [
    {"name": "set_fields",
     "description": "Fill or change input fields on the current page. Use only keys listed in "
                    "the page description. Values are text: an option's label, a number, "
                    "true/false, a date YYYY-MM-DD, or a comma-separated list for "
                    "multi-select fields.",
     "params": {"changes": {"type": "array", "description": "Fields to change",
                            "items": {"type": "object",
                                      "properties": {"key": {"type": "string"},
                                                     "value": {"type": "string"}},
                                      "required": ["key", "value"]}}},
     "required": ["changes"]},
    {"name": "click_button",
     "description": "Press a button on the current page (after setting fields, if needed). "
                    "Use only button keys listed in the page description.",
     "params": {"key": {"type": "string"}}, "required": ["key"]},
    {"name": "go_to_page",
     "description": "Open another page of the app. The page title must be one of the listed "
                    "pages. After the page opens you will see its fields and can continue.",
     "params": {"page": {"type": "string"}}, "required": ["page"]},
]


def _schema(t: dict, upper: bool = False) -> dict:
    def conv(s):
        if isinstance(s, dict):
            out = {k: conv(v) for k, v in s.items()}
            if upper and isinstance(out.get("type"), str):
                out["type"] = out["type"].upper()
            return out
        if isinstance(s, list):
            return [conv(x) for x in s]
        return s
    return conv({"type": "object", "properties": t["params"], "required": t["required"]})


def _post(url: str, headers: dict, body: dict) -> dict:
    try:
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ProviderError(f"network error: {exc}") from None
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {})
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except ValueError:
            msg = r.text[:300]
        raise ProviderError(f"HTTP {r.status_code}: {msg}")
    return r.json()


# ------------------------------------------------------------------ calls
def call(provider: str, api_key: str, model: str, system: str, messages: list[dict],
         use_tools: bool = True) -> Reply:
    """``messages`` = [{"role": "user"|"assistant", "content": str}, ...] (text only)."""
    if not api_key:
        raise ProviderError("no API key")
    if provider == "Claude":
        return _claude(api_key, model or PROVIDERS["Claude"].default_model, system, messages,
                       use_tools)
    if provider == "ChatGPT":
        return _openai(api_key, model or PROVIDERS["ChatGPT"].default_model, system, messages,
                       use_tools)
    if provider == "Gemini":
        return _gemini(api_key, model or _gemini_default(api_key), system, messages, use_tools)
    raise ProviderError(f"unknown provider {provider}")


def _claude(key, model, system, messages, use_tools) -> Reply:
    body = {"model": model, "max_tokens": 1500, "system": system,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages]}
    if use_tools:
        body["tools"] = [{"name": t["name"], "description": t["description"],
                          "input_schema": _schema(t)} for t in TOOLS]
    data = _post("https://api.anthropic.com/v1/messages",
                 {"x-api-key": key, "anthropic-version": "2023-06-01",
                  "content-type": "application/json"}, body)
    rep = Reply()
    for block in data.get("content", []):
        if block.get("type") == "text":
            rep.text += block.get("text", "")
        elif block.get("type") == "tool_use":
            rep.actions.append({"name": block.get("name"), "args": block.get("input") or {}})
    return rep


def _openai(key, model, system, messages, use_tools) -> Reply:
    body = {"model": model,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m["role"], "content": m["content"]} for m in messages]}
    if use_tools:
        body["tools"] = [{"type": "function",
                          "function": {"name": t["name"], "description": t["description"],
                                       "parameters": _schema(t)}} for t in TOOLS]
    data = _post("https://api.openai.com/v1/chat/completions",
                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, body)
    msg = (data.get("choices") or [{}])[0].get("message", {})
    rep = Reply(text=msg.get("content") or "")
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = {}
        rep.actions.append({"name": fn.get("name"), "args": args})
    return rep


def _gemini(key, model, system, messages, use_tools) -> Reply:
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "model" if m["role"] == "assistant" else "user",
                          "parts": [{"text": m["content"]}]} for m in messages]}
    if use_tools:
        body["tools"] = [{"functionDeclarations": [
            {"name": t["name"], "description": t["description"],
             "parameters": _schema(t, upper=True)} for t in TOOLS]}]
    model = model.removeprefix("models/")
    data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
                 ":generateContent", {"x-goog-api-key": key, "Content-Type": "application/json"},
                 body)
    rep = Reply()
    cands = data.get("candidates") or []
    for part in (cands[0].get("content", {}).get("parts", []) if cands else []):
        if "text" in part and not part.get("thought"):
            rep.text += part["text"]
        if "functionCall" in part:
            fc = part["functionCall"]
            rep.actions.append({"name": fc.get("name"), "args": fc.get("args") or {}})
    return rep


# ------------------------------------------------------------------ model lists
def list_models(provider: str, api_key: str) -> list[str]:
    """The models this key can use, straight from the provider."""
    try:
        if provider == "Claude":
            r = requests.get("https://api.anthropic.com/v1/models?limit=100",
                             headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                             timeout=30)
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]
        if provider == "ChatGPT":
            r = requests.get("https://api.openai.com/v1/models",
                             headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
            r.raise_for_status()
            ids = [m["id"] for m in r.json().get("data", [])]
            return sorted([i for i in ids if i.startswith(("gpt", "o"))], reverse=True)
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                         headers={"x-goog-api-key": api_key}, timeout=30)
        r.raise_for_status()
        return [m["name"].removeprefix("models/") for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
    except requests.RequestException as exc:
        raise ProviderError(f"could not list models: {exc}") from None


def _gemini_default(api_key: str) -> str:
    models = list_models("Gemini", api_key)
    for pref in ("pro", "flash"):
        cands = [m for m in models if pref in m and "preview" not in m and "exp" not in m
                 and "gemini" in m]
        if cands:
            return sorted(cands)[-1]
    if not models:
        raise ProviderError("no Gemini model available for this key")
    return models[0]
