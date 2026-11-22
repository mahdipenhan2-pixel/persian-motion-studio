/* NFP Docu kit v2: articulated cartoon characters with real age stages.
   Builds: baby, child, teen, woman, man (aliases kid->child, adult->man).
   Every moving part is an inner <g data-p="name"> whose origin is its pivot. Feet at (0,0), y grows downward.
   Parts: root, torso, head, hairBack, hairFall, armL/R + foreL/R, legL/R + shinL/R + shoeL/R, eyeL/R, irisL/R, lidL/R, browL/R, blush. */
(function (K) {
  "use strict";
  const { OL, S, P, shade, mixc, uid } = K;
  const ALIAS = { kid: "child", adult: "man" };
  const BUILDS = {
    baby:  { legH: 30,  torsoH: 54,  sw: 38, ww: 36, hw: 40, shX: 40, armU: 28, armF: 24, armW: 20, hand: 10, neck: 8,  headS: 0.66, legW: 22, shoe: 20, fw: 86, ch: -6 },
    child: { legH: 92,  torsoH: 96,  sw: 46, ww: 44, hw: 46, shX: 52, armU: 52, armF: 46, armW: 26, hand: 15, neck: 12, headS: 0.94, legW: 30, shoe: 34, fw: 82, ch: -4 },
    teen:  { legH: 150, torsoH: 122, sw: 48, ww: 40, hw: 50, shX: 54, armU: 68, armF: 62, armW: 24, hand: 15, neck: 15, headS: 0.78, legW: 32, shoe: 40, fw: 76, ch: 0 },
    woman: { legH: 196, torsoH: 138, sw: 50, ww: 35, hw: 58, shX: 56, armU: 80, armF: 74, armW: 23, hand: 15, neck: 19, headS: 0.60, legW: 38, shoe: 46, fw: 68, ch: 8 },
    man:   { legH: 170, torsoH: 150, sw: 62, ww: 56, hw: 56, shX: 68, armU: 90, armF: 82, armW: 32, hand: 18, neck: 22, headS: 0.66, legW: 42, shoe: 50, fw: 82, ch: -4 },
  };
  // face parameters per life stage (identity stays: same hair colour, skin tone, brown eyes, strong brows)
  const FACE = {
    baby:  { ex: 18, ey: 22, ir: 15, x: 30, brow: 5,  arch: 3, lash: 0, lip: 0, nose: "dot" },
    child: { ex: 17, ey: 22, ir: 13, x: 32, brow: 8,  arch: 5, lash: 0, lip: 0, nose: "curve" },
    teen:  { ex: 18, ey: 20, ir: 12, x: 32, brow: 9,  arch: 7, lash: 1, lip: 1, nose: "curve" },
    woman: { ex: 20, ey: 17, ir: 11, x: 31, brow: 11, arch: 11, lash: 2, lip: 2, nose: "slim" },
    man:   { ex: 17, ey: 22, ir: 13, x: 32, brow: 9,  arch: 4, lash: 0, lip: 0, nose: "curve" },
  };

  function circlesUnion(list, fill, w) {
    return list.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${OL}" stroke="${OL}" stroke-width="${w}"/>`).join("") +
           list.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"/>`).join("");
  }

  /* ---------- hair: {back (inside head, behind face), front (over forehead), long (behind torso, own part), fall (in front of torso)} ---------- */
  const HAIR = {
    none: () => ({}),
    baby_tuft: (c) => ({ front: `<path d="M-52 -150C-30 -186 10 -190 44 -160C20 -168 -10 -166 -52 -150Z" fill="${c}" ${S(5)}/><path d="M-6 -176C-4 -204 24 -214 34 -196C22 -198 18 -186 6 -178Z" fill="${c}" ${S(5)}/>` }),
    child_pony(c) {  // 1980s child: straight bangs + high side ponytail with a scrunchie
      const hi = shade(c, 0.28);
      return {
        back: `<path d="M-90 -92C-98 -170 -50 -192 0 -192C50 -192 98 -170 90 -92C90 -60 84 -40 78 -30L-78 -30C-84 -40 -90 -60 -90 -92Z" fill="${c}" ${S(6)}/>
               <g transform="translate(72 -170) rotate(-24)"><path d="M0 0C46 -10 78 20 66 90C58 120 36 130 24 110C44 70 28 30 -4 22Z" fill="${c}" ${S(6)}/><path d="M30 24C48 40 52 70 44 96" stroke="${hi}" stroke-width="5" fill="none" opacity=".6" stroke-linecap="round"/></g>`,
        front: `<path d="M-90 -92C-100 -166 -46 -190 6 -188C60 -186 100 -160 90 -92C78 -128 50 -130 8 -126C-30 -124 -60 -122 -90 -92Z" fill="${c}" ${S(6)}/>
                <path d="M-70 -128C-40 -118 -10 -116 20 -124M20 -124C48 -118 66 -118 82 -108" fill="none" stroke="${OL}" stroke-width="3" opacity=".35"/>
                <path d="M-48 -164C-20 -178 20 -178 50 -168" stroke="${hi}" stroke-width="7" fill="none" stroke-linecap="round" opacity=".7"/>
                <g transform="translate(76 -168) rotate(-24)"><rect x="-18" y="-12" width="36" height="24" rx="12" fill="#2fb3a8" ${S(5)}/><path d="M-10 -4h20M-10 4h20" stroke="#fff" stroke-width="3" opacity=".6"/></g>` };
    },
    teen_long(c) {
      const hi = shade(c, 0.28);
      return {
        back: `<path d="M-92 -92C-102 -172 -52 -194 0 -194C52 -194 102 -172 92 -92C98 -46 96 -10 86 10L-86 10C-96 -10 -98 -46 -92 -92Z" fill="${c}" ${S(6)}/>`,
        front: `<path d="M-90 -92C-98 -166 -40 -190 12 -186C64 -182 100 -156 90 -92C84 -112 76 -124 62 -134C36 -124 6 -118 -26 -112C-50 -106 -72 -100 -90 -92Z" fill="${c}" ${S(6)}/>
                <path d="M-66 -156C-30 -174 14 -176 50 -162" stroke="${hi}" stroke-width="7" fill="none" stroke-linecap="round" opacity=".7"/>`,
        fall: (b) => `<path d="M${-b.sw - 6} ${-b.torsoH + 10} C${-b.sw - 18} ${-b.torsoH * 0.6} ${-b.sw - 10} ${-b.torsoH * 0.3} ${-b.sw + 6} ${-b.torsoH * 0.2} L${-b.sw + 26} ${-b.torsoH + 10} Z M${b.sw + 6} ${-b.torsoH + 10} C${b.sw + 18} ${-b.torsoH * 0.6} ${b.sw + 10} ${-b.torsoH * 0.3} ${b.sw - 6} ${-b.torsoH * 0.2} L${b.sw - 26} ${-b.torsoH + 10} Z" fill="${c}" ${S(5)}/>` };
    },
    long_straight(c) {  // adult: sleek, very long, centre-ish part
      const hi = shade(c, 0.35);
      return {
        back: `<path d="M-84 -96C-90 -176 -46 -196 0 -196C46 -196 90 -176 84 -96C86 -60 82 -30 76 -8L-76 -8C-82 -30 -86 -60 -84 -96Z" fill="${c}" ${S(6)}/>`,
        front: `<path d="M-84 -94C-92 -170 -34 -192 -2 -190C30 -192 94 -168 84 -94C80 -118 66 -140 40 -152C28 -128 10 -112 -2 -108C-14 -118 -40 -138 -48 -154C-70 -140 -80 -118 -84 -94Z" fill="${c}" ${S(6)}/>
                <path d="M-2 -190C-4 -160 -2 -130 -2 -108" stroke="${shade(c, 0.45)}" stroke-width="3" opacity=".7" fill="none"/>
                <path d="M-64 -150C-40 -172 0 -178 30 -170" stroke="${hi}" stroke-width="7" fill="none" stroke-linecap="round" opacity=".75"/>`,
        long: (b, yHead) => { const k = b.headS, top = yHead - 120 * k, wd = b.sw + 14, bot = -b.legH - b.torsoH * 0.3;
          return `<path d="M${-86 * k} ${top + 20 * k} C${-wd - 8} ${top + 60} ${-wd - 6} ${bot - 60} ${-wd + 4} ${bot} L${wd - 4} ${bot} C${wd + 6} ${bot - 60} ${wd + 8} ${top + 60} ${86 * k} ${top + 20 * k} Z" fill="${c}" ${S(6)}/>
                  <path d="M${-wd + 10} ${top + 80} C${-wd + 4} ${bot - 90} ${-wd + 8} ${bot - 40} ${-wd + 12} ${bot - 10}" stroke="${hi}" stroke-width="6" fill="none" opacity=".4" stroke-linecap="round"/>`; },
        fall: (b) => `<path d="M${-b.sw - 4} ${-b.torsoH + 8} C${-b.sw - 22} ${-b.torsoH * 0.55} ${-b.sw - 16} ${-b.torsoH * 0.12} ${-b.sw + 2} ${-b.torsoH * 0.04} L${-b.sw + 22} ${-b.torsoH * 0.2} C${-b.sw + 20} ${-b.torsoH * 0.55} ${-b.sw + 24} ${-b.torsoH + 10} ${-b.sw + 24} ${-b.torsoH + 10} Z M${b.sw + 4} ${-b.torsoH + 8} C${b.sw + 22} ${-b.torsoH * 0.55} ${b.sw + 16} ${-b.torsoH * 0.12} ${b.sw - 2} ${-b.torsoH * 0.04} L${b.sw - 22} ${-b.torsoH * 0.2} C${b.sw - 20} ${-b.torsoH * 0.55} ${b.sw - 24} ${-b.torsoH + 10} ${b.sw - 24} ${-b.torsoH + 10} Z" fill="${c}" ${S(5)}/>` };
    },
    big80s(c) {
      const hi = shade(c, 0.22), blobs = [[-70, -150, 52], [-20, -184, 58], [38, -182, 58], [84, -146, 50], [-98, -100, 40], [100, -98, 42], [-90, -48, 34], [92, -44, 34], [0, -150, 70]];
      return { back: circlesUnion(blobs, c, 12), front: `<path d="M-76 -128C-50 -150 -10 -146 10 -128C30 -148 64 -150 80 -126" fill="none" stroke="${hi}" stroke-width="7" stroke-linecap="round" opacity=".7"/><path d="M-86 -96C-80 -126 -50 -138 -20 -134C-30 -118 -60 -108 -86 -96Z M88 -96C82 -126 52 -138 22 -134C32 -118 62 -108 88 -96Z" fill="${c}" ${S(5)}/>` };
    },
    short_man: (c) => ({ front: `<path d="M-88 -98C-96 -170 -40 -190 6 -188C60 -186 98 -160 88 -98C74 -124 44 -138 -4 -134C-40 -130 -66 -120 -88 -98Z" fill="${c}" ${S(6)}/><path d="M-56 -160C-24 -174 18 -174 48 -162" stroke="${shade(c, 0.22)}" stroke-width="6" fill="none" stroke-linecap="round" opacity=".6"/>` }),
    slick: (c) => ({ front: `<path d="M-88 -98C-92 -172 -30 -194 20 -190C66 -186 96 -158 88 -98C70 -140 20 -150 -20 -146C-52 -142 -74 -126 -88 -98Z" fill="${c}" ${S(6)}/><path d="M-40 -170C-10 -182 30 -180 56 -168" stroke="${shade(c, 0.3)}" stroke-width="6" fill="none" stroke-linecap="round" opacity=".6"/>` }),
  };
  HAIR.wavy_long = HAIR.teen_long; HAIR.bob = HAIR.teen_long;

  /* ---------- torso silhouette (shoulders / waist / hips) ---------- */
  function bodyPath(b) {
    const th = b.torsoH, sw = b.sw, ww = b.ww, hw = b.hw;
    return `M${-hw} 0 C${-hw} ${-th * .2} ${-ww} ${-th * .32} ${-ww} ${-th * .5} C${-ww} ${-th * .68} ${-sw} ${-th * .78} ${-sw} ${-th + 16} Q${-sw} ${-th - 2} ${-sw * .55} ${-th - 4} Q0 ${-th + 8} ${sw * .55} ${-th - 4} Q${sw} ${-th - 2} ${sw} ${-th + 16} C${sw} ${-th * .78} ${ww} ${-th * .68} ${ww} ${-th * .5} C${ww} ${-th * .32} ${hw} ${-th * .2} ${hw} 0 Z`;
  }
  function outfit(kind, b, c) {
    const th = b.torsoH, sw = b.sw, ww = b.ww, hw = b.hw, top = c.top, acc = c.accent || "#e4483f";
    let pre = "", post = "";
    const body = (fill) => `<path d="${bodyPath(b)}" fill="${fill || top}" ${S(6)}/>`;
    const shadeR = `<path d="M${hw * .5} 0 Q${hw * .7} ${-th * .5} ${sw * .6} ${-th + 6} Q${sw} ${-th * .5} ${hw} 0 Z" fill="#000" opacity=".12"/>`;
    switch (kind) {
      case "kidtee": post = `<path d="M${-sw * .95} ${-th * .5} l${sw * .24} -16 l${sw * .24} 16 l${sw * .24} -16 l${sw * .24} 16 l${sw * .24} -16 l${sw * .24} 16 l${sw * .24} -16 l${sw * .2} 14" fill="none" stroke="${acc}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>`; break;
      case "sweat80s": post = `<path d="M${-sw} ${-th * .6} L${sw} ${-th * .6} L${sw} ${-th * .42} L${-sw} ${-th * .42} Z" fill="#7fd1c8" opacity=".95"/><path d="M${-sw} ${-th * .36} l12 -10 l12 10 l12 -10 l12 10 l12 -10 l12 10 l12 -10 l12 10" fill="none" stroke="#f6d44a" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/><path d="M${-sw * .45} ${-th + 2} Q0 ${-th + 20} ${sw * .45} ${-th + 2}" fill="${shade(top, .2)}" ${S(5)}/>`; break;
      case "babygrow": post = `<circle cx="0" cy="${-th * .5}" r="${b.sw * .2}" fill="${shade(top, .3)}" ${S(3)}/>${[-1, 1].map((s) => `<path d="M${s * sw * .5} ${-th * .8} l5 10 l11 1 l-8 8 l3 11 l-11 -6 l-10 6 l3 -11 l-8 -8 l11 -1Z" fill="#fff" opacity=".8" transform="scale(.6)"/>`).join("")}`; break;
      case "tee2007": post = `<path d="M${-sw * .3} ${-th - 2} L0 ${-th * .72} L${sw * .3} ${-th - 2}" fill="${shade(top, -.2)}" ${S(4)}/><path d="M${-hw * .8} ${-th * .12} Q0 ${-th * .02} ${hw * .8} ${-th * .12}" fill="none" stroke="${shade(top, .3)}" stroke-width="4" opacity=".5"/>`; break;
      case "crop": post = `<path d="M${-sw} ${-th * .46} Q0 ${-th * .38} ${sw} ${-th * .46}" fill="none" stroke="${OL}" stroke-width="5"/>`; pre = `<path d="${bodyPath(b)}" fill="${c.skin}" ${S(6)}/>`;
        return pre + `<clipPath id="${uid("cr")}"/>` + `<path d="M${-sw} ${-th + 14} Q${-sw} ${-th - 2} ${-sw * .55} ${-th - 4} Q0 ${-th + 8} ${sw * .55} ${-th - 4} Q${sw} ${-th - 2} ${sw} ${-th + 14} L${sw * .86} ${-th * .52} Q0 ${-th * .44} ${-sw * .86} ${-th * .52} Z" fill="${top}" ${S(6)}/>` + `<rect x="${-hw}" y="${-th * .22}" width="${hw * 2}" height="${th * .22}" rx="6" fill="${c.pants}" ${S(5)}/><rect x="${-hw}" y="${-th * .24}" width="${hw * 2}" height="9" fill="#8a5a3a" ${S(3)}/>`;
      case "dress": {  // sleeveless fitted dress, knee length (nude tones)
        const hem = b.legH * 0.5;
        pre = `<path d="M${-hw} 0 L${-hw * .96} ${hem} Q0 ${hem + 10} ${hw * .96} ${hem} L${hw} 0 Z" fill="${top}" ${S(6)}/>`;
        post = `<path d="M${-hw * .96} ${hem - 4} Q0 ${hem + 6} ${hw * .96} ${hem - 4}" fill="none" stroke="${shade(top, -.25)}" stroke-width="4" opacity=".6"/><path d="M${-ww * .5} ${-th * .2} Q0 ${-th * .12} ${ww * .5} ${-th * .2}" fill="none" stroke="${shade(top, .3)}" stroke-width="4" opacity=".4"/><path d="M${-sw * .55} ${-th - 3} Q0 ${-th + 26} ${sw * .55} ${-th - 3}" fill="${c.skin}" ${S(4)}/>`;
        return pre + body() + post + shadeR; }
      case "suit": post = `<path d="M${-sw * .27} ${-th + 2} L0 ${-th * .55} L${sw * .27} ${-th + 2} Z" fill="#f3f0ea" ${S(4)}/><path d="M-7 ${-th + 12} L0 ${-th * .62} L7 ${-th + 12} Z" fill="${acc}" ${S(3)}/><path d="M0 ${-th * .62} L-9 ${-th * .28} L0 ${-th * .18} L9 ${-th * .28} Z" fill="${acc}" ${S(3)}/>`; break;
      case "blazer": post = `<path d="M${-sw * .32} ${-th + 2} L${-sw * .03} ${-th * .5} L${sw * .03} ${-th * .5} L${sw * .32} ${-th + 2} L${sw * .16} ${-th + 4} L0 ${-th * .72} L${-sw * .16} ${-th + 4} Z" fill="${c.under || "#f6e9d6"}" ${S(4)}/><path d="M0 ${-th * .5} L0 0" stroke="${shade(top, -.3)}" stroke-width="4"/><circle cx="${sw * .1}" cy="${-th * .34}" r="4.5" fill="${acc}" ${S(2)}/>`; break;
      case "track": post = `<path d="M${-sw * .95} ${-th + 10} L${-hw * .9} 0 M${sw * .95} ${-th + 10} L${hw * .9} 0" stroke="${acc}" stroke-width="9" stroke-linecap="round"/><path d="M0 ${-th + 4} L0 0" stroke="${shade(top, -.3)}" stroke-width="4"/><path d="M${-sw * .3} ${-th + 2} Q0 ${-th + 16} ${sw * .3} ${-th + 2}" fill="${acc}" ${S(4)}/>`; break;
      case "onesie": post = `<circle cx="0" cy="${-th * .5}" r="${sw * .18}" fill="${shade(top, .3)}" ${S(3)}/>`; break;
    }
    return pre + body() + post + shadeR;
  }

  /* ---------- mouths ---------- */
  function mouths(lip, tier) {
    const L = lip ? lip : null;
    const lipTop = L ? `<path d="M-17 -1 Q-8 -9 0 -4 Q8 -9 17 -1 Q8 3 0 2 Q-8 3 -17 -1Z" fill="${L}" ${S(4)}/>` : "";
    const lipBot = L ? `<path d="M-15 1 Q0 14 15 1 Q8 4 0 4 Q-8 4 -15 1Z" fill="${shade(L, .12)}" ${S(3)}/>` : "";
    const ring = (rx, ry, cy) => L ? `<ellipse cx="0" cy="${cy}" rx="${rx + 6}" ry="${ry + 5}" fill="${L}" ${S(4)}/>` : "";
    return {
      neutral: () => L ? lipTop + lipBot : `<path d="M-12 0 Q0 5 12 0" fill="none" ${S(5)}/>`,
      smile: () => L ? `<path d="M-24 -4 Q0 28 24 -4 Q0 6 -24 -4Z" fill="${L}" ${S(5)}/><path d="M-17 -1 Q0 9 17 -1 L14 3 Q0 11 -14 3Z" fill="#fff"/>` : `<path d="M-22 -4 Q0 26 22 -4 Q0 4 -22 -4Z" fill="#7a2630" ${S(5)}/><path d="M-15 -1 Q0 7 15 -1 L13 3 Q0 10 -13 3Z" fill="#fff"/>`,
      grin: () => `${L ? `<path d="M-28 -8 Q0 40 28 -8Z" fill="${L}" ${S(5)}/>` : ""}<path d="M-24 -6 Q0 34 24 -6Z" fill="#7a2630" ${S(5)}/><path d="M-20 -4 Q0 4 20 -4 L18 4 Q0 10 -18 4Z" fill="#fff"/><path d="M-12 14 Q0 22 12 14 Q0 8 -12 14Z" fill="#d9565e"/>`,
      open: () => `${ring(14, 17, 6)}<ellipse cx="0" cy="6" rx="14" ry="17" fill="#7a2630" ${S(5)}/><ellipse cx="0" cy="14" rx="9" ry="6" fill="#d9565e"/>`,
      small: () => `${ring(9, 7, 4)}<ellipse cx="0" cy="4" rx="9" ry="7" fill="#7a2630" ${S(4)}/>`,
      o: () => `${ring(9, 12, 4)}<ellipse cx="0" cy="4" rx="9" ry="12" fill="#7a2630" ${S(5)}/>`,
      shock: () => `${ring(15, 22, 10)}<ellipse cx="0" cy="10" rx="15" ry="22" fill="#7a2630" ${S(5)}/><ellipse cx="0" cy="22" rx="10" ry="6" fill="#d9565e"/>`,
      sad: () => `<path d="M-17 9 Q0 -9 17 9" fill="none" ${S(5)}/>`,
      frown: () => `<path d="M-18 10 Q0 -4 18 10" fill="none" ${S(6)}/>`,
      smirk: () => `<path d="M-14 3 Q6 10 20 -6" fill="none" ${S(5)}/><path d="M20 -6 l4 -3" ${S(4)}/>`,
      worried: () => `<path d="M-16 4 Q-8 -3 0 4 Q8 11 16 4" fill="none" ${S(5)}/>`,
      proud: () => `<path d="M-22 -4 Q0 22 22 -4" fill="${L || "#7a2630"}" ${S(5)}/>`,
    };
  }
  // expression table: brow height/rotation (worried-positive), eye scale, mouth, blush, extras
  const EXPR = {
    neutral:   { by: 0,   br: 0,   ey: 1,    mouth: "neutral", blush: 0.25 },
    happy:     { by: -5,  br: -6,  ey: 0.92, mouth: "smile",   blush: 0.55 },
    laugh:     { by: -8,  br: -8,  ey: 0.5,  mouth: "grin",    blush: 0.65 },
    surprised: { by: -18, br: -4,  ey: 1.2,  mouth: "o",       blush: 0.2 },
    shock:     { by: -26, br: 6,   ey: 1.35, mouth: "shock",   blush: 0.1 },
    worried:   { by: -4,  br: 18,  ey: 1.06, mouth: "worried", blush: 0.15 },
    nervous:   { by: -6,  br: 22,  ey: 1.1,  mouth: "worried", blush: 0.2, sweat: 1 },
    sad:       { by: 2,   br: 24,  ey: 0.84, mouth: "sad",     blush: 0.1 },
    cry:       { by: 2,   br: 28,  ey: 0.7,  mouth: "frown",   blush: 0.55, tears: 1 },
    smirk:     { by: -3,  br: -12, ey: 0.9,  mouth: "smirk",   blush: 0.3 },
    proud:     { by: -8,  br: -10, ey: 0.45, mouth: "proud",   blush: 0.5 },
    determined:{ by: 6,   br: -16, ey: 0.88, mouth: "neutral", blush: 0.2 },
    angry:     { by: 8,   br: -26, ey: 0.92, mouth: "frown",   blush: 0.3 },
    shout:     { by: -6,  br: 6,   ey: 1.0,  mouth: "open",    blush: 0.3 },
  };

  function head(spec, b, F) {
    const sk = spec.skin, shd = shade(sk, -0.16), hc = spec.hairColor;
    const fw = b.fw, ch = b.ch, ex = F.ex, ey = F.ey, ir = F.ir, eyeX = F.x, eyeY = -88;
    const hair = (HAIR[spec.hair || "none"] || HAIR.none)(hc);
    const cid = uid("clip"), eyeCol = spec.eyeColor || "#5a3320";
    const face = `M${-fw} -92 C${-fw} -152 ${-fw * .56} -176 0 -176 C${fw * .56} -176 ${fw} -152 ${fw} -92 C${fw} -34 ${fw * (F.lash >= 2 ? .4 : .56)} ${ch} 0 ${ch} C${-fw * (F.lash >= 2 ? .4 : .56)} ${ch} ${-fw} -34 ${-fw} -92 Z`;
    const eye = (side) => {
      const sx = side === "L" ? -1 : 1;
      const lash = F.lash ? `<path d="M${-ex - 3} ${-ey + 5} Q0 ${-ey - 9 - F.lash * 2} ${ex + 3} ${-ey + 5}" fill="none" stroke="${OL}" stroke-width="${6 + F.lash * 2}" stroke-linecap="round"/>
        <path d="M${sx * (ex + 1)} ${-ey + 4} l${sx * (8 + F.lash * 3)} ${-5 - F.lash * 2}" fill="none" stroke="${OL}" stroke-width="${4 + F.lash}" stroke-linecap="round"/>
        ${F.lash >= 2 ? `<path d="M${-ex} ${-ey + 2} Q0 ${-ey - 20} ${ex} ${-ey + 2}" fill="#7a4a4a" opacity=".28"/>` : ""}` :
        `<path d="M${-ex - 2} ${-ey + 3} Q0 ${-ey - 7} ${ex + 2} ${-ey + 3}" fill="none" ${S(5)}/><path d="M${sx * (ex + 1)} ${-ey + 4} l${sx * 8} -6" fill="none" ${S(4)}/>`;
      return `<g transform="translate(${sx * eyeX} ${eyeY})">
        <clipPath id="${cid}${side}"><ellipse cx="0" cy="0" rx="${ex}" ry="${ey}"/></clipPath>
        ${P("eye" + side, 0, 0, `<ellipse cx="0" cy="0" rx="${ex}" ry="${ey}" fill="#fff" ${S(4)}/>
          <g clip-path="url(#${cid}${side})">${P("iris" + side, 0, 2, `<circle r="${ir}" fill="${eyeCol}"/><circle r="${ir * .58}" fill="#1b1014"/><circle cx="${-ir * .34}" cy="${-ir * .4}" r="${ir * .3}" fill="#fff"/><circle cx="${ir * .3}" cy="${ir * .32}" r="${ir * .14}" fill="#fff" opacity=".8"/>`)}
          ${P("lid" + side, 0, -3 * ey - 8, `<rect x="${-ex - 4}" y="0" width="${ex * 2 + 8}" height="${ey * 2 + 6}" fill="${sk}"/><path d="M${-ex - 4} ${ey * 2 + 5} Q0 ${ey * 2 + 10} ${ex + 4} ${ey * 2 + 5}" fill="none" ${S(5)}/>`)}</g>
          ${lash}`)}</g>`;
    };
    const brow = (side) => {
      const sx = side === "L" ? -1 : 1;
      return P("brow" + side, sx * eyeX, eyeY - ey - 14, `<path d="M${-ex - 3} ${4 + F.arch * .2} Q${-ex * .1} ${-F.arch - 4} ${ex + 5} ${3 + F.arch * .3}" fill="none" stroke="${hc}" stroke-width="${F.brow + (spec.detail ? 3 : 0)}" stroke-linecap="round"/>`);
    };
    const M = mouths(F.lip === 2 ? (spec.lip || "#c4666b") : F.lip === 1 ? (spec.lip || "#d98a86") : null);
    const mouthEls = Object.keys(M).map((k) => `<g data-m="${k}" style="display:${k === "neutral" ? "inline" : "none"}">${M[k]()}</g>`).join("");
    const nose = F.nose === "dot" ? `<circle cx="0" cy="-62" r="4" fill="${shd}"/>` : F.nose === "slim" ? `<path d="M-3 -78 Q-6 -60 -9 -56 Q0 -50 9 -56" fill="none" stroke="${shd}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>` : `<path d="M-5 -66 Q0 -58 6 -64" fill="none" stroke="${shd}" stroke-width="4" stroke-linecap="round"/>`;
    const contour = F.lash >= 2 ? `<path d="M${-fw + 6} -70 Q${-fw * .55} -48 ${-fw * .3} -22" stroke="${shade(sk, -.3)}" stroke-width="10" opacity=".28" fill="none" stroke-linecap="round"/><path d="M${fw - 6} -70 Q${fw * .55} -48 ${fw * .3} -22" stroke="${shade(sk, -.3)}" stroke-width="10" opacity=".28" fill="none" stroke-linecap="round"/><path d="M-30 -118 Q0 -128 30 -118" stroke="${shade(sk, .4)}" stroke-width="8" opacity=".25" fill="none" stroke-linecap="round"/>` : "";
    const earr = spec.earrings ? [-1, 1].map((s) => `<circle cx="${s * (fw + 10)}" cy="-64" r="11" fill="none" stroke="#e8c15a" stroke-width="5"/>`).join("") : "";
    /* optional close-up detail (spec.detail): lid crease, under-eye shade, nose-bridge shadow, cheekbone light, lip gloss, forehead sheen */
    const dk = shade(sk, -0.34), hl = shade(sk, 0.3), W = F.lash >= 2;
    const det = spec.detail ? [-1, 1].map((sx) => `<path d="M${sx * (eyeX - ex - 2)} ${eyeY - ey - 5} Q${sx * eyeX} ${eyeY - ey - 17 - (W ? 4 : 0)} ${sx * (eyeX + ex + 4)} ${eyeY - ey - 4}" fill="none" stroke="${dk}" stroke-width="3.5" stroke-linecap="round" opacity=".7"/>
      <path d="M${sx * (eyeX - ex)} ${eyeY + ey + 5} Q${sx * eyeX} ${eyeY + ey + 14} ${sx * (eyeX + ex)} ${eyeY + ey + 5}" fill="none" stroke="${dk}" stroke-width="5" stroke-linecap="round" opacity=".28"/>
      <path d="M${sx * (eyeX - 6)} ${eyeY + 12} Q${sx * (eyeX - 4)} -62 ${sx * 5} -58" fill="none" stroke="${dk}" stroke-width="5" stroke-linecap="round" opacity=".22"/>
      <ellipse cx="${sx * fw * .6}" cy="-70" rx="${W ? 17 : 21}" ry="7" fill="${hl}" opacity=".32" transform="rotate(${sx * -14} ${sx * fw * .6} -70)"/>
      ${W ? `<path d="M${sx * (eyeX + ex + 2)} ${eyeY - 2} l${sx * 11} -8" stroke="${OL}" stroke-width="5" stroke-linecap="round"/>` : ""}`).join("") +
      `<ellipse cx="-14" cy="-138" rx="34" ry="9" fill="${hl}" opacity=".22"/><path d="M-5 -60 Q0 -54 7 -60" fill="none" stroke="${dk}" stroke-width="4" opacity=".5" stroke-linecap="round"/>` +
      (F.lip ? `<ellipse cx="-5" cy="${(W ? -30 : -34) + 4}" rx="9" ry="2.6" fill="#fff" opacity=".5"/>` : "") : "";
    const extras = `<g data-x="tears" style="display:none"><path d="M${-eyeX - 2} -66 q-6 18 0 30 q6 -12 0 -30Z M${eyeX + 2} -66 q6 18 0 30 q-6 -12 0 -30Z" fill="#8fd3f4" ${S(3)}/></g>
      <g data-x="sweat" style="display:none"><path d="M${fw - 14} -140 q-12 22 0 34 q12 -12 0 -34Z" fill="#8fd3f4" ${S(3)}/></g>`;
    return `${hair.back || ""}
      <ellipse cx="${-fw + 2}" cy="-88" rx="14" ry="19" fill="${sk}" ${S(5)}/><ellipse cx="${fw - 2}" cy="-88" rx="14" ry="19" fill="${sk}" ${S(5)}/>${earr}
      <path d="${face}" fill="${sk}" ${S(6)}/>
      <path d="M${fw * .64} -158 C${fw} -130 ${fw * 1.06} -64 ${fw * .5} -12 C${fw * .9} -60 ${fw * .84} -128 ${fw * .64} -158Z" fill="${shd}" opacity=".45"/>
      ${contour}
      ${P("blush", 0, 0, `<ellipse cx="${-fw * .64}" cy="-56" rx="${F.lash >= 2 ? 15 : 19}" ry="${F.lash >= 2 ? 8 : 11}" fill="#ff6f7a"/><ellipse cx="${fw * .64}" cy="-56" rx="${F.lash >= 2 ? 15 : 19}" ry="${F.lash >= 2 ? 8 : 11}" fill="#ff6f7a"/>`).replace('<g data-p="blush">', '<g data-p="blush" opacity=".25">')}
      ${eye("L")}${eye("R")}${brow("L")}${brow("R")}${nose}
      ${det}
      <g transform="translate(0 ${F.lash >= 2 ? -30 : -34})">${mouthEls}</g>${extras}
      ${hair.front || ""}${spec.glasses ? `<g fill="rgba(255,255,255,.12)" ${S(5)}><circle cx="${-eyeX}" cy="${eyeY}" r="${ex + 12}"/><circle cx="${eyeX}" cy="${eyeY}" r="${ex + 12}"/><path d="M${-eyeX + ex + 12} ${eyeY} L${eyeX - ex - 12} ${eyeY}" fill="none"/></g>` : ""}`;
  }

  function limb(side, b, c, shY) {
    const sx = side === "L" ? -1 : 1, aw = b.armW, long = c.sleeve !== "none" && c.sleeve !== "short";
    const sleeveUp = c.sleeve === "none" ? c.skin : c.top, foreFill = long ? c.top : c.skin;
    const tp = (w1, w2, len, fill) => `<path d="M${-w1 / 2} -8 L${-w2 / 2} ${len} Q0 ${len + 5} ${w2 / 2} ${len} L${w1 / 2} -8 Z" fill="${fill}" ${S(5)}/>`;
    const hand = `<circle cx="0" cy="${b.armF + 8}" r="${b.hand}" fill="${c.skin}" ${S(5)}/>`;
    return P("arm" + side, sx * b.shX, -b.legH - b.torsoH + 26, tp(aw, aw * .88, b.armU + 4, sleeveUp) + P("fore" + side, 0, b.armU, tp(aw * .88, aw * .7, b.armF + 6, foreFill) + hand));
  }
  function shoeShape(b, c) {
    const lw = b.legW, L = b.shoe, t = c.shoeType || "sneaker";
    if (t === "pump") return `<path d="M${-lw * .3} -18 L${lw * .3} -14 Q${L * .6} -10 ${L * 1.1} -1 L${-lw * .4} -1 Z" fill="${c.shoe}" ${S(4)}/>`;
    if (t === "sneaker") return `<path d="M${-lw * .38} -16 L${lw * .36} -16 L${lw * .36} -8 Q${L} -10 ${L} -1 L${-lw * .42} -1 Z" fill="${c.shoe}" ${S(5)}/><rect x="${-lw * .42}" y="-6" width="${L + lw * .42}" height="6" fill="#f2efe8" ${S(3)}/>`;
    return `<path d="M${-lw * .38} -16 L${lw * .36} -16 L${lw * .36} -8 Q${L} -10 ${L} -1 L${-lw * .42} -1 Z" fill="${c.shoe}" ${S(5)}/>`;
  }
  function leg(side, b, c) {
    const sx = side === "L" ? -1 : 1, lw = b.legW, L1 = Math.round(b.legH * 0.5), L2 = b.legH - L1;
    const bare = c.legs === "bare", fill = bare ? shade(c.skin, -0.02) : c.pants;
    const thigh = `<path d="M${-lw / 2} -10 L${-lw * .43} ${L1} L${lw * .43} ${L1} L${lw / 2} -10 Z" fill="${fill}" ${S(5)}/>`;
    const shinPath = `<path d="M${-lw * .43} -4 L${-lw * .29} ${L2 - 2} L${lw * .29} ${L2 - 2} L${lw * .43} -4 Z" fill="${fill}" ${S(5)}/>`;
    return P("leg" + side, sx * b.hw * 0.45, -b.legH, thigh + P("shin" + side, 0, L1, shinPath + P("shoe" + side, 0, L2, shoeShape(b, c))));
  }

  /** actor(spec) -> SVG markup. spec: build, skin, hair, hairColor, top, pants, shoe, outfit, legs, sleeve, earrings, glasses, lip, skirt */
  function actor(spec) {
    const bn = ALIAS[spec.build] || spec.build || "child";
    spec = Object.assign({ build: bn, skin: "#d99a73", hair: "none", hairColor: "#1c1210", top: "#f0b63a", pants: "#3b4a8c", shoe: "#2b2230", outfit: "kidtee", accent: "#e4483f" }, spec, { build: bn });
    const b = BUILDS[bn], F = FACE[bn];
    const yHead = -b.legH - b.torsoH - b.neck + 8;
    const hairDef = (HAIR[spec.hair || "none"] || HAIR.none)(spec.hairColor);
    const longBack = hairDef.long ? P("hairBack", 0, yHead, `<g transform="translate(0 ${-yHead})">${hairDef.long(b, yHead)}</g>`) : "";
    const hairFall = false && hairDef.fall ? P("hairFall", 0, -b.legH, hairDef.fall(b)) : "";
    return `<g data-actor>
      ${P("shadow", 0, 0, `<ellipse cx="0" cy="4" rx="${b.hw * 1.3}" ry="14" fill="#000" opacity=".3"/>`)}
      ${P("root", 0, 0, `${longBack}
        ${leg("L", b, spec)}${leg("R", b, spec)}
        ${P("torso", 0, -b.legH, outfit(spec.outfit, b, spec))}
        <rect x="${-b.sw * .2}" y="${yHead + b.neck - 6}" width="${b.sw * .4}" height="${b.neck + 8}" fill="${shade(spec.skin, -.1)}" ${S(5)}/>
        ${limb("L", b, spec)}${limb("R", b, spec)}
        <g transform="translate(0 ${yHead}) scale(${b.headS})">${P("head", 0, 0, head(spec, b, F))}</g>
        ${hairFall}`)}
    </g>`;
  }

  BUILDS.kid = BUILDS.child; BUILDS.adult = BUILDS.man; FACE.kid = FACE.child; FACE.adult = FACE.man;
  K.chars = { actor, BUILDS, EXPR, FACE, HAIR };
})(window.K);
