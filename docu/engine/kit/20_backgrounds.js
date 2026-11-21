/* Detailed layered backgrounds. Each returns {layers:[{name,depth,svg}]}; depth = parallax factor. 1920x1080. */
(function (K) {
  "use strict";
  const { OL, S, shade, rng } = K;
  const stroke = (w) => `stroke="${OL}" stroke-width="${w || 5}" stroke-linejoin="round"`;

  function livingRoom(pal) {
    pal = Object.assign({ wall: "#b98a5e", wall2: "#a8794f", floor: "#6a4630", rug: "#9c3b3b", warm: "#ffcf8a" }, pal);
    const r = rng(7);
    let paper = "";
    for (let x = 0; x < 1920; x += 96) paper += `<path d="M${x} 0V760" stroke="${pal.wall2}" stroke-width="20" opacity=".35"/>` +
      Array.from({ length: 8 }, (_, i) => `<circle cx="${x + 48}" cy="${60 + i * 92 + (i % 2) * 40}" r="7" fill="${shade(pal.wall, 0.18)}" opacity=".5"/>`).join("");
    const back = `<rect width="1920" height="780" fill="${pal.wall}"/>${paper}
      <rect y="640" width="1920" height="26" fill="${shade(pal.wall, -0.35)}"/>
      <rect y="666" width="1920" height="120" fill="${shade(pal.wall, -0.18)}"/>`;
    const furn = `
      <g transform="translate(120 250)"><rect width="300" height="520" fill="#5a3a26" ${stroke(6)}/>
        ${[0, 1, 2, 3].map((i) => `<rect x="14" y="${14 + i * 124}" width="272" height="112" fill="#3f281a" ${stroke(4)}/>` +
          Array.from({ length: 9 }, (_, k) => `<rect x="${24 + k * 28}" y="${(30 + i * 124) + (k % 3) * 6}" width="20" height="${90 - (k % 3) * 6}" fill="${["#c2453b", "#3d6a9c", "#e0b040", "#4c8a5a", "#8a4f9c"][(k + i) % 5]}" ${stroke(3)}/>`).join("")).join("")}</g>
      <g transform="translate(780 210)"><rect width="360" height="280" rx="14" fill="#2a2a30" ${stroke(8)}/><rect x="24" y="24" width="312" height="232" rx="8" fill="#1c3a4a"/>
        <path d="M24 200 L150 120 L220 180 L270 140 L336 200 V256 H24 Z" fill="#2a6a7a" opacity=".6"/>
        <rect x="30" y="30" width="300" height="60" fill="#fff" opacity=".07"/></g>
      <rect x="760" y="490" width="400" height="280" fill="#6a4630" ${stroke(6)}/>
      <g transform="translate(1320 230)"><rect width="440" height="360" fill="#e9d9b5" ${stroke(8)}/><rect x="20" y="20" width="400" height="320" fill="#f8c27a"/>
        <circle cx="300" cy="120" r="60" fill="#fff2bd"/><path d="M20 240 Q120 170 210 230 T420 210 V340 H20Z" fill="#c76a3f"/>
        <path d="M220 20V340M20 180H420" stroke="#e9d9b5" stroke-width="12"/></g>`;
    const rug = `<g transform="translate(300 920)"><ellipse cx="660" cy="0" rx="640" ry="92" fill="${pal.rug}" ${stroke(6)}/>
      <ellipse cx="660" cy="0" rx="520" ry="66" fill="none" stroke="#f3d58a" stroke-width="8" stroke-dasharray="26 16"/>
      <ellipse cx="660" cy="0" rx="380" ry="44" fill="none" stroke="#f3d58a" stroke-width="5"/></g>`;
    const floor = `<rect y="780" width="1920" height="300" fill="${pal.floor}"/>` +
      Array.from({ length: 12 }, (_, i) => `<path d="M0 ${790 + i * 28}H1920" stroke="${shade(pal.floor, -0.25)}" stroke-width="3" opacity=".6"/>`).join("");
    return { layers: [{ name: "wall", depth: 0.2, svg: back }, { name: "furn", depth: 0.4, svg: furn }, { name: "floor", depth: 0.7, svg: floor + rug }] };
  }

  function street(pal) {
    pal = Object.assign({ sky1: "#ff9a5a", sky2: "#ffd58a", bld: "#4b3a55", bld2: "#6b4f66", road: "#3a3340" }, pal);
    const r = rng(21);
    let far = `<rect width="1920" height="1080" fill="url(#skyg)"/>`;
    const sky = `<defs><linearGradient id="skyg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${pal.sky1}"/><stop offset="1" stop-color="${pal.sky2}"/></linearGradient></defs>
      <rect width="1920" height="1080" fill="url(#skyg)"/><circle cx="1450" cy="520" r="150" fill="#fff0c0" opacity=".85"/>`;
    const bl = (x, w, h, c) => `<g><rect x="${x}" y="${760 - h}" width="${w}" height="${h}" fill="${c}" ${stroke(5)}/>` +
      Array.from({ length: Math.floor(h / 90) }, (_, i) => Array.from({ length: Math.floor(w / 70) }, (_, k) =>
        `<rect x="${x + 18 + k * 70}" y="${760 - h + 24 + i * 90}" width="40" height="54" fill="${r() > 0.45 ? "#ffd27a" : shade(c, -0.25)}"/>`).join("")).join("") + `</g>`;
    let mid = "", near = "";
    for (let i = 0, x = -40; x < 1960; i++) { const w = 200 + Math.floor(r() * 120), h = 300 + Math.floor(r() * 380); mid += bl(x, w, h, shade(pal.bld2, (r() - 0.5) * 0.2)); x += w + 10; }
    for (let i = 0, x = -80; x < 1960; i++) { const w = 280 + Math.floor(r() * 140), h = 240 + Math.floor(r() * 220); near += bl(x, w, h, shade(pal.bld, (r() - 0.5) * 0.2)); x += w + 40; }
    const road = `<rect y="760" width="1920" height="320" fill="${pal.road}"/><rect y="760" width="1920" height="26" fill="#8d8596" ${stroke(4)}/>
      ${Array.from({ length: 9 }, (_, i) => `<rect x="${i * 240 + 40}" y="930" width="130" height="14" fill="#f3e6b0" opacity=".85"/>`).join("")}`;
    return { layers: [{ name: "sky", depth: 0.05, svg: sky }, { name: "mid", depth: 0.25, svg: `<g opacity=".8">${mid}</g>` }, { name: "near", depth: 0.5, svg: near }, { name: "road", depth: 0.8, svg: road }] };
  }

  function studio(pal) {
    pal = Object.assign({ a: "#2a2147", b: "#6a3d8f", light: "#ff6fae" }, pal);
    const lights = Array.from({ length: 7 }, (_, i) => `<path d="M${200 + i * 260} 0 L${120 + i * 260} 800 L${300 + i * 260} 800 Z" fill="${pal.light}" opacity="${0.06 + (i % 2) * 0.05}"/>`).join("");
    const curt = Array.from({ length: 16 }, (_, i) => `<rect x="${i * 120}" y="0" width="60" height="800" fill="${shade(pal.a, i % 2 ? 0.1 : -0.12)}" opacity=".55"/>`).join("");
    const back = `<defs><linearGradient id="stg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${pal.a}"/><stop offset="1" stop-color="${pal.b}"/></linearGradient>
      <radialGradient id="stg2"><stop offset="0" stop-color="${pal.light}" stop-opacity=".55"/><stop offset="1" stop-color="${pal.light}" stop-opacity="0"/></radialGradient></defs>
      <rect width="1920" height="1080" fill="url(#stg)"/>${curt}${lights}<ellipse cx="960" cy="520" rx="900" ry="420" fill="url(#stg2)"/>`;
    const floor = `<rect y="800" width="1920" height="280" fill="#150f22"/><rect y="800" width="1920" height="10" fill="${pal.light}" opacity=".6"/>
      <ellipse cx="960" cy="880" rx="820" ry="70" fill="${pal.light}" opacity=".12"/>`;
    return { layers: [{ name: "back", depth: 0.2, svg: back }, { name: "floor", depth: 0.7, svg: floor }] };
  }

  K.bg = { livingRoom, street, studio };
})(window.K);
