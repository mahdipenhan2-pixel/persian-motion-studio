#!/usr/bin/env python3
"""G3 - REAL drawing in the local Chromium with the film's local fonts: every text kind in every display it allows, in
Persian and English, three presets, a draft graphic, drawn over a BLACK and a WHITE page:
  geometry  every line where the layout put it (span, length), inside its panel / the safe area, out of the subtitle band,
            no two lines overlapping; panel / rule / leader / dot / badge inside the safe area
  fonts     the browser reports (DevTools protocol) that only our web fonts drew the text - no system font
  pixels    the panel's colour = the style's panel blended over the page; the text's measured contrast against the panel
            (or the full-frame background) meets WCAG (4.5:1, large text 3:1) on both pages; the callout leader visible on both
  preview   the review page loads without errors (a screenshot is kept next to --out)
  python3 nfp/graphics/tests/test_graphics_g3_render.py --fonts <woff2 folder> [--out <folder for the preview>]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path.insert(0, str(NFP))
import graphics as G                              # noqa: E402
from graphics import render as R                  # noqa: E402
from graphics import safearea as SA               # noqa: E402
from graphics.tools import measure as MS          # noqa: E402

RESULTS = []
JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [jobFile, outDir] = process.argv.slice(2);
  const jobs = JSON.parse(fs.readFileSync(jobFile, 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const errors = []; p.on('pageerror', e => errors.push(String(e)));
  const cdp = await p.context().newCDPSession(p);
  await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const res = [];
  for (const [k, job] of jobs.entries()) {
    await p.setContent('<!doctype html><html><head><style>html,body{margin:0;background:' + job.page + '}</style></head><body>' + job.svg + '</body></html>');
    const info = await p.evaluate(async () => {
      await document.fonts.ready;
      const box = e => { const q = e.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; };
      const texts = [...document.querySelectorAll('text[data-p]')].map(t => {       // advance span: from the characters' own positions
        const xs = []; for (let i = 0; i < t.getNumberOfChars(); i++) xs.push(t.getStartPositionOfChar(i).x, t.getEndPositionOfChar(i).x);
        return { p: t.dataset.p, len: t.getComputedTextLength(), adv: [Math.min(...xs), 0, Math.max(...xs), 0], box: box(t) }; });
      const parts = [...document.querySelectorAll('[data-p]')].map(e => ({ p: e.dataset.p, box: box(e) }));
      return { texts, parts, loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight).sort() };
    });
    const root = (await cdp.send('DOM.getDocument', { depth: -1 })).root.nodeId;
    const { nodeIds } = await cdp.send('DOM.querySelectorAll', { nodeId: root, selector: 'text' });
    const sys = new Set();
    for (const id of nodeIds) { const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId: id }); fonts.filter(f => !f.isCustomFont).forEach(f => sys.add(f.familyName)); }
    info.system_fonts = [...sys];
    await p.screenshot({ path: outDir + '/s' + k + '.png' });
    res.push(info);
  }
  if (jobs.preview) { }
  await b.close();
  fs.writeFileSync(outDir + '/out.json', JSON.stringify({ res, errors }));
})().catch(e => { console.error(String(e)); process.exit(1); });
"""
PREVIEW_JS = r"""
const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 2960, height: 1200 }, deviceScaleFactor: 1 });
  const errors = []; p.on('pageerror', e => errors.push(String(e)));
  await p.goto('file://' + process.argv[2]); await p.evaluate(() => document.fonts.ready);
  const n = await p.evaluate(() => document.querySelectorAll('section').length);
  await p.screenshot({ path: process.argv[3], fullPage: true }); console.log(JSON.stringify({ errors, n })); await b.close(); })()
  .catch(e => { console.error(String(e)); process.exit(1); });
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


SRC = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار", "date": "2024", "verified": True},
       {"id": "s2", "title": "Harbour records", "publisher": "Port Authority", "date": "2019", "verified": True}]
TXT = {"fa": {"title": {"title": "فصل اول: بندری که دریا به یاد دارد", "subtitle": "سال‌های ۱۳۳۰ تا ۱۳۴۰"},
              "lower-third": {"title": "مریم احمدی", "subtitle": "تاریخ‌نگار، دانشگاه تهران"},
              "info-card": {"title": "بندر قدیمی", "body": "این بندر در سال ۱۳۳۲ بسته شد و امروز موزه‌ای است با بازدیدکنندگان (visitors) بسیار.", "source": "s1"},
              "quote": {"body": "دریا همه چیز را به یاد دارد؛ حتی آنچه ما فراموش کرده‌ایم.", "attribution": "یک ماهیگیر پیر", "source": "s1"},
              "callout": {"body": "اسکلهٔ قدیمی، بازسازی‌شده پس از طوفان"}},
       "en": {"title": {"title": "Chapter one: the harbour the sea remembers", "subtitle": "The 1950s"},
              "lower-third": {"title": "Maryam Ahmadi", "subtitle": "Historian, University of Tehran"},
              "info-card": {"title": "The old harbour", "body": "Closed in 1953, the harbour reopened as a museum (موزه) that many visit.", "source": "s2"},
              "quote": {"body": "The sea remembers everything, even what we have forgotten.", "attribution": "An old fisherman", "source": "s2"},
              "callout": {"body": "The old pier, rebuilt after the storm"}}}
PRESETS = list(G.PRESETS)


def cases():
    out, n = [], 0
    for kind in ("title", "lower-third", "info-card", "quote", "callout"):
        for disp in G.DISPLAYS[kind]:
            for lang in ("fa", "en"):
                d = {"schema": "nfp.graphics/1", "id": f"{kind}.{disp}.{lang}", "mode": "final", "lang": lang, "kind": kind,
                     "content": TXT[lang][kind], "style": {"preset": PRESETS[n % 3]}}
                n += 1
                if "source" in d["content"]:
                    d["sources"] = SRC[:1] if lang == "fa" else SRC[1:]
                if kind == "callout":
                    d["place"] = {"at": [560, 420] if lang == "fa" else [1400, 300]}
                out.append((d, disp))
    out.append(({"schema": "nfp.graphics/1", "id": "draft.info", "mode": "draft", "lang": "fa", "kind": "info-card",
                 "content": {"title": "آمار", "body": "در سال ۱۳۳۲ نزدیک ۴۰ کشتی پهلو گرفت."}}, "overlay"))
    return out


def png(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(1080, 1920, 3).astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--out", default=None, help="a folder for the preview page + screenshot (kept)")
    a = ap.parse_args()
    fonts = Path(a.fonts)
    if not shutil.which("node"):
        check(False, "node is not installed")
        return finish()
    css = MS.font_face_css(fonts)
    items, jobs = [], []
    for d, disp in cases():
        r = G.validate(d, disp, 150)
        sp = r["graphic"]
        lay = G.layout(sp, MS.measure_graphic(sp, fonts))
        if lay["status"] not in ("OK", "WARN") or R.contrast(sp, lay) and sp["mode"] == "final":
            check(False, f"{d['id']}: lays out without errors and passes contrast ({[i['code'] for i in lay['issues'] + R.contrast(sp, lay)]})")
            continue
        items.append((sp, lay))
        svg = R.render_svg(sp, lay, font_css=css)
        jobs += [{"page": "#000", "svg": svg}, {"page": "#fff", "svg": svg}]
    check(len(items) == 17 and any(lay["badge"] for _, lay in items), f"{len(items)} graphics laid out (8 kind / display pairs x 2 languages + a draft)")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        r = subprocess.run(["node", str(td / "probe.js"), str(td / "jobs.json"), str(td)], capture_output=True, text=True, timeout=900)
        if r.returncode:
            check(False, "Chromium failed: " + (r.stderr or r.stdout)[-300:])
            return finish()
        out = json.loads((td / "out.json").read_text(encoding="utf-8"))
        shots = [png(td / f"s{k}.png") for k in range(len(jobs))]

    print("== F fonts")
    check(not out["errors"], f"no page error {out['errors'][:1]}")
    check(all(not x["system_fonts"] for x in out["res"]), f"only our web fonts drew text (DevTools: system fonts {sorted({f for x in out['res'] for f in x['system_fonts']})})")
    faces = {f"{f} {w}" for f in ("Vazirmatn", "Inter") for w in (400, 700)}
    check(all(x["loaded"] and set(x["loaded"]) <= faces for x in out["res"]) and set().union(*(x["loaded"] for x in out["res"])) == faces,
          "each page loads only our faces (the ones its text uses), and all four are used across the set")

    print("\n== P geometry")
    worst_span = worst_len = 0.0
    bad_inside, bad_safe, bad_overlap = [], [], []
    for (sp, lay), info in zip(items, out["res"][::2]):
        k = R.key_of(sp["id"])
        want = {f"gx-{k}-{b['role']}-{n}": ln for b in lay["blocks"] for n, ln in enumerate(b["lines"])}
        got = {t["p"]: t for t in info["texts"]}
        if set(got) != set(want):
            bad_inside.append(sp["id"] + " (lines missing)")
            continue
        for pid, ln in want.items():
            adv, bx = got[pid]["adv"], got[pid]["box"]           # advance span (where the text is set) / ink box (what is drawn)
            worst_span = max(worst_span, abs(adv[0] - ln["x0"]), abs(adv[2] - ln["x1"]))
            worst_len = max(worst_len, abs(got[pid]["len"] - ln["width"]))
            area = lay["rect"] if sp["display"] == "overlay" else SA.ALLOWED
            if not SA.inside([bx[0], bx[1], bx[2] - bx[0], bx[3] - bx[1]], area, tol=0.75):
                bad_inside.append(pid)
        rows = sorted((got[p]["box"] for p in want), key=lambda b: b[1])
        bad_overlap += [sp["id"] for p_, q in zip(rows, rows[1:]) if q[1] < p_[3] - 0.5]
        for part in info["parts"]:
            # not drawn content of their own: the full-frame background, the root (it holds that background) and the clip
            # rectangle (a mask, G4); the body (everything that moves) and every drawn part are checked
            if part["p"].endswith("-bg") or part["p"] == f"gx-{k}" or part["p"].endswith("-clipr"):
                continue
            bx = part["box"]
            r = [bx[0], bx[1], bx[2] - bx[0], bx[3] - bx[1]]
            if not SA.inside(r, SA.ALLOWED, tol=0.75) or SA.intersects(r, SA.BAND):
                bad_safe.append(part["p"])
    check(worst_span < 1.0 and worst_len < 0.5, f"every line set at its laid-out span (character advances; largest difference {worst_span:.3f} px) and length ({worst_len:.3f} px)")
    check(not bad_inside, f"every line's INK (glyph overhang included, e.g. the madda of «آ») inside its panel (overlay) / the safe area (full frame) {bad_inside[:3]}")
    check(not bad_overlap, f"no two lines overlap {bad_overlap[:3]}")
    check(not bad_safe, f"panels, rules, leaders, dots, badges and text all inside the safe area, none in the subtitle band {bad_safe[:4]}")

    print("\n== X pixels: colours and contrast on a black and a white page")
    worst_panel, low = 0.0, []
    vis_leader = []
    for i, (sp, lay) in enumerate(items):
        c = sp["style"]["colors"]
        for j, page in enumerate(((0, 0, 0), (255, 255, 255))):
            img = shots[2 * i + j]
            if sp["display"] == "overlay":
                pad = sp["style"]["spacing"]["padding"]
                x, y = int(lay["rect"][0] + pad / 2), int(lay["rect"][1] + pad / 2)
                if sp["lang"] == "fa" and lay["rule"]:
                    x = int(lay["rect"][0] + pad / 2)
                bg = img[y, x]
                exp = np.array(R.blend(R._rgb(c["panel"]), c["panel_opacity"], page))
                worst_panel = max(worst_panel, float(np.abs(bg - exp).max()))
            else:
                bg = img[5, 5]
                worst_panel = max(worst_panel, float(np.abs(bg - np.array(R._rgb(c["background"]))).max()))
            for b in lay["blocks"]:
                need = R.LARGE_LIMIT if b["size"] >= 24 or (b["weight"] >= 700 and b["size"] >= 18.66) else R.LIMIT
                for ln in b["lines"]:
                    x0, x1 = int(ln["x0"]), int(ln["x1"]) + 1
                    y0, y1 = int(ln["baseline"] - b["ascent"]), int(ln["baseline"] + b["descent"]) + 1
                    patch = img[y0:y1, x0:x1].reshape(-1, 3)
                    best = max(R.ratio(tuple(px), tuple(bg)) for px in patch[::3])
                    if best < need:
                        low.append((sp["id"], b["role"], round(best, 2), need, "black" if j == 0 else "white"))
            if sp["kind"] == "callout":
                ld = R.leader(lay["rect"], sp["place"]["at"])
                mx, my = int((ld[0][0] + ld[1][0]) / 2), int((ld[0][1] + ld[1][1]) / 2)
                acc = np.array(R._rgb(c["accent"]))
                vis_leader.append(float(np.abs(img[my - 1:my + 2, mx - 1:mx + 2].reshape(-1, 3) - acc).sum(axis=1).min()))
    check(worst_panel <= 3, f"panel = the style's panel colour over the page / full-frame background exact (largest channel difference {worst_panel:.0f})")
    check(not low, f"measured text contrast meets WCAG on both pages (4.5:1, large 3:1) {low[:4]}")
    check(vis_leader and max(vis_leader) < 30, f"the callout leader is drawn in its accent colour on both pages (colour distance {[round(v) for v in vis_leader]})")

    print("\n== V preview page")
    with tempfile.TemporaryDirectory() as td:
        od = Path(a.out) if a.out else Path(td)
        od.mkdir(parents=True, exist_ok=True)
        (od / "preview.html").write_text(R.preview_html(items, css), encoding="utf-8")
        (Path(td) / "pv.js").write_text(PREVIEW_JS, encoding="utf-8")
        r = subprocess.run(["node", str(Path(td) / "pv.js"), str((od / "preview.html").resolve()), str(od / "preview.png")],
                           capture_output=True, text=True, timeout=300)
        res = json.loads(r.stdout) if r.returncode == 0 else {"errors": [r.stderr[-200:]], "n": 0}
        check(res["n"] == len(items) and not res["errors"] and (od / "preview.png").exists(),
              f"the preview page loads: {res['n']} graphics, no error" + (f" ({od / 'preview.png'})" if a.out else ""))
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G3 RENDER TESTS PASSED" if not f else "GRAPHICS G3 RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
