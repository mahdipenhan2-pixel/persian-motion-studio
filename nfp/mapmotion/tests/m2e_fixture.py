"""Shared SYNTHETIC fixture for the M2e tests: a whole-world map with a basemap (a land polygon over the antimeridian,
deliberately NOT split; a polar ring; a coastline), a regional route and a route over the seam, a camera and an
animation. The GeoJSON and assets.json files go to a folder the caller gives (a temporary folder)."""
import datetime
import hashlib
import json
from pathlib import Path

import mapmotion as M
from test_location_l1c import loc
from test_location_l1a import doc as ldoc

TODAY = datetime.date(2026, 11, 25)
LAND = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {"name": "West"}, "geometry": {"type": "Polygon", "coordinates": [[[-120, 50], [-60, 55], [-40, 20], [-70, -10], [-110, 10], [-120, 50]]]}},
    {"type": "Feature", "properties": {"name": "East"}, "geometry": {"type": "Polygon", "coordinates": [[[0, 60], [60, 65], [110, 45], [90, 5], [30, -5], [5, 20], [0, 60]]]}},
    {"type": "Feature", "properties": {"name": "Dateline (not split)"}, "geometry": {"type": "Polygon", "coordinates": [[[165, -10], [-165, -10], [-165, -30], [165, -30], [165, -10]]]}},
    {"type": "Feature", "properties": {"name": "Polar"}, "geometry": {"type": "Polygon", "coordinates": [[[-180, -65], [-90, -70], [0, -66], [90, -72], [180, -65], [180, -90], [-180, -90], [-180, -65]]]}}]}
COAST = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "MultiLineString", "coordinates": [
    [[-120, 50], [-60, 55], [-40, 20], [-70, -10], [-110, 10], [-120, 50]], [[165, -10], [-165, -10], [-165, -30], [165, -30], [165, -10]]]}}]}


def build(folder):
    folder = Path(folder)
    (folder / "geo").mkdir(exist_ok=True)
    rows = []
    for name, d in (("land", LAND), ("coast", COAST)):
        p = folder / "geo" / f"{name}.geojson"
        p.write_text(json.dumps(d), encoding="utf-8")
        rows.append({"id": name, "kind": "map", "local_path": f"geo/{name}.geojson", "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                     "width": None, "height": None, "duration": None, "source_url": None, "author": "NFP test (synthetic)",
                     "license": "original", "license_url": None, "retrieved_at": "2026-11-25", "modifications": "none",
                     "license_verified": True, "attribution": "Synthetic basemap (test)", "restrictions": [], "real_person": False})
    assets = {"schema": "nfp.assets/1", "assets": rows}
    locs = ldoc(loc("a", 40.5, 10.5), loc("b", 55.5, 50.5), loc("c", 20.5, 95.5), loc("w", -20.5, 160.5), loc("e", -22.5, -150.5),
                loc("u", 10.5, -60.5), loc("q", -45.5, -100.5))
    md = {"schema": "nfp.mapmotion/1", "id": "m2e-map", "mode": "draft", "window": {"start": 0, "end": 240},
          "labels": {"lang": "en", "year": None}, "viewport": {"bounds": {"north": 80, "south": -80, "west": -180, "east": 180}},
          "points": [{"id": i, "location": i, "start": 0, "end": 240, "label": False} for i in ("a", "b", "c", "w", "e", "u")]
                    + [{"id": "q", "location": "q", "start": 100, "end": 140, "label": False}],
          "routes": [{"id": "r-east", "stops": ["a", "b", "c"], "start": 20, "end": 120, "samples": 16},
                     {"id": "r-seam", "stops": ["w", "e"], "start": 110, "end": 200, "samples": 16}], "areas": []}
    plan = M.build(md, locs, today=TODAY)
    geo = M.geometry(plan)
    scene = {"schema": "nfp.mapmotion.scene/1", "id": "m2e-scene", "map": "m2e-map", "graticule": {"show": True, "step_deg": 30},
             "basemap": [{"id": "land", "asset": "land", "role": "land"}, {"id": "coast", "asset": "coast", "role": "coastline"}],
             "points": {"u": {"marker": "ring"}, "w": {"marker": "dot"}, "e": {"marker": "dot"}},
             "camera": {"keyframes": [{"frame": 0, "view": {"full": True}}, {"frame": 60, "view": {"points": ["a", "b", "c"], "pad_px": 120}},
                                      {"frame": 120, "view": {"points": ["a", "b", "c"], "pad_px": 120}}, {"frame": 170, "view": {"full": True}}]},
             "animation": {"routes": {"r-east": {"marker": "plane", "ease": "in-out"}, "r-seam": {"marker": "ship"}}}}
    sp = M.resolve(scene, plan, geo, assets, folder)
    return plan, geo, sp
