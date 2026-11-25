"""NFP Graphics - G3: SVG of the text kinds (title, lower-third, info-card, quote, callout) from their layout (G2), the
contrast check of their colours, and an HTML preview. Standard library; no process, no file writing.

  contrast(spec)                         -> QC issues: every text colour against what is really behind it
  render_svg(spec, lay, font_css=None, standalone=True) -> the SVG: a full 1920x1080 <svg> (standalone) or its <g>
  preview_html(items, font_css)          -> one HTML page: every graphic over a dark, a light and a busy background,
                                            with the safe area and the subtitle band drawn as guides
spec = graphics.validate(...)["graphic"], lay = graphics.layout(spec, metrics) (status OK / WARN; FAIL is refused).

Drawing (frame pixels, nothing scaled):
  full frame  the style's background over the whole frame, a short accent rule above the text block (centred for a title /
              quote, on the reading-start side for an info card), the text
  overlay     a panel (style panel colour at panel_opacity, rounded) = the layout's box, the accent rule of a title /
              lower third / info card on the reading-start side, the text; a callout adds a leader from its box to its
              point (an accent line over a wider panel-colour outline, visible on any picture) and a dot on the point
  draft       the draft badge (a pill with the panel colour and an accent outline, "پیش‌نویس" / "DRAFT") where the layout put it
Text: one <text> per laid-out line, at its baseline, in its paragraph's direction, anchored at its start (rtl: x1, ltr:
x0), white-space: pre, the graphic's own font order - also as an inline !important style, so a page rule cannot change
it (fonts: the film's local Vazirmatn / Inter; font_css embeds them).
Every element a later stage animates carries data-p (the Director's handle): gx-<key>-bg / -panel / -rule / -leader /
-dot / -badge / -<role>-<n>; <key> = the graphic id, one-to-one (letters, digits and "-" kept, any other character
_<hex>_). Structure (G4 animates the first three only):
  <g data-p="gx-<key>">                  the root: shown / hidden at the clip's frames
    <defs><clipPath id="gx-<key>-clip"><rect data-p="gx-<key>-clipr" .../></clipPath></defs>   = extent(): a wipe moves it
    [full frame: the background rect - outside the body: cut at the clip's edges, never animated]
    <g clip-path="url(#gx-<key>-clip)"><g data-p="gx-<key>-body"> ... </g></g>   opacity / slide / pop move the body
Contrast (WCAG 2 relative luminance): text >= 4.5:1, large text (>= 24 px, or >= 18.66 px bold) >= 3:1. An overlay panel
is semi-transparent, so its text is checked against the panel over BLACK and over WHITE (the worst of both: whatever the
picture under it); a full frame against its background. Below the limit: error in final, warning in draft.
"""
from . import safearea as SA
from .svg import el, num, text

ROLE_COLOR = {"title": "text", "subtitle": "muted", "body": "text", "attribution": "muted", "source": "muted", "badge": "text",
              "label": "text", "value": "text",                 # G6: a chart's item labels "label-<i>" / values "value-<i>"
              "tick": "muted", "xlabel": "muted", "legend": "text",  # G7 line chart
              "count": "text", "note": "muted"}                 # G7 counter
LIMIT, LARGE_LIMIT = 4.5, 3.0
NONTEXT_LIMIT = 3.0              # WCAG 1.4.11: graphical objects (bars, columns) against what is around them
AXIS_W = 2
LINE_W = 4
MARKER_R = 5


TYPE_OF = {"attribution": "subtitle", "badge": "source", "value": "label", "tick": "label", "xlabel": "label", "legend": "label",
           "count": "title", "note": "body"}               # a role's style type (contrast without a layout)


def base_role(role):
    return role.split("-")[0]
LEADER_W, DOT_R = 3, 7
FF_RULE_W = 120
CLIP_MARGIN = 8


def key_of(gid):
    return "".join(ch if (ch.isascii() and ch.isalnum()) or ch == "-" else f"_{ord(ch):x}_" for ch in gid)


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def luminance(rgb):
    def c(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (c(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def blend(fg, alpha, bg):
    return tuple(alpha * f + (1 - alpha) * g for f, g in zip(fg, bg))


def backgrounds(spec):
    """What is behind the text: [(name, rgb)] - the full-frame background, or the panel over black and over white."""
    c = spec["style"]["colors"]
    if spec["display"] == "fullframe":
        return [("background", _rgb(c["background"]))]
    p = _rgb(c["panel"])
    return [("panel over black", blend(p, c["panel_opacity"], (0, 0, 0))), ("panel over white", blend(p, c["panel_opacity"], (255, 255, 255)))]


def contrast(spec, lay=None):
    """Contrast issues of every text role the graphic shows - with a layout, at each drawn block's own size and weight
    (all roles of its kind at their style sizes when no layout is given) - and of every bar / column colour (non-text)."""
    issues = []
    c, t = spec["style"]["colors"], spec["style"]["type"]
    lvl = "error" if spec["mode"] == "final" else "warning"
    if lay:
        roles = {}
        for b in lay["blocks"]:
            r = base_role(b["role"])
            if r not in roles or b["size"] < roles[r][0]:
                roles[r] = (b["size"], b["weight"])
        if lay.get("badge"):
            roles["badge"] = (lay["badge"]["size"], 700)
        if lay.get("count"):
            roles["count"] = (lay["count"]["size"], lay["count"]["weight"])
        rows = sorted(roles.items())
    else:
        rows = [(r, (t[TYPE_OF.get(r, r)]["size"], 700 if r in ("badge", "value", "count") else t[TYPE_OF.get(r, r)]["weight"]))
                for r in sorted(ROLE_COLOR)]
    for role, (size, weight) in rows:
        need = LARGE_LIMIT if size >= 24 or (weight >= 700 and size >= 18.66) else LIMIT
        worst = min((ratio(_rgb(c[ROLE_COLOR[role]]), bg), name) for name, bg in backgrounds(spec))
        if worst[0] < need:
            issues.append({"level": lvl, "code": "low_contrast", "element": role,
                           "message": f"{role} ({c[ROLE_COLOR[role]]}, {size:g} px) has contrast {worst[0]:.2f}:1 against the {worst[1]} "
                                      f"(at least {need:g}:1)"})
    graphics_ = [("bar", x["fill"]) for x in (lay or {}).get("bars", [])] + [("line", x["stroke"]) for x in (lay or {}).get("lines", [])]
    for what, fill in sorted(set(graphics_)):
        worst = min((ratio(_rgb(fill), bg), name) for name, bg in backgrounds(spec))
        if worst[0] < NONTEXT_LIMIT:
            issues.append({"level": lvl, "code": "low_contrast", "element": what,
                           "message": f"{what}s ({fill}) have contrast {worst[0]:.2f}:1 against the {worst[1]} (at least {NONTEXT_LIMIT:g}:1 for graphics)"})
    return issues


def _text_el(k, role, n, ln, b, color):
    x = ln["x1"] if ln["direction"] == "rtl" else ln["x0"]
    return el("text", (("data-p", f"gx-{k}-{role}-{n}"), ("x", x), ("y", ln["baseline"]), ("fill", color), ("font-family", b["family"]),
                       ("font-size", b["size"]), ("font-weight", b["weight"]), ("direction", ln["direction"]), ("text-anchor", "start"),
                       ("style", _style(b["family"]))), text(ln["text"]))


def _style(family):
    """white-space: pre, and the measured font order as an inline !important declaration: it outranks a page's own
    !important rule (Film's Persian films set #art text { font-family: "Vazirmatn", ... !important }), so a line is drawn
    with exactly the font order it was measured with (Vazirmatn first draws spaces / punctuation of English text wider)."""
    return f"white-space:pre;font-family:{family} !important"


def leader(rect, at):
    """The callout's leader: from the box edge point nearest the target to the target (None if the target is in the box)."""
    x = min(max(at[0], rect[0]), rect[0] + rect[2])
    y = min(max(at[1], rect[1]), rect[1] + rect[3])
    return None if (x, y) == tuple(at) else ((x, y), tuple(at))


def extent(spec, lay, margin=None):
    """Everything a graphic draws except a full-frame background, [x, y, w, h] + CLIP_MARGIN on every side (room for the
    ink of letters that overhang their advance, the leader's outline and the dot): the area its animation stays inside."""
    r = lay["rect"]
    xs, ys = [r[0], r[0] + r[2]], [r[1], r[1] + r[3]]
    if spec["display"] == "fullframe":
        sp = spec["style"]["spacing"]
        ys.append(r[1] - 2 * sp["gap"] - sp["rule"])                       # the accent rule above the text
    if lay.get("badge"):
        b = lay["badge"]["rect"]
        xs += [b[0], b[0] + b[2]]
        ys += [b[1], b[1] + b[3]]
    if spec["kind"] == "callout":
        a = spec["place"]["at"]
        xs += [a[0] - DOT_R - 2, a[0] + DOT_R + 2]
        ys += [a[1] - DOT_R - 2, a[1] + DOT_R + 2]
    m = CLIP_MARGIN if margin is None else margin                    # margin=0: exactly what is drawn (clash checks)
    x0, y0, x1, y1 = min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
    return [round(x0, 3), round(y0, 3), round(x1 - x0, 3), round(y1 - y0, 3)]


def render_svg(spec, lay, font_css=None, standalone=True, key=None):
    """key: the handle prefix (default: from the graphic id); a page holding one graphic several times gives each its own."""
    if lay.get("status") not in ("OK", "WARN") or not lay.get("rect"):
        raise ValueError(f"graphic {spec['id']}: its layout failed ({[i['code'] for i in lay.get('issues', [])][:4]}): nothing is drawn")
    k = key or key_of(spec["id"])
    bg = ""
    c, sp = spec["style"]["colors"], spec["style"]["spacing"]
    rect = lay["rect"]
    parts = []
    if spec["display"] == "fullframe":
        bg = el("rect", (("data-p", f"gx-{k}-bg"), ("x", 0), ("y", 0), ("width", SA.FRAME[0]), ("height", SA.FRAME[1]),
                         ("fill", c["background"])))
        w = min(FF_RULE_W, rect[2])
        if spec["kind"] in ("title", "quote"):
            x = rect[0] + (rect[2] - w) / 2
        else:
            x = rect[0] + rect[2] - w if spec["lang"] == "fa" else rect[0]
        y = rect[1] - 2 * sp["gap"] - sp["rule"]
        parts.append(el("rect", (("data-p", f"gx-{k}-rule"), ("x", x), ("y", y), ("width", w), ("height", sp["rule"]), ("fill", c["accent"]))))
    else:
        if spec["kind"] == "callout":
            ld = leader(rect, spec["place"]["at"])
            if ld:
                (x0, y0), (x1, y1) = ld
                ln = (("x1", x0), ("y1", y0), ("x2", x1), ("y2", y1))
                # an outline in the panel colour under the accent line: it stays visible on any picture (light or busy)
                parts.append(el("g", (("data-p", f"gx-{k}-leader"),),
                                el("line", ln + (("stroke", c["panel"]), ("stroke-width", LEADER_W + 4), ("stroke-linecap", "round"))) +
                                el("line", ln + (("stroke", c["accent"]), ("stroke-width", LEADER_W), ("stroke-linecap", "round")))))
            parts.append(el("circle", (("data-p", f"gx-{k}-dot"), ("cx", spec["place"]["at"][0]), ("cy", spec["place"]["at"][1]), ("r", DOT_R),
                                       ("fill", c["accent"]), ("stroke", c["panel"]), ("stroke-width", 2))))
        parts.append(el("rect", (("data-p", f"gx-{k}-panel"), ("x", rect[0]), ("y", rect[1]), ("width", rect[2]), ("height", rect[3]),
                                 ("rx", sp["radius"]), ("fill", c["panel"]), ("fill-opacity", c["panel_opacity"]))))
        if lay.get("rule"):
            r = lay["rule"]
            parts.append(el("rect", (("data-p", f"gx-{k}-rule"), ("x", r[0]), ("y", r[1]), ("width", r[2]), ("height", r[3]), ("fill", c["accent"]))))
    for a_ in lay.get("axis", []):                                      # G6: the zero line, then the bars / columns
        parts.append(el("line", (("data-p", f"gx-{k}-axis-{lay['axis'].index(a_)}"), ("x1", a_[0]), ("y1", a_[1]), ("x2", a_[2]), ("y2", a_[3]),
                                 ("stroke", c["muted"]), ("stroke-width", AXIS_W))))
    for x in lay.get("bars", []):
        r = x["rect"]
        parts.append(el("rect", (("data-p", f"gx-{k}-bar-{x['item']}"), ("x", r[0]), ("y", r[1]), ("width", r[2]), ("height", r[3]),
                                 ("fill", x["fill"]))))
    for j, g_ in enumerate(lay.get("grid", [])):                        # G7 line chart: grid (zero stronger), lines, markers
        parts.append(el("line", (("data-p", f"gx-{k}-grid-{j}"), ("x1", g_["x0"]), ("y1", g_["y"]), ("x2", g_["x1"]), ("y2", g_["y"]),
                                 ("stroke", c["muted"] if g_["zero"] else c["grid"]), ("stroke-width", AXIS_W if g_["zero"] else 1))))
    for ln_ in lay.get("lines", []):
        pts = " ".join(f"{num(x)},{num(y)}" for x, y in ln_["points"])
        parts.append(el("polyline", (("data-p", f"gx-{k}-line-{ln_['series']}"), ("points", pts), ("fill", "none"), ("stroke", ln_["stroke"]),
                                     ("stroke-width", LINE_W), ("stroke-dasharray", ln_["dash"]), ("stroke-linejoin", "round"),
                                     ("stroke-linecap", "round"))))
    for ln_ in lay.get("lines", []):                                   # every series' points over every line: no line hides a data point
        if ln_["markers"]:
            parts.append(el("g", (("data-p", f"gx-{k}-pts-{ln_['series']}"),), "".join(
                el("circle", (("cx", x), ("cy", y), ("r", MARKER_R), ("fill", ln_["stroke"]), ("stroke", c["panel"] if spec["display"] == "overlay" else c["background"]),
                              ("stroke-width", 2))) for x, y in ln_["points"])))
    for sw in lay.get("swatches", []):
        parts.append(el("line", (("data-p", f"gx-{k}-swatch-{sw['series']}"), ("x1", sw["x0"]), ("y1", sw["y"]), ("x2", sw["x1"]), ("y2", sw["y"]),
                                 ("stroke", sw["stroke"]), ("stroke-width", LINE_W), ("stroke-dasharray", sw["dash"]), ("stroke-linecap", "round"))))
    cnt = lay.get("count")
    if cnt:                                                             # G7 counter: one <text> per shown number; G4 keys them
        for j, st_ in enumerate(cnt["states"]):
            x = st_["x1"] if st_["direction"] == "rtl" else st_["x0"]
            style = _style(cnt["family"]) + ("" if j == cnt["final"] else ";display:none")   # a still drawing shows the final value
            parts.append(el("text", (("data-p", f"gx-{k}-count-{j}"), ("x", x), ("y", st_["baseline"]), ("fill", c["text"]), ("font-family", cnt["family"]),
                                     ("font-size", cnt["size"]), ("font-weight", cnt["weight"]), ("direction", st_["direction"]),
                                     ("text-anchor", "start"), ("style", style)), text(st_["text"])))
    for b in lay["blocks"]:
        col = c[ROLE_COLOR[base_role(b["role"])]]
        parts += [_text_el(k, b["role"], n, ln, b, col) for n, ln in enumerate(b["lines"])]
    bd = lay.get("badge")
    if bd:
        r = bd["rect"]
        x = bd["x1"] if bd["direction"] == "rtl" else bd["x0"]
        parts.append(el("g", (("data-p", f"gx-{k}-badge"),),
                        el("rect", (("x", r[0]), ("y", r[1]), ("width", r[2]), ("height", r[3]), ("rx", r[3] / 2), ("fill", c["panel"]),
                                    ("fill-opacity", c["panel_opacity"]), ("stroke", c["accent"]), ("stroke-width", 2))) +
                        el("text", (("x", x), ("y", bd["baseline"]), ("fill", c["text"]), ("font-family", bd["family"]), ("font-size", bd["size"]),
                                    ("font-weight", 700), ("direction", bd["direction"]), ("text-anchor", "start"), ("style", _style(bd["family"]))),
                           text(bd["text"]))))
    ex = extent(spec, lay)
    clip = el("defs", (), el("clipPath", (("id", f"gx-{k}-clip"), ("clipPathUnits", "userSpaceOnUse")),
                                 el("rect", (("data-p", f"gx-{k}-clipr"), ("x", ex[0]), ("y", ex[1]), ("width", ex[2]), ("height", ex[3])))))
    body = el("g", (("clip-path", f"url(#gx-{k}-clip)"),), el("g", (("data-p", f"gx-{k}-body"),), "".join(parts)))
    g = el("g", (("data-p", f"gx-{k}"), ("data-graphic", spec["id"]), ("data-kind", spec["kind"]), ("data-display", spec["display"])),
           clip + bg + body)
    if not standalone:
        return g
    style = el("style", (), font_css) if font_css else ""
    return el("svg", (("xmlns", "http://www.w3.org/2000/svg"), ("width", SA.FRAME[0]), ("height", SA.FRAME[1]),
                      ("viewBox", f"0 0 {SA.FRAME[0]} {SA.FRAME[1]}")), style + g)


BACKS = {
    "dark": '<rect width="1920" height="1080" fill="#20242b"/><circle cx="1400" cy="300" r="380" fill="#3b4350"/>',
    "light": '<rect width="1920" height="1080" fill="#e8e2d6"/><circle cx="500" cy="700" r="420" fill="#cfc6b4"/>',
    "busy": '<defs><pattern id="pv-busy" width="120" height="120" patternUnits="userSpaceOnUse"><rect width="120" height="120" fill="#f2f2f2"/>'
            '<rect width="60" height="60" fill="#151515"/><rect x="60" y="60" width="60" height="60" fill="#151515"/></pattern></defs>'
            '<rect width="1920" height="1080" fill="url(#pv-busy)"/>',
}


def guides():
    a, b = SA.ALLOWED, SA.BAND
    return (el("rect", (("x", b[0]), ("y", b[1]), ("width", b[2]), ("height", b[3]), ("fill", "#ff2d55"), ("fill-opacity", 0.18))) +
            el("rect", (("x", a[0]), ("y", a[1]), ("width", a[2]), ("height", a[3]), ("fill", "none"), ("stroke", "#00d0ff"),
                        ("stroke-width", 2), ("stroke-dasharray", "12 8"))))


def preview_html(items, font_css="", backs=("dark", "light", "busy")):
    """A static review page: each graphic over each background, half size, with the safe area (dashed) and the subtitle
    band (red) as guides. items: [(spec, lay)]."""
    rows = []
    for spec, lay in items:
        pk = key_of(spec["id"])                       # each copy on the page its own handles / clip id
        frames = "".join(
            f'<figure><svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 1920 1080">{BACKS[bk]}'
            f'{render_svg(spec, lay, standalone=False, key=pk + "-pv-" + bk)}{guides()}</svg>'
            f'<figcaption>{text(bk)}</figcaption></figure>' for bk in backs)
        issues = ", ".join(f"{i['level']}: {i['code']}" for i in lay["issues"] + contrast(spec, lay)) or "no issues"
        rows.append(f'<section><h2>{text(spec["id"])} — {text(spec["kind"])} / {text(spec["display"])} / {text(spec["lang"])}'
                    f' <small>{text(issues)}</small></h2><div class="row">{frames}</div></section>')
    return ("<!doctype html><html><head><meta charset=\"utf-8\"><title>NFP Graphics preview</title><style>" + (font_css or "") +
            "body{margin:16px;background:#111;color:#ddd;font:14px Inter,Vazirmatn,sans-serif}h2{font-size:15px;margin:18px 0 6px}"
            "small{color:#999;font-weight:400}.row{display:flex;gap:12px;flex-wrap:wrap}figure{margin:0}figcaption{color:#888;font-size:12px}"
            "</style></head><body>" + "".join(rows) + "</body></html>")
