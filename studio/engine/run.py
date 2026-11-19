#!/usr/bin/env python3
"""
NFP Studio runner.

  python3 studio/engine/run.py <command> --project <name>

Commands (in pipeline order): plan, check, tts, prepare, whisper, align, compose, verify

The locked Stage 2 core (scripts/story_stage2.py, scripts/stage2_whisper.py) does all the heavy lifting:
Gemini TTS with content-addressed cache, Whisper word timing, Persian-safe alignment, verification.
This runner only points it at a per-project build folder and generated script/config.
Nothing in scripts/ or story/ is modified.
"""
import argparse
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent.parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ROOT / "scripts"))

import project as P  # noqa: E402
import story_stage2 as core  # noqa: E402  (locked core)
import compose as C  # noqa: E402


def setup(name):
    try:
        proj = P.load(name)
        theme = P.load_theme(proj["meta"]["theme"])
    except P.ProjectError as e:
        sys.exit(f"ERROR: {e}")
    build = ROOT / "build" / "studio" / proj["_name"]
    build.mkdir(parents=True, exist_ok=True)
    (build / "script.json").write_text(json.dumps(P.core_script(proj), ensure_ascii=False, indent=2), encoding="utf-8")
    (build / "config.json").write_text(json.dumps(P.core_config(proj), ensure_ascii=False, indent=2), encoding="utf-8")
    # The core reads these module-level paths at call time.
    core.BUILD = build
    core.SCRIPT_PATH = build / "script.json"
    core.CONFIG_PATH = build / "config.json"
    core.SEA = tuple(theme["highlight_rgb"])  # colour the verify step looks for
    return proj, theme, build


def cmd_plan(proj, theme, build):
    sents = P.sentences(proj)
    print(f"Project: {proj['meta']['title']}  [{proj['meta']['lang']}, {proj['meta']['format']}, theme {proj['meta']['theme']}]")
    print(f"{len(proj['scenes'])} scenes, {len(sents)} sentences (each new sentence = 1 TTS request on a cold cache)")
    for sc in proj["scenes"]:
        ss = [s for s in sents if s["id"].startswith(sc["id"] + "_")]
        print(f"  {sc['id']:>4}  {sc['template']:<8} {len(ss)} sentence(s)")


def cmd_compose(proj, theme, build):
    timing = core.load_json(build / "timing.json")
    info = C.compose(proj, theme, timing, build, ROOT / "assets" / "fonts", build / "narration.wav")
    print(f"Composition written: {info['duration']:.2f}s, {info['scenes']} scenes, {info['sentences']} sentences, fade {info['fade']}s")


def cmd_whisper(proj, theme, build):
    import stage2_whisper as w  # imported here: only the whisper virtualenv step needs faster-whisper
    w.BUILD = build
    w.CONFIG = build / "config.json"
    w.main()


COMMANDS = {
    "plan": lambda p, t, b: cmd_plan(p, t, b),
    "check": lambda p, t, b: core.cmd_check(None),
    "tts": lambda p, t, b: core.cmd_tts(None),
    "prepare": lambda p, t, b: core.cmd_prepare(None),
    "whisper": cmd_whisper,
    "align": lambda p, t, b: core.cmd_align(None),
    "compose": cmd_compose,
    "verify": lambda p, t, b: core.cmd_verify(None),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=list(COMMANDS))
    ap.add_argument("--project", required=True, help="folder name under studio/projects (or a path to project.json)")
    a = ap.parse_args()
    proj, theme, build = setup(a.project)
    COMMANDS[a.command](proj, theme, build)


if __name__ == "__main__":
    main()
