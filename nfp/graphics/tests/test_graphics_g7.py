#!/usr/bin/env python3
"""G7 - line chart and counter without a browser (a fake, deterministic "measurement" as in G2):
  line     nice ticks; the vertical domain always contains zero and every value; every point exactly at its value
           (y = zero - value x px_per_unit); points evenly spaced in data order (Persian: first on the right); ALL points
           drawn even when x labels are thinned; shown x labels apart; a stronger zero line, negatives below it; a legend
           only for several series, each series its own colour AND dash; nothing covers anything; errors for too tall
  counter  the last state is exactly format_number(value); it counts over the enter frames only (type none: no count);
           from / to / down / negative / decimals; every state inside the box; the G4 keys show exactly one state per
           frame (the planned one) and the final value from the end of the enter on
  python3 nfp/graphics/tests/test_graphics_g7.py
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(HERE)]
import graphics as G                      # noqa: E402
from graphics import animate as A         # noqa: E402
from graphics import linecounter as LC    # noqa: E402
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


def line(lang="fa", display="fullframe", series=None, n=12, mode="final", **kw):
    xs = [str(1390 + i).translate(FA) if lang == "fa" else str(2011 + i) for i in range(n)]
    series = series or [[4, 6.5, 3, -2, -5.5, 1, 7, 9.5, 8, 12, 10.5, 14][:n]]
    labels = (["بندرعباس", "بوشهر", "چابهار", "انزلی"] if lang == "fa" else ["Bandar Abbas", "Bushehr", "Chabahar", "Anzali"])
    d = {"schema": "nfp.graphics/1", "id": "g-line", "mode": mode, "lang": lang, "kind": "line",
         "content": {"title": "تجارت بنادر" if lang == "fa" else "Harbour trade"},
         "data": {"source": "s1", "unit": "%", "format": {"decimals": 1},
                  "series": [dict({"points": [{"x": x, "value": v} for x, v in zip(xs, vals)]}, **({"label": labels[j]} if len(series) > 1 else {}))
                             for j, vals in enumerate(series)]}, "sources": SRC}
    d.update(kw)
    r = G.validate(d, display, 120)
    if not r["graphic"]:
        return None, r
    sp = r["graphic"]
    return sp, G.layout(sp, measured(sp))


def counter(lang="fa", display="fullframe", value=48600, frm=None, decimals=0, unit=None, anim=None, **kw):
    data = {"value": value, "source": "s1", "format": {"decimals": decimals}}
    if frm is not None:
        data["from"] = frm
    if unit:
        data["unit"] = unit
    d = {"schema": "nfp.graphics/1", "id": "g-count", "mode": "final", "lang": lang, "kind": "counter",
         "content": {"title": "کشتی در سال" if lang == "fa" else "Ships a year"}, "data": data, "sources": SRC,
         "animation": anim or {"in": {"type": "fade", "frames": 30}, "out": {"type": "fade", "frames": 9}}}
    d.update(kw)
    r = G.validate(d, display, 120)
    sp = r["graphic"]
    return sp, G.layout(sp, measured(sp))


def tboxes(lay):
    return [(b["role"], [ln["x0"], ln["baseline"] - b["ascent"], ln["x1"], ln["baseline"] + b["descent"]]) for b in lay["blocks"] for ln in b["lines"]]


def hit(a, b, tol=0.5):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def main():
    print("== A ticks")
    for lo, hi, want in ((0, 18, [0, 5, 10, 15, 20]), (-5.5, 18, [-10, 0, 10, 20]), (0, 1250, [0, 500, 1000, 1500]), (-3, 0, [-3, -2, -1, 0]),
                         (0, 0.04, [0, 0.01, 0.02, 0.03, 0.04]), (0, 0, [0, 1])):
        t, step, dec = LC.nice_ticks(lo, hi)
        check([round(x, 6) for x in t] == want, f"nice ticks for [{lo}, {hi}]: {t} (step {step:g}, {dec} decimals)")
    check(LC.nice_ticks(0, 0.04)[2] == 2 and LC.nice_ticks(0, 25)[2] == 0, "tick decimals follow the step (0.01 -> 2, 5 -> 0)")

    print("\n== B line: honest geometry")
    for lang in ("fa", "en"):
        for disp in ("fullframe", "overlay"):
            sp, lay = line(lang, disp, series=[[4, 6.5, 3, -2, -5.5, 1, 7, 9.5, 8, 12, 10.5, 14], [2, 1, 0, -1, -3, -1, 2, 3, 4, 3.5, 5, 6]])
            vals = [p["value"] for s in sp["data"]["series"] for p in s["points"]]
            sc = lay["scale"]
            exact = all(abs(y - (sc["zero"] - p["value"] * sc["px_per_unit"])) < 1e-3
                        for ln, s in zip(lay["lines"], sp["data"]["series"]) for (_, y), p in zip(ln["points"], s["points"]))
            dom = sc["domain"][0] <= min(0, min(vals)) and sc["domain"][1] >= max(0, max(vals))
            xs = [x for x, _ in lay["lines"][0]["points"]]
            steps = [b - a for a, b in zip(xs, xs[1:])]
            even = max(steps) - min(steps) < 0.002 and (steps[0] < 0) == (lang == "fa")      # (coordinates are rounded to 0.001 px)
            zero = [g for g in lay["grid"] if g["zero"]]
            ticks = [b["lines"][0]["text"] for b in lay["blocks"] if b["role"].startswith("tick-")]
            _, step, dec = LC.nice_ticks(min(0, min(vals)), max(0, max(vals)))
            want_t = [TX.format_number(t, dec, sp["data"]["format"]["digits"], "%") for t in LC.nice_ticks(min(0, min(vals)), max(0, max(vals)))[0]]
            check(lay["status"] in ("OK", "WARN") and exact and dom and even and len(zero) == 1 and abs(zero[0]["y"] - sc["zero"]) < 1e-3 and ticks == want_t,
                  f"line {lang} / {disp}: every point at y = zero - value x {sc['px_per_unit']:.2f}; domain {sc['domain']} contains 0 and all values; "
                  f"evenly spaced, first point on the {'right' if lang == 'fa' else 'left'}; one zero line; ticks {ticks[:2]}...")
    xs40 = [str(2000 + i) for i in range(40)]
    d = {"schema": "nfp.graphics/1", "id": "g40", "mode": "final", "lang": "en", "kind": "line", "content": {"title": "Ships per month"},
         "data": {"source": "s1", "format": {"decimals": 0}, "series": [{"points": [{"x": x, "value": 1200 + (i * 37) % 400} for i, x in enumerate(xs40)]}]},
         "sources": SRC}
    sp = G.validate(d, "overlay", 120)["graphic"]
    lay = G.layout(sp, measured(sp))
    shown = sorted((b["lines"][0]["x0"], b["lines"][0]["x1"], b["point"]) for b in lay["blocks"] if b["role"].startswith("xlabel-"))
    apart = all(b[0] >= a[1] + LC.X_LABEL_GAP - 1e-6 for a, b in zip(shown, shown[1:]))
    check(len(lay["lines"][0]["points"]) == 40 and 2 <= len(shown) < 40 and apart and shown[0][2] == 0 and not lay["lines"][0]["markers"],
          f"40 points: all 40 drawn, {len(shown)} x labels shown (thinned, {LC.X_LABEL_GAP} px apart, the first included), no markers (> {LC.MARKERS_MAX})")
    sp, lay = line("fa", series=[[3, 5, 2]], n=3)
    check(lay["lines"][0]["markers"] and not lay["swatches"] and not [b for b in lay["blocks"] if b["role"].startswith("legend")],
          "one short series: point markers, no legend")
    sp, lay = line("en", series=[[1, 2, 3], [3, 2, 1], [2, 2, 2], [0, 1, 0]], n=3)
    st = {(ln["stroke"], ln["dash"]) for ln in lay["lines"]}
    leg = [b["lines"][0]["text"] for b in lay["blocks"] if b["role"].startswith("legend-")]
    check(len(st) == 4 and len({d for _, d in st}) >= 3 and leg == ["Bandar Abbas", "Bushehr", "Chabahar", "Anzali"] and len(lay["swatches"]) == 4,
          f"4 series: 4 colours and 3 dash patterns (told apart without colour), a legend in order {leg}")
    sp, lay = line("fa", series=[[-5, -2, -8]], n=3)
    zero_y = lay["scale"]["zero"]
    check(all(y > zero_y for _, y in lay["lines"][0]["points"]) and lay["scale"]["domain"][1] == 0, "all values negative: the line under the zero line, the domain up to 0")
    sp, lay = line("en", series=[[0, 0, 0]], n=3)
    check(lay["status"] in ("OK", "WARN") and len({y for _, y in lay["lines"][0]["points"]}) == 1, "all zero: a flat line on the zero line")

    print("\n== C line: nothing covers anything; errors")
    for lang in ("fa", "en"):
        for disp in ("fullframe", "overlay"):
            sp, lay = line(lang, disp, series=[[4, 6.5, 3, -2, -5.5, 1, 7, 9.5, 8, 12, 10.5, 14], [2, 1, 0, -1, -3, -1, 2, 3, 4, 3.5, 5, 6],
                                               [0, 0.5, 1, 2, 4, 6, 5, 8, 11, 13, 15, 18]], content={"title": "x" if lang == "en" else "عنوان", "subtitle": "y"})
            bx = tboxes(lay)
            tt = sum(hit(a[1], b[1]) for i, a in enumerate(bx) for b in bx[i + 1:])
            r_ = lay["rect"]
            ins = all(SA.inside([x0, y0, x1 - x0, y1 - y0], r_, tol=0.5) for _, (x0, y0, x1, y1) in bx) and \
                all(SA.inside([x - 1, y - 1, 2, 2], r_) for ln in lay["lines"] for x, y in ln["points"])
            check(lay["status"] in ("OK", "WARN") and tt == 0 and ins and SA.inside(r_, SA.ALLOWED) and not SA.intersects(r_, SA.BAND),
                  f"line {lang} / {disp}, 3 series + subtitle + legend: no text over text ({tt}), all inside its box and the safe area")
    sp, lay = line("en", "overlay", place={"rect": [96, 54, 800, 300]})
    check("chart_too_tall" in [i["code"] for i in lay["issues"]], "a line chart in a 300 px box: chart_too_tall (never squeezed below its minimum)")
    sp, r = line("en", series=[[1, 2], [1, 2, 3]], n=3)
    check(sp is None, "series of different lengths: refused (G1)")

    print("\n== D counter")
    sp, lay = counter("fa", value=48600)
    cnt = lay["count"]
    final = cnt["states"][cnt["final"]]["text"]
    check(final == TX.format_number(48600, 0, "fa") and cnt["frames"][-1] == cnt["final"] and len(cnt["frames"]) == 31 and
          cnt["states"][cnt["frames"][0]]["text"] == TX.format_number(0, 0, "fa"),
          f"counts 0 -> 48,600 over the 30 enter frames: {len(cnt['frames'])} frame states, first {cnt['states'][0]['text']!r}, last exactly {final!r}")
    vals = [float(cnt["states"][i]["text"].replace("⁦", "").replace("⁩", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٬", "0123456789,")).replace(",", ""))
            for i in cnt["frames"]]
    check(all(b >= a for a, b in zip(vals, vals[1:])) and vals[-1] == 48600, "the shown numbers never go back while counting up; it ends on the data")
    sp, lay = counter("en", value=-2.5, frm=10, decimals=1, unit="%")
    cnt = lay["count"]
    check(cnt["states"][cnt["final"]]["text"] == "−2.5%" and cnt["states"][0]["text"] == "10.0%", "counting down from 10.0% to −2.5% (negative, decimals, unit)")
    sp, lay = counter("en", anim={"in": {"type": "none"}, "out": {"type": "fade", "frames": 9}})
    check(len(lay["count"]["states"]) == 1 and lay["count"]["states"][0]["text"] == "48,600", "enter type none: no counting, the value at once")
    sp, lay = counter("fa", "overlay", value=1234567.891, decimals=2, unit="کیلومتر")
    cnt = lay["count"]
    r_ = lay["rect"]
    check(all(r_[0] - 1e-6 <= s["x0"] and s["x1"] <= r_[0] + r_[2] + 1e-6 for s in cnt["states"]) and SA.inside(r_, SA.ALLOWED),
          f"every one of the {len(cnt['states'])} shown numbers fits inside the box (sized to the widest)")
    keys = A.plan(sp, lay, 30, 120)
    k = R.key_of(sp["id"])
    vis = {}
    for f in range(30, 120):
        shown = set()
        for j in range(len(cnt["states"])):
            p = f"gx-{k}-count-{j}"
            st = "inline" if j == cnt["final"] else "none"
            for x in keys:
                if x["p"] == p and x["frame"] <= f:
                    st = x["value"]
            if st == "inline":
                shown.add(j)
        vis[f] = shown
    n_in = sp["animation"]["in"]["frames"]
    ok = all(vis[f] == {cnt["frames"][f - 30]} for f in range(30, 30 + n_in)) and all(vis[f] == {cnt["final"]} for f in range(30 + n_in, 120))
    check(ok, f"G4 keys: exactly one number per frame, the planned one while counting (frames 30..{29 + n_in}), the final value from {30 + n_in} to the clip's end")
    svg = R.render_svg(sp, lay)
    check(svg.count(f'data-p="gx-{k}-count-') == len(cnt["states"]) and svg.count("display:none") == len(cnt["states"]) - 1,
          "a still drawing shows only the final value (the other states hidden)")
    check({i["element"] for i in R.contrast(*counter("en", style={"text": "#2a2d33"}))} >= {"count"}, "the counter's number is contrast-checked")
    a, b = counter("fa"), counter("fa")
    check(R.render_svg(*a) == R.render_svg(*b) and json.loads(json.dumps(a[1])) == a[1], "deterministic, plain JSON")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G7 TESTS PASSED" if not f else "GRAPHICS G7 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
