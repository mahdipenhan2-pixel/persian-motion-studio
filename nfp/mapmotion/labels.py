"""NFP Map Motion - M2f: label placement - the names of the scene's points, placed in SCREEN space (they keep their
size at every zoom) frame by frame, without overlapping each other, the markers or the drawn routes. Standard library.

Text size comes from a MEASUREMENT (tools/measure.py: the local Chromium with the local fonts, the same renderer and fonts that
draw the result), passed in as a labelmetrics document: {"items": [{"text", "size", "weight", "width", "ascent",
"descent"}]}. Without it a conservative estimate is used (0.62 em per character, ascent 1.0, descent 0.35 em) and QC says
so ("label_metrics_estimated": a warning in draft, an error in final).
scene.json "labels" (optional):  {"size": 22, "weight": 400 | 700, "halo": {"color": "#RRGGBB", "width": 3},
                                  "padding": 3, "offset": 6}
  size / padding / offset / halo width in screen pixels; the text colour is the style's "label" colour, the halo
  (an outline drawn under the text) is the style's background colour unless given.
Placement, deterministic and predictable (no search, no randomness):
  - points in plan order (earlier = higher priority); only points shown in that frame (animation opacity > 0) with a
    label to show (scene show.labels / the point's own "label" setting / a name from M1);
  - 8 candidate positions around the marker, in this order: E, W, NE, NW, SE, SW, N, S (E = to the right of the
    marker, vertically centred on it; N = centred above it; ...), each at `offset` px from the marker's box;
  - a candidate is taken if its box lies inside the screen (8 px margin) and touches no placed label, no marker (all
    shown points, both copies of a point on the seam, the routes' moving markers) and no drawn route segment;
  - stability: if the position a label had in the previous frame is still free, it keeps it (no jumping as the camera
    moves); otherwise the first free one in the order above;
  - none free: the label is not shown in that frame (QC "label_hidden" lists how many frames, never silent);
    a point whose marker is off the screen (the camera looks elsewhere) has no label there and is not counted.
Direction: rtl when the text's first strong character (Unicode bidi class R / AL) is right-to-left, else ltr (digits
are not strong: "۱۴۰۵" alone is ltr); the box is centred on its
candidate, so the drawing does not depend on how a renderer anchors rtl text. Labels change no geometry, timing or
camera value; they only read them.
"""
import math
import unicodedata

from . import camera as CAM

ORDER = ("E", "W", "NE", "NW", "SE", "SW", "N", "S")
SCREEN_MARGIN = 8.0
FONT_STACK = "Vazirmatn, Inter, sans-serif"
DEFAULTS = {"size": 22.0, "weight": 400, "halo_width": 3.0, "padding": 3.0, "offset": 6.0}
EST = {"width_em": 0.62, "ascent_em": 1.0, "descent_em": 0.35}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def direction(s):
    """'rtl' if the first STRONG character (Unicode bidi class R / AL: Persian, Arabic, Hebrew) is right-to-left, 'ltr'
    if it is L; digits (Persian or Latin: classes EN / AN) and punctuation are not strong - a text of digits only is
    'ltr'. The same rule as the Unicode bidi algorithm's paragraph direction (P2 / P3)."""
    for ch in s:
        b = unicodedata.bidirectional(ch)
        if b in ("R", "AL"):
            return "rtl"
        if b == "L":
            return "ltr"
    return "ltr"


def metric_key(text, size, weight):
    return (text, float(size), int(weight))


def marker_box(kind, X, Y, size):
    """Screen box (x0, y0, x1, y1) of a marker drawn by icons.marker at (X, Y)."""
    if kind == "pin":
        return (X - 0.32 * size, Y - 0.98 * size, X + 0.32 * size, Y)
    h = size / 2
    return (X - h, Y - h, X + h, Y + h)


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _seg_hits_box(p, q, b):
    """Does segment p-q touch box b (Liang-Barsky)?"""
    x0, y0, x1, y1 = b
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _candidate(pos, mb, w, h, off):
    cx, cy = (mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2
    if pos in ("E", "NE", "SE"):
        x0 = mb[2] + off
    elif pos in ("W", "NW", "SW"):
        x0 = mb[0] - off - w
    else:
        x0 = cx - w / 2
    if pos in ("N", "NE", "NW"):
        y0 = mb[1] - off - h
    elif pos in ("S", "SE", "SW"):
        y0 = mb[3] + off
    else:
        y0 = cy - h / 2
    return (x0, y0, x0 + w, y0 + h)


def resolve_labels(cfg, sp, plan, metrics, mode, add):
    """The labels block of a scene plan: style, the measured size of every label text, and the placement of every label
    in every frame of the window (plus the static map)."""
    st = dict(DEFAULTS, halo_color=sp["style"]["colors"]["background"])     # the halo is the map's own background colour
    if cfg is not None:
        if not isinstance(cfg, dict) or set(cfg) - {"size", "weight", "halo", "padding", "offset"}:
            add("error", "labels", "labels must be {size, weight, halo, padding, offset}", None)
            cfg = {}
        for k, lo, hi in (("size", 8, 96), ("padding", 0, 32), ("offset", 0, 64)):
            if k in cfg:
                if _num(cfg[k]) and lo <= cfg[k] <= hi:
                    st[k] = float(cfg[k])
                else:
                    add("error", "labels", f"labels.{k} must be a number {lo}..{hi}", None)
        if "weight" in cfg:
            if cfg["weight"] in (400, 700):
                st["weight"] = cfg["weight"]
            else:
                add("error", "labels", "labels.weight must be 400 or 700 (the local font files)", None)
        if "halo" in cfg:
            h = cfg["halo"]
            from .scene import COLOR_RE
            if not (isinstance(h, dict) and set(h) <= {"color", "width"} and (("color" not in h) or (isinstance(h["color"], str) and COLOR_RE.fullmatch(h["color"])))
                    and (("width" not in h) or (_num(h["width"]) and 0 <= h["width"] <= 16))):
                add("error", "labels", "labels.halo must be {color: #RRGGBB, width: 0..16}", None)
            else:
                st["halo_color"] = h.get("color", st["halo_color"]).lower()
                st["halo_width"] = float(h.get("width", st["halo_width"]))
    table = {}
    if metrics is not None:
        if not isinstance(metrics, dict) or metrics.get("schema") != "nfp.mapmotion.labelmetrics/1" or not isinstance(metrics.get("items"), list):
            add("error", "labels", "metrics must be a labelmetrics document (nfp.mapmotion.labelmetrics/1, from tools/measure.py)", None)
        else:
            for it in metrics["items"]:
                table[metric_key(it["text"], it["size"], it["weight"])] = it
    W, H = sp["frame"]["width"], sp["frame"]["height"]
    w0 = plan["window"]["start"]
    sizes, estimated = {}, []
    for p in sp["points"]:
        lab = p["label"]
        if not (p["show"] and lab["show"] and lab.get("display")):
            continue
        key = metric_key(lab["display"], st["size"], st["weight"])
        m = table.get(key)
        if m is None:
            n = len(lab["display"])
            m = {"width": EST["width_em"] * st["size"] * n, "ascent": EST["ascent_em"] * st["size"], "descent": EST["descent_em"] * st["size"]}
            estimated.append(p["id"])
        pad = st["padding"] + st["halo_width"] / 2
        sizes[p["id"]] = {"w": m["width"] + 2 * pad, "h": m["ascent"] + m["descent"] + 2 * pad, "ascent": m["ascent"], "pad": pad,
                          "text": lab["display"], "direction": direction(lab["display"]), "measured": p["id"] not in estimated}
    if estimated:
        add("error" if mode == "final" else "warning", "label_metrics_estimated",
            f"no measurement for the label(s) of {', '.join(estimated)}: their size is estimated (run tools/measure.py)", None)
    pts = {p["id"]: p for p in sp["points"]}
    mk_of = {p["id"]: p["marker"] for p in sp["points"]}

    def place(state, opac, routes_drawn, heads, prev):
        markers = []
        for p in sp["points"]:
            if opac(p["id"]) > 0 and p["show"] and p["marker"] != "none":
                for x in p["x"]:
                    X, Y = CAM.to_screen(state, sp["frame"], x, p["y"])
                    markers.append((p["id"], marker_box(p["marker"], X, Y, p["size"])))
        for (X, Y, s) in heads:
            markers.append((None, (X - s / 2, Y - s / 2, X + s / 2, Y + s / 2)))
        segs = []
        for path in routes_drawn:
            pts_s = [CAM.to_screen(state, sp["frame"], x, y) for x, y in path]
            segs.extend(zip(pts_s, pts_s[1:]))
        placed, out = [], []
        for p in sp["points"]:
            if p["id"] not in sizes or opac(p["id"]) <= 0:
                continue
            sz = sizes[p["id"]]
            own = [b for pid, b in markers if pid == p["id"]]
            mb = own[0] if own else (lambda X, Y: (X, Y, X, Y))(*CAM.to_screen(state, sp["frame"], p["x"][0], p["y"]))
            if not (mb[2] >= 0 and mb[0] <= W and mb[3] >= 0 and mb[1] <= H):
                out.append({"id": p["id"], "shown": False, "offscreen": True})     # the place itself is not on screen
                continue
            order = ([prev[p["id"]]] if prev.get(p["id"]) else []) + [o for o in ORDER if o != prev.get(p["id"])]
            chosen = None
            for pos in order:
                b = _candidate(pos, mb, sz["w"], sz["h"], st["offset"])
                if b[0] < SCREEN_MARGIN or b[1] < SCREEN_MARGIN or b[2] > W - SCREEN_MARGIN or b[3] > H - SCREEN_MARGIN:
                    continue
                if any(_overlap(b, q) for q in placed) or any(_overlap(b, mbx) for _, mbx in markers):
                    continue
                if any(_seg_hits_box(s0, s1, b) for s0, s1 in segs):
                    continue
                chosen = (pos, b)
                break
            if chosen is None:
                out.append({"id": p["id"], "shown": False})
                continue
            pos, b = chosen
            placed.append(b)
            out.append({"id": p["id"], "shown": True, "pos": pos, "box": [round(v, 3) for v in (b[0], b[1], b[2] - b[0], b[3] - b[1])],
                        "x": round((b[0] + b[2]) / 2, 3), "y": round(b[1] + sz["pad"] + sz["ascent"], 3), "opacity": opac(p["id"])})
        return out

    from .render import _prefix                       # the same cut of a route as the drawing (one definition)
    # the static map: every shown point, every route drawn, the route markers at their last stop
    static_routes = [[(v["x"], v["y"]) for v in pc] for r in sp["routes"] if r["show"] for pc in r["pieces"]]
    heads_static = []
    for r in sp["routes"]:
        mk = next(x["marker"] for x in sp["animation"]["routes"] if x["id"] == r["id"])
        if r["show"] and mk != "none":
            v = r["pieces"][-1][-1]
            heads_static.append((v["x"], v["y"], max(18.0, 5 * r["width"])))
    full = {"cx": W / 2, "cy": H / 2, "zoom": 1.0}
    static = place(full, lambda pid: 1.0 if pts[pid]["show"] else 0.0, static_routes,
                   [(*CAM.to_screen(full, sp["frame"], x, y), s) for x, y, s in heads_static], {})
    frames, prev, hidden = [], {}, {}
    for i, cf in enumerate(sp["camera"]["frames"]):
        an = sp["animation"]["frames"][i]
        state = {"cx": cf["cx"], "cy": cf["cy"], "zoom": cf["zoom"]}
        op = {x["id"]: x["opacity"] for x in an["points"]}
        drawn, heads = [], []
        for r, ra in zip(sp["routes"], an["routes"]):
            if not r["show"]:
                continue
            for pc, share in zip(r["pieces"], ra["pieces"]):
                q = _prefix(pc, share)
                if len(q) >= 2:
                    drawn.append(q)
            if ra["head"]:
                X, Y = CAM.to_screen(state, sp["frame"], ra["head"]["x"], ra["head"]["y"])
                heads.append((X, Y, max(18.0, 5 * r["width"])))
        res = place(state, lambda pid: op.get(pid, 0.0), drawn, heads, prev)
        for x in res:
            if x["shown"]:
                prev[x["id"]] = x["pos"]
            elif not x.get("offscreen"):
                hidden[x["id"]] = hidden.get(x["id"], 0) + 1
        frames.append({"frame": w0 + i, "labels": res})
    for pid, n in hidden.items():
        add("warning", "label_hidden", f"no free place for the label in {n} frame(s): not shown there", pid)
    return {"style": {"font_family": FONT_STACK, "size": st["size"], "weight": st["weight"], "color": sp["style"]["colors"]["label"],
                      "halo_color": st["halo_color"], "halo_width": st["halo_width"], "padding": st["padding"], "offset": st["offset"]},
            "texts": {pid: {"text": s["text"], "direction": s["direction"], "measured": s["measured"]} for pid, s in sizes.items()},
            "static": static, "frames": frames}
