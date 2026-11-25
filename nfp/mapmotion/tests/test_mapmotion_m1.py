#!/usr/bin/env python3
"""M1 - Map Motion: Equirectangular projection, 16:9 fit, the date line, great-circle routes, map.json + Location +
Timeline frames -> deterministic plan, QC. Offline, nothing written.

  python3 nfp/mapmotion/tests/test_mapmotion_m1.py

Every coordinate and name here is SYNTHETIC test data, not a claim about a real place.
"""
import copy
import datetime
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests")]
import mapmotion as M                          # noqa: E402
import timeline as TL                          # noqa: E402  (read-only: the anchor contract)
from test_location_l1c import loc              # noqa: E402  (Location test record builder, unchanged)
from test_location_l1a import doc as ldoc      # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
R = M.R_EARTH_M


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def raises(fn, exc=ValueError):
    try:
        fn()
        return False
    except exc:
        return True


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


B = lambda n, s, e, w: {"north": n, "south": s, "east": e, "west": w}
NAMES_A = [{"text": "تست‌آباد کهن", "lang": "fa", "type": "historical", "from": -300, "to": 1500},
           {"text": "تست‌آباد", "lang": "fa", "type": "current", "from": 1501},
           {"text": "Testabad", "lang": "en", "type": "current", "from": 1501}]
LOCS = [loc("ta", 10.1234, 20.1234, names=NAMES_A),
        loc("tb", 11.4321, 21.6789, names=[{"text": "Testburg", "lang": "en", "type": "current"}]),
        loc("tc", 10.9876, 22.5432, names=[{"text": "تست‌کوه", "lang": "fa", "type": "current"}],
            precision="approximate", uncertainty_m=5000, extent={"north": 11.2, "south": 10.8, "east": 22.8, "west": 22.3}),
        loc("td", 12.0123, 20.5555)]                                       # no names
LDOC = ldoc(*LOCS)
WORDS = {"schema": "nfp.film.words/1", "lang": "fa", "fps": 30, "duration": 15.0, "sentences": [
    {"id": "s1", "text": "a b", "offset": 0.3, "duration": 2.0, "words": [
        {"i": 0, "text": "a", "start": 0.3, "end": 0.8}, {"i": 1, "text": "b", "start": 0.8, "end": 2.3}]},
    {"id": "s2", "text": "c d", "offset": 2.6, "duration": 3.0, "words": [
        {"i": 0, "text": "c", "start": 2.6, "end": 3.1}, {"i": 1, "text": "d", "start": 3.1, "end": 5.6}]}]}
CTX = TL.Context.from_words(WORDS)


def mapdoc(**over):
    d = {"schema": "nfp.mapmotion/1", "id": "test-map", "mode": "final", "fps": 30,
         "projection": {"type": "equirectangular", "standard_parallel": "auto"},
         "viewport": {"width": 1920, "height": 1080, "margin": {"x": 96, "y": 64}, "fit": {"locations": ["ta", "tb", "tc"], "pad_deg": 0.25}},
         "window": {"start": 30, "end": 300},
         "labels": {"lang": "fa", "year": None, "fallback": ["en"]},
         "uncertainty": {"show": "auto"},
         "points": [{"id": "p-a", "location": "ta", "start": 30, "end": 300}, {"id": "p-b", "location": "tb", "start": 60, "end": 300},
                    {"id": "p-c", "location": "tc", "start": 90, "end": 300}],
         "routes": [{"id": "r-1", "stops": ["ta", "tb", "tc"], "start": 90, "end": 270, "samples": 16}],
         "areas": [{"id": "ar-c", "location": "tc", "source": "extent", "start": 120, "end": 300}]}
    d.update(over)
    return d


def build(d=None, locs=None, ctx=None):
    return M.build(mapdoc() if d is None else d, LDOC if locs is None else locs, context=ctx, today=TODAY)


def codes(p, level=None):
    return [x["code"] for x in p["qc"]["issues"] if level is None or x["level"] == level]


def main():
    print("== projection: equator, prime meridian, corners, 16:9")
    p = M.Equirectangular(B(10, -10, 10, -10))
    check(close(p.k, 47.6) and close(p.kx, 47.6) and p.phi0 == 0 and close(p.x0, 484) and close(p.y0, 64),
          "box 20 x 20 degrees on the equator: 47.6 px per degree, centred (x0 484, y0 64 = the margin)")
    check(p.project(0, 0) == (960.0, 540.0), "equator x prime meridian -> the frame centre (960, 540)")
    check(p.project(10, -10) == (484.0, 64.0) and p.project(-10, 10) == (1436.0, 1016.0), "the box corners -> exact pixels")
    check(p.project(0, 5)[1] == 540 and p.project(5, 0)[0] == 960, "the equator is horizontal, the prime meridian vertical")
    for w, h in ((1920, 1000), (1080, 1920), (0, 0), (1920.0, 1080)):
        check(raises(lambda: M.Equirectangular(B(10, -10, 10, -10), w, h), M.ProjectionError), f"frame {w}x{h}: refused (16:9 whole pixels)")
    check(M.Equirectangular(B(10, -10, 10, -10), 1280, 720).project(0, 0) == (640.0, 360.0), "any 16:9 frame size works (1280x720)")
    check(raises(lambda: M.Equirectangular(B(10, -10, 10, -10), margin_x=960), M.ProjectionError) and
          raises(lambda: M.Equirectangular(B(10, -10, 10, -10), margin_y=-1), M.ProjectionError), "margins that leave no room / negative: refused")
    q = M.Equirectangular(B(10, -10, 10, -10), margin_x=0, margin_y=0)
    check(close(q.k, 54.0) and q.project(10, -10)[1] == 0, "margin 0: the box touches the frame edge")
    for bad in (B(float("nan"), 0, 10, 0), B(10, float("-inf"), 10, 0), B(91, 0, 10, 0), B(10, 0, 181, 0), B(0, 10, 10, 0),
                B(10, 10, 10, 0), B(10, 0, 5, 5), {"north": 1}, B("10", 0, 10, 0), B(True, 0, 10, 0)):
        check(raises(lambda: M.Equirectangular(bad), M.ProjectionError), f"invalid bounds refused: {json.dumps(bad)[:60]}")
    for lat, lon in ((float("nan"), 0), (0, float("inf")), (91, 0), (0, 181), ("1", 0), (None, 0)):
        check(raises(lambda: p.project(lat, lon), M.ProjectionError), f"invalid point refused: {lat!r}, {lon!r}")
    v = p.visible()
    check(v["north"] >= 10 and v["south"] <= -10 and v["west"] < -10 and v["east"] > 10 and close((v["east"] - v["west"]) / (v["north"] - v["south"]), 16 / 9, 1e-9),
          f"visible area: the box widened to 16:9 {v}")

    print("\n== standard parallel and the poles")
    a = M.Equirectangular(B(40, 20, 60, 40))
    check(a.phi0 == 30 and close(a.kx / a.k, math.cos(math.radians(30))), "auto: the middle latitude (30); east-west scale x cos 30")
    f = M.Equirectangular(B(40, 20, 60, 40), standard_parallel=0)
    check(f.phi0 == 0 and close(f.kx, f.k), "standard_parallel 0: plate carree")
    pol = M.Equirectangular(B(90, 60, 180, -180), standard_parallel=70)
    check(pol.project(90, 0)[1] == pol.project(90, 120)[1] == pol.y0, "the pole is a line (every longitude at the same y)")
    check(raises(lambda: M.Equirectangular(B(90, 89, 10, 0)), M.ProjectionError), "auto parallel 89.5 (beyond 85): refused - give one")
    check(raises(lambda: M.Equirectangular(B(10, 0, 10, 0), standard_parallel="x"), M.ProjectionError) and
          raises(lambda: M.Equirectangular(B(10, 0, 10, 0), standard_parallel=86), M.ProjectionError), "a bad / too-polar standard parallel: refused")

    print("\n== the date line")
    d = M.Equirectangular(B(10, -10, -170, 170))                      # 20 degrees over 180
    xs = {lon: d.project(0, lon)[0] for lon in (170, 175, 180, -180, -175, -170)}
    check(close(xs[180], xs[-180]) and close(xs[180], 960) and xs[170] < xs[175] < xs[180] < xs[-175] < xs[-170],
          f"west 170 > east -170: 180 = -180 at the centre, x grows eastwards across it {[round(x) for x in xs.values()]}")
    check(d.project(0, 169)[0] < xs[170] and d.project(0, -169)[0] > xs[-170] and 0 < d.project(0, 169)[0],
          "a point just outside the box lands just outside it - not 360 degrees away")
    w = M.Equirectangular(B(10, -10, 180, -180))
    check(close(w.lon_span, 360) and close(w.project(0, -180)[0], w.x0) and close(w.project(0, 180)[0], w.x0) and
          close(w.project(0, 0)[0], w.x0 + 180 * w.kx) and close(w.project(0, 0)[0], 960),
          "-180..180: the whole circle of longitude (-180 and 180 on the left edge, 0 in the middle)")
    check(close(M.span(-180, 180), 360) and close(M.span(170, -170), 20) and close(M.span(-10, 10), 20), "span(): 360, 20 over the date line, 20")

    print("\n== fitting a box around places")
    fb = M.fit_bounds([(1, 10), (3, 20)])
    check(fb == B(3, 1, 20, 10), f"two points -> their box {fb}")
    fd = M.fit_bounds([(0, 179), (5, -179), (2, 178)])
    check(fd["west"] == 178 and fd["east"] == -179, f"points on both sides of 180 -> the short box over the date line {fd}")
    check(M.fit_bounds([(1, 10), (3, 20)], 0.5) == B(3.5, 0.5, 20.5, 9.5), "pad_deg widens every side")
    one = M.fit_bounds([(1, 10)])
    check(one["north"] > one["south"] and one["east"] > one["west"] and not M.check_bounds(one), "a single point -> a tiny valid box")

    print("\n== great-circle routes")
    g = M.leg((0, 0), (0, 90), 3)
    check(close(g["distance_m"], R * math.pi / 2, 1e-3) and close(g["points"][1][0], 0) and close(g["points"][1][1], 45),
          "equator 0 -> 90E: a quarter of the circle; the midpoint 0, 45")
    g = M.leg((0, 0), (60, 0), 4)
    check(all(close(pt[1], 0) for pt in g["points"]) and [round(pt[0], 9) for pt in g["points"]] == [0, 20, 40, 60],
          "along a meridian: the latitude grows evenly (0, 20, 40, 60)")
    g = M.leg((45, -60), (45, 60), 3)
    mid_lat = math.degrees(math.atan(math.tan(math.radians(45)) / math.cos(math.radians(60))))
    check(close(g["points"][1][0], mid_lat, 1e-9) and close(g["points"][1][1], 0, 1e-9) and g["points"][1][0] > 45,
          f"45N 60W -> 45N 60E bends poleward: midpoint {g['points'][1][0]:.4f}N on 0 (not along the 45th parallel)")
    g = M.leg((10, 20), (10.001, 20), 2)
    check(close(g["distance_m"], R * math.radians(0.001), 1e-6) and 111 < g["distance_m"] < 112, f"a short leg: {g['distance_m']:.2f} m")
    g = M.leg((0, -75), (0, 75), 64)
    check(close(g["angle_deg"], 150, 1e-9) and len(g["points"]) == 64 and g["points"][0] == (0.0, -75.0) and g["points"][-1] == (0.0, 75.0),
          "a long leg (150 degrees), 64 samples, the ends exact")
    g = M.leg((0, 179), (0, -179), 5)
    lons = [pt[1] for pt in g["points"]]
    un = M.unwrap(lons)
    check(close(g["distance_m"], R * math.radians(2), 1e-3) and un == [179.0, 179.5, 180.0, 180.5, 181.0],
          f"179E -> 179W: 2 degrees the short way; unwrapped {un} (no 358-degree jump)")
    check(M.unwrap([170, -170, 175]) == [170, 190, 175] and M.unwrap([-170, 170]) == [-170, -190], "unwrap(): each step within 180 of the last")
    check(raises(lambda: M.leg((0, 0), (0, 180)), M.RouteError) and raises(lambda: M.leg((30, 10), (-30, -170)), M.RouteError),
          "antipodal points: refused (no single great circle)")
    z = M.leg((5, 5), (5, 5), 4)
    check(z["distance_m"] == 0 and all(pt == (5.0, 5.0) for pt in z["points"]), "identical points: length 0")
    for s in (1, 1001, 2.5, True):
        check(raises(lambda: M.leg((0, 0), (1, 1), s), M.RouteError), f"samples {s!r} refused (2..1000)")
    check(raises(lambda: M.leg((float("nan"), 0), (1, 1)), M.RouteError) and raises(lambda: M.leg((0, 0), (95, 1)), M.RouteError),
          "invalid route points refused")
    check(close(M.leg((10, 20), (11, 21))["distance_m"], __import__("location").distance_m(10, 20, 11, 21), 1e-6),
          "the same sphere as Location's distance_m")

    print("\n== map.json -> plan")
    pl = build()
    check(pl["qc"]["status"] in ("OK", "WARN") and not codes(pl, "error") and pl["schema"] == "nfp.mapmotion.plan/1",
          f"a full map (3 points, a route, an area): plan built {codes(pl)}")
    check(pl["frame"] == {"width": 1920, "height": 1080} and pl["window"] == {"start": 30, "end": 300} and
          all(pt["inside"] for pt in pl["points"]), "frame, window, every point inside the frame")
    ta = next(x for x in pl["points"] if x["id"] == "p-a")
    proj = M.Equirectangular(pl["viewport"]["bounds"], standard_parallel="auto")
    ex, ey = proj.project(10.1234, 20.1234)
    check(close(ta["x"], round(ex, 3)) and close(ta["y"], round(ey, 3)), "point pixels = the projection of its Location point")
    r = pl["routes"][0]
    check(r["stops"] == ["ta", "tb", "tc"] and len(r["legs"]) == 2 and all(len(lg["xy"]) == 16 for lg in r["legs"]) and
          r["legs"][0]["xy"][-1] == r["legs"][1]["xy"][0], "route: stops in order, 16 samples per leg, legs joined end to start")
    d1, d2 = r["legs"][0]["distance_m"], r["legs"][1]["distance_m"]
    check(r["stop_frames"][0] == 90 and r["stop_frames"][-1] == 270 and r["stop_frames"][1] == 90 + round(180 * d1 / (d1 + d2)),
          f"stop frames in proportion to distance: {r['stop_frames']}")
    steps = [math.dist(a, b) for lg in r["legs"] for a, b in zip(lg["xy"], lg["xy"][1:])]
    check(max(steps) < 3 * (sum(steps) / len(steps)), "no jump along the drawn route (steady sample spacing)")
    ar = pl["areas"][0]["shape"]
    x1, y1 = proj.project(11.2, 22.3)
    check(ar["type"] == "rect" and close(ar["x"], round(x1, 3)) and close(ar["y"], round(y1, 3)) and ar["w"] > 0 and ar["h"] > 0,
          "extent area: the Location extent as a rectangle in frame pixels")

    print("\n== the date line inside a plan")
    dl_locs = ldoc(loc("w1", 1.2345, 178.5), loc("e1", 2.3456, -178.5))
    dl = M.build(mapdoc(viewport={"fit": {"locations": ["w1", "e1"], "pad_deg": 1}}, points=[], areas=[], labels={"lang": "en", "year": None},
                        routes=[{"id": "r-dl", "stops": ["w1", "e1"], "start": 30, "end": 300, "samples": 32}]), dl_locs, today=TODAY)
    xs = [xy[0] for xy in dl["routes"][0]["legs"][0]["xy"]]
    check(dl["viewport"]["crosses_date_line"] and not codes(dl, "error") and all(b > a for a, b in zip(xs, xs[1:])) and
          max(b - a for a, b in zip(xs, xs[1:])) < 50 and all(0 <= x <= 1920 for x in xs),
          f"a route over the date line: the fitted box crosses 180, x grows steadily {round(xs[0])} -> {round(xs[-1])}, no jump")

    print("\n== Location: draft / verified, names, uncertainty")
    draft = copy.deepcopy(LOCS)
    draft[1]["reviewed"] = None
    p_final = build(locs=ldoc(*draft))
    p_draft = build(d=mapdoc(mode="draft"), locs=ldoc(*draft))
    check("draft_location" in codes(p_final, "error") and p_final["qc"]["status"] == "FAIL",
          "final mode: a draft (unverified) location is an error")
    check("draft_location" in codes(p_draft, "warning") and not codes(p_draft, "error") and len(p_draft["points"]) == 3,
          "draft mode: the same map is built, with a warning")
    check(codes(p_draft).count("draft_location") == 1, "the draft is reported once although the place is used three times")
    lab = {x["id"]: x["label"] for x in pl["points"]}
    check(lab["p-a"]["display"] == "تست‌آباد" and lab["p-a"]["type"] == "current" and lab["p-c"]["display"] == "تست‌کوه",
          "labels in Persian today (ZWNJ kept)")
    check(lab["p-b"]["text"] == "Testburg" and lab["p-b"]["fallback"] and "label_fallback" in codes(pl, "info"),
          "no Persian name: the English one, marked fallback (info)")
    old = build(d=mapdoc(labels={"lang": "fa", "year": 1200, "fallback": ["en"]}))
    check({x["id"]: x["label"]["text"] if x["label"] else None for x in old["points"]}["p-a"] == "تست‌آباد کهن",
          "year 1200: the historical name (name_at)")
    ov = build(d=mapdoc(points=[{"id": "p-a", "location": "ta", "start": 30, "end": 300, "lang": "en"},
                                {"id": "p-d", "location": "td", "start": 30, "end": 300}, {"id": "p-x", "location": "tb", "start": 30, "end": 300, "label": False}]))
    lab = {x["id"]: x["label"] for x in ov["points"]}
    check(lab["p-a"]["text"] == "Testabad" and lab["p-d"] is None and lab["p-x"] is None and "no_name" in codes(ov, "warning"),
          "per point: lang override; a place without names gets no label (warning, nothing guessed); label false: none")
    check("bad_year" in codes(build(d=mapdoc(labels={"lang": "fa", "year": 0})), "error"), "labels.year 0: refused (no year zero)")
    unc = {x["id"]: x["uncertainty"] for x in pl["points"]}
    c = unc["p-c"]
    lat = 10.9876
    check(unc["p-a"] is None and c and c["m"] == 5000 and close(c["ry"], round(5000 / (math.pi * R / 180) * proj.k, 3)) and
          close(c["rx"] / c["ry"], proj.kx / proj.k / math.cos(math.radians(lat)), 1e-3),
          f"auto: an 'approximate' place shows its 5 km uncertainty (ellipse rx {c['rx']} ry {c['ry']}); an exact one shows none")
    al = build(d=mapdoc(uncertainty={"show": "always"}))
    check(next(x for x in al["points"] if x["id"] == "p-a")["uncertainty"]["m"] == 50 and
          all(x["uncertainty"] is None for x in build(d=mapdoc(uncertainty={"show": "never"}))["points"]), "show always / never")
    nounc = copy.deepcopy(LOCS)
    nounc[2]["uncertainty_m"] = None
    check("unknown_uncertainty" in codes(build(locs=ldoc(*nounc)), "warning"), "an approximate place without uncertainty_m: warning, no area")
    ua = build(d=mapdoc(areas=[{"id": "u", "location": "tc", "source": "uncertainty", "start": 30, "end": 300}]))
    check(ua["areas"][0]["shape"]["type"] == "ellipse" and ua["areas"][0]["shape"]["m"] == 5000, "an uncertainty area: an ellipse")
    check("no_extent" in codes(build(d=mapdoc(areas=[{"id": "x", "location": "ta", "source": "extent", "start": 30, "end": 300}])), "error"),
          "an extent area for a place without extent: error")

    print("\n== timing: Timeline frames and anchors (read-only contract)")
    ok_anchor = mapdoc(window={"start": CTX.resolve(0.3), "end": CTX.resolve(["s2", "e", 1]), "anchors": {"start": 0.3, "end": ["s2", "e", 1]}},
                       points=[{"id": "p", "location": "ta", "start": CTX.resolve(["s1", "w", 1]), "end": CTX.resolve(["s2", "w", 0]),
                                "anchors": {"start": ["s1", "w", 1], "end": ["s2", "w", 0]}}], routes=[], areas=[])
    pa = build(d=ok_anchor, ctx=CTX)
    check(not codes(pa, "error") and pa["window"] == {"start": 9, "end": 168} and pa["points"][0]["start"] == 24 and pa["points"][0]["end"] == 78,
          "anchors resolved with timeline.Context (words.json): window 9..168, point 24..78")
    bad = copy.deepcopy(ok_anchor)
    bad["points"][0]["end"] = 79
    check("anchor_mismatch" in codes(build(d=bad, ctx=CTX), "error"), "a frame that does not match its anchor: error")
    check("anchors_unchecked" in codes(build(d=ok_anchor), "info") and not codes(build(d=ok_anchor), "error"),
          "without word timing anchors are not resolved (info), as in Timeline")
    long = mapdoc(window={"start": 30, "end": 500}, points=[], routes=[], areas=[])
    check("outside_video" in codes(build(d=long, ctx=CTX), "error"), "a window after the end of the video (450 frames): error")
    for el, code in (({"id": "p", "location": "ta", "start": 10, "end": 300}, "outside_window"), ({"id": "p", "location": "ta", "start": 30, "end": 30}, "bad_time"),
                     ({"id": "p", "location": "ta", "start": 30.5, "end": 300}, "bad_time"), ({"id": "p", "location": "ta", "start": -1, "end": 3}, "bad_time")):
        check(code in codes(build(d=mapdoc(points=[el], routes=[], areas=[])), "error"), f"element time {el['start']}..{el['end']}: {code}")

    print("\n== schema and QC")
    for over, code in (({"schema": "nfp.mapmotion/2"}, "schema"), ({"fps": 25}, "fps"), ({"mode": "publish"}, "schema"),
                       ({"projection": {"type": "mercator"}}, "projection"), ({"extra": 1}, "schema"), ({"id": "bad id"}, "bad_id"),
                       ({"viewport": {"bounds": B(10, 0, 10, 0), "fit": {"locations": ["ta"]}}}, "schema"), ({"viewport": {}}, "schema"),
                       ({"viewport": {"bounds": B(0, 10, 10, 0)}}, "viewport"), ({"viewport": {"width": 1920, "height": 1000, "bounds": B(10, 0, 10, 0)}}, "viewport"),
                       ({"window": None}, "schema"), ({"uncertainty": {"show": "sometimes"}}, "schema"), ({"labels": {"lang": "Persian"}}, "schema")):
        p = build(d=mapdoc(**over))
        check(code in codes(p, "error"), f"{json.dumps(over)[:70]}: {code}")
    dup = build(d=mapdoc(points=[{"id": "x", "location": "ta", "start": 30, "end": 300}], routes=[{"id": "x", "stops": ["ta", "tb"], "start": 30, "end": 300}]))
    check("duplicate_id" in codes(dup, "error"), "the same id for a point and a route: refused")
    for r_, code in (({"id": "r", "stops": ["ta"], "start": 30, "end": 300}, "schema"), ({"id": "r", "stops": ["ta", "nowhere"], "start": 30, "end": 300}, "unknown_location"),
                     ({"id": "r", "stops": ["ta", "tb"], "start": 30, "end": 300, "samples": 1}, "schema"), ({"id": "r", "stops": ["ta", "tb"], "start": 30, "end": 300, "speed": 2}, "schema")):
        check(code in codes(build(d=mapdoc(routes=[r_], points=[], areas=[])), "error"), f"route {json.dumps(r_)[:60]}: {code}")
    check("zero_leg" in codes(build(d=mapdoc(routes=[{"id": "r", "stops": ["ta", "ta", "tb"], "start": 30, "end": 300}])), "warning"),
          "a route with the same stop twice in a row: warning")
    anti = ldoc(loc("n1", 10.5, 20.5), loc("n2", -10.5, -159.5))
    check("route" in codes(M.build(mapdoc(viewport={"bounds": B(30, -30, 180, -180)}, points=[], areas=[], labels={"lang": "en"},
                                          routes=[{"id": "r", "stops": ["n1", "n2"], "start": 30, "end": 300}]), anti, today=TODAY), "error"),
          "a route between antipodal places: error")
    off = build(d=mapdoc(viewport={"bounds": B(10.5, 10, 20.5, 20)}))
    check("outside_frame" in codes(off, "warning") and not any(x["inside"] for x in off["points"] if x["id"] == "p-c"),
          "a place outside the chosen viewport: warning, marked inside=false")
    check("no_locations" in codes(M.build(mapdoc(), None, today=TODAY), "error"), "no locations document: error")
    brk = ldoc(*LOCS, loc("ta", 1.5, 1.5))
    check("location_file" in codes(build(locs=brk), "error"), "errors in the locations file are passed on")

    print("\n== determinism and independence")
    j1 = json.dumps(build(), ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(build(), ensure_ascii=False, sort_keys=True)
    j3 = json.dumps(build(locs=ldoc(*reversed(LOCS))), ensure_ascii=False, sort_keys=True)
    check(j1 == j2 == j3, "the same plan every run and whatever order the locations file lists the places in")
    md, ld = mapdoc(), copy.deepcopy(LDOC)
    snap = (json.dumps(md), json.dumps(ld))
    M.build(md, ld, context=CTX, today=TODAY)
    check((json.dumps(md), json.dumps(ld)) == snap, "build() never changes map.json or the locations document")
    check(not re.search(r"20\d\d-\d\d-\d\d", j1) and "today" not in json.loads(j1), "the plan holds no date / clock value")
    src = "".join(p.read_text(encoding="utf-8") for p in (NFP / "mapmotion").glob("*.py"))
    mods = sorted(set(re.findall(r"^\s*(?:from|import) ([\w.]+)", src, re.M)))
    check(set(mods) <= {"datetime", "math", "re", "location", "timeline", ".", ".model", ".projection", ".route"},
          f"nfp/mapmotion imports only the standard library, Location and Timeline (read-only) {mods}")
    check(not re.search(r"urllib|requests|socket|subprocess|http\.client|open\(|write_text", src),
          "no network, process or file-writing code in nfp/mapmotion")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M1 TESTS PASSED" if not f else "MAP MOTION M1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
