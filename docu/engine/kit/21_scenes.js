/* Scene-specific backgrounds (each scene gets its own environment, details match the event). 1920x1080. */
(function (K) {
  "use strict";
  const { OL, shade, rng, uid } = K, B = K.bg;
  const st = (w) => `stroke="${OL}" stroke-width="${w || 5}" stroke-linejoin="round" stroke-linecap="round"`;
  const grad = (id, a, b, v) => `<linearGradient id="${id}" x1="0" y1="0" x2="${v ? 0 : 1}" y2="${v ? 1 : 0}"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient>`;
  const floorBoards = (y, h, c, n) => `<rect y="${y}" width="1920" height="${h}" fill="${c}"/>` + Array.from({ length: n || 10 }, (_, i) => `<path d="M0 ${y + 14 + i * (h / (n || 10))}H1920" stroke="${shade(c, -0.25)}" stroke-width="3" opacity=".6"/>`).join("");
  const win = (x, y, w, h, sky, extra) => `<g transform="translate(${x} ${y})"><rect width="${w}" height="${h}" fill="${sky}" ${st(8)}/>${extra || ""}<path d="M${w / 2} 0V${h}M0 ${h / 2}H${w}" stroke="#f3ead2" stroke-width="10"/><rect width="${w}" height="${h}" fill="none" ${st(8)}/></g>`;
  const frame = (x, y, w, h, c) => `<g transform="translate(${x} ${y})"><rect width="${w}" height="${h}" fill="#f3ead2" ${st(5)}/><rect x="9" y="9" width="${w - 18}" height="${h - 18}" fill="${c || "#c99a6a"}"/><circle cx="${w * .5}" cy="${h * .42}" r="${Math.min(w, h) * .16}" fill="#e0a275"/><path d="M${w * .25} ${h - 9}Q${w * .5} ${h * .55} ${w * .75} ${h - 9}Z" fill="${shade(c || "#c99a6a", -0.3)}"/></g>`;
  const lamp = (x, y, c) => `<g transform="translate(${x} ${y})"><rect x="-6" y="0" width="12" height="150" fill="#3a2a20" ${st(4)}/><ellipse cx="0" cy="152" rx="40" ry="10" fill="#3a2a20" ${st(4)}/><path d="M-50 0L-30 -70H30L50 0Z" fill="${c || "#f6d58a"}" ${st(5)}/></g>`;
  const sofa = (x, y, c, w) => { w = w || 520; return `<g transform="translate(${x} ${y})"><rect x="${-w / 2}" y="-170" width="${w}" height="120" rx="30" fill="${shade(c, -0.1)}" ${st(6)}/><rect x="${-w / 2 - 36}" y="-110" width="64" height="110" rx="22" fill="${c}" ${st(6)}/><rect x="${w / 2 - 28}" y="-110" width="64" height="110" rx="22" fill="${c}" ${st(6)}/><rect x="${-w / 2 + 20}" y="-80" width="${w - 40}" height="80" rx="18" fill="${c}" ${st(6)}/><path d="M0 -80V0" stroke="${OL}" stroke-width="4"/><rect x="${-w / 2 + 14}" y="0" width="14" height="22" fill="#3a2a20"/><rect x="${w / 2 - 28}" y="0" width="14" height="22" fill="#3a2a20"/></g>`; };
  const L = (n, d, svg) => ({ name: n, depth: d, svg });

  /* 1 · Los Angeles 1980: sunset street + maternity hospital + hillside sign */
  function laStreet(pal) {
    const base = B.street(pal), r = rng(5);
    const hills = `<path d="M0 560C200 470 380 520 560 470S900 430 1120 500 1500 470 1920 540V780H0Z" fill="#7a4a52" opacity=".75" ${st(4)}/>
      <g transform="translate(980 470)" font-family="Inter,Arial,sans-serif" font-weight="800" font-size="34" fill="#fff" opacity=".9"><text letter-spacing="10" x="0" y="0">HOLLYWOOD</text></g>`;
    const hosp = `<g transform="translate(250 780)"><rect x="0" y="-420" width="520" height="420" fill="#efe3d0" ${st(6)}/><rect x="170" y="-520" width="180" height="110" fill="#efe3d0" ${st(6)}/>
      <rect x="215" y="-505" width="90" height="26" fill="#d9453f"/><rect x="247" y="-533" width="26" height="82" fill="#d9453f"/>
      ${Array.from({ length: 3 }, (_, i) => Array.from({ length: 5 }, (_, k) => `<rect x="${34 + k * 94}" y="${-380 + i * 110}" width="56" height="70" fill="${r() > .4 ? "#ffd27a" : "#9fb8cf"}" ${st(3)}/>`).join("")).join("")}
      <rect x="190" y="-90" width="140" height="90" fill="#6c8aa8" ${st(5)}/><rect x="60" y="-150" width="400" height="44" rx="8" fill="#fff" ${st(4)}/><text x="260" y="-118" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="26" fill="#d9453f">MATERNITY</text></g>`;
    const lamps = [1100, 1560, 1860].map((x) => `<g transform="translate(${x} 780)"><rect x="-5" y="-250" width="10" height="250" fill="#2a1820"/><circle cy="-262" r="22" fill="#ffe9a8" ${st(4)}/></g>`).join("");
    base.layers.splice(2, 0, L("hills", 0.15, hills), L("hospital", 0.35, hosp));
    base.layers.push(L("lamps", 0.85, lamps));
    return base;
  }

  /* 2 · nursery: pastel stripes, window with moon, shelf, toys, wall stars */
  function nursery(pal) {
    pal = Object.assign({ wall: "#f1d7b0", stripe: "#e9c38f", floor: "#a8714a", rug: "#7fb2c8" }, pal);
    const id = uid("nw"), stripes = Array.from({ length: 20 }, (_, i) => `<rect x="${i * 96}" width="48" height="790" fill="${pal.stripe}" opacity=".55"/>`).join("");
    const wall = `<defs>${grad(id, pal.wall, shade(pal.wall, -0.08), 1)}</defs><rect width="1920" height="790" fill="url(#${id})"/>${stripes}<rect y="650" width="1920" height="140" fill="${shade(pal.wall, -0.2)}"/><rect y="640" width="1920" height="14" fill="#fff" opacity=".6"/>`;
    const stars = Array.from({ length: 9 }, (_, i) => `<path transform="translate(${180 + i * 190} ${110 + (i % 3) * 80}) scale(${0.9 + (i % 2) * 0.5})" d="M0 -22L6 -7H22L9 3L14 19L0 10L-14 19L-9 3L-22 -7H-6Z" fill="${["#f6d54a", "#fff", "#f2a7b8"][i % 3]}" ${st(3)}/>`).join("");
    const det = stars + win(1380, 170, 340, 380, "#27395f", `<circle cx="240" cy="110" r="52" fill="#fff6c8"/><circle cx="262" cy="98" r="44" fill="#27395f"/>${[[70, 60], [120, 150], [260, 250], [60, 290]].map(([x, y]) => `<circle cx="${x}" cy="${y}" r="5" fill="#fff"/>`).join("")}`) +
      `<path d="M1340 160Q1380 300 1370 560M1760 160Q1720 300 1730 560" stroke="#e8809a" stroke-width="30" fill="none" opacity=".85"/>` +
      `<g transform="translate(140 300)"><rect width="440" height="16" fill="#8a5a38" ${st(5)}/>
        <g transform="translate(40 -90)"><rect width="76" height="76" fill="#e4483f" ${st(4)}/><text x="38" y="54" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="46" fill="#fff">A</text></g>
        <g transform="translate(130 -70)"><rect width="56" height="56" fill="#3d8bd0" ${st(4)}/><text x="28" y="42" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="34" fill="#fff">B</text></g>
        <g transform="translate(320 -110)"><ellipse cx="40" cy="70" rx="44" ry="42" fill="#b9825a" ${st(5)}/><circle cx="40" cy="22" r="32" fill="#b9825a" ${st(5)}/><circle cx="14" cy="-2" r="12" fill="#b9825a" ${st(4)}/><circle cx="66" cy="-2" r="12" fill="#b9825a" ${st(4)}/><circle cx="30" cy="20" r="3.5" fill="${OL}"/><circle cx="50" cy="20" r="3.5" fill="${OL}"/><ellipse cx="40" cy="32" rx="9" ry="6" fill="#e9c9a0"/></g></g>` +
      `<g transform="translate(1100 790)"><path d="M-70 0Q-80 -90 -20 -110L90 -110Q120 -60 70 0Z" fill="#c07a46" ${st(5)}/><circle cx="-30" cy="-120" r="30" fill="#c07a46" ${st(5)}/><path d="M-90 -10Q0 40 100 -10" fill="none" stroke="#6a3a22" stroke-width="12" stroke-linecap="round"/><rect x="-14" y="0" width="12" height="40" fill="#6a3a22"/><rect x="60" y="0" width="12" height="40" fill="#6a3a22"/></g>`;
    const fl = floorBoards(790, 290, pal.floor, 9) + `<g transform="translate(260 960)"><ellipse cx="700" cy="0" rx="640" ry="80" fill="${pal.rug}" ${st(6)}/><ellipse cx="700" cy="0" rx="500" ry="56" fill="none" stroke="#fff" stroke-width="6" stroke-dasharray="20 14" opacity=".7"/></g>`;
    return { layers: [L("wall", 0.2, wall), L("det", 0.4, det), L("floor", 0.7, fl)] };
  }

  /* 3 · father's law office: wood panels, law books, diploma, city window, flag */
  function lawOffice() {
    const panels = Array.from({ length: 10 }, (_, i) => `<rect x="${i * 200 + 8}" y="40" width="184" height="700" rx="6" fill="#5d3b28" ${st(5)}/>`).join("");
    const wall = `<rect width="1920" height="800" fill="#4a2e1f"/>${panels}<rect y="40" width="1920" height="14" fill="#2a1810"/>`;
    const shelf = `<g transform="translate(90 170)"><rect width="520" height="560" fill="#3a2316" ${st(7)}/>${[0, 1, 2, 3].map((i) => `<rect x="16" y="${16 + i * 136}" width="488" height="122" fill="#2a1810"/>` + Array.from({ length: 14 }, (_, k) => `<rect x="${24 + k * 34}" y="${(26 + i * 136) + (k % 4) * 5}" width="26" height="${100 - (k % 4) * 5}" fill="${["#7a1f27", "#1f3a5a", "#b88a2a", "#2f5a3a", "#5a2a5a"][(k + i) % 5]}" ${st(3)}/>`).join("")).join("")}</g>`;
    const window_ = win(760, 150, 460, 360, "#8fb8e8", `<g fill="#566a8a" opacity=".9" ${st(3)}><rect x="20" y="170" width="70" height="190"/><rect x="100" y="120" width="86" height="240"/><rect x="200" y="200" width="60" height="160"/><rect x="280" y="90" width="90" height="270"/><rect x="380" y="180" width="64" height="180"/></g>`);
    const dip = `<g transform="translate(1320 200)"><rect width="260" height="190" fill="#f3ead2" ${st(7)}/><rect x="16" y="16" width="228" height="158" fill="#fffaf0"/><path d="M40 60H220M40 90H200M40 120H210" stroke="#7a6a50" stroke-width="5"/><circle cx="214" cy="146" r="18" fill="#c43b3b" ${st(3)}/><text x="130" y="48" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="22" fill="#2a1820">LAW DEGREE</text></g>
      <g transform="translate(1660 120)"><rect x="-6" y="0" width="12" height="500" fill="#c9a24a"/><path d="M6 20H230V230H6Z" fill="#fff" ${st(4)}/>${Array.from({ length: 6 }, (_, i) => `<rect x="6" y="${20 + i * 35}" width="224" height="17" fill="#d9453f"/>`).join("")}<rect x="6" y="20" width="100" height="105" fill="#2c4a8c"/></g>
      <g transform="translate(1360 470)"><circle r="68" fill="#f3ead2" ${st(7)}/><path d="M0 0V-44M0 0L30 20" stroke="${OL}" stroke-width="7" stroke-linecap="round"/><circle r="5" fill="${OL}"/></g>`;
    const fl = floorBoards(800, 280, "#3a3340", 8) + `<g transform="translate(560 960)"><rect x="0" y="-30" width="800" height="90" rx="30" fill="#6a2f3a" ${st(6)}/></g>
      <g transform="translate(1640 780)"><rect x="-70" y="-250" width="140" height="250" fill="#8a8f9a" ${st(6)}/>${[0, 1, 2].map((i) => `<rect x="-56" y="${-236 + i * 80}" width="112" height="68" fill="#a7acb7" ${st(4)}/><rect x="-18" y="${-212 + i * 80}" width="36" height="10" fill="#4a4f5a"/>`).join("")}</g>`;
    return { layers: [L("wall", 0.2, wall), L("det", 0.4, shelf + window_ + dip), L("floor", 0.7, fl)] };
  }

  /* 4 · trial: courthouse facade at dusk, steps, TV news light, scales emblem */
  function courthouse() {
    const id = uid("cg"), sky = `<defs>${grad(id, "#1b2140", "#4b4a78", 1)}</defs><rect width="1920" height="1080" fill="url(#${id})"/>${Array.from({ length: 30 }, (_, i) => `<circle cx="${(i * 311) % 1920}" cy="${(i * 97) % 380}" r="${1.5 + (i % 3)}" fill="#fff" opacity=".6"/>`).join("")}`;
    const cols = Array.from({ length: 7 }, (_, i) => `<g transform="translate(${330 + i * 190} 0)"><rect x="-44" y="270" width="88" height="470" fill="#e8dfd0" ${st(6)}/><rect x="-58" y="250" width="116" height="30" fill="#d4c9b6" ${st(5)}/><rect x="-58" y="730" width="116" height="26" fill="#d4c9b6" ${st(5)}/>${[-22, 0, 22].map((x) => `<path d="M${x} 290V720" stroke="#bfb29a" stroke-width="4"/>`).join("")}</g>`).join("");
    const pedi = `<path d="M240 250L960 70L1680 250Z" fill="#efe6d6" ${st(7)}/><path d="M360 232L960 100L1560 232Z" fill="#d9ceba"/><g transform="translate(960 190)"><path d="M0 -50V50M-50 -20H50" stroke="${OL}" stroke-width="7"/><path d="M-50 -20L-72 18H-28ZM50 -20L28 18H72Z" fill="#c9a24a" ${st(4)}/><circle cy="-56" r="8" fill="#c9a24a" ${st(3)}/></g>`;
    const steps = Array.from({ length: 5 }, (_, i) => `<rect x="${200 - i * 30}" y="${740 + i * 34}" width="${1520 + i * 60}" height="34" fill="${shade("#cfc3ae", -i * 0.05)}" ${st(5)}/>`).join("");
    const door = `<rect x="860" y="470" width="200" height="270" rx="90" fill="#3a2418" ${st(6)}/><path d="M960 470V740" stroke="${OL}" stroke-width="5"/>`;
    return { layers: [L("sky", 0.05, sky), L("bldg", 0.3, pedi + cols + door), L("steps", 0.7, steps)] };
  }

  /* 5 · 1989 home, dim: front door, coat rack, sofa, packed boxes, family photos, TV */
  function home80s(pal) {
    pal = Object.assign({ wall: "#a8794f", floor: "#5a3a28" }, pal);
    const wall = `<rect width="1920" height="790" fill="${pal.wall}"/>${Array.from({ length: 20 }, (_, i) => `<path d="M${i * 100} 0V790" stroke="${shade(pal.wall, -0.1)}" stroke-width="22" opacity=".35"/>`).join("")}<rect y="660" width="1920" height="130" fill="${shade(pal.wall, -0.2)}"/><rect y="650" width="1920" height="12" fill="${shade(pal.wall, 0.25)}"/>`;
    const door = `<g transform="translate(1560 230)"><rect width="230" height="560" fill="#3f2a1c" ${st(7)}/><rect x="24" y="30" width="182" height="190" fill="#7a5238" ${st(5)}/><rect x="24" y="260" width="182" height="250" fill="#7a5238" ${st(5)}/><circle cx="190" cy="300" r="12" fill="#e0b040" ${st(3)}/></g><path d="M1560 790L1500 1000L1860 1000L1790 790Z" fill="#ffd9a0" opacity=".28"/>`;
    const furn = frame(130, 170, 150, 190, "#b88a5a") + frame(320, 140, 130, 160, "#7a9ab0") + frame(490, 190, 170, 130, "#9a6a5a") +
      lamp(220, 520, "#f6d58a").replace('translate(220 520)', 'translate(230 560)') + sofa(760, 790, "#6a7ea0", 620) +
      `<g transform="translate(1180 380)"><rect width="300" height="250" rx="22" fill="#4a3a2e" ${st(7)}/><rect x="26" y="26" width="248" height="190" rx="14" fill="#2a3640"/>${Array.from({ length: 12 }, (_, i) => `<rect x="26" y="${30 + i * 15}" width="248" height="4" fill="#fff" opacity=".05"/>`).join("")}<rect x="40" y="250" width="220" height="130" fill="#6a4a36" ${st(6)}/></g>`;
    const boxes = `<g transform="translate(1250 920)">${[[0, 0, 150, 110], [160, 10, 120, 100], [60, -100, 130, 100]].map(([x, y, w, h]) => `<g transform="translate(${x} ${y})"><rect x="0" y="-${h}" width="${w}" height="${h}" fill="#c99a62" ${st(5)}/><path d="M0 -${h * .62}H${w}" stroke="#a97a42" stroke-width="10"/><rect x="${w * .38}" y="-${h * .62}" width="${w * .24}" height="${h * .3}" fill="#e8d4a8" opacity=".85"/></g>`).join("")}</g>`;
    const fl = floorBoards(790, 290, pal.floor, 10) + `<g transform="translate(300 950)"><ellipse cx="560" cy="0" rx="560" ry="80" fill="#8a3a3a" ${st(6)}/></g>`;
    return { layers: [L("wall", 0.2, wall), L("door", 0.35, door), L("furn", 0.45, furn), L("floor", 0.7, fl + boxes)] };
  }

  /* 6 · new family 1991: backyard wedding - arch of flowers, fence, tree, string lights, cake table */
  function weddingYard() {
    const id = uid("wy"), sky = `<defs>${grad(id, "#ffb98a", "#ffe6b8", 1)}</defs><rect width="1920" height="1080" fill="url(#${id})"/><circle cx="1500" cy="330" r="110" fill="#fff2c4" opacity=".9"/>`;
    const tree = (x, s) => `<g transform="translate(${x} 800) scale(${s})"><rect x="-30" y="-330" width="60" height="330" fill="#5a3a28" ${st(6)}/><circle cx="0" cy="-390" r="170" fill="#3f7a4a" ${st(6)}/><circle cx="-120" cy="-320" r="110" fill="#4c8a5a" ${st(6)}/><circle cx="120" cy="-320" r="110" fill="#4c8a5a" ${st(6)}/>${Array.from({ length: 8 }, (_, i) => `<circle cx="${-120 + i * 34}" cy="${-420 + (i % 3) * 40}" r="8" fill="${["#f2a7b8", "#fff", "#f6d54a"][i % 3]}"/>`).join("")}</g>`;
    const fence = `<rect y="690" width="1920" height="12" fill="#f3ead2" ${st(4)}/><rect y="740" width="1920" height="12" fill="#f3ead2" ${st(4)}/>${Array.from({ length: 34 }, (_, i) => `<path d="M${i * 60 + 14} 800V660L${i * 60 + 30} 636L${i * 60 + 46} 660V800Z" fill="#f8f1de" ${st(4)}/>`).join("")}`;
    const arch = `<g transform="translate(960 800)"><path d="M-300 0V-420Q0 -640 300 -420V0" fill="none" stroke="#f3ead2" stroke-width="30" ${st(5)}/>${Array.from({ length: 22 }, (_, i) => { const a = Math.PI * (i / 21), x = -300 * Math.cos(a), y = -420 - 210 * Math.sin(a); return `<circle cx="${x}" cy="${y}" r="${18 + (i % 3) * 6}" fill="${["#f2a7b8", "#fff", "#f6d54a", "#e4483f"][i % 4]}" ${st(3)}/>`; }).join("")}${Array.from({ length: 6 }, (_, i) => `<circle cx="-300" cy="${-60 - i * 60}" r="16" fill="${["#f2a7b8", "#fff"][i % 2]}" ${st(3)}/><circle cx="300" cy="${-60 - i * 60}" r="16" fill="${["#fff", "#f2a7b8"][i % 2]}" ${st(3)}/>`).join("")}</g>`;
    const lights = `<path d="M0 220Q480 330 960 240T1920 220" fill="none" stroke="#2a1820" stroke-width="4"/>${Array.from({ length: 26 }, (_, i) => { const x = i * 76 + 10; const y = 224 + Math.sin(i / 26 * Math.PI * 4) * 12 + 24 + Math.sin(i / 26 * Math.PI) * 60; return `<circle cx="${x}" cy="${y}" r="11" fill="#ffe08a" ${st(3)}/>`; }).join("")}`;
    const grass = `<rect y="800" width="1920" height="280" fill="#6fa05a"/>${Array.from({ length: 40 }, (_, i) => `<path d="M${i * 50 + 10} ${830 + (i % 5) * 50}l8 -22l8 22" stroke="#4c8a3c" stroke-width="5" fill="none"/>`).join("")}`;
    const table = `<g transform="translate(1530 880)"><rect x="-130" y="-120" width="260" height="20" fill="#f3ead2" ${st(5)}/><rect x="-100" y="-100" width="12" height="100" fill="#a98a5a"/><rect x="88" y="-100" width="12" height="100" fill="#a98a5a"/><rect x="-70" y="-170" width="140" height="50" rx="8" fill="#fff" ${st(5)}/><rect x="-46" y="-216" width="92" height="46" rx="8" fill="#f2a7b8" ${st(5)}/><path d="M0 -216V-244" stroke="${OL}" stroke-width="5"/><circle cy="-250" r="7" fill="#f6a52a"/></g>`;
    const balloons = [[260, 520, "#e4483f"], [330, 470, "#f6d54a"], [400, 540, "#3d8bd0"]].map(([x, y, c]) => `<g><path d="M${x} ${y + 60}Q${x + 20} ${y + 200} ${x - 30} ${y + 300}" stroke="#2a1820" stroke-width="3" fill="none"/><ellipse cx="${x}" cy="${y}" rx="44" ry="56" fill="${c}" ${st(5)}/><path d="M${x - 18} ${y - 28}Q${x - 6} ${y - 40} ${x + 6} ${y - 34}" stroke="#fff" stroke-width="5" fill="none" opacity=".6"/></g>`).join("");
    return { layers: [L("sky", 0.05, sky), L("trees", 0.25, tree(300, 0.9) + tree(1700, 1.05) + fence), L("lights", 0.3, lights), L("arch", 0.5, arch + balloons), L("grass", 0.75, grass + table)] };
  }

  /* 7 · 1976 stadium: night stands, flood lights, track lanes, scoreboard */
  function stadium() {
    const r = rng(11), id = uid("sd"), sky = `<defs>${grad(id, "#0b1230", "#26407a", 1)}</defs><rect width="1920" height="1080" fill="url(#${id})"/>`;
    let crowd = ""; for (let row = 0; row < 7; row++) for (let i = 0; i < 64; i++) crowd += `<circle cx="${i * 31 + (row % 2) * 14}" cy="${430 + row * 40}" r="10" fill="${["#f2c9a0", "#e0a275", "#c98f6a", "#f6d54a", "#e4483f", "#fff"][Math.floor(r() * 6)]}" opacity=".9"/>`;
    const stands = `<path d="M0 380L1920 380V700H0Z" fill="#232a4a"/>${crowd}<rect y="690" width="1920" height="16" fill="#4a5280" ${st(4)}/>`;
    const tower = (x) => `<g transform="translate(${x} 0)"><rect x="-12" y="100" width="24" height="320" fill="#2a2f4a"/><rect x="-90" y="40" width="180" height="90" fill="#1a1f38" ${st(5)}/>${Array.from({ length: 12 }, (_, i) => `<circle cx="${-72 + (i % 6) * 29}" cy="${66 + Math.floor(i / 6) * 42}" r="11" fill="#fff9d0"/>`).join("")}</g>`;
    const board = `<g transform="translate(760 130)"><rect width="400" height="190" rx="12" fill="#101830" ${st(7)}/><text x="200" y="88" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="64" fill="#ffd24a" letter-spacing="6">MONTREAL</text><text x="200" y="158" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="52" fill="#fff" letter-spacing="4">1976</text></g>`;
    const track = `<rect y="700" width="1920" height="380" fill="#b2492f"/>${Array.from({ length: 5 }, (_, i) => `<path d="M0 ${730 + i * 70}H1920" stroke="#fff" stroke-width="6" opacity=".85"/>`).join("")}<ellipse cx="960" cy="1060" rx="900" ry="60" fill="#000" opacity=".15"/>`;
    return { layers: [L("sky", 0.05, sky), L("stands", 0.25, stands + tower(240) + tower(1680) + board), L("track", 0.7, track)] };
  }

  /* 8 · 2007 home: modern living room, flat TV, sofa, plant, window, light stand + cables (film crew) */
  function tvHome() {
    const wall = `<rect width="1920" height="790" fill="#e5dccb"/><rect y="650" width="1920" height="140" fill="#cfc4b0"/><rect y="640" width="1920" height="12" fill="#fff" opacity=".7"/>`;
    const det = win(160, 140, 420, 440, "#a8d4f0", `<path d="M0 300Q100 240 200 290T420 270V440H0Z" fill="#6fa05a"/>`) +
      `<path d="M150 130Q190 300 175 580M590 130Q550 300 565 580" stroke="#c9a98a" stroke-width="34" fill="none"/>` +
      `<g transform="translate(900 250)"><rect width="520" height="300" rx="10" fill="#15181f" ${st(7)}/><rect x="14" y="14" width="492" height="272" fill="#2e5a8a"/><path d="M14 230L170 120L260 200L360 100L506 220V286H14Z" fill="#3f7aa8" opacity=".8"/><rect x="180" y="300" width="160" height="30" fill="#15181f" ${st(5)}/></g>` +
      sofa(1440, 800, "#8a8f98", 560) +
      `<g transform="translate(700 800)"><path d="M-40 0L-30 -90H30L40 0Z" fill="#b9825a" ${st(5)}/>${[[-50, -140], [0, -190], [50, -140], [-20, -240], [30, -230]].map(([x, y], i) => `<path d="M0 -90Q${x} ${y} ${x * 1.6} ${y - 30}Q${x * .4} ${y + 10} 0 -90Z" fill="${["#3f8a52", "#2f7a42"][i % 2]}" ${st(4)}/>`).join("")}</g>` +
      frame(640, 190, 120, 150, "#8aa8c0") + frame(1560, 190, 150, 120, "#c0a08a");
    const fl = floorBoards(790, 290, "#8f6a48", 8) + `<g transform="translate(800 960)"><rect x="0" y="-60" width="760" height="100" rx="12" fill="#cfd4dc" opacity=".6" ${st(5)}/></g>` +
      `<g transform="translate(1120 810)"><path d="M0 0V-300M-60 0L0 -80L60 0" stroke="#2a2f3a" stroke-width="10" fill="none"/><rect x="-70" y="-380" width="140" height="90" rx="8" fill="#2a2f3a" ${st(5)}/><circle cx="0" cy="-335" r="30" fill="#fff6c8" ${st(4)}/></g>` +
      `<path d="M1120 810C1000 900 800 950 560 900S200 990 20 980" stroke="#2a2f3a" stroke-width="8" fill="none" opacity=".8"/>`;
    return { layers: [L("wall", 0.2, wall), L("det", 0.4, det), L("floor", 0.7, fl)] };
  }

  /* 9 · TV studio: set backdrop, couch, ON AIR sign, camera dollies, monitors */
  function tvStage() {
    const id = uid("tv"), back = `<defs>${grad(id, "#2a1a47", "#7a3d8f", 1)}</defs><rect width="1920" height="1080" fill="url(#${id})"/>` +
      Array.from({ length: 8 }, (_, i) => `<rect x="${60 + i * 235}" y="170" width="190" height="520" rx="10" fill="${["#3d2a70", "#5a3a96"][i % 2]}" opacity=".85" ${st(4)}/>`).join("") +
      Array.from({ length: 11 }, (_, i) => `<g transform="translate(${60 + i * 175} 40)"><rect x="-8" y="0" width="16" height="50" fill="#1a1230"/><path d="M-34 50H34L26 100H-26Z" fill="#241a40" ${st(4)}/></g>`).join("");
    const sign = `<g transform="translate(960 120)"><rect x="-150" y="-50" width="300" height="100" rx="14" fill="#a8171f" ${st(7)}/><text y="24" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="70" fill="#fff" letter-spacing="6">ON AIR</text></g>`;
    const set = `<g transform="translate(400 800)">${sofa(0, 0, "#d9a0c0", 520).replace("translate(0 0)", "translate(0 0)")}</g><g transform="translate(1500 800)"><rect x="-130" y="-120" width="260" height="22" rx="8" fill="#f3ead2" ${st(5)}/><rect x="-12" y="-100" width="24" height="100" fill="#a98a5a"/><ellipse cy="0" rx="90" ry="14" fill="#a98a5a" ${st(5)}/></g>` +
      [[1300, "#3a2a60"], [520, "#3a2a60"]].map(([x]) => `<g transform="translate(${x} 790)"><rect x="-70" y="-60" width="140" height="60" fill="#14102a" ${st(5)}/><rect x="-46" y="-190" width="92" height="140" rx="10" fill="#241a40" ${st(6)}/><rect x="-62" y="-250" width="124" height="70" rx="10" fill="#14102a" ${st(5)}/><circle cx="-24" cy="-215" r="18" fill="#7fd0ff" ${st(4)}/></g>`).join("");
    const fl = `<rect y="800" width="1920" height="280" fill="#150f22"/><rect y="800" width="1920" height="10" fill="#ff8ad0" opacity=".7"/><ellipse cx="960" cy="900" rx="820" ry="70" fill="#ff8ad0" opacity=".14"/>`;
    return { layers: [L("back", 0.2, back + sign), L("set", 0.45, set), L("floor", 0.7, fl)] };
  }

  /* 10 · SKIMS boutique: warm neutral shelves, folded garments, mannequins, spotlights, sign */
  function boutique() {
    const id = uid("bq"), wall = `<defs>${grad(id, "#e8d9c6", "#cdb79e", 1)}</defs><rect width="1920" height="800" fill="url(#${id})"/>` +
      Array.from({ length: 12 }, (_, i) => `<path d="M${i * 170 + 40} 0L${i * 170 - 30} 800L${i * 170 + 110} 800Z" fill="#fff" opacity="${0.04 + (i % 3) * 0.03}"/>`).join("");
    const tones = ["#d6bfa6", "#b89b86", "#8f7566", "#efe0cc", "#6f5a4e", "#c9a58a"];
    const shelves = (x) => `<g transform="translate(${x} 260)"><rect width="440" height="520" fill="#f6efe4" ${st(6)}/>${[0, 1, 2, 3].map((i) => `<rect x="12" y="${14 + i * 126}" width="416" height="10" fill="#a98a6a" ${st(3)}/>` + Array.from({ length: 4 }, (_, k) => `<rect x="${24 + k * 100}" y="${24 + i * 126}" width="88" height="${54 + (k % 2) * 8}" rx="6" fill="${tones[(i * 4 + k) % 6]}" ${st(4)}/><rect x="${24 + k * 100}" y="${24 + i * 126 + 28}" width="88" height="5" fill="#fff" opacity=".35"/>`).join("")).join("")}</g>`;
    const sign = `<g transform="translate(960 150)"><rect x="-230" y="-60" width="460" height="120" rx="12" fill="#f6efe4" ${st(7)}/><text y="26" text-anchor="middle" font-family="Inter,Arial" font-weight="800" font-size="84" fill="#5a4538" letter-spacing="16">SKIMS</text></g>`;
    const mannequin = (x, c) => `<g transform="translate(${x} 800)"><rect x="-6" y="-120" width="12" height="120" fill="#4a3a30" ${st(4)}/><ellipse cy="0" rx="50" ry="10" fill="#4a3a30" ${st(4)}/><path d="M-44 -420Q-50 -330 -34 -280Q-50 -220 -40 -150L40 -150Q50 -220 34 -280Q50 -330 44 -420Q0 -440 -44 -420Z" fill="${c}" ${st(6)}/><ellipse cy="-455" rx="22" ry="30" fill="#e9dccb" ${st(5)}/></g>`;
    const fl = `<rect y="800" width="1920" height="280" fill="#b59c82"/><rect y="800" width="1920" height="10" fill="#fff" opacity=".5"/><ellipse cx="960" cy="900" rx="880" ry="70" fill="#fff" opacity=".18"/>`;
    return { layers: [L("wall", 0.2, wall + sign), L("shelf", 0.4, shelves(110) + shelves(1370) + mannequin(780, "#c9a58a") + mannequin(1140, "#8f7566")), L("floor", 0.7, fl)] };
  }

  Object.assign(K.bg, { laStreet, nursery, lawOffice, courthouse, home80s, weddingYard, stadium, tvHome, tvStage, boutique });
})(window.K);
