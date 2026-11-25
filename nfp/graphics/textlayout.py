"""NFP Graphics - G2: text layout of the text kinds (title, lower-third, info-card, quote, callout). Standard library; no
measuring, no process: measured text widths come in as data (tools/measure.py measures them in the local Chromium).

  requests(spec, metrics=None) -> the texts to measure [(text, size, weight, family)]: round 1 (no metrics) every
                                  unbreakable piece; round 2 (with round-1 metrics) every run of pieces that may fit a line
  layout(spec, metrics)        -> nfp.graphics.layout/1: the box (rect), its text blocks, every line with its text, its
                                  measured width, its horizontal span and baseline, plus QC issues
spec = a resolved graphic (graphics.validate(...)["graphic"], nfp.graphics.spec/1).

Lines are broken only at ordinary spaces (text.units). A paragraph is broken by dynamic programming over its pieces with
the MEASURED width of every candidate line (never a sum of word widths): fewest lines first; then titles / subtitles /
attributions are balanced (smallest widest line), bodies are ragged (smallest sum of squared free space, the last line
free). A piece wider than the line, or more lines than the role allows, is an overflow error - text is never shrunk,
cut or drawn outside its box. Without a measurement a width is estimated (warning in draft, error in final). A line is
style.line_height x size tall, or the faces' measured ascent + descent when that is more (Persian script needs it).

Boxes (frame pixels): an overlay box is as wide as its widest line + padding (+ the accent rule of title / lower third /
info card on the reading-start side), at most MAX_W; it is placed by its anchor inside graphics.safearea.ALLOWED, with
BOTTOM_GAP free above the subtitle band, or it is the explicit place.rect (the text must fit inside it). A callout box
sits beside its point (towards the frame centre), CALLOUT_GAP away, kept inside the safe area. A full-frame graphic's
text block is centred in the safe area. Every box is checked with safearea.check_rect (band, safe area, vignette).
Text sits on the reading-start side (fa: right, en: left); full-frame titles and quotes are centred.
"""
from . import safearea as SA
from . import text as TX

LAYOUT_SCHEMA = "nfp.graphics.layout/1"
TEXT_KINDS = ("title", "lower-third", "info-card", "quote", "callout")
DATA_LAID_OUT = ("comparison", "bar", "column")             # G6: datalayout.py
SERIES_LAID_OUT = ("line", "counter")                       # G7: linecounter.py
MAX_W = {"overlay": {"title": 1100, "lower-third": 860, "info-card": 620, "quote": 860, "callout": 460},
         "fullframe": {"title": 1400, "info-card": 1100, "quote": 1200}}
MAX_LINES = {"title": {"fullframe": 3, "overlay": 2}, "subtitle": 2, "attribution": 1, "source": 2,
             "body": {("fullframe", "info-card"): 10, ("fullframe", "quote"): 7, ("overlay", "info-card"): 7,
                      ("overlay", "quote"): 5, ("overlay", "callout"): 4}}
BALANCED = ("title", "subtitle", "attribution")
ROLE_TYPE = {"title": "title", "subtitle": "subtitle", "body": "body", "attribution": "subtitle", "source": "source"}
RULED = ("title", "lower-third", "info-card")
BOTTOM_GAP = 24
CALLOUT_GAP = 48
EST = (0.56, 0.28)            # estimate without a measurement: em per character, em per space


def _source_text(spec):
    if spec["kind"] not in ("info-card", "quote", "callout") or not spec.get("content_source"):
        return None
    s = next((x for x in spec["sources"] if x["id"] == spec["content_source"]), None)
    if not s:
        return None
    lab = TX.LABEL[spec["lang"]]
    year = (s.get("date") or "")[:4]
    pub = s["publisher"] + (("، " if spec["lang"] == "fa" else ", ") + (year.translate(TX.FA_DIGITS) if spec["lang"] == "fa" else year) if year else "")
    return lab["source"] + pub


def blocks_of(spec):
    """[(role, text, multiline)] of a text kind, in drawing order (the shown text: quote marks, the dash, the source line)."""
    c, k, lab = spec["content"], spec["kind"], TX.LABEL[spec["lang"]]
    out = []
    if k in ("title", "lower-third"):
        out += [("title", c["title"], False)] + ([("subtitle", c["subtitle"], False)] if "subtitle" in c else [])
    elif k == "info-card":
        out += ([("title", c["title"], False)] if "title" in c else []) + [("body", c["body"], True)]
    elif k == "quote":
        q0, q1 = lab["quote"]
        out += [("body", q0 + c["body"] + q1, True), ("attribution", lab["dash"] + c["attribution"], False)]
    elif k == "callout":
        out += [("body", c["body"], True)]
    src = _source_text(spec)
    if src:
        out.append(("source", src, False))
    return out


def _frame(spec):
    """(box max width, text max width, rule width + gap or 0) for this kind / display / place."""
    sp = spec["style"]["spacing"]
    rule = sp["rule"] + sp["gap"] if spec["display"] == "overlay" and spec["kind"] in RULED else 0
    if spec["display"] == "fullframe":
        bw = min(MAX_W["fullframe"][spec["kind"]], SA.ALLOWED[2])
        return bw, bw, 0
    rect = (spec.get("place") or {}).get("rect")
    bw = rect[2] if rect else MAX_W["overlay"][spec["kind"]]
    return bw, bw - 2 * sp["padding"] - rule, rule


def _plan(spec):
    st = spec["style"]
    _, tw, _ = _frame(spec)
    out = []
    for role, txt, multi in blocks_of(spec):
        t = st["type"][ROLE_TYPE[role]]
        ml = MAX_LINES[role]
        if isinstance(ml, dict):
            ml = ml.get((spec["display"], spec["kind"])) or ml.get(spec["display"])
        out.append({"role": role, "text": txt, "paras": [TX.units(p) for p in TX.paragraphs(txt, multi)], "size": t["size"],
                    "weight": t["weight"], "family": st["font"], "maxw": tw, "maxlines": ml})
    return out


def _key(text, b):
    return (text, float(b["size"]), int(b["weight"]), b["family"])


def _index(metrics):
    return {} if not metrics else {(m["text"], float(m["size"]), int(m["weight"]), m["family"]): m for m in metrics["items"]}


def _est(text, size):
    return sum(EST[1] if ch == " " else EST[0] for ch in text) * size


BADGE_PAD, BADGE_GAP = 8, 8


def _badge(spec):
    """The draft badge's block (role 'badge': the source type size, bold) or None."""
    if not spec.get("draft_badge"):
        return None
    st = spec["style"]
    return {"role": "badge", "text": TX.LABEL[spec["lang"]]["draft"], "size": st["type"]["source"]["size"], "weight": 700, "family": st["font"]}


def requests(spec, metrics=None):
    """Texts to measure. Round 1 (metrics None): every unbreakable piece (+ the draft badge). Round 2: every run of pieces
    whose estimated width (measured pieces + estimated spaces) is within 10 % over the line width."""
    if spec["kind"] in DATA_LAID_OUT:
        from . import datalayout as DL
        return DL.requests(spec, metrics)
    if spec["kind"] in SERIES_LAID_OUT:
        from . import linecounter as LC
        return LC.requests(spec, metrics)
    if spec["kind"] not in TEXT_KINDS:
        return []
    idx, out = _index(metrics), set()
    bd = _badge(spec)
    if bd:
        out.add(_key(bd["text"], bd))
    for b in _plan(spec):
        for us in b["paras"]:
            for u in us:
                out.add(_key(u, b))
            if metrics is None:
                continue
            for i in range(len(us)):
                w = 0.0
                for j in range(i, len(us)):
                    m = idx.get(_key(us[j], b))
                    w += (m["width"] if m else _est(us[j], b["size"])) + (EST[1] * b["size"] if j > i else 0)
                    if w > b["maxw"] * 1.1:
                        break
                    if j > i:
                        out.add(_key(" ".join(us[i:j + 1]), b))
    return sorted(out)


def break_lines(us, maxw, maxlines, width, balanced):
    """Optimal breaks of one paragraph's pieces. width(text) -> px. -> (lines [(text, width)], error or None)."""
    n = len(us)
    for u in us:
        if width(u) > maxw + 1e-6:
            return None, ("word_too_wide", f"{u!r} is {width(u):.0f} px, wider than the line ({maxw:.0f} px): it cannot be broken")
    best = [None] * (n + 1)
    best[0] = (0, 0.0, 0.0, -1, 0.0)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            if best[i] is None:
                continue
            w = width(" ".join(us[i:j]))
            if w > maxw + 1e-6:
                break
            lines, mx, sq = best[i][:3]
            if balanced:
                cand = (lines + 1, max(mx, w), sq + (maxw - w) ** 2, i, w)
            else:
                cand = (lines + 1, 0.0, sq + (0.0 if j == n else (maxw - w) ** 2), i, w)
            if best[j] is None or cand[:3] < best[j][:3]:
                best[j] = cand
    out, j = [], n
    while j > 0:
        i, w = best[j][3], best[j][4]
        out.append((" ".join(us[i:j]), w))
        j = i
    out.reverse()
    if len(out) > maxlines:
        return out, ("text_overflow", f"needs {len(out)} lines, at most {maxlines} fit")
    return out, None


def _anchor_xy(anchor, w, h):
    x0, y0, aw, ah = SA.ALLOWED
    bottom = y0 + ah - BOTTOM_GAP
    hx = {"left": x0, "center": x0 + (aw - w) / 2, "right": x0 + aw - w}
    vy = {"top": y0, "middle": y0 + (bottom - y0 - h) / 2, "bottom": bottom - h}
    parts = anchor.split("-")
    v = parts[0] if parts[0] in ("top", "bottom") else "middle"
    hh = parts[-1] if parts[-1] in ("left", "right") else "center"
    return hx[hh], vy[v]


def _callout_xy(at, w, h):
    x0, y0, aw, ah = SA.ALLOWED
    x = at[0] + CALLOUT_GAP if at[0] < SA.FRAME[0] / 2 else at[0] - CALLOUT_GAP - w
    y = at[1] - h / 2
    return min(max(x, x0), x0 + aw - w), min(max(y, y0), y0 + ah - BOTTOM_GAP - h)


def ff_rule_space(spec):
    """Height a full-frame graphic keeps free above its content for the accent rule render.py draws there
    (rule y = content top - 2 gap - rule height): counted in the centring, so the rule stays in the safe area."""
    sp = spec["style"]["spacing"]
    return 2 * sp["gap"] + sp["rule"]


def place_badge(spec, rect, idx, add):
    """The draft badge (or None) -> (badge, estimated): above the box at its reading-end corner (below it when there is no
    room above); a full-frame graphic's at the safe area's top reading-end corner. Measured like every text; checked like
    every box."""
    bd = _badge(spec)
    if not bd:
        return None, False
    m = idx.get(_key(bd["text"], bd))
    bw0 = m["width"] if m else _est(bd["text"], bd["size"])
    asc, desc = (m["ascent"], m["descent"]) if m else (bd["size"] * 0.95, bd["size"] * 0.3)
    bw, bh = bw0 + 2 * BADGE_PAD, asc + desc + BADGE_PAD
    end_left = spec["lang"] == "fa"                                  # the reading end: left in Persian, right in English
    if spec["display"] == "fullframe":
        x = SA.ALLOWED[0] if end_left else SA.ALLOWED[0] + SA.ALLOWED[2] - bw
        y = SA.ALLOWED[1]
    else:
        x = rect[0] if end_left else rect[0] + rect[2] - bw
        y = rect[1] - BADGE_GAP - bh
        if y < SA.ALLOWED[1]:
            y = rect[1] + rect[3] + BADGE_GAP
    brect = [round(x, 3), round(y, 3), round(bw, 3), round(bh, 3)]
    SA.check_rect(brect, "draft badge", add)
    tx0 = x + BADGE_PAD
    return ({"text": bd["text"], "rect": brect, "size": bd["size"], "weight": 700, "family": bd["family"],
             "x0": round(tx0, 3), "x1": round(tx0 + bw0, 3), "baseline": round(y + BADGE_PAD / 2 + asc, 3),
             "direction": "rtl" if spec["lang"] == "fa" else "ltr"}, m is None)


def layout(spec, metrics=None):
    """The laid-out text of one text-kind graphic (see the module doc); data kinds: datalayout.layout (G6)."""
    if spec["kind"] in DATA_LAID_OUT:
        from . import datalayout as DL                         # (imported here: datalayout builds on this module)
        return DL.layout(spec, metrics)
    if spec["kind"] in SERIES_LAID_OUT:
        from . import linecounter as LC
        return LC.layout(spec, metrics)
    issues = []

    def add(level, code, msg, element=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("element", element), ("message", msg)) if v is not None})

    out = {"schema": LAYOUT_SCHEMA, "id": spec["id"], "kind": spec["kind"], "display": spec["display"], "lang": spec["lang"],
           "rect": None, "frame": None, "rule": None, "blocks": [], "badge": None, "measured": True, "issues": issues}

    def done():
        ne = sum(x["level"] == "error" for x in issues)
        out["status"] = "FAIL" if ne else "WARN" if any(x["level"] == "warning" for x in issues) else "OK"
        return out

    if spec["kind"] not in TEXT_KINDS:
        add("info", "layout_later", f"a {spec['kind']} is laid out with its data (G7)")
        return done()
    idx = _index(metrics)
    estimated = set()

    def width(text, b):
        m = idx.get(_key(text, b))
        return m["width"] if m else _est(text, b["size"])

    st, sp = spec["style"], spec["style"]["spacing"]
    lh_k = st["line_height"]
    side = "right" if spec["lang"] == "fa" else "left"
    align = "center" if spec["display"] == "fullframe" and spec["kind"] in ("title", "quote") else side
    blocks = []
    for b in _plan(spec):
        lines = []
        for us in b["paras"]:
            got, err = break_lines(us, b["maxw"], b["maxlines"], lambda t: width(t, b), b["role"] in BALANCED)
            if err:
                add("error", err[0], err[1], b["role"])
            pdir = TX.direction(" ".join(us), "rtl" if spec["lang"] == "fa" else "ltr")    # a line keeps its PARAGRAPH's direction
            lines += [(t, w, pdir) for t, w in got or []]
        estimated.update(t for t, _, _ in lines if _key(t, b) not in idx)      # only lines drawn count (not a run tried and refused)
        if len(lines) > b["maxlines"] and not any(x.get("element") == b["role"] and x["code"] == "text_overflow" for x in issues):
            add("error", "text_overflow", f"needs {len(lines)} lines over its paragraphs, at most {b['maxlines']} fit", b["role"])
        ms = [idx.get(_key(t, b)) for t, _, _ in lines]
        asc = max([m["ascent"] for m in ms if m] or [b["size"] * 0.95])
        desc = max([m["descent"] for m in ms if m] or [b["size"] * 0.3])
        # line height: the style's, but never less than the faces' own ascent + descent (Vazirmatn's is ~1.57 em): lines never
        # cover each other and the first / last line stays inside the box
        blocks.append(dict(b, lines=lines, ascent=asc, descent=desc, lh=max(b["size"] * lh_k, asc + desc)))
    if estimated:
        out["measured"] = False
        add("error" if spec["mode"] == "final" else "warning", "text_not_measured",
            f"{len(estimated)} text runs were estimated, not measured (measure with graphics.tools.measure)")
    if any(x["level"] == "error" for x in issues):
        return done()

    text_w = max(w for b in blocks for _, w, _ in b["lines"])
    text_h = sum(len(b["lines"]) * b["lh"] for b in blocks) + sp["gap"] * (len(blocks) - 1)
    bw_max, tw_max, rule = _frame(spec)
    pad = sp["padding"]
    if spec["display"] == "fullframe":
        bw = min(text_w, tw_max)
        top = ff_rule_space(spec)                                       # the accent rule G3 draws above the text
        if text_h + top > SA.ALLOWED[3] + 1e-6:
            add("error", "text_overflow", f"the text needs {text_h + top:.0f} px of height (with its accent rule), the safe area has "
                                          f"{SA.ALLOWED[3]}", "box")
            return done()
        x, y = SA.ALLOWED[0] + (SA.ALLOWED[2] - bw) / 2, SA.ALLOWED[1] + top + (SA.ALLOWED[3] - top - text_h) / 2
        rect = [x, y, bw, text_h]
        inner = rect
        out["frame"] = list(SA.ALLOWED)
    else:
        rect0 = (spec.get("place") or {}).get("rect")
        w, h = text_w + 2 * pad + rule, text_h + 2 * pad
        if rect0:
            if h > rect0[3] + 1e-6:
                add("error", "text_overflow", f"the text needs {h:.0f} px of height, the box has {rect0[3]:.0f}", "place")
                return done()
            rect = list(rect0)
        else:
            if spec["kind"] == "callout":
                x, y = _callout_xy(spec["place"]["at"], w, h)
            else:
                x, y = _anchor_xy(spec["place"]["anchor"], w, h)
            rect = [x, y, w, h]
        ix = rect[0] + pad + (rule if side == "left" else 0)
        inner = [ix, rect[1] + pad, rect[2] - 2 * pad - rule, rect[3] - 2 * pad]
        if rule:
            rx = rect[0] + pad if side == "left" else rect[0] + rect[2] - pad - sp["rule"]
            out["rule"] = [rx, rect[1] + pad, sp["rule"], text_h]
    SA.check_rect(rect, "box", add)
    rect = [round(v, 3) for v in rect]
    y = inner[1]
    for b in blocks:
        rows = []
        for t, w, pdir in b["lines"]:
            if align == "center":
                x0 = inner[0] + (inner[2] - w) / 2
            elif align == "right":
                x0 = inner[0] + inner[2] - w
            else:
                x0 = inner[0]
            base = y + (b["lh"] - (b["ascent"] + b["descent"])) / 2 + b["ascent"]
            rows.append({"text": t, "width": round(w, 3), "x0": round(x0, 3), "x1": round(x0 + w, 3), "baseline": round(base, 3),
                         "direction": pdir})
            y += b["lh"]
        out["blocks"].append({"role": b["role"], "size": b["size"], "weight": b["weight"], "family": b["family"], "align": align,
                              "ascent": round(b["ascent"], 3), "descent": round(b["descent"], 3), "line_height": round(b["lh"], 3),
                              "lines": rows})
        y += sp["gap"]
    out["rect"] = rect
    out["inner"] = [round(v, 3) for v in inner]
    badge, est = place_badge(spec, rect, idx, add)
    out["badge"] = badge
    if est and out["measured"]:
        out["measured"] = False
        add("error" if spec["mode"] == "final" else "warning", "text_not_measured", "the draft badge was estimated, not measured")
    return done()
