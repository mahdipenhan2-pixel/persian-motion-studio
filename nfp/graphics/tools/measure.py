"""NFP Graphics - G2 tool: measuring text in the local Chromium with the film's local fonts. A TOOL, outside the engine core
(nfp/graphics/tools/): the only part of Graphics that runs another program (node + its playwright module, already in the
environment; nothing is downloaded) and writes (temporary) files.

  measure(keys, fonts_dir) -> {"schema": "nfp.graphics.textmetrics/1", "browser", "fonts": {file: sha256},
                               "items": [{"text", "size", "weight", "family", "width", "ascent", "descent"}]}
      keys: [(text, size, weight, family)] - family is the graphic's own font order (styles.FONT_STACK[lang])
  measure_graphic(spec, fonts_dir) -> the metrics a graphic's layout needs (layout.requests: two rounds)
The faces are the files Film uses (FACES and the @font-face rules come from nfp/mapmotion/tools/measure.py, imported,
unchanged): Vazirmatn 400 / 700 (Persian script), Inter 400 / 700 (Latin). Guarantees:
  - every face must be LOADED (else measuring fails: never a silent fallback font);
  - a text with a character none of the faces has fails (it would be drawn with a system font, which can differ between
    machines): the browser itself reports which fonts drew each text (DevTools protocol CSS.getPlatformFontsForNode);
    any font that is not one of our web fonts is refused.
Width = the SVG text's advance (getComputedTextLength); ascent / descent from its box (getBBox) about the baseline.
Each text is laid out as an SVG <text> in its own reading direction (text.direction) - the way G3 draws it.
"""
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from mapmotion.tools.measure import FACES, font_face_css            # the film's faces (Map Motion's tool, unchanged)

from ..textlayout import requests as layout_requests
from ..text import direction

METRICS_SCHEMA = "nfp.graphics.textmetrics/1"
JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.setContent('<!doctype html><html><head><style>' + job.css + '</style></head><body></body></html>');
  const out = await p.evaluate(async (job) => {
    for (const w of [400, 700]) { await document.fonts.load(w + ' 20px Vazirmatn', 'آ'); await document.fonts.load(w + ' 20px Inter', 'A'); }
    await document.fonts.ready;
    const loaded = [400, 700].every(w => document.fonts.check(w + ' 20px Vazirmatn', 'آ') && document.fonts.check(w + ' 20px Inter', 'A'))
      && [...document.fonts].filter(f => f.status === 'loaded').length === 4;
    if (!loaded) return { error: 'the local fonts did not load' };
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('width', '6000'); svg.setAttribute('height', '600');
    document.body.appendChild(svg);
    return { items: job.items.map((it, k) => {
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', '3000'); t.setAttribute('y', '300'); t.setAttribute('font-family', it.family);
      t.setAttribute('font-size', String(it.size)); t.setAttribute('font-weight', String(it.weight));
      t.setAttribute('direction', it.direction); t.setAttribute('style', 'white-space: pre'); t.setAttribute('id', 'm' + k);
      t.textContent = it.text; svg.appendChild(t);
      const w = t.getComputedTextLength(), bb = t.getBBox();
      return { text: it.text, size: it.size, weight: it.weight, family: it.family, width: w, ascent: 300 - bb.y, descent: bb.y + bb.height - 300 };
    }) };
  }, job);
  if (out.error) { console.error(out.error); process.exit(2); }
  // which fonts really drew each text (DevTools protocol): only our own web fonts may - a system font means a character
  // none of the local faces has (it would differ between machines)
  const cdp = await p.context().newCDPSession(p);
  await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
  const root = (await cdp.send('DOM.getDocument', { depth: -1 })).root.nodeId;
  const bad = [];
  for (let k = 0; k < out.items.length; k++) {
    const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root, selector: '#m' + k });
    const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
    const sys = fonts.filter(f => !f.isCustomFont).map(f => f.familyName);
    if (sys.length) bad.push({ text: out.items[k].text, fonts: sys });
  }
  fs.writeFileSync(process.argv[3], JSON.stringify({ browser: b.version(), items: out.items, bad }));
  await b.close();
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


class FallbackGlyphError(ValueError):
    """A text has characters that none of the local faces draws."""


def measure(keys, fonts_dir, node=None, timeout=300):
    d = Path(fonts_dir)
    node = node or shutil.which("node")
    if not node:
        raise RuntimeError("node is not installed: text cannot be measured")
    keys = sorted({(t, float(s), int(w), f) for t, s, w, f in keys if isinstance(t, str) and t})
    job = {"css": font_face_css(d),
           "items": [{"text": t, "size": s, "weight": w, "family": f, "direction": direction(t)} for t, s, w, f in keys]}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "job.json").write_text(json.dumps(job), encoding="utf-8")
        (td / "measure.js").write_text(JS, encoding="utf-8")
        try:
            r = subprocess.run([node, str(td / "measure.js"), str(td / "job.json"), str(td / "out.json")],
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"measuring text in Chromium took longer than {timeout} s") from None
        if r.returncode != 0:
            raise RuntimeError("measuring text in Chromium failed: " + (r.stderr or r.stdout)[-400:])
        res = json.loads((td / "out.json").read_text(encoding="utf-8"))
    if res["bad"]:
        raise FallbackGlyphError("characters that the local fonts (Vazirmatn / Inter) do not have (drawn with system fonts "
                                 + ", ".join(sorted({f for x in res["bad"] for f in x["fonts"]})) + "), in: "
                                 + "; ".join(repr(t) for t in sorted({x["text"] for x in res["bad"]})[:5]))
    items = [{"text": it["text"], "size": it["size"], "weight": it["weight"], "family": it["family"], "width": round(it["width"], 3),
              "ascent": round(it["ascent"], 3), "descent": round(it["descent"], 3)} for it in res["items"]]
    return {"schema": METRICS_SCHEMA, "browser": res["browser"],
            "fonts": {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for _, _, f in FACES}, "items": items}


def merge(a, b):
    if a is None:
        return b
    seen = {(x["text"], x["size"], x["weight"], x["family"]): x for x in a["items"] + b["items"]}
    return dict(a, items=[seen[k] for k in sorted(seen)])


def measure_graphic(spec, fonts_dir, **kw):
    """Two rounds: the unbreakable pieces, then every run of pieces that may fit a line (layout.requests)."""
    m = measure(layout_requests(spec), fonts_dir, **kw)
    have = {(x["text"], x["size"], x["weight"], x["family"]) for x in m["items"]}
    more = [k for k in layout_requests(spec, m) if k not in have]
    return merge(m, measure(more, fonts_dir, **kw)) if more else m
