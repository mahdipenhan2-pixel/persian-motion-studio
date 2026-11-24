"""
NFP Character Engine - visual identity guard (used by adapter.load_checked for every cast).

A new character must not reproduce the overall LOOK of a protected identity (protected_looks.json), even with
slightly different numbers. The rig's own fallback colours are handled elsewhere (forbidden_rig_defaults); this guard
looks at the combination of features a viewer recognises, for EVERY stage x wardrobe of every character:

  R1 outfit replica   the same outfit type with top colour AND pants or shoe colour close to a signature outfit
  R2 palette copy     skin, hair and eye colour all within a few RGB steps of the protected palette
  R3 look-alike       the protected silhouette (build + hair style, aliases resolved) together with a palette that is
                      close on average (mean closeness >= lookalike_min_mean_closeness)

A dark-haired, brown-eyed character is NOT refused for that alone (R3 needs the signature silhouette too), so common
appearances stay available; changing the hair style or moving the palette away is always enough to pass.
Python standard library only.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "protected_looks.json").read_text(encoding="utf-8"))
HAIR_ALIASES = json.loads((HERE.parent / "animation" / "profile_flat_cartoon_v2.json").read_text(encoding="utf-8"))["hair_aliases"]


def _rgb(h):
    h = h.lower()
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def distance(a, b):
    """Euclidean RGB distance (0 = identical, 441 = black vs white)."""
    return round(sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5, 1)


def _nearest(value, refs):
    return min(distance(value, r) for r in refs)


def check_look(identity, body, wardrobe):
    """Problems (list of str) for one stage x wardrobe of one character; empty = independent look."""
    R = DATA["rules"]
    out = []
    hair = HAIR_ALIASES.get(body.get("hair"), body.get("hair"))
    for ref in DATA["identities"]:
        pal = ref["palette"]
        d = {k: _nearest(identity[k], pal[k]) for k in ("skin", "hair_color", "eye_color")}
        close = {k: max(0.0, 1 - d[k] / R["palette_scale"][k]) for k in d}
        mean = round(sum(close.values()) / 3, 3)
        if all(v <= R["palette_copy_max_distance"] for v in d.values()):
            out.append(f"palette copy of the protected identity '{ref['id']}' (skin/hair/eyes within "
                       f"{R['palette_copy_max_distance']} RGB steps: {d})")
        if [body.get("build"), hair] in ref["silhouettes"] and mean >= R["lookalike_min_mean_closeness"]:
            out.append(f"look-alike of the protected identity '{ref['id']}': its signature silhouette "
                       f"{body.get('build')} + {body.get('hair')} with a close palette (mean closeness {mean}, "
                       f"distances {d}); change the hair style or move skin / hair / eye colours away")
        for o in ref["outfits"]:
            if wardrobe.get("outfit") != o["outfit"] or "top" not in wardrobe:
                continue
            top = distance(wardrobe["top"], o["top"])
            second = [distance(wardrobe[k], o[k]) for k in ("pants", "shoe") if k in wardrobe and k in o]
            if top <= R["outfit_replica_max_distance"] and any(s <= R["outfit_replica_max_distance"] for s in second):
                out.append(f"replica of the protected outfit {o['name']} of '{ref['id']}' ({o['outfit']}, top within "
                           f"{top} RGB steps)")
    return out


def check_cast(cast):
    """Every problem of every character of a validated C1 cast: ['<project>/<id> stage S, wardrobe W: ...']."""
    problems = []
    for c in cast["characters"]:
        ident = c["identity"]
        for sname, body in c["stages"].items():
            for wname, wd in c["wardrobe"].items():
                for p in check_look(ident, body, wd):
                    problems.append(f"{cast['project']}/{c['id']} (stage {sname}, wardrobe {wname}): {p}")
    return problems
