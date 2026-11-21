/* NFP Docu kit: articulated cartoon character rig (original design).
   Every moving part is an inner <g data-p="name"> whose ORIGIN is its pivot, so tweens turn around joints.
   Coordinates: feet at (0,0), y grows downward. */
(function (K) {
  "use strict";
  const { OL, S, P, shade, uid } = K;

  const BUILDS = {
    kid:   { legH: 86,  torsoH: 98,  torsoW: 96,  shX: 52, armU: 52, armF: 46, armW: 26, hand: 15, neck: 12, headS: 1.0,  legW: 30, shoe: 34 },
    teen:  { legH: 132, torsoH: 124, torsoW: 108, shX: 58, armU: 70, armF: 64, armW: 28, hand: 16, neck: 16, headS: 0.84, legW: 34, shoe: 40 },
    adult: { legH: 170, torsoH: 150, torsoW: 128, shX: 68, armU: 90, armF: 82, armW: 32, hand: 18, neck: 22, headS: 0.66, legW: 42, shoe: 50 },
  };

  /* ---------- hair styles (head-local coordinates, head centre = (0,-92)) ---------- */
  function circlesUnion(list, fill, strokeW) {
    const o = list.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${OL}" stroke="${OL}" stroke-width="${strokeW}"/>`).join("");
    const f = list.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"/>`).join("");
    return o + f;
  }
  const HAIR = {
    wavy_long(c) {
      const hi = shade(c, 0.28);
      return {
        back: `<path d="M-90 -96 C-104 -176 -56 -196 0 -196 C60 -196 104 -176 90 -96 C100 -40 118 6 96 40 C84 62 62 50 54 24 L-54 24 C-62 50 -84 62 -96 40 C-118 6 -100 -40 -90 -96 Z" fill="${c}" ${S(6)}/>
               <path d="M-84 -60 C-92 -20 -98 10 -88 30 M84 -60 C92 -20 98 10 88 30" stroke="${hi}" stroke-width="6" fill="none" stroke-linecap="round" opacity=".6"/>`,
        front: `<path d="M-88 -92 C-100 -164 -44 -190 6 -188 C62 -186 98 -154 88 -92 C74 -128 42 -142 10 -136 C-22 -132 -52 -118 -88 -92 Z" fill="${c}" ${S(6)}/>
                <path d="M-60 -150 C-30 -168 14 -170 46 -158" stroke="${hi}" stroke-width="7" fill="none" stroke-linecap="round" opacity=".75"/>
                <path d="M-8 -136 C-20 -122 -34 -114 -50 -110" stroke="${shade(c, -0.3)}" stroke-width="4" fill="none" stroke-linecap="round" opacity=".6"/>`,
      };
    },
    bob(c) {
      const hi = shade(c, 0.25);
      return {
        back: `<path d="M-92 -92 C-102 -176 -52 -196 0 -196 C52 -196 102 -176 92 -92 C98 -50 96 -22 84 -8 L-84 -8 C-96 -22 -98 -50 -92 -92 Z" fill="${c}" ${S(6)}/>`,
        front: `<path d="M-90 -92 C-98 -160 -40 -186 6 -184 C60 -182 100 -156 90 -92 C80 -108 70 -122 60 -128 L-60 -128 C-72 -118 -80 -106 -90 -92 Z" fill="${c}" ${S(6)}/>
                <path d="M-62 -158 C-30 -172 10 -172 44 -160" stroke="${hi}" stroke-width="7" fill="none" stroke-linecap="round" opacity=".7"/>`,
      };
    },
    big80s(c) {
      const hi = shade(c, 0.22);
      const blobs = [[-70, -150, 52], [-20, -184, 58], [38, -182, 58], [84, -146, 50], [-98, -100, 40], [100, -98, 42], [-90, -48, 34], [92, -44, 34], [0, -150, 70]];
      return {
        back: circlesUnion(blobs, c, 12),
        front: `<path d="M-76 -128 C-50 -150 -10 -146 10 -128 C30 -148 64 -150 80 -126" fill="none" stroke="${hi}" stroke-width="7" stroke-linecap="round" opacity=".7"/>
                <path d="M-86 -96 C-80 -126 -50 -138 -20 -134 C-30 -118 -60 -108 -86 -96 Z M88 -96 C82 -126 52 -138 22 -134 C32 -118 62 -108 88 -96 Z" fill="${c}" ${S(5)}/>`,
      };
    },
    short_man(c) {
      const hi = shade(c, 0.22);
      return {
        back: "",
        front: `<path d="M-88 -98 C-96 -170 -40 -190 6 -188 C60 -186 98 -160 88 -98 C74 -124 44 -138 -4 -134 C-40 -130 -66 -120 -88 -98 Z" fill="${c}" ${S(6)}/>
                <path d="M-56 -160 C-24 -174 18 -174 48 -162" stroke="${hi}" stroke-width="6" fill="none" stroke-linecap="round" opacity=".6"/>`,
      };
    },
    slick(c) {
      return {
        back: "",
        front: `<path d="M-88 -98 C-92 -172 -30 -194 20 -190 C66 -186 96 -158 88 -98 C70 -140 20 -150 -20 -146 C-52 -142 -74 -126 -88 -98 Z" fill="${c}" ${S(6)}/>
                <path d="M-40 -170 C-10 -182 30 -180 56 -168" stroke="${shade(c, 0.3)}" stroke-width="6" fill="none" stroke-linecap="round" opacity=".6"/>`,
      };
    },
    baby_tuft(c) {
      return {
        back: "",
        front: `<path d="M-30 -168 C-26 -200 6 -212 22 -196 C10 -196 8 -184 -4 -176 Z" fill="${c}" ${S(5)}/>`,
      };
    },
    none() { return { back: "", front: "" }; },
  };

  /* ---------- outfits (torso-local coordinates: hip centre = (0,0), up is negative) ---------- */
  function outfit(kind, b, c) {
    const tw = b.torsoW, th = b.torsoH, top = c.top;
    const body = `<path d="M${-tw * 0.46} 0 Q${-tw * 0.52} ${-th * 0.5} ${-tw * 0.42} ${-th + 4} Q0 ${-th - 10} ${tw * 0.42} ${-th + 4} Q${tw * 0.52} ${-th * 0.5} ${tw * 0.46} 0 Z" fill="${top}" ${S(6)}/>
                  <path d="M${tw * 0.18} 0 Q${tw * 0.3} ${-th * 0.5} ${tw * 0.26} ${-th + 6} Q${tw * 0.5} ${-th * 0.5} ${tw * 0.46} 0 Z" fill="${shade(top, -0.16)}" opacity=".55"/>`;
    let extra = "";
    if (kind === "kidtee") {
      const y = -th * 0.5;
      extra = `<path d="M${-tw * 0.45} ${y} l${tw * 0.12} -16 l${tw * 0.12} 16 l${tw * 0.12} -16 l${tw * 0.12} 16 l${tw * 0.12} -16 l${tw * 0.12} 16 l${tw * 0.12} -16 l${tw * 0.1} 14" fill="none" stroke="${c.accent || "#e4483f"}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
               <path d="M${-tw * 0.22} ${-th + 2} Q0 ${-th + 20} ${tw * 0.22} ${-th + 2}" fill="${shade(top, 0.25)}" ${S(5)}/>`;
    } else if (kind === "suit") {
      extra = `<path d="M${-tw * 0.17} ${-th + 2} L0 ${-th * 0.55} L${tw * 0.17} ${-th + 2} Z" fill="#f3f0ea" ${S(4)}/>
               <path d="M-7 ${-th + 12} L0 ${-th * 0.62} L7 ${-th + 12} Z" fill="${c.accent || "#a63a3a"}" ${S(3)}/>
               <path d="M0 ${-th * 0.62} L-9 ${-th * 0.28} L0 ${-th * 0.18} L9 ${-th * 0.28} Z" fill="${c.accent || "#a63a3a"}" ${S(3)}/>
               <path d="M${-tw * 0.17} ${-th + 2} L${-tw * 0.06} ${-th * 0.4} L${-tw * 0.3} ${-th * 0.2}" fill="none" stroke="${shade(top, 0.3)}" stroke-width="3" opacity=".6"/>`;
    } else if (kind === "blazer") {
      extra = `<path d="M${-tw * 0.2} ${-th + 2} L${-tw * 0.02} ${-th * 0.5} L${tw * 0.02} ${-th * 0.5} L${tw * 0.2} ${-th + 2} L${tw * 0.1} ${-th + 4} L0 ${-th * 0.72} L${-tw * 0.1} ${-th + 4} Z" fill="${c.under || "#f6e9d6"}" ${S(4)}/>
               <path d="M0 ${-th * 0.5} L0 0" stroke="${shade(top, -0.3)}" stroke-width="4"/>
               <circle cx="${tw * 0.06}" cy="${-th * 0.34}" r="4.5" fill="${c.accent || "#f3c64a"}" ${S(2)}/>
               <path d="M${-tw * 0.4} ${-th + 6} Q${-tw * 0.52} ${-th + 2} ${-tw * 0.46} ${-th + 22}" fill="${shade(top, 0.12)}" stroke="none" opacity=".7"/>`;
    } else if (kind === "track") {
      extra = `<path d="M${-tw * 0.44} ${-th + 8} L${-tw * 0.4} 0 M${tw * 0.44} ${-th + 8} L${tw * 0.4} 0" stroke="${c.accent || "#f6f2e8"}" stroke-width="9" stroke-linecap="round"/>
               <path d="M0 ${-th + 4} L0 0" stroke="${shade(top, -0.3)}" stroke-width="4"/>
               <path d="M${-tw * 0.2} ${-th + 2} Q0 ${-th + 16} ${tw * 0.2} ${-th + 2}" fill="${c.accent || "#f6f2e8"}" ${S(4)}/>`;
    } else if (kind === "onesie") {
      extra = `<circle cx="0" cy="${-th * 0.5}" r="${tw * 0.14}" fill="${shade(top, 0.3)}" ${S(3)}/>`;
    }
    return body + extra;
  }

  /* ---------- eyes / brows / mouths ---------- */
  const MOUTHS = {
    neutral: () => `<path d="M-12 0 Q0 5 12 0" fill="none" ${S(5)}/>`,
    smile: () => `<path d="M-22 -4 Q0 26 22 -4 Q0 4 -22 -4 Z" fill="#7a2630" ${S(5)}/><path d="M-15 -1 Q0 7 15 -1 L13 3 Q0 10 -13 3 Z" fill="#fff"/>`,
    grin: () => `<path d="M-24 -6 Q0 34 24 -6 Z" fill="#7a2630" ${S(5)}/><path d="M-20 -4 Q0 4 20 -4 L18 4 Q0 10 -18 4 Z" fill="#fff"/><path d="M-12 14 Q0 22 12 14 Q0 8 -12 14 Z" fill="#d9565e"/>`,
    open: () => `<ellipse cx="0" cy="6" rx="14" ry="17" fill="#7a2630" ${S(5)}/><ellipse cx="0" cy="14" rx="9" ry="6" fill="#d9565e"/>`,
    o: () => `<ellipse cx="0" cy="4" rx="9" ry="12" fill="#7a2630" ${S(5)}/>`,
    sad: () => `<path d="M-16 8 Q0 -8 16 8" fill="none" ${S(5)}/>`,
    smirk: () => `<path d="M-14 3 Q6 10 20 -6" fill="none" ${S(5)}/><path d="M20 -6 l4 -3" ${S(4)}/>`,
    worried: () => `<path d="M-16 4 Q-8 -3 0 4 Q8 11 16 4" fill="none" ${S(5)}/>`,
  };
  // brow pose per expression: [y offset, rotation] in "worried-positive" terms (left brow is mirrored in code)
  const EXPR = {
    neutral:   { by: 0,   br: 0,   ey: 1,    mouth: "neutral", blush: 0.25 },
    happy:     { by: -5,  br: -6,  ey: 0.92, mouth: "smile",   blush: 0.55 },
    laugh:     { by: -8,  br: -8,  ey: 0.55, mouth: "grin",    blush: 0.6 },
    surprised: { by: -16, br: -4,  ey: 1.2,  mouth: "o",       blush: 0.2 },
    worried:   { by: -4,  br: 16,  ey: 1.06, mouth: "worried", blush: 0.15 },
    sad:       { by: 0,   br: 20,  ey: 0.86, mouth: "sad",     blush: 0.1 },
    smirk:     { by: -3,  br: -10, ey: 0.9,  mouth: "smirk",   blush: 0.3 },
    determined:{ by: 4,   br: -14, ey: 0.9,  mouth: "neutral", blush: 0.2 },
    shout:     { by: -6,  br: 6,   ey: 1.0,  mouth: "open",    blush: 0.3 },
  };

  function head(spec, b) {
    const sk = spec.skin, sh = shade(sk, -0.16);
    const e = spec.eyes || {};
    const ex = e.ex || 17, ey = e.ey || 22, ir = e.ir || 13, eyeX = e.x || 32, eyeY = -88;
    const hair = (HAIR[spec.hair || "none"] || HAIR.none)(spec.hairColor || "#3b2118");
    const cid = uid("clip");
    const eye = (side) => {
      const sx = side === "L" ? -1 : 1;
      return `<g transform="translate(${sx * eyeX} ${eyeY})">
        <clipPath id="${cid}${side}"><ellipse cx="0" cy="0" rx="${ex}" ry="${ey}"/></clipPath>
        ${P("eye" + side, 0, 0, `<ellipse cx="0" cy="0" rx="${ex}" ry="${ey}" fill="#fff" ${S(4)}/>
          <g clip-path="url(#${cid}${side})">${P("iris" + side, 0, 2, `<circle r="${ir}" fill="${e.iris || "#6b3a22"}"/><circle r="${ir * 0.58}" fill="#1b1014"/><circle cx="${-ir * 0.34}" cy="${-ir * 0.4}" r="${ir * 0.3}" fill="#fff"/><circle cx="${ir * 0.3}" cy="${ir * 0.32}" r="${ir * 0.14}" fill="#fff" opacity=".8"/>`)}
          ${P("lid" + side, 0, -3 * ey - 8, `<rect x="${-ex - 4}" y="0" width="${ex * 2 + 8}" height="${ey * 2 + 6}" fill="${sk}"/><path d="M${-ex - 4} ${ey * 2 + 5} Q0 ${ey * 2 + 10} ${ex + 4} ${ey * 2 + 5}" fill="none" ${S(5)}/>`)}</g>
          <path d="M${-ex - 2} ${-ey + 3} Q0 ${-ey - 7} ${ex + 2} ${-ey + 3}" fill="none" ${S(5)}/>
          <path d="M${sx * (ex + 1)} ${-ey + 4} l${sx * 8} -6" fill="none" ${S(4)}/>`)}
      </g>`;
    };
    const brow = (side) => {
      const sx = side === "L" ? -1 : 1;
      return P("brow" + side, sx * eyeX, eyeY - ey - 14, `<path d="M${-ex - 2} 4 Q0 -7 ${ex + 2} 3" fill="none" stroke="${spec.hairColor || "#3b2118"}" stroke-width="8" stroke-linecap="round"/>`);
    };
    const mouths = Object.keys(MOUTHS).map((k) => `<g data-m="${k}" style="display:${k === "neutral" ? "inline" : "none"}">${MOUTHS[k]()}</g>`).join("");
    const acc = [];
    if (spec.glasses) acc.push(`<g fill="rgba(255,255,255,.12)" ${S(5)}><circle cx="${-eyeX}" cy="${eyeY}" r="${ex + 12}"/><circle cx="${eyeX}" cy="${eyeY}" r="${ex + 12}"/><path d="M${-eyeX + ex + 12} ${eyeY} L${eyeX - ex - 12} ${eyeY}" fill="none"/></g>`);
    if (spec.bow) acc.push(`<g transform="translate(-52 -176) rotate(-18)"><path d="M0 0 L-34 -20 Q-44 0 -34 20 Z M0 0 L34 -20 Q44 0 34 20 Z" fill="${spec.bow}" ${S(5)}/><circle r="9" fill="${shade(spec.bow, -0.2)}" ${S(4)}/><path d="M-26 -8 L-12 -4 M26 -8 L12 -4" stroke="${shade(spec.bow, 0.35)}" stroke-width="3" fill="none" stroke-linecap="round"/></g>`);
    return `${hair.back}
      <ellipse cx="-80" cy="-88" rx="14" ry="19" fill="${sk}" ${S(5)}/><ellipse cx="80" cy="-88" rx="14" ry="19" fill="${sk}" ${S(5)}/>
      <path d="M-82 -92 C-82 -152 -46 -174 0 -174 C46 -174 82 -152 82 -92 C82 -34 46 -4 0 -4 C-46 -4 -82 -34 -82 -92 Z" fill="${sk}" ${S(6)}/>
      <path d="M52 -158 C84 -138 90 -64 40 -12 C70 -60 66 -132 52 -158 Z" fill="${sh}" opacity=".5"/>
      ${P("blush", 0, 0, `<ellipse cx="-52" cy="-58" rx="19" ry="11" fill="#ff6f7a"/><ellipse cx="52" cy="-58" rx="19" ry="11" fill="#ff6f7a"/>`).replace('<g data-p="blush">', '<g data-p="blush" opacity=".25">')}
      ${eye("L")}${eye("R")}${brow("L")}${brow("R")}
      <path d="M-5 -66 Q0 -58 6 -64" fill="none" stroke="${sh}" stroke-width="4" stroke-linecap="round"/>
      <g transform="translate(0 -34)">${mouths}</g>
      ${hair.front}${acc.join("")}`;
  }

  function limb(side, b, c, ctx) {
    const sx = side === "L" ? -1 : 1;
    const sleeve = c.top, skin = c.skin, long = c.sleeve !== "short";
    const aw = b.armW;
    const hand = `<circle cx="0" cy="${b.armF + 8}" r="${b.hand}" fill="${skin}" ${S(5)}/>`;
    const fore = `<rect x="${-aw * 0.42}" y="-6" width="${aw * 0.84}" height="${b.armF + 8}" rx="${aw * 0.4}" fill="${long ? sleeve : skin}" ${S(5)}/>${hand}`;
    const upper = `<rect x="${-aw / 2}" y="-8" width="${aw}" height="${b.armU + 12}" rx="${aw * 0.45}" fill="${sleeve}" ${S(5)}/>`;
    return P("arm" + side, sx * b.shX, ctx.shY, upper + P("fore" + side, 0, b.armU, fore));
  }

  function leg(side, b, c) {
    const sx = side === "L" ? -1 : 1, lw = b.legW, len = b.legH;
    const pants = `<rect x="${-lw / 2}" y="-8" width="${lw}" height="${len - 2}" rx="${lw * 0.4}" fill="${c.pants}" ${S(5)}/>`;
    const shoe = `<path d="M${-lw * 0.62} ${len - 12} Q${-lw * 0.7} ${len + 6} ${-lw * 0.4} ${len + 6} L${lw * 0.2 + b.shoe * 0.5} ${len + 6} Q${lw * 0.2 + b.shoe * 0.7} ${len - 2} ${lw * 0.55} ${len - 12} Z" fill="${c.shoe}" ${S(5)}/>`;
    return P("leg" + side, sx * b.torsoW * 0.2, -b.legH, pants + shoe);
  }

  /** actor(spec) -> SVG markup of one character. spec: build, skin, hair, hairColor, top, pants, shoe, outfit, glasses, bow, skirt, eyes */
  function actor(spec) {
    spec = Object.assign({ build: "kid", skin: "#e2a679", hair: "bob", hairColor: "#3b2118", top: "#f0b63a", pants: "#3b4a8c", shoe: "#2b2230", outfit: "kidtee", accent: "#e4483f" }, spec);
    const b = BUILDS[spec.build];
    const shY = -b.legH - b.torsoH + 26;
    const yHead = -b.legH - b.torsoH - b.neck + 8;
    const c = spec;
    const skirt = spec.skirt ? `<path d="M${-b.torsoW * 0.5} ${-b.legH + 6} L${-b.torsoW * 0.62} ${-b.legH + b.legH * 0.55} Q0 ${-b.legH + b.legH * 0.66} ${b.torsoW * 0.62} ${-b.legH + b.legH * 0.55} L${b.torsoW * 0.5} ${-b.legH + 6} Z" fill="${spec.skirt}" ${S(6)}/>` : "";
    return `<g data-actor>
      ${P("shadow", 0, 0, `<ellipse cx="0" cy="4" rx="${b.torsoW * 0.8}" ry="14" fill="#000" opacity=".3"/>`)}
      ${P("root", 0, 0, `
        ${leg("L", b, c)}${leg("R", b, c)}
        ${P("torso", 0, -b.legH, outfit(spec.outfit, b, c) + skirt.replace(/-?\d+(\.\d+)? /, (m) => m))}
        <rect x="${-b.torsoW * 0.1}" y="${yHead + b.neck - 6}" width="${b.torsoW * 0.2}" height="${b.neck + 8}" fill="${shade(spec.skin, -0.1)}" ${S(5)}/>
        ${limb("L", b, c, { shY })}${limb("R", b, c, { shY })}
        <g transform="translate(0 ${yHead}) scale(${b.headS})">${P("head", 0, 0, head(spec, b))}</g>`)}
    </g>`;
  }

  K.chars = { actor, BUILDS, EXPR, MOUTHS };
})(window.K);
