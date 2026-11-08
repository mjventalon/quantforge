"""Gentler mouse-wheel / trackpad zoom for every Plotly chart in the app.

Plotly zooms by up to ~10 % per wheel event (it clamps each event's delta to ±20), which
feels jumpy with trackpads and free-spinning wheels. This installs one capture-phase
listener on the page that scales each wheel event down before Plotly sees it
(click-and-drag pan is unchanged). It runs in the browser only; nothing is sent to the server.
"""

from __future__ import annotations

import json

import streamlit as st

SPEEDS = {"Slow": 0.25, "Normal": 0.45, "Fast": 1.0}

# Runs in the PARENT page (injected as a <script> element) so the listener survives Streamlit
# re-rendering the tiny iframe that carries it.
_LISTENER = r"""
(function () {
  if (window.__qfWheelInstalled) return;
  window.__qfWheelInstalled = true;
  document.addEventListener("wheel", function (e) {
    if (e.__qfScaled || !e.isTrusted) return;
    const plot = e.target && e.target.closest && e.target.closest(".js-plotly-plot");
    if (!plot) return;
    const f = window.__qfWheelFactor || 0.45;
    if (f >= 0.999) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    // 2-D: Plotly clamps each event to +/-20 before zooming, so scale after clamping.
    // 3-D scenes use the raw delta, so scale it directly.
    const is3d = !!(e.target.closest && e.target.closest(".gl-container"));
    const clamp = v => is3d ? v * f : Math.max(-20, Math.min(20, v)) * f;
    const ev = new WheelEvent("wheel", {
      deltaX: clamp(e.deltaX), deltaY: clamp(e.deltaY), deltaZ: e.deltaZ,
      deltaMode: e.deltaMode, clientX: e.clientX, clientY: e.clientY,
      screenX: e.screenX, screenY: e.screenY, ctrlKey: e.ctrlKey, shiftKey: e.shiftKey,
      altKey: e.altKey, metaKey: e.metaKey, bubbles: true, cancelable: true, composed: true
    });
    ev.__qfScaled = true;
    e.target.dispatchEvent(ev);
  }, { capture: true, passive: false });
})();
"""

_JS = """<script>
(function () {
  const P = window.parent;
  if (!P || !P.document) return;
  P.__qfWheelFactor = %(factor)s;
  if (P.__qfWheelInstalled) return;
  const s = P.document.createElement("script");
  s.textContent = %(listener)s;
  P.document.head.appendChild(s);
})();
</script>"""


def install(speed: str = "Normal") -> None:
    """Inject the listener (idempotent; updates the speed on every run)."""
    html = _JS % {"factor": json.dumps(SPEEDS.get(speed, 0.45)),
                  "listener": json.dumps(_LISTENER).replace("</", "<\\/")}
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=0)
