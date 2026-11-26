#!/usr/bin/env python3
"""O1 - nfp/output/check.py, the read-only MP4 quality check (offline):
  real builds made with the Production Orchestrator (synthetic voices = test tones; whisper = its TEST-ONLY substitute)
  in English karaoke, Persian karaoke, sentence, word, off, and an old project without a subtitles block:
    karaoke / old project: verify.py's highlight check still applies (nothing reclassified);
    sentence / word / off: its "caption highlight" problems are not_applicable with the mode's reason, the mode's own
    caption check replaces them and passes; every other verify.py problem stays; the MP4 and verify.json are unchanged
    (sha256 before / after) and output_qc.json is the only file written;
  real errors are not hidden: a highlight problem on karaoke / an old project stays applicable; a sentence project whose
  MP4 has no caption, an off project whose MP4 has the karaoke highlight, fail; a default mode is named as the default;
  defective MP4s (copies, in --work) are each found by name: pixel format, no faststart, short audio, late audio, no
  audio, silent, true peak, very quiet, a 400 ms sync slip from sentence 2 on (and a 100 ms one measured, not failed),
  no pause between sentences (not_measurable - never a guessed number), a missing file; CLI exit codes; nothing in the
  repository.
  python3 nfp/output/tests/test_output_o1.py --gsap <gsap.min.js> --fonts <woff2 dir> --work <dir outside the repository>
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
NFP = HERE.parent.parent
ROOT = NFP.parent
sys.path[:0] = [str(NFP), str(NFP / "orchestrator" / "tests")]
import fixture as FX                              # noqa: E402  (the Orchestrator's test fixture: synthetic voices)
from orchestrator import plan as PL               # noqa: E402
from orchestrator import runner as RN             # noqa: E402
from output import check as OC                    # noqa: E402

RESULTS = []
CLI = NFP / "output" / "check.py"
NEAR_STATIC = "long near-static stretches"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(b):
    return {str(p.relative_to(b)): sha(p) for p in sorted(Path(b).rglob("*")) if p.is_file()}


def codes(r, level="error"):
    return sorted({i["code"] for i in r["issues"] if i["level"] == level})


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fonts, gsap = str(Path(a.fonts).resolve()), str(Path(a.gsap).resolve())
    git0 = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=ROOT, capture_output=True, text=True).stdout

    print("== real builds (Orchestrator, offline, synthetic voices)")
    builds = {}
    for key, lang, mode in (("en-karaoke", "en", "karaoke"), ("fa-karaoke", "fa", "karaoke"), ("en-sentence", "en", "sentence"),
                            ("en-word", "en", "word"), ("en-off", "en", "off"), ("en-legacy", "en", None)):
        v = FX.voice_project(work, key, lang, subtitles=mode is not None)
        if mode:
            pj = json.loads((v / "project.json").read_text(encoding="utf-8"))
            pj["subtitles"] = {"mode": mode}
            (v / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
        b = work / f"b-{key}"
        st = RN.run(PL.plan(v, build=str(b)), fonts=fonts, gsap=gsap, executors={"whisper": FX.whisper_executor}, say=lambda *_: None)
        builds[key] = (v, b)
        check(st["status"] in ("complete", "complete_with_problems") and (b / "story.mp4").exists() and (b / "verify.json").exists(),
              f"{key}: rendered and verified ({st['status']})")

    print("\n== the check on each real build")
    for key, (v, b) in builds.items():
        before = files(b)
        vraw = (b / "verify.json").read_text(encoding="utf-8")
        r = OC.check(b, v)
        after = files(b)
        added = sorted(set(after) - set(before))
        changed = [k for k in before if before[k] != after.get(k)]
        sub = r["subtitles"]
        vp = json.loads(vraw)["problems"]
        hl = [p for p in vp if "caption highlight" in p]
        if key.endswith(("karaoke", "legacy")):
            ok = sub["highlight_check_applies"] and not sub["not_applicable"] and sub["still_applicable"] == vp and sub["mode"] == ("legacy" if key.endswith("legacy") else "karaoke")
            what = f"highlight check applies (mode {sub['mode']}); verify problems kept: {[p[:40] for p in vp]}"
        else:
            rows = sub["replacement"]["sentences"]
            ok = (len(hl) == 3 and [x["problem"] for x in sub["not_applicable"]] == hl and all(sub["mode"] in x["reason"] for x in sub["not_applicable"])
                  and all(NEAR_STATIC in p for p in sub["still_applicable"]) and len(rows) == 3 and not any(x["problem"] for x in rows))
            what = (f"{len(sub['not_applicable'])} highlight problem(s) not applicable (mode '{sub['mode']}'), replaced by '{sub['replacement']['check']}': "
                    + ", ".join(f"{x['sentence']} text {x['text_px']} / hl {x['highlight_px']} px" for x in rows))
        sy = r["sync"]
        check(ok and r["status"] == "OK" and sy["measured"] == 3 and all(abs(x["offset_ms"]) <= 30 for x in sy["sentences"]),
              f"{key}: {r['status']}; {what}; sync {[x['offset_ms'] for x in sy['sentences']]} ms")
        touched = sorted(set(added) | set(changed))            # the Orchestrator's output step (O2) may have written it already
        check(set(touched) <= {"output_qc.json"} and (b / "output_qc.json").exists() and before.get("story.mp4") == after["story.mp4"] and before.get("verify.json") == after["verify.json"]
              and (b / "verify.json").read_text(encoding="utf-8") == vraw,
              f"{key}: story.mp4 and verify.json unchanged (sha256); only output_qc.json written")

    print("\n== real errors are not hidden")
    v, b = builds["en-karaoke"]
    c = work / "c-karaoke-hl"
    shutil.copytree(b, c)
    vj = json.loads((c / "verify.json").read_text(encoding="utf-8"))
    vj["problems"] = ["s3: caption highlight too large for the first word (153 px, expected about 76)"]
    (c / "verify.json").write_text(json.dumps(vj), encoding="utf-8")
    r = OC.check(c, v, write=False)
    check(r["subtitles"]["still_applicable"] == vj["problems"] and not r["subtitles"]["not_applicable"],
          "karaoke: a highlight problem in verify.json stays applicable")
    vl, bl = builds["en-legacy"]
    c = work / "c-legacy-hl"
    shutil.copytree(bl, c)
    (c / "verify.json").write_text(json.dumps(vj), encoding="utf-8")
    r = OC.check(c, vl, write=False)
    check(r["subtitles"]["still_applicable"] == vj["problems"], "old project (no subtitles block): the same problem stays applicable")
    vs, bs = builds["en-sentence"]
    c = work / "c-sentence-nocap"
    shutil.copytree(bs, c)
    shutil.copyfile(builds["en-off"][1] / "story.mp4", c / "story.mp4")
    r = OC.check(c, vs, write=False)
    check(r["status"] == "FAIL" and "sentence_caption" in codes(r), f"sentence project, an MP4 without captions: FAIL {codes(r)}")
    vo, bo = builds["en-off"]
    c = work / "c-off-hl"
    shutil.copytree(bo, c)
    shutil.copyfile(b / "story.mp4", c / "story.mp4")
    r = OC.check(c, vo, write=False)
    check(r["status"] == "FAIL" and "off_caption" in codes(r), f"off project, an MP4 with the karaoke highlight: FAIL {codes(r)}")
    d = work / "default-mode"
    shutil.copytree(vs, d)
    pj = json.loads((d / "project.json").read_text(encoding="utf-8"))
    pj["subtitles"] = {}
    (d / "project.json").write_text(json.dumps(pj), encoding="utf-8")
    r = OC.check(bs, d, write=False)
    check(r["subtitles"]["mode"] == "sentence" and "default" in r["subtitles"]["mode_source"] and len(r["subtitles"]["not_applicable"]) == 3,
          f"a subtitles block without mode: the Subtitle Engine's default is used and named: {r['subtitles']['mode_source']}")
    pj["subtitles"] = {"mode": "teletype"}
    (d / "project.json").write_text(json.dumps(pj), encoding="utf-8")
    try:
        OC.check(bs, d, write=False)
        check(False, "an invalid subtitles.mode is refused")
    except Exception as e:
        check("subtitles.mode" in str(e), f"an invalid subtitles.mode is refused, nothing reclassified: {str(e)[:70]}")
    r = OC.check(bs, None, write=False)
    check(r["subtitles"]["highlight_check_applies"] and r["subtitles"]["still_applicable"] == json.loads((bs / "verify.json").read_text())["problems"],
          "no project given: verify.py's problems are all kept")

    print("\n== defective MP4s (copies in --work)")
    src = b / "story.mp4"
    t = json.loads((b / "timing.json").read_text(encoding="utf-8"))
    s1end = t["sentences"][0]["offset"] + t["sentences"][0]["duration"]
    gap = round((s1end + t["sentences"][1]["words"][0]["abs_start"]) / 2, 3)

    def defect(name, *ffargs, keep_timing=True):
        c = work / f"d-{name}"
        c.mkdir()
        if keep_timing:
            shutil.copyfile(b / "timing.json", c / "timing.json")
        ff(*ffargs, c / "story.mp4") if ffargs else None
        return c, OC.check(c, v, write=False)
    cases = [
        ("pix444", ["-i", src, "-c:v", "libx264", "-pix_fmt", "yuv444p", "-preset", "ultrafast", "-c:a", "copy"], "error", "pix_fmt"),
        ("nofaststart", ["-i", src, "-c", "copy"], "warning", "faststart"),
        ("shortaudio", ["-i", src, "-c:v", "copy", "-af", "atrim=0:15", "-c:a", "aac"], "error", "stream_length"),
        ("lateaudio", ["-i", src, "-itsoffset", "0.5", "-i", src, "-map", "0:v", "-map", "1:a", "-c", "copy"], "error", "stream_start"),
        ("noaudio", ["-i", src, "-an", "-c:v", "copy"], "error", "no_audio"),
        ("silent", ["-i", src, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-t", "20"], "error", "silent"),
        ("hot", ["-i", src, "-c:v", "copy", "-af", "volume=14dB", "-c:a", "aac"], "warning", "true_peak"),
        ("quiet", ["-i", src, "-c:v", "copy", "-af", "volume=-20dB", "-c:a", "aac"], "warning", "quiet"),
    ]
    for name, args, level, code in cases:
        c, r = defect(name, *args)
        lv = codes(r, level)
        check(code in lv, f"{name}: {level} {code} found {codes(r)} {codes(r, 'warning')}")
    for ms, fail in ((400, True), (100, False)):
        fc = (f"[0:a]atrim=0:{gap},asetpts=PTS-STARTPTS[a0];[0:a]atrim={gap},asetpts=PTS-STARTPTS,adelay={ms}:all=1[a1];"
              f"[a0][a1]concat=n=2:v=0:a=1,atrim=0:20[a]")
        c, r = defect(f"slip{ms}", "-i", src, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac")
        offs = [x.get("offset_ms") for x in r["sync"]["sentences"]]
        bad = [i["message"][:3] for i in r["issues"] if i["code"] == "sentence_offset"]
        if fail:
            check(bad == ["s2:", "s3:"] and abs(offs[0]) <= 30 and all(abs(o + ms) <= 30 for o in offs[1:]),
                  f"audio slips {ms} ms after s1: s2 and s3 fail, s1 does not; offsets {offs} ms")
        else:
            check(not bad and all(abs(o + ms) <= 30 for o in offs[1:]), f"a {ms} ms slip is measured ({offs} ms) and stays under the {OC.SYNC_LIMIT_MS} ms limit")
    c, r = defect("nopause", "-i", src, "-f", "lavfi", "-i", "sine=f=440:r=48000", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-t", "20")
    check(r["sync"]["measured"] == 0 and all(x["status"] == "not_measurable" and x["reason"] for x in r["sync"]["sentences"]) and "sentence_offset" not in codes(r),
          f"no pause between sentences: every onset not_measurable with its reason, no number made up ({r['sync']['sentences'][0]['reason'][:60]})")
    c = work / "d-missing"
    c.mkdir()
    r = OC.check(c, v, write=False)
    check(r["status"] == "FAIL" and codes(r) == ["missing"], "missing MP4: FAIL missing")

    print("\n== CLI")
    env = dict(FX.CLEAN_ENV, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-B", str(CLI), "--build", str(builds["en-off"][1]), "--project", str(builds["en-off"][0])], capture_output=True, text=True, env=env)
    q = subprocess.run([sys.executable, "-B", str(CLI), "--build", str(work / "d-noaudio"), "--project", str(v)], capture_output=True, text=True, env=env)
    check(p.returncode == 0 and "output check: OK" in p.stdout and q.returncode == 1 and "no_audio" in q.stdout, "cli: exit 0 on OK, 1 on FAIL")
    git1 = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=ROOT, capture_output=True, text=True).stdout
    check(git0 == git1, "nothing written into the repository (git status unchanged, also ignored files)")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL OUTPUT O1 TESTS PASSED" if not f else "OUTPUT O1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
