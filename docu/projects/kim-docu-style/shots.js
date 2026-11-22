/* Documentary motion-graphics style experiment (project kim-docu-style, 18.5 s, sentences s1-s4 of the approved script).
   Self-contained: the documentary helpers (DK) live at the top of this file so NO shared engine file is changed and the
   approved cinematic cartoon version (kim-test30-cine) is untouched.
   Pillars: animated timeline + dates, stylised map motion, photo-frame layouts with camera movement,
   cinematic transitions (flash, whip pan, rewind, map zoom-through), cartoon reconstruction where no photo exists.
   PHOTOS: none is embedded. Every photo slot is a clearly marked PLACEHOLDER (see photo_slots.json). */

const KIM = { skin: "#d99a73", hairColor: "#16100f", eyeColor: "#4a2a1a", accent: "#e4483f" };
const BABY = Object.assign({}, KIM, { build: "baby", hair: "baby_tuft", outfit: "babygrow", top: "#f6e7a8", pants: "#f6e7a8", shoe: "#f6e7a8", legs: "pants", sleeve: "none" });
const KID = Object.assign({}, KIM, { build: "child", hair: "child_pony", outfit: "sweat80s", top: "#f2a7b8", pants: "#6a7ec2", shoe: "#f2efe8" });
const DAD = { build: "man", skin: "#e8b896", hair: "short_man", hairColor: "#4a3426", top: "#2f3a4f", pants: "#262b3a", outfit: "suit", glasses: 1, accent: "#a63a3a" };
const MOM = { build: "woman", skin: "#e5ae88", hair: "big80s", hairColor: "#241713", top: "#b4434a", pants: "#2b2230", outfit: "blazer", accent: "#f3c64a", earrings: 1, lip: "#b23a4a", sleeve: "long" };
const MOMW = Object.assign({}, MOM, { outfit: "dress", top: "#f6f1e8", legs: "bare", shoe: "#f6f1e8", shoeType: "pump", sleeve: "none" });
const BRUCE = { build: "man", skin: "#e9b996", hair: "slick", hairColor: "#6a4a2e", top: "#3a6aa8", pants: "#2e3a5a", outfit: "track", accent: "#f6f2e8", shoe: "#f6f2e8" };
const BRUCEW = Object.assign({}, BRUCE, { outfit: "suit", top: "#2b2f3d", pants: "#2b2f3d", accent: "#c43b3b", shoe: "#1a1a22" });
const FX = K.fx, PR = FX.props, C = K.cine, B = K.bgc, FG = K.fgc, OLN = K.OL, P = K.P, rng = K.rng, uid = K.uid;
const W = (sid, i) => [sid, "w", i], E = (sid, i) => [sid, "e", i];
const st = (w) => `stroke="${OLN}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"`;
const grade = (S, name, o) => S.layer(C.look(name, o), 0);
const light = (S, x, y, rx, ry, col, op) => S.layer(C.key(x, y, rx, ry, col, op), 0);
const SVGNS = "http://www.w3.org/2000/svg", FONT = FX.FONT;
const lerp = (a, b, t) => a + (b - a) * t;
const EASEF = { "power2.inOut": (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2), "power3.out": (p) => 1 - Math.pow(1 - p, 4), "power2.out": (p) => 1 - Math.pow(1 - p, 3), none: (p) => p };

/* =====================================================================================================
   DK: documentary kit
   ===================================================================================================== */
const DK = {};

/* ---------- stylised map: Albers conic projection of hand-simplified outlines (not survey data) ---------- */
(() => {
  const R = Math.PI / 180, p1 = 29.5 * R, p2 = 45.5 * R, p0 = 37.5 * R, l0 = -96 * R;
  const n = (Math.sin(p1) + Math.sin(p2)) / 2, Cc = Math.cos(p1) ** 2 + 2 * n * Math.sin(p1), r0 = Math.sqrt(Cc - 2 * n * Math.sin(p0)) / n;
  const base = (lo, la) => { const r = Math.sqrt(Cc - 2 * n * Math.sin(la * R)) / n, th = n * (lo * R - l0); return [r * Math.sin(th), r0 - r * Math.cos(th)]; };
  const c = base(-96, 39.5), SC = 2000;
  DK.proj = (lo, la) => { const q = base(lo, la); return [960 + (q[0] - c[0]) * SC, 500 - (q[1] - c[1]) * SC]; };
})();
DK.LA = [-118.24, 34.05];
DK.MTL = [-73.57, 45.5];

const US_W = [[-117.12, 32.53], [-117.3, 33.1], [-118.4, 33.75], [-118.5, 34.03], [-119.2, 34.15], [-120.5, 34.45], [-120.65, 35.15], [-121.9, 36.6], [-122.4, 37.2], [-122.5, 37.8], [-123, 38], [-123.8, 39.4], [-124.35, 40.4], [-124.1, 41.9], [-124.5, 42.8], [-124.1, 44], [-124, 46.25], [-124.7, 48.4], [-123.2, 48.2], [-122.75, 47.2], [-122.4, 47.6], [-122.8, 48.1], [-122.75, 49]];
const US_N = [[-95.15, 49], [-95.15, 49.38], [-94.6, 48.72], [-93, 48.62], [-91.4, 48.1], [-89.6, 48], [-88.4, 48.3], [-84.9, 46.95], [-84.5, 46.45], [-83.6, 45.8], [-82.5, 45.3], [-82.4, 43], [-83.1, 42], [-82.5, 41.9], [-80.5, 42.4], [-79, 42.8], [-79.05, 43.25], [-77.5, 43.6], [-76.3, 43.9], [-76, 44.3], [-75, 44.95], [-71.5, 45], [-70.8, 45.4], [-70.4, 46], [-70, 46.7], [-69.2, 47.45], [-68.3, 47.35], [-67.8, 47], [-67.8, 45.7], [-67.4, 45.15], [-66.98, 44.8]];
const US_E = [[-68.2, 44.3], [-69.1, 44], [-70.2, 43.65], [-70.7, 43], [-70.8, 42.6], [-70.6, 42.3], [-70, 42], [-70.6, 41.6], [-71.5, 41.4], [-72.9, 41.25], [-73.7, 40.9], [-74, 40.55], [-74.1, 39.7], [-74.9, 38.95], [-75.1, 38.4], [-75.7, 37.5], [-76, 37], [-75.9, 36.5], [-75.5, 35.25], [-76.5, 34.7], [-77.9, 33.9], [-78.9, 33.7], [-79.9, 32.7], [-80.9, 32], [-81.4, 30.7], [-81.3, 29.8], [-80.6, 28.4], [-80.05, 26.8], [-80.2, 25.7], [-80.4, 25.2], [-81.1, 25.15], [-81.8, 26.1], [-82.2, 26.8], [-82.7, 27.7], [-82.7, 28.9], [-83.7, 29.9], [-84.3, 30.05], [-85.3, 29.7], [-86.4, 30.4], [-87.5, 30.3], [-88.4, 30.35], [-89.4, 30.2], [-89.4, 29.5], [-89.2, 29.05], [-90.2, 29.1], [-91.3, 29.3], [-92.3, 29.55], [-93.8, 29.7], [-94.8, 29.35], [-95.9, 28.6], [-96.9, 28], [-97.4, 27.3], [-97.2, 25.95]];
const US_S = [[-99.1, 26.4], [-99.5, 27.5], [-100.3, 28.3], [-101.4, 29.8], [-102.4, 29.8], [-103.1, 29], [-104.5, 29.6], [-104.9, 30.6], [-106.5, 31.78], [-108.2, 31.8], [-108.2, 31.33], [-111.07, 31.33], [-114.8, 32.5]];
const CA_PAC = [[-123.1, 49.3], [-124.8, 50], [-127.5, 51], [-128.6, 52.6], [-130.2, 54.7], [-132, 56.5], [-135, 59.5], [-138, 62.5]];
const CA_ATL = [[-48, 62.5], [-55.5, 52.2], [-57, 51.8], [-60, 46.4], [-61.2, 45.2], [-63.5, 44.5], [-65.8, 43.6], [-66.2, 44.4]];
const MX_GULF = [[-97.5, 25], [-97.8, 22.5], [-97.2, 20.5], [-96.1, 19.1], [-94.8, 18.2], [-92.5, 18.6], [-91.5, 18.8], [-90.5, 19.8], [-90.4, 21], [-87.5, 21.5], [-87, 20], [-88, 17.5], [-88, 14], [-103, 14], [-104, 18.8], [-105.5, 20.2], [-105.3, 21.5], [-106.4, 23.2], [-108, 25.1], [-109.4, 26.6], [-110.6, 27.9], [-112.2, 29.1], [-113, 30.6], [-114.4, 31.7], [-114.8, 31.7]];
const BAJA = [[-114.8, 31], [-113.5, 28.9], [-112.3, 27.3], [-111.3, 26], [-110.3, 24.1], [-109.9, 22.9], [-112.1, 24.6], [-115.1, 27.8], [-116.6, 31.85]];
const LAKES = [
  [[-92.1, 46.8], [-90.4, 46.6], [-88.5, 47.4], [-87.4, 46.5], [-85, 46.7], [-84.7, 47], [-86.5, 48.2], [-88.3, 48.9], [-89.6, 48.1], [-90.8, 47.7]],
  [[-87.8, 41.7], [-87, 41.7], [-86.3, 42.5], [-86.5, 44], [-85.5, 45.2], [-85, 45.9], [-86, 45.9], [-87, 45.5], [-87.7, 44.5], [-87.9, 43]],
  [[-84.7, 45.9], [-82, 46.1], [-80.2, 45.3], [-81.7, 44.6], [-81.7, 43.5], [-82.5, 43], [-83, 44], [-83.5, 45], [-84.7, 45.5]],
  [[-83.4, 41.7], [-81.7, 41.5], [-79.8, 42.2], [-78.9, 42.8], [-80.4, 42.8], [-82.5, 42]],
  [[-79.8, 43.3], [-78, 43.3], [-76.3, 43.5], [-76.2, 44.1], [-77.5, 44], [-79.4, 43.7]],
  [[-71, 46.85], [-69.4, 47.9], [-67, 49.1], [-64.5, 49.9], [-61.2, 50.2], [-57.8, 51.2], [-55.9, 51.9], [-55.5, 50], [-57.5, 48.5], [-58.5, 47.5], [-60.4, 46.6], [-61.6, 46], [-63.5, 46.3], [-64.8, 47.2], [-65.2, 48], [-66.4, 48.2], [-68, 48.6], [-69.5, 47.7], [-70.6, 47]],
];
const chaikin = (pts, it) => { for (let k = 0; k < it; k++) { const o = []; for (let i = 0; i < pts.length; i++) { const a = pts[i], b = pts[(i + 1) % pts.length]; o.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25], [a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]); } pts = o; } return pts; };
const pathOf = (ll, it) => { const p = chaikin(ll.map(([lo, la]) => DK.proj(lo, la)), it === undefined ? 1 : it); return "M" + p.map((q) => q[0].toFixed(1) + " " + q[1].toFixed(1)).join("L") + "Z"; };
DK.mapSvg = () => {
  const oc = uid("oc"), dp = uid("dp"), usd = uid("usd");
  const usLL = [].concat(US_W, US_N, US_E, US_S);
  const contLL = [].concat(US_W, CA_PAC, CA_ATL, US_E, MX_GULF, BAJA);
  let grat = "";
  for (let lo = -150; lo <= -40; lo += 10) { let d = ""; for (let la = 12; la <= 66; la += 3) { const q = DK.proj(lo, la); d += (d ? "L" : "M") + q[0].toFixed(0) + " " + q[1].toFixed(0); } grat += `<path d="${d}"/>`; }
  for (let la = 10; la <= 60; la += 10) { let d = ""; for (let lo = -160; lo <= -30; lo += 4) { const q = DK.proj(lo, la); d += (d ? "L" : "M") + q[0].toFixed(0) + " " + q[1].toFixed(0); } grat += `<path d="${d}"/>`; }
  const T = (txt, lo, la, sz, op, rot) => { const q = DK.proj(lo, la); return `<text transform="translate(${q[0].toFixed(0)} ${q[1].toFixed(0)}) rotate(${rot || 0})" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="${sz}" letter-spacing="${Math.round(sz * 0.42)}" fill="#cfe0f5" opacity="${op}">${txt}</text>`; };
  const cont = pathOf(contLL, 1), us = pathOf(usLL, 1);
  return `<defs>
      <radialGradient id="${oc}" cx="52%" cy="46%" r="75%"><stop offset="0" stop-color="#17324f"/><stop offset=".6" stop-color="#0d1d31"/><stop offset="1" stop-color="#060d18"/></radialGradient>
      <pattern id="${dp}" width="14" height="14" patternUnits="userSpaceOnUse"><circle cx="7" cy="7" r="1.8" fill="#9ec2ea" opacity=".55"/></pattern>
      <linearGradient id="${usd}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#37587f"/><stop offset="1" stop-color="#27425f"/></linearGradient></defs>
    <rect x="-900" y="-700" width="3700" height="2500" fill="url(#${oc})"/>
    <g fill="none" stroke="#7fa6d4" stroke-width="1.6" opacity=".2">${grat}</g>
    <path d="${cont}" transform="translate(0 16)" fill="#000" opacity=".45"/>
    <path d="${cont}" fill="#1c2c42" stroke="#5a7da6" stroke-width="2.4" stroke-linejoin="round"/>
    <path d="${cont}" fill="url(#${dp})" opacity=".28"/>
    <path d="${us}" fill="url(#${usd})" stroke="#a9c9ee" stroke-width="3" stroke-linejoin="round"/>
    <path d="${us}" fill="url(#${dp})" opacity=".34"/>
    ${LAKES.map((l) => `<path d="${pathOf(l, 1)}" fill="#0d1d31" stroke="#7fa6d4" stroke-width="2" opacity=".96"/>`).join("")}
    ${T("PACIFIC OCEAN", -131, 33, 30, 0.2, -62)}${T("ATLANTIC", -62, 36, 28, 0.2, 52)}${T("UNITED STATES", -99, 40.2, 40, 0.34)}${T("CANADA", -101, 55, 46, 0.22)}${T("MEXICO", -102, 23.4, 30, 0.22)}`;
};

/* ---------- timeline HUD: scrolling year ruler + rolling year number (all keys on the shot, deterministic) ---------- */
DK.hud = (S, id, o) => {
  const PX = 46, y = o.y || 150, lo = Math.floor(Math.min(o.from, o.to)) - 4, hi = Math.ceil(Math.max(o.from, o.to)) + 4, mk = uid("hm");
  let tk = "", yrs = "";
  for (let k = lo; k <= hi; k++) {
    const major = k % 5 === 0;
    tk += `<path d="M${k * PX} ${major ? -15 : -8}V${major ? 15 : 8}" stroke="#fff" stroke-width="${major ? 3 : 2}" opacity="${major ? 0.9 : 0.45}"/>`;
    if (major) tk += `<text x="${k * PX}" y="40" text-anchor="middle" font-family='${FONT}' font-size="21" font-weight="700" fill="#d5deec" opacity=".85">${k}</text>`;
  }
  (o.marks || []).forEach((m) => { tk += `<circle cx="${m.y * PX}" cy="0" r="7" fill="#ffb84a" stroke="#1a1208" stroke-width="2"/><text x="${m.y * PX}" y="64" text-anchor="middle" font-family='${FONT}' font-size="18" font-weight="800" fill="#ffb84a" letter-spacing="2">${m.label}</text>`; });
  const yMin = Math.min(o.from, o.to), yMax = Math.max(o.from, o.to);
  for (let k = Math.floor(yMin); k <= Math.ceil(yMax); k++) yrs += `<text data-p="${id}_y${k}" x="960" y="86" text-anchor="middle" font-family='${FONT}' font-size="84" font-weight="800" fill="#fff" stroke="#0a0d14" stroke-width="5" paint-order="stroke" letter-spacing="3" style="visibility:hidden">${k}</text>`;
  S.layer(`<defs><linearGradient id="${mk}g" x1="0" x2="1"><stop offset="0" stop-color="#000"/><stop offset=".18" stop-color="#fff"/><stop offset=".82" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
      <mask id="${mk}" maskUnits="userSpaceOnUse" x="240" y="${y - 70}" width="1440" height="180"><rect x="240" y="${y - 70}" width="1440" height="180" fill="url(#${mk}g)"/></mask></defs>
    <g data-p="${id}"><rect x="260" y="${y - 52}" width="1400" height="128" rx="14" fill="#05070c" opacity=".62" stroke="#fff" stroke-opacity=".16" stroke-width="2"/>
    <g mask="url(#${mk})"><g transform="translate(960 ${y})"><g data-p="${id}_r">${tk}</g></g></g>
    <path d="M960 ${y - 52}V${y + 76}" stroke="#ffb84a" stroke-width="4"/><path d="M944 ${y - 52}H976L960 ${y - 34}Z" fill="#ffb84a"/>${yrs}</g>`, 0);
  const rr = S.q(id + "_r");
  S.key(rr, "--x", S.t0, -o.from * PX, 0);
  const ease = o.ease || "power2.inOut", span = o.t1 - o.t0, f = EASEF[ease] || EASEF["power2.inOut"];
  if (o.from !== o.to) S.key(rr, "--x", o.t0, -o.to * PX, span, ease);   // the ruler rests on `from` from the first frame of the shot
  // rolling number: year k becomes visible when the eased progress reaches it
  const shown = (k) => S.show(id + "_y" + k, S.t0, false);
  const seq = []; const dir = o.to >= o.from ? 1 : -1;
  for (let k = o.from; dir > 0 ? k <= o.to : k >= o.to; k += dir) seq.push(k);
  seq.forEach((k, i) => { let tt = S.t0; if (o.from !== o.to && i > 0) { const target = i / (seq.length - 1); let a = 0, b = 1; for (let q = 0; q < 24; q++) { const m = (a + b) / 2; if (f(m) < target) a = m; else b = m; } tt = o.t0 + span * b; } tt = Math.round(tt * 30) / 30;
    if (i > 0) S.show(id + "_y" + seq[i - 1], tt, false);
    S.show(id + "_y" + k, tt, true); });
  void shown;
  if (o.label) { S.layer(`<text data-p="${id}_lab" x="960" y="${y + 112}" text-anchor="middle" font-family='${FONT}' font-size="22" font-weight="800" letter-spacing="6" fill="#ffb84a" stroke="#0a0d14" stroke-width="4" paint-order="stroke">${o.label}</text>`, 0); S.fadeIn(id + "_lab", o.t0 + 0.2, 0.3); }
};

/* ---------- lower-third tag (accent bar + two lines), wipes in from the left ---------- */
DK.tag = (S, id, title, sub, x, y, t, o) => {
  o = o || {}; const w = o.w || Math.max(520, title.length * 30 + 90);
  S.layer(P(id, x, y, `<defs><linearGradient id="${id}bg" x1="0" x2="1"><stop offset="0" stop-color="#05070c" stop-opacity=".82"/><stop offset="1" stop-color="#05070c" stop-opacity="0"/></linearGradient></defs>
    <rect x="0" y="-56" width="${w}" height="${sub ? 118 : 84}" fill="url(#${id}bg)"/><rect x="0" y="-56" width="8" height="${sub ? 118 : 84}" fill="#ffb84a"/>
    <text x="28" y="${sub ? -8 : 8}" font-family='${FONT}' font-weight="800" font-size="${o.size || 46}" fill="#fff" letter-spacing="3">${title}</text>
    ${sub ? `<text x="28" y="34" font-family='${FONT}' font-weight="700" font-size="24" fill="#ffb84a" letter-spacing="5">${sub}</text>` : ""}`), 0.4);
  S.key(id, "--sx", t, 0, 0); S.key(id, "--sx", t, 1, 0.45, "power3.out"); S.key(id, "--s", t, 1, 0);
  const e = S.q(id); e.style.opacity = "0"; S.key(e, "opacity", t, 0, 0); S.key(e, "opacity", t, 1, 0.2, "power1.out");
};

/* ---------- photo frame (print on an archive board). PLACEHOLDER unless an explicit, licence-verified src is passed ---------- */
DK.photoSvg = (id, o) => {
  const w = o.w || 760, h = o.h || 500, b = 20, cap = 84, tw = w + 2 * b, th = h + b + cap, X = -tw / 2, Y = -th / 2, ix = X + b, iy = Y + b;
  const pat = uid("pp"), gr = uid("pg"), cl = uid("pc"), sh = uid("ps"), hz = uid("hz");
  const inner = o.src ? `<image href="${o.src}" x="${ix}" y="${iy}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid slice"/>`
    : `<rect x="${ix}" y="${iy}" width="${w}" height="${h}" fill="url(#${gr})"/><rect x="${ix}" y="${iy}" width="${w}" height="${h}" fill="url(#${pat})"/>
       <g transform="translate(${ix + w / 2} ${iy + h / 2 - 34})" opacity=".55"><circle cx="-92" cy="-58" r="30" fill="#9db2d2"/><path d="M-190 90L-70 -20L-10 50L60 -40L190 90Z" fill="#7d93b6"/></g>
       ${o.bare ? "" : `<text x="${ix + w / 2}" y="${iy + h / 2 + 92}" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#fff" letter-spacing="4">PHOTO SLOT ${o.slot}</text>
       <text x="${ix + w / 2}" y="${iy + h / 2 + 134}" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="25" fill="#ffb84a" letter-spacing="4">NO LICENSED PHOTO YET</text>
       <rect x="${ix}" y="${iy}" width="${w}" height="46" fill="url(#${hz})"/><text x="${ix + w / 2}" y="${iy + 33}" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="28" fill="#15110a" letter-spacing="14">PLACEHOLDER</text>`}`;
  return `<defs>
      <linearGradient id="${gr}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a5670"/><stop offset="1" stop-color="#242b3b"/></linearGradient>
      <pattern id="${pat}" width="26" height="26" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="13" height="26" fill="#fff" opacity=".05"/></pattern>
      <pattern id="${hz}" width="44" height="46" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="22" height="60" fill="#ffb84a"/><rect x="22" width="22" height="60" fill="#e8d6a8"/></pattern>
      <radialGradient id="${sh}"><stop offset="0" stop-color="#000" stop-opacity=".65"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
      <clipPath id="${cl}"><rect x="${ix}" y="${iy}" width="${w}" height="${h}"/></clipPath></defs>
    <g data-p="${id}"><ellipse cx="14" cy="${th / 2 + 6}" rx="${tw * 0.58}" ry="46" fill="url(#${sh})"/><rect x="${X}" y="${Y}" width="${tw}" height="${th}" rx="6" fill="#f3eee2" stroke="#d9d1bf" stroke-width="2"/>
      <g clip-path="url(#${cl})">${inner}<g data-p="${id}_sheen"><path d="M${ix - 260} ${iy - 20}L${ix - 120} ${iy - 20}L${ix - 300} ${iy + h + 20}L${ix - 440} ${iy + h + 20}Z" fill="#fff" opacity=".3" style="mix-blend-mode:screen"/></g></g>
      <text x="${X + 34}" y="${Y + th - 28}" font-family='${FX.HAND}' font-weight="700" font-size="50" fill="#2a1820">${o.cap}</text>
      <rect x="${X - 26}" y="${Y - 14}" width="130" height="40" fill="#e9ddb4" opacity=".78" transform="rotate(-32 ${X + 40} ${Y})"/><rect x="${X + tw - 104}" y="${Y - 14}" width="130" height="40" fill="#e9ddb4" opacity=".78" transform="rotate(32 ${X + tw - 40} ${Y})"/></g>`;
};

/* ---------- archive board backdrop: dark wall, faint giant year, scattered papers (parallax layers) ---------- */
DK.boardFar = (year, seed) => {
  const g = uid("bd"); const r = rng(seed);
  return `<defs><radialGradient id="${g}" cx="52%" cy="45%" r="70%"><stop offset="0" stop-color="#2a3550"/><stop offset=".6" stop-color="#141b2c"/><stop offset="1" stop-color="#070a12"/></radialGradient></defs>
    <rect x="-200" y="-200" width="2320" height="1480" fill="url(#${g})"/>
    <g stroke="#9db6dd" stroke-width="1.5" opacity=".09">${Array.from({ length: 30 }, (_, i) => `<path d="M${-200 + i * 90} -200V1300"/>`).join("")}${Array.from({ length: 18 }, (_, i) => `<path d="M-200 ${-100 + i * 90}H2200"/>`).join("")}</g>
    <text x="960" y="760" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="560" fill="none" stroke="#9db6dd" stroke-width="3" opacity=".13">${year}</text>` + C.bokeh(seed, ["#7d98c8", "#ffd9a0"], 10);
};
DK.boardNear = (seed) => {
  const r = rng(seed); let m = "";
  for (let i = 0; i < 7; i++) { const x = Math.round(r() * 1920), y = Math.round(r() * 1080), w = 150 + Math.round(r() * 170), h = 100 + Math.round(r() * 140), a = Math.round((r() - 0.5) * 50); m += `<g transform="translate(${x} ${y}) rotate(${a})"><rect x="${-w / 2 + 8}" y="${-h / 2 + 12}" width="${w}" height="${h}" fill="#000" opacity=".35"/><rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${["#d9d1bf", "#c3cbd8", "#e8dcc0"][i % 3]}" opacity=".55"/><path d="M${-w / 2 + 14} ${-h / 2 + 22}H${w / 2 - 14}M${-w / 2 + 14} ${-h / 2 + 40}H${w / 2 - 50}" stroke="#444" stroke-width="3" opacity=".35"/></g>`; }
  return m;
};

/* ---------- transitions: flash, whip pan, fade from/to black. Registered during the build, applied in time order ---------- */
DK.pend = { flash: [], whip: [] };
DK.flash = (t, peak, dur) => DK.pend.flash.push([t, peak === undefined ? 0.9 : peak, dur || 0.22]);
DK.whip = (tCut, dir) => DK.pend.whip.push([tCut, dir || 1]);
DK.flush = (D_) => {
  const post = document.getElementById("post"), world = D_.world;
  const defs = document.createElementNS(SVGNS, "defs");
  defs.innerHTML = '<filter id="whipf" x="-6%" y="-6%" width="112%" height="112%" color-interpolation-filters="sRGB"><feGaussianBlur id="whipb" stdDeviation="0 0"/></filter>';
  post.appendChild(defs);
  const fl = document.createElementNS(SVGNS, "rect"); fl.setAttribute("id", "dflash"); fl.setAttribute("width", "1920"); fl.setAttribute("height", "1080"); fl.setAttribute("fill", "#fff"); fl.setAttribute("opacity", "0"); fl.setAttribute("data-p", "dflash"); post.appendChild(fl);
  const bl = document.createElementNS(SVGNS, "rect"); bl.setAttribute("width", "1920"); bl.setAttribute("height", "1080"); bl.setAttribute("fill", "#000"); bl.setAttribute("opacity", "1"); bl.setAttribute("data-p", "dblack"); post.appendChild(bl);
  const SN = (t) => Math.round(t * 30) / 30;
  DK.pend.flash.sort((a, b) => a[0] - b[0]).forEach(([t, pk, d]) => { D_.key(fl, "opacity", SN(t), pk, 1 / 30, "none"); D_.key(fl, "opacity", SN(t) + 1 / 30, 0, d, "power2.out"); });
  D_.key(bl, "opacity", 0, 1, 0); D_.key(bl, "opacity", 0, 0, 0.55, "power2.out");
  D_.key(bl, "opacity", SN(D_.DATA.duration - 0.45), 0, 0); D_.key(bl, "opacity", SN(D_.DATA.duration - 0.45), 1, 0.43, "power1.in");
  const bb = document.getElementById("whipb");
  DK.pend.whip.sort((a, b) => a[0] - b[0]).forEach(([t, dir]) => {
    const seq = [[-0.1, 14, -50], [-0.067, 60, -120], [-0.033, 120, -190], [0, 150, 190], [0.033, 100, 110], [0.067, 46, 48], [0.1, 14, 12]];
    D_.tl.set(world, { filter: "url(#whipf)" }, SN(t - 0.1));
    seq.forEach(([dt, sd, tx]) => { D_.tl.set(bb, { attr: { stdDeviation: sd + " 0" } }, SN(t + dt)); D_.tl.set(world, { attr: { transform: "translate(" + (tx * dir) + " 0)" } }, SN(t + dt)); });
    D_.tl.set(world, { filter: "none" }, SN(t + 0.133)); D_.tl.set(world, { attr: { transform: "translate(0 0)" } }, SN(t + 0.133));
  });
};

/* ---------- map helpers ---------- */
const mapGo = (S, nm, t, dur, s, Q, T, ease) => { S.key(nm, "--s", t, s, dur, ease); S.key(nm, "--x", t, T[0] - s * Q[0], dur, ease); S.key(nm, "--y", t, T[1] - s * Q[1], dur, ease); };
const dashIn = (el, L, t, dur, ease) => { el.setAttribute("stroke-dasharray", L); el.setAttribute("stroke-dashoffset", L); D.tl.fromTo(el, { attr: { "stroke-dashoffset": L } }, { attr: { "stroke-dashoffset": 0 }, duration: dur, ease: ease || "power1.inOut", immediateRender: false }, t); };
const pinSvg = (id, label, o) => `<g data-p="${id}"><circle r="52" fill="none" stroke="#ffb84a" stroke-width="4" opacity=".0" data-p="${id}_rp"/><circle r="9" fill="#ffb84a" stroke="#1a1208" stroke-width="3"/><circle r="22" fill="none" stroke="#ffb84a" stroke-width="3"/>
    <path d="M0 -9V-${(o && o.stem) || 70}" stroke="#ffb84a" stroke-width="3"/><g transform="translate(0 -${((o && o.stem) || 70) + 6})"><rect x="${-(label.length * 21 + 44) / 2}" y="-40" width="${label.length * 21 + 44}" height="48" rx="6" fill="#05070c" opacity=".86" stroke="#ffb84a" stroke-width="2"/>
    <text y="-6" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="25" fill="#fff" letter-spacing="3">${label}</text></g></g>`;

/* ===================================================================================================== */
/* shots                                                                                                    */
/* ===================================================================================================== */
const closeUp = (S, id, spec, cx, cy, head, o) => {
  const b = K.chars.BUILDS[spec.build], yH = -(b.legH + b.torsoH + b.neck - 8), sc = head / (184 * b.headS);
  return S.actor(id, Object.assign({ detail: 1 }, spec), cx, cy - (yH - 88 * b.headS) * sc, sc, o || {});
};
const confetti = (S, t0, n, seed) => { const r = rng(seed), cols = ["#f3c64a", "#e4483f", "#4c8a5a", "#3d6a9c", "#fff"]; let m = "";
  for (let i = 0; i < n; i++) m += `<g transform="translate(${Math.round(160 + r() * 1600)} -40)"><g data-p="cf${i}"><rect x="-9" y="-5" width="18" height="10" fill="${cols[i % 5]}" stroke="#2a1820" stroke-width="2"/></g></g>`;
  S.layer(m, 1.2);
  for (let i = 0; i < n; i++) { const e = S.q("cf" + i), s0 = t0 + r() * 0.9, d = Math.max(0.3, Math.min(2.0 + r() * 1.4, S.t1 - s0 - 0.02));
    S.key(e, "--y", s0, 0, 0); S.key(e, "--y", s0, 1180, d, "none"); S.key(e, "--x", s0, 0, 0); S.key(e, "--x", s0, (r() - 0.5) * 260, d, "sine.inOut"); S.key(e, "--r", s0, 0, 0); S.key(e, "--r", s0, (r() - 0.5) * 900, d, "none"); } };
const LAp = DK.proj(DK.LA[0], DK.LA[1]), MTp = DK.proj(DK.MTL[0], DK.MTL[1]);
const spos = (q, s, Q, T) => [s * q[0] + T[0] - s * Q[0], s * q[1] + T[1] - s * Q[1]];
const CITIES = [["SEATTLE", -122.3, 47.6], ["SAN FRANCISCO", -122.4, 37.8], ["SAN DIEGO", -117.2, 32.7], ["DENVER", -105, 39.7], ["HOUSTON", -95.4, 29.8], ["CHICAGO", -87.6, 41.9], ["NEW YORK", -74, 40.7], ["MIAMI", -80.2, 25.8]];
const cityDots = () => CITIES.map(([n, lo, la]) => { const q = DK.proj(lo, la); return `<circle cx="${q[0].toFixed(0)}" cy="${q[1].toFixed(0)}" r="4.5" fill="#fff" opacity=".8"/><text x="${(q[0] + 10).toFixed(0)}" y="${(q[1] + 5).toFixed(0)}" font-family='${FONT}' font-weight="700" font-size="13" letter-spacing="2" fill="#dbe7f7" opacity=".6">${n}</text>`; }).join("");

/* ================= 1 · MAP: North America, push in to Los Angeles (title -> location) ================= */
D.shot({ id: "map1", a: 0, b: W("s1", 7), cam: { from: [0, 0, 0], to: [0, 0, 0.05] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, T = [760, 520];
    S.layer(`<g data-p="mz">${DK.mapSvg()}${cityDots()}</g>`, 0.45);
    mapGo(S, "mz", t0, 0, 0.94, [960, 500], [960, 500]);
    mapGo(S, "mz", 0.45, 1.15, 3.0, LAp, T, "power2.inOut");
    mapGo(S, "mz", 1.6, t1 - 1.6, 3.3, LAp, T, "none");
    S.layer(`<g data-p="title"><text x="960" y="196" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="34" letter-spacing="14" fill="#cfe0f5" stroke="#05070c" stroke-width="5" paint-order="stroke">WHAT IF YOU WERE BORN AS</text>
      <text x="960" y="300" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="100" letter-spacing="4" fill="#fff" stroke="#05070c" stroke-width="7" paint-order="stroke">KIM KARDASHIAN?</text></g>`, 0.1);
    S.fadeIn("title", 0.2, 0.3); S.fadeOut("title", 1.0, 0.35);
    S.layer(`<g transform="translate(${T[0]} ${T[1]})">${pinSvg("pinLA", "LOS ANGELES", { stem: 96 })}</g>`, 0.95);
    const tp = D.W("s1", 5);
    S.pop("pinLA", tp, 0.4);
    S.key("pinLA_rp", "--s", tp, 0.3, 0); S.key("pinLA_rp", "--s", tp, 2.4, 0.9, "power2.out"); S.key("pinLA_rp", "opacity", tp, 1, 0); S.key("pinLA_rp", "opacity", tp, 0, 0.9, "power1.in");
    grade(S, "mono", { tint: "#7b98c4", ta: 0.14, dark: 0.04, vig: 0.7 });
  } });

/* ================= 2 · CARTOON RECONSTRUCTION + DATE CARD: the birth (no photograph of a newborn is used) ================= */
DK.flash(D.W("s1", 7), 0.85, 0.28);
D.shot({ id: "birth", a: W("s1", 7), b: W("s2", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("baby") }] }, cam: { from: [0, 0, 0.02], to: [20, -8, 0.13] },
  build(S) {
    const t0 = S.t0, t3 = D.W("s1", 9);
    S.layer(C.rays(1700, -40, 1.9, 1100, 0.3, "#9fb8ff", 0.34), 0.4);
    const baby = closeUp(S, "baby", BABY, 600, 580, 540, { depth: 0.9, seed: 4 });
    baby.face(t0, "neutral", 0); baby.look(t0, -8, -6, 0); baby.look(t0 + 0.6, 8, -6, 0.6, "sine.inOut"); baby.face(t0 + 1.4, "happy", 0.3); baby.turn(t0 + 0.1, -4, -3, 0.7); baby.turn(t0 + 1.2, 4, 3, 1.2);
    C.dust(S, { n: 16, seed: 12, box: [100, 150, 900, 800], color: "#d8e4ff", depth: 1.1, op: 0.5 });
    S.layer(FG.barsAt([50, 170]), 1.55);
    grade(S, "night");
    light(S, 600, 560, 520, 420, "#ffe2b0", 0.4);
    const txt = (id, x, y, sz, fill, str, ex) => S.layer(P(id, x, y, `<text font-family='${FONT}' font-weight="800" font-size="${sz}" fill="${fill}" letter-spacing="${ex || 3}" stroke="#05070c" stroke-width="6" paint-order="stroke">${str}</text>`), 1.0);
    txt("kick", 1010, 400, 30, "#ffb84a", "THE DAY YOU ARE BORN", 11);
    txt("dOct", 1010, 530, 112, "#fff", "OCTOBER", 4);
    txt("d21", 1610, 530, 112, "#ffb84a", "21", 4);
    txt("d80", 1010, 800, 250, "#fff", "1980", 6);
    S.layer(`<g transform="translate(1010 575)"><g data-p="ul"><rect width="760" height="6" fill="#ffb84a"/></g></g>`, 1.0);
    S.key("kick", "--sx", t0 + 0.1, 0, 0); S.key("kick", "--sx", t0 + 0.1, 1, 0.4, "power3.out");
    S.key("dOct", "--sx", t0, 0, 0); S.key("dOct", "--sx", t0, 1, 0.35, "power3.out");
    S.key("ul", "--sx", t0 + 0.1, 0, 0); S.key("ul", "--sx", t0 + 0.1, 1, 0.7, "power3.out");
    S.pop("d21", D.W("s1", 8), 0.3);
    const e80 = S.q("d80"); e80.style.visibility = "hidden"; S.key(e80, "--s", t3, 1.7, 0); S.show("d80", t3, true); S.key(e80, "--s", t3, 1, 0.16, "power3.out");
    DK.flash(t3, 0.35, 0.2);
    DK.hud(S, "h2", { from: 1970, to: 1980, t0: t0 + 0.05, t1: t0 + 1.25, marks: [{ y: 1980, label: "BORN" }] });
  } });

/* ================= 3 · CARTOON RECONSTRUCTION: the father (a lawyer) walks into his office; timeline jumps 1980 -> 1995 ================= */
D.shot({ id: "office", a: W("s2", 0), b: W("s2", 7), bg: B.office(), cam: { from: [-60, 6, 0.0], to: [40, -10, 0.18] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 340, Math.PI / 2, 800, 0.36, "#cfe0ff", 0.3), 0.45);
    S.layer(PR.desk(1180, 860, 520), 0.8);
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 5, depth: 0.55, drift: 80 });
    const dad = S.actor("dad", DAD, 520, 860, 1.22, { seed: 9, pivot: [520, 860] });
    dad.k("self", "--x", t0, -760, 0); dad.walk(t0 + 0.02, t1 - 0.12, 1000, { arms: false, step: 0.3 }); dad.face(t0, "neutral", 0);
    dad.arm("R", t0, -14, -4, 0.05); dad.arm("R", t1 - 0.2, -60, -50, 0.18);
    S.layer(PR.briefcase(0, 0), 0.9); const bc = S.q("pr"); S.key(bc, "--x", t0, -200, 0); S.key(bc, "--y", t0, 760, 0); S.key(bc, "--x", t0 + 0.02, 780, t1 - t0 - 0.14, "none");
    C.dust(S, { n: 18, seed: 31, box: [500, 200, 900, 560], color: "#fff4d0", depth: 1.0, op: 0.55 });
    S.layer(FG.desk(), 1.5); S.layer(FG.post(60), 1.6);
    grade(S, "office");
    light(S, 960, 720, 700, 420, "#ffd9a0", 0.28);
    DK.tag(S, "dadTag", "YOUR FATHER", "A LAWYER", 1180, 330, D.W("s2", 1) + 0.05);
    DK.hud(S, "h3", { from: 1980, to: 1995, t0: D.W("s2", 4) - 0.1, t1: t1 - 0.04, marks: [{ y: 1980, label: "BORN" }, { y: 1995, label: "TRIAL" }] });
  } });

/* ================= 4 · PHOTO-FRAME LAYOUT with camera movement: the 1995 trial (PLACEHOLDER slot P-02) ================= */
DK.whip(D.W("s2", 7), 1);
D.shot({ id: "trial", a: W("s2", 7), b: W("s3", 0), bg: { layers: [{ name: "far", depth: 0.25, svg: DK.boardFar(1995, 11) }] }, cam: { from: [-40, 8, 0.0], to: [50, -8, 0.1], ease: "power1.inOut" },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(`<g transform="translate(300 560) rotate(8)" opacity=".5">${DK.photoSvg("sideL", { w: 420, h: 270, slot: "P-02b", cap: "", bare: true })}</g>`, 0.6);
    S.layer(`<g transform="translate(1680 600) rotate(-7)" opacity=".5">${DK.photoSvg("sideR", { w: 420, h: 270, slot: "P-02c", cap: "", bare: true })}</g>`, 0.7);
    S.layer(DK.boardNear(5), 1.35);
    S.layer(`<g transform="translate(1090 560) rotate(-3.5)">${DK.photoSvg("frame", { w: 620, h: 350, slot: "P-02", cap: "The trial, 1995" })}</g>`, 1.0);
    S.key("frame", "--s", t0, 0.9, 0); S.key("frame", "--s", t0, 1.0, 0.4, "power3.out"); S.key("frame", "--s", t0 + 0.4, 1.1, t1 - t0 - 0.4, "power1.inOut");
    S.key("frame", "--r", t0, 0, 0); S.key("frame", "--r", t0, 1.2, t1 - t0, "power1.inOut");
    S.key("frame_sheen", "--x", t0 + 0.35, 0, 0); S.key("frame_sheen", "--x", t0 + 0.35, 1400, 0.9, "power1.inOut");
    C.dust(S, { n: 22, seed: 61, box: [100, 100, 1700, 800], color: "#dbe6ff", depth: 1.2, op: 0.5 });
    grade(S, "mono", { tint: "#6c84b4", ta: 0.2, dark: 0.12, vig: 0.78 });
    light(S, 1090, 540, 700, 380, "#cfe0ff", 0.22);
    DK.tag(S, "trialTag", "1995 · THE TRIAL", "O. J. SIMPSON DEFENSE", 140, 770, D.W("s2", 9));
    const st1 = D.W("s2", 10), stamp = `<g transform="rotate(-9)"><rect x="-205" y="-40" width="410" height="80" rx="9" fill="none" stroke="#d63a3a" stroke-width="8"/><text y="20" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="50" fill="#d63a3a" letter-spacing="4">DEFENSE TEAM</text></g>`;
    S.layer(P("stamp", 1500, 745, stamp), 1.0);
    const sp = S.q("stamp"); sp.style.visibility = "hidden"; S.key(sp, "--s", st1, 2.4, 0); S.show("stamp", st1, true); S.key(sp, "--s", st1, 1, 0.13, "power3.out");
    DK.hud(S, "h4", { from: 1995, to: 1995, t0: t0, t1: t1, marks: [{ y: 1995, label: "TRIAL" }] });
  } });

/* ================= 5 · CARTOON RECONSTRUCTION: age nine, the parents part (rewind transition 1995 -> 1989) ================= */
D.vhs(D.W("s3", 0), null, { strength: 0.5, pre: 0.05, post: 0.2, bars: 3 });
DK.flash(D.W("s3", 0), 0.55, 0.3);
D.shot({ id: "divorce", a: W("s3", 0), b: E("s3", 6), bg: B.home(), cam: { from: [0, 0, 0.0], to: [0, 14, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 420, Math.PI / 2, 700, 0.3, "#ffe0a8", 0.3), 0.4);
    C.fog(S, { y: 700, h: 200, color: "#ffc88a", op: 0.2, seed: 14, depth: 0.55, drift: 70 });
    const dadc = S.actor("dadL", DAD, 640, 790, 0.82, { seed: 21, idle: false, pivot: [640, 790], depth: 0.6 }), mom = S.actor("momR", MOM, 1280, 790, 0.82, { seed: 22, idle: false, pivot: [1280, 790], depth: 0.6 });
    S.layer(K.P("suit", 0, 0, PR.suitcase(0, 0)), 0.6); S.key("suit", "--x", t0, 700, 0); S.key("suit", "--y", t0, 790, 0);
    const kid = S.actor("kid", KID, 960, 1040, 1.6, { seed: 5, expr: "worried", depth: 1.0 });
    dadc.face(t0, "sad", 0); mom.face(t0, "sad", 0);
    const tp = D.W("s3", 4);
    dadc.turn(tp, 10, 3, 0.3); dadc.walk(tp + 0.35, t1 - 0.02, -620, { arms: false }); S.key("suit", "--x", tp + 0.35, 700 - 620, t1 - tp - 0.37, "none");
    mom.turn(tp + 0.15, -10, -3, 0.3); mom.walk(tp + 0.5, t1 - 0.02, 640);
    [dadc, mom].forEach((a) => { a.k("self", "--s", tp + 0.35, 1, 0); a.k("self", "--s", tp + 0.35, 0.7, t1 - tp - 0.37, "none"); });
    kid.turn(t0 + 0.4, 10, 5, 0.4); kid.look(t0 + 0.4, -11, 0, 0.3); kid.turn(tp, -12, -6, 0.4); kid.look(tp, 11, 0, 0.3); kid.face(tp + 0.2, "sad", 0.4);
    kid.arm("L", tp, 28, 10, 0.4); kid.arm("R", tp + 0.3, -28, -10, 0.4);
    S.layer(`<g data-p="dim"><rect width="1920" height="1080" fill="#101830" opacity="0"/></g>`, 0); const dm = S.q("dim").firstElementChild; S.key(dm, "opacity", tp, 0, 0); S.key(dm, "opacity", tp, 0.3, t1 - tp, "sine.inOut");
    S.layer(FG.couch(), 1.5); S.layer(FG.post(1860), 1.6);
    grade(S, "home");
    light(S, 960, 800, 520, 420, "#ffc88a", 0.35);
    DK.tag(S, "ageTag", "AGE 9 · 1989", "YOUR PARENTS DIVORCE", 120, 330, D.W("s3", 3), { w: 680 });
    DK.hud(S, "h5", { from: 1995, to: 1989, t0: t0 + 0.12, t1: D.W("s3", 4) - 0.02, marks: [{ y: 1995, label: "TRIAL" }, { y: 1989, label: "AGE 9" }] });
  } });

/* ================= 6 · CARTOON RECONSTRUCTION: close-up of the child ================= */
D.shot({ id: "kidCry", a: E("s3", 6), b: W("s4", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kid") }] }, cam: { from: [0, 0, 0.02], to: [-8, 6, 0.16] },
  build(S) {
    const t0 = S.t0;
    const kid = closeUp(S, "kidc", KID, 960, 540, 600, { depth: 0.9, seed: 6 });
    kid.face(t0, "sad", 0); kid.look(t0, 0, 6, 0); kid.face(t0 + 0.3, "cry", 0.4); kid.nod(t0 + 0.4, 12, 0.5);
    C.dust(S, { n: 12, seed: 41, box: [200, 100, 1500, 800], color: "#ffd9a0", depth: 1.1, op: 0.4 });
    S.layer(FG.curtain("L"), 1.6);
    grade(S, "home", { dark: 0.2, vig: 0.8 });
    light(S, 960, 500, 520, 420, "#ffc88a", 0.38);
    DK.hud(S, "h6", { from: 1989, to: 1989, t0: t0, t1: S.t1, marks: [{ y: 1989, label: "AGE 9" }] });
  } });

/* ================= 7 · CARTOON RECONSTRUCTION: the 1991 wedding; timeline +2 years ================= */
DK.whip(D.W("s4", 0), -1);
D.shot({ id: "wedding", a: W("s4", 0), b: W("s4", 6), bg: B.garden(), cam: { from: [30, 0, 0.0], to: [-20, -8, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(1500, -40, 1.95, 1300, 0.3, "#fff0c0", 0.3), 0.35);
    C.fog(S, { y: 640, h: 200, color: "#fff1d0", op: 0.3, seed: 15, depth: 0.5, drift: 80 });
    const mom = S.actor("mom", MOMW, 900, 640, 0.62, { seed: 31, depth: 0.6, pivot: [900, 640] }), br = S.actor("bruce", BRUCEW, 1030, 640, 0.64, { seed: 32, depth: 0.6, pivot: [1030, 640] });
    const tw = D.W("s4", 4);
    mom.face(tw, "happy", 0.3); br.face(tw, "happy", 0.3); mom.arm("R", tw + 0.1, 34, 40, 0.3); br.arm("L", tw + 0.1, -34, -40, 0.3);
    [mom, br].forEach((a) => { a.k("self", "--s", t0, 1, 0); a.k("self", "--s", t0, 1.55, t1 - t0, "power1.inOut"); a.k("self", "--y", t0, 0, 0); a.k("self", "--y", t0, 150, t1 - t0, "power1.inOut"); });
    const kid = S.actor("kid2", KID, 1560, 1040, 1.35, { seed: 33, expr: "surprised", depth: 1.0 });
    kid.look(t0, -9, -6, 0); kid.turn(t0 + 0.2, -10, -4, 0.4); kid.face(tw, "happy", 0.4); kid.arm("L", tw, -40, -60, 0.4);
    S.layer(PR.heart("hrt", 960, 330), 1.1); S.pop("hrt", tw + 0.1, 0.5); S.key("hrt", "--y", tw + 0.5, -40, 0.9, "sine.out");
    confetti(S, tw, 20, 4);
    S.layer(FG.leaves("L"), 1.7);
    grade(S, "garden");
    light(S, 960, 640, 600, 380, "#fff0c0", 0.3);
    DK.tag(S, "wedTag", "1991 · THE WEDDING", "TWO YEARS LATER", 120, 330, D.W("s4", 2) - 0.1, { w: 700 });
    DK.hud(S, "h7", { from: 1989, to: 1991, t0: D.W("s4", 0) + 0.1, t1: D.W("s4", 3) - 0.05, marks: [{ y: 1989, label: "AGE 9" }, { y: 1991, label: "WEDDING" }], label: "+2 YEARS" });
  } });

/* ================= 8 · MAP: Los Angeles -> Montreal 1976, then a photo-frame slides in (PLACEHOLDER slot P-04) ================= */
DK.flash(D.W("s4", 6), 0.7, 0.26);
D.shot({ id: "map2", a: W("s4", 6), b: "end", cam: { from: [0, 0, 0], to: [0, 0, 0.04] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, TM = [610, 520], FR = [1300, 560];
    const ctl = [(LAp[0] + MTp[0]) / 2, Math.min(LAp[1], MTp[1]) - 200], bz = (u) => [(1 - u) * (1 - u) * LAp[0] + 2 * u * (1 - u) * ctl[0] + u * u * MTp[0], (1 - u) * (1 - u) * LAp[1] + 2 * u * (1 - u) * ctl[1] + u * u * MTp[1]];
    let len = 0, pv = bz(0); for (let i = 1; i <= 40; i++) { const q = bz(i / 40); len += Math.hypot(q[0] - pv[0], q[1] - pv[1]); pv = q; }
    const route = `<path data-p="route" d="M${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)}Q${ctl[0].toFixed(1)} ${ctl[1].toFixed(1)} ${MTp[0].toFixed(1)} ${MTp[1].toFixed(1)}" fill="none" stroke="#ffb84a" stroke-width="5" stroke-linecap="round" stroke-dasharray="${len.toFixed(0)}" stroke-dashoffset="${len.toFixed(0)}"/>
      <path d="M${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)}Q${ctl[0].toFixed(1)} ${ctl[1].toFixed(1)} ${MTp[0].toFixed(1)} ${MTp[1].toFixed(1)}" fill="none" stroke="#ffb84a" stroke-width="2" stroke-dasharray="3 14" opacity=".45"/>
      <g transform="translate(${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)})"><g data-p="head"><circle r="22" fill="#ffb84a" opacity=".28"/><circle r="9" fill="#fff" stroke="#ffb84a" stroke-width="4"/></g></g>
      <g transform="translate(${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)}) scale(.9)">${pinSvg("pinLA2", "LOS ANGELES", { stem: 84 })}</g>`;
    S.layer(`<g data-p="mz2">${DK.mapSvg()}${cityDots()}${route}</g>`, 0.45);
    mapGo(S, "mz2", t0, 0, 0.98, [960, 500], [960, 500]);
    const tr0 = t0 + 0.12, tr1 = t0 + 0.95;
    dashIn(S.q("route"), len.toFixed(0), tr0, tr1 - tr0, "power1.inOut");
    const hd = S.q("head"); S.key(hd, "--x", t0, 0, 0); S.key(hd, "--y", t0, 0, 0);
    for (let i = 1; i <= 14; i++) { const u = i / 14, p0 = bz((i - 1) / 14), p1 = bz(u), ta = tr0 + (tr1 - tr0) * EASEF["power2.inOut"]((i - 1) / 14) * 0 + (tr1 - tr0) * ((i - 1) / 14), tb = tr0 + (tr1 - tr0) * u; void p0; S.key(hd, "--x", ta, p1[0] - LAp[0], tb - ta, "none"); S.key(hd, "--y", ta, p1[1] - LAp[1], tb - ta, "none"); }
    S.fadeOut("head", tr1 + 0.02, 0.2);
    mapGo(S, "mz2", t0 + 0.7, 0.75, 2.2, MTp, TM, "power2.inOut");
    S.layer(`<g transform="translate(${TM[0]} ${TM[1]})">${pinSvg("pinMTL", "MONTREAL · 1976", { stem: 96 })}</g>`, 0.95);
    const tpin = t0 + 1.45; S.pop("pinMTL", tpin, 0.4);
    S.key("pinMTL_rp", "--s", tpin, 0.3, 0); S.key("pinMTL_rp", "--s", tpin, 2.4, 0.9, "power2.out"); S.key("pinMTL_rp", "opacity", tpin, 1, 0); S.key("pinMTL_rp", "opacity", tpin, 0, 0.9, "power1.in");
    const tf = D.W("s4", 8);
    S.layer(`<g transform="translate(${FR[0]} ${FR[1]})"><g data-p="slide"><g transform="rotate(-2.5)">${DK.photoSvg("frame2", { w: 620, h: 360, slot: "P-04", cap: "Montreal 1976" })}</g></g></g>`, 1.0);
    S.key("slide", "--x", S.t0, 1100, 0); S.key("slide", "--x", tf - 0.05, 1100, 0); S.key("slide", "--x", tf - 0.05, 0, 0.55, "power3.out");
    S.key("slide", "--r", tf - 0.05, 9, 0); S.key("slide", "--r", tf - 0.05, 0, 0.55, "power3.out");
    S.key("slide", "--s", tf + 0.5, 1, 0); S.key("slide", "--s", tf + 0.5, 1.07, t1 - tf - 0.5, "power1.inOut");
    S.key("frame2_sheen", "--x", tf + 0.4, 0, 0); S.key("frame2_sheen", "--x", tf + 0.4, 1300, 0.7, "power1.inOut");
    DK.tag(S, "brTag", "BRUCE JENNER", "OLYMPIC CHAMPION", 140, 770, D.W("s4", 9) - 0.02);
    grade(S, "mono", { tint: "#7b98c4", ta: 0.14, dark: 0.06, vig: 0.72 });
    DK.hud(S, "h8", { from: 1991, to: 1976, t0: t0 + 0.05, t1: t0 + 1.0, marks: [{ y: 1991, label: "WEDDING" }, { y: 1976, label: "OLYMPICS" }] });
  } });

DK.flush(D);
