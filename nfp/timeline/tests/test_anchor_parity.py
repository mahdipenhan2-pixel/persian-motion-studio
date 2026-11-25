#!/usr/bin/env python3
"""T1 - anchors resolved in Python (nfp/timeline/anchors.py) vs the REAL Film Director (kit/50_director.js, unchanged).

  python3 nfp/timeline/tests/test_anchor_parity.py --work <dir outside the repository>

For Film fixture pages composed with synthetic timing (en, fa, with characters; one with estimated words; one where
compose's own fallback for never-timed words is used), DATA is taken from the composed page and words.json from the same
build. Every word start / end, a grid of sentence fractions, many times (frame halves included) and 'end' are resolved
by both; frame numbers and seconds must be identical. Anchors the Director rejects (unknown sentence / word) must be
rejected by Python too; anchors only Python rejects (stricter: fraction outside 0..1, negative time) are listed.
Uses Node + the Film fixtures read-only; no browser, no network.
"""
import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
ROOT = NFP.parent
FILM = NFP / "film"
sys.path[:0] = [str(NFP), str(FILM / "engine"), str(FILM / "tests"), str(ROOT / "scripts")]
import timeline as TL                                  # noqa: E402
import project as P                                    # noqa: E402  (Film, read-only, to compose fixtures)
import compose as C                                    # noqa: E402
import cast_plan as CP                                 # noqa: E402
from film_equivalence_check import synth_timing        # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def build(fixture, work, name, untimed=(), raw_untimed=False):
    proj = P.load(FILM / "tests/fixtures" / fixture)
    ch = proj["chapters"][0]
    timing = synth_timing(ch)
    for sid, i in untimed:
        for s in timing["sentences"]:
            if s["id"] == sid:
                s["words"][i]["abs_start"] = s["words"][i]["abs_end"] = None
    b = work / name
    b.mkdir(parents=True)
    with wave.open(str(b / "narration.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * int(24000 * timing["audio"]["total"]))
    ke, fr, _ = CP.fragment(proj, ch, timing, b)
    keep = C.estimate_untimed
    if raw_untimed:                     # compose's own fallback path (words still untimed after estimation)
        C.estimate_untimed = lambda t: t
    try:
        C.compose(proj, ch, timing, b, str(work / "nofonts"), b / "narration.wav", cast_fragment=fr, kit_extra=ke)
    finally:
        C.estimate_untimed = keep
    page = (b / "story/index.html").read_text(encoding="utf-8")
    found = re.findall(r"\n  const DATA = (\{.*?\});\n", page)
    if len(found) != 1:
        sys.exit(f"{name}: the page's timeline DATA not found exactly once")
    data = json.loads(found[0])
    return data, json.loads((b / "words.json").read_text(encoding="utf-8"))


def anchors_for(data, rng):
    A = []
    for s in data["sentences"]:
        for i in range(len(s["words"])):
            A += [[s["id"], "w", i], [s["id"], "e", i]]
        A += [[s["id"], f] for f in (0, 0.1, 0.25, 1 / 3, 0.5, 2 / 3, 0.75, 0.9, 0.999, 1)]
    d = data["duration"]
    A += [0, 0.3, 1 / 60, 0.05, 2.5 / 30, 3.5 / 30, 1.75, 4.664, 7.0166666, 10.5 / 30, d - 0.01, d, "end"]
    A += [round(rng.uniform(0, d), 3) for _ in range(150)] + [(k + 0.5) / 30 for k in range(0, int(d * 30), 7)]
    return A


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    rng = random.Random(7)
    cases = {}
    for name, fx, unt, raw in (("neutral-en", "neutral-en", (), False), ("cast-en", "cast-en", (), False),
                               ("cast-fa", "cast-fa", (), False), ("estimated", "cast-en", (("s2", 3), ("s2", 4)), False),
                               ("never-timed", "cast-fa", (("s1", 2), ("s3", 4)), True)):
        data, words = build(fx, work, name, unt, raw)
        cases[name] = (data, words, anchors_for(data, rng))
    bad = [["zz", "w", 0], ["s1", "w", 999], ["s1", "e", 999], ["zz", 0.5]]
    stricter = [["s1", 1.5], ["s1", -0.2], -1.0]
    cfg = {"director": str(FILM / "kit/50_director.js"), "out": str(work / "js.json"),
           "cases": [{"name": n, "data": d, "anchors": A + bad + stricter} for n, (d, _, A) in cases.items()]}
    (work / "cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "director_anchors.mjs"), str(work / "cfg.json")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("node failed:\n" + r.stderr[-2000:])
    JS = json.loads((work / "js.json").read_text(encoding="utf-8"))
    total = 0
    for name, (data, words, A) in cases.items():
        ctx = TL.Context.from_words(words)
        js = JS[name]
        diffs = []
        for anc, j in zip(A, js):
            try:
                f = ctx.resolve(anc)
            except TL.AnchorError as e:
                diffs.append((anc, j, f"python error: {e}"))
                continue
            if "error" in j or j["f"] != f or j["t"] != f / 30:
                diffs.append((anc, j, f))
        total += len(A)
        kinds = sum(1 for x in A if isinstance(x, list) and len(x) == 3)
        check(not diffs, f"{name}: {len(A)} anchors ({kinds} word starts / ends, fractions, times, end) - Python = Director, "
                         f"frame and seconds ({len(diffs)} differences {diffs[:2]})")
        jb = js[len(A):len(A) + len(bad)]
        pb = []
        for anc in bad:
            try:
                ctx.resolve(anc)
                pb.append(False)
            except TL.AnchorError:
                pb.append(True)
        check(all("error" in x for x in jb) and all(pb), f"{name}: unknown sentence / word rejected by both")
        js_strict = js[len(A) + len(bad):]
        py_strict = []
        for anc in stricter:
            try:
                ctx.resolve(anc)
                py_strict.append("accepted")
            except TL.AnchorError:
                py_strict.append("rejected")
        check(all("error" not in x for x in js_strict) and py_strict == ["rejected"] * len(stricter),
              f"{name}: Python is stricter only where the Director silently accepts (fraction 1.5 / -0.2, time -1 -> "
              f"Director frames {[x.get('f') for x in js_strict]}; Python rejects them)")
        check(ctx.frames == round(data["duration"] * 30) and ctx.frames / 30 == data["duration"],
              f"{name}: duration {ctx.frames} frames = DATA.duration {data['duration']} s")
    est = any(w.get("estimated") for s in cases["estimated"][1]["sentences"] for w in s["words"])
    never = any(w["start"] is None for s in cases["never-timed"][1]["sentences"] for w in s["words"])
    check(est and never, "the estimated-word path and compose's never-timed fallback are both exercised")
    print(f"\n{total} anchors compared in total")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"{n} checks: {n - f} passed, {f} failed. " + ("ALL ANCHOR PARITY TESTS PASSED" if not f else "ANCHOR PARITY TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
