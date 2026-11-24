#!/usr/bin/env node
/*
 * F4 browser part: a composed Film page with C3 characters (local Chromium, network blocked and counted).
 *   node film_cast_page.mjs <config.json>
 * config: { page, expect: {instances: [...], words: [...], silent: [...]}, safe: {tags, attrs}, bad_pages: {name: dir} }
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const NET = [], res = {};
const browser = await chromium.launch();
async function open(dir) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage(); const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:")) return r.continue(); NET.push(u); r.abort(); });
  await page.goto("file://" + path.join(dir, "index.html"));
  await page.waitForFunction(() => document.readyState === "complete", null, { timeout: 20000 });
  await page.evaluate(() => document.fonts.ready.then(() => true));
  return { page, errors };
}
const P = await open(cfg.page);
res.errors = P.errors;
res.cast = await P.page.evaluate(() => window.__nfpFilmCast || null);
res.dom_ids = await P.page.evaluate(() => [...document.querySelectorAll("[data-nfp-actor]")].map((e) => e.id));

// per-frame state of every instance = the planned KeyList (C3 sampler), shot window, parallax position
res.state = await P.page.evaluate((E) => {
  const tl = window.__timelines.main, bad = [], par = [];
  let n = 0;
  E.instances.forEach((I) => {
    I.frames.forEach((f, k) => {
      tl.seek(f / 30, false); n++;
      const outer = document.getElementById(I.dom_id), self = outer.querySelector('[data-p="self"]');
      const shown = getComputedStyle(outer).visibility === "visible" && getComputedStyle(self).visibility === "visible";
      const mouth = [...outer.querySelectorAll("[data-m]")].filter((m) => getComputedStyle(m).display !== "none").map((m) => m.getAttribute("data-m")).join("");
      const sx = +(parseFloat(getComputedStyle(self).getPropertyValue("--x")) || 0).toFixed(3);
      if (shown !== I.shown[k]) bad.push(`${I.key}@${f} shown ${shown}/${I.shown[k]}`);
      if (I.shown[k] && mouth !== I.mouth[k]) bad.push(`${I.key}@${f} mouth ${mouth}/${I.mouth[k]}`);
      if (I.shown[k] && Math.abs(sx - I.selfx[k]) > 0.01) bad.push(`${I.key}@${f} --x ${sx}/${I.selfx[k]}`);
      if (I.shown[k]) {
        const g = document.getElementById("shot-" + I.shot), cs = getComputedStyle(g);
        const cam = ["--cx", "--cy", "--cz"].map((p) => parseFloat(cs.getPropertyValue(p)) || 0), d = I.depth, s = 1 + cam[2] * d;
        const m = outer.getScreenCTM(), got = [m.e, m.f], want = [960 - cam[0] * d + s * (I.x - 960), 540 - cam[1] * d + s * (I.y - 540)];
        par.push(Math.max(Math.abs(got[0] - want[0]), Math.abs(got[1] - want[1])));
      }
    });
  });
  return { bad, n, parallax_max_err: par.length ? Math.max(...par) : null, parallax_samples: par.length };
}, cfg.expect);

// layer order: every character layer has later layers (grade / light) of its shot above it
res.order = await P.page.evaluate(() => [...document.querySelectorAll("[data-nfp-film-cast]")].map((l) => {
  const sib = [...l.parentNode.children]; return { key: l.getAttribute("data-nfp-film-cast"), index: sib.indexOf(l), layers: sib.length, depth: l.style.getPropertyValue("--d") };
}));

// lip sync on the page: the speaker's mouth is open on each spoken word; silent instances keep one mouth shape
res.lip = await P.page.evaluate((E) => {
  const tl = window.__timelines.main, bad = [], silent = {};
  const mouth = (id) => [...document.getElementById(id).querySelectorAll("[data-m]")].filter((m) => getComputedStyle(m).display !== "none").map((m) => m.getAttribute("data-m")).join("");
  E.words.forEach((w) => { tl.seek(w.f / 30, false); const m = mouth(w.dom_id); if (!["open", "small", "o", "grin", "shock", "wide"].includes(m)) bad.push(`${w.key} '${w.text}' @${w.f}: ${m}`); });
  E.silent.forEach((s) => { const set = new Set(); s.frames.forEach((f) => { tl.seek(f / 30, false); set.add(mouth(s.dom_id)); }); silent[s.key + " during " + s.during] = [...set]; });
  return { bad, words: E.words.length, silent };
}, cfg.expect);

// C3 sanitizer vs the whole rig vocabulary: every rig output must pass the runtime's allow-list (no capability lost)
res.sweep = await P.page.evaluate((SAFE) => {
  const C = window.K.chars, B = Object.keys(C.BUILDS), out = { combos: 0, rejected: [], builds: B.length, build_names: B };
  const HAIR = ["none", "baby_tuft", "child_pony", "teen_long", "long_straight", "big80s", "short_man", "slick"];
  const OUT = ["kidtee", "sweat80s", "babygrow", "tee2007", "crop", "dress", "suit", "blazer", "track", "onesie"];
  const tpl = document.createElement("template");
  const check = (markup) => {
    tpl.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg">' + markup + "</svg>";
    const bad = [];
    tpl.content.firstElementChild.querySelectorAll("*").forEach((el) => {
      if (!SAFE.tags.includes(el.localName)) bad.push("<" + el.localName + ">");
      for (const a of el.attributes) {
        if (!SAFE.attrs.includes(a.name)) bad.push("@" + a.name);
        if (/url\(/i.test(a.value) && !/^url\(#[A-Za-z0-9_-]+\)$/.test(a.value)) bad.push("url " + a.value);
        if (a.name === "style" && !/^display:\s*(inline|none);?$/.test(a.value)) bad.push("style " + a.value);
      }
    });
    return [...new Set(bad)];
  };
  B.forEach((b) => HAIR.forEach((h) => OUT.forEach((o) => [0, 1].forEach((flag) => {
    const spec = { build: b, hair: h, outfit: o, skin: "#aa8866", hairColor: "#222222", eyeColor: "#334455", top: "#123456", pants: "#654321",
      shoe: "#111111", accent: "#ff0000", lip: "#aa4444", under: "#eeeeee", detail: flag, earrings: flag, glasses: flag,
      legs: flag ? "bare" : "pants", sleeve: ["none", "short", "long"][(b.length + h.length) % 3], shoeType: ["sneaker", "pump", "flat"][o.length % 3] };
    out.combos++;
    const bad = check(C.actor(spec)); if (bad.length) out.rejected.push(`${b}/${h}/${o}/${flag}: ${bad.join(" ")}`);
  }))));
  return out;
}, cfg.safe);

// broken pages must stop with a clear error
res.bad_pages = {};
for (const [name, dir] of Object.entries(cfg.bad_pages || {})) { const B = await open(dir); res.bad_pages[name] = B.errors.map((e) => e.slice(0, 160)); }
res.network_requests = NET.length;
fs.writeFileSync(cfg.out, JSON.stringify(res, null, 1));
await browser.close();
