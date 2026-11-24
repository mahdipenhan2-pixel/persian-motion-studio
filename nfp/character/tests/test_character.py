#!/usr/bin/env python3
"""
Offline tests for the NFP Character Engine, phase C1 (no rig, no browser, no network, no API).

  python3 nfp/character/tests/test_character.py        T1 + T2
  python3 nfp/character/tests/test_character.py t1     schema / catalogue / policy validation
  python3 nfp/character/tests/test_character.py t2     fingerprint, identity lock, resolve, isolation, CLI
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG.parent))

from character import isolation as ISO  # noqa: E402
from character import registry as REG  # noqa: E402
from character.registry import CastError  # noqa: E402

DEMO = PKG / "examples" / "demo-cast"
FAILS, COUNT = [], [0]


def check(cond, msg):
    COUNT[0] += 1
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def rejects(data, needle, label, project=None):
    try:
        REG.validate_cast(data, project=project)
    except CastError as e:
        check(any(needle in p for p in e.problems), f"rejects {label} ({next((p for p in e.problems if needle in p), e.problems[0])})")
        return
    check(False, f"rejects {label} (was accepted)")


def base():
    return json.loads((DEMO / "cast.json").read_text(encoding="utf-8"))


def mutate(fn):
    d = base()
    fn(d)
    return d


def write_project(root, name, data, lock=True):
    p = Path(root) / name
    p.mkdir(parents=True)
    (p / "cast.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if lock:
        (p / "cast.lock.json").write_text(json.dumps(REG.make_lock(REG.validate_cast(data))), encoding="utf-8")
    return p


# =========================================================================================== T1
def t1():
    print("\n== T1 schema, style catalogue, cross-references, policy")
    cast = REG.validate_cast(base(), project="demo-cast")
    check(len(cast["characters"]) == 2, "demo cast is valid (2 characters, Persian display names)")
    check(REG.available_styles() == ["flat_cartoon_v2"], "style catalogues found: flat_cartoon_v2")

    # the JSON Schema file and the Python validator describe the same fields
    sch = json.loads((PKG / "schema" / "cast.v1.json").read_text(encoding="utf-8"))
    d = sch["$defs"]
    pairs = [
        (set(sch["properties"]), REG.TOP_KEYS, "top level"),
        (set(d["character"]["properties"]), REG.CHAR_KEYS, "character"),
        (set(d["character"]["required"]), REG.CHAR_REQUIRED, "character required"),
        (set(d["character"]["properties"]["identity"]["properties"]), REG.IDENTITY_KEYS, "identity"),
        (set(d["character"]["properties"]["identity"]["required"]), REG.IDENTITY_REQUIRED, "identity required"),
        (set(d["character"]["properties"]["stages"]["additionalProperties"]["properties"]), REG.STAGE_KEYS, "stage"),
        (set(d["character"]["properties"]["wardrobe"]["additionalProperties"]["properties"]), REG.WARDROBE_KEYS, "wardrobe"),
        (set(d["character"]["properties"]["defaults"]["properties"]), REG.DEFAULT_KEYS, "defaults"),
        (set(d["character"]["properties"]["provenance"]["properties"]), REG.PROVENANCE_KEYS, "provenance"),
        (set(d["usage"]["properties"]), REG.USAGE_KEYS, "usage"),
    ]
    check(all(a == b for a, b, _ in pairs), "JSON Schema and Python validator list the same fields (" + ", ".join(n for _, _, n in pairs) + ")")
    check(all(d["character"]["additionalProperties"] is False for _ in [0]) and sch["additionalProperties"] is False,
          "JSON Schema rejects unknown fields")

    c0 = lambda d: d["characters"][0]
    rejects(mutate(lambda d: c0(d).update(bow="#e4483f")), "unknown field 'bow'", "an unknown field (the silent 'bow' of the old qa sheet)")
    rejects(mutate(lambda d: c0(d)["wardrobe"]["casual"].update(skirt="#d9534f")), "unknown field 'skirt'", "an unknown wardrobe field ('skirt')")
    rejects(mutate(lambda d: d.update(schema="nfp.cast/2")), "must be 'nfp.cast/1'", "a wrong schema version")
    rejects(base(), "belongs to project", "a cast whose project id differs from its folder", project="other-project")
    rejects(mutate(lambda d: c0(d).update(id="Zahra")), "must match", "an id with capital letters")
    rejects(mutate(lambda d: d["characters"].append(copy.deepcopy(c0(d)))), "duplicate id", "a duplicate id in one project")
    rejects(mutate(lambda d: c0(d).update(style="semi_real_v9")), "unknown style", "an unknown style")
    rejects(mutate(lambda d: c0(d)["identity"].update(skin="tan")), "#rrggbb", "a non-hex skin colour")
    rejects(mutate(lambda d: c0(d)["identity"].pop("eye_color")), "missing required field 'eye_color'", "a missing identity colour")
    rejects(mutate(lambda d: c0(d)["identity"].update(marks=["tattoo"])), "not a marks", "a mark the style does not have")
    rejects(mutate(lambda d: c0(d)["identity"].update(face={"shape": "square"})), "not a face shape", "a face shape the style does not have")
    rejects(mutate(lambda d: c0(d)["stages"]["adult"].update(build="elder")), "not a build", "an unknown build")
    rejects(mutate(lambda d: c0(d)["stages"]["adult"].update(build="adult")), "not a build", "a rig alias ('adult') instead of a canonical build")
    rejects(mutate(lambda d: c0(d)["stages"]["adult"].update(hair="mohawk")), "not a hair style", "an unknown hair style")
    rejects(mutate(lambda d: c0(d)["wardrobe"]["casual"].update(outfit="kimono")), "not a outfit", "an unknown outfit")
    rejects(mutate(lambda d: c0(d)["wardrobe"]["casual"].update(sleeve="half")), "not a sleeve", "an unknown sleeve")
    rejects(mutate(lambda d: c0(d)["wardrobe"]["casual"].pop("top")), "missing required field 'top'", "an outfit without a top colour")
    rejects(mutate(lambda d: c0(d).update(stages={})), "1-12 stages", "a character without stages")
    rejects(mutate(lambda d: c0(d)["defaults"].update(stage="elderly")), "not one of this character's stages", "a default stage that does not exist")
    rejects(mutate(lambda d: c0(d)["defaults"].update(wardrobe="party")), "not one of this character's outfits", "a default outfit that does not exist")
    rejects(mutate(lambda d: c0(d)["defaults"].update(expr="dancing")), "not a expression", "an unknown default expression")
    rejects(mutate(lambda d: c0(d).update(derived_from="no slash")), "<project>/<character id>", "a malformed derived_from")
    rejects(mutate(lambda d: c0(d).update(display_name="")), "1-40 characters", "an empty display name")

    # policy
    real = lambda **p: mutate(lambda d: c0(d)["provenance"].clear() or c0(d)["provenance"].update(p))
    rejects(real(real_person=True, depiction="symbolic"), "documented source", "a real person without sources")
    rejects(real(real_person=True, sources=["Britannica entry"]), "only be shown symbolically", "a real person without symbolic depiction")
    rejects(real(real_person=False, depiction="symbolic"), "'symbolic' is for real people", "a fictional character marked symbolic")
    rejects(real(real_person="yes"), "true or false", "a non-boolean real_person")
    ok = real(real_person=True, depiction="symbolic", sources=["Encyclopaedia Britannica, biography entry"])
    check(REG.validate_cast(ok) is not None, "a real person shown symbolically with a documented source is accepted")
    rejects(mutate(lambda d: c0(d).update(role="see https://example.com/photo.jpg")), "remote references", "a URL inside a character")
    rejects(mutate(lambda d: c0(d)["provenance"].update(notes="www.example.com")), "remote references", "a www link in notes")
    rejects(mutate(lambda d: c0(d).update(display_name="Za\x07hra")), "control characters", "control characters in a name")

    # usage (what a scene may say)
    cast = REG.validate_cast(base())
    check(REG.validate_usage(cast, {"character": "zahra", "stage": "child", "wardrobe": "formal", "expr": "happy"})["id"] == "zahra",
          "a scene may pick stage, wardrobe and expression")
    for bad, needle, label in [
        ({"character": "zahra", "skin": "#ffffff"}, "locked identity", "a scene overriding skin"),
        ({"character": "zahra", "hair_color": "#ff0000"}, "locked identity", "a scene overriding hair colour"),
        ({"character": "zahra", "hairColor": "#ff0000"}, "locked identity", "a scene using the rig's raw hairColor"),
        ({"character": "zahra", "x": 10}, "unknown field 'x'", "an unknown scene field"),
        ({"character": "nobody"}, "unknown character", "an unknown character"),
        ({"character": "zahra", "stage": "teen"}, "not a stage", "a stage the character does not have"),
        ({"character": "karim", "wardrobe": "casual"}, "not an outfit", "another character's outfit"),
        ({"character": "zahra", "expr": "dancing"}, "not a expression", "an unknown expression"),
        ({"stage": "adult"}, "missing 'character'", "a reference without a character"),
    ]:
        try:
            REG.validate_usage(cast, bad)
            check(False, f"usage rejects {label} (was accepted)")
        except CastError as e:
            check(any(needle in p for p in e.problems), f"usage rejects {label}")


# =========================================================================================== T2
def t2():
    print("\n== T2 fingerprint, identity lock, resolve, isolation, CLI")
    cast = REG.load_and_check(DEMO)
    check(True, "demo cast passes its committed lock (cast.lock.json)")
    z = REG.character(cast, "zahra")
    fp = REG.fingerprint(z)
    check(fp == REG.fingerprint(copy.deepcopy(z)) and len(fp) == 64, "fingerprint is deterministic SHA-256")

    # what the fingerprint covers - and what it deliberately does not
    def fp_after(fn):
        c = copy.deepcopy(z)
        fn(c)
        return REG.fingerprint(c)
    zskin = z["identity"]["skin"]
    check(fp_after(lambda c: c["identity"].update(skin=zskin.upper())) == fp,
          f"colour case does not matter ({zskin.upper()} == {zskin})")
    check(fp_after(lambda c: c["identity"].update(face={"shape": "default"})) == fp, "an explicit default face equals an absent face")
    check(fp_after(lambda c: c.update(display_name="Z", role="other", id="zz")) == fp, "renaming a character keeps its identity")
    check(fp_after(lambda c: c["wardrobe"]["casual"].update(top="#ffffff")) == fp, "changing clothes keeps the identity")
    check(fp_after(lambda c: c["stages"]["adult"].update(hair="bob")) == fp, "another hair style per stage keeps the identity")
    for field, val in (("skin", "#d99a73"), ("hair_color", "#16100f"), ("eye_color", "#5a3320")):
        check(fp_after(lambda c, f=field, v=val: c["identity"].update({f: v})) != fp, f"changing identity.{field} changes the fingerprint")
    check(fp_after(lambda c: c["identity"].update(marks=[])) != fp, "removing a distinguishing mark changes the fingerprint")
    check(fp_after(lambda c: c.update(style="other_style")) != fp, "another style is another identity")

    # the drift seen in the audit (same role, #1c1210 in one project, #16100f in another) is caught by the lock
    with tempfile.TemporaryDirectory() as td:
        d = base()
        p = write_project(td, "demo-cast", d)
        check(REG.load_and_check(p) is not None, "a freshly locked project passes")
        d["characters"][0]["identity"]["hair_color"] = "#16100f"
        (p / "cast.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        try:
            REG.load_and_check(p)
            check(False, "lock catches an identity drift (was accepted)")
        except CastError as e:
            check(any("identity changed since it was locked" in x for x in e.problems), f"lock catches an identity drift ({e.problems[0]})")
        d2 = base()
        d2["characters"][0]["wardrobe"]["casual"]["top"] = "#ffffff"
        (p / "cast.json").write_text(json.dumps(d2, ensure_ascii=False), encoding="utf-8")
        check(REG.load_and_check(p) is not None, "changing clothes does not need a new lock")
        d3 = base()
        d3["characters"].append(dict(copy.deepcopy(d3["characters"][1]), id="leila", display_name="لیلا",
                                     identity={"skin": "#e0a275", "hair_color": "#2b1a17", "eye_color": "#3a2a1a"}))
        (p / "cast.json").write_text(json.dumps(d3, ensure_ascii=False), encoding="utf-8")
        try:
            REG.load_and_check(p)
            check(False, "a new character must be locked deliberately (was accepted)")
        except CastError as e:
            check(any("not in cast.lock.json" in x for x in e.problems), "a new character must be locked deliberately")
        (p / "cast.lock.json").unlink()
        try:
            REG.load_and_check(p)
            check(False, "a missing lock file is refused (was accepted)")
        except CastError as e:
            check(any("missing" in x for x in e.problems), "a missing lock file is refused")
        lock = REG.make_lock(REG.validate_cast(base()))
        lock["characters"]["ghost"] = "0" * 64
        check(any("no longer in cast.json" in x for x in REG.check_lock(REG.validate_cast(base()), lock)),
              "a locked character that was removed is reported")
        check(any("belongs to project" in x for x in REG.check_lock(REG.validate_cast(base()), dict(lock, project="x"))),
              "a lock from another project is refused")

    # resolve: identity always from the cast; same identity in every stage / outfit / expression
    specs = [REG.resolve(cast, "zahra", s, w, e) for s in ("child", "adult") for w in ("casual", "formal")
             for e in ("neutral", "happy", "sad")]
    check(len({json.dumps(s["identity"], sort_keys=True) for s in specs}) == 1 and len({s["fingerprint"] for s in specs}) == 1,
          f"identity is identical in all {len(specs)} stage x outfit x expression combinations")
    r = REG.resolve(cast, "zahra")
    check((r["stage"], r["wardrobe_name"], r["expr"]) == ("adult", "casual", "neutral"), "defaults are applied when a scene says nothing")
    r["identity"]["skin"] = "#000000"
    check(REG.resolve(cast, "zahra")["identity"]["skin"] == zskin, "a resolved spec is a copy (editing it cannot leak back)")

    # isolation across projects
    with tempfile.TemporaryDirectory() as td:
        a = base(); a["project"] = "story-a"
        b = base(); b["project"] = "story-b"
        for c in b["characters"]:
            c["identity"]["skin"] = "#a87452"
        write_project(td, "story-a", a)
        write_project(td, "story-b", b)
        rep = ISO.scan([td])
        check(rep["projects"] == 2 and not rep["problems"], "the same character ids in two projects do not clash (own identities)")
        ids = {ISO.dom_id(p, c, 1) for p in ("story-a", "story-b") for c in ("zahra", "karim")}
        check(len(ids) == 4 and all(i.startswith("nfp-c-") for i in ids), "DOM ids are namespaced per project (no collisions)")

    with tempfile.TemporaryDirectory() as td:
        a = base(); a["project"] = "story-a"
        b = base(); b["project"] = "story-b"
        write_project(td, "story-a", a)
        write_project(td, "story-b", b)
        rep = ISO.scan([td])
        check(any("unintended copy" in p for p in rep["problems"]), "an identical character copied into another project is reported")

    with tempfile.TemporaryDirectory() as td:
        a = base(); a["project"] = "story-a"
        b = base(); b["project"] = "story-b"
        for c in b["characters"]:
            c["derived_from"] = f"story-a/{c['id']}"
        write_project(td, "story-a", a)
        write_project(td, "story-b", b)
        rep = ISO.scan([td])
        check(not rep["problems"], "a deliberate reuse with derived_from is accepted")
        b2 = base(); b2["project"] = "story-c"
        b2["characters"][0]["derived_from"] = "story-x/zahra"
        b2["characters"][0]["identity"]["skin"] = "#123456"
        b2["characters"][1]["identity"]["skin"] = "#654321"
        write_project(td, "story-c", b2)
        check(any("does not exist" in p for p in ISO.scan([td])["problems"]), "derived_from must point at an existing character")

    with tempfile.TemporaryDirectory() as td:
        a = base(); a["project"] = "story-a"
        a["characters"][1]["identity"] = copy.deepcopy(a["characters"][0]["identity"])
        a["characters"][1]["style"] = a["characters"][0]["style"]
        write_project(td, "story-a", a)
        check(any("indistinguishable" in p for p in ISO.scan([td])["problems"]), "two identical identities inside one project are reported")

    with tempfile.TemporaryDirectory() as td:
        d = base(); d["project"] = "wrong-name"
        write_project(td, "story-a", d, lock=False)
        check(any("belongs to project" in p for p in ISO.scan([td])["problems"]), "a cast whose project id differs from its folder is reported by scan")

    # CLI end to end (subprocess, offline)
    cli = [sys.executable, str(PKG / "cli.py")]
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}
    r = subprocess.run(cli + ["check", str(DEMO)], capture_output=True, text=True, env=env)
    check(r.returncode == 0 and "identities match" in r.stdout, "cli check: OK on the demo cast")
    r = subprocess.run(cli + ["lock", str(DEMO)], capture_output=True, text=True, env=env)
    check(r.returncode == 0 and json.loads(r.stdout) == json.loads((DEMO / "cast.lock.json").read_text(encoding="utf-8")),
          "cli lock (without --write) prints exactly the committed lock and writes nothing")
    with tempfile.TemporaryDirectory() as td:
        d = base(); d["characters"][0]["identity"]["eye_color"] = "#000000"
        p = Path(td) / "demo-cast"; p.mkdir()
        (p / "cast.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        (p / "cast.lock.json").write_text((DEMO / "cast.lock.json").read_text(encoding="utf-8"), encoding="utf-8")
        r = subprocess.run(cli + ["check", str(p)], capture_output=True, text=True, env=env)
        check(r.returncode == 1 and "identity changed" in r.stdout, "cli check: exit 1 on identity drift")
    r = subprocess.run(cli + ["scan", str(PKG / "examples")], capture_output=True, text=True, env=env)
    check(r.returncode == 0 and "no unintended copies" in r.stdout, "cli scan: examples are isolated")


PHASES = {"t1": t1, "t2": t2}


def main():
    for name in sys.argv[1:] or list(PHASES):
        if name not in PHASES:
            sys.exit(f"unknown phase {name}; available: {', '.join(PHASES)}")
        PHASES[name]()
    print(f"\n{COUNT[0]} checks, " + ("ALL CHARACTER TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
