#!/usr/bin/env python3
"""D2 - preflight: every engine's documents checked with that engine's own checks, before anything costly:
  clean projects (legacy core TTS, synthetic Voice Engine, a timeline with a map, graphics and an image) -> OK;
  one deliberate fault per engine -> FAIL with an issue of THAT engine (film, character, voice, subtitles, timeline,
  mapmotion, graphics); the cost forecast: the core's TTS requests (sentences not in its cache), the Voice Engine's
  Gemini requests (only when voice.providers enables Gemini; refused when it does not), 0 for synthetic voices;
  the environment (faster_whisper, gsap, HyperFrames offline ...) is reported apart from the project's status;
  preflight sends nothing and writes nothing into the repository.
  python3 nfp/orchestrator/tests/test_orch_d2.py --fonts <woff2 dir> --gsap <gsap.min.js> --work <dir outside the repository>
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
from orchestrator import preflight as PF          # noqa: E402

RESULTS = []
FIX = FX.NFP / "film" / "tests" / "fixtures"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def jedit(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def copy(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


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
    fonts, gsap = Path(a.fonts).resolve(), Path(a.gsap).resolve()
    before = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout

    def pf(p, **kw):
        return PF.preflight(PL.plan(p, build=str(work / "build")), fonts=kw.get("fonts", fonts), gsap=kw.get("gsap", gsap))

    def engines(r, level="error"):
        return {(i["engine"], i["code"]) for i in r["issues"] if i["level"] == level}

    print("== clean projects")
    r = pf(FIX / "neutral-en")
    check(r["status"] == "OK" and r["cost"]["gemini_requests"] == 3 and "audio" in r["cost"]["network"],
          f"legacy (core TTS): OK; 3 TTS requests forecast (no sentence cached): {r['cost']['network'].get('audio')}")
    v = FX.voice_project(work, "voice", "en")
    r = pf(v)
    check(r["status"] == "OK" and r["cost"]["gemini_requests"] == 0 and set(r["cost"]["network"]) <= {"whisper"},
          "synthetic Voice Engine project: OK, nothing online (with faster-whisper installed, only its possible model download is "
          f"listed; the runner runs that step offline): {sorted(r['cost']['network'])}")
    sys.path.insert(0, str(FX.NFP / "graphics" / "tests"))
    import test_graphics_g5_film as T5
    T5.make_image(work / "wide.png", 3200, 1800)
    t = T5.project(work, "tl", gclips=T5.GCLIPS[:4], video=False)
    r = pf(t)
    check(r["status"] == "OK" and ("mapmotion", "at_compose") in engines(r, "info"),
          f"timeline with an image, a map and 4 graphics: OK (map window / labels: checked at compose) {sorted(engines(r))}")

    print("\n== one fault per engine -> that engine")
    faults = []
    p = copy(FIX / "neutral-en", work / "f-film")
    (p / "shots.js").unlink()
    faults.append(("film", p, ("film", "shots_missing")))
    p = copy(FIX / "cast-en", work / "f-char")
    cd = json.loads((p / "project.json").read_text(encoding="utf-8"))["cast"]["dir"]
    jedit(p / cd / "cast.json", lambda c: c["characters"][0]["identity"].update(hair="#123456") if "hair" in c["characters"][0].get("identity", {})
          else c["characters"][0]["identity"].update(skin="#123456"))
    faults.append(("character (identity changed, lock not)", p, ("character", "cast")))
    p = copy(FIX / "cast-en", work / "f-char2")
    jedit(p / "project.json", lambda d: d["characters"][0].update(character="nobody"))
    faults.append(("character (unknown character)", p, ("character", "unknown_character")))
    p = copy(v, work / "f-voice")
    jedit(p / "voices.cast.json", lambda c: c["narrator"].update(voice="gemini:Charon"))
    faults.append(("voice (Gemini voice, Gemini not enabled)", p, ("voice", "gemini_disabled")))
    p = copy(v, work / "f-subs")
    jedit(p / "project.json", lambda d: d.update(subtitles={"mode": "teletype"}))
    try:                                    # Film's loader hands the block to the Subtitle Engine itself: refused at plan
        PL.plan(p)
        check(False, "subtitles: an invalid mode is refused")
    except PL.PlanError as e:
        check("subtitles.mode" in str(e), f"subtitles: refused already by Film's loader (Subtitle Engine's own check): {e}")
    p = copy(t, work / "f-tl")
    jedit(p / "timeline.json", lambda d: d["clips"].append({"id": "bad", "track": "pictures", "kind": "image", "start": 400, "end": 300, "asset": "wide"}))
    faults.append(("timeline", p, ("timeline", None)))
    p = copy(t, work / "f-map")
    jedit(p / "maps" / "film.map.json", lambda d: d["points"][0].update(location="nowhere"))
    faults.append(("mapmotion", p, ("mapmotion", None)))
    p = copy(t, work / "f-gfx")
    jedit(p / "timeline.json", lambda d: [c.update(track="pictures", start=380, end=440) for c in d["clips"] if c["id"] == "g-lt"])
    faults.append(("graphics (a lower third on a visual track)", p, ("graphics", "graphic")))
    for name, p, (eng, code) in faults:
        r = pf(p)
        got = engines(r)
        hit = any(e == eng and (code is None or c == code) for e, c in got)
        check(r["status"] == "FAIL" and hit, f"{name}: FAIL, reported by {eng} {sorted(got)[:3]}")
    p = copy(v, work / "f-gem")
    jedit(p / "voices.cast.json", lambda c: c["narrator"].update(voice="gemini:Charon"))
    jedit(p / "project.json", lambda d: d["voice"].update(providers={"gemini": {}}))
    r = pf(p)
    check(r["status"] == "OK" and r["cost"]["gemini_requests"] == 1 and "audio" in r["cost"]["network"],
          f"Gemini enabled for the narrator: 1 request forecast (the narrator's sentence) - no request sent: {r['cost']['network'].get('audio')}")

    print("\n== environment apart from the project")
    r = pf(FIX / "neutral-en", gsap=None, fonts=work / "no-fonts")
    env = r["environment"]
    check(r["status"] in ("OK", "WARN") and not env["gsap"]["ok"] and env["gsap"]["needed_by"] == ["smoke", "render"] and not env["fonts"]["ok"],
          "no GSAP copy / fonts: environment gaps naming the steps that need them; the project itself stays valid")
    check("faster_whisper" in env and env["faster_whisper"]["needed_by"] == ["whisper"],
          f"faster-whisper reported for the whisper step (here: {'installed' if env['faster_whisper']['ok'] else 'NOT installed'})")
    after = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    check(before == after, "preflight wrote nothing into the repository (git status unchanged, also ignored files)")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR D2 TESTS PASSED" if not f else "ORCHESTRATOR D2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
