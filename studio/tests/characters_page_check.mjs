#!/usr/bin/env node
/*
 * T3 for the Studio character layer (C4): the composed pages in a real browser (local Chromium, local GSAP copy,
 * every network request blocked and counted). Called by studio/tests/characters_render_check.py, which prepares:
 *   --cast  render copy of the page WITH characters        --ref   the same page with cast.js emptied (no characters)
 *   --plain run_motion page of the project without fields   --nocss the cast page without rig.css
 *   --expect JSON {frames, actors:{id:{visible:[], mouth:[]}}, slot, zones}   --out dir for screenshots + results JSON
 * Pixel comparisons (cast vs ref outside the slot, captions) are done afterwards in Python on the saved screenshots.
 */
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const { chromium } = createRequire(import.meta.url)("playwright");
const arg = (n) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : null; };
const OUT = arg("--out"), EXP = JSON.parse(fs.readFileSync(arg("--expect"), "utf8"));
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const check = (ok, msg) => { results.push({ ok: !!ok, msg }); console.log((ok ? "PASS " : "FAIL ") + msg); };
const NET = [];
const browser = await chromium.launch();

async function open(dir) {
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:")) return r.continue(); NET.push(u); r.abort(); });
  await page.goto(pathToFileURL(path.join(dir, "index.html")).href, { waitUntil: "commit" });
  await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 15000 });
  await page.waitForFunction(() => document.readyState === "complete", null, { timeout: 15000 });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  return { page, errors, ctx };
}
const seek = (p, t) => p.evaluate((t) => { window.__timelines.main.seek(t, false); }, t);   // never return the timeline

const cast = await open(arg("--cast")), ref = await open(arg("--ref")), plain = await open(arg("--plain"));
const info = await cast.page.evaluate(() => ({ cast: window.__nfpCast ? { actors: window.__nfpCast.actors, keys: window.__nfpCast.keys, duration: window.__nfpCast.duration } : null,
  tl: window.__timelines.main.duration(), cam: window.__nfpCamera ? window.__nfpCamera.tweens : 0 }));
const plainDur = await plain.page.evaluate(() => window.__timelines.main.duration());
check(cast.errors.length === 0 && info.cast && info.cast.actors === EXP.n_actors,
  `cast page runs: ${info.cast ? info.cast.actors : 0} actors, ${info.cast ? info.cast.keys : 0} keys, camera ${info.cam} tweens (${cast.errors.join(" | ") || "no errors"})`);
check(Math.abs(info.tl - plainDur) < 1e-9 && Math.abs(info.cast.duration - plainDur) < 1e-9,
  `timeline duration unchanged: ${info.tl}s with characters = ${plainDur}s without`);
const refInfo = await ref.page.evaluate(() => ({ actors: document.querySelectorAll("[data-nfp-actor]").length }));
check(ref.errors.length === 0 && refInfo.actors === 0, "reference page (cast.js emptied) loads with no characters and no errors");

// rig metrics in zones.json = the real rig in this page
const metrics = await cast.page.evaluate((bh) => {
  const C = window.K.chars, out = { builds: {}, extent: {} };
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); document.body.appendChild(s);
  Object.keys(bh.builds).forEach((bn) => { const x = C.BUILDS[bn]; out.builds[bn] = { legH: x.legH, torsoH: x.torsoH, neck: x.neck, headS: x.headS, ch: x.ch, armU: x.armU, armF: x.armF, shX: x.shX }; });
  Object.keys(bh.extent).forEach((k) => { const [bn, h] = k.split("/");
    s.innerHTML = '<g transform="translate(1000 1500)">' + C.actor({ build: bn, hair: h, outfit: "tee2007", skin: "#aa8866", hairColor: "#222222", eyeColor: "#334455", top: "#123456", pants: "#654321", shoe: "#111111", accent: "#ff0000", lip: "#aa4444", under: "#eeeeee", detail: 0, earrings: 1, glasses: 1, legs: "pants", sleeve: "short", shoeType: "flat" }) + "</g>";
    const r = s.querySelector('[data-p="root"]').getBBox(); out.extent[k] = { top: Math.floor(r.y), left: Math.floor(r.x), right: Math.ceil(r.x + r.width) }; });
  out.gestures = {};
  Object.keys(bh.builds).forEach((bn) => {          // the same poses as presets.wave / presets.point
    s.innerHTML = '<g transform="translate(1000 1500)">' + C.actor({ build: bn, hair: "none", outfit: "tee2007", skin: "#aa8866", hairColor: "#222222", eyeColor: "#334455", top: "#123456", pants: "#654321", shoe: "#111111", accent: "#ff0000", lip: "#aa4444", under: "#eeeeee", detail: 0, earrings: 0, glasses: 0, legs: "pants", sleeve: "long", shoeType: "flat" }) + "</g>";
    const q = (n) => s.querySelector('[data-p="' + n + '"]'), o = s.querySelector("g").getBoundingClientRect(), O = [o.left, o.top];
    const g0 = s.firstChild.getCTM(), ox = g0.e, oy = g0.f, rc = (n) => q(n).getBoundingClientRect(), sr = s.getBoundingClientRect();
    const pose = (side, ar, fr) => { q("arm" + side).style.setProperty("--r", ar); q("fore" + side).style.setProperty("--r", fr); };
    let top = 0; [-25, -20, 0, 20, 25].forEach((fr) => { pose("R", -150, fr); top = Math.min(top, rc("armR").top - sr.top - oy); });
    pose("R", -4, -4); [-25, -20, 0, 20, 25].forEach((fr) => { pose("L", 150, fr); top = Math.min(top, rc("armL").top - sr.top - oy); });
    pose("L", 4, 4); pose("R", -80, -10); const right = rc("armR").right - sr.left - ox;
    pose("R", -4, -4); pose("L", 80, 10); const left = rc("armL").left - sr.left - ox;
    out.gestures[bn] = { wave_top: Math.floor(top), point_left: Math.floor(left), point_right: Math.ceil(right) }; });
  s.remove(); return out; }, EXP.rig_metrics);
check(JSON.stringify(metrics) === JSON.stringify({ builds: EXP.rig_metrics.builds, extent: EXP.rig_metrics.extent, gestures: EXP.rig_metrics.gestures }),
  `zones.json rig metrics equal the real rig (${Object.keys(metrics.extent).length} build/hair extents + wave/point reach of ${Object.keys(metrics.gestures).length} builds)${JSON.stringify(metrics.gestures) === JSON.stringify(EXP.rig_metrics.gestures) ? "" : " measured " + JSON.stringify(metrics.gestures)}`);

// per-frame DOM state: visibility + mouth of every actor = the planned KeyList; bounding box inside the slot
const dom = await cast.page.evaluate(async (EXP) => {
  const tl = window.__timelines.main, slotEl = document.getElementById("nfp-cast-slot-bottom").getBoundingClientRect();
  const bad = [], outside = []; let n = 0;
  EXP.frames.forEach((f, i) => {
    tl.seek(f / 30, false);
    Object.keys(EXP.actors).forEach((id) => {
      const el = document.querySelector('[data-nfp-actor="' + id + '"]');
      const self = el.querySelector('[data-p="self"]');
      const vis = getComputedStyle(self).visibility === "visible" ? 1 : 0;
      const mouths = [...el.querySelectorAll("[data-m]")].filter((m) => getComputedStyle(m).display !== "none").map((m) => m.getAttribute("data-m"));
      const e = EXP.actors[id];
      n++;
      if (vis !== e.visible[i]) bad.push(`${id}@${f} visible ${vis}/${e.visible[i]}`);
      if (mouths.length !== 1 || mouths[0] !== e.mouth[i]) bad.push(`${id}@${f} mouth ${mouths}/${e.mouth[i]}`);
      if (vis && parseFloat(getComputedStyle(self).opacity) > 0.99) {
        const r = el.querySelector('[data-p="root"]').getBoundingClientRect();
        if (r.top < slotEl.top - 0.5 || r.left < slotEl.left - 0.5 || r.right > slotEl.right + 0.5) outside.push(`${id}@${f} [${r.left.toFixed(0)},${r.top.toFixed(0)},${r.right.toFixed(0)}] slot [${slotEl.left},${slotEl.top},${slotEl.right}]`);
      }
    });
  });
  return { bad, outside, n };
}, EXP);
check(dom.bad.length === 0, `visibility and mouth of every actor match the plan on ${EXP.frames.length} frames (${dom.n} actor-frames)${dom.bad.length ? " " + dom.bad.slice(0, 6) : ""}`);
check(dom.outside.length === 0, `head, arms and body stay inside the slot whenever an actor is fully shown (bust: only the legs are cut by the slot's lower edge)${dom.outside.length ? " " + dom.outside.slice(0, 4) : ""}`);

// lip sync: every timed word of a speaker sentence shows an open mouth on its own frame
const lip = await cast.page.evaluate((words) => {
  const tl = window.__timelines.main, bad = [];
  words.forEach((w) => { tl.seek(w.f / 30, false);
    const el = document.querySelector('[data-nfp-actor="' + w.actor + '"]');
    const m = [...el.querySelectorAll("[data-m]")].filter((x) => getComputedStyle(x).display !== "none").map((x) => x.getAttribute("data-m"))[0];
    if (!["open", "small", "o", "grin", "shock"].includes(m)) bad.push(`${w.actor} '${w.text}' @${w.f}: ${m}`); });
  return bad; }, EXP.words);
check(lip.length === 0, `lip sync: all ${EXP.words.length} timed speaker words open the speaker's mouth on their own frame (real Whisper timing)${lip.length ? " " + lip.slice(0, 5) : ""}`);

// screenshots for the Python pixel comparisons (cast / ref / plain at the same times)
for (const t of EXP.shot_times) {
  for (const [k, P] of [["cast", cast], ["ref", ref], ["plain", plain]]) { await seek(P.page, t); await P.page.screenshot({ path: path.join(OUT, `${k}_${t.toFixed(2)}.png`), animations: "disabled" }); }
}
// seek determinism: the same time after different seek histories gives the same pixels
await seek(cast.page, 8.0); const A = await cast.page.screenshot();
await seek(cast.page, 30.0); await seek(cast.page, 2.0); await seek(cast.page, 17.0); await seek(cast.page, 8.0); const B = await cast.page.screenshot();
check(A.equals(B), "seek is deterministic: identical frame at 8.0s after different seek histories");

// guards: rig.css missing -> clear error, no character; a second run of cast.js is refused
const nocss = await open(arg("--nocss"));
const nc = await nocss.page.evaluate(() => document.querySelectorAll("[data-nfp-actor]").length);
check(nocss.errors.some((e) => e.includes("rig.css is not active")) && nc === 0,
  `rig.css missing: stops with a clear error and draws nothing (${nocss.errors.map((e) => e.slice(0, 80)).join(" | ")})`);
const again = await cast.page.evaluate(() => { const s = document.getElementById("nfp-cast-js").textContent;
  try { new Function(s)(); return "ran"; } catch (e) { return String(e); } });
check(again.includes("already on this page"), `running cast.js a second time is refused (${again.slice(0, 80)})`);
const inStage = await cast.page.evaluate(() => !!document.querySelector("#stage [data-nfp-actor], #stage #nfp-cast"));
check(!inStage, "no character element inside the captions (#stage)");
check(NET.length === 0, `no network request from any page (${NET.length})`);

fs.writeFileSync(path.join(OUT, "t3.json"), JSON.stringify({ results }, null, 1));
await browser.close();
const fails = results.filter((r) => !r.ok).length;
console.log(`\n${results.length} checks: ${results.length - fails} passed, ${fails} failed.`);
process.exit(fails ? 1 : 0);
