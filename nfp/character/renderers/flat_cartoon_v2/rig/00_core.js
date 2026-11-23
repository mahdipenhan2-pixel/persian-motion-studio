/* NFP Docu kit: core helpers (shared by every art module). Pure functions, no DOM access. */
(function (g) {
  "use strict";
  const W = 1920, H = 1080, OL = "#2a1820";

  function rng(seed) { // deterministic PRNG (mulberry32): same seed, same picture, on every render
    let s = seed >>> 0;
    return function () {
      s = (s + 0x6D2B79F5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  function hex2rgb(h) {
    h = h.replace("#", "");
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  const rgb2hex = (c) => "#" + c.map((v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0")).join("");
  function shade(hex, amt) { // amt < 0 darkens, amt > 0 lightens (range -1..1)
    const c = hex2rgb(hex), t = amt < 0 ? 0 : 255, a = Math.abs(amt);
    return rgb2hex(c.map((v) => v + (t - v) * a));
  }
  function mixc(a, b, t) {
    const x = hex2rgb(a), y = hex2rgb(b);
    return rgb2hex(x.map((v, i) => v + (y[i] - v) * t));
  }
  const S = (w) => `stroke="${OL}" stroke-width="${w || 6}" stroke-linejoin="round" stroke-linecap="round"`;
  // Pivot helper: the inner <g data-p> has its origin AT the pivot, so rotation/scale tweens turn around it.
  const P = (name, x, y, inner) => `<g transform="translate(${x} ${y})"><g data-p="${name}">${inner}</g></g>`;
  let n = 0;
  const uid = (p) => p + "_" + (++n);
  g.K = Object.assign(g.K || {}, { W, H, OL, rng, clamp, shade, mixc, S, P, uid });
})(window);
