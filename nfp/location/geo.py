"""NFP Location Engine - L1c: geographic extent (bounding box), containment and distances on WGS84. Standard library.

extent = {"north": lat, "south": lat, "east": lon, "west": lon}     decimal degrees, numbers
  south <= north (a reversed pair is an error: latitude has no wrap-around)
  west <= east     an ordinary box
  west >  east     the box CROSSES the 180th meridian (the date line): it runs east from `west` past 180 to `east`
                   (e.g. west 170, east -170 is a 20-degree box over the date line). A box that would then span more than
                   180 degrees of longitude gets a warning: the two values may simply be swapped.
  west -180, east 180  the whole circle of longitude
Longitudes -180 and 180 are the same meridian and are treated as equal when testing containment.

Distances: haversine on a sphere of the mean Earth radius R = 6 371 008.8 m (good to ~0.5 % - enough to find near
duplicates; not a survey-grade geodesic).
"""
import math

R_EARTH_M = 6371008.8
EPS = 1e-9


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_extent(e):
    """Problems of an extent: [(level, code, message)]. Empty = a valid box."""
    keys = {"north", "south", "east", "west"}
    if not isinstance(e, dict) or set(e) != keys:
        return [("error", "bad_extent", "extent must be an object with exactly north, south, east, west")]
    out = []
    for k in ("north", "south", "east", "west"):
        v = e[k]
        if not _num(v):
            out.append(("error", "bad_extent", f"extent.{k} {v!r} is not a number"))
        elif not math.isfinite(v):
            out.append(("error", "bad_extent", f"extent.{k} is {v!r} (NaN / infinity)"))
    if out:
        return out
    for k in ("north", "south"):
        if not -90 <= e[k] <= 90:
            out.append(("error", "extent_range", f"extent.{k} {e[k]!r} is outside -90..90"))
    for k in ("east", "west"):
        if not -180 <= e[k] <= 180:
            out.append(("error", "extent_range", f"extent.{k} {e[k]!r} is outside -180..180"))
    if out:
        return out
    if e["south"] > e["north"]:
        out.append(("error", "extent_reversed", f"extent.south {e['south']!r} is north of extent.north {e['north']!r}"))
        return out
    w = width(e)
    if e["west"] > e["east"] and w > 180:
        out.append(("warning", "extent_maybe_swapped", f"west {e['west']!r} > east {e['east']!r} is read as a box over the "
                                                         f"date line {w:g} degrees wide: are east and west swapped?"))
    if w == 0 or e["north"] == e["south"]:
        out.append(("warning", "extent_degenerate", "the extent has no width or no height (a line or a point)"))
    return out


def width(e):
    """Longitude span of a valid extent in degrees (0..360); over the date line when west > east."""
    if e["west"] == -180 and e["east"] == 180:
        return 360.0
    return (e["east"] - e["west"]) % 360


def _lon_in(lon, west, span):
    if span >= 360 - EPS:
        return True
    for x in {lon, lon + 360 if lon == -180 else lon, lon - 360 if lon == 180 else lon}:
        if (x - west) % 360 <= span + EPS:
            return True
    return False


def contains_point(e, lat, lon):
    """Is the point inside the (valid) extent? Edges included; the date line handled."""
    return e["south"] - EPS <= lat <= e["north"] + EPS and _lon_in(lon, e["west"], width(e))


def contains_extent(outer, inner):
    """Is the (valid) inner extent entirely inside the (valid) outer extent?"""
    if not (outer["south"] - EPS <= inner["south"] and inner["north"] <= outer["north"] + EPS):
        return False
    wo, wi = width(outer), width(inner)
    if wo >= 360 - EPS:
        return True
    if wi > wo + EPS:
        return False
    d = (inner["west"] - outer["west"]) % 360
    if d > 360 - EPS:
        d = 0.0
    return d + wi <= wo + EPS


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres (haversine, mean Earth radius)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH_M * math.asin(min(1.0, math.sqrt(a)))
