"""NFP Map Motion - M2c: the camera - zoom and pan over the plan's map, frame by frame. Standard library. Data only.

The camera works in the plan's own pixels (its fixed projection: M1's frame, M2a's geometry). It does not reproject:
zooming in is a 2D scale about a centre, so every coordinate of the plan, the geometry and the scene plan stays valid.
  state = (cx, cy, zoom): the point of the map (plan pixels) at the middle of the screen, and the scale (1 = the plan's
  whole frame). A map point (x, y) is shown at
      X = W/2 + zoom * (x - cx),   Y = H/2 + zoom * (y - cy)          (the matrix [zoom, 0, 0, zoom, tx, ty], SVG order)
  Line widths and marker sizes are meant in SCREEN pixels: a renderer draws them unscaled (it divides by zoom).

scene.json "camera" (optional; without it the camera is the plan's full frame, zoom 1, at every frame):
  {"max_zoom": 40, "keyframes": [
     {"frame": 30,  "view": {"full": true}},
     {"frame": 90,  "view": {"center": {"lat": 35.7, "lon": 51.4}, "zoom": 6}, "ease": "in-out"},
     {"frame": 150, "view": {"bounds": {"north": 40, "south": 30, "west": 45, "east": 60}, "pad_px": 40}},
     {"frame": 210, "view": {"points": ["p1", "p2"], "pad_px": 80}}]}
  - frames are video frames inside the plan's window (as every element), strictly increasing; anchors are not taken
    here (whole frames only);
  - a view is exactly one of: full; center (lat / lon) + zoom; bounds (a geographic box, fitted to the 16:9 frame);
    points (plan point ids, their markers fitted; one point needs a zoom);
  - bounds / points accept pad_px (screen pixels kept free around the fitted box, >= 0, < half the frame);
  - zoom is within 1 .. max_zoom (max_zoom <= 64, default 40: beyond that a browser's single-precision transforms are
    no longer exact) - a fitted view that would need more is an error, never silently clamped;
  - a bounds box must lie on one side of the map's seam (a box over the seam would need both map edges at once).
Between two keyframes (frames f0 < f1) the move uses the ease of the LATER keyframe on t = (f - f0) / (f1 - f0):
  linear: t;  in: t^2;  out: 1 - (1 - t)^2;  in-out: 2 t^2 if t < 1/2 else 1 - 2 (1 - t)^2   (GSAP's power1 / quad)
  the centre moves linearly with the eased value, the zoom geometrically (zoom0^(1-e) * zoom1^e: an even zoom).
Before the first keyframe the camera holds the first view, after the last the last one.
QC: "view_outside_map" (warning) when a keyframe's view shows beyond the plan's frame (empty background there).
The table holds one state per frame of the window, rounded to 6 decimals; it depends only on its inputs.
"""
import math

from .geometry import projection_from_plan
from .seam import marker_us

EASES = ("linear", "in", "out", "in-out")
DEFAULT_MAX_ZOOM = 40.0
HARD_MAX_ZOOM = 64.0


def ease(name, t):
    t = min(1.0, max(0.0, t))
    if name == "in":
        return t * t
    if name == "out":
        return 1 - (1 - t) * (1 - t)
    if name == "in-out":
        return 2 * t * t if t < 0.5 else 1 - 2 * (1 - t) * (1 - t)
    return t


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def matrix(state, frame):
    """SVG matrix(a, b, c, d, e, f) that shows plan pixels at screen pixels for a camera state."""
    W, H = frame["width"], frame["height"]
    z = state["zoom"]
    return [z, 0.0, 0.0, z, W / 2 - z * state["cx"], H / 2 - z * state["cy"]]


def to_screen(state, frame, x, y):
    W, H = frame["width"], frame["height"]
    return W / 2 + state["zoom"] * (x - state["cx"]), H / 2 + state["zoom"] * (y - state["cy"])


def visible(state, frame):
    """The plan-pixel rectangle the screen shows: {x, y, w, h}."""
    W, H, z = frame["width"], frame["height"], state["zoom"]
    return {"x": state["cx"] - W / (2 * z), "y": state["cy"] - H / (2 * z), "w": W / z, "h": H / z}


def state_at(keyframes, f):
    """Camera state at video frame f from resolved keyframes [{frame, cx, cy, zoom, ease}] (sorted)."""
    if f <= keyframes[0]["frame"]:
        k = keyframes[0]
        return {"cx": k["cx"], "cy": k["cy"], "zoom": k["zoom"]}
    for a, b in zip(keyframes, keyframes[1:]):
        if f < b["frame"]:
            e = ease(b["ease"], (f - a["frame"]) / (b["frame"] - a["frame"]))
            return {"cx": a["cx"] + (b["cx"] - a["cx"]) * e, "cy": a["cy"] + (b["cy"] - a["cy"]) * e,
                    "zoom": math.exp(math.log(a["zoom"]) * (1 - e) + math.log(b["zoom"]) * e)}
    k = keyframes[-1]
    return {"cx": k["cx"], "cy": k["cy"], "zoom": k["zoom"]}


def resolve_camera(cam, plan, points_xy, add):
    """The camera block of a scene plan. cam: the scene's "camera" (or None); points_xy: {point id: (x, y)} in plan
    pixels; add(level, code, message, element) records QC issues. Returns {max_zoom, keyframes, frames}."""
    frame = plan["frame"]
    W, H = frame["width"], frame["height"]
    w0, w1 = plan["window"]["start"], plan["window"]["end"]
    full = {"frame": w0, "cx": W / 2, "cy": H / 2, "zoom": 1.0, "ease": "linear"}
    if cam is None:
        kfs, max_zoom = [full], DEFAULT_MAX_ZOOM
    else:
        kfs, max_zoom = [], DEFAULT_MAX_ZOOM
        if not isinstance(cam, dict) or set(cam) - {"keyframes", "max_zoom"} or not isinstance(cam.get("keyframes"), list) \
                or not cam["keyframes"]:
            add("error", "camera", "camera must be {keyframes: [at least one], max_zoom}", None)
            cam = {"keyframes": []}
        mz = cam.get("max_zoom", DEFAULT_MAX_ZOOM)
        if not (_num(mz) and 1 <= mz <= HARD_MAX_ZOOM):
            add("error", "camera", f"max_zoom must be a number 1..{HARD_MAX_ZOOM:g}", None)
            mz = DEFAULT_MAX_ZOOM
        max_zoom = float(mz)
        proj = projection_from_plan(plan)
        last = None
        for n, k in enumerate(cam["keyframes"]):
            where = f"camera keyframe {n + 1}"
            if not isinstance(k, dict) or set(k) - {"frame", "view", "ease"} or not {"frame", "view"} <= set(k):
                add("error", "camera", f"{where} must be {{frame, view, ease}}", None)
                continue
            f = k["frame"]
            if not (_int(f) and w0 <= f < w1):
                add("error", "camera", f"{where}: frame must be a whole video frame in the window {w0}..{w1 - 1}", None)
                continue
            if last is not None and f <= last:
                add("error", "camera", f"{where}: frames must increase (frame {f} after {last})", None)
                continue
            ez = k.get("ease", "in-out")
            if ez not in EASES:
                add("error", "camera", f"{where}: ease must be one of {', '.join(EASES)}", None)
                continue
            st = _view(k["view"], where, proj, frame, points_xy, max_zoom, add)
            if st is None:
                continue
            r = visible(st, frame)
            if r["x"] < -1e-6 or r["y"] < -1e-6 or r["x"] + r["w"] > W + 1e-6 or r["y"] + r["h"] > H + 1e-6:
                add("warning", "view_outside_map", f"{where}: the view shows beyond the map's frame (empty background there)", None)
            kfs.append(dict(st, frame=f, ease=ez))
            last = f
        if not kfs:
            kfs = [full]
    rnd = lambda v: round(v + 0.0, 6)
    frames = []
    for f in range(w0, w1):
        s = state_at(kfs, f)
        frames.append({"frame": f, "cx": rnd(s["cx"]), "cy": rnd(s["cy"]), "zoom": rnd(s["zoom"]),
                       "matrix": [rnd(v) for v in matrix(s, frame)]})
    return {"max_zoom": max_zoom,
            "keyframes": [{"frame": k["frame"], "cx": rnd(k["cx"]), "cy": rnd(k["cy"]), "zoom": rnd(k["zoom"]), "ease": k["ease"]} for k in kfs],
            "frames": frames}


def _view(v, where, proj, frame, points_xy, max_zoom, add):
    W, H = frame["width"], frame["height"]
    kinds = [k for k in ("full", "center", "bounds", "points") if isinstance(v, dict) and k in v]
    if len(kinds) != 1:
        add("error", "camera", f"{where}: view must be exactly one of full / center / bounds / points", None)
        return None
    kind = kinds[0]
    allowed = {"full": {"full"}, "center": {"center", "zoom"}, "bounds": {"bounds", "pad_px"}, "points": {"points", "pad_px", "zoom"}}[kind]
    if set(v) - allowed:
        add("error", "camera", f"{where}: a {kind} view takes only {', '.join(sorted(allowed))}", None)
        return None
    if kind == "full":
        if v["full"] is not True:
            add("error", "camera", f"{where}: full must be true", None)
            return None
        return {"cx": W / 2, "cy": H / 2, "zoom": 1.0}
    if kind == "center":
        c, z = v["center"], v.get("zoom")
        if not (isinstance(c, dict) and set(c) == {"lat", "lon"} and _num(c["lat"]) and _num(c["lon"])
                and -90 <= c["lat"] <= 90 and -180 <= c["lon"] <= 180):
            add("error", "camera", f"{where}: center must be {{lat, lon}} (WGS84 degrees)", None)
            return None
        if not (_num(z) and 1 <= z <= max_zoom):
            add("error", "camera", f"{where}: zoom must be a number 1..{max_zoom:g}", None)
            return None
        x = proj.x_of_u(marker_us(proj, c["lat"], c["lon"])[0])
        y = proj.y0 + (proj.bounds["north"] - c["lat"]) * proj.k
        return {"cx": x, "cy": y, "zoom": float(z)}
    pad = v.get("pad_px", 0)
    if not (_num(pad) and 0 <= pad < min(W, H) / 2):
        add("error", "camera", f"{where}: pad_px must be a number of pixels 0..{min(W, H) / 2:g} (exclusive)", None)
        return None
    if kind == "bounds":
        b = v["bounds"]
        if not (isinstance(b, dict) and set(b) == {"north", "south", "east", "west"} and all(_num(b[k]) for k in b)
                and -90 <= b["south"] < b["north"] <= 90 and -180 <= b["west"] <= 180 and -180 <= b["east"] <= 180 and b["west"] != b["east"]):
            add("error", "camera", f"{where}: bounds must be {{north, south, east, west}} (south < north, west != east)", None)
            return None
        xw = proj.x_of_u(marker_us(proj, 0, b["west"])[0])
        xe = proj.x_of_u(marker_us(proj, 0, b["east"])[-1])
        if xe <= xw:
            add("error", "camera", f"{where}: the box crosses the map's seam: a view cannot show both map edges at once", None)
            return None
        yn = proj.y0 + (proj.bounds["north"] - b["north"]) * proj.k
        ys = proj.y0 + (proj.bounds["north"] - b["south"]) * proj.k
        x0, x1, y0, y1 = xw, xe, yn, ys
    else:
        ids = v["points"]
        if not (isinstance(ids, list) and ids and all(isinstance(i, str) for i in ids)):
            add("error", "camera", f"{where}: points must be a list of plan point ids", None)
            return None
        miss = [i for i in ids if i not in points_xy]
        if miss:
            add("error", "camera", f"{where}: the plan has no point {miss[0]!r}", None)
            return None
        xs = [points_xy[i][0] for i in ids]
        ys_ = [points_xy[i][1] for i in ids]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys_), max(ys_)
        if x1 - x0 < 1e-9 and y1 - y0 < 1e-9:
            z = v.get("zoom")
            if not (_num(z) and 1 <= z <= max_zoom):
                add("error", "camera", f"{where}: a single point needs a zoom 1..{max_zoom:g}", None)
                return None
            return {"cx": x0, "cy": y0, "zoom": float(z)}
        if "zoom" in v:
            add("error", "camera", f"{where}: zoom is fitted from the points; give zoom only for a single point", None)
            return None
    bw, bh = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    z = min((W - 2 * pad) / bw, (H - 2 * pad) / bh)
    if z > max_zoom + 1e-9:
        add("error", "camera", f"{where}: fitting needs zoom {z:.2f}, more than max_zoom {max_zoom:g} - widen the view or raise max_zoom", None)
        return None
    if z < 1 - 1e-9:
        add("warning", "view_outside_map", f"{where}: the box is larger than the map's frame: zoom 1 is used and part of it is cut", None)
        z = 1.0
    return {"cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "zoom": float(z)}
