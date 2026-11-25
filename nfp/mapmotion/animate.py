"""NFP Map Motion - M2d: animation data - routes drawn over time with a moving marker, points and areas appearing and
disappearing - one state per video frame of the plan's window. Standard library. Data only: nothing is drawn here.

Timing is M1's (unchanged): a route is drawn from its start frame to its end frame and reaches stop k at
plan["routes"][..]["stop_frames"][k] (in proportion to great-circle distance). Inside each leg the drawn distance moves
with the leg's ease (linear: constant speed along the leg; in-out: slow off a stop and into the next). After its end
frame the route stays fully drawn until the window ends; before its start frame nothing of it is drawn.
Distances are the geometry's (M2a) s_m; positions are the geometry's pieces, in plan pixels (the camera, M2c, maps them
to the screen). For every frame and route:
  s_m       drawn distance from the first stop (metres), 0 .. length_m, never decreasing
  fraction  s_m / length_m (1 for a route of length 0 once started)
  pieces    per piece of the drawn route, the drawn share of its PIXEL length (0..1): what a renderer uses as
            stroke-dashoffset (pathLength = 1); a piece on the far side of a seam crossing starts when the head gets there
  head      the tip of the line: {x, y, heading_deg, piece} (heading: screen direction of travel, degrees, 0 = east,
            90 = south / down, as SVG rotate()) - or null when the route has no marker ("none") or is not being drawn
            yet. When the tip is on the seam (both edges), it is placed on the piece the route goes on with.
Points and areas: opacity per frame, 1 inside [start, end) and 0 outside; "fade" ramps linearly over fade_frames
after start and before end (a cut otherwise). Hidden elements (show false in the scene) have opacity 0 throughout.

scene.json "animation" (optional, every field optional):
  {"defaults": {"ease": "linear", "marker": "none", "appear": "cut", "fade_frames": 0},
   "routes": {"r1": {"ease": "in-out", "marker": "plane"}},
   "points": {"p1": {"appear": "fade", "fade_frames": 12}},
   "areas":  {"a1": {"appear": "fade", "fade_frames": 20}}}
marker: plane | ship | dot | none (the drawn shape is the renderer's); appear: cut | fade; fade_frames: whole frames
0..300, at most half the element's own duration.
"""
import math

from .camera import ease as _ease

ROUTE_EASES = ("linear", "in-out")
ROUTE_MARKERS = ("plane", "ship", "dot", "none")
APPEARS = ("cut", "fade")
MAX_FADE = 300


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _drawn_distance(route, f, ez):
    """Drawn distance (m) at video frame f: piecewise over the legs, M1's stop frames, the ease inside each leg."""
    sf = route["stop_frames"]
    cum = route["_cum"]
    if f < route["start"]:
        return 0.0
    if f >= sf[-1]:
        return cum[-1]
    for k in range(len(sf) - 1):
        a, b = sf[k], sf[k + 1]
        if a <= f < b:
            return cum[k] + (cum[k + 1] - cum[k]) * _ease(ez, (f - a) / (b - a))
    return cum[-1]


def _piece_state(pc, s):
    """(drawn share of the piece's pixel length, head (x, y, heading) or None if s is outside the piece)."""
    lens = [math.hypot(w["x"] - v["x"], w["y"] - v["y"]) for v, w in zip(pc, pc[1:])]
    total = sum(lens)
    s0, s1 = pc[0]["s_m"], pc[-1]["s_m"]
    if s <= s0:
        return 0.0, None
    if s >= s1:
        return 1.0, None
    run = 0.0
    for i, (v, w) in enumerate(zip(pc, pc[1:])):
        if v["s_m"] <= s <= w["s_m"]:
            t = 0.0 if w["s_m"] == v["s_m"] else (s - v["s_m"]) / (w["s_m"] - v["s_m"])
            x, y = v["x"] + (w["x"] - v["x"]) * t, v["y"] + (w["y"] - v["y"]) * t
            share = 1.0 if total == 0 else (run + lens[i] * t) / total
            return share, (x, y, _heading(pc, i))
        run += lens[i]
    return 1.0, None


def _heading(pc, i):
    """Direction of segment i of a piece (screen degrees, atan2(dy, dx)); a zero-length segment takes its neighbour's."""
    order = [i] + [j for d in range(1, len(pc)) for j in (i + d, i - d) if 0 <= j < len(pc) - 1]
    for j in order:
        dx, dy = pc[j + 1]["x"] - pc[j]["x"], pc[j + 1]["y"] - pc[j]["y"]
        if dx or dy:
            return math.degrees(math.atan2(dy, dx))
    return 0.0


def resolve_animation(cfg, plan, scene_plan, add):
    """The animation block of a scene plan (scene_plan: points / routes / areas already resolved by scene.resolve)."""
    w0, w1 = plan["window"]["start"], plan["window"]["end"]
    cfg = {} if cfg is None else cfg
    if not isinstance(cfg, dict) or set(cfg) - {"defaults", "routes", "points", "areas"}:
        add("error", "animation", "animation must be {defaults, routes, points, areas}", None)
        cfg = {}
    d = {"ease": "linear", "marker": "none", "appear": "cut", "fade_frames": 0}
    dg = cfg.get("defaults", {})
    if not isinstance(dg, dict) or set(dg) - set(d):
        add("error", "animation", "animation.defaults takes only ease, marker, appear, fade_frames", None)
        dg = {}
    d.update(dg)

    def pick(group, eid, fields):
        g = cfg.get(group, {})
        if not isinstance(g, dict):
            return {}
        e = g.get(eid, {})
        if not isinstance(e, dict) or set(e) - set(fields):
            add("error", "animation", f"animation.{group}.{eid} takes only {', '.join(fields)}", eid)
            return {}
        return e

    for group, ids in (("routes", {r["id"] for r in scene_plan["routes"]}), ("points", {p["id"] for p in scene_plan["points"]}),
                       ("areas", {a["id"] for a in scene_plan["areas"]})):
        g = cfg.get(group, {})
        if not isinstance(g, dict):
            add("error", "animation", f"animation.{group} must be an object keyed by the plan's ids", None)
            continue
        for eid in g:
            if eid not in ids:
                add("error", "unknown_element", f"animation.{group}.{eid}: the plan has no {group[:-1]} {eid!r}", eid)

    routes = []
    for r in scene_plan["routes"]:
        e = pick("routes", r["id"], ("ease", "marker"))
        ez, mk = e.get("ease", d["ease"]), e.get("marker", d["marker"])
        if ez not in ROUTE_EASES:
            add("error", "animation", f"route ease must be one of {', '.join(ROUTE_EASES)}", r["id"])
            ez = "linear"
        if mk not in ROUTE_MARKERS:
            add("error", "animation", f"route marker must be one of {', '.join(ROUTE_MARKERS)}", r["id"])
            mk = "none"
        legs = [lg["distance_m"] for lg in next(x for x in plan["routes"] if x["id"] == r["id"])["legs"]]
        cum = [0.0]
        for L in legs:
            cum.append(cum[-1] + L)
        routes.append(dict(r, _cum=cum, _ease=ez, _marker=mk))

    def appear(group, el):
        e = pick(group, el["id"], ("appear", "fade_frames"))
        ap, ff = e.get("appear", d["appear"]), e.get("fade_frames", d["fade_frames"] if e.get("appear", d["appear"]) == "fade" else 0)
        if ap not in APPEARS:
            add("error", "animation", f"appear must be one of {', '.join(APPEARS)}", el["id"])
            ap = "cut"
        if not (_int(ff) and 0 <= ff <= MAX_FADE):
            add("error", "animation", f"fade_frames must be a whole number 0..{MAX_FADE}", el["id"])
            ff = 0
        if ap == "fade" and 2 * ff > el["end"] - el["start"]:
            add("error", "animation", f"fade_frames {ff} is more than half of the element's {el['end'] - el['start']} frames", el["id"])
            ff = 0
        return ap, (ff if ap == "fade" else 0)

    fades = {("points", p["id"]): appear("points", p) for p in scene_plan["points"]}
    fades.update({("areas", a["id"]): appear("areas", a) for a in scene_plan["areas"]})
    if not _int(d["fade_frames"]) or d["ease"] not in ROUTE_EASES or d["marker"] not in ROUTE_MARKERS or d["appear"] not in APPEARS:
        add("error", "animation", "animation.defaults: ease linear | in-out, marker plane | ship | dot | none, appear cut | fade, "
                                  "fade_frames a whole number", None)

    def opacity(el, group, f):
        if not el["show"] or not (el["start"] <= f < el["end"]):
            return 0.0
        ap, ff = fades[(group, el["id"])]
        if ap == "cut" or ff == 0:
            return 1.0
        return round(min(1.0, (f - el["start"] + 1) / ff, (el["end"] - f) / ff), 4)

    frames = []
    for f in range(w0, w1):
        rs = []
        for r in routes:
            s = _drawn_distance(r, f, r["_ease"])
            shares, head = [], None
            for k, pc in enumerate(r["pieces"]):
                sh, hd = _piece_state(pc, s)
                shares.append(round(sh, 6))
                if hd is not None:
                    head = (k, hd)                         # the last piece holding the tip: the side the route goes on
            if head is None and r["start"] <= f and r["pieces"]:
                # the tip sits exactly on a piece end (a stop, a seam point, the route's end): the piece that continues
                k = max(i for i, pc in enumerate(r["pieces"]) if pc[0]["s_m"] <= s) if any(pc[0]["s_m"] <= s for pc in r["pieces"]) else 0
                pc = r["pieces"][k]
                at = pc[0] if s <= pc[0]["s_m"] else pc[-1]
                i = 0 if at is pc[0] else len(pc) - 2
                head = (k, (at["x"], at["y"], _heading(pc, max(i, 0))))
            total = r["_cum"][-1]
            frac = (s / total) if total > 0 else (1.0 if f >= r["start"] else 0.0)
            show_head = r["show"] and r["_marker"] != "none" and f >= r["start"] and head is not None
            rs.append({"id": r["id"], "s_m": round(s, 2), "fraction": round(frac, 6), "pieces": shares,
                       "head": {"x": round(head[1][0], 3), "y": round(head[1][1], 3), "heading_deg": round(head[1][2], 3),
                                "piece": head[0]} if show_head else None})
        frames.append({"frame": f, "routes": rs,
                       "points": [{"id": p["id"], "opacity": opacity(p, "points", f)} for p in scene_plan["points"]],
                       "areas": [{"id": a["id"], "opacity": opacity(a, "areas", f)} for a in scene_plan["areas"]]})
    return {"routes": [{"id": r["id"], "ease": r["_ease"], "marker": r["_marker"]} for r in routes],
            "points": [{"id": p["id"], "appear": fades[("points", p["id"])][0], "fade_frames": fades[("points", p["id"])][1]} for p in scene_plan["points"]],
            "areas": [{"id": a["id"], "appear": fades[("areas", a["id"])][0], "fade_frames": fades[("areas", a["id"])][1]} for a in scene_plan["areas"]],
            "frames": frames}
