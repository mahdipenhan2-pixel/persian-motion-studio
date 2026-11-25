#!/usr/bin/env python3
"""M2a - Map Motion geographic accuracy: routes split exactly on the seam (the date line of the view), the +-180 rule,
adaptive sampling by map error in pixels with depth / point caps, the plan unchanged. Offline, nothing written.
All data SYNTHETIC.

  python3 nfp/mapmotion/tests/test_mapmotion_m2a.py
"""
import datetime
import itertools
import json
import math
import random
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import adaptive as AD           # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402
from test_mapmotion_m1 import mapdoc, LDOC     # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
WORLD = {"north": 80, "south": -80, "west": -180, "east": 180}
EXACT = M.Equirectangular(WORLD)
LEFT, RIGHT = EXACT.x_of_u(0), EXACT.x_of_u(360)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def plan(locs, bounds=None, fit=None, routes=(), points=(), samples=32):
    vp = {"bounds": bounds} if bounds else {"fit": fit}
    d = {"schema": "nfp.mapmotion/1", "id": "m2a-map", "mode": "draft", "window": {"start": 0, "end": 300},
         "labels": {"lang": "en", "year": None}, "viewport": vp, "areas": [],
         "points": [{"id": f"p{i}", "location": l, "start": 0, "end": 300, "label": False} for i, l in enumerate(points)],
         "routes": [{"id": f"r{i}", "stops": list(s), "start": 0, "end": 300, "samples": samples} for i, s in enumerate(routes)]}
    return M.build(d, ldoc(*locs), today=TODAY)


def codes(p):
    return {x["code"] for x in p["qc"]["issues"]}


def ends(route):
    return [(pc[0]["x"], pc[-1]["x"]) for pc in route["pieces"]]


def gc_normal(a, b):
    va, vb = AD._vec(*a), AD._vec(*b)
    return (va[1] * vb[2] - va[2] * vb[1], va[2] * vb[0] - va[0] * vb[2], va[0] * vb[1] - va[1] * vb[0])


def independent_crossing(a, b, lon_seam):
    """Reference written separately from mapmotion: own slerp, bisection on the unwrapped longitude (200 steps)."""
    def vec(lat, lon):
        p, l = math.radians(lat), math.radians(lon)
        return (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))
    va, vb = vec(*a), vec(*b)
    om = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb)))))

    def at(t):
        f1, f2 = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
        x, y, z = (f1 * p + f2 * q for p, q in zip(va, vb))
        return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))

    def east(t):                                        # degrees travelled east from a (continuous, small steps)
        return ((at(t)[1] - a[1]) % 360)
    target = (lon_seam - a[1]) % 360
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if east(mid) < target:
            lo = mid
        else:
            hi = mid
    return at((lo + hi) / 2)[0]


def pieces_ok(g, proj, route):
    """Every point of every piece on the drawn side (x within one map width: seam-360 .. seam); no step of more than
    180 degrees inside a piece (a run along a pole line is exactly 180); every stop on one of its marker positions."""
    lo, hi = proj.x_of_u(M.seam_u(proj) - 360) - 0.002, proj.x_of_u(M.seam_u(proj)) + 0.002
    for pc in route["pieces"]:
        if any(not lo <= v["x"] <= hi for v in pc):
            return "point off the drawn side"
        for a, b in zip(pc, pc[1:]):                      # at most 180 degrees in one step (a pole-line run), never more
            if abs(b["x"] - a["x"]) > 180 * proj.kx + 0.01:
                return f"jump {a['x']} -> {b['x']} at lat {a['lat']}"
    return None if not g["issues"] else str(g["issues"])


def main():
    print("== the seam")
    check(M.seam_u(EXACT) == 360 and M.seam_lon(EXACT) == -180, "whole-world map: the seam is the map edge, longitude +-180")
    dl = M.Equirectangular({"north": 10, "south": -10, "west": 170, "east": -170})
    check(M.seam_lon(dl) == 0 and M.seam_u(dl) == 190, "box 170E..170W: the seam is the prime meridian (behind the box)")
    check(M.seam_lon(M.Equirectangular({"north": 40, "south": 20, "west": 30, "east": 60})) == -135, "box 30E..60E: seam at 135W")
    check(M.marker_xs(EXACT, 0, 180) == [LEFT, RIGHT] and M.marker_xs(EXACT, 0, -180) == [LEFT, RIGHT] and
          M.marker_xs(EXACT, 0, 179.5) == [EXACT.project(0, 179.5)[0]], "a marker on +-180: two positions (both edges); elsewhere one")
    check(M.marker_xs(dl, 5, 0) == [dl.x_of_u(-170), dl.x_of_u(190)] and len(M.marker_xs(dl, 5, 180)) == 1,
          "regional seam: a marker exactly on it has two positions; 180 is inside this box (one)")

    print("\n== east -> west and west -> east over the date line (whole-world map)")
    for a, b, name in (((1.5, 178.5), (2.5, -178.5), "178.5E -> 178.5W"), ((2.5, -178.5), (1.5, 178.5), "178.5W -> 178.5E")):
        p = plan([loc("a", *a), loc("b", *b)], bounds=WORLD, routes=[("a", "b")], points=("a", "b"))
        g = M.geometry(p, proj=EXACT)
        r = g["routes"][0]
        e = ends(r)
        want = [(g["points"][0]["x"][0], RIGHT if a[1] > 0 else LEFT), (LEFT if a[1] > 0 else RIGHT, g["points"][1]["x"][0])]
        check("route_wraps" in codes(p) and len(r["pieces"]) == 2 and r["crossings"] == 1 and
              all(abs(x - w) <= 0.002 for pr, pw in zip(e, want) for x, w in zip(pr, pw)) and not g["issues"],
              f"{name}: plan still reports route_wraps; geometry splits it in 2 pieces ending on the edges {e}")
        seam_pts = [v for pc in r["pieces"] for v in pc if v["kind"] == "seam"]
        check(len(seam_pts) == 2 and seam_pts[0]["lat"] == seam_pts[1]["lat"] and {abs(v["lon"]) for v in seam_pts} == {180.0},
              f"   the crossing point appears once on each edge (lat {seam_pts[0]['lat']}, lon {sorted(v['lon'] for v in seam_pts)})")
    a, b = (10.0, 170.0), (50.0, -160.0)
    p = plan([loc("a", *a), loc("b", *b)], bounds=WORLD, routes=[("a", "b")])
    r = M.geometry(p, proj=EXACT)["routes"][0]
    c = [v for v in r["pieces"][0] if v["kind"] == "seam"][0]
    n = gc_normal(a, b)
    vc = AD._vec(c["lat"], 180.0)
    on_gc = abs(sum(x * y for x, y in zip(n, vc))) / math.sqrt(sum(x * x for x in n))
    lin = a[0] + (b[0] - a[0]) * (10 / 30)
    ref = independent_crossing(a, b, 180.0)
    check(on_gc < 1e-9 and abs(c["lat"] - ref) < 1e-6 and abs(c["lat"] - lin) > 1,
          f"exact crossing: on the great circle (|n.c| {on_gc:.1e}), = an independent dense search ({ref:.7f}), "
          f"not the longitude average ({lin:.4f}) -> {c['lat']}")
    check(abs(c["s_m"] - M.central_angle(a, (c["lat"], 180)) * M.R_EARTH_M) < 0.01,
          "   the crossing's distance along the route (s_m) is its own great-circle distance")

    print("\n== exactly on +-180")
    cases = [((0.5, 170.5), (0.5, 180.0), [(None, RIGHT)], "170.5E -> exactly 180: ends on the east edge"),
             ((0.5, -170.5), (0.5, -180.0), [(None, LEFT)], "170.5W -> exactly -180: ends on the west edge"),
             ((10.5, -180.0), (20.5, -170.5), [(LEFT, None)], "starts on -180 going east: from the west edge"),
             ((0.5, 170.5), (0.5, -180.0), [(None, RIGHT)], "170.5E -> -180 (the same meridian): the east edge")]
    for a, b, want, name in cases:
        p = plan([loc("a", *a), loc("b", *b)], bounds=WORLD, routes=[("a", "b")], points=("a", "b"))
        g = M.geometry(p, proj=EXACT)
        e = ends(g["routes"][0])
        ok = len(e) == 1 and all(w is None or abs(x - w) <= 0.002 for x, w in zip(e[0], want[0])) and not g["issues"]
        check(ok and "route_wraps" not in codes(p), f"{name} {e}; plan: no route_wraps (the edge is a marker position)")
    p = plan([loc("a", 10.5, 180.0), loc("b", 20.5, 170.5)], bounds=WORLD, routes=[("a", "b")], points=("a", "b"))
    g = M.geometry(p, proj=EXACT)
    e = ends(g["routes"][0])
    check(len(e) == 1 and abs(e[0][0] - RIGHT) <= 0.002 and not g["issues"] and "route_wraps" in codes(p),
          f"starts on 180 going west: geometry draws it from the east edge {e}; the plan (M1 rule: a route starts at the "
          "point's own x, the west edge) still reports route_wraps - correct for the plan's continuous line")
    p = plan([loc("a", 10.5, 180.0), loc("b", 40.5, 180.0)], bounds=WORLD, routes=[("a", "b")], points=("a", "b"))
    g = M.geometry(p, proj=EXACT)
    xs = {v["x"] for v in g["routes"][0]["pieces"][0]}
    check(len(g["routes"][0]["pieces"]) == 1 and xs == {round(LEFT, 3)} and g["points"][0]["on_seam"] and not g["issues"],
          "a route along the 180th meridian: one piece, drawn where M1 draws the point (the west edge)")
    p = plan([loc("a", 80.5, 180.0), loc("b", 80.5, 0.0)], bounds=WORLD, routes=[("a", "b")])
    g = M.geometry(p, proj=EXACT)
    check(not g["issues"] and pieces_ok(g, EXACT, g["routes"][0]) is None, "from 180 over the pole to 0: consistent, no issue")
    p = plan([loc("a", 5.5, 175.5), loc("b", 6.5, 0.0)], bounds={"north": 10, "south": 0, "west": 170, "east": -170}, routes=[("a", "b")])
    g = M.geometry(p, proj=M.Equirectangular({"north": 10, "south": 0, "west": 170, "east": -170}))
    check(not g["issues"] and len(g["routes"][0]["pieces"]) == 1, "regional map, a far stop exactly on its seam: consistent")

    print("\n== poles")
    a, b = (80.5, 10.5), (80.5, -169.5)
    p = plan([loc("a", *a), loc("b", *b)], bounds=WORLD, routes=[("a", "b")])
    g = M.geometry(p, proj=EXACT)
    r = g["routes"][0]
    lats = [v["lat"] for v in r["pieces"][0]]
    s = M.sample_route([a, b], EXACT)
    check(max(lats) > 89.99 and pieces_ok(g, EXACT, r) is None and M.max_error_px(s, [a, b], EXACT, 4000) <= 0.5,
          f"exactly over the North Pole: reaches lat {max(lats):.4f}, runs along the pole line, error <= 0.5 px")
    for a, b, what in (((85.5, 0.5), (85.5, 90.5), "near the pole (85.5N, 90 degrees apart)"),
                       ((-89.5, 20.0), (-89.5, -150.0), "close to the South Pole"),
                       ((90.0, 0.0), (60.5, 30.5), "starting on the pole"), ((70.0, -100.0), (89.999, 80.0), "ending next to the pole")):
        s = M.sample_route([a, b], EXACT)
        e = M.max_error_px(s, [a, b], EXACT, 4000)
        m1 = M.leg(a, b, 32)["points"]
        check(e <= 0.5 and not s["capped"], f"{what}: measured error {e:.3f} px with {len(s['points'])} points (M1 fixed: 32)")
    a, b = (85.5, 0.5), (85.5, 90.5)
    s = M.sample_route([a, b], EXACT)
    steps = [math.hypot(*(lambda p, q: (EXACT.x_of_u(q[4]) - EXACT.x_of_u(p[4]), (q[2] - p[2]) * EXACT.k))(p, q)) for p, q in zip(s["points"], s["points"][1:])]
    m1 = M.Equirectangular(WORLD)
    check(max(steps) < 200, f"near the pole the drawn steps stay short (longest {max(steps):.0f} px)")

    print("\n== long and near-antipodal routes")
    for a, b in (((10.25, 20.25), (-10.0, -159.0)), ((0.0, 0.0), (0.05, 179.9)), ((60.0, -170.0), (-50.0, 20.0)), ((-45.0, 100.0), (44.9, -80.2))):
        s = M.sample_route([a, b], EXACT)
        e = M.max_error_px(s, [a, b], EXACT, 6000)
        check(e <= 0.5 and not s["capped"], f"{math.degrees(M.central_angle(a, b)):.3f}-degree leg: error {e:.3f} px, {len(s['points'])} points")
    locs = [loc("s0", 0.5, 0.5), loc("s1", 0.5, 120.5), loc("s2", 0.5, -119.5), loc("s3", 0.5, 0.25)]
    p = plan(locs, bounds=WORLD, routes=[("s0", "s1", "s2", "s3")], points=("s0", "s1", "s2", "s3"))
    g = M.geometry(p, proj=EXACT)
    r = g["routes"][0]
    check(r["crossings"] == 1 and len(r["pieces"]) == 2 and pieces_ok(g, EXACT, r) is None,
          f"round the world in 3 legs: plan route_wraps on {sum(1 for x in p['qc']['issues'] if x['code'] == 'route_wraps')} legs; "
          "geometry: 1 crossing, 2 pieces, every stop on its marker")
    try:
        M.sample_route([(10.5, 20.5), (-10.5, -159.5)], EXACT)
        msg = "accepted"
    except M.RouteError as ex:
        msg = str(ex)
    check("antipodal" in msg, "exactly antipodal: still refused (RouteError)")
    p = plan([loc("a", 10.5, 20.5), loc("b", -10.5, -159.5)], bounds=WORLD, routes=[("a", "b")])
    try:
        M.geometry(p)
        msg = "accepted"
    except ValueError as ex:
        msg = str(ex)
    check(p["qc"]["status"] == "FAIL" and "FAIL plan" in msg, "a FAIL plan is refused by geometry()")

    print("\n== regional routes are not changed")
    reg = [([loc("a", 10.5, 179.5), loc("b", 11.5, -179.5)], {"fit": {"locations": ["a", "b"], "pad_deg": 0.5}}, "regional over the date line"),
           ([loc("a", 35.6892, 51.3890), loc("b", 29.5918, 52.5837)], {"fit": {"locations": ["a", "b"], "pad_deg": 1}}, "regional, ordinary"),
           ([loc("a", 60.1, 5.3), loc("b", 64.1, -21.9)], {"bounds": {"north": 70, "south": 55, "west": -30, "east": 15}}, "regional, high latitude")]
    for locs, vp, what in reg:
        p = plan(locs, routes=[("a", "b")], samples=1000, **vp)
        exact = M.Equirectangular(p["viewport"]["bounds"])
        g = M.geometry(p, proj=exact)
        r = g["routes"][0]
        xy = p["routes"][0]["legs"][0]["xy"]
        pc = r["pieces"][0]
        poly = [(v["x"], v["y"]) for v in pc]
        far = max(min(AD._seg_dist(x, y, *poly[i], *poly[i + 1]) for i in range(len(poly) - 1)) for x, y in xy)
        check(len(r["pieces"]) == 1 and r["crossings"] == 0 and abs(pc[0]["x"] - xy[0][0]) <= 0.002 and abs(pc[-1]["x"] - xy[-1][0]) <= 0.002
              and far <= 0.5 + 0.002 and not g["issues"],
              f"{what}: one piece, same ends as the plan, every one of M1's 1000 points within {far:.3f} px of it ({r['points']} points)")

    print("\n== the random routes of the audit (the same generator: 300 routes; the audit report said 298 by mistake)")
    rnd = random.Random(7)
    n = bad = wraps = 0
    for k in range(300):
        a = (round(rnd.uniform(-70, 70), 4), round(rnd.uniform(-179.9, 179.9), 4))
        b = (round(rnd.uniform(-70, 70), 4), round(rnd.uniform(-179.9, 179.9), 4))
        if M.central_angle(a, b) > math.radians(178):
            continue
        p = plan([loc("a", *a), loc("b", *b)], bounds=WORLD, routes=[("a", "b")], points=("a", "b"))
        if any(x["level"] == "error" for x in p["qc"]["issues"]):
            continue
        n += 1
        g = M.geometry(p, proj=EXACT)
        r = g["routes"][0]
        w = "route_wraps" in codes(p)
        wraps += w
        prob = pieces_ok(g, EXACT, r)
        if prob or (w and r["crossings"] == 0) or (r["crossings"] == 0 and len(r["pieces"]) != 1) or r["error_measured_px"] > 0.5:
            bad += 1
            print("   ", a, b, prob, r["crossings"], len(r["pieces"]))
    check(n == 300 and bad == 0, f"{n} routes ({wraps} with route_wraps in the plan): every one split where needed, every stop "
                                 f"on its marker, no jump across the map, measured error <= tol 0.5 px (problems {bad})")

    print("\n== adaptive sampling: measured map error")
    rnd = random.Random(1)
    boxes = [WORLD, {"north": 89, "south": 50, "west": -180, "east": 180}, {"north": 40, "south": 20, "west": 30, "east": 60},
             {"north": 10, "south": -10, "west": 170, "east": -170}]
    worst, cnt = 0.0, 0
    for bx in boxes:
        pj = M.Equirectangular(bx)
        for k in range(40):
            a = (rnd.uniform(-89.9, 89.9), rnd.uniform(-180, 180))
            b = (rnd.uniform(-89.9, 89.9), rnd.uniform(-180, 180))
            if M.central_angle(a, b) > math.radians(179.9):
                continue
            for tol in (0.5, 0.1, 2.0):
                s = M.sample_route([a, b], pj, tol)
                worst = max(worst, M.max_error_px(s, [a, b], pj, 2000) / tol)
                cnt += 1
    check(worst <= 1.0, f"{cnt} random routes on 4 maps at tol 0.5 / 0.1 / 2 px: measured error <= tol (worst {worst:.3f} x tol)")
    a, b = (35.0, -120.0), (40.0, 116.0)
    n1 = len(M.sample_route([a, b], EXACT, 2.0)["points"])
    n2 = len(M.sample_route([a, b], EXACT, 0.5)["points"])
    n3 = len(M.sample_route([a, b], EXACT, 0.1)["points"])
    check(n1 < n2 < n3, f"a smaller tolerance gives more points ({n1} < {n2} < {n3})")
    s = M.sample_route([(1.0, 1.0), (1.0, 1.0)], EXACT)
    check(len(s["points"]) == 2 and s["error_px"] == 0, "a zero-length leg: 2 equal points, no error")
    s = M.sample_route([(10.0, 10.0), (12.0, 14.0), (12.0, 14.0), (20.0, 40.0)], EXACT)
    check(sum(1 for q in s["points"] if q[1] == 1.0) == 3 and M.max_error_px(s, [(10.0, 10.0), (12.0, 14.0), (12.0, 14.0), (20.0, 40.0)], EXACT) <= 0.5,
          "a multi-leg route with a zero-length leg: one shared point per stop, error <= 0.5 px")

    print("\n== caps and limits")
    a, b = (60.0, -170.0), (-50.0, 20.0)
    n0 = math.ceil(math.degrees(M.central_angle(a, b)) / 10)
    s = M.sample_route([a, b], EXACT, 0.5, max_depth=0)
    check(s["capped"] == ["depth"] and s["error_px"] > 0.5 and len(s["points"]) == n0 + 1,
          f"max_depth 0: only the minimum density ({n0 + 1} points), capped by depth, estimated error {s['error_px']:.1f} px reported")
    s = M.sample_route([a, b], EXACT, 0.01, max_depth=2)
    check(s["capped"] == ["depth"] and len(s["points"]) <= n0 * 4 + 1, f"max_depth 2 at tol 0.01: capped, at most 4 x the segments ({len(s['points'])} points)")
    s = M.sample_route([a, b], EXACT, 0.01, max_points=40)
    check(s["capped"] == ["points"] and len(s["points"]) == 40, "max_points 40 at tol 0.01: exactly 40 points, capped by points")
    s = M.sample_route([a, b], EXACT, 0.001, max_depth=60, max_points=1_000_000)
    check(not s["capped"] or len(s["points"]) < 1_000_000, f"tol 0.001 px: terminates ({len(s['points'])} points, capped {s['capped']})")
    try:
        M.sample_route([a, b], EXACT, 0.5, max_points=10)
        msg = "accepted"
    except M.RouteError as ex:
        msg = str(ex)
    check("minimum density" in msg, "max_points below the minimum density: refused with a clear message")
    p = plan([loc("a", *a), loc("b", *b)], bounds=WORLD, routes=[("a", "b")])
    g = M.geometry(p, max_depth=0)
    check([x["code"] for x in g["issues"]] == ["sampling_capped"] and "max_depth" in g["issues"][0]["message"],
          "geometry() reports a cap as a 'sampling_capped' warning, with the estimated error")
    for kw, what in (({"tol_px": 0}, "tol 0"), ({"tol_px": -1}, "tol -1"), ({"tol_px": float("nan")}, "tol NaN"), ({"tol_px": True}, "tol bool"),
                     ({"tol_px": "0.5"}, "tol string"), ({"max_depth": -1}, "depth -1"), ({"max_depth": 61}, "depth 61"),
                     ({"max_depth": 1.5}, "depth 1.5"), ({"max_depth": True}, "depth bool"), ({"max_points": 1}, "points 1"),
                     ({"max_points": True}, "points bool")):
        try:
            M.geometry(p, **kw)
            msg = "accepted"
        except ValueError as ex:
            msg = type(ex).__name__
        check(msg == "RouteError", f"{what}: refused")

    print("\n== determinism and the plan")
    p = plan([loc("a", 1.5, 178.5), loc("b", 2.5, -178.5), loc("c", 60.5, -150.5)], bounds=WORLD, routes=[("a", "b", "c")], points=("a", "b", "c"))
    j1 = json.dumps(M.geometry(p), sort_keys=True)
    j2 = json.dumps(M.geometry(p), sort_keys=True)
    perms = {json.dumps(M.geometry(plan(list(perm), bounds=WORLD, routes=[("a", "b", "c")], points=("a", "b", "c"))), sort_keys=True)
             for perm in itertools.permutations([loc("a", 1.5, 178.5), loc("b", 2.5, -178.5), loc("c", 60.5, -150.5)])}
    check(j1 == j2 and perms == {j1}, "the same geometry twice, and for all 6 orders of the location file")
    before = json.dumps(p, sort_keys=True)
    M.geometry(p)
    check(json.dumps(p, sort_keys=True) == before, "geometry() does not change the plan")
    pj = M.projection_from_plan(p)
    diff = max(max(abs(a - b) for a, b in zip(pj.project(la, lo), EXACT.project(la, lo))) for la in range(-80, 81, 20) for lo in range(-180, 181, 30))
    g1, g2 = M.geometry(p), M.geometry(p, proj=EXACT)
    d2 = max(abs(v["x"] - w["x"]) + abs(v["y"] - w["y"]) for r1, r2 in zip(g1["routes"], g2["routes"])
             for p1, p2 in zip(r1["pieces"], r2["pieces"]) for v, w in zip(p1, p2))
    check(diff < 0.001 and d2 <= 0.002, f"the projection rebuilt from the plan matches the exact one ({diff:.1e} px; geometry {d2:.3f} px)")
    m = M.build(mapdoc(), LDOC, today=TODAY)
    check(m["schema"] == "nfp.mapmotion.plan/1" and "geometry" not in m and M.geometry(m)["schema"] == "nfp.mapmotion.geometry/1",
          "the M1 plan keeps its schema and fields; the geometry is a separate document")

    print("\n== boundaries")
    src = "".join(p.read_text(encoding="utf-8") for p in (NFP / "mapmotion").glob("*.py"))
    for f in ("adaptive.py", "seam.py", "geometry.py"):
        t = (NFP / "mapmotion" / f).read_text(encoding="utf-8")
        mods = set(re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", t, re.M))
        mods = {a or b for a, b in mods}
        check(mods <= {"heapq", "math", ".", ".adaptive", ".seam", ".model", ".projection", ".route"}, f"{f} imports only the standard library and mapmotion {sorted(mods)}")
    check(not re.search(r"date\.today|datetime\.now|time\.time|import random|random\.|urllib|socket|subprocess|open\(", src),
          "no clock, randomness, network, process or file access in nfp/mapmotion")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    check(all(k in rd for k in ("M2a", "geometry", "marker_xs", "tol_px", "max_depth", "max_points", "sampling_capped", "±180")),
          "README documents M2a")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2a TESTS PASSED" if not f else "MAP MOTION M2a TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
