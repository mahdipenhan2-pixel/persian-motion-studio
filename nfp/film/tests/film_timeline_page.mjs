#!/usr/bin/env node
/*
 * T2 browser part: still-image clips (nfp/timeline) on a composed Film page, frame by frame.
 *   node film_timeline_page.mjs <config.json>   config: { dir, clips: [{id, start, end}], shots: [{id, frame}], out }
 * For every clip and every frame from start-1 to end: is its shot visible, the image group's --s / --x / --y, and the
 * image's box on screen (to check: covers 1920x1080, keeps its aspect ratio). Screenshots (post layers and subtitles
 * hidden) at the listed frames, to look at the real pixels.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const NET = [], errors = [];
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "warning" || m.type() === "error") errors.push(m.text()); });
await page.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:")) return r.continue(); NET.push(u); r.abort(); });
await page.goto("file://" + path.join(cfg.dir, "index.html"));
await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
await page.evaluate(() => Promise.all([document.fonts.ready, ...[...document.querySelectorAll("image")].map((i) => new Promise((ok) => {
  const im = new Image(); im.onload = im.onerror = ok; im.src = i.getAttribute("href"); }))]));
const res = await page.evaluate((clips) => {
  const tl = window.__timelines.main, out = { duration: tl.duration(), clips: {}, warns: window.__docuWarnings || [] };
  for (const c of clips) {
    const g = document.getElementById("shot-tl-" + c.id), e = g && g.querySelector('[data-p="kb-' + c.id + '"]'), im = e && e.querySelector("image");
    const rows = [];
    for (let f = Math.max(0, c.start - 1); f <= c.end; f++) {
      tl.seek(f / 30, false);
      const cs = getComputedStyle(e), b = im.getBoundingClientRect();
      rows.push({ f, vis: getComputedStyle(g).visibility, s: +cs.getPropertyValue("--s"), x: +cs.getPropertyValue("--x"), y: +cs.getPropertyValue("--y"),
                  box: [b.left, b.top, b.right, b.bottom] });
    }
    out.clips[c.id] = { found: !!im, href: im && im.getAttribute("href"), w: im && +im.getAttribute("width"), h: im && +im.getAttribute("height"),
                        par: im && im.getAttribute("preserveAspectRatio"), rows };
  }
  return out;
}, cfg.clips);
await page.addStyleTag({ content: "#post, #subs { display: none !important; }" });
res.shots = {};
for (const s of cfg.shots) {
  await page.evaluate((t) => { window.__timelines.main.seek(t, false); }, s.frame / 30);
  const file = path.join(cfg.out_dir, `${s.id}-${s.frame}.png`);
  await page.screenshot({ path: file });
  res.shots[`${s.id}-${s.frame}`] = file;
}
res.errors = errors; res.network_requests = NET.length;
fs.writeFileSync(cfg.out, JSON.stringify(res));
await browser.close();
