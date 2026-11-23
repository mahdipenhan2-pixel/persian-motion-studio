#!/usr/bin/env python3
"""
C3c tests: word-timing normaliser + lip sync (offline; no audio, no Whisper, no TTS, no network).

  python3 nfp/character/tests/test_lipsync.py

D. Persian and English; timed and untimed words; incomplete and unsorted timings; overlaps; silence > 0.15 s closes
   the mouth; mouth opens within one frame of the word start; the mouth closes after the speech (back to the
   expression); every input format (Studio timing.json, Docu DATA, Whisper segments, word lists); RTL text handling.
All timings here are hand-written test data.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG.parent))

from character.animation import keys as KY  # noqa: E402
from character.animation import lipsync as LS  # noqa: E402
from character.animation import timing_normalize as TN  # noqa: E402
from character.animation.keys import PROFILE, PlanError  # noqa: E402
from character.animation.script import plan  # noqa: E402

DEMO = PKG / "examples" / "demo-anim"
TIMING = json.loads((DEMO / "timing.json").read_text(encoding="utf-8"))
OPEN, CLOSED = set(PROFILE["open_mouths"]), set(PROFILE["closed_mouths"])
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg)


def talk_plan(timing, expr="neutral", duration=None, extra=(), t=0.1, **talk):
    words = TN.normalize(timing)
    ends = [w["t1"] for s in words["sentences"] for w in s["words"] if w["t1"] is not None]
    duration = duration or (max(ends) + 1.5)
    doc = {"schema": "nfp.anim.actions/1", "fps": 30, "duration": duration, "timing": timing,
           "actors": [{"id": "z", "cast": "../demo-cast", "character": "zahra", "expr": expr, "idle": False}],
           "actions": [{"actor": "z", "do": "talk", "t": t, **talk}, *extra]}
    return plan(doc, base_dir=DEMO)


def mouth(kl, fr):
    lst = KY.channels(kl["keys"]).get(("z", "mouth", "shape"), [])
    return KY.sample_channel(lst, "mouth", "shape", fr)


def en_words():
    return [{"word": " Hello", "start": 0.50, "end": 0.92}, {"word": " my", "start": 0.98, "end": 1.14},
            {"word": " name", "start": 1.18, "end": 1.50}, {"word": " is", "start": 1.54, "end": 1.66},
            {"word": " Zahra.", "start": 1.72, "end": 2.20}, {"word": " Today", "start": 2.70, "end": 3.04},
            {"word": " you", "start": 3.10, "end": 3.30}, {"word": " listen.", "start": 3.34, "end": 3.80}]


def main():
    print("== D1 Persian (Studio timing.json shape)")
    n = TN.normalize(TIMING)
    rep = n["report"]
    check(n["source"] == "studio" and rep["words"] == 11 and rep["timed"] == 10 and rep["estimated"] == 1
          and [u["text"] for u in rep["unresolved"]] == ["شهرم"],
          f"11 words: 10 timed, 1 estimated (برایتان), 1 unresolved listed by name ({rep['unresolved'][0]['note']})")
    fa = talk_plan(TIMING, t=8.0)
    talk = fa["lipsync"]["talks"][0]
    timed = [w for s in n["sentences"] for w in s["words"] if w["t0"] is not None]
    opens = [(w["text"], mouth(fa, round(w["t0"] * 30)), abs(round(w["t0"] * 30) - w["t0"] * 30)) for w in timed]
    check(all(m in OPEN for _, m, _ in opens) and max(o for _, _, o in opens) <= 1.0,
          f"every timed Persian word opens the mouth on its own frame (max offset {max(o for _, _, o in opens):.2f} frame)")
    check(talk["max_open_offset_frames"] <= 1.0 and talk["words"] == 10 and talk["estimated_words"][0]["text"] == "برایتان",
          f"lip-sync report: {talk['words']} words, {talk['flaps']} mouth changes, estimated words labelled")
    mk = [k for k in fa["keys"] if k["part"] == "mouth"]
    check(any(k["src"] == "lipsync:estimated" for k in mk) and all(k["val"] in PROFILE["mouths"] for k in mk),
          "estimated words keep their 'estimated' label on the keys; only the 12 rig mouths are used")
    da = next(w for w in timed if w["text"] == "داستان")      # داستان ... (شهرم has no time) ... را
    ra = next(w for w in timed if w["text"] == "را")
    check(mouth(fa, round(da["t1"] * 30)) in CLOSED and mouth(fa, round(ra["t0"] * 30) - 1) in CLOSED,
          "the untimed word gets NO invented mouth motion: the mouth stays closed in its gap")

    print("\n== D2 English (Whisper segments shape)")
    en = {"segments": [{"words": en_words()[:5]}, {"words": en_words()[5:]}]}
    ne = TN.normalize(en)
    check(ne["source"] == "whisper" and ne["report"]["timed"] == 8, "Whisper segments -> 8 timed words")
    ek = talk_plan(en)
    w0 = ne["sentences"][0]["words"]
    check(all(mouth(ek, round(w["t0"] * 30)) in OPEN for w in w0) and ek["lipsync"]["talks"][0]["max_open_offset_frames"] <= 1,
          "every English word opens the mouth within one frame")
    you = [k for k in ek["keys"] if k["part"] == "mouth" and k["f"] == round(3.10 * 30)]
    check(you and you[0]["val"] == "o" and LS.word_shapes("cat", 1) == ["open"] and LS.word_shapes("see", 1) == ["small"],
          "English mapping: 'you' -> o, 'cat' -> open, 'see' -> small")

    print("\n== D3 silence, pauses, end of speech")
    z1 = round(2.20 * 30)        # 'Zahra.' ends; next word at 2.70: 0.50 s pause
    check(mouth(ek, z1) in CLOSED and mouth(ek, z1 + 5) in CLOSED and mouth(ek, round(2.70 * 30)) in OPEN,
          "a 0.50 s pause (> 0.15 s) closes the mouth at the word end and it reopens on the next word")
    short = [{"text": "aa", "start": 1.0, "end": 1.3}, {"text": "bo", "start": 1.4, "end": 1.7}]
    sk = talk_plan(short)
    check(mouth(sk, round(1.3 * 30)) == "small" and mouth(sk, round(1.3 * 30)) not in CLOSED,
          "a 0.10 s pause (<= 0.15 s) only half-closes the mouth ('small'), it does not snap shut")
    exact = [{"text": "aa", "start": 1.0, "end": 1.3}, {"text": "bo", "start": 1.46, "end": 1.7}]
    xk = talk_plan(exact)
    check(mouth(xk, round(1.3 * 30)) in CLOSED, "a 0.16 s pause closes the mouth (threshold 0.15 s)")
    last = round(3.80 * 30)
    check(mouth(ek, last) in CLOSED and all(mouth(ek, f) in CLOSED for f in range(last, ek["frames"] + 1)),
          "after the last word the mouth closes on its end frame and stays closed")
    hk = talk_plan(en, expr="happy")
    sh = talk_plan(en, expr="shout")
    check(mouth(hk, last) == "smile" and mouth(hk, 5) == "smile" and mouth(sh, last) == "neutral",
          "closing returns to the expression's own mouth (happy -> smile); an open expression mouth (shout) closes to neutral")
    mid = talk_plan(en, extra=[{"actor": "z", "do": "expr", "t": 1.0, "name": "happy"}])
    check(mouth(mid, round(1.0 * 30)) in OPEN and mouth(mid, z1) == "smile",
          "an expression change during speech does not cut the speech; its mouth appears at the next pause")

    print("\n== D4 incomplete, invalid, unsorted, overlapping timings")
    broken = [{"text": "one", "start": 0.5, "end": 0.8}, {"text": "two", "start": None, "end": None},
              {"text": "three", "start": 1.2, "end": 1.1}, {"text": "four", "start": float("nan"), "end": 2.0},
              {"text": "five", "start": 2.2, "end": 2.6}, {"text": "six", "start": -1, "end": 0.2}]
    nb = TN.normalize(broken)
    un = {u["text"]: u["note"] for u in nb["report"]["unresolved"]}
    check(sorted(un) == ["four", "six", "three", "two"] and nb["report"]["timed"] == 2
          and all(w["t0"] is None for s in nb["sentences"] for w in s["words"] if w["text"] in un),
          f"missing / reversed / NaN / negative intervals become unresolved with a reason, never a made-up time ({un['three']})")
    bk = talk_plan(broken)
    check([k["f"] for k in bk["keys"] if k["part"] == "mouth" and k["src"].startswith("lipsync") and k["val"] in OPEN][:1] == [15]
          and bk["lipsync"]["talks"][0]["words"] == 2, "only the 2 valid words move the mouth")
    shuffled = en_words()
    shuffled = [shuffled[i] for i in (3, 0, 7, 1, 5, 2, 6, 4)]
    ns = TN.normalize({"words": shuffled})
    sk2, ok2 = talk_plan({"words": shuffled}), talk_plan({"words": en_words()})
    mk2 = lambda kl: [(k["f"], k["val"]) for k in kl["keys"] if k["part"] == "mouth"]  # noqa: E731
    check(ns["report"]["reordered"] > 0 and mk2(sk2) == mk2(ok2),
          f"unsorted words are put in time order ({ns['report']['reordered']} moved) and give the same mouth track")
    ov = [{"text": "aa", "start": 1.0, "end": 1.5}, {"text": "bb", "start": 1.3, "end": 1.8}, {"text": "cc", "start": 1.35, "end": 1.45}]
    no = TN.normalize(ov)
    check(no["report"]["clipped"] == 1 and no["sentences"][0]["words"][1]["t0"] == 1.5
          and no["sentences"][0]["words"][2]["quality"] == "unresolved",
          "an overlapping word is clipped to the previous end; a fully covered one becomes unresolved")
    nothing = [{"text": "x", "start": None, "end": None}]
    try:
        talk_plan(nothing, duration=3)
        check(False, "a talk with no timed word is refused")
    except PlanError as e:
        check("no timed words" in str(e), f"a talk with no timed word is refused ({e.problems[0][:70]})")

    print("\n== D5 formats")
    docu = {"sentences": [{"id": "a", "start": 0.5, "end": 1.6, "words": [
        {"id": "w-a-0", "start": 0.5, "end": 0.9, "hl": True}, {"id": "w-a-1", "start": 1.0, "end": 1.06, "hl": False},
        {"id": "w-a-2", "start": 1.1, "end": 1.6, "hl": True}]}]}
    nd = TN.normalize(docu)
    check(nd["source"] == "docu" and nd["report"]["timed"] == 2 and "placeholder" in nd["report"]["unresolved"][0]["note"],
          "Docu DATA: hl:false placeholder times are NOT used (unresolved), hl:true words are")
    stage2 = {"language": "fa", "words": [{"text": "سلام", "start": 0.1, "end": 0.5}]}
    n2 = TN.normalize(stage2, offset=8.0)
    check(n2["source"] == "words" and n2["sentences"][0]["words"][0]["t0"] == 8.1,
          "Stage 2 Whisper cache (local times) + sentence offset -> absolute times")
    bad = copy.deepcopy(TIMING)
    bad["sentences"][0]["words"][0]["timing_quality"] = None
    bad["sentences"][0]["words"][0]["status"] = "bracketed"
    check(TN.normalize(bad)["sentences"][0]["words"][0]["quality"] == "estimated",
          "Studio words without timing_quality fall back to status (bracketed -> estimated)")
    try:
        TN.normalize({"foo": 1})
        check(False, "an unknown timing format is refused")
    except TN.TimingError as e:
        check(True, f"an unknown timing format is refused ({e})")

    print("\n== D6 Persian text / RTL")
    check(LS.letters("كتاب")[1] == LS.letters("کتاب")[1] and LS.letters("مي‌گويم")[1] == LS.letters("می‌گویم")[1],
          "Arabic kaf/yeh variants normalise to Persian ک / ی")
    check(LS.letters("می‌کنم")[1] == list("میکنم") and LS.letters("‏سلام‎")[1] == list("سلام"),
          "ZWNJ and bidi marks are ignored for sounds (they only matter for display)")
    check((LS.syllables("سلام"), LS.syllables("زهرا"), LS.syllables("هستم")) == (2, 2, 2) and LS.syllables("۱۴۰۲") == 0,
          "syllable estimate: سلام, زهرا, هستم -> 2 each; digits -> decided by duration")
    check(LS.word_shapes("آبو", 2) == ["open", "o"] and LS.word_shapes("وبا", 2) == ["o", "open"],
          "shapes follow the logical (spoken) letter order, not the right-to-left display order")
    check(LS.word_shapes("بُت", 1) == ["o"] and LS.word_shapes("بِت", 1) == ["small"] and LS.word_shapes("بَت", 1) == ["open"],
          "written short vowels are used when present (damma -> o, kasra -> small, fatha -> open)")

    print("\n== D7 audit fixes: Docu text, sentence order, estimated words")
    docu = {"sentences": [{"id": "a", "start": 0.5, "end": 3.0, "words": [
        {"id": "w-a-0", "start": 0.5, "end": 0.95, "hl": True}, {"id": "w-a-1", "start": 1.0, "end": 1.06, "hl": False},
        {"id": "w-a-2", "start": 1.4, "end": 1.9, "hl": True}, {"id": "w-a-3", "start": 1.95, "end": 2.6, "hl": True}]}]}
    nd = TN.normalize(docu)
    ws = nd["sentences"][0]["words"]
    check(all(w["text"] == "" for w in ws) and "no word text" in ws[0]["note"] and not any("w-a" in w["text"] for w in ws),
          "Docu words without text keep an EMPTY text (the element id 'w-a-0' is never used as spoken text)")
    dk = talk_plan(docu)
    shapes = {k["val"] for k in dk["keys"] if k["part"] == "mouth" and k["src"].startswith("lipsync") and not k["src"].endswith("close")}
    check(shapes <= {"open", "small"} and len(shapes) == 2,
          f"without text the mouth uses only the neutral duration-based flaps {sorted(shapes)} (the id letter 'w' used to give 'o')")
    hole = [mouth(dk, f) for f in range(KY.to_frame(0.95, 30), KY.to_frame(1.4, 30))]   # planner rounding (half up)
    check(all(m in CLOSED for m in hole) and dk["lipsync"]["talks"][0]["words"] == 3,
          "the hl:false placeholder (1.00-1.06 s) gets no mouth motion: the mouth stays closed across its gap")
    named = TN.normalize({"sentences": [{"id": "a", "words": [{"id": "w1", "text": "Today", "start": 0.5, "end": 0.9, "hl": True}]}]})
    check(named["sentences"][0]["words"][0]["text"] == "Today", "when the Docu data does carry text, that text is used")

    ordered = copy.deepcopy(TIMING)
    flipped = copy.deepcopy(TIMING)
    flipped["sentences"].reverse()
    for s_ in flipped["sentences"]:
        s_["words"].reverse()
    no, nf = TN.normalize(ordered), TN.normalize(flipped)
    po, pf = talk_plan(ordered, t=8.0), talk_plan(flipped, t=8.0)
    mt = lambda kl: [(k["f"], k["val"]) for k in kl["keys"] if k["part"] == "mouth"]  # noqa: E731
    check(nf["report"]["timed"] == no["report"]["timed"] == 10 and nf["report"]["clipped"] == 0
          and [u["text"] for u in nf["report"]["unresolved"]] == ["شهرم"] and mt(po) == mt(pf),
          f"sentences and words listed in reverse file order give the same result (10 timed, same mouth track; {nf['report']['reordered']} reordered)")

    est = talk_plan(TIMING, t=8.0, estimated=False)
    tk = est["lipsync"]["talks"][0]
    check(not [k for k in est["keys"] if k["src"] == "lipsync:estimated"] and tk["words"] == 9
          and tk["estimated_skipped"][0]["text"] == "برایتان" and tk["estimated_used"] is False,
          "talk with estimated:false leaves the estimated word (برایتان) silent and lists it as skipped")
    dflt = talk_plan(TIMING, t=8.0)["lipsync"]["talks"][0]
    check(dflt["estimated_used"] is True and dflt["estimated_words"][0]["text"] == "برایتان",
          "by default estimated words are used and labelled (policy recorded in the report)")

    n_ = len(RESULTS)
    f = n_ - sum(RESULTS)
    print(f"\n{n_} checks: {n_ - f} passed, {f} failed. " + ("ALL LIPSYNC TESTS PASSED" if not f else "LIPSYNC TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
