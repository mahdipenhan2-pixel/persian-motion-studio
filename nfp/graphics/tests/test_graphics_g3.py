#!/usr/bin/env python3
"""G3 - SVG of the text kinds without a browser: contrast (WCAG) of the presets and of overrides (final error / draft
warning, large vs normal text, panel over black AND white), the drawn elements and their Director handles (data-p),
panel / rule / text exactly where the layout put them, full-frame background and accent rule inside the safe area,
callout leader from its box edge to its point, the draft badge only on a draft graphic, XML escaping, determinism, a
failed layout is never drawn, the preview page. Widths come from a fake, deterministic "measurement" (as in G2).
  python3 nfp/graphics/tests/test_graphics_g3.py
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(HERE)]
import graphics as G                      # noqa: E402
from graphics import render as R          # noqa: E402
from graphics import safearea as SA       # noqa: E402
from graphics import textlayout as LY     # noqa: E402
from test_graphics_g2 import measured     # noqa: E402

RESULTS = []
SRC = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار", "date": "2024", "verified": True}]


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def make(kind, display, lang="fa", **kw):
    d = {"schema": "nfp.graphics/1", "id": f"g.{kind}", "mode": "final", "lang": lang, "kind": kind}
    d.update({"title": {"content": {"title": "فصل اول: بندر قدیمی", "subtitle": "سال‌های ۱۳۳۰ تا ۱۳۴۰"}},
              "lower-third": {"content": {"title": "مریم احمدی", "subtitle": "Historian & writer <Tehran>"}},
              "info-card": {"content": {"title": "بندر", "body": "این بندر در سال ۱۳۳۲ بسته شد.", "source": "s1"}, "sources": SRC},
              "quote": {"content": {"body": "دریا همه چیز را به یاد دارد.", "attribution": "یک ماهیگیر", "source": "s1"}, "sources": SRC},
              "callout": {"content": {"body": "اسکلهٔ قدیمی"}, "place": {"at": [600, 400]}}}[kind])
    d.update(kw)
    r = G.validate(d, display, 120)
    assert r["graphic"], r["issues"]
    sp = r["graphic"]
    return sp, G.layout(sp, measured(sp))


def attrs_of(svg, p):
    m = re.search(r'<(\w+)[^>]*data-p="' + re.escape(p) + r'"[^>]*>', svg)
    return dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(0))) if m else None


def main():
    print("== A contrast")
    check(abs(R.ratio((0, 0, 0), (255, 255, 255)) - 21) < 1e-9 and abs(R.ratio((119, 119, 119), (255, 255, 255)) - 4.48) < 0.01,
          "WCAG ratio: black / white 21:1, #777 / white 4.48:1")
    for p in G.PRESETS:
        for disp in ("overlay", "fullframe"):
            sp, _ = make("info-card", disp, style={"preset": p})
            check(R.contrast(sp) == [], f"preset {p} / {disp}: every text role passes (overlay: panel over black and over white)")
    sp, lay = make("info-card", "overlay", style={"muted": "#6a6a6a"})
    iss = R.contrast(sp, lay)
    check([i["element"] for i in iss if i["level"] == "error"] == ["source"], f"final: a muted grey too dark for the panel is an error (source 18 px): {[i['message'] for i in iss][:1]}")
    sp, lay = make("info-card", "overlay", mode="draft", style={"muted": "#6a6a6a"})
    check([i["level"] for i in R.contrast(sp, lay)] == ["warning"], "draft: the same is a warning")
    # #8c8c8c on the dark panel over white (~(54,56,61)): ~3.5:1 - enough for large text (>= 24 px: the 30 px attribution),
    # not for normal text (the 18 px source line)
    sp, lay = make("quote", "overlay", style={"muted": "#8c8c8c"})
    roles = {i["element"] for i in R.contrast(sp, lay)}
    check(roles == {"source"}, f"large text (>= 24 px) needs 3:1, normal text 4.5:1 (flagged: {sorted(roles)})")
    sp, lay = make("title", "fullframe", style={"background": "#f4efe6"})
    check({i["element"] for i in R.contrast(sp, lay)} >= {"title", "subtitle"}, "full frame: text against its own background (light text on light: error)")

    print("\n== B the drawn elements")
    for kind, disps in (("title", ("fullframe", "overlay")), ("lower-third", ("overlay",)), ("info-card", ("fullframe", "overlay")),
                        ("quote", ("fullframe", "overlay")), ("callout", ("overlay",))):
        for disp in disps:
            for lang in ("fa", "en"):
                sp, lay = make(kind, disp, lang)
                svg = R.render_svg(sp, lay)
                k = R.key_of(sp["id"])
                n_lines = sum(len(b["lines"]) for b in lay["blocks"])
                texts = re.findall(r'<text data-p="gx-' + re.escape(k) + r'-(\w+)-(\d+)"', svg)
                ok = len(texts) == n_lines and svg.startswith("<svg") and 'width="1920"' in svg
                if disp == "overlay":
                    a = attrs_of(svg, f"gx-{k}-panel")
                    ok = ok and a and [float(a[x]) for x in ("x", "y", "width", "height")] == [round(v, 3) for v in lay["rect"]]
                else:
                    a, r = attrs_of(svg, f"gx-{k}-bg"), attrs_of(svg, f"gx-{k}-rule")
                    rr = [float(r[x]) for x in ("x", "y", "width", "height")]
                    ok = ok and a and a["width"] == "1920" and SA.inside(rr, SA.ALLOWED) and rr[1] + rr[3] < lay["rect"][1]
                check(ok, f"{kind} / {disp} / {lang}: {n_lines} lines = {len(texts)} <text>, " +
                          ("panel = the layout's box" if disp == "overlay" else "full-frame background, accent rule above the text inside the safe area"))
    sp, lay = make("info-card", "overlay")
    svg = R.render_svg(sp, lay)
    k = R.key_of(sp["id"])
    r = attrs_of(svg, f"gx-{k}-rule")
    check([float(r[x]) for x in ("x", "y", "width", "height")] == lay["rule"] and float(r["x"]) > lay["inner"][0] + lay["inner"][2] - 1e-6,
          "the accent rule is the layout's, on the right of a Persian card")
    ln = lay["blocks"][0]["lines"][0]
    t = attrs_of(svg, f"gx-{k}-title-0")
    check(float(t["x"]) == ln["x1"] and t["direction"] == "rtl" and t["text-anchor"] == "start" and float(t["y"]) == ln["baseline"],
          "an rtl line starts at its right end (x1) on its baseline; its direction is set")
    sp, lay = make("lower-third", "overlay", "en", content={"title": "Maryam Ahmadi", "subtitle": "Historian & writer <Tehran>"})
    svg = R.render_svg(sp, lay)
    t = attrs_of(svg, f"gx-{R.key_of(sp['id'])}-title-0")
    check(float(t["x"]) == lay["blocks"][0]["lines"][0]["x0"] and t["direction"] == "ltr", "an ltr line starts at its left end (x0)")
    check("Historian &amp; writer &lt;Tehran&gt;" in svg and "<Tehran>" not in svg, "text is XML-escaped")
    sp, lay = make("callout", "overlay")
    svg = R.render_svg(sp, lay)
    k = R.key_of(sp["id"])
    lines = re.findall(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"', svg)
    (x0, y0, x1, y1) = map(float, lines[1])
    rect = lay["rect"]
    on_edge = abs(x0 - rect[0]) < 1e-6 or abs(x0 - rect[0] - rect[2]) < 1e-3
    check(len(lines) == 2 and lines[0] == lines[1] and (x1, y1) == (600.0, 400.0) and on_edge and attrs_of(svg, f"gx-{k}-dot")["cx"] == "600",
          f"callout: leader (outline + accent line) from the box edge ({x0:g}, {y0:g}) to its point (600, 400), dot on the point")
    check(R.leader([100, 100, 200, 100], [150, 150]) is None, "a point inside the box: no leader")

    print("\n== C draft badge, determinism, failures, preview")
    sp, lay = make("info-card", "overlay", mode="draft", content={"body": "در سال ۱۳۳۲ بسته شد."}, sources=[])
    check(sp["draft_badge"] and lay["badge"] and SA.inside(lay["badge"]["rect"], SA.ALLOWED) and not SA.intersects(lay["badge"]["rect"], lay["rect"]),
          f"a draft graphic with an unsourced number gets the draft badge, outside its box, in the safe area {lay['badge'] and lay['badge']['rect']}")
    svg = R.render_svg(sp, lay)
    check(f'data-p="gx-{R.key_of(sp["id"])}-badge"' in svg and "پیش‌نویس" in svg, "the badge is drawn: «پیش‌نویس»")
    sp2, lay2 = make("info-card", "overlay")
    check(not lay2["badge"] and "-badge" not in R.render_svg(sp2, lay2), "a final (sourced) graphic has no badge")
    sp, lay = make("lower-third", "overlay", place={"rect": [96, 54, 600, 200]})
    check(lay["badge"] is None, "(no badge on a final graphic)")
    sp, lay = make("info-card", "overlay", mode="draft", place={"rect": [96, 54, 600, 260]}, content={"body": "در سال ۱۳۳۲"}, sources=[])
    check(lay["badge"]["rect"][1] > lay["rect"][1] + lay["rect"][3], "no room above a box at the top of the safe area: the badge goes below it")
    a, b = make("quote", "fullframe"), make("quote", "fullframe")
    check(R.render_svg(*a) == R.render_svg(*b), "the same graphic gives the same bytes")
    check(R.key_of("a.b") != R.key_of("a_b") and R.key_of("map-1") == "map-1", "handles are one-to-one ('a.b' and 'a_b' differ)")
    sp, lay = make("title", "overlay")
    check(R.render_svg(sp, lay, font_css="@font-face{}").count("<style>@font-face{}</style>") == 1
          and not R.render_svg(sp, lay, standalone=False).startswith("<svg"), "standalone <svg> carries the font CSS; the fragment is a <g>")
    bad = G.layout(sp, None)
    bad["status"] = "FAIL"
    try:
        R.render_svg(sp, bad)
        check(False, "a failed layout is never drawn")
    except ValueError:
        check(True, "a failed layout is never drawn (ValueError)")
    html = R.preview_html([make("title", "fullframe"), make("lower-third", "overlay")])
    check(html.count("<section>") == 2 and html.count("<figure>") == 6 and html.count('stroke-dasharray="12 8"') == 6,
          "preview: each graphic over 3 backgrounds, with the safe-area guide")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G3 TESTS PASSED" if not f else "GRAPHICS G3 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
