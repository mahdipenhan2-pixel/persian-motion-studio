#!/usr/bin/env python3
"""
NFP Studio runner WITH the Camera Motion Engine.

  python3 studio/engine/run_motion.py <command> --project <name>

Commands: plan, camera-check, check, tts, prepare, whisper, align, compose, verify

Everything except "compose" (and the camera lines of "plan") is the unchanged run.py command, which drives the locked
Stage 2 core. "compose" first runs the unchanged compose.py and then, only if the project uses camera fields,
adds motion with studio/engine/camera. A project without camera fields gets exactly the same files as run.py.
"""
import argparse
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent.parent
sys.path.insert(0, str(ENGINE))

import run as R  # noqa: E402  (unchanged Studio runner; also sets up the import path of the locked core)
import compose as C  # noqa: E402  (unchanged)
import project as P  # noqa: E402  (unchanged)
from camera import inject as I  # noqa: E402
from camera import media as M  # noqa: E402
from camera import schema as SC  # noqa: E402
from camera.presets import CameraError  # noqa: E402


def project_dir(name_or_path):
    p = Path(name_or_path)
    return p.parent if p.suffix else P.PROJECTS / name_or_path


def camera_plan(proj, pdir):
    try:
        return SC.validate(proj, pdir)
    except CameraError as e:
        sys.exit(f"ERROR (camera): {e}")


def compose_with_camera(proj, theme, build, fonts_dir, narration_wav, pdir):
    """compose.py output, then camera motion when the project asks for it. Returns (info, compiled or None)."""
    plan = camera_plan(proj, pdir)                       # validate before writing anything
    timing = json.loads((Path(build) / "timing.json").read_text(encoding="utf-8"))
    info = C.compose(proj, theme, timing, build, fonts_dir, narration_wav)
    if plan is None:
        return info, None
    try:
        I.check_anchor_files()
        story = Path(build) / "story"
        page = (story / "index.html").read_text(encoding="utf-8")
        srcs = M.copy_media(plan, story)
        page, compiled = I.apply(page, plan, theme, srcs)
    except CameraError as e:
        sys.exit(f"ERROR (camera): {e}")
    (story / "index.html").write_text(page, encoding="utf-8")
    (Path(build) / "camera_plan.json").write_text(json.dumps(compiled["report"], ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    return info, compiled


def print_camera(plan):
    if plan is None:
        print("Camera: no camera fields (output is identical to run.py)")
        return
    print("Camera plan:")
    for s in plan["scenes"]:
        mv = s["move"]
        m = s["media"]
        desc = "-" if mv is None else f"{mv['move']} on {mv['target']} (intensity {mv['intensity']}, speed {mv['speed']}, {mv['ease']})"
        tr = s["transition"]["kind"] if s["transition"] else "fade"
        print(f"  {s['id']:>4}  move: {desc:<58} media: {m['src'] + ' [' + m['frame'] + ']' if m else '-':<34} in: {tr}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=list(R.COMMANDS) + ["camera-check"])
    ap.add_argument("--project", required=True, help="folder name under studio/projects (or a path to project.json)")
    a = ap.parse_args()
    pdir = project_dir(a.project)
    if a.command == "camera-check":          # offline, writes nothing
        try:
            proj = P.load(a.project)
        except P.ProjectError as e:
            sys.exit(f"ERROR: {e}")
        print_camera(camera_plan(proj, pdir))
        return
    proj, theme, build = R.setup(a.project)
    if a.command == "plan":
        R.cmd_plan(proj, theme, build)
        print_camera(camera_plan(proj, pdir))
    elif a.command == "compose":
        info, compiled = compose_with_camera(proj, theme, build, ROOT / "assets" / "fonts", build / "narration.wav", pdir)
        print(f"Composition written: {info['duration']:.2f}s, {info['scenes']} scenes, {info['sentences']} sentences, fade {info['fade']}s")
        if compiled is not None:
            print(f"Camera: {len(compiled['tweens'])} tweens added (timeline duration stays {compiled['duration']:.3f}s)")
    else:
        R.COMMANDS[a.command](proj, theme, build)


if __name__ == "__main__":
    main()
