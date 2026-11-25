#!/usr/bin/env python3
"""G7 - line chart and counter for REAL (local Chromium, the film's fonts, the Film Director, a real MP4):
  C  line charts (Persian / English, 1..3 series, 40 points, negatives, light preset) and counters drawn over a black page:
     lines set where the layout put them, only our web fonts, no text ink over other text or outside its box, the
     polylines' points = the layout's, safe area / subtitle band; PIXELS: each point marker and each solid segment's
     middle in its series' colour
  D  the counter with the Film's own Director, GSAP and [data-p] CSS (read from base.html, unchanged), seeked frame by frame:
     hidden before / after its clip, exactly the planned number on every frame (one at a time), the final value exactly
     the data from the end of the enter on, its ink inside the box on every frame
  F  a line chart (overlay over an image, wipe) and a counter (full frame, counting over a 45-frame fade) as graphic
     clips through Timeline / Film (G5), and a real HyperFrames MP4: the counter's last frames show a steady number that
     differs from its counting frames; the line's point markers in their colours in the MP4
  python3 nfp/graphics/tests/test_graphics_g7_render.py --fonts <woff2> [--gsap <gsap.min.js> [--work <dir outside the repo>]]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(HERE)]
import graphics as G                              # noqa: E402
from graphics import animate as A                 # noqa: E402
from graphics import render as R                  # noqa: E402
from graphics import safearea as SA               # noqa: E402
from graphics import text as TX                   # noqa: E402
from graphics.tools import measure as MS          # noqa: E402

RESULTS = []
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
SRC_FA = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار ایران", "date": "2023", "verified": True}]
SRC_EN = [{"id": "s1", "title": "Yearbook", "publisher": "Statistical Centre of Iran", "date": "2023", "verified": True}]
STATIC_JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [jobFile, outDir] = process.argv.slice(2);
  const jobs = JSON.parse(fs.readFileSync(jobFile, 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const errors = []; p.on('pageerror', e => errors.push(String(e)));
  const cdp = await p.context().newCDPSession(p); await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const res = [];
  for (const [k, svg] of jobs.entries()) {
    await p.setContent('<!doctype html><html><head><style>html,body{margin:0;background:#000}</style></head><body>' + svg + '</body></html>');
    const info = await p.evaluate(async () => {
      await document.fonts.ready;
      const box = e => { const q = e.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; };
      const shown = e => getComputedStyle(e).display !== 'none';
      const texts = [...document.querySelectorAll('text[data-p]')].filter(shown).map(t => {
        const xs = []; for (let i = 0; i < t.getNumberOfChars(); i++) xs.push(t.getStartPositionOfChar(i).x, t.getEndPositionOfChar(i).x);
        return { p: t.dataset.p, adv: [Math.min(...xs), Math.max(...xs)], ink: box(t) }; });
      const lines = [...document.querySelectorAll('polyline[data-p]')].map(l => ({ p: l.dataset.p, pts: l.getAttribute('points') }));
      const parts = [...document.querySelectorAll('[data-p]')].filter(shown).map(e => ({ p: e.dataset.p, box: box(e) }));
      return { texts, lines, parts };
    });
    const root = (await cdp.send('DOM.getDocument', { depth: -1 })).root.nodeId;
    const { nodeIds } = await cdp.send('DOM.querySelectorAll', { nodeId: root, selector: 'text' });
    const sys = new Set();
    for (const id of nodeIds) { const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId: id }); fonts.filter(f => !f.isCustomFont).forEach(f => sys.add(f.familyName)); }
    info.system_fonts = [...sys];
    await p.screenshot({ path: outDir + '/s' + k + '.png' });
    res.push(info);
  }
  await b.close();
  fs.writeFileSync(outDir + '/out.json', JSON.stringify({ res, errors }));
})().catch(e => { console.error(String(e)); process.exit(1); });
"""
SEEK_JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [page, out, a, b, key] = process.argv.slice(2);
  const br = await chromium.launch(); const p = await br.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = []; p.on('pageerror', e => errors.push(String(e)));
  await p.goto('file://' + page); await p.evaluate(() => document.fonts.ready);
  const rows = await p.evaluate(([a, b, key]) => {
    const rows = [];
    const shown = (e) => { for (let x = e; x && x.nodeType === 1; x = x.parentNode) if (getComputedStyle(x).display === 'none') return false; return true; };
    for (let f = a; f <= b; f++) {
      window.tl.seek(f / 30, false);
      const vis = [...document.querySelectorAll('[data-p^="gx-' + key + '-count-"]')].filter(shown).map(t => { const q = t.getBoundingClientRect();
        return { p: t.dataset.p, text: t.textContent, ink: [q.left, q.top, q.right, q.bottom] }; });
      rows.push({ f, root: shown(document.querySelector('[data-p="gx-' + key + '"]')), vis });
    }
    return rows;
  }, [+a, +b, key]);
  fs.writeFileSync(out, JSON.stringify({ rows, errors, warns: await p.evaluate(() => window.__warns || []) })); await br.close();
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def line_doc(gid, lang, series, title, unit=None, decimals=1, subtitle=None, preset=None, anim=None, n=None):
    xs = [str(1390 + i).translate(FA) if lang == "fa" else str(2011 + i) for i in range(n or len(series[0][1]))]
    d = {"schema": "nfp.graphics/1", "id": gid, "mode": "final", "lang": lang, "kind": "line", "content": {"title": title},
         "data": {"source": "s1", "format": {"decimals": decimals},
                  "series": [dict({"points": [{"x": x, "value": v} for x, v in zip(xs, vals)]}, **({"label": lab} if lab else {})) for lab, vals in series]},
         "sources": SRC_FA if lang == "fa" else SRC_EN}
    if unit:
        d["data"]["unit"] = unit
    if subtitle:
        d["content"]["subtitle"] = subtitle
    if preset:
        d["style"] = {"preset": preset}
    if anim:
        d["animation"] = anim
    return d


def counter_doc(gid, lang, value, title, frm=None, decimals=0, unit=None, subtitle=None, frames=45):
    d = {"schema": "nfp.graphics/1", "id": gid, "mode": "final", "lang": lang, "kind": "counter", "content": {"title": title},
         "data": {"value": value, "source": "s1", "format": {"decimals": decimals}}, "sources": SRC_FA if lang == "fa" else SRC_EN,
         "animation": {"in": {"type": "fade", "frames": frames}, "out": {"type": "fade", "frames": 9}}}
    if frm is not None:
        d["data"]["from"] = frm
    if unit:
        d["data"]["unit"] = unit
    if subtitle:
        d["content"]["subtitle"] = subtitle
    return d


CASES = [
    ("fullframe", line_doc("line-fa", "fa", [("بندرعباس", [4, 6.5, 3, -2, -5.5, 1, 7, 9.5, 8, 12, 10.5, 14]), ("بوشهر", [2, 1, 0, -1, -3, -1, 2, 3, 4, 3.5, 5, 6]),
                                             ("چابهار", [0, 0.5, 1, 2, 4, 6, 5, 8, 11, 13, 15, 18])], "تغییر تجارت بنادر", unit="%", subtitle="درصد نسبت به سال پیش")),
    ("overlay", line_doc("line-en40", "en", [(None, [1200 + (i * 37) % 400 for i in range(40)])], "Ships per month", decimals=0)),
    ("overlay", line_doc("line-en2", "en", [("North", [31.5, 33, 30.2, 35]), ("South", [54, 50.5, 52, 49])], "Share of trade", unit="%", preset="documentary-light")),
    ("overlay", line_doc("line-fa-neg", "fa", [(None, [-5, -2, -8, -1.5, 0])], "کسری بودجه", unit="%", preset="parchment")),
    ("fullframe", counter_doc("cnt-fa", "fa", 48600, "کشتی در سال ۱۴۰۲", subtitle="در بندرعباس")),
    ("overlay", counter_doc("cnt-en", "en", -2.5, "Change in trade", frm=10, decimals=1, unit="%")),
    ("overlay", counter_doc("cnt-fa-km", "fa", 1234567.891, "طول خط ساحلی", decimals=2, unit="کیلومتر")),
]


def png(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 1080, 1920, 3)


def _segdist(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy or 1)))
    return ((a[0] + t * dx - px) ** 2 + (a[1] + t * dy - py) ** 2) ** 0.5


def point_colours(img, lay, tol):
    """largest colour distance at the point markers' centres (and solid segments' middles) from their series' colour.
    Markers are drawn over every line, so a marker is skipped only where a LATER series' marker sits on it (the data
    overlap); a segment's middle where a later series' line crosses it."""
    worst, n = 0.0, 0
    reach = R.MARKER_R + R.LINE_W / 2 + 1
    for ln in lay["lines"]:
        c = np.array(R._rgb(ln["stroke"]))
        later = [o for o in lay["lines"] if o["series"] > ln["series"]]
        pts = [(x, y) for x, y in ln["points"] if not any(o["markers"] and min(((x - u) ** 2 + (y - v) ** 2) ** 0.5 for u, v in o["points"]) < 2 * R.MARKER_R + 2
                                                       for o in later)] if ln["markers"] else []
        segs = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(ln["points"], ln["points"][1:])] if ln["dash"] is None else []
        segs = [(x, y) for x, y in segs if not any(_segdist(x, y, a, b) < reach for o in later for a, b in zip(o["points"], o["points"][1:]))]
        for x, y in pts + segs:
            d = float(np.abs(img[int(round(y)), int(round(x))].astype(int) - c).max())
            worst, n = max(worst, d), n + 1
    return worst, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--gsap")
    ap.add_argument("--work")
    a = ap.parse_args()
    fonts = Path(a.fonts)
    if not shutil.which("node"):
        check(False, "node is not installed")
        return finish()
    css = MS.font_face_css(fonts)
    items = []
    for disp, d in CASES:
        sp = G.validate(d, disp, 120)["graphic"]
        lay = G.layout(sp, MS.measure_graphic(sp, fonts))
        ok = lay["status"] in ("OK", "WARN") and not R.contrast(sp, lay)
        check(ok, f"{d['id']} ({disp}): {lay['status']} {[i['code'] for i in lay['issues']]}, box {lay['rect']}")
        if ok:
            items.append((sp, lay))

    print("\n== C drawn in Chromium")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "jobs.json").write_text(json.dumps([R.render_svg(sp, lay, font_css=css) for sp, lay in items]), encoding="utf-8")
        (td / "probe.js").write_text(STATIC_JS, encoding="utf-8")
        r = subprocess.run(["node", str(td / "probe.js"), str(td / "jobs.json"), str(td)], capture_output=True, text=True, timeout=900)
        if r.returncode:
            check(False, "Chromium failed: " + (r.stderr or r.stdout)[-300:])
            return finish()
        out = json.loads((td / "out.json").read_text(encoding="utf-8"))
        shots = [png(td / f"s{k}.png")[0] for k in range(len(items))]
    check(not out["errors"] and all(not x["system_fonts"] for x in out["res"]), "no page error, only our web fonts drew text")
    span, bad_ink, overlaps, bad_pts, bad_safe = 0.0, [], [], [], []
    worst_c, n_c = 0.0, 0
    for (sp, lay), info, img in zip(items, out["res"], shots):
        k = R.key_of(sp["id"])
        want = {f"gx-{k}-{b['role']}-{n}": ln for b in lay["blocks"] for n, ln in enumerate(b["lines"])}
        if lay.get("count"):
            fs = lay["count"]["states"][lay["count"]["final"]]
            want[f"gx-{k}-count-{lay['count']['final']}"] = fs
        got = {t["p"]: t for t in info["texts"]}
        if set(got) != set(want):
            span = 99
        inks = []
        for p, ln in want.items():
            t = got.get(p)
            if not t:
                continue
            span = max(span, abs(t["adv"][0] - ln["x0"]), abs(t["adv"][1] - ln["x1"]))
            ink = t["ink"]
            inks.append((p, ink))
            if not SA.inside([ink[0], ink[1], ink[2] - ink[0], ink[3] - ink[1]], lay["rect"], tol=0.75):
                bad_ink.append(p)
        overlaps += [(p, q) for i, (p, a_) in enumerate(inks) for q, b_ in inks[i + 1:]
                     if a_[0] < b_[2] - 1 and b_[0] < a_[2] - 1 and a_[1] < b_[3] - 1 and b_[1] < a_[3] - 1]
        for ln in lay["lines"]:
            drawn = next((x["pts"] for x in info["lines"] if x["p"] == f"gx-{k}-line-{ln['series']}"), "")
            pts = [[float(v) for v in xy.split(",")] for xy in drawn.split()]
            if len(pts) != len(ln["points"]) or max(abs(p_[0] - q[0]) + abs(p_[1] - q[1]) for p_, q in zip(pts, ln["points"])) > 0.002:
                bad_pts.append(sp["id"])
        for part in info["parts"]:
            if part["p"].endswith("-bg") or part["p"] == f"gx-{k}" or part["p"].endswith("-clipr"):
                continue
            bx = part["box"]
            rr = [bx[0], bx[1], bx[2] - bx[0], bx[3] - bx[1]]
            if rr[2] > 0 and rr[3] > 0 and (not SA.inside(rr, SA.ALLOWED, tol=0.75) or SA.intersects(rr, SA.BAND)):
                bad_safe.append(part["p"])
        w, n = point_colours(img, lay, tol=0)
        worst_c, n_c = max(worst_c, w), n_c + n
    check(span < 1.0, f"every text (labels, ticks, legend, counter) set where the layout put it (largest difference {span:.3f} px)")
    check(not bad_ink and not overlaps, f"no text ink outside its box {bad_ink[:3]} or over other text {overlaps[:2]}")
    check(not bad_pts, f"every polyline's points are the layout's (every data point, unchanged) {bad_pts}")
    check(not bad_safe, f"everything inside the safe area, nothing in the subtitle band {bad_safe[:4]}")
    check(n_c >= 40 and worst_c <= 2, f"pixels: {n_c} point markers / solid segment middles in their series' colour (largest difference {worst_c:.0f})")
    if not a.gsap:
        return finish()

    print("\n== D the counter with the Film's Director, frame by frame")
    base = (NFP / "film/engine/base.html").read_text(encoding="utf-8")
    film_css = "\n".join(re.findall(r"@property[^}]*\}", base)) + "\n" + re.search(r"\[data-p\] \{[^}]*\}", base).group(0)
    director = (NFP / "film/kit/50_director.js").read_text(encoding="utf-8")
    S, E = 15, 105
    for sp, lay in [x for x in items if x[0]["kind"] == "counter"]:
        k = R.key_of(sp["id"])
        html = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#000}}\n{film_css}\n{css}</style></head><body>'
                f'<svg id="svg" xmlns="http://www.w3.org/2000/svg" width="1920" height="1080">{R.render_svg(sp, lay, standalone=False)}</svg>'
                f'<script src="{Path(a.gsap).resolve().as_uri()}"></script><script>window.K = {{}};\n{director}\n</script><script>'
                "const tl = gsap.timeline({ paused: true }); const D = K.Director({ sentences: [], duration: 5 }, tl, document.getElementById('svg'));\n"
                + A.anim_js(sp, lay, S, E) + "\nwindow.tl = tl; window.__warns = D.warns;</script></body></html>")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "p.html").write_text(html, encoding="utf-8")
            (td / "seek.js").write_text(SEEK_JS, encoding="utf-8")
            r = subprocess.run(["node", str(td / "seek.js"), str(td / "p.html"), str(td / "o.json"), str(S - 2), str(E + 2), k],
                               capture_output=True, text=True, timeout=300, cwd=str(NFP / "graphics"))
            res = json.loads((td / "o.json").read_text(encoding="utf-8")) if r.returncode == 0 else {"rows": [], "errors": [r.stderr[-200:]], "warns": []}
        cnt = lay["count"]
        n_in = sp["animation"]["in"]["frames"]
        bad = []
        for row in res["rows"]:
            f = row["f"]
            if not (S <= f < E):
                if row["root"]:
                    bad.append((f, "shown outside its clip"))
                continue
            want = cnt["states"][cnt["frames"][f - S] if f - S < n_in else cnt["final"]]["text"]
            if len(row["vis"]) != 1 or row["vis"][0]["text"] != want:
                bad.append((f, [v["text"] for v in row["vis"]], want))
            elif not SA.inside([row["vis"][0]["ink"][0], row["vis"][0]["ink"][1], row["vis"][0]["ink"][2] - row["vis"][0]["ink"][0],
                                row["vis"][0]["ink"][3] - row["vis"][0]["ink"][1]], lay["rect"], tol=0.75):
                bad.append((f, "ink outside the box"))
        last = [row["vis"][0]["text"] for row in res["rows"] if S + n_in <= row["f"] < E and row["vis"]]
        final = TX.format_number(sp["data"]["value"], sp["data"]["format"]["decimals"], sp["data"]["format"]["digits"], sp["data"]["unit"])
        check(res["rows"] and not bad and not res["errors"] and not res["warns"] and set(last) == {final},
              f"{sp['id']}: frames {S}..{E - 1} each show exactly the planned number ({len(cnt['states'])} states over {n_in} enter frames), "
              f"then exactly {final!r}; its ink inside the box on every frame; hidden outside the clip {bad[:2]}")
    if not a.work:
        return finish()

    print("\n== F graphic clips on the Film page and in a real MP4")
    import test_graphics_g5_film as T5
    work = Path(a.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    T5.make_image(work / "wide.png", 3200, 1800)
    docs = {"line-en": line_doc("line-en", "en", [("North", [31.5, 33, 30.2, 35, 37.5, 36]), ("South", [54, 50.5, 52, 49, 47, 48.5])], "Share of trade",
                                unit="%", anim={"in": {"type": "wipe", "frames": 15}, "out": {"type": "fade", "frames": 9}}),
            "cnt-fa": counter_doc("cnt-fa", "fa", 48600, "کشتی در سال ۱۴۰۲", subtitle="در بندرعباس")}
    gclips = [("g-line", "line-en", "over", 30, 105), ("g-cnt", "cnt-fa", "pictures", 130, 230)]
    d = T5.project(work, "film-g7", gclips=gclips, docs=docs, mapclip=False, video=False)
    b = work / "b-g7"
    T5.compose_dir(d, b, fonts)
    exp = T5.expectations(d, b, fonts)
    rdir = T5.render_copy(b, a.gsap)
    frames = sorted({f for c, _, _ in exp.values() for f in (c["start"] - 1, c["start"], (c["start"] + c["end"]) // 2, c["end"] - 1, c["end"])})
    P = T5.probe(work, rdir, frames, [T5.GF.key_of_clip(c) for c in exp], "page-g7")
    T5.check_page(P, exp, "Film page with a line chart and a counter")
    RESULTS.extend(T5.RESULTS)
    T5.RESULTS.clear()
    env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=T5.BROWSER, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    npx = ["npx", "--yes", f"hyperframes@{T5.HF_VERSION}"]
    lint = subprocess.run(npx + ["lint"], cwd=rdir, env=env, capture_output=True, text=True)
    mp4 = b / "story.mp4"
    rr = subprocess.run(npx + ["render", "--output", str(mp4), "--fps", "30", "--quality", "standard"], cwd=rdir, env=env, capture_output=True, text=True)
    check(lint.returncode == 0 and re.search(r"\b0 error", lint.stdout + lint.stderr) and rr.returncode == 0 and mp4.exists(),
          f"lint 0 errors, HyperFrames render {[ln for ln in (rr.stdout + rr.stderr).splitlines() if 'rendered in' in ln][-1:]}")
    if rr.returncode:
        return finish()
    F = png(mp4)
    c, s, l = exp["g-cnt"]
    st = l["count"]["states"]
    x0 = int(min(v["x0"] for v in st)) - 4
    x1 = int(max(v["x1"] for v in st)) + 4
    y0, y1 = int(st[0]["baseline"] - l["count"]["ascent"]) - 4, int(st[0]["baseline"] + l["count"]["descent"]) + 4
    reg = lambda f: F[f][y0:y1, x0:x1].astype(int)
    n_in = s["animation"]["in"]["frames"]
    steady = [float(np.abs(reg(f) - reg(f - 5)).mean()) for f in range(c["start"] + n_in + 6, c["end"] - 12, 5)]
    counting = [float(np.abs(reg(f) - reg(c["start"] + n_in + 10)).mean()) for f in (c["start"] + 8, c["start"] + 15, c["start"] + 25)]
    check(F.shape[0] == 450 and max(steady) < 3 and min(counting) > 3,
          f"MP4: after the count the number is steady (frame-to-frame diff <= {max(steady):.1f}), while counting it differs from the final ({min(counting):.1f}+)")
    cl, sl, ll = exp["g-line"]
    w, n = point_colours(F[(cl["start"] + cl["end"]) // 2].astype(int), ll, tol=60)
    check(n >= 10 and w <= 60, f"MP4: the line's {n} point markers / segment middles in their series' colours (largest difference {w:.0f}: grain, codec)")
    shutil.copyfile(mp4, work / "g7-film.mp4")
    for f in ((cl["start"] + cl["end"]) // 2, c["start"] + 15, c["start"] + n_in + 20):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"select=eq(n\\,{f})", "-frames:v", "1", str(work / f"mp4-{f}.png")], check=True)
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G7 RENDER TESTS PASSED" if not f else "GRAPHICS G7 RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
