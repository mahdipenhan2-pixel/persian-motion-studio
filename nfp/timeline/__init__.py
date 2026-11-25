"""NFP Timeline Engine (stage T1): timeline.json (nfp.timeline/1) + assets.json (nfp.assets/1), anchors -> frames, QC.
Data and checks only - no rendering, no network, no imports from Film / Voice / Subtitles / Character / Studio."""
from .anchors import FPS, AnchorError, Context, frame, js_round
from .assets import check as check_assets, to_photo_slot
from .model import SCHEMA, resolve, validate

__all__ = ["FPS", "AnchorError", "Context", "frame", "js_round", "check_assets", "to_photo_slot", "SCHEMA", "resolve", "validate"]
