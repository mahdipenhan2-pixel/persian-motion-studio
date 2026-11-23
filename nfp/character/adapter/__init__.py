"""NFP Character Engine - C3a Character Adapter: a locked C1 cast character -> a complete, explicit rig spec.
See flat_cartoon_v2.py and README_C3.md."""
from .flat_cartoon_v2 import (AdapterError, CheckedCast, RIG_SPEC_FIELDS, adapt, forbidden_rig_defaults,  # noqa: F401
                              load_checked, validate_rig_spec)
