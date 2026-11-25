#!/usr/bin/env python3
"""M2f - REAL measurement and render of the labels in the local Chromium with the local fonts (Vazirmatn + Inter woff2,
the files Film uses; nothing is downloaded): the browser's own boxes of the drawn text agree with the measurement and
with the planned boxes, no drawn label overlaps another label or a marker, Persian / English / mixed text runs in the
right direction, the fonts really loaded, and measuring is deterministic.

  python3 nfp/mapmotion/tests/test_mapmotion_m2f_render.py --fonts <folder with the woff2 files>
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
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
from mapmotion.tools import measure as MS            # noqa: E402
from mapmotion import render as R              # noqa: E402
import test_mapmotion_m2f as T                 # noqa: E402

RESULTS = []
JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const svgs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  const out = [];
  for (const svg of svgs) {
    await p.setContent('<!doctype html><html><body style="margin:0">' + svg + '</body></html>');
    out.push(await p.evaluate(async () => {
      await document.fonts.ready;
      const loaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight).sort();
      const r = e => { const q = e.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; };
      const texts = [...document.querySelectorAll('#labels text')].map(t => {
        const n = t.getNumberOfChars();
        const pos = []; for (let i = 0; i < n; i++) pos.push(t.getStartPositionOfChar(i).x);
        const bb = t.getBBox();
        return { id: t.dataset.label, text: t.textContent, rect: [bb.x, bb.y, bb.x + bb.width, bb.y + bb.height], pos };
      });
      const markers = [...document.querySelectorAll('#markers > *')].map(r);
      return { loaded, texts, markers };
    }));
  }
  await b.close();
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def overlap(a, b, tol=0.5):
    return a[0] < b[2] - tol and b[0] < a[2] - tol and a[1] < b[3] - tol and b[1] < a[3] - tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True, help="folder with vazirmatn-arabic-400/700 and inter-latin-400/700 woff2")
    a = ap.parse_args()
    if not shutil.which("node"):
        check(False, "node is not installed: the real measurement / render cannot run")
        return finish()
    cam = {"keyframes": [{"frame": 0, "view": {"full": True}}, {"frame": 90, "view": {"points": ["teh", "qom", "kas"], "pad_px": 160}},
                         {"frame": 150, "view": {"full": True}}]}
    plan, geo, scene, sp0 = T.setup(camera=cam, extra_points=[{"id": "teh-en", "location": "teh", "start": 0, "end": 180, "lang": "en"},
                                                              {"id": "yaz-en", "location": "yaz", "start": 0, "end": 180, "lang": "en"}])
    st = sp0["labels"]["style"]
    texts = [t["text"] for t in sp0["labels"]["texts"].values()]
    metrics = MS.measure(texts, st["size"], st["weight"], a.fonts)
    check(metrics == MS.measure(texts, st["size"], st["weight"], a.fonts), f"measuring is deterministic (browser {metrics['browser']})")
    check(set(metrics["fonts"]) == {f for _, _, f in MS.FACES} and all(len(v) == 64 for v in metrics["fonts"].values()), "the metrics record the font files' sha256")
    import mapmotion as M
    sp = M.resolve(scene, plan, geo, metrics=metrics)
    check(not any(i["code"] == "label_metrics_estimated" for i in sp["qc"]["issues"]) and all(t["measured"] for t in sp["labels"]["texts"].values()),
          "with the measurement no label size is estimated")
    css = MS.font_face_css(a.fonts)
    bm = R.basemap_paths(sp, plan)
    shots = [None, 0, 60, 90, 120, 179]
    svgs = [R.render_svg(sp, plan, f, bm, font_css=css) for f in shots]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "svgs.json").write_text(json.dumps(svgs), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        r = subprocess.run(["node", str(td / "probe.js"), str(td / "svgs.json"), str(td / "out.json")], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            check(False, f"Chromium failed: {(r.stderr or r.stdout)[-300:]}")
            return finish()
        out = json.loads((td / "out.json").read_text(encoding="utf-8"))
    used = {f"Vazirmatn {int(st['weight'])}", f"Inter {int(st['weight'])}"}       # a face is loaded when text uses it
    check(all(used <= set(o["loaded"]) for o in out if o["texts"]), f"the local faces the labels use ({sorted(used)}) are loaded in every rendered frame")
    by = {(m["text"]): m for m in metrics["items"]}
    worst_w = worst_h = worst_pos = 0.0
    n_lab, n_plan = 0, 0
    over = 0
    rtl_ok = ltr_ok = 0
    rtl_bad = ltr_bad = 0
    for f, o in zip(shots, out):
        rows = {x["id"]: x for x in (sp["labels"]["static"] if f is None else sp["labels"]["frames"][f]["labels"]) if x["shown"]}
        n_plan += len(rows)
        boxes = []
        for t in o["texts"]:
            n_lab += 1
            m = by[t["text"]]
            w, h = t["rect"][2] - t["rect"][0], t["rect"][3] - t["rect"][1]
            worst_w = max(worst_w, abs(w - m["width"]))
            worst_h = max(worst_h, abs(h - (m["ascent"] + m["descent"])))
            plan_box = rows[t["id"]]["box"]
            pad = st["padding"] + st["halo_width"] / 2
            want = (plan_box[0] + pad, plan_box[1] + pad, plan_box[0] + plan_box[2] - pad, plan_box[1] + plan_box[3] - pad)
            worst_pos = max(worst_pos, max(abs(x - y) for x, y in zip(t["rect"], want)))
            boxes.append(t["rect"])
            d = sp["labels"]["texts"][t["id"]]["direction"]
            ps = t["pos"]
            if len(ps) > 1:
                if d == "rtl":
                    (rtl_ok, rtl_bad) = (rtl_ok + 1, rtl_bad) if ps[0] > ps[-1] else (rtl_ok, rtl_bad + 1)
                else:
                    (ltr_ok, ltr_bad) = (ltr_ok + 1, ltr_bad) if ps[0] < ps[-1] else (ltr_ok, ltr_bad + 1)
        for i, b in enumerate(boxes):
            over += sum(overlap(b, c) for c in boxes[i + 1:]) + sum(overlap(b, mk) for mk in o["markers"])
    check(n_lab == n_plan and n_lab > 30, f"every placed label is drawn: {n_lab} over the static map and 5 frames (zoomed and not)")
    check(worst_w < 0.5 and worst_h < 0.5, f"the drawn text's size = the measurement (largest difference: width {worst_w:.3f} px, height {worst_h:.3f} px)")
    check(worst_pos < 0.5, f"the drawn text sits in its planned box (largest difference {worst_pos:.3f} px), zoomed or not")
    check(over == 0, f"no drawn label overlaps another label or a marker in the browser's own geometry ({over})")
    check(rtl_ok > 0 and rtl_bad == 0, f"Persian (rtl) labels run right to left: the first character is drawn rightmost ({rtl_ok} labels)")
    check(ltr_ok > 0 and ltr_bad == 0, f"English (ltr) labels run left to right ({ltr_ok} labels)")
    st0 = {t["id"]: t for t in out[0]["texts"]}
    yz = st0.get("yaz")
    if yz:
        ps, s = yz["pos"], yz["text"]
        check(ps[s.index("ی")] > ps[s.index("Y")] and ps[s.index("Y")] < ps[s.index("d")], "mixed 'یزد (Yazd)': the Persian word right, the Latin run left and itself left to right")
    kas = st0.get("kas")
    if kas:
        ps, s = kas["pos"], kas["text"]
        check(ps[s.index("ک")] > ps[s.index("۱")] and ps[s.index("۱")] < ps[s.index("۵")], "'کاشان ۱۴۰۵': the number after the word (to its left), its digits left to right")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2f RENDER TESTS PASSED" if not f else "MAP MOTION M2f RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
