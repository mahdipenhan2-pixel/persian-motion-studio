#!/usr/bin/env python3
"""
NFP Studio runner WITH the Camera Motion Engine AND the character layer (C4).

  python3 studio/engine/run_cast.py <command> --project <name>

Commands: plan, cast-check, camera-check, check, tts, prepare, whisper, align, compose, verify

Everything except "compose", "plan" and "cast-check" is the unchanged run.py command (locked Stage 2 core).
"compose" runs exactly run_motion.py's compose (unchanged compose.py + camera engine) and then, only if the project
uses characters (meta.cast / scene.characters), adds them with studio/engine/characters. A project without
character fields gets byte-for-byte the same files as run_motion.py.
"""
import argparse
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent.parent
sys.path.insert(0, str(ENGINE))

import run as R  # noqa: E402  (unchanged)
import run_motion as RM  # noqa: E402  (unchanged)
import project as P  # noqa: E402  (unchanged)
from camera import inject as CI  # noqa: E402  (unchanged, read-only use)
from characters import build as CB  # noqa: E402
from characters import inject as CJ  # noqa: E402
from characters import schema as CS  # noqa: E402
from characters.schema import CastError  # noqa: E402


def cast_plan(proj, pdir):
    try:
        return CS.validate(proj, pdir, [s["id"] for s in P.sentences(proj)])
    except CastError as e:
        sys.exit(f"ERROR (characters): {e}")


def compose_with_cast(proj, theme, build, fonts_dir, narration_wav, pdir):
    """run_motion's compose, then characters when the project asks for them. Returns (info, compiled, report)."""
    plan = cast_plan(proj, pdir)                                  # validate before writing anything
    info, compiled = RM.compose_with_camera(proj, theme, build, fonts_dir, narration_wav, pdir)
    if plan is None:
        return info, compiled, None
    try:
        CJ.check_anchor_files()
        story = Path(build) / "story"
        page = (story / "index.html").read_text(encoding="utf-8")
        timing = json.loads((Path(build) / "timing.json").read_text(encoding="utf-8"))
        data = CI.read_timeline_data(page)
        kl, doc, report = CB.build_keylist(plan, data, timing, pdir)
        page = CJ.apply(page, kl, plan["slot"], report["deco_hidden"])
    except CastError as e:
        sys.exit(f"ERROR (characters): {e}")
    (story / "index.html").write_text(page, encoding="utf-8")
    (Path(build) / "cast_keylist.json").write_text(json.dumps(kl, ensure_ascii=False, sort_keys=True, indent=1),
                                                   encoding="utf-8")
    (Path(build) / "cast_actions.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(build) / "cast_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return info, compiled, report


def print_cast(plan):
    if plan is None:
        print("Characters: none (output is identical to run_motion.py)")
        return
    print(f"Characters ({plan['format']}, bottom slot {plan['slot']}):")
    for aid, a in plan["actors"].items():
        pl = a["placement"]
        print(f"  {aid:<10} {a['character']}/{a['stage']}/{a['wardrobe']}  {pl['framing']} scale {pl['scale']} "
              f"x {pl['x']} face {pl['face_px']}px  fp {a['fingerprint'][:12]}")
    for p in plan["scenes"]:
        if p:
            spk = ", ".join(f"{k}:{v}" for k, v in p["speakers"].items())
            print(f"  {p['scene']:>4}  on screen: {', '.join(p['present'])}  speakers: {spk}  actions: {len(p['actions'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=list(R.COMMANDS) + ["camera-check", "cast-check"])
    ap.add_argument("--project", required=True, help="folder name under studio/projects (or a path to project.json)")
    a = ap.parse_args()
    pdir = RM.project_dir(a.project)
    if a.command in ("camera-check", "cast-check"):          # offline, writes nothing
        try:
            proj = P.load(a.project)
        except P.ProjectError as e:
            sys.exit(f"ERROR: {e}")
        if a.command == "camera-check":
            RM.print_camera(RM.camera_plan(proj, pdir))
        else:
            print_cast(cast_plan(proj, pdir))
        return
    proj, theme, build = R.setup(a.project)
    if a.command == "plan":
        R.cmd_plan(proj, theme, build)
        RM.print_camera(RM.camera_plan(proj, pdir))
        print_cast(cast_plan(proj, pdir))
    elif a.command == "compose":
        info, compiled, report = compose_with_cast(proj, theme, build, ROOT / "assets" / "fonts", build / "narration.wav", pdir)
        print(f"Composition written: {info['duration']:.2f}s, {info['scenes']} scenes, {info['sentences']} sentences, fade {info['fade']}s")
        if compiled is not None:
            print(f"Camera: {len(compiled['tweens'])} tweens added (timeline duration stays {compiled['duration']:.3f}s)")
        if report is not None:
            print(f"Characters: {len(report['actors'])} actor(s), {report['keys']} keys, speakers "
                  f"{sorted(set(report['speakers'].values()))}, KeyList {report['digest'][:16]}")
    else:
        R.COMMANDS[a.command](proj, theme, build)


if __name__ == "__main__":
    main()
