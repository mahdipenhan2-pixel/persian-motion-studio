"""NFP Map Motion - M1: map.json (nfp.mapmotion/1) -> a deterministic plan (nfp.mapmotion.plan/1). No rendering.

  {"schema": "nfp.mapmotion/1", "id": "route-1", "mode": "draft" | "final", "fps": 30,
   "projection": {"type": "equirectangular", "standard_parallel": "auto" | <degrees>},
   "viewport": {"width": 1920, "height": 1080, "margin": {"x": 96, "y": 64},
                "bounds": {"north": .., "south": .., "east": .., "west": ..}          (exactly one of bounds / fit)
                "fit": {"locations": ["loc-a", ...], "pad_deg": 0.5}},
   "window": {"start": 30, "end": 300, "anchors": {"start": .., "end": ..}},     frames of the VIDEO (see below)
   "labels": {"lang": "fa", "year": 1600 | null, "fallback": ["en"]},
   "uncertainty": {"show": "auto" | "always" | "never"},
   "points": [{"id": "p1", "location": "loc-a", "start": 30, "end": 300, "anchors": {..},
               "label": true, "lang": "en", "year": 1700}],                         lang / year override the map's
   "routes": [{"id": "r1", "stops": ["loc-a", "loc-b", "loc-c"], "start": 60, "end": 240, "samples": 32}],
   "areas":  [{"id": "a1", "location": "loc-b", "source": "extent" | "uncertainty", "start": 30, "end": 300}]}

Time: whole frames at 30 fps - the Timeline contract (end exclusive; "anchors" optional, the same anchor forms; they
are resolved with Timeline's own Context from words.json, read-only, never re-implemented). The frames are VIDEO
frames (like Timeline clips), not frames counted from the map's start; every element must lie inside the window.
How a Timeline map clip will point to a map.json (and whether its frames must equal the window) is decided when the
two are connected (M3) - not here.

Places come only from a Location document (nfp.locations/1, read with nfp.location's public API): point, extent,
uncertainty, precision, status, names. In "final" mode a location that is not verified is an error; in "draft" mode a
warning. Labels: name_at(location, year, lang, fallback) - no name, no label (a warning; nothing is guessed).
Route timing: the route is "drawn" from start to end in proportion to great-circle distance; each stop gets the frame
at which the line reaches it.

The plan contains frame coordinates (pixels, 3 decimals), sampled routes, the viewport, names, frames and the QC
report; it depends only on the inputs (no clock, no randomness, element order as written in map.json).
"""
import datetime
import math
import re

import location as LOC                    # nfp/location public API (read only)
import timeline as TL                     # nfp/timeline public anchor contract (read only)

from . import projection as PJ
from . import route as RT
from . import seam as SM

SCHEMA = "nfp.mapmotion/1"
PLAN_SCHEMA = "nfp.mapmotion.plan/1"
FPS = 30
TOP = {"schema", "id", "mode", "fps", "projection", "viewport", "window", "labels", "uncertainty", "points", "routes", "areas"}
POINT_KEYS = {"id", "location", "start", "end", "anchors", "label", "lang", "year"}
ROUTE_KEYS = {"id", "stops", "start", "end", "anchors", "samples"}
AREA_KEYS = {"id", "location", "source", "start", "end", "anchors"}
SHOW = ("auto", "always", "never")
UNCERTAIN = ("approximate", "centroid", "uncertain")
DEG_M = math.pi * RT.R_EARTH_M / 180          # metres per degree of latitude on the sphere
# Map Motion's own patterns (the same rules Location uses; Location's module internals are not imported)
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
LANG_RE = re.compile(r"[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|\d{3}))?")
NEAR_ANTIPODAL_DEG = 179.0


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _r(v, n=3):
    return round(float(v), n)


def build(doc, locations_doc, context=None, today=None):
    """map.json + locations.json (+ a timeline.Context from words.json) -> plan dict with plan["qc"].
    `today` (a datetime.date) is REQUIRED: Location review dates are checked against it, so the plan depends only on
    its inputs, never on the computer's clock."""
    if today is None:
        raise ValueError("build() needs today=datetime.date(...): the date Location review / accessed dates are checked "
                         "against (the system clock is never used)")
    if not isinstance(today, datetime.date) or isinstance(today, datetime.datetime):
        raise ValueError(f"today must be a datetime.date (not {type(today).__name__})")
    issues = []

    def add(level, code, msg, el=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("element", el), ("message", msg)) if v is not None})

    plan = {"schema": PLAN_SCHEMA, "map": None, "mode": None, "fps": FPS, "frame": None, "projection": None,
            "viewport": None, "window": None, "points": [], "routes": [], "areas": []}

    def done():
        n = {lv: sum(1 for x in issues if x["level"] == lv) for lv in ("error", "warning", "info")}
        plan["qc"] = {"status": "FAIL" if n["error"] else "WARN" if n["warning"] else "OK", "errors": n["error"],
                      "warnings": n["warning"], "infos": n["info"], "issues": issues}
        return plan

    # ---- document
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        add("error", "schema", f"map must have schema {SCHEMA}")
        return done()
    extra = sorted(set(doc) - TOP)
    if extra:
        add("error", "schema", f"unknown top-level field(s) {', '.join(extra)}")
    mid = doc.get("id")
    if not isinstance(mid, str) or not ID_RE.fullmatch(mid):
        add("error", "bad_id", f"bad map id {mid!r}")
    plan["map"] = mid
    mode = doc.get("mode", "draft")
    if mode not in ("draft", "final"):
        add("error", "schema", "mode must be 'draft' or 'final'")
    plan["mode"] = mode
    if doc.get("fps", FPS) != FPS:
        add("error", "fps", f"fps must be {FPS} (the Timeline contract)")
    # ---- locations (read only)
    if locations_doc is None:
        add("error", "no_locations", "a locations document (nfp.locations/1) is needed")
        return done()
    lrep = LOC.validate(locations_doc, today=today)
    for x in lrep["issues"]:
        if x["level"] == "error":
            add("error", "location_file", f"locations file: {x.get('location', '-')}: {x['message']}")
    status = lrep["locations"]
    recs = {r["id"]: r for r in locations_doc.get("locations", []) if isinstance(r, dict) and r.get("id") in status} \
        if isinstance(locations_doc, dict) and isinstance(locations_doc.get("locations"), list) else {}
    used = {}

    def place(lid, el):
        """(lat, lon) of a usable location, or None (problem reported)."""
        if not isinstance(lid, str) or lid not in recs:
            add("error", "unknown_location", f"location {lid!r} is not in the locations file", el)
            return None
        r = recs[lid]
        pt = r.get("point")
        if not isinstance(pt, dict) or [p for p in LOC.check_point(pt) if p[0] == "error"]:
            add("error", "bad_location", f"location {lid!r} has no valid point", el)
            return None
        if status.get(lid) != "verified" and lid not in used:
            if mode == "final":
                add("error", "draft_location", f"location {lid!r} is a draft (not verified): not allowed in a final map", el)
            else:
                add("warning", "draft_location", f"location {lid!r} is a draft (not verified)", el)
        used[lid] = True
        return float(pt["lat"]), float(pt["lon"])

    # ---- timing
    win = doc.get("window")

    def frames(obj, el, where="", lo=None, hi=None):
        """(start, end) of an element, checked; None if unusable."""
        if not isinstance(obj, dict):
            return None
        a, b = obj.get("start"), obj.get("end")
        if not (_int(a) and _int(b)):
            add("error", "bad_time", f"{where}start and end must be whole frame numbers", el)
            return None
        if a < 0 or b <= a:
            add("error", "bad_time", f"{where}start {a} / end {b}: need 0 <= start < end", el)
            return None
        an = obj.get("anchors")
        if an is not None:
            if not isinstance(an, dict) or not an or set(an) - {"start", "end"}:
                add("error", "bad_anchor", f"{where}anchors must be an object with start and / or end", el)
            elif context is None:
                add("info", "anchors_unchecked", f"{where}anchors not resolved (no word timing given)", el)
            else:
                for k, v in an.items():
                    try:
                        f = context.resolve(v)
                    except TL.AnchorError as e:
                        add("error", "bad_anchor", f"{where}{k}: {e}", el)
                        continue
                    if f != obj[k]:
                        add("error", "anchor_mismatch", f"{where}{k} is frame {obj[k]} but its anchor {v!r} resolves to frame {f}", el)
        if lo is not None and (a < lo or b > hi):
            add("error", "outside_window", f"frames {a}..{b - 1} are outside the map window {lo}..{hi - 1}", el)
        return a, b

    w = frames(win, None, "window: ") if isinstance(win, dict) else None
    if not isinstance(win, dict):
        add("error", "schema", "window {start, end} is required")
    elif set(win) - {"start", "end", "anchors"}:
        add("error", "schema", "window takes only start, end, anchors")
    if w and context is not None and w[1] > context.frames:
        add("error", "outside_video", f"the window ends at frame {w[1]}, after the video ({context.frames})")
    plan["window"] = {"start": w[0], "end": w[1]} if w else None
    # ---- labels / uncertainty settings
    lab = doc.get("labels", {"lang": "fa", "year": None})
    if not isinstance(lab, dict) or set(lab) - {"lang", "year", "fallback"} or not isinstance(lab.get("lang"), str) \
            or not LANG_RE.fullmatch(lab.get("lang", "")):
        add("error", "schema", "labels must be {lang, year, fallback} with a language code like fa / en")
        lab = {"lang": "fa", "year": None}
    fb = lab.get("fallback")
    if fb is not None and not (isinstance(fb, list) and all(isinstance(x, str) and LANG_RE.fullmatch(x) for x in fb)):
        add("error", "schema", "labels.fallback must be a list of language codes")
        fb = None
    yr = lab.get("year")
    if yr is not None and (not _int(yr) or yr == 0):
        add("error", "bad_year", f"labels.year {yr!r} must be a whole year other than 0 (1 BC = -1, AD 1 = 1) or null")
        yr = None
    unc = doc.get("uncertainty", {"show": "auto"})
    if not isinstance(unc, dict) or set(unc) - {"show"} or unc.get("show", "auto") not in SHOW:
        add("error", "schema", f"uncertainty must be {{show: {' | '.join(SHOW)}}}")
        unc = {"show": "auto"}
    show = unc.get("show", "auto")
    # ---- projection / viewport
    pr = doc.get("projection", {"type": "equirectangular"})
    if not isinstance(pr, dict) or pr.get("type") != "equirectangular" or set(pr) - {"type", "standard_parallel"}:
        add("error", "projection", "projection must be {type: equirectangular, standard_parallel: auto | degrees} (M1)")
        pr = {"type": "equirectangular"}
    vp = doc.get("viewport")
    proj = None
    if not isinstance(vp, dict) or set(vp) - {"width", "height", "margin", "bounds", "fit"}:
        add("error", "schema", "viewport must be {width, height, margin, bounds | fit}")
    elif ("bounds" in vp) == ("fit" in vp):
        add("error", "schema", "viewport needs exactly one of bounds / fit")
    else:
        m = vp.get("margin", {"x": 96, "y": 64})
        if isinstance(m, (int, float)) and not isinstance(m, bool):
            m = {"x": m, "y": m}
        if not isinstance(m, dict) or set(m) != {"x", "y"}:
            add("error", "schema", "viewport.margin must be a number or {x, y}")
            m = None
        bounds = vp.get("bounds")
        if "fit" in vp:
            f = vp["fit"]
            if not isinstance(f, dict) or set(f) - {"locations", "pad_deg"} or not isinstance(f.get("locations"), list) \
                    or not f["locations"] or not PJ.finite(f.get("pad_deg", 0)) or f.get("pad_deg", 0) < 0:
                add("error", "schema", "viewport.fit must be {locations: [ids], pad_deg: >= 0}")
                bounds = None
            else:
                pts = [p for p in (place(lid, "viewport") for lid in f["locations"]) if p]
                ext = []
                for lid in f["locations"]:
                    e = (recs.get(lid) or {}).get("extent") if isinstance(lid, str) else None
                    if isinstance(e, dict) and not [x for x in LOC.check_extent(e) if x[0] == "error"]:
                        ext += [(e["north"], e["west"]), (e["south"], e["east"])]
                bounds = PJ.fit_bounds(pts + ext, f.get("pad_deg", 0)) if len(pts) == len(f["locations"]) else None
        if bounds is not None and m is not None:
            try:
                proj = PJ.Equirectangular(bounds, vp.get("width", 1920), vp.get("height", 1080), m["x"], m["y"],
                                          pr.get("standard_parallel", "auto"))
            except PJ.ProjectionError as e:
                add("error", "viewport", str(e))
    if proj is not None:
        plan["frame"] = {"width": proj.width, "height": proj.height}
        plan["projection"] = {"type": "equirectangular", "standard_parallel": _r(proj.phi0, 6),
                              "px_per_deg_lat": _r(proj.k, 6), "px_per_deg_lon": _r(proj.kx, 6)}
        plan["viewport"] = {"bounds": {k: _r(v, 7) for k, v in proj.bounds.items()},
                            "visible": {k: _r(v, 7) for k, v in proj.visible().items()},
                            "crosses_date_line": proj.bounds["west"] > proj.bounds["east"]}
    # ---- elements
    seen = set()

    def element(e, keys, kind):
        eid = e.get("id") if isinstance(e, dict) else None
        if not isinstance(eid, str) or not ID_RE.fullmatch(eid):
            add("error", "bad_id", f"bad {kind} id {eid!r}")
            return None
        if eid in seen:
            add("error", "duplicate_id", f"element id {eid!r} is used twice", eid)
            return None
        seen.add(eid)
        ex = sorted(set(e) - keys)
        if ex:
            add("error", "schema", f"unknown field(s) {', '.join(ex)}", eid)
        return eid

    def label_for(lid, e, el):
        if e.get("label", True) is False:
            return None
        lang = e.get("lang", lab.get("lang", "fa"))
        year = e.get("year", yr)
        if not isinstance(lang, str) or not LANG_RE.fullmatch(lang):
            add("error", "schema", f"lang {lang!r} is not a language code", el)
            return None
        if year is not None and (not _int(year) or year == 0):
            add("error", "bad_year", f"year {year!r} must be a whole year other than 0, or null", el)
            return None
        try:
            n = LOC.name_at(recs[lid], year, lang, fb)
        except ValueError as ex:                         # Location's name errors are ValueErrors
            add("error", "label", f"name of {lid!r}: {ex}", el)
            return None
        if n is None:
            add("warning", "no_name", f"{lid!r} has no name valid in {year if year is not None else 'today'} - no label", el)
            return None
        if n["fallback"]:
            add("info", "label_fallback", f"{lid!r}: no {lang} name for {year if year is not None else 'today'}, "
                                          f"shown in {n['lang']}", el)
        return {"text": n["text"], "display": n["display"], "lang": n["lang"], "type": n["type"], "fallback": n["fallback"],
                "year": year}

    def uncertainty(lid, lat, el):
        r = recs[lid]
        um, prec = r.get("uncertainty_m"), r.get("precision")
        want = show == "always" or (show == "auto" and prec in UNCERTAIN)
        if not want:
            return None
        if not (PJ.finite(um) and um >= 0):
            if show == "always" or prec in UNCERTAIN:
                add("warning", "unknown_uncertainty", f"{lid!r} is {prec} but has no uncertainty_m: no area shown", el)
            return None
        dlat = um / DEG_M
        cl = math.cos(math.radians(lat))
        dlon = dlat / cl if cl > 1e-9 else 180.0
        return {"m": um, "rx": _r(min(dlon, 180.0) * proj.kx), "ry": _r(dlat * proj.k), "precision": prec}

    lo, hi = (w if w else (None, None))
    for e in doc.get("points", []) if isinstance(doc.get("points", []), list) else []:
        eid = element(e, POINT_KEYS, "point")
        if eid is None:
            continue
        t = frames(e, eid, lo=lo, hi=hi)
        if "label" in e and not isinstance(e["label"], bool):
            add("error", "schema", "label must be true or false", eid)
        ll = place(e.get("location"), eid)
        if ll is None or t is None or proj is None:
            continue
        x, y = proj.project(*ll)
        inside = proj.inside_map(x, y)                   # inside the map's own bounds, not just the frame
        if not proj.inside_frame(x, y):
            add("warning", "outside_frame", f"{e['location']!r} is outside the frame ({x:.0f}, {y:.0f})", eid)
        elif not inside:
            add("warning", "outside_map", f"{e['location']!r} is in the frame margin, outside the map bounds "
                                          f"({x:.0f}, {y:.0f})", eid)
        plan["points"].append({"id": eid, "location": e["location"], "status": status.get(e["location"]),
                               "lat": ll[0], "lon": ll[1], "x": _r(x), "y": _r(y), "inside": inside,
                               "label": label_for(e["location"], e, eid), "uncertainty": uncertainty(e["location"], ll[0], eid),
                               "start": t[0], "end": t[1]})
    for e in doc.get("routes", []) if isinstance(doc.get("routes", []), list) else []:
        eid = element(e, ROUTE_KEYS, "route")
        if eid is None:
            continue
        t = frames(e, eid, lo=lo, hi=hi)
        stops = e.get("stops")
        samples = e.get("samples", 32)
        if not (_int(samples) and 2 <= samples <= 1000):
            add("error", "schema", "samples must be a whole number 2..1000", eid)
            continue
        if not (isinstance(stops, list) and len(stops) >= 2):
            add("error", "schema", "stops must list at least two location ids, in order", eid)
            continue
        pts = [place(s, eid) for s in stops]
        if any(p is None for p in pts) or t is None or proj is None:
            continue
        legs, total, ok = [], 0.0, True
        for i in range(len(pts) - 1):
            if stops[i] == stops[i + 1]:
                add("warning", "zero_leg", f"stop {i + 1} and {i + 2} are the same place ({stops[i]!r})", eid)
            try:
                g = RT.leg(pts[i], pts[i + 1], samples)
            except RT.RouteError as ex:
                add("error", "route", f"leg {stops[i]!r} -> {stops[i + 1]!r}: {ex}", eid)
                ok = False
                break
            if g["angle_deg"] > NEAR_ANTIPODAL_DEG:
                add("warning", "near_antipodal", f"leg {stops[i]!r} -> {stops[i + 1]!r} spans {g['angle_deg']:.3f} degrees "
                                                 f"(> {NEAR_ANTIPODAL_DEG:g}): its great circle is unstable - a tiny change in "
                                                 f"either point can send it round the other side of the globe; add an "
                                                 f"intermediate stop to fix the way it should go", eid)
            legs.append(g)
            total += g["distance_m"]
        if not ok:
            continue
        # one continuous longitude series for the whole route, projected from the first stop's x
        flat = [p for g_i, g in enumerate(legs) for p in (g["points"] if g_i == 0 else g["points"][1:])]
        un = RT.unwrap([p[1] for p in flat])
        u0 = PJ.east_of(flat[0][1], proj.bounds["west"], proj.lon_span)
        xy = [(proj.x_of_u(u0 + (lu - un[0])), proj.y0 + (proj.bounds["north"] - lat) * proj.k) for (lat, _), lu in zip(flat, un)]
        if any(not proj.inside_frame(x, y) for x, y in xy):
            add("warning", "outside_frame", "part of the route is outside the frame", eid)
        elif any(not proj.inside_map(x, y) for x, y in xy):
            add("warning", "outside_map", "part of the route is outside the map bounds (in the frame margin)", eid)
        out_legs, k0, run = [], 0, 0.0
        stop_frames = [t[0]]
        for i, g in enumerate(legs):
            n = len(g["points"])
            seg = xy[k0:k0 + n]
            mx, _ = proj.project(*pts[i + 1])               # where the stop's own marker is drawn
            alt = SM.marker_xs(proj, *pts[i + 1])           # a stop on the seam is drawn on both edges (M2a)
            if min(abs(seg[-1][0] - x) for x in alt) > 0.5:
                turns = (seg[-1][0] - mx) / (360 * proj.kx)
                add("warning", "route_wraps", f"leg {stops[i]!r} -> {stops[i + 1]!r} reaches x {seg[-1][0]:.1f} but the marker "
                                              f"of {stops[i + 1]!r} is at x {mx:.1f}: the route end and the stop marker differ "
                                              f"by {turns:+.0f} x 360 degrees of longitude, so they are drawn in different "
                                              f"places - the route is not split here (M2 will split it)", eid)
            run += g["distance_m"]
            stop_frames.append(t[0] + (round((t[1] - t[0]) * run / total) if total > 0 else (t[1] - t[0])))
            out_legs.append({"from": stops[i], "to": stops[i + 1], "distance_m": _r(g["distance_m"], 2), "angle_deg": _r(g["angle_deg"], 6),
                             "geo": [[_r(la, 7), _r(lo_, 7)] for la, lo_ in g["points"]],
                             "lon_unwrapped": [_r(v, 7) for v in un[k0:k0 + n]],
                             "xy": [[_r(x), _r(y)] for x, y in seg]})
            k0 += n - 1
        stop_frames[-1] = t[1]
        plan["routes"].append({"id": eid, "stops": list(stops), "start": t[0], "end": t[1], "samples": samples,
                               "length_m": _r(total, 2), "stop_frames": stop_frames, "legs": out_legs})
    for e in doc.get("areas", []) if isinstance(doc.get("areas", []), list) else []:
        eid = element(e, AREA_KEYS, "area")
        if eid is None:
            continue
        t = frames(e, eid, lo=lo, hi=hi)
        src = e.get("source")
        if src not in ("extent", "uncertainty"):
            add("error", "schema", "source must be 'extent' or 'uncertainty'", eid)
            continue
        ll = place(e.get("location"), eid)
        if ll is None or t is None or proj is None:
            continue
        r = recs[e["location"]]
        if src == "extent":
            ex = r.get("extent")
            if not isinstance(ex, dict) or [x for x in LOC.check_extent(ex) if x[0] == "error"]:
                add("error", "no_extent", f"{e['location']!r} has no valid extent", eid)
                continue
            x1 = proj.x_of_u(PJ.east_of(ex["west"], proj.bounds["west"], proj.lon_span))
            x2 = x1 + PJ.span(ex["west"], ex["east"]) * proj.kx
            y1, y2 = proj.y0 + (proj.bounds["north"] - ex["north"]) * proj.k, proj.y0 + (proj.bounds["north"] - ex["south"]) * proj.k
            shape = {"type": "rect", "x": _r(x1), "y": _r(y1), "w": _r(x2 - x1), "h": _r(y2 - y1)}
        else:
            um = r.get("uncertainty_m")
            if not (PJ.finite(um) and um > 0):
                add("error", "no_uncertainty", f"{e['location']!r} has no uncertainty_m", eid)
                continue
            x, y = proj.project(*ll)
            dlat = um / DEG_M
            cl = math.cos(math.radians(ll[0]))
            shape = {"type": "ellipse", "cx": _r(x), "cy": _r(y), "rx": _r(min(dlat / cl if cl > 1e-9 else 180, 180) * proj.kx),
                     "ry": _r(dlat * proj.k), "m": um}
        plan["areas"].append({"id": eid, "location": e["location"], "source": src, "start": t[0], "end": t[1], "shape": shape})
    return done()
