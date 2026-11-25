"""NFP Map Motion - M2a: adaptive sampling of great-circle routes for drawing. Standard library.

M1 samples every leg at a fixed number of points (`samples`, uniform along the great circle). On the map that is
uneven: near a pole the longitude changes fast and the drawn line becomes a coarse polygon, while a short leg in a
small region gets more points than it needs. Here the points are chosen by the error ON THE MAP, in frame pixels:

  error of a segment = the largest distance (px) from the true great circle to the straight segment, measured at
                       1/4, 1/2 and 3/4 of the segment (three probes, so an S-shaped piece is not missed)
  the worst segment is split at its middle (spherical interpolation, never an average of coordinates) until every
  segment's probe error is within 0.9 x tol_px (default tol 0.5 px; the 10 % margin covers what three probes can
  miss - measured at most ~3 % on random routes), or a cap stops it:
    max_depth  - no segment is split more than this many times (default 24)
    max_points - the whole route never has more than this many points (default 20000)
  A cap is reported in "capped", never hidden.
When no cap is hit, sampling ends only when every final segment's error_px (below) is <= tol_px: after the
three-probe refinement every segment is measured densely, and any segment whose 1.1 x measured error exceeds tol_px is
split again (this catches the corner of a path over a pole, which the three probes can miss).
The reported error is MEASURED after sampling, not the three-probe estimate (which can be ~25 % low on a coarse, capped
segment next to a pole): every final segment is measured at DENSE_PROBES (32) evenly spaced points ->
"error_measured_px" (can still be ~0.5 % low: the peak may lie between two points), and the reported "error_px" is
1.1 x that - the conservative figure, at or above the real error in every test (worst 1.095 x real). Both are
measurements of a sampled curve, not a proof: "error_basis" says so.

Every leg starts from ceil(angle / 10 degrees) equal parts (a minimum density, so a long leg is never judged by a
single chord). Longitudes are unwrapped exactly as M1 does (route.unwrap), so a route over the date line or a pole
stays continuous; x uses the same convention as the plan (u = degrees east of the box's west edge, unwrapped).
Exactly over a pole the longitude is undefined: the point takes the longitude of the point before it (as M1 does), and
the drawn line runs along the pole line (the pole is a line on this projection). There the longitude steps by exactly
180 degrees, and rounding alone would decide +180 or -180; so (1) every point inserted or probed between two points is
placed between their unwrapped longitudes (seam.u_between: a great-circle segment's longitude is monotonic), never a
whole turn away, whatever neighbour it is computed from; (2) in the first points of a route, a step of +-180 (within
1e-9) goes to the side that stays on the drawn map (between the seam - 360 and the seam), else M1's own rule. Deterministic: no clock, no randomness;
ties are broken by leg and position.
"""
import heapq
import math

from .projection import east_of
from .route import RouteError, _latlon, _vec, central_angle, leg as m1_leg, unwrap
from .seam import seam_u, u_between

DEFAULT_TOL_PX = 0.5
DEFAULT_MAX_DEPTH = 24
DEFAULT_MAX_POINTS = 20000
MAX_ARC_DEG = 10.0
POLE_LAT = 90 - 1e-12
PROBES = (0.25, 0.5, 0.75)
DENSE_PROBES = 32               # points per final segment for the reported (measured) error
BOUND_MARGIN = 1.1              # error_px = 1.1 x the measured error (conservative)
SAFETY = 0.9                   # split until the probe error is <= 0.9 x tol: the probes can miss up to ~3 %


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check_params(tol_px, max_depth, max_points):
    """Raise RouteError (a ValueError) for invalid sampling limits."""
    if not (isinstance(tol_px, (int, float)) and not isinstance(tol_px, bool) and math.isfinite(tol_px) and 0.001 <= tol_px <= 100):
        raise RouteError(f"tol_px {tol_px!r} must be a number of pixels in 0.001..100")
    if not (_int(max_depth) and 0 <= max_depth <= 60):
        raise RouteError(f"max_depth {max_depth!r} must be a whole number 0..60")
    if not (_int(max_points) and 2 <= max_points <= 1_000_000):
        raise RouteError(f"max_points {max_points!r} must be a whole number 2..1000000")


def du(lon_from, lon_to):
    """The unwrapped longitude step from lon_from to lon_to, with M1's own rule (route.unwrap)."""
    return unwrap([lon_from, lon_to])[1] - lon_from


class _Leg:
    __slots__ = ("a", "b", "va", "vb", "om", "s")

    def __init__(self, a, b):
        m1_leg(a, b, 2)                                # M1's own checks: valid coordinates, not antipodal
        self.a, self.b = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
        self.va, self.vb = _vec(*a), _vec(*b)
        self.om = central_angle(a, b)
        self.s = math.sin(self.om)

    def at(self, t, prev_lon):
        """(lat, lon) at fraction t of the great circle (spherical linear interpolation)."""
        if t <= 0:
            return self.a
        if t >= 1:
            return self.b
        if self.om < 1e-12:
            return self.a
        f1, f2 = math.sin((1 - t) * self.om) / self.s, math.sin(t * self.om) / self.s
        lat, lon = _latlon(tuple(f1 * x + f2 * y for x, y in zip(self.va, self.vb)))
        if abs(lat) > POLE_LAT:
            lon = prev_lon
        return lat, lon


def _xy(proj, u, lat):
    return proj.x_of_u(u), proj.y0 + (proj.bounds["north"] - lat) * proj.k


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L <= 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _span(p, q):
    """(leg, t of p, t of q) of the segment p-q; p may be the stop shared with the previous leg (its t is 0 here)."""
    return q[0], (p[1] if p[0] == q[0] else 0.0), q[1]


def _probe_error(proj, legs, p, q):
    """Largest pixel distance from the great circle to the chord p-q, at the PROBES fractions of the segment."""
    li, tp, tq = _span(p, q)
    lg = legs[li]
    ax, ay = _xy(proj, p[4], p[2])
    bx, by = _xy(proj, q[4], q[2])
    worst = 0.0
    for f in PROBES:
        lat_m, lon_m = lg.at(tp + (tq - tp) * f, p[3])
        mx, my = _xy(proj, u_between(p[4] + du(p[3], lon_m), p[4], q[4]), lat_m)
        worst = max(worst, _seg_dist(mx, my, ax, ay, bx, by))
    return worst


def _dense_error(proj, legs, p, q, n=DENSE_PROBES):
    """Largest pixel distance from the great circle to the chord p-q at n evenly spaced interior points."""
    li, tp, tq = _span(p, q)
    lg = legs[li]
    ax, ay = _xy(proj, p[4], p[2])
    bx, by = _xy(proj, q[4], q[2])
    worst = 0.0
    for i in range(1, n + 1):
        lat_m, lon_m = lg.at(tp + (tq - tp) * i / (n + 1), p[3])
        mx, my = _xy(proj, u_between(p[4] + du(p[3], lon_m), p[4], q[4]), lat_m)
        worst = max(worst, _seg_dist(mx, my, ax, ay, bx, by))
    return worst


def sample_route(stops, proj, tol_px=DEFAULT_TOL_PX, max_depth=DEFAULT_MAX_DEPTH, max_points=DEFAULT_MAX_POINTS):
    """Adaptive points of a route through `stops` [(lat, lon), ...] (>= 2) on the projection `proj` (an Equirectangular,
    or anything with bounds, lon_span, k, y0 and x_of_u). Returns
      {"points": [(leg, t, lat, lon, u), ...]  in route order; a stop between two legs is ONE point (leg i, t = 1),
       "error_px": 1.1 x error_measured_px (conservative), "error_measured_px": the largest error measured at
       DENSE_PROBES points of every final segment, "error_basis": how they were measured,
       "capped": [] | ["depth"] | ["points"] | both,
       "within_tol": error_px <= tol_px (always true when nothing is capped: see below), "tol_px": ...}
    u is the unwrapped 'degrees east of the west edge' of the plan (x = proj.x_of_u(u))."""
    check_params(tol_px, max_depth, max_points)
    if not (isinstance(stops, (list, tuple)) and len(stops) >= 2):
        raise RouteError("a route needs at least two stops")
    legs = [_Leg(stops[i], stops[i + 1]) for i in range(len(stops) - 1)]
    raw = []                                                 # minimum density: ceil(angle / 10 degrees) parts per leg
    for li, lg in enumerate(legs):
        n0 = 1 if lg.om < 1e-12 else max(1, math.ceil(math.degrees(lg.om) / MAX_ARC_DEG - 1e-9))
        for i in range(0 if li == 0 else 1, n0 + 1):
            lat, lon = lg.at(i / n0, raw[-1][3] if raw else lg.a[1])
            raw.append((li, i / n0, lat, lon))
    if len(raw) > max_points:
        raise RouteError(f"max_points {max_points} is below the minimum density of this route ({len(raw)} points)")
    s0 = seam_u(proj)
    us = [east_of(raw[0][3], proj.bounds["west"], proj.lon_span)]
    for prev, r in zip(raw, raw[1:]):
        d = du(prev[3], r[3])
        if abs(abs(d) - 180.0) < 1e-9:                       # over a pole: the side that stays on the drawn map
            inside = [v for v in (us[-1] + 180.0, us[-1] - 180.0) if s0 - 360.0 < v < s0]
            if len(inside) == 1:
                d = inside[0] - us[-1]
        us.append(us[-1] + d)
    verts = [r + (u,) for r, u in zip(raw, us)]
    nxt = {i: i + 1 for i in range(len(verts) - 1)}          # vertex id -> the next vertex id (route order)
    heap, capped, frozen, depth_of = [], set(), 0.0, {}

    def push(i, depth, key=None):
        p, q = verts[i], verts[nxt[i]]
        li, tp, _ = _span(p, q)
        depth_of[i] = depth
        heapq.heappush(heap, (-(_probe_error(proj, legs, p, q) if key is None else key), li, tp, i, depth))

    for i in range(len(verts) - 1):
        push(i, 0)
    while True:
        while heap:
            neg, li, tp, i, depth = heap[0]
            if -neg <= tol_px * SAFETY:
                break
            if len(verts) >= max_points:
                capped.add("points")
                break
            heapq.heappop(heap)
            if depth >= max_depth:
                capped.add("depth")
                frozen = max(frozen, -neg)
                continue
            p, q = verts[i], verts[nxt[i]]
            tm = (tp + q[1]) / 2
            lat, lon = legs[li].at(tm, p[3])
            verts.append((li, tm, lat, lon, u_between(p[4] + du(p[3], lon), p[4], q[4])))
            j = len(verts) - 1
            nxt[j], nxt[i] = nxt[i], j
            push(i, depth + 1)
            push(j, depth + 1)
        if capped:
            break
        # check every segment densely (the three probes can miss the corner of a path over a pole): a segment whose
        # conservative error (1.1 x measured) is above tol_px is split again; repeat until none is, or a cap stops it
        heap, i = [], 0
        while i in nxt:
            d = _dense_error(proj, legs, verts[i], verts[nxt[i]]) * BOUND_MARGIN
            if d > tol_px:
                push(i, depth_of[i], key=d)
            i = nxt[i]
        if not heap:
            break
    out, i = [verts[0]], 0
    while i in nxt:
        i = nxt[i]
        out.append(verts[i])
    measured = max([_dense_error(proj, legs, a, b) for a, b in zip(out, out[1:])] + [0.0])
    measured = max(measured, max([-h[0] for h in heap] + [frozen, 0.0]))     # never below the probe estimate
    return {"points": out, "error_px": measured * BOUND_MARGIN, "error_measured_px": measured,
            "error_basis": f"measured at {DENSE_PROBES} points per segment, +{BOUND_MARGIN - 1:.0%} margin (a measurement, not a proof)",
            "capped": sorted(capped), "within_tol": measured * BOUND_MARGIN <= tol_px, "tol_px": tol_px}


def max_error_px(sampled, stops, proj, probes_per_leg=2000):
    """Measured map error of a sampled route: the true great circle at probes_per_leg + 1 evenly spaced fractions of
    every leg, each compared (in pixels) with the drawn segment that covers it. For tests and QC; independent of the
    three probes used while sampling."""
    legs = [_Leg(stops[i], stops[i + 1]) for i in range(len(stops) - 1)]
    pts = sampled["points"]
    per_leg = [[] for _ in legs]
    for k, p in enumerate(pts):
        if k == 0:
            per_leg[0].append(p)
            continue
        per_leg[p[0]].append(p)
        if p[0] + 1 < len(legs) and p[1] == 1.0:
            per_leg[p[0] + 1].append((p[0] + 1, 0.0) + p[2:])  # the stop also starts the next leg
    worst = 0.0
    for li, lg in enumerate(legs):
        seg = per_leg[li]
        ts = [0.0 if (n == 0) else p[1] for n, p in enumerate(seg)]
        j = 0
        for n in range(probes_per_leg + 1):
            t = n / probes_per_leg
            while j < len(seg) - 2 and ts[j + 1] < t:
                j += 1
            p, q = seg[j], seg[j + 1]
            lat, lon = lg.at(t, p[3])
            ax, ay = _xy(proj, p[4], p[2])
            bx, by = _xy(proj, q[4], q[2])
            mx, my = _xy(proj, u_between(p[4] + du(p[3], lon), p[4], q[4]), lat)
            worst = max(worst, _seg_dist(mx, my, ax, ay, bx, by))
    return worst
