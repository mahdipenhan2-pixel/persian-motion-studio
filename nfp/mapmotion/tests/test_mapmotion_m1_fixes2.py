#!/usr/bin/env python3
"""M1 second audit fixes - Map Motion: (1) the route_wraps message is true on whole-world AND regional maps,
(2) the public fit_bounds() refuses invalid input and keeps its behaviour for valid input. Offline, nothing written.
All data SYNTHETIC.

  python3 nfp/mapmotion/tests/test_mapmotion_m1_fixes2.py
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
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
WORLD = {"north": 80, "south": -80, "west": -180, "east": 180}


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def wraps(bounds, a, b):
    d = {"schema": "nfp.mapmotion/1", "id": "wrap-map", "mode": "draft", "window": {"start": 0, "end": 300},
         "labels": {"lang": "en", "year": None}, "viewport": {"bounds": bounds}, "points": [], "areas": [],
         "routes": [{"id": "r", "stops": ["a", "b"], "start": 0, "end": 300, "samples": 16}]}
    p = M.build(d, ldoc(loc("a", *a), loc("b", *b)), today=TODAY)
    return [x["message"] for x in p["qc"]["issues"] if x["code"] == "route_wraps"], p


def refused(points, pad=0.0):
    try:
        M.fit_bounds(points, pad)
    except M.ProjectionError as e:
        return str(e)
    except Exception as e:                      # any other exception is a failure of the check
        return f"WRONG {type(e).__name__}"
    return None


def reference_fit(points, pad_deg=0.0):
    """fit_bounds as it was before the input checks (valid input only), copied here to compare behaviour."""
    pts = [(lat, lon) for lat, lon in points]
    lats = [p[0] for p in pts]
    lons = sorted({p[1] for p in pts})
    if len(lons) == 1:
        west = east = lons[0]
    else:
        gaps = [((lons[(i + 1) % len(lons)] - lons[i]) % 360, i) for i in range(len(lons))]
        gap, i = max(gaps, key=lambda g: (g[0], -g[1]))
        west, east = lons[(i + 1) % len(lons)], lons[i]
    north, south = max(lats) + pad_deg, min(lats) - pad_deg
    arc = 0.0 if len(lons) == 1 else (east - west) % 360
    if arc + 2 * pad_deg >= 360:
        return {"north": min(90.0, north), "south": max(-90.0, south), "west": -180.0, "east": 180.0}
    west, east = west - pad_deg, east + pad_deg
    if north - south < 1e-9:
        north, south = north + 0.01, south - 0.01
    if M.span((west + 180) % 360 - 180, (east + 180) % 360 - 180) < 1e-9 or west == east:
        west, east = west - 0.01, east + 0.01
    norm = lambda v: (v + 180) % 360 - 180 if not -180 <= v <= 180 else v
    w, e = norm(west), norm(east)
    if (east - west) >= 360:
        w, e = -180.0, 180.0
    return {"north": min(90.0, north), "south": max(-90.0, south), "west": w, "east": e}


def main():
    print("== 1. the route_wraps message")
    src = (NFP / "mapmotion" / "model.py").read_text(encoding="utf-8")
    check("whole-world map" not in src, "model.py no longer says 'whole-world map'")
    m, p = wraps(WORLD, (1.2345, 178.5), (2.3456, -178.5))
    check(len(m) == 1 and "differ by +1 x 360 degrees of longitude" in m[0] and "'a' -> 'b'" in m[0] and "M2" in m[0]
          and "whole-world" not in m[0], f"whole-world map: {m[0][:110] if m else 'none'}...")
    reg = {"north": 40, "south": -40, "west": -32.5, "east": 6.129}
    m, p = wraps(reg, (25.2367, -26.4739), (-59.4406, 159.4878))
    codes = {x["code"] for x in p["qc"]["issues"]}
    check(len(m) == 1 and "x 360 degrees of longitude" in m[0] and "whole-world" not in m[0] and "outside_frame" in codes,
          "regional map, far stop reached the other way round: the same general message (with outside_frame)")
    xe = p["routes"][0]["legs"][0]["xy"][-1][0]
    mx = M.Equirectangular(reg).project(-59.4406, 159.4878)[0]
    turns = (xe - mx) / (360 * M.Equirectangular(reg).kx)
    check(abs(abs(turns) - 1) < 1e-6 and f"{turns:+.0f} x 360" in m[0], f"the stated turns ({turns:+.6f}) are the real x difference / 360 degrees")
    m, p = wraps({"north": 20, "south": 0, "west": 170, "east": -170}, (10.5, 175.5), (11.5, -175.5))
    check(not m, "regional route across the date line: still no route_wraps")

    print("\n== 2. fit_bounds: invalid input refused")
    nan, inf = float("nan"), float("inf")
    bad = [([(nan, 0)], "NaN latitude"), ([(0, nan)], "NaN longitude"), ([(inf, 0)], "+Inf latitude"), ([(0, -inf)], "-Inf longitude"),
           ([(90.0001, 0)], "latitude > 90"), ([(-90.5, 0)], "latitude < -90"), ([(0, 180.0001)], "longitude > 180"), ([(0, -181)], "longitude < -180"),
           ([(True, 0)], "bool latitude"), ([(0, False)], "bool longitude"), ([("1", 2)], "string latitude"), ([(1, None)], "None longitude"),
           ([(1, 2, 3)], "a 3-tuple"), ([(1,)], "a 1-tuple"), ([5], "a number instead of a pair"), (["ab"], "a 2-letter string"),
           ([{"lat": 1, "lon": 2}], "a dict"), ([(1, 2), (nan, 3)], "one bad point among good ones"), ([], "no points"),
           (None, "None instead of a list"), (7, "a number instead of a list"), ([(1, 1j)], "a complex number")]
    for pts, what in bad:
        r = refused(pts)
        check(r is not None and not r.startswith("WRONG"), f"{what}: ProjectionError ({r})")
    for pad, what in ((-0.1, "negative"), (nan, "NaN"), (inf, "Inf"), (True, "bool"), ("1", "string"), (None, "None")):
        r = refused([(1, 2), (3, 4)], pad)
        check(r is not None and not r.startswith("WRONG") and "pad_deg" in r, f"pad_deg {what}: ProjectionError")

    print("\n== 2. fit_bounds: valid input unchanged")
    fixed = [([(1, 10), (3, 20)], 0.5), ([(0, 179), (5, -179), (2, 178)], 0), ([(0, 0), (0, 10)], 175), ([(0, 0), (0, 10)], 174.999),
             ([(10, 30)], 0), ([(10, 30)], 200), ([(0, -180), (0, 180)], 0), ([(90, 0), (-90, 0)], 0), ([(90, 180), (-90, -180)], 3),
             ([(0, 0), (0, 180)], 90), ([(5, -170), (5, 170)], 169.9), ([(1, 2)], 0), ([(1.5, 2.5), (1.5, 2.5)], 0)]
    same = all(M.fit_bounds(p, d) == reference_fit(p, d) for p, d in fixed)
    check(same, f"{len(fixed)} hand-picked valid inputs (edges, date line, poles, the 360 threshold): identical results")
    rnd = random.Random(11)
    diff = 0
    for k in range(2000):
        n = rnd.randint(1, 6)
        pts = [(round(rnd.uniform(-90, 90), rnd.choice((0, 2, 6))), round(rnd.uniform(-180, 180), rnd.choice((0, 2, 6)))) for _ in range(n)]
        if rnd.random() < 0.3:
            pts = [(lat, rnd.choice((-180, 180, 179.5, -179.5))) for lat, _ in pts]
        pts = [(int(a) if rnd.random() < 0.2 else a, b) for a, b in pts]
        pad = rnd.choice((0, 0.5, 1, 10, 90, 179, 180, 250, rnd.uniform(0, 200)))
        if M.fit_bounds(pts, pad) != reference_fit(pts, pad):
            diff += 1
    check(diff == 0, f"2000 random valid inputs (ints, floats, +-180, large pads): identical results (differences {diff})")
    check(M.fit_bounds([[1, 10], [3, 20]]) == M.fit_bounds([(1, 10), (3, 20)]), "lists [lat, lon] are accepted like tuples")
    check(M.fit_bounds(iter([(1, 10), (3, 20)])) == M.fit_bounds([(1, 10), (3, 20)]), "any iterable of pairs is accepted, as before")
    check(not M.check_bounds(M.fit_bounds([(90, 180), (-90, -180)])), "pole/date-line corner points give a valid box")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M1 FIX2 TESTS PASSED" if not f else "MAP MOTION M1 FIX2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
