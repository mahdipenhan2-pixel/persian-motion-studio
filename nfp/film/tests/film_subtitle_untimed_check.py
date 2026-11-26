#!/usr/bin/env python3
"""Subtitle Engine - a word Whisper could not match and estimate_untimed could not place (no gap before the next word:
real speech, e.g. a short Persian word at a sentence start). It is placed so that it ENDS where the next timed word
starts (from max(previous word end / sentence start, next start - 60 ms)), flagged est - never overlapping the next word,
so the engine's own word-order QC passes; an untimed LAST word keeps its place at the sentence end; the timed words'
times are not changed; every word still appears once, in order.
  python3 nfp/film/tests/film_subtitle_untimed_check.py
"""
import copy
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "engine"), str(HERE), str(HERE.parents[1]), str(HERE.parents[2] / "scripts")]
import subtitles as SB                      # noqa: E402
from film_subtitle_check import mk_timing, proj, words_in   # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def main():
    t = mk_timing([("s1", "خیابان آرام بیدار می‌شود."), ("s2", "در خانه دوستی قدیمی داستان را تعریف می‌کند.")], untimed={("s2", 0)})
    s2 = t["sentences"][1]
    s2["words"][1]["abs_start"] = s2["offset"] + 0.0004          # the next word starts at the sentence start: no gap at all
    s2["words"][1]["start"] = 0.0004
    before = copy.deepcopy(t)
    d = SB.build(proj("fa", mode="karaoke"), {}, t)
    codes = [i["code"] for i in d["qc"]["issues"]]
    w = {r["text"]: r for s in SB.timed_words(t) for r in s["words"]}
    check("word_overlap" not in codes and d["qc"]["status"] != "FAIL", f"no gap before the next word: QC {d['qc']['status']} {sorted(set(codes))}")
    check(w["در"]["est"] and w["در"]["end"] == round(s2["words"][1]["abs_start"], 3) and w["در"]["start"] <= w["در"]["end"],
          f"'در' placed {w['در']['start']}-{w['در']['end']} s: ends where 'خانه' starts ({round(s2['words'][1]['abs_start'], 3)} s), est")
    check(t == before, "the timing itself is not changed")
    check([x for _, x in words_in(d)] == "خیابان آرام بیدار می‌شود. در خانه دوستی قدیمی داستان را تعریف می‌کند.".split(),
          "every word once, in order")
    t2 = mk_timing([("s1", "The street wakes up slowly today.")], untimed={("s1", 2)})
    d2 = SB.build(proj("en", mode="karaoke"), {}, t2)
    w2 = SB.timed_words(t2)[0]["words"]
    check(d2["qc"]["status"] != "FAIL" and w2[1]["end"] <= w2[2]["start"] <= w2[2]["end"] <= w2[3]["start"],
          f"an untimed middle word with a gap around it: estimated inside the gap ({w2[2]['start']}-{w2[2]['end']} s)")
    t3 = mk_timing([("s1", "The street wakes up slowly.")], untimed={("s1", 4)})
    w3 = SB.timed_words(t3)[0]["words"]
    s = t3["sentences"][0]
    check(w3[-1]["est"] and w3[-1]["start"] >= w3[-2]["end"] - 1e-6, f"an untimed last word: after the last timed word ({w3[-1]['start']} s)")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL SUBTITLE UNTIMED TESTS PASSED" if not f else "SUBTITLE UNTIMED TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
