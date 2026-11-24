#!/usr/bin/env python3
"""F6 + F7 - languages of a Film page: English (default, LTR) and Persian (RTL, Vazirmatn).

  python3 nfp/film/tests/film_lang_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir with Inter + Vazirmatn woff2> --work <dir>

Checks: lang/dir of the page; subtitle direction and font; Persian SVG art text in Vazirmatn (the kit files stay
byte-identical); the highlighted word at the middle of every timed word is exactly that word and the highlights move
right-to-left (fa) or left-to-right (en) along a line; words.json (nfp.film.words/1) keeps the exact word timing;
story.srt is only a side output (same text, never read back); core config: Whisper language = project language;
Persian speech of a C3 character opens its mouth on the spoken words. Synthetic timing, silent audio, no TTS.
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FILM / "engine"))
sys.path.insert(0, str(ROOT / "nfp"))
from film_cast_check import compose  # noqa: E402
import project as P  # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def words_for(timing):
    """Sample time per word inside the window where the highlight is fully on (base.html: on after 0.05 s, off
    after max(0.06 s, word length)): the middle of the word, but never inside the 0.05 s fade-in."""
    return [{"id": f"w-{s['id']}-{w['i']}", "sid": s["id"],
             "mid": round(w["abs_start"] + max(0.055, (w["abs_end"] - w["abs_start"]) / 2), 3)}
            for s in timing["sentences"] for w in s["words"] if w["abs_start"] is not None]


def monotone(rows, sign):
    """Within each sentence and each text line, highlight centres move in one direction (sign -1: right-to-left)."""
    bad = 0
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        if a["sid"] == b["sid"] and a["top"] == b["top"] and a["x"] is not None and b["x"] is not None:
            if (b["x"] - a["x"]) * sign <= 0:
                bad += 1
    return bad


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)
    pages = {}
    for name in ("en", "fa"):
        proj, ch, timing, b, rep = compose(HERE / "fixtures" / f"cast-{name}", work, f"page-{name}", a.fonts, a.gsap)
        pages[name] = (proj, ch, timing, b, rep)

    print("== F7 data and core configuration")
    for name, (proj, ch, timing, b, rep) in pages.items():
        W = json.loads((b / "words.json").read_text(encoding="utf-8"))
        same = all(w["start"] == r["abs_start"] and w["end"] == r["abs_end"] and w["text"] == r["text"]
                   for s, ws in zip(timing["sentences"], W["sentences"]) for r, w in zip(s["words"], ws["words"]))
        check(W["schema"] == "nfp.film.words/1" and W["lang"] == name and same and sum(len(s["words"]) for s in W["sentences"]) ==
              sum(len(s["words"]) for s in timing["sentences"]), f"{name}: words.json keeps every word with its exact start/end and text")
        srt = (b / "story.srt").read_text(encoding="utf-8")
        engine_src = "".join(f.read_text(encoding="utf-8") for f in (FILM / "engine").glob("*.py"))
        check(srt.count("-->") == 3 and all(s["text"] in srt for s in ch["sentences"])
              and not re.search(r"story\.srt\"\)\.read|load\w*\([^)]*story\.srt", engine_src),
              f"{name}: story.srt is a side output with the sentence texts (no engine file reads it back)")
        cfg = P.core_config(proj, ch)
        check(cfg["whisper"]["language"] == name and cfg["video"] == {"width": 1080, "height": 1920, "fps": 30},
              f"{name}: Whisper language = project language ({cfg['whisper']['language']}); core video block untouched (core only does audio)")
    talks = [t for i in pages["fa"][4]["instances"] for t in i["talks"]]
    check(len(talks) == 2 and all(t["flaps"] > 0 and t["words"] > 5 and not t["unresolved_words"] for t in talks),
          f"fa: the C3 planner made Persian lip sync for both speaker sentences "
          f"({[(t['sentences'], t['words'], t['flaps'], len(t['unresolved_words'])) for t in talks]})")

    print("\n== F6 page (browser)")
    cfg = {"pages": {n: {"dir": str(v[3] / "story"), "words": words_for(v[2]), "shot": 11.5} for n, v in pages.items()},
           "out": str(work / "lang.json")}
    (work / "lang.cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "film_lang_page.mjs"), str(work / "lang.cfg.json")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("browser check failed:\n" + r.stderr[-2000:])
    R = json.loads((work / "lang.json").read_text(encoding="utf-8"))
    for name, want_dir, sign in (("en", "ltr", 1), ("fa", "rtl", -1)):
        x = R[name]
        check(not x["errors"], f"{name}: page runs without errors {x['errors'][:1]}")
        check(x["lang"] == name and x["dir"] == want_dir and x["sentence_direction"] == want_dir,
              f"{name}: <html lang={x['lang']} dir={x['dir']}>, subtitles direction {x['sentence_direction']}")
        rows = [dict(h, sid=w["sid"]) for h, w in zip(x["highlight"], cfg["pages"][name]["words"])]
        exact = sum(1 for h in rows if h["got"] == [h["want"]])
        check(exact == len(rows), f"{name}: at the middle of each of the {len(rows)} timed words exactly that word is highlighted ({exact} exact)")
        bad = monotone(rows, sign)
        check(bad == 0, f"{name}: highlights move {'right-to-left' if sign < 0 else 'left-to-right'} along each line ({bad} reversals)")
        texts = [[w["text"] for w in s["words"]] for s in pages[name][2]["sentences"]]
        check(x["text_order"] == texts, f"{name}: subtitle words in script order (the browser lays them out by direction)")
    fa, en = R["fa"], R["en"]
    check(fa["fonts_loaded"]["vazirmatn"] and fa["sentence_font"].replace('"', "").startswith("Vazirmatn,") and any(f.startswith("Vazirmatn") for f in fa["font_faces"]),
          f"fa: Vazirmatn loaded and used for subtitles ({fa['sentence_font'][:40]})")
    check(fa["art_text_font"] and fa["art_text_font"].replace('"', "").startswith("Vazirmatn,"),
          f"fa: SVG text of the art uses Vazirmatn through CSS ({fa['art_text_font'][:40]}); kit files unchanged")
    check(en["fonts_loaded"]["inter"] and en["sentence_font"].replace('"', "").startswith("Inter,") and not any(f.startswith("Vazirmatn") for f in en["font_faces"]),
          f"en: Inter for subtitles, no Persian font on the English page ({en['sentence_font'][:30]})")
    check(R["network_requests"] == 0, f"no network request ({R['network_requests']})")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL LANGUAGE TESTS PASSED" if not f else "LANGUAGE TESTS FAILED"))
    print(f"screenshots: {work}/en.png {work}/fa.png")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
