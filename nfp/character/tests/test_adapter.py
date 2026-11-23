#!/usr/bin/env python3
"""
C3a tests: Character Adapter (offline; no rig, no browser, no network, no API).

  python3 nfp/character/tests/test_adapter.py

A. identity: distinct identities, stable fingerprints (= cast.lock.json), no Kim/rig-default leak, missing fields
   fail loudly, an identity change is caught by the C1 lock
B. adapter: C1 -> C2 field mapping, complete rig spec, neutral colours, wardrobe, hair aliases, fingerprint + DOM id,
   invalid input
Temporary casts are written only to a temp directory; nothing in the repository is modified.
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG.parent))

from character import isolation as ISO  # noqa: E402
from character import registry as REG  # noqa: E402
from character.adapter import (AdapterError, CheckedCast, RIG_SPEC_FIELDS, adapt, forbidden_rig_defaults,  # noqa: E402
                               load_checked, validate_rig_spec)
from character.adapter.flat_cartoon_v2 import NEUTRAL, derive_lip  # noqa: E402

DEMO = PKG / "examples" / "demo-cast"
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg)


def raises(fn, *needles):
    try:
        fn()
    except (AdapterError, REG.CastError) as e:
        lines = str(e).splitlines()
        hit = next((ln for ln in lines if all(n in ln for n in needles)), None)
        return hit is not None, (hit or lines[0])[:150]
    return False, "no error raised"


def temp_cast(tmp, name, chars):
    d = Path(tmp) / name
    d.mkdir()
    cast = {"schema": "nfp.cast/1", "project": name, "characters": chars}
    (d / "cast.json").write_text(json.dumps(cast, ensure_ascii=False), encoding="utf-8")
    (d / "cast.lock.json").write_text(json.dumps(REG.make_lock(REG.load_cast(d))), encoding="utf-8")
    return d


def char(cid, skin, hair_color, eye_color, stages, wardrobe, marks=None):
    ident = {"skin": skin, "hair_color": hair_color, "eye_color": eye_color}
    if marks:
        ident["marks"] = marks
    first_stage, first_wd = next(iter(stages)), next(iter(wardrobe))
    return {"id": cid, "display_name": cid, "style": "flat_cartoon_v2", "identity": ident, "stages": stages,
            "wardrobe": wardrobe, "defaults": {"stage": first_stage, "wardrobe": first_wd, "expr": "neutral"},
            "provenance": {"real_person": False, "depiction": "fictional"}}


def main():
    kim, generic = forbidden_rig_defaults()
    cast = load_checked(DEMO)
    lock = json.loads((DEMO / "cast.lock.json").read_text(encoding="utf-8"))
    raw = REG.load_cast(DEMO)

    print("== A. identity")
    z, k = adapt(cast, "zahra"), adapt(cast, "karim")
    check(z["fingerprint"] != k["fingerprint"] and
          (z["spec"]["skin"], z["spec"]["hairColor"], z["spec"]["eyeColor"]) !=
          (k["spec"]["skin"], k["spec"]["hairColor"], k["spec"]["eyeColor"]),
          f"two characters, two identities (zahra {z['fingerprint'][:12]}, karim {k['fingerprint'][:12]})")
    again = [adapt(load_checked(DEMO), c)["fingerprint"] for c in ("zahra", "karim")]
    check(again == [z["fingerprint"], k["fingerprint"]] == [lock["characters"]["zahra"], lock["characters"]["karim"]]
          == [REG.fingerprint(REG.character(raw, c)) for c in ("zahra", "karim")],
          "fingerprints are stable across loads and equal cast.lock.json and C1 fingerprint()")
    fps = {adapt(cast, "zahra", stage=s, wardrobe=w, expr=e)["fingerprint"]
           for s in ("child", "adult") for w in ("casual", "formal") for e in ("neutral", "happy", "cry")}
    check(fps == {z["fingerprint"]}, "stage, wardrobe and expression never change the identity fingerprint (12 combos)")

    leaks, combos = [], 0
    for c in raw["characters"]:
        for s in c["stages"]:
            for w in c["wardrobe"]:
                a = adapt(cast, c["id"], stage=s, wardrobe=w)
                combos += 1
                for f in ("accent", "eyeColor", "hairColor", "lip", "pants", "shoe", "skin", "top", "under"):
                    if a["sources"][f] != "cast" and (a["spec"][f] in kim or a["spec"][f] in generic):
                        leaks.append(f"{c['id']}/{s}/{w}.{f}={a['spec'][f]}")
    check(not leaks and combos == 5, f"no adapter-filled colour equals a Kim or generic rig default ({combos} combos)"
          + (f" LEAKS: {leaks}" if leaks else ""))
    check(z["warnings"] == ["hairColor #1c1210 equals a Kim rig default, but it is the cast's own locked choice"]
          and k["warnings"] == [],
          "a cast that explicitly chose a Kim-equal colour (zahra hair #1c1210) is reported, never silent")

    with tempfile.TemporaryDirectory() as td:
        d = temp_cast(td, "bare-min", [char("min", "#8d5a3c", "#3a2a20", "#2a4a6a",
                                            {"a": {"build": "woman", "hair": "teen_long"}},
                                            {"w": {"outfit": "blazer", "top": "#405060"}})])
        m = adapt(load_checked(d), "min")
        filled = {f: m["spec"][f] for f in m["sources"] if m["sources"][f] in ("neutral", "derived")}
        check(sorted(filled) == ["accent", "legs", "lip", "pants", "shoe", "shoeType", "sleeve", "under"]
              and not (set(filled.values()) & (kim | generic)),
              f"a minimal wardrobe (outfit+top only) is completed from neutral values, none a rig default: {filled}")
        kd = temp_cast(td, "kim-like", [char("k1", "#d99a73", "#2a2a2a", "#336699",
                                             {"a": {"build": "woman", "hair": "long_straight"}},
                                             {"w": {"outfit": "dress", "top": "#aa8877"}})])
        km = adapt(load_checked(kd), "k1")
        check(km["spec"]["skin"] == "#d99a73" and any("skin #d99a73" in w for w in km["warnings"])
              and km["spec"]["lip"] != "#c4666b" and km["spec"]["accent"] != "#e4483f",
              "even a Kim-skinned cast never receives Kim's lip or accent (lip derived, accent neutral)")

        bad = json.loads((DEMO / "cast.json").read_text(encoding="utf-8"))
        del bad["characters"][0]["identity"]["eye_color"]
        bad["project"] = "no-eye"
        bd = Path(td) / "no-eye"
        bd.mkdir()
        (bd / "cast.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
        ok, msg = raises(lambda: load_checked(bd), "eye_color")
        check(ok, f"missing identity.eye_color stops with a clear error ({msg})")
        bad2 = json.loads((DEMO / "cast.json").read_text(encoding="utf-8"))
        del bad2["characters"][1]["wardrobe"]["home"]["top"]
        bad2["project"] = "no-top"
        b2 = Path(td) / "no-top"
        b2.mkdir()
        (b2 / "cast.json").write_text(json.dumps(bad2, ensure_ascii=False), encoding="utf-8")
        ok, msg = raises(lambda: load_checked(b2), "top")
        check(ok, f"missing wardrobe.top stops with a clear error ({msg})")
        spec = dict(z["spec"])
        del spec["eyeColor"]
        ok, msg = raises(lambda: validate_rig_spec(spec), "eyeColor", "fall back")
        check(ok, f"a rig spec missing a field is refused by name ({msg})")

        dd = Path(td) / "demo-cast"
        shutil.copytree(DEMO, dd)
        cj = json.loads((dd / "cast.json").read_text(encoding="utf-8"))
        cj["characters"][0]["identity"]["skin"] = "#d99a73"
        (dd / "cast.json").write_text(json.dumps(cj, ensure_ascii=False), encoding="utf-8")
        ok, msg = raises(lambda: load_checked(dd), "zahra", "identity changed")
        check(ok, f"an unauthorised identity change is caught by the C1 lock ({msg})")
        ok, _ = raises(lambda: REG.validate_usage(raw, {"character": "zahra", "skin": "#000000"}), "locked identity")
        check(ok, "a scene cannot override identity (skin) through C1 usage")

    print("\n== B. adapter")
    zs = z["spec"]
    ident = REG.character(raw, "zahra")["identity"]
    check(zs["skin"] == ident["skin"] and zs["hairColor"] == ident["hair_color"] and zs["eyeColor"] == ident["eye_color"]
          and zs["glasses"] == 1 and k["spec"]["glasses"] == 0,
          "identity maps 1:1 (skin, hair_color->hairColor, eye_color->eyeColor, marks glasses->glasses)")
    check((zs["build"], zs["hair"]) == ("woman", "long_straight") and
          (adapt(cast, "zahra", stage="child")["spec"]["build"], adapt(cast, "zahra", stage="child")["spec"]["hair"])
          == ("child", "child_pony"), "stage maps to build + hair (adult: woman/long_straight, child: child/child_pony)")
    f = adapt(cast, "zahra", wardrobe="formal")["spec"]
    check((zs["outfit"], zs["top"], zs["pants"], zs["sleeve"]) == ("tee2007", "#24242c", "#3b5a8a", "short")
          and (f["outfit"], f["shoeType"], f["earrings"], f["top"]) == ("blazer", "flat", 1, "#3a4a6a")
          and zs["earrings"] == 0 and k["spec"]["accent"] == "#a63a3a",
          "wardrobe maps (outfit, top, pants, sleeve, shoe_type->shoeType, accessories earrings->earrings, accent)")
    every = [adapt(cast, c["id"], stage=s, wardrobe=w, expr=e)
             for c in raw["characters"] for s in c["stages"] for w in c["wardrobe"] for e in ("neutral", "angry")]
    check(all(list(a["spec"]) == list(RIG_SPEC_FIELDS) and validate_rig_spec(a["spec"]) for a in every)
          and len(RIG_SPEC_FIELDS) == 18,
          f"every output is a complete, valid 18-field rig spec in a fixed field order ({len(every)} outputs)")
    neutral_vals = {v for v in NEUTRAL["wardrobe"].values() if str(v).startswith("#")}
    check(not (neutral_vals & (kim | generic)), f"neutral_defaults.json shares no colour with any rig default ({sorted(neutral_vals)})")
    lips = {derive_lip(s) for s in ("#c98f6a", "#b9845c", "#8d5a3c", "#f1d2b8")}
    check(len(lips) == 4 and not (lips & (kim | generic)) and zs["lip"] == derive_lip(zs["skin"]),
          f"lip is derived from each skin (4 skins -> 4 lips, none a rig default: {sorted(lips)})")
    with tempfile.TemporaryDirectory() as td:
        d = temp_cast(td, "alias", [char("h", "#9a6a4a", "#5a3a2a", "#2a3a2a",
                                         {"b": {"build": "teen", "hair": "bob"}, "w": {"build": "woman", "hair": "wavy_long"}},
                                         {"x": {"outfit": "crop", "top": "#887766"}})])
        ac = load_checked(d)
        b, w = adapt(ac, "h", stage="b"), adapt(ac, "h", stage="w")
        check(b["spec"]["hair"] == w["spec"]["hair"] == "teen_long" and b["sources"]["hair"] == "cast(alias)",
              "hair aliases bob / wavy_long resolve to the rig's teen_long (marked as alias)")
    check(z["dom_id"] == ISO.dom_id("demo-cast", "zahra", None) and
          adapt(cast, "karim", instance=3)["dom_id"] == "nfp-c-demo-cast-karim-3",
          f"DOM id comes from C1 isolation ({adapt(cast, 'karim', instance=3)['dom_id']})")
    check(len(z["fingerprint"]) == 64 and z["fingerprint"] == lock["characters"]["zahra"],
          "the adapted character carries the C1 fingerprint (for data-nfp-fp)")
    for desc, fn, needle in (
        ("a raw dict instead of a CheckedCast", lambda: adapt(copy.deepcopy(raw), "zahra"), "CheckedCast"),
        ("building a CheckedCast by hand", lambda: CheckedCast(raw, DEMO), "load_checked"),
        ("an unknown character", lambda: adapt(cast, "nobody"), "unknown character"),
        ("an unknown stage", lambda: adapt(cast, "zahra", stage="old"), "not a stage"),
        ("an unknown wardrobe", lambda: adapt(cast, "zahra", wardrobe="swim"), "not an outfit"),
        ("an unknown expression", lambda: adapt(cast, "zahra", expr="sleepy"), "expression"),
        ("a non-hex colour in a spec", lambda: validate_rig_spec(dict(zs, top="red")), "#rrggbb"),
        ("an unknown rig field", lambda: validate_rig_spec(dict(zs, skirt=1)), "unknown rig field"),
        ("an unknown outfit in a spec", lambda: validate_rig_spec(dict(zs, outfit="cape")), "outfit"),
    ):
        ok, msg = raises(fn, needle)
        check(ok, f"invalid input refused: {desc} ({msg})")

    print("\n== B+ audit fix m7: the checked cast cannot be changed behind the lock")
    c2 = load_checked(DEMO)
    c2._cast["characters"][0]["identity"]["skin"] = "#d99a73"        # deliberate tampering with the private copy
    ok, msg = raises(lambda: adapt(c2, "zahra"), "changed after load_checked")
    check(ok and adapt(c2, "karim")["fingerprint"] == lock["characters"]["karim"],
          f"changing a CheckedCast's data after the lock check is refused for that character ({msg[:90]})")
    d = load_checked(DEMO).data()
    d["characters"][0]["identity"]["skin"] = "#000000"
    check(adapt(load_checked(DEMO), "zahra")["spec"]["skin"] == "#c98f6a", "data() returns a copy: editing it changes nothing")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ADAPTER TESTS PASSED" if not f else "ADAPTER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
