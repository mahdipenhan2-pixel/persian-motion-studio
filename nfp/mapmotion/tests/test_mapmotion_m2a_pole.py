#!/usr/bin/env python3
"""M2a - routes exactly over a pole (longitudes 180 degrees apart): no false 360-degree step in the sampled route, in
the split pieces or in geometry(); independent of the order points are inserted (the tolerance), of the direction of
travel and of rounding at the +-180 tie; boundary cases just off the pole. Offline, nothing written. SYNTHETIC data.

  python3 nfp/mapmotion/tests/test_mapmotion_m2a_pole.py
"""
import datetime
import json
import math
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import adaptive as AD           # noqa: E402
from mapmotion import seam as SM               # noqa: E402
from test_mapmotion_m2a_fixes import plan, true_error   # noqa: E402

RESULTS = []
WORLD = {"north": 85, "south": -85, "west": -180, "east": 180}
E = M.Equirectangular(WORLD)
ARCTIC = {"north": 89.9, "south": 60, "west": -180, "east": 180}
EA = M.Equirectangular(ARCTIC, standard_parallel=60)
DL = {"north": 89, "south": 50, "west": 150, "east": -150}
ED = M.Equirectangular(DL, standard_parallel=60)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def opposite(lon):
    return (lon + 180.0 + 180.0) % 360.0 - 180.0


STEP_TOL = 1e-6                 # degrees: float noise of atan2 next to a pole is ~1e-9; a false step would be 360


def max_step(us):
    return max([abs(b - a) for a, b in zip(us, us[1:])] + [0.0])


def pieces(stops, proj, tol=0.5, md=24):
    s = M.sample_route(stops, proj, tol, max_depth=md)
    legs = [AD._Leg(stops[i], stops[i + 1]) for i in range(len(stops) - 1)]
    return s, SM.split(s["points"], stops, proj, lambda li, t, pl: legs[li].at(t, pl), AD.du)


def main():
    print("== the reported case and the rule")
    a, b = (62.555473, -90.921245), (89.972857, 89.078755)
    for tol, md in ((0.5, 24), (0.1, 24), (0.05, 3)):
        s, pcs = pieces([a, b], E, tol, md)
        check(max_step([p[4] for p in s["points"]]) <= 180 + STEP_TOL and len(pcs) == 1 and not any(v[5] == "seam" for v in pcs[0]),
              f"{a} -> {b}, tol {tol}, max_depth {md}: largest step {max_step([p[4] for p in s['points']]):.6f} degrees, one piece, "
              "no false crossing")
    check(SM.u_between(150.0, 100.0, 200.0) == 150.0 and SM.u_between(510.0, 100.0, 200.0) == 150.0 and
          SM.u_between(-210.0, 100.0, 200.0) == 150.0 and SM.u_between(150.0, 200.0, 100.0) == 150.0,
          "u_between: a value between the ends is kept; one a whole turn off (either way, either order) is brought back")
    check(abs(SM.u_between(-90.92, 89.08, 269.08) - 269.08) < 1e-9 and abs(SM.u_between(449.08, 89.08, 269.08) - 89.08) < 1e-9,
          "u_between: -90.92 and 449.08 (one turn off either way) become the ends of the 180-degree pole run")

    print("\n== exactly over the pole: random, both poles, both directions, three maps")
    rnd = random.Random(8)
    n = bad = fail_geo = 0
    worst_ratio = 0.0
    for proj, box, hemis in ((E, WORLD, (1, -1)), (EA, ARCTIC, (1,)), (ED, DL, (1,))):
        for k in range(60):
            sg = rnd.choice(hemis)
            L = round(rnd.uniform(-180, 180), 6)
            a = (round(sg * rnd.uniform(60.5, 89.999), 6), L)
            b = (round(sg * rnd.uniform(60.5, 89.999), 6), round(opposite(L), 6))
            for st in ([a, b], [b, a]):
                for tol, md in ((0.5, 24), (0.1, 24), (0.05, 3), (2.0, 24)):
                    s, pcs = pieces(st, proj, tol, md)
                    n += 1
                    us = [p[4] for p in s["points"]]
                    if max_step(us) > 180 + STEP_TOL or any(max_step([v[4] for v in pc]) > 180 + STEP_TOL for pc in pcs):
                        bad += 1
                    t = true_error(st, proj, s, 8000)
                    if t > 1e-9:
                        worst_ratio = max(worst_ratio, t / s["error_px"])
                if box is not DL:
                    p = plan(st, bounds=box)
                    if p["qc"]["status"] != "FAIL":
                        g = M.geometry(p)
                        if g["issues"] and any(x["code"] != "sampling_capped" for x in g["issues"]):
                            fail_geo += 1
    check(bad == 0, f"{n} sampled routes exactly over a pole: no step of more than 180 degrees, before or after the split ({bad} bad)")
    check(fail_geo == 0, f"geometry() on the same routes (world and Arctic maps): no route_jump / route_wraps ({fail_geo})")
    check(worst_ratio <= 1.0, f"error_px is at or above the real error on all of them (largest real / reported {worst_ratio:.3f})")

    print("\n== independent of the insertion order (the tolerance) and of rounding at the tie")
    a, b = (80.5, 10.5), (80.5, -169.5)
    signs = set()
    for tol in (2.0, 0.5, 0.1, 0.02, 0.005):
        s = M.sample_route([a, b], E, tol)
        k = next(i for i, p in enumerate(s["points"]) if abs(s["points"][i + 1][4] - p[4]) > 90)
        signs.add(math.copysign(1, s["points"][k + 1][4] - s["points"][k][4]))
    check(len(signs) == 1, f"the pole-line run goes the same way at 5 tolerances ({'east' if signs == {1.0} else 'west' if signs == {-1.0} else signs})")
    for d in (-1e-11, 1e-11, -1e-10, 1e-10):
        bb = (80.5, opposite(10.5) + d)
        s = M.sample_route([a, bb], E)
        g = M.geometry(plan([a, (80.5, round(opposite(10.5) + d, 7))]))
        check(max_step([p[4] for p in s["points"]]) <= 180 + 1e-6 and not [x for x in g["issues"] if x["code"] != "sampling_capped"],
              f"far end {d:+.0e} degrees off exactly opposite (rounding at the tie): no false step, geometry clean")
    check(json.dumps(M.sample_route([a, b], E)) == json.dumps(M.sample_route([a, b], E)), "deterministic")

    print("\n== the pole-line run on the whole-world map stays on the map")
    for L in (10.5, -100.25, 0.0, 90.0, -90.0, 179.0, -179.0):
        for st in ([(80.5, L), (75.5, opposite(L))], [(75.5, opposite(L)), (80.5, L)], [(-80.5, L), (-75.5, opposite(L))]):
            p = plan(st)
            g = M.geometry(p)
            r = g["routes"][0]
            check(not g["issues"] and len(r["pieces"]) == 1 and r["crossing_points"] == 0,
                  f"{st[0]} -> {st[1]}: one piece, no seam crossing, no issue")
    for st in ([(80.5, 180.0), (80.5, 0.0)], [(80.5, 0.0), (80.5, 180.0)], [(80.5, -180.0), (75.0, 0.0)]):
        g = M.geometry(plan(st))
        r = g["routes"][0]
        check(not g["issues"] and r["seam_stops"] == 1, f"{st[0]} -> {st[1]} (a stop on the seam): clean, {len(r['pieces'])} piece(s)")

    print("\n== boundary cases just off the pole and poles as stops")
    for d in (1e-7, 1e-4, 0.01, 1.0):
        for sg in (1, -1):
            st = [(80.5, 10.5), (80.5, opposite(10.5) + sg * d)]
            s = M.sample_route(st, E)
            t = true_error(st, E, s, 8000)
            check(max_step([p[4] for p in s["points"]]) <= 180 + STEP_TOL and t <= s["error_px"] and s["error_measured_px"] <= 0.5,
                  f"opposite {sg * d:+g} degrees: no false step, real error {t:.3f} <= error_px {s['error_px']:.3f}")
    for st in ([(90.0, 0.0), (60.5, 30.5)], [(60.5, 30.5), (90.0, 0.0)], [(-90.0, 45.0), (-70.0, -135.0)], [(89.9999999, 0.0), (80.0, 180.0)]):
        g = M.geometry(plan(st))
        check(not g["issues"], f"{st[0]} -> {st[1]}: geometry clean")
    st = [(70.5, 0.0), (75.5, 180.0), (70.5, 0.0), (65.5, 180.0)]
    g = M.geometry(plan(st))
    check(not g["issues"] and all(max_step([v["x"] / E.kx for v in pc]) <= 180 + 1e-3 for pc in g["routes"][0]["pieces"]),
          "a route over the North Pole three times (0 -> 180 -> 0 -> 180): clean, no step of more than 180 degrees")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2a POLE TESTS PASSED" if not f else "MAP MOTION M2a POLE TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
