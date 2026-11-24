#!/usr/bin/env python3
"""S1 - Subtitle Engine cues + QC (engine/subtitles.py), offline, no browser.

  python3 nfp/film/tests/film_subtitle_check.py --fonts <dir with woff2> --work <dir outside the repository>

  L legacy   compose output (page, words.json, story.srt, cast report) byte-identical to the committed Film (HEAD, via
             `git archive`), with and without a "subtitles" block; the subtitle module is not imported by compose
  T text     visible length, ZWNJ / nim-fasele kept and never a break point, no lone punctuation / را at a line start,
             max 2 lines x max chars, balanced breaks at punctuation, weak words not at a line end
  M modes    sentence / karaoke / word: every word exactly once and in order, karaoke + word times = the word timing,
             a whole-sentence cue has the same times as story.srt
  Q qc       CPS, short / long cues, gaps, overlap, outside the video, over-long words, estimated words, Persian spacing
  R run      `run.py subs` writes subtitles.json and leaves timing.json / words.json / the page unchanged
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path[:0] = [str(FILM / "engine"), str(HERE)]
import project as P            # noqa: E402
import subtitles as SB         # noqa: E402
from film_equivalence_check import synth_timing   # noqa: E402

RESULTS = []
RUN = FILM / "engine" / "run.py"
ENV = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GEMINI_FREE_TIER_CONFIRMED")}
ENV["PYTHONDONTWRITEBYTECODE"] = "1"
ZWNJ = "\u200c"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


COMPOSE = r"""
import json, sys, wave
eng, proj_path, build, scripts, fonts, block = sys.argv[1:7]
sys.path.insert(0, eng); sys.path.insert(0, scripts)
sys.path.insert(0, sys.argv[7]); sys.path.insert(0, sys.argv[8])
import project as P, compose as C, cast_plan as CP
from film_equivalence_check import synth_timing
raw = json.load(open(proj_path + "/project.json", encoding="utf-8"))
if block != "-":
    import shutil, tempfile
    d = tempfile.mkdtemp(dir=build); shutil.copytree(proj_path, d + "/p", dirs_exist_ok=True)
    raw["subtitles"] = json.loads(block); json.dump(raw, open(d + "/p/project.json", "w", encoding="utf-8"), ensure_ascii=False)
    proj_path = d + "/p"
proj = P.load(proj_path); ch = proj["chapters"][0]
timing = synth_timing(ch)
with wave.open(build + "/narration.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * int(24000 * timing["audio"]["total"]))
if "subtitles" in proj:                 # S3: compose draws <build>/subtitles.json, made by `run.py subs`
    import subtitles as SB
    SB.write(build, SB.build(proj, ch, timing))
ke, fr, rep = CP.fragment(proj, ch, timing, build)
C.compose(proj, ch, timing, build, fonts, build + "/narration.wav", cast_fragment=fr, kit_extra=ke)
if rep: open(build + "/cast_report.json", "w", encoding="utf-8").write(json.dumps(rep, ensure_ascii=False, indent=1))
print(json.dumps("subtitles" in sys.modules))
"""


def compose_outputs(root, fixture, build, fonts, block="-"):
    build.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-B", "-c", COMPOSE, str(root / "nfp/film/engine"), str(fixture), str(build),
                        str(root / "scripts"), str(fonts), block, str(root / "nfp/film/tests"), str(root / "nfp")],
                       capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        raise SystemExit(f"compose failed ({root}):\n{r.stderr[-1500:]}")
    files = {f: (build / f).read_bytes() for f in ("story/index.html", "words.json", "story.srt", "cast_report.json")
             if (build / f).exists()}
    return files, json.loads(r.stdout.strip().splitlines()[-1])


def mk_timing(sentences, gap=0.3, cps=14.0, lead=0.3, untimed=()):
    """A core-format timing.json: sentences = [(id, text)] or [(id, text, cps)]; words timed by their length."""
    cur, out = lead, []
    for spec in sentences:
        sid, text = spec[0], spec[1]
        rate = spec[2] if len(spec) > 2 else cps
        words = text.split()
        dur = round(max(0.3, len(text) / rate), 3)
        tot = sum(len(w) for w in words) or 1
        acc, rows = 0, []
        for i, w in enumerate(words):
            a = cur + dur * acc / tot
            acc += len(w)
            b = cur + dur * acc / tot
            timed = (sid, i) not in untimed
            rows.append({"i": i, "text": w, "abs_start": round(a, 3) if timed else None, "abs_end": round(b, 3) if timed else None,
                         "status": "exact" if timed else "missing"})
        out.append({"id": sid, "text": text, "offset": round(cur, 3), "duration": dur, "words": rows})
        cur += dur + gap
    return {"summary": {"status": "OK"}, "audio": {"total": round(cur + 0.2, 3), "gap": gap}, "sentences": out}


def proj(lang="en", **sub):
    p = {"meta": {"title": "t", "lang": lang, "width": 1920, "height": 1080, "fps": 30}, "chapters": [{"id": "c1"}]}
    if sub:
        p["subtitles"] = sub
    return p


def words_in(doc):
    """(sentence, word text) of every word as the cues show it, in order (line text split on spaces)."""
    out = []
    for c in doc["cues"]:
        for ln in c["lines"]:
            out += [(c["sentence"], w) for w in ln.split(" ")]
    return out


def srt_times(text):
    def t(x):
        h, m, s = x.split(":")
        return round(int(h) * 3600 + int(m) * 60 + float(s.replace(",", ".")), 3)
    return [(t(a), t(b)) for a, b in re.findall(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", text)]


def no_overlap(doc):
    c = doc["cues"]
    return all(x["end"] > x["start"] for x in c) and all(c[i + 1]["start"] >= c[i]["end"] - 1e-9 for i in range(len(c) - 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    head_rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(f"== L legacy (byte-identical to the committed Film {head_rev[:7]})")
    head = work / "head"
    head.mkdir()
    arch = subprocess.run(["git", "-C", str(ROOT), "archive", head_rev], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(head)], input=arch.stdout, check=True)
    for fx in ("neutral-en", "cast-en", "cast-fa"):
        f = FILM / "tests/fixtures" / fx
        old, _ = compose_outputs(head, f, work / "L" / fx / "old", a.fonts)
        new, imp = compose_outputs(ROOT, f, work / "L" / fx / "new", a.fonts)
        sub, _ = compose_outputs(ROOT, f, work / "L" / fx / "sub", a.fonts, json.dumps({"mode": "karaoke"}))
        check(old == new and len(new) >= 3 and not imp,
              f"{fx}: {', '.join(sorted(new))} byte-identical to {head_rev[:7]}; compose does not import subtitles")
        same = {k: v for k, v in sub.items() if k != "story/index.html"} == {k: v for k, v in new.items() if k != "story/index.html"}
        check(same and sub["story/index.html"] != new["story/index.html"],
              f"{fx}: with a subtitles block words.json, story.srt and the cast report are the same bytes; only the page "
              f"changes (S3 draws the cues)")

    print("\n== T text and line breaks")
    check(SB.vis("می" + ZWNJ + "شود") == 5 and SB.vis("کِتاب") == 4 and SB.vis("door.") == 5,
          "visible length ignores ZWNJ and diacritics")
    long_en = ("When the factory closed in the spring, the whole town waited for news, and nobody "
               "knew what the new owners would do with the old buildings near the river.")
    T = mk_timing([("s1", long_en)])
    d = SB.build(proj(), {}, T)
    lines = [ln for c in d["cues"] for ln in c["lines"]]
    check(len(d["cues"]) >= 2 and all(len(c["lines"]) <= 2 for c in d["cues"]) and all(SB.vis(x) <= 42 for x in lines),
          f"a {SB.vis(long_en)}-character sentence -> {len(d['cues'])} cues, <= 2 lines of <= 42 characters: {lines}")
    check([w for _, w in words_in(d)] == long_en.split(), "every word exactly once, in order, never cut")
    ends = [c["lines"][-1].split(" ")[-1] for c in d["cues"][:-1]] + [ln.split(" ")[-1] for c in d["cues"] for ln in c["lines"][:-1]]
    weak = {"a", "an", "the", "to", "of", "and", "or", "in", "on", "at", "for", "with", "by", "from"}
    check(not [e for e in ends if e.lower().strip(",.") in weak], f"no line / cue ends on a weak word ({ends})")
    check(any(c["lines"][-1].endswith(",") for c in d["cues"][:-1]) or any(ln.endswith(",") for c in d["cues"] for ln in c["lines"][:-1]),
          "breaks fall on punctuation where there is one")
    d = SB.build(proj(), {}, mk_timing([("s1", "The street wakes up slowly.")]))
    check(len(d["cues"]) == 1 and d["cues"][0]["lines"] == ["The street wakes up slowly."], "a short sentence stays one line")
    d = SB.build(proj(max_lines=1), {}, mk_timing([("s1", long_en)]))
    check(all(len(c["lines"]) == 1 and SB.vis(c["lines"][0]) <= 42 for c in d["cues"]), "max_lines 1: single-line cues")

    fa = ("کتاب‌های قدیمی کتابخانه را دوباره می‌خوانیم، چون داستان‌هایشان هنوز برای بچه‌ها و بزرگ‌ترها "
          "خواندنی است و هیچ‌کس نمی‌خواهد آن‌ها فراموش شوند.")
    d = SB.build(proj("fa"), {}, mk_timing([("s1", fa)]))
    lines = [ln for c in d["cues"] for ln in c["lines"]]
    toks = [w for ln in lines for w in ln.split(" ")]
    check(d["dir"] == "rtl" and toks == fa.split() and "".join(lines).count(ZWNJ) == fa.count(ZWNJ),
          f"fa: every nim-fasele kept inside its word, breaks only at spaces ({len(d['cues'])} cues, {len(lines)} lines)")
    check(all(SB.vis(x) <= 42 for x in lines) and all(len(c["lines"]) <= 2 for c in d["cues"])
          and not any(ln.startswith(ZWNJ) or ln.endswith(ZWNJ) for ln in lines), f"fa: <= 2 lines of <= 42 characters {lines}")
    check(not any(ln.split(" ")[0] == "را" for ln in lines), "fa: no line starts with را")
    fa2 = "او کتاب را برداشت ، و " + ZWNJ + "رفت سمت در خانه و دیگر هرگز به آن خانه قدیمی برنگشت تا امروز."
    d = SB.build(proj("fa", max_chars_per_line=20), {}, mk_timing([("s1", fa2)]))
    lines = [ln for c in d["cues"] for ln in c["lines"]]
    codes = {x["code"] for x in d["qc"]["issues"]}
    check(not any(ln.split(" ")[0] in ("،", "را") for ln in lines) and "رفت" in " ".join(lines).split(" ")
          and {"space_before_punct", "space_around_zwnj", "edge_zwnj_removed"} <= codes,
          f"fa: a lone «،» stays with its word, an edge ZWNJ is dropped, spacing problems reported {sorted(codes)}")

    print("\n== M modes and timing")
    for fx in ("neutral-en", "cast-fa"):
        pr = P.load(FILM / "tests/fixtures" / fx)
        ch = pr["chapters"][0]
        tm = synth_timing(ch)
        flat = [(s["id"], w["text"], w["abs_start"], w["abs_end"]) for s in tm["sentences"] for w in s["words"]]
        docs = {}
        for mode in SB.MODES:
            pr["subtitles"] = {"mode": mode}
            docs[mode] = SB.build(pr, ch, tm)
        ok = all(no_overlap(d) and d["qc"]["status"] == "OK" and words_in(d) == [(s, w) for s, w, _, _ in flat] for d in docs.values())
        check(ok, f"{fx}: sentence / karaoke / word cues in order, no overlap, all words once, QC OK "
                  f"({', '.join(f'{m} {len(d['cues'])}' for m, d in docs.items())})")
        kw = [(c["sentence"], w["text"], w["start"], w["end"]) for c in docs["karaoke"]["cues"] for w in c["words"]]
        ww = [(c["sentence"], c["words"][0]["text"], c["start"]) for c in docs["word"]["cues"]]
        check(kw == flat and ww == [(s, w, a0) for s, w, a0, _ in flat] and "words" not in docs["sentence"]["cues"][0],
              f"{fx}: karaoke word times and word-cue starts = the word timing exactly; sentence cues carry no word list")
        same = [c["lines"] for c in docs["karaoke"]["cues"]] == [c["lines"] for c in docs["sentence"]["cues"]]
        check(same, f"{fx}: karaoke shows the same lines as sentence mode")
    # whole-sentence cue = story.srt times (compose's rule)
    srt = (work / "L/neutral-en/new/story.srt").read_text(encoding="utf-8")
    pr = P.load(FILM / "tests/fixtures/neutral-en")
    d = SB.build(pr, pr["chapters"][0], synth_timing(pr["chapters"][0]))
    check([(c["start"], c["end"]) for c in d["cues"]] == srt_times(srt), f"sentence cues have story.srt's times {srt_times(srt)}")

    print("\n== Q quality control")
    d = SB.build(proj(), {}, mk_timing([("s1", "Everything changed overnight for the people of this town.", 32)]))
    check(any(x["code"] == "cps" for x in d["qc"]["issues"]) and d["qc"]["status"] == "WARN", "fast speech: CPS warning")
    d = SB.build(proj(), {}, mk_timing([("s1", "Yes."), ("s2", "No.")], gap=0.05))
    check(any(x["code"] == "short" for x in d["qc"]["issues"]) and no_overlap(d), "a short cue with no room to grow: warning, no overlap")
    d = SB.build(proj(), {}, mk_timing([("s1", "Yes."), ("s2", "The street wakes up slowly.")], gap=1.5))
    check(d["cues"][0]["duration"] >= 0.833 - 1e-9 and no_overlap(d), f"a short cue is held to the minimum when there is room ({d['cues'][0]['duration']}s)")
    slow = "The story moves slowly here and every word takes its time to arrive on the screen."
    d = SB.build(proj(), {}, mk_timing([("s1", slow, 6)]))
    check(len(d["cues"]) >= 2 and all(c["duration"] <= 7.0 + 1e-9 or any(x["code"] == "long" for x in d["qc"]["issues"]) for c in d["cues"]),
          f"a {round(len(slow) / 6, 1)} s sentence is split under the 7 s maximum ({[c['duration'] for c in d['cues']]})")
    d = SB.build(proj(), {}, mk_timing([("s1", "Pneumonoultramicroscopicsilicovolcanoconiosisxyzabcdefghijk is long.")]))
    check(any(x["code"] == "line_too_long" for x in d["qc"]["issues"]), "a word longer than a line: warning")
    T = mk_timing([("s1", "The first sentence is right here."), ("s2", "The second one follows it.")])
    T["sentences"][1]["offset"] = T["sentences"][0]["words"][-1]["abs_start"]       # broken timing: s2 starts inside s1
    for w in T["sentences"][1]["words"]:
        w["abs_start"] -= 1.0
        w["abs_end"] -= 1.0
    d = SB.build(proj(), {}, T)
    check(d["qc"]["status"] == "FAIL" and any(x["code"] == "word_overlap" for x in d["qc"]["issues"]) and no_overlap(d),
          "overlapping word timing: error, QC FAIL (and the cues themselves still never overlap)")
    pr = proj()
    pr["meta"]["target_duration"] = 5
    d = SB.build(pr, {}, mk_timing([("s1", long_en)]))
    check(any(x["code"] == "outside_video" for x in d["qc"]["issues"]), "cues after the end of the video: error")
    d = SB.build(proj(mode="karaoke"), {}, mk_timing([("s1", "It cost 294 dollars in the end.")], untimed={("s1", 2)}))
    w = [x for c in d["cues"] for x in c["words"] if x["text"] == "294"]
    check(w and w[0]["est"] and any(x["code"] == "estimated_words" for x in d["qc"]["issues"]) and no_overlap(d),
          "a word Whisper could not match: estimated time (est), reported as info")
    for bad in ({"mode": "scroll"}, {"max_lines": 3}, {"color": "red"}, {"min_duration": 8, "max_duration": 7}):
        try:
            SB.settings({"subtitles": bad})
            ok = False
        except SB.SubtitleError:
            ok = True
        check(ok, f"invalid settings refused: {bad}")
    a1 = json.dumps(SB.build(proj("fa"), {}, mk_timing([("s1", fa)])), ensure_ascii=False)
    a2 = json.dumps(SB.build(proj("fa"), {}, mk_timing([("s1", fa)])), ensure_ascii=False)
    check(a1 == a2, "deterministic: the same input gives the same subtitles.json")

    print("\n== R run.py subs")
    src = FILM / "tests/fixtures/cast-fa"
    pdir = work / "projects" / "subs-fa"
    shutil.copytree(src, pdir)
    pj = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    pj["subtitles"] = {"mode": "karaoke", "max_chars_per_line": 30}
    (pdir / "project.json").write_text(json.dumps(pj, ensure_ascii=False), encoding="utf-8")
    b = work / "L/cast-fa/new"
    (b / "timing.json").write_text(json.dumps(synth_timing(P.load(pdir)["chapters"][0]), ensure_ascii=False), encoding="utf-8")
    before = {f: sha(b / f) for f in ("timing.json", "words.json", "story.srt", "story/index.html", "cast_report.json")}
    r = subprocess.run([sys.executable, "-B", str(RUN), "subs", "--project", str(pdir), "--build", str(b)],
                       capture_output=True, text=True, env=ENV)
    doc = json.loads((b / "subtitles.json").read_text(encoding="utf-8")) if (b / "subtitles.json").exists() else {}
    after = {f: sha(b / f) for f in before}
    check(r.returncode == 0 and doc.get("schema") == "nfp.film.subtitles/1" and doc.get("mode") == "karaoke"
          and doc["settings"]["max_chars_per_line"] == 30 and doc["lang"] == "fa",
          f"run.py subs: {r.stdout.strip()[:110]}")
    check(before == after, "timing.json, words.json, story.srt, the page and the cast report are unchanged by `subs`")
    W = json.loads((b / "words.json").read_text(encoding="utf-8"))
    wj = [(s["id"], w["text"], w["start"], w["end"]) for s in W["sentences"] for w in s["words"]]
    sj = [(c["sentence"], w["text"], w["start"], w["end"]) for c in doc["cues"] for w in c["words"]]
    check(wj == sj, f"karaoke words in subtitles.json = words.json ({len(sj)} words)")
    r = subprocess.run([sys.executable, "-B", str(RUN), "subs", "--project", str(FILM / "tests/fixtures/neutral-en"),
                        "--build", str(work / "empty")], capture_output=True, text=True, env=ENV)
    check(r.returncode != 0 and "run `align` first" in r.stderr, "no timing.json: clear error")
    pj["subtitles"] = {"mode": "teleprompter"}
    (pdir / "project.json").write_text(json.dumps(pj, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(RUN), "plan", "--project", str(pdir), "--build", str(work / "empty")],
                       capture_output=True, text=True, env=ENV)
    check(r.returncode != 0 and "subtitles.mode" in (r.stderr + r.stdout), "a bad subtitles block is refused when the project loads")
    src_txt = (FILM / "engine/subtitles.py").read_text(encoding="utf-8")
    imports = sorted(set(re.findall(r"^(?:from|import) (\w+)", src_txt, re.M)))
    check(set(imports) <= {"json", "re", "unicodedata", "pathlib", "untimed"}, f"subtitles.py: standard library + untimed only {imports}")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL SUBTITLE S1 TESTS PASSED" if not f else "SUBTITLE S1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
