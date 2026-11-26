#!/usr/bin/env python3
"""D5 - the integrated QC report (report.py), offline:
  a real run to MP4 (synthetic voices; whisper = TEST-ONLY substitute) ends with production_report.json / .md written
  by the runner: verify.py's "long near-static stretches" is a KNOWN limitation (with its source and what to look at),
  nothing new -> PASS_WITH_KNOWN_LIMITATIONS, yet production_ready = NO (the substitute and the test tones are named);
  classification on copies of that build's verify.json: a new problem fails it, the T4 highlight limitation does not,
  no problem -> PASS; the readiness rule itself (no substitute, real voices -> ready) on an edited copy (a rule check,
  labelled so - not a real production);
  a blocked run -> BLOCKED with the cost guard's reason; a smoke failure -> FAIL with the page error;
  a timeline build composed outside the orchestrator -> the Graphics and Map Motion QC are collected, INCOMPLETE;
  the report reads the engines' files only (all unchanged); the CLI's report exit codes; nothing in the repository.
  python3 nfp/orchestrator/tests/test_orch_d5.py --fonts <woff2 dir> --gsap <gsap.min.js> --work <dir outside the repository>
"""
import argparse
import hashlib
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
from orchestrator import report as RP             # noqa: E402
from orchestrator import runner as RN             # noqa: E402
from output import check as OC                    # noqa: E402  (O2: an edited copy gets its own current output QC)

RESULTS = []
FIX = FX.NFP / "film" / "tests" / "fixtures"
CLI = HERE.parent / "cli.py"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def jedit(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def digest(b, skip=("production_report.json", "production_report.md")):
    return {str(p.relative_to(b)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(b.rglob("*")) if p.is_file() and p.name not in skip}


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
    W = {"whisper": FX.whisper_executor}
    quiet = lambda *_: None                                         # noqa: E731
    env = dict(FX.CLEAN_ENV, PYTHONDONTWRITEBYTECODE="1")

    print("== a real run to MP4 -> the report")
    v = FX.voice_project(work, "film-en", "en")
    b = work / "b-en"
    pl = PL.plan(v, build=str(b))
    RN.run(pl, fonts=fonts, gsap=gsap, executors=W, say=quiet)
    rep = json.loads((b / "production_report.json").read_text(encoding="utf-8")) if (b / "production_report.json").exists() else {}
    md = (b / "production_report.md").read_text(encoding="utf-8") if (b / "production_report.md").exists() else ""
    vk = (rep.get("verify") or {}).get("known_limitations", [])
    check(rep.get("verdict") == "PASS_WITH_KNOWN_LIMITATIONS" and [x["id"] for x in vk] == ["verify.near_static"] and not rep["verify"]["new_problems"]
          and vk[0]["source"] and vk[0]["look_at"],
          f"written by the runner: {rep.get('verdict')}; known: {[x['problem'][:60] for x in vk]}")
    check(rep.get("production_ready") is False and any(s.startswith("whisper: TEST-ONLY") for s in rep["substitutes"])
          and any("synthetic" in s for s in rep["substitutes"]) and "NOT A PRODUCTION BUILD" in md,
          f"production_ready: NO - {rep.get('substitutes')}")
    check(set(rep.get("engines", {})) >= {"voice", "subtitles", "character"} and rep["render"]["ffprobe"]["width"] == 1920 and rep["smoke"]["ok"],
          f"one report: preflight, steps, {sorted(rep.get('engines', {}))}, smoke, render (ffprobe), verify")

    print("\n== classification (copies of that build's verify.json)")
    d0 = digest(b)

    def variant(name, problems, edit=None):
        c = work / name
        shutil.copytree(b, c)
        jedit(c / "verify.json", lambda d: d.update(problems=problems))
        if edit:
            edit(c)
        OC.check(c, pl["project"], pl["chapter"])         # the copy's verify.json changed: its output QC is made again
        return RP.report(dict(pl, build=str(c)), fonts=fonts, gsap=gsap, write=False)
    r = variant("c-new", ["wrong fps 25.00", "s3: caption highlight too large for the first word (153 px, expected about 76)",
                          "s1: caption highlight is not visible (reference word shows 0 px)"])
    check(r["verdict"] == "FAIL" and [x["problem"] for x in r["verify"]["new_problems"]]
          == ["wrong fps 25.00", "s1: caption highlight is not visible (reference word shows 0 px)"]
          and [x["id"] for x in r["verify"]["known_limitations"]] == ["verify.highlight_first_word"],
          "new problems (wrong fps, an invisible highlight) fail it; only the documented T4 highlight problem is classed as known")
    r = variant("c-none", [])
    check(r["verdict"] == "PASS" and not r["production_ready"], "no problem -> PASS (still not production-ready: substitutes)")

    def real(c):                                                    # rule check only: the documents are edited, nothing is real
        jedit(c / "production.json", lambda d: d["steps"]["whisper"].update(executor="run.py whisper"))
        jedit(c / "voice" / "voice_manifest.json", lambda d: d.update(synthetic=False))
    r = variant("c-rule", [], real)
    check(r["verdict"] == "PASS" and r["production_ready"] and not r["substitutes"],
          "readiness rule (edited copy, NOT a real production): no substitute, no test tones -> production_ready")
    check(digest(b) == d0, "the report changed none of the engines' files")

    print("\n== blocked and failed runs")
    lb = work / "b-legacy"
    RN.run(PL.plan(FIX / "neutral-en", build=str(lb)), fonts=fonts, gsap=gsap, say=quiet)
    r = json.loads((lb / "production_report.json").read_text(encoding="utf-8"))
    check(r["verdict"] == "BLOCKED" and "cost guard" in " ".join(r["reasons"]) and r["preflight"]["cost"]["network"].get("audio"),
          f"legacy project without --allow-network: BLOCKED - {r['reasons'][0][:100]}")
    c = subprocess.run([sys.executable, "-B", str(CLI), "report", "--project", str(FIX / "neutral-en"), "--build", str(lb)], capture_output=True, text=True, env=env)
    check(c.returncode == 1 and "verdict: BLOCKED" in c.stdout, "cli report on it: exit 1, verdict printed")
    c = subprocess.run([sys.executable, "-B", str(CLI), "report", "--project", str(v), "--build", str(b)], capture_output=True, text=True, env=env)
    check(c.returncode == 0 and "PASS_WITH_KNOWN_LIMITATIONS" in c.stdout and "look at:" in c.stdout, "cli report on the MP4 build: exit 0")
    h = FX.voice_project(work, "broken-fa", "fa")
    hb = work / "b-broken-fa"
    hp = PL.plan(h, build=str(hb))
    RN.run(hp, fonts=fonts, gsap=gsap, executors=W, until="compose", say=quiet)
    pg = hb / "story" / "index.html"
    pg.write_text(pg.read_text(encoding="utf-8").replace("</body>", "<script>throw new Error('deliberate page error')</script></body>", 1), encoding="utf-8")
    RN.run(hp, fonts=fonts, gsap=gsap, executors=W, say=quiet)
    r = json.loads((hb / "production_report.json").read_text(encoding="utf-8"))
    check(r["verdict"] == "FAIL" and any(x.startswith("smoke:") and "deliberate page error" in x for x in r["reasons"]) and r["verify"] is None,
          f"a smoke failure: FAIL - {[x[:90] for x in r['reasons']]}")

    print("\n== a timeline build (composed outside the orchestrator)")
    sys.path.insert(0, str(FX.NFP / "graphics" / "tests"))
    import test_graphics_g5_film as T5
    T5.make_image(work / "wide.png", 3200, 1800)
    t = T5.project(work, "tl", gclips=T5.GCLIPS[:4], video=False)
    tb = work / "b-tl"
    res = T5.try_compose(t, tb, Path(fonts))
    r = RP.report(PL.plan(t, build=str(tb)), fonts=fonts, gsap=gsap)
    check(res == "composed" and r["verdict"] == "INCOMPLETE" and r["production"]["state"].startswith("none")
          and len(r["engines"].get("graphics", {}).get("clips", [])) == 4 and len(r["engines"].get("mapmotion", {}).get("clips", [])) == 1,
          f"graphics QC ({len(r['engines'].get('graphics', {}).get('clips', []))} clips) and map QC collected; {r['verdict']}: {r['reasons']}")
    after = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    check(before == after, "nothing written into the repository (git status unchanged, also ignored files)")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR D5 TESTS PASSED" if not f else "ORCHESTRATOR D5 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
