#!/usr/bin/env python3
"""F2 + F3 - Film vs the reference documentary engine (Kim engine, branch docu-16x9-test30), compared on PICTURES.

  python3 nfp/film/tests/film_equivalence_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir with woff2> \
      --work <dir outside the repository> [--fixture nfp/film/tests/fixtures/neutral-en]

1. The reference engine is taken from the source commit in PROVENANCE.json with `git archive` into --work (read only,
   nothing is checked out, the branch is never touched) and composes the neutral fixture; nfp/film composes the same
   fixture with the same synthetic word timing (no audio, no TTS).
2. Page source differences (title, kit list, paths, placeholders) are reported as INFO only - they are not failures.
3. Pictures: in local Chromium both pages are compared frame by frame for each layer view: full frame, art without
   characters (backgrounds, camera, light, grade, graphics, grain/VHS), subtitles only, art with characters; plus the
   camera values (--cx --cy --cz) and visibility of every shot read from the DOM. Every view must be pixel-identical.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
PROV = json.loads((FILM / "PROVENANCE.json").read_text(encoding="utf-8"))
CDN = '<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>'
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def synth_timing(ch, cps=14.0, lead=0.3, gap=0.3, tail=0.5):
    """Deterministic synthetic word timing (14 characters per second) in the core timing.json shape."""
    cur, sents = lead, []
    for s in ch["sentences"]:
        dur = round(len(s["text"]) / cps, 3)
        words = s["text"].split()
        tot = sum(len(w) for w in words)
        acc, rows = 0, []
        for i, w in enumerate(words):
            a = cur + dur * acc / tot
            acc += len(w)
            b = cur + dur * acc / tot
            rows.append({"i": i, "text": w, "abs_start": round(a, 3), "abs_end": round(b, 3), "status": "exact"})
        sents.append({"id": s["id"], "text": s["text"], "offset": round(cur, 3), "duration": dur, "words": rows})
        cur += dur + gap
    return {"summary": {"status": "OK"}, "audio": {"total": round(cur - gap + tail, 3), "gap": gap}, "sentences": sents}


def silent_wav(path, seconds):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * int(24000 * seconds))


RUNNER = r"""
import json, sys
eng, proj_path, build, fonts, kind = sys.argv[1:6]
sys.path.insert(0, eng)
import project as P, compose as C
proj = P.load(proj_path); ch = proj["chapters"][0]
timing = json.load(open(build + "/timing.json"))
if kind == "ref":
    info = C.compose(proj, ch, timing, build, fonts, build + "/narration.wav", local=False)
else:
    info = C.compose(proj, ch, timing, build, fonts, build + "/narration.wav")
print(json.dumps(info))
"""


def build_page(kind, eng, fixture, work, timing, fonts, gsap):
    b = work / kind
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    (b / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    silent_wav(b / "narration.wav", timing["audio"]["total"])
    r = subprocess.run([sys.executable, "-I", "-B", "-c", RUNNER, str(eng), str(fixture / "project.json"), str(b), str(fonts), kind],
                       capture_output=True, text=True, env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    if r.returncode != 0:
        raise SystemExit(f"{kind} compose failed:\n{r.stderr[-2000:]}")
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    if page.count(CDN) != 1:
        raise SystemExit(f"{kind}: expected exactly one cdnjs GSAP tag")
    (b / "story" / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(gsap, b / "story" / "gsap.min.js")
    return b, json.loads(r.stdout.strip().splitlines()[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gsap", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--fixture", default=str(HERE / "fixtures" / "neutral-en"))
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)
    fixture = Path(a.fixture).resolve()

    # reference engine: exported (not checked out) from the source commit
    ref_src = work / "ref-src"
    if ref_src.exists():
        shutil.rmtree(ref_src)
    ref_src.mkdir()
    arch = subprocess.run(["git", "-C", str(ROOT), "archive", PROV["source"]["commit"], "docu/engine", "studio/config"], capture_output=True)
    if arch.returncode != 0:
        sys.exit("source commit not available locally: " + arch.stderr.decode()[-300:])
    subprocess.run(["tar", "-x", "-C", str(ref_src)], input=arch.stdout, check=True)

    sys.path.insert(0, str(FILM / "engine"))
    import project as FP
    proj = FP.load(fixture / "project.json")
    timing = synth_timing(proj["chapters"][0])
    ref, ri = build_page("ref", ref_src / "docu" / "engine", fixture, work, timing, a.fonts, a.gsap)
    film, fi = build_page("film", FILM / "engine", fixture, work, timing, a.fonts, a.gsap)
    check(ri["duration"] == fi["duration"] and ri["sentences"] == fi["sentences"],
          f"both engines compose the fixture: duration {fi['duration']}s, {fi['sentences']} sentences")
    pr, pf = (ref / "story/index.html").read_text(encoding="utf-8"), (film / "story/index.html").read_text(encoding="utf-8")
    lr, lf = pr.splitlines(), pf.splitlines()
    print(f"INFO page source (not a test): reference {len(lr)} lines / film {len(lf)} lines, identical={pr == pf}. "
          "Expected differences: <title>, lang/dir attributes, kit list (Film has no Kim scene sets).")
    check((film / "words.json").exists() and json.loads((film / "words.json").read_text(encoding="utf-8"))["schema"] == "nfp.film.words/1",
          "word timing is written as its own data file (words.json, nfp.film.words/1); story.srt is a side output")

    dur = fi["duration"]
    times = sorted({round(0.2 + i * (dur - 0.4) / 29, 2) for i in range(30)})
    vhs = timing["sentences"][2]["words"][0]["abs_start"]
    times = sorted(set(times) | {round(vhs - 0.05, 2), round(vhs + 0.1, 2)})
    cfg = {"a": str(ref / "story"), "b": str(film / "story"), "times": times, "out": str(work / "frames"),
           "save": [times[3], times[15], times[-3]],
           "layers": {"full": "",
                      # opacity, not visibility: shots set visibility:visible on their own groups, which would
                      # show through a hidden parent
                      "art_without_characters": '#subs{opacity:0!important} [data-p="root"]{opacity:0!important}',
                      "art_with_characters": "#subs{opacity:0!important}",
                      "subtitles_only": "#art{opacity:0!important}"},
           "sanity": [["art_with_characters", "art_without_characters"], ["full", "art_with_characters"],
                      ["full", "subtitles_only"]]}
    (work / "frames.cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "film_frames.mjs"), str(work / "frames.cfg.json")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("browser comparison failed:\n" + r.stderr[-2000:])
    res = json.loads((work / "frames" / "frames.json").read_text(encoding="utf-8"))
    check(not res["errors"]["a"] and not res["errors"]["b"], f"no page errors ({res['errors']})")
    check(res["info"]["a"]["duration"] == res["info"]["b"]["duration"] and res["info"]["a"]["shots"] == res["info"]["b"]["shots"],
          f"same timeline duration ({res['info']['b']['duration']}s) and shots {res['info']['b']['shots']}")
    check(res["info"]["a"]["warnings"] == res["info"]["b"]["warnings"], f"same Director warnings ({res['info']['b']['warnings']})")
    for name, v in res["layers"].items():
        check(v["differing_frames"] == 0, f"{name}: {v['frames']} frames pixel-identical to the reference engine "
                                          f"(differing frames {v['differing_frames']}, max {v['max_pixels']} px)")
    for pair, k in res["sanity"].items():
        check(k > 0, f"layer views really separate the reference picture: '{pair}' differ on {k} frames")
    check(all(c["equal"] for c in res["camera"]), f"camera (--cx --cy --cz) and shot visibility equal at all {len(res['camera'])} times")
    check(res["network_requests"] == 0, f"no network request ({res['network_requests']})")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL EQUIVALENCE TESTS PASSED" if not f else "EQUIVALENCE TESTS FAILED"))
    print(f"work: {work}")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
