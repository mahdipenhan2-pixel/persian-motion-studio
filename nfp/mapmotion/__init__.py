"""NFP Map Motion Engine (stages M1, M2a, M2b): map.json (nfp.mapmotion/1) -> a deterministic plan; M2a adds its drawing
geometry (adaptive sampling, routes split on the seam); M2b a scene (nfp.mapmotion.scene/1: style, basemap from local
GeoJSON, markers, visibility) resolved into a scene plan. Geography, timing and QC only:
no map drawing, no rendering, no network, no connection to Film / HyperFrames. Reads places with nfp.location's public
API and frames / anchors with nfp.timeline's public Context (both unchanged; nfp/ must be on sys.path). See README.md."""
from .model import PLAN_SCHEMA, SCHEMA, build
from .projection import Equirectangular, ProjectionError, check_bounds, fit_bounds, span
from .route import R_EARTH_M, RouteError, central_angle, leg, unwrap
from .adaptive import max_error_px, sample_route
from .seam import marker_xs, on_seam, seam_lon, seam_u
from .geometry import GEOMETRY_SCHEMA, geometry, projection_from_plan
from .geodata import GeoDataError, check_geojson, read_geojson
from .scene import PRESETS, SCENE_PLAN_SCHEMA, SCENE_SCHEMA, resolve

__all__ = ["PLAN_SCHEMA", "SCHEMA", "build", "Equirectangular", "ProjectionError", "check_bounds", "fit_bounds", "span",
           "R_EARTH_M", "RouteError", "central_angle", "leg", "unwrap",
           "max_error_px", "sample_route", "marker_xs", "on_seam", "seam_lon", "seam_u", "GEOMETRY_SCHEMA", "geometry",
           "projection_from_plan", "GeoDataError", "check_geojson", "read_geojson", "PRESETS", "SCENE_PLAN_SCHEMA",
           "SCENE_SCHEMA", "resolve"]
