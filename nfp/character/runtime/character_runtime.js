/* NFP Character Engine - C3d: JavaScript animation runtime for KeyLists (schema nfp.anim.keylist/1).

   Load order (all local, nothing from the network):
     renderers/flat_cartoon_v2/rig.css, rig/00_core.js, rig/10_chars.js, runtime/character_runtime.js

   const rt = NFPCharacterRuntime.create({ svg, keylist });   // validates the KeyList, builds the characters
   rt.seek(t)              apply the exact state at time t (seconds). Stateless: same t -> same picture, any order.
   rt.state(t)             the same values as data, without touching the DOM: {actor: {part: {prop: value}}}
   rt.play({from, to, rate, onFrame, onEnd})   real-time playback (requestAnimationFrame), clamped to [from, to]
   rt.pause() / rt.resume() / rt.stop()        stop() returns to `from`; time() and playing() report the state
   rt.toTimeline(gsap, tl) optional: the same animation as tweens on a GSAP timeline (a local GSAP must be passed in;
                           this file never loads one). Equivalent to seek() - checked by tests/anim_render_check.mjs.
   rt.dispose()            remove the characters again
   NFPCharacterRuntime.validate(keylist) -> [problems]   (the same rules as animation/keys.py validate_keylist)

   Input safety (a KeyList is treated as untrusted data):
   * every rig spec field is checked by type and value (#rrggbb colours, 0/1 flags, rig vocabulary): an empty, null
     or malformed value is refused, so the rig never reaches its fallback colours (some are the Kim character's);
   * x, y, scale, ids are checked; the wrapper elements are made with createElementNS/setAttribute (no markup);
   * the rig's SVG is parsed in an inert <template>, checked against an allow-list of elements and attributes (no
     event handlers, no foreignObject/script, only url(#local) references), and only then moved into the page;
   * the fingerprint must equal the identity of the spec (recomputed with SHA-256 exactly like C1 fingerprint());
   * the digest must equal the content (canonical JSON, the same bytes as animation/keys.py canonical()).
   Limits: the fingerprint check proves the fingerprint matches the spec's colours/glasses, NOT that the identity is
   in some cast.lock.json (the runtime has no access to casts; the Python adapter checks the lock). A digest is not a
   signature: whoever edits a KeyList can recompute it. Recomputing the fingerprint from the spec is exact only while
   the style catalogue has face "default" and no mark other than glasses (true for flat_cartoon_v2 today).
   Independent of the docu Director, base.html, Studio and HyperFrames: it only needs window.K (the C2 rig). */
(function (g) {
  "use strict";
  const SCHEMA = "nfp.anim.keylist/1", STYLE = "flat_cartoon_v2", FPS = 30, POS_LIMIT = 100000, SCALE_MAX = 20;
  const RIG_SPEC_FIELDS = ["accent", "build", "detail", "earrings", "eyeColor", "glasses", "hair", "hairColor", "legs", "lip",
    "outfit", "pants", "shoe", "shoeType", "skin", "sleeve", "top", "under"];
  const COLOR_FIELDS = ["accent", "eyeColor", "hairColor", "lip", "pants", "shoe", "skin", "top", "under"];
  const FLAG_FIELDS = ["detail", "earrings", "glasses"];
  const VOCAB = {   // = animation/profile_flat_cartoon_v2.json (checked by tests/anim_render_check.mjs)
    build: ["baby", "child", "teen", "woman", "man"],
    hair: ["none", "baby_tuft", "child_pony", "teen_long", "long_straight", "big80s", "short_man", "slick"],
    outfit: ["kidtee", "sweat80s", "babygrow", "tee2007", "crop", "dress", "suit", "blazer", "track", "onesie"],
    shoeType: ["sneaker", "pump", "flat"], sleeve: ["none", "short", "long"], legs: ["pants", "bare"],
  };
  const LONG_HAIR = ["long_straight"];
  const RIG_PARTS = ["shadow", "root", "torso", "head", "armL", "armR", "foreL", "foreR", "legL", "legR", "shinL", "shinR",
    "shoeL", "shoeR", "eyeL", "eyeR", "irisL", "irisR", "lidL", "lidR", "browL", "browR", "blush", "hairBack"];
  const MOUTHS = ["neutral", "smile", "grin", "open", "small", "o", "shock", "sad", "frown", "smirk", "worried", "proud"];
  const LIMB_PROPS = ["--x", "--y", "--r", "--s", "--sx", "--sy"];
  const PART_PROPS = { self: ["--x", "--y", "--s", "opacity", "visible"], mouth: ["shape"], tears: ["display"],
    sweat: ["display"], blush: ["opacity"] };
  const DISCRETE = { shape: 1, display: 1, visible: 1 };
  const REST = { "--x": 0, "--y": 0, "--r": 0, "--s": 1, "--sx": 1, "--sy": 1, opacity: 1, visible: 1, display: 0, shape: "neutral" };
  const REST_OVERRIDE = { "blush.opacity": 0.25 };
  const KEY_FIELDS = ["actor", "df", "dur", "ease", "f", "from", "part", "prop", "src", "t", "val"].sort();
  const HEX = /^#[0-9a-f]{6}$/, ACTOR_ID = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/, DOM_ID = /^nfp-c-[a-z0-9-]{1,200}$/, FP = /^[0-9a-f]{64}$/;
  // what the rig is allowed to produce (anything else in its output is refused before it reaches the page)
  const SAFE_TAGS = ["g", "path", "ellipse", "circle", "rect", "clipPath"];
  const SAFE_ATTRS = ["clip-path", "cx", "cy", "d", "data-actor", "data-m", "data-p", "data-x", "fill", "height", "id", "opacity",
    "r", "rx", "ry", "stroke", "stroke-linecap", "stroke-linejoin", "stroke-width", "style", "transform", "width", "x", "y"];
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const backOut = (s) => (p) => (p - 1) * (p - 1) * ((s + 1) * (p - 1) + s) + 1;
  const backIn = (s) => (p) => p * p * ((s + 1) * p - s);
  const EASES = {
    "none": (p) => p,
    "sine.in": (p) => 1 - Math.cos(p * Math.PI / 2),
    "sine.out": (p) => Math.sin(p * Math.PI / 2),
    "sine.inOut": (p) => -(Math.cos(Math.PI * p) - 1) / 2,
    "power1.in": (p) => p * p,
    "power1.out": (p) => 1 - (1 - p) * (1 - p),
    "power1.inOut": (p) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2),
    "power2.in": (p) => p * p * p,
    "power2.out": (p) => 1 - Math.pow(1 - p, 3),
    "power2.inOut": (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    "back.out(1.6)": backOut(1.6),
    "back.in(1.6)": backIn(1.6),
  };
  const EPS = 1e-9;
  /** times in a KeyList are rounded to 6 decimals; a time within 1e-4 frame of a frame IS that frame */
  const toFrame = (t, fps) => { const fr = t * fps, r = Math.round(fr); return Math.abs(fr - r) < 1e-4 ? r : fr; };
  const ftime = (f, fps) => Math.round((f / fps) * 1e6) / 1e6;
  const finite = (v) => typeof v === "number" && Number.isFinite(v);
  const allowed = (part) => (typeof part !== "string" ? [] : own(PART_PROPS, part) ? PART_PROPS[part] : RIG_PARTS.indexOf(part) >= 0 ? LIMB_PROPS : []);
  const restOf = (part, prop) => (own(REST_OVERRIDE, part + "." + prop) ? REST_OVERRIDE[part + "." + prop] : REST[prop]);
  const conflict = (f1, d1, f2, d2) => (d1 === 0 && d2 === 0 ? f1 === f2 : d1 === 0 ? f2 <= f1 && f1 < f2 + d2 :
    d2 === 0 ? f1 <= f2 && f2 < f1 + d1 : f1 < f2 + d2 && f2 < f1 + d1);

  // ---------------------------------------------------------------------------------------- SHA-256 + canonical JSON
  const SK = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
    0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70,
    0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  const SH = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  function sha256(str) {
    const msg = new TextEncoder().encode(str), len = msg.length;
    const buf = new Uint8Array(((len + 9 + 63) >> 6) << 6);
    buf.set(msg); buf[len] = 0x80;
    const dv = new DataView(buf.buffer), bits = len * 8;
    dv.setUint32(buf.length - 8, Math.floor(bits / 4294967296)); dv.setUint32(buf.length - 4, bits >>> 0);
    const h = SH.slice(), w = new Uint32Array(64), rotr = (x, n) => (x >>> n) | (x << (32 - n));
    for (let o = 0; o < buf.length; o += 64) {
      for (let t = 0; t < 16; t++) w[t] = dv.getUint32(o + t * 4);
      for (let t = 16; t < 64; t++) {
        const s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3), s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10);
        w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
      }
      let [a, b, c, d, e, f, gg, hh] = h;
      for (let t = 0; t < 64; t++) {
        const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & gg)) + SK[t] + w[t]) >>> 0;
        const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
        hh = gg; gg = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      [a, b, c, d, e, f, gg, hh].forEach((v, i) => { h[i] = (h[i] + v) >>> 0; });
    }
    return h.map((v) => v.toString(16).padStart(8, "0")).join("");
  }
  /** canonical JSON: sorted keys, no spaces, integral numbers as integers - byte-identical to keys.py canonical() */
  function canon(v) {
    if (v === null || typeof v === "boolean" || typeof v === "string") return JSON.stringify(v);
    if (typeof v === "number") { if (!Number.isFinite(v)) throw new Error("canonical JSON: non-finite number"); return JSON.stringify(v); }
    if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
    if (typeof v === "object") return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}";
    throw new Error("canonical JSON: unsupported value");
  }
  function digestOf(kl) { const c = {}; Object.keys(kl).forEach((k) => { if (k !== "digest") c[k] = kl[k]; }); return sha256(canon(c)); }
  /** C1 identity fingerprint (registry.fingerprint) recomputed from a rig spec */
  function fingerprintOf(spec) {
    return sha256(canon({ identity: { eye_color: spec.eyeColor, face: { brows: "default", nose: "default", shape: "default" },
      hair_color: spec.hairColor, marks: spec.glasses === 1 ? ["glasses"] : [], skin: spec.skin, style: STYLE }, v: 1 }));
  }

  // ---------------------------------------------------------------------------------------- validation
  function validateSpec(s, w) {
    const P = [];
    if (!s || typeof s !== "object" || Array.isArray(s)) return [w + ": rig spec must be an object"];
    const miss = RIG_SPEC_FIELDS.filter((f) => !own(s, f)), extra = Object.keys(s).filter((f) => RIG_SPEC_FIELDS.indexOf(f) < 0);
    if (miss.length) P.push(w + ": rig spec misses " + miss.join(", ") + " (the rig would fall back to its defaults)");
    if (extra.length) P.push(w + ": unknown rig spec field(s) " + extra.join(", "));
    COLOR_FIELDS.forEach((f) => { if (own(s, f) && !(typeof s[f] === "string" && HEX.test(s[f]))) P.push(w + "." + f + ": must be a lower-case #rrggbb colour (got " + JSON.stringify(s[f]) + ")"); });
    FLAG_FIELDS.forEach((f) => { if (own(s, f) && s[f] !== 0 && s[f] !== 1) P.push(w + "." + f + ": must be 0 or 1"); });
    Object.keys(VOCAB).forEach((f) => { if (own(s, f) && VOCAB[f].indexOf(s[f]) < 0) P.push(w + "." + f + ": " + JSON.stringify(s[f]) + " unknown to the rig"); });
    return P;
  }
  function validateActor(a, w) {
    if (!a || typeof a !== "object" || Array.isArray(a)) return [w + ": must be an object"];
    const P = [];
    if (!(typeof a.id === "string" && ACTOR_ID.test(a.id))) P.push(w + ": id must match " + ACTOR_ID);
    if (!(typeof a.dom_id === "string" && DOM_ID.test(a.dom_id))) P.push(w + ": dom_id must match " + DOM_ID);
    ["x", "y"].forEach((k) => { if (!(finite(a[k]) && Math.abs(a[k]) <= POS_LIMIT)) P.push(w + ": " + k + " must be a finite number within +-" + POS_LIMIT); });
    if (!(finite(a.scale) && a.scale > 0 && a.scale <= SCALE_MAX)) P.push(w + ": scale must be a number in (0, " + SCALE_MAX + "]");
    const sp = validateSpec(a.spec, w + ".spec");
    if (sp.length) return P.concat(sp);
    if (!(typeof a.fingerprint === "string" && FP.test(a.fingerprint))) P.push(w + ": fingerprint must be 64 lower-case hex characters");
    else if (a.fingerprint !== fingerprintOf(a.spec)) P.push(w + ": fingerprint does not belong to this spec's identity (skin/hair/eyes/glasses) - forged or stale");
    return P;
  }
  const cmp = (x, y) => (x < y ? -1 : x > y ? 1 : 0);
  /** the KeyList rules, identical to animation/keys.py validate_keylist */
  function validate(kl) {
    const P = [];
    if (!kl || typeof kl !== "object" || kl.schema !== SCHEMA) return ["schema must be '" + SCHEMA + "'"];
    if (kl.fps !== FPS) return ["fps must be " + FPS + ": C3 is only built and tested for " + FPS + " fps"];
    if (!(Number.isInteger(kl.frames) && kl.frames > 0)) return ["frames must be a positive integer"];
    if (typeof kl.digest !== "string") P.push("digest missing");
    else { let d = null; try { d = digestOf(kl); } catch (e) { P.push(String(e.message)); } if (d !== null && d !== kl.digest) P.push("digest does not match the content (the KeyList was edited after planning)"); }
    if (!Array.isArray(kl.actors) || !kl.actors.length || !Array.isArray(kl.keys)) return P.concat(["actors (non-empty list) and keys (list) are required"]);
    const actors = Object.create(null), doms = Object.create(null);
    let bad = 0;
    kl.actors.forEach((a, i) => {
      const ap = validateActor(a, "actors[" + i + "]");
      if (ap.length) { bad++; P.push(...ap); return; }
      if (actors[a.id] || doms[a.dom_id]) { bad++; P.push("actors[" + i + "]: duplicate id or dom_id"); return; }
      actors[a.id] = a; doms[a.dom_id] = 1;
    });
    if (bad) return P;
    let prev = null;
    const good = [];
    kl.keys.forEach((k, i) => {
      const w = "key " + i;
      if (!k || typeof k !== "object" || Object.keys(k).sort().join() !== KEY_FIELDS.join()) { P.push(w + ": fields wrong"); return; }
      if (typeof k.actor !== "string" || !actors[k.actor]) { P.push(w + ": unknown actor " + JSON.stringify(k.actor)); return; }
      if (allowed(k.part).indexOf(k.prop) < 0) { P.push(w + ": '" + k.prop + "' not allowed on part '" + k.part + "'"); return; }
      if (k.part === "hairBack" && LONG_HAIR.indexOf(actors[k.actor].spec.hair) < 0) P.push(w + ": hairBack keyed but '" + k.actor + "' has no long hair");
      if (!(Number.isInteger(k.f) && Number.isInteger(k.df) && k.f >= 0 && k.df >= 0)) { P.push(w + ": f/df must be non-negative integers"); return; }
      if (k.t !== ftime(k.f, kl.fps) || k.dur !== ftime(k.df, kl.fps)) P.push(w + ": t/dur not on the frame grid");
      if (k.f + k.df > kl.frames) P.push(w + ": ends after the timeline");
      if (typeof k.ease !== "string" || !own(EASES, k.ease)) P.push(w + ": unknown ease " + JSON.stringify(k.ease));
      if (DISCRETE[k.prop] && k.df !== 0) P.push(w + ": discrete prop tweened");
      ["val", "from"].forEach((fld) => {
        const v = k[fld];
        if (k.prop === "shape") { if (MOUTHS.indexOf(v) < 0) P.push(w + ": unknown mouth " + JSON.stringify(v)); }
        else if (k.prop === "display" || k.prop === "visible") { if (v !== 0 && v !== 1) P.push(w + ": " + fld + " must be 0 or 1"); }
        else if (!finite(v)) P.push(w + ": " + fld + " must be a finite number");
      });
      if (typeof k.src !== "string") P.push(w + ": src must be a string");
      const s = [k.f, k.actor, k.part, k.prop];
      if (prev) { let c = 0; for (let j = 0; j < 4 && !c; j++) c = cmp(s[j], prev[j]); if (c < 0) P.push(w + ": keys not sorted"); }
      prev = s;
      good.push(k);
    });
    groupChannels(good).forEach((c) => {
      let pv = restOf(c.part, c.prop);
      c.keys.forEach((k, j) => {
        if (k.from !== pv) P.push(c.actor + "." + c.part + "." + c.prop + " @frame " + k.f + ": from " + k.from + " != previous value " + pv);
        if (j && conflict(k.f, k.df, c.keys[j - 1].f, c.keys[j - 1].df)) P.push(c.actor + "." + c.part + "." + c.prop + " @frame " + k.f + ": overlaps the previous key");
        pv = k.val;
      });
    });
    return P;
  }

  function groupChannels(keys) {
    const ch = new Map();
    keys.forEach((k) => {
      const id = k.actor + "|" + k.part + "|" + k.prop;
      if (!ch.has(id)) ch.set(id, { actor: k.actor, part: k.part, prop: k.prop, keys: [] });
      ch.get(id).keys.push(k);
    });
    ch.forEach((c) => c.keys.sort((a, b) => a.f - b.f));
    return ch;
  }

  function sampleChannel(keys, part, prop, fr) {
    let cur = keys.length ? keys[0].from : restOf(part, prop);
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      if (k.f > fr + EPS) break;
      if (k.df === 0 || fr >= k.f + k.df - EPS) cur = k.val;
      else cur = k.from + (k.val - k.from) * EASES[k.ease]((fr - k.f) / k.df);
    }
    return cur;
  }

  /** the rig's SVG, parsed inert and checked against the allow-list; returns the checked nodes or throws */
  function safeRigNodes(doc, markup, who) {
    const tpl = doc.createElement("template");
    if (!tpl.content) throw new Error("NFPCharacterRuntime: needs an HTML document (template element)");
    tpl.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg">' + markup + "</svg>";   // inert: nothing runs or loads here
    const root = tpl.content.firstElementChild;
    if (!root || tpl.content.children.length !== 1 || root.localName !== "svg") throw new Error("NFPCharacterRuntime: " + who + ": unexpected rig output");
    const walk = (el) => {
      if (el !== root) {
        if (el.namespaceURI !== "http://www.w3.org/2000/svg" || SAFE_TAGS.indexOf(el.localName) < 0) throw new Error("NFPCharacterRuntime: " + who + ": element <" + el.localName + "> is not allowed");
        for (const at of Array.from(el.attributes)) {
          const n = at.name, v = at.value;
          if (SAFE_ATTRS.indexOf(n) < 0) throw new Error("NFPCharacterRuntime: " + who + ": attribute '" + n + "' is not allowed");
          if (/[<>]|javascript:|data:/i.test(v)) throw new Error("NFPCharacterRuntime: " + who + ": unsafe value in '" + n + "'");
          if (/url\(/i.test(v) && !/^url\(#[A-Za-z0-9_-]+\)$/.test(v)) throw new Error("NFPCharacterRuntime: " + who + ": only url(#local) references are allowed");
          if (n === "style" && !/^display:\s*(inline|none);?$/.test(v)) throw new Error("NFPCharacterRuntime: " + who + ": style '" + v + "' is not allowed");
        }
      }
      for (const n of Array.from(el.childNodes)) {
        if (n.nodeType === 1) walk(n);
        else if (n.nodeType === 3) { if (n.data.trim()) throw new Error("NFPCharacterRuntime: " + who + ": unexpected text in the rig output"); }
        else throw new Error("NFPCharacterRuntime: " + who + ": unexpected node in the rig output");
      }
    };
    walk(root);
    return Array.from(root.childNodes);
  }

  function create(opts) {
    opts = opts || {};
    const K = opts.K || g.K, svg = opts.svg, kl = opts.keylist;
    if (!K || !K.chars || typeof K.chars.actor !== "function") throw new Error("NFPCharacterRuntime: the rig (window.K.chars) is not loaded");
    if (!svg || !svg.ownerDocument) throw new Error("NFPCharacterRuntime: opts.svg must be an <svg> or <g> element");
    const problems = validate(kl);
    if (problems.length) throw new Error("NFPCharacterRuntime: invalid KeyList (" + problems.length + " problem(s))\n" + problems.slice(0, 20).join("\n"));
    const doc = svg.ownerDocument, NS = "http://www.w3.org/2000/svg";
    kl.actors.forEach((a) => { if (doc.getElementById(a.dom_id)) throw new Error("NFPCharacterRuntime: an element with id '" + a.dom_id + "' already exists in this document (the same character placed twice?)"); });
    const fps = kl.fps, duration = kl.frames / fps;
    const built = Object.create(null), frag = doc.createDocumentFragment();

    // ---- build every actor (all or nothing): translate(x y) > [data-p=self] (pivot at the feet) > scale(s) > rig SVG ----
    kl.actors.forEach((a) => {
      const outer = doc.createElementNS(NS, "g"), self = doc.createElementNS(NS, "g"), sc = doc.createElementNS(NS, "g");
      outer.setAttribute("transform", "translate(" + Number(a.x) + " " + Number(a.y) + ")");
      outer.setAttribute("id", a.dom_id);
      outer.setAttribute("data-nfp-actor", a.id);
      outer.setAttribute("data-nfp-fp", a.fingerprint);
      self.setAttribute("data-p", "self");
      sc.setAttribute("transform", "scale(" + Number(a.scale) + ")");
      const spec = {};
      RIG_SPEC_FIELDS.forEach((f) => { spec[f] = a.spec[f]; });
      safeRigNodes(doc, K.chars.actor(spec), a.id).forEach((n) => sc.appendChild(n));
      self.appendChild(sc); outer.appendChild(self); frag.appendChild(outer);
      const mouths = Object.create(null);
      // re-write the rig's inline display styles once, so the DOM text is canonical whatever the seek history
      outer.querySelectorAll("[data-m], [data-x]").forEach((m) => { const d = m.style.display; m.style.cssText = ""; m.style.display = d; });
      outer.querySelectorAll("[data-m]").forEach((m) => { mouths[m.getAttribute("data-m")] = m; });
      built[a.id] = { outer, self, mouths, el: (part) => {
        if (part === "self") return self;
        if (part === "tears" || part === "sweat") return outer.querySelector('[data-x="' + part + '"]');
        return self.querySelector('[data-p="' + part + '"]');
      } };
    });

    // ---- resolve channels to elements once ----
    const channels = [];
    groupChannels(kl.keys).forEach((c) => {
      const b = built[c.actor];
      const target = c.part === "mouth" ? b.mouths : b.el(c.part);
      if (!target || (c.part === "mouth" && MOUTHS.some((m) => !b.mouths[m])))
        throw new Error("NFPCharacterRuntime: actor " + c.actor + " has no part '" + c.part + "' in the rig");
      channels.push(Object.assign(c, { target, actorEl: b }));
    });
    svg.appendChild(frag);

    function apply(c, v) {
      const el = c.target;
      if (c.prop === "shape") { MOUTHS.forEach((m) => { el[m].style.display = m === v ? "inline" : "none"; }); return; }
      if (c.prop === "visible") { el.style.visibility = v ? "visible" : "hidden"; return; }
      if (c.prop === "display") { el.style.display = v ? "inline" : "none"; return; }
      if (c.prop === "opacity") { el.style.opacity = String(v); return; }
      el.style.setProperty(c.prop, String(v));
    }

    let now = 0;
    function state(t) {
      const fr = toFrame(t, fps), out = {};
      channels.forEach((c) => {
        ((out[c.actor] = out[c.actor] || {})[c.part] = out[c.actor][c.part] || {})[c.prop] = sampleChannel(c.keys, c.part, c.prop, fr);
      });
      return out;
    }
    function seek(t) {
      t = Math.max(0, Math.min(duration, +t || 0));
      const fr = toFrame(t, fps);
      channels.forEach((c) => apply(c, sampleChannel(c.keys, c.part, c.prop, fr)));
      now = t;
      return t;
    }

    // ---- real-time playback ----
    const clock = opts.clock || (() => (g.performance ? g.performance.now() : Date.now()));
    const raf = opts.requestAnimationFrame || (g.requestAnimationFrame ? g.requestAnimationFrame.bind(g) : (cb) => setTimeout(() => cb(clock()), 16));
    const caf = opts.cancelAnimationFrame || (g.cancelAnimationFrame ? g.cancelAnimationFrame.bind(g) : clearTimeout);
    let play = null, handle = null, disposed = false;
    function tick() {
      if (!play || play.paused) return;
      const t = play.base + ((clock() - play.started) / 1000) * play.rate;
      if (t >= play.to) {
        seek(play.to); const end = play.onEnd; play.paused = true; play.ended = true; handle = null;
        if (play.onFrame) play.onFrame(play.to);
        if (end) end(play.to);
        return;
      }
      seek(t);
      if (play.onFrame) play.onFrame(t);
      handle = raf(tick);
    }
    const api = {
      fps, duration, keylist: kl, actors: built, channels: channels.length,
      seek, state, time: () => now,
      playing: () => !!(play && !play.paused),
      play(o) {
        o = o || {};
        if (disposed) throw new Error("play: the runtime was disposed");
        const from = o.from !== undefined ? o.from : 0, to = o.to !== undefined ? o.to : duration, rate = o.rate !== undefined ? o.rate : 1;
        if (!finite(from) || !finite(to) || from < 0 || to > duration || !(to > from)) throw new Error("play: need 0 <= from < to <= " + duration);
        if (!finite(rate) || rate <= 0 || rate > 16) throw new Error("play: rate must be a number in (0, 16] (playback only runs forward)");
        if (handle) caf(handle);
        play = { from, to, base: from, rate, started: clock(), paused: false, onFrame: o.onFrame, onEnd: o.onEnd };
        seek(from);
        handle = raf(tick);
        return api;
      },
      pause() {
        if (play && !play.paused) { if (handle) caf(handle); handle = null; tickFreeze(); }
        return api;
      },
      resume() {
        if (play && play.paused && !play.ended) { play.base = now; play.started = clock(); play.paused = false; handle = raf(tick); }
        return api;
      },
      stop() {
        if (handle) caf(handle); handle = null;
        const from = play ? play.from : 0; play = null; if (!disposed) seek(from);
        return api;
      },
      toTimeline(gsap, tl) {
        if (!gsap || typeof gsap.timeline !== "function") throw new Error("toTimeline: pass a local GSAP instance");
        tl = tl || gsap.timeline({ paused: true });
        channels.forEach((c) => {
          c.keys.forEach((k) => {
            const at = k.f / fps, len = k.df / fps;            // exact frame times (k.t is rounded for JSON)
            if (c.prop === "shape") {
              if (k.from !== k.val) { tl.set(c.target[k.from], { display: "none" }, at); tl.set(c.target[k.val], { display: "inline" }, at); }
            } else if (c.prop === "visible") tl.set(c.target, { visibility: k.val ? "visible" : "hidden" }, at);
            else if (c.prop === "display") tl.set(c.target, { display: k.val ? "inline" : "none" }, at);
            else if (k.df === 0) tl.set(c.target, { [c.prop]: k.val }, at);
            else tl.fromTo(c.target, { [c.prop]: k.from }, { [c.prop]: k.val, duration: len, ease: k.ease, immediateRender: false }, at);
          });
        });
        if (tl.duration() < duration) tl.set({}, {}, duration);    // the timeline is exactly as long as the KeyList
        return tl;
      },
      dispose() { api.stop(); disposed = true; Object.keys(built).forEach((id) => built[id].outer.remove()); },
    };
    function tickFreeze() {
      const t = play.base + ((clock() - play.started) / 1000) * play.rate;
      seek(Math.min(play.to, t)); play.paused = true;
    }
    seek(0);
    return api;
  }

  g.NFPCharacterRuntime = { version: "c3d-2", schema: SCHEMA, fps: FPS, RIG_SPEC_FIELDS, VOCAB, EASES, validate, create,
    sampleChannel, sha256, canon, digestOf, fingerprintOf };
})(typeof window !== "undefined" ? window : globalThis);
