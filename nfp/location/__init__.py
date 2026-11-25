"""NFP Location Engine (L1a + L1b + L1c): locations.json (nfp.locations/1) - place records, names, parents, extents,
possible duplicates, QC and a command line (cli.py).
Data and checks only - no maps, no rendering, no network, no imports from Film / Timeline / Voice / Subtitles /
Character / Studio. See README.md."""
from .model import (FIELDS, KINDS, LEVELS, PRECISIONS, SCHEMA, SOURCE_TYPES, check_point, load, source_problems,
                    validate)
from .names import TYPES as NAME_TYPES, check_names, name_at, normalize_fa
from .geo import check_extent, contains_extent, contains_point, distance_m
from .hierarchy import RELATIONS, ancestors

__all__ = ["FIELDS", "KINDS", "LEVELS", "PRECISIONS", "SCHEMA", "SOURCE_TYPES", "check_point", "load", "source_problems",
           "validate", "NAME_TYPES", "check_names", "name_at", "normalize_fa",
           "check_extent", "contains_extent", "contains_point", "distance_m", "RELATIONS", "ancestors"]
