/* Cinematic toolkit (additive; the old kim-test30 never calls it):
   K.cine.look()  scene colour grade + deep shadows + strong vignette (kept above the crush limit),
   K.cine.fog/dust/rays  atmosphere and volumetric light,
   K.cine.haze    aerial perspective (distance goes lighter and cooler),
   K.persp.*      one-point-perspective helpers (facade rows, floors with converging lines, rooms).
   Everything is deterministic: seeded rng, finite GSAP keys, no runtime randomness. */
(function (K) {
  "use strict";
  const { OL, S, P, shade, mixc, uid, rng } = K;

  /* ---------- scene looks: tint (multiply), dark (black veil), vig (edge darkness), hi (highlight colour) ---------- */
  const LOOKS = {
    dusk:    { tint: "#ff9c70", ta: 0.36, dark: 0.16, vig: 0.78, hi: "#ffb985" },   // warm LA sunset
    night:   { tint: "#5a76c8", ta: 0.46, dark: 0.22, vig: 0.82, hi: "#9fb8ff" },   // moonlit nursery
    office:  { tint: "#7d98c8", ta: 0.38, dark: 0.2,  vig: 0.8,  hi: "#ffd9a0" },   // cold blue + warm lamp
    court:   { tint: "#7088c0", ta: 0.38, dark: 0.22, vig: 0.8,  hi: "#a8c4ff" },
    home:    { tint: "#d49a62", ta: 0.38, dark: 0.22, vig: 0.8,  hi: "#ffc88a" },   // 1989: amber, lonely
    garden:  { tint: "#ffc08a", ta: 0.28, dark: 0.1,  vig: 0.66, hi: "#ffe0b0" },   // 1991: golden hour
    stadium: { tint: "#9ab8e0", ta: 0.28, dark: 0.1,  vig: 0.66, hi: "#fff2c0" },
    studio:  { tint: "#c08ae8", ta: 0.34, dark: 0.2,  vig: 0.78, hi: "#ffb6f0" },   // reality-TV set
    glam:    { tint: "#e0a888", ta: 0.28, dark: 0.12, vig: 0.7,  hi: "#ffe2c0" },
    mono:    { tint: "#8890a8", ta: 0.3,  dark: 0.24, vig: 0.84, hi: "#d8e0ff" },
  };
  function look(name, o) {
    const L = Object.assign({}, LOOKS[name] || LOOKS.mono, o || {}), id = uid("vg");
    return `<defs><radialGradient id="${id}" cx="50%" cy="46%" r="72%"><stop offset=".38" stop-color="#000" stop-opacity="0"/><stop offset=".78" stop-color="#05030a" stop-opacity="${(L.vig * 0.55).toFixed(2)}"/><stop offset="1" stop-color="#05030a" stop-opacity="${L.vig}"/></radialGradient></defs>
      <rect width="1920" height="1080" fill="${L.tint}" opacity="${L.ta}" style="mix-blend-mode:multiply"/>
      <rect width="1920" height="1080" fill="#05030a" opacity="${L.dark}"/>
      <rect width="1920" height="1080" fill="url(#${id})"/>`;
  }
  /** pool of light that keeps the subject readable inside the dark grade */
  function key(x, y, rx, ry, color, op) { return K.fx.glow(x, y, rx, ry, color, op, "screen"); }

  /* ---------- atmosphere ---------- */
  /** drifting fog bank; the layer returned is already on the shot (S.layer) and drifts slowly across the shot */
  function fog(S_, o) {
    o = Object.assign({ y: 700, h: 260, color: "#9fb0d8", op: 0.28, seed: 1, depth: 0.6, drift: 90, n: 6 }, o);
    const r = rng(o.seed), nm = "fog" + uid("f");
    let m = "";
    for (let i = 0; i < o.n; i++) {
      const id = uid("fg"), cx = Math.round(-100 + (2120 * (i + r() * 0.6)) / o.n), cy = Math.round(o.y + (r() - 0.5) * o.h * 0.6), rx = 320 + Math.round(r() * 280), ry = Math.round(o.h * (0.55 + r() * 0.5));
      m += `<defs><radialGradient id="${id}"><stop offset="0" stop-color="${o.color}" stop-opacity="${o.op}"/><stop offset="1" stop-color="${o.color}" stop-opacity="0"/></radialGradient></defs><ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="url(#${id})"/>`;
    }
    S_.layer(`<g data-p="${nm}">${m}</g>`, o.depth);
    S_.key(nm, "--x", S_.t0, -o.drift / 2, 0); S_.key(nm, "--x", S_.t0, o.drift / 2, S_.dur, "none");
    return nm;
  }
  /** floating dust motes in a light beam (screen blend, tiny, slow) */
  function dust(S_, o) {
    o = Object.assign({ n: 18, seed: 2, box: [200, 120, 1500, 800], color: "#fff4d0", depth: 1.0, op: 0.55 }, o);
    const r = rng(o.seed); let m = "";
    for (let i = 0; i < o.n; i++) {
      const x = Math.round(o.box[0] + r() * o.box[2]), y = Math.round(o.box[1] + r() * o.box[3]), rr = (1.6 + r() * 3.2).toFixed(1);
      m += `<g transform="translate(${x} ${y})"><g data-p="dm${i}_${o.seed}"><circle r="${rr}" fill="${o.color}" opacity="${(o.op * (0.4 + r() * 0.6)).toFixed(2)}" style="mix-blend-mode:screen"/></g></g>`;
    }
    S_.layer(m, o.depth);
    const r2 = rng(o.seed + 99);
    for (let i = 0; i < o.n; i++) {
      const e = S_.q("dm" + i + "_" + o.seed);
      S_.key(e, "--x", S_.t0, 0, 0); S_.key(e, "--x", S_.t0, Math.round((r2() - 0.4) * 90), S_.dur, "sine.inOut");
      S_.key(e, "--y", S_.t0, 0, 0); S_.key(e, "--y", S_.t0, -Math.round(30 + r2() * 90), S_.dur, "none");
    }
  }
  /** volumetric light shaft(s) from a source point, fanning out; stacked soft polygons */
  function rays(x, y, angle, len, spread, color, op) {
    const id = uid("rz"); let m = `<defs><linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${x}" y1="${y}" x2="${x + Math.cos(angle) * len}" y2="${y + Math.sin(angle) * len}"><stop offset="0" stop-color="${color}" stop-opacity="${op}"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>`;
    [[1, 1], [0.62, 0.7], [0.3, 0.5]].forEach(([k, o2], i) => {
      const a1 = angle - spread * k, a2 = angle + spread * k, L = len * (1 + i * 0.05);
      m += `<path d="M${x} ${y} L${Math.round(x + Math.cos(a1) * L)} ${Math.round(y + Math.sin(a1) * L)} L${Math.round(x + Math.cos(a2) * L)} ${Math.round(y + Math.sin(a2) * L)} Z" fill="url(#${id})" opacity="${o2}" style="mix-blend-mode:screen"/>`;
    });
    return m;
  }
  /** aerial perspective: a soft horizon band that lightens/cools what is far away */
  function haze(y, h, color, op) {
    const id = uid("hz");
    return `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="0"/><stop offset=".55" stop-color="${color}" stop-opacity="${op}"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><rect y="${y - h / 2}" width="1920" height="${h}" fill="url(#${id})"/>`;
  }
  /** big blurred bokeh discs (cheap: radial gradients, no filter) for close-up backdrops */
  function bokeh(seed, colors, n, box) {
    const r = rng(seed); box = box || [0, 0, 1920, 1080]; let m = "";
    for (let i = 0; i < n; i++) {
      const id = uid("bk"), c = colors[i % colors.length], x = Math.round(box[0] + r() * box[2]), y = Math.round(box[1] + r() * box[3]), rr = 40 + Math.round(r() * 120);
      m += `<defs><radialGradient id="${id}"><stop offset=".0" stop-color="${c}" stop-opacity=".0"/><stop offset=".78" stop-color="${c}" stop-opacity=".5"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></radialGradient></defs><circle cx="${x}" cy="${y}" r="${rr}" fill="url(#${id})" style="mix-blend-mode:screen" opacity="${(0.35 + r() * 0.45).toFixed(2)}"/>`;
    }
    return m;
  }

  /* ---------- one-point perspective ---------- */
  const lerp = (a, b, t) => a + (b - a) * t;
  /** Row of building facades on one side of an avenue. vp=[x,y]. d in 0(near)..1(vanishing point). */
  function facades(side, vp, o) {
    o = Object.assign({ nearX: -120, top: -260, bot: 930, ds: [0, 0.18, 0.34, 0.5, 0.66, 0.8], colors: ["#4a3552", "#5d4062", "#3e2f4c"], gap: 0.012, win: "#ffd27a", winOff: "#6b5a82", seed: 3, lit: 0.45 }, o);
    const sg = side === "L" ? 1 : -1, r = rng(o.seed), nearX = side === "L" ? o.nearX : 1920 - o.nearX;
    const X = (d) => lerp(nearX, vp[0], d), T = (d) => lerp(o.top, vp[1] - 90, d), B = (d) => lerp(o.bot, vp[1] + 24, d);
    let m = "";
    o.ds.forEach((d0, i) => {
      const d1 = (o.ds[i + 1] === undefined ? 0.92 : o.ds[i + 1]) - o.gap, c = o.colors[i % o.colors.length];
      m += `<path d="M${X(d0)} ${T(d0)} L${X(d1)} ${T(d1)} L${X(d1)} ${B(d1)} L${X(d0)} ${B(d0)} Z" fill="${c}" stroke="${OL}" stroke-width="4" stroke-linejoin="round"/>`;
      // darker lower band + roofline lip for volume
      m += `<path d="M${X(d0)} ${T(d0)} L${X(d1)} ${T(d1)} L${X(d1)} ${T(d1) + 16} L${X(d0)} ${T(d0) + 26} Z" fill="${shade(c, -0.35)}"/>`;
      const cols = 3 + (i % 2), rows = o.rows === undefined ? 5 : o.rows;
      if (rows === 0) for (let k = 0; k < 26; k++) { const dd = lerp(d0, d1, r()), vv = 0.1 + r() * 0.8, px = X(dd), py = lerp(T(dd), B(dd), vv), rr = lerp(5, 22, 1 - dd) * (0.6 + r() * 0.8); m += `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="${rr.toFixed(1)}" fill="${r() < 0.2 ? o.win : shade(c, r() < 0.5 ? 0.18 : -0.2)}" opacity=".9"/>`; }
      for (let k = 0; k < cols; k++) {
        const a = lerp(d0, d1, (k + 0.18) / cols), b = lerp(d0, d1, (k + 0.82) / cols);
        for (let q = 0; q < rows; q++) {
          const v0 = (q + 0.2) / (rows + 0.6) + 0.04, v1 = (q + 0.72) / (rows + 0.6) + 0.04;
          const ya = (d, v) => lerp(T(d), B(d), v);
          const lit = r() < o.lit;
          m += `<path d="M${X(a)} ${ya(a, v0)} L${X(b)} ${ya(b, v0)} L${X(b)} ${ya(b, v1)} L${X(a)} ${ya(a, v1)} Z" fill="${lit ? o.win : o.winOff}" stroke="${OL}" stroke-width="2.5" ${lit ? "" : 'opacity=".85"'}/>`;
        }
      }
    });
    return m;
  }
  /** floor plane with lines converging on the vanishing point + evenly foreshortened cross lines */
  function floor(vp, y0, o) {
    o = Object.assign({ color: "#3a3340", line: "#8a7f98", n: 11, rows: 9, lineOp: 0.55, x0: -900, x1: 2820, xs: null }, o);
    let m = `<path d="M${o.x0} 1080 L${vp[0]} ${y0} L${o.x1} 1080 Z" fill="${o.color}"/>`;
    const xs = o.xs || Array.from({ length: o.n }, (_, i) => lerp(o.x0, o.x1, i / (o.n - 1)));
    xs.forEach((x) => { m += `<path d="M${vp[0]} ${y0} L${x} 1080" stroke="${o.line}" stroke-width="3" opacity="${o.lineOp}"/>`; });
    for (let i = 1; i <= o.rows; i++) { const t = Math.pow(i / o.rows, 2.1), y = lerp(y0, 1080, t); m += `<path d="M0 ${y.toFixed(1)}H1920" stroke="${o.line}" stroke-width="${(1.5 + t * 4).toFixed(1)}" opacity="${(o.lineOp * (0.5 + t * 0.5)).toFixed(2)}"/>`; }
    return m;
  }
  /** a whole room: ceiling, both side walls, back wall, floor, all converging on vp. back=[x0,y0,x1,y1] */
  function room(vp, back, o) {
    o = Object.assign({ wall: "#6a5a70", side: "#4e4056", ceil: "#2e2634", floor: "#4a3a3a", line: "#9a8aa0", lineOp: 0.4, panels: 0, panel: null }, o);
    const [x0, y0, x1, y1] = back;
    let m = `<path d="M-300 -200 L2220 -200 L${x1} ${y0} L${x0} ${y0} Z" fill="${o.ceil}"/>
      <path d="M-300 -200 L${x0} ${y0} L${x0} ${y1} L-300 1280 Z" fill="${o.side}"/>
      <path d="M2220 -200 L${x1} ${y0} L${x1} ${y1} L2220 1280 Z" fill="${shade(o.side, -0.12)}"/>
      <rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" fill="${o.wall}"/>
      <path d="M-300 1280 L${x0} ${y1} L${x1} ${y1} L2220 1280 Z" fill="${o.floor}"/>`;
    for (let i = 1; i < 9; i++) { const f = i / 9; m += `<path d="M${lerp(-300, x0, 0)} ${lerp(1280, y1, 0)}" stroke="none"/>`; }
    // floor boards converging on vp
    for (let i = -6; i <= 6; i++) { const fx = lerp(x0, x1, 0.5 + i / 9); m += `<path d="M${fx} ${y1} L${vp[0] + (fx - vp[0]) * 4.2} 1280" stroke="${o.line}" stroke-width="3" opacity="${o.lineOp}"/>`; }
    for (let i = 1; i <= 6; i++) { const t = Math.pow(i / 6, 2), y = lerp(y1, 1080, t); m += `<path d="M${lerp(x0, -300, t * 1.4)} ${y}H${lerp(x1, 2220, t * 1.4)}" stroke="${o.line}" stroke-width="${2 + t * 3}" opacity="${o.lineOp}"/>`; }
    // wall corner lines
    m += `<path d="M${x0} ${y0}V${y1}M${x1} ${y0}V${y1}M${x0} ${y0}H${x1}" stroke="${OL}" stroke-width="5" opacity=".7"/>`;
    // side panels foreshortened toward vp
    if (o.panels) for (let i = 1; i <= o.panels; i++) { const t = i / (o.panels + 1), xl = lerp(-300, x0, t), top = lerp(-200, y0, t), bot = lerp(1280, y1, t); m += `<path d="M${xl} ${top}V${bot}" stroke="${shade(o.side, -0.4)}" stroke-width="${(8 - t * 5).toFixed(1)}" opacity=".7"/><path d="M${lerp(2220, x1, t)} ${top}V${bot}" stroke="${shade(o.side, -0.5)}" stroke-width="${(8 - t * 5).toFixed(1)}" opacity=".7"/>`; }
    return m;
  }

  K.cine = { LOOKS, look, key, fog, dust, rays, haze, bokeh };
  K.persp = { facades, floor, room, lerp };
})(window.K);
