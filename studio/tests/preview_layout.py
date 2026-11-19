#!/usr/bin/env python3
"""
OPTIONAL local tool (not used in CI): screenshots every scene of a composed index.html with headless Chromium,
without GSAP, to check layout (text inside its zone, caption band free). Needs `pip install playwright` + chromium.

  python3 studio/tests/preview_layout.py build/studio/<project>/story/index.html out_dir
"""
import sys
from pathlib import Path


def main(index, out_dir):
    from playwright.sync_api import sync_playwright
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    url = Path(index).resolve().as_uri()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.route("**/*gsap*", lambda r: r.abort())
        pg.on("pageerror", lambda e: None)  # GSAP is blocked on purpose; the DOM is already complete
        pg.goto(url)
        scene_ids = pg.evaluate("[...document.querySelectorAll('.scene')].map(e => e.id.slice(6))")
        for sid in scene_ids:
            pg.evaluate("""(sid) => {
              document.querySelectorAll('.scene').forEach(e => e.style.opacity = e.id === 'scene-' + sid ? 1 : 0);
              document.querySelectorAll('.a').forEach(e => { e.style.opacity = 1; e.style.transform = 'none'; });
              const sents = [...document.querySelectorAll('.sentence')];
              sents.forEach(e => e.style.opacity = 0);
              const mine = sents.filter(e => e.id.startsWith('sent-' + sid + '_'));
              // show the LONGEST sentence of the scene (worst case for the caption band) with one word highlighted
              const s = mine.sort((a, b) => b.textContent.length - a.textContent.length)[0];
              s.style.opacity = 1;
              const ws = s.querySelectorAll('.w');
              ws.forEach((w, i) => { w.style.color = i < 2 ? 'rgb(239,233,220)' : ''; });
              const w = ws[Math.min(2, ws.length - 1)];
              w.style.backgroundColor = 'rgb(143,214,168)'; w.style.color = 'rgb(11,31,24)';
            }""", sid)
            overflow = pg.evaluate("""() => {
              const r = [];
              for (const z of document.querySelectorAll('.zt, .zb')) {
                if (z.scrollHeight > z.clientHeight + 2 || z.scrollWidth > z.clientWidth + 2) r.push(z.parentElement.id + ' ' + z.className + ' overflows');
                const zr = z.getBoundingClientRect();
                for (const c of z.children) { const cr = c.getBoundingClientRect();
                  if (cr.height && (cr.top < zr.top - 2 || cr.bottom > zr.bottom + 2)) r.push(z.parentElement.id + ' child outside zone'); }
              }
              const live = [...document.querySelectorAll('.sentence')].find(e => e.style.opacity === '1');
              if (live) { const b = live.getBoundingClientRect(); if (b.top < 560 || b.bottom > 1360) r.push('caption leaves the 560-1360 band: ' + Math.round(b.top) + '-' + Math.round(b.bottom)); }
              return r;
            }""")
            pg.screenshot(path=str(out / f"{sid}.png"))
            print(sid, "OK" if not overflow else "PROBLEM: " + "; ".join(overflow))
        b.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
