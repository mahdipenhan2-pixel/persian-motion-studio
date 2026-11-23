"""
NFP Character Engine - policy rules (C1). Called by registry.validate_cast after the schema checks.

  * Real people are only ever shown symbolically: provenance.real_person = true requires depiction "symbolic",
    at least one documented source, and a style whose catalogue allows it (never a photo-real likeness).
  * Fictional characters are marked as such (depiction "fictional" or absent).
  * No remote references anywhere in a character (no URLs, no downloaded likeness, nothing fetched at build time).
  * Names and notes contain no control characters.
Returns plain-language problems; an empty list means the character passes.
"""
import re

_URL = re.compile(r"(?i)\b(?:[a-z][a-z0-9+.-]*://|www\.)")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _strings(v, path):
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _strings(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _strings(x, f"{path}[{i}]")


def check_policy(c, cat):
    problems = []
    for path, s in _strings(c, "character"):
        if _URL.search(s):
            problems.append(f"{path}: remote references (URLs) are not allowed in a character")
        if _CTRL.search(s):
            problems.append(f"{path}: control characters are not allowed")
    prov = c["provenance"]
    depiction = prov.get("depiction")
    if prov["real_person"]:
        if not (cat or {}).get("allows_real_person", False):
            problems.append(f"style '{c['style']}' may not depict real people")
        if depiction != "symbolic":
            problems.append("a real person may only be shown symbolically (provenance.depiction must be 'symbolic')")
        if not prov.get("sources"):
            problems.append("a real person needs at least one documented source (provenance.sources)")
    else:
        if depiction not in (None, "fictional"):
            problems.append("a fictional character has depiction 'fictional' (or none); 'symbolic' is for real people")
    if cat is not None and depiction is not None and depiction not in cat.get("depiction", []):
        problems.append(f"depiction '{depiction}' is not supported by style '{c['style']}'")
    return problems
