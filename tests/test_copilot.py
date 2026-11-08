"""AI copilot: widget registry, value conversion, provider parsing, and the full loop in the
app with a scripted model (no network)."""

import re
from datetime import date

import pytest
from test_app import _open, offline  # noqa: F401  (autouse offline data fixture)

from quantforge.app.copilot import providers as P
from quantforge.app.copilot import registry as R

# ------------------------------------------------------------------ conversion


def test_convert_values():
    sel = {"kind": "selectbox", "label": "Type", "options": ["call", "put"],
           "option_labels": ["Call option", "Put option"], "multi": False, "value": "call"}
    assert R.convert(sel, "put") == "put"
    assert R.convert(sel, "Put option") == "put"
    with pytest.raises(ValueError):
        R.convert(sel, "straddle")
    ms = {**sel, "kind": "multiselect", "multi": True}
    assert R.convert(ms, "call, put") == ["call", "put"]
    assert R.convert(ms, '["put"]') == ["put"]
    num = {"kind": "number_input", "label": "Qty", "min_value": 0, "max_value": 100, "value": 5}
    assert R.convert(num, "42") == 42 and isinstance(R.convert(num, "42.0"), int)
    with pytest.raises(ValueError):
        R.convert(num, "500")
    fl = {"kind": "slider", "label": "σ", "value": 20.0}
    assert R.convert(fl, "35%") == 35.0
    rng = {"kind": "slider", "label": "range", "value": (1, 5)}
    assert R.convert(rng, "2, 4") == (2, 4)
    assert R.convert({"kind": "toggle", "label": "x", "value": False}, "yes") is True
    assert R.convert({"kind": "date_input", "label": "d", "value": date(2020, 1, 1)},
                     "2024-03-01") == date(2024, 3, 1)


def test_describe_hides_secrets_and_dangerous_buttons():
    reg = {"a": {"kind": "text_input", "label": "FMP API key", "help": "", "value": "SECRET",
                 "secret": True},
           "b": {"kind": "number_input", "label": "Strike", "help": "", "value": 100.0},
           "c": {"kind": "button", "label": "Delete this account", "help": "", "blocked": True},
           "d": {"kind": "button", "label": "Run", "help": "", "blocked": False}}
    fields, buttons = R.describe_for_ai(reg)
    text = "\n".join(fields + buttons)
    assert "SECRET" not in text and "Delete" not in text
    assert "key=b" in text and "key=d" in text


# ------------------------------------------------------------------ providers (mocked HTTP)
class _Resp:
    def __init__(self, data, code=200):
        self._d, self.status_code, self.text = data, code, str(data)

    def json(self):
        return self._d


def test_provider_parsing(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent["url"], sent["body"], sent["headers"] = url, json, headers
        if "anthropic" in url:
            return _Resp({"content": [{"type": "text", "text": "Sure."},
                                      {"type": "tool_use", "name": "click_button",
                                       "input": {"key": "k1"}}]})
        if "openai" in url:
            return _Resp({"choices": [{"message": {"content": None, "tool_calls": [
                {"function": {"name": "set_fields",
                              "arguments": '{"changes":[{"key":"k","value":"1"}]}'}}]}}]})
        return _Resp({"candidates": [{"content": {"parts": [
            {"text": "Done"}, {"functionCall": {"name": "go_to_page",
                                                "args": {"page": "Risk"}}}]}}]})

    monkeypatch.setattr(P.requests, "post", fake_post)
    msgs = [{"role": "user", "content": "hi"}]
    r = P.call("Claude", "k", "m", "sys", msgs)
    assert r.text == "Sure." and r.actions == [{"name": "click_button", "args": {"key": "k1"}}]
    assert sent["headers"]["x-api-key"] == "k" and sent["body"]["tools"][0]["name"]
    r = P.call("ChatGPT", "k", "m", "sys", msgs)
    assert r.actions[0]["args"]["changes"][0]["value"] == "1"
    assert sent["body"]["messages"][0] == {"role": "system", "content": "sys"}
    r = P.call("Gemini", "k", "gemini-x", "sys", msgs)
    assert r.text == "Done" and r.actions[0]["name"] == "go_to_page"
    decl = sent["body"]["tools"][0]["functionDeclarations"][0]["parameters"]
    assert decl["type"] == "OBJECT"
    r = P.call("Claude", "k", "m", "sys", msgs, use_tools=False)
    assert "tools" not in sent["body"]


def test_provider_errors(monkeypatch):
    monkeypatch.setattr(P.requests, "post",
                        lambda *a, **k: _Resp({"error": {"message": "invalid x-api-key"}}, 401))
    with pytest.raises(P.ProviderError, match="401"):
        P.call("Claude", "bad", "m", "s", [{"role": "user", "content": "x"}])
    with pytest.raises(P.ProviderError):
        P.call("Claude", "", "m", "s", [])


# ------------------------------------------------------------------ the loop in the app
def _scripted(actions_for):
    calls = []

    def fake_call(provider, key, model, system, messages, use_tools=True):
        calls.append(system)
        keys = dict(re.findall(r'key=(\S+) \| (?:button )?"([^"]+)"', system))
        by_label = {v: k for k, v in keys.items()}
        return actions_for(len(calls), by_label, system)
    return fake_call, calls


def _setup(at, mode):
    at.selectbox(key="qfai_mode").set_value(mode).run()
    at.checkbox(key=f"qfai_consent_Claude_{ {'Autopilot': 'auto', 'Suggest — I approve': 'suggest', 'Explain only': 'explain'}[mode]}").check().run()


def test_copilot_autopilot_fills_the_page(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def plan(n, by_label, system):
        if n == 1:
            assert "Options pricer" in system and "Strike" in by_label
            return P.Reply("Setting a put.", [{"name": "set_fields", "args": {"changes": [
                {"key": by_label["Type"], "value": "put"},
                {"key": by_label["Exercise"], "value": "european"}]}}])
        return P.Reply("The put is priced with Black-Scholes below.", [])

    fake, calls = _scripted(plan)
    monkeypatch.setattr("quantforge.app.copilot.panel.call", fake)
    at = _open("04_Options_pricer.py", 300)
    _setup(at, "Autopilot")
    at.text_area(key="qfai_input").input("price a european put")
    at.button(key="FormSubmitter:qfai_form-Send").click().run()
    assert not at.exception, [e.message for e in at.exception]
    at.run()                                   # follow-up turn after the refresh
    assert not at.exception, [e.message for e in at.exception]
    radios = {r.label: r.value for r in at.radio}
    assert radios["Type"] == "put" and radios["Exercise"] == "european"
    assert len(calls) == 2


def test_copilot_suggest_needs_approval(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake, _ = _scripted(lambda n, by, s: P.Reply("Try a put.", [{"name": "set_fields", "args": {
        "changes": [{"key": by["Type"], "value": "put"}]}}]))
    monkeypatch.setattr("quantforge.app.copilot.panel.call", fake)
    at = _open("04_Options_pricer.py", 300)
    _setup(at, "Suggest — I approve")
    at.text_area(key="qfai_input").input("make it a put")
    at.button(key="FormSubmitter:qfai_form-Send").click().run()
    assert {r.label: r.value for r in at.radio}["Type"] == "call"     # nothing changed yet
    at.button(key="qfai_apply").click().run()
    assert not at.exception, [e.message for e in at.exception]
    assert {r.label: r.value for r in at.radio}["Type"] == "put"


def test_copilot_rejects_unknown_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake, _ = _scripted(lambda n, by, s: P.Reply("", [{"name": "set_fields", "args": {
        "changes": [{"key": "nope", "value": "1"}]}}]) if n == 1 else P.Reply("ok", []))
    monkeypatch.setattr("quantforge.app.copilot.panel.call", fake)
    at = _open("04_Options_pricer.py", 300)
    _setup(at, "Autopilot")
    at.text_area(key="qfai_input").input("x")
    at.button(key="FormSubmitter:qfai_form-Send").click().run()
    assert not at.exception, [e.message for e in at.exception]
    msgs = at.session_state["qfai_chat"]["messages"]
    assert any("unknown field nope" in m["content"] for m in msgs)
