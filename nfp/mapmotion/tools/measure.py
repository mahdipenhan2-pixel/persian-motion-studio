"""NFP Map Motion - M2f tool: measuring label text in the local Chromium with the local fonts - the same renderer and
font files that draw the result - and the @font-face CSS that embeds those fonts. A TOOL, outside the engine core
(nfp/mapmotion/tools/): the only part of Map Motion that runs another program (node with its playwright module, both
already in the environment; nothing is downloaded) and writes (temporary) files - the engine itself does neither.

  font_face_css(fonts_dir) -> @font-face rules with the woff2 files embedded as data: URLs (Vazirmatn 400 / 700 for
                              Arabic script, Inter 400 / 700 for Latin - the files Film uses)
  measure(texts, size, weight, fonts_dir) -> {"schema": "nfp.mapmotion.labelmetrics/1", "browser": "...",
      "fonts": {file: sha256}, "items": [{"text", "size", "weight", "direction", "width", "ascent", "descent"}]}
The four local faces must be LOADED by the browser (checked: no silent fallback font), else measuring fails.
Each text is laid out as an SVG <text> with the label font stack, size, weight and direction (labels.direction), and
measured with getBBox: width, and ascent / descent from the baseline. Items are sorted (text, size, weight), so the
document is the same for the same inputs, browser and fonts (their versions are recorded in it).
"""
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..labels import FONT_STACK, direction

FACES = (("Vazirmatn", 400, "vazirmatn-arabic-400-normal.woff2"), ("Vazirmatn", 700, "vazirmatn-arabic-700-normal.woff2"),
         ("Inter", 400, "inter-latin-400-normal.woff2"), ("Inter", 700, "inter-latin-700-normal.woff2"))
METRICS_SCHEMA = "nfp.mapmotion.labelmetrics/1"
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
    const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('width', '4000'); svg.setAttribute('height', '400');
    document.body.appendChild(svg);
    return { items: job.items.map(it => {
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', '2000'); t.setAttribute('y', '200'); t.setAttribute('text-anchor', 'middle');
      t.setAttribute('font-family', job.family); t.setAttribute('font-size', String(it.size));
      t.setAttribute('font-weight', String(it.weight)); t.setAttribute('direction', it.direction);
      t.textContent = it.text; svg.appendChild(t);
      const bb = t.getBBox(); t.remove();
      return Object.assign({}, it, { width: bb.width, ascent: 200 - bb.y, descent: bb.y + bb.height - 200 });
    }) };
  }, job);
  if (out.error) { console.error(out.error); process.exit(2); }
  fs.writeFileSync(process.argv[3], JSON.stringify({ browser: b.version(), items: out.items }));
  await b.close();
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def _font_files(fonts_dir):
    d = Path(fonts_dir)
    missing = [f for _, _, f in FACES if not (d / f).is_file()]
    if missing:
        raise FileNotFoundError(f"local font files missing in {d}: {', '.join(missing)}")
    return d


def font_face_css(fonts_dir):
    d = _font_files(fonts_dir)
    rules = []
    for fam, w, f in FACES:
        b64 = base64.b64encode((d / f).read_bytes()).decode("ascii")
        rules.append(f'@font-face{{font-family:"{fam}";src:url(data:font/woff2;base64,{b64}) format("woff2");font-weight:{w};'
                     'font-style:normal;font-display:block}')
    return "".join(rules)


def measure(texts, size, weight, fonts_dir, node=None, timeout=300):
    d = _font_files(fonts_dir)
    node = node or shutil.which("node")
    if not node:
        raise RuntimeError("node is not installed: label text cannot be measured (labels would use estimates)")
    items = sorted({(t, float(size), int(weight)) for t in texts if isinstance(t, str) and t})
    job = {"css": font_face_css(d), "family": FONT_STACK,
           "items": [{"text": t, "size": s, "weight": w, "direction": direction(t)} for t, s, w in items]}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "job.json").write_text(json.dumps(job), encoding="utf-8")
        (td / "measure.js").write_text(JS, encoding="utf-8")
        try:
            r = subprocess.run([node, str(td / "measure.js"), str(td / "job.json"), str(td / "out.json")],
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"measuring label text in Chromium took longer than {timeout} s") from None
        if r.returncode != 0:
            raise RuntimeError("measuring label text in Chromium failed: " + (r.stderr or r.stdout)[-400:])
        res = json.loads((td / "out.json").read_text(encoding="utf-8"))
    out = [{"text": it["text"], "size": it["size"], "weight": it["weight"], "direction": it["direction"],
            "width": round(it["width"], 3), "ascent": round(it["ascent"], 3), "descent": round(it["descent"], 3)} for it in res["items"]]
    return {"schema": METRICS_SCHEMA, "browser": res["browser"],
            "fonts": {f: hashlib.sha256((d / f).read_bytes()).hexdigest() for _, _, f in FACES}, "items": out}
