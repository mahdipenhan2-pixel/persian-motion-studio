#!/usr/bin/env node
/*
 * F6 browser part: language, direction, fonts and the word-by-word highlight of a composed Film page.
 *   node film_lang_page.mjs <config.json>     config: { pages: {name: {dir, words: [...]}}, out }
 * For every timed word: seek to its middle, find the highlighted span (yellow background), record its id and position.
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
  await page.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:")) return r.continue(); NET.push(u); r.abort(); });
  await page.goto("file://" + path.join(P.dir, "index.html"));
  await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  const r = await page.evaluate((words) => {
    const tl = window.__timelines.main, out = { lang: document.documentElement.lang, dir: document.documentElement.dir };
    const sent = document.querySelector(".sentence"), sc = getComputedStyle(sent);
    out.sentence_direction = sc.direction; out.sentence_font = sc.fontFamily;
    out.fonts_loaded = { vazirmatn: document.fonts.check('700 56px "Vazirmatn"', "آب"), inter: document.fonts.check('700 56px "Inter"', "Ab") };
    out.font_faces = [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family + " " + f.weight);
    const lab = document.querySelector("#art text"); out.art_text_font = lab ? getComputedStyle(lab).fontFamily : null;
    out.highlight = words.map((w) => {
      tl.seek(w.mid, false);
      const on = [...document.querySelectorAll(".w")].filter((e) => getComputedStyle(e).backgroundColor === "rgb(255, 214, 90)");
      const r0 = on.length === 1 ? on[0].getBoundingClientRect() : null;
      return { want: w.id, got: on.map((e) => e.id), x: r0 ? Math.round(r0.left + r0.width / 2) : null, top: r0 ? Math.round(r0.top) : null };
    });
    out.text_order = [...document.querySelectorAll(".sentence")].map((s) => [...s.querySelectorAll(".w")].map((e) => e.textContent));
    return out;
  }, P.words);
  r.errors = errors;
  if (P.shot !== undefined) { await page.evaluate((t) => { window.__timelines.main.seek(t, false); }, P.shot); await page.screenshot({ path: path.join(path.dirname(cfg.out), name + ".png") }); }
  res[name] = r;
  await ctx.close();
}
res.network_requests = NET.length;
fs.writeFileSync(cfg.out, JSON.stringify(res, null, 1));
await browser.close();
