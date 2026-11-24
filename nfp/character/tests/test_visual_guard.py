"""
NFP Character Engine - visual identity guard tests (adapter/visual_guard.py + protected_looks.json).

Negative cases: casts that must be refused because their overall look reproduces the protected identity
(the earlier demo designs of maryam and zahra, an outfit replica, a palette copy). Positive cases: common looks
that must stay available (dark hair + brown eyes with another silhouette, the protected silhouette with a different
palette) and every character of the committed casts. The guard runs inside load_checked(), so every case is also
checked end to end through a real, locked temp cast.

Run: python3 nfp/character/tests/test_visual_guard.py   (standard library only, writes only to a temp folder)
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = PKG.parent.parent
sys.path.insert(0, str(PKG.parent))

from character import registry as REG  # noqa: E402
from character.adapter import AdapterError, load_checked  # noqa: E402
from character.adapter.visual_guard import DATA, check_cast, check_look, distance  # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg)


def char(cid, ident, stages, wardrobe):
    first_stage, first_wd = next(iter(stages)), next(iter(wardrobe))
    return {"id": cid, "display_name": cid, "style": "flat_cartoon_v2", "identity": ident, "stages": stages,
            "wardrobe": wardrobe, "defaults": {"stage": first_stage, "wardrobe": first_wd, "expr": "neutral"},
            "provenance": {"real_person": False, "depiction": "fictional"}}


def locked_cast(tmp, name, chars):
    d = Path(tmp) / name
    d.mkdir()
    (d / "cast.json").write_text(json.dumps({"schema": "nfp.cast/1", "project": name, "characters": chars},
                                            ensure_ascii=False), encoding="utf-8")
    (d / "cast.lock.json").write_text(json.dumps(REG.make_lock(REG.load_cast(d))), encoding="utf-8")
    return d


def guard_problems(d):
    try:
        load_checked(d)
        return []
    except AdapterError as e:
        return [p for p in e.problems if p.startswith("visual identity guard:")]


# earlier designs from this repository's own history (refused since this guard exists)
OLD_MARYAM = char("maryam", {"skin": "#b8805c", "hair_color": "#2a1a14", "eye_color": "#3a2a1c"},
                  {"adult": {"build": "woman", "hair": "long_straight"}},
                  {"studio": {"outfit": "blazer", "top": "#2f4a5c", "pants": "#1e2a36", "shoe": "#1a1a1a"}})
OLD_ZAHRA = char("zahra", {"skin": "#c98f6a", "hair_color": "#1c1210", "eye_color": "#4a2a1a", "marks": ["glasses"]},
                 {"child": {"build": "child", "hair": "child_pony"}, "adult": {"build": "woman", "hair": "long_straight"}},
                 {"casual": {"outfit": "tee2007", "top": "#24242c", "pants": "#3b5a8a", "shoe": "#2b2230"}})
NEUTRAL_ID = {"skin": "#8d5a3c", "hair_color": "#6b4a2a", "eye_color": "#2f6a4a"}


def main():
    print("== A. protection data")
    kim = next(i for i in DATA["identities"] if i["id"] == "kim")
    check({o["name"] for o in kim["outfits"]} >= {"KIM07", "KIM25"} and ["woman", "long_straight"] in kim["silhouettes"],
          "protected_looks.json covers the signature silhouette and the KIM07 / KIM25 outfits")
    check(distance("#000000", "#ffffff") == 441.7 and distance("#123456", "#123456") == 0,
          "RGB distance: 0 for equal colours, 441.7 for black vs white")

    print("\n== B. refused (negative)")
    with tempfile.TemporaryDirectory() as td:
        p = guard_problems(locked_cast(td, "old-maryam", [OLD_MARYAM]))
        check(any("look-alike" in x and "maryam" in x for x in p), f"the earlier maryam (woman + long_straight, dark "
              f"hair, brown eyes) is refused as a look-alike: {p[:1]}")
        p = guard_problems(locked_cast(td, "old-zahra", [OLD_ZAHRA]))
        check(any("look-alike" in x for x in p) and any("KIM07" in x for x in p),
              f"the earlier zahra is refused (look-alike AND KIM07 outfit replica, {len(p)} problems)")
        rep = char("rep", NEUTRAL_ID, {"a": {"build": "man", "hair": "short_man"}},
                   {"w": {"outfit": "tee2007", "top": "#26262e", "pants": "#3d5c8c", "shoe": "#50607a"}})
        p = guard_problems(locked_cast(td, "replica", [rep]))
        check(len(p) == 1 and "KIM07" in p[0], "a KIM07 replica (same outfit, top + pants within a few steps) is "
              "refused even on a different body and palette")
        dress = char("dr", NEUTRAL_ID, {"a": {"build": "woman", "hair": "slick"}},
                     {"w": {"outfit": "dress", "top": "#b99c88", "shoe": "#c8a48b"}})
        p = guard_problems(locked_cast(td, "dress", [dress]))
        check(len(p) == 1 and "KIM25" in p[0], "a KIM25 replica (dress, top + shoe) is refused")
        pal = char("pc", {"skin": "#d79872", "hair_color": "#18110f", "eye_color": "#4c2b1b"},
                   {"a": {"build": "man", "hair": "short_man"}}, {"w": {"outfit": "blazer", "top": "#305070"}})
        p = guard_problems(locked_cast(td, "palette", [pal]))
        check(any("palette copy" in x for x in p), "a palette copy (skin, hair and eyes within 20 steps) is refused "
              "whatever the silhouette")
        alias = char("al", {"skin": "#c49070", "hair_color": "#20160f", "eye_color": "#503020"},
                     {"t": {"build": "teen", "hair": "wavy_long"}}, {"w": {"outfit": "blazer", "top": "#305070"}})
        check(any("look-alike" in x for x in check_cast({"project": "x", "characters": [alias]})),
              "the teen silhouette is caught through the rig's hair alias (wavy_long -> teen_long)")
        two = char("two", NEUTRAL_ID, {"a": {"build": "man", "hair": "short_man"}},
                   {"ok": {"outfit": "blazer", "top": "#305070"},
                    "bad": {"outfit": "tee2007", "top": "#24242c", "pants": "#3b5a8a"}})
        p = check_cast({"project": "x", "characters": [two]})
        check(len(p) == 1 and "wardrobe bad" in p[0], "every wardrobe is checked: one bad outfit among good ones is "
              "named precisely")

    print("\n== C. allowed (positive)")
    ok_cases = {
        "blonde woman with long straight hair": ({"skin": "#e8c4a0", "hair_color": "#e0c060", "eye_color": "#3a6a9a"},
                                                {"build": "woman", "hair": "long_straight"}),
        "dark-haired, brown-eyed woman with a bob": ({"skin": "#b8805c", "hair_color": "#2a1a14", "eye_color": "#3a2a1c"},
                                                     {"build": "woman", "hair": "bob"}),
        "dark-haired, brown-eyed man": ({"skin": "#c98f6a", "hair_color": "#1c1210", "eye_color": "#4a2a1a"},
                                        {"build": "man", "hair": "short_man"}),
    }
    for desc, (ident, body) in ok_cases.items():
        p = check_look(ident, body, {"outfit": "blazer", "top": "#305070"})
        check(p == [], f"allowed: {desc} {p[:1]}")
    check(check_look(NEUTRAL_ID, {"build": "woman", "hair": "teen_long"},
                     {"outfit": "tee2007", "top": "#24242c", "pants": "#a0d0a0", "shoe": "#f0f0f0"}) == [],
          "the same outfit type with only the top colour close (pants / shoes clearly different) is allowed")
    for rel in ("nfp/character/examples/demo-cast", "studio/projects/cast-demo-fa/cast/cast-demo-fa"):
        d = ROOT / rel
        ids = load_checked(d).character_ids()
        check(check_cast(REG.load_cast(d)) == [], f"committed cast {rel} passes the guard ({', '.join(ids)})")
    m = next(c for c in REG.load_cast(ROOT / "studio/projects/cast-demo-fa/cast/cast-demo-fa")["characters"]
             if c["id"] == "maryam")
    far = {k: min(distance(m["identity"][k], r) for r in kim["palette"][k]) for k in ("skin", "hair_color", "eye_color")}
    check(all(v >= 100 for v in far.values()) and m["stages"]["adult"]["hair"] != "long_straight",
          f"the new maryam is far from the protected palette in every feature {far} and has another hair style")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL VISUAL GUARD TESTS PASSED" if not f else
                                                         "VISUAL GUARD TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
