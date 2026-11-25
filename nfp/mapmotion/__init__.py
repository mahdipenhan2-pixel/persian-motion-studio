"""NFP Map Motion Engine (stage M1): map.json (nfp.mapmotion/1) -> a deterministic plan. Geography, timing and QC only:
no map drawing, no rendering, no network, no connection to Film / HyperFrames. Reads places with nfp.location's public
API and frames / anchors with nfp.timeline's public Context (both unchanged; nfp/ must be on sys.path). See README.md."""
from .model import PLAN_SCHEMA, SCHEMA, build
from .projection import Equirectangular, ProjectionError, check_bounds, fit_bounds, span
from .route import R_EARTH_M, RouteError, central_angle, leg, unwrap

__all__ = ["PLAN_SCHEMA", "SCHEMA", "build", "Equirectangular", "ProjectionError", "check_bounds", "fit_bounds", "span",
           "R_EARTH_M", "RouteError", "central_angle", "leg", "unwrap"]
