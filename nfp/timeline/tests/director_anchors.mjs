#!/usr/bin/env node
/*
 * T1 parity: resolve anchors with the REAL Film Director (nfp/film/kit/50_director.js, loaded unchanged) in Node.
 *   node director_anchors.mjs <config.json>   config: { director: <path>, cases: [{name, data: DATA, anchors: [...]}], out }
 * Every anchor goes through D.shot({a: anchor, b: anchor}) - the Director's own TT() - and its S.t0 is recorded
 * (seconds, already snapped to 1/30 s) or the error it throws. A tiny DOM stub stands in for the page (no browser).
 */
import fs from "node:fs";
import vm from "node:vm";
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const el = () => ({ setAttribute() {}, style: { setProperty() {} }, appendChild() {}, querySelector() { return null; } });
globalThis.window = { K: {} };
globalThis.document = { createElementNS: () => el(), getElementById: () => el() };
vm.runInThisContext(fs.readFileSync(cfg.director, "utf8"), { filename: "50_director.js" });
const K = window.K;
const out = {};
for (const c of cfg.cases) {
  const tl = { set() {}, fromTo() {} };
  const D = K.Director(c.data, tl, el());
  out[c.name] = c.anchors.map((a, n) => {
    try { const S = D.shot({ id: "p" + n, a, b: a }); return { t: S.t0, f: Math.round(S.t0 * 30) }; }
    catch (e) { return { error: String(e.message || e) }; }
  });
}
fs.writeFileSync(cfg.out, JSON.stringify(out));
