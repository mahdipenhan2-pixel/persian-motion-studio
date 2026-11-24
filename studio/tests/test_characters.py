#!/usr/bin/env python3
"""
T1 + T2 for the Studio character layer (C4), offline: no API, no network, no TTS, no browser.

  python3 studio/tests/test_characters.py --timing <timing.json of motion-demo-fa> --fonts <dir with vazirmatn woff2>
                                          [--work <dir outside the repository>]

T1  anchors, safe zones, schema rules (every conflict of the final interference table), placement (bust / full),
    single KeyList per video (ids, fingerprints, speakers, narrator default, deco only where characters are), inject
T2  backward compatibility: a project without character fields gets byte-for-byte the same build files from
    run_cast.py as from run_motion.py (with and without camera); motion-demo-fa is unaffected; the injected page
    minus the three additions is byte-identical to run_motion's page.
Everything is written below --work (a temp dir by default); the repository is never written to.
"""
import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "studio" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import project as P  # noqa: E402
import run_cast as RC  # noqa: E402
import run_motion as RM  # noqa: E402
from camera import inject as CI  # noqa: E402
from camera_local_check import synth_narration  # noqa: E402
from characters import build as CB  # noqa: E402
from characters import inject as CJ  # noqa: E402
from characters import schema as CS  # noqa: E402
from characters.schema import CastError  # noqa: E402
from character.animation.keys import sample  # noqa: E402

RESULTS = []
DEMO = "cast-demo-fa"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def refused(fn, needle):
    try:
        fn()
    except (CastError, SystemExit) as e:
        text = str(e)
        return needle in text, text.splitlines()[0][:150]
    return False, "accepted"


def temp_project(work, name, mutate):
    """Copy cast-demo-fa (project.json + cast) into work/projects/<name>, apply mutate(project dict)."""
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(P.PROJECTS / DEMO, d)
    p = json.loads((d / "project.json").read_text(encoding="utf-8"))
    mutate(p)
    (d / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return d / "project.json"


def validate_path(pj):
    proj = P.load(str(pj))
    return CS.validate(proj, Path(pj).parent, [s["id"] for s in P.sentences(proj)])


def compose(kind, name_or_path, work, timing, fonts):
    proj = P.load(str(name_or_path))
    theme = P.load_theme(proj["meta"]["theme"])
    pdir = RM.project_dir(str(name_or_path))
    b = work / kind
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    (b / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
    synth_narration(timing, b / "narration.wav")
    if kind.startswith("motion"):
        RM.compose_with_camera(proj, theme, b, fonts, b / "narration.wav", pdir)
    else:
        RC.compose_with_cast(proj, theme, b, fonts, b / "narration.wav", pdir)
    return b


def tree_hashes(d):
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}


def strip_cast(p):
    p["meta"].pop("cast", None)
    for s in p["scenes"]:
        s.pop("characters", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work")
    a = ap.parse_args()
    work = Path(a.work or tempfile.mkdtemp(prefix="nfp-c4-t12-")).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)
    timing = json.loads(Path(a.timing).read_text(encoding="utf-8"))
    fonts = Path(a.fonts)

    print("== T1.1 anchors and safe zones")
    try:
        CJ.check_anchor_files()
        check(True, "base.html, compose.py, camera/inject.py and camera/camera.js match ANCHORS.json")
    except CastError as e:
        check(False, f"anchors: {e}")
    z = CS.ZONES["formats"]["9:16"]
    s = z["slots"]["bottom"]
    check(s["y"] > z["caption_band"][1] and s["y"] + s["height"] < z["reserved"]["handle_from"]
          and s["x"] >= 0 and s["x"] + s["width"] <= z["page"]["width"] and z["slots"]["top"] is None,
          f"bottom slot y {s['y']}-{s['y'] + s['height']} lies between the caption band (..{z['caption_band'][1]}) and "
          f"the handle ({z['reserved']['handle_from']}..); top slot reserved")
    ok, msg = refused(lambda: CS.slot_geometry("16:9"), "not supported")
    check(ok, f"16:9 is refused explicitly ({msg})")

    print("\n== T1.2 schema: the final interference table")
    check(CS.uses_characters(P.load(DEMO)) and all(not CS.uses_characters(P.load(n)) for n in
                                                    ("motion-demo-fa", "demo-en", "wrinkled-palms-fa")),
          "only cast-demo-fa uses characters; every existing project is untouched by the layer")
    plan = validate_path(P.PROJECTS / DEMO / "project.json")
    check(plan and sorted(plan["actors"]) == ["guest", "host"], "cast-demo-fa validates (2 actors, 4 scenes with characters)")

    def scene(p, sid):
        return next(x for x in p["scenes"] if x["id"] == sid)
    cases = [
        ("cta with note + characters", lambda p: scene(p, "s6").update(characters={"actors": ["host"]}), "cta"),
        ("cta with handle + characters", lambda p: (scene(p, "s6")["on_screen"].pop("note"),
                                                     scene(p, "s6")["on_screen"].update(handle="@x"),
                                                     scene(p, "s6").update(characters={"actors": ["host"]})), "cta"),
        ("camera media frame bottom", lambda p: scene(p, "s5").update(media={"src": "x.png", "frame": "bottom"},
                                                                       characters={"actors": ["host"]}), "media frame 'bottom'"),
        ("slot top", lambda p: scene(p, "s1")["characters"].update(slot="top"), "not available"),
        ("speaker not in the scene", lambda p: scene(p, "s1")["characters"].update(speaker="guest"), "not present"),
        ("sentence number that does not exist", lambda p: scene(p, "s3")["characters"].update(sentence_speakers={"2": "host"}),
         "not a sentence number"),
        ("undeclared actor", lambda p: scene(p, "s1")["characters"]["actors"].append("ghost"), "not declared"),
        ("declared but unused actor", lambda p: p["meta"]["cast"]["actors"].update(extra={"character": "maryam"}),
         "appear in no scene"),
        ("cast dir outside the project", lambda p: p["meta"]["cast"].update(dir="../motion-demo-fa"), "inside the project"),
        ("walk inside the slot", lambda p: scene(p, "s1")["characters"]["actions"].append({"actor": "host", "do": "walk",
                                                                                           "at": 1, "dx": 50}), "not available in the slot"),
        ("action without 'at'", lambda p: scene(p, "s1")["characters"]["actions"].append({"actor": "host", "do": "nod"}), "'at'"),
        ("hop in bust framing", lambda p: scene(p, "s1")["characters"]["actions"].append({"actor": "host", "do": "hop", "at": 2}),
         "bust"),
        ("x at the slot edge", lambda p: p["meta"]["cast"]["actors"]["host"].update(x=0.01), "cut by the slot edge"),
        ("unknown framing", lambda p: p["meta"]["cast"]["actors"]["host"].update(framing="close"), "framing"),
        ("unknown field", lambda p: scene(p, "s1")["characters"].update(camera=1), "unknown field"),
        ("scene characters without meta.cast", lambda p: p["meta"].pop("cast"), "meta.cast is missing"),
    ]
    for i, (desc, mut, needle) in enumerate(cases):
        pj = temp_project(work, f"bad{i}", mut)
        ok, msg = refused(lambda: validate_path(pj), needle)
        check(ok, f"refused: {desc} ({msg})")
    pj = temp_project(work, "nolock", lambda p: None)
    (pj.parent / "cast" / "cast-demo-fa" / "cast.lock.json").unlink()
    ok, msg = refused(lambda: validate_path(pj), "cast.lock.json")
    check(ok, f"refused: cast without cast.lock.json ({msg[:110]})")
    pj = temp_project(work, "drift", lambda p: None)
    cj = pj.parent / "cast" / "cast-demo-fa" / "cast.json"
    c = json.loads(cj.read_text(encoding="utf-8"))
    c["characters"][0]["identity"]["skin"] = "#d99a73"
    cj.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    ok, msg = refused(lambda: validate_path(pj), "identity changed")
    check(ok, f"refused: identity changed since the lock ({msg[:110]})")

    print("\n== T1.3 placement: bust default, full only when it really fits")
    slot = CS.slot_geometry()
    woman = {"build": "woman", "hair": "long_straight"}
    bust = CS.placement(woman, 0.5, "bust", slot)
    b = CS.ZONES["rig_metrics"]["builds"]["woman"]
    check(abs(bust["y"] - (slot["height"] + b["legH"] * bust["scale"])) < 0.01 and bust["face_px"] >= 56,
          f"bust: hips exactly on the slot's lower edge, scale {bust['scale']}, face {bust['face_px']}px")
    full = CS.placement(woman, 0.5, "full", slot)
    top = CS.ZONES["rig_metrics"]["extent"]["woman/long_straight"]["top"]
    check(full["y"] + top * full["scale"] >= 0 and full["face_px"] >= 56 and full["scale"] < bust["scale"],
          f"full: whole body inside the slot (head at {full['y'] + top * full['scale']:.1f}px), face {full['face_px']}px")
    ok, msg = refused(lambda: CS.placement(woman, 0.5, "full", dict(slot, height=150)), "face would be only")
    check(ok, f"full refused when the face would be too small ({msg})")
    check(plan["actors"]["host"]["placement"]["framing"] == "bust" and plan["actors"]["guest"]["placement"]["framing"] == "bust",
          "demo actors use the default bust framing")

    print("\n== T1.4 one KeyList per video")
    cb = compose("cast", P.PROJECTS / DEMO / "project.json", work, timing, fonts)
    kl = json.loads((cb / "cast_keylist.json").read_text(encoding="utf-8"))
    rep = json.loads((cb / "cast_report.json").read_text(encoding="utf-8"))
    page = (cb / "story" / "index.html").read_text(encoding="utf-8")
    data = CI.read_timeline_data(page)
    lock = json.loads((P.PROJECTS / DEMO / "cast" / "cast-demo-fa" / "cast.lock.json").read_text(encoding="utf-8"))
    check(kl["frames"] == int(float(data["duration"]) * 30) and kl["duration"] <= float(data["duration"]),
          f"KeyList {kl['frames']} frames = floor(page {data['duration']}s x 30): the timeline can never grow")
    doms = [x["dom_id"] for x in kl["actors"]]
    check(len(set(doms)) == len(doms) == 2 and all(d.startswith("nfp-c-cast-demo-fa-") for d in doms),
          f"one element per actor for the whole video, C1 ids {doms}")
    fps = {x["id"]: x["fingerprint"] for x in kl["actors"]}
    check(fps == {"host": lock["characters"]["maryam"], "guest": lock["characters"]["reza"]},
          "actor fingerprints = cast.lock.json")
    check(rep["speakers"] == {"s1_1": "host", "s2_1": "host", "s3_1": "guest", "s4_1": "host"}
          and sorted(rep["deco_hidden"]) == ["s1", "s2", "s3", "s4"],
          "speakers as declared (s3 via sentence_speakers); .deco hidden only in the 4 scenes with characters")
    mouth_actors = {k["actor"] for k in kl["keys"] if k["part"] == "mouth" and k["src"].startswith("lipsync")}
    talks = {}
    for t in kl["lipsync"]["talks"]:
        talks.setdefault(t["actor"], []).extend(t["sentences"])
    check(mouth_actors == {"host", "guest"} and sorted(sum(talks.values(), [])) == ["s1_1", "s2_1", "s3_1", "s4_1"],
          "only the declared speakers' mouths move, only on their own sentences")
    spans = CI.scene_spans(data)
    s3 = [w for s_ in timing["sentences"] if s_["id"] == "s3_1" for w in s_["words"] if w["abs_start"] is not None]
    mids = [round((w["abs_start"] + w["abs_end"]) / 2 * 30) for w in s3]
    host_still = all(sample(kl, f)["host"]["mouth"]["shape"] in ("neutral", "smile") for f in mids)
    check(host_still, "while the guest speaks (s3), the host's mouth stays closed")
    unres = [u["text"] for t in kl["lipsync"]["talks"] for u in t["unresolved_words"]]
    check("شش" in unres, f"the real unmatched word 'شش' gets no mouth motion (unresolved: {unres})")
    iv = rep["actors"]["host"]["intervals"][0]
    check(len(rep["actors"]["host"]["intervals"]) == 1 and iv[0] == 0 and abs(iv[1] - spans["s4"][1]) < 1e-3
          and talks["host"] == ["s1_1", "s2_1", "s4_1"] and talks["guest"] == ["s3_1"],
          f"host stays on screen through s1-s4 as one element (0..{iv[1]}s = end of s4) and is gone when s5 is shown")
    g = rep["actors"]["guest"]["intervals"][0]
    gv = lambda f: sample(kl, f)["guest"]["self"]["visible"]  # noqa: E731
    check(gv(int(g[0] * 30) - 2) == 0 and gv(int(g[0] * 30) + 12) == 1 and gv(int(g[1] * 30) + 2) == 0,
          f"guest fades in with s2 ({g[0]}s) and out before s4 ({g[1]}s)")
    s2mid = int((spans["s2"][0] + spans["s2"][1]) / 2 * 30)
    s3late = int((spans["s3"][0] + 2.0) * 30)
    gm = lambda f: sample(kl, f)["guest"]["mouth"]["shape"]  # noqa: E731
    check(gm(s2mid) == "neutral" and sample(kl, s3late)["guest"]["browL"]["--y"] == -18,
          f"expressions follow their own scene: guest neutral in s2 ({gm(s2mid)}), surprised only from s3")
    narr = [s_ for s_ in ("s5_1", "s6_1") if s_ not in rep["speakers"]]
    check(narr == ["s5_1", "s6_1"], "scenes without characters: narrator (no mouth motion)")
    kl2, _, _ = CB.build_keylist(validate_path(P.PROJECTS / DEMO / "project.json"), data, timing, P.PROJECTS / DEMO)
    check(kl2["digest"] == kl["digest"], f"deterministic: same input -> same KeyList digest {kl['digest'][:16]}")

    print("\n== T1.5 inject")
    for needle in ('<style id="nfp-cast-css">', '<div id="nfp-cast"', '<script id="nfp-cast-js">',
                   '<script id="nfp-cast-00-core">', '<script id="nfp-cast-10-chars">', '<script id="nfp-cast-character-runtime">'):
        check(page.count(needle) == 1, f"page contains exactly one {needle}")
    i_layer, i_stage = page.index('<div id="nfp-cast"'), page.index('<section id="stage"')
    check(i_layer < i_stage and page.index("</div></div>", i_layer) < i_stage and page.index('id="scenes"') < i_layer,
          "character layer sits after the scenes and right before the captions (#stage)")
    ok, msg = refused(lambda: CJ.apply(page, kl, slot, []), "already contains")
    check(ok, f"a page cannot get a second character layer ({msg})")
    for sid in ("s5", "s6"):
        check(f"#scene-{sid} .deco" not in page, f"scene {sid} (no characters) keeps its .deco")

    print("\n== T2 backward compatibility (byte for byte)")
    mb = compose("motion-camera", "motion-demo-fa", work, timing, fonts)
    cb2 = compose("cast-camera", "motion-demo-fa", work, timing, fonts)
    check(tree_hashes(mb) == tree_hashes(cb2), f"motion-demo-fa (camera + media, no characters): run_cast == run_motion "
                                                f"for all {len(tree_hashes(mb))} build files")
    pj = temp_project(work, "stripped", strip_cast)
    mb3 = compose("motion-stripped", pj, work, timing, fonts)
    cb3 = compose("cast-stripped", pj, work, timing, fonts)
    check(tree_hashes(mb3) == tree_hashes(cb3), "cast-demo-fa without character fields: run_cast == run_motion, byte for byte")
    pj = temp_project(work, "nocam", lambda p: (strip_cast(p), [s_.pop("camera", None) for s_ in p["scenes"]]))
    mb4 = compose("motion-nocam", pj, work, timing, fonts)
    cb4 = compose("cast-nocam", pj, work, timing, fonts)
    import compose as C
    pb = work / "plain-nocam"
    if pb.exists():
        shutil.rmtree(pb)
    pb.mkdir()
    (pb / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
    synth_narration(timing, pb / "narration.wav")
    proj = P.load(str(pj))
    C.compose(proj, P.load_theme(proj["meta"]["theme"]), timing, pb, fonts, pb / "narration.wav")
    check(tree_hashes(mb4) == tree_hashes(cb4) == tree_hashes(pb),
          "no camera, no characters: run_cast == run_motion == plain compose.py, byte for byte")
    # the character page minus its three additions is exactly run_motion's page for the same project
    cast_page = page
    for a_, b_ in (('<style id="nfp-cast-css">', "</style>\n"), ('<div id="nfp-cast"', "</div></div>\n  ")):
        i = cast_page.index(a_)
        cast_page = cast_page[:i] + cast_page[cast_page.index(b_, i) + len(b_):]
    i = cast_page.index('<script id="nfp-cast-00-core">')
    j = cast_page.index("</body>")
    cast_page = cast_page[:i] + cast_page[j:]
    check(cast_page == (mb3 / "story" / "index.html").read_text(encoding="utf-8"),
          "the character page minus its 3 additions is byte-identical to run_motion's page (scenes, captions, camera untouched)")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL CHARACTER LAYER TESTS PASSED" if not f else "CHARACTER LAYER TESTS FAILED"))
    print(f"work: {work}")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
