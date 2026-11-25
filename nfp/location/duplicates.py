"""NFP Location Engine - L1c: possible duplicate locations. Reports only - nothing is ever merged or changed.

Two locations are reported (a warning on each, naming the other id, the distance and the reason) when
  same_point      their points are identical
  near_point      their points are within `near_m` metres (default 50 m)
  same_name_near  they share a name (Persian letters normalized, case folded, any language / type) and their points are
                  within `name_m` metres (default 5000 m)
Not reported:
  - a pair where one is an ancestor of the other (a citadel inside its city may share the city's point);
  - a pair one of which lists the other in "distinct_from": the user's own statement that they are different places -
    e.g. an ancient city and the modern city on the same spot. Same coordinates alone never make two places one.
The thresholds are parameters of validate() / the command line and are always printed with each warning.
Pairs are compared one by one (n * (n - 1) / 2): fine for the hundreds of places of a film, slow for a gazetteer.
"""
from . import geo
from .names import normalize_fa

NEAR_M = 50.0
NAME_M = 5000.0


def _names(r):
    out = set()
    for n in r.get("names") or []:
        if isinstance(n, dict) and isinstance(n.get("text"), str) and n["text"].strip():
            out.add(normalize_fa(n["text"].strip()).casefold())
    return out


def find(index, points, related, near_m=NEAR_M, name_m=NAME_M):
    """[(id_a, id_b, code, distance_m, detail)] for every suspicious pair (a < b), deterministic order."""
    ids = sorted(i for i in index if i in points)
    out = []
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            a, b = ids[x], ids[y]
            if (a, b) in related:
                continue
            (la, oa), (lb, ob) = points[a], points[b]
            d = geo.distance_m(la, oa, lb, ob)
            if (la, oa) == (lb, ob):
                out.append((a, b, "same_point", 0.0, "identical coordinates"))
            elif d <= near_m:
                out.append((a, b, "near_point", d, f"within {near_m:g} m"))
            else:
                common = _names(index[a]) & _names(index[b])
                if common and d <= name_m:
                    out.append((a, b, "same_name_near", d, f"same name {sorted(common)[0]!r} within {name_m:g} m"))
    return out
