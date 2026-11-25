#!/usr/bin/env python3
"""G2 - text rules and layout logic, without a browser: direction, unbreakable pieces (half-space, no-break space,
«را», punctuation), number formatting (Persian / English), optimal line breaking on MEASURED line widths (fewest lines,
balanced titles, ragged bodies), overflow, boxes for anchors / explicit rects / callouts in the safe area, alignment,
paragraph direction, the two measuring rounds. Widths come from a fake, deterministic "measurement".
  python3 nfp/graphics/tests/test_graphics_g2.py
"""
import copy
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path.insert(0, str(NFP))
import graphics as G                      # noqa: E402
from graphics import textlayout as LY     # noqa: E402
from graphics import safearea as SA       # noqa: E402
from graphics import text as TX           # noqa: E402

RESULTS = []
NB = TX.NBSP


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def fake_measure(keys, k=0.5):
    """A deterministic stand-in for the browser: every character k em wide (a space too)."""
    return {"schema": "fake", "browser": "fake", "fonts": {}, "items": [
        {"text": t, "size": s, "weight": w, "family": f, "width": len(t) * s * k, "ascent": s * 0.95, "descent": s * 0.3}
        for t, s, w, f in keys]}


def measured(spec):
    m1 = fake_measure(LY.requests(spec))
    m2 = fake_measure(LY.requests(spec, m1))
    return {"items": m1["items"] + m2["items"]}


SRC = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار", "date": "2024-05-01", "verified": True}]


def spec(kind, display, lang="fa", mode="final", **kw):
    d = {"schema": "nfp.graphics/1", "id": "g", "mode": mode, "lang": lang, "kind": kind}
    d.update({"title": {"content": {"title": "فصل اول: بندر قدیمی" if lang == "fa" else "Chapter one: the old harbour",
                                    "subtitle": "سال‌های ۱۳۳۰ تا ۱۳۴۰" if lang == "fa" else "The 1950s"}},
              "lower-third": {"content": {"title": "مریم احمدی" if lang == "fa" else "Maryam Ahmadi",
                                          "subtitle": "Historian, University of Tehran"}},
              "info-card": {"content": {"title": "بندر", "body": "این بندر در سال ۱۳۳۲ بسته شد و امروز موزه است.\nهر سال (visitors) زیادی دارد.",
                                        "source": "s1"}, "sources": SRC},
              "quote": {"content": {"body": "دریا همه چیز را به یاد دارد.", "attribution": "یک ماهیگیر", "source": "s1"}, "sources": SRC},
              "callout": {"content": {"body": "اسکلهٔ قدیمی"}, "place": {"at": [600, 400]}}}[kind])
    d.update(kw)
    r = G.validate(d, display, 120)
    assert r["graphic"], r["issues"]
    return r["graphic"]


def main():
    print("== A text rules")
    check(TX.direction("۱۲۳ بندر") == "rtl" and TX.direction("123 Tehran") == "ltr" and TX.direction("۱۲۳ - 45", "rtl") == "rtl"
          and TX.direction("(visitors) دارد") == "ltr", "direction: the first strong letter (digits and punctuation are not strong)")
    check(TX.units("آن‌ها می‌روند") == ["آن‌ها", "می‌روند"], "the half-space (ZWNJ) never breaks: آن‌ها / می‌روند stay whole")
    check(TX.units(f"۴۰{NB}هزار نفر") == [f"۴۰{NB}هزار", "نفر"], "a no-break space keeps number and word together")
    check(TX.units("کتاب را خواندم") == ["کتاب را", "خواندم"], "«را» never starts a line: it stays with the word before it")
    check(TX.units("سلام ، دنیا !") == ["سلام ،", "دنیا !"] and TX.units("« آغاز") == ["«", "آغاز"],
          "a piece of only punctuation stays with the piece before it (but may open a paragraph)")
    check(TX.units("a  b ") == ["a", "b"] and TX.paragraphs("a\nb", True) == ["a", "b"] and TX.paragraphs("a\nb", False) == ["a\nb"],
          "repeated spaces are one break; explicit line breaks split a body only")
    f = TX.format_number
    I = lambda t: "\u2066" + t + "\u2069"          # a Persian number is one left-to-right isolate (the same in every context)
    M = "\u2212"
    cases = [((1250, 0, "fa"), I("۱٬۲۵۰")), ((1250, 0, "en"), "1,250"), ((999, 0, "fa"), I("۹۹۹")), ((1234567.891, 2, "en"), "1,234,567.89"),
             ((31.5, 1, "fa", "%"), I("۳۱٫۵٪")), ((31.5, 1, "en", "%"), "31.5%"), ((-1.5, 1, "fa"), I(M + "۱٫۵")), ((2.5, 0, "en"), "3"),
             ((-2.5, 0, "en"), M + "3"), ((0.125, 2, "en"), "0.13"), ((-0.004, 2, "en"), "0.00"), ((12, 0, "fa", "km"), I("۱۲") + f"{NB}km"),
             ((12, 0, "fa", "کیلومتر"), I("۱۲") + f"{NB}کیلومتر"), ((1e6, 0, "fa"), I("۱٬۰۰۰٬۰۰۰"))]
    bad = [(a, f(*a), want) for a, want in cases if f(*a) != want]
    check(not bad, f"numbers: Persian digits ٬ ٫ ٪ (one isolate), English , . %, minus U+2212, half away from zero, unit after a no-break space, outside the isolate {bad}")

    print("\n== B line breaking on measured widths")
    w10 = lambda t: len(t) * 10.0
    us = ["aaaa", "bb", "cc", "dddd", "e"]
    lines, err = LY.break_lines(us, 120, 5, w10, balanced=True)
    check(err is None and len(lines) == 2 and max(w for _, w in lines) <= 120, f"fewest lines that fit: {lines}")
    bal = max(w for _, w in lines)
    rag, _ = LY.break_lines(us, 120, 5, w10, balanced=False)
    check(bal <= max(w for _, w in rag) and len(rag) == len(lines), f"balanced (title) widest line {bal:.0f} <= ragged (body) {max(w for _, w in rag):.0f}")
    kern = lambda t: len(t) * 10.0 - (30.0 if t == "aaaa bb cc" else 0.0)       # the measured line is narrower than its pieces
    lines, err = LY.break_lines(["aaaa", "bb", "cc"], 80, 3, kern, balanced=True)
    check(err is None and lines == [("aaaa bb cc", 70.0)], "the measured width of the WHOLE line decides (not a sum of words)")
    lines, err = LY.break_lines(["a" * 20, "b"], 100, 3, w10, balanced=False)
    check(err and err[0] == "word_too_wide", "a piece wider than the line: error (never cut)")
    lines, err = LY.break_lines(["aaaa"] * 10, 100, 2, w10, balanced=False)
    check(err and err[0] == "text_overflow" and len(lines) == 5, "more lines than allowed: overflow error")

    print("\n== C layout of every text kind")
    for kind, displays in (("title", G.DISPLAYS["title"]), ("lower-third", ("overlay",)), ("info-card", G.DISPLAYS["info-card"]),
                           ("quote", G.DISPLAYS["quote"]), ("callout", ("overlay",))):
        for disp in displays:
            for lang in ("fa", "en"):
                sp = spec(kind, disp, lang)
                L = G.layout(sp, measured(sp))
                r = L["rect"]
                inside = L["status"] in ("OK", "WARN") and SA.inside(r, SA.ALLOWED) and not SA.intersects(r, SA.BAND)
                inner = L["inner"]
                fits = all(inner[0] - 1e-6 <= ln["x0"] and ln["x1"] <= inner[0] + inner[2] + 1e-6 for b in L["blocks"] for ln in b["lines"])
                al = {b["align"] for b in L["blocks"]}
                want = {"center"} if disp == "fullframe" and kind in ("title", "quote") else {"right" if lang == "fa" else "left"}
                check(inside and fits and al == want and L["measured"],
                      f"{kind} / {disp} / {lang}: {L['status']} box {r}, lines inside the box, aligned {sorted(al)}")
    sp = spec("lower-third", "overlay")
    L = G.layout(sp, measured(sp))
    check(abs(L["rect"][1] + L["rect"][3] - (SA.ALLOWED[1] + SA.ALLOWED[3] - LY.BOTTOM_GAP)) < 1e-6 and
          abs(L["rect"][0] + L["rect"][2] - (SA.ALLOWED[0] + SA.ALLOWED[2])) < 1e-6,
          f"Persian lower third: bottom-right, {LY.BOTTOM_GAP} px above the subtitle band {L['rect']}")
    check(L["rule"] and L["rule"][0] > L["inner"][0] + L["inner"][2] - 1e-6, "its accent rule is on the reading-start (right) side")
    sp = spec("lower-third", "overlay", "en")
    L = G.layout(sp, measured(sp))
    check(L["rect"][0] == SA.ALLOWED[0] and L["rule"][0] < L["inner"][0], "English lower third: bottom-left, rule on the left")
    sp = spec("info-card", "overlay")
    L = G.layout(sp, measured(sp))
    body = next(b for b in L["blocks"] if b["role"] == "body")
    check(all(ln["direction"] == "rtl" for ln in body["lines"]),
          "every line of a Persian paragraph is rtl, even one that starts with an English word")
    src = next(b for b in L["blocks"] if b["role"] == "source")
    check(src["lines"][0]["text"] == "منبع: مرکز آمار، ۲۰۲۴", f"the source line: {src['lines'][0]['text']}")
    check(len(body["lines"]) >= 2 and "\n" not in "".join(ln["text"] for ln in body["lines"]), "the body's explicit line break starts a new line")
    sp = spec("quote", "fullframe")
    L = G.layout(sp, measured(sp))
    t = [b["lines"][0]["text"] for b in L["blocks"]]
    check(t[0].startswith("«") and L["blocks"][0]["lines"][-1]["text"].endswith("»") and t[1] == "— یک ماهیگیر",
          f"quote marks and the attribution dash in the shown text: {t[:2]}")
    ys = [ln["baseline"] for b in L["blocks"] for ln in b["lines"]]
    check(ys == sorted(ys) and len(set(ys)) == len(ys), "baselines go down, one line each")
    sp = spec("callout", "overlay", place={"at": [600, 400]})
    L = G.layout(sp, measured(sp))
    check(L["rect"][0] >= 600 + LY.CALLOUT_GAP - 1e-6, f"a callout left of centre sits right of its point {L['rect']}")
    sp = spec("callout", "overlay", place={"at": [1500, 400]})
    L = G.layout(sp, measured(sp))
    check(L["rect"][0] + L["rect"][2] <= 1500 - LY.CALLOUT_GAP + 1e-6, f"... right of centre, left of it {L['rect']}")

    print("\n== D overflow, explicit boxes, measurement")
    sp = spec("lower-third", "overlay", place={"rect": [200, 600, 500, 60]})
    check("text_overflow" in [i["code"] for i in G.layout(sp, measured(sp))["issues"]], "text taller than an explicit box: overflow error")
    sp = spec("lower-third", "overlay", place={"rect": [200, 560, 860, 200]})
    L = G.layout(sp, measured(sp))
    check(L["status"] == "OK" and L["rect"] == [200.0, 560.0, 860.0, 200.0], "text that fits an explicit box: the box is kept")
    long_t = "واژه " * 60
    sp = spec("lower-third", "overlay", content={"title": long_t[:80].strip()})
    L = G.layout(sp, measured(sp))
    check("text_overflow" in [i["code"] for i in L["issues"]] and L["rect"] is None,
          "a lower-third name over its 2 lines (80 characters in an 860 px box): overflow error, nothing drawn, never shrunk")
    sp = spec("title", "overlay")
    check("text_not_measured" in [i["code"] for i in G.layout(sp, None)["issues"] if i["level"] == "error"], "final without measurement: error")
    sp = spec("title", "overlay", mode="draft")
    L = G.layout(sp, None)
    check(L["status"] == "WARN" and not L["measured"], "draft without measurement: an estimate, with a warning")
    sp = spec("info-card", "overlay")
    r1 = LY.requests(sp)
    r2 = LY.requests(sp, fake_measure(r1))
    check(r1 and all(TX.units(t) == [t] for t, *_ in r1),
          f"round 1 asks for single pieces only ({len(r1)})")
    check(set(r1) <= set(r2) and any(len(TX.units(t)) > 1 for t, *_ in r2), f"round 2 adds runs of pieces that may fit a line ({len(r2)})")
    sp = G.validate({"schema": "nfp.graphics/1", "id": "c", "lang": "fa", "kind": "counter", "content": {"title": "x"},
                     "data": {"value": 1, "source": "s1"}, "sources": SRC}, "fullframe")["graphic"]
    check(LY.requests(sp) and "layout_later" not in [i["code"] for i in G.layout(sp, measured(sp))["issues"]],
          "every data kind is laid out now (comparison / bar / column: G6, line / counter: G7)")
    a, b = G.layout(spec("info-card", "overlay"), measured(spec("info-card", "overlay"))), G.layout(spec("info-card", "overlay"), measured(spec("info-card", "overlay")))
    check(a == b and json.loads(json.dumps(a)) == a, "deterministic, plain JSON")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G2 TESTS PASSED" if not f else "GRAPHICS G2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
