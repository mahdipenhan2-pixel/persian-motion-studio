#!/usr/bin/env python3
"""G6 - comparison / bar / column for REAL in the local Chromium (film fonts), then on the Film page and in a real MP4:
  C  charts (Persian / English, overlay / full frame, negatives, zero, highlight, 12 bars) drawn over a black page:
     every line where the layout put it, only our web fonts, no text ink over a bar or outside its box, everything in
     the safe area and out of the subtitle band; PIXEL geometry: along each bar's centre line the run of its exact colour
     is as long as its laid-out length (= |value| x scale) and starts at the zero line
  F  a bar chart (overlay, over an image), a column chart (full frame) and a comparison (overlay, over a map) as graphic
     clips through the Timeline / Film path (G5) with G4 animation: the page (shown exactly on its clips' frames, lines in
     place) and a real HyperFrames MP4, whose bars / columns have their laid-out lengths (accent-coloured run, +-3 px:
     grain / vignette / codec) on fully shown frames
  python3 nfp/graphics/tests/test_graphics_g6_render.py --fonts <woff2> [--gsap <gsap.min.js> --work <dir outside the repo>]
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
  const cdp = await p.context().newCDPSession(p); await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const res = [];
  for (const [k, svg] of jobs.entries()) {
    await p.setContent('<!doctype html><html><head><style>html,body{margin:0;background:#000}</style></head><body>' + svg + '</body></html>');
    const info = await p.evaluate(async () => {
      await document.fonts.ready;
      const box = e => { const q = e.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; };
      const texts = [...document.querySelectorAll('text[data-p]')].map(t => {
        const xs = []; for (let i = 0; i < t.getNumberOfChars(); i++) xs.push(t.getStartPositionOfChar(i).x, t.getEndPositionOfChar(i).x);
        return { p: t.dataset.p, adv: [Math.min(...xs), Math.max(...xs)], ink: box(t) }; });
      const parts = [...document.querySelectorAll('[data-p]')].map(e => ({ p: e.dataset.p, box: box(e) }));
      return { texts, parts };
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


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
SRC_FA = [{"id": "s1", "title": "Yearbook", "publisher": "مرکز آمار ایران", "date": "2023", "verified": True}]
SRC_EN = [{"id": "s1", "title": "Yearbook", "publisher": "Statistical Centre of Iran", "date": "2023", "verified": True}]


def chart(gid, lang, kind, items, title, unit=None, decimals=1, subtitle=None, anim=None, preset=None):
    d = {"schema": "nfp.graphics/1", "id": gid, "mode": "final", "lang": lang, "kind": kind, "content": {"title": title},
         "data": {"source": "s1", "format": {"decimals": decimals}, "items": [dict(label=l, value=v, **({"highlight": True} if h else {})) for l, v, h in items]},
         "sources": SRC_FA if lang == "fa" else SRC_EN}
    if unit:
        d["data"]["unit"] = unit
    if subtitle:
        d["content"]["subtitle"] = subtitle
    if anim:
        d["animation"] = anim
    if preset:
        d["style"] = {"preset": preset}
    return d


CHARTS = [
    ("overlay", chart("bar-fa", "fa", "bar", [("تهران", 9.04, True), ("مشهد", 3.37, 0), ("اصفهان", 2.24, 0), ("کرج", 1.97, 0), ("شیراز", 1.87, 0)],
                      "جمعیت شهرها", subtitle="میلیون نفر")),
    ("fullframe", chart("bar-en-neg", "en", "bar", [("Bandar Abbas", 12.5, 0), ("Bushehr", -4.2, 0), ("Chabahar", 27.9, 0), ("Anzali", -11.0, 0),
                                                    ("Amirabad", 0, 0)], "Change in harbour traffic", unit="%", subtitle="Per cent, 2019 to 2023")),
    ("fullframe", chart("col-fa", "fa", "column", [(str(1395 + i).translate(FA), v, i == 5) for i, v in enumerate([12, 15, -3, 8, 22, 30])],
                        "تولید سالانه", unit="%", decimals=0, preset="parchment")),
    ("overlay", chart("col-en", "en", "column", [("North", 31.5, 0), ("South", 54.0, 1), ("East", 9.1, 0), ("West", 0.4, 0)], "Share of trade",
                      unit="%", preset="documentary-light")),
    ("overlay", chart("cmp-en", "en", "comparison", [("1953", 1250, 0), ("2023", 48600, 1)], "Ships per year", decimals=0)),
    ("fullframe", chart("cmp-fa", "fa", "comparison", [("بندرعباس", 54.2, 0), ("بوشهر", 18.7, 0), ("چابهار", 9.1, 0), ("انزلی", 0, 0)], "سهم بازار",
                        unit="%")),
    ("fullframe", chart("bar12-fa", "fa", "bar", [(n, v, 0) for n, v in zip(["تهران", "مشهد", "اصفهان", "کرج", "شیراز", "تبریز", "قم", "اهواز", "رشت", "یزد",
                                                                              "کرمان", "ارومیه"], [9.0, 3.4, 2.2, 2.0, 1.9, 1.6, 1.4, 1.3, 0.9, 0.7, 0.6, 0.5])],
                        "دوازده شهر بزرگ", subtitle="میلیون نفر")),
]


def png(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 1080, 1920, 3)          # uint8: a frame is converted when measured


def run_len(img, bar, fill, tol, horizontal):
    """the run of pixels close to `fill` along the bar's centre line -> (first, last) coordinate or None"""
    r = bar["rect"]
    if horizontal:
        y = int(r[1] + r[3] / 2)
        line = img[y, :]
    else:
        x = int(r[0] + r[2] / 2)
        line = img[:, x]
    close = np.abs(line - np.array(fill)).max(axis=1) <= tol
    mid = int(r[0] + r[2] / 2) if horizontal else int(r[1] + r[3] / 2)
    if r[2 if horizontal else 3] < 1 or not close[mid]:
        return None
    a = mid
    while a > 0 and close[a - 1]:
        a -= 1
    b = mid
    while b < len(close) - 1 and close[b + 1]:
        b += 1
    return a, b + 1


def bar_geometry(img, lay, tol, slack):
    """largest difference between each drawn bar's run and its laid-out extent"""
    worst, n = 0.0, 0
    horizontal = lay["kind"] != "column"
    for bar in lay["bars"]:
        r = bar["rect"]
        if r[2 if horizontal else 3] < 4:
            continue
        got = run_len(img, bar, R._rgb(bar["fill"]), tol, horizontal)
        want = (r[0], r[0] + r[2]) if horizontal else (r[1], r[1] + r[3])
        if got is None:
            return 99.0, n
        worst = max(worst, abs(got[0] - want[0]), abs(got[1] - want[1]))
        n += 1
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
    for disp, d in CHARTS:
        r = G.validate(d, disp, 120)
        sp = r["graphic"]
        lay = G.layout(sp, MS.measure_graphic(sp, fonts))
        ok = lay["status"] in ("OK", "WARN") and not R.contrast(sp, lay)
        check(ok, f"{d['id']} ({disp}): {lay['status']} {[i['code'] for i in lay['issues']]}, {len(lay['bars'])} bars, box {lay['rect']}")
        if ok:
            items.append((sp, lay))
    print("\n== C drawn in Chromium")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "jobs.json").write_text(json.dumps([R.render_svg(sp, lay, font_css=css) for sp, lay in items]), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        r = subprocess.run(["node", str(td / "probe.js"), str(td / "jobs.json"), str(td)], capture_output=True, text=True, timeout=900)
        if r.returncode:
            check(False, "Chromium failed: " + (r.stderr or r.stdout)[-300:])
            return finish()
        out = json.loads((td / "out.json").read_text(encoding="utf-8"))
        shots = [png(td / f"s{k}.png")[0].astype(int) for k in range(len(items))]
    check(not out["errors"] and all(not x["system_fonts"] for x in out["res"]), f"no page error, only our web fonts drew text {sorted({f for x in out['res'] for f in x['system_fonts']})}")
    span, bad_ink, bad_safe, worst_px, n_px = 0.0, [], [], 0.0, 0
    for (sp, lay), info, img in zip(items, out["res"], shots):
        k = R.key_of(sp["id"])
        want = {f"gx-{k}-{b['role']}-{n}": ln for b in lay["blocks"] for n, ln in enumerate(b["lines"])}
        got = {t["p"]: t for t in info["texts"] if t["p"] in want}
        if set(got) != set(want):
            span = 99
        bars = [[b["rect"][0], b["rect"][1], b["rect"][0] + b["rect"][2], b["rect"][1] + b["rect"][3]] for b in lay["bars"]]
        for p, ln in want.items():
            t = got.get(p)
            if not t:
                continue
            span = max(span, abs(t["adv"][0] - ln["x0"]), abs(t["adv"][1] - ln["x1"]))
            ink = t["ink"]
            if not SA.inside([ink[0], ink[1], ink[2] - ink[0], ink[3] - ink[1]], lay["rect"], tol=0.75) or \
                    any(ink[0] < b[2] - 0.5 and b[0] < ink[2] - 0.5 and ink[1] < b[3] - 0.5 and b[1] < ink[3] - 0.5 for b in bars if b[2] - b[0] > 0.5 and b[3] - b[1] > 0.5):
                bad_ink.append(p)
        for part in info["parts"]:
            if part["p"].endswith("-bg") or part["p"] == f"gx-{k}" or part["p"].endswith("-clipr"):
                continue
            bx = part["box"]
            rr = [bx[0], bx[1], bx[2] - bx[0], bx[3] - bx[1]]
            if rr[2] > 0 and rr[3] > 0 and (not SA.inside(rr, SA.ALLOWED, tol=0.75) or SA.intersects(rr, SA.BAND)):
                bad_safe.append(part["p"])
        w, n = bar_geometry(img, lay, tol=2, slack=1)
        worst_px, n_px = max(worst_px, w), n_px + n
    check(span < 1.0, f"every line set where the layout put it (largest difference {span:.3f} px)")
    check(not bad_ink, f"no text ink over a bar or outside its box {bad_ink[:4]}")
    check(not bad_safe, f"everything inside the safe area, nothing in the subtitle band {bad_safe[:4]}")
    check(n_px >= 30 and worst_px <= 1.0, f"pixel geometry: {n_px} bars / columns drawn exactly their laid-out length from the zero line "
                                          f"(largest difference {worst_px:.1f} px)")
    if not (a.gsap and a.work):
        return finish()

    print("\n== F graphic clips on the Film page and in a real MP4 (Timeline + G4 animation)")
    import test_graphics_g5_film as T5
    work = Path(a.work).resolve()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    T5.make_image(work / "wide.png", 3200, 1800)
    T5.FV.make_video(work / "v30.mp4", 30, 600, (1920, 1080))
    docs = {"bar-fa": chart("bar-fa", "fa", "bar", [("تهران", 9.04, True), ("مشهد", 3.37, 0), ("اصفهان", 2.24, 0)], "جمعیت شهرها",
                            anim={"in": {"type": "fade", "frames": 9}, "out": {"type": "fade", "frames": 9}}),
            "col-en": chart("col-en", "en", "column", [("North", 31.5, 0), ("South", 54.0, 1), ("East", 9.1, 0), ("West", -4.0, 0)], "Share of trade",
                            unit="%", anim={"in": {"type": "wipe", "frames": 12, "direction": "up"}, "out": {"type": "fade", "frames": 9}}),
            "cmp-fa": chart("cmp-fa", "fa", "comparison", [("۱۳۳۲", 1250, 0), ("۱۴۰۲", 48600, 1)], "کشتی در سال", decimals=0,
                            anim={"in": {"type": "pop", "frames": 10}, "out": {"type": "slide", "frames": 9}})}
    gclips = [("g-bar", "bar-fa", "over", 30, 100), ("g-col", "col-en", "pictures", 120, 175), ("g-cmp", "cmp-fa", "over", 200, 300)]
    d = T5.project(work, "film-g6", gclips=gclips, docs=docs, video=False)
    b = work / "b-g6"
    T5.compose_dir(d, b, fonts)
    exp = T5.expectations(d, b, fonts)
    rdir = T5.render_copy(b, a.gsap)
    frames = sorted({f for c, _, _ in exp.values() for f in (c["start"] - 1, c["start"], (c["start"] + c["end"]) // 2, c["end"] - 1, c["end"])})
    P = T5.probe(work, rdir, frames, [T5.GF.key_of_clip(c) for c in exp], "page-g6")
    T5.check_page(P, exp, "Film page with charts")
    for chk in T5.RESULTS:
        RESULTS.append(chk)
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
    check(F.shape[0] == 450 and F.shape[1:3] == (1080, 1920), f"MP4: {F.shape[0]} frames of {F.shape[2]}x{F.shape[1]}")
    worst, n = 0.0, 0
    for cid, (c, s, l) in exp.items():
        f = (c["start"] + c["end"]) // 2
        w, k_ = bar_geometry(F[f].astype(int), l, tol=60, slack=3)
        worst, n = max(worst, w), n + k_
    check(n >= 8 and worst <= 3.0, f"in the MP4 (mid clip) {n} bars / columns have their laid-out lengths (largest difference {worst:.1f} px; "
                                   "grain, vignette and the codec allow +-3)")
    shutil.copyfile(mp4, work / "charts-film.mp4")
    for cid, (c, s, l) in exp.items():
        f = (c["start"] + c["end"]) // 2
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vf", f"select=eq(n\\,{f})", "-frames:v", "1", str(work / f"mp4-{cid}-{f}.png")], check=True)
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G6 RENDER TESTS PASSED" if not f else "GRAPHICS G6 RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
