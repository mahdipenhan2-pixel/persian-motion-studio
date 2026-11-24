#!/usr/bin/env python3
"""F4 + F5 - C3 characters inside the Film Director (bridge 55_cast_bridge.js + engine/cast_plan.py).

  python3 nfp/film/tests/film_cast_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir> --work <dir outside repo>

Python: planning through C1-C3 (lock, visual guard, C3 planner, C3 validate_keylist after the move to the shot start),
speakers, voice rule, refusals with clear messages. Browser (film_cast_page.mjs): every instance plays its C3 KeyList
exactly (shown / mouth / walk offset on every 3rd frame), parallax position = camera formula for its depth, layer
order (grade above characters), lip sync only for the speaker, the C3 sanitizer accepts the whole rig vocabulary,
broken pages stop with a clear error. Synthetic word timing, silent audio; nothing is written to the repository.
"""
import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FILM / "engine"))
sys.path.insert(0, str(ROOT / "nfp"))
from film_equivalence_check import CDN, silent_wav, synth_timing  # noqa: E402
import cast_plan as CP  # noqa: E402
import compose as C  # noqa: E402
import project as P  # noqa: E402
from character import registry as REG  # noqa: E402
from character.adapter import load_checked  # noqa: E402
from character.animation.keys import sample, validate_keylist  # noqa: E402

FIX = HERE / "fixtures" / "cast-en"
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def refused(fn, needle):
    try:
        fn()
    except SystemExit as e:
        return needle in str(e), str(e).splitlines()[0][:150]
    return False, "accepted"


def variant(work, name, mutate, shots_edit=None, base=None):
    """A copy of a fixture (default: the English cast fixture) in work/<name>, with project.json changed by mutate(p)."""
    d = work / "fixtures" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(base or FIX, d)
    p = json.loads((d / "project.json").read_text(encoding="utf-8"))
    mutate(p)
    (d / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    if shots_edit:
        (d / "shots.js").write_text(shots_edit((d / "shots.js").read_text(encoding="utf-8")), encoding="utf-8")
    return d


def compose(src, work, name, fonts, gsap):
    proj = P.load(src)
    ch = proj["chapters"][0]
    timing = synth_timing(ch)
    b = work / name
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    silent_wav(b / "narration.wav", timing["audio"]["total"])
    ke, fr, rep = CP.fragment(proj, ch, timing, b)
    C.compose(proj, ch, timing, b, fonts, b / "narration.wav", cast_fragment=fr, kit_extra=ke)
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    (b / "story" / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(gsap, b / "story" / "gsap.min.js")
    return proj, ch, timing, b, rep


def plan_only(src):
    proj = P.load(src)
    ch = proj["chapters"][0]
    return CP.fragment(proj, ch, synth_timing(ch), None)


def keylists(b):
    import re
    t = (b / "story" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"window\.K\.film\.mount\((.*)\);\n</script>", t, re.S)
    return json.loads(m.group(1))


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)

    print("== F5 identity (C1 lock + visual guard + real-person policy)")
    check(load_checked(FIX / "film-cast-en").character_ids() == ["lina", "omid"], "fixture cast passes the C1 lock and the visual guard")
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "film-cast-en"
        shutil.copytree(FIX / "film-cast-en", d)
        cj = json.loads((d / "cast.json").read_text(encoding="utf-8"))
        cj["characters"][0]["identity"]["skin"] = "#d99a73"
        (d / "cast.json").write_text(json.dumps(cj), encoding="utf-8")
        ok, msg = refused(lambda: CP.fragment(dict(P.load(FIX), _dir=td, cast={"dir": "film-cast-en"}),
                                              P.load(FIX)["chapters"][0], synth_timing(P.load(FIX)["chapters"][0]), None),
                          "identity changed")
        check(ok, f"a changed identity is refused by the C1 lock ({msg[:90]})")
        cj["characters"][0]["identity"].update(skin="#d99a73", hair_color="#16100f", eye_color="#4a2a1a")
        cj["characters"][0]["stages"]["adult"]["hair"] = "long_straight"
        (d / "cast.json").write_text(json.dumps(cj), encoding="utf-8")
        (d / "cast.lock.json").write_text(json.dumps(REG.make_lock(REG.load_cast(d))), encoding="utf-8")
        ok, msg = refused(lambda: CP.fragment(dict(P.load(FIX), _dir=td, cast={"dir": "film-cast-en"}),
                                              P.load(FIX)["chapters"][0], synth_timing(P.load(FIX)["chapters"][0]), None),
                          "visual identity guard")
        check(ok, f"a locked look-alike of the protected identity is refused ({msg[:90]})")
        cj = json.loads((FIX / "film-cast-en" / "cast.json").read_text(encoding="utf-8"))
        cj["characters"].append({"id": "real", "display_name": "A real athlete", "style": "flat_cartoon_v2",
                                 "identity": {"skin": "#b07a52", "hair_color": "#2a2420", "eye_color": "#3a2a1c"},
                                 "stages": {"adult": {"build": "man", "hair": "slick"}},
                                 "wardrobe": {"kit": {"outfit": "track", "top": "#c8102e", "pants": "#ffffff"}},
                                 "defaults": {"stage": "adult", "wardrobe": "kit", "expr": "neutral"},
                                 "provenance": {"real_person": True, "depiction": "symbolic", "sources": ["a documented public source"]}})
        (d / "cast.json").write_text(json.dumps(cj), encoding="utf-8")
        (d / "cast.lock.json").write_text(json.dumps(REG.make_lock(REG.load_cast(d))), encoding="utf-8")
        check(load_checked(d).character_ids() == ["lina", "omid", "real"],
              "a real person shown symbolically (with a source) is allowed: the guard protects only the Kim identity")

    print("\n== F4 planning (Python)")
    proj, ch, timing, b, rep = compose(FIX, work, "page", a.fonts, a.gsap)
    kls = keylists(b)
    check(rep and len(rep["instances"]) == 4 and all(not validate_keylist(k) for k in kls.values()),
          f"4 instances planned by C3; every moved KeyList passes C3 validate_keylist ({rep['summary']})")
    doms = [i["dom_id"] for i in rep["instances"]]
    check(len(set(doms)) == 4 and doms == ["nfp-c-film-cast-en-lina-1", "nfp-c-film-cast-en-lina-2", "nfp-c-film-cast-en-omid-1",
                                           "nfp-c-film-cast-en-omid-2"], f"C1 DOM ids, one per instance: {doms}")
    lock = json.loads((FIX / "film-cast-en" / "cast.lock.json").read_text(encoding="utf-8"))["characters"]
    check(all(i["fingerprint"] == lock[i["dom_id"].split("-")[-2]] for i in rep["instances"]), "fingerprints = cast.lock.json")
    talks = {i["key"]: [t for x in i["talks"] for t in x["sentences"]] for i in rep["instances"]}
    check(talks == {"lina-street": [], "lina-room": [], "omid-room": ["s2"], "omid-stage": ["s3"]},
          f"speech only for the sentence speakers, each in its own shot ({talks}); s1 = narrator")
    srcs = {k: sorted({x["src"].split(":")[0].split("[")[0] for x in kl["keys"]}) for k, kl in kls.items()}
    check("idle_blink" in srcs["lina-room"] and "idle_breathe" in srcs["lina-room"] and "initial_expr" in srcs["lina-room"]
          and "lipsync" in srcs["omid-room"] and "actions" in srcs["lina-street"],
          f"C3 features present: idle blink/breathe, expressions, actions, viseme lip sync ({srcs['omid-room']})")
    f0 = {i["key"]: i["from_frame"] for i in rep["instances"]}
    check(all(min(k["f"] for k in kl["keys"]) >= f0[key] for key, kl in kls.items()),
          "every key of an instance lies inside its shot (planned in shot time, moved to the shot start)")

    print("\n== F4 refusals (clear messages)")
    cases = [
        ("woman speaking with the project's male voice", lambda p: (p["characters"][1].update(), p["chapters"][0]["sentences"][1].update(speaker="lina-room")), "male voice"),
        ("unknown speaker", lambda p: p["chapters"][0]["sentences"][1].update(speaker="nobody"), "not characters of this chapter"),
        ("speaker not on screen for its sentence", lambda p: p["chapters"][0]["sentences"][0].update(speaker="omid-room"), "not on screen for the whole sentence"),
        ("talk written as an action", lambda p: p["characters"][0]["actions"].append({"do": "talk", "at": 1.0}), "speech comes from the sentence speakers"),
        ("same actor key twice", lambda p: p["characters"].append(copy.deepcopy(p["characters"][0])), "more than one entry"),
        ("action outside the shot", lambda p: p["characters"][0]["actions"].append({"do": "nod", "at": 12.0}), "outside the shot window"),
        ("bad anchor", lambda p: p["characters"][0]["actions"].append({"do": "nod", "at": ["s9", "w", 0]}), "bad time anchor"),
        ("unknown field", lambda p: p["characters"][0].update(colour="#fff"), "unknown field"),
        ("cast outside the project", lambda p: p["cast"].update(dir="../x"), "relative folder inside the project"),
        ("C3 refuses an impossible action", lambda p: p["characters"][0]["actions"].append({"do": "fly", "at": 1.0}), "C3 refused the plan"),
    ]
    for desc, mut, needle in cases:
        d = variant(work, "bad", mut)
        ok, msg = refused(lambda: plan_only(d), needle)
        check(ok, f"refused: {desc} ({msg[:110]})")

    print("\n== F4 page (browser)")
    exp = {"instances": [], "words": [], "silent": []}
    for i in rep["instances"]:
        kl = kls[i["key"]]
        f_a, f_b = i["from_frame"], int(round(i["window"][1] * 30))
        frames = list(range(max(0, f_a - 6), min(kl["frames"], f_b + 6), 3))
        actor = kl["actors"][0]
        st = [sample(kl, f)[i["key"]] for f in frames]
        exp["instances"].append({"key": i["key"], "dom_id": i["dom_id"], "shot": i["shot"], "depth": next(e["depth"] for e in proj["characters"] if e["actor"] == i["key"]),
                                 "x": actor["x"], "y": actor["y"], "frames": frames,
                                 "shown": [f_a <= f < f_b and s.get("self", {}).get("visible", 1) == 1 for f, s in zip(frames, st)],
                                 "mouth": [s.get("mouth", {}).get("shape", "neutral") for s in st],
                                 "selfx": [round(s.get("self", {}).get("--x", 0), 3) for s in st]})
        for t in kl["lipsync"]["talks"]:
            for s in timing["sentences"]:
                if s["id"] in t["sentences"]:
                    exp["words"] += [{"key": i["key"], "dom_id": i["dom_id"], "f": round(w["abs_start"] * 30) + 1, "text": w["text"]} for w in s["words"]]
    s2 = next(s for s in timing["sentences"] if s["id"] == "s2")
    s1 = next(s for s in timing["sentences"] if s["id"] == "s1")
    exp["silent"] = [{"key": "lina-room", "dom_id": "nfp-c-film-cast-en-lina-2", "during": "s2 (omid speaks)",
                      "frames": [round(w["abs_start"] * 30) + 1 for w in s2["words"]][1:]},
                     {"key": "lina-street", "dom_id": "nfp-c-film-cast-en-lina-1", "during": "s1 (narrator)",
                      "frames": [round(w["abs_start"] * 30) + 1 for w in s1["words"]]}]
    rt = (ROOT / "nfp/character/runtime/character_runtime.js").read_text(encoding="utf-8")
    import re
    safe = {k: json.loads(re.search(r"const %s = (\[[^\]]*\]);" % n, rt, re.S).group(1)) for k, n in (("tags", "SAFE_TAGS"), ("attrs", "SAFE_ATTRS"))}
    bad_pages = {}
    d = variant(work, "nocast", lambda p: None, lambda s: s.replace('    K.film.cast(S, "lina-room");\n', ""))
    bad_pages["missing K.film.cast"] = str(compose(d, work, "page-nocast", a.fonts, a.gsap)[3] / "story")
    d = variant(work, "wrongshot", lambda p: None, lambda s: s.replace('b: W("s3", 0), bg: K.bg.livingRoom()', 'b: W("s3", 2), bg: K.bg.livingRoom()'))
    bad_pages["shot window differs from the plan"] = str(compose(d, work, "page-wrongshot", a.fonts, a.gsap)[3] / "story")
    cfg = {"page": str(b / "story"), "expect": exp, "safe": safe, "bad_pages": bad_pages, "out": str(work / "cast_page.json")}
    (work / "cast_page.cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "film_cast_page.mjs"), str(work / "cast_page.cfg.json")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("browser check failed:\n" + r.stderr[-2000:])
    R = json.loads((work / "cast_page.json").read_text(encoding="utf-8"))
    check(not R["errors"] and R["cast"] and R["cast"]["instances"] == 4 and abs(R["cast"]["duration"] - 15) < 1e-6,
          f"page runs: 4 instances mounted on the Director timeline, length unchanged 15s ({R['errors'] or 'no errors'})")
    check(sorted(R["dom_ids"]) == sorted(doms) and len(set(R["dom_ids"])) == 4,
          f"DOM ids on the page = plan, all unique ({len(R['dom_ids'])}; page order follows the K.film.cast calls)")
    check(not R["state"]["bad"], f"every instance plays its C3 KeyList exactly: shown / mouth / walk offset on {R['state']['n']} "
                                 f"instance-frames {R['state']['bad'][:4]}")
    check(R["state"]["parallax_max_err"] is not None and R["state"]["parallax_max_err"] < 0.01,
          f"parallax: character position = camera formula for its depth ({R['state']['parallax_samples']} samples, "
          f"max error {R['state']['parallax_max_err']:.4f} px)")
    check(all(o["index"] < o["layers"] - 1 for o in R["order"]),
          f"layer order: shot grade/light layers lie above every character layer {[(o['key'], o['index'], o['layers']) for o in R['order']]}")
    check(not R["lip"]["bad"] and R["lip"]["words"] > 15, f"lip sync: the speaker's mouth is open on all {R['lip']['words']} spoken words {R['lip']['bad'][:3]}")
    check(all(len(v) == 1 for v in R["lip"]["silent"].values()), f"non-speakers keep one mouth shape: {R['lip']['silent']}")
    check(not R["sweep"]["rejected"] and R["sweep"]["combos"] == R["sweep"]["builds"] * 8 * 10 * 2 and R["sweep"]["builds"] >= 5,
          f"C3 sanitizer accepts all {R['sweep']['combos']} rig combinations ({R['sweep']['builds']} builds of the rig x 8 hair x 10 outfits x 2 flag sets) {R['sweep']['rejected'][:3]}")
    bp = R["bad_pages"]
    check(any("not placed in shots.js" in e for e in bp["missing K.film.cast"]), f"missing K.film.cast stops the page: {bp['missing K.film.cast'][:1]}")
    check(any("was planned for" in e for e in bp["shot window differs from the plan"]),
          f"a shot window that differs from the plan stops the page: {bp['shot window differs from the plan'][:1]}")
    check(R["network_requests"] == 0, f"no network request ({R['network_requests']})")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL CAST BRIDGE TESTS PASSED" if not f else "CAST BRIDGE TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
