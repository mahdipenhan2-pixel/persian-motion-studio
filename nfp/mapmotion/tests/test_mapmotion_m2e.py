#!/usr/bin/env python3
"""M2e - Map Motion SVG rendering (no browser here; see test_mapmotion_m2e_render.py for the real render): valid and
deterministic SVG, basemap projection / seam cutting / frame clipping / simplification checked by geometry (areas
conserved, parts on the drawn side, error of the simplification measured), routes and markers where M2a / M2c / M2d put
them. Offline. SYNTHETIC data; the GeoJSON files go to a temporary folder outside the project.

  python3 nfp/mapmotion/tests/test_mapmotion_m2e.py
"""
import math
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import camera as CAM            # noqa: E402
from mapmotion import clip as CL               # noqa: E402
from mapmotion import render as R              # noqa: E402
import m2e_fixture as FX                       # noqa: E402

RESULTS = []
NSP = "{http://www.w3.org/2000/svg}"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def area(p):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(p, p[1:] + p[:1]))) / 2


def parse_d(d):
    """[[(x, y), ...], ...] from M/L/Z path data written by svg.path_d."""
    out = []
    for part in re.findall(r"M[^M]*", d):
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", part)]
        out.append(list(zip(nums[0::2], nums[1::2])))
    return out


def plen(p):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(p, p[1:]))


def main():
    W = M.Equirectangular({"north": 80, "south": -80, "west": -180, "east": 180})
    fr = {"width": 1920, "height": 1080}
    kx, k = W.kx, W.k
    left, right = W.x_of_u(0), W.x_of_u(360)

    print("== basemap: projection, seam, frame, simplification (clip.py)")
    unsplit = [{"type": "Polygon", "coordinates": [[[170, 10], [-170, 10], [-170, 20], [170, 20], [170, 10]]]}]
    split = [{"type": "MultiPolygon", "coordinates": [[[[170, 10], [180, 10], [180, 20], [170, 20], [170, 10]]],
                                                      [[[-180, 10], [-170, 10], [-170, 20], [-180, 20], [-180, 10]]]]}]
    a, b = CL.project_layer(unsplit, W, fr, eps=0.01), CL.project_layer(split, W, fr, eps=0.01)
    norm = lambda o: sorted(tuple(sorted((round(x, 6), round(y, 6)) for x, y in p)) for s in o for p in s["paths"])
    check(norm(a) == norm(b), "a polygon over the antimeridian: unsplit (not RFC 7946) and split give the same drawing")
    pa = [p for s in a for p in s["paths"]]
    check(len(pa) == 2 and abs(sum(area(p) for p in pa) - 20 * 10 * kx * k) < 1e-6
          and all(left - 1e-9 <= x <= right + 1e-9 for p in pa for x, _ in p),
          f"cut into one part on each edge; total area conserved ({sum(area(p) for p in pa):.3f} = 20 x 10 degrees)")
    for lo0 in (-175.0, 100.0, 179.0):
        poly = [{"type": "Polygon", "coordinates": [[[lo0, 0], [lo0 + 8, 0], [lo0 + 8, 6], [lo0, 6], [lo0, 0]]]}]
        poly[0]["coordinates"][0] = [[((x + 180) % 360) - 180 if x > 180 else x, y] for x, y in poly[0]["coordinates"][0]]
        o = CL.project_layer(poly, W, fr, eps=0.01)
        check(abs(sum(area(p) for s in o for p in s["paths"]) - 8 * 6 * kx * k) < 1e-6, f"8 x 6 degree box from {lo0}: area conserved after cutting")
    ant = [{"type": "Polygon", "coordinates": [[[-180, -65], [-90, -70], [0, -66], [90, -72], [180, -65], [180, -90], [-180, -90], [-180, -65]]]}]
    o = CL.project_layer(ant, W, fr, eps=0.01)
    pp = [p for s in o for p in s["paths"]]
    ypole = W.y0 + (80 + 90) * k
    check(len(pp) == 1 and abs(min(x for x, _ in pp[0]) - left) < 1e-6 and abs(max(x for x, _ in pp[0]) - right) < 1e-6
          and abs(max(y for _, y in pp[0]) - ypole) < 1e-6, "a ring around the South Pole: one polygon, edge to edge, closed along the pole line")
    ring_pole = [{"type": "Polygon", "coordinates": [[[-180, -65], [-90, -70], [0, -66], [90, -72], [180, -65], [-180, -65]]]}]
    o2 = CL.project_layer(ring_pole, W, fr, eps=0.01)
    check(norm(o2) == norm(o), "the same ring without its own pole edge (a whole turn of longitude): closed along the pole line too")
    line = [{"type": "LineString", "coordinates": [[170, 0], [-170, 10]]}]
    lp = [p for s in CL.project_layer(line, W, fr) for p in s["paths"]]
    yc = W.y0 + (80 - 5) * k
    check(len(lp) == 2 and abs(lp[0][-1][0] - right) < 1e-6 and abs(lp[1][0][0] - left) < 1e-6
          and abs(lp[0][-1][1] - yc) < 1e-6 and abs(lp[1][0][1] - yc) < 1e-6, "a line over the antimeridian: split exactly at the edges (latitude 5 at 180, linear)")
    R0 = M.Equirectangular({"north": 20, "south": 0, "west": 0, "east": 30})
    big = [{"type": "Polygon", "coordinates": [[[-20, -10], [60, -10], [60, 40], [-20, 40], [-20, -10]]]}]
    o = CL.project_layer(big, R0, fr, eps=0.01, margin=8)
    p = o[0]["paths"][0]
    check(abs(area(p) - (1920 + 16) * (1080 + 16)) < 1e-6, "a polygon larger than the frame: clipped to the frame + margin exactly")
    wav = [[x / 10.0, 5 + 2 * math.sin(x / 7.0)] for x in range(0, 301)]
    lw = [{"type": "LineString", "coordinates": wav}]
    full = [p for s in CL.project_layer(lw, R0, fr, eps=0) for p in s["paths"]][0]
    for eps in (0.1, 0.5, 2.0):
        simp = [p for s in CL.project_layer(lw, R0, fr, eps=eps) for p in s["paths"]][0]
        err = max(min(math.hypot(*(lambda a, b, q: (lambda L, t: (q[0] - a[0] - t * (b[0] - a[0]), q[1] - a[1] - t * (b[1] - a[1])))
                                                     ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2,
                                                      max(0, min(1, ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / max((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2, 1e-12)))))(a, b, q))
                           for a, b in zip(simp, simp[1:])) for q in full)
        check(err <= eps + 1e-9 and len(simp) < len(full), f"simplification at {eps} px: {len(full)} -> {len(simp)} points, largest error {err:.3f} px")
    check(CL.project_layer(unsplit, W, fr) == CL.project_layer(unsplit, W, fr), "deterministic")

    print("\n== the scene rendered")
    with tempfile.TemporaryDirectory() as td:
        plan, geo, sp = FX.build(td)
        check(sp["qc"]["status"] in ("OK", "WARN") and not [i for i in sp["qc"]["issues"] if i["level"] == "error"], "the fixture's scene plan is usable")
        bm = R.basemap_paths(sp, plan)
        svgs = {f: R.render_svg(sp, plan, f, bm) for f in (None, 0, 45, 90, 150, 239)}
        ok = True
        for f, s in svgs.items():
            try:
                root = ET.fromstring(s)
                ok &= root.tag == NSP + "svg" and root.get("width") == "1920" and root.get("viewBox") == "0 0 1920 1080"
            except ET.ParseError:
                ok = False
        check(ok, "every SVG parses as XML, root <svg> 1920 x 1080")
        check(all(R.render_svg(sp, plan, f, bm) == s for f, s in svgs.items()) and R.render_svg(sp, plan, None) == svgs[None],
              "deterministic: the same bytes again (and with the basemap computed inside)")
        strip = lambda s: re.sub(r"<desc>.*?</desc>", "", s)
        qp = next(p_ for p_ in sp["points"] if p_["id"] == "q")
        q_pin = R.IC.marker("pin", qp["x"][0], qp["y"], qp["size"], qp["color"], qp["stroke"])
        check(strip(svgs[239]) == strip(svgs[None]).replace(q_pin, "", 1) and q_pin in svgs[None],
              "the last frame (camera back to full, everything drawn) = the static map, except point q (shown only in frames 100..139)")
        for f in (45, 90):
            root = ET.fromstring(svgs[f])
            g = root.find(NSP + "g")
            mtx = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", g.get("transform"))]
            want = sp["camera"]["frames"][f]["matrix"]
            check(all(abs(a_ - b_) < 1e-3 for a_, b_ in zip(mtx, want)), f"frame {f}: the map group carries the camera's matrix")
        root = ET.fromstring(svgs[45])
        rpath = [e for e in root.iter(NSP + "path") if e.get("data-route") == "r-east"][0]
        drawn = parse_d(rpath.get("d"))
        an = sp["animation"]["frames"][45]["routes"][0]
        route = sp["routes"][0]
        full_len = [plen([(v["x"], v["y"]) for v in pc]) for pc in route["pieces"]]
        check(len(drawn) == 1 and abs(plen(drawn[0]) - an["pieces"][0] * full_len[0]) < 0.01,
              f"frame 45: the route is drawn to its animation share ({an['pieces'][0]:.4f} of {full_len[0]:.1f} px)")
        head = an["head"]
        tip = drawn[0][-1]
        check(head and abs(tip[0] - head["x"]) < 2e-3 and abs(tip[1] - head["y"]) < 2e-3, "the drawn line ends at the animation's tip")
        st = sp["camera"]["frames"][45]
        X, Y = CAM.to_screen(st, sp["frame"], head["x"], head["y"])
        mk = root.find(NSP + "g[@id='markers']")
        plane = [e for e in mk.iter(NSP + "path") if f"rotate({R.num(head['heading_deg'])})" in (e.get("transform") or "")]
        tr = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", plane[0].get("transform"))] if plane else []
        check(plane and abs(tr[0] - X) < 2e-3 and abs(tr[1] - Y) < 2e-3, f"the plane marker is at the tip on SCREEN ({X:.1f}, {Y:.1f}), turned to its heading")
        pts = {p["id"]: p for p in sp["points"]}
        a_ = pts["a"]
        Xa, Ya = CAM.to_screen(st, sp["frame"], a_["x"][0], a_["y"])
        pins = [e for e in mk.iter(NSP + "path") if (e.get("transform") or "").startswith(f"translate({R.num(Xa)} {R.num(Ya)})")]
        check(len(pins) == 1 and "scale(14)" in pins[0].get("transform"), "a point's pin is at its screen position, at its size in screen pixels")
        r0 = ET.fromstring(svgs[0])
        check(not [e for e in r0.iter() if e.get("data-route")] and len([e for e in r0.find(NSP + "g[@id='markers']")]) == 6,
              "frame 0: no route drawn yet; the 6 shown points (q appears only at frame 100)")
        r150 = ET.fromstring(svgs[150])
        seam = [e for e in r150.iter(NSP + "path") if e.get("data-route") == "r-seam"][0]
        parts = parse_d(seam.get("d"))
        check(len(parts) == 2 and abs(sp["camera"]["frames"][150]["matrix"][0] - 1) > 0, "frame 150: the route over the seam is drawn in two parts")
        land = [e for e in ET.fromstring(svgs[None]).iter(NSP + "path") if e.get("data-layer") == "land" and e.get("fill")][0]
        check(land.get("fill") == sp["style"]["colors"]["land"] and land.get("fill-rule") == "evenodd", "land filled with the style's land colour")
        lines = [e for e in ET.fromstring(svgs[None]).iter() if e.get("vector-effect") == "non-scaling-stroke"]
        check(len(lines) >= 3, "lines keep their width on screen (non-scaling-stroke)")
        check("Synthetic basemap (test)" in svgs[None], "the basemap's attribution is shown")
        sp_h = M.resolve(dict({"schema": "nfp.mapmotion.scene/1", "id": "h", "map": "m2e-map"}, show={"routes": False, "points": False}), plan, geo)
        sh = R.render_svg(sp_h, plan, None)
        check("data-route" not in sh and not len(ET.fromstring(sh).find(NSP + "g[@id='markers']")), "hidden routes and points are not drawn")
        for bad in (-1, 240, True, 1.5):
            try:
                R.render_svg(sp, plan, bad, bm)
                msg = "drawn"
            except ValueError:
                msg = "ValueError"
            check(msg == "ValueError", f"frame {bad!r}: refused")
        html = R.preview_html(sp, plan, step=40)
        check(html == R.preview_html(sp, plan, step=40) and html.count("<svg") == 1 + len(range(0, 240, 40)) + 1 and "<!doctype html>" in html,
              "preview: deterministic page with the static map, every 40th frame and the last one")

    print("\n== boundaries")
    for f in ("clip.py", "svg.py", "icons.py", "render.py"):
        t = (NFP / "mapmotion" / f).read_text(encoding="utf-8")
        mods = {a_ or b_ for a_, b_ in re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", t, re.M)}
        check(mods <= {"math", "xml.sax.saxutils", ".", ".adaptive", ".projection", ".seam", ".svg", ".camera", ".clip", ".icons", ".geometry"},
              f"{f} imports only the standard library and mapmotion {sorted(mods)}")
        check(not re.search(r"urllib|socket|subprocess|write_text|write_bytes|open\(|date\.today|import random|random\.", t),
              f"{f}: no network, process, file writing, clock or randomness")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    check(all(k_ in rd for k_ in ("M2e", "render_svg", "preview_html", "non-scaling-stroke", "Douglas")), "README documents M2e")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2e TESTS PASSED" if not f else "MAP MOTION M2e TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
