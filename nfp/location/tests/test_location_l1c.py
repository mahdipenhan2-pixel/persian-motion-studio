#!/usr/bin/env python3
"""L1c - Location Engine: parent relationships, geographic extent (incl. the date line), possible duplicates, the
command line. Offline; the CLI runs on files in a temporary folder that is removed afterwards.

  python3 nfp/location/tests/test_location_l1c.py

Every coordinate, box and name here is SYNTHETIC test data, not a claim about a real place.
"""
import copy
import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent.parent), str(HERE)]
import location as L                        # noqa: E402
from test_location_l1a import place, doc    # noqa: E402  (L1a record builder, unchanged)

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
CLI = HERE.parent / "cli.py"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def run(*rows, **kw):
    return L.validate(doc(*rows), today=TODAY, **kw)


def codes(rep, level=None, loc=None):
    return [x["code"] for x in rep["issues"] if (level is None or x["level"] == level) and (loc is None or x.get("location") == loc)]


def box(n, s, e, w):
    return {"north": n, "south": s, "east": e, "west": w}


def loc(lid, lat, lon, **kw):
    return place(id=lid, point={"lat": lat, "lon": lon}, **kw)


# a synthetic three-level hierarchy: country > region > town (+ a building in the town)
COUNTRY = loc("t-country", 30.5, 50.5, kind="country", precision="centroid", uncertainty_m=100000, extent=box(35, 25, 56, 44))
REGION = loc("t-region", 32.25, 51.75, kind="region", precision="centroid", uncertainty_m=20000, extent=box(33.5, 31, 53, 50.5),
             parent={"id": "t-country", "relation": "administrative"})
TOWN = loc("t-town", 32.6543, 51.6789, kind="town", parent={"id": "t-region", "relation": "within"})
GATE = loc("t-gate", 32.6544, 51.679, kind="building", parent={"id": "t-town", "relation": "part_of"})


def main():
    print("== compatibility")
    r = run(place())
    check(r["locations"]["test-place"] == "verified" and r["status"] == "OK" and r["duplicates"] == [],
          "an L1a record (no parent / extent): unchanged - verified, OK, no duplicates")

    print("\n== parent relationships")
    r = run(COUNTRY, REGION, TOWN, GATE)
    check(r["status"] == "OK" and all(v == "verified" for v in r["locations"].values()) and not codes(r, "warning"),
          f"a valid 4-level hierarchy: all verified, no warnings {codes(r, 'warning')}")
    idx = {x["id"]: x for x in (COUNTRY, REGION, TOWN, GATE)}
    check(L.ancestors(idx, "t-gate") == ["t-town", "t-region", "t-country"] and L.ancestors(idx, "t-country") == [],
          "ancestors(): the chain up to the root, without any other engine")
    r = run(loc("a", 1.5, 1.5, parent={"id": "nowhere", "relation": "within"}))
    check("unknown_parent" in codes(r, "error") and r["locations"]["a"] == "draft", "a parent that is not in the file: error, draft")
    r = run(loc("a", 1.5, 1.5, parent={"id": "a", "relation": "within"}))
    check("parent_self" in codes(r, "error") and r["locations"]["a"] == "draft", "its own parent: error")
    r = run(loc("a", 1.5, 1.5, parent={"id": "b", "relation": "within"}), loc("b", 2.5, 2.5, parent={"id": "a", "relation": "within"}))
    check(codes(r, "error", "a") == ["parent_cycle"] and codes(r, "error", "b") == ["parent_cycle"], "a 2-cycle: both places reported")
    three = [loc("a", 1.5, 1.5, parent={"id": "b", "relation": "within"}), loc("b", 2.5, 2.5, parent={"id": "c", "relation": "within"}),
             loc("c", 3.5, 3.5, parent={"id": "a", "relation": "within"}), loc("d", 4.5, 4.5, parent={"id": "a", "relation": "within"})]
    r = run(*three)
    check(all(codes(r, "error", x) == ["parent_cycle"] for x in "abc") and "parent_cycle" not in codes(r, None, "d"),
          "a 3-cycle: its three members reported; a place hanging below the cycle is not on it")
    try:
        L.ancestors({x["id"]: x for x in three}, "d")
        raised = False
    except ValueError:
        raised = True
    check(raised, "ancestors() of a place below a cycle stops with an error (never loops)")
    for p, code in (("t-region", "schema"), ({"id": "t-region"}, "schema"), ({"id": "t-region", "relation": "near"}, "bad_relation"),
                    ({"id": "", "relation": "within"}, "bad_parent"), ({"id": 5, "relation": "within"}, "bad_parent"),
                    ({"id": "t-region", "relation": "within", "x": 1}, "schema")):
        r = run(COUNTRY, REGION, loc("x-town", 32.5, 51.5, parent=p))
        check(code in codes(r, "error", "x-town") and r["locations"]["x-town"] == "draft", f"parent {p!r}: {code}")
    r = run(COUNTRY, REGION, loc("x-town", 40.5, 60.5, parent={"id": "t-region", "relation": "within"}))
    check("outside_parent" in codes(r, "warning", "x-town") and r["locations"]["x-town"] == "verified",
          "a point outside its parent's extent: warning (not refused, nothing changed)")
    r = run(COUNTRY, REGION, loc("x-town", 51.5, 32.5, parent={"id": "t-region", "relation": "within"}))
    msg = [x["message"] for x in r["issues"] if x["code"] == "outside_parent"]
    check(msg and "swapped" in msg[0], "outside the parent but inside with lat / lon swapped: the warning says so (a hint only)")
    r = run(COUNTRY, REGION, loc("x-town", 40.5, 60.5, parent={"id": "t-region", "relation": "historical"}))
    check("outside_parent" not in codes(r), "relation 'historical': no geometric check (a former realm need not contain it)")
    r = run(COUNTRY, loc("x-reg", 30.5, 50.5, extent=box(40, 20, 60, 45), parent={"id": "t-country", "relation": "within"}))
    check("extent_outside_parent" in codes(r, "warning", "x-reg"), "an extent sticking out of its parent's extent: warning")
    r = run(dict(COUNTRY, reviewed=None), REGION)
    check(r["locations"]["t-country"] == "draft" and r["locations"]["t-region"] == "verified" and not codes(r, "error"),
          "a draft parent is allowed (the child keeps its own status)")
    check(set(L.RELATIONS) == {"within", "part_of", "administrative", "historical"}, "relations: within, part_of, administrative, historical")

    print("\n== geographic extent (bounding box)")
    r = run(loc("e", 32.5123, 51.5123, extent=box(33, 32, 52, 51)))
    check(r["status"] == "OK" and r["locations"]["e"] == "verified", "a valid box around its point: OK")
    for e, code in ((box(32, 33, 52, 51), "extent_reversed"), (box(91, 32, 52, 51), "extent_range"), (box(33, -91, 52, 51), "extent_range"),
                    (box(33, 32, 181, 51), "extent_range"), (box(33, 32, 52, -180.5), "extent_range"),
                    (box(33, 32, float("nan"), 51), "bad_extent"), (box("33", 32, 52, 51), "bad_extent"), (box(33, 32, True, 51), "bad_extent"),
                    ({"north": 33, "south": 32, "east": 52}, "bad_extent"), ([33, 32, 52, 51], "bad_extent"),
                    (dict(box(33, 32, 52, 51), top=1), "bad_extent")):
        r = run(loc("e", 32.5, 51.5, extent=e))
        check(code in codes(r, "error") and r["locations"]["e"] == "draft", f"extent {json.dumps(e)[:60]}: {code}")
    dl = box(-15, -20, -175, 175)                          # over the date line: 175E .. 180 .. 175W (10 degrees wide)
    r = run(loc("pacific", -17.5, 178.25, precision="approximate", uncertainty_m=1000, extent=dl))
    check(not codes(r, "error") and not codes(r, "warning"), "west 175 > east -175: a 10-degree box over the date line, valid")
    check(all(L.contains_point(dl, -17.5, x) for x in (175, 178, 180, -180, -178, -175)) and
          not any(L.contains_point(dl, -17.5, x) for x in (174.9, 0, -174.9, 90)) and not L.contains_point(dl, -21, 178),
          "date-line containment: 175..180 and -180..-175 inside (180 = -180), 174.9 / 0 / -174.9 outside")
    r = run(loc("w", 1.5, 1.5, precision="approximate", uncertainty_m=1000, extent=box(5, -5, -10, 10)))
    check("extent_maybe_swapped" in codes(r, "warning") and not codes(r, "error"),
          "west 10 > east -10 reads as a 340-degree box over the date line: a warning that east / west may be swapped")
    world = box(90, -90, 180, -180)
    check(not codes(run(loc("g", 0.5, 0.5, kind="other", precision="centroid", uncertainty_m=1, extent=world)), "error") and
          L.contains_point(world, 89, -179.9) and L.contains_extent(world, dl), "west -180 / east 180: the whole circle of longitude")
    check("extent_degenerate" in codes(run(loc("z", 1.5, 1.5, extent=box(2, 1, 1.5, 1.5))), "warning"), "a box with no width: warning")
    r = run(loc("e", 40.5, 51.5, extent=box(33, 32, 52, 51)))
    check("point_outside_extent" in codes(r, "warning") and r["locations"]["e"] == "verified", "a point outside its own box: warning")
    check(L.contains_extent(dl, box(-16, -19, -177, 177)) and not L.contains_extent(dl, box(-16, -19, -170, 177)) and
          L.contains_extent(box(10, -10, 20, -20), box(5, -5, 10, -10)) and not L.contains_extent(box(10, -10, 20, -20), dl),
          "box-in-box, also across the date line")

    print("\n== possible duplicates (warnings only, nothing merged)")
    a, b = loc("dup-a", 10.12345, 20.12345), loc("dup-b", 10.12345, 20.12345)
    r = run(a, b)
    check(codes(r, "warning", "dup-a") == ["same_point"] and codes(r, "warning", "dup-b") == ["same_point"] and
          r["duplicates"] == [{"a": "dup-a", "b": "dup-b", "reason": "same_point", "distance_m": 0.0, "detail": "identical coordinates"}]
          and all(v == "verified" for v in r["locations"].values()),
          "identical points: a warning on both naming the other, listed in 'duplicates'; statuses unchanged")
    msg = [x["message"] for x in r["issues"] if x["code"] == "same_point" and x["location"] == "dup-a"][0]
    check("'dup-b'" in msg and "nothing merged" in msg, f"the warning names the other id and says nothing was merged")
    near = loc("dup-c", 10.12345 + 0.00027, 20.12345)       # ~30 m north
    far = loc("dup-d", 10.12345 + 0.0009, 20.12345)         # ~100 m north
    r = run(a, near, far)
    pairs = {(d["a"], d["b"], d["reason"]) for d in r["duplicates"]}
    check(("dup-a", "dup-c", "near_point") in pairs and not any("dup-d" in (x, y) for x, y, _ in pairs),
          f"30 m apart: near_point (default threshold 50 m); 100 m: nothing {sorted(pairs)}")
    check(any(d["reason"] == "near_point" and "dup-d" in (d["a"], d["b"]) for d in run(a, far, near_m=150)["duplicates"]) and
          not run(a, near, near_m=10)["duplicates"], "the threshold is a parameter: 150 m finds the 100 m pair, 10 m drops the 30 m pair")
    d30 = [d["distance_m"] for d in r["duplicates"] if d["b"] == "dup-c"][0]
    check(29 < d30 < 31.5, f"the reported distance is right ({d30} m for 0.00027 degrees of latitude)")
    n1 = loc("n1", 10.1, 20.1, names=[{"text": "تستيك", "lang": "fa", "type": "current"}])      # Arabic YEH / KAF
    n2 = loc("n2", 10.12, 20.1, names=[{"text": "تستیک", "lang": "fa", "type": "historical", "from": 100, "to": 200}])
    r = run(n1, n2)
    check([d["reason"] for d in r["duplicates"]] == ["same_name_near"] and 2000 < r["duplicates"][0]["distance_m"] < 2400,
          "same name (Persian letters normalized) ~2.2 km apart: same_name_near (default 5 km)")
    n3 = dict(n2, names=[{"text": "دیگر", "lang": "fa", "type": "current"}])
    check(run(n1, n3)["duplicates"] == [] and run(n1, n2, name_m=1000)["duplicates"] == [],
          "different names 2.2 km apart: nothing; same names with a 1 km name threshold: nothing")
    r = run(COUNTRY, REGION, dict(TOWN), dict(GATE, point=dict(TOWN["point"])))
    check(not r["duplicates"], "a building at its town's very point is not a duplicate (parent / child)")
    old = loc("old-city", 10.5432, 20.5432, distinct_from=["new-city"])
    new = loc("new-city", 10.5432, 20.5432)
    r = run(old, new)
    check(r["duplicates"] == [] and not codes(r, "warning") and not codes(r, "error"),
          "an ancient and a modern city on the same spot, marked distinct_from: no warning, both kept")
    r = run(loc("x", 1.5, 1.5, distinct_from=["nobody"]))
    check("bad_distinct" in codes(r, "error") and r["locations"]["x"] == "draft", "distinct_from an id not in the file: error")
    check("bad_distinct" in codes(run(loc("x", 1.5, 1.5, distinct_from=["x"])), "error") and
          "schema" in codes(run(loc("x", 1.5, 1.5, distinct_from="y")), "error"), "distinct_from itself / not a list: refused")
    rows = [copy.deepcopy(a), copy.deepcopy(b), copy.deepcopy(near)]
    before = json.dumps(rows)
    L.validate(doc(*rows), today=TODAY)
    check(json.dumps(rows) == before, "duplicate detection never changes the records")
    check(abs(L.distance_m(0, 0, 1, 0) - 111194.93) < 1 and L.distance_m(10, 20, 10, 20) == 0 and
          abs(L.distance_m(0, 179.9, 0, -179.9) - L.distance_m(0, 0, 0, 0.2)) < 1e-6,
          "distance: 1 degree of latitude = 111.195 km; zero; across the date line = the short way")
    for bad in (-1, float("nan"), "50"):
        try:
            run(a, near_m=bad)
            ok = False
        except ValueError:
            ok = True
        check(ok, f"a bad threshold {bad!r} is refused")
    r1, r2 = json.dumps(run(a, b, near, far, n1, n2)), json.dumps(run(far, near, b, a, n2, n1))
    check(sorted(json.loads(r1)["duplicates"], key=json.dumps) == sorted(json.loads(r2)["duplicates"], key=json.dumps),
          "the same pairs whatever order the file lists the places in")

    print("\n== command line")
    with tempfile.TemporaryDirectory(prefix="nfp-location-l1c-") as td:
        td = Path(td)
        good = td / "good.json"
        good.write_text(json.dumps(doc(COUNTRY, REGION, TOWN, GATE, old, new, dict(place(id="draft-one"), reviewed=None)),
                                   ensure_ascii=False), encoding="utf-8")
        bad = td / "bad.json"
        bad.write_text(json.dumps(doc(loc("a", 1.5, 1.5, parent={"id": "b", "relation": "within"}),
                                      loc("b", 2.5, 2.5, parent={"id": "a", "relation": "within"}), a, b)), encoding="utf-8")
        (td / "broken.json").write_text("{not json", encoding="utf-8")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def cli(*args):
            return subprocess.run([sys.executable, "-B", str(CLI), *map(str, args)], capture_output=True, text=True, env=env)
        r = cli("check", good, "--today", "2026-11-25")
        check(r.returncode == 0 and "QC OK" in r.stdout, f"check (valid file): exit 0, {r.stdout.strip().splitlines()[-1]}")
        r = cli("check", bad, "--today", "2026-11-25")
        check(r.returncode == 1 and "parent_cycle" in r.stdout and "same_point" in r.stdout, "check (cycle + duplicates): exit 1, both shown")
        r = cli("status", good, "--today", "2026-11-25")
        check(r.returncode == 0 and "verified  t-gate" in r.stdout and "draft     draft-one" in r.stdout and "not reviewed" in r.stdout
              and "6 verified, 1 draft" in r.stdout, "status: verified / draft per place, with the draft's reason")
        r = cli("parents", good, "--id", "t-gate")
        check(r.returncode == 0 and "t-gate  -part_of->  t-town  ->  t-region  ->  t-country" in r.stdout, "parents --id: the chain")
        r = cli("parents", bad)
        check(r.returncode == 1 and "cycle" in r.stdout and "parent_cycle" in r.stdout, "parents (cycle): reported, exit 1")
        r = cli("duplicates", bad, "--near-m", "10")
        check(r.returncode == 0 and "same_point" in r.stdout and "nothing merged" in r.stdout and "near: 10 m" in r.stdout,
              "duplicates: pairs with distance and reason; the thresholds are printed")
        for args, want in ((("check", td / "broken.json"), "not valid JSON"), (("check", td / "missing.json"), "cannot read"),
                           (("check", good, "--today", "25/11/2026"), "--today"), (("parents", good, "--id", "nope"), "no location"),
                           (("check", good, "--near-m", "-5"), "near_m")):
            r = cli(*args)
            check(r.returncode == 2 and want in r.stderr, f"{' '.join(str(x) for x in args[:1])} {args[-1] if len(args) > 2 else ''}: "
                                                          f"exit 2, clear message ({r.stderr.strip()[:60]})")
        check(json.loads(good.read_text(encoding="utf-8")) == doc(COUNTRY, REGION, TOWN, GATE, old, new,
                                                                  dict(place(id="draft-one"), reviewed=None)),
              "the command line never changes the file it reads")
    check(not list(Path(tempfile.gettempdir()).glob("nfp-location-l1c-*")), "the temporary folder is gone")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL LOCATION L1c TESTS PASSED" if not f else "LOCATION L1c TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
