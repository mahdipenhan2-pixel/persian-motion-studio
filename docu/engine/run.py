#!/usr/bin/env python3
"""Documentary runner (16:9, 1920x1080, 30 fps).

  python3 docu/engine/run.py <command> --project <name> [--chapter <id>]

Commands: plan, check, tts, fit, prepare, whisper, align, compose, verify
The locked Stage 2 core does audio/Whisper/alignment (audio only); compose/verify here are 16:9.
Nothing in scripts/ is modified."""
import argparse
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent.parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ROOT / "scripts"))

import project as P  # noqa: E402
import story_stage2 as core  # noqa: E402  (locked core, imported unchanged)


def setup(name, cid):
    try:
        proj = P.load(name)
        ch = P.chapter(proj, cid)
    except P.ProjectError as e:
        sys.exit(f"ERROR: {e}")
    build = ROOT / "build" / "docu" / proj["_name"] / ch["id"]
    build.mkdir(parents=True, exist_ok=True)
    (build / "script.json").write_text(json.dumps(P.core_script(proj, ch), ensure_ascii=False, indent=2), encoding="utf-8")
    (build / "config.json").write_text(json.dumps(P.core_config(proj, ch), ensure_ascii=False, indent=2), encoding="utf-8")
    core.BUILD, core.SCRIPT_PATH, core.CONFIG_PATH = build, build / "script.json", build / "config.json"
    return proj, ch, build


def cmd_plan(proj, ch, build):
    n = sum(len(c["sentences"]) for c in proj["chapters"])
    print(f"Project {proj['meta']['title']} - {len(proj['chapters'])} chapter(s), {n} sentences, target {proj['meta'].get('target_duration')} s")
    for c in proj["chapters"]:
        print(f"  {c['id']}: {len(c['sentences'])} sentences, {sum(len(s['text']) for s in c['sentences'])} chars")


def cmd_fit(proj, ch, build):
    """After TTS: will the narration fit the target? Fails early with a clear message (audio is cached, so editing text is cheap)."""
    meta = json.loads((build / "tts_meta.json").read_text(encoding="utf-8"))
    cfg = json.loads((build / "config.json").read_text(encoding="utf-8"))
    a = cfg["audio"]
    speech = sum(s["duration"] for s in meta["sentences"])
    total = a["lead_in_ms"] / 1000 + speech + a["gap_ms"] / 1000 * (len(meta["sentences"]) - 1) + a["tail_ms"] / 1000
    target = proj["meta"].get("target_duration")
    print(f"Narration {speech:.1f}s speech, {total:.1f}s with gaps (target {target})")
    if target and total > float(target):
        sys.exit(f"ERROR: narration is {total:.1f}s but the target is {target}s. Shorten the text; cached sentences cost nothing to re-run.")


def cmd_whisper(proj, ch, build):
    import stage2_whisper as w
    w.BUILD, w.CONFIG = build, build / "config.json"
    w.main()


def cmd_compose(proj, ch, build):
    import compose as C
    timing = core.load_json(build / "timing.json")
    info = C.compose(proj, ch, timing, build, ROOT / "assets" / "fonts", build / "narration.wav", local=False)
    print(f"Composition: {info}")


def cmd_verify(proj, ch, build):
    import os
    import verify as V
    # VERIFY_FILE / VERIFY_SIZE / VERIFY_TAG let the workflow check the master AND the delivered 720p file with the same code
    V.verify(proj, ch, build, mp4_name=os.environ.get("VERIFY_FILE") or "story.mp4",
             expect=V.parse_size(os.environ.get("VERIFY_SIZE"), (1920, 1080)), tag=os.environ.get("VERIFY_TAG") or "")


COMMANDS = {"plan": cmd_plan, "check": lambda p, c, b: core.cmd_check(None), "tts": lambda p, c, b: core.cmd_tts(None),
            "fit": cmd_fit, "prepare": lambda p, c, b: core.cmd_prepare(None), "whisper": cmd_whisper,
            "align": lambda p, c, b: core.cmd_align(None), "compose": cmd_compose, "verify": cmd_verify}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=list(COMMANDS))
    ap.add_argument("--project", required=True)
    ap.add_argument("--chapter")
    a = ap.parse_args()
    proj, ch, build = setup(a.project, a.chapter)
    COMMANDS[a.command](proj, ch, build)


if __name__ == "__main__":
    main()
