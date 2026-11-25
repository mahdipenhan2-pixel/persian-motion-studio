"""NFP Map Motion - M2e: basemap geometry for drawing - projection onto the plan's pixels, cutting on the map's seam,
clipping to the frame and simplification. Standard library.

GeoJSON edges are straight in longitude / latitude (RFC 7946), and the plan's projection is equirectangular (x linear
in longitude, y linear in latitude), so every edge is a straight line in plan pixels too: cutting an edge with linear
interpolation is exact here (not an approximation).
  1. longitude, continuous: along each ring / line every step is taken the short way (< 180 degrees; seam.du's rule), so
     a geometry over the antimeridian - split as RFC 7946 asks, or not - stays one connected shape in u (degrees east of
     the map's west edge, as the plan and the geometry use);
  2. a ring around a pole (its continuous longitude ends a whole turn from where it began - Antarctica in most world
     data) is closed along the pole line, which is what that polygon covers on this projection;
  3. the seam: the shape is cut into 360-degree strips (seam.seam_u: the drawn side is seam - 360 .. seam) and each part
     moved onto the drawn side (polygons: Sutherland-Hodgman against the strip's two edges; lines: split where they
     cross a strip edge);
  4. the frame: polygons clipped (Sutherland-Hodgman) and lines clipped (Liang-Barsky) to the frame grown by a margin;
  5. simplification: Douglas-Peucker in pixels, at eps px (the caller chooses it from the camera's largest zoom, so that
     the error stays below half a screen pixel when zoomed in); rings left with < 3 points or an area below eps^2 drop.
Output: [{"kind": "polygon" | "line", "paths": [[(x, y), ...], ...]}] in plan pixels, in the file's feature order.
"""
import math

from .adaptive import du
from .projection import east_of
from .seam import seam_u


def _unwrap_ring(pts, proj):
    """[(lon, lat)] -> [(u, lat)] with u continuous (short steps), starting where the map draws the first point."""
    out = []
    for lon, lat in pts:
        if not out:
            out.append((east_of(lon, proj.bounds["west"], proj.lon_span), lat))
        else:
            out.append((out[-1][0] + du(prev, lon), lat))
        prev = lon
    return out


def _close_pole(ring):
    """A ring whose continuous longitude ends a whole turn away encloses a pole: close it along the pole line."""
    turn = ring[-1][0] - ring[0][0]
    if abs(turn) < 180:
        return ring
    pole = 90.0 if sum(lat for _, lat in ring) > 0 else -90.0
    return ring + [(ring[-1][0], pole), (ring[0][0], pole), ring[0]]


def _clip_poly(poly, inside, cross):
    """Sutherland-Hodgman against one half-plane."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i - 1], poly[i]
        ia, ib = inside(a), inside(b)
        if ib:
            if not ia:
                out.append(cross(a, b))
            out.append(b)
        elif ia:
            out.append(cross(a, b))
    return out


def _vcut(c):
    def cross(a, b):
        t = (c - a[0]) / (b[0] - a[0])
        return (c, a[1] + (b[1] - a[1]) * t)
    return cross


def _hcut(c):
    def cross(a, b):
        t = (c - a[1]) / (b[1] - a[1])
        return (a[0] + (b[0] - a[0]) * t, c)
    return cross


def _strips(lo, hi, s0):
    """Strip numbers k whose span [s0 - 360 + 360k, s0 + 360k] meets [lo, hi]."""
    return range(math.floor((lo - s0) / 360.0) + 1, math.ceil((hi - s0) / 360.0) + 1)


def _poly_strips(ring, s0):
    us = [p[0] for p in ring]
    out = []
    for k in _strips(min(us), max(us), s0):
        a, b = s0 - 360 + 360 * k, s0 + 360 * k
        p = _clip_poly(ring, lambda q, a=a: q[0] >= a, _vcut(a))
        p = _clip_poly(p, lambda q, b=b: q[0] <= b, _vcut(b)) if p else p
        if len(p) >= 3:
            out.append([(u - 360 * k, lat) for u, lat in p])
    return out


def _line_strips(line, s0):
    """A line clipped to each 360-degree strip it meets (the same clipping as the frame), each part moved onto the drawn
    side; a part ends exactly on the strip edge it crosses."""
    us = [p[0] for p in line]
    out = []
    for k in _strips(min(us), max(us), s0):
        a, b = s0 - 360 + 360 * k, s0 + 360 * k
        for part in _clip_line_rect(line, (a, -1e9, b, 1e9)):
            out.append([(u - 360 * k, lat) for u, lat in part])
    return out


def _liang_barsky(a, b, r):
    x0, y0, x1, y1 = r
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return (a[0] + dx * t0, a[1] + dy * t0), (a[0] + dx * t1, a[1] + dy * t1)


def _clip_line_rect(line, r):
    out, cur = [], []
    for a, b in zip(line, line[1:]):
        seg = _liang_barsky(a, b, r)
        if seg is None:
            if len(cur) >= 2:
                out.append(cur)
            cur = []
            continue
        p, q = seg
        if cur and math.hypot(cur[-1][0] - p[0], cur[-1][1] - p[1]) < 1e-9:
            cur.append(q)
        else:
            if len(cur) >= 2:
                out.append(cur)
            cur = [p, q]
    if len(cur) >= 2:
        out.append(cur)
    return out


def _clip_poly_rect(poly, r):
    x0, y0, x1, y1 = r
    for inside, cross in ((lambda q: q[0] >= x0, _vcut(x0)), (lambda q: q[0] <= x1, _vcut(x1)),
                          (lambda q: q[1] >= y0, _hcut(y0)), (lambda q: q[1] <= y1, _hcut(y1))):
        poly = _clip_poly(poly, inside, cross)
        if not poly:
            return []
    return poly


def simplify(pts, eps, closed=False):
    """Douglas-Peucker (iterative, deterministic); the ends are kept (a closed ring keeps its first point)."""
    if len(pts) < 3 or eps <= 0:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        a, b = pts[i], pts[j]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        best, k = -1.0, None
        for m in range(i + 1, j):
            p = pts[m]
            d = abs(dy * (p[0] - a[0]) - dx * (p[1] - a[1])) / L if L > 0 else math.hypot(p[0] - a[0], p[1] - a[1])
            if d > best:
                best, k = d, m
        if k is not None and best > eps:
            keep[k] = True
            stack.append((i, k))
            stack.append((k, j))
    return [p for p, f in zip(pts, keep) if f]


def _area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def project_layer(features, proj, frame, eps=0.25, margin=8.0):
    """Basemap features (geodata form: [lon, lat] coordinates) -> drawable paths in plan pixels."""
    s0 = seam_u(proj)
    rect = (-margin, -margin, frame["width"] + margin, frame["height"] + margin)
    xy = lambda q: (proj.x_of_u(q[0]), proj.y0 + (proj.bounds["north"] - q[1]) * proj.k)
    out = []
    for f in features:
        t, c = f["type"], f["coordinates"]
        if t in ("Polygon", "MultiPolygon"):
            polys = [c] if t == "Polygon" else c
            paths = []
            for poly in polys:
                for ring in poly:
                    r = _close_pole(_unwrap_ring([(p[0], p[1]) for p in ring[:-1]], proj))
                    if r[-1] == r[0]:
                        r = r[:-1]
                    for part in _poly_strips(r, s0):
                        px = _clip_poly_rect([xy(q) for q in part], rect)
                        if len(px) >= 3:
                            px = simplify(px + [px[0]], eps)[:-1]
                            if len(px) >= 3 and _area(px) >= eps * eps:
                                paths.append(px)
            if paths:
                out.append({"kind": "polygon", "paths": paths})
        else:
            lines = [c] if t == "LineString" else c
            paths = []
            for line in lines:
                for part in _line_strips(_unwrap_ring([(p[0], p[1]) for p in line], proj), s0):
                    for seg in _clip_line_rect([xy(q) for q in part], rect):
                        seg = simplify(seg, eps)
                        if len(seg) >= 2:
                            paths.append(seg)
            if paths:
                out.append({"kind": "line", "paths": paths})
    return out
