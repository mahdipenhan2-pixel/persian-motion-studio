#!/usr/bin/env python3
"""G4 - REAL animation in the local Chromium with the Film's own Director (nfp/film/kit/50_director.js) and GSAP, and the
Film page's own [data-p] / @property CSS (read from nfp/film/engine/base.html; nothing of Film is changed): every type
(none, fade, pop, wipe, slide) in Persian and English, an explicit direction, a full-frame title and a callout. Key frames
of each clip are screenshot over a black page and compared with the static drawing:
  - before the clip and from its end on: nothing drawn (the graphic never outlives its clip)
  - frame start: the enter's first state (folded / transparent); start + n_in .. end - n_out: exactly the static drawing
  - mid enter / mid exit: partly drawn, in the right direction (wipe revealed / hidden from the reading-start side,
    slide coming from / leaving towards the right side, pop about its centre)
  - never a pixel outside the graphic's extent; panel / text never keyed (their transform stays identity)
  - no Director warning, no page error
  python3 nfp/graphics/tests/test_graphics_g4_render.py --gsap <gsap.min.js> --fonts <woff2 folder>
"""
import argparse
import json
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
sys.path.insert(0, str(NFP))
import graphics as G                              # noqa: E402
from graphics import animate as A                 # noqa: E402
from graphics import render as R                  # noqa: E402
from graphics.tools import measure as MS          # noqa: E402

RESULTS = []
S, E = 15, 75
JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [jobFile, outDir] = process.argv.slice(2);
  const jobs = JSON.parse(fs.readFileSync(jobFile, 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const errors = []; p.on('pageerror', e => errors.push(String(e)));
  const res = [];
  for (const [k, job] of jobs.entries()) {
    await p.goto('file://' + job.page);
    await p.evaluate(() => document.fonts.ready);
    const rows = [];
    for (const f of job.frames) {
      const info = await p.evaluate(([f, key]) => {
        if (window.tl) window.tl.seek(f / 30, false);
        const q = s => document.querySelector('[data-p="' + s + '"]');
        const m = e => { const t = getComputedStyle(e).transform; return t === 'none' ? [1, 0, 0, 1, 0, 0] : t.match(/-?[\d.e]+/g).map(Number); };
        const still = [...document.querySelectorAll('[data-p]')].filter(e => !/^gx-[^]*?(-body|-clipr)?$/.test(e.dataset.p) || /-(panel|rule|bg|title-\d+|subtitle-\d+|body-\d+|leader|dot|badge)$/.test(e.dataset.p))
          .filter(e => e.dataset.p !== 'gx-' + key && e.dataset.p !== 'gx-' + key + '-body' && e.dataset.p !== 'gx-' + key + '-clipr')
          .map(e => ({ p: e.dataset.p, m: m(e), o: getComputedStyle(e).opacity }));
        return { f, display: getComputedStyle(q('gx-' + key)).display, opacity: getComputedStyle(q('gx-' + key + '-body')).opacity, still };
      }, [f, job.key]);
      await p.screenshot({ path: outDir + '/j' + k + '-f' + f + '.png' });
      rows.push(info);
    }
    res.push({ rows, warns: await p.evaluate(() => window.__warns || []) });
  }
  await b.close();
  fs.writeFileSync(outDir + '/out.json', JSON.stringify({ res, errors }));
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def film_css():
    """The Film page's own animation CSS: the @property registrations and the [data-p] transform rule (read, not changed)."""
    base = (NFP / "film/engine/base.html").read_text(encoding="utf-8")
    props = re.findall(r"@property[^}]*\}", base)
    rule = re.search(r"\[data-p\] \{[^}]*\}", base).group(0)
    assert len(props) >= 5 and "transform-origin: 0 0" in rule
    return "\n".join(props) + "\n" + rule


def page(gsap, director, css, svg, anim):
    script = ("const tl = gsap.timeline({ paused: true });\n"
              "const D = K.Director({ sentences: [], duration: 4 }, tl, document.getElementById('svg'));\n"
              + anim + "\nwindow.tl = tl; window.__warns = D.warns;\n") if anim else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#000}}\n{css}</style></head><body>'
            f'<svg id="svg" xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">{svg}</svg>'
            f'<script src="{gsap}"></script><script>window.K = {{}};\n{director}\n</script><script>{script}</script></body></html>')


def png(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(1080, 1920, 3).astype(int)


CASES = [  # id, lang, kind, display, in, out
    ("fa-none", "fa", "lower-third", "overlay", {"type": "none"}, {"type": "none"}),
    ("fa-fade", "fa", "lower-third", "overlay", {"type": "fade", "frames": 12}, {"type": "fade", "frames": 9}),
    ("fa-pop", "fa", "lower-third", "overlay", {"type": "pop", "frames": 12}, {"type": "pop", "frames": 10}),
    ("fa-wipe", "fa", "lower-third", "overlay", {"type": "wipe", "frames": 12}, {"type": "wipe", "frames": 10}),
    ("en-wipe", "en", "lower-third", "overlay", {"type": "wipe", "frames": 12}, {"type": "wipe", "frames": 10}),
    ("fa-slide", "fa", "lower-third", "overlay", {"type": "slide", "frames": 12}, {"type": "slide", "frames": 10}),
    ("en-slide", "en", "lower-third", "overlay", {"type": "slide", "frames": 12}, {"type": "slide", "frames": 10}),
    ("fa-wipe-up", "fa", "info-card", "overlay", {"type": "wipe", "frames": 12, "direction": "up"}, {"type": "fade", "frames": 6}),
    ("fa-title-ff", "fa", "title", "fullframe", {"type": "slide", "frames": 12}, {"type": "fade", "frames": 9}),
    ("en-callout", "en", "callout", "overlay", {"type": "wipe", "frames": 12}, {"type": "pop", "frames": 10}),
]
TEXT = {"fa": {"lower-third": {"title": "مریم احمدی", "subtitle": "تاریخ‌نگار، دانشگاه تهران"}, "info-card": {"title": "بندر", "body": "بندر قدیمی امروز موزه است."},
               "title": {"title": "فصل اول: بندر قدیمی"}},
        "en": {"lower-third": {"title": "Maryam Ahmadi", "subtitle": "Historian, University of Tehran"}, "callout": {"body": "The old pier"}}}


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    if not shutil.which("node"):
        check(False, "node is not installed")
        return finish()
    fonts = Path(a.fonts)
    css = film_css() + MS.font_face_css(fonts)
    director = (NFP / "film/kit/50_director.js").read_text(encoding="utf-8")
    gsap = Path(a.gsap).resolve().as_uri()
    jobs, meta = [], []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for cid, lang, kind, disp, a_in, a_out in CASES:
            d = {"schema": "nfp.graphics/1", "id": cid, "mode": "final", "lang": lang, "kind": kind, "content": TEXT[lang][kind],
                 "animation": {"in": a_in, "out": a_out}}
            if kind == "callout":
                d["place"] = {"at": [600, 420]}
            sp = G.validate(d, disp, E - S)["graphic"]
            lay = G.layout(sp, MS.measure_graphic(sp, fonts))
            svg = R.render_svg(sp, lay)
            ni, no = sp["animation"]["in"]["frames"], sp["animation"]["out"]["frames"]
            frames = sorted({S - 1, S, S + 2, S + max(1, ni // 2), S + ni, (S + E) // 2, min(E - no, E - 1), E - no + max(1, no // 2), E - 1, E, E + 1})
            for name, anim, fr in (("static", None, [0]), ("anim", A.anim_js(sp, lay, S, E), frames)):
                f = td / f"{cid}-{name}.html"
                f.write_text(page(gsap, director, css, svg, anim), encoding="utf-8")
                jobs.append({"page": str(f), "frames": fr, "key": R.key_of(sp["id"])})
            meta.append((cid, sp, lay, frames, ni, no))
        (td / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        r = subprocess.run(["node", str(td / "probe.js"), str(td / "jobs.json"), str(td)], capture_output=True, text=True, timeout=1200,
                           cwd=str(NFP / "graphics"))
        if r.returncode:
            check(False, "Chromium failed: " + (r.stderr or r.stdout)[-400:])
            return finish()
        out = json.loads((td / "out.json").read_text(encoding="utf-8"))
        imgs = {}
        for j, job in enumerate(jobs):
            for f in job["frames"]:
                imgs[(j, f)] = png(td / f"j{j}-f{f}.png")

    check(not out["errors"] and all(not x["warns"] for x in out["res"]), f"no page error {out['errors'][:1]}, no Director warning")
    for n, (cid, sp, lay, frames, ni, no) in enumerate(meta):
        static = imgs[(2 * n, 0)]
        rows = {x["f"]: x for x in out["res"][2 * n + 1]["rows"]}
        im = {f: imgs[(2 * n + 1, f)] for f in frames}
        ex = R.extent(sp, lay)
        x0, y0, x1, y1 = int(ex[0]) - 1, int(ex[1]) - 1, int(ex[0] + ex[2]) + 2, int(ex[1] + ex[3]) + 2
        ff = sp["display"] == "fullframe"
        bgc = np.array(R._rgb(sp["style"]["colors"]["background"])) if ff else np.zeros(3)

        def blank(img):              # largest difference from "nothing of the graphic" (full frame: only its background)
            return float(np.abs(img - (bgc if ff else 0)).max())

        def outside(img):            # largest pixel value outside the extent (a full frame's background excluded)
            m = np.ones(img.shape[:2], bool)
            m[max(0, y0):y1, max(0, x0):x1] = False
            return float(np.abs(img[m] - (bgc if ff else 0)).max())

        def drawn_cols(img):         # columns of the extent with something drawn
            reg = np.abs(img[max(0, y0):y1, max(0, x0):x1] - (bgc if ff else 0)).sum(axis=2) > 30
            cols = np.nonzero(reg.any(axis=0))[0]
            rows_ = np.nonzero(reg.any(axis=1))[0]
            return (cols.min() + max(0, x0), cols.max() + max(0, x0), rows_.min() + max(0, y0), rows_.max() + max(0, y0), reg) if len(cols) else None

        full = drawn_cols(static)
        hidden = [f for f in (S - 1, E, E + 1) if rows[f]["display"] != "none" or np.abs(im[f]).max() > 0]
        last_full = min(E - no, E - 1)                # the last fully shown frame (E - 1 when there is no exit)
        same = [f for f in (S + ni, (S + E) // 2, last_full) if np.abs(im[f] - static).max() > 0]
        outs = max(outside(im[f]) for f in frames if S <= f < E)
        moved = [s["p"] for f in frames for s in rows[f]["still"] if s["m"] != [1, 0, 0, 1, 0, 0] or s["o"] != "1"]
        check(not hidden and not same and outs == 0 and not moved,
              f"{cid}: nothing before {S} / from {E}; frames {S + ni}, {(S + E) // 2}, {last_full} = the static drawing exactly; "
              f"never a pixel outside its extent; panel / text never moved {moved[:2]}")
        t_in = sp["animation"]["in"]["type"]
        mid_in, mid_out = S + max(1, ni // 2), E - no + max(1, no // 2)
        if t_in == "none":
            check(np.abs(im[S] - static).max() == 0, f"{cid}: cut in - frame {S} is already the full drawing")
            continue
        first = blank(im[S]) if not ff else float(np.abs(im[S][y0 + 1:y1 - 1, x0 + 1:x1 - 1] - bgc).max())
        check(first == 0, f"{cid}: frame {S} (enter's first state) shows nothing of the graphic" + (" - only its background (cut in)" if ff else ""))
        part = drawn_cols(im[mid_in])
        d = sp["animation"]["in"]["direction"]
        if t_in == "wipe":
            if d in ("left", "right"):
                grows_from_right = part[1] >= full[1] - 2 and part[0] > full[0] + 20
                grows_from_left = part[0] <= full[0] + 2 and part[1] < full[1] - 20
                ok = grows_from_right if d == "left" else grows_from_left
                check(ok, f"{cid}: wipe {d}, mid enter (frame {mid_in}) revealed from the {'right' if d == 'left' else 'left'} edge "
                          f"(drawn x {part[0]}..{part[1]} of {full[0]}..{full[1]})")
            else:
                check(part[3] >= full[3] - 2 and part[2] > full[2] + 10, f"{cid}: wipe up, mid enter revealed from the bottom (y {part[2]}..{part[3]} of {full[2]}..{full[3]})")
        elif t_in == "slide":
            sm = np.abs(im[mid_in] - (bgc if ff else 0)).sum(axis=2)
            st = np.abs(static - (bgc if ff else 0)).sum(axis=2)
            cx_m, cx_s = (sm * np.arange(1920)).sum() / sm.sum(), (st * np.arange(1920)).sum() / st.sum()
            check((cx_m > cx_s + 3) if d == "left" else (cx_m < cx_s - 3),
                  f"{cid}: slide {d}, mid enter the drawing is {cx_m - cx_s:+.1f} px from its place (coming from the {'right' if d == 'left' else 'left'})")
        elif t_in == "pop":
            early = drawn_cols(im[S + 2])
            cf = (full[0] + full[1]) / 2
            check(early[0] > full[0] + 5 and early[1] < full[1] - 5 and abs((early[0] + early[1]) / 2 - cf) < 3 and abs((part[0] + part[1]) / 2 - cf) < 3,
                  f"{cid}: pop about its centre: frame {S + 2} smaller (x {early[0]}..{early[1]} of {full[0]}..{full[1]}), centred at frame {S + 2} and mid enter "
                  f"(overshoot x {part[0]}..{part[1]}, inside the clip)")
        elif t_in == "fade":
            v = float(rows[mid_in]["opacity"])
            check(0 < v < 1 and 0 < np.abs(im[mid_in]).max() < np.abs(static).max() + 1, f"{cid}: fade, mid enter opacity {v:.2f}")
        t_out = sp["animation"]["out"]["type"]
        po = drawn_cols(im[mid_out])
        if t_out == "wipe":
            d = sp["animation"]["out"]["direction"]
            ok = (po[0] <= full[0] + 2 and po[1] < full[1] - 20) if d == "left" else (po[1] >= full[1] - 2 and po[0] > full[0] + 20)
            check(ok, f"{cid}: wipe {d}, mid exit hidden from the {'right' if d == 'left' else 'left'} edge (x {po[0]}..{po[1]})")
        elif t_out == "slide":
            d = sp["animation"]["out"]["direction"]
            sm = np.abs(im[mid_out]).sum(axis=2)
            st = np.abs(static).sum(axis=2)
            cx_m, cx_s = (sm * np.arange(1920)).sum() / sm.sum(), (st * np.arange(1920)).sum() / st.sum()
            check((cx_m < cx_s - 3) if d == "left" else (cx_m > cx_s + 3), f"{cid}: slide {d}, mid exit moved {cx_m - cx_s:+.1f} px (leaving {d})")
        elif t_out in ("fade", "pop"):
            v = float(rows[E - 1]["opacity"])
            check(0 <= v < 1, f"{cid}: {t_out} out, last frame {E - 1} not yet gone (opacity {v:.2f}), frame {E} gone")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G4 RENDER TESTS PASSED" if not f else "GRAPHICS G4 RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
