#!/usr/bin/env node
/*
 * Frame / layer comparison of two composed pages in local Chromium (every non-file request is blocked and counted).
 *   node film_frames.mjs <config.json>
 * config: { a: <dir with index.html>, b: <dir>, times: [s], layers: {name: css}, out: <dir>, shots: [ids] }
 * For every layer view (CSS applied to BOTH pages) and every time: number of differing pixels. Also the camera values
 * (--cx --cy --cz) and visibility of every shot group, read from the DOM, so camera equality is checked numerically.
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
fs.mkdirSync(cfg.out, { recursive: true });
const NET = [];
const browser = await chromium.launch();
async function open(dir) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage(); const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:")) return r.continue(); NET.push(u); r.abort(); });
  await page.goto("file://" + path.join(dir, "index.html"));
  await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  return { page, errors };
}
const seek = (p, t) => p.evaluate((t) => { window.__timelines.main.seek(t, false); }, t);
const css = (p, txt) => p.evaluate((txt) => { let s = document.getElementById("cmpcss"); if (!s) { s = document.createElement("style"); s.id = "cmpcss"; document.head.appendChild(s); } s.textContent = txt; }, txt);
const cmp = await (await browser.newContext()).newPage();
async function diff(a, b) {
  return cmp.evaluate(async ([a, b]) => {
    const load = (b64) => new Promise((r) => { const i = new Image(); i.onload = () => r(i); i.src = "data:image/png;base64," + b64; });
    const [ia, ib] = await Promise.all([load(a), load(b)]);
    const c = document.createElement("canvas"); c.width = ia.width; c.height = ia.height; const x = c.getContext("2d");
    x.drawImage(ia, 0, 0); const da = x.getImageData(0, 0, c.width, c.height).data;
    x.clearRect(0, 0, c.width, c.height); x.drawImage(ib, 0, 0); const db = x.getImageData(0, 0, c.width, c.height).data;
    let n = 0, mx = 0;
    for (let i = 0; i < da.length; i += 4) { const d = Math.max(Math.abs(da[i] - db[i]), Math.abs(da[i + 1] - db[i + 1]), Math.abs(da[i + 2] - db[i + 2])); if (d) { n++; if (d > mx) mx = d; } }
    return { n, max: mx };
  }, [a.toString("base64"), b.toString("base64")]);
}
const A = await open(cfg.a), B = await open(cfg.b);
const info = async (p) => p.evaluate(() => ({ duration: window.__timelines.main.duration(), shots: [...document.querySelectorAll("g.shot")].map((g) => g.id),
  warnings: (window.__docuWarnings || []).length }));
const res = { errors: { a: A.errors, b: B.errors }, info: { a: await info(A.page), b: await info(B.page) }, layers: {}, camera: [], sanity: {} };
const keepA = {};   // reference screenshots per view, for the sanity check that every view really removes something
for (const [name, rule] of Object.entries(cfg.layers)) {
  const per = [];
  for (const t of cfg.times) {
    await css(A.page, rule); await css(B.page, rule); await seek(A.page, t); await seek(B.page, t);
    const a = await A.page.screenshot(), b = await B.page.screenshot();
    const d = await diff(a, b); per.push({ t, ...d });
    (keepA[name] = keepA[name] || []).push(a);
    if (cfg.save && name === "full" && cfg.save.includes(t)) { fs.writeFileSync(path.join(cfg.out, `a_${t}.png`), a); fs.writeFileSync(path.join(cfg.out, `b_${t}.png`), b); }
  }
  res.layers[name] = { frames: per.length, differing_frames: per.filter((x) => x.n).length, max_pixels: Math.max(...per.map((x) => x.n)), per };
}
for (const [x, y] of cfg.sanity || []) {
  let k = 0; for (let i = 0; i < cfg.times.length; i++) if ((await diff(keepA[x][i], keepA[y][i])).n > 0) k++;
  res.sanity[x + " vs " + y] = k;
}
await css(A.page, ""); await css(B.page, "");
for (const t of cfg.times) {
  const cam = async (p) => { await seek(p, t); return p.evaluate(() => [...document.querySelectorAll("g.shot")].map((g) => { const cs = getComputedStyle(g);
    return [g.id, cs.visibility, ...["--cx", "--cy", "--cz"].map((k) => +(parseFloat(cs.getPropertyValue(k)) || 0).toFixed(4))]; })); };
  const ca = await cam(A.page), cb = await cam(B.page);
  res.camera.push({ t, equal: JSON.stringify(ca) === JSON.stringify(cb), a: ca });
}
res.network_requests = NET.length;
fs.writeFileSync(path.join(cfg.out, "frames.json"), JSON.stringify(res, null, 1));
console.log(JSON.stringify({ errors: res.errors, info: res.info, layers: Object.fromEntries(Object.entries(res.layers).map(([k, v]) => [k, { frames: v.frames, differing_frames: v.differing_frames, max_pixels: v.max_pixels }])),
  camera_equal: res.camera.every((c) => c.equal), sanity: res.sanity, network_requests: NET.length }));
await browser.close();
