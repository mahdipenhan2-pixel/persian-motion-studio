"""NFP Map Motion - M2a: the seam of the map and routes split on it. Standard library.

The seam: every longitude is drawn on the side nearer the box (projection.east_of). The meridian where "nearer"
changes sides - straight behind the box - is the seam:
    seam_u   = width + (360 - width) / 2     (degrees east of `west`; for the whole world -180..180: 360, the map edge)
    seam_lon = west + seam_u, as a longitude (the whole world: +-180; a box 170E..170W: 0)
A continuous (unwrapped) route crosses the seam wherever its u passes seam_u + 360 j. There it is cut into pieces;
each piece is moved by a whole multiple of 360 degrees so that it lies on the drawn side, between seam_u - 360 and
seam_u, and every piece ends exactly on the seam (one copy of the crossing point on each side). A route that never
crosses the seam - every regional route over the date line - stays one piece, with exactly the coordinates of the plan.

The crossing point is exact: the intersection of the leg's great-circle plane (normal a x b) with the plane of the
seam meridian, the one of the two opposite candidates that lies between the two route points (no averaging of
coordinates). If the leg lies in the seam meridian's own plane the intersection is undefined; then a bisection on the
great circle finds it (deterministic, 80 steps).

ONE rule decides whether a PLACE (a marker, a route stop) is on the seam - on_seam_lon(): its longitude rounded to
7 decimals (the plan's own precision for route coordinates) equals the seam longitude rounded the same way. So
179.99999996 (the plan writes 180.0) is on the seam on the whole-world map, while 179.9999999 (a different 7-decimal
value) is not. Markers (marker_us / marker_xs), the stops of split() and M1's route_wraps check all use it; a stop on
the seam is snapped to the seam itself (a shift of at most 5e-8 degrees). Points computed along a route (samples,
crossings) are not places: for them the exact test on_seam(u) (within 1e-9 degrees) is used.
Points exactly on the seam (on the whole-world map: longitude 180 or -180, which are the same meridian):
  - a marker on the seam has TWO positions, one on each edge (seam_u - 360 and seam_u); M1's plan keeps its single x
    (projection.east_of: the west edge on the whole-world map) - marker_us() / marker_xs() give both;
  - a route piece that ends or starts on the seam is drawn on the edge it arrives from or leaves to, so its end always
    matches one of the marker's two positions;
  - a piece that lies entirely on the seam (a route along the 180th meridian) is drawn where M1 draws the point
    (projection.east_of).
"""
import math

from .projection import east_of
from .route import _latlon, _vec, central_angle

EPS_DEG = 1e-9                  # exact test for computed route points (on_seam)
ROUND_DIGITS = 7                # places: the plan's precision for route coordinates (on_seam_lon)


def seam_u(proj):
    return proj.lon_span + (360.0 - proj.lon_span) / 2


def seam_lon(proj):
    v = proj.bounds["west"] + seam_u(proj)
    return (v + 180.0) % 360.0 - 180.0


def on_seam(u, proj):
    """True when the unwrapped u lies on the seam (within 1e-9 degrees)."""
    return abs((u - seam_u(proj) + 180.0) % 360.0 - 180.0) <= EPS_DEG


def on_seam_lon(lon, proj):
    """True when a PLACE at longitude `lon` is on the seam: lon and the seam longitude, both rounded to 7 decimals,
    are the same meridian (180 and -180 are one)."""
    d = round(lon, ROUND_DIGITS) - round(seam_lon(proj), ROUND_DIGITS)
    return abs((d + 180.0) % 360.0 - 180.0) < 1e-9


def marker_us(proj, lat, lon):
    """The u positions of a marker at (lat, lon): one, or two (both edges) when the place is on the seam."""
    u = east_of(lon, proj.bounds["west"], proj.lon_span)
    if on_seam_lon(lon, proj):
        s = seam_u(proj)
        return [s - 360.0, s]
    return [u]


def marker_xs(proj, lat, lon):
    return [proj.x_of_u(u) for u in marker_us(proj, lat, lon)]


def u_between(c, a, b):
    """c moved by a whole turn (-360, 0 or +360) so that it lies between a and b (or as near as possible).
    Along a great-circle segment the unwrapped longitude runs monotonically from a to b - across a pole it jumps by
    exactly 180 degrees, still in that direction - so a point of the segment lies between its two ends. This makes a
    step of +-180 (a pole, where rounding decides the sign) independent of which neighbour it is computed from."""
    lo, hi = (a, b) if a <= b else (b, a)
    best = None
    for k in (0, -1, 1):
        v = c + 360.0 * k
        d = 0.0 if lo - 1e-9 <= v <= hi + 1e-9 else min(abs(v - lo), abs(v - hi))
        if best is None or d < best[0]:
            best = (d, v)
    return best[1]


def _sheet(u, proj):
    """Which 360-degree copy a point not on the seam is in (0 = the drawn one: seam_u - 360 < u < seam_u)."""
    return math.floor((u - seam_u(proj)) / 360.0) + 1


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def crossing(leg_a, leg_b, p, q, lon):
    """Latitude where the great circle leg_a -> leg_b, between its points p and q, meets the meridian `lon`.
    Exact intersection of the two planes; returns None if the leg lies in that meridian's plane."""
    n = _cross(_vec(*leg_a), _vec(*leg_b))
    lam = math.radians(lon)
    m = (-math.sin(lam), math.cos(lam), 0.0)
    d = _cross(n, m)
    L = _norm(d)
    if _norm(n) < 1e-15 or L < 1e-12:
        return None
    best = None
    pq = central_angle(p, q)
    for sgn in (1.0, -1.0):
        c = tuple(sgn * x / L for x in d)
        lat_c = _latlon(c)[0]
        off = central_angle(p, (lat_c, _latlon(c)[1])) + central_angle((lat_c, _latlon(c)[1]), q) - pq
        if best is None or off < best[0]:
            best = (off, lat_c)
    return best[1] if best[0] < 1e-7 else None


def _bisect(lg_at, tp, tq, p, s, proj, du, uq):
    """Fraction t in [tp, tq] where the unwrapped u reaches s (the leg's own slerp; deterministic bisection)."""
    lo, hi = tp, tq
    side = p[4] < s
    for _ in range(80):
        mid = (lo + hi) / 2
        lat, lon = lg_at(mid, p[3])
        u = u_between(p[4] + du(p[3], lon), p[4], uq)
        if (u < s) == side:
            lo = mid
        else:
            hi = mid
    return lg_at((lo + hi) / 2, p[3])[0]


def split(points, stops, proj, leg_at, du):
    """Cut a sampled route (adaptive.sample_route()["points"]: (leg, t, lat, lon, u) in order) on the seam.
    Returns a list of pieces; each piece is a list of (leg, t, lat, lon, u_drawn, kind) with kind "route", "stop" or
    "seam" (a crossing point). leg_at(leg, t, prev_lon) gives the leg's own great-circle point; du is the unwrap step."""
    s0 = seam_u(proj)
    seq, flag = [], []                                           # (leg, t, lat, lon, u, kind); on the seam or not
    for k, p in enumerate(points):
        kind = "stop" if (k == 0 or p[1] == 1.0) else "route"
        if kind == "stop":                                       # a place: the shared rule (rounded longitude)
            here = on_seam_lon(p[3], proj)
            if here:                                             # snap it onto the seam (<= 5e-8 degrees)
                p = tuple(p[:4]) + (s0 + 360.0 * round((p[4] - s0) / 360.0),)
        else:
            here = on_seam(p[4], proj)
        if seq:
            a = seq[-1]
            if not flag[-1] and not here and _sheet(a[4], proj) != _sheet(p[4], proj):
                li = p[0]
                tp = a[1] if a[0] == li else 0.0
                lo_s, hi_s = sorted((_sheet(a[4], proj), _sheet(p[4], proj)))
                js = list(range(lo_s, hi_s))
                if p[4] < a[4]:
                    js.reverse()
                for j in js:                                     # usually exactly one seam between two points
                    s = s0 + 360.0 * j
                    lat = crossing(stops[li], stops[li + 1], a[2:4], p[2:4], seam_lon(proj))
                    if lat is None:
                        lat = _bisect(lambda t, pl: leg_at(li, t, pl), tp, p[1], a, s, proj, du, p[4])
                    seq.append((li, None, lat, seam_lon(proj), s, "seam"))
                    flag.append(True)
        seq.append(tuple(p) + (kind,))
        flag.append(here)
    pieces, cur, cur_flag, cur_sheet = [], [], [], None
    for v, f in zip(seq, flag):
        if f:
            cur.append(v)
            cur_flag.append(True)
            continue
        sh = _sheet(v[4], proj)
        if cur_sheet is not None and sh != cur_sheet:
            tail = []
            while cur and cur_flag[-1]:
                tail.insert(0, cur.pop())
                cur_flag.pop()
            pieces.append((cur + tail, cur_sheet))
            cur, cur_flag = list(tail), [True] * len(tail)
        cur_sheet = sh
        cur.append(v)
        cur_flag.append(False)
    pieces.append((cur, cur_sheet))
    out = []
    for pts, sh in pieces:
        if sh is None:                                           # entirely on the seam: where M1 draws the point
            first = pts[0]
            sh = round((first[4] - east_of(first[3], proj.bounds["west"], proj.lon_span)) / 360.0)
        out.append([(v[0], v[1], v[2], v[3], v[4] - 360.0 * sh, v[5]) for v in pts])
    return out
