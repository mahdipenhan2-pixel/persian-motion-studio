#!/usr/bin/env python3
"""G6 - comparison / bar / column without a browser (a fake, deterministic "measurement" as in G2):
  honesty   one linear scale from zero for all items (length = |value| x px_per_unit), zero = no bar, negative values on
            the other side of the zero line, a comparison refuses negative values, every item drawn in its order with
            its value exactly as format_number writes it, a non-zero value shown as zero is a warning
  direction Persian charts grow from the right (labels right, positive bars leftwards, first column rightmost), English
            from the left
  layout    no text over a bar or another text, everything inside its box, the safe area, out of the subtitle band; the
            full-frame accent rule inside the safe area (also for a tall full-frame text graphic: a G6 fix in G2's layout)
  errors    a bar label too wide, a value wider than its column, a chart too tall - never shrunk or cut
  render    one rect per item (data-p bar-<i>), the zero axis, highlight colours; bar colour contrast (non-text, 3:1)
  python3 nfp/graphics/tests/test_graphics_g6.py
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
from graphics import render as R          # noqa: E402
from graphics import safearea as SA       # noqa: E402
from graphics import text as TX           # noqa: E402
from test_graphics_g2 import measured     # noqa: E402

RESULTS = []
SRC = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار", "date": "2023", "verified": True},
       {"id": "s2", "title": "Records", "publisher": "Port Authority", "date": "2019", "verified": True}]


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def make(kind, display="overlay", lang="fa", values=(9.04, 3.37, 2.24, 0, 1.87), labels=None, mode="final", **kw):
    labels = labels or (["تهران", "مشهد", "اصفهان", "کرج", "شیراز", "تبریز", "قم", "اهواز", "رشت", "یزد", "کرمان", "ارومیه"] if lang == "fa"
                        else ["Tehran", "Mashhad", "Isfahan", "Karaj", "Shiraz", "Tabriz", "Qom", "Ahvaz", "Rasht", "Yazd", "Kerman", "Urmia"])
    d = {"schema": "nfp.graphics/1", "id": f"g-{kind}", "mode": mode, "lang": lang, "kind": kind,
         "content": {"title": "جمعیت شهرها" if lang == "fa" else "City population"},
         "data": {"source": "s1", "format": {"decimals": 1}, "items": [{"label": l, "value": v} for l, v in zip(labels, values)]},
         "sources": SRC}
    for k, v in kw.items():
        if k == "data":
            d["data"].update(v)
        else:
            d[k] = v
    r = G.validate(d, display, 120)
    if not r["graphic"]:
        return None, r
    sp = r["graphic"]
    return sp, G.layout(sp, measured(sp))


def boxes(lay):
    """ink-free text boxes [x0, y0, x1, y1] (advance span x font box) of every line, with its block role"""
    out = []
    for b in lay["blocks"]:
        for ln in b["lines"]:
            out.append((b["role"], [ln["x0"], ln["baseline"] - b["ascent"], ln["x1"], ln["baseline"] + b["descent"]]))
    return out


def hit(a, b, tol=0.5):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def main():
    print("== A data rules")
    sp, r = make("comparison", values=(5, -2))
    check(sp is None and any("must be >= 0" in i["message"] for i in r["issues"]), "a comparison refuses a negative value (bar / column show them)")
    for kind, n in (("bar", 12), ("column", 12), ("comparison", 4)):
        sp, lay = make(kind, "fullframe", values=list(range(1, n + 1)))
        check(sp and lay["status"] in ("OK", "WARN"), f"{kind}: {n} items in a full frame lay out ({lay and lay['status']})")
    sp, lay = make("bar", values=(0, 0, 0))
    check(lay["status"] in ("OK", "WARN") and all(b["rect"][2] == 0 for b in lay["bars"]) and lay["scale"]["px_per_unit"] == 0,
          "all values zero: zero-length bars, labels and values still shown")

    print("\n== B honesty: one scale from zero, exact values, order")
    for kind in ("bar", "column", "comparison"):
        for lang in ("fa", "en"):
            vals = (9.04, 3.37, 2.24, 0, 1.87) if kind != "comparison" else (1250, 48600)
            sp, lay = make(kind, lang=lang, values=vals, labels=None if kind != "comparison" else (["۱۳۳۲", "۱۴۰۲"] if lang == "fa" else ["1953", "2023"]),
                           data={"format": {"decimals": 1 if kind != "comparison" else 0}})
            k = lay["scale"]["px_per_unit"]
            ax = 2 if kind != "column" else 3
            lens = [b["rect"][ax] for b in lay["bars"]]
            exact = all(abs(L - abs(v) * k) < 1e-3 for L, v in zip(lens, vals))
            z = lay["scale"]["zero"]
            starts = all(abs(b["rect"][0] - z) < 1e-3 or abs(b["rect"][0] + b["rect"][2] - z) < 1e-3 for b in lay["bars"]) if kind != "column" else \
                all(abs(b["rect"][1] + b["rect"][3] - z) < 1e-3 for b in lay["bars"])
            want = [TX.format_number(v, sp["data"]["format"]["decimals"], sp["data"]["format"]["digits"], sp["data"]["unit"]) for v in vals]
            got = [next(b for b in lay["blocks"] if b["role"] == f"value-{i}")["lines"][0]["text"] for i in range(len(vals))]
            if kind == "column":
                xs = [b["rect"][0] for b in lay["bars"]]
                order = xs == sorted(xs, reverse=(lang == "fa"))
            else:
                ys = [b["rect"][1] for b in lay["bars"]]
                order = ys == sorted(ys)
            grow = [b["rect"] for b, v in zip(lay["bars"], vals) if v > 0]
            if kind == "column":
                dir_ok = all(r_[1] + r_[3] <= z + 1e-3 for r_ in grow)
            else:
                dir_ok = all((r_[0] + r_[2] <= z + 1e-3) if lang == "fa" else (r_[0] >= z - 1e-3) for r_ in grow)
            check(exact and starts and got == want and order and dir_ok,
                  f"{kind} / {lang}: every length = |value| x {k:.3f} px from the zero line, values exactly {got[:3]}..., "
                  f"{'first column on the ' + ('right' if lang == 'fa' else 'left') if kind == 'column' else 'rows in data order'}, "
                  f"positive {'up' if kind == 'column' else 'leftwards' if lang == 'fa' else 'rightwards'}")
    sp, lay = make("bar", "fullframe", lang="en", values=(12.5, -4.2, 27.9, -11, 0), data={"unit": "%"})
    z = lay["scale"]["zero"]
    neg = [b["rect"] for b, v in zip(lay["bars"], (12.5, -4.2, 27.9, -11, 0)) if v < 0]
    check(all(abs(r_[0] + r_[2] - z) < 1e-3 for r_ in neg) and lay["axis"] and abs(lay["axis"][0][0] - z) < 1e-3,
          "negative values: bars on the other side of the zero line (English: leftwards), a zero line drawn")
    sp, lay = make("column", "fullframe", lang="fa", values=(12, 15, -3, 8), data={"unit": "%", "format": {"decimals": 0}})
    z = lay["scale"]["zero"]
    c3 = lay["bars"][2]["rect"]
    v3 = next(b for b in lay["blocks"] if b["role"] == "value-2")["lines"][0]
    check(abs(c3[1] - z) < 1e-3 and v3["baseline"] > c3[1] + c3[3], "a negative column hangs below the zero line, its value under it")
    sp, lay = make("bar", values=(0.004, 2), data={"format": {"decimals": 2}})
    check("rounded_to_zero" in [i["code"] for i in lay["issues"]], "a non-zero value that shows as 0.00: warning (rounded_to_zero)")
    sp, lay = make("bar", values=(5, 3), labels=["A", "B"], lang="en")
    src = next(b for b in lay["blocks"] if b["role"] == "source")["lines"][0]["text"]
    check(src == "Source: مرکز آمار, 2023", f"the source line names the items' sources: {src!r}")
    d2 = {"items": [{"label": "A", "value": 5, "source": "s1"}, {"label": "B", "value": 3, "source": "s2"}]}
    sp, lay = make("bar", values=(), labels=[], lang="en", data=d2)
    src = next(b for b in lay["blocks"] if b["role"] == "source")["lines"][0]["text"]
    check(src == "Source: مرکز آمار, 2023; Port Authority, 2019", f"... every source once, in item order: {src!r}")

    print("\n== C nothing covers anything; everything in its place")
    for kind in ("bar", "column", "comparison"):
        for disp in ("overlay", "fullframe"):
            for lang in ("fa", "en"):
                vals = (9.04, -3.37, 2.24, 0, 1.87) if kind != "comparison" else (54.2, 18.7, 9.1)
                sp, lay = make(kind, disp, lang, values=vals)
                bx = boxes(lay)
                bars = [[b["rect"][0], b["rect"][1], b["rect"][0] + b["rect"][2], b["rect"][1] + b["rect"][3]] for b in lay["bars"]]
                t_t = sum(hit(a[1], b[1]) for i, a in enumerate(bx) for b in bx[i + 1:])
                t_b = sum(hit(a[1], b) for a in bx for b in bars)
                r_ = lay["rect"]
                inside = all(SA.inside([x0, y0, x1 - x0, y1 - y0], r_, tol=0.5) for _, (x0, y0, x1, y1) in bx) and \
                    all(SA.inside([b[0], b[1], b[2] - b[0], b[3] - b[1]], r_, tol=0.5) for b in bars)
                ok = lay["status"] in ("OK", "WARN") and t_t == 0 and t_b == 0 and inside and SA.inside(r_, SA.ALLOWED) and not SA.intersects(r_, SA.BAND)
                if disp == "fullframe":
                    svg = R.render_svg(sp, lay)
                    m = re.search(r'data-p="gx-[^"]+-rule" x="([\d.]+)" y="([\d.]+)"', svg)
                    ok = ok and m and float(m.group(2)) >= SA.ALLOWED[1]
                check(ok, f"{kind} / {disp} / {lang}: no text over text ({t_t}) or over a bar ({t_b}); all inside the box, the safe area"
                          + ("; the accent rule in the safe area" if disp == "fullframe" else ""))
    sp = G.validate({"schema": "nfp.graphics/1", "id": "tall", "mode": "final", "lang": "fa", "kind": "info-card",
                     "content": {"title": "بندر قدیمی", "body": "\n".join(["خطی از متن"] * 8)}}, "fullframe")["graphic"]
    lay = G.layout(sp, measured(sp))
    svg = R.render_svg(sp, lay)
    ry = float(re.search(r'data-p="gx-[^"]+-rule" x="[\d.]+" y="([\d.]+)"', svg).group(1))
    check(ry >= SA.ALLOWED[1], f"a tall full-frame TEXT graphic (title + 8 lines): its accent rule at y {ry:.0f} >= {SA.ALLOWED[1]} (G6 fix of G2's centring)")

    print("\n== D what does not fit is an error, never shrunk")
    sp, lay = make("bar", lang="en", labels=["Bandar-e Mahshahr Petrochemical Zone", "B"], values=(3, 4))
    check("text_overflow" in [i["code"] for i in lay["issues"]] and lay["rect"] is None, "a bar label wider than 40 % of the chart: error")
    sp, lay = make("column", lang="en", values=[123456.78] * 12, labels=[f"C{i}" for i in range(12)], data={"format": {"decimals": 2}})
    check("text_overflow" in [i["code"] for i in lay["issues"]], "12 columns whose values are wider than their places: error")
    sp, lay = make("bar", lang="en", values=list(range(1, 13)), place={"rect": [96, 54, 800, 300]})
    check("chart_too_tall" in [i["code"] for i in lay["issues"]], "12 bars in a 300 px box: chart_too_tall")

    print("\n== E drawing")
    sp, lay = make("bar", values=(9.04, 3.37, 2.24), labels=["تهران", "مشهد", "اصفهان"],
                   data={"items": [{"label": "تهران", "value": 9.04, "highlight": True}, {"label": "مشهد", "value": 3.37}, {"label": "اصفهان", "value": 2.24}]})
    svg = R.render_svg(sp, lay)
    k = R.key_of(sp["id"])
    fills = re.findall(r'data-p="gx-' + re.escape(k) + r'-bar-\d+"[^>]*fill="(#[0-9a-f]+)"', svg)
    c = sp["style"]["colors"]
    check(len(fills) == 3 and fills == [c["accent"], c["muted"], c["muted"]] and f'gx-{k}-axis-0' in svg,
          "one rect per item, the highlighted one in the accent colour, the others muted; the zero axis")
    check(len(re.findall(r'<text data-p="gx-' + re.escape(k) + r'-(label|value)-\d+-\d+"', svg)) == 6, "every label and value drawn as text")
    sp, lay = make("bar", style={"accent": "#1f2227"})
    check([i["element"] for i in R.contrast(sp, lay)] == ["bar"], "bars nearly the panel's colour: low contrast error (graphics need 3:1)")
    a, b = make("column", "fullframe"), make("column", "fullframe")
    check(R.render_svg(*a) == R.render_svg(*b) and json.loads(json.dumps(a[1])) == a[1], "deterministic, plain JSON")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G6 TESTS PASSED" if not f else "GRAPHICS G6 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
