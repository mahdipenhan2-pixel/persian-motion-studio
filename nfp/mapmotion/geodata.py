"""NFP Map Motion - M2b: reading a LOCAL GeoJSON file (RFC 7946) for the basemap. Standard library; nothing is fetched.

  read_geojson(path) -> {"features": [{"type", "coordinates", "name"}], "features_count", "positions", "bbox",
                         "antimeridian_segments", "issues": [{level, code, message}]}
  check_geojson(doc)  -> the same, for an already parsed document

Accepted: a FeatureCollection, a Feature or a bare geometry; geometry types Polygon, MultiPolygon, LineString and
MultiLineString (what a basemap draws). Positions are [longitude, latitude] (RFC 7946 order; a third value, the
altitude, is ignored), finite numbers (not bool) within -180..180 / -90..90. A LineString needs >= 2 positions; a
polygon ring >= 4 and closed (first = last). Not drawn, with a warning: Point / MultiPoint / GeometryCollection, and
features without geometry. A "crs" member is not part of RFC 7946: warning, coordinates are taken as WGS84.
Nothing is projected, cut or simplified here (that is drawing work, a later stage); only checked and reported:
  - "antimeridian_segment" (warning): a segment whose ends are more than 180 degrees of longitude apart. RFC 7946 asks
    for such geometries to be split at the antimeridian; this one is not, and must be cut before drawing.
Limits: MAX_BYTES (64 MB) for the file, MAX_POSITIONS (2,000,000) in all - larger is an error, not a slow surprise.
The output keeps the file's feature order and coordinates as given (deterministic).
"""
import json
import math
from pathlib import Path

DRAWN = ("Polygon", "MultiPolygon", "LineString", "MultiLineString")
SKIPPED = ("Point", "MultiPoint", "GeometryCollection")
MAX_BYTES = 64 * 1024 * 1024
MAX_POSITIONS = 2_000_000


class GeoDataError(ValueError):
    pass


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_geojson(doc):
    issues = []
    out = {"features": [], "features_count": 0, "positions": 0, "bbox": None, "antimeridian_segments": 0, "issues": issues}

    def add(level, code, msg):
        issues.append({"level": level, "code": code, "message": msg})

    if not isinstance(doc, dict) or not isinstance(doc.get("type"), str):
        add("error", "geojson", "not a GeoJSON object (no type)")
        return out
    if "crs" in doc:
        add("warning", "crs", "a 'crs' member is not part of RFC 7946: coordinates are taken as WGS84 longitude / latitude")
    t = doc["type"]
    if t == "FeatureCollection":
        feats = doc.get("features")
        if not isinstance(feats, list):
            add("error", "geojson", "a FeatureCollection needs a features list")
            return out
    elif t == "Feature":
        feats = [doc]
    elif t in DRAWN + SKIPPED:
        feats = [{"type": "Feature", "geometry": doc, "properties": None}]
    else:
        add("error", "geojson", f"unknown GeoJSON type {t!r}")
        return out
    box = [math.inf, -math.inf, math.inf, -math.inf]          # min lat, max lat, min lon, max lon
    skipped = {}
    for n, f in enumerate(feats):
        where = f"feature {n}"
        if not isinstance(f, dict) or f.get("type") != "Feature":
            add("error", "geojson", f"{where} is not a Feature")
            continue
        g = f.get("geometry")
        props = f.get("properties") if isinstance(f.get("properties"), dict) else {}
        name = props.get("name") if isinstance(props.get("name"), str) else None
        if g is None:
            skipped["no geometry"] = skipped.get("no geometry", 0) + 1
            continue
        if not isinstance(g, dict) or not isinstance(g.get("type"), str):
            add("error", "geojson", f"{where}: geometry has no type")
            continue
        gt = g["type"]
        if gt in SKIPPED:
            skipped[gt] = skipped.get(gt, 0) + 1
            continue
        if gt not in DRAWN:
            add("error", "geojson", f"{where}: unknown geometry type {gt!r}")
            continue
        c = g.get("coordinates")
        parts = {"LineString": [[c]], "MultiLineString": [[x] for x in c] if isinstance(c, list) else None,
                 "Polygon": [c], "MultiPolygon": c}[gt]
        if not isinstance(c, list) or not isinstance(parts, list):
            add("error", "geojson", f"{where}: {gt} coordinates must be nested lists")
            continue
        ok, clean = True, []
        for part in parts:
            if not isinstance(part, list) or not part:
                ok = False
                break
            rings = []
            for ring in part:
                if not isinstance(ring, list):
                    ok = False
                    break
                pts = []
                for p in ring:
                    if not (isinstance(p, list) and len(p) in (2, 3) and all(_num(v) for v in p)):
                        ok = False
                        break
                    lon, lat = float(p[0]), float(p[1])
                    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                        add("error", "coordinate", f"{where}: position [{p[0]!r}, {p[1]!r}] is outside -180..180 / -90..90 "
                                                   "(GeoJSON order is [longitude, latitude])")
                        ok = False
                        break
                    pts.append([lon, lat])
                if not ok:
                    break
                line = gt in ("LineString", "MultiLineString")
                if line and len(pts) < 2:
                    add("error", "geojson", f"{where}: a line needs at least 2 positions")
                    ok = False
                    break
                if not line and (len(pts) < 4 or pts[0] != pts[-1]):
                    add("error", "geojson", f"{where}: a polygon ring needs at least 4 positions and must be closed "
                                            "(first = last)")
                    ok = False
                    break
                for a, b in zip(pts, pts[1:]):
                    if abs(b[0] - a[0]) > 180:
                        out["antimeridian_segments"] += 1
                for lon, lat in pts:
                    box = [min(box[0], lat), max(box[1], lat), min(box[2], lon), max(box[3], lon)]
                out["positions"] += len(pts)
                rings.append(pts)
            if not ok:
                break
            clean.append(rings)
        if not ok:
            if not any(i["level"] == "error" and i["message"].startswith(where) for i in issues):
                add("error", "geojson", f"{where}: {gt} coordinates must be [longitude, latitude] number pairs")
            continue
        if out["positions"] > MAX_POSITIONS:
            add("error", "too_large", f"more than {MAX_POSITIONS} positions: simplify the file before using it")
            return out
        coords = {"LineString": clean[0][0], "MultiLineString": [r[0] for r in clean], "Polygon": clean[0], "MultiPolygon": clean}[gt]
        out["features"].append({"type": gt, "coordinates": coords, "name": name})
    for k, v in sorted(skipped.items()):
        add("warning", "not_drawn", f"{v} feature(s) of type {k} are not drawn (a basemap draws lines and polygons)")
    if out["antimeridian_segments"]:
        add("warning", "antimeridian_segment", f"{out['antimeridian_segments']} segment(s) jump more than 180 degrees of "
                                               "longitude: the geometry crosses the antimeridian without being split "
                                               "(RFC 7946); it must be cut before drawing")
    out["features_count"] = len(out["features"])
    if out["features"]:
        out["bbox"] = {"south": box[0], "north": box[1], "west": box[2], "east": box[3]}
    elif not any(i["level"] == "error" for i in issues):
        add("warning", "empty", "no drawable feature")
    return out


def read_geojson(path):
    """Read and check a local GeoJSON file. Raises GeoDataError for a file that cannot be read or parsed."""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as e:
        raise GeoDataError(f"{p.name}: cannot be read ({e.strerror})") from None
    if size > MAX_BYTES:
        raise GeoDataError(f"{p.name}: {size} bytes is more than {MAX_BYTES}: simplify the file before using it")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise GeoDataError(f"{p.name}: not valid UTF-8 JSON ({e})") from None
    return check_geojson(doc)
