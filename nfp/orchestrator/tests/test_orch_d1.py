#!/usr/bin/env python3
"""D1 - the step graph (plan.py), no process, no file written:
  legacy (the core's TTS), cast, Voice Engine + subtitles, Gemini enabled, timeline projects each get the right steps in
  the right order, owned by the right engine; every step's needs come earlier; network-capable steps are marked; the
  build folder is run.py's default unless given; a broken project or chapter is refused with Film's own message;
  deterministic and plain JSON.
  python3 nfp/orchestrator/tests/test_orch_d1.py --work <dir outside the repository>
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent.parent)]
import fixture as FX                              # noqa: E402
from orchestrator import plan as PL               # noqa: E402

RESULTS = []
FIX = FX.NFP / "film" / "tests" / "fixtures"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def edit(src, dst, fn):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    p = json.loads((dst / "project.json").read_text(encoding="utf-8"))
    fn(p)
    (dst / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return dst


def names(pl):
    return [s["name"] for s in pl["steps"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    base = ["fit", "prepare", "whisper", "align"]
    tail = ["compose", "smoke", "render", "verify", "output"]

    pl = PL.plan(FIX / "neutral-en")
    st = {s["name"]: s for s in pl["steps"]}
    check(names(pl) == ["audio"] + base + tail and st["audio"]["run"] == ["run.py", "tts"] and st["audio"]["engine"] == "core"
          and st["audio"]["cost"] == "network?", f"legacy project: the core's tts first, no subtitles step: {names(pl)}")
    check(pl["build"] == str(FX.ROOT / "build" / "film" / "neutral-en" / pl["chapter"]), "build folder = run.py's default")
    check(PL.plan(FIX / "neutral-en", build="/x/y")["build"] == "/x/y", "... or the one given")
    pl = PL.plan(FIX / "cast-en")
    check(pl["features"]["cast"] and names(pl)[0] == "audio", "cast project: characters seen, same steps")
    d = FX.voice_project(work, "v", "en")
    pl = PL.plan(d)
    st = {s["name"]: s for s in pl["steps"]}
    check(names(pl) == ["audio"] + base + ["subs"] + tail and st["audio"]["run"] == ["run.py", "voice"] and st["audio"]["engine"] == "voice"
          and st["subs"]["engine"] == "subtitles" and "subs" in st["compose"]["needs"],
          f"Voice Engine + subtitles: voice instead of tts, subs before compose: {names(pl)}")
    cast_dir = json.loads((d / "project.json").read_text(encoding="utf-8"))["cast"]["dir"]
    check(["file", "voices.cast.json"] in st["audio"]["inputs"] and ["dir", cast_dir] in st["audio"]["inputs"] and not any(i[0] == "code" for i in st["audio"]["inputs"]),
          "the audio step depends on the casting and cast files, never on code (a code change must not re-make paid audio)")
    g = edit(d, work / "g", lambda p: p["voice"].update(providers={"gemini": {}}))
    check(PL.plan(g)["features"]["gemini_providers"] and "Gemini" in PL.plan(g)["steps"][0]["why"], "Gemini in voice.providers: marked")
    t = edit(FIX / "neutral-en", work / "t", lambda p: p.update(timeline={"file": "timeline.json"}))
    pl = PL.plan(t)
    check(pl["features"]["timeline"] and ["dir", "."] in {s["name"]: s for s in pl["steps"]}["compose"]["inputs"],
          "timeline project: compose depends on the whole project folder (maps, graphics, assets)")
    for p_ in (FIX / "neutral-en", FIX / "cast-fa", d):
        pl = PL.plan(p_)
        seen, ok = set(), True
        for s in pl["steps"]:
            ok &= set(s["needs"]) <= seen and s["name"] in PL.ORDER
            seen.add(s["name"])
        check(ok and [n for n in PL.ORDER if n in seen] == names(pl), f"{p_.name}: every step's needs come earlier, in the fixed order")
    bad = edit(FIX / "neutral-en", work / "bad", lambda p: p["meta"].update(fps=25))
    try:
        PL.plan(bad)
        check(False, "a broken project is refused")
    except PL.PlanError as e:
        check("1080p30" in str(e) or "fps" in str(e), f"a broken project is refused with Film's own message: {str(e)[:90]}")
    try:
        PL.plan(FIX / "neutral-en", chapter="nope")
        check(False, "an unknown chapter is refused")
    except PL.PlanError as e:
        check(True, f"an unknown chapter is refused: {str(e)[:80]}")
    a1, a2 = PL.plan(d), PL.plan(d)
    check(a1 == a2 and json.loads(json.dumps(a1)) == a1, "deterministic, plain JSON")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR D1 TESTS PASSED" if not f else "ORCHESTRATOR D1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
