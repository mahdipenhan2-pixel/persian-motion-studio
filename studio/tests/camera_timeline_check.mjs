#!/usr/bin/env node
/*
 * T3: browser check of a camera page against the SAME project composed without camera (local, no network).
 *
 *   node studio/tests/camera_timeline_check.mjs --camera <index.html> --plain <index.html> \
 *        --plan <camera_plan.json> --gsap <gsap.min.js> --out <dir>
 *
 * The page's cdnjs GSAP request is answered with a local copy of the same GSAP version (cdnjs is not reachable in
 * every sandbox). Nothing in the page is edited. Checks, at many seek times:
 *   1. no page errors; camera.js ran; timeline duration identical to the plain page
 *   2. captions identical to the plain page (position, opacity, every word colour/background)
 *   3. nothing painted by a scene ever overlaps the caption band y 560-1360 (clipped media frames included)
 *   4. caption-band pixels with captions hidden are identical to the plain page (no stray graphics at all)
 *   5. every camera move really moves: transform at start/end equals the planned from/to, and the frame changes
 *   6. seeking is deterministic (forward, backward, jump) - required by the HyperFrames renderer
 */
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const { chromium } = createRequire(import.meta.url)("playwright"); // global or local install
const arg = (k) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null; };
const cameraFile = arg("--camera"), plainFile = arg("--plain"), planFile = arg("--plan"), gsapFile = arg("--gsap");
const outDir = arg("--out");
for (const [k, v] of Object.entries({ cameraFile, plainFile, planFile, gsapFile, outDir })) {
  if (!v) { console.error("missing argument for " + k); process.exit(2); }
}
fs.mkdirSync(outDir, { recursive: true });
const BAND = [560, 1360];
const plan = JSON.parse(fs.readFileSync(planFile, "utf8"));
const results = []; let fails = 0;
const check = (ok, msg) => { results.push({ ok, msg }); if (!ok) fails++; console.log((ok ? "PASS " : "FAIL ") + msg); };

const browser = await chromium.launch();
async function open(file) {
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.route("**/gsap.min.js", (r) => r.fulfill({ path: gsapFile, contentType: "application/javascript" }));
  await page.goto(pathToFileURL(path.resolve(file)).href);
  await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 15000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((im) => im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; })));
  });
  return { page, errors };
}
const cam = await open(cameraFile);
const pln = await open(plainFile);

// ---------------------------------------------------------------- 1
check(cam.errors.length === 0 && pln.errors.length === 0, `no page errors (camera: ${cam.errors.length}, plain: ${pln.errors.length}) ${cam.errors.concat(pln.errors).join(" | ")}`);
const camInfo = await cam.page.evaluate(() => window.__nfpCamera || null);
check(camInfo && camInfo.tweens > 0, `camera.js ran (${camInfo ? camInfo.tweens : 0} tweens)`);
const durC = await cam.page.evaluate(() => window.__timelines.main.duration());
const durP = await pln.page.evaluate(() => window.__timelines.main.duration());
check(Math.abs(durC - durP) < 1e-9, `timeline duration unchanged (camera ${durC.toFixed(4)} s = plain ${durP.toFixed(4)} s)`);
const total = durP;

const seek = (p, t) => p.evaluate((t) => { window.__timelines.main.seek(t, false); }, t);
const captionState = (p) => p.evaluate(() => [...document.querySelectorAll("#stage .sentence")].map((s) => {
  const r = s.getBoundingClientRect(); const cs = getComputedStyle(s);
  return [s.id, Math.round(r.x * 100), Math.round(r.y * 100), Math.round(r.width * 100), Math.round(r.height * 100),
    cs.opacity, cs.transform, [...s.querySelectorAll(".w")].map((w) => { const c = getComputedStyle(w); return c.color + "|" + c.backgroundColor; }).join(",")];
}));
const bandHits = (p, band) => p.evaluate((band) => {
  const hits = [];
  const paints = (el) => {
    const cs = getComputedStyle(el);
    if (el.tagName === "IMG" || el.tagName.toLowerCase() === "svg") return true;
    if (cs.backgroundImage !== "none") return true;
    if (cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== "transparent") return true;
    if (["Top", "Right", "Bottom", "Left"].some((k) => parseFloat(cs["border" + k + "Width"]) > 0)) return true;
    return [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  };
  const opacity = (el) => { let o = 1; for (let e = el; e && e.id !== "scenes"; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  for (const el of document.querySelectorAll("#scenes *")) {
    if (el.closest("svg") && el.tagName.toLowerCase() !== "svg") continue;
    if (!paints(el) || opacity(el) < 0.004) continue;
    const frame = el.closest(".cam-media");
    const r = (frame || el).getBoundingClientRect();
    if (r.width < 0.5 || r.height < 0.5) continue;
    if (r.bottom > band[0] + 0.5 && r.top < band[1] - 0.5) hits.push((el.id || el.className || el.tagName) + " " + Math.round(r.top) + "-" + Math.round(r.bottom));
  }
  return hits;
}, band);

// ---------------------------------------------------------------- 2 + 3
const times = [];
for (let t = 0; t <= total + 1e-9; t += 0.2) times.push(+t.toFixed(3));
for (const row of plan) {
  if (row.move && row.move.t !== undefined) times.push(row.move.t, row.move.t + row.move.d / 2, row.move.t + row.move.d);
  if (row.transition) for (let k = 0; k <= 4; k++) times.push(row.transition.t + row.transition.d * k / 4);
}
const uniq = [...new Set(times.map((t) => +Math.min(total, Math.max(0, t)).toFixed(3)))].sort((a, b) => a - b);
let capDiff = 0, hitCount = 0; const hitSamples = [];
for (const t of uniq) {
  await seek(cam.page, t); await seek(pln.page, t);
  const a = JSON.stringify(await captionState(cam.page)), b = JSON.stringify(await captionState(pln.page));
  if (a !== b) { capDiff++; if (capDiff <= 3) console.log("  caption difference at", t); }
  const h = await bandHits(cam.page, BAND);
  if (h.length) { hitCount++; if (hitSamples.length < 5) hitSamples.push(t + ": " + h.slice(0, 3).join("; ")); }
}
check(capDiff === 0, `captions identical to the plain page at all ${uniq.length} sampled times (position, opacity, every word colour)`);
check(hitCount === 0, `no scene graphics or media inside the caption band at any of ${uniq.length} times ${hitSamples.join(" | ")}`);

// ---------------------------------------------------------------- 4 pixel check of the band with captions hidden
// captions are compared separately (check 2); the faint .deco icon already overlaps the handle strip in the original
// design and legitimately moves with the scene graphics (its geometry is covered by check 3), so both are hidden here
const hideCaptions = (p, hide) => p.evaluate((h) => {
  document.getElementById("stage").style.visibility = h ? "hidden" : "";
  document.querySelectorAll(".deco").forEach((d) => { d.style.visibility = h ? "hidden" : ""; });
}, hide);
// PNGs are decoded in a helper page (canvas) so the comparison is per pixel, not per file byte.
const cmpPage = await (await browser.newContext()).newPage();
const pixelDiff = (A, B) => cmpPage.evaluate(async ([a, b]) => {
  const load = (s) => new Promise((res) => { const im = new Image(); im.onload = () => res(im); im.src = "data:image/png;base64," + s; });
  const [ia, ib] = await Promise.all([load(a), load(b)]);
  const c = document.createElement("canvas"); c.width = ia.width; c.height = ia.height;
  const g = c.getContext("2d", { willReadFrequently: true });
  g.drawImage(ia, 0, 0); const da = g.getImageData(0, 0, c.width, c.height).data;
  g.clearRect(0, 0, c.width, c.height); g.drawImage(ib, 0, 0); const db = g.getImageData(0, 0, c.width, c.height).data;
  let n = 0, max = 0;
  for (let i = 0; i < da.length; i += 4) {
    const d = Math.max(Math.abs(da[i] - db[i]), Math.abs(da[i + 1] - db[i + 1]), Math.abs(da[i + 2] - db[i + 2]));
    if (d > 0) n++; if (d > max) max = d;
  }
  return { n, max };
}, [A.toString("base64"), B.toString("base64")]);
const REGIONS = [["caption band", BAND[0], BAND[1]], ["progress bar strip", 56, 80], ["handle strip", 1652, 1720]];
const pixTimes = uniq.filter((_, i) => i % 3 === 0);
const stats = Object.fromEntries(REGIONS.map(([n]) => [n, { n: 0, max: 0, bad: 0 }]));
await hideCaptions(cam.page, true); await hideCaptions(pln.page, true);
for (const t of pixTimes) {
  await seek(cam.page, t); await seek(pln.page, t);
  for (const [name, y0, y1] of REGIONS) {
    const clip = { x: 0, y: y0, width: 1080, height: y1 - y0 };
    const A = await cam.page.screenshot({ clip }), B = await pln.page.screenshot({ clip });
    if (A.equals(B)) continue;
    const d = await pixelDiff(A, B), st = stats[name];
    st.n = Math.max(st.n, d.n); st.max = Math.max(st.max, d.max);
    if (d.n > 50 || d.max > 3) { st.bad++; if (st.bad === 1) { fs.writeFileSync(path.join(outDir, `diff-${name.replace(/ /g, "-")}-camera-${t}.png`), A); fs.writeFileSync(path.join(outDir, `diff-${name.replace(/ /g, "-")}-plain-${t}.png`), B); } }
  }
}
await hideCaptions(cam.page, false); await hideCaptions(pln.page, false);
for (const [name, y0, y1] of REGIONS) {
  const st = stats[name];
  check(st.bad === 0, `${name} y ${y0}-${y1} (captions hidden) matches the plain page at ${pixTimes.length} times: at most ${st.n} of ${1080 * (y1 - y0)} pixels differ, by at most ${st.max}/255 (limit 50 px, 3 levels)`);
}

// ---------------------------------------------------------------- 5 moves really happen
const matrix = (p, id) => p.evaluate((id) => {
  const m = new DOMMatrixReadOnly(getComputedStyle(document.getElementById(id)).transform);
  return { s: Math.hypot(m.a, m.b), x: m.e, y: m.f };
}, id);
const near = (a, b, tol) => Math.abs(a.s - b.s) < 0.002 && Math.abs(a.x - b.x) < tol && Math.abs(a.y - b.y) < tol;
for (const row of plan) {
  const mv = row.move;
  if (!mv || mv.t === undefined) continue;
  const id = (mv.target === "media" ? "caml-" : "camg-") + row.scene;
  await seek(cam.page, mv.t); const a = await matrix(cam.page, id);
  await seek(cam.page, mv.t + mv.d); const b = await matrix(cam.page, id);
  const ok = near(a, mv.from, 0.6) && near(b, mv.to, 0.6);
  const frameId = mv.target === "media" ? "camm-" + row.scene : "scene-" + row.scene;
  await seek(cam.page, mv.t + 0.05);
  const shotA = await cam.page.locator("#" + frameId).screenshot();
  await seek(cam.page, mv.t + mv.d - 0.05);
  const shotB = await cam.page.locator("#" + frameId).screenshot();
  check(ok && !shotA.equals(shotB), `${row.scene} ${mv.move} on ${mv.target}: start ${JSON.stringify(a)} -> end ${JSON.stringify(b)} matches the plan and the picture changes`);
  fs.writeFileSync(path.join(outDir, `${row.scene}-start.png`), shotA);
  fs.writeFileSync(path.join(outDir, `${row.scene}-end.png`), shotB);
}

// ---------------------------------------------------------------- 5b transitions really happen and end clean
for (const row of plan) {
  const tr = row.transition;
  if (!tr) continue;
  const st = (t) => seek(cam.page, t).then(() => cam.page.evaluate((id) => {
    const cs = getComputedStyle(document.getElementById(id));
    const m = new DOMMatrixReadOnly(cs.transform);
    return { s: +Math.hypot(m.a, m.b).toFixed(4), x: +m.e.toFixed(2), clip: cs.clipPath };
  }, "scene-" + row.scene));
  const mid = await st(tr.t + tr.d * 0.3), end = await st(tr.t + tr.d + 0.01);
  const moving = tr.kind === "wipe" ? mid.clip !== end.clip : (mid.s !== 1 || mid.x !== 0);
  const clean = end.s === 1 && end.x === 0 && (tr.kind !== "wipe" || /inset\(0(px|%)?( 0(px|%)?){0,3}\)/.test(end.clip));
  check(moving && clean, `${row.scene} ${tr.kind} transition: mid ${JSON.stringify(mid)} -> end ${JSON.stringify(end)}`);
}

// ---------------------------------------------------------------- 6 seek determinism
let nondet = 0;
const dTimes = [0, total * 0.13, total * 0.37, total * 0.5, total * 0.71, total * 0.93].map((t) => +t.toFixed(3));
for (const t of dTimes) {
  await seek(cam.page, t); const A = await cam.page.screenshot();
  await seek(cam.page, total); await seek(cam.page, 0); await seek(cam.page, total / 3);
  await seek(cam.page, t); const B = await cam.page.screenshot();
  if (!A.equals(B)) { const d = await pixelDiff(A, B); nondet++; console.log(`  seek ${t}s: ${d.n} pixels differ, max ${d.max}/255`); }
  fs.writeFileSync(path.join(outDir, `frame-${t.toFixed(2)}s.png`), A);
}
check(nondet === 0, `seeking is deterministic (forward/backward/jump) at ${dTimes.length} times`);

fs.writeFileSync(path.join(outDir, "t3_report.json"), JSON.stringify({ fails, results, samples: uniq.length }, null, 2));
await browser.close();
console.log(`\nT3: ${results.length} checks, ` + (fails ? `${fails} FAILED` : "ALL PASSED"));
process.exit(fails ? 1 : 0);
