"""NFP Graphics Engine (stages G1 - G4): graphic documents (nfp.graphics/1) for 16:9 documentaries - data model, style presets,
safe area and QC (G1); text rules and text layout from measured widths (G2); SVG of the text kinds, contrast QC and a preview (G3);
enter / exit animation as Director keys (G4). The core runs nothing:
no process, no file writing, no network, no connection to Film (text is measured by graphics.tools.measure, outside the core). See README.md."""
from .model import DISPLAYS, KINDS, SCHEMA, SPEC_SCHEMA, has_digit, validate
from .safearea import ALLOWED, BAND, FRAME, RESERVED, TITLE_SAFE, check_overlays, check_rect, vignette_at, vignette_of
from .styles import FONT_STACK, PRESETS, resolve_style
from .text import direction, format_number, units
from .textlayout import LAYOUT_SCHEMA, TEXT_KINDS, break_lines, layout, requests
from .render import contrast, extent, preview_html, render_svg
from .animate import anim_js, plan as anim_plan

__all__ = ["DISPLAYS", "KINDS", "SCHEMA", "SPEC_SCHEMA", "has_digit", "validate", "ALLOWED", "BAND", "FRAME", "RESERVED",
           "TITLE_SAFE", "check_overlays", "check_rect", "vignette_at", "vignette_of", "FONT_STACK", "PRESETS", "resolve_style",
           "direction", "format_number", "units", "LAYOUT_SCHEMA", "TEXT_KINDS", "break_lines", "layout", "requests",
           "contrast", "extent", "preview_html", "render_svg", "anim_js", "anim_plan"]
