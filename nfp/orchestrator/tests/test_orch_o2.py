#!/usr/bin/env python3
"""O2 - the output step (nfp/output/check.py through tools/output.py) in the Production Orchestrator, offline (synthetic
voices = test tones; whisper = the TEST-ONLY substitute):
  karaoke, sentence, word, off and an old project without subtitles run all 11 steps; the output step is done, the
  report shows the output QC; sentence / word / off: verify.py's caption-highlight problems are "not applicable" (with
  the mode's reason), karaoke / old project: never; the verdict is PASS_WITH_KNOWN_LIMITATIONS everywhere;
  a second run runs nothing; an old build (no output step yet) runs only the output step;
  stale results are never used: a changed project setting (subtitles) makes the output QC not current - nothing is
  reclassified - and restoring the exact setting makes it current again; a run after a real change re-makes it;
  a real MP4 defect (pixel format) -> output "problems", run complete_with_problems, report FAIL, render still done;
  a 400 ms sync slip -> WARNING only, verdict unchanged; an output check that crashes -> that step failed, render done,
  report INCOMPLETE (not FAIL); with an earlier result still current, that result is used and the failure noted;
  the MP4 and verify.json are not changed by the output step; nothing written into the repository.
  python3 nfp/orchestrator/tests/test_orch_o2.py --fonts <woff2 dir> --gsap <gsap.min.js> --work <dir outside the repository>
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
from output import check as OC                    # noqa: E402

RESULTS = []
ALL = ["audio", "fit", "prepare", "whisper", "align", "subs", "compose", "smoke", "render", "verify", "output"]


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


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
    git0 = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    W = {"whisper": FX.whisper_executor}
    quiet = lambda *_: None                                         # noqa: E731

    def go(p, b, **kw):
        return RN.run(PL.plan(p, build=str(b)), fonts=fonts, gsap=gsap, executors=dict(W, **kw.pop("ex", {})), say=quiet, **kw)

    def rep(b):
        return json.loads((Path(b) / "production_report.json").read_text(encoding="utf-8"))

    print("== all 11 steps, every subtitle mode and an old project")
    B = {}
    for key, mode in (("karaoke", "karaoke"), ("sentence", "sentence"), ("word", "word"), ("off", "off"), ("legacy", None)):
        v = FX.voice_project(work, f"p-{key}", "en", subtitles=mode is not None)
        if mode:
            pj = json.loads((v / "project.json").read_text(encoding="utf-8"))
            pj["subtitles"] = {"mode": mode}
            (v / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
        b = work / f"b-{key}"
        st = go(v, b)
        B[key] = (v, b)
        r = rep(b)
        na = r["verify"]["not_applicable"]
        o = r["output"]
        names = [x["step"] for x in r["production"]["steps"]]
        ok = (names == [n for n in ALL if n != "subs" or mode] and st["steps"]["output"]["status"] == "done" and st["steps"]["render"]["status"] == "done"
              and o["current"] and o["status"] == "OK" and r["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS" and not r["verify"]["new_problems"])
        if key in ("sentence", "word", "off"):
            ok &= len(na) == 3 and all(f"'{mode}'" in x["reason"] for x in na)
        else:
            ok &= na == []
        check(ok, f"{key}: {len(names)} steps, output {st['steps']['output']['status']} ({o['status']}), {len(na)} not applicable, "
                  f"known {[x['id'] for x in r['verify']['known_limitations']]}, verdict {r['verdict']}")
        q = json.loads((b / "output_qc.json").read_text(encoding="utf-8"))
        check(q["inputs"]["mp4_sha256"] == sha(b / "story.mp4") and q["inputs"]["verify_json_sha256"] == sha(b / "verify.json")
              and q["inputs"]["settings"]["subtitle_mode"] == (mode or "legacy"),
              f"{key}: output_qc.json records the files it checked (sha256, unchanged now) and the mode {q['inputs']['settings']}")
    v, b = B["karaoke"]
    st = go(v, b)
    check(st["runs"][-1]["ran"] == [], "a second run runs nothing (output up to date)")

    print("\n== an old build (made before the output step existed)")
    v, b = B["word"]
    s = json.loads((b / "production.json").read_text(encoding="utf-8"))
    s["steps"].pop("output")
    (b / "production.json").write_text(json.dumps(s), encoding="utf-8")
    (b / "output_qc.json").unlink()
    r0 = RP.report(PL.plan(v, build=str(b)), write=False)
    st = go(v, b)
    check(r0["verdict"] == "INCOMPLETE" and len(r0["verify"]["pending_output_qc"]) == 3 and st["runs"][-1]["ran"] == ["output"] and rep(b)["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS",
          f"without an output QC the report says INCOMPLETE ({r0['reasons'][-1][:60]}); the next run runs only {st['runs'][-1]['ran']}")

    print("\n== stale results are never used")
    v, b = B["sentence"]
    pj_text = (v / "project.json").read_text(encoding="utf-8")
    pj = json.loads(pj_text)
    pj["subtitles"]["mode"] = "karaoke"
    (v / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    r = RP.report(PL.plan(v, build=str(b)), write=False)
    check(not r["output"]["current"] and "project settings" in r["output"]["why"] and r["verify"]["not_applicable"] == []
          and len([x for x in r["verify"]["new_problems"] if "caption highlight" in x["problem"]]) == 3,
          f"subtitles.mode changed after the check: output QC not current ({r['output']['why'][:70]}), nothing reclassified -> {r['verdict']}")
    pj["subtitles"] = {"mode": "sentence", "max_lines": 1}
    (v / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    r = RP.report(PL.plan(v, build=str(b)), write=False)
    check(not r["output"]["current"] and r["verify"]["not_applicable"] == [], "another subtitle setting (max_lines) changed: also not current")
    (v / "project.json").write_text(pj_text, encoding="utf-8")
    r = RP.report(PL.plan(v, build=str(b)), write=False)
    check(r["output"]["current"] and len(r["verify"]["not_applicable"]) == 3, "the exact setting restored: current again (contents, not times)")
    vj = b / "verify.json"
    keep = vj.read_text(encoding="utf-8")
    vj.write_text(keep.replace('"problems": [', '"problems": ["wrong fps 25.00", ', 1), encoding="utf-8")
    r = RP.report(PL.plan(v, build=str(b)), write=False)
    check(not r["output"]["current"] and "verify.json" in r["output"]["why"] and r["verdict"] == "FAIL",
          f"verify.json changed after the check: not current; the new verify problem fails the report: {r['reasons'][:2]}")
    vj.write_text(keep, encoding="utf-8")

    print("\n== a real MP4 defect, a sync slip")
    v, b = B["karaoke"]
    mp4 = b / "story.mp4"
    good = work / "good.mp4"
    shutil.copyfile(mp4, good)
    ff("-i", good, "-c:v", "libx264", "-pix_fmt", "yuv444p", "-preset", "ultrafast", "-c:a", "copy", "-movflags", "+faststart", mp4)
    st = go(v, b)
    r = rep(b)
    check(st["runs"][-1]["ran"] == ["verify", "output"] and st["steps"]["output"]["status"] == "problems" and st["status"] == "complete_with_problems"
          and st["steps"]["render"]["status"] == "done" and r["verdict"] == "FAIL" and any(x.startswith("output QC") and "pix_fmt" in x for x in r["reasons"]),
          f"pixel format defect: verify + output re-run, output 'problems', render still done, verdict {r['verdict']}: {[x[:60] for x in r['reasons']]}")
    t = json.loads((b / "timing.json").read_text(encoding="utf-8"))
    gap = round((t["sentences"][0]["offset"] + t["sentences"][0]["duration"] + t["sentences"][1]["words"][0]["abs_start"]) / 2, 3)
    ff("-i", good, "-filter_complex", f"[0:a]atrim=0:{gap},asetpts=PTS-STARTPTS[a0];[0:a]atrim={gap},asetpts=PTS-STARTPTS,adelay=400:all=1[a1];"
       "[a0][a1]concat=n=2:v=0:a=1,atrim=0:20[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", mp4)
    st = go(v, b)
    r = rep(b)
    w = [x for x in r["output"]["warnings"] if x["code"] == "sentence_offset"]
    check(st["steps"]["output"]["status"] == "done" and r["output"]["status"] == "WARN" and len(w) == 2 and r["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS",
          f"400 ms sync slip from s2: {len(w)} WARNING(s) only, verdict {r['verdict']} (offsets {r['output']['sync']['offsets_ms']})")
    shutil.copyfile(good, mp4)
    st = go(v, b)
    check(st["runs"][-1]["ran"] == ["verify", "output"] and rep(b)["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS", "the good MP4 back: verify + output again, PASS again")

    print("\n== an output check that crashes")

    def crash(step, ctx):
        raise RuntimeError("simulated crash of the output check")
    v, b = B["off"]
    h_mp4, h_vj = sha(b / "story.mp4"), sha(b / "verify.json")
    st = go(v, b, start="output", ex={"output": crash})
    r = rep(b)
    check(st["steps"]["output"]["status"] == "failed" and st["steps"]["render"]["status"] == "done" and r["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS"
          and r["output"]["current"] and any("last output step failed" in n for n in r["notes"]),
          f"crash, an earlier result still current: that result is used, the failure noted; render done; verdict {r['verdict']}")
    (b / "output_qc.json").unlink()
    st = go(v, b, start="output", ex={"output": crash})
    r = rep(b)
    check(st["status"] == "failed" and st["steps"]["render"]["status"] == "done" and r["verdict"] == "INCOMPLETE"
          and not any("failed step" in x for x in r["reasons"]) and any(x.startswith("output QC") for x in r["reasons"])
          and len(r["verify"]["pending_output_qc"]) == 3 and not r["verify"]["new_problems"],
          f"crash, no result: render still done, verdict {r['verdict']} (not FAIL): {[x[:70] for x in r['reasons']]}")
    st = go(v, b)
    check(st["runs"][-1]["ran"] == ["output"] and rep(b)["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS", "the next run: only output again, PASS again")
    check(sha(b / "story.mp4") == h_mp4 and sha(b / "verify.json") == h_vj, "the output step and the report changed neither story.mp4 nor verify.json")
    git1 = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    check(git0 == git1, "nothing written into the repository (git status unchanged, also ignored files)")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR O2 TESTS PASSED" if not f else "ORCHESTRATOR O2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
