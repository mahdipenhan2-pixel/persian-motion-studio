"""NFP Graphics - G1: the graphic document (nfp.graphics/1), its validation and QC. Standard library; data only (no
layout, no SVG, no rendering, no process, no network).

  {"schema": "nfp.graphics/1", "id": "title-1", "mode": "draft" | "final", "lang": "fa" | "en",
   "kind": "title" | "lower-third" | "info-card" | "quote" | "callout" | "comparison" | "bar" | "column" | "line" | "counter",
   "style": {"preset": "documentary-dark", "accent": "#d9a441", "scale": 1},            styles.py
   "place": {"anchor": "bottom-left"} | {"rect": [x, y, w, h]} (+ "at": [x, y] for a callout)     overlays only
   "content": {"title": "...", "subtitle": "...", "body": "...", "attribution": "...", "source": "s1"},
   "data": {"unit": "%", "format": {"digits": "auto" | "fa" | "en", "decimals": 0..3}, "source": "s1",
            "items": [{"label": "...", "value": 42.5, "source": "s2"}]                    comparison / bar / column
            "series": [{"label": "...", "points": [{"x": "1990", "value": 3.1}]}]         line
            "value": 1250, "from": 0},                                                     counter
   "sources": [{"id": "s1", "title": "...", "publisher": "...", "url": "https://...", "date": "2024-05-01", "verified": true}],
   "animation": {"in": {"type": "fade" | "pop" | "wipe" | "slide" | "none", "frames": 12, "direction": "left"},
                 "out": {"type": "fade", "frames": 9}}}

- Display (full frame / overlay) is NOT in the document: it comes from the Timeline track the clip sits on (visual = full
  frame, overlay = overlay); validate(doc, display) checks the kind allows it. Timing is the clip's; the document only
  has enter / exit lengths in frames.
- Data integrity: every number of a data kind must reach a source (its own "source" or data.source); a quote, and an
  info-card / callout whose text has digits, needs content.source. In "final" mode a missing, unknown or unverified source
  is an error; in "draft" a warning (unknown ids are always errors), and the graphic is marked draft (draft_badge).
"""
import math
import re
import unicodedata

from . import safearea as SA
from . import styles as ST

SCHEMA = "nfp.graphics/1"
SPEC_SCHEMA = "nfp.graphics.spec/1"
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")           # the id rule of nfp.timeline / nfp.mapmotion
DATE_RE = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")
URL_RE = re.compile(r"https?://\S+")
TOP = {"schema", "id", "mode", "lang", "kind", "style", "place", "content", "data", "sources", "animation", "note"}
BOTH, OVERLAY = ("fullframe", "overlay"), ("overlay",)
DISPLAYS = {"title": BOTH, "lower-third": OVERLAY, "info-card": BOTH, "quote": BOTH, "callout": OVERLAY,
            "comparison": BOTH, "bar": BOTH, "column": BOTH, "line": BOTH, "counter": BOTH}
KINDS = tuple(DISPLAYS)
DATA_KINDS = ("comparison", "bar", "column", "line", "counter")
# content: (required, optional)
CONTENT = {"title": ({"title"}, {"subtitle", "source"}), "lower-third": ({"title"}, {"subtitle", "source"}),
           "info-card": ({"body"}, {"title", "source"}), "quote": ({"body", "attribution", "source"}, set()),
           "callout": ({"body"}, {"source"}), "comparison": (set(), {"title", "subtitle"}), "bar": (set(), {"title", "subtitle"}),
           "column": (set(), {"title", "subtitle"}), "line": (set(), {"title", "subtitle"}), "counter": ({"title"}, {"subtitle"})}
MAXLEN = {"title": 80, "subtitle": 120, "body": 400, "attribution": 120, "label": 40, "x": 16, "unit": 12}
MULTILINE = {"body"}                      # only the body may hold an explicit line break
DIGIT_NEEDS_SOURCE = ("info-card", "callout")
ITEMS = {"comparison": (2, 4), "bar": (1, 12), "column": (1, 12)}
SERIES, POINTS = (1, 4), (2, 60)
DATA_KEYS = {"comparison": {"unit", "format", "source", "items"}, "bar": {"unit", "format", "source", "items"},
             "column": {"unit", "format", "source", "items"}, "line": {"unit", "format", "source", "series"},
             "counter": {"unit", "format", "source", "value", "from"}}
ANCHORS = ("top-left", "top", "top-right", "left", "center", "right", "bottom-left", "bottom", "bottom-right")
DEFAULT_ANCHOR = {"title": "top", "lower-third": "bottom-start", "info-card": "start", "quote": "center", "callout": "start",
                  "comparison": "center", "bar": "center", "column": "center", "line": "center", "counter": "center"}
ANIM_TYPES = ("none", "fade", "pop", "wipe", "slide")
DIRECTIONS = ("left", "right", "up", "down")
ANIM_MAX = 90
ANIM_DEFAULT = {"type": "fade", "frames": 9}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def has_digit(s):
    return any(unicodedata.category(ch) == "Nd" for ch in s)


def _text(v, key, where, add, multiline=False):
    """A text field: a non-empty string within its length, no control characters (a body may break lines with \\n)."""
    if not isinstance(v, str) or not v.strip():
        add("error", "schema", f"{key} must be non-empty text", where)
        return None
    bad = [ch for ch in v if unicodedata.category(ch) == "Cc" and not (multiline and ch == "\n")]
    if bad:
        add("error", "schema", f"{key} holds control characters" + ("" if multiline else " (a line break only in body)"), where)
        return None
    n = MAXLEN.get(key)
    if n and len(v) > n:
        add("error", "text_length", f"{key} is {len(v)} characters (at most {n})", where)
        return None
    return v


def _anchor(name, lang):
    """start / end anchors follow the reading direction (Persian starts on the right)."""
    start, end = ("right", "left") if lang == "fa" else ("left", "right")
    return {"start": start, "end": end, "bottom-start": "bottom-" + start, "bottom-end": "bottom-" + end,
            "top-start": "top-" + start, "top-end": "top-" + end}.get(name, name)


def validate(doc, display=None, clip_frames=None):
    """QC of one graphic document. display: 'fullframe' / 'overlay' (from the clip's track) or None (document only);
    clip_frames: the clip's length in frames (or None). -> {"status": OK | WARN | FAIL, "errors", "warnings",
    "issues": [{level, code, element?, message}], "graphic": the resolved graphic (nfp.graphics.spec/1) when there is no
    error and a display is given, else None}."""
    if display not in (None, "fullframe", "overlay"):
        raise ValueError("display must be 'fullframe', 'overlay' or None")
    issues = []

    def add(level, code, msg, element=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("element", element), ("message", msg)) if v is not None})

    def done(graphic=None):
        ne = sum(x["level"] == "error" for x in issues)
        nw = sum(x["level"] == "warning" for x in issues)
        return {"status": "FAIL" if ne else "WARN" if nw else "OK", "errors": ne, "warnings": nw, "issues": issues,
                "graphic": graphic if not ne and display else None}

    if not isinstance(doc, dict):
        add("error", "schema", "a graphic document is a JSON object")
        return done()
    for k in sorted(set(doc) - TOP):
        add("error", "schema", f"unknown key {k!r}")
    if doc.get("schema") != SCHEMA:
        add("error", "schema", f"schema must be {SCHEMA!r}")
    gid = doc.get("id")
    if not (isinstance(gid, str) and ID_RE.fullmatch(gid)):
        add("error", "schema", "id must be 1..80 of A-Z a-z 0-9 . _ - (starting with a letter or digit)")
    mode = doc.get("mode", "draft")
    if mode not in ("draft", "final"):
        add("error", "schema", "mode must be 'draft' or 'final'")
        mode = "draft"
    lang = doc.get("lang")
    if lang not in ("fa", "en"):
        add("error", "schema", "lang must be 'fa' or 'en' (it sets the font order, the digits and the reading direction)")
        lang = "en"
    kind = doc.get("kind")
    if kind not in KINDS:
        add("error", "schema", f"kind must be one of {', '.join(KINDS)}")
        return done()
    if display and display not in DISPLAYS[kind]:
        add("error", "display", f"a {kind} is drawn only as {' / '.join(DISPLAYS[kind])} (its clip is on a "
                                f"{'visual' if display == 'fullframe' else 'overlay'} track)")
    style = ST.resolve_style(doc.get("style"), display or DISPLAYS[kind][0], lang, add)

    # ---- sources
    sources = {}
    raw = doc.get("sources", [])
    if not isinstance(raw, list):
        add("error", "schema", "sources must be a list")
        raw = []
    for i, s in enumerate(raw):
        where = f"sources[{i}]"
        if not isinstance(s, dict):
            add("error", "schema", "a source is an object", where)
            continue
        sid = s.get("id")
        if not (isinstance(sid, str) and ID_RE.fullmatch(sid)):
            add("error", "schema", "a source needs an id", where)
            continue
        where = f"source {sid}"
        if sid in sources:
            add("error", "schema", "duplicate source id", where)
            continue
        for k in sorted(set(s) - {"id", "title", "publisher", "url", "date", "verified", "note"}):
            add("error", "schema", f"unknown source key {k!r}", where)
        ok = True
        for k in ("title", "publisher"):
            if not (isinstance(s.get(k), str) and s[k].strip()):
                add("error", "source", f"a source needs {k}", where)
                ok = False
        if "url" in s and not (isinstance(s["url"], str) and URL_RE.fullmatch(s["url"])):
            add("error", "source", "url must be an http(s) address", where)
            ok = False
        if "date" in s and not (isinstance(s["date"], str) and DATE_RE.fullmatch(s["date"])):
            add("error", "source", "date must be YYYY, YYYY-MM or YYYY-MM-DD", where)
            ok = False
        if not isinstance(s.get("verified"), bool):
            add("error", "source", "verified must be true or false (a person checked the source)", where)
            ok = False
        sources[sid] = {"id": sid, "title": s.get("title"), "publisher": s.get("publisher"), "url": s.get("url"),
                        "date": s.get("date"), "verified": s.get("verified") is True and ok}
    used = set()
    draft_marks = []

    def need_source(ref, where, what):
        lvl = "error" if mode == "final" else "warning"
        if ref is None:
            add(lvl, "unsourced", f"{what} has no source" + (" (not allowed in a final graphic)" if mode == "final" else ""), where)
            draft_marks.append(where)
            return
        if not (isinstance(ref, str) and ref in sources):
            add("error", "unknown_source", f"{what}: source {ref!r} is not in sources", where)
            return
        used.add(ref)
        if not sources[ref]["verified"]:
            add(lvl, "unverified_source", f"{what}: source {ref!r} is not verified" + (" (not allowed in a final graphic)" if mode == "final" else ""), where)
            draft_marks.append(where)

    # ---- content
    content = doc.get("content", {})
    if not isinstance(content, dict):
        add("error", "schema", "content must be an object")
        content = {}
    req, opt = CONTENT[kind]
    for k in sorted(set(content) - req - opt):
        add("error", "schema", f"a {kind} has no content {k!r} (it takes {', '.join(sorted(req | opt)) or 'nothing'})", "content")
    for k in sorted(req - {"source"} - set(content)):
        add("error", "schema", f"a {kind} needs content {k!r}", "content")
    text = {}
    for k in sorted((req | opt) - {"source"}):
        if k in content:
            v = _text(content[k], k, "content", add, k in MULTILINE)
            if v is not None:
                text[k] = v
    if kind == "quote":
        need_source(content.get("source"), "content", "the quote")
    elif kind in DIGIT_NEEDS_SOURCE and any(has_digit(v) for v in text.values()):
        need_source(content.get("source"), "content", f"the {kind}'s text has a number and")
    elif content.get("source") is not None:
        need_source(content.get("source"), "content", "the text")

    # ---- data
    data_out = None
    data = doc.get("data")
    if kind not in DATA_KINDS:
        if data is not None:
            add("error", "schema", f"a {kind} has no data (data is for {', '.join(DATA_KINDS)})", "data")
    elif not isinstance(data, dict):
        add("error", "schema", f"a {kind} needs data", "data")
    else:
        for k in sorted(set(data) - DATA_KEYS[kind]):
            add("error", "schema", f"a {kind}'s data has no {k!r} (it takes {', '.join(sorted(DATA_KEYS[kind]))})", "data")
        unit = data.get("unit")
        if unit is not None:
            unit = _text(unit, "unit", "data", add)
        fmt = data.get("format", {})
        fmt = fmt if isinstance(fmt, dict) else add("error", "schema", "format must be an object", "data") or {}
        for k in sorted(set(fmt) - {"digits", "decimals"}):
            add("error", "schema", f"unknown format key {k!r}", "data")
        digits = fmt.get("digits", "auto")
        if digits not in ("auto", "fa", "en"):
            add("error", "schema", "format.digits must be auto, fa or en", "data")
            digits = "auto"
        decimals = fmt.get("decimals", 0)
        if not (_int(decimals) and 0 <= decimals <= 3):
            add("error", "schema", "format.decimals must be 0..3", "data")
            decimals = 0
        dsrc = data.get("source")
        data_out = {"unit": unit, "format": {"digits": lang if digits == "auto" else digits, "decimals": decimals}}

        def value(v, where):
            if not _num(v):
                add("error", "data", "value must be a finite number", where)
                return None
            return float(v)

        if kind in ITEMS:
            items = data.get("items")
            lo, hi = ITEMS[kind]
            if not (isinstance(items, list) and lo <= len(items) <= hi):
                add("error", "data", f"a {kind} needs {lo}..{hi} items", "data")
                items = []
            out, labels = [], set()
            for i, it in enumerate(items):
                where = f"data.items[{i}]"
                if not isinstance(it, dict):
                    add("error", "data", "an item is an object", where)
                    continue
                for k in sorted(set(it) - {"label", "value", "source", "highlight"}):
                    add("error", "schema", f"unknown item key {k!r}", where)
                lab = _text(it.get("label"), "label", where, add)
                if lab is not None and lab in labels:
                    add("error", "data", f"duplicate label {lab!r}", where)
                labels.add(lab)
                v = value(it.get("value"), where)
                if kind == "comparison" and v is not None and v < 0:
                    add("error", "data", "a comparison sets magnitudes side by side from zero: values must be >= 0 "
                                         "(a bar or column chart shows negative values)", where)
                if "highlight" in it and not isinstance(it["highlight"], bool):
                    add("error", "schema", "highlight must be true or false", where)
                need_source(it.get("source", dsrc), where, f"item {lab!r}")
                out.append({"label": lab, "value": v, "source": it.get("source", dsrc), "highlight": it.get("highlight") is True})
            data_out["items"] = out
        elif kind == "line":
            series = data.get("series")
            if not (isinstance(series, list) and SERIES[0] <= len(series) <= SERIES[1]):
                add("error", "data", f"a line chart needs {SERIES[0]}..{SERIES[1]} series", "data")
                series = []
            out, xs0 = [], None
            for i, s in enumerate(series):
                where = f"data.series[{i}]"
                if not isinstance(s, dict):
                    add("error", "data", "a series is an object", where)
                    continue
                for k in sorted(set(s) - {"label", "points", "source"}):
                    add("error", "schema", f"unknown series key {k!r}", where)
                lab = _text(s["label"], "label", where, add) if "label" in s else None
                if len(series) > 1 and lab is None:
                    add("error", "data", "with several series each needs a label", where)
                pts = s.get("points")
                if not (isinstance(pts, list) and POINTS[0] <= len(pts) <= POINTS[1]):
                    add("error", "data", f"a series needs {POINTS[0]}..{POINTS[1]} points", where)
                    pts = []
                ssrc = s.get("source", dsrc)
                po = []
                for j, p in enumerate(pts):
                    pw = f"{where}.points[{j}]"
                    if not isinstance(p, dict):
                        add("error", "data", "a point is an object", pw)
                        continue
                    for k in sorted(set(p) - {"x", "value", "source"}):
                        add("error", "schema", f"unknown point key {k!r}", pw)
                    x = _text(p.get("x"), "x", pw, add)
                    v = value(p.get("value"), pw)
                    need_source(p.get("source", ssrc), pw, f"point {x!r}")
                    po.append({"x": x, "value": v, "source": p.get("source", ssrc)})
                xs = [p["x"] for p in po]
                if len(set(xs)) != len(xs):
                    add("error", "data", "the x labels of a series must differ", where)
                if xs0 is None:
                    xs0 = xs
                elif xs != xs0:
                    add("error", "data", "every series must have the same x labels in the same order", where)
                out.append({"label": lab, "points": po})
            data_out["series"] = out
        else:                                   # counter
            v = value(data.get("value"), "data")
            f0 = value(data.get("from", 0), "data")
            need_source(dsrc, "data", "the counter's value")
            data_out.update({"value": v, "from": f0, "source": dsrc})
    for sid in sorted(set(sources) - used):
        add("warning", "unused_source", "this source is not used by any text or number", f"source {sid}")

    # ---- place (overlays)
    place = doc.get("place")
    place_out = None
    if display == "fullframe" or (display is None and DISPLAYS[kind] == ("fullframe",)):
        if place is not None:
            add("error", "schema", "place is for overlays (a full-frame graphic fills the safe area)", "place")
    else:
        place = {} if place is None else place
        if not isinstance(place, dict):
            add("error", "schema", "place must be an object", "place")
            place = {}
        for k in sorted(set(place) - {"anchor", "rect", "at"}):
            add("error", "schema", f"unknown place key {k!r}", "place")
        if "anchor" in place and "rect" in place:
            add("error", "schema", "place takes anchor or rect, not both", "place")
        anchor, rect, at = None, None, None
        if "rect" in place:
            if SA.check_rect(place["rect"], "place", add):
                rect = [float(v) for v in place["rect"]]
        else:
            a = place.get("anchor", DEFAULT_ANCHOR[kind])
            anchor = _anchor(a, lang)
            if anchor not in ANCHORS:
                add("error", "schema", f"anchor must be one of {', '.join(ANCHORS)} (or start / end / bottom-start / bottom-end / "
                                       "top-start / top-end, which follow the reading direction)", "place")
                anchor = None
        if kind == "callout":
            p = place.get("at")
            if not (isinstance(p, (list, tuple)) and len(p) == 2 and all(_num(v) for v in p)):
                add("error", "schema", "a callout needs place.at = [x, y], the frame point it points to", "place")
            elif not (0 <= p[0] <= SA.FRAME[0] and 0 <= p[1] < SA.BAND[1]):
                add("error", "outside_safe_area", f"place.at {list(p)} must be inside the frame and above the subtitle band", "place")
            else:
                at = [float(v) for v in p]
        elif "at" in place:
            add("error", "schema", "place.at is only for a callout", "place")
        place_out = {"anchor": anchor, "rect": rect, "at": at}

    # ---- animation
    anim = doc.get("animation", {})
    if not isinstance(anim, dict):
        add("error", "schema", "animation must be an object", "animation")
        anim = {}
    for k in sorted(set(anim) - {"in", "out"}):
        add("error", "schema", f"unknown animation key {k!r} (in, out)", "animation")
    anim_out = {}
    for side in ("in", "out"):
        a = anim.get(side, ANIM_DEFAULT)
        where = f"animation.{side}"
        if not isinstance(a, dict):
            add("error", "schema", "an animation is an object", where)
            a = ANIM_DEFAULT
        for k in sorted(set(a) - {"type", "frames", "direction"}):
            add("error", "schema", f"unknown key {k!r}", where)
        t = a.get("type", "fade")
        if t not in ANIM_TYPES:
            add("error", "schema", f"type must be one of {', '.join(ANIM_TYPES)}", where)
            t = "fade"
        n = 0 if t == "none" else a.get("frames", ANIM_DEFAULT["frames"])
        if not (_int(n) and 0 <= n <= ANIM_MAX):
            add("error", "schema", f"frames must be a whole number 0..{ANIM_MAX}", where)
            n = 0
        if t != "none" and n == 0:
            add("error", "schema", f"a {t} needs at least 1 frame (or type none)", where)
        d = a.get("direction")
        if t in ("wipe", "slide"):
            d = d if d is not None else ("left" if lang == "fa" else "right")
            if d not in DIRECTIONS:
                add("error", "schema", f"direction must be one of {', '.join(DIRECTIONS)}", where)
                d = None
        elif d is not None:
            add("error", "schema", f"direction is only for wipe / slide", where)
            d = None
        anim_out[side] = {"type": t, "frames": n, "direction": d}
    if clip_frames is not None:
        if not (_int(clip_frames) and clip_frames > 0):
            raise ValueError("clip_frames must be a positive whole number")
        if anim_out["in"]["frames"] + anim_out["out"]["frames"] >= clip_frames:
            add("error", "animation_too_long", f"enter {anim_out['in']['frames']} + exit {anim_out['out']['frames']} frames leave no "
                                               f"frame fully shown in a clip of {clip_frames} frames", "animation")

    graphic = {"schema": SPEC_SCHEMA, "id": gid, "mode": mode, "lang": lang, "kind": kind, "display": display, "style": style,
               "place": place_out, "content": text, "content_source": content.get("source"), "data": data_out,
               "sources": [sources[k] for k in sorted(sources)], "animation": anim_out,
               "draft_badge": mode == "draft" and bool(draft_marks)}
    return done(graphic)
