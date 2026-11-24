#!/usr/bin/env node
/*
 * S3 browser part: the subtitles drawn from subtitles.json on a composed Film page.
 *   node film_subtitle_page.mjs <config.json>   config: { pages: {name: {dir, subs, shot?}}, out }
 * For every cue: seek to its middle -> which cues are visible, how many rendered lines, their size, text and direction.
 * Karaoke: for every word, seek to its middle -> which word is highlighted (yellow background); also just before it.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const NET = [], res = {};
const browser = await chromium.launch();
for (const [name, P] of Object.entries(cfg.pages)) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage(); const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "warning" || m.type() === "error") errors.push(m.text()); });
  await page.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:")) return r.continue(); NET.push(u); r.abort(); });
  await page.goto("file://" + path.join(P.dir, "index.html"));
  await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  const r = await page.evaluate((subs) => {
    const tl = window.__timelines.main, out = { lang: document.documentElement.lang, dir: document.documentElement.dir };
    const band = document.getElementById("band");
    out.band_display = getComputedStyle(band).display;
    out.legacy_sentences = document.querySelectorAll(".sentence").length;
    out.cue_elements = document.querySelectorAll(".cue").length;
    const first = document.querySelector(".cue");
    if (first) { const cs = getComputedStyle(first); out.cue_font = cs.fontFamily; out.cue_direction = cs.direction;
      out.cue_style = [cs.fontSize, cs.fontWeight, cs.lineHeight, cs.color, cs.textShadow, cs.bottom, cs.left, cs.right].join(" | "); }
    out.fonts_loaded = { vazirmatn: document.fonts.check('700 56px "Vazirmatn"', "آب"), inter: document.fonts.check('700 56px "Inter"', "Ab") };
    const vis = (lo) => [...document.querySelectorAll(".cue")].filter((e) => +getComputedStyle(e).opacity > lo).map((e) => +e.id.slice(4));
    const lh = 56 * 1.32;
    out.cues = subs.cues.map((c) => {
      tl.seek((c.start + c.end) / 2, false);
      const el = document.getElementById("cue-" + c.i);
      const row = { i: c.i, visible: vis(0.99), any: vis(0.01) };
      if (el) {
        const lines = [...el.querySelectorAll(".ln")];
        row.lines = lines.map((l) => l.textContent);
        row.rendered_lines = lines.reduce((n, l) => n + Math.round(l.getBoundingClientRect().height / lh), 0);
        const rr = lines.map((l) => { const range = document.createRange(); range.selectNodeContents(l); return range.getBoundingClientRect(); });
        row.text_left = Math.min(...rr.map((x) => x.left)); row.text_right = Math.max(...rr.map((x) => x.right));
        const b = el.getBoundingClientRect(); row.box = [Math.round(b.left), Math.round(b.top), Math.round(b.right), Math.round(b.bottom)];
      }
      return row;
    });
    // between two cues of different sentences (or after the last one): at most one cue visible at any time
    out.overlap = [];
    for (let t = 0; t < tl.duration(); t += 0.05) { tl.seek(t, false); const v = vis(0.01); if (v.length > 1) out.overlap.push([+t.toFixed(2), v]); }
    if (subs.mode === "karaoke") {
      const yellow = "rgb(255, 214, 90)";
      const lit = () => [...document.querySelectorAll(".w")].filter((e) => getComputedStyle(e).backgroundColor === yellow).map((e) => e.id);
      out.words = [];
      subs.cues.forEach((c) => c.words.forEach((w, j) => {
        const id = "cw-" + c.i + "-" + j;
        tl.seek(w.start + Math.max(0.055, (w.end - w.start) / 2), false);
        const got = lit(); const e = document.getElementById(id); const r0 = e.getBoundingClientRect();
        const row = { want: id, got, x: Math.round(r0.left + r0.width / 2), top: Math.round(r0.top), cue: c.i };
        tl.seek(Math.max(0, w.start - 0.02), false);
        row.before = getComputedStyle(e).color;
        tl.seek(w.start + Math.max(0.06, w.end - w.start) + 0.15, false);
        row.after = getComputedStyle(e).color;
        out.words.push(row);
      }));
    }
    return out;
  }, P.subs);
  r.errors = errors;
  if (P.shot !== undefined) { await page.evaluate((t) => { window.__timelines.main.seek(t, false); }, P.shot);
    await page.screenshot({ path: path.join(path.dirname(cfg.out), name + ".png") }); }
  res[name] = r;
  await ctx.close();
}
res.network_requests = NET.length;
fs.writeFileSync(cfg.out, JSON.stringify(res, null, 1));
await browser.close();
