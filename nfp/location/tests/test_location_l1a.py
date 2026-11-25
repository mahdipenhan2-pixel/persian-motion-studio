#!/usr/bin/env python3
"""L1a - Location Engine base records + QC (nfp.locations/1). Offline, no files written.

  python3 nfp/location/tests/test_location_l1a.py

All coordinates here are SYNTHETIC test values (not claims about real places).
"""
import copy
import datetime
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
import location as L                  # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def place(**over):
    r = {"id": "test-place", "kind": "city", "point": {"lat": 12.3456, "lon": 45.6789}, "datum": "WGS84",
         "precision": "exact", "uncertainty_m": 50,
         "sources": [{"type": "gazetteer", "title": "Test gazetteer (synthetic)", "author": None,
                      "url": "https://example.org/gazetteer/test-place", "accessed": "2026-11-20", "page": None,
                      "license": None, "citation": None}],
         "reviewed": {"by": "test reviewer", "date": "2026-11-21"},
         "confidence": {"level": "high", "reason": "synthetic test record"},
         "notes": "synthetic test data"}
    r.update(over)
    return r


def doc(*rows):
    return {"schema": "nfp.locations/1", "locations": list(rows)}


def run(*rows, today=TODAY):
    return L.validate(doc(*rows), today=today)


def codes(rep, level=None):
    return [x["code"] for x in rep["issues"] if level is None or x["level"] == level]


def st(rep, lid="test-place"):
    return rep["locations"].get(lid)


def main():
    print("== schema and structure")
    r = run(place())
    check(r["status"] == "OK" and st(r) == "verified" and not codes(r, "error") and not codes(r, "warning"),
          f"a complete record: verified, QC OK {codes(r)}")
    for bad, code in (({"schema": "nfp.locations/2", "locations": []}, "schema"), ({"locations": []}, "schema"),
                      ({"schema": "nfp.locations/1", "locations": {}}, "schema"), ([], "schema"),
                      ({"schema": "nfp.locations/1", "locations": [], "extra": 1}, "schema")):
        check(code in codes(L.validate(bad, today=TODAY), "error"), f"document refused: {json.dumps(bad)[:60]}")
    r = run(place(names=[{"text": "x"}]), place(id="p2", parent="p1"))
    check(codes(r, "error").count("schema") == 2 and all(st(r, i) == "draft" for i in ("test-place", "p2")),
          "unknown fields refused (names = L1b, parent = L1c): not accepted early")
    for k in L.FIELDS:
        if k == "id":
            continue
        row = place()
        del row[k]
        r = run(row)
        check("schema" in codes(r, "error") and st(r) == "draft", f"missing field '{k}' refused (null must be written)")
    r = run(place(), place(), place(id="bad id"), place(id="-x"), place(id=7), "row")
    check(codes(r, "error").count("duplicate_id") == 1 and codes(r, "error").count("bad_id") == 3 and "schema" in codes(r, "error"),
          "duplicate id, malformed ids and a non-object row refused")
    for k, v, code in (("kind", "castle", "bad_kind"), ("datum", "ED50", "bad_datum"), ("datum", None, "bad_datum"),
                       ("precision", "rough", "bad_precision"), ("notes", 5, "schema")):
        r = run(place(**{k: v}))
        check(code in codes(r, "error") and st(r) == "draft", f"{k} {v!r} refused ({code})")
    check(len(L.KINDS) == 14 and "route-point" in L.KINDS and L.PRECISIONS == ("exact", "approximate", "centroid", "uncertain"),
          "kinds and precisions as designed")

    print("\n== coordinates: types, NaN, ranges")
    for lat, lon, code in (("12.3", 45.0, "not_a_number"), (12.3, "45", "not_a_number"), (None, 45.0, "not_a_number"),
                           (True, 45.0, "not_a_number"), ([1], 45.0, "not_a_number"), (float("nan"), 45.0, "not_finite"),
                           (12.0, float("inf"), "not_finite"), (12.0, float("-inf"), "not_finite"),
                           (90.0000001, 0.5, "lat_range"), (-90.5, 0.5, "lat_range"), (10.0, 180.0001, "lon_range"),
                           (10.0, -181, "lon_range")):
        r = run(place(point={"lat": lat, "lon": lon}))
        check(code in codes(r, "error") and st(r) == "draft", f"lat {lat!r} lon {lon!r}: {code}, stays draft")
    for pt in ({"lat": 1}, {"lat": 1, "lon": 2, "alt": 3}, [1, 2], "1,2", None):
        r = run(place(point=pt))
        check("bad_point" in codes(r, "error"), f"malformed point refused: {pt!r}")
    edges = [(90, 0.5), (-90, 0.5), (0.5, 180), (0.5, -180), (90.0, 180.0), (-90.0, -180.0)]
    ok = all(not codes(run(place(point={"lat": a, "lon": b}, precision="approximate", uncertainty_m=10)), "error") for a, b in edges)
    check(ok, f"the exact limits are valid: {edges}")
    raw = '{"schema": "nfp.locations/1", "locations": [' + json.dumps(place())[:-1].replace('"lat": 12.3456', '"lat": NaN') + "}]}"
    r = L.validate(json.loads(raw), today=TODAY)
    check("not_finite" in codes(r, "error"), "a NaN written in the JSON file itself is caught")

    print("\n== swapped lat / lon (a warning, never a silent fix)")
    r = run(place(point={"lat": 120.5, "lon": 33.25}))
    check("lat_range" in codes(r, "error") and "maybe_swapped" in codes(r, "warning") and "maybe_swapped" not in codes(r, "error")
          and r["locations"]["test-place"] == "draft",
          "lat 120.5 / lon 33.25: the range error stays, 'maybe swapped' is only a warning, nothing is swapped")
    r = run(place(point={"lat": -150.0, "lon": 200.0}))
    check("maybe_swapped" not in codes(r), "both out of range: no swap suggestion")
    r = run(place(point={"lat": 33.25, "lon": 12.75}))
    check("maybe_swapped" not in codes(r) and st(r) == "verified", "both in range: not detectable in L1a (needs an area, L1c)")

    print("\n== precision and uncertainty")
    r = run(place(point={"lat": 0, "lon": 0}, precision="approximate", uncertainty_m=100))
    check("null_island" in codes(r, "warning"), "0, 0 warns (usually a missing value)")
    r = run(place(point={"lat": 12.123456789, "lon": 45.5}))
    check("false_precision" in codes(r, "warning"), "9 decimals warn (false precision)")
    r = run(place(point={"lat": 12.5, "lon": 45.25}))
    check("precision_mismatch" in codes(r, "warning"), "exact with fewer than 3 decimals warns")
    r = run(place(uncertainty_m=5000))
    check("precision_mismatch" in codes(r, "warning") and st(r) == "verified", "exact with 5 km uncertainty warns (still verified)")
    r = run(place(precision="uncertain", uncertainty_m=None))
    check("no_uncertainty" in codes(r, "warning"), "uncertain without uncertainty_m warns")
    for u in (-1, float("nan"), "50", True):
        r = run(place(uncertainty_m=u))
        check("bad_uncertainty" in codes(r, "error"), f"uncertainty_m {u!r} refused")
    r = run(place(uncertainty_m=None))
    check(st(r) == "verified" and not codes(r, "warning"), "exact with uncertainty_m null: allowed")

    print("\n== sources: what makes one complete (a URL alone does not)")
    src = place()["sources"][0]
    url_only = dict(src, type=None, title=None)
    r = run(place(sources=[url_only]))
    check(st(r) == "draft" and "incomplete_source" in codes(r, "info") and "no complete source" in json.dumps(r["issues"]),
          "a URL alone (no type, no title): incomplete, the place stays draft")
    r = run(place(sources=[dict(src, accessed=None)]))
    check(st(r) == "draft", "a URL without its accessed date: incomplete")
    for variant, why in ((dict(src, url=None, accessed=None, citation="Test atlas, sheet 4"), "citation"),
                         (dict(src, url=None, accessed=None, author="A. Surveyor", page="p. 12"), "author + page")):
        check(st(run(place(sources=[variant]))) == "verified", f"complete without a URL: {why}")
    for s, code in ((dict(src, type="blog"), "bad_source_type"), (dict(src, url="example.org/x"), "bad_url"),
                    (dict(src, accessed="20-11-2026"), "bad_date"), (dict(src, accessed="2026-02-30"), "bad_date"),
                    (dict(src, accessed="2027-01-01"), "bad_date"), (dict(src, extra=1), "schema"),
                    ({k: v for k, v in src.items() if k != "license"}, "schema"), (dict(src, title=5), "schema"), ("text", "schema")):
        r = run(place(sources=[s]))
        check(code in codes(r, "error") and st(r) == "draft", f"malformed source refused: {code}")
    check(st(run(place(sources=[]))) == "draft" and "schema" in codes(run(place(sources=None)), "error"),
          "no sources: draft; sources null: refused (write [])")
    r = run(place(sources=[url_only, src]))
    check(st(r) == "verified", "one complete source among incomplete ones is enough")

    print("\n== review and confidence")
    for rv, ok_ in ((None, False), ({"by": "x", "date": "2026-11-21"}, True), ({"by": "", "date": "2026-11-21"}, False),
                    ({"by": "x", "date": "2026-13-01"}, False), ({"by": "x", "date": "2026-11-26"}, False),
                    ({"by": "x"}, False)):
        r = run(place(reviewed=rv))
        check((st(r) == "verified") == ok_, f"reviewed {rv!r}: {'verified' if ok_ else 'draft'}")
    for cf, ok_, code in ((None, False, None), ({"level": "medium", "reason": "two sources agree"}, True, None),
                          ({"level": "low", "reason": "one old map"}, True, "low_confidence"),
                          ({"level": "certain", "reason": "x"}, False, "bad_confidence"),
                          ({"level": "high", "reason": ""}, False, "schema"), ({"level": "high"}, False, "schema")):
        r = run(place(confidence=cf))
        check((st(r) == "verified") == ok_ and (code is None or code in codes(r)), f"confidence {cf!r}: "
                                                                               f"{'verified' if ok_ else 'draft'}{' + ' + code if code else ''}")
    r = run(place(reviewed={"by": "x", "date": "2026-11-25"}))
    check(st(r) == "verified", "reviewed today: allowed (the date is compared with the 'today' given)")
    check(st(run(place(), today=datetime.date(2026, 11, 20))) == "draft",
          "the same record checked 'before' its review date: not verified (no future dates)")

    print("\n== draft reasons, determinism, independence")
    r = run(place(sources=[], reviewed=None, confidence=None, point={"lat": "x", "lon": 1}))
    msg = [x["message"] for x in r["issues"] if x["code"] == "draft"][0]
    check(all(w in msg for w in ("coordinates", "complete source", "reviewed", "confidence")), f"the draft says why: {msg}")
    base = place()
    run(base)
    check(base == place(), "validate() does not change the record it checks")
    d1 = json.dumps(L.validate(doc(place(), place(id="b", point={"lat": 120, "lon": 1})), today=TODAY))
    d2 = json.dumps(L.validate(doc(place(), place(id="b", point={"lat": 120, "lon": 1})), today=TODAY))
    check(d1 == d2, "deterministic: the same input gives the same report")
    src_code = "".join(p.read_text(encoding="utf-8") for p in (HERE.parent).glob("*.py"))
    mods = sorted(set(re.findall(r"^\s*(?:from|import) ([\w.]+)", src_code, re.M)))
    check(set(mods) <= {"argparse", "datetime", "json", "math", "re", "pathlib", "sys", "unicodedata", ".", ".model", ".names",
                        ".geo", ".hierarchy", "location", "location.hierarchy"},
          f"nfp/location imports only the standard library and itself {mods}")
    check(not re.search(r"urllib|requests|http\.client|socket|subprocess", src_code), "no network or process code in nfp/location")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL LOCATION L1a TESTS PASSED" if not f else "LOCATION L1a TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
