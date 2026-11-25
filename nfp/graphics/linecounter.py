"""NFP Graphics - G7: layout of the line chart and the counter. Standard library; no measuring, no process: every text is
MEASURED (G2 tools) and broken with G2's rules, numbers are written by text.format_number (G2), the style is the preset
(G1), the chart type scale and source line follow G6.

  requests(spec, metrics=None) / layout(spec, metrics)   as datalayout (dispatched from textlayout)

LINE  (data.series: 1..4 series of the same 2..60 x labels; graphics.validate)
  Honesty: one linear vertical scale whose domain ALWAYS contains zero (a cut axis exaggerates a trend), extended to
  round tick values ("nice" steps 1 / 2 / 2.5 / 5 x 10^k, 4..6 ticks, labels by format_number); the plot is
  LINE_PLOT_H tall, less when the header / legend leave less room, never below LINE_PLOT_MIN; every point drawn at its
  exact value (y = plot top + (top tick - value) x px_per_unit); points are evenly spaced in data order (x labels are
  text, not a time axis - G1); a line is never smoothed. Only the x LABELS are thinned (every s-th, s the smallest that
  keeps them apart) - never the points. Zero / negative values: below the zero line, which is drawn stronger.
  Reading direction: Persian puts the first point on the right and the tick labels on the right; English the reverse.
  Series: the preset's accent, positive, text and muted colours, solid / solid / dashed / dotted (told apart without
  colour too); point markers when a series has <= 24 points; a legend (swatch + label, reading order, wrapped rows)
  when there are several series.
COUNTER  (data.value, data.from (default 0); content.title = what is counted, content.subtitle = a note)
  The number counts from `from` to `value` over the clip's ENTER frames (animation.in.frames - no other timing; type none
  = no counting); frame i of n shows from + (value - from) x (1 - (1 - i/n)^2), written with the data's format; from
  frame n on - and in a still drawing - exactly format_number(value). Every state's text is measured and the box is as
  wide as the widest of them, so the number stays inside its box on every frame.
"""
import math

from . import safearea as SA
from . import styles as ST
from . import text as TX
from .textlayout import (BOTTOM_GAP, EST, LAYOUT_SCHEMA, _anchor_xy, _est, _index, _key, break_lines, ff_rule_space, place_badge)

KINDS = ("line", "counter")
MAX_W = {"overlay": {"line": 900, "counter": 760}, "fullframe": {"line": 1400, "counter": 1200}}
LINE_PLOT_H = {"fullframe": 400, "overlay": 240}           # the plot's height: at most this, the room left if less ...
LINE_PLOT_MIN = {"fullframe": 240, "overlay": 160}         # ... but never below this (then chart_too_tall)
MARKERS_MAX, MARKER_R = 24, 5
SWATCH_W = 32
SERIES_STYLE = (("accent", None), ("positive", None), ("text", "14 8"), ("muted", "3 7"))
LINE_W = 4
X_LABEL_GAP = 14


def _roles(spec):
    st, f = spec["style"], spec["style"]["font"]

    def ov(typ, weight=None):                                  # the chart type scale (G6): the preset's overlay sizes
        size, w = ST.TYPE["overlay"][typ]
        return {"size": round(size * st["scale"], 2), "weight": weight or w, "family": f}

    def own(typ, weight=None):                                 # a counter is set like a card: its display's own scale
        t = st["type"][typ]
        return {"size": t["size"], "weight": weight or t["weight"], "family": f}
    if spec["kind"] == "line":
        return {"title": ov("title"), "subtitle": ov("subtitle"), "source": ov("source"), "tick": ov("label"),
                "xlabel": ov("label"), "legend": ov("label")}
    return {"label": own("subtitle"), "count": own("title", 700), "note": own("body"), "source": own("source")}


def _source_text(spec):
    if spec["kind"] == "line":
        refs = [p["source"] for s in spec["data"]["series"] for p in s["points"]]
    else:
        refs = [spec["data"]["source"]]
    ids = []
    for r in refs:
        if r and r not in ids:
            ids.append(r)
    srcs = {s["id"]: s for s in spec["sources"]}
    fa = spec["lang"] == "fa"
    parts = []
    for i in ids:
        s = srcs.get(i)
        if s:
            year = (s.get("date") or "")[:4]
            parts.append(s["publisher"] + ((("، " + year.translate(TX.FA_DIGITS)) if fa else (", " + year)) if year else ""))
    return TX.LABEL[spec["lang"]]["source"] + ("؛ " if fa else "; ").join(parts) if parts else None


def _width(spec):
    sp = spec["style"]["spacing"]
    if spec["display"] == "fullframe":
        return min(MAX_W["fullframe"][spec["kind"]], SA.ALLOWED[2])
    rect = (spec.get("place") or {}).get("rect")
    return (rect[2] if rect else MAX_W["overlay"][spec["kind"]]) - 2 * sp["padding"]


def nice_ticks(lo, hi):
    """Round tick values covering [lo, hi] (which contains 0), 4..6 of them -> (ticks, step, decimals)."""
    if hi - lo <= 0:
        return [0.0, 1.0], 1.0, 0
    raw = (hi - lo) / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-12)
    t0, t1 = math.floor(lo / step + 1e-9) * step, math.ceil(hi / step - 1e-9) * step
    n = int(round((t1 - t0) / step))
    ticks = [round(t0 + i * step, 10) for i in range(n + 1)]
    dec = 0 if step >= 1 else min(3, -math.floor(math.log10(step)) + (1 if round(step / 10 ** math.floor(math.log10(step)), 6) == 2.5 else 0))
    return ticks, step, dec


def _ticks(spec):
    vals = [p["value"] for s in spec["data"]["series"] for p in s["points"]]
    ticks, step, dec = nice_ticks(min(0.0, min(vals)), max(0.0, max(vals)))
    f = spec["data"]["format"]
    dec = max(dec, 0)
    return ticks, [TX.format_number(t, dec, f["digits"], spec["data"]["unit"]) for t in ticks]


def count_states(spec):
    """The counter's shown texts: (states [text], frames [state index of enter frame i, i = 0..n], final index)."""
    d, f = spec["data"], spec["data"]["format"]
    a = spec["animation"]["in"]
    n = 0 if a["type"] == "none" else a["frames"]
    fmt = lambda v: TX.format_number(v, f["decimals"], f["digits"], d["unit"])
    seq = [fmt(d["from"] + (d["value"] - d["from"]) * (1 - (1 - i / n) ** 2)) for i in range(n)] + [fmt(d["value"])]
    states, frames = [], []
    for t in seq:
        if t not in states:
            states.append(t)
        frames.append(states.index(t))
    return states, frames, frames[-1]


def _texts(spec):
    W, R = _width(spec), _roles(spec)
    c = spec["content"]
    out = []
    if spec["kind"] == "line":
        out += [(c[x], x, True, W) for x in ("title", "subtitle") if x in c]
        out += [(t, "tick", False, W) for t in _ticks(spec)[1]]
        out += [(p["x"], "xlabel", False, W) for p in spec["data"]["series"][0]["points"]]
        if len(spec["data"]["series"]) > 1:
            out += [(s["label"], "legend", False, W) for s in spec["data"]["series"]]
    else:
        out.append((c["title"], "label", True, W))
        if "subtitle" in c:
            out.append((c["subtitle"], "note", True, W))
        out += [(t, "count", False, W) for t in count_states(spec)[0]]
    s = _source_text(spec)
    if s:
        out.append((s, "source", True, W))
    return out, R


def requests(spec, metrics=None):
    idx, out = _index(metrics), set()
    texts, R = _texts(spec)
    for txt, role, breakable, maxw in texts:
        st = R[role]
        if not breakable:
            out.add(_key(txt, st))
            continue
        us = TX.units(txt)
        for u in us:
            out.add(_key(u, st))
        if metrics is None:
            continue
        for i in range(len(us)):
            w = 0.0
            for j in range(i, len(us)):
                m = idx.get(_key(us[j], st))
                w += (m["width"] if m else _est(us[j], st["size"])) + (EST[1] * st["size"] if j > i else 0)
                if w > maxw * 1.1:
                    break
                if j > i:
                    out.add(_key(" ".join(us[i:j + 1]), st))
    if spec.get("draft_badge"):
        b = spec["style"]["type"]["source"]
        out.add((TX.LABEL[spec["lang"]]["draft"], float(b["size"]), 700, spec["style"]["font"]))
    return sorted(out)


class _Ctx:
    """measuring / breaking / block helpers shared by the two layouts"""

    def __init__(self, spec, metrics, add):
        self.spec, self.idx, self.add, self.R = spec, _index(metrics), add, _roles(spec)
        self.estimated = set()
        self.lh_k = spec["style"]["line_height"]
        self.blocks = []

    def meas(self, text, role):
        s = self.R[role]
        m = self.idx.get(_key(text, s))
        if not m:
            self.estimated.add(text)
            return {"width": _est(text, s["size"]), "ascent": s["size"] * 0.95, "descent": s["size"] * 0.3}
        return m

    def lh(self, role, texts):
        ms = [self.meas(t, role) for t in texts]
        return max(self.R[role]["size"] * self.lh_k, max([m["ascent"] + m["descent"] for m in ms] or [0]))

    def breaks(self, text, role, maxw, maxlines):
        s = self.R[role]

        def probe(t):                    # a run tried by the breaking (maybe too long, never asked for): not "estimated"
            m = self.idx.get(_key(t, s))
            return m["width"] if m else _est(t, s["size"])
        got, err = break_lines(TX.units(text), maxw, maxlines, probe, True)
        if err:
            self.add("error", err[0], f"{role} {text!r}: {err[1]}", role)
            return None
        for t, _ in got:                 # only the lines drawn count
            self.meas(t, role)
        return got

    def block(self, name, role, rows, align, extra=None):
        """rows: [(text, width, x0, baseline, direction)] in frame px"""
        s = self.R[role]
        ms = [self.meas(t, role) for t, *_ in rows]
        b = {"role": name, "size": s["size"], "weight": s["weight"], "family": s["family"], "align": align,
             "ascent": round(max([m["ascent"] for m in ms] or [0]), 3), "descent": round(max([m["descent"] for m in ms] or [0]), 3),
             "line_height": round(self.lh(role, [r[0] for r in rows]), 3),
             "lines": [{"text": t, "width": round(w, 3), "x0": round(x0, 3), "x1": round(x0 + w, 3), "baseline": round(bl, 3), "direction": d}
                       for t, w, x0, bl, d in rows]}
        if extra:
            b.update(extra)
        self.blocks.append(b)

    def baseline(self, role, top, texts):
        """the baseline that centres texts' common font box in a line of this role starting at y = top"""
        ms = [self.meas(t, role) for t in texts]
        a, d = max(m["ascent"] for m in ms), max(m["descent"] for m in ms)
        return top + (self.lh(role, texts) - (a + d)) / 2 + a


def layout(spec, metrics=None):
    issues = []

    def add(level, code, msg, element=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("element", element), ("message", msg)) if v is not None})

    out = {"schema": LAYOUT_SCHEMA, "id": spec["id"], "kind": spec["kind"], "display": spec["display"], "lang": spec["lang"],
           "rect": None, "frame": None, "rule": None, "blocks": [], "badge": None, "bars": [], "axis": [], "grid": [], "lines": [],
           "swatches": [], "count": None, "scale": None, "measured": True, "issues": issues}

    def done():
        ne = sum(x["level"] == "error" for x in issues)
        out["status"] = "FAIL" if ne else "WARN" if any(x["level"] == "warning" for x in issues) else "OK"
        return out

    cx = _Ctx(spec, metrics, add)
    sp = spec["style"]["spacing"]
    gap, pad = sp["gap"], sp["padding"]
    rtl = spec["lang"] == "fa"
    pdir = "rtl" if rtl else "ltr"
    side = "right" if rtl else "left"
    W = _width(spec)
    src = _source_text(spec)
    foot = cx.breaks(src, "source", W, 2) if src else []
    if foot is None:
        return done()
    foot_h = (gap + len(foot) * cx.lh("source", [t for t, _ in foot])) if foot else 0.0
    if spec["display"] == "fullframe":
        room = SA.ALLOWED[3] - ff_rule_space(spec)
    else:
        rect0 = (spec.get("place") or {}).get("rect")
        room = (rect0[3] if rect0 else SA.ALLOWED[3] - BOTTOM_GAP) - 2 * pad
    # ---- body: (height, width, place(out, ox, oy, W) -> draws blocks / geometry at that origin)
    if spec["kind"] == "line":
        body = _line_body(spec, cx, W, add, room - foot_h)
    else:
        body = _counter_body(spec, cx, W, add)
    if body is None or any(x["level"] == "error" for x in issues):
        return done()
    body_h, body_w, place_body = body
    total_h = body_h + foot_h
    if spec["kind"] == "counter":
        W = max(body_w, max([w for _, w in foot] or [0]))            # a counter's box is as wide as its widest text
    if total_h > room + 1e-6:
        add("error", "chart_too_tall", f"the {spec['kind']} needs {total_h:.0f} px of height, {room:.0f} px fit", "data")
        return done()
    if cx.estimated:
        out["measured"] = False
        add("error" if spec["mode"] == "final" else "warning", "text_not_measured",
            f"{len(cx.estimated)} text runs were estimated, not measured (measure with graphics.tools.measure)")
        if spec["mode"] == "final":
            return done()
    if spec["display"] == "fullframe":
        top = ff_rule_space(spec)
        ox, oy = SA.ALLOWED[0] + (SA.ALLOWED[2] - W) / 2, SA.ALLOWED[1] + top + (SA.ALLOWED[3] - top - total_h) / 2
        rect = [ox, oy, W, total_h]
        out["frame"] = list(SA.ALLOWED)
    else:
        if rect0:
            rect = list(rect0)
            W = rect0[2] - 2 * pad if spec["kind"] == "counter" else W
        else:
            x, y_ = _anchor_xy(spec["place"]["anchor"], W + 2 * pad, total_h + 2 * pad)
            rect = [x, y_, W + 2 * pad, total_h + 2 * pad]
        ox, oy = rect[0] + pad, rect[1] + pad
    SA.check_rect(rect, "box", add)
    place_body(out, ox, oy, W)
    if foot:
        y = oy + body_h + gap
        L = cx.lh("source", [t for t, _ in foot])
        for t, w in foot:
            cx.block("source", "source", [(t, w, ox + W - w if rtl else ox, cx.baseline("source", y, [t]), pdir)], side)
            y += L
        if len(foot) > 1:                                              # one block, several lines (like G6)
            src_blocks = [b for b in cx.blocks if b["role"] == "source"]
            first = src_blocks[0]
            for b in src_blocks[1:]:
                first["lines"] += b["lines"]
                cx.blocks.remove(b)
    out["blocks"] = cx.blocks
    out["rect"] = [round(v, 3) for v in rect]
    out["inner"] = [round(ox, 3), round(oy, 3), round(W, 3), round(total_h, 3)]
    badge, est = place_badge(spec, out["rect"], cx.idx, add)
    out["badge"] = badge
    if est and out["measured"]:
        out["measured"] = False
        add("error" if spec["mode"] == "final" else "warning", "text_not_measured", "the draft badge was estimated, not measured")
    return done()


def _header(spec, cx, W):
    head = []
    for role in ("title", "subtitle"):
        if role in spec["content"]:
            got = cx.breaks(spec["content"][role], role, W, 2)
            if got is None:
                return None
            head.append((role, got))
    return head


def _line_body(spec, cx, W, add, room):
    gap = spec["style"]["spacing"]["gap"]
    rtl = spec["lang"] == "fa"
    pdir = "rtl" if rtl else "ltr"
    side = "right" if rtl else "left"
    colors = spec["style"]["colors"]
    head = _header(spec, cx, W)
    if head is None:
        return None
    series = spec["data"]["series"]
    n = len(series[0]["points"])
    ticks, tick_txt = _ticks(spec)
    tm = [cx.meas(t, "tick") for t in tick_txt]
    Tw = max(m["width"] for m in tm)
    xs_txt = [p["x"] for p in series[0]["points"]]
    xm = [cx.meas(t, "xlabel") for t in xs_txt]
    # legend: swatch + label items in reading order, wrapped into rows of width W
    leg_rows = []
    if len(series) > 1:
        lm = [cx.meas(s["label"], "legend") for s in series]
        row, used = [], 0.0
        for j, m in enumerate(lm):
            w = SWATCH_W + gap / 2 + m["width"]
            if w > W + 1e-6:
                add("error", "text_overflow", f"legend label {series[j]['label']!r} is wider than the chart", "legend")
                return None
            if row and used + gap + w > W + 1e-6:
                leg_rows.append(row)
                row, used = [], 0.0
            used += (gap if row else 0) + w
            row.append((j, w, m["width"]))
        leg_rows.append(row)
    plot_x0, plot_x1 = (0.0, W - Tw - gap) if rtl else (Tw + gap, W)          # tick labels on the reading-start side
    inset = MARKER_R + 2
    px0, px1 = plot_x0 + inset, plot_x1 - inset
    if px1 - px0 < 0.5 * W:
        add("error", "text_overflow", f"the tick labels ({Tw:.0f} px) leave the plot less than half the chart", "tick")
        return None
    step = (px1 - px0) / (n - 1)
    xpos = [(px1 - i * step) if rtl else (px0 + i * step) for i in range(n)]
    # x labels: thinned (never the points) - the smallest stride s whose labels keep X_LABEL_GAP apart
    def spans(s):
        shown = list(range(0, n, s))
        if (n - 1) not in shown:
            shown.append(n - 1)
        out = []
        for i in shown:
            w = xm[i]["width"]
            x0 = min(max(xpos[i] - w / 2, 0.0), W - w)
            out.append((i, x0, w))
        return out

    for stride in range(1, n + 1):
        shown = sorted(spans(stride), key=lambda r: r[1])
        if all(b[1] >= a[1] + a[2] + X_LABEL_GAP for a, b in zip(shown, shown[1:])):
            break
    else:                                    # even the first and last label alone collide
        add("error", "text_overflow", "the first and last x labels do not fit side by side", "xlabel")
        return None
    lo, hi = ticks[0], ticks[-1]
    head_h = sum(len(got) * cx.lh(role, [t for t, _ in got]) for role, got in head) + gap * len(head)
    leg_lh = cx.lh("legend", [s["label"] for s in series]) if leg_rows else 0.0
    leg_h = (len(leg_rows) * leg_lh + gap) if leg_rows else 0.0
    t_lh = cx.lh("tick", tick_txt)
    plot_top = head_h + leg_h + t_lh / 2                      # half a tick label of room above the top tick
    x_lh = cx.lh("xlabel", xs_txt)
    x_gap = t_lh / 2 + gap / 4                                 # the lowest tick label hangs half below the plot: x labels start under it
    PH = min(LINE_PLOT_H[spec["display"]], room - (plot_top + x_gap + x_lh))
    if PH < LINE_PLOT_MIN[spec["display"]] - 1e-6:
        add("error", "chart_too_tall", f"the line chart's plot would be {max(PH, 0):.0f} px tall (at least {LINE_PLOT_MIN[spec['display']]}): "
                                       "no subtitle, fewer legend rows or a full-frame graphic", "data")
        return None
    body_h = plot_top + PH + x_gap + x_lh

    def place(out, ox, oy, Wb):
        y = oy
        for role, got in head:
            L = cx.lh(role, [t for t, _ in got])
            rows = []
            for t, w in got:
                rows.append((t, w, ox + Wb - w if rtl else ox, cx.baseline(role, y, [t]), TX.direction(spec["content"][role], pdir)))
                y += L
            cx.block(role, role, rows, side)
            y += gap
        for r_i, row in enumerate(leg_rows):
            ry = oy + head_h + r_i * leg_lh
            x = ox + Wb if rtl else ox
            for j, w, tw in row:
                sw0 = (x - SWATCH_W) if rtl else x
                color, dash = SERIES_STYLE[j]
                yb = cx.baseline("legend", ry, [series[j]["label"]])
                mid = ry + leg_lh / 2
                out["swatches"].append({"series": j, "x0": round(sw0, 3), "x1": round(sw0 + SWATCH_W, 3), "y": round(mid, 3),
                                        "stroke": colors[color], "dash": dash})
                tx0 = (sw0 - gap / 2 - tw) if rtl else (sw0 + SWATCH_W + gap / 2)
                cx.block(f"legend-{j}", "legend", [(series[j]["label"], tw, tx0, yb, TX.direction(series[j]["label"], pdir))], side, {"series": j})
                x = (tx0 - gap) if rtl else (tx0 + tw + gap)
        top = oy + plot_top
        k = PH / (hi - lo)
        yv = lambda v: top + (hi - v) * k
        for ti, (t, txt, m) in enumerate(zip(ticks, tick_txt, tm)):
            y = yv(t)
            tx0 = (ox + Wb - m["width"]) if rtl else (ox + Tw - m["width"])          # flush against the plot's side
            a_, d_ = m["ascent"], m["descent"]
            cx.block(f"tick-{ti}", "tick", [(txt, m["width"], tx0, y + (a_ - d_) / 2, pdir)], side, {"value": t})
            out["grid"].append({"y": round(y, 3), "x0": round(ox + plot_x0, 3), "x1": round(ox + plot_x1, 3), "zero": abs(t) < 1e-12})
        for j, s in enumerate(series):
            color, dash = SERIES_STYLE[j]
            pts = [[round(ox + x, 3), round(yv(p["value"]), 3)] for x, p in zip(xpos, s["points"])]
            out["lines"].append({"series": j, "points": pts, "stroke": colors[color], "dash": dash, "markers": n <= MARKERS_MAX})
        yt = top + PH + x_gap
        for i, x0, w in shown:
            cx.block(f"xlabel-{i}", "xlabel", [(xs_txt[i], w, ox + x0, cx.baseline("xlabel", yt, [xs_txt[i]]), TX.direction(xs_txt[i], pdir))],
                     "center", {"point": i})
        out["scale"] = {"axis": "y", "zero": round(yv(0.0), 3), "px_per_unit": k, "domain": [lo, hi]}

    return body_h, W, place


def _counter_body(spec, cx, W, add):
    gap = spec["style"]["spacing"]["gap"]
    rtl = spec["lang"] == "fa"
    pdir = "rtl" if rtl else "ltr"
    ff = spec["display"] == "fullframe"
    align = "center" if ff else ("right" if rtl else "left")
    c = spec["content"]
    lab = cx.breaks(c["title"], "label", W, 2)
    note = cx.breaks(c["subtitle"], "note", W, 2) if "subtitle" in c else []
    if lab is None or note is None:
        return None
    states, frames, final = count_states(spec)
    sm = [cx.meas(t, "count") for t in states]
    cw = max(m["width"] for m in sm)
    if cw > W + 1e-6:
        add("error", "text_overflow", f"the counter's number {states[sm.index(max(sm, key=lambda m: m['width']))]!r} ({cw:.0f} px) is wider than "
                                      f"its box ({W:.0f} px)", "count")
        return None
    lab_lh, cnt_lh = cx.lh("label", [t for t, _ in lab]), cx.lh("count", states)
    note_lh = cx.lh("note", [t for t, _ in note]) if note else 0.0
    body_h = len(lab) * lab_lh + gap / 2 + cnt_lh + ((gap / 2 + len(note) * note_lh) if note else 0.0)
    body_w = max([cw] + [w for _, w in lab] + [w for _, w in note])

    def x_of(ox, Wb, w):
        return ox + (Wb - w) / 2 if align == "center" else (ox + Wb - w if rtl else ox)

    def place(out, ox, oy, Wb):
        y = oy
        rows = []
        for t, w in lab:
            rows.append((t, w, x_of(ox, Wb, w), cx.baseline("label", y, [t]), TX.direction(c["title"], pdir)))
            y += lab_lh
        cx.block("label", "label", rows, align)
        y += gap / 2
        bl = cx.baseline("count", y, states)
        s = cx.R["count"]
        out["count"] = {"states": [{"text": t, "width": round(m["width"], 3), "x0": round(x_of(ox, Wb, m["width"]), 3),
                                    "x1": round(x_of(ox, Wb, m["width"]) + m["width"], 3), "baseline": round(bl, 3), "direction": pdir}
                                   for t, m in zip(states, sm)],
                        "frames": frames, "final": final, "size": s["size"], "weight": s["weight"], "family": s["family"],
                        "ascent": round(max(m["ascent"] for m in sm), 3), "descent": round(max(m["descent"] for m in sm), 3)}
        y += cnt_lh
        if note:
            y += gap / 2
            rows = []
            for t, w in note:
                rows.append((t, w, x_of(ox, Wb, w), cx.baseline("note", y, [t]), TX.direction(c["subtitle"], pdir)))
                y += note_lh
            cx.block("note", "note", rows, align)

    return body_h, body_w, place
