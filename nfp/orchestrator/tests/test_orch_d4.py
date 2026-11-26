#!/usr/bin/env python3
"""D4 - smoke, a REAL render and verify through the runner (offline): a Voice-Engine project (synthetic voices = test
tones; whisper = TEST-ONLY substitute) in English and Persian runs every step to a real MP4:
  smoke: the page in Chromium, 0 page errors, timeline length = words.json, outside requests refused;
  render: HyperFrames 0.9.83 from the local npx cache with npm offline -> story.mp4 (ffprobe: 1920x1080 30 fps h264 + aac,
          the page's length); the product page story/index.html still has its CDN tag (only the render copy changed);
  verify: Film's verify.py on the MP4 -> verify.json (its problems, if any, are listed: the report classifies them);
  a second run renders nothing again; a page error is caught by smoke BEFORE rendering (render not tried);
  no local GSAP -> smoke and render blocked with that reason; nothing written into the repository.
  The Persian fixture's s3 starts exactly on a half frame (9.35 s = frame 280.5): the case this test found failing at
  smoke before cast_plan.snap rounded halves up like the Director (see nfp/film/tests/film_cast_halfframe_check.py);
  it is rendered unchanged.
  python3 nfp/orchestrator/tests/test_orch_d4.py --fonts <woff2 dir> --gsap <gsap.min.js> --work <dir outside the repository> [--langs en,fa]
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent.parent)]
import fixture as FX                              # noqa: E402
from orchestrator import plan as PL               # noqa: E402
from orchestrator import runner as RN             # noqa: E402
from orchestrator.tools import render as R        # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    for k in ("--fonts", "--gsap", "--work"):
        ap.add_argument(k, required=True)
    ap.add_argument("--langs", default="en,fa")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if FX.ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fonts, gsap = str(Path(a.fonts).resolve()), str(Path(a.gsap).resolve())
    before = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    W = {"whisper": FX.whisper_executor}
    say = lambda m: print("     " + m, flush=True)                 # noqa: E731

    projects = {}
    for lang in a.langs.split(","):
        print(f"\n== {lang}: every step to a real MP4")
        v = FX.voice_project(work, f"film-{lang}", lang)
        projects[lang] = v
        b = work / f"b-{lang}"
        pl = PL.plan(v, build=str(b))
        st = RN.run(pl, fonts=fonts, gsap=gsap, executors=W, say=say)
        steps = st["steps"]
        check(st["status"] in ("complete", "complete_with_problems") and all(steps[s["name"]]["status"] in ("done", "problems") for s in pl["steps"]),
              f"{lang}: all {len(pl['steps'])} steps ran: {st['status']}")
        sm = json.loads((b / "smoke.json").read_text(encoding="utf-8")) if (b / "smoke.json").exists() else {}
        if lang == "fa":
            s3 = next(x for x in json.loads((b / "timing.json").read_text(encoding="utf-8"))["sentences"] if x["id"] == "s3")
            check(s3["offset"] == 9.35, "fa: s3 starts on a half frame (9.35 s = frame 280.5) - the case smoke stopped before the fix")
        check(sm.get("ok") and not sm["page_errors"] and abs(sm["timeline_seconds"] - sm["expected_seconds"]) <= 0.05,
              f"{lang} smoke: {steps.get('smoke', {}).get('detail')}")
        mp4 = b / "story.mp4"
        pr = R.ffprobe(mp4) if mp4.exists() else {}
        check(pr and (pr["width"], pr["height"], pr["fps"], pr["video_codec"], pr["audio_codec"]) == (1920, 1080, "30/1", "h264", "aac")
              and abs(pr["seconds"] - sm.get("expected_seconds", 0)) < 0.1,
              f"{lang} REAL MP4 (HyperFrames {R.HF_VERSION}, offline): {steps.get('render', {}).get('detail')}")
        page = (b / "story" / "index.html").read_text(encoding="utf-8")
        check(page.count(R.CDN) == 1 and R.LOCAL in (b / "render-copy" / "index.html").read_text(encoding="utf-8"),
              f"{lang}: the product page keeps its CDN tag; only the render copy uses the local GSAP")
        vj = json.loads((b / "verify.json").read_text(encoding="utf-8")) if (b / "verify.json").exists() else None
        check(vj is not None and steps.get("verify", {}).get("status") == ("problems" if vj["problems"] else "done"),
              f"{lang} verify.py on the MP4: {steps.get('verify', {}).get('status')}; problems {vj['problems'] if vj else '-'}")
        t = (b / "story.mp4").stat().st_mtime_ns
        st = RN.run(pl, fonts=fonts, gsap=gsap, executors=W, say=lambda *_: None)
        check(st["runs"][-1]["ran"] == [] and (b / "story.mp4").stat().st_mtime_ns == t, f"{lang}: second run - nothing again, the MP4 untouched")

    print("\n== smoke stops a broken page before rendering")
    lang = a.langs.split(",")[0]
    v, b = projects[lang], work / f"b-{lang}"
    pl = PL.plan(v, build=str(b))
    p = b / "story" / "index.html"
    good = p.read_text(encoding="utf-8")
    p.write_text(good.replace("</body>", "<script>throw new Error('deliberate page error')</script></body>", 1), encoding="utf-8")
    t = (b / "story.mp4").stat().st_mtime_ns
    st = RN.run(pl, fonts=fonts, gsap=gsap, executors=W, say=lambda *_: None)
    check(st["status"] == "failed" and st["runs"][-1]["stopped_at"] == "smoke" and "page error" in st["steps"]["smoke"]["detail"]
          and "render" not in st["runs"][-1]["ran"] and (b / "story.mp4").stat().st_mtime_ns == t,
          f"a page error: smoke FAILED ({st['steps']['smoke']['detail'][:80]}), render not tried")
    st = RN.run(pl, fonts=fonts, gsap=gsap, executors=W, say=lambda *_: None, start="compose")
    check(st["status"] in ("complete", "complete_with_problems") and st["runs"][-1]["ran"][:2] == ["compose", "smoke"],
          f"--from compose: the page is composed again and the run completes: ran {st['runs'][-1]['ran']}")

    print("\n== no local GSAP")
    st = RN.run(PL.plan(v, build=str(work / "b-nogsap")), fonts=fonts, gsap=None, executors=W, say=lambda *_: None)
    check(st["status"] == "blocked" and st["runs"][-1]["stopped_at"] == "smoke" and "gsap" in st["steps"]["smoke"]["reason"],
          f"blocked at smoke: {st['steps']['smoke']['reason'][:100]}")
    after = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    check(before == after, "nothing written into the repository (git status unchanged, also ignored files)")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR D4 TESTS PASSED" if not f else "ORCHESTRATOR D4 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
