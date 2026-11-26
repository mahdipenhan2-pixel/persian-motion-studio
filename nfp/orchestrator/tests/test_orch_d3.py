#!/usr/bin/env python3
"""D3 - the runner: real step processes, the production state, Resume and the Cost Guard (offline; synthetic voices):
  a Voice-Engine project runs audio -> ... -> compose (whisper = TEST-ONLY substitute, recorded as such);
  a second run re-runs nothing (outputs untouched); a run that failed at a step resumes there, earlier steps untouched;
  a changed subtitle setting re-runs only subs and compose; --from re-runs that step and later ones; --force all;
  the Cost Guard blocks the core's Gemini TTS and a Gemini voice without --allow-network (nothing run, nothing sent,
  no cache created) and strips the API key / forces offline flags from every step's process; a missing faster-whisper
  blocks the real whisper step with that reason; the CLI's exit codes; nothing written into the repository.
  python3 nfp/orchestrator/tests/test_orch_d3.py --fonts <woff2 dir> --gsap <gsap.min.js> --work <dir outside the repository>
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent.parent)]
import fixture as FX                              # noqa: E402
from orchestrator import plan as PL               # noqa: E402
from orchestrator import preflight as PF          # noqa: E402
from orchestrator import runner as RN             # noqa: E402
from orchestrator import state as S               # noqa: E402

RESULTS = []
FIX = FX.NFP / "film" / "tests" / "fixtures"
CLI = HERE.parent / "cli.py"
CHAIN = ["audio", "fit", "prepare", "whisper", "align", "subs", "compose"]


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def jedit(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def mtimes(b, names):
    return {n: (b / n).stat().st_mtime_ns for n in names if (b / n).exists()}


def main():
    ap = argparse.ArgumentParser()
    for k in ("--fonts", "--gsap", "--work"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if FX.ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fonts, gsap = str(Path(a.fonts).resolve()), str(Path(a.gsap).resolve())
    before = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    quiet = lambda *_: None                                         # noqa: E731
    W = {"whisper": FX.whisper_executor}

    def go(p, b, fonts_=None, **kw):
        return RN.run(PL.plan(p, build=str(b)), fonts=fonts_ or fonts, gsap=gsap, say=quiet, **kw)

    print("== a full chain to compose, then Resume")
    v = FX.voice_project(work, "voice", "en")
    b = work / "b-voice"
    st = go(v, b, until="compose", executors=W)
    run = st["runs"][-1]
    check(st["status"] == "partial" and run["ran"] == CHAIN and all(st["steps"][n]["status"] == "done" for n in CHAIN)
          and (b / "story" / "index.html").exists() and (b / "production.json").exists(),
          f"audio -> compose ran as 7 processes / executors, state in production.json: {run['ran']}")
    check(st["steps"]["whisper"]["executor"].startswith("TEST-ONLY") and st["steps"]["audio"]["executor"] == "run.py voice",
          f"the substitute is recorded as such: whisper = {st['steps']['whisper']['executor'][:40]}...; audio = {st['steps']['audio']['executor']}")
    check(all((b / "orchestrator" / "logs" / f"{n}.log").exists() for n in CHAIN), "one log per step")
    outs = ["narration.wav", "timing.json", "subtitles.json", "story/index.html", "voice/voice_manifest.json"]
    m0 = mtimes(b, outs)
    st = go(v, b, until="compose", executors=W)
    run = st["runs"][-1]
    check(run["ran"] == [] and run["up_to_date"] == CHAIN and mtimes(b, outs) == m0, "second run: every step up to date, no output touched")

    def broken(step, ctx):
        raise RuntimeError("simulated crash of the whisper step")
    r = work / "b-resume"
    st = go(v, r, until="compose", executors={"whisper": broken})
    check(st["status"] == "failed" and st["runs"][-1]["stopped_at"] == "whisper" and "align" not in st["steps"]
          and st["steps"]["whisper"]["status"] == "failed", "a crash at whisper: the run stops there, later steps not tried")
    m1 = mtimes(r, ["narration.wav", "audio_meta.json", "tts_meta.json"])
    st = go(v, r, until="compose", executors=W)
    run = st["runs"][-1]
    check(st["status"] == "partial" and run["up_to_date"] == ["audio", "fit", "prepare"] and run["ran"] == CHAIN[3:]
          and mtimes(r, ["narration.wav", "audio_meta.json", "tts_meta.json"]) == m1,
          f"Resume: audio / fit / prepare left alone, ran {run['ran']}")

    jedit(v / "project.json", lambda d: d["subtitles"].update(mode="word"))
    st = go(v, b, until="compose", executors=W)
    run = st["runs"][-1]
    check(run["ran"] == ["subs", "compose"] and run["up_to_date"] == CHAIN[:5], f"a subtitle setting changed: only {run['ran']} ran again")
    st = go(v, b, until="compose", executors=W, start="align")
    check(st["runs"][-1]["ran"] == ["align", "subs", "compose"], f"--from align: {st['runs'][-1]['ran']}")
    st = go(v, b, until="fit", executors=W, force=True)
    check(st["runs"][-1]["ran"] == ["audio", "fit"] and st["status"] == "partial", "--force --until fit: audio and fit again, then stop")
    st = go(v, b, until="compose", executors=W)
    check(st["runs"][-1]["ran"] == ["prepare"] and st["runs"][-1]["up_to_date"] == ["audio", "fit"] + CHAIN[3:],
          "re-made audio: only prepare runs (tts_meta.json now says cache_hit: true); its outputs are byte-identical, so "
          f"whisper -> compose stay up to date: ran {st['runs'][-1]['ran']}")

    print("\n== which inputs make a step run again")
    jedit(v / "voices.cast.json", lambda c: c["narrator"].update(voice="synthetic:female"))
    st = go(v, b, until="compose", executors=W)
    check(st["runs"][-1]["ran"] == CHAIN, f"the casting file changed (narrator voice): audio and everything after it again: {st['runs'][-1]['ran']}")
    f2 = work / "fonts-copy"
    shutil.copytree(fonts, f2)
    st = go(v, b, fonts_=str(f2), until="compose", executors=W)
    check(st["runs"][-1]["ran"] == [], "the same fonts in another folder: nothing again (contents are fingerprinted, not paths)")
    first = sorted(f2.glob("*.woff2"))[0]
    shutil.copyfile(first, f2 / ("extra-" + first.name))
    st = go(v, b, fonts_=str(f2), until="compose", executors=W)
    check(st["runs"][-1]["ran"] == ["compose"], f"a font added: only compose again: {st['runs'][-1]['ran']}")
    pl = PL.plan(v, build=str(b))
    steps = {x["name"]: x for x in pl["steps"]}
    code = work / "code.py"
    code.write_text("x = 1\n")
    fake = {"inputs": [["code", str(code)]]}
    h1 = S.fingerprint(fake, pl)
    code.write_text("x = 2\n")
    check(S.fingerprint(fake, pl) != h1 and any(i[0] == "code" and "nfp/film" in i for i in steps["compose"]["inputs"])
          and not any(i[0] == "code" for i in steps["audio"]["inputs"]),
          "a code change changes the fingerprint of the steps that name that code (compose names nfp/film; audio names no code)")

    print("\n== Cost Guard")
    cache = FX.ROOT / ".cache"
    had_cache = cache.exists()
    lb = work / "b-legacy"
    st = go(FIX / "neutral-en", lb)
    check(st["status"] == "blocked" and st["runs"][-1]["ran"] == [] and "cost guard" in st["steps"]["audio"]["reason"]
          and not (lb / "audio").exists() and cache.exists() == had_cache,
          f"legacy project (core Gemini TTS): blocked before anything ran: {st['steps']['audio']['reason'][:110]}")
    g = work / "gem"
    shutil.copytree(v, g)
    jedit(g / "voices.cast.json", lambda c: c["narrator"].update(voice="gemini:Charon"))
    jedit(g / "project.json", lambda d: d["voice"].update(providers={"gemini": {}}))
    st = go(g, work / "b-gem")
    check(st["status"] == "blocked" and st["runs"][-1]["ran"] == [] and "Gemini" in st["steps"]["audio"]["reason"],
          f"a Gemini voice without --allow-network: blocked: {st['steps']['audio']['reason'][:100]}")
    keep = PF.hyperframes_offline
    PF.hyperframes_offline = lambda: (False, "SIMULATED: the cache probe is replaced in this check")
    try:
        st = go(v, b, fonts_=str(f2), executors=W)
    finally:
        PF.hyperframes_offline = keep
    check(st["status"] == "blocked" and st["runs"][-1]["stopped_at"] == "render" and "cost guard" in st["steps"]["render"]["reason"]
          and "HyperFrames" in st["steps"]["render"]["reason"] and st["steps"]["smoke"]["status"] == "done" and not (b / "story.mp4").exists(),
          f"HyperFrames not in the npx cache (simulated probe): render blocked, never downloaded: {st['steps']['render']['reason'][:90]}")
    os.environ["GEMINI_API_KEY"] = "dummy-not-a-key"                   # only to see that it is stripped
    e0, e1 = RN.step_env(fonts, False), RN.step_env(fonts, True)
    del os.environ["GEMINI_API_KEY"]
    check("GEMINI_API_KEY" not in e0 and e0["HF_HUB_OFFLINE"] == "1" and e0["npm_config_offline"] == "true" and e1.get("GEMINI_API_KEY") == "dummy-not-a-key",
          "without --allow-network every step's process gets no API key and offline flags (with it: the key is passed)")

    print("\n== environment")
    wb = work / "b-whisper"
    st = go(v, wb, until="align")
    fw = importlib.util.find_spec("faster_whisper") is not None
    if fw:
        check(st["steps"]["whisper"]["status"] in ("done", "failed"), "faster-whisper installed: the real whisper step ran offline")
    else:
        check(st["status"] == "blocked" and st["runs"][-1]["ran"] == ["audio", "fit", "prepare"] and "faster_whisper" in st["steps"]["whisper"]["reason"],
              f"faster-whisper missing: the REAL whisper step is blocked, not faked: {st['steps']['whisper']['reason'][:90]}")

    print("\n== CLI")
    env = dict(FX.CLEAN_ENV, PYTHONDONTWRITEBYTECODE="1")
    c = subprocess.run([sys.executable, "-B", str(CLI), "run", "--project", str(FIX / "neutral-en"), "--build", str(lb), "--fonts", fonts, "--gsap", gsap],
                       capture_output=True, text=True, env=env)
    check(c.returncode == 2 and "BLOCKED" in c.stdout, f"cli run on a blocked step: exit 2 ({c.stdout.strip().splitlines()[-1]})")
    c = subprocess.run([sys.executable, "-B", str(CLI), "status", "--project", str(v), "--build", str(b)], capture_output=True, text=True, env=env)
    check(c.returncode == 0 and "compose  done" in c.stdout and "TEST-ONLY" in c.stdout, "cli status lists each step with its executor")
    c = subprocess.run([sys.executable, "-B", str(CLI), "run", "--project", str(v), "--build", str(b), "--until", "nope"], capture_output=True, text=True, env=env)
    check(c.returncode == 3, "cli run --until <unknown>: exit 3")
    after = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    check(before == after, "nothing written into the repository (git status unchanged, also ignored files)")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR D3 TESTS PASSED" if not f else "ORCHESTRATOR D3 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
