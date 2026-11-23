"""
NFP Character Engine - project isolation (C1).

  dom_id(project, character, instance)   one namespaced DOM id per placed character: never collides between projects
  scan(roots)                            every <root>/<project>/cast.json, checked together:
      * each cast is valid and its project id equals its folder name (no project-id collisions)
      * two characters with the SAME identity fingerprint are a copy: allowed only when one declares
        derived_from "<project>/<id>" pointing at the other (or both at the same origin). Otherwise: an
        unintended copy between projects, or two indistinguishable characters inside one project.
      * derived_from must point at a character that exists.
Characters are local to their project; nothing here is global except this read-only check.
"""
import re
from pathlib import Path

from .registry import CastError, fingerprint, load_cast

_SAFE = re.compile(r"[^a-z0-9-]")


def dom_id(project, character, instance=None):
    parts = ["nfp-c", project, character] + ([str(instance)] if instance is not None else [])
    out = "-".join(_SAFE.sub("-", p.lower()) for p in parts)
    if not re.match(r"^[a-z][a-z0-9-]*$", out):
        raise ValueError(f"cannot build a DOM id from {parts}")
    return out


def find_casts(roots):
    found = []
    for r in roots:
        r = Path(r)
        if r.is_dir():
            found += sorted(p for p in r.glob("*/cast.json") if p.is_file())
    return found


def scan(roots):
    """Return {"projects", "characters", "problems": [...], "index": {fingerprint: [refs]}} for all casts under roots."""
    problems, casts, by_project = [], [], {}
    for p in find_casts(roots):
        try:
            cast = load_cast(p.parent)
        except CastError as e:
            problems += [f"{p.parent.name}: {x}" for x in e.problems]
            continue
        if cast["project"] in by_project:
            problems.append(f"project id '{cast['project']}' is used by two folders: {by_project[cast['project']]} and {p.parent}")
            continue
        by_project[cast["project"]] = p.parent
        casts.append(cast)

    refs = {}           # "<project>/<id>" -> (fingerprint, derived_from)
    index = {}          # fingerprint -> ["<project>/<id>", ...]
    for cast in casts:
        for c in cast["characters"]:
            ref = f"{cast['project']}/{c['id']}"
            fp = fingerprint(c)
            refs[ref] = (fp, c.get("derived_from"))
            index.setdefault(fp, []).append(ref)

    for ref, (fp, der) in sorted(refs.items()):
        if der is not None:
            if der not in refs:
                problems.append(f"{ref}: derived_from '{der}' does not exist")
            elif der == ref:
                problems.append(f"{ref}: derived_from points at itself")

    def origin(ref, seen=()):
        der = refs[ref][1]
        if der is None or der not in refs or der in seen:
            return ref
        return origin(der, seen + (ref,))

    for fp, group in sorted(index.items()):
        if len(group) < 2:
            continue
        projects = {g.split("/")[0] for g in group}
        for proj in sorted(projects):
            same = [g for g in group if g.startswith(proj + "/")]
            if len(same) > 1:
                problems.append(f"{', '.join(same)}: identical identity inside one project (indistinguishable characters)")
        roots_ = {origin(g) for g in group}
        if len(roots_) > 1 and len(projects) > 1:
            problems.append(f"{', '.join(group)}: identical identity in different projects without derived_from "
                            "(unintended copy; declare derived_from or give each its own identity)")
    n_chars = sum(len(c["characters"]) for c in casts)
    return {"projects": len(casts), "characters": n_chars, "problems": problems, "index": index}
