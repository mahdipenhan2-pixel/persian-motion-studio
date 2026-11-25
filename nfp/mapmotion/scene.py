"""NFP Map Motion - M2b: scene.json (nfp.mapmotion.scene/1) - how a map is to be shown - and its resolution into a
deterministic scene plan (nfp.mapmotion.sceneplan/1). Standard library. Data only: nothing is drawn here.

  {"schema": "nfp.mapmotion.scene/1", "id": "scene-1", "map": "route-1",          the M1 map (plan["map"]) it shows
   "mode": "draft" | "final",
   "style": {"preset": "documentary-light" | "documentary-dark" | "parchment", "colors": {..}, "widths": {..}},
   "graticule": {"show": false, "step_deg": 10},
   "basemap": [{"id": "land", "asset": "ne-land", "role": "land" | "lakes" | "coastline" | "borders" | "rivers",
                "show": true}],                                                  assets from assets.json (nfp.assets/1)
   "show": {"points": true, "routes": true, "areas": true, "labels": true, "uncertainty": true},
   "points": {"p1": {"marker": "pin" | "dot" | "ring" | "plane" | "ship" | "none", "size": 14, "color": "#RRGGBB",
                     "label": true, "show": true}},                              per point of the plan (all optional)
   "routes": {"r1": {"color": "#RRGGBB", "width": 3, "dash": [8, 4] | null, "show": true}},
   "areas":  {"a1": {"fill": "#RRGGBB", "opacity": 0.25, "stroke": "#RRGGBB", "show": true}},
   "camera": {"max_zoom": 40, "keyframes": [{"frame": 30, "view": {..}, "ease": "in-out"}]},   M2c: see camera.py
   "animation": {"defaults": {..}, "routes": {"r1": {"ease": "in-out", "marker": "plane"}}, ..}}  M2d: see animate.py

resolve(scene, plan, geometry, assets=None, assets_dir=None) -> scene plan:
  - plan: an M1 plan (OK / WARN; FAIL is refused), geometry: geometry(plan) from M2a for that plan (its route_jump /
    route_wraps errors are refused; its warnings are passed on). Neither is changed; their contracts are unchanged.
  - Every element of the plan appears in the scene plan with its final style and visibility (defaults from the preset,
    then the scene's "show", then the element's own entry); an entry for an id the plan does not have is an error.
  - Basemap layers are read from LOCAL GeoJSON files registered in assets.json (kind "map"), checked with Timeline's
    public asset check (file, sha256, licence). In "final" mode an unverified asset is an error, in "draft" a warning.
    Polygons are needed for land / lakes; lines or polygons (as outlines) for coastline / borders / rivers.
  - The camera (M2c, camera.py): zoom and pan over the plan's map, one state per frame of the window ("camera" in
    the scene plan); without "camera" in the scene, the full frame at zoom 1.
  - The animation (M2d, animate.py): routes drawn over time (M1's timing) with a moving marker, points and areas
    appearing (cut / fade), one state per frame ("animation" in the scene plan).
  - The labels (M2f, labels.py): the points' names placed in screen space, frame by frame, without overlaps;
    metrics = a labelmetrics document from tools/measure.py (the browser's own text measurement), else estimated sizes.
  - Later stages are not here: Film / Timeline (M2g). Its key ("timeline") is refused with a clear message.
The scene plan is deterministic: element order as in the plan, basemap layers as in the scene, no clock, no randomness.
"""
import re
from pathlib import Path

import timeline as TL                     # nfp/timeline public asset check (read only)

from . import animate as AN
from . import labels as LB
from . import camera as CAM
from . import geodata as GD
from .geometry import GEOMETRY_SCHEMA
from .model import PLAN_SCHEMA

SCENE_SCHEMA = "nfp.mapmotion.scene/1"
SCENE_PLAN_SCHEMA = "nfp.mapmotion.sceneplan/1"
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?")
MARKERS = ("pin", "dot", "ring", "plane", "ship", "none")
ROLES = {"land": ("polygon",), "lakes": ("polygon",), "coastline": ("polygon", "line"), "borders": ("polygon", "line"),
         "rivers": ("line", "polygon")}
LATER = {"timeline": "M2g (Film / Timeline)"}
TOP = {"schema", "id", "map", "mode", "style", "graticule", "basemap", "show", "points", "routes", "areas", "camera", "animation", "labels"}
SHOW_KEYS = ("points", "routes", "areas", "labels", "uncertainty")
COLOR_KEYS = ("background", "land", "lakes", "coastline", "borders", "rivers", "graticule", "route", "point", "point_stroke",
              "area_fill", "area_stroke", "uncertainty", "label")
WIDTH_KEYS = ("coastline", "borders", "rivers", "graticule", "route", "area_stroke", "point_size")
PRESETS = {
    "documentary-light": {
        "colors": {"background": "#dfe8ee", "land": "#f4f1ea", "lakes": "#dfe8ee", "coastline": "#8a9aa6", "borders": "#b4a99a",
                   "rivers": "#9fb8c8", "graticule": "#c5d2da", "route": "#b3261e", "point": "#b3261e", "point_stroke": "#ffffff",
                   "area_fill": "#b3261e", "area_stroke": "#b3261e", "uncertainty": "#b3261e", "label": "#1f2328"},
        "widths": {"coastline": 1.0, "borders": 0.8, "rivers": 0.8, "graticule": 0.6, "route": 4.0, "area_stroke": 1.5,
                   "point_size": 14.0},
        "opacity": {"area": 0.2, "uncertainty": 0.18}},
    "documentary-dark": {
        "colors": {"background": "#10161c", "land": "#25303a", "lakes": "#10161c", "coastline": "#5d6f7d", "borders": "#4a5763",
                   "rivers": "#33495a", "graticule": "#1d2731", "route": "#f2b84b", "point": "#f2b84b", "point_stroke": "#10161c",
                   "area_fill": "#f2b84b", "area_stroke": "#f2b84b", "uncertainty": "#f2b84b", "label": "#e8edf1"},
        "widths": {"coastline": 1.0, "borders": 0.8, "rivers": 0.8, "graticule": 0.6, "route": 4.0, "area_stroke": 1.5,
                   "point_size": 14.0},
        "opacity": {"area": 0.2, "uncertainty": 0.2}},
    "parchment": {
        "colors": {"background": "#d9cdb1", "land": "#efe4c8", "lakes": "#d9cdb1", "coastline": "#7d6a4f", "borders": "#a48e6c",
                   "rivers": "#8fa3a0", "graticule": "#cbbd9c", "route": "#7a1f12", "point": "#7a1f12", "point_stroke": "#efe4c8",
                   "area_fill": "#7a1f12", "area_stroke": "#7a1f12", "uncertainty": "#7a1f12", "label": "#2b2118"},
        "widths": {"coastline": 1.2, "borders": 0.9, "rivers": 0.9, "graticule": 0.6, "route": 4.0, "area_stroke": 1.5,
                   "point_size": 14.0},
        "opacity": {"area": 0.22, "uncertainty": 0.2}},
}
DEFAULT_PRESET = "documentary-light"


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def resolve(scene, plan, geometry, assets=None, assets_dir=None, metrics=None):
    issues = []

    def add(level, code, msg, element=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("element", element), ("message", msg)) if v is not None})

    out = {"schema": SCENE_PLAN_SCHEMA, "scene": None, "map": None, "mode": None, "frame": None, "style": None,
           "graticule": None, "basemap": [], "areas": [], "routes": [], "points": [], "camera": None, "animation": None, "labels": None, "qc": None}
    # ---- the inputs this stage consumes (unchanged contracts)
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"resolve() needs an M1 plan ({PLAN_SCHEMA})")
    if (plan.get("qc") or {}).get("status") not in ("OK", "WARN"):
        raise ValueError(f"the plan's QC status is {(plan.get('qc') or {}).get('status')!r}: a FAIL plan is not usable")
    if not isinstance(geometry, dict) or geometry.get("schema") != GEOMETRY_SCHEMA:
        raise ValueError(f"resolve() needs the plan's geometry ({GEOMETRY_SCHEMA})")
    if geometry.get("map") != plan.get("map") or [r["id"] for r in geometry["routes"]] != [r["id"] for r in plan["routes"]] \
            or [p["id"] for p in geometry["points"]] != [p["id"] for p in plan["points"]]:
        raise ValueError("the geometry is not the geometry of this plan (map / route / point ids differ)")
    bad = [x for x in geometry.get("issues", []) if x.get("level") == "error"]
    if bad:
        raise ValueError("the geometry has errors (" + ", ".join(sorted({x['code'] for x in bad})) + "): not usable")
    for x in geometry.get("issues", []):
        add(x["level"], x["code"], "geometry: " + x["message"], x.get("element"))
    # ---- the scene document
    if not isinstance(scene, dict) or scene.get("schema") != SCENE_SCHEMA:
        add("error", "schema", f"schema must be {SCENE_SCHEMA!r}")
        scene = {}
    for k in sorted(set(scene) - TOP):
        if k in LATER:
            add("error", "later_stage", f"{k!r} is not part of this stage: it comes with {LATER[k]}")
        elif k != "schema":
            add("error", "schema", f"unknown key {k!r}")
    sid = scene.get("id")
    if not (isinstance(sid, str) and ID_RE.fullmatch(sid)):
        add("error", "bad_id", "id must be 1-80 letters, digits, . _ - (starting with a letter or digit)")
    out["scene"] = sid
    if scene.get("map") != plan.get("map"):
        add("error", "map", f"the scene is for map {scene.get('map')!r}, the plan is map {plan.get('map')!r}")
    out["map"] = plan.get("map")
    mode = scene.get("mode", "draft")
    if mode not in ("draft", "final"):
        add("error", "schema", "mode must be 'draft' or 'final'")
        mode = "draft"
    out["mode"] = mode
    out["frame"] = dict(plan["frame"])
    # ---- style
    st = scene.get("style", {})
    if not isinstance(st, dict) or set(st) - {"preset", "colors", "widths", "opacity"}:
        add("error", "schema", "style must be {preset, colors, widths, opacity}")
        st = {}
    preset = st.get("preset", DEFAULT_PRESET)
    if preset not in PRESETS:
        add("error", "style", f"unknown style preset {preset!r} (one of {', '.join(PRESETS)})")
        preset = DEFAULT_PRESET
    colors = dict(PRESETS[preset]["colors"])
    widths = dict(PRESETS[preset]["widths"])
    opac = dict(PRESETS[preset]["opacity"])
    for name, store, keys, ok, what in (("colors", colors, COLOR_KEYS, lambda v: isinstance(v, str) and COLOR_RE.fullmatch(v), "#RRGGBB or #RRGGBBAA"),
                                         ("widths", widths, WIDTH_KEYS, lambda v: _num(v) and 0 < v <= 64, "a number of pixels in (0, 64]"),
                                         ("opacity", opac, ("area", "uncertainty"), lambda v: _num(v) and 0 <= v <= 1, "a number 0..1")):
        given = st.get(name, {})
        if not isinstance(given, dict):
            add("error", "style", f"style.{name} must be an object")
            continue
        for k, v in given.items():
            if k not in keys:
                add("error", "style", f"style.{name}.{k} is unknown ({', '.join(keys)})")
            elif not ok(v):
                add("error", "style", f"style.{name}.{k} must be {what}")
            else:
                store[k] = v.lower() if isinstance(v, str) else float(v)
    out["style"] = {"preset": preset, "colors": colors, "widths": widths, "opacity": opac}
    # ---- visibility defaults
    show = {k: True for k in SHOW_KEYS}
    sh = scene.get("show", {})
    if not isinstance(sh, dict):
        add("error", "schema", "show must be an object")
        sh = {}
    for k, v in sh.items():
        if k not in SHOW_KEYS:
            add("error", "schema", f"show.{k} is unknown ({', '.join(SHOW_KEYS)})")
        elif not isinstance(v, bool):
            add("error", "schema", f"show.{k} must be true or false")
        else:
            show[k] = v
    # ---- graticule
    gr = scene.get("graticule", {})
    if not isinstance(gr, dict) or set(gr) - {"show", "step_deg"}:
        add("error", "schema", "graticule must be {show, step_deg}")
        gr = {}
    gshow, gstep = gr.get("show", False), gr.get("step_deg", 10)
    if not isinstance(gshow, bool):
        add("error", "schema", "graticule.show must be true or false")
        gshow = False
    if not (_num(gstep) and gstep in (1, 2, 5, 10, 15, 20, 30, 45, 90)):
        add("error", "schema", "graticule.step_deg must be one of 1, 2, 5, 10, 15, 20, 30, 45, 90")
        gstep = 10
    out["graticule"] = {"show": gshow, "step_deg": gstep, "color": colors["graticule"], "width": widths["graticule"]}
    # ---- per-element entries
    def entries(key, ids, fields):
        given = scene.get(key, {})
        if not isinstance(given, dict):
            add("error", "schema", f"{key} must be an object keyed by the plan's {key[:-1]} ids")
            return {}
        res = {}
        for eid, e in given.items():
            if eid not in ids:
                add("error", "unknown_element", f"{key}.{eid}: the plan has no {key[:-1]} {eid!r}", eid)
                continue
            if not isinstance(e, dict) or set(e) - set(fields):
                add("error", "schema", f"{key}.{eid} takes only {', '.join(fields)}", eid)
                continue
            res[eid] = e
        return res

    def color(e, k, default, eid):
        v = e.get(k, default)
        if not (isinstance(v, str) and COLOR_RE.fullmatch(v)):
            add("error", "style", f"{k} must be #RRGGBB or #RRGGBBAA", eid)
            return default
        return v.lower()

    def flag(e, k, default, eid):
        v = e.get(k, default)
        if not isinstance(v, bool):
            add("error", "schema", f"{k} must be true or false", eid)
            return default
        return v

    geo_pts = {p["id"]: p for p in geometry["points"]}
    pe = entries("points", geo_pts, ("marker", "size", "color", "label", "show"))
    for p in plan["points"]:
        e = pe.get(p["id"], {})
        marker = e.get("marker", "pin")
        if marker not in MARKERS:
            add("error", "marker", f"marker must be one of {', '.join(MARKERS)}", p["id"])
            marker = "pin"
        size = e.get("size", widths["point_size"])
        if not (_num(size) and 2 <= size <= 128):
            add("error", "style", "size must be a number of pixels 2..128", p["id"])
            size = widths["point_size"]
        label = p.get("label") or {}
        want_label = flag(e, "label", show["labels"], p["id"])
        if want_label and not label.get("text"):
            want_label = False
        g = geo_pts[p["id"]]
        out["points"].append({"id": p["id"], "location": p["location"], "show": flag(e, "show", show["points"], p["id"]) and marker != "none",
                              "marker": marker, "size": float(size), "color": color(e, "color", colors["point"], p["id"]),
                              "stroke": colors["point_stroke"], "x": list(g["x"]), "y": g["y"], "on_seam": g["on_seam"],
                              "inside": p["inside"], "start": p["start"], "end": p["end"],
                              "label": {"show": want_label, "text": label.get("text"), "display": label.get("display"),
                                        "lang": label.get("lang"), "color": colors["label"]},
                              "uncertainty": dict(p["uncertainty"], show=show["uncertainty"],
                                                  color=colors["uncertainty"], opacity=opac["uncertainty"]) if p.get("uncertainty") else None})
    geo_routes = {r["id"]: r for r in geometry["routes"]}
    re_ = entries("routes", geo_routes, ("color", "width", "dash", "show"))
    for r in plan["routes"]:
        e = re_.get(r["id"], {})
        w = e.get("width", widths["route"])
        if not (_num(w) and 0 < w <= 64):
            add("error", "style", "width must be a number of pixels in (0, 64]", r["id"])
            w = widths["route"]
        dash = e.get("dash")
        if dash is not None and not (isinstance(dash, list) and 1 <= len(dash) <= 8 and all(_num(d) and 0 < d <= 256 for d in dash)):
            add("error", "style", "dash must be null or a list of 1-8 lengths in pixels (0, 256]", r["id"])
            dash = None
        g = geo_routes[r["id"]]
        out["routes"].append({"id": r["id"], "stops": list(r["stops"]), "show": flag(e, "show", show["routes"], r["id"]),
                              "color": color(e, "color", colors["route"], r["id"]), "width": float(w),
                              "dash": [float(d) for d in dash] if dash else None, "start": r["start"], "end": r["end"],
                              "stop_frames": list(r["stop_frames"]), "length_m": r["length_m"],
                              "pieces": [[{"x": v["x"], "y": v["y"], "s_m": v["s_m"], "kind": v["kind"]} for v in pc] for pc in g["pieces"]],
                              "error_px": g["error_px"]})
    ae = entries("areas", {a["id"] for a in plan["areas"]}, ("fill", "opacity", "stroke", "show"))
    for a in plan["areas"]:
        e = ae.get(a["id"], {})
        op = e.get("opacity", opac["area"])
        if not (_num(op) and 0 <= op <= 1):
            add("error", "style", "opacity must be a number 0..1", a["id"])
            op = opac["area"]
        out["areas"].append({"id": a["id"], "location": a["location"], "show": flag(e, "show", show["areas"], a["id"]),
                             "fill": color(e, "fill", colors["area_fill"], a["id"]), "opacity": float(op),
                             "stroke": color(e, "stroke", colors["area_stroke"], a["id"]), "width": widths["area_stroke"],
                             "shape": dict(a["shape"]), "start": a["start"], "end": a["end"]})
    # ---- basemap: local GeoJSON through assets.json
    layers = scene.get("basemap", [])
    if not isinstance(layers, list):
        add("error", "schema", "basemap must be a list of layers")
        layers = []
    statuses, rows = {}, {}
    if layers:
        if assets is None or assets_dir is None:
            add("error", "basemap", "basemap layers need assets.json (assets and assets_dir)")
        else:
            statuses, aiss = TL.check_assets(assets, assets_dir, check_files=True)
            rows = {a.get("id"): a for a in assets.get("assets", []) if isinstance(a, dict)}
            for x in aiss:
                if x["level"] == "error" and x.get("asset") in {l.get("asset") for l in layers if isinstance(l, dict)}:
                    add("error", "asset", f"{x.get('asset')}: {x['message']}", x.get("asset"))
    seen = set()
    for l in layers:
        if not isinstance(l, dict) or set(l) - {"id", "asset", "role", "show"} or not {"id", "asset", "role"} <= set(l):
            add("error", "schema", "a basemap layer is {id, asset, role, show}")
            continue
        lid = l["id"]
        if not (isinstance(lid, str) and ID_RE.fullmatch(lid)) or lid in seen:
            add("error", "bad_id", f"basemap layer id {lid!r} is invalid or repeated")
            continue
        seen.add(lid)
        role = l["role"]
        if role not in ROLES:
            add("error", "basemap", f"role must be one of {', '.join(ROLES)}", lid)
            continue
        lshow = l.get("show", True)
        if not isinstance(lshow, bool):
            add("error", "schema", "show must be true or false", lid)
            lshow = True
        row = rows.get(l["asset"])
        if row is None:
            if assets is not None:
                add("error", "asset", f"asset {l['asset']!r} is not in assets.json", lid)
            continue
        if row.get("kind") != "map":
            add("error", "asset", f"asset {l['asset']!r} is a {row.get('kind')!r} asset, a basemap needs kind 'map'", lid)
            continue
        if statuses.get(l["asset"]) != "verified":
            add("error" if mode == "final" else "warning", "unverified_asset",
                f"asset {l['asset']!r} is not verified (licence / file / sha256)", lid)
        try:
            gd = GD.read_geojson(Path(assets_dir) / row["local_path"])
        except (GD.GeoDataError, TypeError, KeyError) as ex:
            add("error", "geojson", str(ex), lid)
            continue
        for x in gd["issues"]:
            add(x["level"], x["code"], x["message"], lid)
        kinds = {"polygon" if f["type"] in ("Polygon", "MultiPolygon") else "line" for f in gd["features"]}
        wrong = kinds - set(ROLES[role])
        if wrong:
            add("error", "basemap", f"a {role} layer takes {' / '.join(ROLES[role])} geometry, the file has {', '.join(sorted(wrong))}", lid)
            continue
        out["basemap"].append({"id": lid, "asset": l["asset"], "role": role, "show": lshow, "status": statuses.get(l["asset"]),
                               "attribution": row.get("attribution"),
                               "fill": colors[role] if role in ("land", "lakes") else None,          # areas are filled,
                               "stroke": None if role in ("land", "lakes") else colors[role],       # lines are stroked
                               "width": None if role in ("land", "lakes") else widths[role],
                               "features": gd["features"], "features_count": gd["features_count"], "positions": gd["positions"],
                               "bbox": gd["bbox"], "antimeridian_segments": gd["antimeridian_segments"]})
    # ---- camera (M2c): in the plan's pixels; a point on the seam is framed at its first marker position
    out["camera"] = CAM.resolve_camera(scene.get("camera"), plan, {p["id"]: (p["x"][0], p["y"]) for p in geometry["points"]}, add)
    # ---- animation (M2d): over the resolved routes / points / areas, in plan pixels
    out["animation"] = AN.resolve_animation(scene.get("animation"), plan, out, add)
    # ---- labels (M2f): in screen space, after the camera and the animation they read
    out["labels"] = LB.resolve_labels(scene.get("labels"), out, plan, metrics, mode, add)
    n_err = sum(1 for x in issues if x["level"] == "error")
    n_warn = sum(1 for x in issues if x["level"] == "warning")
    out["qc"] = {"status": "FAIL" if n_err else "WARN" if n_warn else "OK", "errors": n_err, "warnings": n_warn,
                 "info": sum(1 for x in issues if x["level"] == "info"), "issues": issues}
    return out
