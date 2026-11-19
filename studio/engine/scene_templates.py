"""
Scene templates for the 9:16 layout.

Layout contract (1080x1920):
  top zone     y 110-540   : scene graphic (this module)
  caption band y 560-1360  : word-highlight captions (compose.py) - never put graphics here
  bottom zone  y 1400-1630 : optional second block (this module)

Each template has a validator (clear error messages, length limits that keep text inside its zone)
and a renderer that returns (top_html, bottom_html). Elements with class "a" are animated in.
"""
import html

from icons import ICON_NAMES, svg


class SceneError(ValueError):
    pass


def _e(v):
    return html.escape(str(v), quote=True)


def _text(d, key, where, maxlen, required=True):
    v = d.get(key)
    if v is None or v == "":
        if required:
            raise SceneError(f"{where}.{key} is required")
        return None
    if not isinstance(v, str) or not v.strip():
        raise SceneError(f"{where}.{key} must be a non-empty string")
    if len(v) > maxlen:
        raise SceneError(f"{where}.{key} is {len(v)} characters; the limit is {maxlen} so it fits its zone")
    return v.strip()


def _icon(d, key, where, required=False):
    v = d.get(key)
    if v is None:
        if required:
            raise SceneError(f"{where}.{key} is required")
        return None
    if v not in ICON_NAMES:
        raise SceneError(f"{where}.{key} '{v}' is not an icon. Available: {', '.join(ICON_NAMES)}")
    return v


def _obj(d, where):
    if not isinstance(d, dict):
        raise SceneError(f"{where} must be an object")
    return d


def _unknown(d, allowed, where):
    extra = sorted(set(d) - set(allowed))
    if extra:
        raise SceneError(f"{where}: unknown field(s) {', '.join(extra)}. Allowed: {', '.join(sorted(allowed))}")


# ---------------------------------------------------------------- title
def check_title(o, w):
    _unknown(o, {"title", "subtitle", "icon"}, w)
    _text(o, "title", w, 24)
    _text(o, "subtitle", w, 40, required=False)
    _icon(o, "icon", w)


def render_title(o):
    out = []
    if o.get("icon"):
        out.append(f'<div class="t-icon a">{svg(o["icon"], 108)}</div>')
    out.append(f'<div class="t-title a">{_e(o["title"])}</div>')
    if o.get("subtitle"):
        out.append(f'<div class="t-sub a">{_e(o["subtitle"])}</div>')
    return "".join(out), ""


# ---------------------------------------------------------------- compare
def _side(o, key, w):
    s = _obj(o.get(key), f"{w}.{key}") if key in o else None
    if s is None:
        raise SceneError(f"{w}.{key} is required")
    _unknown(s, {"big", "small", "tone", "icon"}, f"{w}.{key}")
    _text(s, "big", f"{w}.{key}", 14)
    _text(s, "small", f"{w}.{key}", 18)
    _icon(s, "icon", f"{w}.{key}")
    if s.get("tone", "ok") not in ("ok", "warn"):
        raise SceneError(f"{w}.{key}.tone must be 'ok' or 'warn'")


def check_compare(o, w):
    _unknown(o, {"a", "b"}, w)
    _side(o, "a", w)
    _side(o, "b", w)


def render_compare(o):
    cards = []
    for key, default in (("a", "ok"), ("b", "warn")):
        s = o[key]
        tone = s.get("tone", default)
        ic = f'<div class="c-icon">{svg(s["icon"], 64)}</div>' if s.get("icon") else ""
        cards.append(f'<div class="card tone-{tone} a">{ic}<div class="big">{_e(s["big"])}</div>'
                     f'<div class="small">{_e(s["small"])}</div></div>')
    return f'<div class="cmp">{"".join(cards)}</div>', ""


# ---------------------------------------------------------------- info
def check_info(o, w):
    _unknown(o, {"heading", "lines", "icon"}, w)
    _text(o, "heading", w, 30)
    _icon(o, "icon", w)
    lines = o.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 3:
        raise SceneError(f"{w}.lines must be a list of 1-3 short strings")
    for i, ln in enumerate(lines):
        if not isinstance(ln, str) or not ln.strip() or len(ln) > 36:
            raise SceneError(f"{w}.lines[{i}] must be a string of at most 36 characters")


def render_info(o):
    head = (f'<div class="i-head a">{svg(o["icon"], 64) if o.get("icon") else ""}'
            f'<span>{_e(o["heading"])}</span></div>')
    rows = "".join(f'<div class="i-row a"><i></i><span>{_e(x)}</span></div>' for x in o["lines"])
    return f'{head}<div class="i-rows">{rows}</div>', ""


# ---------------------------------------------------------------- steps
def check_steps(o, w):
    _unknown(o, {"heading", "items"}, w)
    _text(o, "heading", w, 30, required=False)
    items = o.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= 4:
        raise SceneError(f"{w}.items must be a list of 2-4 items")
    limit = 22 if len(items) <= 3 else 16
    for i, it in enumerate(items):
        _obj(it, f"{w}.items[{i}]")
        _unknown(it, {"icon", "text"}, f"{w}.items[{i}]")
        _icon(it, "icon", f"{w}.items[{i}]", required=True)
        _text(it, "text", f"{w}.items[{i}]", limit)


def render_steps(o):
    n = len(o["items"])
    size = 96 if n <= 3 else 72
    cards = "".join(f'<div class="step a"><div class="s-icon">{svg(it["icon"], size)}</div>'
                    f'<div class="s-text">{_e(it["text"])}</div></div>' for it in o["items"])
    head = f'<div class="s-head a">{_e(o["heading"])}</div>' if o.get("heading") else ""
    return f'{head}<div class="steps n{n}">{cards}</div>', ""


# ---------------------------------------------------------------- cta
def check_cta(o, w):
    _unknown(o, {"heading", "note", "handle", "icon"}, w)
    _text(o, "heading", w, 30)
    _text(o, "note", w, 60, required=False)
    _text(o, "handle", w, 30, required=False)
    _icon(o, "icon", w)


def render_cta(o):
    top = ""
    if o.get("icon"):
        top += f'<div class="t-icon a">{svg(o["icon"], 96)}</div>'
    top += f'<div class="c-head a">{_e(o["heading"])}</div>'
    bottom = ""
    if o.get("note"):
        bottom += f'<div class="c-note a">{_e(o["note"])}</div>'
    if o.get("handle"):
        bottom += f'<div class="c-handle a">{_e(o["handle"])}</div>'
    return top, bottom


TEMPLATES = {
    "title": (check_title, render_title),
    "compare": (check_compare, render_compare),
    "info": (check_info, render_info),
    "steps": (check_steps, render_steps),
    "cta": (check_cta, render_cta),
}


def validate(template, on_screen, where):
    if template not in TEMPLATES:
        raise SceneError(f"{where}.template '{template}' is unknown. Available: {', '.join(sorted(TEMPLATES))}")
    TEMPLATES[template][0](_obj(on_screen, f"{where}.on_screen"), f"{where}.on_screen")


def render(template, on_screen):
    return TEMPLATES[template][1](on_screen)


def deco_icon(scene):
    """Icon used for the faint background decoration in the empty bottom area (None if the scene has none)."""
    o = scene["on_screen"]
    if o.get("icon"):
        return o["icon"]
    for side in ("a", "b"):
        if isinstance(o.get(side), dict) and o[side].get("icon"):
            return o[side]["icon"]
    items = o.get("items")
    if isinstance(items, list) and items:
        return items[0]["icon"]
    return None
