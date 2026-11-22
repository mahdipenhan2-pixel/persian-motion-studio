/* Kim Kardashian documentary, 6 minutes (project kim-docu-6min): 70 % cinematic cartoon (style A) + 30 % documentary graphics (style B).
   Self-contained: the documentary helpers (DK) live at the top of this file; NO shared engine/kit file is changed by it and the
   approved versions (kim-test30, kim-test30-cine, kim-docu-style, kim-docu-style-full) are untouched.
   Three chapters share this file; each chapter only builds the shots whose sentences it contains (has()).
   PHOTOS: none is embedded. Historic moments are CARTOON RECONSTRUCTIONS (badge on screen) or documentary graphics
   (cards, timeline, map); real photographs are only ever added through photo_slots.json after a licence check (ASSET_LICENSES.md). */

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
  DK.pend.hud.push([o.t0 !== undefined ? o.t0 : S.t0, o.t1 !== undefined ? o.t1 : S.t1]);
  const PX = 46, y = o.y || 150, lo = Math.floor(Math.min(o.from, o.to)) - 4, hi = Math.ceil(Math.max(o.from, o.to)) + 4, mk = uid("hm");
  let tk = "", yrs = "";
  for (let k = lo; k <= hi; k++) {
    const major = k % 5 === 0;
    tk += `<path d="M${k * PX} ${major ? -15 : -8}V${major ? 15 : 8}" stroke="#fff" stroke-width="${major ? 3 : 2}" opacity="${major ? 0.9 : 0.45}"/>`;
    if (major) tk += `<text x="${k * PX}" y="46" text-anchor="middle" font-family='${FONT}' font-size="28" font-weight="700" fill="#e6edf8" opacity=".95">${k}</text>`;
  }
  let row2 = false, prev = null, prevRow = 0;   /* mark labels 23 px; staggered onto a second row when two would touch */
  (o.marks || []).slice().sort((a, b) => a.y - b.y).forEach((m) => { let row = 0; if (prev && prevRow === 0 && (m.y - prev.y) * PX < (m.label.length + prev.label.length) / 2 * 17 + 16) row = 1; if (row) row2 = true; prevRow = row; prev = m;
    tk += `<circle cx="${m.y * PX}" cy="0" r="7" fill="#ffb84a" stroke="#1a1208" stroke-width="2"/><text x="${m.y * PX}" y="${88 + row * 30}" text-anchor="middle" font-family='${FONT}' font-size="23" font-weight="800" fill="#ffb84a" stroke="#05070c" stroke-width="4" paint-order="stroke" letter-spacing="2">${m.label}</text>`; });
  const panelH = row2 ? 176 : 148;
  const yMin = Math.min(o.from, o.to), yMax = Math.max(o.from, o.to);
  for (let k = Math.floor(yMin); k <= Math.ceil(yMax); k++) yrs += `<text data-p="${id}_y${k}" x="960" y="86" text-anchor="middle" font-family='${FONT}' font-size="84" font-weight="800" fill="#fff" stroke="#0a0d14" stroke-width="5" paint-order="stroke" letter-spacing="3" style="visibility:hidden">${k}</text>`;
  S.layer(`<defs><linearGradient id="${mk}g" x1="0" x2="1"><stop offset="0" stop-color="#000"/><stop offset=".18" stop-color="#fff"/><stop offset=".82" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
      <mask id="${mk}" maskUnits="userSpaceOnUse" x="240" y="${y - 70}" width="1440" height="260"><rect x="240" y="${y - 70}" width="1440" height="260" fill="url(#${mk}g)"/></mask></defs>
    <g data-p="${id}"><rect x="260" y="${y - 52}" width="1400" height="${panelH}" rx="14" fill="#05070c" opacity=".62" stroke="#fff" stroke-opacity=".16" stroke-width="2"/>
    <g mask="url(#${mk})"><g transform="translate(960 ${y})"><g data-p="${id}_r">${tk}</g></g></g>
    <path d="M960 ${y - 52}V${y - 52 + panelH}" stroke="#ffb84a" stroke-width="4"/><path d="M944 ${y - 52}H976L960 ${y - 34}Z" fill="#ffb84a"/>${yrs}</g>`, 0);
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
  if (o.label) { S.layer(`<text data-p="${id}_lab" x="960" y="${y - 52 + panelH + 34}" text-anchor="middle" font-family='${FONT}' font-size="27" font-weight="800" letter-spacing="5" fill="#ffb84a" stroke="#0a0d14" stroke-width="4" paint-order="stroke">${o.label}</text>`, 0); S.fadeIn(id + "_lab", o.t0 + 0.2, 0.3); }
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
/* zones the floating papers must never cover: HUD panel, text block, source line, subtitles, chart icon */
const NOPAPER = [[250, 80, 1670, 270], [40, 300, 1290, 930], [140, 860, 1780, 1040], [1380, 330, 1900, 830]];
DK.boardNear = (seed) => {
  /* scattered papers; a position is re-drawn until it clears every NOPAPER zone */
  const r = rng(seed); let m = "";
  for (let i = 0; i < 7; i++) {
    let x, y, w, h, a, n = 0;
    do { x = Math.round(r() * 1920); y = Math.round(r() * 1080); w = 150 + Math.round(r() * 170); h = 100 + Math.round(r() * 140); a = Math.round((r() - 0.5) * 50); n++; }
    while (n < 80 && NOPAPER.some(([x0, y0, x1, y1]) => x + w * 0.75 > x0 && x - w * 0.75 < x1 && y + h * 0.75 > y0 && y - h * 0.75 < y1));
    if (n >= 80) continue;   // no free spot for this sheet: it is simply left out
    m += `<g transform="translate(${x} ${y}) rotate(${a})"><rect x="${-w / 2 + 8}" y="${-h / 2 + 12}" width="${w}" height="${h}" fill="#000" opacity=".35"/><rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${["#d9d1bf", "#c3cbd8", "#e8dcc0"][i % 3]}" opacity=".55"/><path d="M${-w / 2 + 14} ${-h / 2 + 22}H${w / 2 - 14}M${-w / 2 + 14} ${-h / 2 + 40}H${w / 2 - 50}" stroke="#444" stroke-width="3" opacity=".35"/></g>`;
  }
  return m;
};

/* ---------- transitions: flash, whip pan, fade from/to black. Registered during the build, applied in time order ---------- */
DK.pend = { flash: [], whip: [], hud: [] };
DK.flash = (t, peak, dur) => DK.pend.flash.push([t, peak === undefined ? 0.9 : peak, dur || 0.22]);
DK.whip = (tCut, dir) => DK.pend.whip.push([tCut, dir || 1]);
DK.flush = (D_) => {
  window.__docuCues = { flash: DK.pend.flash.slice(), whip: DK.pend.whip.slice(), hud: DK.pend.hud.slice(), shots: D_.shots.map((q) => [q.id, q.t0, q.t1]) };   // read by the offline sound-design step
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


/* ===================================================================================================== */
/* library: characters, text, badge, counter, documentary cards                                           */
/* ===================================================================================================== */
const has = (sid) => D.DATA.sentences.some((s) => s.id === sid);
const nW = (sid) => D.DATA.sentences.find((s) => s.id === sid).words.length;
const SN = (t) => Math.round(t * 30) / 30;
const KIM07 = Object.assign({}, KIM, { build: "woman", hair: "long_straight", outfit: "tee2007", top: "#24242c", pants: "#3b5a8a", shoe: "#2b2230", earrings: 1, sleeve: "short", lip: "#b8626a" });
const KIM25 = Object.assign({}, KIM, { build: "woman", hair: "long_straight", outfit: "dress", top: "#b89b86", legs: "bare", shoe: "#c9a58a", shoeType: "pump", sleeve: "none", earrings: 1, lip: "#c4666b" });
const KIM00 = Object.assign({}, KIM07, { top: "#d9c7a8", pants: "#2e3a5a" });
const KIMT = Object.assign({}, KIM, { build: "teen", hair: "teen_long", outfit: "tee2007", top: "#c9c3d6", pants: "#46557f", shoe: "#f2efe8", sleeve: "short" });
const CREW = { build: "man", skin: "#c98f6a", hair: "short_man", hairColor: "#1f1512", top: "#35353f", pants: "#22222a", outfit: "track", accent: "#6a6a78" };
const SIS1 = { build: "child", skin: "#dba27d", hair: "bob", hairColor: "#2a1a14", outfit: "kidtee", top: "#e4a13a", pants: "#3b4a8c", shoe: "#2b2230", accent: "#4c8a5a" };
const SIS2 = { build: "child", skin: "#e0ac88", hair: "teen_long", hairColor: "#7a5434", outfit: "kidtee", top: "#8fc3a4", pants: "#6a7ec2", shoe: "#f2efe8", accent: "#c4666b" };
const BRO = { build: "child", skin: "#dba27d", hair: "short_man", hairColor: "#2a1a14", outfit: "kidtee", top: "#4c8a5a", pants: "#2e3a5a", shoe: "#f2efe8", accent: "#e4483f" };
const SISA = Object.assign({}, SIS1, { build: "woman", hair: "bob", outfit: "dress", top: "#9a6a8c", legs: "bare", shoe: "#c9a58a", shoeType: "pump", sleeve: "none", lip: "#b23a4a" });
const SISB = Object.assign({}, SIS2, { build: "woman", hair: "wavy_long", outfit: "dress", top: "#6a8a9c", legs: "bare", shoe: "#d9c9b0", shoeType: "pump", sleeve: "none", lip: "#c4666b" });
const KRIS = Object.assign({}, MOM, { top: "#3a3a4a", outfit: "blazer" });

/* text helper: animated (wipe from the left / fade), stroked for readability on any background */
const TX = (S, id, x, y, size, fill, str, o) => {
  o = o || {};
  S.layer(P(id, x, y, `<text text-anchor="${o.anchor || "start"}" font-family='${FONT}' font-weight="${o.w || 800}" font-size="${size}" fill="${fill}" letter-spacing="${o.ls === undefined ? 3 : o.ls}" stroke="#05070c" stroke-width="${o.sw === undefined ? 6 : o.sw}" paint-order="stroke">${str}</text>`), o.depth === undefined ? 1.0 : o.depth);
  return id;
};
const appear = (S, id, t, dur, wipe) => { S.fadeIn(id, t, dur || 0.3); if (wipe) { S.key(id, "--sx", t, 0, 0); S.key(id, "--sx", t, 1, (dur || 0.3) + 0.15, "power3.out"); } };

/* small on-screen badge that tells the viewer what kind of picture this is */
const badge = (S, text, t) => {
  const id = uid("bdg");
  S.layer(P(id, 64, 62, `<rect x="0" y="-24" width="${text.length * 14 + 58}" height="42" rx="21" fill="#05070c" opacity=".66" stroke="#fff" stroke-opacity=".25" stroke-width="2"/><circle cx="24" cy="-3" r="6" fill="#ffb84a"/><text x="42" y="4" font-family='${FONT}' font-weight="700" font-size="19" letter-spacing="4" fill="#e8eef9">${text}</text>`), 0);
  S.fadeIn(id, t === undefined ? S.t0 + 0.3 : t, 0.3);
};
const RECON = "CARTOON RECONSTRUCTION", GRAPHIC = "DOCUMENTARY GRAPHIC", MAPB = "ANIMATED MAP";

/* rolling counter (text swaps, fully deterministic): vals are strings, last one stays */
const counter = (S, id, x, y, size, fill, vals, t0, t1, o) => {
  o = o || {};
  S.layer(vals.map((v, i) => `<g data-p="${id}${i}" style="visibility:hidden"><g transform="translate(${x} ${y})"><text text-anchor="${o.anchor || "middle"}" font-family='${FONT}' font-weight="800" font-size="${size}" fill="${fill}" stroke="#05070c" stroke-width="${o.sw || 8}" paint-order="stroke" letter-spacing="${o.ls || 2}">${v}</text></g></g>`).join(""), o.depth || 1.0);
  const f = EASEF["power2.out"];
  vals.forEach((v, i) => { const t = SN(t0 + (t1 - t0) * f(i / Math.max(1, vals.length - 1))); S.show(id + i, t, true); if (i < vals.length - 1) S.hideAt(id + i, SN(t0 + (t1 - t0) * f((i + 1) / (vals.length - 1)))); });
};
const range = (a, b, n) => Array.from({ length: n }, (_, i) => Math.round(a + (b - a) * i / (n - 1)));

/* ---------- icons for the documentary cards (centre cx, cy). All pure SVG in our own style ---------- */
const O = (w) => st(w || 7);
const ic = {};
ic.news = (S, cx, cy, t) => {
  const tv = (i) => { const c = i % 3, r = (i / 3) | 0, x = (c - 1) * 290, y = (r - 0.5) * 236, hue = ["#2a4a7a", "#6a3a5a", "#2a6a5a", "#7a5a2a", "#3a3a7a", "#5a2a2a"][i];
    return `<g data-p="tv${i}"><g transform="translate(${x} ${y})"><rect x="-122" y="-84" width="244" height="168" rx="14" fill="#10141f" ${O(7)}/><rect x="-106" y="-68" width="212" height="136" rx="6" fill="${hue}"/>
      <rect x="-106" y="-68" width="212" height="136" fill="url(#scan)" opacity=".5"/><rect x="-106" y="30" width="212" height="38" fill="#c4252d"/><text y="57" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="24" fill="#fff" letter-spacing="5">BREAKING</text>
      <circle cx="-30" cy="-12" r="22" fill="#e8dccb" opacity=".8"/><path d="M-70 26Q-30 -26 10 26Z" fill="#e8dccb" opacity=".6"/></g></g>`; };
  S.layer(P("icn", cx, cy, [0, 1, 2, 3, 4, 5].map(tv).join("")), 1.0);
  for (let i = 0; i < 6; i++) S.pop("tv" + i, t + i * 0.14, 0.35);
};
ic.case = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="fold"><path d="M-250 -190H-60L-30 -224H250V230H-250Z" fill="#c9a86a" ${O(8)}/><rect x="-226" y="-170" width="476" height="380" fill="#efe5c8" ${O(6)}/>
    <text x="-190" y="-98" font-family='${FONT}' font-weight="800" font-size="52" fill="#2a1820" letter-spacing="6">CASE FILE</text><path d="M-190 -64H210M-190 -20H210M-190 24H110M-190 68H190M-190 112H70" stroke="#2a1820" stroke-width="5" opacity=".5"/>
    <g transform="translate(120 150) rotate(-10)"><rect x="-130" y="-34" width="260" height="68" rx="8" fill="none" stroke="#c4252d" stroke-width="7"/><text y="18" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#c4252d" letter-spacing="4">JUNE 1994</text></g></g>`), 1.0);
  S.pop("fold", t, 0.45);
};
ic.roster = (S, cx, cy, t, names, times) => {
  const rows = names.map((n, i) => `<g data-p="pl${i}"><g transform="translate(0 ${(i - (names.length - 1) / 2) * 118})"><rect x="-340" y="-46" width="680" height="92" rx="10" fill="#f3eee2" ${O(6)}/><rect x="-340" y="-46" width="16" height="92" fill="${n[2] || "#ffb84a"}"/>
    <text x="-296" y="${n[1] ? -4 : 14}" font-family='${FONT}' font-weight="800" font-size="40" fill="#2a1820" letter-spacing="3">${n[0]}</text>${n[1] ? `<text x="-296" y="32" font-family='${FONT}' font-weight="700" font-size="22" fill="#7a5a2a" letter-spacing="4">${n[1]}</text>` : ""}</g></g>`).join("");
  S.layer(P("icn", cx, cy, rows), 1.0);
  names.forEach((n, i) => { const ti = times ? times[i] : t + i * 0.35, e = S.q("pl" + i); e.style.opacity = "0"; S.key(e, "opacity", ti, 0, 0); S.key(e, "opacity", ti, 1, 0.25, "power1.out"); S.key(e, "--x", ti, 120, 0); S.key(e, "--x", ti, 0, 0.4, "power3.out"); });
};
ic.clock = (S, cx, cy, t, t1) => {
  let ticks = ""; for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; ticks += `<path d="M${(Math.sin(a) * 188).toFixed(1)} ${(-Math.cos(a) * 188).toFixed(1)}L${(Math.sin(a) * 212).toFixed(1)} ${(-Math.cos(a) * 212).toFixed(1)}" stroke="#2a1820" stroke-width="${i % 3 ? 6 : 10}" stroke-linecap="round"/>`; }
  const arc = (deg) => { const a = deg * Math.PI / 180; return `M0 0L0 -170A170 170 0 ${deg > 180 ? 1 : 0} 1 ${(Math.sin(a) * 170).toFixed(1)} ${(-Math.cos(a) * 170).toFixed(1)}Z`; };
  S.layer(P("icn", cx, cy, `<circle r="240" fill="#f3eee2" ${O(10)}/>${ticks}<path d="${arc(115)}" fill="#ffb84a" opacity=".55"/><g data-p="hand"><path d="M0 0L0 -176" stroke="#c4252d" stroke-width="10" stroke-linecap="round"/><circle r="14" fill="#2a1820"/></g>
    <text y="108" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="30" fill="#2a1820" letter-spacing="4">UNDER 4 HOURS</text>`), 1.0);
  S.pop("icn", t, 0.4); S.key("hand", "--r", t, 0, 0); S.key("hand", "--r", t + 0.2, 115, Math.max(0.5, t1 - t - 0.5), "power2.inOut");
};
ic.stamp = (S, cx, cy, t, big, small, col) => {
  S.layer(P("icn", cx, cy, `<g data-p="stp"><g transform="rotate(-8)"><rect x="-330" y="-120" width="660" height="240" rx="16" fill="#f3eee2" opacity=".95" ${O(8)}/><rect x="-306" y="-96" width="612" height="192" rx="10" fill="none" stroke="${col || "#c4252d"}" stroke-width="10"/><text y="22" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="${big.length > 9 ? 88 : 110}" fill="${col || "#c4252d"}" letter-spacing="6">${big}</text><text y="74" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="30" fill="#2a1820" letter-spacing="8">${small}</text></g></g>`), 1.0);
  const e = S.q("stp"); e.style.visibility = "hidden"; S.key(e, "--s", t, 2.6, 0); S.show("stp", t, true); S.key(e, "--s", t, 1, 0.14, "power3.out"); DK.flash(t, 0.3, 0.2);
};
ic.cap = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="cap"><path d="M0 -150L230 -50L0 50L-230 -50Z" fill="#23232e" ${O(8)}/><path d="M-130 -2V96Q0 150 130 96V-2L0 50Z" fill="#2e2e3c" ${O(8)}/><path d="M200 -38V90" stroke="#f3c64a" stroke-width="8"/><circle cx="200" cy="100" r="16" fill="#f3c64a" ${O(5)}/><text y="212" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#fff" stroke="#05070c" stroke-width="6" paint-order="stroke" letter-spacing="6">HIGH SCHOOL</text></g>`), 1.0);
  S.pop("cap", t, 0.5); S.key("cap", "--r", t + 0.5, -6, 0.9, "sine.inOut"); S.key("cap", "--r", t + 1.4, 4, 1.1, "sine.inOut");
};
ic.rings = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="r1"><circle cx="-62" r="100" fill="none" stroke="#f3c64a" stroke-width="22"/><circle cx="-62" r="100" fill="none" stroke="#2a1820" stroke-width="4" transform="scale(1.11)"/></g><g data-p="r2"><circle cx="62" r="100" fill="none" stroke="#e8e2d6" stroke-width="22"/><circle cx="62" r="100" fill="none" stroke="#2a1820" stroke-width="4" transform="scale(1.11)"/></g>`), 1.0);
  S.key("r1", "--x", t, -260, 0); S.key("r2", "--x", t, 260, 0); S.key("r1", "--x", t, 0, 0.7, "power3.out"); S.key("r2", "--x", t, 0, 0.7, "power3.out");
};
ic.tvshow = (S, cx, cy, t, t1) => {
  S.layer(P("icn", cx, cy, `<rect x="-300" y="-230" width="600" height="400" rx="34" fill="#2a2018" ${O(10)}/><rect x="-262" y="-194" width="524" height="328" rx="12" fill="#1a1230"/><rect x="-262" y="-194" width="524" height="328" fill="url(#scan)" opacity=".4"/>
    <g data-p="scr"><text y="-84" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="30" fill="#fff" letter-spacing="5">KEEPING UP WITH</text><text y="-26" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#ffb84a" letter-spacing="1">THE KARDASHIANS</text>
    <rect x="-90" y="26" width="180" height="56" rx="8" fill="none" stroke="#fff" stroke-width="4"/><text y="68" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#fff" letter-spacing="6">E! · OCT 2007</text></g>
    <path d="M-120 170L-170 250H170L120 170" fill="#2a2018" ${O(8)}/>`), 1.0);
  S.pop("icn", t, 0.45); S.fadeIn("scr", t + 0.4, 0.5);
};
ic.phone = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<rect x="-170" y="-290" width="340" height="580" rx="44" fill="#14141c" ${O(10)}/><rect x="-146" y="-254" width="292" height="508" rx="18" fill="#3a2a5a"/><rect x="-146" y="-254" width="292" height="508" rx="18" fill="url(#scan)" opacity=".25"/>
    <circle cx="0" cy="-90" r="74" fill="#d99a73" ${O(5)}/><path d="M-74 -100C-74 -190 74 -190 74 -100C60 -140 -60 -140 -74 -100Z" fill="#16100f" ${O(5)}/><path d="M-50 -140L-80 -40" stroke="#16100f" stroke-width="22" stroke-linecap="round"/>
    <text y="60" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="31" fill="#fff" letter-spacing="2">KIM KARDASHIAN:</text><text y="102" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#ffb84a" letter-spacing="4">HOLLYWOOD</text>
    <rect x="-125" y="160" width="250" height="58" rx="29" fill="#ffb84a" ${O(5)}/><text y="200" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="27" fill="#2a1820" letter-spacing="3">MOBILE GAME</text>`), 1.0);
  S.pop("icn", t, 0.45); S.key("icn", "--r", t + 0.5, -3, 1.0, "sine.inOut"); S.key("icn", "--r", t + 1.5, 3, 1.2, "sine.inOut");
};
ic.beauty = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="lip"><g transform="translate(-170 40) rotate(-12)"><rect x="-36" y="-60" width="72" height="150" rx="8" fill="#23232e" ${O(7)}/><rect x="-30" y="-130" width="60" height="76" rx="8" fill="#c4252d" ${O(7)}/><path d="M-30 -130L30 -160V-130Z" fill="#a01a22" ${O(5)}/></g></g>
    <g data-p="cmp"><g transform="translate(70 40)"><circle r="130" fill="#e8d9c2" ${O(8)}/><circle r="92" fill="#c98a6a" ${O(6)}/><path d="M-60 -20Q0 -80 60 -20" fill="none" stroke="#fff" stroke-width="8" opacity=".5"/></g></g>
    <g data-p="brs"><g transform="translate(250 10) rotate(24)"><rect x="-10" y="-30" width="20" height="170" rx="8" fill="#2a1820" ${O(5)}/><path d="M-30 -30Q0 -140 30 -30Z" fill="#f0c9a8" ${O(6)}/></g></g>`), 1.0);
  ["lip", "cmp", "brs"].forEach((n, i) => S.pop(n, t + i * 0.2, 0.4));
};
ic.doc = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="dc"><g transform="rotate(-3)"><rect x="-250" y="-250" width="500" height="520" fill="#f3eee2" ${O(8)}/><circle cy="-188" r="42" fill="#c9a24a" ${O(5)}/><text y="-176" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#2a1820">★</text>
    <text y="-100" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#2a1820" letter-spacing="3">PRESIDENTIAL</text><text y="-52" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="46" fill="#2a1820" letter-spacing="3">COMMUTATION</text>
    <path d="M-190 0H190M-190 40H190M-190 80H120" stroke="#2a1820" stroke-width="5" opacity=".4"/><text y="156" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="30" fill="#2a1820" letter-spacing="3">ALICE MARIE JOHNSON</text></g></g>`), 1.0);
  S.pop("dc", t, 0.45);
};
ic.clap = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="cl"><rect x="-290" y="-110" width="580" height="330" rx="14" fill="#23232e" ${O(9)}/><g data-p="clap"><g transform="translate(-290 -110)"><path d="M0 -70H580V0H0Z" fill="#f3eee2" ${O(8)}/>${[0, 1, 2, 3, 4, 5].map((i) => `<path d="M${i * 100 + 10} -66l50 0 -50 62z" fill="#23232e"/>`).join("")}</g></g>
    <text y="30" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="50" fill="#fff" letter-spacing="5">THE JUSTICE</text><text y="92" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="62" fill="#ffb84a" letter-spacing="5">PROJECT</text><text y="170" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="30" fill="#cfe0f5" letter-spacing="8">DOCUMENTARY · 2020</text></g>`), 1.0);
  S.pop("cl", t, 0.4); S.key("clap", "--r", t + 0.1, -26, 0); S.key("clap", "--r", t + 0.5, -26, 0); S.key("clap", "--r", t + 0.5, 0, 0.12, "power3.in");
};
ic.four = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, [0, 1, 2, 3].map((i) => `<g data-p="kid${i}"><g transform="translate(${(i - 1.5) * 190} ${i % 2 ? 30 : -10})"><circle cy="-66" r="46" fill="${["#e0a77f", "#d99a73", "#e5ae88", "#dba27d"][i]}" ${O(6)}/><path d="M-46 -72C-46 -128 46 -128 46 -72C30 -98 -30 -98 -46 -72Z" fill="#16100f" ${O(5)}/><path d="M-62 90Q-62 -8 0 -8Q62 -8 62 90Z" fill="${["#f2a7b8", "#6a7ec2", "#8fc3a4", "#e4a13a"][i]}" ${O(6)}/></g></g>`).join("") + `<text y="190" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="46" fill="#fff" stroke="#05070c" stroke-width="7" paint-order="stroke" letter-spacing="8">FOUR CHILDREN</text>`), 1.0);
  for (let i = 0; i < 4; i++) S.pop("kid" + i, t + i * 0.18, 0.35);
};
ic.attempts = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, [0, 1, 2, 3].map((i) => `<g data-p="at${i}"><g transform="translate(${(i - 1.5) * 190} 0)"><rect x="-80" y="-110" width="160" height="220" rx="14" fill="#f3eee2" ${O(7)}/><text y="-48" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="30" fill="#2a1820" letter-spacing="3">TRY ${i + 1}</text>
      ${i < 3 ? `<path d="M-34 4L34 72M34 4L-34 72" stroke="#c4252d" stroke-width="14" stroke-linecap="round"/>` : `<path d="M-40 38L-8 72L44 -2" fill="none" stroke="#2f9a5a" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>`}</g></g>`).join("") + `<text y="190" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="32" fill="#ffb84a" stroke="#05070c" stroke-width="7" paint-order="stroke" letter-spacing="3">BABY BAR EXAM · DEC 2021</text>`), 1.0);
  for (let i = 0; i < 4; i++) S.pop("at" + i, t + i * 0.3, 0.3);
};
ic.bars = (S, cx, cy, t, bars, times) => {   // bars: [{label, val(0..1), txt, col}]
  const bw = 170, gap = 100, n = bars.length, x0 = -((n * bw + (n - 1) * gap) / 2) + bw / 2;
  S.layer(P("icn", cx, cy, `<path d="M${x0 - 120} 240H${-x0 + 120}" stroke="#cfe0f5" stroke-width="5" opacity=".6"/>` + bars.map((b, i) => `<g transform="translate(${x0 + i * (bw + gap)} 240)"><g data-p="bar${i}"><rect x="${-bw / 2}" y="${-(b.val * 420)}" width="${bw}" height="${b.val * 420}" fill="${b.col || "#ffb84a"}" ${O(7)}/>
      <text y="${-(b.val * 420) - 18}" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="52" fill="#fff" stroke="#05070c" stroke-width="8" paint-order="stroke">${b.txt}</text></g><text y="52" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="23" fill="#e8eef9" letter-spacing="2">${b.label}</text></g>`).join("")), 1.0);
  bars.forEach((b, i) => { const e = S.q("bar" + i), ti = times ? times[i] : t + i * 0.3; e.style.opacity = "0"; S.key(e, "opacity", ti, 0, 0); S.key(e, "opacity", ti, 1, 0.05); S.key(e, "--sy", ti, 0.001, 0); S.key(e, "--sy", ti, 1, 0.6, "power3.out"); });
};
ic.funding = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<rect x="-380" y="-210" width="760" height="420" rx="22" fill="#f3eee2" ${O(8)}/><text y="-90" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="30" fill="#7a5a2a" letter-spacing="8">FUNDING ROUND · NOV 2025</text><text y="50" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="190" fill="#2a1820">$225M</text>
    <path d="M-300 90H300" stroke="#2a1820" stroke-width="4" opacity=".4"/><text y="140" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="26" fill="#2a1820" letter-spacing="2">LED BY GOLDMAN SACHS ALTERNATIVES</text><text y="182" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="22" fill="#7a5a2a" letter-spacing="3">WITH BDT &amp; MSD PARTNERS</text>`), 1.0);
  S.pop("icn", t, 0.45);
};
ic.tiles = (S, cx, cy, t) => {
  const T = [["FAME", "#c4666b"], ["FAMILY", "#e4a13a"], ["LAW", "#3d6a9c"], ["BUSINESS", "#2f9a5a"]];
  S.layer(P("icn", cx, cy, T.map((q, i) => `<g data-p="ti${i}"><g transform="translate(${(i % 2 - 0.5) * 420} ${((i / 2) | 0 ? 1 : -1) * 130})"><rect x="-190" y="-100" width="380" height="200" rx="18" fill="${q[1]}" ${O(8)}/><text y="22" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="62" fill="#fff" stroke="#05070c" stroke-width="7" paint-order="stroke" letter-spacing="5">${q[0]}</text></g></g>`).join("")), 1.0);
  for (let i = 0; i < 4; i++) S.pop("ti" + i, t + i * 0.45, 0.4);
};

/* ---------- documentary card: archive-board backdrop + kicker + big title lines + icon + sources + timeline ---------- */
const card = (o) => D.shot({ id: o.id, a: o.a, b: o.b, bg: { layers: [{ name: "far", depth: 0.25, svg: DK.boardFar(o.year || "", o.seed || 3) }] }, cam: o.cam || { from: [-26, 6, 0.0], to: [26, -6, 0.07] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, left = o.left || (o.icon ? 150 : 260), sz = o.size || 92, y0 = o.y0 || 470;
    S.layer(DK.boardNear(o.seed || 3), 1.3);
    if (o.kick) { TX(S, "kick", left, y0 - Math.round(sz * 0.74) - 20, 30, "#ffb84a", o.kick, { ls: 11 }); appear(S, "kick", t0 + 0.1, 0.3, true); }
    (o.lines || []).forEach((ln, i) => { TX(S, "ln" + i, left, y0 + i * sz * 1.08, sz, i === (o.hi === undefined ? -1 : o.hi) ? "#ffb84a" : "#fff", ln, { ls: 4 }); appear(S, "ln" + i, o.lineAt && o.lineAt[i] ? o.lineAt[i](S) : t0 + 0.2 + i * 0.2, 0.3, true); });
    if (o.sub) { TX(S, "sub", left, y0 + (o.lines || []).length * sz * 1.08 + 20, o.subSize || 36, "#cfe0f5", o.sub, { w: 700, ls: 6, sw: 5 }); appear(S, "sub", t0 + 0.6, 0.3, true); }
    if (o.icon) o.icon(S, o.ix || 1430, o.iy || 560, t0 + (o.iat || 0.3), t1);
    if (o.hud) DK.hud(S, "hud", Object.assign({ t0: t0 + 0.05, t1: Math.min(t1 - 0.05, t0 + (o.hudDur || 1.6)) }, o.hud));
    if (o.src) { TX(S, "src", 140, 850, 28, "#e8eef9", o.src, { w: 700, ls: 2, sw: 5 }); appear(S, "src", t0 + 0.8, 0.3); }
    badge(S, o.badge || GRAPHIC);
    if (o.extra) o.extra(S, t0, t1);
    grade(S, "mono", { tint: o.tint || "#6c84b4", ta: 0.2, dark: 0.1, vig: 0.74 });
    light(S, o.ix || 1430, o.iy || 560, 700, 380, "#cfe0ff", 0.2);
  } });

/* ---------- cartoon scene wrapper: reconstruction badge + shot-level grade/light ---------- */
const scene = (o) => D.shot({ id: o.id, a: o.a, b: o.b, bg: o.bg, cam: o.cam || { from: [0, 0, 0], to: [0, 0, 0.1] },
  build(S) {
    if (o.rays !== false) S.layer(C.rays(o.rays ? o.rays[0] : 1500, o.rays ? o.rays[1] : -40, o.rays ? o.rays[2] : 1.95, 1100, 0.3, o.rayc || "#ffe0a8", 0.3), 0.4);
    o.build(S);
    if (o.tag) DK.tag(S, "tg", o.tag[0], o.tag[1], o.tag[2] === undefined ? 120 : o.tag[2], o.tag[3] === undefined ? 330 : o.tag[3], o.tag[4] === undefined ? S.t0 + 0.25 : o.tag[4], { w: o.tag[5] });
    if (o.hud) DK.hud(S, "hud", Object.assign({ t0: S.t0 + 0.05, t1: Math.min(S.t1 - 0.05, S.t0 + 1.5) }, o.hud));
    if (o.badge !== false) badge(S, o.badge || RECON);
    if (o.grade) grade(S, o.grade[0], o.grade[1]);
    if (o.light) light(S, o.light[0], o.light[1], o.light[2], o.light[3], o.light[4], o.light[5]);
  } });

/* ---------- shared cartoon helpers (used by chapters 2 and 3) ---------- */
const NW = (sid, i) => D.W(sid, Math.min(i, nW(sid) - 1));
const GROOM1 = { build: "man", skin: "#c98f6a", hair: "short_man", hairColor: "#2a1a14", top: "#2b2f3d", pants: "#2b2f3d", outfit: "suit", accent: "#c43b3b", shoe: "#1a1a22" };
const GROOM2 = Object.assign({}, GROOM1, { skin: "#b9835e", hair: "slick", hairColor: "#1c1210", top: "#e9e4d6", pants: "#1f2330", accent: "#3d6a9c" });
const BRIDE = Object.assign({}, KIM25, { top: "#f6f1e8", shoe: "#f6f1e8" });
const KID2 = Object.assign({}, SIS1, { top: "#f2a7b8", pants: "#6a7ec2" });
const KID3 = Object.assign({}, BRO, { top: "#3d6a9c" });
const BABY2 = Object.assign({}, BABY, { top: "#bfe0f4", pants: "#bfe0f4", shoe: "#bfe0f4" });
/* the couple stands on the left, happy; the right side stays free for the icon that tells the next fact */
const couple = (S, a, b, bride, groom, x, y, sc, tw, seed) => {
  const t0 = S.t0, t1 = S.t1;
  const br = S.actor("cpB", bride, x, y, sc, { seed: seed, expr: "happy", depth: 0.9, pivot: [x, y] }), gr = S.actor("cpG", groom, x + 190 * sc, y, sc * 1.02, { seed: seed + 1, expr: "happy", depth: 0.9, pivot: [x + 190 * sc, y] });
  br.arm("R", tw, 34, 40, 0.3); gr.arm("L", tw, -34, -40, 0.3); br.face(tw, "laugh", 0.3); gr.face(tw, "happy", 0.3);
  br.talkWords(a, t0); 
  S.layer(PR.heart("hrt", x + 95 * sc, y - 500 * sc), 1.1); S.pop("hrt", tw + 0.1, 0.5); S.key("hrt", "--y", tw + 0.5, -40, 0.9, "sine.out");
  return [br, gr];
};

const GROOM3 = Object.assign({}, GROOM1, { skin: "#d9a07a", hair: "short_man", hairColor: "#3a2a20", top: "#3a4a6a", pants: "#2a3250", accent: "#e4a13a" });
const BRANDYS = { build: "woman", skin: "#8a5a3c", hair: "wavy_long", hairColor: "#1c1210", outfit: "dress", top: "#8a3a6a", legs: "bare", shoe: "#d9c9b0", shoeType: "pump", sleeve: "none", earrings: 1, lip: "#a8323f", accent: "#f3c64a" };
const JOHNSONS = { build: "woman", skin: "#8a5a3c", hair: "bob", hairColor: "#1c1210", outfit: "dress", top: "#4c6a9c", legs: "bare", shoe: "#2b2230", shoeType: "pump", sleeve: "none", lip: "#a8323f", accent: "#e8e4d8" };

/* shot isolation: an element that was made visible explicitly (pop / show / appear) overrides a hidden parent group in SVG,
   so such elements used to linger after their shot ended. Every shot group is therefore also switched off with display:none. */
const _shot = D.shot;
D.shot = (o) => { const S = _shot(o); S.el.style.display = "none"; D.key(S.el, "display", S.t0, "inline", 0); D.key(S.el, "display", S.t1, "none", 0); return S; };

const nameTag = (S, id, text, x, y, t) => { const w = text.length * 25 + 70; S.layer(P(id, x, y, `<rect x="${-w / 2}" y="-34" width="${w}" height="52" rx="8" fill="#fff" ${st(6)}/><text y="6" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="30" fill="#2a1820" letter-spacing="3">${text}</text>`), 1.1); S.pop(id, t, 0.35); };
const dimTo = (S, t, op, dur, col) => { S.layer(`<g data-p="dimv"><rect width="1920" height="1080" fill="${col || "#0a1020"}" opacity="0"/></g>`, 0); const e = S.q("dimv").firstElementChild; S.key(e, "opacity", t, 0, 0); S.key(e, "opacity", t, op, dur, "sine.inOut"); };

/* ===================================================================================================== */
/* CHAPTER 1 · the question, birth, childhood                                                             */
/* ===================================================================================================== */
if (has("c1a")) {

/* 1 · OPENING (0-11 s): Los Angeles at dusk, the question as a big title that stays long enough to be read */
scene({ id: "open", a: 0, b: W("c1a", 0), bg: B.avenue(), cam: { from: [0, 20, 0.0], to: [0, -12, 0.24], ease: "power1.inOut" }, rays: false, badge: false,
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 548, Math.PI / 2, 760, 0.42, "#ffd9a0", 0.34), 0.42);
    C.fog(S, { y: 650, h: 220, color: "#ffcfa0", op: 0.34, seed: 3, depth: 0.55, drift: 120 });
    C.dust(S, { n: 22, seed: 13, box: [100, 100, 1700, 800], color: "#ffe9c0", depth: 1.1, op: 0.5 });
    S.layer(FG.leaves("L"), 1.7); S.layer(FG.leaves("R"), 1.75);
    grade(S, "dusk");
    light(S, 960, 780, 620, 380, "#ffd7a0", 0.5);
    S.layer(`<defs><linearGradient id="tband" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05070c" stop-opacity=".0"/><stop offset=".25" stop-color="#05070c" stop-opacity=".62"/><stop offset=".75" stop-color="#05070c" stop-opacity=".62"/><stop offset="1" stop-color="#05070c" stop-opacity="0"/></linearGradient></defs><rect x="0" y="130" width="1920" height="330" fill="url(#tband)"/>`, 0);
    TX(S, "t1", 960, 232, 36, "#cfe0f5", "WHAT IF YOU WERE BORN AS", { anchor: "middle", ls: 16, w: 700, sw: 5, depth: 0 });
    TX(S, "t2", 960, 366, 120, "#fff", "KIM KARDASHIAN?", { anchor: "middle", ls: 5, sw: 8, depth: 0 });
    appear(S, "t1", 0.6, 0.5); appear(S, "t2", 0.9, 0.5);
    S.key("t2", "--s", 0.9, 1.08, 0); S.key("t2", "--s", 0.9, 1, 0.9, "power3.out");
    S.fadeOut("t1", t1 - 0.5, 0.45); S.fadeOut("t2", t1 - 0.5, 0.45);
  } });


/* 1b · 5-12 s: the narrator asks the question while our cartoon Kim is introduced */
scene({ id: "intro", a: W("c1a", 0), b: W("c1c", 0), bg: B.avenue(), cam: { from: [0, 12, 0.08], to: [0, -6, 0.0], ease: "power1.out" }, rays: false, grade: ["dusk", {}], light: [960, 800, 620, 380, "#ffd7a0", 0.45],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 548, Math.PI / 2, 760, 0.42, "#ffd9a0", 0.3), 0.42);
    C.fog(S, { y: 650, h: 220, color: "#ffcfa0", op: 0.3, seed: 3, depth: 0.55, drift: 120 });
    C.dust(S, { n: 22, seed: 14, box: [100, 100, 1700, 800], color: "#ffe9c0", depth: 1.1, op: 0.5 });
    const k = S.actor("kimI", KIM25, 960, 960, 1.12, { seed: 71, expr: "neutral", pivot: [960, 960], depth: 0.95 });
    k.k("self", "--x", t0, -700, 0); k.walk(t0 + 0.05, t0 + 2.0, 700, { arms: true, step: 0.3 });
    k.face(t0 + 2.1, "smirk", 0.3); k.arm("R", t0 + 2.3, -40, -10, 0.4, "back.out(1.4)");
    if (has("c1b")) k.talkWords("c1b", D.W("c1b", 0));
    S.layer(FG.leaves("L"), 1.7); S.layer(FG.leaves("R"), 1.75);
    S.layer(`<defs><linearGradient id="gx" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05070c" stop-opacity=".5"/><stop offset="1" stop-color="#05070c" stop-opacity="0"/></linearGradient></defs><rect width="1920" height="200" fill="url(#gx)"/>`, 0);
    nameTag(S, "kn", "KIM KARDASHIAN", 960, 250, t0 + 2.2);
    TX(S, "hdr", 960, 120, 40, "#fff", "WHAT IF YOU WERE BORN AS KIM KARDASHIAN?", { anchor: "middle", ls: 5, sw: 3, depth: 0 });
    appear(S, "hdr", t0 + 0.1, 0.4);
  } });

/* 2-5 · MONTAGE: a famous family / television cameras / fashion / a business empire */
scene({ id: "mFam", badge: false, a: W("c1c", 0), b: W("c1c", 3), bg: B.living(), cam: { from: [50, 0, 0.0], to: [-30, 0, 0.12] }, grade: ["glam", {}], light: [960, 760, 700, 400, "#ffe2c0", 0.3],
  build(S) {
    const t0 = S.t0, L = [[DAD, 560, 0.9], [MOM, 760, 0.86], [SIS1, 960, 1.1], [KID, 1140, 1.0], [BRO, 1310, 0.9], [SIS2, 1470, 0.95]];
    L.forEach(([sp, x, sc], i) => { const a = S.actor("f" + i, sp, x, 930, sc, { seed: 5 + i, expr: "happy", depth: 0.9, pivot: [x, 930] }); a.k("self", "--y", t0, 80, 0); a.k("self", "--y", t0 + 0.12 * i, 0, 0.35, "power3.out"); a.appear(t0 + 0.12 * i, 0.3); });
    C.dust(S, { n: 12, seed: 17, box: [300, 200, 1300, 600], color: "#fff1c4", depth: 1.1, op: 0.4 });
  } });
DK.flash(D.W("c1c", 3), 0.55, 0.18);
scene({ id: "mCam", badge: false, a: W("c1c", 3), b: W("c1c", 5), bg: B.stage(), cam: { from: [0, 0, 0.0], to: [0, 0, 0.1] }, grade: ["studio", {}],
  build(S) {
    const t0 = S.t0;
    S.layer(PR.spot(300, 330, 10), 0.8); S.layer(PR.spot(1620, 330, 170), 0.8);
    S.layer(`<g data-p="bigcam"><g transform="translate(960 640) scale(2.3) translate(-1500 -760)">${FG.cam()}</g></g>`, 1.3);
    S.key("bigcam", "--s", t0, 0.85, 0); S.key("bigcam", "--s", t0, 1, S.dur, "power1.out");
    [0.55, 0.95, 1.35].forEach((d) => DK.flash(t0 + d, 0.6, 0.15));
    C.dust(S, { n: 14, seed: 19, box: [200, 100, 1500, 800], color: "#fff", depth: 1.2, op: 0.4 });
  } });
DK.flash(D.W("c1c", 5), 0.5, 0.18);
scene({ id: "mFash", badge: false, a: W("c1c", 5), b: W("c1c", 9), bg: B.stage(), cam: { from: [0, 0, 0.0], to: [0, 0, 0.14] }, grade: ["glam", {}], light: [960, 760, 520, 380, "#ffe0f6", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1, PV = [960, 720];
    S.layer(PR.spot(300, 330, 10), 0.8); S.layer(PR.spot(1620, 330, 170), 0.8);
    S.layer(FX.cone(330, 330, 700, 900, 1220, 900, 370, 340, "#ffd9f0", 0.38), 0.7); S.layer(FX.cone(1590, 330, 1220, 900, 700, 900, 1550, 340, "#ffd9f0", 0.34), 0.7);
    const k = S.actor("runway", KIM25, PV[0], PV[1], 0.5, { depth: 0.9, seed: 77, idle: false, pivot: PV, expr: "smirk" });
    k.walk(t0 + 0.05, t1 - 0.1, 0, { arms: true, step: 0.34, amp: 16 });
    k.k("self", "--s", t0, 1, 0); k.k("self", "--s", t0 + 0.05, 2.3, t1 - t0 - 0.1, "power1.in"); k.k("self", "--y", t0, 0, 0); k.k("self", "--y", t0 + 0.05, 300, t1 - t0 - 0.1, "power1.in");
    for (let t = t0 + 0.3; t < t1 - 0.2; t += 0.55) DK.flash(t, 0.35, 0.12);
    S.layer(FG.heads(5, 8, 1150), 1.45);
  } });
scene({ id: "mEmp", badge: false, a: W("c1c", 9), b: W("c1d", 0), bg: B.boutique(), cam: { from: [0, 14, 0.0], to: [0, -8, 0.16] }, grade: ["glam", {}], light: [560, 760, 520, 420, "#fff1d8", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    const k = S.actor("kimE", KIM25, 700, 920, 1.05, { seed: 61, expr: "happy", pivot: [700, 920] });
    k.arm("L", t0 + 0.2, 150, 20, 0.45, "back.out(1.6)"); k.arm("R", t0 + 0.2, -150, -20, 0.45, "back.out(1.6)"); k.hop(t0 + 0.4, 26, 0.4);
    for (let i = 0; i < 5; i++) { S.layer(PR.coin("mc" + i, 1160 + i * 120, 860), 1.2); S.pop("mc" + i, t0 + 0.15 + i * 0.12, 0.35); S.key("mc" + i, "--y", t0 + 0.5 + i * 0.1, -40 - (i % 2) * 26, 0.7, "sine.out"); }
    confetti(S, t0 + 0.2, 22, 6);
    DK.tag(S, "empTag", "A BUSINESS EMPIRE", "", 1210, 330, t0 + 0.2, { w: 640 });
  } });

/* 6 · MAP: none of that exists yet; the story begins in Los Angeles */
DK.whip(D.W("c1d", 0), 1);
D.shot({ id: "map1", a: W("c1d", 0), b: W("s1", 0), cam: { from: [0, 0, 0], to: [0, 0, 0.05] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, T = [760, 520], tp = D.W("c1d", 10);
    S.layer(`<g data-p="mz">${DK.mapSvg()}${cityDots()}</g>`, 0.45);
    mapGo(S, "mz", t0, 0, 0.94, [960, 500], [960, 500]);
    mapGo(S, "mz", t0 + 0.4, 1.6, 3.0, LAp, T, "power2.inOut");
    mapGo(S, "mz", t0 + 2.0, Math.max(0.2, t1 - t0 - 2.0), 3.3, LAp, T, "none");
    S.layer(`<g transform="translate(${T[0]} ${T[1]})">${pinSvg("pinLA", "LOS ANGELES", { stem: 96 })}</g>`, 0.95);
    S.pop("pinLA", tp - 0.1, 0.4);
    S.key("pinLA_rp", "--s", tp, 0.3, 0); S.key("pinLA_rp", "--s", tp, 2.4, 0.9, "power2.out"); S.key("pinLA_rp", "opacity", tp, 1, 0); S.key("pinLA_rp", "opacity", tp, 0, 0.9, "power1.in");
    badge(S, MAPB);
    grade(S, "mono", { tint: "#7b98c4", ta: 0.14, dark: 0.04, vig: 0.7 });
  } });

/* 7 · BIRTH: close-up of the newborn behind crib bars + date card (cartoon reconstruction, no photograph) */
DK.flash(D.W("s1", 0), 0.85, 0.28);
D.shot({ id: "birth", a: W("s1", 0), b: W("c1s", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("baby") }] }, cam: { from: [0, 0, 0.02], to: [20, -8, 0.13] },
  build(S) {
    const t0 = S.t0, t3 = D.W("s1", 9);
    S.layer(C.rays(1700, -40, 1.9, 1100, 0.3, "#9fb8ff", 0.34), 0.4);
    const baby = closeUp(S, "baby", BABY, 600, 580, 540, { depth: 0.9, seed: 4 });
    baby.face(t0, "neutral", 0); baby.look(t0, -8, -6, 0); baby.look(t0 + 0.6, 8, -6, 0.6, "sine.inOut"); baby.face(t0 + 1.4, "happy", 0.3); baby.turn(t0 + 0.1, -4, -3, 0.7); baby.turn(t0 + 1.2, 4, 3, 1.2);
    C.dust(S, { n: 16, seed: 12, box: [100, 150, 900, 800], color: "#d8e4ff", depth: 1.1, op: 0.5 });
    S.layer(FG.barsAt([50, 170]), 1.55);
    grade(S, "night");
    light(S, 600, 560, 520, 420, "#ffe2b0", 0.4);
    TX(S, "kick", 1010, 400, 30, "#ffb84a", "THE DAY YOU ARE BORN", { ls: 11 }); TX(S, "dOct", 1010, 530, 112, "#fff", "OCTOBER", { ls: 4 }); TX(S, "d21", 1610, 530, 112, "#ffb84a", "21", { ls: 4 }); TX(S, "d80", 1010, 800, 250, "#fff", "1980", { ls: 6 });
    S.layer(`<g transform="translate(1010 575)"><g data-p="ul"><rect width="760" height="6" fill="#ffb84a"/></g></g>`, 1.0);
    S.key("kick", "--sx", t0 + 0.1, 0, 0); S.key("kick", "--sx", t0 + 0.1, 1, 0.4, "power3.out"); S.key("dOct", "--sx", t0, 0, 0); S.key("dOct", "--sx", t0, 1, 0.35, "power3.out");
    S.key("ul", "--sx", t0 + 0.1, 0, 0); S.key("ul", "--sx", t0 + 0.1, 1, 0.7, "power3.out");
    S.pop("d21", D.W("s1", 8), 0.3);
    const e80 = S.q("d80"); e80.style.visibility = "hidden"; S.key(e80, "--s", t3, 1.7, 0); S.show("d80", t3, true); S.key(e80, "--s", t3, 1, 0.16, "power3.out");
    DK.flash(t3, 0.35, 0.2);
    DK.hud(S, "h2", { from: 1970, to: 1980, t0: t0 + 0.05, t1: t0 + 1.25, marks: [{ y: 1980, label: "BORN" }] });
    badge(S, RECON);
  } });

/* 8 · LOS ANGELES 1980: palm avenue, film-premiere searchlights, a city built on fame */
scene({ id: "la80", a: W("c1s", 0), b: W("c1e", 0), bg: B.avenue(), cam: { from: [-30, 10, 0.0], to: [40, -14, 0.2] }, rays: false, grade: ["dusk", {}], light: [960, 780, 520, 360, "#ffd7a0", 0.4],
  build(S) {
    const t0 = S.t0, t1 = S.t1, ts = D.W("c1s", 10);
    S.layer(C.rays(960, 548, Math.PI / 2, 760, 0.42, "#ffd9a0", 0.3), 0.42);
    C.fog(S, { y: 650, h: 220, color: "#ffcfa0", op: 0.3, seed: 3, depth: 0.55, drift: 120 });
    S.layer(`<g data-p="sl1"><g transform="translate(420 700)"><path d="M-30 0L30 0L170 -900L-170 -900Z" fill="#fff4d0" opacity=".26"/></g></g><g data-p="sl2"><g transform="translate(1500 700)"><path d="M-30 0L30 0L170 -900L-170 -900Z" fill="#fff4d0" opacity=".24"/></g></g>`, 0.5);
    for (let t = t0, i = 0; t < t1; t += 0.9, i++) { S.key("sl1", "--r", t, i % 2 ? -22 : 14, 0.9, "sine.inOut"); S.key("sl2", "--r", t, i % 2 ? 22 : -14, 0.9, "sine.inOut"); }
    C.dust(S, { n: 18, seed: 33, box: [100, 100, 1700, 800], color: "#ffe9c0", depth: 1.1, op: 0.5 });
    S.layer(FG.leaves("L"), 1.7); S.layer(FG.leaves("R"), 1.75);
    DK.tag(S, "laTag", "LOS ANGELES · 1980", "", 1160, 330, D.W("c1s", 4) + 0.1, { w: 700 });
    DK.hud(S, "hla", { from: 1980, to: 1980, t0, t1, marks: [{ y: 1980, label: "BORN" }] });
    void ts; badge(S, RECON);
  } });

/* 9 · father: a lawyer walks into his office */
scene({ id: "dadOffice", a: W("c1e", 0), b: W("c1e", 6), bg: B.office(), cam: { from: [-60, 6, 0.0], to: [40, -10, 0.18] }, rays: [960, 340, Math.PI / 2], rayc: "#cfe0ff", grade: ["office", {}], light: [960, 720, 700, 420, "#ffd9a0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(PR.desk(1180, 860, 520), 0.8);
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 5, depth: 0.55, drift: 80 });
    const dad = S.actor("dad", DAD, 520, 860, 1.22, { seed: 9, pivot: [520, 860] });
    dad.k("self", "--x", t0, -760, 0); dad.walk(t0 + 0.02, t1 - 0.12, 1000, { arms: false, step: 0.3 }); dad.face(t0, "neutral", 0);
    dad.arm("R", t0, -14, -4, 0.05); dad.arm("R", t1 - 0.2, -60, -50, 0.18);
    S.layer(PR.briefcase(0, 0), 0.9); const bc = S.q("pr"); S.key(bc, "--x", t0, -200, 0); S.key(bc, "--y", t0, 760, 0); S.key(bc, "--x", t0 + 0.02, 780, t1 - t0 - 0.14, "none");
    C.dust(S, { n: 18, seed: 31, box: [500, 200, 900, 560], color: "#fff4d0", depth: 1.0, op: 0.55 });
    S.layer(FG.desk(), 1.5); S.layer(FG.post(60), 1.6);
    DK.tag(S, "dadTag", "YOUR FATHER · ROBERT", "A LAWYER", 1180, 330, D.W("c1e", 2) + 0.05, { w: 640 });
  } });
/* 9b · mother: close-up */
scene({ id: "momClose", a: W("c1e", 6), b: W("c1f", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kid") }] }, cam: { from: [0, 0, 0.02], to: [-10, 4, 0.14] }, grade: ["home", { dark: 0.16 }], light: [960, 540, 520, 430, "#ffc88a", 0.38],
  build(S) {
    const t0 = S.t0, m = closeUp(S, "mom", MOM, 960, 580, 540, { depth: 0.9, seed: 8, expr: "neutral" });
    m.face(t0 + 0.4, "happy", 0.4); m.look(t0, 8, 0, 0); m.look(t0 + 0.6, -6, 0, 0.5, "sine.inOut"); m.turn(t0 + 0.2, 3, 3, 0.7);
    C.dust(S, { n: 14, seed: 41, box: [200, 100, 1500, 800], color: "#ffd9a0", depth: 1.1, op: 0.4 });
    S.layer(PR.heart("hr", 1500, 380), 1.1); S.pop("hr", D.W("c1e", 11), 0.5); S.key("hr", "--y", D.W("c1e", 11) + 0.5, -40, 0.9, "sine.out");
    DK.tag(S, "momTag", "YOUR MOTHER · KRIS", "A GROWING FAMILY", 120, 330, D.W("c1e", 7) + 0.05, { w: 660 });
  } });

/* 10 · siblings */
scene({ id: "sibs", a: W("c1f", 0), b: W("s3", 0), bg: B.living(), cam: { from: [40, 0, 0.0], to: [-30, 0, 0.1] }, grade: ["home", { tint: "#e0a870", dark: 0.14 }], light: [960, 780, 700, 400, "#ffd9a8", 0.34],
  build(S) {
    const t0 = S.t0;
    const mk = (id, sp, x, sc, t, seed) => { const a = S.actor(id, sp, x, 1010, sc, { seed, expr: "happy", depth: 1.0, pivot: [x, 1010] }); a.k("self", "--y", t0, 140, 0); a.k("self", "--y", t, 0, 0.4, "power3.out"); a.appear(t, 0.35); return a; };
    mk("sk1", SIS1, 620, 1.28, t0 + 0.05, 3); mk("sk2", KID, 900, 1.18, t0 + 0.05, 4); mk("sk3", SIS2, 1190, 1.06, D.W("c1f", 8), 5); mk("sk4", BRO, 1460, 0.98, D.W("c1f", 13), 6);
    nameTag(S, "n1", "KOURTNEY", 620, 330, D.W("c1f", 7)); nameTag(S, "n2", "YOU", 900, 350, t0 + 0.9); nameTag(S, "n3", "KHLOÉ", 1190, 380, D.W("c1f", 12)); nameTag(S, "n4", "ROB", 1460, 400, D.W("c1f", 15));
    DK.hud(S, "hsib", { from: 1979, to: 1987, t0: t0 + 0.05, t1: Math.min(S.t1 - 0.05, t0 + 4.5), marks: [{ y: 1979, label: "KOURTNEY" }, { y: 1984, label: "KHLOÉ" }, { y: 1987, label: "ROB" }] });
  } });

/* 11 · age nine: the parents part (the narration says "separate"; the divorce was final in 1991) */
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
    DK.tag(S, "ageTag", "AGE 9 · 1989", "YOUR PARENTS SEPARATE", 120, 330, D.W("s3", 3), { w: 700 });
    DK.hud(S, "h5", { from: 1980, to: 1989, t0: t0 + 0.05, t1: D.W("s3", 4) - 0.02, marks: [{ y: 1980, label: "BORN" }, { y: 1989, label: "AGE 9" }] });
    badge(S, RECON);
  } });
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
    badge(S, RECON);
  } });

/* 12 · two years later: the 1991 wedding */
DK.whip(D.W("s4", 0), -1);
D.shot({ id: "wedding", a: W("s4", 0), b: W("c1h", 0), bg: B.garden(), cam: { from: [30, 0, 0.0], to: [-20, -8, 0.2] },
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
    badge(S, RECON);
  } });
card({ id: "apr91", a: W("c1h", 0), b: W("c1h2", 0), year: 1991, seed: 5, kick: "KRIS & BRUCE JENNER", lines: ["APRIL 1991"], sub: "ONE MONTH AFTER HER DIVORCE IS FINAL", icon: ic.rings, ix: 1480, iy: 560,
  hud: { from: 1991, to: 1991, marks: [{ y: 1991, label: "WEDDING" }] }, src: "SOURCES: BUSTLE · BRITANNICA" });
card({ id: "span", a: W("c1h2", 0), b: W("c1i", 0), year: 2014, seed: 6, kick: "THEIR MARRIAGE", lines: ["1991 – 2014"], sub: "KRIS & BRUCE JENNER", hudDur: 2.6, hud: { from: 1991, to: 2014, marks: [{ y: 1991, label: "WEDDING" }, { y: 2014, label: "ENDS" }] }, src: "SOURCE: BRITANNICA" });

/* 13 · MAP: Los Angeles -> Montreal, July 30th 1976 */
DK.flash(D.W("c1i", 0), 0.7, 0.26);
D.shot({ id: "map2", a: W("c1i", 0), b: W("c1i", 6), cam: { from: [0, 0, 0], to: [0, 0, 0.04] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, TM = [800, 520];
    const ctl = [(LAp[0] + MTp[0]) / 2, Math.min(LAp[1], MTp[1]) - 200], bz = (u) => [(1 - u) * (1 - u) * LAp[0] + 2 * u * (1 - u) * ctl[0] + u * u * MTp[0], (1 - u) * (1 - u) * LAp[1] + 2 * u * (1 - u) * ctl[1] + u * u * MTp[1]];
    let len = 0, pv = bz(0); for (let i = 1; i <= 40; i++) { const q = bz(i / 40); len += Math.hypot(q[0] - pv[0], q[1] - pv[1]); pv = q; }
    const route = `<path data-p="route" d="M${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)}Q${ctl[0].toFixed(1)} ${ctl[1].toFixed(1)} ${MTp[0].toFixed(1)} ${MTp[1].toFixed(1)}" fill="none" stroke="#ffb84a" stroke-width="5" stroke-linecap="round" stroke-dasharray="${len.toFixed(0)}" stroke-dashoffset="${len.toFixed(0)}"/>
      <path d="M${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)}Q${ctl[0].toFixed(1)} ${ctl[1].toFixed(1)} ${MTp[0].toFixed(1)} ${MTp[1].toFixed(1)}" fill="none" stroke="#ffb84a" stroke-width="2" stroke-dasharray="3 14" opacity=".45"/>
      <g transform="translate(${LAp[0].toFixed(1)} ${LAp[1].toFixed(1)}) scale(.9)">${pinSvg("pinLA2", "LOS ANGELES", { stem: 84 })}</g>`;
    S.layer(`<g data-p="mz2">${DK.mapSvg()}${cityDots()}${route}</g>`, 0.45);
    mapGo(S, "mz2", t0, 0, 0.98, [960, 500], [960, 500]);
    const tr0 = t0 + 0.12, tr1 = t0 + 1.0;
    dashIn(S.q("route"), len.toFixed(0), tr0, tr1 - tr0, "power1.inOut");
    mapGo(S, "mz2", t0 + 0.8, 0.9, 2.2, MTp, TM, "power2.inOut");
    S.layer(`<g transform="translate(${TM[0]} ${TM[1]})">${pinSvg("pinMTL", "MONTREAL · JULY 30, 1976", { stem: 96 })}</g>`, 0.95);
    const tpin = Math.min(t0 + 1.75, t1 - 0.5); S.pop("pinMTL", tpin, 0.4);
    S.key("pinMTL_rp", "--s", tpin, 0.3, 0); S.key("pinMTL_rp", "--s", tpin, 2.4, 0.9, "power2.out"); S.key("pinMTL_rp", "opacity", tpin, 1, 0); S.key("pinMTL_rp", "opacity", tpin, 0, 0.9, "power1.in");
    badge(S, MAPB);
    grade(S, "mono", { tint: "#7b98c4", ta: 0.14, dark: 0.06, vig: 0.72 });
    DK.hud(S, "h8", { from: 1991, to: 1976, t0: t0 + 0.05, t1: t0 + 1.2, marks: [{ y: 1991, label: "WEDDING" }, { y: 1976, label: "OLYMPICS" }] });
  } });
scene({ id: "stadium", a: W("c1i", 6), b: W("c1j", 0), bg: B.stadium(), cam: { from: [-40, 0, 0.0], to: [30, -8, 0.16] }, grade: ["stadium", {}], light: [960, 760, 640, 380, "#fff2c0", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1, PV = [700, 900];
    const br = S.actor("bruceR", BRUCE, PV[0], PV[1], 0.9, { seed: 91, idle: false, pivot: PV, expr: "determined" });
    br.k("self", "--x", t0, -260, 0); br.walk(t0 + 0.05, t1 - 0.1, 1300, { arms: true, step: 0.22, amp: 30 });
    S.layer(FX.note("olym", ["Olympic decathlon", "GOLD · 1976"], 1350, 330, { w: 600, size: 66, rot: -4 }), 1.0); S.fadeIn("olym", D.W("c1i", 9), 0.3); S.wipe("olym", D.W("c1i", 9) + 0.25, 1.2);
    S.layer(P("md", 0, 0, PR.medal(1560, 640)), 1.1); S.pop("md", D.W("c1i", 12) - 0.1, 0.4);
    DK.flash(D.W("c1i", 13), 0.45, 0.2);
    DK.tag(S, "brTag", "BRUCE JENNER", "OLYMPIC CHAMPION", 120, 330, D.W("c1i", 6) + 0.1, { w: 640 });
    DK.hud(S, "hst", { from: 1976, to: 1976, t0, t1, marks: [{ y: 1976, label: "OLYMPICS" }] });
  } });
card({ id: "deca", a: W("c1j", 0), b: W("c1k", 0), year: 1976, seed: 9, kick: "THE DECATHLON", lines: ["10 EVENTS", "2 DAYS"], hi: 1, sub: "OFTEN CALLED THE WORLD'S GREATEST ATHLETE", subSize: 32, src: "SOURCE: HISTORY.COM",
  extra(S, t0, t1) {
    let m = ""; for (let i = 0; i < 10; i++) m += `<g data-p="ev${i}"><g transform="translate(${(i % 5) * 130} ${(i / 5 | 0) * 150})"><circle r="48" fill="${i < 5 ? "#3d6a9c" : "#c4666b"}" ${st(7)}/><text y="15" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="42" fill="#fff">${i + 1}</text></g></g>`;
    S.layer(P("evs", 1290, 560, m), 1.0); for (let i = 0; i < 10; i++) S.pop("ev" + i, D.W("c1j", 3) + i * 0.22, 0.3);
    TX(S, "day1", 1240, 470, 24, "#9ec2ea", "DAY 1", { ls: 8, w: 800, sw: 4 }); TX(S, "day2", 1240, 648, 24, "#f0b6c0", "DAY 2", { ls: 8, w: 800, sw: 4 }); appear(S, "day1", D.W("c1j", 3), 0.3); appear(S, "day2", D.W("c1j", 3) + 1.2, 0.3);
  } });

/* 14 · the new family: Bruce and Kris with the children; the world is about to notice the father */
scene({ id: "fam91", a: W("c1k", 0), b: "end", bg: B.garden(), cam: { from: [0, 0, 0.2], to: [0, 0, 0.0], ease: "power2.out" }, grade: ["garden", {}], light: [960, 700, 700, 380, "#fff0c0", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1, ts = D.W("c1k", 8);
    S.layer(C.rays(1500, -40, 1.95, 1300, 0.3, "#fff0c0", 0.3), 0.35);
    const L = [[SIS1, 520, 0.88], [KID, 700, 0.84], [MOMW, 880, 0.92], [BRUCEW, 1060, 0.95], [SIS2, 1230, 0.78], [BRO, 1390, 0.74]];
    L.forEach(([sp, x, sc], i) => { const a = S.actor("g" + i, sp, x, 900, sc, { seed: 20 + i, expr: "happy", depth: 0.9, pivot: [x, 900] }); a.appear(t0 + 0.08 * i, 0.3); });
    const dad = S.actor("gDad", DAD, 1680, 900, 0.95, { seed: 29, expr: "neutral", depth: 0.9, pivot: [1680, 900] }); dad.k("self", "--x", t0, 240, 0); dad.k("self", "--x", ts, 0, 0.8, "power2.out"); dad.hiddenUntil(ts - 0.05);
    dimTo(S, ts, 0.5, 1.2, "#0a1226"); S.layer(C.key(1680, 700, 300, 520, "#cfe0ff", 0.0), 0.5);
    DK.tag(S, "dadT2", "ROBERT KARDASHIAN", "ABOUT TO BECOME A PUBLIC FIGURE", 1060, 330, ts + 0.3, { w: 860 });
    DK.hud(S, "h91", { from: 1991, to: 1991, t0, t1, marks: [{ y: 1991, label: "A NEW FAMILY" }] });
    badge(S, RECON);
  } });

}

/* ===================================================================================================== */
/* CHAPTER 2 · father's case, school, first jobs, the TV show                                              */
/* ===================================================================================================== */
if (has("c2a")) {

/* 1994: night in Los Angeles, a case grips the country */
scene({ id: "n94", a: 0, b: W("c2b", 0), bg: B.avenue(), cam: { from: [20, 8, 0.0], to: [-20, -8, 0.16] }, rays: false, grade: ["night", {}], light: [960, 760, 560, 360, "#9fb8ff", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    dimTo(S, t0, 0.55, 0.1, "#0a1226");
    S.layer(`<defs><radialGradient id="rgR"><stop offset="0" stop-color="#ff3a3a" stop-opacity=".75"/><stop offset="1" stop-color="#ff3a3a" stop-opacity="0"/></radialGradient><radialGradient id="rgB"><stop offset="0" stop-color="#3a6aff" stop-opacity=".75"/><stop offset="1" stop-color="#3a6aff" stop-opacity="0"/></radialGradient></defs><g data-p="rl"><ellipse cx="420" cy="620" rx="420" ry="300" fill="url(#rgR)" opacity="0"/></g><g data-p="bl"><ellipse cx="1500" cy="620" rx="420" ry="300" fill="url(#rgB)" opacity="0"/></g>`, 0.7);
    const rl = S.q("rl").firstElementChild, bl = S.q("bl").firstElementChild;
    for (let t = t0, i = 0; t < t1; t += 0.3, i++) { S.key(rl, "opacity", t, i % 2 ? 0 : 0.55, 0); S.key(bl, "opacity", t, i % 2 ? 0.55 : 0, 0); }
    C.fog(S, { y: 650, h: 220, color: "#6f86c0", op: 0.3, seed: 8, depth: 0.55, drift: 100 });
    S.layer(FG.leaves("L"), 1.7); S.layer(FG.leaves("R"), 1.75);
    DK.tag(S, "n94t", "LOS ANGELES · 1994", "A MURDER CASE GRIPS THE COUNTRY", 120, 330, t0 + 0.3, { w: 860 });
    DK.hud(S, "h94", { from: 1989, to: 1994, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 1989, label: "AGE 9" }, { y: 1994, label: "1994" }] });
  } });
card({ id: "oj", a: W("c2b", 0), b: W("s2", 0), year: 1994, seed: 11, kick: "THE CASE", lines: ["O. J. SIMPSON"], sub: "FAMOUS ATHLETE · CHARGED WITH TWO MURDERS", subSize: 30, size: 96, icon: ic.case, ix: 1470, iy: 560,
  hud: { from: 1994, to: 1994, marks: [{ y: 1994, label: "CHARGED" }] }, src: "SOURCE: BRITANNICA" });

/* the father joins the defense team */
DK.whip(D.W("s2", 0), 1);
scene({ id: "dadJoin", a: W("s2", 0), b: W("c2c", 0), bg: B.court(), cam: { from: [-30, 10, 0.0], to: [30, -6, 0.16] }, rays: [960, 300, Math.PI / 2], rayc: "#cfe0ff", grade: ["court", {}], light: [960, 760, 640, 380, "#ffd9a0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 5, depth: 0.55, drift: 80 });
    const dad = S.actor("dadJ", DAD, 560, 930, 1.1, { seed: 9, pivot: [560, 930] });
    dad.k("self", "--x", t0, -700, 0); dad.walk(t0 + 0.02, t1 - 0.2, 700, { arms: false, step: 0.3 });
    S.layer(PR.briefcase(0, 0), 0.9); const bc = S.q("pr"); S.key(bc, "--x", t0, -150, 0); S.key(bc, "--y", t0, 860, 0); S.key(bc, "--x", t0 + 0.02, 660, t1 - t0 - 0.22, "none");
    C.dust(S, { n: 14, seed: 31, box: [300, 200, 1300, 560], color: "#fff4d0", depth: 1.0, op: 0.5 });
    DK.tag(S, "djT", "YOUR FATHER JOINS", "THE O. J. SIMPSON DEFENSE TEAM", 1060, 330, D.W("s2", 4), { w: 780 });
    DK.hud(S, "hdj", { from: 1994, to: 1995, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 1994, label: "CHARGED" }, { y: 1995, label: "TRIAL" }] });
  } });
scene({ id: "dadFriend", a: W("c2c", 0), b: W("c2c2", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kid") }] }, cam: { from: [0, 0, 0.02], to: [-8, 4, 0.14] }, grade: ["office", { dark: 0.14 }], light: [960, 540, 520, 430, "#ffc88a", 0.34],
  build(S) {
    const t0 = S.t0, d = closeUp(S, "dadc", DAD, 960, 580, 540, { depth: 0.9, seed: 12, expr: "neutral" });
    d.face(t0 + 0.8, "happy", 0.4); d.look(t0, 8, 0, 0); d.look(t0 + 0.8, -6, 0, 0.5, "sine.inOut"); d.turn(t0 + 0.2, 3, 3, 0.7);
    C.dust(S, { n: 12, seed: 41, box: [200, 100, 1500, 800], color: "#ffd9a0", depth: 1.1, op: 0.4 });
    DK.tag(S, "frT", "ROBERT KARDASHIAN", "SIMPSON'S LONGTIME FRIEND", 120, 330, t0 + 0.4, { w: 720 });
  } });
card({ id: "team", a: W("c2c2", 0), b: W("c2d", 0), year: 1995, seed: 12, kick: "THE DEFENSE TEAM", lines: ["FOUR", "LAWYERS"], hi: 1, sub: "COCHRAN LATER LEADS THE TEAM", subSize: 30,
  icon: (S, cx, cy, t) => ic.roster(S, cx, cy, t, [["ROBERT KARDASHIAN", "YOUR FATHER", "#ffb84a"], ["F. LEE BAILEY", ""], ["ROBERT SHAPIRO", ""], ["JOHNNIE COCHRAN", "LATER LEADS THE TEAM"]], [t + 0.3, D.W("c2c2", 8), D.W("c2c2", 10), D.W("c2c2", 13)]),
  ix: 1400, iy: 520, src: "SOURCE: BRITANNICA · HISTORY.COM" });

/* January 1995: the trial begins; the nation watches */
scene({ id: "trial95", a: W("c2d", 0), b: W("c2d", 9), bg: B.court(), cam: { from: [-40, 8, 0.0], to: [50, -8, 0.14], ease: "power1.inOut" }, rays: [960, 300, Math.PI / 2], rayc: "#cfe0ff", grade: ["court", { dark: 0.14 }], light: [960, 760, 640, 380, "#ffd9a0", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(FG.heads(7, 8, 1120), 1.5);
    S.layer(`<g data-p="live"><g transform="translate(1700 130)"><rect x="-100" y="-34" width="200" height="64" rx="10" fill="#c4252d" ${st(6)}/><text y="14" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="40" fill="#fff" letter-spacing="6">LIVE</text></g></g>`, 0);
    S.pop("live", D.W("c2d", 9) - 1.2, 0.3);
    DK.tag(S, "t95", "LOS ANGELES · JANUARY 1995", "THE TRIAL BEGINS", 120, 330, t0 + 0.2, { w: 860 });
    DK.hud(S, "h95", { from: 1994, to: 1995, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 1994, label: "CHARGED" }, { y: 1995, label: "TRIAL" }] });
  } });
card({ id: "nation", a: W("c2d", 9), b: W("c2d2", 0), year: 1995, seed: 13, kick: "ON EVERY SCREEN", lines: ["THE NATION", "WATCHES"], hi: 1, icon: ic.news, ix: 1450, iy: 540, hud: { from: 1995, to: 1995, marks: [{ y: 1995, label: "TRIAL" }] }, badge: GRAPHIC });
card({ id: "jury", a: W("c2d2", 0), b: W("c2e", 0), year: 1995, seed: 14, kick: "THE JURY DELIBERATES", lines: ["LESS THAN", "4 HOURS"], hi: 1, icon: ic.clock, ix: 1440, iy: 540, src: "SOURCE: BRITANNICA" });
card({ id: "verdict", a: W("c2e", 0), b: W("c2e2", 0), year: 1995, seed: 15, kick: "OCTOBER 3, 1995", lines: ["THE VERDICT"], sub: "SIMPSON IS FOUND NOT GUILTY", subSize: 34, size: 100,
  icon: (S, cx, cy, t) => ic.stamp(S, cx, cy, D.W("c2e", 6), "NOT GUILTY", "OCT 3 · 1995"), ix: 1400, iy: 560,
  hud: { from: 1995, to: 1995, marks: [{ y: 1995, label: "VERDICT" }] }, src: "SOURCE: BRITANNICA · HISTORY.COM" });

/* age fourteen: the whole country argues, and you watch */
scene({ id: "age14", a: W("c2e2", 0), b: W("c2f", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kid") }] }, cam: { from: [0, 0, 0.02], to: [-8, 6, 0.15] }, grade: ["night", { dark: 0.2 }], light: [960, 540, 520, 430, "#9fc0ff", 0.4],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    const k = closeUp(S, "k14", KIMT, 960, 580, 540, { depth: 0.9, seed: 14, expr: "neutral" });
    k.look(t0, 10, 0, 0); k.look(t0 + 0.9, -10, 2, 0.5, "sine.inOut"); k.look(t0 + 2.2, 8, 0, 0.5, "sine.inOut"); k.turn(t0 + 0.2, 3, 2, 1.0); k.face(t0 + 1.2, "worried", 0.4);
    const gl = S.layer(`<g data-p="tvg"><ellipse cx="1500" cy="560" rx="520" ry="420" fill="#9fc0ff" opacity=".0"/></g>`, 0.4); void gl;
    const e = S.q("tvg").firstElementChild; for (let t = t0, i = 0; t < t1; t += 0.22, i++) S.key(e, "opacity", t, 0.1 + ((i * 7) % 5) * 0.045, 0);
    C.dust(S, { n: 12, seed: 41, box: [200, 100, 1500, 800], color: "#cfe0ff", depth: 1.1, op: 0.4 });
    DK.tag(S, "a14", "AGE 14 · 1995", "THE COUNTRY ARGUES ABOUT YOUR FATHER'S TRIAL", 120, 330, t0 + 0.3, { w: 1100 });
    DK.hud(S, "h14", { from: 1980, to: 1995, t0, t1: Math.min(t1 - 0.05, t0 + 1.8), marks: [{ y: 1980, label: "BORN" }, { y: 1995, label: "AGE 14" }] });
    badge(S, RECON);
  } });

/* 1998 graduation */
card({ id: "grad", a: W("c2f", 0), b: W("c2g", 0), year: 1998, seed: 16, kick: "HIGH SCHOOL", lines: ["GRADUATION", "1998"], hi: 1, icon: ic.cap, ix: 1440, iy: 540, hud: { from: 1995, to: 1998, marks: [{ y: 1995, label: "AGE 14" }, { y: 1998, label: "GRADUATION" }] } });

/* first jobs: a clothing store, then styling clients */
scene({ id: "jobs", a: W("c2g", 0), b: W("c2h", 0), bg: B.boutique(), cam: { from: [-30, 10, 0.0], to: [30, -8, 0.16] }, rays: [960, 300, Math.PI / 2], rayc: "#fff4e4", grade: ["glam", { dark: 0.1 }], light: [700, 780, 520, 420, "#fff1d8", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tc = D.W("c2g", 9), ts = D.W("c2g", 12);
    const k = S.actor("kimJ", KIM00, 640, 930, 1.06, { seed: 81, expr: "neutral", pivot: [640, 930] });
    k.arm("R", t0 + 0.4, -100, -60, 0.4, "back.out(1.3)"); k.arm("R", t0 + 1.2, -50, -20, 0.5, "sine.inOut"); k.face(tc, "happy", 0.3);
    k.walk(ts - 0.1, ts + 1.2, 260, { arms: false, step: 0.3 });
    const cl = S.actor("cli", SISB, 1480, 930, 1.0, { seed: 82, expr: "happy", pivot: [1480, 930] }); cl.hiddenUntil(ts - 0.3); cl.k("self", "--x", ts - 0.3, 180, 0); cl.k("self", "--x", ts - 0.3, 0, 0.6, "power3.out");
    DK.tag(S, "jT", "FIRST JOBS", "A CLOTHING STORE · THEN STYLING", 1130, 330, D.W("c2g", 5), { w: 760 });
    DK.hud(S, "hj", { from: 1998, to: 2000, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 1998, label: "GRADUATION" }] });
    badge(S, RECON);
  } });
/* 2000: the first marriage, ending in 2004 (cartoon: the couple, then the groom walks away) */
scene({ id: "dthomas", a: W("c2h", 0), b: W("c2i", 0), bg: B.living(), cam: { from: [-30, 0, 0.0], to: [26, -6, 0.14] }, rays: [1500, -40, 1.95], rayc: "#ffe0a8", grade: ["home", {}], light: [800, 700, 640, 380, "#ffe0b0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1, te = NW("c2h", 7);
    const [br, gr] = couple(S, "c2h", null, Object.assign({}, KIM00, { top: "#f6f1e8", pants: "#f6f1e8" }), GROOM3, 700, 930, 1.0, NW("c2h", 3), 141);
    br.face(te, "sad", 0.4); gr.face(te, "neutral", 0.3); gr.walk(te + 0.1, Math.max(te + 0.6, t1 - 0.25), 520, { arms: false, step: 0.3 });
    S.layer(PR.heart("hbk", 1500, 520), 1.1); S.pop("hbk", NW("c2h", 8), 0.4); S.key("hbk", "--r", te + 0.5, 14, 0.5, "sine.inOut"); S.key("hbk", "--y", te + 0.6, 120, 0.9, "power2.in");
    DK.tag(S, "dtTag", "2000 · MARRIAGE", "DAMON THOMAS", 120, 330, t0 + 0.3, { w: 620 });
    DK.tag(S, "dtTag2", "2004 · IT ENDS", "THE MARRIAGE IS OVER", 1180, 330, te, { w: 680 });
    DK.hud(S, "hdt", { from: 2000, to: 2004, t0, t1: Math.min(t1 - 0.05, t0 + 2.4), marks: [{ y: 2000, label: "MARRIED" }, { y: 2004, label: "ENDS" }] });
  } });
/* 2003: personal stylist for the singer Brandy */
scene({ id: "brandy", a: W("c2i", 0), b: W("c2j", 0), bg: B.boutique(), cam: { from: [0, 12, 0.0], to: [0, -6, 0.14] }, rays: [960, 200, Math.PI / 2], rayc: "#fff4e4", grade: ["glam", {}], light: [800, 760, 560, 420, "#fff1d8", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1, ts = NW("c2i", 5), tb = NW("c2i", 9);
    const you = S.actor("kBd", KIM00, 620, 930, 1.1, { seed: 151, expr: "happy", pivot: [620, 930] });
    you.talkWords("c2i", t0); you.arm("L", ts, 140, 22, 0.45, "back.out(1.6)"); you.hop(ts, 22, 0.36);
    const sg = S.actor("sgB", BRANDYS, 1250, 930, 1.1, { seed: 152, expr: "happy", depth: 1.0, pivot: [1250, 930] });
    sg.hiddenUntil(tb - 0.1); sg.k("self", "--x", tb - 0.1, 260, 0); sg.k("self", "--x", tb - 0.05, 0, 0.55, "power3.out"); sg.face(tb + 0.5, "laugh", 0.3); sg.arm("R", tb + 0.4, -150, -30, 0.4, "back.out(1.6)");
    for (let i = 0; i < 4; i++) { S.layer(PR.sparkle("bs" + i, 1000 + i * 150, 330 + (i % 2) * 90), 1.2); S.pop("bs" + i, tb + 0.3 + i * 0.1, 0.32); }
    DK.tag(S, "brdTag", "BY 2003 · PERSONAL STYLIST", "FOR THE SINGER BRANDY", 120, 330, t0 + 0.2, { w: 820 });
    DK.hud(S, "hbd", { from: 2000, to: 2003, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 2000, label: "2000" }, { y: 2003, label: "STYLIST" }] });
  } });
/* 2006: Paris Hilton, and the DASH boutique with your sisters */
scene({ id: "dash", a: W("c2j", 0), b: W("c2k", 0), bg: B.boutique(), cam: { from: [20, 8, 0.0], to: [-20, -8, 0.16] }, rays: [960, 300, Math.PI / 2], rayc: "#fff4e4", grade: ["glam", {}], light: [960, 780, 640, 420, "#fff1d8", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1, td = D.W("c2j", 9);
    const L = [[SISA, 560, 1.0, "sA"], [KIM00, 960, 1.04, "kD"], [SISB, 1360, 1.0, "sB"]];
    L.forEach(([sp, x, sc, id], i) => { const a = S.actor(id, sp, x, 940, sc, { seed: 91 + i, expr: "happy", pivot: [x, 940] }); if (i !== 1) { a.k("self", "--y", td - 0.1, 90, 0); a.k("self", "--y", td + 0.1 * i, 0, 0.4, "power3.out"); a.hiddenUntil(td - 0.1); } else { a.face(td, "laugh", 0.3); a.arm("R", td + 0.5, -150, -20, 0.4, "back.out(1.5)"); } });
    S.layer(`<g data-p="dsign"><g transform="translate(1260 330)"><rect x="-210" y="-70" width="420" height="120" rx="14" fill="#2a1820" ${st(8)}/><rect x="-194" y="-54" width="388" height="88" rx="8" fill="none" stroke="#ffb84a" stroke-width="4"/><text y="22" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="86" fill="#ffb84a" letter-spacing="14">DASH</text></g></g>`, 1.0);
    S.pop("dsign", D.W("c2j", 11), 0.4); confetti(S, td + 0.2, 16, 5);
    DK.tag(S, "dT", "2006 · PARIS HILTON", "YOU OPEN A BOUTIQUE: DASH", 120, 330, D.W("c2j", 0) + 0.3, { w: 780 });
    DK.hud(S, "hd", { from: 2003, to: 2006, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 2003, label: "STYLIST" }, { y: 2006, label: "DASH" }] });
    badge(S, RECON);
  } });
scene({ id: "mgr", a: W("c2k", 0), b: W("c2k2", 0), bg: B.living(), cam: { from: [30, 0, 0.0], to: [-20, 0, 0.12] }, grade: ["home", { tint: "#e0a870", dark: 0.12 }], light: [960, 780, 700, 400, "#ffd9a8", 0.32],
  build(S) {
    const t0 = S.t0, tm = D.W("c2k", 4);
    const kr = S.actor("kris", KRIS, 1180, 940, 1.1, { seed: 101, expr: "happy", pivot: [1180, 940] }); kr.arm("R", t0 + 0.4, -120, -50, 0.4, "back.out(1.4)");
    const kk = S.actor("kimM", KIM00, 720, 940, 1.04, { seed: 102, expr: "neutral", pivot: [720, 940] }); kk.face(tm, "happy", 0.4);
    DK.tag(S, "mT", "KRIS JENNER", "LATER BECOMES YOUR MANAGER", 1040, 330, tm - 0.4, { w: 780 });
    DK.hud(S, "hm", { from: 2006, to: 2007, t0, t1: Math.min(S.t1 - 0.05, t0 + 1.2), marks: [{ y: 2006, label: "DASH" }] });
    badge(S, RECON);
  } });
scene({ id: "age26", a: W("c2k2", 0), b: W("s5", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kim07") }] }, cam: { from: [0, 0, 0.02], to: [0, 0, 0.14] }, grade: ["studio", { tint: "#d2a8d8", ta: 0.28 }], light: [940, 540, 520, 430, "#ffe2c0", 0.42],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tf = D.W("c2k2", 8);
    S.layer(C.rays(1750, -40, 2.05, 1200, 0.3, "#fff1c4", 0.34), 0.4);
    const kim = closeUp(S, "k26", KIM07, 760, 580, 520, { depth: 0.9, seed: 41, expr: "neutral" });
    kim.look(t0, 10, 0, 0); kim.look(t0 + 0.8, -4, 0, 0.4, "sine.inOut"); kim.turn(t0 + 0.2, -3, -3, 0.5); kim.face(tf, "surprised", 0.35);
    TX(S, "a26", 1210, 470, 36, "#ffb84a", "YOU ARE", { ls: 12 }); TX(S, "n26", 1210, 650, 230, "#fff", "26", { ls: 4 }); TX(S, "y26", 1210, 740, 34, "#cfe0ff", "YEARS OLD", { ls: 10, w: 700 });
    appear(S, "a26", D.W("c2k2", 1), 0.3, true); S.pop("n26", D.W("c2k2", 2), 0.35); appear(S, "y26", D.W("c2k2", 3), 0.3, true);
    for (let t = tf; t < t1 - 0.1; t += 0.3) DK.flash(t, 0.35, 0.12);
    C.dust(S, { n: 14, seed: 61, box: [200, 100, 1500, 800], color: "#fff1c4", depth: 1.1, op: 0.4 });
    DK.hud(S, "h26", { from: 1980, to: 2007, t0, t1: Math.min(t1 - 0.05, t0 + 2.2), marks: [{ y: 1980, label: "BORN" }, { y: 2007, label: "TV" }] });
    badge(S, RECON);
  } });

/* 2007: cameras move in */
DK.whip(D.W("s5", 0), 1);
scene({ id: "crew", a: W("s5", 0), b: W("c2l", 0), bg: B.living(), cam: { from: [60, 0, 0.0], to: [-30, 0, 0.18] }, rays: [1160, 340, Math.PI / 2 + 0.2], rayc: "#fff1c4", grade: ["glam", { tint: "#d0a070", ta: 0.3 }], light: [640, 780, 520, 420, "#ffe2c0", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    C.fog(S, { y: 700, h: 200, color: "#fff1d0", op: 0.18, seed: 19, depth: 0.55, drift: 80 });
    const you = S.actor("kimL", KIM07, 640, 900, 0.95, { seed: 41, expr: "neutral", pivot: [640, 900] });
    const crew = S.actor("crew", CREW, 1500, 800, 0.75, { seed: 42, idle: false, pivot: [1500, 800], depth: 0.7 });
    crew.k("self", "--x", t0, 520, 0); crew.walk(t0 + 0.05, t1 - 0.05, -900, { arms: false, step: 0.28 }); crew.face(t0, "neutral", 0);
    crew.k("self", "--s", t0, 0.8, 0); crew.k("self", "--s", t0 + 0.05, 1.3, t1 - t0 - 0.1, "power1.in"); crew.k("self", "--y", t0 + 0.05, 120, t1 - t0 - 0.1, "power1.in");
    crew.arm("R", t0 + 0.05, -95, -105, 0.2); crew.arm("L", t0 + 0.05, 70, 70, 0.2);
    you.turn(t0 + 0.15, -10, -4, 0.4); you.look(t0 + 0.15, 12, 0, 0.3); you.face(t0 + 0.3, "surprised", 0.3); you.arm("L", t0 + 0.5, 70, 40, 0.4, "back.out(1.3)");
    S.layer(`<g data-p="fcam">${FG.cam()}</g>`, 1.55); S.key("fcam", "--x", t0, 600, 0); S.key("fcam", "--x", t0, 0, 0.7, "power3.out");
    S.layer(`<circle id="recdot" cx="1780" cy="110" r="18" fill="#e22"/><text x="1740" y="122" text-anchor="end" font-family='${FONT}' font-weight="800" font-size="40" fill="#fff" stroke="#000" stroke-width="2">REC</text>`, 0);
    const rd = S.el.querySelector("#recdot"); for (let t = t0; t < t1; t += 0.4) S.key(rd, "opacity", t, Math.round((t - t0) / 0.4) % 2 ? 0.15 : 1, 0);
    DK.tag(S, "crewTag", "CAMERAS MOVE IN", "2007", 120, 330, D.W("s5", 2) + 0.1, { w: 640 });
    DK.hud(S, "h10", { from: 2007, to: 2007, t0, t1, marks: [{ y: 2007, label: "TV" }] });
    badge(S, RECON);
  } });
/* October 2007: the premiere, watched at home (cartoon: three of them on the couch, the TV lights up) */
scene({ id: "premiere", a: W("c2l", 0), b: W("c2m", 0), bg: B.living(), cam: { from: [20, 0, 0.0], to: [-24, -6, 0.14] }, rays: [1500, -40, 1.95], rayc: "#cfe0ff", grade: ["studio", {}], light: [1300, 600, 640, 380, "#cfe0ff", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tp = NW("c2l", 5);
    S.layer(`<g data-p="tvs"><g transform="translate(1390 560)"><rect x="-320" y="-200" width="640" height="400" rx="24" fill="#16161e" ${st(9)}/><rect x="-292" y="-172" width="584" height="344" rx="12" fill="#2a3a7a"/>
      <text y="30" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="150" fill="#fff" stroke="#05070c" stroke-width="8" paint-order="stroke">E!</text>
      <text y="100" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="26" fill="#ffb84a" letter-spacing="3">KEEPING UP WITH THE KARDASHIANS</text></g></g>`, 1.0);
    S.pop("tvs", tp - 0.2, 0.5);
    const cast = [[KIM07, 420, "k07"], [SISA, 640, "sa"], [SISB, 860, "sb"]];
    cast.forEach(([sp, x, id], i) => { const a = S.actor(id, sp, x, 930, 1.0, { seed: 161 + i, expr: "neutral", pivot: [x, 930] }); a.look(t0, 9, -2, 0); a.face(tp, "laugh", 0.3); a.arm(i % 2 ? "R" : "L", tp + 0.1, i % 2 ? -150 : 150, i % 2 ? -30 : 30, 0.4, "back.out(1.6)"); a.hop(tp + 0.1 + i * 0.12, 20, 0.36); });
    for (let i = 0; i < 4; i++) { S.layer(PR.sparkle("pv" + i, 1100 + i * 190, 270 + (i % 2) * 70, "#ffb84a"), 1.2); S.pop("pv" + i, tp + 0.2 + i * 0.12, 0.32); }
    confetti(S, tp, 18, 19);
    DK.tag(S, "pvTag", "OCTOBER 2007 · E!", "KEEPING UP WITH THE KARDASHIANS PREMIERES", 120, 330, t0 + 0.3, { w: 1000 });
    DK.hud(S, "hpv", { from: 2007, to: 2007, t0, t1: Math.min(t1 - 0.05, t0 + 1.0), marks: [{ y: 2007, label: "TV" }] });
  } });
card({ id: "run", a: W("c2m", 0), b: W("c2m2", 0), year: 2021, seed: 20, kick: "THE SHOW RUNS FOR", lines: ["14 YEARS"], hi: 0, size: 130, sub: "2007 – 2021", subSize: 34, hudDur: 2.6,
  hud: { from: 2007, to: 2021, marks: [{ y: 2007, label: "PREMIERE" }, { y: 2021, label: "FINALE" }] }, src: "SOURCES: WIKIPEDIA · HISTORY.COM" });
/* the final episode: the cast cheers while the episode counter runs up to 294 */
scene({ id: "eps", a: W("c2m2", 0), b: W("c2n", 0), bg: B.stage(), cam: { from: [-20, 0, 0.0], to: [20, -6, 0.1] }, rays: [960, 200, Math.PI / 2], rayc: "#ffe0f6", grade: ["studio", {}], light: [900, 780, 760, 380, "#ffe0f6", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1, ta = D.W("c2m2", 7), tb = Math.max(ta + 1.0, D.W("c2m2", 12) - 0.05);
    S.layer(PR.spot(260, 330, 10), 0.8); S.layer(PR.spot(1660, 330, 170), 0.8);
    [[KIM07, 330, "e1"], [SISA, 540, "e2"], [SISB, 750, "e3"]].forEach(([sp, x, id], i) => { const a = S.actor(id, sp, x, 930, 1.0, { seed: 191 + i, expr: "happy", pivot: [x, 930] }); a.look(t0, 9, -2, 0); a.arm(i % 2 ? "R" : "L", ta, i % 2 ? -150 : 150, i % 2 ? -30 : 30, 0.4, "back.out(1.6)"); a.hop(tb + 0.1 + i * 0.12, 22, 0.38); a.face(tb + 0.1, "laugh", 0.3); });
S.layer(`<g data-p="epb"><g transform="translate(1440 560)"><rect x="-300" y="-190" width="600" height="380" rx="26" fill="#f3eee2" ${st(8)}/><text y="-110" text-anchor="middle" font-family='${FONT}' font-weight="700" font-size="30" fill="#7a5a2a" letter-spacing="10">EPISODES</text></g></g>`, 1.0);
    S.pop("epb", ta - 0.3, 0.4);
    counter(S, "ep", 1440, 640, 200, "#c4252d", range(0, 294, 14).map(String), ta, tb, { sw: 0, depth: 1.05 });
    confetti(S, tb, 22, 21);
    DK.tag(S, "epTag", "THE FINAL EPISODE", "JUNE 2021", 120, 330, t0 + 0.3, { w: 620 });
    DK.hud(S, "hep", { from: 2020, to: 2021, t0, t1: Math.min(t1 - 0.05, t0 + 1.0), marks: [{ y: 2021, label: "FINALE" }] });
  } });

/* the show is on air */
DK.whip(D.W("c2n", 0), -1);
scene({ id: "onair", a: W("c2n", 0), b: "end", bg: B.stage(), cam: { from: [0, 0, 0.16], to: [0, -6, 0.02], ease: "power2.out" }, rays: false, grade: ["studio", {}], light: [960, 760, 520, 380, "#ffe0f6", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(PR.spot(300, 330, 10), 0.8); S.layer(PR.spot(1620, 330, 170), 0.8);
    S.layer(FX.cone(330, 330, 700, 900, 1220, 900, 370, 340, "#ffd9f0", 0.38), 0.7); S.layer(FX.cone(1590, 330, 1220, 900, 700, 900, 1550, 340, "#ffd9f0", 0.34), 0.7);
    C.fog(S, { y: 760, h: 240, color: "#c08ae8", op: 0.28, seed: 23, depth: 0.55, drift: 120 });
    const you = S.actor("kimT", KIM07, 960, 930, 1.12, { seed: 51, expr: "smirk", pivot: [960, 930] });
    you.arm("R", t0 + 0.25, -150, -20, 0.35, "back.out(1.5)"); you.face(t0 + 0.3, "laugh", 0.3);
    for (let t = t0 + 0.6, i = 0; t < t1 - 0.15; t += 0.28, i++) you.arm("R", t, i % 2 ? -150 : -120, i % 2 ? -20 : -55, 0.28, "sine.inOut");
    S.layer(FG.heads(5, 8, 1150), 1.45); S.layer(`<g transform="translate(1500 700) scale(1.6)">${FG.cam()}</g>`, 1.6);
    S.layer(`<g data-p="onr"><g transform="translate(1700 130)"><rect x="-120" y="-34" width="240" height="64" rx="10" fill="#c4252d" ${st(6)}/><text y="14" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="38" fill="#fff" letter-spacing="6">ON AIR</text></g></g>`, 0);
    S.pop("onr", t0 + 0.4, 0.3);
    DK.tag(S, "tvTag", "PRIVATE LIFE", "BECOMES PUBLIC ENTERTAINMENT", 120, 330, t0 + 0.2, { w: 820 });
    DK.hud(S, "h12", { from: 2007, to: 2007, t0, t1, marks: [{ y: 2007, label: "TV" }] });
    badge(S, RECON);
  } });

}

/* ===================================================================================================== */
/* CHAPTER 3 · from a TV name to a brand: 2011-2025                                                        */
/* ===================================================================================================== */
if (has("c3a")) {

ic.bag = (S, cx, cy, t) => {
  S.layer(P("icn", cx, cy, `<g data-p="bag"><path d="M-170 -80H170L200 250H-200Z" fill="#f3eee2" ${O(9)}/><path d="M-90 -80V-150C-90 -230 90 -230 90 -150V-80" fill="none" ${O(9)}/>
    <text y="40" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="46" fill="#2a1820" letter-spacing="6">YOUR NAME</text><path d="M-110 80H110" stroke="#c9a24a" stroke-width="6"/><text y="150" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="62" fill="#c4252d" letter-spacing="6">BRAND</text></g>`), 1.0);
  S.pop("bag", t, 0.5); S.key("bag", "--r", t + 0.6, -4, 1.0, "sine.inOut"); S.key("bag", "--r", t + 1.6, 3, 1.2, "sine.inOut");
};

/* 2007-2011: the show turns a name into a brand (cartoon: the star on stage, a shopping bag with her name rises beside her) */
scene({ id: "brand", a: 0, b: W("c3a2", 0), bg: B.stage(), cam: { from: [-20, 0, 0.0], to: [20, -6, 0.1] }, rays: [960, 200, Math.PI / 2], rayc: "#ffe0f6", grade: ["studio", {}], light: [960, 780, 760, 380, "#ffe0f6", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tb = NW("c3a", 8);
    S.layer(PR.spot(260, 330, 10), 0.8); S.layer(PR.spot(1660, 330, 170), 0.8);
    const you = S.actor("kB", KIM07, 640, 930, 1.1, { seed: 71, expr: "happy", pivot: [640, 930] });
    you.arm("L", t0 + 0.5, 140, 24, 0.5, "back.out(1.6)"); you.talkWords("c3a", t0);
    you.arm("R", tb, -150, -30, 0.4, "back.out(1.6)"); you.hop(tb, 26, 0.4); you.face(tb, "laugh", 0.3);
    ic.bag(S, 1430, 560, tb - 0.1);
    for (let i = 0; i < 4; i++) { S.layer(PR.sparkle("sp" + i, 1180 + i * 150, 330 + (i % 2) * 90), 1.2); S.pop("sp" + i, tb + 0.2 + i * 0.12, 0.35); }
    confetti(S, tb + 0.2, 16, 7);
    DK.tag(S, "brTag", "THE SHOW TURNS", "YOUR NAME INTO A BRAND", 120, 330, t0 + 0.3, { w: 760 });
    DK.hud(S, "hbr", { from: 2007, to: 2011, t0, t1: Math.min(t1 - 0.05, t0 + 1.6), marks: [{ y: 2007, label: "TV" }, { y: 2011, label: "BRAND" }] });
  } });
/* 2011 marriage, 2013 first child */
scene({ id: "humphries", a: W("c3a2", 0), b: W("c3b", 0), bg: B.garden(), cam: { from: [30, 0, 0.0], to: [-20, -8, 0.16] }, rays: [1500, -40, 1.95], rayc: "#fff0c0", grade: ["garden", {}], light: [900, 700, 640, 380, "#fff0c0", 0.3],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tc = NW("c3a2", 6);
    C.fog(S, { y: 700, h: 200, color: "#fff1d0", op: 0.28, seed: 16, depth: 0.5, drift: 80 });
    couple(S, "c3a2", null, BRIDE, GROOM1, 560, 900, 0.95, t0 + 0.4, 81);
    const baby = S.actor("cpK", BABY2, 1500, 890, 1.05, { seed: 84, expr: "happy", depth: 1.0, pivot: [1500, 890] });
    baby.hiddenUntil(tc); baby.k("self", "--y", tc, 90, 0); baby.k("self", "--y", tc + 0.01, 0, 0.45, "back.out(1.6)"); baby.face(tc + 0.4, "laugh", 0.3);
    S.layer(PR.heart("hrt2", 1500, 520), 1.1); S.pop("hrt2", tc + 0.35, 0.5); S.key("hrt2", "--y", tc + 0.85, -40, 0.9, "sine.out");
    confetti(S, tc, 18, 12);
    S.layer(FG.leaves("L"), 1.7);
    DK.tag(S, "hu1", "2011 · MARRIAGE", "KRIS HUMPHRIES", 120, 330, t0 + 0.4, { w: 700 });
    DK.tag(S, "hu2", "2013 · YOUR FIRST CHILD", "A BABY IS BORN", 1180, 330, tc, { w: 700 });
    DK.hud(S, "hhu", { from: 2011, to: 2013, t0, t1: Math.min(t1 - 0.05, t0 + 1.5), marks: [{ y: 2011, label: "MARRIAGE" }, { y: 2013, label: "CHILD" }] });
  } });
/* 2014: second marriage and the mobile game */
scene({ id: "kanye", a: W("c3b", 0), b: W("c3d", 0), bg: B.living(), cam: { from: [-30, 0, 0.0], to: [30, -8, 0.14] }, rays: [1500, -40, 1.95], rayc: "#ffe0a8", grade: ["home", {}], light: [900, 700, 640, 380, "#ffe0b0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tg = NW("c3b", 8);
    couple(S, "c3b", null, BRIDE, GROOM2, 520, 930, 1.0, NW("c3b", 3), 91);
    ic.phone(S, 1440, 540, tg);
    for (let i = 0; i < 3; i++) { S.layer(PR.sparkle("kp" + i, 1250 + i * 190, 280 + (i % 2) * 60, "#ffb84a"), 1.2); S.pop("kp" + i, tg + 0.3 + i * 0.15, 0.35); }
    DK.tag(S, "kyTag", "2014 · MARRIAGE", "KANYE WEST", 120, 330, NW("c3b", 3) - 0.1, { w: 760 });
    DK.hud(S, "hky", { from: 2013, to: 2014, t0, t1: Math.min(t1 - 0.05, t0 + 1.2), marks: [{ y: 2013, label: "2013" }, { y: 2014, label: "2014" }] });
  } });
/* 2017: KKW Beauty */
scene({ id: "kkw", a: W("c3d", 0), b: W("c3e", 0), bg: B.boutique(), cam: { from: [0, 10, 0.0], to: [0, -6, 0.14] }, rays: [960, 200, Math.PI / 2], rayc: "#fff4e4", grade: ["glam", {}], light: [700, 760, 560, 420, "#fff1d8", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tl = NW("c3d", 3);
    const you = S.actor("kK", KIM25, 600, 930, 1.1, { seed: 95, expr: "happy", pivot: [600, 930] });
    you.arm("L", t0 + 0.3, 140, 22, 0.45, "back.out(1.6)"); you.arm("R", t0 + 0.3, -150, -24, 0.45, "back.out(1.6)"); you.talkWords("c3d", t0); you.hop(tl, 24, 0.38);
    ic.beauty(S, 1440, 560, tl);
    for (let i = 0; i < 4; i++) { S.layer(PR.sparkle("kk" + i, 1180 + i * 140, 320 + (i % 2) * 80), 1.2); S.pop("kk" + i, tl + 0.15 + i * 0.1, 0.32); }
    DK.tag(S, "kkTag", "2017 · YOU LAUNCH", "KKW BEAUTY", 120, 330, t0 + 0.2, { w: 620 });
    DK.hud(S, "hkk", { from: 2014, to: 2017, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 2014, label: "2014" }, { y: 2017, label: "KKW" }] });
  } });


/* your father's world of courtrooms never leaves you */
scene({ id: "court2", a: W("c3e", 0), b: W("c3f", 0), bg: B.court(), cam: { from: [20, 6, 0.0], to: [-20, -6, 0.14] }, rays: [960, 300, Math.PI / 2], rayc: "#cfe0ff", grade: ["court", {}], light: [960, 760, 640, 380, "#ffd9a0", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 5, depth: 0.55, drift: 80 });
    const dd = S.actor("dadG", DAD, 620, 900, 0.9, { seed: 9, expr: "neutral", pivot: [620, 900], depth: 0.8 });
    const kk = S.actor("kimC", KIM25, 1130, 940, 1.08, { seed: 111, expr: "neutral", pivot: [1130, 940] });
    kk.k("self", "--x", t0, 480, 0); kk.walk(t0 + 0.05, t1 - 0.2, -480, { arms: false, step: 0.3 }); 
    S.layer(PR.briefcase(0, 0), 0.9); const bc = S.q("pr"); S.key(bc, "--x", t0, 800, 0); S.key(bc, "--y", t0, 900, 0); S.key(bc, "--x", t0 + 0.02, 330, t1 - t0 - 0.22, "none");
    DK.tag(S, "c2T", "YOUR FATHER'S WORLD", "OF COURTROOMS NEVER LEAVES YOU", 120, 330, t0 + 0.3, { w: 860 });
    DK.hud(S, "hc2", { from: 2017, to: 2018, t0, t1: Math.min(t1 - 0.05, t0 + 1.2), marks: [{ y: 2017, label: "KKW" }] });
    badge(S, RECON);
  } });
/* 2018: the commutation (cartoon: bars fade, Alice Johnson walks to Kim) */
scene({ id: "johnson", a: W("c3f", 0), b: W("c3h", 0), bg: B.court(), cam: { from: [20, 6, 0.0], to: [-20, -6, 0.12] }, rays: [960, 300, Math.PI / 2], rayc: "#cfe0ff", grade: ["court", {}], light: [960, 760, 640, 380, "#ffd9a0", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tc = NW("c3f", 7), tw = Math.min(NW("c3f", 12), t1 - 2.0);
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 7, depth: 0.55, drift: 80 });
    const you = S.actor("kJ", KIM25, 420, 940, 1.08, { seed: 171, expr: "determined", pivot: [420, 940] });
    you.talkWords("c3f", t0); you.arm("R", tc, -150, -30, 0.4, "back.out(1.6)");
    const al = S.actor("alJ", JOHNSONS, 1250, 940, 1.08, { seed: 172, expr: "sad", depth: 0.95, pivot: [1250, 940] });
    al.face(tc + 0.3, "happy", 0.4); al.walk(tw, t1 - 0.3, -430, { arms: false, step: 0.3 }); al.face(t1 - 1.4, "laugh", 0.3);
    const bars = S.layer(`<g fill="#07050b" opacity=".92">${[1150, 1250, 1350, 1450, 1550].map((x) => `<rect x="${x - 20}" y="320" width="40" height="680"/>`).join("")}<rect x="1110" y="320" width="480" height="34"/><rect x="1110" y="950" width="480" height="40"/></g>`, 1.0); S.key(bars, "opacity", t0, 1, 0); S.key(bars, "opacity", tc + 0.2, 0, 0.6, "power1.in");
    ic.doc(S, 1560, 500, tc);
    S.layer(PR.heart("hj", 840, 420), 1.1); S.pop("hj", t1 - 1.2, 0.5); S.key("hj", "--y", t1 - 0.7, -40, 0.9, "sine.out");
    DK.tag(S, "jnTag", "2018 · PRESIDENTIAL COMMUTATION", "ALICE MARIE JOHNSON · LIFE SENTENCE", 120, 330, t0 + 0.3, { w: 1000 });
    TX(S, "src", 140, 850, 28, "#e8eef9", "SOURCE: HISTORY.COM · BRITANNICA", { w: 700, ls: 2, sw: 5 }); appear(S, "src", t0 + 0.8, 0.3);
    DK.hud(S, "hjn", { from: 2017, to: 2018, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 2017, label: "KKW" }, { y: 2018, label: "2018" }] });
  } });
/* 2019: SKIMS, mother of four (cartoon boutique: four children walk in one by one) */
scene({ id: "skims19", a: W("c3h", 0), b: W("c3g", 0), bg: B.boutique(), cam: { from: [0, 14, 0.0], to: [0, -8, 0.14] }, rays: [960, 200, Math.PI / 2], rayc: "#fff4e4", grade: ["glam", {}], light: [700, 760, 560, 420, "#fff1d8", 0.34],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tl = NW("c3h", 4);
    const you = S.actor("kS", KIM25, 520, 930, 1.1, { seed: 101, expr: "happy", pivot: [520, 930] });
    you.arm("L", t0 + 0.3, 140, 22, 0.45, "back.out(1.6)"); you.talkWords("c3h", t0); you.hop(tl, 22, 0.36);
    const kids = [[KID, 960], [KID2, 1180], [KID3, 1400], [BABY2, 1620]];
    kids.forEach(([sp, x], i) => {
      const t = Math.min(NW("c3h", 12 + Math.min(i, 3)), t1 - 0.9) + (i >= 3 ? 0.0 : 0);
      const a = S.actor("kd" + i, sp, x, 905, sp.build === "baby" ? 0.9 : 0.95, { seed: 110 + i, expr: "happy", depth: 1.0, pivot: [x, 905] });
      a.hiddenUntil(t - 0.02); a.k("self", "--y", t - 0.02, 110, 0); a.k("self", "--y", t, 0, 0.4, "back.out(1.6)"); a.face(t + 0.3, "laugh", 0.3);
    });
    const tmom = Math.min(NW("c3h", 13), t1 - 0.9);
    S.layer(PR.heart("hk", 1290, 400), 1.1); S.pop("hk", tmom + 0.2, 0.5); S.key("hk", "--y", tmom + 0.7, -40, 0.9, "sine.out");
    confetti(S, tmom, 18, 14);
    DK.tag(S, "s19Tag", "2019 · YOU LAUNCH SKIMS", "A SHAPEWEAR BRAND", 120, 330, t0 + 0.2, { w: 700 });
    DK.hud(S, "h19", { from: 2018, to: 2019, t0, t1: Math.min(t1 - 0.05, t0 + 1.2), marks: [{ y: 2018, label: "2018" }, { y: 2019, label: "SKIMS" }] });
  } });

/* 2020: the documentary crew films Kim at work */
scene({ id: "justice", a: W("c3g", 0), b: W("c3i", 0), bg: B.office(), cam: { from: [-30, 4, 0.0], to: [26, -8, 0.14] }, rays: [1500, -40, 1.95], rayc: "#ffe0a8", grade: ["office", {}], light: [700, 780, 600, 400, "#ffe0b0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1, td = NW("c3g", 3), tp = NW("c3g", 6);
    const you = S.actor("kJu", KIM25, 520, 940, 1.08, { seed: 181, expr: "determined", pivot: [520, 940] });
    you.talkWords("c3g", t0); you.arm("R", td, -140, -30, 0.4, "back.out(1.6)");
    const cr = S.actor("crJ", CREW, 1100, 940, 1.05, { seed: 182, expr: "neutral", depth: 1.0, pivot: [1100, 940] });
    cr.hiddenUntil(td - 0.1); cr.k("self", "--x", td - 0.1, 220, 0); cr.k("self", "--x", td - 0.05, 0, 0.5, "power3.out"); cr.look(td + 0.5, -9, 0, 0.2);
    S.layer(PR.camera("cam", 1000, 700), 1.05); S.pop("cam", td + 0.2, 0.4);
    ic.clap(S, 1560, 560, tp);
    DK.tag(S, "juTag", "2020 · DOCUMENTARY", "THE JUSTICE PROJECT · CRIMINAL JUSTICE REFORM", 120, 330, t0 + 0.3, { w: 1000 });
    DK.hud(S, "hju", { from: 2019, to: 2020, t0, t1: Math.min(t1 - 0.05, t0 + 1.2), marks: [{ y: 2019, label: "SKIMS" }, { y: 2020, label: "2020" }] });
  } });
/* 2021: Forbes - cartoon office, a BILLIONAIRE stamp lands, coins rain */
scene({ id: "forbes", a: W("c3i", 0), b: W("c3j", 0), bg: B.office(), cam: { from: [-30, 4, 0.0], to: [26, -8, 0.14] }, rays: [1500, -40, 1.95], rayc: "#ffe0a8", grade: ["office", {}], light: [700, 780, 600, 400, "#ffe0b0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1, ts = NW("c3i", 5);
    const you = S.actor("kF", KIM25, 620, 940, 1.08, { seed: 121, expr: "neutral", pivot: [620, 940] });
    you.talkWords("c3i", t0); you.arm("R", ts, -150, -30, 0.4, "back.out(1.6)"); you.face(ts, "laugh", 0.3); you.hop(ts, 26, 0.4);
    ic.stamp(S, 1450, 560, ts, "BILLIONAIRE", "FORBES · 2021");
    for (let i = 0; i < 6; i++) { S.layer(PR.coin("fc" + i, 1180 + i * 110, 880), 1.2); S.pop("fc" + i, ts + 0.1 + i * 0.1, 0.35); S.key("fc" + i, "--y", ts + 0.4 + i * 0.1, -40 - (i % 3) * 22, 0.7, "sine.out"); }
    confetti(S, ts, 22, 16);
    DK.tag(S, "fbTag", "2021 · FORBES", "AMONG THE WORLD'S BILLIONAIRES", 120, 330, t0 + 0.3, { w: 860 });
    DK.hud(S, "hfb", { from: 2020, to: 2021, t0, t1: Math.min(t1 - 0.05, t0 + 1.2), marks: [{ y: 2020, label: "2020" }, { y: 2021, label: "FORBES" }] });
  } });
/* December 2021: the baby bar, fourth attempt (cartoon: three failed marks, then a pass) */
scene({ id: "babybar", a: W("c3j", 0), b: W("c3k", 0), bg: B.court(), cam: { from: [20, 6, 0.0], to: [-20, -6, 0.14] }, rays: [960, 300, Math.PI / 2], rayc: "#cfe0ff", grade: ["court", {}], light: [960, 760, 640, 380, "#ffd9a0", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1, tf = NW("c3j", 11);
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 6, depth: 0.55, drift: 80 });
    S.layer(PR.scales(1000, 860), 0.9);
    const you = S.actor("kQ", KIM25, 560, 940, 1.08, { seed: 131, expr: "neutral", pivot: [560, 940] });
    you.talkWords("c3j", t0); you.arm("R", tf, -150, -30, 0.4, "back.out(1.6)"); you.arm("L", tf, 150, 30, 0.4, "back.out(1.6)"); you.face(tf, "laugh", 0.3); you.hop(tf, 30, 0.4);
    ic.attempts(S, 1340, 560, Math.max(t0 + 0.3, NW("c3j", 6) - 0.2));
    confetti(S, tf, 24, 18);
    DK.tag(S, "bbTag", "DECEMBER 2021", "THE CALIFORNIA BABY BAR EXAM", 120, 330, t0 + 0.3, { w: 820 });
    DK.hud(S, "hbb", { from: 2021, to: 2021, t0, t1: Math.min(t1 - 0.05, t0 + 1.0), marks: [{ y: 2021, label: "DEC 2021" }] });
  } });

/* SKIMS grows fast: valued above $4 billion by 2023 */
card({ id: "g23", a: W("c3k", 0), b: W("s6", 0), year: 2023, seed: 30, kick: "SKIMS GROWS FAST", lines: ["BY 2023"], hi: 0, size: 130, sub: "COMPANY VALUATION: MORE THAN $4 BILLION", subSize: 28,
  icon: (S, cx, cy, t) => ic.bars(S, cx, cy, t, [{ label: "2023", val: 0.8, txt: "$4B+", col: "#c98a12" }], [D.W("c3k", 12)]), ix: 1500, iy: 500, hud: { from: 2021, to: 2023, marks: [{ y: 2021, label: "2021" }, { y: 2023, label: "2023" }] }, src: "SOURCE: COMPANY VALUATION REPORTS (FORTUNE · FOX)" });

/* 2025: boutique wide + valuation counter lands on "billion"; shown as a company valuation, never as revenue */
D.shot({ id: "skims", a: W("s6", 0), b: W("c3l", 0), bg: B.boutique(), cam: { from: [0, 14, 0.0], to: [0, -8, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, tb = D.W("s6", 9);
    S.layer(C.rays(960, 300, Math.PI / 2, 800, 0.36, "#fff4e4", 0.26), 0.45);
    const you = S.actor("kimS", KIM25, 560, 920, 1.1, { seed: 61, expr: "happy", pivot: [560, 920] });
    you.arm("L", t0 + 0.4, 150, 20, 0.5, "back.out(1.6)"); you.arm("R", t0 + 0.4, -150, -20, 0.5, "back.out(1.6)"); you.talkWords("s6", t0);
    you.hop(tb - 0.2, 30, 0.4); you.face(tb - 0.2, "laugh", 0.3);
    for (let t = tb + 0.5, i = 0; t < t1 - 0.6; t += 0.7, i++) { you.hop(t, 20 + (i % 2) * 8, 0.38); you.arm("L", t + 0.4, i % 2 ? 150 : 120, i % 2 ? 20 : 50, 0.35, "sine.inOut"); you.arm("R", t + 0.4, i % 2 ? -120 : -150, i % 2 ? -50 : -20, 0.35, "sine.inOut"); }
    S.layer(`<g data-p="vcard"><g transform="translate(1440 560)"><rect x="-300" y="-150" width="600" height="300" rx="26" fill="#fffaf0" ${st(8)}/><rect x="-280" y="-130" width="560" height="260" rx="16" fill="none" stroke="#c9a24a" stroke-width="4" stroke-dasharray="14 10"/><text y="-84" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="28" fill="#7a5a2a" letter-spacing="7">COMPANY VALUATION</text></g></g>`, 1.1);
    S.pop("vcard", t0 + 0.15, 0.4);
    const vals = ["$4B+", "$5B"], x = 1440, y = 640;
    S.layer(vals.map((v, i) => `<g data-p="v${i}" style="visibility:hidden"><g transform="translate(${x} ${y})"><text text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="170" fill="#c98a12" stroke="${OLN}" stroke-width="8" paint-order="stroke">${v}</text></g></g>`).join(""), 1.1);
    S.show("v0", t0 + 0.4, true); S.hideAt("v0", tb - 0.05); S.key("v0", "--s", t0 + 0.4, 0.8, 0); S.key("v0", "--s", t0 + 0.4, 1, 0.2, "back.out(2)");
    S.show("v1", tb - 0.05, true); S.key("v1", "--s", tb - 0.05, 0.8, 0); S.key("v1", "--s", tb - 0.05, 1, 0.2, "back.out(2)"); DK.flash(tb - 0.05, 0.4, 0.2);
    for (let i = 0; i < 5; i++) { S.layer(PR.coin("c" + i, 1260 + i * 110, 860), 1.2); S.pop("c" + i, tb + 0.1 + i * 0.1, 0.35); S.key("c" + i, "--y", tb + 0.4 + i * 0.1, -30 - (i % 2) * 24, 0.7, "sine.out"); }
    confetti(S, tb, 30, 9);
    S.layer(FG.post(1870), 1.6); S.layer(FG.leaves("L"), 1.7);
    grade(S, "glam");
    light(S, 560, 760, 520, 420, "#fff1d8", 0.34); light(S, 1500, 580, 520, 340, "#fff0b0", 0.3);
    DK.tag(S, "valTag", "YOUR BRAND · SKIMS", "2025", 1210, 290, t0 + 0.2, { w: 620 });
    DK.hud(S, "h15", { from: 2023, to: 2025, t0, t1: Math.min(t1 - 0.05, t0 + 1.4), marks: [{ y: 2023, label: "2023" }, { y: 2025, label: "2025" }] });
    badge(S, RECON);
  } });
card({ id: "fund", a: W("c3l", 0), b: W("c3l2", 0), year: 2025, seed: 31, kick: "NOVEMBER 2025", lines: ["A $225 MILLION", "FUNDING ROUND"], hi: 1, size: 84, icon: ic.funding, ix: 1500, iy: 540, iat: Math.max(0.3, D.W("c3l", 5) - D.W("c3l", 0) - 0.2), hud: { from: 2023, to: 2025, marks: [{ y: 2023, label: "2023" }, { y: 2025, label: "NOV 2025" }] }, src: "SOURCE: GOLDMAN SACHS ALTERNATIVES PRESS RELEASE · NOV 12, 2025" });
/* the round is led by Goldman Sachs Alternatives (cartoon boardroom handshake) */
scene({ id: "gs", a: W("c3l2", 0), b: W("c3m", 0), bg: B.office(), cam: { from: [-24, 4, 0.0], to: [24, -8, 0.14] }, rays: [1500, -40, 1.95], rayc: "#ffe0a8", grade: ["office", {}], light: [900, 780, 640, 400, "#ffe0b0", 0.28],
  build(S) {
    const t0 = S.t0, t1 = S.t1, ts = NW("c3l2", 4);
    const you = S.actor("kG", KIM25, 860, 940, 1.08, { seed: 201, expr: "happy", pivot: [860, 940] });
    const bk = S.actor("bkG", GROOM1, 1120, 940, 1.08, { seed: 202, expr: "neutral", depth: 1.0, pivot: [1120, 940] });
    you.talkWords("c3l2", t0); you.arm("R", ts, -88, -8, 0.5, "back.out(1.4)"); bk.arm("L", ts, 88, 8, 0.5, "back.out(1.4)"); you.face(ts + 0.3, "laugh", 0.3); bk.face(ts + 0.3, "happy", 0.3); you.hop(ts + 0.6, 18, 0.36);
    S.layer(PR.briefcase(560, 940), 1.05);
    for (let i = 0; i < 4; i++) { S.layer(PR.coin("gc" + i, 880 + i * 80, 700), 1.2); S.pop("gc" + i, ts + 0.5 + i * 0.1, 0.35); S.key("gc" + i, "--y", ts + 0.9 + i * 0.1, -40 - (i % 2) * 24, 0.7, "sine.out"); }
    confetti(S, ts + 0.4, 16, 23);
    DK.tag(S, "gsTag", "THE ROUND IS LED BY", "GOLDMAN SACHS ALTERNATIVES", 120, 330, t0 + 0.3, { w: 880 });
    TX(S, "src", 140, 850, 28, "#e8eef9", "SOURCE: GOLDMAN SACHS ALTERNATIVES · NOV 12, 2025", { w: 700, ls: 2, sw: 5 }); appear(S, "src", t0 + 0.8, 0.3);
  } });
card({ id: "valnote", a: W("c3m", 0), b: W("c3n", 0), year: 2025, seed: 32, kick: "VALUATION IS NOT REVENUE", lines: ["$5 BILLION"], hi: 0, size: 120,
  icon: (S, cx, cy, t) => ic.bars(S, cx, cy, t, [{ label: "VALUATION", val: 1.0, txt: "$5B", col: "#c98a12" }, { label: "NET SALES 2025", val: 0.2, txt: "$1B+", col: "#3d6a9c" }], [D.W("c3m", 2), D.W("c3m2", 8)]), ix: 1500, iy: 480, hud: { from: 2025, to: 2025, marks: [{ y: 2025, label: "NOV 2025" }] },
  src: "SOURCES: GOLDMAN SACHS ALTERNATIVES · COMPANY STATEMENT",
  extra(S, t0) {
    S.layer(`<g data-p="vbar"><g transform="translate(140 640)"><rect width="1040" height="86" rx="12" fill="#05070c" opacity=".78"/><text x="520" y="58" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="35" fill="#ffb84a" letter-spacing="1.5">COMPANY VALUATION: $5 BILLION — NOVEMBER 2025</text></g></g>`, 1.0);
    S.fadeIn("vbar", t0 + 0.2, 0.4);
    TX(S, "nrev", 140, 790, 30, "#cfe0ff", "A VALUATION OF THE COMPANY, NOT YEARLY REVENUE", { w: 700, ls: 3, sw: 5 }); appear(S, "nrev", D.W("c3m", 4), 0.3, true);
  } });

/* from a birth in Los Angeles in 1980 to a global business: Kim at four ages */
scene({ id: "ages", a: W("c3n", 0), b: W("c3n2", 0), bg: B.stage(), cam: { from: [0, 0, 0.0], to: [0, 0, 0.08] }, rays: false, grade: ["studio", {}], light: [960, 780, 760, 380, "#ffe0f6", 0.26],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(PR.spot(300, 330, 10), 0.8); S.layer(PR.spot(1620, 330, 170), 0.8);
    const L = [[BABY, 330, 0.7, "1980", D.W("c3n", 2), "ab"], [KID, 700, 1.0, "1989", D.W("c3n", 4), "ak"], [KIM07, 1090, 1.0, "2007", D.W("c3n", 8), "a7"], [KIM25, 1500, 1.08, "2025", D.W("c3n", 10), "a25"]];
    L.forEach(([sp, x, sc, yr, t, id], i) => { const a = S.actor(id, sp, x, 960, sc, { seed: 120 + i, expr: "happy", depth: 0.95, pivot: [x, 960] }); a.hiddenUntil(t - 0.05); a.k("self", "--y", t - 0.05, 120, 0); a.k("self", "--y", t, 0, 0.4, "power3.out"); nameTag(S, "ay" + i, yr, x, 330, t + 0.1); });
    DK.hud(S, "hag", { from: 1980, to: 2025, t0, t1: Math.min(t1 - 0.05, t0 + 4.4), marks: [{ y: 1980, label: "BORN" }, { y: 2007, label: "TV" }, { y: 2025, label: "SKIMS" }] });
    badge(S, RECON);
  } });
card({ id: "worlds", a: W("c3n2", 0), b: W("c3o", 0), year: 2025, seed: 33, kick: "FOUR DIFFERENT WORLDS", lines: ["ONE NAME"], hi: 0, size: 120, icon: ic.tiles, ix: 1450, iy: 520, iat: 0.0 });

/* the closing question */
DK.whip(D.W("c3o", 0), 1);
scene({ id: "endq", a: W("c3o", 0), b: "end", bg: B.avenue(), cam: { from: [0, -8, 0.2], to: [0, 10, 0.0], ease: "power1.out" }, rays: false, grade: ["dusk", {}], light: [960, 780, 620, 380, "#ffd7a0", 0.45],
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 548, Math.PI / 2, 760, 0.42, "#ffd9a0", 0.32), 0.42);
    C.fog(S, { y: 650, h: 220, color: "#ffcfa0", op: 0.32, seed: 3, depth: 0.55, drift: 120 });
    C.dust(S, { n: 22, seed: 23, box: [100, 100, 1700, 800], color: "#ffe9c0", depth: 1.1, op: 0.5 });
    S.layer(FG.leaves("L"), 1.7); S.layer(FG.leaves("R"), 1.75);
    S.layer(`<defs><linearGradient id="eband" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05070c" stop-opacity="0"/><stop offset=".25" stop-color="#05070c" stop-opacity=".62"/><stop offset=".75" stop-color="#05070c" stop-opacity=".62"/><stop offset="1" stop-color="#05070c" stop-opacity="0"/></linearGradient></defs><rect x="0" y="170" width="1920" height="420" fill="url(#eband)"/>`, 0);
    TX(S, "q1", 960, 290, 40, "#cfe0ff", "NOW IMAGINE IT WAS YOUR LIFE", { anchor: "middle", ls: 10, w: 700, sw: 5, depth: 0 });
    TX(S, "q2", 960, 420, 84, "#fff", "WHAT WOULD YOU HAVE", { anchor: "middle", ls: 4, sw: 7, depth: 0 });
    TX(S, "q3", 960, 530, 84, "#ffb84a", "DONE DIFFERENTLY?", { anchor: "middle", ls: 4, sw: 7, depth: 0 });
    appear(S, "q1", D.W("c3o", 0) + 0.1, 0.5); appear(S, "q2", D.W("c3o", 6) - 0.1, 0.5); appear(S, "q3", D.W("c3o", 8), 0.5);
  } });

}
DK.flush(D);
