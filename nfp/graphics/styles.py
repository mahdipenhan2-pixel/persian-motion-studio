"""NFP Graphics - G1: style presets. Standard library; data only.

A style = colours + type sizes / weights + spacing, per display (full frame / overlay), at scale 1 (frame pixels).
Fonts are the film's own local faces (copied by Film's compose to story/assets/fonts; nothing is downloaded):
Vazirmatn 400 / 700 (Persian script) and Inter 400 / 700 (Latin). Only weights 400 and 700 exist for both scripts
(Film maps Persian 800 to the 700 file), so a style uses only 400 / 700.
scene override keys: accent, text, muted, background, panel (#RRGGBB), panel_opacity (0..1), scale (0.75..1.5).
"""
import re

COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}")
FONT_STACK = {"fa": "Vazirmatn, Inter, sans-serif", "en": "Inter, Vazirmatn, sans-serif"}
TYPE = {   # px at scale 1, weight
    "fullframe": {"title": (88, 700), "subtitle": (44, 400), "body": (40, 400), "label": (30, 400), "number": (64, 700), "source": (22, 400)},
    "overlay": {"title": (46, 700), "subtitle": (30, 400), "body": (30, 400), "label": (24, 400), "number": (40, 700), "source": (18, 400)},
}
SPACING = {"fullframe": {"padding": 56, "gap": 24, "radius": 8, "rule": 6},
           "overlay": {"padding": 28, "gap": 12, "radius": 6, "rule": 4}}
LINE_HEIGHT = 1.35
PRESETS = {
    "documentary-dark": {"background": "#101216", "panel": "#15181d", "panel_opacity": 0.86, "text": "#f4efe6", "muted": "#b9b2a6",
                         "accent": "#d9a441", "grid": "#3a3f47", "positive": "#6fae7a", "negative": "#c8574d"},
    "documentary-light": {"background": "#f3efe6", "panel": "#fbf8f1", "panel_opacity": 0.92, "text": "#1d1b18", "muted": "#5f5a52",
                          "accent": "#9c2f24", "grid": "#d5cec2", "positive": "#3f7a4b", "negative": "#9c2f24"},
    "parchment": {"background": "#efe3c8", "panel": "#f6ecd4", "panel_opacity": 0.92, "text": "#3b2a1a", "muted": "#6e5a43",
                  "accent": "#8a3b12", "grid": "#d6c49e", "positive": "#4f6b2c", "negative": "#8a3b12"},
}
DEFAULT = "documentary-dark"
COLOR_KEYS = ("accent", "text", "muted", "background", "panel")
STYLE_KEYS = {"preset", "panel_opacity", "scale"} | set(COLOR_KEYS)


def resolve_style(style, display, lang, add, where="style"):
    """A style block (or None) -> the resolved style for one display ('fullframe' / 'overlay') and language."""
    style = {} if style is None else style
    if not isinstance(style, dict):
        add("error", "schema", "style must be an object", where)
        style = {}
    for k in sorted(set(style) - STYLE_KEYS):
        add("error", "schema", f"unknown style key {k!r} (one of {', '.join(sorted(STYLE_KEYS))})", where)
    name = style.get("preset", DEFAULT)
    if name not in PRESETS:
        add("error", "schema", f"unknown style preset {name!r} (one of {', '.join(PRESETS)})", where)
        name = DEFAULT
    colors = dict(PRESETS[name])
    for k in COLOR_KEYS:
        if k in style:
            if isinstance(style[k], str) and COLOR_RE.fullmatch(style[k]):
                colors[k] = style[k].lower()
            else:
                add("error", "schema", f"{k} must be a colour #RRGGBB", where)
    if "panel_opacity" in style:
        v = style["panel_opacity"]
        if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1:
            colors["panel_opacity"] = float(v)
        else:
            add("error", "schema", "panel_opacity must be a number 0..1", where)
    scale = style.get("scale", 1)
    if not (isinstance(scale, (int, float)) and not isinstance(scale, bool) and 0.75 <= scale <= 1.5):
        add("error", "schema", "scale must be a number 0.75..1.5", where)
        scale = 1
    disp = display if display in TYPE else "overlay"
    return {"preset": name, "colors": colors, "scale": float(scale), "font": FONT_STACK.get(lang, FONT_STACK["en"]),
            "type": {r: {"size": round(s * scale, 2), "weight": w} for r, (s, w) in TYPE[disp].items()},
            "spacing": {k: round(v * scale, 2) for k, v in SPACING[disp].items()}, "line_height": LINE_HEIGHT}
