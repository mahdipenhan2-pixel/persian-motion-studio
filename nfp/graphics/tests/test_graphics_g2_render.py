#!/usr/bin/env python3
"""G2 - REAL text measurement and layout in the local Chromium with the film's local fonts (Vazirmatn + Inter woff2;
nothing is downloaded): measuring is deterministic and records its browser / fonts, the faces really load, a character
none of the faces has is refused (never a silent system font), and for a set of Persian / English / mixed graphics the
lines the browser draws are exactly where the layout put them (span, baseline box), never wider than their box, in the
right reading order (Persian right to left, English left to right, a Persian paragraph keeps its direction on a line that
starts with an English word, digits left to right).
  python3 nfp/graphics/tests/test_graphics_g2_render.py --fonts <folder with the woff2 files>
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path.insert(0, str(NFP))
import graphics as G                              # noqa: E402
from graphics import safearea as SA               # noqa: E402
from graphics import text as TX                   # noqa: E402
from graphics.tools import measure as MS          # noqa: E402

RESULTS = []
JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const pages = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  const out = [];
  for (const html of pages) {
    await p.setContent(html);
    out.push(await p.evaluate(async () => {
      await document.fonts.ready;
      const loaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight).sort();
      const lines = [...document.querySelectorAll('text')].map(t => {
        const n = t.getNumberOfChars(), xs = [];
        for (let i = 0; i < n; i++) { const a = t.getStartPositionOfChar(i).x, e = t.getEndPositionOfChar(i).x; xs.push([Math.min(a, e), Math.max(a, e)]); }
        const bb = t.getBBox();
        return { id: t.dataset.id, text: t.textContent, len: t.getComputedTextLength(), box: [bb.x, bb.y, bb.x + bb.width, bb.y + bb.height], xs };
      });
      return { loaded, lines };
    }));
  }
  await b.close();
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


SRC = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار", "date": "2024", "verified": True},
       {"id": "s2", "title": "Harbour records", "publisher": "Port Authority", "date": "2019", "verified": True}]
DOCS = [
    ("fa-info", "overlay", {"lang": "fa", "kind": "info-card", "content": {
        "title": "بندر قدیمی", "body": "این بندر در سال ۱۳۳۲ بسته شد و امروز موزه‌ای است که هر سال بیش از ۴۰ هزار بازدیدکننده (visitors) دارد.",
        "source": "s1"}, "sources": SRC[:1]}),
    ("fa-lt", "overlay", {"lang": "fa", "kind": "lower-third", "content": {"title": "مریم احمدی", "subtitle": "Historian, University of Tehran"}}),
    ("en-lt", "overlay", {"lang": "en", "kind": "lower-third", "content": {"title": "Maryam Ahmadi", "subtitle": "تاریخ‌نگار، دانشگاه تهران"}}),
    ("fa-title", "fullframe", {"lang": "fa", "kind": "title", "content": {"title": "فصل اول: بندری که دریا آن را به یاد دارد و مردمانش هرگز فراموش نکردند",
                                                                           "subtitle": "سال‌های ۱۳۳۰ تا ۱۳۴۰"}}),
    ("fa-quote", "fullframe", {"lang": "fa", "kind": "quote", "content": {"body": "دریا همه چیز را به یاد دارد؛ حتی آنچه ما فراموش کرده‌ایم.",
                                                                         "attribution": "یک ماهیگیر پیر", "source": "s1"}, "sources": SRC[:1]}),
    ("en-callout", "overlay", {"lang": "en", "kind": "callout", "content": {"body": "The old pier, rebuilt in 1958 after the storm (بندر).", "source": "s2"},
                               "sources": SRC[1:], "place": {"at": [700, 380]}}),
    ("en-info", "fullframe", {"lang": "en", "kind": "info-card", "content": {
        "title": "The harbour", "body": "Closed in 1953, the harbour reopened as a museum.\nIt now welcomes more than 40,000 visitors a year.",
        "source": "s2"}, "sources": SRC[1:]}),
]


def svg_page(css, layouts):
    rows = []
    for gid, L in layouts:
        for b in L["blocks"]:
            for k, ln in enumerate(b["lines"]):
                x = ln["x1"] if ln["direction"] == "rtl" else ln["x0"]
                t = ln["text"].replace("&", "&amp;").replace("<", "&lt;")
                rows.append(f'<text data-id="{gid}|{b["role"]}|{k}" x="{x}" y="{ln["baseline"]}" font-family="{b["family"]}" '
                            f'font-size="{b["size"]}" font-weight="{b["weight"]}" direction="{ln["direction"]}" text-anchor="start" '
                            f'style="white-space: pre">{t}</text>')
    return ('<!doctype html><html><head><style>' + css + 'body{margin:0}</style></head><body>'
            '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">' + "".join(rows) + '</svg></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    a = ap.parse_args()
    fonts = Path(a.fonts)
    if not shutil.which("node"):
        check(False, "node is not installed: the real measurement cannot run")
        return finish()

    print("== M measuring")
    keys = [("بندر قدیمی", 30.0, 700, G.FONT_STACK["fa"]), ("The harbour 1953", 30.0, 400, G.FONT_STACK["en"]),
            ("۴۰ هزار", 30.0, 400, G.FONT_STACK["fa"])]
    m1, m2 = MS.measure(keys, fonts), MS.measure(keys, fonts)
    check(m1 == m2 and m1["browser"] and len(m1["fonts"]) == 4 and all(len(h) == 64 for h in m1["fonts"].values()),
          f"deterministic; records the browser ({m1['browser']}) and the sha256 of the 4 font files")
    w = {(x["text"], x["family"]): x["width"] for x in MS.measure([("2024", 30.0, 400, G.FONT_STACK["fa"]), ("2024", 30.0, 400, G.FONT_STACK["en"])], fonts)["items"]}
    check(all(v > 0 for v in w.values()), f"Latin digits measured in both font orders (fa {w[('2024', G.FONT_STACK['fa'])]:.2f} / en {w[('2024', G.FONT_STACK['en'])]:.2f} px)")
    try:
        MS.measure([("بندر 港口", 30.0, 400, G.FONT_STACK["fa"])], fonts)
        check(False, "a character the local fonts lack is refused")
    except MS.FallbackGlyphError as e:
        check("港口" in str(e), f"a character none of the local faces has is refused (it would be a system font): {str(e)[:70]}")
    try:
        MS.measure(keys, Path(a.fonts).parent / "no-such-fonts")
        check(False, "missing font files are refused")
    except FileNotFoundError:
        check(True, "missing font files: error (nothing is downloaded)")

    print("\n== L layout with real measurement")
    layouts = []
    for gid, disp, d in DOCS:
        doc = dict({"schema": "nfp.graphics/1", "id": gid, "mode": "final"}, **d)
        r = G.validate(doc, disp, 150)
        if not r["graphic"]:
            check(False, f"{gid}: valid document ({r['issues'][:2]})")
            continue
        sp = r["graphic"]
        L = G.layout(sp, MS.measure_graphic(sp, fonts))
        ok = L["status"] in ("OK", "WARN") and L["measured"] and not [i for i in L["issues"] if i["level"] == "error"]
        n = sum(len(b["lines"]) for b in L["blocks"])
        check(ok and SA.inside(L["rect"], SA.ALLOWED), f"{gid} ({disp}): {L['status']} {[i['code'] for i in L['issues']]}, {n} lines, box {L['rect']}")
        layouts.append((gid, L))
    css = MS.font_face_css(fonts)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "pages.json").write_text(json.dumps([svg_page(css, layouts)]), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        r = subprocess.run(["node", str(td / "probe.js"), str(td / "pages.json"), str(td / "out.json")], capture_output=True, text=True, timeout=300)
        if r.returncode:
            check(False, "Chromium failed: " + (r.stderr or r.stdout)[-300:])
            return finish()
        out = json.loads((td / "out.json").read_text(encoding="utf-8"))[0]

    print("\n== D drawn in the browser")
    used = {f"{f} {w}" for f in ("Vazirmatn", "Inter") for w in (400, 700)}
    check(used <= set(out["loaded"]), f"the faces are loaded: {sorted(out['loaded'])}")
    want = {}
    for gid, L in layouts:
        for b in L["blocks"]:
            for k, ln in enumerate(b["lines"]):
                want[f"{gid}|{b['role']}|{k}"] = (L, b, ln)
    drawn = {x["id"]: x for x in out["lines"]}
    check(set(drawn) == set(want), f"every laid-out line is drawn ({len(drawn)})")
    d_len = max(abs(x["len"] - want[i][2]["width"]) for i, x in drawn.items())
    d_span = max(max(abs(x["box"][0] - want[i][2]["x0"]), abs(x["box"][2] - want[i][2]["x1"])) for i, x in drawn.items())
    check(d_len < 0.5, f"each drawn line's length = its measured width (largest difference {d_len:.3f} px)")
    check(d_span < 1.0, f"each drawn line spans exactly x0..x1 of the layout (largest difference {d_span:.3f} px)")
    inside = all(want[i][0]["inner"][0] - 0.5 <= x["box"][0] and x["box"][2] <= want[i][0]["inner"][0] + want[i][0]["inner"][2] + 0.5 for i, x in drawn.items())
    check(inside, "no drawn line is wider than its box's text area (no overflow)")
    over = 0
    for gid, L in layouts:
        rows = sorted((x["box"] for i, x in drawn.items() if i.startswith(gid + "|")), key=lambda b: b[1])
        over += sum(1 for p, q in zip(rows, rows[1:]) if q[1] < p[3] - 0.5)
        r = L["rect"]
        over += sum(1 for bx in rows if bx[1] < r[1] - 0.5 or bx[3] > r[1] + r[3] + 0.5)
    check(over == 0, "lines do not overlap one another and stay inside their box vertically")

    print("\n== B reading order")
    rtl_bad = ltr_bad = n_rtl = n_ltr = 0
    for i, x in drawn.items():
        ln = want[i][2]
        xs, t = x["xs"], x["text"]
        strong = [k for k, ch in enumerate(t) if TX.direction(ch, "") in ("rtl", "ltr") and TX.direction(ch, "") == ln["direction"]]
        if len(strong) < 2:
            continue
        a, b_ = xs[strong[0]], xs[strong[-1]]
        if ln["direction"] == "rtl":
            n_rtl += 1
            rtl_bad += not (a[0] > b_[0])
        else:
            n_ltr += 1
            ltr_bad += not (a[0] < b_[0])
    check(n_rtl > 5 and rtl_bad == 0, f"Persian lines run right to left ({n_rtl} lines)")
    check(n_ltr > 3 and ltr_bad == 0, f"English lines run left to right ({n_ltr} lines)")
    mixed = [(i, x) for i, x in drawn.items() if "visitors" in x["text"] and i.startswith("fa-info")]
    if mixed:
        i, x = mixed[0]
        t, xs = x["text"], x["xs"]
        check(want[i][2]["direction"] == "rtl" and xs[t.index("v")][0] > xs[t.index("د", t.index("visitors"))][0] if "د" in t[t.index("visitors"):] else True,
              f"Persian paragraph, line with an English word: drawn rtl, the English word on the right of the Persian after it: {t!r}")
        check(xs[t.index("v")][0] < xs[t.index("s", t.index("visitors"))][0], "... and the English word itself left to right")
    else:
        check(False, "the mixed line is in the layout")
    dig = [(i, x) for i, x in drawn.items() if "۱۳۳۲" in x["text"]]
    i, x = dig[0]
    k = x["text"].index("۱۳۳۲")
    check(x["xs"][k][0] < x["xs"][k + 3][0], "Persian digits ۱۳۳۲ run left to right inside the rtl line")
    en_mixed = [(i, x) for i, x in drawn.items() if "بندر" in x["text"] and i.startswith("en-callout")]
    i, x = en_mixed[0]
    t = x["text"]
    check(want[i][2]["direction"] == "ltr" and x["xs"][t.index("(")][0] < x["xs"][t.index("ب")][0] and x["xs"][t.index("ب")][0] > x["xs"][t.index("ر")][0],
          f"English paragraph with a Persian word: ltr line, the Persian word after the English, itself right to left: {t!r}")
    print("\n== N a Persian number is drawn the same in every context")
    f = TX.format_number
    n1, n2 = f(-1234.5, 1, "fa", "%"), f(31.5, 1, "fa", "%")
    texts = [n1, "رشد " + n1 + " در سال", n2, "رشد " + n2 + " در سال", "کاهش " + f(-2, 0, "fa") + " درصد", f(12, 0, "fa", "کیلومتر") + " راه"]
    MS.measure([(t, 40.0, 400, G.FONT_STACK["fa"]) for t in texts], fonts)          # the isolate marks need no system font
    page = ('<!doctype html><html><head><style>' + css + '</style></head><body><svg xmlns="http://www.w3.org/2000/svg" width="1920" height="600">'
            + "".join(f'<text data-id="n{k}" x="1800" y="{60 + 70 * k}" font-family="{G.FONT_STACK["fa"]}" font-size="40" direction="rtl">{t}</text>'
                      for k, t in enumerate(texts)) + '</svg></body></html>')
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "pages.json").write_text(json.dumps([page]), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        subprocess.run(["node", str(td / "probe.js"), str(td / "pages.json"), str(td / "out.json")], capture_output=True, text=True, timeout=300, check=True)
        rows = json.loads((td / "out.json").read_text(encoding="utf-8"))[0]["lines"]
    iso = (TX.LRI, TX.PDI)
    vis = ["".join(c for _, c in sorted((x["xs"][i][0], c) for i, c in enumerate(x["text"]) if c not in iso)) for x in rows]
    want1, want2 = TX.MINUS + "۱٬۲۳۴٫۵٪", "۳۱٫۵٪"
    check(vis[0] == want1 and want1 in vis[1] and vis[2] == want2 and want2 in vis[3],
          f"alone and inside a sentence a number is drawn the same, left to right: {vis[0]!r} / {vis[1]!r}; {vis[2]!r} / {vis[3]!r}")
    check(TX.MINUS + "۲" in vis[4] and vis[5].endswith("۱۲") and "رتمولیک" in vis[5],
          f"a negative number in a sentence keeps its sign on the left; a unit word reads after its number (to its left): {vis[4]!r}, {vis[5]!r}")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G2 RENDER TESTS PASSED" if not f else "GRAPHICS G2 RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
