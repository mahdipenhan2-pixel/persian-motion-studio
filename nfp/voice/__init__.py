"""NFP Voice Engine (V1): voices, casting, per-sentence plan, offline sources, manifest. Standalone: it imports
nothing of Film, Studio or the Stage 2 core, and C1 only read-only (for casting against a locked cast).

    from voice import load_casting, make_plan, produce, validate_manifest
"""
from .casting import NARRATOR, load_casting  # noqa: F401
from .manifest import produce, validate_manifest  # noqa: F401
from .plan import make_plan  # noqa: F401
from .registry import VoiceError, load_registry  # noqa: F401
