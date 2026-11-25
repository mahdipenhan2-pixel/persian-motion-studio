"""NFP Location Engine - L1c: parent relationships between locations (a hierarchy). Standard library only.

  "parent": {"id": "<another location's id>", "relation": "within" | "part_of" | "administrative" | "historical"}
    within          the place lies inside the parent area (a village within a valley)
    part_of         a component of the parent (a gate, part of a citadel)
    administrative  belongs to the parent administrative unit (a town in a province)
    historical      belonged to the parent in the past (a city of a former empire) - no geometric check
For within / part_of / administrative, when the parent has an extent the child's point (and extent) must lie inside it
(a warning otherwise: the record may be right and the box too small, so nothing is refused or changed).

Refused: a parent id that is not in the file, a place that is its own parent, and cycles (a -> b -> a); every place
on a cycle is reported. ancestors(index, id) walks the chain up to the root without needing any other NFP engine.
"""
from . import geo

RELATIONS = ("within", "part_of", "administrative", "historical")
GEOMETRIC = ("within", "part_of", "administrative")


def check_shape(p):
    """Shape problems of one parent field: [(level, code, message)]."""
    if not isinstance(p, dict) or set(p) != {"id", "relation"}:
        return [("error", "schema", "parent must be {\"id\": ..., \"relation\": ...}")]
    out = []
    if not isinstance(p["id"], str) or not p["id"]:
        out.append(("error", "bad_parent", f"parent.id {p['id']!r} must be a location id"))
    if p["relation"] not in RELATIONS:
        out.append(("error", "bad_relation", f"parent.relation must be one of {', '.join(RELATIONS)}"))
    return out


def ancestors(index, lid):
    """[parent, grandparent, ...] ids of `lid` in `index` ({id: record}); raises ValueError on a cycle or a missing id."""
    chain, seen, cur = [], {lid}, lid
    while True:
        p = (index.get(cur) or {}).get("parent")
        if not isinstance(p, dict) or not isinstance(p.get("id"), str):
            return chain
        pid = p["id"]
        if pid not in index:
            raise ValueError(f"{cur}: parent {pid!r} is not in the file")
        if pid in seen:
            raise ValueError(f"cycle: {' -> '.join([lid] + chain + [pid])}")
        chain.append(pid)
        seen.add(pid)
        cur = pid


def on_cycle(index, lid):
    """Does walking up from `lid` come back to `lid`? (a place merely BELOW a cycle is not on it)"""
    cur = lid
    for _ in range(len(index) + 1):
        p = (index.get(cur) or {}).get("parent")
        if not isinstance(p, dict) or p.get("id") not in index:
            return False
        if p["id"] == lid:
            return True
        cur = p["id"]
    return False


def check_links(index, valid_points, valid_extents):
    """Cross-record parent checks: {id: [(level, code, message)]}."""
    out = {}

    def add(lid, *x):
        out.setdefault(lid, []).append(x)

    for lid, r in index.items():
        p = r.get("parent")
        if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not p["id"]:
            continue
        pid = p["id"]
        if pid == lid:
            add(lid, "error", "parent_self", "a location cannot be its own parent")
            continue
        if pid not in index:
            add(lid, "error", "unknown_parent", f"parent {pid!r} is not in this file")
            continue
        if on_cycle(index, lid):
            add(lid, "error", "parent_cycle", f"{lid} is its own ancestor (a cycle through its parent {pid!r})")
            continue
        if p.get("relation") not in GEOMETRIC:
            continue
        pe = valid_extents.get(pid)
        if pe is None:
            continue
        pt = valid_points.get(lid)
        if pt is not None and not geo.contains_point(pe, *pt):
            msg = f"the point {pt[0]!r}, {pt[1]!r} is outside the extent of its parent {pid!r} ({p['relation']})"
            if -90 <= pt[1] <= 90 and geo.contains_point(pe, pt[1], pt[0]):
                msg += " - it would be inside with lat / lon swapped"
            add(lid, "warning", "outside_parent", msg)
        ce = valid_extents.get(lid)
        if ce is not None and not geo.contains_extent(pe, ce):
            add(lid, "warning", "extent_outside_parent", f"the extent is not inside the extent of its parent {pid!r}")
    return out
