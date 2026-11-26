#!/usr/bin/env python3
"""Film manifest - several chapters to ONE MP4 (orchestrator/film.py; Film's assemble.py), offline (synthetic voices;
whisper = the TEST-ONLY substitute, recorded as such):
  two chapter projects (English, Persian) - each a normal Film project - run to their own verified MP4, then joined:
  film.mp4 = the sum of the chapters (frames and audio exactly: whole frames per chapter), 1920x1080 30 fps h264 + aac;
  no drift at the join (every sentence's voice onset in the FILM audio = its shifted timing: Output QC sync, <= 30 ms);
  the merged timing has every sentence with "<chapter>.<sentence>" ids at its chapter's offset; film.srt has every
  sentence; Film's verify.py and the Output check ran on film.mp4; film_report.json: the chapters' verdicts + the film's;
  a second run assembles nothing again (film.mp4 untouched); different subtitle settings across chapters are refused;
  a blocked chapter (the core's Gemini TTS without --allow-network) stops the film there: no film.mp4, BLOCKED;
  the CLI: plan --film, run --film exit codes; nothing written into the repository.
  python3 nfp/orchestrator/tests/test_orch_film.py --fonts <woff2 dir> --gsap <gsap.min.js> --work <dir outside the repository>
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
from orchestrator import film as FM               # noqa: E402

RESULTS = []
CLI = HERE.parent / "cli.py"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def probe(mp4):
    p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(mp4)],
                                  capture_output=True, text=True).stdout)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next(s for s in p["streams"] if s["codec_type"] == "audio")
    return v, a, float(p["format"]["duration"])


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
    git0 = subprocess.run(["git", "status", "--porcelain"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    W = {"whisper": FX.whisper_executor}
    quiet = lambda *_: None                                         # noqa: E731

    print("== two chapters -> one film")
    c1 = FX.voice_project(work, "ch1", "fa")
    c2 = FX.voice_project(work, "ch2", "fa")
    pj = json.loads((c2 / "project.json").read_text(encoding="utf-8"))
    pj["chapters"][0]["target_duration"] = 16                        # chapters of different lengths
    (c2 / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    man = work / "film.json"
    man.write_text(json.dumps({"schema": FM.SCHEMA, "title": "test film", "chapters": [{"id": "c1", "project": "projects/ch1"},
                                                                                     {"id": "c2", "project": "projects/ch2"}]}), encoding="utf-8")
    b = work / "build"
    st = FM.run_film(man, build=b, fonts=fonts, gsap=gsap, executors=W, say=quiet)
    out = b / "film"
    rep = json.loads((out / "film_report.json").read_text(encoding="utf-8"))
    check(st["status"] in FM.DONE and (out / "film.mp4").exists() and all(x["status"] in FM.DONE for x in st["chapters"].values()),
          f"both chapters ran to their own MP4, the film was assembled: {st['status']}")
    d1 = json.loads((b / "c1" / "words.json").read_text(encoding="utf-8"))["duration"]
    d2 = json.loads((b / "c2" / "words.json").read_text(encoding="utf-8"))["duration"]
    v, au, dur = probe(out / "film.mp4")
    check(abs(dur - (d1 + d2)) < 0.03 and int(v["nb_read_frames"]) == round((d1 + d2) * 30) and (v["width"], v["height"], v["avg_frame_rate"]) == (1920, 1080, "30/1")
          and v["codec_name"] == "h264" and au["codec_name"] == "aac" and abs(float(au["duration"]) - (d1 + d2)) < 0.03
          and float(v.get("start_time", 0)) == 0 and float(au.get("start_time", 0)) == 0,
          f"film.mp4 = {d1} + {d2} s: {dur:.3f} s, {v['nb_read_frames']} frames, audio {float(au['duration']):.3f} s")
    t = json.loads((out / "timing.json").read_text(encoding="utf-8"))
    ids = [s["id"] for s in t["sentences"]]
    t2 = json.loads((b / "c2" / "timing.json").read_text(encoding="utf-8"))
    check(ids == ["c1.s1", "c1.s2", "c1.s3", "c2.s1", "c2.s2", "c2.s3"] and abs(t["sentences"][3]["offset"] - (d1 + t2["sentences"][0]["offset"])) < 1e-6,
          f"merged timing: {ids}; chapter 2 starts at {d1} s")
    q = json.loads((out / "output_qc.json").read_text(encoding="utf-8"))
    offs = [r.get("offset_ms") for r in q["sync"]["sentences"]]
    check(q["sync"]["measured"] == 6 and all(abs(o) <= 30 for o in offs), f"no drift at the join: voice onsets in the film audio vs timing {offs} ms")
    srt = (out / "film.srt").read_text(encoding="utf-8")
    check(srt.count(" --> ") == 6, "film.srt: all 6 sentences")
    vj = json.loads((out / "verify.json").read_text(encoding="utf-8"))
    check(vj["file_checked"] == "film.mp4" and abs(vj["duration"] - (d1 + d2)) < 0.03 and rep["verify"] and not rep["verify"]["new_problems"],
          f"verify.py on film.mp4: problems {vj['problems']}")
    check(rep["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS" and [x["verdict"] for x in rep["chapters"]] == ["PASS_WITH_KNOWN_LIMITATIONS"] * 2
          and rep["production_ready"] is False and rep["output"]["status"] in ("OK", "WARN"),
          f"film report: {rep['verdict']}, chapters {[x['verdict'] for x in rep['chapters']]}, not production-ready (substitutes)")
    vraw = (out / "verify.json").read_text(encoding="utf-8")
    fst = json.loads((out / "film_state.json").read_text(encoding="utf-8"))
    pls = FM.plans(FM.load(man), b)[1]
    for bad, ok_join in (("black frames at [5.0]", False), ("black frames at [19.8, 20.0]", True)):
        vv = json.loads(vraw)
        vv["problems"] = [bad]
        (out / "verify.json").write_text(json.dumps(vv), encoding="utf-8")
        rr = FM.report(FM.load(man), pls, out, fst, fst["assembled"])
        hit = [x["problem"] for x in rr["verify"]["not_applicable"]] == [bad] if ok_join else [x["problem"] for x in rr["verify"]["new_problems"]] == [bad]
        check(hit, f"'{bad}': {'chapter transition (not applicable)' if ok_join else 'NOT at a join: a new problem'} -> {rr['verdict']}")
    (out / "verify.json").write_text(vraw, encoding="utf-8")
    FM.report(FM.load(man), pls, out, fst, fst["assembled"])
    t0 = (out / "film.mp4").stat().st_mtime_ns
    st = FM.run_film(man, build=b, fonts=fonts, gsap=gsap, executors=W, say=quiet)
    check(st["assembly"] == "up_to_date" and (out / "film.mp4").stat().st_mtime_ns == t0 and all(x["ran"] == [] for x in st["chapters"].values()),
          "a second run: every chapter up to date, the film not assembled again")

    print("\n== refused / stopped")
    pj2 = json.loads((c2 / "project.json").read_text(encoding="utf-8"))
    pj2["subtitles"] = {"mode": "sentence"}
    (c2 / "project.json").write_text(json.dumps(pj2, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        FM.run_film(man, build=b, fonts=fonts, gsap=gsap, executors=W, say=quiet)
        check(False, "different subtitle settings are refused")
    except FM.FilmError as e:
        check("subtitle" in str(e), f"different subtitle settings across chapters are refused: {e}")
    pj2["subtitles"] = {"mode": "karaoke"}
    (c2 / "project.json").write_text(json.dumps(pj2, ensure_ascii=False, indent=1), encoding="utf-8")
    leg = work / "legacy"
    shutil.copytree(FX.NFP / "film" / "tests" / "fixtures" / "neutral-en", leg)
    m2 = work / "film-blocked.json"
    m2.write_text(json.dumps({"schema": FM.SCHEMA, "chapters": [{"id": "a", "project": "legacy"}]}), encoding="utf-8")
    st = FM.run_film(m2, build=work / "b2", fonts=fonts, gsap=gsap, executors=W, say=quiet)
    r2 = json.loads((work / "b2" / "film" / "film_report.json").read_text(encoding="utf-8"))
    check(st["status"] == "blocked" and st["stopped_at"] == "a" and not (work / "b2" / "film" / "film.mp4").exists() and r2["verdict"] == "BLOCKED",
          f"a blocked chapter (Gemini TTS, no --allow-network) stops the film: {r2['verdict']}")

    print("\n== CLI")
    env = dict(FX.CLEAN_ENV, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-B", str(CLI), "plan", "--film", str(man), "--build", str(b)], capture_output=True, text=True, env=env)
    q2 = subprocess.run([sys.executable, "-B", str(CLI), "run", "--film", str(m2), "--build", str(work / "b2"), "--fonts", fonts, "--gsap", gsap],
                        capture_output=True, text=True, env=env)
    check(p.returncode == 0 and "assemble -> verify -> output QC" in p.stdout and q2.returncode == 2, f"cli plan --film exit 0; run --film on a blocked chapter exit {q2.returncode}")
    git1 = subprocess.run(["git", "status", "--porcelain"], cwd=FX.ROOT, capture_output=True, text=True).stdout
    check(git0 == git1, "nothing written into the repository (git status unchanged)")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ORCHESTRATOR FILM TESTS PASSED" if not f else "ORCHESTRATOR FILM TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
