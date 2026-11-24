/* Look & feel: lighting, vignette, grain, labels, handwritten note, VHS transition, props. */
(function (K) {
  "use strict";
  const { OL, S, P, shade, uid } = K;
  const FONT = `"Inter","Noto Sans","DejaVu Sans",sans-serif`;
  const HAND = `"Caveat","Segoe Script","Comic Sans MS","Noto Sans",cursive`;

  /** Soft light pool (blend mode gives "lit by this light" without hard shapes). */
  function glow(x, y, rx, ry, color, op, blend) {
    const id = uid("gl");
    return `<defs><radialGradient id="${id}"><stop offset="0" stop-color="${color}" stop-opacity="1"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></radialGradient></defs>
      <ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="url(#${id})" opacity="${op}" style="mix-blend-mode:${blend || "screen"}"/>`;
  }
  /** Light cone, e.g. from a door or window. */
  function cone(x1, y1, x2, y2, x3, y3, x4, y4, color, op) {
    const id = uid("cn");
    return `<defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${color}" stop-opacity="${op}"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="M${x1} ${y1} L${x2} ${y2} L${x3} ${y3} L${x4} ${y4} Z" fill="url(#${id})" style="mix-blend-mode:screen"/>`;
  }
  /** Colour grade for a whole shot: multiply tint + dark corners. */
  function grade(color, op) { return `<rect width="1920" height="1080" fill="${color}" opacity="${op}" style="mix-blend-mode:multiply"/>`; }

  /** Pop label ("AGE 9" style). Returns markup with pivot group "<id>" so the director can pop it. */
  function label(id, text, x, y, o) {
    o = Object.assign({ bg: "#ffffff", fg: "#241418", size: 56, rot: -3 }, o);
    const w = Math.max(160, text.length * o.size * 0.62 + 56), h = o.size + 40;
    return P(id, x, y, `<g transform="rotate(${o.rot})"><rect x="${-w / 2 + 7}" y="${-h / 2 + 8}" width="${w}" height="${h}" rx="14" fill="#000" opacity=".35"/>
      <rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="14" fill="${o.bg}" ${S(6)}/>
      <text x="0" y="${o.size * 0.35}" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="${o.size}" fill="${o.fg}" letter-spacing="1">${text}</text></g>`);
  }
  /** Name tag following a character (small). */
  function tag(id, text, x, y) { return label(id, text, x, y, { size: 34, bg: "#f4ecd8", rot: 0 }); }

  /** Handwritten red note on paper. Text appears by a wipe (group "<id>_wipe" scaleX 1->0). */
  function note(id, lines, x, y, o) {
    o = Object.assign({ w: 520, size: 52, rot: -4, paper: "#f5eccf", ink: "#c4252d" }, o);
    const lh = o.size * 1.15, h = lines.length * lh + 64, w = o.w;
    const txt = lines.map((l, i) => `<text x="${-w / 2 + 34}" y="${-h / 2 + 62 + i * lh}" font-family='${HAND}' font-weight="700" font-size="${o.size}" fill="${o.ink}">${l}</text>`).join("");
    return P(id, x, y, `<g transform="rotate(${o.rot})">
      <rect x="${-w / 2 + 9}" y="${-h / 2 + 12}" width="${w}" height="${h}" fill="#000" opacity=".3"/>
      <rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" fill="${o.paper}" ${S(5)}/>
      ${Array.from({ length: lines.length }, (_, i) => `<path d="M${-w / 2 + 20} ${-h / 2 + 76 + i * lh}H${w / 2 - 20}" stroke="#b9c7d8" stroke-width="2"/>`).join("")}
      <rect x="${-30}" y="${-h / 2 - 16}" width="60" height="28" fill="#e9e4d2" opacity=".85" ${S(3)}/>
      ${txt}
      ${P(id + "_wipe", w / 2 - 8, 0, `<rect x="${-w + 16}" y="${-h / 2 + 8}" width="${w - 16}" height="${h - 16}" fill="${o.paper}"/>`)}</g>`);
  }

  /* ---------- props ---------- */
  const props = {
    briefcase: (x, y, c) => P("pr", x, y, `<rect x="-46" y="-8" width="92" height="64" rx="8" fill="${c || "#7a4a2b"}" ${S(5)}/><path d="M-18 -8V-22H18V-8" fill="none" ${S(5)}/><rect x="-6" y="14" width="12" height="12" fill="#f3c64a" ${S(3)}/>`),
    suitcase: (x, y) => `<g transform="translate(${x} ${y})"><rect x="-50" y="-70" width="100" height="78" rx="9" fill="#3d6a9c" ${S(5)}/><path d="M-20 -70V-86H20V-70" fill="none" ${S(5)}/><rect x="-50" y="-34" width="100" height="10" fill="#2c4f78" opacity=".8"/><circle cx="-30" cy="14" r="8" fill="#222" ${S(3)}/><circle cx="30" cy="14" r="8" fill="#222" ${S(3)}/></g>`,
    medal: (x, y) => `<g transform="translate(${x} ${y})"><path d="M-16 -40L0 0L16 -40Z" fill="#c4252d" ${S(4)}/><circle cx="0" cy="14" r="26" fill="#f3c64a" ${S(5)}/><circle cx="0" cy="14" r="15" fill="none" stroke="${shade("#f3c64a", -0.3)}" stroke-width="4"/><path d="M-8 14L0 4L8 14L0 24Z" fill="${shade("#f3c64a", -0.25)}"/></g>`,
    camera: (id, x, y) => P(id, x, y, `<rect x="-62" y="-40" width="124" height="74" rx="10" fill="#2a2a32" ${S(5)}/><rect x="-92" y="-30" width="44" height="52" rx="6" fill="#3a3a46" ${S(5)}/><circle cx="-76" cy="-4" r="16" fill="#101820" ${S(4)}/><circle cx="-76" cy="-4" r="7" fill="#4a7ab0"/><rect x="-30" y="-64" width="70" height="26" rx="6" fill="#3a3a46" ${S(5)}/><circle cx="46" cy="-24" r="8" fill="#e22" ${S(3)}/>`),
    spot: (x, y, rot) => `<g transform="translate(${x} ${y}) rotate(${rot})"><rect x="-26" y="-20" width="52" height="40" rx="6" fill="#2a2a32" ${S(5)}/><path d="M26 -16L60 -30V30L26 16Z" fill="#f3e6b0" ${S(4)}/><path d="M-4 20V70M-4 70L-30 110M-4 70L22 110" stroke="${OL}" stroke-width="7" fill="none" stroke-linecap="round"/></g>`,
    crib: (x, y) => `<g transform="translate(${x} ${y})"><rect x="-190" y="-150" width="380" height="14" fill="#e9d9b5" ${S(5)}/><rect x="-190" y="-14" width="380" height="14" fill="#e9d9b5" ${S(5)}/>${Array.from({ length: 11 }, (_, i) => `<rect x="${-180 + i * 36}" y="-150" width="12" height="150" fill="#f3e6c8" ${S(4)}/>`).join("")}<rect x="-204" y="-190" width="20" height="230" rx="6" fill="#e0c690" ${S(5)}/><rect x="184" y="-190" width="20" height="230" rx="6" fill="#e0c690" ${S(5)}/></g>`,
    blanket: (x, y) => `<g transform="translate(${x} ${y})"><path d="M-170 -58C-100 -80 100 -80 170 -58V-6H-170Z" fill="#9fc3df" ${S(5)}/><path d="M-170 -58C-100 -80 100 -80 170 -58" fill="none" stroke="#fff" stroke-width="10" opacity=".35"/>${Array.from({ length: 6 }, (_, i) => `<circle cx="${-120 + i * 48}" cy="-34" r="7" fill="#fff" opacity=".6"/>`).join("")}</g>`,
    scales: (x, y) => `<g transform="translate(${x} ${y})"><path d="M0 -150V0M-60 0H60" stroke="${OL}" stroke-width="8"/><path d="M-100 -130H100" stroke="${OL}" stroke-width="8"/>${[-100, 100].map((d) => `<path d="M${d} -130L${d - 34} -72H${d + 34}Z" fill="none" ${S(4)}/><path d="M${d - 40} -72Q${d} -40 ${d + 40} -72Z" fill="#f3c64a" ${S(4)}/>`).join("")}</g>`,
    desk: (x, y, w) => `<g transform="translate(${x} ${y})"><rect x="${-w / 2}" y="-110" width="${w}" height="22" fill="#7a4a2b" ${S(6)}/><rect x="${-w / 2 + 14}" y="-88" width="46" height="88" fill="#5e3a22" ${S(6)}/><rect x="${w / 2 - 60}" y="-88" width="46" height="88" fill="#5e3a22" ${S(6)}/><rect x="-40" y="-150" width="80" height="40" rx="4" fill="#ede3c8" ${S(4)}/><path d="M-26 -134h52M-26 -122h36" stroke="#8a7a5a" stroke-width="4"/></g>`,
    heart: (id, x, y) => P(id, x, y, `<path d="M0 30C-60 -10 -40 -56 -10 -40C-4 -36 0 -30 0 -26C0 -30 4 -36 10 -40C40 -56 60 -10 0 30Z" fill="#e4483f" ${S(5)}/><path d="M-26 -22C-22 -34 -12 -34 -8 -30" stroke="#fff" stroke-width="5" fill="none" opacity=".6" stroke-linecap="round"/>`),
    sparkle: (id, x, y, c) => P(id, x, y, `<path d="M0 -36Q4 -4 36 0Q4 4 0 36Q-4 4 -36 0Q-4 -4 0 -36Z" fill="${c || "#fff4b0"}" ${S(3)}/>`),
    coin: (id, x, y) => P(id, x, y, `<circle r="22" fill="#f3c64a" ${S(4)}/><text y="9" text-anchor="middle" font-family='${FONT}' font-weight="800" font-size="26" fill="#8a5a10">$</text>`),
    tv: (id, x, y, w, h) => `<g transform="translate(${x} ${y})"><rect x="${-w / 2}" y="${-h}" width="${w}" height="${h}" rx="18" fill="#3a2a22" ${S(7)}/><rect x="${-w / 2 + 22}" y="${-h + 22}" width="${w - 44}" height="${h - 60}" rx="10" fill="#cfe7ee"/>${P(id, 0, 0, `<rect x="${-w / 2 + 22}" y="${-h + 22}" width="${w - 44}" height="${h - 60}" rx="10" fill="#fff" opacity="0"/>`)}</g>`,
  };

  /* ---------- global overlays (defs + vignette + scan lines) ---------- */
  function globalDefs() {
    return `<defs>
      <radialGradient id="vig" cx="50%" cy="50%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#0a0508" stop-opacity=".62"/></radialGradient>
      <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="2" fill="#000"/></pattern>
      <filter id="vhs" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
        <feTurbulence id="vhsT" type="fractalNoise" baseFrequency="0.002 0.06" numOctaves="1" seed="3" result="n"/>
        <feDisplacementMap id="vhsD" in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G"/>
      </filter></defs>`;
  }
  function overlays() {
    return `<rect width="1920" height="1080" fill="url(#vig)"/>
      <rect width="1920" height="1080" fill="url(#scan)" opacity=".05"/>`;
  }
  /** VHS transition overlay: bars + REW icon + year stamp. Visible only during a cut (director toggles). */
  function vhsOverlay() {
    const bars = Array.from({ length: 6 }, (_, i) => `${P("vb" + i, 0, 0, `<rect x="0" y="${80 + i * 170}" width="1920" height="${14 + (i % 3) * 14}" fill="${i % 2 ? "#00e5ff" : "#ff2d95"}" opacity=".55" style="mix-blend-mode:screen"/>`)}`).join("");
    return `<g id="vhsov" style="visibility:hidden">
      <rect width="1920" height="1080" fill="#fff" opacity=".0" id="vhsflash"/>
      ${bars}
      <g transform="translate(110 120)"><path d="M0 0L60 -36V36Z M60 0L120 -36V36Z" fill="#fff" ${S(4)}/><text x="148" y="14" font-family='${FONT}' font-weight="800" font-size="44" fill="#fff" stroke="#000" stroke-width="2">REW</text></g>
      <text id="vhsyear" x="1810" y="150" text-anchor="end" font-family='${FONT}' font-weight="800" font-size="84" fill="#fff" stroke="#000" stroke-width="3" letter-spacing="3"></text>
    </g>`;
  }

  K.fx = { glow, cone, grade, label, tag, note, props, globalDefs, overlays, vhsOverlay, FONT, HAND };
})(window.K);
