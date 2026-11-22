/* Cinematic scenes (additive): every set is built in one-point perspective (converging lines),
   split into depth layers (far / structure / foreground) so the camera dolly parallaxes them against each other.
   K.bgc.<scene>() -> { layers:[{name, depth, svg}] }.  K.fgc.<item>() -> svg for dark foreground silhouettes. */
(function (K) {
  "use strict";
  const { OL, shade, mixc, rng, uid } = K, C = K.cine, Pp = K.persp, lerp = Pp.lerp;
  const st = (w) => `stroke="${OL}" stroke-width="${w || 5}" stroke-linejoin="round" stroke-linecap="round"`;
  const L = (name, depth, svg) => ({ name, depth, svg });
  const grad = (id, a, b, v) => `<linearGradient id="${id}" x1="0" y1="0" x2="${v ? 0 : 1}" y2="${v ? 1 : 0}"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`;
  const sky = (a, b, h) => { const id = uid("sk"); return `<defs>${grad(id, a, b, 1)}</defs><rect width="1920" height="${h || 700}" y="-60" fill="url(#${id})"/>`; };

  /* ================= 1 · Los Angeles avenue, sunset (wide establishing, vanishing point 960,545) ================= */
  function avenue() {
    const vp = [960, 545], r = rng(8);
    const far = sky("#ff7a4a", "#ffd9a0", 640) +
      `<ellipse cx="960" cy="560" rx="260" ry="120" fill="#fff0c0" opacity=".85"/><circle cx="960" cy="548" r="86" fill="#fffbe6"/>` +
      `<path d="M0 520C220 440 400 500 600 450S880 420 1100 480 1500 440 1920 510V640H0Z" fill="#8a4a5a" opacity=".7"/>` +
      `<g transform="translate(1190 452)" font-family="Inter,Arial,sans-serif" font-weight="800" font-size="30" fill="#fff" opacity=".85"><text letter-spacing="9">HOLLYWOOD</text></g>` +
      Array.from({ length: 16 }, (_, i) => { const h = 40 + Math.round(r() * 70), x = 620 + i * 44; return `<rect x="${x}" y="${548 - h}" width="34" height="${h}" fill="#6a3f58" ${st(2.5)}/>`; }).join("") +
      C.haze(560, 180, "#ffc890", 0.55);
    const road = Pp.floor(vp, vp[1] + 26, { color: "#3a3340", line: "#ffd98a", n: 5, rows: 8, lineOp: 0.0, x0: -380, x1: 2300 }) +
      // sidewalks + dashed centre line, all converging on the vanishing point
      `<path d="M-700 1080 L${vp[0] - 18} ${vp[1] + 26} L${vp[0] - 4} ${vp[1] + 26} L-260 1080Z" fill="#8a7f8c" opacity=".9"/><path d="M2620 1080 L${vp[0] + 18} ${vp[1] + 26} L${vp[0] + 4} ${vp[1] + 26} L2180 1080Z" fill="#8a7f8c" opacity=".9"/>` +
      [0.1, 0.24, 0.4, 0.58, 0.8].map((t, i) => { const y = lerp(vp[1] + 26, 1080, t * t * 1.02), w = 6 + t * 26, hh = 8 + t * 60; return `<path d="M${vp[0] - w / 2} ${y} L${vp[0] + w / 2} ${y} L${vp[0] + w * 0.8} ${y + hh} L${vp[0] - w * 0.8} ${y + hh}Z" fill="#ffd98a"/>`; }).join("");
    const bl = Pp.facades("L", vp, { colors: ["#4a3552", "#5d4062", "#3e2f4c", "#6e4a63"], seed: 3, lit: 0.55 }) + Pp.facades("R", vp, { colors: ["#53395a", "#40304e", "#6a4466", "#47345a"], seed: 9, lit: 0.5 });
    // lamp posts marching toward the horizon (near = tall and dark)
    const lamps = [0.06, 0.2, 0.36, 0.52, 0.68].map((d) => [["L", 1], ["R", -1]].map(([sd, sg]) => { const x = lerp(sg > 0 ? 80 : 1840, vp[0] + sg * 70, d), yb = lerp(1010, vp[1] + 26, d), h = lerp(520, 60, d), w = lerp(14, 3, d); return `<path d="M${x} ${yb}V${yb - h}" stroke="#241522" stroke-width="${w}" stroke-linecap="round"/><circle cx="${x}" cy="${yb - h}" r="${lerp(26, 5, d)}" fill="#ffe9a8" ${st(3)}/>`; }).join("")).join("");
    return { layers: [L("far", 0.12, far), L("road", 0.42, road + bl + lamps)] };
  }

  /* ================= 3 · father's law office (room in perspective) ================= */
  function office() {
    const vp = [960, 500], back = [560, 250, 1360, 790];
    const room = Pp.room(vp, back, { wall: "#5b4636", side: "#43302a", ceil: "#2a1c18", floor: "#35282c", line: "#7a5a4a", lineOp: 0.5, panels: 5 });
    const win = `<g transform="translate(790 300)"><rect width="340" height="280" fill="#8fb8e8" ${st(7)}/><g fill="#44587a" opacity=".92" ${st(3)}><rect x="14" y="130" width="54" height="150"/><rect x="78" y="86" width="64" height="194"/><rect x="152" y="150" width="48" height="130"/><rect x="214" y="60" width="70" height="220"/><rect x="290" y="140" width="40" height="140"/></g><path d="M170 0V280M0 140H340" stroke="#e8dcc0" stroke-width="9"/></g>`;
    const shelf = `<g transform="translate(590 290)"><rect width="150" height="440" fill="#2e1e16" ${st(5)}/>${[0, 1, 2, 3].map((i) => Array.from({ length: 5 }, (_, k) => `<rect x="${10 + k * 26}" y="${14 + i * 106 + (k % 3) * 4}" width="20" height="${86 - (k % 3) * 4}" fill="${["#7a1f27", "#1f3a5a", "#b88a2a", "#2f5a3a", "#5a2a5a"][(k + i) % 5]}" ${st(2)}/>`).join("")).join("")}</g>`;
    const dip = `<g transform="translate(1190 330)"><rect width="130" height="100" fill="#f3ead2" ${st(5)}/><rect x="9" y="9" width="112" height="82" fill="#fffaf0"/><path d="M22 34H108M22 52H100M22 70H104" stroke="#7a6a50" stroke-width="4"/></g>`;
    return { layers: [L("room", 0.3, room + win + shelf + dip)] };
  }

  /* ================= 4 · courthouse at dusk: columns, steps narrowing upward, converging sidewalks ================= */
  function court() {
    const vp = [960, 600];
    let m = sky("#40507a", "#d6a07a", 640);
    m += `<g transform="translate(0 40)">${Array.from({ length: 6 }, (_, i) => `<rect x="${360 + i * 240}" y="210" width="96" height="430" fill="#cfc6bb" ${st(5)}/><rect x="${348 + i * 240}" y="196" width="120" height="26" fill="#e8e0d4" ${st(4)}/><path d="M${380 + i * 240} 236V630M${424 + i * 240} 236V630" stroke="#9c9388" stroke-width="3"/>`).join("")}
      <path d="M300 200 L960 60 L1620 200Z" fill="#d8d0c4" ${st(6)}/><rect x="300" y="196" width="1320" height="34" fill="#e4dccf" ${st(5)}/></g>`;
    // steps as trapezoids shrinking toward the door
    const steps = Array.from({ length: 7 }, (_, i) => { const y = 690 + i * 50, wTop = lerp(1100, 1500, i / 6), wBot = lerp(1100, 1700, (i + 1) / 6); return `<path d="M${960 - wTop / 2} ${y} H${960 + wTop / 2} L${960 + wBot / 2} ${y + 50} H${960 - wBot / 2} Z" fill="${shade("#b9b0a4", -0.05 * i)}" ${st(4)}/>`; }).join("");
    const walk = Pp.floor(vp, 680, { color: "#4a4452", line: "#9a90a4", n: 7, rows: 5, lineOp: 0.35, x0: -1200, x1: 3120 });
    return { layers: [L("sky", 0.1, m), L("ground", 0.38, walk + steps)] };
  }

  /* ================= 5 · 1989 family home (amber room, doorway light, photos) ================= */
  function home() {
    const vp = [960, 520], back = [520, 250, 1400, 800];
    let m = Pp.room(vp, back, { wall: "#8a6a50", side: "#6a4e3c", ceil: "#43332a", floor: "#5a3e30", line: "#8a6446", lineOp: 0.5, panels: 4 });
    m += `<g transform="translate(850 380)"><rect width="220" height="420" fill="#2a1a14" ${st(6)}/><rect x="14" y="14" width="192" height="406" fill="#ffd9a0"/><path d="M14 14L206 14" stroke="#fff3d0" stroke-width="6"/></g>`;
    m += [[560, 330, 90, 120], [700, 360, 100, 80], [1250, 340, 110, 140], [1100, 300, 60, 80]].map(([x, y, w, h], i) => `<g transform="translate(${x} ${y})"><rect width="${w}" height="${h}" fill="#e9dcc0" ${st(4)}/><rect x="8" y="8" width="${w - 16}" height="${h - 16}" fill="${["#b98a6a", "#7a8aa8", "#a8a07a", "#c08a8a"][i]}"/></g>`).join("");
    return { layers: [L("room", 0.3, m)] };
  }

  /* ================= 6 · wedding garden: hedge walls, petal path and flower arch at the vanishing point ================= */
  function garden() {
    const vp = [960, 520];
    const far = sky("#ffd9a0", "#fff1d0", 620) + `<path d="M0 520C300 440 600 500 960 470S1500 440 1920 500V620H0Z" fill="#6a9a6a" opacity=".7"/>` + C.haze(540, 160, "#fff1d0", 0.6);
    const hedges = Pp.facades("L", vp, { colors: ["#2f6a45", "#3a7a50", "#2a5a3c"], win: "#e8708a", winOff: "#2a5a3c", seed: 4, lit: 0.18, top: -80, bot: 960, nearX: -40, rows: 0 }) + Pp.facades("R", vp, { colors: ["#337348", "#2c6240", "#3a7a50"], win: "#f3c64a", winOff: "#2a5a3c", seed: 6, lit: 0.18, top: -80, bot: 960, nearX: -40, rows: 0 });
    const path = Pp.floor(vp, vp[1] + 26, { color: "#cfa57a", line: "#e8c9a0", n: 3, rows: 9, lineOp: 0.0, x0: 200, x1: 1720 }) +
      `<path d="M-900 1080 L${vp[0] - 120} ${vp[1] + 26} L-300 1080Z" fill="#4f8a58"/><path d="M2820 1080 L${vp[0] + 120} ${vp[1] + 26} L2220 1080Z" fill="#4f8a58"/>`;
    const arch = `<g transform="translate(960 ${vp[1] + 30})"><path d="M-120 0V-190Q0 -290 120 -190V0" fill="none" stroke="#f6f1e8" stroke-width="16" stroke-linecap="round"/>${Array.from({ length: 14 }, (_, i) => `<circle cx="${Math.round(-120 + (i / 13) * 240)}" cy="${Math.round(-190 - 90 * Math.sin((i / 13) * Math.PI))}" r="${8 + (i % 3) * 3}" fill="${["#f2a7b8", "#fff", "#f6d54a"][i % 3]}"/>`).join("")}</g>`;
    const chairs = [0.1, 0.22, 0.36, 0.52, 0.7].map((d) => [["L", -1], ["R", 1]].map(([s, sg]) => { const x = lerp(960 + sg * 560, vp[0] + sg * 110, d), y = lerp(990, vp[1] + 26, d), w = lerp(120, 18, d), h = lerp(150, 22, d); return `<rect x="${x - w / 2}" y="${y - h}" width="${w}" height="${h}" fill="#f4efe6" stroke="${OL}" stroke-width="${lerp(5, 1.6, d)}"/>`; }).join("")).join("");
    return { layers: [L("far", 0.1, far), L("garden", 0.4, hedges + path + arch + chairs)] };
  }

  /* ================= 7 · 1976 Montreal stadium: crowd stands + lanes running to the far end ================= */
  function stadium() {
    const r = rng(11);
    let far = sky("#7aa8e0", "#cfe2f6", 560) + C.haze(520, 140, "#e8f0ff", 0.55);
    // stands: curved rows of spectators getting smaller toward the top
    for (let row = 0; row < 8; row++) { const y = 470 - row * 26, hh = 24; far += `<rect x="0" y="${y}" width="1920" height="${hh}" fill="${shade("#5a4a6a", -0.03 * row)}"/>` + Array.from({ length: 64 }, (_, k) => `<circle cx="${14 + k * 30 + (row % 2) * 15}" cy="${y + 8}" r="${8 - row * 0.4}" fill="${["#e8b896", "#c98f6a", "#f3d3b0", "#d99a73"][Math.floor(r() * 4)]}"/><rect x="${6 + k * 30 + (row % 2) * 15}" y="${y + 14}" width="16" height="9" fill="${["#d9453f", "#3a6aa8", "#f3c64a", "#4c8a5a", "#fff"][Math.floor(r() * 5)]}"/>`).join(""); }
    far += `<rect y="520" width="1920" height="40" fill="#8a6a5a"/><path d="M0 520H1920" stroke="${OL}" stroke-width="5"/>`;
    let trk = `<rect y="560" width="1920" height="540" fill="#c4553f"/>`;
    for (let i = 0; i <= 7; i++) { const t = Math.pow(i / 7, 1.5), yl = lerp(566, 1080, t), yr = lerp(552, 1020, t); trk += `<path d="M0 ${yl} L1920 ${yr}" stroke="#fff" stroke-width="${(3 + t * 9).toFixed(1)}" opacity=".9"/>`; }
    for (let k = 0; k < 14; k++) trk += `<path d="M${k * 160 - 40} 570 L${k * 190 - 220} 1080" stroke="#a8412f" stroke-width="3" opacity=".55"/>`;
    return { layers: [L("stands", 0.12, far), L("track", 0.42, trk)] };
  }

  /* ================= 8 · 2007 family living room: big window, converging floor, TV glow ================= */
  function living() {
    const vp = [960, 500], back = [540, 240, 1380, 800];
    let m = Pp.room(vp, back, { wall: "#b79a7a", side: "#8a6e56", ceil: "#5a4636", floor: "#6a4a38", line: "#8a6446", lineOp: 0.45, panels: 3 });
    m += `<g transform="translate(1000 300)"><rect width="320" height="260" fill="#cfe7f6" ${st(7)}/><path d="M160 0V260M0 130H320" stroke="#fff" stroke-width="9"/></g><g transform="translate(600 360)"><rect width="260" height="170" rx="8" fill="#1a1e2a" ${st(6)}/><rect x="12" y="12" width="236" height="146" fill="#6a8ab0"/></g>`;
    m += `<g transform="translate(700 800)"><rect x="-190" y="-130" width="380" height="110" rx="26" fill="#8a4a52" ${st(6)}/><rect x="-170" y="-60" width="340" height="60" rx="18" fill="#a85a62" ${st(6)}/></g>`;
    return { layers: [L("room", 0.3, m)] };
  }

  /* ================= 9 · reality-TV stage: reflective floor, light truss, converging stage lines ================= */
  function stage() {
    const vp = [960, 470];
    let m = `<rect width="1920" height="1080" fill="#1a0f2a"/>` + Array.from({ length: 9 }, (_, i) => `<rect x="${60 + i * 220}" y="120" width="170" height="${320 + (i % 3) * 40}" fill="${["#4a2a78", "#7a2a78", "#2a3a88"][i % 3]}" opacity=".85" ${st(4)}/>`).join("");
    m += Pp.floor(vp, 560, { color: "#2b1a3a", line: "#c08ae8", n: 13, rows: 9, lineOp: 0.5, x0: -1400, x1: 3320 });
    m += `<path d="M0 90H1920" stroke="#8a8aa0" stroke-width="16"/>` + Array.from({ length: 9 }, (_, i) => `<g transform="translate(${140 + i * 205} 96)"><rect x="-22" y="0" width="44" height="40" rx="6" fill="#2a2a32" ${st(4)}/><circle cx="0" cy="44" r="14" fill="#fff4c0"/></g>`).join("");
    return { layers: [L("stage", 0.3, m)] };
  }

  /* ================= 10 · boutique: neutral shelves in perspective, bright display ================= */
  function boutique() {
    const vp = [960, 500], back = [600, 270, 1320, 780];
    let m = Pp.room(vp, back, { wall: "#c9b8a6", side: "#a89684", ceil: "#7a6a5c", floor: "#8a7466", line: "#6a5648", lineOp: 0.35, panels: 5 });
    m += [0, 1, 2].map((i) => `<g transform="translate(${back[0] + 30} ${320 + i * 150})"><rect width="${back[2] - back[0] - 60}" height="10" fill="#6a5648"/>${Array.from({ length: 9 }, (_, k) => `<rect x="${10 + k * 72}" y="-${52 + (k % 3) * 8}" width="58" height="${52 + (k % 3) * 8}" rx="6" fill="${["#d8b8a0", "#c8a088", "#e8d0bc", "#b89078", "#f0dccb"][(k + i) % 5]}" ${st(3)}/>`).join("")}</g>`).join("");
    return { layers: [L("room", 0.3, m)] };
  }

  /* ---------- backdrops for close-ups: soft coloured light, no hard structure ---------- */
  function closeBack(name) {
    const P2 = { baby: ["#1b2748", "#0c1226", ["#9fb8ff", "#ffe2b0"]], dad: ["#2a2230", "#120d18", ["#ffd9a0", "#7d98c8"]], kid: ["#3a2a22", "#1a110c", ["#ffc88a", "#d49a62"]], kim07: ["#3a2a3e", "#150e1a", ["#fff1c4", "#ffb6f0"]], kim25: ["#3c2e2a", "#171110", ["#ffe2c0", "#e0a888"]], rings: ["#4a3a28", "#1c140c", ["#ffe0b0", "#fff"]], lens: ["#1a1a22", "#08080c", ["#4a7ab0", "#e22"]], skims: ["#d8c8b8", "#9a8676", ["#fff", "#ffe8d0"]] }[name];
    const id = uid("cb");
    return `<defs>${grad(id, P2[0], P2[1], 1)}</defs><rect x="-80" y="-80" width="2080" height="1240" fill="url(#${id})"/>` + C.bokeh(name.length * 17 + 3, P2[2], 14, [0, 0, 1920, 1000]);
  }

  /* ---------- dark foreground silhouettes (placed on layers with depth > 1 so they slide faster than the set) ---------- */
  const DK = "#07050b";
  const fgc = {
    leaves: (side) => `<g transform="translate(${side === "L" ? -60 : 1980} 1100) scale(${side === "L" ? 1 : -1} 1)">${[-34, -8, 18, 44, 70].map((a, i) => `<path d="M0 0C${30 + i * 6} -${260 + i * 40} ${120 + i * 20} -${420 + i * 30} ${200 + i * 26} -${520 + i * 20}C${140} -${300} ${70} -${150} 0 0Z" transform="rotate(${a - 30})" fill="${DK}" opacity=".94"/>`).join("")}</g>`,
    bars: (n) => Array.from({ length: n }, (_, i) => `<rect x="${Math.round(((i + 0.5) * 1920) / n) - 18}" y="-60" width="36" height="1200" fill="${DK}" opacity=".9"/>`).join("") + `<rect x="-40" y="880" width="2000" height="40" fill="${DK}" opacity=".9"/>`,
    barsAt: (xs) => xs.map((x) => `<rect x="${x - 20}" y="-60" width="40" height="1200" fill="${DK}" opacity=".92"/>`).join("") + `<rect x="-40" y="900" width="2000" height="40" fill="${DK}" opacity=".9"/>`,
    heads: (seed, n, y) => { const r = rng(seed); return Array.from({ length: n }, (_, i) => { const x = Math.round(((i + 0.5) * 1920) / n + (r() - 0.5) * 60), s = 0.9 + r() * 0.5; return `<g transform="translate(${x} ${y}) scale(${s.toFixed(2)})"><circle r="62" fill="${DK}"/><path d="M-110 200C-100 90 -50 60 0 60S100 90 110 200Z" fill="${DK}"/></g>`; }).join(""); },
    curtain: (side) => `<path d="${side === "L" ? "M-40 -40H300Q220 300 280 640Q240 900 300 1140H-40Z" : "M1960 -40H1620Q1700 300 1640 640Q1680 900 1620 1140H1960Z"}" fill="${DK}" opacity=".93"/>`,
    post: (x) => `<rect x="${x - 26}" y="-60" width="52" height="1240" fill="${DK}" opacity=".95"/>`,
    desk: () => `<path d="M-60 1140V930Q500 880 1000 910T1980 900V1140Z" fill="${DK}" opacity=".95"/>`,
    couch: () => `<path d="M-60 1140V820Q120 760 360 800L520 1140Z" fill="${DK}" opacity=".95"/>`,
    cam: () => `<g transform="translate(1500 760)"><rect x="-210" y="-130" width="420" height="280" rx="26" fill="${DK}"/><rect x="-330" y="-70" width="140" height="170" rx="16" fill="${DK}"/><circle cx="-400" cy="15" r="62" fill="#0e0f16"/><circle cx="-400" cy="15" r="34" fill="#16202c"/><path d="M-110 150V420M110 150V420" stroke="${DK}" stroke-width="40"/></g>`,
  };
  K.bgc = { avenue, office, court, home, garden, stadium, living, stage, boutique, closeBack };
  K.fgc = fgc;
})(window.K);
