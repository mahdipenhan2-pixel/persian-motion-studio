"""NFP Map Motion - M2a: drawing geometry of a plan - routes sampled adaptively and split on the seam, and the marker
positions of points (two on the seam). Standard library. Data only: no drawing, no file, the plan is not changed.

  geometry(plan, tol_px=0.5, max_depth=24, max_points=20000, proj=None)  ->
    {"schema": "nfp.mapmotion.geometry/1", "map": .., "tol_px": .., "seam": {"lon": .., "u": ..},
     "points": [{"id", "x": [one or two], "y", "on_seam"}],
     "routes": [{"id", "pieces": [[{"x", "y", "lat", "lon", "s_m", "leg", "kind"}, ...], ...],
                 "crossings", "crossing_points", "seam_stops", "points", "error_px", "error_measured_px", "error_basis",
                 "capped", "length_m"}],
     "issues": [{"level", "code", "element", "message"}]}

  - The plan must be a successful M1 plan (QC status OK or WARN); a FAIL plan is refused (it is not for output).
  - The projection is rebuilt from the plan (bounds, frame, px per degree: it matches the plan's x / y within 0.001 px)
    unless `proj` (the Equirectangular the plan was built with) is given.
  - Stops come from the plan's own legs (the first and last point of every leg). s_m = distance along the route from
    its first stop, in metres (great circle), for timing the drawing later; kind = "stop", "route" or "seam".
  - crossings = len(pieces) - 1: how many times the drawn route changes edge. It changes either at a computed crossing
    point (crossing_points; kind "seam", one copy on each edge) or at a stop that lies on the seam (seam_stops counts
    the route's stops on the seam by the shared rule; a seam stop is a piece boundary only when the route goes on to
    the other side - one that it touches and leaves on the same side stays inside a piece).
  - error_px = 1.1 x error_measured_px (measured at 32 points per final segment): conservative; see adaptive.py.
  - QC: "route_jump" (error) if a step inside a piece spans more than 180 + 1e-3 degrees of longitude (measured in
    degrees, so float noise on a very zoomed map is not an error: next to a pole atan2 gives longitudes ~1e-5 degrees
    off) - a guard: the sampling cannot produce one; a real false step is 360 degrees.
  - QC: "tolerance_exceeded" (warning) if nothing was capped yet error_px > tol_px - a guard: sampling refines until
    error_px <= tol_px unless a cap stops it (then "sampling_capped").
  - QC: "sampling_capped" (warning) when a cap stopped the sampling before tol_px; "route_wraps" (error) if a piece
    end ever missed its stop's marker - by construction it cannot, the check guards the construction.
"""
import math

from . import adaptive as AD
from . import seam as SM
from .model import PLAN_SCHEMA
from .projection import east_of, span
from .route import R_EARTH_M, central_angle

GEOMETRY_SCHEMA = "nfp.mapmotion.geometry/1"
MATCH_PX = 0.002
JUMP_TOL_DEG = 1e-3             # route_jump: more than 180 + 1e-3 degrees (pole noise up to ~1e-5 seen; a false step is 360)


class PlanProjection:
    """The plan's projection, rebuilt from the plan alone (the same formulas as projection.Equirectangular)."""

    def __init__(self, plan):
        b = plan["viewport"]["bounds"]
        self.bounds = dict(b)
        self.width, self.height = plan["frame"]["width"], plan["frame"]["height"]
        self.phi0 = plan["projection"]["standard_parallel"]
        self.k = plan["projection"]["px_per_deg_lat"]
        self.kx = plan["projection"]["px_per_deg_lon"]
        self.lon_span = span(b["west"], b["east"])
        self.lat_span = b["north"] - b["south"]
        self.x0 = (self.width - self.lon_span * self.kx) / 2
        self.y0 = (self.height - self.lat_span * self.k) / 2

    def x_of_u(self, u):
        return self.x0 + u * self.kx

    def project(self, lat, lon):
        return self.x_of_u(east_of(lon, self.bounds["west"], self.lon_span)), self.y0 + (self.bounds["north"] - lat) * self.k


def projection_from_plan(plan):
    return PlanProjection(plan)


def _r(v, n=3):
    return round(v + 0.0, n)


def geometry(plan, tol_px=AD.DEFAULT_TOL_PX, max_depth=AD.DEFAULT_MAX_DEPTH, max_points=AD.DEFAULT_MAX_POINTS, proj=None):
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"geometry() needs an M1 plan ({PLAN_SCHEMA})")
    status = (plan.get("qc") or {}).get("status")
    if status not in ("OK", "WARN"):
        raise ValueError(f"the plan's QC status is {status!r}: a FAIL plan is not usable for drawing")
    AD.check_params(tol_px, max_depth, max_points)
    proj = proj or PlanProjection(plan)
    issues = []
    out = {"schema": GEOMETRY_SCHEMA, "map": plan.get("map"), "tol_px": tol_px,
           "seam": {"lon": _r(SM.seam_lon(proj), 7), "u": _r(SM.seam_u(proj), 7)}, "points": [], "routes": [], "issues": issues}
    for p in plan["points"]:
        xs = SM.marker_xs(proj, p["lat"], p["lon"])
        y = proj.y0 + (proj.bounds["north"] - p["lat"]) * proj.k
        out["points"].append({"id": p["id"], "x": [_r(x) for x in xs], "y": _r(y), "on_seam": len(xs) == 2})
    for r in plan["routes"]:
        stops = [tuple(r["legs"][0]["geo"][0])] + [tuple(lg["geo"][-1]) for lg in r["legs"]]
        sm = AD.sample_route(stops, proj, tol_px, max_depth, max_points)
        legs = [AD._Leg(stops[i], stops[i + 1]) for i in range(len(stops) - 1)]
        pieces = SM.split(sm["points"], stops, proj, lambda li, t, pl: legs[li].at(t, pl), AD.du)
        cum = [0.0]
        for lg in legs:
            cum.append(cum[-1] + R_EARTH_M * lg.om)
        drawn = []
        for pc in pieces:
            row = []
            for li, t, lat, lon, u, kind in pc:
                if t is None:                                    # a seam point: its own distance along the leg
                    t = central_angle(stops[li], (lat, lon)) / legs[li].om if legs[li].om > 0 else 0.0
                s_m = cum[li] + R_EARTH_M * legs[li].om * t
                x = proj.x_of_u(u)
                y = proj.y0 + (proj.bounds["north"] - lat) * proj.k
                lon_d = proj.bounds["west"] + u
                lon_d = lon_d if -180 <= lon_d <= 180 else (lon_d + 180) % 360 - 180
                row.append({"x": _r(x), "y": _r(y), "lat": _r(lat, 7), "lon": _r(lon_d, 7), "s_m": _r(s_m, 2), "leg": li,
                            "kind": kind, "_x": x})
            drawn.append(row)
        # every stop must sit on one of its marker's positions, in the piece it belongs to
        stop_rows = [v for pc in drawn for v in pc if v["kind"] == "stop"]
        for k, (lat, lon) in enumerate(stops):
            want = SM.marker_xs(proj, lat, lon)
            mine = [v for v in stop_rows if (v["leg"] == 0 and k == 0 and v["s_m"] == 0) or (k > 0 and v["leg"] == k - 1 and
                    abs(v["s_m"] - _r(cum[k], 2)) < 0.01)]
            if not mine or any(min(abs(v["_x"] - x) for x in want) > MATCH_PX for v in mine):
                issues.append({"level": "error", "code": "route_wraps", "element": r["id"],
                               "message": f"stop {k + 1} of the route is not drawn on its marker"})
        # no step inside a piece may span more than 180 degrees of longitude (a run along a pole line is exactly 180)
        for pc in drawn:
            if any(abs(w["_x"] - v["_x"]) / proj.kx > 180.0 + JUMP_TOL_DEG for v, w in zip(pc, pc[1:])):
                issues.append({"level": "error", "code": "route_jump", "element": r["id"],
                               "message": "a piece of the drawn route jumps more than 180 degrees of longitude"})
                break
        for pc in drawn:
            for v in pc:
                del v["_x"]
        if sm["capped"]:
            issues.append({"level": "warning", "code": "sampling_capped", "element": r["id"],
                           "message": f"sampling stopped by max_{' / max_'.join(sm['capped'])} before {tol_px:g} px: the drawn "
                                      f"route is up to about {sm['error_px']:.3f} px from the true great circle (measured "
                                      f"{sm['error_measured_px']:.3f} px at 32 points per segment, +10 % margin; a measurement, "
                                      f"not a guarantee)"})
        if not sm["capped"] and not sm["within_tol"]:
            issues.append({"level": "warning", "code": "tolerance_exceeded", "element": r["id"],
                           "message": f"the drawn route is up to about {sm['error_px']:.3f} px from the true great circle, "
                                      f"more than tol {tol_px:g} px, although no cap was hit"})
        cp = sum(1 for pc in drawn for v in pc if v["kind"] == "seam") // 2
        out["routes"].append({"id": r["id"], "pieces": drawn, "crossings": len(drawn) - 1, "crossing_points": cp,
                              "seam_stops": sum(1 for lat, lon in stops if SM.on_seam_lon(lon, proj)),
                              "points": len(sm["points"]), "error_px": _r(sm["error_px"], 4),
                              "error_measured_px": _r(sm["error_measured_px"], 4), "error_basis": sm["error_basis"],
                              "capped": sm["capped"], "length_m": r["length_m"]})
    return out
