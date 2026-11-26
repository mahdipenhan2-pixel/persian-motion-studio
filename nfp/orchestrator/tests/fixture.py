"""Test fixtures of the Production Orchestrator (offline).

  voice_project(work, name, lang, subtitles=True)  a copy of a Film cast fixture that uses the Voice Engine with SYNTHETIC
                                                   voices (test tones, not speech: Voice Engine V1, no network)
  whisper_substitute(build)                        TEST-ONLY stand-in for the `whisper` step: Whisper words written from
                                                   the synthetic word times the Voice Engine records for its test tones
                                                   (the same substitute Film's V4 test uses). faster-whisper is not
                                                   installed in this environment, and a test tone could not be recognised
                                                   anyway: no recognition is performed or claimed.
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
ROOT = NFP.parent
FILM_TESTS = NFP / "film" / "tests"
CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GEMINI_FREE_TIER_CONFIRMED")}


def voice_project(work, name, lang="en", subtitles=True, cache=True):
    if str(FILM_TESTS) not in sys.path:
        sys.path.insert(0, str(FILM_TESTS))
    import film_voice_check as FV
    base = "cast-en" if lang == "en" else "cast-fa"       # their speakers: narrator, omid-room, omid-stage
    d = FV.voice_project(Path(work), base, name, {"narrator": "synthetic:narrator", "lina": "synthetic:female", "omid": "synthetic:male"},
                         {}, {}, cache=cache)
    if subtitles:
        p = json.loads((d / "project.json").read_text(encoding="utf-8"))
        p["subtitles"] = {"mode": "karaoke"}
        (d / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def whisper_substitute(build):
    """TEST-ONLY: see the module doc."""
    if str(FILM_TESTS) not in sys.path:
        sys.path.insert(0, str(FILM_TESTS))
    import film_voice_check as FV
    FV.fake_whisper(Path(build))
    return "whisper substitute (test only): words from the synthetic voice's recorded word times"


def whisper_executor(step, ctx):
    """The runner executor form of whisper_substitute (TEST-ONLY; its label is recorded in production.json)."""
    return True, whisper_substitute(ctx["pl"]["build"]), "TEST-ONLY whisper substitute: no speech recognition was performed\n"


whisper_executor.label = "TEST-ONLY whisper substitute (synthetic word times; no recognition)"
