#!/usr/bin/env node
/*
 * C2 browser check of the flat_cartoon_v2 rig (local Chromium, no network, no API).
 *
 *   node nfp/character/tests/rig_render_check.mjs [--out <file.json>]
 *
 * Loads rig/00_core.js + rig/10_chars.js (+ rig.css) into a blank page; every network request is blocked and counted.
 *   1. the rig loads without errors, exposes K.chars, and requests nothing from the network
 *   2. its vocabulary equals the C1 catalogue (builds, hair, expressions; every catalogue outfit really exists)
 *   3. all builds x hair x outfits render; every SVG has all animated parts and all 12 mouth shapes
 *   4. every expression points at an existing mouth shape
 *   5. option variants (sleeve, legs, shoe type, earrings, glasses, close-up detail) render
 *   6. determinism: same spec -> same SVG (within a page, after normalising generated ids, and across fresh pages)
 *   7. rig.css turns --x/--y/--r/--s into the expected transform; custom properties do not inherit into child parts
 *   8. no Kim identity colour (and no other rig default) appears when every field is passed; negative controls prove
 *      that the check does detect a leak when a field is left out
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import path from "node:path";

const { chromium } = createRequire(import.meta.url)("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const R = path.resolve(HERE, "..", "renderers", "flat_cartoon_v2");
const CAT = JSON.parse(fs.readFileSync(path.resolve(HERE, "..", "parts", "flat_cartoon_v2.json"), "utf8"));
const PROV = JSON.parse(fs.readFileSync(path.join(R, "PROVENANCE.json"), "utf8"));
const outIdx = process.argv.indexOf("--out");
const OUT = outIdx > 0 ? process.argv[outIdx + 1] : null;

const results = [];
const check = (ok, msg) => { results.push({ ok: !!ok, msg }); console.log((ok ? "PASS " : "FAIL ") + msg); };

// every colour the rig falls back to when a field is missing (Kim identity + generic placeholders)
const KIM = PROV.kim_identity_defaults.values.map((v) => v.value.toLowerCase());
const PLACEHOLDERS = PROV.kim_identity_defaults.generic_placeholders.map((v) => v.value).filter((v) => v.startsWith("#")).map((v) => v.toLowerCase());
const SENTINEL = { skin: "#a15c38", hairColor: "#2e6b4f", eyeColor: "#1f5fa8", top: "#6b2d8f", pants: "#14506e",
  shoe: "#5c4b12", accent: "#0f8a7a", lip: "#8e1f4c", under: "#d1e8f2" };

const PARTS = ["shadow", "root", "torso", "head", "armL", "armR", "foreL", "foreR", "legL", "legR", "shinL", "shinR",
  "shoeL", "shoeR", "eyeL", "eyeR", "irisL", "irisR", "lidL", "lidR", "browL", "browR", "blush"];

const browser = await chromium.launch();
async function freshPage(withCss) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  const net = [], errors = [];
  await page.route("**/*", (r) => { if (!r.request().url().startsWith("about:")) net.push(r.request().url()); r.abort(); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.setContent(`<!doctype html><html><body><svg id="s" xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"></svg></body></html>`);
  if (withCss) await page.addStyleTag({ content: fs.readFileSync(path.join(R, "rig.css"), "utf8") });
  await page.addScriptTag({ content: fs.readFileSync(path.join(R, "rig", "00_core.js"), "utf8") });
  await page.addScriptTag({ content: fs.readFileSync(path.join(R, "rig", "10_chars.js"), "utf8") });
  return { page, net, errors };
}

// ------------------------------------------------------------------------------------------ 1
const A = await freshPage(true);
const loaded = await A.page.evaluate(() => !!(window.K && K.chars && typeof K.chars.actor === "function"));
check(loaded && A.errors.length === 0, `rig loads without errors and exposes K.chars.actor (${A.errors.join(" | ") || "no errors"})`);

// ------------------------------------------------------------------------------------------ 2
const vocab = await A.page.evaluate(() => ({
  builds: Object.keys(K.chars.BUILDS), hair: Object.keys(K.chars.HAIR), expr: Object.keys(K.chars.EXPR) }));
const same = (a, b) => JSON.stringify([...new Set(a)].sort()) === JSON.stringify([...new Set(b)].sort());
const canonicalBuilds = vocab.builds.filter((b) => !["kid", "adult"].includes(b));
check(same(canonicalBuilds, CAT.builds), `builds = catalogue (${CAT.builds.join(", ")}); rig aliases kid/adult only`);
check(same(vocab.hair, CAT.hair), `hair styles = catalogue (${CAT.hair.length})`);
check(same(vocab.expr, CAT.expressions), `expressions = catalogue (${CAT.expressions.length})`);
const outfitReal = await A.page.evaluate((outfits) => {
  const base = { build: "woman", skin: "#a15c38", hairColor: "#2e6b4f", eyeColor: "#1f5fa8", top: "#6b2d8f", pants: "#14506e", shoe: "#5c4b12", accent: "#0f8a7a", lip: "#8e1f4c", under: "#d1e8f2" };
  const norm = (s) => s.replace(/\b(clip|cr)_\d+/g, "$1_N");
  const none = norm(K.chars.actor(Object.assign({}, base, { outfit: "__no_such_outfit__" })));
  return outfits.filter((o) => norm(K.chars.actor(Object.assign({}, base, { outfit: o }))) === none);
}, CAT.outfits);
check(outfitReal.length === 0, `every catalogue outfit (${CAT.outfits.length}) changes the drawing (not silently ignored) ${outfitReal.join(",")}`);

// ------------------------------------------------------------------------------------------ 3 + 8 (positive)
const grid = await A.page.evaluate(({ builds, hair, outfits, parts, sentinel, bad }) => {
  const fails = [], leaks = [];
  let n = 0, mouthsSeen = null;
  for (const build of builds) for (const h of hair) for (const outfit of outfits) {
    const spec = Object.assign({}, sentinel, { build, hair: h, outfit, sleeve: "long", legs: "pants", shoeType: "sneaker", earrings: 1, glasses: 1 });
    let svg;
    try { svg = K.chars.actor(spec); } catch (e) { fails.push(`${build}/${h}/${outfit}: throws ${e}`); continue; }
    n++;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.innerHTML = svg;
    const have = new Set([...g.querySelectorAll("[data-p]")].map((e) => e.getAttribute("data-p")));
    const miss = parts.filter((p) => !have.has(p));
    if (miss.length) fails.push(`${build}/${h}/${outfit}: missing parts ${miss.join(",")}`);
    const mouths = [...g.querySelectorAll("[data-m]")].map((e) => e.getAttribute("data-m"));
    if (mouths.length !== 12) fails.push(`${build}/${h}/${outfit}: ${mouths.length} mouth shapes`);
    if (!mouthsSeen) mouthsSeen = mouths;
    const visible = [...g.querySelectorAll("[data-m]")].filter((e) => e.style.display !== "none").map((e) => e.getAttribute("data-m"));
    if (visible.length !== 1 || visible[0] !== "neutral") fails.push(`${build}/${h}/${outfit}: visible mouth ${visible}`);
    const low = svg.toLowerCase();
    for (const c of bad) if (low.includes(c)) leaks.push(`${build}/${h}/${outfit}: ${c}`);
  }
  return { n, fails, leaks, mouths: mouthsSeen };
}, { builds: CAT.builds, hair: CAT.hair, outfits: CAT.outfits, parts: PARTS, sentinel: SENTINEL, bad: KIM.concat(PLACEHOLDERS) });
const total = CAT.builds.length * CAT.hair.length * CAT.outfits.length;
check(grid.n === total && grid.fails.length === 0,
  `all ${total} build x hair x outfit combinations render with all ${PARTS.length} animated parts, 12 mouth shapes, neutral mouth visible ${grid.fails.slice(0, 3).join(" | ")}`);

// ------------------------------------------------------------------------------------------ 4
const exprOk = await A.page.evaluate((mouths) => Object.entries(K.chars.EXPR).filter(([k, e]) =>
  !mouths.includes(e.mouth) || !["by", "br", "ey"].every((x) => Number.isFinite(e[x]))).map(([k]) => k), grid.mouths || []);
check(exprOk.length === 0 && (grid.mouths || []).length === 12, `all ${CAT.expressions.length} expressions point at an existing mouth shape (${(grid.mouths || []).join(", ")}) ${exprOk.join(",")}`);

// ------------------------------------------------------------------------------------------ 5
const variants = await A.page.evaluate(({ sentinel, bad, sleeves, legs, shoes }) => {
  const fails = [], leaks = [];
  let n = 0;
  for (const build of ["baby", "child", "teen", "woman", "man"]) for (const sleeve of sleeves) for (const lg of legs)
    for (const shoeType of shoes) for (const earrings of [0, 1]) for (const glasses of [0, 1]) for (const detail of [0, 1]) {
      const spec = Object.assign({}, sentinel, { build, hair: "long_straight", outfit: "blazer", sleeve, legs: lg, shoeType, earrings, glasses, detail });
      try { const s = K.chars.actor(spec).toLowerCase(); n++; for (const c of bad) if (s.includes(c)) leaks.push(`${build}/${sleeve}/${lg}/${shoeType}: ${c}`); }
      catch (e) { fails.push(`${build}/${sleeve}/${lg}/${shoeType}: ${e}`); }
    }
  return { n, fails, leaks };
}, { sentinel: SENTINEL, bad: KIM.concat(PLACEHOLDERS), sleeves: CAT.sleeves, legs: CAT.legs, shoes: CAT.shoe_types });
check(variants.fails.length === 0 && variants.n === 5 * CAT.sleeves.length * CAT.legs.length * CAT.shoe_types.length * 8,
  `${variants.n} option variants render (sleeves x legs x shoe types x earrings x glasses x close-up detail, all builds)`);

// ------------------------------------------------------------------------------------------ 6
const det = await A.page.evaluate((sentinel) => {
  const spec = Object.assign({}, sentinel, { build: "woman", hair: "big80s", outfit: "dress", detail: 1, glasses: 1, earrings: 1 });
  const norm = (s) => s.replace(/\b(clip|cr)_\d+/g, "$1_N");
  const a = K.chars.actor(spec), b = K.chars.actor(spec);
  return { rawDiffers: a !== b, normEqual: norm(a) === norm(b), first: a };
}, SENTINEL);
const B = await freshPage(false);
const fresh = await B.page.evaluate((sentinel) => K.chars.actor(Object.assign({}, sentinel, { build: "woman", hair: "big80s", outfit: "dress", detail: 1, glasses: 1, earrings: 1 })), SENTINEL);
const C = await freshPage(false);
const fresh2 = await C.page.evaluate((sentinel) => K.chars.actor(Object.assign({}, sentinel, { build: "woman", hair: "big80s", outfit: "dress", detail: 1, glasses: 1, earrings: 1 })), SENTINEL);
check(det.normEqual, "same spec -> same SVG within one page (only the generated clip/clip-path ids advance)");
check(fresh === fresh2 && fresh.length > 1000, `same spec -> byte-identical SVG in two fresh pages (${fresh.length} chars)`);

// ------------------------------------------------------------------------------------------ 7
const css = await A.page.evaluate((sentinel) => {
  const svg = document.getElementById("s");
  svg.innerHTML = `<g transform="translate(400 900)">${K.chars.actor(Object.assign({}, sentinel, { build: "man", hair: "short_man", outfit: "suit" }))}</g>`;
  const head = svg.querySelector('[data-p="head"]'), lid = svg.querySelector('[data-p="lidL"]');
  const before = getComputedStyle(head).transform;
  head.style.setProperty("--x", "10"); head.style.setProperty("--y", "-4"); head.style.setProperty("--r", "90"); head.style.setProperty("--s", "2");
  const m = new DOMMatrixReadOnly(getComputedStyle(head).transform);
  const lidX = getComputedStyle(lid).getPropertyValue("--x").trim(), lidR = getComputedStyle(lid).getPropertyValue("--r").trim();
  const lidT = getComputedStyle(lid).transform;
  return { before, a: m.a, b: m.b, c: m.c, d: m.d, e: m.e, f: m.f, lidX, lidR, lidT,
    registered: ["--x", "--y", "--r", "--s", "--sx", "--sy"].every((p) => CSS.supports(`${p}: 1`)) };
}, SENTINEL);
const near = (x, y) => Math.abs(x - y) < 1e-6;
check(css.before === "matrix(1, 0, 0, 1, 0, 0)" || css.before === "none", `with rig.css a part at rest has the identity transform (${css.before})`);
check(near(css.a, 0) && near(css.b, 2) && near(css.c, -2) && near(css.d, 0) && near(css.e, 10) && near(css.f, -4),
  `--x 10, --y -4, --r 90, --s 2 -> translate(10,-4) rotate(90deg) scale(2) = matrix(${[css.a, css.b, css.c, css.d, css.e, css.f].map((v) => +v.toFixed(3)).join(", ")})`);
check(css.lidX === "0" && css.lidR === "0" && (css.lidT === "matrix(1, 0, 0, 1, 0, 0)" || css.lidT === "none"),
  `custom properties do not inherit: a child part (lidL) keeps --x ${css.lidX}, --r ${css.lidR}, transform ${css.lidT}`);
const noCss = await B.page.evaluate((sentinel) => {
  const svg = document.getElementById("s");
  svg.innerHTML = K.chars.actor(Object.assign({}, sentinel, { build: "man", hair: "short_man", outfit: "suit" }));
  const head = svg.querySelector('[data-p="head"]');
  head.style.setProperty("--x", "10");
  return getComputedStyle(head).transform;
}, SENTINEL);
check(noCss === "none", `control: without rig.css the same --x does nothing (${noCss}) - so the CSS file is what animates the rig`);

// ------------------------------------------------------------------------------------------ 8
check(grid.leaks.length === 0 && variants.leaks.length === 0,
  `no Kim identity colour (${KIM.join(", ")}) and no other rig default (${PLACEHOLDERS.join(", ")}) in ${grid.n + variants.n} renders with every field passed ${grid.leaks.concat(variants.leaks).slice(0, 3).join(" | ")}`);
const neg = await A.page.evaluate((sentinel) => {
  const full = Object.assign({}, sentinel, { build: "woman", hair: "long_straight", outfit: "blazer" });
  const drop = (k) => { const s = Object.assign({}, full); delete s[k]; return K.chars.actor(s).toLowerCase(); };
  return { eye: drop("eyeColor").includes("#5a3320"), skin: drop("skin").includes("#d99a73"), hair: drop("hairColor").includes("#1c1210"),
    accent: drop("accent").includes("#e4483f"), lip: drop("lip").includes("#c4666b") };
}, SENTINEL);
check(Object.values(neg).every(Boolean), `negative control: leaving a field out DOES leak the Kim value (eye ${neg.eye}, skin ${neg.skin}, hair ${neg.hair}, accent ${neg.accent}, lip ${neg.lip}) - the leak check is real`);

// ------------------------------------------------------------------------------------------ 1 (network)
const allNet = A.net.concat(B.net, C.net), allErr = A.errors.concat(B.errors, C.errors);
check(allNet.length === 0, `no network request from the rig (${allNet.length} blocked)`);
check(allErr.length === 0, `no page errors in any page (${allErr.length})`);

await browser.close();
const fails = results.filter((r) => !r.ok).length;
if (OUT) fs.writeFileSync(OUT, JSON.stringify({ fails, results, renders: grid.n + variants.n }, null, 2));
console.log(`\nRIG: ${results.length} checks, ` + (fails ? `${fails} FAILED` : "ALL PASSED"));
process.exit(fails ? 1 : 0);
