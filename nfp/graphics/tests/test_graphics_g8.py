#!/usr/bin/env python3
"""G8 - the whole engine, across its stages, without a browser (a fake, deterministic "measurement" as in G2):
  M  every kind x every display it allows x Persian / English x every preset: lays out (OK / WARN), passes contrast,
     sits in the safe area out of the subtitle band, draws deterministically, animates inside its clip
  Z  a seeded fuzz of 900 documents (random kinds, languages, presets, scales, texts with half-spaces / no-break spaces /
     mixed scripts, values from 1e-7 to 1e6 with signs, 1..60 points, 1..4 series, anchors, animations): nothing crashes -
     a document is drawn or refused with a stated reason - and every drawn one keeps the engine's promises:
       inside the safe area / its box, no text over text, bars and columns |value| x scale from zero, line points at their
       values with zero in the domain, the counter ending exactly on the data, animation keys only inside the clip
       (the root hidden from its end), a final graphic never reported unmeasured when everything it draws was measured
  python3 nfp/graphics/tests/test_graphics_g8.py
"""
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(HERE)]
import graphics as G                      # noqa: E402
from graphics import animate as A         # noqa: E402
from graphics import render as R          # noqa: E402
from graphics import safearea as SA       # noqa: E402
from graphics import text as TX           # noqa: E402
from test_graphics_g2 import measured     # noqa: E402

RESULTS = []
SRC = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار", "date": "2023", "verified": True}]
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sample(kind, lang):
    fa = lang == "fa"
    if kind in ("title", "lower-third"):
        return {"content": {"title": "مریم احمدی" if fa else "Maryam Ahmadi", "subtitle": "تاریخ‌نگار، دانشگاه تهران" if fa else "Historian, University of Tehran"}}
    if kind == "info-card":
        return {"content": {"title": "بندر" if fa else "The harbour", "body": "این بندر در سال ۱۳۳۲ بسته شد و امروز موزه است." if fa else
                            "Closed in 1953, the harbour reopened as a museum.", "source": "s1"}, "sources": SRC}
    if kind == "quote":
        return {"content": {"body": "دریا همه چیز را به یاد دارد." if fa else "The sea remembers everything.", "attribution": "یک ماهیگیر" if fa else "A fisherman",
                            "source": "s1"}, "sources": SRC}
    if kind == "callout":
        return {"content": {"body": "اسکلهٔ قدیمی" if fa else "The old pier"}, "place": {"at": [700, 420]}}
    labels = ["تهران", "مشهد", "اصفهان", "کرج"] if fa else ["Tehran", "Mashhad", "Isfahan", "Karaj"]
    if kind in ("comparison", "bar", "column"):
        vals = [54.2, 18.7, 9.1, 0] if kind == "comparison" else [9.04, -3.37, 2.24, 0]
        return {"content": {"title": "آمار" if fa else "Figures"}, "sources": SRC,
                "data": {"source": "s1", "unit": "%", "format": {"decimals": 1}, "items": [{"label": l, "value": v} for l, v in zip(labels, vals)]}}
    if kind == "line":
        xs = [str(1390 + i).translate(FA) if fa else str(2011 + i) for i in range(8)]
        return {"content": {"title": "روند" if fa else "Trend"}, "sources": SRC,
                "data": {"source": "s1", "format": {"decimals": 1}, "series": [
                    {"label": labels[0], "points": [{"x": x, "value": v} for x, v in zip(xs, [4, 6.5, -2, 3, 8, 7, 9, 12])]},
                    {"label": labels[1], "points": [{"x": x, "value": v} for x, v in zip(xs, [1, 2, 2, 3, 2, 4, 5, 4])]}]}}
    return {"content": {"title": "کشتی در سال" if fa else "Ships a year"}, "sources": SRC, "data": {"value": 48600, "source": "s1"},
            "animation": {"in": {"type": "fade", "frames": 30}, "out": {"type": "fade", "frames": 9}}}


def promises(sp, lay, start=20, end=140):
    """[] when the drawn graphic keeps every promise, else what it breaks"""
    bad = []
    r = lay["rect"]
    if not (SA.inside(r, SA.ALLOWED, tol=1e-6) and not SA.intersects(r, SA.BAND)):
        bad.append("box outside the safe area / in the band")
    if lay.get("badge") and not SA.inside(lay["badge"]["rect"], SA.ALLOWED, tol=1e-6):
        bad.append("badge outside the safe area")
    boxes = [(b["role"], [ln["x0"], ln["baseline"] - b["ascent"], ln["x1"], ln["baseline"] + b["descent"]]) for b in lay["blocks"] for ln in b["lines"]]
    for role, (x0, y0, x1, y1) in boxes:
        if not SA.inside([x0, y0, x1 - x0, y1 - y0], r, tol=0.5):
            bad.append(f"{role} outside its box")
            break
    for i, (ra, a) in enumerate(boxes):
        if any(a[0] < b[2] - 0.5 and b[0] < a[2] - 0.5 and a[1] < b[3] - 0.5 and b[1] < a[3] - 0.5 for _, b in boxes[i + 1:]):
            bad.append(f"{ra} over another text")
            break
    k = sp["kind"]
    if k in ("comparison", "bar", "column"):
        s = lay["scale"]
        ax = 3 if k == "column" else 2
        if any(abs(b["rect"][ax] - abs(it["value"]) * s["px_per_unit"]) > 1e-3 for b, it in zip(lay["bars"], sp["data"]["items"])):
            bad.append("a bar is not |value| x scale")
        want = [TX.format_number(it["value"], sp["data"]["format"]["decimals"], sp["data"]["format"]["digits"], sp["data"]["unit"]) for it in sp["data"]["items"]]
        got = [next(b for b in lay["blocks"] if b["role"] == f"value-{i}")["lines"][0]["text"] for i in range(len(want))]
        if got != want:
            bad.append("a value label is not the data")
    if k == "line":
        s = lay["scale"]
        vals = [p["value"] for se in sp["data"]["series"] for p in se["points"]]
        if not (s["domain"][0] <= min(0, min(vals)) and s["domain"][1] >= max(0, max(vals))):
            bad.append("the domain misses zero or a value")
        if any(abs(y - (s["zero"] - p["value"] * s["px_per_unit"])) > 1e-3 for ln, se in zip(lay["lines"], sp["data"]["series"])
               for (_, y), p in zip(ln["points"], se["points"])):
            bad.append("a point is not at its value")
        if sum(len(ln["points"]) for ln in lay["lines"]) != len(vals):
            bad.append("a point is missing")
    if k == "counter":
        c = lay["count"]
        want = TX.format_number(sp["data"]["value"], sp["data"]["format"]["decimals"], sp["data"]["format"]["digits"], sp["data"]["unit"])
        if c["states"][c["final"]]["text"] != want or c["frames"][-1] != c["final"]:
            bad.append("the counter does not end on the data")
        if any(not (r[0] - 1e-6 <= st["x0"] and st["x1"] <= r[0] + r[2] + 1e-6) for st in c["states"]):
            bad.append("a counter state outside its box")
    keys = A.plan(sp, lay, start, end)
    root = f"gx-{R.key_of(sp['id'])}"
    if any(not (start <= x["frame"] and x["frame"] + x["frames"] <= end) for x in keys if not (x["p"] == root and x["frame"] == 0)):
        bad.append("an animation key outside the clip")
    if not any(x["p"] == root and x["frame"] == end and x["value"] == "none" for x in keys):
        bad.append("not hidden from the clip's end")
    if R.render_svg(sp, lay) != R.render_svg(sp, lay):
        bad.append("not deterministic")
    return bad


def main():
    print("== M every kind x display x language x preset")
    n = 0
    for kind in G.KINDS:
        bad = []
        for disp in G.DISPLAYS[kind]:
            for lang in ("fa", "en"):
                for preset in G.PRESETS:
                    d = dict({"schema": "nfp.graphics/1", "id": f"m-{kind}", "mode": "final", "lang": lang, "kind": kind, "style": {"preset": preset}},
                             **sample(kind, lang))
                    r = G.validate(d, disp, 120)
                    if not r["graphic"]:
                        bad.append((disp, lang, preset, [i["code"] for i in r["issues"]]))
                        continue
                    sp = r["graphic"]
                    lay = G.layout(sp, measured(sp))
                    if lay["status"] == "FAIL" or R.contrast(sp, lay):
                        bad.append((disp, lang, preset, [i["code"] for i in lay["issues"] + R.contrast(sp, lay)]))
                        continue
                    p = promises(sp, lay)
                    if p:
                        bad.append((disp, lang, preset, p))
                    n += 1
        check(not bad, f"{kind}: every display / language / preset draws and keeps its promises {bad[:2]}")
    check(n == sum(len(G.DISPLAYS[k]) for k in G.KINDS) * 2 * len(G.PRESETS), f"{n} combinations drawn")

    print("\n== Z seeded fuzz")
    rnd = random.Random(8)
    words = {"fa": ["بندر", "تهران", "سال", "۱۳۳۲", "کشتی", "می‌روند", "را", "،", "(visitors)", "Iran", "۴۰ هزار"],
             "en": ["harbour", "Tehran", "1953", "ships", "rebuilt", "(بندر)", "—", "and", "the", "storm"]}
    txt = lambda lang, k: " ".join(rnd.choice(words[lang]) for _ in range(k))
    num = lambda: rnd.choice([0, 0.004, -3.5, 12, 1e6, 48600, -0.5, 7.25, 99999.99, 1e-7])
    crashes, drawn, refused, broken, spurious = [], 0, 0, [], 0
    for it in range(900):
        lang = rnd.choice(["fa", "en"])
        kind = rnd.choice(G.KINDS)
        disp = rnd.choice(G.DISPLAYS[kind])
        d = {"schema": "nfp.graphics/1", "id": f"f{it}", "mode": rnd.choice(["draft", "final"]), "lang": lang, "kind": kind, "sources": SRC,
             "style": {"preset": rnd.choice(list(G.PRESETS)), "scale": rnd.choice([0.75, 1, 1.25, 1.5])}}
        if kind in ("title", "lower-third"):
            c = {"title": txt(lang, rnd.randint(1, 9)), "subtitle": txt(lang, rnd.randint(1, 12))}
        elif kind == "info-card":
            c = {"title": txt(lang, 3), "body": txt(lang, rnd.randint(1, 50)), "source": "s1"}
        elif kind == "quote":
            c = {"body": txt(lang, rnd.randint(1, 40)), "attribution": txt(lang, 3), "source": "s1"}
        elif kind == "callout":
            c = {"body": txt(lang, rnd.randint(1, 15)), "source": "s1"}
            d["place"] = {"at": [rnd.uniform(0, 1920), rnd.uniform(0, 829)]}
        elif kind == "counter":
            c = {"title": txt(lang, 3)}
            d["data"] = {"value": num(), "from": num(), "source": "s1", "format": {"decimals": rnd.randint(0, 3)}}
            u = rnd.choice([None, "%", "km"])
            if u:
                d["data"]["unit"] = u
        elif kind == "line":
            n_, ns = rnd.randint(2, 60), rnd.randint(1, 4)
            d["data"] = {"source": "s1", "format": {"decimals": rnd.randint(0, 3)},
                         "series": [dict({"points": [{"x": str(2000 + i), "value": num()} for i in range(n_)]}, **({"label": txt(lang, 2)} if ns > 1 else {}))
                                    for _ in range(ns)]}
            c = {"title": txt(lang, 4)}
        else:
            lo, hi = {"comparison": (2, 4), "bar": (1, 12), "column": (1, 12)}[kind]
            d["data"] = {"source": "s1", "format": {"decimals": rnd.randint(0, 3)},
                         "items": [{"label": f"{txt(lang, 1)}{i}", "value": abs(num()) if kind == "comparison" else num()} for i in range(rnd.randint(lo, hi))]}
            c = {"title": txt(lang, 3)}
        if rnd.random() < 0.3 and disp == "overlay" and kind != "callout":
            d["place"] = {"anchor": rnd.choice(["top-left", "bottom", "right", "center", "bottom-start"])}
        if rnd.random() < 0.3:
            d["animation"] = {"in": {"type": rnd.choice(["none", "fade", "pop", "wipe", "slide"]), "frames": rnd.randint(1, 40)},
                              "out": {"type": rnd.choice(["fade", "wipe"]), "frames": rnd.randint(1, 30)}}
        d["content"] = c
        try:
            r = G.validate(d, disp, 120)
            if not r["graphic"]:
                refused += 1
                continue
            sp = r["graphic"]
            lay = G.layout(sp, measured(sp))
            if any(i["code"] == "text_not_measured" for i in lay["issues"]):
                spurious += 1
            if lay["status"] == "FAIL":
                refused += 1
                continue
            R.contrast(sp, lay)
            p = promises(sp, lay)
            if p:
                broken.append((d["id"], kind, disp, p))
            drawn += 1
        except Exception as e:                                      # noqa: BLE001 - the point of the fuzz
            crashes.append((d["id"], kind, disp, repr(e)[:80]))
    check(not crashes, f"900 random documents: {drawn} drawn, {refused} refused with a stated reason, {len(crashes)} crashes {crashes[:2]}")
    check(not broken, f"every drawn one keeps every promise (safe area, no overlap, honest data, animation in its clip) {broken[:2]}")
    check(spurious == 0, f"no graphic is reported unmeasured when all its drawn text was measured ({spurious})")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G8 TESTS PASSED" if not f else "GRAPHICS G8 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
