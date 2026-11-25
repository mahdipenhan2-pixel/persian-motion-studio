"""NFP Map Motion - M1: great-circle routes (the shortest path on the sphere) sampled for drawing. Standard library.

Between two WGS84 points the route follows the great circle (spherical linear interpolation of the two unit vectors;
mean Earth radius 6 371 008.8 m, the same sphere as Location's distance_m). `samples` points per leg, both ends
included (>= 2). Refused: a leg between two antipodal points (every great circle joins them: no single route) and
invalid coordinates. A leg between identical points has length 0 (all samples equal).

The date line: sampled longitudes are returned two ways - "lon" in -180..180 and "lon_unwrapped", a continuous series
(each step chosen within +-180 of the previous one) so that a route from 179E to 179W runs 179 -> 181, never jumping
358 degrees back across the map. Projection uses the unwrapped series, so the drawn path stays continuous.
"""
import math

R_EARTH_M = 6371008.8
ANTIPODE_EPS = 1e-9


class RouteError(ValueError):
    pass


def _vec(lat, lon):
    p, l = math.radians(lat), math.radians(lon)
    return (math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p))


def _latlon(v):
    x, y, z = v
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def _ok(lat, lon):
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon)) \
        and -90 <= lat <= 90 and -180 <= lon <= 180


def central_angle(a, b):
    """Angle (radians) between two (lat, lon) points, numerically stable (atan2 of cross / dot)."""
    va, vb = _vec(*a), _vec(*b)
    cx = va[1] * vb[2] - va[2] * vb[1]
    cy = va[2] * vb[0] - va[0] * vb[2]
    cz = va[0] * vb[1] - va[1] * vb[0]
    return math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), sum(x * y for x, y in zip(va, vb)))


def leg(a, b, samples=32):
    """Sampled great circle from a to b: {"distance_m", "angle_deg", "points": [(lat, lon), ...]} (both ends included)."""
    if not (_ok(*a) and _ok(*b)):
        raise RouteError(f"invalid coordinate in leg {a!r} -> {b!r}")
    if not (isinstance(samples, int) and not isinstance(samples, bool) and 2 <= samples <= 1000):
        raise RouteError("samples must be a whole number 2..1000")
    om = central_angle(a, b)
    if math.pi - om < ANTIPODE_EPS:
        raise RouteError(f"{a!r} and {b!r} are antipodal: no single great-circle route")
    va, vb = _vec(*a), _vec(*b)
    pts = []
    for i in range(samples):
        t = i / (samples - 1)
        if i == 0:
            pts.append((float(a[0]), float(a[1])))
            continue
        if i == samples - 1:
            pts.append((float(b[0]), float(b[1])))
            continue
        if om < 1e-12:
            pts.append((float(a[0]), float(a[1])))
            continue
        s = math.sin(om)
        f1, f2 = math.sin((1 - t) * om) / s, math.sin(t * om) / s
        v = tuple(f1 * x + f2 * y for x, y in zip(va, vb))
        lat, lon = _latlon(v)
        if abs(lat) > 90 - 1e-12:                    # exactly over a pole the longitude is undefined: keep the last one
            lon = pts[-1][1]
        pts.append((lat, lon))
    return {"distance_m": R_EARTH_M * om, "angle_deg": math.degrees(om), "points": pts}


def unwrap(lons, start=None):
    """Continuous longitudes: each value moved by a multiple of 360 to lie within 180 of the previous one."""
    out = []
    for lon in lons:
        if not out:
            out.append(lon if start is None else start)
            continue
        prev = out[-1]
        d = (lon - prev + 180) % 360 - 180
        if d == -180 and lon - prev > 0:
            d = 180
        out.append(prev + d)
    return out
