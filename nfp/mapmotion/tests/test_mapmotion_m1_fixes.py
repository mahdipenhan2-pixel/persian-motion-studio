#!/usr/bin/env python3
"""M1 audit fixes - Map Motion: (1) only Location's public API, (2) no hidden system clock (today is required),
(3) whole-world route ends vs stop markers + 'inside' = the map area, (4) near-antipodal warning, (5) fit_bounds with a
padded arc of 360 degrees or more. Offline, nothing written. All data SYNTHETIC.

  python3 nfp/mapmotion/tests/test_mapmotion_m1_fixes.py
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
import location as L                           # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402
from test_mapmotion_m1 import mapdoc, LDOC     # noqa: E402  (the M1 test fixtures, unchanged)

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
SRC = {p.name: p.read_text(encoding="utf-8") for p in (NFP / "mapmotion").glob("*.py")}


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def codes(p, level=None):
    return [x["code"] for x in p["qc"]["issues"] if level is None or x["level"] == level]


def msgs(p, code):
    return [x["message"] for x in p["qc"]["issues"] if x["code"] == code]


def base(**o):
    d = {"schema": "nfp.mapmotion/1", "id": "fix-map", "mode": "final", "window": {"start": 0, "end": 300},
         "labels": {"lang": "en", "year": None}, "points": [], "routes": [], "areas": []}
    d.update(o)
    return d


def main():
    print("== 1. Location's public API only")
    used = sorted(set(re.findall(r"\bLOC\.(\w+)", SRC["model.py"])))
    check(set(used) <= set(L.__all__), f"model.py uses only names in location.__all__: {used}")
    check(not re.search(r"LOC\.(model|names)\b|NameError_", "".join(SRC.values())),
          "no location.model / location.names internals, no NameError_ (Location's name errors are caught as ValueError)")
    p = M.build(mapdoc(id="bad id", labels={"lang": "Persian"}), LDOC, today=TODAY)
    check({"bad_id", "schema"} <= set(codes(p, "error")), "map id and language codes are still validated (own patterns)")
    check(M.model.ID_RE.pattern == L.model.ID_RE.pattern and M.model.LANG_RE.pattern == L.names.LANG_RE.pattern,
          "the own patterns are the same rules Location uses (compared here in the test only)")
    tie = ldoc(loc("t1", 10.1234, 20.1234, names=[{"text": "A", "lang": "en", "type": "historical", "from": 100, "to": 300},
                                                 {"text": "B", "lang": "en", "type": "historical", "from": 200, "to": 400}]))
    p = M.build(base(mode="draft", viewport={"bounds": {"north": 11, "south": 9, "west": 19, "east": 21}}, labels={"lang": "en", "year": 250},
                     points=[{"id": "p", "location": "t1", "start": 0, "end": 300}]), tie, today=TODAY)
    check("label" in codes(p, "error") and "location_file" in codes(p, "error"),
          "an ambiguous name from Location (its ValueError) becomes a 'label' error, not a crash")

    print("\n== 2. no hidden system clock: today is required")
    for bad, want in ((None, "needs today"), (datetime.datetime(2026, 11, 25, 12, 0), "datetime.date"),
                      ("2026-11-25", "datetime.date"), (20261125, "datetime.date")):
        try:
            M.build(mapdoc(), LDOC, today=bad)
            msg = "accepted"
        except ValueError as e:
            msg = str(e)
        check(want in msg, f"today={bad!r}: refused with a clear message ({msg[:70]})")
    try:
        M.build(mapdoc(), LDOC)
        msg = "accepted"
    except ValueError as e:
        msg = str(e)
    check("system clock is never used" in msg, "build() without today: refused")
    check(not re.search(r"date\.today|datetime\.now|time\.time|utcnow", "".join(SRC.values())),
          "no clock call anywhere in nfp/mapmotion")
    reviewed_later = ldoc(dict(loc("ta", 10.1234, 20.1234), reviewed={"by": "x", "date": "2026-11-21"}))
    early = M.build(base(viewport={"bounds": {"north": 11, "south": 9, "west": 19, "east": 21}},
                         points=[{"id": "p", "location": "ta", "start": 0, "end": 300}]), reviewed_later, today=datetime.date(2026, 11, 20))
    late = M.build(base(viewport={"bounds": {"north": 11, "south": 9, "west": 19, "east": 21}},
                        points=[{"id": "p", "location": "ta", "start": 0, "end": 300}]), reviewed_later, today=TODAY)
    check("location_file" in codes(early, "error") and not codes(late, "error"),
          "the result depends on the given date only (a review dated after 'today' is an error then, fine later)")

    print("\n== 3. whole-world routes and 'inside' = the map area")
    locs = ldoc(loc("w", 1.2345, 178.5), loc("e", 2.3456, -178.5), loc("m", 3.4567, 100.25))
    world = M.build(base(viewport={"bounds": {"north": 60, "south": -60, "west": -180, "east": 180}},
                         points=[{"id": "pe", "location": "e", "start": 0, "end": 300}],
                         routes=[{"id": "r", "stops": ["w", "e"], "start": 0, "end": 300, "samples": 16}]), locs, today=TODAY)
    m = msgs(world, "route_wraps")
    end_x = world["routes"][0]["legs"][0]["xy"][-1][0]
    marker_x = world["points"][0]["x"]
    check(m and "'w' -> 'e'" in m[0] and "360" in m[0] and "M2" in m[0] and abs(end_x - marker_x) > 1000,
          f"whole-world map, 178.5E -> 178.5W: QC 'route_wraps' names the leg and both x (route end {end_x:.0f}, marker {marker_x:.0f})")
    check("outside_map" in codes(world, "warning") and world["routes"][0]["legs"][0]["xy"][-1] == [round(end_x, 3), world["routes"][0]["legs"][0]["xy"][-1][1]],
          "the part beyond the map edge is reported 'outside_map'; the plan's coordinates are left as they are (no split in M1)")
    dl = M.build(base(viewport={"fit": {"locations": ["w", "e"], "pad_deg": 1}},
                      points=[{"id": "pw", "location": "w", "start": 0, "end": 300}, {"id": "pe", "location": "e", "start": 0, "end": 300}],
                      routes=[{"id": "r", "stops": ["w", "e"], "start": 0, "end": 300, "samples": 16}]), locs, today=TODAY)
    xy = dl["routes"][0]["legs"][0]["xy"]
    check(not {"route_wraps", "outside_map", "outside_frame"} & set(codes(dl)) and not codes(dl, "error") and xy[0][0] == dl["points"][0]["x"] and xy[-1][0] == dl["points"][1]["x"] and all(p["inside"] for p in dl["points"]),
          "a regional map over the date line: no wrap or outside warning, the route starts and ends exactly on its two markers")
    margin = M.build(base(viewport={"bounds": {"north": 4, "south": 0, "west": 99, "east": 100}},
                          points=[{"id": "pm", "location": "m", "start": 0, "end": 300}]), locs, today=TODAY)
    pm = margin["points"][0]
    check(pm["inside"] is False and "outside_map" in codes(margin, "warning") and "outside_frame" not in codes(margin) and 0 <= pm["x"] <= 1920,
          f"a place visible in the frame margin but east of the map bounds: inside=false, 'outside_map' (x {pm['x']:.0f})")
    far = M.build(base(viewport={"bounds": {"north": 4, "south": 0, "west": 10, "east": 11}},
                       points=[{"id": "pm", "location": "m", "start": 0, "end": 300}]), locs, today=TODAY)
    check(far["points"][0]["inside"] is False and "outside_frame" in codes(far, "warning") and "outside_map" not in codes(far),
          "a place outside the frame altogether: 'outside_frame' (not both)")
    p = M.Equirectangular({"north": 10, "south": -10, "east": 10, "west": -10})
    check(p.inside_map(484, 64) and p.inside_map(1436, 1016) and not p.inside_map(483, 540) and p.inside_frame(483, 540),
          "inside_map(): the corners of the fitted box are in, one pixel into the margin is out (but in the frame)")

    print("\n== 4. near-antipodal legs: a warning, the route untouched")
    near = ldoc(loc("a1", 10.25, 20.25), loc("a2", -10.0, -159.0))
    p = M.build(base(mode="draft", viewport={"bounds": {"north": 60, "south": -60, "west": -180, "east": 180}},
                     routes=[{"id": "r", "stops": ["a1", "a2"], "start": 0, "end": 300, "samples": 3}]), near, today=TODAY)
    g = M.leg((10.25, 20.25), (-10.0, -159.0), 3)
    w = msgs(p, "near_antipodal")
    check(g["angle_deg"] > 179 and w and "unstable" in w[0] and "intermediate stop" in w[0] and not codes(p, "error"),
          f"a {g['angle_deg']:.3f}-degree leg: warning 'near_antipodal' (unstable; add an intermediate stop), not an error")
    check(p["routes"] and p["routes"][0]["legs"][0]["geo"][1] == [round(g["points"][1][0], 7), round(g["points"][1][1], 7)],
          "the route is exactly the plain great circle (not pushed to either side)")
    ok178 = ldoc(loc("b1", 0.25, 0.25), loc("b2", 0.25, 178.25))
    p = M.build(base(mode="draft", viewport={"bounds": {"north": 60, "south": -60, "west": -180, "east": 180}},
                     routes=[{"id": "r", "stops": ["b1", "b2"], "start": 0, "end": 300}]), ok178, today=TODAY)
    check("near_antipodal" not in codes(p), "a 178-degree leg: no warning")
    anti = ldoc(loc("c1", 10.5, 20.5), loc("c2", -10.5, -159.5))
    p = M.build(base(mode="draft", viewport={"bounds": {"north": 60, "south": -60, "west": -180, "east": 180}},
                     routes=[{"id": "r", "stops": ["c1", "c2"], "start": 0, "end": 300}]), anti, today=TODAY)
    check("route" in codes(p, "error") and not p["routes"], "exactly antipodal: still refused (unchanged)")

    print("\n== 5. fit_bounds with a large pad")
    check(M.fit_bounds([(0, 178), (0, -179)], 179) == {"north": 90.0, "south": -90.0, "west": -180.0, "east": 180.0},
          "arc 3 + 2 x 179 >= 360: the whole world (was a wrong 1-degree box)")
    check(M.fit_bounds([(0, 0), (0, 10)], 175)["west"] == -180.0 and M.fit_bounds([(0, 0), (0, 10)], 174.9)["west"] != -180.0,
          "the threshold is exactly 360 (arc 10 + 2 x 175 = 360 -> world; 174.9 -> not)")
    check(M.fit_bounds([(1, 10), (3, 20)], 0.5) == {"north": 3.5, "south": 0.5, "west": 9.5, "east": 20.5} and
          M.fit_bounds([(0, 179), (5, -179), (2, 178)]) == {"north": 5, "south": 0, "west": 178, "east": -179},
          "ordinary and date-line boxes unchanged")
    check(M.fit_bounds([(10, 30)], 200)["west"] == -180.0, "a single point padded past 180 on both sides: the whole world")
    p = M.build(base(viewport={"fit": {"locations": ["w", "e"], "pad_deg": 179}}, points=[{"id": "p", "location": "w", "start": 0, "end": 300}]),
                locs, today=TODAY)
    check(p["viewport"]["bounds"]["west"] == -180 and p["viewport"]["bounds"]["east"] == 180 and not codes(p, "error"),
          "a map fitted with such a pad gets a whole-world viewport")

    print("\n== documentation")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    for key, what in (("today", "today required"), ("route_wraps", "whole-world routes"), ("outside_map", "inside = map area"),
                      ("near_antipodal", "near-antipodal"), ("نمونه‌برداری تطبیقی", "adaptive sampling for M2"),
                      ("از روی قطب", "routes over a pole"), ("طول صفر", "zero-length legs"), ("span(180, -180)", "span(180, -180)"),
                      ("استفاده نشده", "strict location file"), ("FAIL", "a failed plan")):
        check(key in rd, f"README documents: {what}")
    print("\n== determinism")
    a = json.dumps(M.build(mapdoc(), LDOC, today=TODAY), sort_keys=True, ensure_ascii=False)
    b = json.dumps(M.build(mapdoc(), LDOC, today=TODAY), sort_keys=True, ensure_ascii=False)
    check(a == b, "the same plan twice")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M1 FIX TESTS PASSED" if not f else "MAP MOTION M1 FIX TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
