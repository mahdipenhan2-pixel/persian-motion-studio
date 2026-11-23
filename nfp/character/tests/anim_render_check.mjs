#!/usr/bin/env node
/*
 * C3d browser check: JavaScript runtime + the C3 demo (local Chromium, every network request blocked and counted).
 *
 *   node nfp/character/tests/anim_render_check.mjs [--gsap <path to a LOCAL gsap.min.js>] [--shots <dir>] [--out <file.json>]
 *
 * Fixtures are made by the Python planner on the spot (python3, offline): the golden demo KeyList, Python-sampled values,
 * a 9:16 plan and the standalone demo page. Nothing is downloaded. GSAP is optional: without a local copy the GSAP
 * equivalence check is reported as NOT RUN (never as passed).
 *
 * E1  rig + runtime load without errors and without network
 * E2  the animation profile (Python) equals the real rig: geometry, face, expressions, long hair, hair, mouths
 * E3  runtime constants equal the Python ones (18 spec fields, eases and their values)
 * E4  build: DOM id, data-nfp-fp = cast.lock.json, every part and all 12 mouths present
 * E5  no Kim / rig-default colour in the rendered character; negative controls prove the check works
 * E6  runtime state(t) equals the Python sampler at 90 frames (same maths in both languages)
 * E7  seek(t) really applies those values to the DOM; exactly one mouth visible
 * E8  seek is stateless: same picture whatever the seek order, and in a fresh page
 * E9  lip sync in the DOM: at every mouth key the displayed mouth is the planned one
 * E10 play / pause / resume / stop with the real clock
 * E11 invalid KeyLists (overlap, broken continuity, unknown part, unsorted, missing spec field) are refused
 * E12 GSAP timeline == built-in seek (optional, local GSAP only)
 * E13 9:16 (1080x1920) and 16:9 (1920x1080): the character stays inside the frame when on stage
 * E14 input security: empty / malformed spec values, Kim fallbacks, markup injection, forged fingerprint and digest,
       unsafe rig output (sanitiser), ids, duplicate placement, playback arguments, fps; SHA-256 / digest / fingerprint
       parity with Python
 * F   the standalone demo page: the 10-step scenario, checked step by step on the real page
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG = path.resolve(HERE, "..");
const RIG = path.join(PKG, "renderers", "flat_cartoon_v2");
const arg = (n) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : null; };
const OUT = arg("--out"), SHOTS = arg("--shots");
let GSAP = arg("--gsap") || process.env.NFP_GSAP || null;
if (!GSAP) { try { GSAP = require.resolve("gsap/dist/gsap.min.js"); } catch (e) { GSAP = null; } }

const results = [];
const check = (ok, msg, status) => { const st = status || (ok ? "PASS" : "FAIL"); results.push({ status: st, msg }); console.log(st + " " + msg); };
const read = (p) => fs.readFileSync(p, "utf8");
const PROFILE = JSON.parse(read(path.join(PKG, "animation", "profile_flat_cartoon_v2.json")));
const PROV = JSON.parse(read(path.join(RIG, "PROVENANCE.json")));
const LOCK = JSON.parse(read(path.join(PKG, "examples", "demo-cast", "cast.lock.json")));
const KSCHEMA = JSON.parse(read(path.join(PKG, "schema", "keylist.v1.json")));
const GOLDEN = JSON.parse(read(path.join(PKG, "examples", "demo-anim", "keylist.json")));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "nfp-c3-"));

// ------------------------------------------------------------------------------------------ fixtures (python, offline)
function py(code) {
  return execFileSync("python3", ["-c", "import sys, json; sys.path.insert(0, " + JSON.stringify(path.dirname(PKG)) + ")\n" + code],
    { encoding: "utf8", maxBuffer: 64 << 20 });
}
const FRAMES = [...new Set([0, 1, 14, 15, 16, 20, 45, 80, 96, 100, 111, 120, 135, 150, 160, 171, 180, 200, 230, 246, 247, 250, 258, 270,
  280, 290, 303, 310, 317, 320, 331, 335, 342, 350, 360, 372, 380, 386, 390, 393, 400, 405, 410, 420, 430, 440, 447, 450, 460, 470, 480,
  490, 500, 505, 510, 520, 525, 530, 539, 540].concat(Array.from({ length: 30 }, (_, i) => 7 + i * 18)))].filter((f) => f <= GOLDEN.frames).sort((a, b) => a - b);
const PYSAMPLES = JSON.parse(py(`
from character.animation.keys import sample, EASES
kl = json.load(open(${JSON.stringify(path.join(PKG, "examples", "demo-anim", "keylist.json"))}, encoding="utf-8"))
frames = ${JSON.stringify(FRAMES)}
print(json.dumps({"samples": {str(f): sample(kl, f) for f in frames},
                  "eases": {e: [EASES[e](p / 20) for p in range(21)] for e in EASES}}))`));
const KL916 = JSON.parse(py(`
from character.animation.script import plan
doc = {"schema": "nfp.anim.actions/1", "fps": 30, "duration": 9.0, "stage": {"width": 1080, "height": 1920},
       "actors": [{"id": "k", "cast": "../demo-cast", "character": "karim", "x": 540, "y": 1560, "scale": 1.6, "seed": 5}],
       "actions": [{"actor": "k", "do": "enter", "t": 0.3, "style": "pop"}, {"actor": "k", "do": "walk", "t": 1.2, "dur": 1.8, "dx": 200},
                   {"actor": "k", "do": "walk", "t": 3.6, "dur": 1.8, "dx": -200}, {"actor": "k", "do": "hop", "t": 6.0},
                   {"actor": "k", "do": "wave", "t": 6.6}]}
print(json.dumps(plan(doc, base_dir=${JSON.stringify(path.join(PKG, "examples", "demo-anim"))}), ensure_ascii=False))`));
const DEMO_HTML = path.join(TMP, "demo.html");
execFileSync("python3", [path.join(PKG, "animation", "cli.py"), "demo", path.join(PKG, "examples", "demo-anim", "actions.json"), "--html", DEMO_HTML]);

// ------------------------------------------------------------------------------------------ pages
const browser = await chromium.launch();
const NET = [];
async function page(w, h, opts) {
  opts = opts || {};
  const ctx = await browser.newContext({ viewport: { width: Math.min(w, 1920) + 40, height: Math.min(h, 1920) + 40 } });
  const p = await ctx.newPage();
  const errors = [];
  await p.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("about:") || (opts.file && u === opts.file)) return r.continue(); NET.push(u); r.abort(); });
  p.on("pageerror", (e) => errors.push(String(e)));
  if (opts.file) { await p.goto(opts.file); return { p, errors }; }
  await p.setContent(`<!doctype html><html><body style="margin:0"><svg id="s" xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"></svg>
    <svg id="s2" xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"></svg></body></html>`);
  await p.addStyleTag({ content: read(path.join(RIG, "rig.css")) });
  for (const f of ["rig/00_core.js", "rig/10_chars.js"]) await p.addScriptTag({ content: read(path.join(RIG, f)) });
  await p.addScriptTag({ content: read(path.join(PKG, "runtime", "character_runtime.js")) });
  if (opts.gsap) await p.addScriptTag({ content: read(opts.gsap) });
  return { p, errors };
}

// ------------------------------------------------------------------------------------------ E1
const A = await page(1920, 1080);
const api = await A.p.evaluate(() => ({ rt: !!window.NFPCharacterRuntime, v: window.NFPCharacterRuntime && NFPCharacterRuntime.version,
  rig: !!(window.K && K.chars), director: typeof window.Director !== "undefined" || typeof window.DIRECTOR !== "undefined" }));
check(api.rt && api.rig && !api.director && A.errors.length === 0, `rig + runtime (${api.v}) load without errors, without any Director (${A.errors.join(" | ") || "no errors"})`);

// ------------------------------------------------------------------------------------------ E2
const rig = await A.p.evaluate(() => {
  const C = K.chars, g = {}, f = {};
  ["baby", "child", "teen", "woman", "man"].forEach((b) => { const x = C.BUILDS[b]; g[b] = { legH: x.legH, torsoH: x.torsoH, armU: x.armU, armF: x.armF, headS: x.headS };
    f[b] = { ex: C.FACE[b].ex, ey: C.FACE[b].ey, ir: C.FACE[b].ir }; });
  const div = document.createElement("div");
  div.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg">' + C.actor({ build: "woman", hair: "long_straight" }) + "</svg>";
  return { g, f, expr: C.EXPR, hair: Object.keys(C.HAIR), long: Object.keys(C.HAIR).filter((h) => C.HAIR[h]("#000000").long),
    mouths: [...div.querySelectorAll("[data-m]")].map((m) => m.getAttribute("data-m")),
    parts: [...div.querySelectorAll("[data-p]")].map((m) => m.getAttribute("data-p")) };
});
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
check(same(rig.g, PROFILE.geometry) && same(rig.f, PROFILE.face), "profile geometry and face sizes equal the real rig (5 builds)");
check(same(rig.expr, PROFILE.expressions), `profile expressions equal K.chars.EXPR (${Object.keys(rig.expr).length} expressions, values included)`);
check(same(rig.long, PROFILE.long_hair) && same([...rig.hair].sort(), [...PROFILE.hair, ...Object.keys(PROFILE.hair_aliases)].sort()) &&
  same(rig.mouths, PROFILE.mouths) && PROFILE.parts.every((p) => rig.parts.includes(p)) && rig.parts.includes("hairBack"),
  "profile hair (+aliases), long hair, 12 mouths and all 23 parts (+hairBack) equal the real rig");

// ------------------------------------------------------------------------------------------ E3
const consts = await A.p.evaluate(() => ({ fields: NFPCharacterRuntime.RIG_SPEC_FIELDS, vocab: NFPCharacterRuntime.VOCAB, fps: NFPCharacterRuntime.fps, eases: Object.fromEntries(Object.entries(NFPCharacterRuntime.EASES).map(([k, f]) => [k, Array.from({ length: 21 }, (_, i) => f(i / 20))])) }));
const easeDiff = Math.max(...Object.keys(PYSAMPLES.eases).map((e) => Math.max(...PYSAMPLES.eases[e].map((v, i) => Math.abs(v - consts.eases[e][i])))));
const vocabOk = same(consts.vocab, { build: PROFILE.builds, hair: PROFILE.hair, outfit: PROFILE.outfits, shoeType: PROFILE.shoe_types,
  sleeve: PROFILE.sleeves, legs: PROFILE.legs });
check(same(consts.fields, KSCHEMA.properties.actors.items.properties.spec.required) && same(Object.keys(consts.eases).sort(), [...PROFILE.eases].sort()) && easeDiff < 1e-12 && vocabOk && consts.fps === 30,
  `runtime spec fields (18), rig vocabulary, fps 30 and eases (${Object.keys(consts.eases).length}) equal Python; ease values differ by at most ${easeDiff.toExponential(1)}`);

// ------------------------------------------------------------------------------------------ E4
await A.p.evaluate((kl) => { window.RT = NFPCharacterRuntime.create({ svg: document.getElementById("s"), keylist: kl }); }, GOLDEN);
const b = await A.p.evaluate((kl) => {
  const a = kl.actors[0], el = document.getElementById(a.dom_id);
  return { id: !!el, fp: el && el.getAttribute("data-nfp-fp"), actor: el && el.getAttribute("data-nfp-actor"),
    parts: [...el.querySelectorAll("[data-p]")].map((x) => x.getAttribute("data-p")), mouths: el.querySelectorAll("[data-m]").length,
    channels: RT.channels, dur: RT.duration };
}, GOLDEN);
check(b.id && b.fp === LOCK.characters.zahra && b.actor === "zahra", `character built as #${GOLDEN.actors[0].dom_id} with data-nfp-fp = cast.lock.json (${b.fp.slice(0, 12)}…)`);
check(PROFILE.parts.every((p) => b.parts.includes(p)) && b.parts.includes("self") && b.parts.includes("hairBack") && b.mouths === 12,
  `all 23 rig parts + hairBack + the self wrapper, 12 mouths; ${b.channels} animated channels, ${b.dur} s`);

// ------------------------------------------------------------------------------------------ E5
const KIM = PROV.kim_identity_defaults.values.map((v) => v.value.toLowerCase());
const GEN = PROV.kim_identity_defaults.generic_placeholders.map((v) => v.value).filter((v) => v.startsWith("#")).map((v) => v.toLowerCase());
const spec = GOLDEN.actors[0].spec, chosen = new Set(Object.values(spec).map((v) => String(v).toLowerCase()));
const forbidden = [...KIM, ...GEN].filter((c) => !chosen.has(c));
const svgText = (await A.p.evaluate((id) => document.getElementById(id).outerHTML, GOLDEN.actors[0].dom_id)).toLowerCase();
const found = forbidden.filter((c) => svgText.includes(c));
check(found.length === 0, `rendered character contains none of the ${forbidden.length} rig-default colours it did not choose (${forbidden.join(" ")})`);
const neg = await A.p.evaluate((s) => { const x = Object.assign({}, s); delete x.eyeColor; return K.chars.actor(x).toLowerCase().includes("#5a3320"); }, spec);
const negRt = await A.p.evaluate((kl) => { const k = JSON.parse(JSON.stringify(kl)); delete k.actors[0].spec.eyeColor;
  try { NFPCharacterRuntime.create({ svg: document.getElementById("s2"), keylist: k }); return "built"; } catch (e) { return String(e); } }, GOLDEN);
check(neg && negRt.includes("misses eyeColor"), "negative controls: the bare rig leaks Kim's eye colour when eyeColor is missing, and the runtime refuses such a spec");

// ------------------------------------------------------------------------------------------ E6
const jsStates = await A.p.evaluate((frames) => Object.fromEntries(frames.map((f) => [f, RT.state(f / RT.fps)])), FRAMES);
let maxd = 0, mism = [];
for (const f of FRAMES) {
  const P = PYSAMPLES.samples[f], J = jsStates[f];
  for (const a in P) for (const part in P[a]) for (const prop in P[a][part]) {
    const pv = P[a][part][prop], jv = J[a][part][prop];
    if (typeof pv === "number") { const d = Math.abs(pv - jv); if (d > maxd) maxd = d; if (d > 1e-6) mism.push(`${f}:${part}.${prop} ${pv}/${jv}`); }
    else if (pv !== jv) mism.push(`${f}:${part}.${prop} ${pv}/${jv}`);
  }
}
check(mism.length === 0, `runtime state == Python sampler on ${FRAMES.length} frames x every channel (max difference ${maxd.toExponential(2)})${mism.length ? " " + mism.slice(0, 5) : ""}`);

// ------------------------------------------------------------------------------------------ E7
const applied = await A.p.evaluate((frames) => {
  const bad = []; let multi = 0;
  frames.forEach((f) => {
    const t = f / RT.fps, st = RT.state(t); RT.seek(t);
    Object.keys(st).forEach((aid) => {
      const b = RT.actors[aid];
      Object.keys(st[aid]).forEach((part) => Object.keys(st[aid][part]).forEach((prop) => {
        const v = st[aid][part][prop];
        if (prop === "shape") { const vis = Object.keys(b.mouths).filter((m) => b.mouths[m].style.display !== "none"); if (vis.length !== 1) multi++; if (vis[0] !== v) bad.push(f + " mouth " + vis + "/" + v); return; }
        const el = b.el(part);
        if (prop === "visible") { if ((el.style.visibility === "visible") !== !!v) bad.push(f + " visible"); return; }
        if (prop === "display") { if ((el.style.display === "inline") !== !!v) bad.push(f + " " + part + " display"); return; }
        const inline = prop === "opacity" ? el.style.opacity : el.style.getPropertyValue(prop);
        const got = prop === "opacity" ? parseFloat(getComputedStyle(el).opacity) : parseFloat(getComputedStyle(el).getPropertyValue(prop));
        // inline value: exact; computed value: Chromium serialises registered numbers to 6 significant digits
        if ((prop === "opacity" ? Math.abs(parseFloat(inline) - v) > 1e-6 : inline !== String(v)) || Math.abs(got - v) > 1e-5 * Math.max(1, Math.abs(v)) + 1e-6) bad.push(f + " " + part + "." + prop + " " + inline + "/" + got + "/" + v);
      }));
    });
  });
  return { bad, multi };
}, FRAMES);
check(applied.bad.length === 0 && applied.multi === 0, `seek() applies every value to the DOM (computed styles checked) and shows exactly one mouth${applied.bad.length ? " " + applied.bad.slice(0, 5) : ""}`);

// ------------------------------------------------------------------------------------------ E8
const snap = (p, t) => p.evaluate((t) => { RT.seek(t); return document.getElementById("s").innerHTML.replace(/(clip|cr)_\d+/g, "$1_N"); }, t);
const s1 = await snap(A.p, 9.0);
await A.p.evaluate(() => { RT.seek(15); RT.seek(2); RT.seek(11.3); });
const s2 = await snap(A.p, 9.0);
const B = await page(1920, 1080);
await B.p.evaluate((kl) => { window.RT = NFPCharacterRuntime.create({ svg: document.getElementById("s"), keylist: kl }); }, GOLDEN);
const s3 = await snap(B.p, 9.0);
check(s1 === s2 && s2 === s3, "seek is stateless: identical picture at 9.0 s after any seek order and in a fresh page");

// ------------------------------------------------------------------------------------------ E9
const mouthKeys = GOLDEN.keys.filter((k) => k.part === "mouth");
const lip = await A.p.evaluate((ks) => ks.map((k) => { RT.seek(k.t); const b = RT.actors[k.actor];
  return Object.keys(b.mouths).filter((m) => b.mouths[m].style.display !== "none").join() === k.val; }), mouthKeys);
const talk = GOLDEN.lipsync.talks[0];
check(lip.every(Boolean) && mouthKeys.length > 15, `lip sync in the DOM: all ${mouthKeys.length} mouth changes show the planned shape on their frame (${talk.words} words, max open offset ${talk.max_open_offset_frames} frame)`);

// ------------------------------------------------------------------------------------------ E10
const pl = await A.p.evaluate(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  let ended = null;
  RT.play({ from: 2, to: 6 }); await wait(450);
  const t1 = RT.time(), playing1 = RT.playing();
  RT.pause(); const tp = RT.time(); await wait(400); const t2 = RT.time(), playing2 = RT.playing();
  RT.resume(); await wait(400); const t3 = RT.time();
  RT.stop(); const t4 = RT.time();
  RT.play({ from: 1, to: 1.3, onEnd: (t) => { ended = t; } }); await wait(700);
  return { t1, playing1, tp, t2, playing2, t3, t4, ended, playing3: RT.playing() };
});
check(pl.playing1 && pl.t1 > 2.2 && pl.t1 < 2.9 && !pl.playing2 && pl.t2 === pl.tp && pl.t3 > pl.t2 + 0.2 && pl.t4 === 2 && pl.ended === 1.3 && !pl.playing3,
  `play/pause/resume/stop: ${pl.t1.toFixed(2)} s after 0.45 s, frozen at ${pl.t2.toFixed(2)} while paused, ${pl.t3.toFixed(2)} after resume, stop -> ${pl.t4}, end callback at ${pl.ended}`);

// ------------------------------------------------------------------------------------------ E11
const bad = await A.p.evaluate((kl) => {
  const variants = {
    overlap: (k) => { const i = k.keys.findIndex((x) => x.part === "legL" && x.df > 3);
      k.keys.push(Object.assign({}, k.keys[i], { f: k.keys[i].f + 1, t: Math.round((k.keys[i].f + 1) / 30 * 1e6) / 1e6 }));
      const key = (x) => [x.f, x.actor, x.part, x.prop];
      k.keys.sort((a, b) => { const p = key(a), q = key(b); for (let j = 0; j < 4; j++) { if (p[j] < q[j]) return -1; if (p[j] > q[j]) return 1; } return 0; }); },
    continuity: (k) => { k.keys.find((x) => x.part === "legL" && x.f > 20).from = 77; },
    unknown_part: (k) => { k.keys.find((x) => x.part === "head").part = "tail"; },
    unsorted: (k) => { k.keys.reverse(); },
    missing_field: (k) => { delete k.actors[0].spec.lip; },
  };
  const out = {};
  for (const name in variants) {
    const k = JSON.parse(JSON.stringify(kl)); variants[name](k); k.digest = NFPCharacterRuntime.digestOf(k);   // isolate the reason
    const before = document.querySelectorAll("[data-nfp-actor]").length;
    try { NFPCharacterRuntime.create({ svg: document.getElementById("s2"), keylist: k }); out[name] = "accepted"; }
    catch (e) { out[name] = String(e); }
    out[name + "_added"] = document.querySelectorAll("[data-nfp-actor]").length - before;
  }
  return out;
}, GOLDEN);
const why = { overlap: "overlaps the previous key", continuity: "!= previous value", unknown_part: "not allowed on part 'tail'",
  unsorted: "keys not sorted", missing_field: "misses lip" };
const refused = Object.keys(why).filter((n) => bad[n].includes(why[n]) && bad[n + "_added"] === 0);
check(refused.length === 5, `invalid KeyLists refused for the right reason, before anything is drawn: ${refused.join(", ")}` +
  (refused.length < 5 ? " | " + Object.keys(why).filter((n) => !refused.includes(n)).map((n) => n + ": " + bad[n].slice(0, 120)).join(" | ") : ""));

// ------------------------------------------------------------------------------------------ E12
if (!GSAP || !fs.existsSync(GSAP)) {
  check(true, "GSAP timeline equivalence: no local GSAP (pass --gsap <local gsap.min.js>); nothing downloaded", "NOT RUN");
} else {
  const G = await page(1920, 1080, { gsap: GSAP });
  const eq = await G.p.evaluate(({ kl, frames }) => {
    const ref = NFPCharacterRuntime.create({ svg: document.getElementById("s"), keylist: kl });
    const k2 = JSON.parse(JSON.stringify(kl).split(kl.actors[0].dom_id).join(kl.actors[0].dom_id + "-g"));
    k2.digest = NFPCharacterRuntime.digestOf(k2);           // a second copy in the same page needs its own DOM id
    const rt2 = NFPCharacterRuntime.create({ svg: document.getElementById("s2"), keylist: k2 });
    const tl = rt2.toTimeline(gsap);
    let maxd = 0; const bad = [];
    frames.forEach((f) => {
      const t = f / ref.fps, st = ref.state(t); tl.seek(t, false);
      Object.keys(st).forEach((aid) => { const bb = rt2.actors[aid];
        Object.keys(st[aid]).forEach((part) => Object.keys(st[aid][part]).forEach((prop) => {
          const v = st[aid][part][prop];
          if (prop === "shape") { const vis = Object.keys(bb.mouths).filter((m) => getComputedStyle(bb.mouths[m]).display !== "none"); if (vis.join() !== v) bad.push(f + " mouth " + vis + "/" + v); return; }
          const el = bb.el(part);
          if (prop === "visible") { if ((getComputedStyle(el).visibility === "visible") !== !!v) bad.push(f + " visible"); return; }
          if (prop === "display") { if ((getComputedStyle(el).display !== "none") !== !!v) bad.push(f + " " + part + " display"); return; }
          const got = prop === "opacity" ? parseFloat(getComputedStyle(el).opacity) : parseFloat(getComputedStyle(el).getPropertyValue(prop));
          const d = Math.abs(got - v), rel = d / Math.max(1, Math.abs(v)); if (rel > maxd) maxd = rel;
          if (rel > 1e-4) bad.push(f + " " + part + "." + prop + " " + got + "/" + v);
        }));
      });
    });
    return { maxd, bad, ver: gsap.version, dur: tl.duration() };
  }, { kl: GOLDEN, frames: FRAMES });
  check(eq.bad.length === 0, `GSAP ${eq.ver} timeline (toTimeline) == built-in seek on ${FRAMES.length} frames (max relative difference ${eq.maxd.toExponential(2)}, timeline ${eq.dur} s)${eq.bad.length ? " " + eq.bad.slice(0, 5) : ""}`);
}

// ------------------------------------------------------------------------------------------ E13
async function inside(kl, w, h, frames) {
  const P = await page(w, h);
  return P.p.evaluate(({ kl, frames, w, h }) => {
    const rt = NFPCharacterRuntime.create({ svg: document.getElementById("s"), keylist: kl });
    const svg = document.getElementById("s").getBoundingClientRect(), out = [];
    frames.forEach((f) => {
      rt.seek(f / rt.fps);
      kl.actors.forEach((a) => { if (!rt.state(f / rt.fps)[a.id].self || rt.state(f / rt.fps)[a.id].self.visible === 0) return;
        const r = document.getElementById(a.dom_id).getBoundingClientRect();
        out.push({ f, x0: r.left - svg.left, y0: r.top - svg.top, x1: r.right - svg.left, y1: r.bottom - svg.top }); });
    });
    return out.filter((b) => b.x0 < -0.5 || b.y0 < -0.5 || b.x1 > w + 0.5 || b.y1 > h + 0.5).concat([{ n: out.length }]);
  }, { kl, frames, w, h });
}
const v916 = await inside(KL916, 1080, 1920, Array.from({ length: 26 }, (_, i) => 12 + i * 10));
const n916 = v916.pop().n;
const v169 = await inside(GOLDEN, 1920, 1080, Array.from({ length: 22 }, (_, i) => 90 + i * 16));
const n169 = v169.pop().n;
check(v916.length === 0 && n916 > 20 && v169.length === 0 && n169 > 20,
  `9:16 (1080x1920, scale 1.6) and 16:9 (1920x1080): the character stays inside the frame while on stage (${n916} + ${n169} frames checked)`);

// ------------------------------------------------------------------------------------------ E14 input security
const PYHASH = JSON.parse(py(`
import hashlib
from character.animation.keys import spec_fingerprint
strs = ["", "abc", "سلام دنیا", "x" * 1000, "\u200c\u0645\u06cc"]
kl = json.load(open(${JSON.stringify(path.join(PKG, "examples", "demo-anim", "keylist.json"))}, encoding="utf-8"))
print(json.dumps({"sha": [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in strs], "strs": strs,
                  "fp": spec_fingerprint(kl["actors"][0]["spec"]), "fpk": spec_fingerprint(${JSON.stringify(KL916.actors[0].spec)})}))`));
const S = await page(1920, 1080);
const sec = await S.p.evaluate(async ({ kl, pyh, lock }) => {
  const R = NFPCharacterRuntime, out = {}, svg = document.getElementById("s");
  const clone = () => JSON.parse(JSON.stringify(kl));
  const attempt = (k, opts) => { svg.innerHTML = ""; const before = document.querySelectorAll("[data-nfp-actor]").length;
    try { const rt = R.create(Object.assign({ svg, keylist: k }, opts || {})); const html = svg.innerHTML.toLowerCase(); rt.dispose(); return { ok: true, html }; }
    catch (e) { return { ok: false, err: String(e), added: document.querySelectorAll("[data-nfp-actor]").length - before }; } };
  const refused = (fn, needle, opts) => { const k = clone(); fn(k); k.digest = R.digestOf(k); const r = attempt(k, opts); return !r.ok && r.added === 0 && r.err.includes(needle) ? "ok" : (r.ok ? "ACCEPTED" : r.err.slice(0, 160)); };
  out.parity = { sha: pyh.strs.every((s, i) => R.sha256(s) === pyh.sha[i]), digest: R.digestOf(kl) === kl.digest,
    fp: R.fingerprintOf(kl.actors[0].spec) === pyh.fp && pyh.fp === lock.characters.zahra && kl.actors[0].fingerprint === lock.characters.zahra };
  out.spec = {
    empty_eye: refused((k) => { k.actors[0].spec.eyeColor = ""; }, "eyeColor: must be a lower-case #rrggbb"),
    null_skin: refused((k) => { k.actors[0].spec.skin = null; }, "skin: must be"),
    short_hex: refused((k) => { k.actors[0].spec.lip = "#abc"; }, "lip: must be"),
    upper_hex: refused((k) => { k.actors[0].spec.accent = "#ABCDEF"; }, "accent: must be"),
    named: refused((k) => { k.actors[0].spec.top = "red"; }, "top: must be"),
    flag: refused((k) => { k.actors[0].spec.glasses = "1"; }, "glasses: must be 0 or 1"),
    vocab: refused((k) => { k.actors[0].spec.outfit = "cape"; }, "outfit"),
    missing: refused((k) => { delete k.actors[0].spec.under; }, "misses under"),
  };
  out.markup = {
    top_handler: refused((k) => { k.actors[0].spec.top = '#111111" onmouseover="alert(1)'; }, "top: must be"),
    scale_markup: refused((k) => { k.actors[0].scale = '1)"/><foreignObject/><g transform="scale(1'; }, "scale must be"),
    x_string: refused((k) => { k.actors[0].x = "100"; }, "x must be"),
    y_nan: refused((k) => { k.actors[0].y = null; }, "y must be"),
    scale_zero: refused((k) => { k.actors[0].scale = 0; }, "scale must be"),
    scale_huge: refused((k) => { k.actors[0].scale = 1e6; }, "scale must be"),
    actor_id: refused((k) => { const o = k.actors[0].id; k.actors[0].id = "<img src=x onerror=alert(1)>"; k.keys.forEach((x) => { if (x.actor === o) x.actor = k.actors[0].id; }); }, "id must match"),
    proto_id: refused((k) => { const o = k.actors[0].id; k.actors[0].id = "__proto__"; k.keys.forEach((x) => { if (x.actor === o) x.actor = "__proto__"; }); }, "id must match"),
    dom_id: refused((k) => { k.actors[0].dom_id = 'x" onclick="alert(1)'; }, "dom_id must match"),
    val_string: refused((k) => { const x = k.keys.find((q) => q.part === "head" && q.prop === "--r"); x.val = "1;background:url(http://x)"; }, "val must be a finite number"),
    ease_proto: refused((k) => { k.keys.find((q) => q.df > 0).ease = "constructor"; }, "unknown ease"),
  };
  const UNSAFE = "[onmouseover],[onclick],[onerror],[onload],foreignObject,script,img";   // inside the drawing areas only
  out.handlers_in_dom = document.querySelectorAll("#s " + UNSAFE.split(",").join(", #s ") + ", #s2 " + UNSAFE.split(",").join(", #s2 ")).length;
  // the rig itself is trusted code, but its output is still checked: a rig that emitted unsafe SVG would be stopped
  const fakeK = (markup) => ({ chars: { actor: () => markup } });
  out.sanitizer = {
    onload: refused(() => {}, "attribute 'onload' is not allowed", { K: fakeK('<g onload="alert(1)"></g>') }),
    foreign: refused(() => {}, "element <foreignObject> is not allowed", { K: fakeK('<foreignObject><div>x</div></foreignObject>') }),
    script: refused(() => {}, "is not allowed", { K: fakeK('<script>alert(1)</script>') }),
    image: refused(() => {}, "element <image> is not allowed", { K: fakeK('<image href="http://example.com/x.png"/>') }),
    ext_url: refused(() => {}, "only url(#local)", { K: fakeK('<g fill="url(http://example.com/a.svg#p)"></g>') }),
    style: refused(() => {}, "style", { K: fakeK('<g style="background:red"></g>') }),
    text: refused(() => {}, "unexpected text", { K: fakeK('<g>hello</g>') }),
  };
  out.identity = {
    forged_fp: refused((k) => { k.actors[0].fingerprint = "f".repeat(64); }, "fingerprint does not belong"),
    swapped_skin: refused((k) => { k.actors[0].spec.skin = "#d99a73"; }, "fingerprint does not belong"),
    no_digest: (() => { const k = clone(); delete k.digest; const r = attempt(k); return !r.ok && r.err.includes("digest missing") ? "ok" : "ACCEPTED"; })(),
    stale_digest: (() => { const k = clone(); k.actors[0].x += 1; const r = attempt(k); return !r.ok && r.err.includes("digest does not match") ? "ok" : "ACCEPTED"; })(),
    fps24: refused((k) => { k.fps = 24; }, "fps must be 30"),
    fps60: refused((k) => { k.fps = 60; }, "fps must be 30"),
  };
  // documented limit: a consistent re-signed identity (new colours + recomputed fingerprint + digest) is accepted,
  // because the runtime cannot see cast.lock.json - the Python adapter is the lock gate
  const k = clone(); k.actors[0].spec.skin = "#7a5030"; k.actors[0].fingerprint = R.fingerprintOf(k.actors[0].spec); k.digest = R.digestOf(k);
  out.limit_resigned_accepted = attempt(k).ok;
  // duplicate placement, playback arguments
  svg.innerHTML = "";
  const a = R.create({ svg, keylist: kl });
  let dup; try { R.create({ svg: document.getElementById("s2"), keylist: kl }); dup = "ACCEPTED"; } catch (e) { dup = String(e).includes("already exists") ? "ok" : String(e); }
  out.duplicate = dup; out.duplicate_count = document.querySelectorAll("#" + kl.actors[0].dom_id).length;
  out.play = ["-1", "0", "NaN", "100", "from>to"].map((c) => { try {
    if (c === "from>to") a.play({ from: 5, to: 3 }); else a.play({ rate: c === "NaN" ? NaN : Number(c) }); a.stop(); return c + ":ACCEPTED"; }
    catch (e) { return "ok"; } });
  a.dispose();
  out.after_dispose = document.querySelectorAll("[data-nfp-actor]").length;
  return out;
}, { kl: GOLDEN, pyh: PYHASH, lock: LOCK });
const allOk = (o) => Object.values(o).every((v) => v === "ok");
check(sec.parity.sha && sec.parity.digest && sec.parity.fp, "runtime SHA-256 = Python hashlib (5 strings incl. Persian), digest = planner digest, recomputed fingerprint = cast.lock.json");
check(allOk(sec.spec), `malformed rig specs refused before drawing (empty / null / short / upper-case / named colour, non 0/1 flag, unknown outfit, missing field)${allOk(sec.spec) ? "" : " " + JSON.stringify(sec.spec)}`);
check(allOk(sec.markup) && sec.handlers_in_dom === 0, `markup injection refused: colour with event handler, scale with markup, string/null/0/huge x,y,scale, unsafe ids, CSS string as value, prototype names (unsafe nodes left in the page: ${sec.handlers_in_dom})${allOk(sec.markup) ? "" : " " + JSON.stringify(sec.markup)}`);
check(allOk(sec.sanitizer), `rig output sanitiser stops event handlers, foreignObject, script, image, external url(), styles and text${allOk(sec.sanitizer) ? "" : " " + JSON.stringify(sec.sanitizer)}`);
check(allOk(sec.identity), `forged fingerprint, swapped identity colour, missing or stale digest and fps 24/60 are refused${allOk(sec.identity) ? "" : " " + JSON.stringify(sec.identity)}`);
check(sec.limit_resigned_accepted === true, "documented limit confirmed: a fully re-signed KeyList (new colours + recomputed fingerprint + digest) is accepted - the lock is enforced by the Python adapter, not the runtime", "INFO");
check(sec.duplicate === "ok" && sec.duplicate_count === 1 && sec.play.every((x) => x === "ok") && sec.after_dispose === 0,
  `same character placed twice is refused, invalid playback arguments refused (${sec.play.join(",")}), dispose leaves nothing`);

// ------------------------------------------------------------------------------------------ F demo page
const D = await page(1140, 760, { file: "file://" + DEMO_HTML });
await D.p.waitForFunction(() => !!window.NFP_RT);
const sc = await D.p.evaluate(() => {
  const rt = NFP_RT, S = (t) => rt.state(t).zahra, v = (t, part, prop) => (S(t)[part] || {})[prop];
  const range = (a, b, part, prop) => { const xs = []; for (let t = a; t <= b; t += 1 / 30) xs.push(v(t, part, prop)); return [Math.min(...xs), Math.max(...xs)]; };
  const mouths = new Set(); for (let t = 8.2; t <= 12.9; t += 1 / 30) mouths.add(v(t, "mouth", "shape"));
  return {
    controls: ["play", "pause", "resume", "stop", "seek"].every((id) => !!document.getElementById(id)),
    hiddenStart: v(0.2, "self", "visible") === 0, enters: v(0.6, "self", "visible") === 1 && v(0.6, "self", "--x") < -800 && Math.abs(v(3.2, "self", "--x")) < 1e-9,
    stands: ["legL", "legR", "torso"].every((p) => v(3.4, p, "--r") === 0),
    blinks: range(3, 15, "lidL", "--y")[1] > 30, breathes: range(3, 6, "torso", "--sy")[1] > 1.015,
    lookL: v(3.95, "irisL", "--x") < 0, lookR: v(4.65, "irisL", "--x") > 0,
    walks: range(6.0, 7.2, "legL", "--r")[1] > 15 && v(7.6, "self", "--x") > v(5.7, "self", "--x"),
    stopped: ["legL", "legR", "shinL", "torso"].every((p) => v(7.95, p, "--r") === 0),
    talk: mouths.size >= 4, closedAfter: ["neutral"].includes(v(12.95, "mouth", "shape")),
    exprBefore: v(13.0, "mouth", "shape"), exprAfter: v(13.6, "mouth", "shape"), brows: v(13.6, "browL", "--y"),
    exits: v(17.5, "self", "visible") === 0 && v(17.3, "self", "--x") > 900,
  };
});
check(D.errors.length === 0 && sc.controls, `demo page loads from file:// with play/pause/resume/stop/seek controls (${D.errors.join(" | ") || "no errors"})`);
check(sc.hiddenStart && sc.enters, "scenario 1: hidden at first, then walks in from off-stage to its mark");
check(sc.stands && sc.blinks && sc.breathes, "scenario 2-3: stands still; blinks and breathes (idle)");
check(sc.lookL && sc.lookR, "scenario 4: looks left, then right");
check(sc.walks && sc.stopped, "scenario 5-6: walks forward, then stops with legs at rest");
check(sc.talk && sc.closedAfter, `scenario 7-8: Persian sentence drives the mouth (${sc.talk ? ">= 4" : "< 4"} shapes during speech), closed after it`);
check(sc.exprBefore === "neutral" && sc.exprAfter === "grin" && sc.brows === -8, `scenario 9: expression changes (mouth ${sc.exprBefore} -> ${sc.exprAfter}, brows up)`);
check(sc.exits, "scenario 10: walks out and is hidden at the end");
if (SHOTS) {
  fs.mkdirSync(SHOTS, { recursive: true });
  for (const t of [0.2, 1.7, 3.95, 4.65, 6.6, 8.75, 10.2, 13.6, 16.4]) {
    await D.p.evaluate((t) => NFP_RT.seek(t), t);
    await D.p.locator("#stage").screenshot({ path: path.join(SHOTS, `demo_${t.toFixed(2)}.png`) });
  }
  const P9 = await page(1080, 1920);
  await P9.p.evaluate((kl) => { window.RT = NFPCharacterRuntime.create({ svg: document.getElementById("s"), keylist: kl }); RT.seek(6.9); }, KL916);
  await P9.p.locator("#s").screenshot({ path: path.join(SHOTS, "portrait_9x16.png") });
}

// ------------------------------------------------------------------------------------------ E1 (network)
check(NET.length === 0, `no network request from any page (${NET.length} blocked${NET.length ? ": " + NET.slice(0, 3) : ""})`);
await browser.close();
fs.rmSync(TMP, { recursive: true, force: true });
const fails = results.filter((r) => r.status === "FAIL").length, notRun = results.filter((r) => r.status === "NOT RUN").length;
const info = results.filter((r) => r.status === "INFO").length;
console.log(`\n${results.length} checks: ${results.length - fails - notRun - info} passed, ${fails} failed, ${notRun} not run, ${info} info.`);
if (OUT) fs.writeFileSync(OUT, JSON.stringify({ results, fails, notRun }, null, 1));
process.exit(fails ? 1 : 0);
