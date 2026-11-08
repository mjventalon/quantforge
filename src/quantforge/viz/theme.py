"""Shared visual identity for every quantforge chart (Plotly)."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# Colour-blind-safe categorical palette (validated for light and dark backgrounds)
PALETTE = ["#2E86DE", "#E67E22", "#27AE60", "#C0392B", "#8E44AD",
           "#16A085", "#D4AC0D", "#7F8C8D", "#E84393", "#2C3E50"]
GAIN = "#27AE60"
LOSS = "#C0392B"
NEUTRAL = "#7F8C8D"
ACCENT = "#2E86DE"
GAIN_FILL = "rgba(39,174,96,0.14)"
LOSS_FILL = "rgba(192,57,43,0.14)"
BAND_FILL = "rgba(46,134,222,0.15)"
BAND_FILL_2 = "rgba(46,134,222,0.30)"

FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

pio.templates["quantforge"] = go.layout.Template(
    layout=go.Layout(
        dragmode="pan",
        font=dict(family=FONT, size=13),
        colorway=PALETTE,
        title=dict(font=dict(size=18), x=0.01, xanchor="left"),
        hovermode="x unified",
        margin=dict(l=60, r=30, t=70, b=55),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.18)", zeroline=False,
                   showline=True, linecolor="rgba(128,128,128,0.5)", ticks="outside"),
        yaxis=dict(showgrid=True, gridcolor="rgba(128,128,128,0.18)", zeroline=False,
                   showline=True, linecolor="rgba(128,128,128,0.5)", ticks="outside"),
    )
)
#: Plotly config used everywhere: mouse-wheel zoom, drag to pan, clean toolbar, 2x PNG export.
PLOTLY_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "doubleClick": "reset",
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "quantforge_chart"},
}
ANNOTATION_BG = "rgba(128,128,128,0.22)"   # readable on light and dark backgrounds

TEMPLATE = "plotly_white+quantforge"
TEMPLATE_DARK = "plotly_dark+quantforge"


def apply(fig: go.Figure, title: str | None = None, x: str | None = None, y: str | None = None,
          source: str | None = None, dark: bool = False) -> go.Figure:
    """Apply the house style, axis titles and a data-source footnote."""
    fig.update_layout(template=TEMPLATE_DARK if dark else TEMPLATE, dragmode="pan")
    if any(getattr(t, "type", "") in ("surface", "scatter3d", "mesh3d") for t in fig.data):
        fig.update_scenes(dragmode="orbit")     # 3-D: drag rotates freely, 360° in every way
    if title:
        fig.update_layout(title=title)
    if x:
        fig.update_xaxes(title_text=x)
    if y:
        fig.update_yaxes(title_text=y)
    if source:
        fig.add_annotation(text=f"Source: {source}", xref="paper", yref="paper", x=0, y=-0.16,
                           showarrow=False, font=dict(size=10, color=NEUTRAL), xanchor="left")
    return fig


def show(fig: go.Figure) -> None:
    """``fig.show()`` with wheel-zoom and drag-to-pan enabled (notebooks / scripts)."""
    fig.show(config=PLOTLY_CONFIG)
