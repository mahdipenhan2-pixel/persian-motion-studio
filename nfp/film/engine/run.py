#!/usr/bin/env python3
"""NFP Film runner (16:9, 1920x1080, 30 fps).

  python3 nfp/film/engine/run.py <command> --project <dir or project.json> [--chapter <id>] [--build <dir>]

Commands: plan, check, tts, voice, fit, prepare, whisper, align, subs, compose, verify
  subs   (S1) subtitle cues + readability QC from timing.json -> <build>/subtitles.json (data only: what is drawn on
         the video, words.json, timing.json and lip sync are not changed); (S2) then SRT / VTT / ASS made from that
         file -> <build>/subtitles/subtitles.<lang>.{srt,vtt,ass} (the old <build>/story.srt is a separate file)
  voice  (V4, only for projects with voice.engine) makes the sentence audio with the Voice Engine (nfp/voice) instead of
         the core's single-voice tts; such projects refuse `tts`. Legacy projects never load the Voice Engine.
The locked Stage 2 core does audio, Whisper and alignment (imported unchanged); compose / verify here are 16:9.
Derived from docu/engine/run.py (docu-16x9-test30, see PROVENANCE.json); changes: projects are folders anywhere
(nfp/film has no project store of its own), --build, Whisper language = project language, characters (cast_plan.py)."""
import argparse
import json
import os
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent.parent.parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "nfp"))

import project as P  # noqa: E402
import story_stage2 as core  # noqa: E402  (locked core, imported unchanged)


def setup(path, cid, build=None):
    try:
        proj = P.load(path)
        ch = P.chapter(proj, cid)
    except P.ProjectError as e:
        sys.exit(f"ERROR: {e}")
    build = Path(build) if build else ROOT / "build" / "film" / proj["_name"] / ch["id"]
    build.mkdir(parents=True, exist_ok=True)
    (build / "script.json").write_text(json.dumps(P.core_script(proj, ch), ensure_ascii=False, indent=2), encoding="utf-8")
    (build / "config.json").write_text(json.dumps(P.core_config(proj, ch), ensure_ascii=False, indent=2), encoding="utf-8")
    core.BUILD, core.SCRIPT_PATH, core.CONFIG_PATH = build, build / "script.json", build / "config.json"
    return proj, ch, build


def cmd_plan(proj, ch, build):
    n = sum(len(c["sentences"]) for c in proj["chapters"])
    print(f"Project {proj['meta']['title']} [{proj['meta']['lang']}] - {len(proj['chapters'])} chapter(s), {n} sentences, "
          f"target {proj['meta'].get('target_duration')} s")
    for c in proj["chapters"]:
        print(f"  {c['id']}: {len(c['sentences'])} sentences, {sum(len(s['text']) for s in c['sentences'])} chars")


def cmd_fit(proj, ch, build):
    """After TTS: will the narration fit the target? (audio is cached, so editing text is cheap)."""
    meta = json.loads((build / "tts_meta.json").read_text(encoding="utf-8"))
    cfg = json.loads((build / "config.json").read_text(encoding="utf-8"))
    a = cfg["audio"]
    speech = sum(s["duration"] for s in meta["sentences"])
    total = a["lead_in_ms"] / 1000 + speech + a["gap_ms"] / 1000 * (len(meta["sentences"]) - 1) + a["tail_ms"] / 1000
    target = P.chapter_target(proj, ch)
    print(f"Narration {speech:.1f}s speech, {total:.1f}s with gaps (target {target})")
    if target and total > float(target):
        sys.exit(f"ERROR: narration is {total:.1f}s but the target is {target}s. Shorten the text; cached sentences cost nothing to re-run.")


def uses_voice_engine(proj):
    v = proj.get("voice") or {}
    return isinstance(v, dict) and "engine" in v        # plain check: legacy projects import nothing new


def cmd_tts(proj, ch, build):
    if uses_voice_engine(proj):
        sys.exit("ERROR: this project uses the Voice Engine (voice.engine): run `voice` instead of `tts` "
                 "(the core's single-voice tts would replace the per-speaker audio)")
    core.cmd_tts(None)


def cmd_voice(proj, ch, build):
    if not uses_voice_engine(proj):
        sys.exit("ERROR: `voice` needs voice.engine in project.json; this project uses the core's `tts`")
    import voice_bridge as VB
    m = VB.produce(proj, ch, build)
    c = m.get("cache") or {}
    print(f"Voice Engine: {len(m['sentences'])} sentence(s), speakers {sorted(m['speakers'])}, {m['sample_rate']} Hz"
          + (f", cache {c.get('hits', 0)} hit(s) / {c.get('misses', 0)} miss(es)" if c else "")
          + (f", QC {m['qc']['summary']}" if "qc" in m else "") + f" -> {build / 'audio'}")


def cmd_subs(proj, ch, build):
    import subtitles as SB
    if not (build / "timing.json").exists():
        sys.exit(f"ERROR: {build / 'timing.json'} is missing - run `align` first")
    try:
        doc = SB.build(proj, ch, core.load_json(build / "timing.json"))
    except SB.SubtitleError as e:
        sys.exit(f"ERROR: {e}")
    path = SB.write(build, doc)
    q = doc["qc"]
    print(f"Subtitles ({doc['mode']}, {doc['lang']}): {q['cues']} cue(s), QC {q['status']} - {q['errors']} error(s), "
          f"{q['warnings']} warning(s), {q['infos']} info -> {path}")
    import subtitle_export as SX
    if q["status"] == "FAIL":
        SX.remove(build / "subtitles")          # no stale SRT / VTT / ASS next to a subtitles.json that failed QC
        sys.exit("ERROR: subtitle QC failed (no SRT / VTT / ASS written): " + "; ".join(
            f"cue {x.get('cue', '-')}: {x['message']}" for x in q["issues"] if x["level"] == "error"))
    try:
        files = SX.export(path, build / "subtitles")
    except SX.ExportError as e:
        sys.exit(f"ERROR: {e}")
    print("Subtitle files: " + ", ".join(str(f) for f in files.values()))


def cmd_whisper(proj, ch, build):
    import stage2_whisper as w
    w.BUILD, w.CONFIG = build, build / "config.json"
    w.main()


def compose_build(proj, ch, build, fonts_dir):
    import compose as C
    import cast_plan as CP
    timing = core.load_json(build / "timing.json")
    kit_extra, frag, report = CP.fragment(proj, ch, timing, build)
    info = C.compose(proj, ch, timing, build, fonts_dir, build / "narration.wav", cast_fragment=frag, kit_extra=kit_extra)
    if report:
        (build / "cast_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return info, report


def cmd_compose(proj, ch, build):
    info, report = compose_build(proj, ch, build, os.environ.get("NFP_FONTS") or ROOT / "assets" / "fonts")
    print(f"Composition: {info}" + (f"; characters: {report['summary']}" if report else ""))


def cmd_verify(proj, ch, build):
    import verify as V
    V.verify(proj, ch, build, mp4_name=os.environ.get("VERIFY_FILE") or "story.mp4", expect=(1920, 1080),
             tag=os.environ.get("VERIFY_TAG") or "")


COMMANDS = {"plan": cmd_plan, "check": lambda p, c, b: core.cmd_check(None), "tts": cmd_tts, "voice": cmd_voice,
            "fit": cmd_fit, "prepare": lambda p, c, b: core.cmd_prepare(None), "whisper": cmd_whisper,
            "align": lambda p, c, b: core.cmd_align(None), "subs": cmd_subs, "compose": cmd_compose, "verify": cmd_verify}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=list(COMMANDS))
    ap.add_argument("--project", required=True)
    ap.add_argument("--chapter")
    ap.add_argument("--build")
    a = ap.parse_args()
    proj, ch, build = setup(a.project, a.chapter, a.build)
    COMMANDS[a.command](proj, ch, build)


if __name__ == "__main__":
    main()
