#!/usr/bin/env python3
"""M2a audit fixes - Map Motion: (1) one seam rule for places (markers, stops, M1's route_wraps) at the plan's 7-decimal
precision, (2) crossings = len(pieces) - 1 with crossing_points / seam_stops, (3) the reported error is measured and
never below the real one (checked with an independent slerp written here). Offline, nothing written. SYNTHETIC data.

  python3 nfp/mapmotion/tests/test_mapmotion_m2a_fixes.py
"""
import datetime
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests")]
import mapmotion as M                          # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
WORLD = {"north": 85, "south": -85, "west": -180, "east": 180}
E = M.Equirectangular(WORLD)
LEFT, RIGHT = E.x_of_u(0), E.x_of_u(360)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def plan(stops, bounds=WORLD, samples=16):
    ids = [f"s{i}" for i in range(len(stops))]
    d = {"schema": "nfp.mapmotion/1", "id": "fix-map", "mode": "draft", "window": {"start": 0, "end": 300},
         "labels": {"lang": "en", "year": None}, "viewport": {"bounds": bounds}, "areas": [],
         "points": [{"id": f"p{i}", "location": l, "start": 0, "end": 300, "label": False} for i, l in enumerate(ids)],
         "routes": [{"id": "r", "stops": ids, "start": 0, "end": 300, "samples": samples}]}
    return M.build(d, ldoc(*[loc(f"s{i}", *s) for i, s in enumerate(stops)]), today=TODAY)


def codes(p):
    return {x["code"] for x in p["qc"]["issues"]}


def true_error(stops, proj, sampled, n=20000):
    """Independent measurement: own slerp / unwrap, n points per leg, distance to the drawn segment covering each."""
    def vec(lat, lon):
        p, l = math.radians(lat), math.radians(lon)
        return (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))
    def step(a, b):
        d = (b - a + 180) % 360 - 180
        return 180.0 if d == -180 and b - a > 0 else d
    pts = sampled["points"]
    worst = 0.0
    for li in range(len(stops) - 1):
        va, vb = vec(*stops[li]), vec(*stops[li + 1])
        om = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb)))))
        seg = [p for p in pts if p[0] == li]
        start = pts[0] if li == 0 else [p for p in pts if p[0] == li - 1][-1]
        seg = [(li, 0.0) + tuple(start[2:])] + [p for p in seg if not (li == 0 and p is pts[0])]
        j = 0
        for i in range(n + 1):
            t = i / n
            while j < len(seg) - 2 and seg[j + 1][1] < t:
                j += 1
            p, q = seg[j], seg[j + 1]
            if om < 1e-12 or t in (0.0, 1.0):
                continue
            f1, f2 = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
            x, y, z = (f1 * a + f2 * b for a, b in zip(va, vb))
            lat, lon = math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))
            if abs(lat) > 90 - 1e-12:
                lon = p[3]
            st = step(p[3], lon)
            # across a pole the step is +-180 within rounding: both signs are the same point (the pole line)
            alts = (st, st - 360.0, st + 360.0) if abs(abs(st) - 180.0) < 1e-6 else (st,)
            ax, ay = proj.x_of_u(p[4]), proj.y0 + (proj.bounds["north"] - p[2]) * proj.k
            bx, by = proj.x_of_u(q[4]), proj.y0 + (proj.bounds["north"] - q[2]) * proj.k
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            my = proj.y0 + (proj.bounds["north"] - lat) * proj.k
            best = None
            for sv in alts:
                mx = proj.x_of_u(p[4] + sv)
                tt = 0.0 if L == 0 else max(0.0, min(1.0, ((mx - ax) * dx + (my - ay) * dy) / L))
                d = math.hypot(mx - ax - tt * dx, my - ay - tt * dy)
                best = d if best is None else min(best, d)
            worst = max(worst, best)
    return worst


def main():
    print("== 1. one seam rule for places, at the plan's 7-decimal precision")
    p = plan([(0.5, -170.0), (0.5, 179.99999996)])
    g = M.geometry(p, proj=E)
    end = g["routes"][0]["pieces"][-1][-1]["x"]
    mk = g["points"][1]["x"]
    check(mk == [round(LEFT, 3), round(RIGHT, 3)] and min(abs(end - x) for x in mk) <= 0.002 and not g["issues"] and "route_wraps" not in codes(p),
          f"the audit case 179.99999996 from -170: marker on both edges {mk}, route ends on one of them ({end}), no issue, "
          "plan without route_wraps")
    for lon, seam in ((179.99999996, True), (-179.99999996, True), (179.99999995, round(179.99999995, 7) == 180.0),
                      (-179.99999995, round(-179.99999995, 7) == -180.0),
                      (179.9999999, False), (-179.9999999, False), (179.99999994, False), (180.0, True), (-180.0, True), (179.5, False)):
        check(M.on_seam(0, E) and M.seam.on_seam_lon(lon, E) == seam and (len(M.marker_xs(E, 0, lon)) == 2) == seam,
              f"lon {lon!r}: {'on' if seam else 'not on'} the seam (7-decimal value {round(lon, 7)!r})")
    for a, b, what in (((0.5, -170.0), (0.5, 179.99999996), "from the west side to 179.99999996"),
                       ((0.5, 170.0), (0.5, 179.99999996), "from the east side to 179.99999996"),
                       ((0.5, -170.0), (0.5, -179.99999996), "from the west side to -179.99999996"),
                       ((0.5, 170.0), (0.5, -179.99999996), "from the east side to -179.99999996"),
                       ((0.5, 179.99999996), (0.5, 170.0), "from 179.99999996 westwards"),
                       ((0.5, -179.99999996), (0.5, -170.0), "from -179.99999996 eastwards"),
                       ((0.5, -170.0), (0.5, 179.9999999), "to 179.9999999 (not the seam) from the west"),
                       ((0.5, 170.0), (0.5, -179.9999999), "to -179.9999999 (not the seam) from the east")):
        p = plan([a, b])
        g = M.geometry(p, proj=E)
        r = g["routes"][0]
        first, last = r["pieces"][0][0]["x"], r["pieces"][-1][-1]["x"]
        ok = (min(abs(first - x) for x in g["points"][0]["x"]) <= 0.002 and min(abs(last - x) for x in g["points"][1]["x"]) <= 0.002
              and not g["issues"])
        check(ok, f"{what}: both route ends on their markers (pieces {len(r['pieces'])}, seam stops {r['seam_stops']}); "
                  f"plan route_wraps {'route_wraps' in codes(p)}")
    p = plan([(0.5, -170.0), (0.5, 179.9999999)])
    check(not M.geometry(p, proj=E)["points"][1]["x"][1:], "no false seam: 179.9999999 keeps a single marker position")
    dl = {"north": 10, "south": -10, "west": 150.12345678, "east": -150.12345678}
    pj = M.Equirectangular(dl)
    sl = M.seam_lon(pj)
    for lon in (round(sl, 7), round(sl, 7) + 4e-8, round(sl, 7) + 1e-7):
        on = M.seam.on_seam_lon(lon, pj)
        p = plan([(5.0, 160.0), (5.0, lon)], bounds=dl)
        g = M.geometry(p)
        last = g["routes"][0]["pieces"][-1][-1]["x"]
        check(on == (abs(lon - round(sl, 7)) < 5e-8) and not g["issues"] and min(abs(last - x) for x in g["points"][1]["x"]) <= 0.002,
              f"regional seam {sl:.9f} (not a 7-decimal value): stop at {lon:.9f} -> on the seam {on}; route end on its marker; "
              "the plan's rebuilt projection agrees")

    print("\n== 2. crossings = len(pieces) - 1")
    for st, want, what in (([(0.5, -170.0), (0.5, 180.0), (0.5, 170.0)], (2, 1, 0, 1), "-170 -> 180 -> 170 (changes side at a seam stop)"),
                           ([(1.5, 178.5), (2.5, -178.5)], (2, 1, 1, 0), "178.5E -> 178.5W (a real crossing)"),
                           ([(0.5, -170.0), (0.5, 180.0), (0.5, -175.0)], (1, 0, 0, 1), "-170 -> 180 -> -175 (touches the seam, same side)"),
                           ([(0.5, 0.5), (0.5, 120.5), (0.5, -119.5), (0.5, 0.25)], (2, 1, 1, 0), "round the world"),
                           ([(1.5, 170.0), (2.5, -170.0), (3.5, 170.0), (4.5, -170.0)], (4, 3, 3, 0), "three real crossings"),
                           ([(10.5, 180.0), (40.5, 180.0)], (1, 0, 0, 2), "along the 180th meridian"),
                           ([(1.5, 10.0), (2.5, 20.0)], (1, 0, 0, 0), "no seam at all")):
        r = M.geometry(plan(st), proj=E)["routes"][0]
        got = (len(r["pieces"]), r["crossings"], r["crossing_points"], r["seam_stops"])
        check(got == want and r["crossings"] == len(r["pieces"]) - 1,
              f"{what}: pieces {got[0]}, crossings {got[1]}, crossing_points {got[2]}, seam_stops {got[3]}")

    print("\n== 3. the reported error is measured, never below the real one")
    cases = [([(80.5, 10.5), (80.5, -169.5)], 0.05, 3, 20000, "the audit case: over the pole, max_depth 3, tol 0.05"),
             ([(60.0, -170.0), (-50.0, 20.0)], 0.5, 0, 20000, "max_depth 0"),
             ([(60.0, -170.0), (-50.0, 20.0)], 0.01, 2, 20000, "max_depth 2, tol 0.01"),
             ([(85.5, 0.5), (85.5, 90.5)], 0.1, 1, 20000, "near the pole, max_depth 1"),
             ([(10.0, 10.0), (60.0, 120.0)], 0.05, 24, 25, "max_points 25"),
             ([(-89.0, 0.0), (-89.0, 179.0)], 0.02, 2, 20000, "next to the South Pole, max_depth 2"),
             ([(60.0, -170.0), (-50.0, 20.0)], 0.01, 24, 40, "max_points 40")]
    for st, tol, md, mp, what in cases:
        s = M.sample_route(st, E, tol, max_depth=md, max_points=mp)
        true = true_error(st, E, s)
        check(s["capped"] and s["error_px"] >= true and s["error_px"] > tol,
              f"{what}: capped {s['capped']}, real {true:.4f} px; reported error_px {s['error_px']:.4f} (>= real), "
              f"measured {s['error_measured_px']:.4f} ({s['error_measured_px'] / true:.3f} x real)")
    p = plan([(80.5, 10.5), (80.5, -169.5)])
    g = M.geometry(p, tol_px=0.05, max_depth=3, proj=E)
    w = [x for x in g["issues"] if x["code"] == "sampling_capped"]
    r = g["routes"][0]
    check(len(w) == 1 and w[0]["level"] == "warning" and f"{r['error_px']:.3f}" in w[0]["message"] and "not a guarantee" in w[0]["message"]
          and "measured" in r["error_basis"], "geometry(): the cap warning is still given, with the conservative bound and the basis")
    for st in ([(1.5, 178.5), (2.5, -178.5)], [(35.0, -120.0), (40.0, 116.0)], [(80.5, 10.5), (80.5, -169.5)], [(-45.0, 100.0), (44.9, -80.2)]):
        s = M.sample_route(st, E)
        true = true_error(st, E, s)
        check(not s["capped"] and true <= 0.5 and s["error_px"] >= true and s["error_measured_px"] <= 0.5,
              f"uncapped {st}: real {true:.4f} px <= tol, reported error_px {s['error_px']:.4f} (not below the real one)")

    print("\n== documentation")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    for key, what in (("179.99999996", "the 7-decimal seam rule"), ("crossing_points", "crossings / crossing_points / seam_stops"),
                      ("error_measured_px", "the measured error and the conservative error_px"), ("روی هر دو لبه", "routes along the seam meridian itself")):
        check(key in rd, f"README documents {what}")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2a FIX TESTS PASSED" if not f else "MAP MOTION M2a FIX TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
