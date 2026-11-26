#!/usr/bin/env python3
"""D0 - the process-model experiment the orchestrator is built on (no orchestrator code yet):
  every existing step of nfp/film/engine/run.py runs as its OWN process, one after another, on a real Voice-Engine
  project (synthetic voices: test tones, offline), in English and Persian, with subtitles:
      voice -> fit -> prepare -> [whisper: TEST-ONLY substitute, see fixture.py] -> align -> subs -> compose
  each step succeeds from the files the previous one left, and its outputs are where run.py writes them; the core's
  module-level state never crosses steps (separate processes).
  Also states the environment's facts (INFO, not pass / fail): faster-whisper, a TTS key, node, ffmpeg, HyperFrames in
  the local npx cache (offline).
  python3 nfp/orchestrator/tests/test_orch_d0.py --fonts <woff2 dir> --work <dir outside the repository>
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixture as FX                              # noqa: E402

RESULTS = []
RUN = FX.NFP / "film" / "engine" / "run.py"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def info(msg):
    print("INFO " + msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if FX.ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print("== environment (facts, not results)")
    info(f"faster-whisper importable: {importlib.util.find_spec('faster_whisper') is not None}")
    info(f"GEMINI_API_KEY set: {bool(os.environ.get('GEMINI_API_KEY'))}")
    info(f"node: {shutil.which('node') is not None}; ffmpeg: {shutil.which('ffmpeg') is not None}; ffprobe: {shutil.which('ffprobe') is not None}")
    r = subprocess.run(["npx", "--yes", "hyperframes@0.9.83", "--version"], capture_output=True, text=True, cwd="/tmp",
                       env=dict(os.environ, npm_config_offline="true"), timeout=180)
    info(f"HyperFrames 0.9.83 from the local npx cache with npm offline: {r.returncode == 0} {r.stdout.strip()[-20:]}")

    for lang in ("en", "fa"):
        print(f"\n== {lang}: run.py steps as separate processes")
        d = FX.voice_project(work, f"d0-{lang}", lang)
        b = work / f"b-{lang}"
        env = dict(FX.CLEAN_ENV, NFP_FONTS=str(Path(a.fonts).resolve()))
        steps = ["voice", "fit", "prepare", "whisper*", "align", "subs", "compose"]
        outs = {"voice": ["audio", "tts_meta.json", "voice/voice_manifest.json"], "fit": [], "prepare": ["narration.wav", "audio_meta.json", "whisper_in"],
                "whisper*": ["whisper"], "align": ["timing.json"], "subs": ["subtitles.json", "subtitles"], "compose": ["story/index.html", "words.json"]}
        ok_all = True
        for st in steps:
            if st == "whisper*":
                msg = FX.whisper_substitute(b)
                rc, tail = 0, msg
            else:
                p = subprocess.run([sys.executable, "-B", str(RUN), st, "--project", str(d), "--build", str(b)], capture_output=True, text=True, env=env)
                rc, tail = p.returncode, (p.stdout + p.stderr).strip().splitlines()[-1:] if (p.stdout + p.stderr).strip() else []
            missing = [o for o in outs[st] if not (b / o).exists()]
            ok = rc == 0 and not missing
            ok_all &= ok
            check(ok, f"{lang} {st:9s}: exit {rc}, outputs {'present' if not missing else 'MISSING ' + str(missing)} {tail}")
            if not ok:
                break
        check(ok_all, f"{lang}: the whole chain ran step by step in separate processes (whisper = TEST-ONLY substitute)")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR D0 TESTS PASSED" if not f else "ORCHESTRATOR D0 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
