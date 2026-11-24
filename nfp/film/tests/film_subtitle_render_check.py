#!/usr/bin/env python3
"""S3 - subtitles drawn on the video from subtitles.json (engine/subtitle_layer.py), offline, synthetic timing.

  python3 nfp/film/tests/film_subtitle_render_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir> --work <dir>

  L legacy    no subtitles block -> page / words.json / story.srt / cast report byte-identical to the committed Film
              (HEAD); removing the block brings that page back; with a block, words.json, story.srt, the lip sync data
              (DATA.sentences, C3 key lists) are the same bytes as legacy - only the subtitle layer changes
  P page      en + fa x sentence / word / karaoke / off in the browser: the right cue is visible in its time window and
              never two at once, <= 2 rendered lines inside the frame, text = subtitles.json (ZWNJ, punctuation),
              direction / font / look as before, karaoke: at the middle of every word exactly that word is highlighted,
              dim before, white after, highlights move right-to-left (fa) / left-to-right (en); off: nothing drawn
  E errors    a block without subtitles.json, or a stale one, is refused with a clear message
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path[:0] = [str(FILM / "engine"), str(HERE), str(ROOT / "nfp"), str(ROOT / "scripts")]
import project as P                       # noqa: E402
import subtitles as SB                    # noqa: E402
import compose as C                       # noqa: E402
import cast_plan as CP                    # noqa: E402
from film_equivalence_check import synth_timing      # noqa: E402
from film_cast_check import silent_wav, CDN          # noqa: E402
from film_subtitle_check import compose_outputs      # noqa: E402

RESULTS = []
ZWNJ = "‌"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def make(fixture, work, name, sub=None, run_subs=True):
    """A project copy (+ subtitles block), subtitles.json via the S1 builder, composed page with local GSAP."""
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FILM / "tests/fixtures" / fixture, d)
    if sub is not None:
        pj = json.loads((d / "project.json").read_text(encoding="utf-8"))
        pj["subtitles"] = sub
        (d / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    proj = P.load(d)
    ch = proj["chapters"][0]
    timing = synth_timing(ch)
    b = work / "builds" / name
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    silent_wav(b / "narration.wav", timing["audio"]["total"])
    doc = None
    if sub is not None and run_subs:
        doc = SB.build(proj, ch, timing)
        SB.write(b, doc)
    ke, fr, rep = CP.fragment(proj, ch, timing, b)
    return proj, ch, timing, b, doc, (ke, fr, rep)


def compose_page(proj, ch, timing, b, frag, fonts, gsap):
    ke, fr, rep = frag
    C.compose(proj, ch, timing, b, fonts, b / "narration.wav", cast_fragment=fr, kit_extra=ke)
    if rep:
        (b / "cast_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    (b / "story" / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(gsap, b / "story" / "gsap.min.js")
    return page


def timeline_json(page):
    return re.search(r"const DATA = (.*?);\n", page).group(1)


def mount_json(page):
    m = re.search(r"window\.K\.film\.mount\((.*)\);\n</script>", page, re.S)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
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
    legacy = {}
    for fx in ("neutral-en", "cast-en", "cast-fa"):
        f = FILM / "tests/fixtures" / fx
        old, _ = compose_outputs(head, f, work / "L" / fx / "old", a.fonts)
        new, imp = compose_outputs(ROOT, f, work / "L" / fx / "new", a.fonts)
        legacy[fx] = new
        check(old == new and len(new) >= 3 and not imp, f"{fx}: {', '.join(sorted(new))} byte-identical to {head_rev[:7]}")

    pages, docs = {}, {}
    for lang, fx in (("en", "cast-en"), ("fa", "cast-fa")):
        for mode in SB.MODES:
            proj, ch, timing, b, doc, frag = make(fx, work, f"{lang}-{mode}", {"mode": mode})
            page = compose_page(proj, ch, timing, b, frag, a.fonts, a.gsap)
            pages[(lang, mode)] = (b, page)
            docs[(lang, mode)] = doc
        # same data for Director / lip sync, words.json, story.srt and cast report as the legacy page
        lg = legacy[fx]
        lpage = lg["story/index.html"].decode("utf-8")
        ok = True
        for mode in SB.MODES:
            b, page = pages[(lang, mode)]
            ok &= bool(timeline_json(page) == timeline_json(lpage) and mount_json(page) == mount_json(lpage) and mount_json(page))
            ok &= all((b / f).read_bytes() == lg[f] for f in ("words.json", "story.srt", "cast_report.json"))
        check(ok, f"{fx}: in all 4 modes DATA.sentences (Director + lip sync), the C3 key lists, words.json, story.srt and "
                  f"the cast report are the same bytes as the legacy page")
        # rollback: the same project without its block composes the legacy page again
        proj, ch, timing, b, _, frag = make(fx, work, f"{lang}-rollback")
        C.compose(proj, ch, timing, b, a.fonts, b / "narration.wav", cast_fragment=frag[1], kit_extra=frag[0])
        check((b / "story/index.html").read_bytes() == lg["story/index.html"], f"{fx}: without the block the page is the legacy page again")
        b, page = pages[(lang, "sentence")]
        check(page.count("/* subtitles (Subtitle Engine S3") == 1 and "Subtitles: a sentence shows" not in page
              and 'class="sentence"' not in page, f"{lang}: with a block, the subtitle layer replaces the old one (once)")

    print("\n== P page (browser)")
    cfg = {"pages": {}, "out": str(work / "subs.json")}
    for (lang, mode), (b, _) in pages.items():
        doc = docs[(lang, mode)]
        mid = (doc["cues"][1]["start"] + doc["cues"][1]["end"]) / 2 if mode != "word" else doc["cues"][5]["start"] + 0.05
        cfg["pages"][f"{lang}-{mode}"] = {"dir": str(b / "story"), "subs": doc, "shot": round(mid, 3)}
    (work / "subs.cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "film_subtitle_page.mjs"), str(work / "subs.cfg.json")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("browser check failed:\n" + r.stderr[-2500:])
    R = json.loads((work / "subs.json").read_text(encoding="utf-8"))
    legacy_style = None
    for (lang, mode), (b, _) in pages.items():
        x, doc, key = R[f"{lang}-{mode}"], docs[(lang, mode)], f"{lang} {mode}"
        check(not x["errors"], f"{key}: page runs without errors or warnings {x['errors'][:1]}")
        check(x["lang"] == lang and x["dir"] == ("rtl" if lang == "fa" else "ltr") and x["legacy_sentences"] == 0,
              f"{key}: <html lang={x['lang']} dir={x['dir']}>, no old sentence elements")
        if mode == "off":
            check(x["cue_elements"] == 0 and x["band_display"] == "none" and all(not c["any"] for c in x["cues"]) and not x["overlap"],
                  f"{key}: nothing drawn - no cue, no band, at every cue time")
            continue
        font = "Vazirmatn," if lang == "fa" else "Inter,"
        check(x["cue_font"].replace('"', "").startswith(font) and x["cue_direction"] == x["dir"]
              and (x["fonts_loaded"]["vazirmatn"] if lang == "fa" else x["fonts_loaded"]["inter"]),
              f"{key}: font {x['cue_font'][:28]}, direction {x['cue_direction']}")
        if legacy_style is None:
            legacy_style = x["cue_style"]
        check(x["cue_style"] == legacy_style and x["cue_style"].startswith("56px | 700 | 73.92px | rgb(255, 255, 255)"),
              f"{key}: the old look - {x['cue_style'][:90]}")
        right = all(c["visible"] == [c["i"]] for c in x["cues"])
        check(right and not x["overlap"], f"{key}: in each of the {len(x['cues'])} cue windows exactly that cue is visible; "
                                         f"never two at once ({len(x['overlap'])} overlaps)")
        lines_ok = all(c["rendered_lines"] == len(dc["lines"]) <= 2 for c, dc in zip(x["cues"], doc["cues"]))
        inside = all(c["text_left"] >= 160 - 1 and c["text_right"] <= 1760 + 1 and c["box"][3] <= 1080 for c in x["cues"])
        check(lines_ok and inside, f"{key}: every cue shows its own {max(len(c['lines']) for c in doc['cues'])} line(s) at most "
                                   f"(<= 2), inside the 160-1760 px text area")
        text_ok = all(c["lines"] == dc["lines"] for c, dc in zip(x["cues"], doc["cues"]))
        zw = sum(ln.count(ZWNJ) for c in doc["cues"] for ln in c["lines"])
        check(text_ok and sum(ln.count(ZWNJ) for c in x["cues"] for ln in c["lines"]) == zw,
              f"{key}: the text on screen = subtitles.json ({zw} nim-fasele, punctuation kept)")
        if mode == "karaoke":
            W = x["words"]
            exact = sum(1 for w in W if w["got"] == [w["want"]])
            check(exact == len(W), f"{key}: at the middle of each of the {len(W)} words exactly that word is highlighted ({exact})")
            check(all(w["before"] == "rgba(255, 255, 255, 0.62)" and w["after"] == "rgb(255, 255, 255)" for w in W),
                  f"{key}: each word dim just before it is spoken and white after")
            sign = -1 if lang == "fa" else 1
            bad = sum(1 for p, q in zip(W, W[1:]) if p["cue"] == q["cue"] and p["top"] == q["top"] and (q["x"] - p["x"]) * sign <= 0)
            check(bad == 0, f"{key}: highlights move {'right-to-left' if sign < 0 else 'left-to-right'} along each line ({bad} reversals)")
            times = [(w["start"], w["end"]) for c in doc["cues"] for w in c["words"]]
            T = [(r_["abs_start"], r_["abs_end"]) for s in synth_timing(P.load(work / "projects" / f"{lang}-karaoke")["chapters"][0])["sentences"]
                 for r_ in s["words"]]
            check(times == T, f"{key}: highlight times are the spoken word times (timing.json / words.json) exactly")
    check(R["network_requests"] == 0, f"no network request ({R['network_requests']})")
    shots = " ".join(str(work / f"{k}.png") for k in ("fa-karaoke", "en-karaoke", "fa-sentence", "fa-word"))
    print(f"   screenshots: {shots}")

    print("\n== E errors")
    proj, ch, timing, b, _, frag = make("cast-fa", work, "fa-missing", {"mode": "karaoke"}, run_subs=False)
    try:
        C.compose(proj, ch, timing, b, a.fonts, b / "narration.wav", cast_fragment=frag[1], kit_extra=frag[0])
        msg = "accepted"
    except SystemExit as e:
        msg = str(e)
    check("run `run.py subs` before compose" in msg and not (b / "story/index.html").exists(), "a block without subtitles.json: clear error, no page")
    proj, ch, timing, b, _, frag = make("cast-fa", work, "fa-stale", {"mode": "karaoke"})
    proj["subtitles"]["max_chars_per_line"] = 30
    try:
        C.compose(proj, ch, timing, b, a.fonts, b / "narration.wav", cast_fragment=frag[1], kit_extra=frag[0])
        msg = "accepted"
    except SystemExit as e:
        msg = str(e)
    check("does not match the current timing / subtitle settings" in msg, "a stale subtitles.json (settings changed): clear error")
    src = (FILM / "engine/subtitle_layer.py").read_text(encoding="utf-8")
    imports = sorted(set(re.findall(r"^(?:from|import) (\w+)", src, re.M)))
    check(set(imports) <= {"html", "json", "pathlib", "subtitles"}, f"subtitle_layer.py: standard library + subtitles only {imports}")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL SUBTITLE S3 TESTS PASSED" if not f else "SUBTITLE S3 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
