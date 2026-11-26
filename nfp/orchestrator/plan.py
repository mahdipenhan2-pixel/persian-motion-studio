"""NFP Production Orchestrator - D1: the step graph of one chapter of one Film project. Standard library; reads the
project with Film's own loader (nfp/film/engine/project.py, unchanged); runs nothing, writes nothing.

  plan(project, chapter=None, build=None) -> nfp.orchestrator.plan/1:
     {"project", "chapter", "build", "features": {...}, "steps": [step, ...]}
  step = {"name", "run": ["run.py", <command>] | ["tool", <name>] | ["test-substitute"], "engine": the owner,
          "cost": "light" | "local" | "heavy" | "network?", "needs": [names], "inputs": [spec], "outputs": [build paths],
          "why": text}

The steps are the existing ones - the orchestrator owns only their order, state, cost gate and report:
  audio    run.py voice  (Voice Engine projects: voice.engine)  |  run.py tts  (the core's single-voice Gemini TTS)
  fit      run.py fit      does the narration fit the target (a check; no output)
  prepare  run.py prepare  narration.wav + per-sentence Whisper input (Stage 2 core)
  whisper  run.py whisper  word times with faster-whisper (Stage 2 core; local, heavy; may fetch its model once)
  align    run.py align    timing.json (Stage 2 core)
  subs     run.py subs     subtitles.json + SRT / VTT / ASS (Subtitle Engine; only with a "subtitles" block)
  compose  run.py compose  story/index.html (Film: Character, Timeline, Map Motion, Graphics through their bridges)
  smoke    tool smoke      the composed page in Chromium: page errors, Director warnings, duration (before rendering)
  render   tool render     story.mp4 with the local HyperFrames (offline; local GSAP copy)
  verify   run.py verify   verify.json (Film's own verify.py)
Cost classes: light = file checks; local = local processing; heavy = minutes of local CPU; network? = may call an online
(possibly paid) service - decided at run time (D3): the core's TTS (Gemini), Voice Engine projects whose casting asks
Gemini and whose voice.providers enables it, a HyperFrames that is not in the local cache.
Input specs (hashed by D3 to decide whether a step is up to date):
  ["project", key, ...]  those keys of project.json (+ "chapter": the chapter being built)
  ["file", rel] / ["dir", rel]   project files / folders      ["build", rel]   an earlier step's output
  ["code", rel, ...]     repository code (nfp/... or scripts/...)   ["fonts"] the fonts folder   ["gsap"] the local GSAP
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NFP = HERE.parent
ROOT = NFP.parent
ENGINE = NFP / "film" / "engine"
PLAN_SCHEMA = "nfp.orchestrator.plan/1"
ORDER = ("audio", "fit", "prepare", "whisper", "align", "subs", "compose", "smoke", "render", "verify")
CORE = ["code", "scripts/story_stage2.py"]
RENDER_CODE = ["code", "nfp/film", "nfp/character/runtime", "nfp/character/renderers", "nfp/timeline", "nfp/mapmotion", "nfp/location",
               "nfp/graphics", "nfp/voice", "scripts/story_stage2.py"]


class PlanError(ValueError):
    pass


def _film():
    for p in (str(ENGINE), str(NFP), str(ROOT / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import project as P                     # Film's project loader (unchanged)
    return P


def load(project, chapter=None):
    P = _film()
    try:
        proj = P.load(project)
        ch = P.chapter(proj, chapter)
    except P.ProjectError as e:
        raise PlanError(f"project: {e}") from None
    return proj, ch


def default_build(proj, ch):
    return ROOT / "build" / "film" / proj["_name"] / ch["id"]          # the same default as run.py


def features(proj):
    v = proj.get("voice") or {}
    tl = proj.get("timeline")
    return {"voice_engine": isinstance(v, dict) and "engine" in v, "subtitles": "subtitles" in proj,
            "cast": bool(proj.get("cast") or proj.get("characters")), "timeline": isinstance(tl, dict),
            "gemini_providers": isinstance(v, dict) and "gemini" in (v.get("providers") or {})}


def plan(project, chapter=None, build=None):
    proj, ch = load(project, chapter)
    f = features(proj)
    b = Path(build) if build else default_build(proj, ch)
    steps = []

    def step(name, run, engine, cost, needs, inputs, outputs, why):
        steps.append({"name": name, "run": run, "engine": engine, "cost": cost, "needs": needs, "inputs": inputs,
                      "outputs": outputs, "why": why})

    if f["voice_engine"]:
        cast_dir = (proj.get("cast") or {}).get("dir")
        step("audio", ["run.py", "voice"], "voice", "network?", [],
             [["project", "meta", "voice", "characters", "chapter"], ["file", proj["voice"].get("casting", "voices.cast.json")]]
             + ([["dir", cast_dir]] if cast_dir else []),
             ["audio", "tts_meta.json", "voice"],
             "sentence audio by the Voice Engine (voice.engine)" + ("; Gemini is enabled in voice.providers" if f["gemini_providers"] else ""))
    else:
        step("audio", ["run.py", "tts"], "core", "network?", [], [["project", "meta", "voice", "audio", "chapter"]],
             ["audio", "tts_meta.json"], "sentence audio by the Stage 2 core's single-voice Gemini TTS (cached per sentence)")
    step("fit", ["run.py", "fit"], "film", "light", ["audio"], [["build", "tts_meta.json"], ["project", "meta", "audio", "chapter"]], [],
         "does the narration fit the target duration (a check)")
    step("prepare", ["run.py", "prepare"], "core", "local", ["audio"], [["build", "audio"], ["build", "tts_meta.json"], ["project", "audio"], CORE],
         ["narration.wav", "audio_meta.json", "whisper_in"], "narration.wav and the per-sentence Whisper input")
    step("whisper", ["run.py", "whisper"], "core", "heavy", ["prepare"], [["build", "whisper_in"], ["project", "meta"], ["code", "scripts/stage2_whisper.py"]],
         ["whisper"], "word times with faster-whisper (local; needs the faster_whisper module and its model)")
    step("align", ["run.py", "align"], "core", "local", ["whisper"], [["build", "whisper"], ["build", "audio_meta.json"], ["build", "audio"], CORE],
         ["timing.json", "timing_report.md"], "timing.json: every word's time (the source of truth for everything drawn)")
    if f["subtitles"]:
        step("subs", ["run.py", "subs"], "subtitles", "light", ["align"], [["build", "timing.json"], ["project", "meta", "subtitles", "chapter"],
                                                                           ["code", "nfp/film/engine/subtitles.py", "nfp/film/engine/subtitle_export.py"]],
             ["subtitles.json", "subtitles"], "subtitle cues, QC and SRT / VTT / ASS (Subtitle Engine)")
    step("compose", ["run.py", "compose"], "film", "local", ["align"] + (["subs"] if f["subtitles"] else []),
         [["dir", "."], ["build", "timing.json"], ["build", "narration.wav"]] + ([["build", "subtitles.json"]] if f["subtitles"] else [])
         + [["fonts"], RENDER_CODE],
         ["story", "words.json", "story.srt"], "the Film page (Character, Timeline, Map Motion and Graphics through their bridges)")
    step("smoke", ["tool", "smoke"], "orchestrator", "local", ["compose"], [["build", "story"], ["gsap"]], ["smoke.json"],
         "the composed page in Chromium before rendering: page errors, Director warnings, timeline length")
    step("render", ["tool", "render"], "film", "heavy", ["smoke"], [["build", "story"], ["gsap"]], ["story.mp4"],
         "story.mp4 with the local HyperFrames (npm offline; the page's GSAP from the local copy)")
    step("verify", ["run.py", "verify"], "film", "local", ["render"], [["build", "story.mp4"], ["build", "timing.json"], ["code", "nfp/film/engine/verify.py"]],
         ["verify.json"], "Film's own verify.py on the MP4")
    return {"schema": PLAN_SCHEMA, "project": proj["_dir"], "name": proj["_name"], "chapter": ch["id"], "build": str(b),
            "lang": proj["meta"]["lang"], "features": f, "steps": steps}
