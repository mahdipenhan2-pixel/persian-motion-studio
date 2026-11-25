#!/usr/bin/env python3
"""M2a second audit fixes - Map Motion: (1) route_jump is measured in degrees (float noise on a very zoomed map is not
an error; a real jump still is), (2) near a pole an uncapped route is within tol_px (checked with an exact measurement
written here: own slerp, the exact t-interval of every drawn chord), tolerance_exceeded as a guard. Offline, nothing
written. SYNTHETIC data.

  python3 nfp/mapmotion/tests/test_mapmotion_m2a_fixes2.py
"""
import datetime
import math
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests")]
import mapmotion as M                          # noqa: E402
from mapmotion import adaptive as AD           # noqa: E402
from mapmotion import seam as SM               # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
ZOOM = ({"north": 84.9, "south": 84.6, "west": 10, "east": 10.6}, "auto")
MAPS = [({"north": 85, "south": -85, "west": -180, "east": 180}, "auto"), ({"north": 89.9, "south": 60, "west": -180, "east": 180}, 60),
        ({"north": -60, "south": -89.9, "west": -180, "east": 180}, -60), ({"north": 89, "south": 40, "west": 150, "east": -150}, 60),
        ({"north": 50, "south": 20, "west": 30, "east": 80}, "auto"), ZOOM]


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def plan(stops, box, sp):
    ids = [f"s{i}" for i in range(len(stops))]
    d = {"schema": "nfp.mapmotion/1", "id": "fix2-map", "mode": "draft", "window": {"start": 0, "end": 300},
         "labels": {"lang": "en", "year": None}, "projection": {"type": "equirectangular", "standard_parallel": sp},
         "viewport": {"bounds": box}, "areas": [], "points": [],
         "routes": [{"id": "r", "stops": ids, "start": 0, "end": 300, "samples": 8}]}
    return M.build(d, ldoc(*[loc(f"s{i}", *s) for i, s in enumerate(stops)]), today=TODAY)


def opp(lon):
    return (lon + 360.0) % 360.0 - 180.0


def exact_error(stops, proj, sampled, n=120):
    """Independent: own slerp on the exact t-interval of every drawn chord; each true point moved by whole turns to the
    chord's own longitude range (so a pole step of either sign is the same point); largest distance to the chord (px)."""
    def vec(lat, lon):
        p, l = math.radians(lat), math.radians(lon)
        return (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))
    worst = 0.0
    pts = sampled["points"]
    W, N = proj.bounds["west"], proj.bounds["north"]
    for p, q in zip(pts, pts[1:]):
        li = q[0]
        tp = p[1] if p[0] == q[0] else 0.0
        va, vb = vec(*stops[li]), vec(*stops[li + 1])
        om = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb)))))
        if om < 1e-12:
            continue
        lo, hi = min(p[4], q[4]), max(p[4], q[4])
        ax, ay = proj.x_of_u(p[4]), proj.y0 + (N - p[2]) * proj.k
        bx, by = proj.x_of_u(q[4]), proj.y0 + (N - q[2]) * proj.k
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        for i in range(1, n):
            t = tp + (q[1] - tp) * i / n
            f1, f2 = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
            x, y, z = (f1 * a + f2 * b for a, b in zip(va, vb))
            lat, lon = math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))
            u = (lon - W) % 360.0
            u = min((u + 360.0 * k for k in range(-3, 4)), key=lambda c: 0.0 if lo - 1e-7 <= c <= hi + 1e-7 else min(abs(c - lo), abs(c - hi)))
            mx, my = proj.x_of_u(u), proj.y0 + (N - lat) * proj.k
            tt = 0.0 if L == 0 else max(0.0, min(1.0, ((mx - ax) * dx + (my - ay) * dy) / L))
            worst = max(worst, math.hypot(mx - ax - tt * dx, my - ay - tt * dy))
    return worst


def main():
    print("== 1. route_jump is measured in degrees")
    box, sp = ZOOM
    e = M.Equirectangular(box, standard_parallel=sp)
    for st in ([(83.9110297, 10.26555504), (86.4926794, -169.73444496), (85.6577992, 12.73315865), (83.3439536, -92.67658787),
                (84.4587293, 9.77406868), (86.1309829, 30.0)],
               [(83.1454151, 9.70295878), (84.3738849, -170.29704122), (85.5095463, -180.0), (83.8118013, 0.0),
                (85.5897865, 9.25373167), (84.8219798, 8.28076933)]):
        g = M.geometry(plan(st, box, sp), tol_px=0.1, proj=e)
        steps = [abs(w["x"] - v["x"]) / e.kx for pc in g["routes"][0]["pieces"] for v, w in zip(pc, pc[1:])]
        check("route_jump" not in [x["code"] for x in g["issues"]] and max(steps) <= 180 + 1e-3,
              f"the audit's zoomed-map case ({e.kx:.0f} px/deg): a valid 180-degree pole run (largest step {max(steps):.6f}) "
              "is not a route_jump any more")
    check(M.geometry.__module__ and __import__("mapmotion.geometry", fromlist=["JUMP_TOL_DEG"]).JUMP_TOL_DEG == 1e-3,
          "the threshold is 1e-3 degrees")
    box4k, sp4k = {"north": 84.96, "south": 84.94, "west": 10.0, "east": 10.04}, "auto"
    e4k = M.Equirectangular(box4k, standard_parallel=sp4k)
    for st, tol in (([(84.4846938, -92.03671362), (85.7461016, 87.96328638)], 0.1),
                    ([(84.4846938, -92.03671362), (85.7461016, 87.96328638)], 0.02),
                    ([(84.5920916, 10.08145131), (85.2324181, -169.91854869), (84.866441, -44.465123), (84.6438202, 10.08145131)], 0.02),
                    ([(84.9386997, 10.00243097), (85.7360211, -169.99756903), (85.141309, -41.79911821), (85.7023468, 180.0)], 0.02)):
        g = M.geometry(plan(st, box4k, sp4k), tol_px=tol, proj=e4k)
        steps = [abs(w["x"] - v["x"]) / e4k.kx for pc in g["routes"][0]["pieces"] for v, w in zip(pc, pc[1:])]
        check("route_jump" not in [x["code"] for x in g["issues"]] and 180.0 < max(steps) < 180.001,
              f"{e4k.kx:.0f} px/deg, over the pole, tol {tol}: the 180-degree pole run has float noise "
              f"(+{max(steps) - 180:.1e} degrees) but is not a route_jump")
    real_split = SM.split
    for extra, want, what in ((360.0, True, "a false 360-degree step"), (0.5, True, "a step of 180.5 degrees"),
                              (2e-3, True, "180 + 2e-3 degrees (just over the threshold, JUMP_TOL_DEG = 1e-3)"),
                              (2e-6, False, "180 + 2e-6 degrees (below the threshold: within pole noise, not reported)"),
                              (0.0, False, "exactly 180 degrees")):
        def fake_split(points, stops, proj, leg_at, du, extra=extra):
            pcs = real_split(points, stops, proj, leg_at, du)
            pc = pcs[0]
            k = len(pc) // 2
            base = pc[k - 1][4]
            pc[k] = pc[k][:4] + (base + 180.0 + extra,) + pc[k][5:]
            return pcs
        SM.split = fake_split
        try:
            g = M.geometry(plan([(10.5, 10.5), (20.5, 40.5)], {"north": 85, "south": -85, "west": -180, "east": 180}, "auto"))
        finally:
            SM.split = real_split
        check(("route_jump" in [x["code"] for x in g["issues"]]) == want,
              f"a piece with {what} inside it: route_jump {'reported' if want else 'not reported'}")

    print("\n== 2. near a pole: an uncapped route is within tol (exact independent measurement)")
    rnd = random.Random(20261125)
    n = over = below = capped = 0
    worst = 0.0
    for box, sp in MAPS:
        e = M.Equirectangular(box, standard_parallel=sp)
        for k in range(10):
            if box["north"] > 89 or box is ZOOM[0]:
                la = lambda: rnd.uniform(83, 89.999) if box is not ZOOM[0] else rnd.uniform(83, 86.5)
            elif box["south"] < -89:
                la = lambda: -rnd.uniform(60.5, 89.999)
            else:
                la = lambda: rnd.uniform(40.5, 88.9) if box["west"] == 150 else rnd.uniform(-84.9, 84.9)
            L = rnd.uniform(-180, 180)
            far = opp(L) + rnd.choice([0.0, 0.0, 1e-7, -1e-7, 1e-4, -1e-4, 0.01])
            st = [(round(la(), 6), round(L, 6)), (round(la(), 6), round(far, 7))]
            if M.central_angle(*st) > math.radians(179.6):
                continue
            for tol in (0.5, 0.1):
                s = M.sample_route(st, e, tol)
                t = exact_error(st, e, s)
                n += 1
                capped += bool(s["capped"])
                worst = max(worst, t / tol if not s["capped"] else 0.0)
                if not s["capped"] and t > tol:
                    over += 1
                if t > s["error_px"] + 1e-9:
                    below += 1
    check(n >= 100 and over == 0, f"{n} routes over / near a pole on 6 maps ({capped} capped): uncapped and real error > tol: {over} "
                                  f"(worst uncapped real / tol {worst:.3f})")
    check(below == 0, f"error_px at or above the exact real error on all of them ({below} below)")
    a, b = (80.5, 10.5), (80.5, -169.5)
    e = M.Equirectangular(*MAPS[0][:1])
    s = M.sample_route([a, b], e, 0.1)
    check(not s["capped"] and s["within_tol"] and s["error_px"] <= 0.1 and exact_error([a, b], e, s) <= 0.1,
          f"over the North Pole at tol 0.1: within_tol, error_px {s['error_px']:.4f} <= tol, exact {exact_error([a, b], e, s):.4f}")
    s = M.sample_route([(60.0, -170.0), (-50.0, 20.0)], e, 0.5, max_depth=0)
    check(s["capped"] == ["depth"] and not s["within_tol"], "a capped route is not within_tol (and is reported as capped)")
    real_sample = AD.sample_route

    def fake_sample(*a, **k):
        r = real_sample(*a, **k)
        r["within_tol"], r["capped"], r["error_px"] = False, [], 0.9
        return r
    AD.sample_route = fake_sample
    try:
        g = M.geometry(plan([(10.5, 10.5), (20.5, 40.5)], MAPS[0][0], "auto"), tol_px=0.5)
    finally:
        AD.sample_route = real_sample
    w = [x for x in g["issues"] if x["code"] == "tolerance_exceeded"]
    check(len(w) == 1 and w[0]["level"] == "warning" and "0.900" in w[0]["message"],
          "guard: uncapped but over tol (forced) -> warning tolerance_exceeded with the error")

    print("\n== documentation")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    for key, what in (("tolerance_exceeded", "the tolerance guard"), ("JUMP", "route_jump in degrees"),
                      ("از `s_m`", "positions from x / y, not s_m"), ("1e-11", "routes very close to a pole")):
        check(key in rd, f"README documents {what}")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2a FIX2 TESTS PASSED" if not f else "MAP MOTION M2a FIX2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
