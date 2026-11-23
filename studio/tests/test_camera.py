#!/usr/bin/env python3
"""
Offline tests for the Camera Motion Engine (no API, no network, no browser).

  python3 studio/tests/test_camera.py            all phases that are installed
  python3 studio/tests/test_camera.py t1         presets, safety math, schema
  python3 studio/tests/test_camera.py t2         backward compatibility + anchors (needs run_motion / inject)
  python3 studio/tests/test_camera.py t3m        injected page structure (camera.js / camera.css / media)
"""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "studio" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))

from camera import presets as PR  # noqa: E402
from camera import schema as SC  # noqa: E402
from camera.presets import CameraError  # noqa: E402
import project as P  # noqa: E402

FAILS = []
COUNT = [0]


def check(cond, msg, quiet=False):
    COUNT[0] += 1
    if not cond or not quiet:
        print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def raises(fn, needle, label):
    try:
        fn()
    except CameraError as e:
        check(needle in str(e), f"rejects {label} ({e})")
        return
    check(False, f"rejects {label} (was accepted)")


def lerp(a, b, p):
    return {k: a[k] + (b[k] - a[k]) * p for k in ("s", "x", "y")}


# =========================================================================================== T1
def t1():
    print("\n== T1 presets / safety math / schema")
    intensities = [0.0, 0.25, 0.5, 0.75, 1.0]
    speeds = [0.25, 0.5, 1.0, 2.0, 4.0]
    n_ok = 0
    worst_top, worst_bottom = 0.0, 10_000.0
    for move in PR.MOVES:
        for lang in ("fa", "en"):
            for i in intensities:
                for sp in speeds:
                    # scene graphics: every point of the tween must stay out of the caption band
                    p = PR.plan_move(move, "scene", i, sp, lang, "s3")
                    for k in range(11):
                        st = lerp(p["from"], p["to"], k / 10)
                        PR.check_scene_state(st, f"{move} {lang} i={i} sp={sp} p={k / 10}")
                        e = PR.scene_edges(st)
                        worst_top = max(worst_top, e["top_zone_bottom"])
                        worst_bottom = min(worst_bottom, e["bottom_zone_top"])
                    # media: coverage holds for every point (both frames)
                    for frame in PR.FRAMES:
                        m = PR.plan_move(move, "media", i, sp, lang, "s3", frame)
                        for k in range(11):
                            PR.check_media_state(lerp(m["from"], m["to"], k / 10), PR.FRAMES[frame])
                    n_ok += 1
    check(n_ok == len(PR.MOVES) * 2 * len(intensities) * len(speeds),
          f"{n_ok} move/lang/intensity/speed combinations pass the band + coverage checks at 11 points each")
    check(worst_top <= PR.CAPTION_BAND[0] - PR.BAND_MARGIN,
          f"worst top-zone edge y={worst_top:.1f} stays <= {PR.CAPTION_BAND[0] - PR.BAND_MARGIN}")
    check(worst_bottom >= PR.CAPTION_BAND[1] + PR.BAND_MARGIN,
          f"worst bottom-zone edge y={worst_bottom:.1f} stays >= {PR.CAPTION_BAND[1] + PR.BAND_MARGIN}")
    for name, f in PR.FRAMES.items():
        PR.check_frame(name)
        check(f["bottom"] <= PR.CAPTION_BAND[0] - PR.BAND_MARGIN or f["top"] >= PR.CAPTION_BAND[1] + PR.BAND_MARGIN,
              f"media frame '{name}' ({f['top']}-{f['bottom']}) is outside the caption band")

    # camera state + whole-scene transition scale, combined, for every scene move and every media frame
    n_comp = 0
    for move in PR.MOVES:
        for i in intensities:
            p = PR.plan_move(move, "scene", i, 1.0, "fa", "s3")
            for k in range(11):
                PR.check_composite(lerp(p["from"], p["to"], k / 10), None, PR.TRANSITION_MAX_SCALE)
                n_comp += 1
    for frame in PR.FRAMES:
        PR.check_composite(None, frame, PR.TRANSITION_MAX_SCALE)
        n_comp += 1
    check(True, f"{n_comp} camera + zoom-through combinations keep band, progress bar and handle clear")
    for name, (a, b) in PR.RESERVED.items():
        check(all(f["bottom"] <= a or f["top"] >= b for f in PR.FRAMES.values()), f"no media frame covers the {name} (y {a}-{b})")
    raises(lambda: PR.check_composite(None, "top", 1.06), "progress bar", "a 1.06 whole-scene zoom over the top frame")
    raises(lambda: PR.check_scene_state({"s": 1.05, "x": 0, "y": 0}), "progress bar", "scene zoom over the progress bar")

    # the safety checks really reject unsafe states
    raises(lambda: PR.check_scene_state({"s": 0.95, "x": 0, "y": 0}), "< 1", "scene zoom-out below 1.0")
    raises(lambda: PR.check_scene_state({"s": 1.0, "x": 0, "y": 20}), "top zone", "scene pan down 20 px into band")
    raises(lambda: PR.check_scene_state({"s": 1.0, "x": 0, "y": -40}), "bottom zone", "scene pan up 40 px into band")
    raises(lambda: PR.check_scene_state({"s": 1.2, "x": 0, "y": 0}), "leave the frame", "scene zoom that leaves the frame")
    raises(lambda: PR.check_scene_state({"s": 1.0, "x": 90, "y": 0}), "horizontally", "scene pan that leaves the frame sideways")
    raises(lambda: PR.check_media_state({"s": 1.05, "x": 60, "y": 0}, PR.FRAMES["top"]), "coverage", "media pan revealing an edge")
    raises(lambda: PR.check_media_state({"s": 0.9, "x": 0, "y": 0}, PR.FRAMES["top"]), "< 1", "media scale below 1")

    # moves are visible (not just present in code): minimum travel at the default intensity
    for move in PR.MOVES:
        if move == "none":
            continue
        m = PR.plan_move(move, "media", 0.5, 1.0, "fa", "s3")
        travel = abs(m["to"]["s"] - m["from"]["s"]) * 1080 / 2 + abs(m["to"]["x"] - m["from"]["x"]) + abs(m["to"]["y"] - m["from"]["y"])
        check(travel >= 40, f"media {move}: travel {travel:.0f} px-equivalent >= 40 (visible)", quiet=True)
        g = PR.plan_move(move, "scene", 0.5, 1.0, "fa", "s3")
        gt = abs(g["to"]["s"] - g["from"]["s"]) * 1080 / 2 + abs(g["to"]["x"] - g["from"]["x"]) + abs(g["to"]["y"] - g["from"]["y"])
        check(gt >= 8, f"scene {move}: travel {gt:.0f} px-equivalent >= 8 (visible)", quiet=True)
    check(True, "every move has a visible minimum travel at intensity 0.5 (media >= 40 px, scene >= 8 px)")

    # determinism and direction
    check(all(PR.variant_of("s5") == PR.variant_of("s5") for _ in range(5)), "Ken Burns variant is stable for a scene id")
    check(len({PR.variant_of(f"s{k}") for k in range(1, 30)}) == 4, "Ken Burns uses all 4 variants across scenes")
    check(PR.plan_move("ken-burns", "media", 0.5, 1, "fa", "s2") == PR.plan_move("ken-burns", "media", 0.5, 1, "fa", "s2"),
          "plan_move is deterministic")
    check(PR.resolve_direction("pan-start", "fa") == "pan-right" and PR.resolve_direction("pan-start", "en") == "pan-left",
          "pan-start follows the reading direction (RTL: right, LTR: left)")
    check(PR.plan_transition("slide", "fa")["in_from"]["x"] < 0 < PR.plan_transition("slide", "en")["in_from"]["x"],
          "slide transition is mirrored for RTL")
    check(PR.plan_transition("wipe", "fa")["clip_from"] == "inset(0% 0% 0% 100%)", "RTL wipe reveals from the right")
    for k in PR.TRANSITIONS:
        t = PR.plan_transition(k, "fa")
        for key in ("in_from", "out_to"):
            if key in t:
                check(t[key]["s"] >= 1.0 and t[key]["y"] == 0, f"transition {k} {key}: no shrink, no vertical move", quiet=True)
    check(True, "transitions never shrink a scene or move it vertically")
    p = PR.plan_move("zoom-in", "media", 1.0, 0.5, "fa")
    q = PR.plan_move("zoom-in", "media", 0.5, 1.0, "fa")
    check(p["from"] == q["from"] and p["to"] == q["to"] and p["travel"] == 1.0,
          "speed 0.5 at intensity 1 travels like intensity 0.5 over the full span")
    check(PR.plan_move("zoom-in", "media", 0.5, 2.0, "fa")["travel"] == 0.5, "speed 2 finishes the move in half the span")

    # invalid input
    raises(lambda: PR.plan_move("spin", "media"), "unknown move", "unknown move")
    raises(lambda: PR.plan_move("zoom-in", "media", 1.5), "intensity", "intensity > 1")
    raises(lambda: PR.plan_move("zoom-in", "media", 0.5, 9), "speed", "speed > 4")
    raises(lambda: PR.plan_move("zoom-in", "drone"), "unknown target", "unknown target")
    raises(lambda: PR.plan_transition("spin"), "unknown transition", "unknown transition")
    raises(lambda: PR.plan_transition("slide", "fa", 2.0), "between", "transition longer than 0.6 s")

    # ---- schema
    for n in ("demo-en", "wrinkled-palms-fa"):
        proj = P.load(n)
        check(not SC.has_camera(proj) and SC.validate(proj) is None, f"{n}: no camera fields -> engine stays out of the way")

    base = P.load("wrinkled-palms-fa")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "assets").mkdir()
        (td / "assets" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        (td / "assets" / "fake.jpg").write_bytes(b"not a jpeg")
        (td / "assets" / "bad.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script></svg>')
        (td / "assets" / "ok.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')

        def with_scene(**kw):
            p = copy.deepcopy(base)
            p["scenes"][1].update(kw)
            return p

        good = with_scene(media={"src": "assets/a.png", "frame": "top", "focus": [0.4, 0.6]},
                          camera={"move": "ken-burns", "intensity": 0.7, "transition_in": {"type": "slide", "duration": 0.4}})
        plan = SC.validate(good, td)
        sc1 = plan["scenes"][1]
        check(sc1["move"]["target"] == "media" and sc1["transition"]["kind"] == "slide" and sc1["media"]["frame"] == "top",
              "valid media + camera + transition is accepted (target defaults to media)")
        check(plan["scenes"][0]["move"] is None and plan["scenes"][0]["transition"] is None,
              "scenes without camera keep the plain behaviour")
        svg_ok = with_scene(media={"src": "assets/ok.svg"}, camera={"move": "zoom-in"})
        check(SC.validate(svg_ok, td)["scenes"][1]["media"]["src"] == "assets/ok.svg", "plain SVG media is accepted")
        dflt = copy.deepcopy(base)
        dflt["meta"]["camera_default"] = {"move": "push-in", "intensity": 0.4, "transition": "fade"}
        pl = SC.validate(dflt, td)
        check(all(s["move"]["move"] == "push-in" and s["move"]["target"] == "scene" for s in pl["scenes"]),
              "meta.camera_default applies to every scene (scene graphics when there is no media)")

        raises(lambda: SC.validate(with_scene(camera={"move": "zoom-in", "zoomy": 1}), td), "unknown field", "unknown camera field")
        raises(lambda: SC.validate(with_scene(camera={"move": "zoom-in", "target": "media"}), td), "no media", "media target without media")
        raises(lambda: SC.validate(with_scene(camera={"move": "zoom-in", "ease": "bounce"}), td), "ease", "unknown ease")
        raises(lambda: SC.validate(with_scene(media={"src": "https://example.com/a.png"}), td), "URLs", "remote URL as media")
        raises(lambda: SC.validate(with_scene(media={"src": "/etc/passwd.png"}), td), "relative", "absolute media path")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/../../x.png"}), td), "assets/", "path traversal")
        raises(lambda: SC.validate(with_scene(media={"src": "photos/a.png"}), td), "assets/", "media outside assets/")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/a.gif"}), td), "supported", "unsupported extension")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/missing.png"}), td), "not found", "missing media file")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/fake.jpg"}), td), "real .jpg", "file with a wrong signature")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/bad.svg"}), td), "plain drawing", "SVG with a script")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/a.png", "frame": "middle"}), td), "frame", "media frame inside the band")
        raises(lambda: SC.validate(with_scene(media={"src": "assets/a.png", "focus": [2, 0]}), td), "focus", "focus outside 0-1")
        first = copy.deepcopy(base)
        first["scenes"][0]["camera"] = {"move": "zoom-in", "transition_in": "slide"}
        raises(lambda: SC.validate(first, td), "first scene", "transition into the first scene")
        raises(lambda: SC.validate(with_scene(camera={"move": "zoom-in", "transition_in": {"type": "slide", "duration": 3}}), td),
               "between", "over-long transition")


# =========================================================================================== shared helpers
def fake_timing(proj, word=0.42, gap=0.35):
    """Timing in the exact shape the locked core writes (summary/audio/sentences/words)."""
    cursor, rows = 0.3, []
    for s in P.sentences(proj):
        toks = s["text"].split()
        dur = word * len(toks)
        words = [{"i": i, "text": t, "abs_start": round(cursor + i * dur / len(toks), 3),
                  "abs_end": round(cursor + (i + 0.9) * dur / len(toks), 3), "status": "exact", "timing_quality": "exact"}
                 for i, t in enumerate(toks)]
        rows.append({"id": s["id"], "text": s["text"], "offset": round(cursor, 3), "duration": round(dur, 3), "words": words})
        cursor += dur + gap
    return {"audio": {"total": round(cursor - gap + 0.8, 3), "gap": gap}, "sentences": rows, "summary": {"status": "OK"}}


def prepare_build(td, timing):
    fonts = td / "fonts"
    fonts.mkdir(exist_ok=True)
    (fonts / "vazirmatn-arabic-400-normal.woff2").write_bytes(b"font400")
    (fonts / "vazirmatn-arabic-700-normal.woff2").write_bytes(b"font700")
    (td / "narration.wav").write_bytes(b"RIFF....WAVE")
    (td / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
    return fonts


def tree_bytes(d):
    d = Path(d)
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


# =========================================================================================== T2
def t2():
    print("\n== T2 backward compatibility, anchors, locked core")
    import subprocess
    import compose as C
    import run_motion as RM
    from camera import inject as I

    # anchors: the files the injection depends on are exactly the verified ones
    try:
        I.check_anchor_files()
        check(True, "base.html and compose.py match ANCHORS.json")
    except CameraError as e:
        check(False, f"anchor files changed: {e}")
    base = (ROOT / "studio" / "engine" / "base.html").read_text(encoding="utf-8")
    for a in ("</head>", "</body>", 'window.__timelines["main"] = tl;', "const DATA = __TIMELINE_JSON__;", '<section id="stage"'):
        check(base.count(a) == 1, f"anchor {a!r} appears exactly once in base.html")
    src = (ROOT / "studio" / "engine" / "compose.py").read_text(encoding="utf-8")
    check(src.count("<div class=\"scene\" id=\"scene-{sc[\"id\"]}\">") == 1, "compose.py writes one scene opener per scene")

    # byte-identical output for projects WITHOUT camera fields: run.py path (compose.py) vs run_motion.py
    for n in ("demo-en", "wrinkled-palms-fa"):
        proj = P.load(n)
        theme = P.load_theme(proj["meta"]["theme"])
        timing = fake_timing(proj)
        with tempfile.TemporaryDirectory() as A, tempfile.TemporaryDirectory() as B:
            A, B = Path(A), Path(B)
            fa, fb = prepare_build(A, timing), prepare_build(B, timing)
            C.compose(copy.deepcopy(proj), theme, timing, A, fa, A / "narration.wav")            # what run.py does
            _, compiled = RM.compose_with_camera(copy.deepcopy(proj), theme, B, fb, B / "narration.wav", P.PROJECTS / n)
            ta = {k: v for k, v in tree_bytes(A).items() if k.startswith("story") }
            tb = {k: v for k, v in tree_bytes(B).items() if k.startswith("story")}
            check(compiled is None, f"{n}: camera engine is not applied (no camera fields)")
            check(ta.keys() == tb.keys(), f"{n}: same output files ({len(ta)})")
            check(all(ta[k] == tb[k] for k in ta), f"{n}: every output file is byte-identical (index.html, story.srt, fonts, audio)")
            check(not (B / "camera_plan.json").exists(), f"{n}: no extra camera_plan.json written")

    # run_motion delegates every non-compose command to the unchanged run.py functions
    import run as R
    check(all(RM.R.COMMANDS[k] is R.COMMANDS[k] for k in R.COMMANDS), "run_motion reuses the exact run.py command functions")

    # existing suites and locked hashes
    for script in ("scripts/test_stage2_alignment.py", "studio/tests/test_studio.py"):
        r = subprocess.run([sys.executable, str(ROOT / script)], capture_output=True, text=True,
                           env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        check(r.returncode == 0, f"{script} passes ({tail[0]})")
    want = json.loads((ROOT / "studio" / "CORE_HASHES.json").read_text(encoding="utf-8"))
    check(all(hashlib.sha256((ROOT / k).read_bytes()).hexdigest() == v for k, v in want.items()),
          f"all {len(want)} locked core files match CORE_HASHES.json")


# =========================================================================================== main
PHASES = {"t1": t1, "t2": t2}


def main():
    wanted = sys.argv[1:] or list(PHASES)
    for name in wanted:
        if name not in PHASES:
            sys.exit(f"unknown phase {name}; available: {', '.join(PHASES)}")
        PHASES[name]()
    print(f"\n{COUNT[0]} checks, " + ("ALL CAMERA TESTS PASSED" if not FAILS else f"{len(FAILS)} FAILED"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
