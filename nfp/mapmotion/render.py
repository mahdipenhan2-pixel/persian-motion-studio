"""NFP Map Motion - M2e: SVG rendering of a scene plan (M2b), with its camera (M2c) and animation (M2d). Standard
library. Returns strings; writes no file (the caller saves them).

  render_svg(scene_plan, plan, frame=None, basemap=None, font_css=None) -> one SVG document (font_css: the @font-face
      rules of tools.measure.font_face_css, embedded so the labels use the same local fonts they were measured with)
      frame = a video frame of the window: that frame's camera and animation state; None = the static map (whole frame,
      zoom 1, every shown element fully drawn, route markers at their last stop)
  basemap_paths(scene_plan, plan) -> the projected, cut, clipped, simplified basemap (clip.py), to pass to render_svg
      when drawing many frames (it does not change from frame to frame)
  preview_html(scene_plan, plan, step=10) -> an HTML page: the static map and every step-th frame, with a slider

Layers, bottom to top: background; the map group (basemap fills, then lines; graticule; areas; uncertainty ellipses;
routes) under the camera's matrix; then, in SCREEN space (so they keep their size), point markers and route markers;
then the basemap attribution. Lines keep their width in screen pixels (vector-effect: non-scaling-stroke). A route is
drawn up to its animation share of each piece's pixel length, cut in Python (no dash trick), so the SVG shows exactly
the frame's state. Nothing is invented here: positions come from the plan (M1), the geometry (M2a), the scene plan
(M2b), the camera (M2c) and the animation (M2d); this module only draws them.
Deterministic: same input, same bytes (numbers with at most 3 decimals; fixed element order).
"""
import math

from . import camera as CAM
from . import clip as CL
from . import icons as IC
from .geometry import projection_from_plan
from .svg import el, num, path_d, text

NS = "http://www.w3.org/2000/svg"


def basemap_paths(sp, plan):
    proj = projection_from_plan(plan)
    zmax = max([f["zoom"] for f in sp["camera"]["frames"]] + [1.0])
    eps = 0.25 / zmax                                     # under half a screen pixel at the largest zoom used
    return [{"id": l["id"], "role": l["role"], "show": l["show"], "fill": l["fill"], "stroke": l["stroke"], "width": l["width"],
             "attribution": l["attribution"], "shapes": CL.project_layer(l["features"], proj, sp["frame"], eps=eps)}
            for l in sp["basemap"]]


def _prefix(pts, share):
    """The first `share` (0..1) of a polyline's pixel length."""
    if share >= 1:
        return list((p["x"], p["y"]) for p in pts)
    if share <= 0 or len(pts) < 2:
        return []
    lens = [math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(pts, pts[1:])]
    goal, run, out = share * sum(lens), 0.0, [(pts[0]["x"], pts[0]["y"])]
    for (a, b), L in zip(zip(pts, pts[1:]), lens):
        if run + L >= goal:
            t = 0.0 if L == 0 else (goal - run) / L
            out.append((a["x"] + (b["x"] - a["x"]) * t, a["y"] + (b["y"] - a["y"]) * t))
            return out
        out.append((b["x"], b["y"]))
        run += L
    return out


def _graticule(sp, plan, proj):
    g = sp["graticule"]
    if not g["show"]:
        return ""
    step = g["step_deg"]
    west, span = proj.bounds["west"], proj.lon_span
    xl, xr = proj.x_of_u(0), proj.x_of_u(span)
    yt = proj.y0
    yb = proj.y0 + proj.lat_span * proj.k
    lines = []
    u = (math.ceil(west / step) * step - west)
    while u <= span + 1e-9:
        x = proj.x_of_u(u)
        lines.append([(x, yt), (x, yb)])
        u += step
    lat = math.floor(proj.bounds["north"] / step) * step
    while lat >= proj.bounds["south"] - 1e-9:
        y = proj.y0 + (proj.bounds["north"] - lat) * proj.k
        lines.append([(xl, y), (xr, y)])
        lat -= step
    return el("path", (("d", path_d(lines, False)), ("fill", "none"), ("stroke", g["color"]), ("stroke-width", g["width"]),
                       ("vector-effect", "non-scaling-stroke")))


def render_svg(sp, plan, frame=None, basemap=None, font_css=None):
    W, H = sp["frame"]["width"], sp["frame"]["height"]
    w0 = plan["window"]["start"]
    if frame is None:
        state = {"cx": W / 2, "cy": H / 2, "zoom": 1.0}
        anim = None
    else:
        if not (isinstance(frame, int) and not isinstance(frame, bool) and w0 <= frame < plan["window"]["end"]):
            raise ValueError(f"frame must be a video frame of the window {w0}..{plan['window']['end'] - 1}")
        cf = sp["camera"]["frames"][frame - w0]
        state = {"cx": cf["cx"], "cy": cf["cy"], "zoom": cf["zoom"]}
        anim = sp["animation"]["frames"][frame - w0]
    if basemap is None:
        basemap = basemap_paths(sp, plan)
    c = sp["style"]["colors"]
    m = CAM.matrix(state, sp["frame"])
    dyn, heads = layer_map_dynamic(sp, frame, anim)
    body = [el("rect", (("width", W), ("height", H), ("fill", c["background"]))),
            el("g", (("id", "map"), ("transform", "matrix(" + " ".join(num(v) for v in m) + ")")), layer_map_static(sp, plan, basemap) + dyn)]
    markers, labels = layer_screen(sp, state, frame, anim, heads)
    body.append(el("g", (("id", "markers"),), markers))
    if labels is not None:
        body.append(el("g", (("id", "labels"),), labels))
    body.append(attribution(sp, basemap))
    head = f'<svg xmlns="{NS}" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    desc = el("desc", (), text(f"NFP Map Motion - scene {sp['scene']} - map {sp['map']} - " + ("static" if frame is None else f"frame {frame}")))
    defs = el("defs", (), el("style", (), font_css)) if font_css else ""
    return head + desc + defs + "".join(body) + "</svg>"


# ---- the layers, shared by render_svg (one SVG per frame) and filmclip (the Film page): one drawing, two hosts

NSS = ("vector-effect", "non-scaling-stroke")


def layer_map_static(sp, plan, basemap):
    """What never changes from frame to frame, in plan pixels (under the camera): basemap fills, lines, graticule."""
    proj = projection_from_plan(plan)
    mp = []
    for l in basemap:                                     # fills first, then lines: coasts stay on top of land
        if l["show"] and l["fill"]:
            polys = [p for s in l["shapes"] if s["kind"] == "polygon" for p in s["paths"]]
            if polys:
                mp.append(el("path", (("d", path_d(polys, True)), ("fill", l["fill"]), ("fill-rule", "evenodd"), ("data-layer", l["id"]))))
    for l in basemap:
        if l["show"] and l["stroke"]:
            ps = [p + p[:1] if s["kind"] == "polygon" else p for s in l["shapes"] for p in s["paths"]]
            if ps:
                mp.append(el("path", (("d", path_d(ps, False)), ("fill", "none"), ("stroke", l["stroke"]), ("stroke-width", l["width"]),
                                      ("stroke-linejoin", "round"), NSS, ("data-layer", l["id"]))))
    mp.append(_graticule(sp, plan, proj))
    return "".join(mp)


def _opacity(anim, frame, group, eid):
    return 1.0 if frame is None else next(x["opacity"] for x in anim[group] if x["id"] == eid)


def layer_map_dynamic(sp, frame, anim):
    """What a frame changes in plan pixels (under the camera): areas, uncertainty ellipses, routes drawn so far.
    Returns (svg, heads): heads = the route markers to draw in screen space."""
    mp = []
    for a in sp["areas"]:
        o = _opacity(anim, frame, "areas", a["id"]) if a["show"] else 0.0
        if o <= 0:
            continue
        sh = a["shape"]
        common = (("fill", a["fill"]), ("fill-opacity", a["opacity"]), ("stroke", a["stroke"]), ("stroke-width", a["width"]), NSS,
                  ("opacity", None if o >= 1 else o), ("data-area", a["id"]))
        if sh["type"] == "rect":
            mp.append(el("rect", (("x", sh["x"]), ("y", sh["y"]), ("width", sh["w"]), ("height", sh["h"])) + common))
        else:
            mp.append(el("ellipse", (("cx", sh["cx"]), ("cy", sh["cy"]), ("rx", sh["rx"]), ("ry", sh["ry"])) + common))
    for p in sp["points"]:
        u = p["uncertainty"]
        o = _opacity(anim, frame, "points", p["id"]) if p["show"] else 0.0
        if u and u["show"] and o > 0:
            for x in p["x"]:
                mp.append(el("ellipse", (("cx", x), ("cy", p["y"]), ("rx", u["rx"]), ("ry", u["ry"]), ("fill", u["color"]),
                                         ("fill-opacity", u["opacity"] * o), ("stroke", "none"))))
    heads = []
    for k, r in enumerate(sp["routes"]):
        if not r["show"]:
            continue
        ra = None if anim is None else anim["routes"][k]
        shares = [1.0] * len(r["pieces"]) if ra is None else ra["pieces"]
        drawn = [q for pc, s in zip(r["pieces"], shares) for q in [_prefix(pc, s)] if len(q) >= 2]
        if drawn:
            mp.append(el("path", (("d", path_d(drawn, False)), ("fill", "none"), ("stroke", r["color"]), ("stroke-width", r["width"]),
                                  ("stroke-linecap", "round"), ("stroke-linejoin", "round"),
                                  ("stroke-dasharray", " ".join(num(d) for d in r["dash"]) if r["dash"] else None), NSS, ("data-route", r["id"]))))
        marker = next(x["marker"] for x in sp["animation"]["routes"] if x["id"] == r["id"])
        if marker != "none":
            if ra is not None:
                h = ra["head"]
            else:                                         # static: at the last stop, heading of the last segment
                pc = r["pieces"][-1]
                a_, b_ = pc[-2], pc[-1]
                h = {"x": b_["x"], "y": b_["y"], "heading_deg": math.degrees(math.atan2(b_["y"] - a_["y"], b_["x"] - a_["x"]))}
            if h:
                heads.append((marker, h, r))
    return "".join(mp), heads


def layer_screen(sp, state, frame, anim, heads):
    """Screen-space content of a frame: (markers svg, labels svg or None when the scene plan has no labels block)."""
    w0 = sp["camera"]["frames"][0]["frame"]               # the window's first frame (one camera state per frame)
    mk = []
    for p in sp["points"]:
        o = _opacity(anim, frame, "points", p["id"]) if p["show"] else 0.0
        for x in p["x"]:
            X, Y = CAM.to_screen(state, sp["frame"], x, p["y"])
            mk.append(IC.marker(p["marker"], X, Y, p["size"], p["color"], p["stroke"], o))
    for marker, h, r in heads:
        X, Y = CAM.to_screen(state, sp["frame"], h["x"], h["y"])
        mk.append(IC.marker(marker, X, Y, max(18.0, 5 * r["width"]), r["color"], sp["style"]["colors"]["point_stroke"], 1.0, h["heading_deg"]))
    lab = sp.get("labels")
    if not lab:
        return "".join(mk), None
    ls = lab["style"]
    rows = lab["static"] if frame is None else lab["frames"][frame - w0]["labels"]
    tx = []
    for x in rows:
        if not x["shown"]:
            continue
        t = lab["texts"][x["id"]]
        tx.append(el("text", (("x", x["x"]), ("y", x["y"]), ("text-anchor", "middle"), ("direction", t["direction"]),
                              ("font-family", ls["font_family"]), ("font-size", ls["size"]), ("font-weight", ls["weight"]),
                              ("fill", ls["color"]), ("stroke", ls["halo_color"] if ls["halo_width"] > 0 else None),
                              ("stroke-width", ls["halo_width"] if ls["halo_width"] > 0 else None), ("stroke-linejoin", "round"),
                              ("paint-order", "stroke"), ("opacity", None if x.get("opacity", 1) >= 1 else x["opacity"]),
                              ("data-label", x["id"]), ("data-pos", x["pos"])), text(t["text"])))
    return "".join(mk), "".join(tx)


def attribution(sp, basemap):
    W, H = sp["frame"]["width"], sp["frame"]["height"]
    attr = sorted({l["attribution"] for l in basemap if l["show"] and l["attribution"]})
    if not attr:
        return ""
    return el("text", (("x", W - 12), ("y", H - 12), ("text-anchor", "end"), ("font-size", 14), ("font-family", "sans-serif"),
                       ("fill", sp["style"]["colors"]["label"]), ("fill-opacity", 0.7)), text(" · ".join(attr)))


def preview_html(sp, plan, step=10, font_css=None):
    """A self-contained page to look at the result: the static map and every step-th frame (and the last), a slider."""
    if not (isinstance(step, int) and not isinstance(step, bool) and step >= 1):
        raise ValueError("step must be a whole number of frames >= 1")
    bm = basemap_paths(sp, plan)
    w0, w1 = plan["window"]["start"], plan["window"]["end"]
    frames = list(range(w0, w1, step))
    if frames[-1] != w1 - 1:
        frames.append(w1 - 1)
    shots = [("static", render_svg(sp, plan, None, bm))] + [(str(f), render_svg(sp, plan, f, bm)) for f in frames]
    head_css = f"<style>{font_css}</style>" if font_css else ""      # the fonts once for the page, not in every frame
    W, H = sp["frame"]["width"], sp["frame"]["height"]
    items = "".join(f'<div class="shot" data-i="{i}" data-label="{text(lbl)}"{"" if i == 0 else " hidden"}>{svg}</div>'
                    for i, (lbl, svg) in enumerate(shots))
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Map Motion preview</title>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" + head_css +
            "<style>body{margin:0;background:#202326;color:#e8edf1;font:14px sans-serif}"
            f".bar{{padding:8px 16px;display:flex;gap:12px;align-items:center}}.shot svg{{width:100%;height:auto;max-width:{W}px;display:block}}"
            "input{flex:1}</style></head><body>"
            f"<div class=\"bar\"><span>{text(sp['scene'])} &middot; {len(shots) - 1} frames (step {step})</span>"
            f"<input id=\"s\" type=\"range\" min=\"0\" max=\"{len(shots) - 1}\" value=\"0\"><span id=\"l\">static</span></div>"
            f"{items}<script>const s=document.getElementById('s'),l=document.getElementById('l'),"
            "d=[...document.querySelectorAll('.shot')];s.oninput=()=>{d.forEach(x=>x.hidden=x.dataset.i!==s.value);"
            "l.textContent=d[+s.value].dataset.label;};</script></body></html>")
