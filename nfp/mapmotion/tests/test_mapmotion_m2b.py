#!/usr/bin/env python3
"""M2b - Map Motion scene: local GeoJSON reading (geodata.py) and scene.json (nfp.mapmotion.scene/1) resolved with an
M1 plan and its M2a geometry into a scene plan (nfp.mapmotion.sceneplan/1). Offline. SYNTHETIC data; the GeoJSON and
assets.json test files are written to a temporary folder outside the project and removed at the end.

  python3 nfp/mapmotion/tests/test_mapmotion_m2b.py
"""
import copy
import datetime
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import geodata as GD            # noqa: E402
from test_mapmotion_m1 import mapdoc, LDOC     # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def codes(x, level=None):
    return [i["code"] for i in x["issues"] if level is None or i["level"] == level]


def only_label_estimate(sp):
    """Since M2f, labels without a browser measurement give exactly one warning (label_metrics_estimated): status WARN."""
    return sp["qc"]["status"] == "OK" or (sp["qc"]["status"] == "WARN" and {i["code"] for i in sp["qc"]["issues"]} == {"label_metrics_estimated"})


def qcodes(sp, level=None):
    return [i["code"] for i in sp["qc"]["issues"] if level is None or i["level"] == level]


SQUARE = [[[19.0, 9.0], [22.0, 9.0], [22.0, 12.0], [19.0, 12.0], [19.0, 9.0]]]
LAND = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"name": "Synthetic island"}, "geometry": {"type": "Polygon", "coordinates": SQUARE}},
    {"type": "Feature", "properties": {}, "geometry": {"type": "MultiPolygon", "coordinates": [
        [[[30.0, 20.0], [31.0, 20.0], [31.0, 21.0, 5.0], [30.0, 20.0]]]]}}]}
COAST = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": None, "geometry": {"type": "LineString", "coordinates": [[19.0, 9.0], [22.0, 9.0]]}},
    {"type": "Feature", "properties": None, "geometry": {"type": "MultiLineString", "coordinates": [[[1.0, 1.0], [2.0, 2.0]], [[3.0, 3.0], [4.0, 4.0]]]}}]}


def asset(aid, path, sha, verified=True, kind="map"):
    return {"id": aid, "kind": kind, "local_path": path, "sha256": sha, "width": None, "height": None, "duration": None,
            "source_url": None, "author": "NFP test (synthetic)", "license": "original", "license_url": None,
            "retrieved_at": "2026-11-25", "modifications": "none", "license_verified": verified,
            "attribution": "Synthetic test data", "restrictions": [], "real_person": False}


def write(folder, name, doc):
    p = folder / name
    p.write_text(json.dumps(doc), encoding="utf-8")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    plan = M.build(mapdoc(), LDOC, today=TODAY)
    geo = M.geometry(plan)
    base_scene = {"schema": "nfp.mapmotion.scene/1", "id": "scene-1", "map": plan["map"]}

    print("== GeoJSON reading (geodata.py)")
    g = GD.check_geojson(LAND)
    check(g["features_count"] == 2 and g["positions"] == 9 and [f["type"] for f in g["features"]] == ["Polygon", "MultiPolygon"]
          and g["features"][0]["name"] == "Synthetic island" and g["bbox"] == {"south": 9.0, "north": 21.0, "west": 19.0, "east": 31.0}
          and not g["issues"], "a FeatureCollection of polygons: features in file order, names, [lon, lat] kept, altitude dropped, bbox")
    check(g["features"][1]["coordinates"][0][0][2] == [31.0, 21.0], "the altitude (third value) is ignored")
    check(GD.check_geojson(COAST)["features_count"] == 2 and GD.check_geojson({"type": "Polygon", "coordinates": SQUARE})["features_count"] == 1
          and GD.check_geojson({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}})["features_count"] == 1,
          "lines, a bare geometry and a single Feature are read")
    for doc, code, what in (
            ({"type": "Polygon", "coordinates": [[[9.0, 19.0], [9.0, 100.0], [12.0, 22.0], [9.0, 19.0]]]}, "coordinate", "latitude 100 (swapped order)"),
            ({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}, "geojson", "an unclosed ring"),
            ({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}, "geojson", "a ring of 3 positions"),
            ({"type": "LineString", "coordinates": [[0, 0]]}, "geojson", "a line of 1 position"),
            ({"type": "LineString", "coordinates": [[0, 0], [float("nan"), 1]]}, "geojson", "NaN"),
            ({"type": "LineString", "coordinates": [[0, 0], [True, 1]]}, "geojson", "a bool"),
            ({"type": "LineString", "coordinates": [[0, 0], ["1", 1]]}, "geojson", "a string"),
            ({"type": "LineString", "coordinates": [[0, 0], [1, 1, 1, 1]]}, "geojson", "four values"),
            ({"type": "Curve", "coordinates": []}, "geojson", "an unknown type"),
            ({"features": []}, "geojson", "no type"), ([1, 2], "geojson", "not an object")):
        r = GD.check_geojson(doc)
        check(code in codes(r, "error") and not r["features"], f"refused: {what}")
    r = GD.check_geojson({"type": "FeatureCollection", "crs": {"type": "name"}, "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 1]}}, {"type": "Feature", "geometry": None},
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[179.0, 0.0], [-179.0, 1.0], [-178.0, 2.0]]}}]})
    check(set(codes(r, "warning")) == {"crs", "not_drawn", "antimeridian_segment"} and r["antimeridian_segments"] == 1 and r["features_count"] == 1,
          "warnings: crs member, a Point and a feature without geometry not drawn, one segment over the antimeridian")
    check("empty" in codes(GD.check_geojson({"type": "FeatureCollection", "features": []}), "warning"), "an empty collection: warning")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "bad.json").write_text("{not json", encoding="utf-8")
        for path, what in ((td / "bad.json", "invalid JSON"), (td / "missing.geojson", "a missing file")):
            try:
                GD.read_geojson(path)
                msg = "read"
            except GD.GeoDataError as e:
                msg = str(e)
            check(msg != "read", f"read_geojson: {what} -> GeoDataError ({msg[:50]})")
        write(td, "ok.geojson", LAND)
        old = GD.MAX_BYTES
        GD.MAX_BYTES = 100
        try:
            GD.read_geojson(td / "ok.geojson")
            msg = "read"
        except GD.GeoDataError as e:
            msg = str(e)
        finally:
            GD.MAX_BYTES = old
        check("more than" in msg, "a file larger than MAX_BYTES is refused before it is parsed")
        check(GD.read_geojson(td / "ok.geojson") == GD.read_geojson(td / "ok.geojson") == GD.check_geojson(LAND), "deterministic, file = parsed")

    print("\n== scene.json: defaults and every plan element")
    before = (json.dumps(plan, sort_keys=True), json.dumps(geo, sort_keys=True))
    sp = M.resolve(dict(base_scene), plan, geo)
    check(sp["schema"] == "nfp.mapmotion.sceneplan/1" and only_label_estimate(sp) and sp["style"]["preset"] == "documentary-light",
          "a minimal scene resolves (OK), default preset documentary-light")
    check([p["id"] for p in sp["points"]] == [p["id"] for p in plan["points"]] and [r["id"] for r in sp["routes"]] == [r["id"] for r in plan["routes"]]
          and [a["id"] for a in sp["areas"]] == [a["id"] for a in plan["areas"]], "every point, route and area of the plan, in plan order")
    p0, g0 = sp["points"][0], geo["points"][0]
    check(p0["x"] == g0["x"] and p0["y"] == g0["y"] and p0["marker"] == "pin" and p0["color"] == M.PRESETS["documentary-light"]["colors"]["point"]
          and p0["label"]["text"] == plan["points"][0]["label"]["text"] and p0["label"]["show"], "a point: M2a marker positions, preset style, M1 label")
    r0 = sp["routes"][0]
    check([[(v["x"], v["y"]) for v in pc] for pc in r0["pieces"]] == [[(v["x"], v["y"]) for v in pc] for pc in geo["routes"][0]["pieces"]]
          and r0["stop_frames"] == plan["routes"][0]["stop_frames"] and r0["width"] == 4.0, "a route: M2a pieces, M1 timing, preset width")
    check(sp["areas"][0]["shape"] == plan["areas"][0]["shape"], "an area: the M1 shape")
    uc = [p for p in sp["points"] if p["uncertainty"]]
    check(uc and uc[0]["uncertainty"]["rx"] == [p for p in plan["points"] if p["uncertainty"]][0]["uncertainty"]["rx"], "uncertainty ellipse from M1")
    check((json.dumps(plan, sort_keys=True), json.dumps(geo, sort_keys=True)) == before, "the plan and the geometry are not changed")
    check(sp["basemap"] == [] and sp["graticule"]["show"] is False, "no basemap, no graticule by default")

    print("\n== scene.json: style, visibility and per-element settings")
    pid, rid, aid = plan["points"][0]["id"], plan["routes"][0]["id"], plan["areas"][0]["id"]
    sc = dict(base_scene, style={"preset": "documentary-dark", "colors": {"route": "#ABCDEF80"}, "widths": {"route": 6}, "opacity": {"area": 0.5}},
              graticule={"show": True, "step_deg": 5}, show={"labels": False},
              points={pid: {"marker": "plane", "size": 20, "color": "#112233", "label": True},
                      plan["points"][1]["id"]: {"marker": "none"}},
              routes={rid: {"dash": [8, 4], "width": 2.5}}, areas={aid: {"show": False}})
    sp = M.resolve(sc, plan, geo)
    p0, p1 = sp["points"][0], sp["points"][1]
    check(only_label_estimate(sp) and sp["style"]["colors"]["route"] == "#abcdef80" and sp["style"]["widths"]["route"] == 6.0
          and sp["style"]["colors"]["background"] == M.PRESETS["documentary-dark"]["colors"]["background"],
          "preset documentary-dark with colour / width overrides (colours lower-case)")
    check(p0["marker"] == "plane" and p0["size"] == 20.0 and p0["color"] == "#112233" and p0["label"]["show"] and not p1["show"]
          and not any(p["label"]["show"] for p in sp["points"][1:]), "point overrides; marker none hides it; show.labels off except where asked")
    check(sp["routes"][0]["dash"] == [8.0, 4.0] and sp["routes"][0]["width"] == 2.5 and sp["routes"][0]["color"] == "#abcdef80",
          "route: own dash and width, colour from the style override")
    check(not sp["areas"][0]["show"] and sp["areas"][0]["opacity"] == 0.5 and sp["graticule"] == {"show": True, "step_deg": 5,
          "color": sp["style"]["colors"]["graticule"], "width": sp["style"]["widths"]["graticule"]}, "area hidden; area opacity; graticule")
    sp = M.resolve(dict(base_scene, show={"points": False, "routes": False, "uncertainty": False}), plan, geo)
    check(not any(p["show"] for p in sp["points"]) and not any(r["show"] for r in sp["routes"])
          and all(p["uncertainty"]["show"] is False for p in sp["points"] if p["uncertainty"]), "show: points / routes / uncertainty off")

    print("\n== scene.json: errors")
    for sc, code, what in (
            (dict(base_scene, schema="nfp.mapmotion.scene/2"), "schema", "wrong schema"),
            (dict(base_scene, extra=1), "schema", "an unknown key"),
            (dict(base_scene, camera={}), "camera", "a camera without keyframes (the camera is M2c)"), (dict(base_scene, animation=[]), "animation", "an animation that is not an object (the animation is M2d)"),
            (dict(base_scene, labels=[]), "labels", "labels that are not an object (labels are M2f)"), (dict(base_scene, timeline={}), "later_stage", "timeline (M2g)"),
            (dict(base_scene, id="bad id"), "bad_id", "a bad id"), (dict(base_scene, map="other-map"), "map", "the scene of another map"),
            (dict(base_scene, mode="publish"), "schema", "a bad mode"),
            (dict(base_scene, style={"preset": "neon"}), "style", "an unknown preset"),
            (dict(base_scene, style={"colors": {"route": "red"}}), "style", "a colour name"),
            (dict(base_scene, style={"colors": {"sea": "#000000"}}), "style", "an unknown colour key"),
            (dict(base_scene, style={"widths": {"route": 0}}), "style", "width 0"), (dict(base_scene, style={"widths": {"route": 65}}), "style", "width 65"),
            (dict(base_scene, style={"opacity": {"area": 1.5}}), "style", "opacity 1.5"),
            (dict(base_scene, graticule={"step_deg": 7}), "schema", "graticule step 7"),
            (dict(base_scene, show={"labels": "yes"}), "schema", "show.labels 'yes'"),
            (dict(base_scene, points={"nope": {}}), "unknown_element", "a point the plan does not have"),
            (dict(base_scene, points={pid: {"marker": "star"}}), "marker", "an unknown marker"),
            (dict(base_scene, points={pid: {"size": 1}}), "style", "marker size 1"),
            (dict(base_scene, points={pid: {"glow": True}}), "schema", "an unknown point setting"),
            (dict(base_scene, routes={rid: {"dash": [0, 4]}}), "style", "a dash of 0"),
            (dict(base_scene, routes={rid: {"width": True}}), "style", "a bool width"),
            (dict(base_scene, areas={aid: {"opacity": -0.1}}), "style", "a negative opacity")):
        sp = M.resolve(sc, plan, geo)
        check(sp["qc"]["status"] == "FAIL" and code in qcodes(sp, "error"), f"refused: {what}")
    sp = M.resolve(dict(base_scene, timeline={}), plan, geo)
    check("M2g" in [i["message"] for i in sp["qc"]["issues"] if i["code"] == "later_stage"][0], "a later-stage key names the stage")

    print("\n== the inputs of this stage")
    bad_plan = M.build(mapdoc(id="bad id"), LDOC, today=TODAY)
    for args, what in (((base_scene, bad_plan, geo), "a FAIL plan"), ((base_scene, plan, {"schema": "x"}), "not a geometry"),
                       ((base_scene, {"schema": "x"}, geo), "not a plan")):
        try:
            M.resolve(*args)
            msg = "accepted"
        except ValueError as e:
            msg = str(e)
        check(msg != "accepted", f"refused: {what} ({msg[:60]})")
    other = copy.deepcopy(geo)
    other["routes"] = other["routes"][:-1]
    jump = copy.deepcopy(geo)
    jump["issues"] = [{"level": "error", "code": "route_jump", "element": rid, "message": "x"}]
    for gg, what in ((other, "the geometry of another plan"), (jump, "a geometry with a route_jump error")):
        try:
            M.resolve(base_scene, plan, gg)
            msg = "accepted"
        except ValueError as e:
            msg = str(e)
        check(msg != "accepted", f"refused: {what}")
    capped = M.geometry(plan, max_depth=0)
    sp = M.resolve(base_scene, plan, capped)
    check("sampling_capped" in qcodes(sp, "warning") and sp["qc"]["status"] == "WARN", "geometry warnings are passed on (sampling_capped)")

    print("\n== basemap from local GeoJSON (assets.json, nfp.assets/1)")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "geo").mkdir()
        s_land = write(td / "geo", "land.geojson", LAND)
        s_coast = write(td / "geo", "coast.geojson", COAST)
        s_am = write(td / "geo", "am.geojson", {"type": "LineString", "coordinates": [[179.0, 0.0], [-179.0, 1.0]]})
        s_bad = write(td / "geo", "bad.geojson", {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]})
        assets = {"schema": "nfp.assets/1", "assets": [
            asset("land", "geo/land.geojson", s_land), asset("coast", "geo/coast.geojson", s_coast), asset("am", "geo/am.geojson", s_am),
            asset("draft-land", "geo/land.geojson", s_land, verified=False), asset("bad", "geo/bad.geojson", s_bad),
            asset("wrong-sha", "geo/land.geojson", "0" * 64), asset("photo", "geo/land.geojson", s_land, kind="image")]}
        layers = [{"id": "l-land", "asset": "land", "role": "land"}, {"id": "l-coast", "asset": "coast", "role": "coastline"}]
        sp = M.resolve(dict(base_scene, basemap=layers), plan, geo, assets, td)
        bl = sp["basemap"]
        check(only_label_estimate(sp) and [l["id"] for l in bl] == ["l-land", "l-coast"] and bl[0]["status"] == "verified"
              and bl[0]["features"] == GD.check_geojson(LAND)["features"] and bl[0]["fill"] == sp["style"]["colors"]["land"]
              and bl[0]["stroke"] is None and bl[1]["stroke"] == sp["style"]["colors"]["coastline"] and bl[1]["fill"] is None
              and bl[0]["attribution"] == "Synthetic test data", "land (filled) + coastline (stroked) from verified local files, layer order kept")
        for lay, extra, code, level, what in (
                ([{"id": "x", "asset": "coast", "role": "land"}], {}, "basemap", "error", "a land layer from lines"),
                ([{"id": "x", "asset": "draft-land", "role": "land"}], {}, "unverified_asset", "warning", "a draft asset in draft mode"),
                ([{"id": "x", "asset": "draft-land", "role": "land"}], {"mode": "final"}, "unverified_asset", "error", "a draft asset in final mode"),
                ([{"id": "x", "asset": "wrong-sha", "role": "land"}], {}, "asset", "error", "a sha256 mismatch"),
                ([{"id": "x", "asset": "photo", "role": "land"}], {}, "asset", "error", "an image asset as basemap"),
                ([{"id": "x", "asset": "nope", "role": "land"}], {}, "asset", "error", "an asset not in assets.json"),
                ([{"id": "x", "asset": "bad", "role": "land"}], {}, "geojson", "error", "a broken GeoJSON file"),
                ([{"id": "x", "asset": "am", "role": "borders"}], {}, "antimeridian_segment", "warning", "a line over the antimeridian"),
                ([{"id": "x", "asset": "land", "role": "sea"}], {}, "basemap", "error", "an unknown role"),
                ([{"id": "x", "asset": "land", "role": "land"}, {"id": "x", "asset": "coast", "role": "coastline"}], {}, "bad_id", "error",
                 "a repeated layer id"),
                ([{"id": "x", "asset": "land"}], {}, "schema", "error", "a layer without role")):
            sp = M.resolve(dict(base_scene, basemap=lay, **extra), plan, geo, assets, td)
            check(code in qcodes(sp, level), f"{what}: {level} {code}")
        sp = M.resolve(dict(base_scene, basemap=layers), plan, geo)
        check("basemap" in qcodes(sp, "error"), "basemap layers without assets.json: error")
        a1 = json.dumps(M.resolve(dict(base_scene, basemap=layers), plan, geo, assets, td), sort_keys=True)
        a2 = json.dumps(M.resolve(dict(base_scene, basemap=layers), plan, geo, assets, td), sort_keys=True)
        check(a1 == a2, "deterministic: the same scene plan twice")

    print("\n== boundaries")
    for f in ("scene.py", "geodata.py"):
        t = (NFP / "mapmotion" / f).read_text(encoding="utf-8")
        mods = {a or b for a, b in re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", t, re.M)}
        check(mods <= {"json", "math", "re", "pathlib", "timeline", ".", ".geometry", ".model"},
              f"{f} imports only the standard library, Timeline's public API and mapmotion {sorted(mods)}")
        check(not re.search(r"urllib|socket|subprocess|write_text|write_bytes|open\(|date\.today|import random|random\.", t),
              f"{f}: no network, process, file writing, clock or randomness")
    m1 = M.build(mapdoc(), LDOC, today=TODAY)
    check(m1["schema"] == "nfp.mapmotion.plan/1" and set(m1) == {"schema", "map", "mode", "fps", "frame", "projection", "viewport", "window",
                                                             "points", "routes", "areas", "qc"}, "the M1 plan keeps its schema and fields")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    check(all(k in rd for k in ("M2b", "nfp.mapmotion.scene/1", "nfp.mapmotion.sceneplan/1", "GeoJSON", "later_stage")), "README documents M2b")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2b TESTS PASSED" if not f else "MAP MOTION M2b TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
