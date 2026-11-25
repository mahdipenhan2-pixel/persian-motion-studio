"""NFP Graphics - G6: layout of the data kinds comparison, bar and column. Standard library; no measuring, no process:
every text (title, subtitle, category labels, value labels, the source line, the draft badge) is MEASURED (G2 tools) and
set in the preset's overlay type scale (both displays: see _roles), and
broken with G2's rules; numbers are written by text.format_number (G2: Persian / English digits, separators, unit).

  requests(spec, metrics=None) -> the texts to measure (two rounds, like textlayout.requests)
  layout(spec, metrics)        -> nfp.graphics.layout/1 (as textlayout.layout) + "bars": [{item, rect, fill}],
                                  "axis": [[x1, y1, x2, y2]], "scale": {"zero", "px_per_unit"}

Honesty (a chart never changes or hides data):
  - one linear scale for all items, always from ZERO (no cut axis, no log scale); bar length / column height =
    |value| x px_per_unit exactly; a negative value goes the other way from the zero line (bar / column; a comparison
    takes only values >= 0 - graphics.validate);
  - every item is drawn, in the document's order, with its own label and its value exactly as formatted from the data
    (format.decimals, digits, unit); a value that would SHOW as zero but is not zero is a warning (rounded_to_zero);
  - nothing is shrunk to fit: a label wider than its place, a value wider than its column, or a chart taller than the
    safe area is an error (text_overflow / chart_too_tall) naming what does not fit.
Reading direction: Persian charts grow from the right (bar labels on the right, positive bars leftwards, the first
column on the right), English from the left. Categories are read top to bottom (bar, comparison).

Geometry (frame px; W = the chart's inner width: overlay = MAX_W - 2 padding (or the explicit rect's), full frame =
MAX_W; header = title (<= 2 lines) + subtitle (<= 2 lines); footer = the source line "Source: publisher, year; ..." of
the items' sources (<= 2 lines)):
  bar        rows of [label | bar ... value]; label column = the widest label (<= 40 % of W); room for the value label
             at the bar's outer end (both ends when there are negative values); row = the label / value line height
             (12 bars + title + subtitle fit a full frame); bar thickness 55 % of the row; a vertical zero line
  column     W split in n equal slots; column width 60 % of a slot (<= 140 px); category labels under the plot, centred
             in their slot (<= 2 lines); the value label above a column (below a negative one); plot height
             COL_PLOT_H; a horizontal zero line
  comparison 2..4 blocks: label (subtitle type) above a bar + its value in the number type at the bar's end
Colours (the style's): bars accent; when some items are highlighted, those accent and the others muted; the zero line muted.
"""
from . import safearea as SA
from . import styles as ST
from . import text as TX
from .textlayout import (BOTTOM_GAP, EST, LAYOUT_SCHEMA, _anchor_xy, _est, _index, _key, break_lines, ff_rule_space, place_badge)

DATA_KINDS = ("comparison", "bar", "column")
MAX_W = {"overlay": {"comparison": 760, "bar": 900, "column": 900}, "fullframe": {"comparison": 1200, "bar": 1400, "column": 1400}}
COL_PLOT_H = {"fullframe": 420, "overlay": 260}
LABEL_COL_MAX = 0.40
BAR_FILL = 0.55
COL_FILL, COL_MAX_W = 0.60, 140
MIN_PLOT = 0.25          # bars need at least a quarter of the chart width


def _roles(spec):
    """A chart's text uses the preset's OVERLAY type scale in both displays (x the style's scale): the full-frame scale
    (an 88 px title) is for title cards - with it a 12-bar chart would not fit the safe area."""
    st = spec["style"]
    f = st["font"]

    def r(typ, weight=None):
        size, w = ST.TYPE["overlay"][typ]
        return {"size": round(size * st["scale"], 2), "weight": weight or w, "family": f}
    return {"title": r("title"), "subtitle": r("subtitle"), "source": r("source"), "label": r("label"),
            "value": r("number", 700) if spec["kind"] == "comparison" else r("label", 700),
            "clabel": r("subtitle") if spec["kind"] == "comparison" else r("label")}


def _source_text(spec):
    ids = []
    for it in spec["data"]["items"]:
        if it["source"] and it["source"] not in ids:
            ids.append(it["source"])
    srcs = {s["id"]: s for s in spec["sources"]}
    lang = spec["lang"]
    parts = []
    for i in ids:
        s = srcs.get(i)
        if not s:
            continue
        year = (s.get("date") or "")[:4]
        if lang == "fa":
            parts.append(s["publisher"] + ("، " + year.translate(TX.FA_DIGITS) if year else ""))
        else:
            parts.append(s["publisher"] + (", " + year if year else ""))
    return TX.LABEL[lang]["source"] + ("؛ " if lang == "fa" else "; ").join(parts) if parts else None


def _value_text(spec, v):
    f = spec["data"]["format"]
    return TX.format_number(v, f["decimals"], f["digits"], spec["data"]["unit"])


def _width(spec):
    """Inner chart width W."""
    sp = spec["style"]["spacing"]
    if spec["display"] == "fullframe":
        return min(MAX_W["fullframe"][spec["kind"]], SA.ALLOWED[2])
    rect = (spec.get("place") or {}).get("rect")
    return (rect[2] if rect else MAX_W["overlay"][spec["kind"]]) - 2 * sp["padding"]


def _texts(spec):
    """[(text, role, breakable, max width)] - every text of the chart."""
    W, R = _width(spec), _roles(spec)
    c, k, n = spec["content"], spec["kind"], len(spec["data"]["items"])
    out = [(c[x], x, True, W) for x in ("title", "subtitle") if x in c]
    for it in spec["data"]["items"]:
        if k == "column":
            out.append((it["label"], "clabel", True, W / n * 0.95))
        elif k == "comparison":
            out.append((it["label"], "clabel", True, W))
        else:
            out.append((it["label"], "clabel", False, W))
        out.append((_value_text(spec, it["value"]), "value", False, W))
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
        b = spec["style"]["type"]["source"]                     # the badge: the display's own source size (textlayout)
        out.add((TX.LABEL[spec["lang"]]["draft"], float(b["size"]), 700, spec["style"]["font"]))
    return sorted(out)


def layout(spec, metrics=None):
    issues = []

    def add(level, code, msg, element=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("element", element), ("message", msg)) if v is not None})

    out = {"schema": LAYOUT_SCHEMA, "id": spec["id"], "kind": spec["kind"], "display": spec["display"], "lang": spec["lang"],
           "rect": None, "frame": None, "rule": None, "blocks": [], "badge": None, "bars": [], "axis": [], "scale": None,
           "measured": True, "issues": issues}

    def done():
        ne = sum(x["level"] == "error" for x in issues)
        out["status"] = "FAIL" if ne else "WARN" if any(x["level"] == "warning" for x in issues) else "OK"
        return out

    idx = _index(metrics)
    estimated = set()
    R = _roles(spec)
    sp, st = spec["style"]["spacing"], spec["style"]
    lh_k = st["line_height"]
    rtl = spec["lang"] == "fa"
    side = "right" if rtl else "left"
    W = _width(spec)
    kind, items = spec["kind"], spec["data"]["items"]
    pdir = "rtl" if rtl else "ltr"

    def meas(text, role):
        s = R[role]
        m = idx.get(_key(text, s))
        if not m:
            estimated.add(text)
            return {"width": _est(text, s["size"]), "ascent": s["size"] * 0.95, "descent": s["size"] * 0.3}
        return m

    def lh(role, ms):
        s = R[role]
        return max(s["size"] * lh_k, max([m["ascent"] + m["descent"] for m in ms] or [0]))

    def breaks(text, role, maxw, maxlines, balanced=True):
        s = R[role]

        def probe(t):                    # a run tried by the breaking (maybe too long, never asked for): not "estimated"
            m = idx.get(_key(t, s))
            return m["width"] if m else _est(t, s["size"])
        got, err = break_lines(TX.units(text), maxw, maxlines, probe, balanced)
        if err:
            add("error", err[0], f"{role} {text!r}: {err[1]}", role)
            return None
        for t, _ in got:                 # only the lines drawn count
            meas(t, role)
        return got

    blocks = []

    def block(name, role, rows, align, extra=None):
        """name: the block's role in the layout (title / label-<i> / value-<i> / source); role: its style;
        rows: [(text, width, x0, baseline, direction)]"""
        s = R[role]
        ms = [meas(t, role) for t, *_ in rows]
        b = {"role": name, "size": s["size"], "weight": s["weight"], "family": s["family"], "align": align,
             "ascent": round(max([m["ascent"] for m in ms] or [0]), 3), "descent": round(max([m["descent"] for m in ms] or [0]), 3),
             "line_height": round(lh(role, ms), 3),
             "lines": [{"text": t, "width": round(w, 3), "x0": round(x0, 3), "x1": round(x0 + w, 3), "baseline": round(bl, 3), "direction": d}
                       for t, w, x0, bl, d in rows]}
        if extra:
            b.update(extra)
        blocks.append(b)

    # ---- values: exactly the data, formatted; warn when a non-zero value shows as zero
    vals = [it["value"] for it in items]
    vtxt = [_value_text(spec, v) for v in vals]
    zero_txt = _value_text(spec, 0)
    for it, v, t in zip(items, vals, vtxt):
        if v != 0 and t.replace("−", "") == zero_txt:
            add("warning", "rounded_to_zero", f"{it['label']!r} = {v!r} is shown as {t!r} with {spec['data']['format']['decimals']} decimals", "data")

    # ---- header (title, subtitle) and footer (source): broken like text at width W
    head = []
    for role in ("title", "subtitle"):
        if role in spec["content"]:
            got = breaks(spec["content"][role], role, W, 2)
            if got is not None:
                head.append((role, got))
    src = _source_text(spec)
    foot = breaks(src, "source", W, 2) if src else []
    if any(x["level"] == "error" for x in issues):
        return done()

    # ---- the chart body, relative to (0, 0) = the body's top-left; width W
    bars, axis, labels = [], [], []          # labels: (role, item index, rows) with rows in body coordinates
    hi = any(it["highlight"] for it in items)
    fill = lambda it: st["colors"]["accent"] if (it["highlight"] or not hi) else st["colors"]["muted"]
    gap = sp["gap"]
    vm = [meas(t, "value") for t in vtxt]
    v_lh = lh("value", vm)
    v_asc, v_desc = max(m["ascent"] for m in vm), max(m["descent"] for m in vm)
    pos, neg = max(0.0, max(vals)), max(0.0, -min(vals))
    scale = None
    if kind in ("bar", "comparison"):
        if kind == "bar":
            lm = [meas(it["label"], "clabel") for it in items]
            Lw = max(m["width"] for m in lm)
            if Lw > LABEL_COL_MAX * W + 1e-6:
                w_it = items[max(range(len(items)), key=lambda i: lm[i]["width"])]["label"]
                add("error", "text_overflow", f"bar label {w_it!r} is {Lw:.0f} px, more than {LABEL_COL_MAX:.0%} of the chart ({LABEL_COL_MAX * W:.0f} px)", "label")
                return done()
            l_asc, l_desc = max(m["ascent"] for m in lm), max(m["descent"] for m in lm)
            row = max(lh("clabel", lm), v_lh)              # the faces' own line height (~1.57 em for Vazirmatn) spaces the rows
            plot0, plot1 = (0.0, W - Lw - gap) if rtl else (Lw + gap, W)
        else:
            Lw, row = 0.0, None
            plot0, plot1 = 0.0, W
        Vw = max(m["width"] for m in vm)
        reserve_pos = Vw + gap
        reserve_neg = (Vw + gap) if neg > 0 else 0.0
        P = (plot1 - plot0) - reserve_pos - reserve_neg
        if P < MIN_PLOT * W:
            add("error", "text_overflow", f"the value labels ({Vw:.0f} px) leave the bars {max(P, 0):.0f} px of the {W:.0f} px chart "
                                          f"(at least {MIN_PLOT:.0%})", "value")
            return done()
        k = P / (pos + neg) if pos + neg > 0 else 0.0
        # positive bars grow in the reading direction: rightwards (en) / leftwards (fa)
        zero = (plot1 - reserve_neg - neg * k) if rtl else (plot0 + reserve_neg + neg * k)
        scale = {"zero": zero, "px_per_unit": k}
        y = 0.0
        for i, (it, v, t, m) in enumerate(zip(items, vals, vtxt, vm)):
            if kind == "comparison":
                got = breaks(it["label"], "clabel", W, 2)
                if got is None:
                    return done()
                cm = [meas(x, "clabel") for x, _ in got]
                clh = lh("clabel", cm)
                rows = []
                for j, (x, w) in enumerate(got):
                    x0 = W - w if rtl else 0.0
                    rows.append((x, w, x0, y + j * clh + (clh - (cm[j]["ascent"] + cm[j]["descent"])) / 2 + cm[j]["ascent"],
                                 TX.direction(it["label"], pdir)))
                labels.append(("clabel", i, rows))
                y += len(got) * clh + gap / 4
                rowh = v_lh
            else:
                rowh = row
                lw = lm[i]["width"]
                x0 = (W - Lw) if rtl else (Lw - lw)                    # labels on the reading-start side, flush against the bars
                bl = y + rowh / 2 + (l_asc - l_desc) / 2
                labels.append(("clabel", i, [(it["label"], lw, x0, bl, TX.direction(it["label"], pdir))]))
            thick = rowh * BAR_FILL
            L = abs(v) * k
            outward = (v >= 0) != rtl                                   # does the bar grow rightwards?
            bx = zero if outward else zero - L
            bars.append({"item": i, "rect": [bx, y + (rowh - thick) / 2, L, thick], "fill": fill(it)})
            vx0 = (zero + L + gap) if outward else (zero - L - gap - m["width"])
            labels.append(("value", i, [(t, m["width"], vx0, y + rowh / 2 + (v_asc - v_desc) / 2, pdir)]))
            y += rowh + (gap if kind == "comparison" else 0)
        if kind == "comparison":
            y -= gap
        axis.append([zero, 0.0, zero, y])
        body_h = y
    else:                                                               # column
        n = len(items)
        slot = W / n
        cw = min(slot * COL_FILL, COL_MAX_W)
        over = [(it["label"], t, m["width"]) for it, t, m in zip(items, vtxt, vm) if m["width"] > slot * 0.98]
        if over:
            add("error", "text_overflow", f"value {over[0][1]!r} ({over[0][2]:.0f} px) is wider than its column's place ({slot * 0.98:.0f} px): "
                                          "fewer columns, fewer decimals or a bar chart", "value")
            return done()
        H = COL_PLOT_H[spec["display"]]
        top_res = v_lh if pos > 0 or neg == 0 else 0.0
        bot_res = v_lh if neg > 0 else 0.0
        avail = H - top_res - bot_res
        k = avail / (pos + neg) if pos + neg > 0 else 0.0
        zero = top_res + pos * k
        scale = {"zero": zero, "px_per_unit": k}
        cat_rows = []
        for i, (it, v, t, m) in enumerate(zip(items, vals, vtxt, vm)):
            si = (n - 1 - i) if rtl else i                               # the first item on the reading-start side
            cx = slot * si + slot / 2
            L = abs(v) * k
            y0 = zero - L if v >= 0 else zero
            bars.append({"item": i, "rect": [cx - cw / 2, y0, cw, L], "fill": fill(it)})
            bl = (zero - L - gap / 4 - v_desc) if v >= 0 else (zero + L + gap / 4 + v_asc)
            labels.append(("value", i, [(t, m["width"], cx - m["width"] / 2, bl, pdir)]))
            got = breaks(it["label"], "clabel", slot * 0.95, 2)
            if got is None:
                return done()
            cat_rows.append((i, cx, got))
        axis.append([0.0, zero, W, zero])
        cm_all = [meas(x, "clabel") for _, _, got in cat_rows for x, _ in got]
        clh = lh("clabel", cm_all)
        c_asc, c_desc = max(m["ascent"] for m in cm_all), max(m["descent"] for m in cm_all)
        y_cat = H + gap / 2
        for i, cx, got in cat_rows:
            rows = [(x, w, cx - w / 2, y_cat + j * clh + (clh - (c_asc + c_desc)) / 2 + c_asc, TX.direction(items[i]["label"], pdir))
                    for j, (x, w) in enumerate(got)]
            labels.append(("clabel", i, rows))
        body_h = y_cat + max(len(g) for _, _, g in cat_rows) * clh

    # ---- stack: header, body, footer; place the box
    hm = [(role, got, [meas(t, role) for t, _ in got]) for role, got in head]
    head_h = sum(len(got) * lh(role, ms) for role, got, ms in hm) + gap * len(hm)
    fm = [meas(t, "source") for t, _ in foot]
    foot_h = (gap + len(foot) * lh("source", fm)) if foot else 0.0
    total_h = head_h + body_h + foot_h
    pad = sp["padding"]
    if spec["display"] == "fullframe":
        room = SA.ALLOWED[3] - ff_rule_space(spec)                     # the accent rule above the chart
    else:
        rect0 = (spec.get("place") or {}).get("rect")
        room = (rect0[3] if rect0 else SA.ALLOWED[3] - BOTTOM_GAP) - 2 * pad
    if total_h > room + 1e-6:
        add("error", "chart_too_tall", f"the chart needs {total_h:.0f} px of height, {room:.0f} px fit "
                                        f"({len(items)} items): fewer items, no subtitle, or a full-frame graphic", "data")
        return done()
    if estimated:
        out["measured"] = False
        add("error" if spec["mode"] == "final" else "warning", "text_not_measured",
            f"{len(estimated)} text runs were estimated, not measured (measure with graphics.tools.measure)")
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
        else:
            x, y_ = _anchor_xy(spec["place"]["anchor"], W + 2 * pad, total_h + 2 * pad)
            rect = [x, y_, W + 2 * pad, total_h + 2 * pad]
        ox, oy = rect[0] + pad, rect[1] + pad
    SA.check_rect(rect, "box", add)
    # header blocks
    y = oy
    for role, got, ms in hm:
        L_h = lh(role, ms)
        a, d = max(m["ascent"] for m in ms), max(m["descent"] for m in ms)
        rows = []
        for t, w in got:
            x0 = ox + W - w if rtl else ox
            rows.append((t, w, x0, y + (L_h - (a + d)) / 2 + a, TX.direction(spec["content"][role], pdir)))
            y += L_h
        block(role, role, rows, side)
        y += gap
    by = y
    for role, i, rows in labels:
        block(f"value-{i}" if role == "value" else f"label-{i}", role,
              [(t, w, ox + x0, by + bl, d) for t, w, x0, bl, d in rows],
              "center" if kind == "column" else side, {"item": i})
    out["bars"] = [{"item": x["item"], "rect": [round(ox + x["rect"][0], 3), round(by + x["rect"][1], 3), round(x["rect"][2], 3),
                                                  round(x["rect"][3], 3)], "fill": x["fill"]} for x in bars]
    out["axis"] = [[round(ox + a[0], 3), round(by + a[1], 3), round(ox + a[2], 3), round(by + a[3], 3)] for a in axis]
    out["scale"] = {"zero": round((ox if kind != "column" else by) + scale["zero"], 3), "px_per_unit": scale["px_per_unit"],
                    "axis": "x" if kind != "column" else "y"}
    if foot:
        y = by + body_h + gap
        L_h = lh("source", fm)
        a, d = max(m["ascent"] for m in fm), max(m["descent"] for m in fm)
        rows = []
        for t, w in foot:
            rows.append((t, w, ox + W - w if rtl else ox, y + (L_h - (a + d)) / 2 + a, pdir))
            y += L_h
        block("source", "source", rows, side)
    out["blocks"] = blocks
    out["rect"] = [round(v, 3) for v in rect]
    out["inner"] = [round(ox, 3), round(oy, 3), round(W, 3), round(total_h, 3)]
    badge, est = place_badge(spec, out["rect"], idx, add)
    out["badge"] = badge
    if est and out["measured"]:
        out["measured"] = False
        add("error" if spec["mode"] == "final" else "warning", "text_not_measured", "the draft badge was estimated, not measured")
    return done()
