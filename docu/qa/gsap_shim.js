/* Minimal local stand-in for GSAP (QA only; the real render uses GSAP 3.12.5 from the CDN).
   Supports exactly the subset the docu kit uses: timeline({paused}), fromTo, set, seek/time/duration, attr, CSS vars, colors, steps(). */
(function () {
  const E = {
    none: (p) => p, linear: (p) => p,
    sine: { in: (p) => 1 - Math.cos(p * Math.PI / 2), out: (p) => Math.sin(p * Math.PI / 2), inOut: (p) => -(Math.cos(Math.PI * p) - 1) / 2 },
  };
  [1, 2, 3, 4].forEach((n) => { E["power" + n] = { in: (p) => Math.pow(p, n + 1), out: (p) => 1 - Math.pow(1 - p, n + 1), inOut: (p) => p < .5 ? Math.pow(2 * p, n + 1) / 2 : 1 - Math.pow(2 * (1 - p), n + 1) / 2 }; });
  function ease(name) {
    name = name || "power1.out";
    let m = /^steps\((\d+)\)$/.exec(name); if (m) { const n = +m[1]; return (p) => Math.min(1, Math.floor(p * n) / n); }
    m = /^back\.(in|out|inOut)(?:\(([\d.]+)\))?$/.exec(name);
    if (m) { const s = m[2] ? +m[2] : 1.70158; const o = (p) => { p -= 1; return p * p * ((s + 1) * p + s) + 1; };
      return m[1] === "out" ? o : m[1] === "in" ? (p) => 1 - o(1 - p) : (p) => p < .5 ? (1 - o(1 - 2 * p)) / 2 : (o(2 * p - 1) + 1) / 2 + 0; }
    const [a, b] = name.split("."); if (E[a] && E[a][b]) return E[a][b]; if (typeof E[a] === "function") return E[a]; return (p) => p;
  }
  function targets(t) {
    if (typeof t === "string") return Array.from(document.querySelectorAll(t));
    if (t instanceof Element) return [t];
    if (t && t.length !== undefined) return Array.from(t);
    return [];
  }
  const num = (v) => typeof v === "number";
  function rgba(s) { const m = /rgba?\(([^)]+)\)/.exec(s); if (!m) return null; const a = m[1].split(",").map(Number); return [a[0], a[1], a[2], a.length > 3 ? a[3] : 1]; }
  const ORIG = new Map(); // el -> {key: initial value}; restored before every seek so backward seeks behave like GSAP
  function remember(el, k, a) {
    let m = ORIG.get(el); if (!m) { m = {}; ORIG.set(el, m); }
    const id = a ? "attr:" + a : k; if (id in m) return;
    m[id] = a ? el.getAttribute(a) : (k.startsWith("--") ? el.style.getPropertyValue(k) : el.style[k]);
  }
  function restoreAll() {
    ORIG.forEach((m, el) => { for (const id in m) { const v = m[id];
      if (id.startsWith("attr:")) { const a = id.slice(5); v === null ? el.removeAttribute(a) : el.setAttribute(a, v); }
      else if (id.startsWith("--")) { v === "" ? el.style.removeProperty(id) : el.style.setProperty(id, v); }
      else el.style[id] = v; } });
  }
  function applyProp(el, k, v) {
    if (k === "attr") { for (const a in v) remember(el, k, a); } else remember(el, k);
    if (k === "attr") { for (const a in v) el.setAttribute(a, v[a]); return; }
    if (k.startsWith("--")) { el.style.setProperty(k, String(v)); return; }
    el.style[k] = typeof v === "number" ? (k === "opacity" ? String(v) : v + "px") : v;
  }
  function timeline() {
    const tw = []; let dur = 0;
    const tl = {
      fromTo(t, from, to, pos) { return add(t, from, to, pos, false); },
      set(t, vars, pos) { return add(t, null, Object.assign({ duration: 0 }, vars), pos, true); },
      seek(x) { return tl.time(x); }, duration() { return dur; },
      time(x) {
        if (x === undefined) return tl._t; tl._t = x; restoreAll();
        const latest = new Map();
        for (const w of tw) { // later tweens override earlier on the same el/prop; evaluate in creation order
          for (const el of w.els) {
            if (x < w.start) continue;
            const p = w.dur > 0 ? Math.min(1, (x - w.start) / w.dur) : 1;
            const ep = w.easeF(p);
            for (const k in w.to) {
              if (["duration", "ease", "immediateRender", "delay"].includes(k)) continue;
              const tv = w.to[k];
              if (k === "attr") { const o = {}; for (const a in tv) { const f = w.from && w.from.attr ? w.from.attr[a] : undefined; o[a] = num(tv[a]) && num(f) ? f + (tv[a] - f) * ep : tv[a]; } applyProp(el, k, o); continue; }
              const fv = w.from ? w.from[k] : undefined;
              let val;
              if (num(tv) && num(fv)) val = fv + (tv - fv) * ep;
              else if (typeof tv === "string" && typeof fv === "string" && rgba(tv) && rgba(fv)) { const a = rgba(fv), b = rgba(tv); val = `rgba(${a.map((q, i) => q + (b[i] - q) * ep).map((q, i) => i < 3 ? Math.round(q) : q.toFixed(3)).join(",")})`; }
              else val = (p >= 1 || w.set) ? tv : (fv !== undefined ? fv : tv);
              applyProp(el, k, val);
            }
          }
        }
      },
      _t: 0, paused() { return tl; }, pause() { return tl; },
    };
    function add(t, from, to, pos, isSet) {
      const els = targets(t); if (!els.length) throw new Error("shim: no target for " + t);
      const w = { els, from, to, start: pos === undefined ? dur : pos, dur: to.duration || 0, easeF: ease(to.ease), set: isSet };
      tw.push(w); dur = Math.max(dur, w.start + w.dur); return tl;
    }
    return tl;
  }
  window.gsap = { timeline: (o) => timeline(o), set: (t, v) => targets(t).forEach((el) => { for (const k in v) applyProp(el, k, v[k]); }) };
})();
