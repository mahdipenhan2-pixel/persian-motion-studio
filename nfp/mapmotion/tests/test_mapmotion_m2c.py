#!/usr/bin/env python3
"""M2c - Map Motion camera: zoom and pan over the plan's map (scene.json "camera"), one deterministic state per video
frame. Checked by properties, not by re-running the formulas: a centred place is at the middle of the screen, a fitted
box fills the frame inside its padding, the zoom moves evenly (linear in log zoom), the matrix and to_screen agree.
Offline, nothing written. SYNTHETIC data.

  python3 nfp/mapmotion/tests/test_mapmotion_m2c.py
"""
import datetime
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import camera as CAM            # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402
from test_mapmotion_m1 import mapdoc, LDOC     # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def errs(sp):
    return [i for i in sp["qc"]["issues"] if i["level"] == "error"]


def main():
    plan = M.build(mapdoc(), LDOC, today=TODAY)
    geo = M.geometry(plan)
    W, H = plan["frame"]["width"], plan["frame"]["height"]
    w0, w1 = plan["window"]["start"], plan["window"]["end"]
    pts = {p["id"]: p for p in plan["points"]}
    pid = [p["id"] for p in plan["points"]]
    scene = {"schema": "nfp.mapmotion.scene/1", "id": "cam-scene", "map": plan["map"]}

    def run(cam, **extra):
        return M.resolve(dict(scene, camera=cam, **extra), plan, geo)

    print("== no camera: the plan's full frame")
    sp = M.resolve(scene, plan, geo)
    c = sp["camera"]
    check(len(c["frames"]) == w1 - w0 and c["frames"][0]["frame"] == w0 and c["frames"][-1]["frame"] == w1 - 1,
          f"one camera state per video frame of the window ({w0}..{w1 - 1})")
    check(all(f["zoom"] == 1 and f["cx"] == W / 2 and f["cy"] == H / 2 and f["matrix"] == [1, 0, 0, 1, 0, 0] for f in c["frames"]),
          "zoom 1 at the frame centre, identity matrix, every frame")

    print("\n== views")
    p0 = pts[pid[0]]
    sp = run({"keyframes": [{"frame": w0, "view": {"center": {"lat": p0["lat"], "lon": p0["lon"]}, "zoom": 6}}]})
    st = sp["camera"]["frames"][0]
    X, Y = CAM.to_screen(st, plan["frame"], p0["x"], p0["y"])
    check(not errs(sp) and abs(X - W / 2) < 1e-3 * 6 and abs(Y - H / 2) < 1e-3 * 6 and st["zoom"] == 6,      # plan x has 3 decimals
          f"center view: the place ({p0['lat']}, {p0['lon']}) is at the middle of the screen at zoom 6 ({X:.4f}, {Y:.4f})")
    vb = plan["viewport"]["bounds"]
    cy_, cx_, hy, hx = (vb["north"] + vb["south"]) / 2, (vb["west"] + vb["east"]) / 2, (vb["north"] - vb["south"]) * 0.2, (vb["east"] - vb["west"]) * 0.2
    box = {"north": cy_ + hy, "south": cy_ - hy, "west": cx_ - hx, "east": cx_ + hx}              # the central 40 % of the map
    for pad in (0, 40, 200):
        sp = run({"keyframes": [{"frame": w0, "view": {"bounds": box, "pad_px": pad}}]})
        st = sp["camera"]["frames"][0]
        pj = M.projection_from_plan(plan)
        corners = [CAM.to_screen(st, plan["frame"], *pj.project(la, lo)) for la in (box["north"], box["south"]) for lo in (box["west"], box["east"])]
        xs, ys = [c_[0] for c_ in corners], [c_[1] for c_ in corners]
        tl = 1e-3 * st["zoom"]
        inside = min(xs) >= pad - tl and max(xs) <= W - pad + tl and min(ys) >= pad - tl and max(ys) <= H - pad + tl
        touches = abs(min(xs) - pad) < tl or abs(min(ys) - pad) < tl
        check(not errs(sp) and inside and touches,
              f"bounds view, pad {pad}: the box fills the frame inside the padding, touching it on one side (zoom {st['zoom']:.4f})")
    sp = run({"keyframes": [{"frame": w0, "view": {"points": pid[:3], "pad_px": 60}}]})
    st = sp["camera"]["frames"][0]
    sc = [CAM.to_screen(st, plan["frame"], pts[i]["x"], pts[i]["y"]) for i in pid[:3]]
    check(not errs(sp) and all(60 - 1e-3 <= x <= W - 60 + 1e-3 and 60 - 1e-3 <= y <= H - 60 + 1e-3 for x, y in sc),
          f"points view: all three markers inside the frame with 60 px kept free (zoom {st['zoom']:.4f})")
    sp = run({"keyframes": [{"frame": w0, "view": {"points": pid[:1], "zoom": 8}}]})
    st = sp["camera"]["frames"][0]
    check(not errs(sp) and st["zoom"] == 8 and abs(CAM.to_screen(st, plan["frame"], pts[pid[0]]["x"], pts[pid[0]]["y"])[0] - W / 2) < 1e-3,
          "a single point with a zoom: centred at that zoom")
    sp = run({"keyframes": [{"frame": w0, "view": {"full": True}}]})
    check(sp["camera"]["frames"][0]["matrix"] == [1, 0, 0, 1, 0, 0], "full view = identity")

    print("\n== movement between keyframes")
    a, b = 60, 180
    cam = {"keyframes": [{"frame": a, "view": {"full": True}},
                         {"frame": b, "view": {"center": {"lat": p0["lat"], "lon": p0["lon"]}, "zoom": 16}, "ease": "linear"}]}
    fr = {f["frame"]: f for f in run(cam)["camera"]["frames"]}
    check(all(fr[f] == {**fr[a], "frame": f} for f in range(w0, a)) and all(fr[f] == {**fr[b], "frame": f} for f in range(b, w1)),
          "before the first keyframe the first view holds, after the last the last one")
    logs = [math.log(fr[f]["zoom"]) for f in range(a, b + 1)]
    steps = [y - x for x, y in zip(logs, logs[1:])]
    check(max(steps) - min(steps) < 1e-4 and abs(fr[(a + b) // 2]["zoom"] - 4.0) < 1e-3,
          f"linear ease: the zoom grows evenly (equal steps of log zoom; half way: zoom {fr[(a + b) // 2]['zoom']} = sqrt(16))")
    cxs = [fr[f]["cx"] for f in range(a, b + 1)]
    d = [y - x for x, y in zip(cxs, cxs[1:])]
    check(max(d) - min(d) < 1e-4, "linear ease: the centre moves evenly")
    for name, vals in (("in", (0.0, 0.0625, 0.25, 1.0)), ("out", (0.0, 0.4375, 0.75, 1.0)), ("in-out", (0.0, 0.125, 0.5, 1.0)), ("linear", (0.0, 0.25, 0.5, 1.0))):
        check(all(abs(CAM.ease(name, t) - v) < 1e-12 for t, v in zip((0, 0.25, 0.5, 1), vals)), f"ease {name}: exact values at 0, 1/4, 1/2, 1")
    cam_io = {"keyframes": [cam["keyframes"][0], dict(cam["keyframes"][1], ease="in-out")]}
    fr2 = {f["frame"]: f for f in run(cam_io)["camera"]["frames"]}
    zs = [fr2[f]["zoom"] for f in range(a, b + 1)]
    check(all(y >= x for x, y in zip(zs, zs[1:])) and (zs[1] - zs[0]) < (zs[61] - zs[60]) and abs(fr2[(a + b) // 2]["zoom"] - 4.0) < 1e-3,
          "in-out: starts and ends slowly, monotonic, half way at the geometric mean")
    check(fr2[a]["zoom"] == 1 and fr2[b]["zoom"] == 16, "keyframe frames hit their views exactly")
    for f in (w0, a + 7, b - 3, w1 - 1):
        st = fr2[f]
        m = st["matrix"]
        x, y = pts[pid[1]]["x"], pts[pid[1]]["y"]
        X1, Y1 = CAM.to_screen(st, plan["frame"], x, y)
        check(abs(m[0] * x + m[4] - X1) < 1e-3 and abs(m[3] * y + m[5] - Y1) < 1e-3 and m[1] == 0 and m[2] == 0,
              f"frame {f}: the matrix and to_screen agree")
    j1 = json.dumps(run(cam_io)["camera"], sort_keys=True)
    check(j1 == json.dumps(run(cam_io)["camera"], sort_keys=True), "deterministic: the same table twice")

    print("\n== errors and warnings")
    bad = [({"keyframes": []}, "no keyframe"), ({"frames": []}, "an unknown camera key"), ({"keyframes": [{"frame": w0 - 1, "view": {"full": True}}]}, "a frame before the window"),
           ({"keyframes": [{"frame": w1, "view": {"full": True}}]}, "a frame at the window end (exclusive)"),
           ({"keyframes": [{"frame": True, "view": {"full": True}}]}, "a bool frame"),
           ({"keyframes": [{"frame": 60, "view": {"full": True}}, {"frame": 60, "view": {"full": True}}]}, "frames not increasing"),
           ({"keyframes": [{"frame": 60, "view": {"full": True}, "ease": "bounce"}]}, "an unknown ease"),
           ({"keyframes": [{"frame": 60, "view": {}}]}, "an empty view"),
           ({"keyframes": [{"frame": 60, "view": {"full": True, "center": {"lat": 0, "lon": 0}}}]}, "two view kinds"),
           ({"keyframes": [{"frame": 60, "view": {"center": {"lat": 95, "lon": 0}, "zoom": 2}}]}, "a center at lat 95"),
           ({"keyframes": [{"frame": 60, "view": {"center": {"lat": 1, "lon": 1}}}]}, "a center without zoom"),
           ({"keyframes": [{"frame": 60, "view": {"center": {"lat": 1, "lon": 1}, "zoom": 41}}]}, "zoom 41 > max_zoom 40"),
           ({"keyframes": [{"frame": 60, "view": {"center": {"lat": 1, "lon": 1}, "zoom": 0.5}}]}, "zoom 0.5"),
           ({"max_zoom": 65, "keyframes": [{"frame": 60, "view": {"full": True}}]}, "max_zoom 65"),
           ({"keyframes": [{"frame": 60, "view": {"bounds": {"north": 10.001, "south": 10.0, "west": 20.0, "east": 20.001}}}]}, "a box needing zoom > 40 (not clamped)"),
           ({"keyframes": [{"frame": 60, "view": {"bounds": {"north": 11, "south": 10, "west": 20, "east": 21}, "pad_px": 540}}]}, "pad_px of half the frame"),
           ({"keyframes": [{"frame": 60, "view": {"points": ["nope"]}}]}, "an unknown point"),
           ({"keyframes": [{"frame": 60, "view": {"points": pid[:1]}}]}, "a single point without zoom"),
           ({"keyframes": [{"frame": 60, "view": {"points": pid[:2], "zoom": 3}}]}, "a zoom with several points"),
           ({"keyframes": [{"frame": 60, "view": {"full": True}, "speed": 2}]}, "an unknown keyframe key")]
    for cam_, what in bad:
        sp = run(cam_)
        check(any(i["code"] == "camera" for i in errs(sp)) and sp["qc"]["status"] == "FAIL", f"refused: {what}")
    sp = run({"keyframes": [{"frame": 60, "view": {"bounds": box}}]})
    zfit = sp["camera"]["frames"][0]["zoom"]
    sp2 = run({"max_zoom": 2, "keyframes": [{"frame": 60, "view": {"bounds": box}}]})
    check(zfit > 2 and bool(errs(sp2)), f"max_zoom is enforced for fitted views too (fit zoom {zfit:.2f} > max_zoom 2: error)")
    big = {"north": vb["north"] + 5, "south": vb["south"] - 5, "west": vb["west"] - 5, "east": vb["east"] + 5}
    sp = run({"keyframes": [{"frame": 60, "view": {"bounds": big}}]})
    check(sp["camera"]["frames"][0]["zoom"] == 1 and any(i["code"] == "view_outside_map" for i in sp["qc"]["issues"]) and not errs(sp),
          "a box larger than the whole map: zoom 1 and a view_outside_map warning (not an error)")
    sp = run({"keyframes": [{"frame": 60, "view": {"center": {"lat": p0["lat"], "lon": p0["lon"]}, "zoom": 1.2}}]})
    check(any(i["code"] == "view_outside_map" for i in sp["qc"]["issues"]) and not errs(sp), "a view past the map's edge: warning view_outside_map")

    print("\n== the whole-world map and its seam")
    wl = ldoc(loc("w1", 10.5, 170.5), loc("w2", 12.5, -170.5), loc("w3", 0.5, 180.0))
    md = {"schema": "nfp.mapmotion/1", "id": "world-map", "mode": "draft", "window": {"start": 0, "end": 120}, "labels": {"lang": "en", "year": None},
          "viewport": {"bounds": {"north": 80, "south": -80, "west": -180, "east": 180}}, "areas": [], "routes": [],
          "points": [{"id": i, "location": i, "start": 0, "end": 120, "label": False} for i in ("w1", "w2", "w3")]}
    wp = M.build(md, wl, today=TODAY)
    wg = M.geometry(wp)
    ws = {"schema": "nfp.mapmotion.scene/1", "id": "world-scene", "map": "world-map"}
    sp = M.resolve(dict(ws, camera={"keyframes": [{"frame": 0, "view": {"bounds": {"north": 20, "south": 0, "west": 160, "east": -160}}}]}), wp, wg)
    check(any("seam" in i["message"] for i in errs(sp)), "a box over the whole-world map's seam (160E..160W): refused with a clear message")
    sp = M.resolve(dict(ws, camera={"keyframes": [{"frame": 0, "view": {"bounds": {"north": 20, "south": 0, "west": 150, "east": 179.9}}}]}), wp, wg)
    check(not errs(sp), "a box up to the seam on one side: accepted")
    sp = M.resolve(dict(ws, camera={"keyframes": [{"frame": 0, "view": {"points": ["w3"], "zoom": 4}}]}), wp, wg)
    st = sp["camera"]["frames"][0]
    check(not errs(sp) and abs(st["cx"] - wg["points"][2]["x"][0]) < 1e-3, "a point on the seam is framed at its first marker position (documented)")

    print("\n== boundaries and compatibility")
    t = (NFP / "mapmotion" / "camera.py").read_text(encoding="utf-8")
    mods = {a_ or b_ for a_, b_ in re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", t, re.M)}
    check(mods <= {"math", ".geometry", ".seam"}, f"camera.py imports only the standard library and mapmotion {sorted(mods)}")
    check(not re.search(r"urllib|socket|subprocess|write_text|open\(|date\.today|import random|random\.", t), "camera.py: no network, files, clock, randomness")
    sp_old_keys = {"schema", "scene", "map", "mode", "frame", "style", "graticule", "basemap", "areas", "routes", "points", "qc"}
    sp = M.resolve(scene, plan, geo)
    check(set(sp) >= sp_old_keys | {"camera"} and sp["schema"] == "nfp.mapmotion.sceneplan/1", "the scene plan keeps every M2b field and adds 'camera'")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    check(all(k in rd for k in ("M2c", "camera", "max_zoom", "view_outside_map", "in-out")), "README documents M2c")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2c TESTS PASSED" if not f else "MAP MOTION M2c TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
