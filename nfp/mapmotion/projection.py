"""NFP Map Motion - M1: Equirectangular projection and fitting a geographic box into a 16:9 frame. Standard library.

Projection (equidistant cylindrical, "equirectangular"):
    x = x0 + (lon - west) * k * cos(phi0)          y = y0 + (north - lat) * k
  k     pixels per degree of latitude (chosen so the box fits the frame inside the margins)
  phi0  the standard parallel: "auto" = the middle latitude of the box (true horizontal scale there), or a number
        in -85..85 degrees. phi0 = 0 is the plate carree.
Limitations (by design, documented):
  - distances and shapes are true only along the standard parallel and along meridians; away from phi0 east-west
    distances are stretched by cos(phi0) / cos(lat) - fine for a region, wrong for a hemisphere;
  - areas are not preserved; the poles are lines, not points (a box reaching +-90 is allowed but very stretched);
  - it is a flat map: a great-circle route is drawn through its sampled points (route.py), not as a straight line.
Longitude and the date line: the box is the arc that starts at `west` and runs east to `east`; west > east means it
crosses 180 (the same rule as Location's extent). Every longitude is measured as an angle east of `west` (0..360) and
taken on the side nearer the box, so a point just west of the box gets a small negative x, never one 360 degrees away.
Screen coordinates: origin top-left, x to the right, y down, in pixels of the frame (1920 x 1080 by default).
"""
import math

EPS = 1e-9
MAX_PARALLEL = 85.0


class ProjectionError(ValueError):
    pass


def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def span(west, east):
    """Longitude width (degrees, 0..360] of the arc from west eastwards to east (360 for -180..180 or equal ends)."""
    if west == -180 and east == 180:
        return 360.0
    w = (east - west) % 360
    return 360.0 if w == 0 and west != east else w


def check_bounds(b):
    """Problems of a {north, south, east, west} box: list of messages ([] = valid)."""
    if not isinstance(b, dict) or set(b) != {"north", "south", "east", "west"}:
        return ["bounds must be an object with exactly north, south, east, west"]
    bad = [k for k in ("north", "south", "east", "west") if not finite(b[k])]
    if bad:
        return [f"bounds.{k} must be a finite number" for k in bad]
    out = []
    for k in ("north", "south"):
        if not -90 <= b[k] <= 90:
            out.append(f"bounds.{k} {b[k]!r} is outside -90..90")
    for k in ("east", "west"):
        if not -180 <= b[k] <= 180:
            out.append(f"bounds.{k} {b[k]!r} is outside -180..180")
    if out:
        return out
    if b["south"] >= b["north"]:
        out.append(f"bounds.south {b['south']!r} must be south of bounds.north {b['north']!r} (and not equal)")
    if b["west"] == b["east"]:
        out.append("bounds.west and bounds.east are equal: no width")
    return out


def east_of(lon, west, width):
    """Degrees east of `west` (unwrapped), on the side nearer the box [west, west + width]."""
    u = (lon - west) % 360
    if u > width + (360 - width) / 2:
        u -= 360
    return u


class Equirectangular:
    """A fitted projection: the box `bounds` centred in a width x height frame inside the margins."""

    def __init__(self, bounds, width=1920, height=1080, margin_x=96, margin_y=64, standard_parallel="auto"):
        probs = check_bounds(bounds)
        if probs:
            raise ProjectionError("; ".join(probs))
        for k, v in (("width", width), ("height", height)):
            if not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
                raise ProjectionError(f"{k} must be a whole number of pixels > 0")
        if width * 9 != height * 16:
            raise ProjectionError(f"the frame {width}x{height} is not 16:9")
        for k, v in (("margin_x", margin_x), ("margin_y", margin_y)):
            if not finite(v) or v < 0:
                raise ProjectionError(f"{k} must be a finite number of pixels >= 0")
        if 2 * margin_x >= width or 2 * margin_y >= height:
            raise ProjectionError("the margins leave no room for the map")
        if standard_parallel == "auto":
            phi0 = (bounds["north"] + bounds["south"]) / 2
        elif finite(standard_parallel):
            phi0 = float(standard_parallel)
        else:
            raise ProjectionError('standard_parallel must be "auto" or a number')
        if not -MAX_PARALLEL <= phi0 <= MAX_PARALLEL:
            raise ProjectionError(f"standard_parallel {phi0:g} must be within -{MAX_PARALLEL:g}..{MAX_PARALLEL:g}")
        self.bounds = dict(bounds)
        self.width, self.height = width, height
        self.phi0 = phi0
        self.cos0 = math.cos(math.radians(phi0))
        self.lon_span = span(bounds["west"], bounds["east"])
        self.lat_span = bounds["north"] - bounds["south"]
        cw, ch = width - 2 * margin_x, height - 2 * margin_y
        self.k = min(cw / (self.lon_span * self.cos0), ch / self.lat_span)          # px per degree of latitude
        self.kx = self.k * self.cos0                                                  # px per degree of longitude
        self.x0 = (width - self.lon_span * self.kx) / 2
        self.y0 = (height - self.lat_span * self.k) / 2

    def x_of_u(self, u):
        return self.x0 + u * self.kx

    def project(self, lat, lon):
        """(x, y) in frame pixels of a WGS84 point (finite, lat -90..90, lon -180..180)."""
        if not (finite(lat) and finite(lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ProjectionError(f"point ({lat!r}, {lon!r}) is not a valid WGS84 coordinate")
        return self.x_of_u(east_of(lon, self.bounds["west"], self.lon_span)), self.y0 + (self.bounds["north"] - lat) * self.k

    def inside_frame(self, x, y):
        return -EPS <= x <= self.width + EPS and -EPS <= y <= self.height + EPS

    def inside_map(self, x, y):
        """Inside the drawn map area (the fitted bounds), not merely somewhere in the frame (its margins included)."""
        return (self.x0 - 1e-6 <= x <= self.x0 + self.lon_span * self.kx + 1e-6 and
                self.y0 - 1e-6 <= y <= self.y0 + self.lat_span * self.k + 1e-6)

    def visible(self):
        """The geographic box the whole frame shows (the fitted box widened to the frame's 16:9 shape)."""
        dlon = self.x0 / self.kx
        dlat = self.y0 / self.k
        north = min(90.0, self.bounds["north"] + dlat)
        south = max(-90.0, self.bounds["south"] - dlat)
        width = self.lon_span + 2 * dlon
        if width >= 360 - EPS:
            return {"north": north, "south": south, "west": -180.0, "east": 180.0}
        west = (self.bounds["west"] - dlon + 180) % 360 - 180
        east = (self.bounds["east"] + dlon + 180) % 360 - 180
        return {"north": north, "south": south, "west": west, "east": east}


def fit_bounds(points, pad_deg=0.0):
    """The smallest box around (lat, lon) points: latitudes min..max; longitudes the shortest arc, which may cross the
    date line (the largest empty gap between the sorted longitudes is left out). pad_deg widens it on every side.
    Raises ProjectionError for invalid input: a point that is not a (lat, lon) pair of finite numbers (bool is not a
    number) within -90..90 / -180..180, or a pad_deg that is not a finite number >= 0."""
    if not finite(pad_deg) or pad_deg < 0:
        raise ProjectionError(f"pad_deg {pad_deg!r} must be a finite number >= 0")
    try:
        pts = list(points)
    except TypeError:
        raise ProjectionError("points must be a list of (lat, lon) pairs") from None
    for i, p in enumerate(pts):
        if not (isinstance(p, (list, tuple)) and len(p) == 2):
            raise ProjectionError(f"point {i} {p!r} is not a (lat, lon) pair")
        lat, lon = p
        if not (finite(lat) and finite(lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ProjectionError(f"point {i} ({lat!r}, {lon!r}) is not a valid WGS84 coordinate "
                                  "(finite numbers, lat -90..90, lon -180..180)")
    pts = [(lat, lon) for lat, lon in pts]
    if not pts:
        raise ProjectionError("no points to fit")
    lats = [p[0] for p in pts]
    lons = sorted({p[1] for p in pts})
    if len(lons) == 1:
        west = east = lons[0]
    else:
        gaps = [((lons[(i + 1) % len(lons)] - lons[i]) % 360, i) for i in range(len(lons))]
        gap, i = max(gaps, key=lambda g: (g[0], -g[1]))
        west, east = lons[(i + 1) % len(lons)], lons[i]
    north, south = max(lats) + pad_deg, min(lats) - pad_deg
    arc = 0.0 if len(lons) == 1 else (east - west) % 360
    if arc + 2 * pad_deg >= 360:                         # the padded arc closes the circle: the whole world
        return {"north": min(90.0, north), "south": max(-90.0, south), "west": -180.0, "east": 180.0}
    west, east = west - pad_deg, east + pad_deg
    if north - south < EPS:
        north, south = north + 0.01, south - 0.01                    # a single latitude: give it 0.02 degrees of room
    if span((west + 180) % 360 - 180, (east + 180) % 360 - 180) < EPS or west == east:
        west, east = west - 0.01, east + 0.01
    norm = lambda v: (v + 180) % 360 - 180 if not -180 <= v <= 180 else v
    w, e = norm(west), norm(east)
    if (east - west) >= 360:
        w, e = -180.0, 180.0
    return {"north": min(90.0, north), "south": max(-90.0, south), "west": w, "east": e}
