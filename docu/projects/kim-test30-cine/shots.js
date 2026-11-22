/* Cinematic revision of the 32-second Kim test (project kim-test30-cine).
   18 shots, every cut hangs on a real word start/end from timing.json (anchors ["sN","w",i] / ["sN","e",i]).
   Layers per shot: far set -> structure -> fog -> actors -> dark foreground -> colour grade -> key light -> labels.
   Kim is a semi-realistic cartoon built from design traits (jet-black hair, strong arched brows, brown eyes, fuller lips);
   no photo is embedded and no exact likeness is claimed. */
const KIM = { skin: "#d99a73", hairColor: "#16100f", eyeColor: "#4a2a1a", accent: "#e4483f" };
const YOU = (stage, extra) => Object.assign({}, KIM, ({
  baby:  { build: "baby",  hair: "baby_tuft",  outfit: "babygrow", top: "#f6e7a8", pants: "#f6e7a8", shoe: "#f6e7a8", legs: "pants", sleeve: "none" },
  child: { build: "child", hair: "child_pony", outfit: "sweat80s", top: "#f2a7b8", pants: "#6a7ec2", shoe: "#f2efe8" },
  w2007: { build: "woman", hair: "long_straight", outfit: "tee2007", top: "#24242c", pants: "#3b5a8a", shoe: "#2b2230", earrings: 1, sleeve: "short", lip: "#b8626a" },
  w2025: { build: "woman", hair: "long_straight", outfit: "dress", top: "#b89b86", legs: "bare", shoe: "#c9a58a", shoeType: "pump", sleeve: "none", earrings: 1, lip: "#c4666b" },
})[stage], extra || {});
const DAD = { build: "man", skin: "#e8b896", hair: "short_man", hairColor: "#4a3426", top: "#2f3a4f", pants: "#262b3a", outfit: "suit", glasses: 1, accent: "#a63a3a" };
const MOM = { build: "woman", skin: "#e5ae88", hair: "big80s", hairColor: "#241713", top: "#b4434a", pants: "#2b2230", outfit: "blazer", accent: "#f3c64a", earrings: 1, lip: "#b23a4a", sleeve: "long" };
const MOMW = Object.assign({}, MOM, { outfit: "dress", top: "#f6f1e8", legs: "bare", shoe: "#f6f1e8", shoeType: "pump", sleeve: "none" });
const BRUCE = { build: "man", skin: "#e9b996", hair: "slick", hairColor: "#6a4a2e", top: "#3a6aa8", pants: "#2e3a5a", outfit: "track", accent: "#f6f2e8", shoe: "#f6f2e8" };
const BRUCEW = Object.assign({}, BRUCE, { outfit: "suit", top: "#2b2f3d", pants: "#2b2f3d", accent: "#c43b3b", shoe: "#1a1a22" });
const CREW = { build: "man", skin: "#c98f6a", hair: "short_man", hairColor: "#1f1512", top: "#35353f", pants: "#22222a", outfit: "track", accent: "#6a6a78" };
const NURSE = { build: "woman", skin: "#e9c0a0", hair: "bob", hairColor: "#5a3a26", top: "#e9f3f2", legs: "bare", outfit: "dress", shoe: "#f2efe8", sleeve: "none" };
const FX = K.fx, PR = FX.props, C = K.cine, B = K.bgc, FG = K.fgc, OLN = K.OL;
const W = (sid, i) => [sid, "w", i], E = (sid, i) => [sid, "e", i];
const lab = (S, id, text, x, y, t, o) => { S.layer(FX.label(id, text, x, y, o), 1.1); S.pop(id, t, 0.34); };
const grade = (S, name, o) => S.layer(C.look(name, o), 0);
const light = (S, x, y, rx, ry, col, op) => S.layer(C.key(x, y, rx, ry, col, op), 0);
/** actor scaled so the HEAD is `head` px tall and its face centre sits at (cx, cy): real facial close-up */
const closeUp = (S, id, spec, cx, cy, head, o) => {
  const b = K.chars.BUILDS[spec.build], yH = -(b.legH + b.torsoH + b.neck - 8), sc = head / (184 * b.headS);
  return S.actor(id, Object.assign({ detail: 1 }, spec), cx, cy - (yH - 88 * b.headS) * sc, sc, o || {});
};
const confetti = (S, t0, n, seed) => { const r = K.rng(seed), cols = ["#f3c64a", "#e4483f", "#4c8a5a", "#3d6a9c", "#fff"]; let m = "";
  for (let i = 0; i < n; i++) m += `<g transform="translate(${Math.round(160 + r() * 1600)} -40)"><g data-p="cf${i}"><rect x="-9" y="-5" width="18" height="10" fill="${cols[i % 5]}" stroke="#2a1820" stroke-width="2"/></g></g>`;
  S.layer(m, 1.2);
  for (let i = 0; i < n; i++) { const e = S.q("cf" + i), st = t0 + r() * 0.9, d = Math.max(0.3, Math.min(2.0 + r() * 1.4, S.t1 - st - 0.02));
    S.key(e, "--y", st, 0, 0); S.key(e, "--y", st, 1180, d, "none"); S.key(e, "--x", st, 0, 0); S.key(e, "--x", st, (r() - 0.5) * 260, d, "sine.inOut"); S.key(e, "--r", st, 0, 0); S.key(e, "--r", st, (r() - 0.5) * 900, d, "none"); } };
const OL = K.OL, st = (w) => `stroke="${OL}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"`;

/* ================= 1 · wide: Los Angeles avenue at sunset, nurse + newborn walk toward camera ================= */
D.shot({ id: "la", a: 0, b: W("s1", 8), bg: B.avenue(), cam: { from: [20, 14, 0.0], to: [-30, -16, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, PV = [1190, 640], nx = 1190, ny = 640, SC = 0.42;
    S.layer(C.rays(960, 548, Math.PI / 2, 760, 0.42, "#ffd9a0", 0.34), 0.42);
    C.fog(S, { y: 650, h: 220, color: "#ffcfa0", op: 0.32, seed: 3, depth: 0.55, drift: 120 });
    const nurse = S.actor("nurse", NURSE, nx, ny, SC, { depth: 0.9, seed: 77, idle: false, pivot: PV }), kimB = S.actor("kimBaby", YOU("baby"), nx + 30, ny - 252 * 1.0, SC * 0.95, { depth: 0.9, seed: 5, idle: false, pivot: PV });
    S.layer(`<g transform="translate(${PV[0]} ${PV[1]})"><g data-p="bundle"><g transform="translate(30 -224) scale(${SC})"><path d="M-88 -46Q0 -86 88 -46L102 40Q0 74 -102 40Z" fill="#fbf6ea" ${st(6)}/><path d="M-70 -20Q0 -46 70 -20M-80 8Q0 -18 80 8" stroke="#f2a7b8" stroke-width="7" fill="none" stroke-linecap="round"/></g></g></g>`, 0.9);
    const bund = S.q("bundle"), a = t0 + 0.1, b = t1 - 0.05;
    nurse.face(t0, "happy", 0); kimB.face(t0, "happy", 0); kimB.look(t0, 0, -4, 0);
    nurse.arm("L", t0, -48, -78, 0.01); nurse.arm("R", t0, 48, 78, 0.01);
    nurse.walk(a, b, 0, { arms: false, step: 0.3, amp: 16 });
    [nurse.el, kimB.el, bund].forEach((e) => { S.key(e, "--s", t0, 1, 0); S.key(e, "--s", a, 2.45, b - a, "power1.in"); S.key(e, "--y", t0, 0, 0); S.key(e, "--y", a, 330, b - a, "power1.in"); });
    S.layer(FG.leaves("L"), 1.7); S.layer(FG.leaves("R"), 1.75);
    grade(S, "dusk");
    light(S, 1190, 780, 420, 380, "#ffd7a0", 0.5);
    S.layer(`<g data-p="title"><g transform="translate(960 190)"><rect x="-640" y="-58" width="1280" height="116" rx="18" fill="#fff" ${st(7)}/><text x="0" y="18" text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="50" fill="#2a1820">WHAT IF YOU WERE BORN AS KIM KARDASHIAN?</text></g></g>`, 0.1);
    S.pop("title", t0 + 0.25, 0.45); S.key("title", "opacity", D.W("s1", 4) - 0.1, 0, 0.3, "power1.in");
    lab(S, "laLabel", "LOS ANGELES · 1980", 1400, 420, D.W("s1", 4) + 0.05, { size: 52, rot: 3 });
  } });

/* ================= 2 · close-up: newborn face behind crib bars, moonlight ================= */
D.vhs(D.W("s1", 8), "1980", { strength: 0.5, post: 0.22, year: 0.4 });
D.shot({ id: "babyClose", a: W("s1", 8), b: W("s1", 9), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("baby") }] }, cam: { from: [0, 0, 0.02], to: [14, -10, 0.14] },
  build(S) {
    const t0 = S.t0;
    S.layer(C.rays(1700, -40, 1.9, 1100, 0.3, "#9fb8ff", 0.34), 0.4);
    const baby = closeUp(S, "baby", YOU("baby"), 960, 500, 560, { depth: 0.9, seed: 4 });
    baby.face(t0, "neutral", 0); baby.look(t0, -8, -6, 0); baby.look(t0 + 0.45, 8, -6, 0.5, "sine.inOut"); baby.face(t0 + 0.7, "happy", 0.3);
    baby.turn(t0 + 0.1, -4, -3, 0.5); baby.turn(t0 + 0.7, 4, 3, 0.4);
    C.dust(S, { n: 16, seed: 12, box: [200, 100, 1500, 800], color: "#d8e4ff", depth: 1.1, op: 0.5 });
    S.layer(FG.barsAt([70, 250, 1670, 1850]), 1.55);
    grade(S, "night");
    light(S, 960, 470, 520, 420, "#ffe2b0", 0.4);
    lab(S, "bornLabel", "OCT 21, 1980", 1480, 250, t0 + 0.12, { size: 54, rot: 3 });
  } });

/* ================= 3 · detail: the hospital wristband on a tiny wrist ================= */
D.shot({ id: "bracelet", a: W("s1", 9), b: W("s2", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: `<rect x="-80" y="-80" width="2080" height="1240" fill="#cfd9ea"/>` + Array.from({ length: 10 }, (_, i) => `<path d="M${-100 + i * 240} -80 L${140 + i * 240} 1160" stroke="#b6c6dc" stroke-width="60" opacity=".5"/>`).join("") + C.bokeh(9, ["#fff", "#ffe2b0"], 8) }] }, cam: { from: [-40, 10, 0.0], to: [30, -10, 0.16] },
  build(S) {
    const t0 = S.t0, band = `<g data-p="wrist"><g transform="translate(960 610) rotate(-14)"><path d="M-760 -92 Q-300 -130 90 -100 Q300 -86 330 0 Q300 90 90 100 Q-300 130 -760 92Z" fill="#e0a77f" ${st(10)}/><path d="M-700 -52 Q-300 -88 80 -62" stroke="#f0c09a" stroke-width="18" fill="none" stroke-linecap="round" opacity=".7"/><path d="M-30 -96 Q-14 0 -30 96" stroke="#c98a64" stroke-width="8" fill="none" opacity=".5"/>
      <g data-p="fist"><path d="M300 -70 Q400 -96 470 -40 Q510 10 470 66 Q400 110 300 80Z" fill="#e0a77f" ${st(10)}/>${[-44, -8, 28, 60].map((y) => `<path d="M440 ${y} Q500 ${y - 6} 506 ${y + 14}" stroke="${OLN}" stroke-width="8" fill="none" stroke-linecap="round"/>`).join("")}<path d="M330 -66 Q380 -120 430 -96" stroke="${OLN}" stroke-width="8" fill="#e0a77f" stroke-linecap="round"/></g>
      <g data-p="bandA"><rect x="-120" y="-98" width="360" height="196" rx="24" fill="#fbfbff" ${st(9)}/><rect x="-100" y="-78" width="320" height="156" rx="14" fill="none" stroke="#8aa8d8" stroke-width="4"/>
      <text x="60" y="-26" text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="40" fill="#24304a" letter-spacing="2">BABY GIRL</text>
      <text x="60" y="26" text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="46" fill="#c4252d">10 · 21 · 1980</text>
      ${Array.from({ length: 22 }, (_, i) => `<rect x="${-80 + i * 14}" y="42" width="${i % 3 ? 5 : 9}" height="26" fill="#24304a"/>`).join("")}</g></g></g>`;
    S.layer(band, 0.9); S.layer(FG.leaves("L"), 1.7);
    S.key("wrist", "--x", t0, -180, 0); S.key("wrist", "--x", t0, 0, 0.6, "power3.out");
    S.key("fist", "--r", t0 + 0.4, 0, 0); for (let t = t0 + 0.4, i = 0; t < S.t1 - 0.2; t += 0.45, i++) S.key("fist", "--r", t, i % 2 ? 6 : -6, 0.45, "sine.inOut");
    S.fadeIn("bandA", t0 + 0.05, 0.3);
    C.dust(S, { n: 12, seed: 21, box: [100, 100, 1600, 700], color: "#fff", depth: 1.2, op: 0.5 });
    grade(S, "night", { tint: "#9db0d8", ta: 0.3, dark: 0.14 });
    light(S, 1000, 560, 640, 360, "#fff4e0", 0.55);
    lab(S, "wbLabel", "BORN 1980", 520, 300, t0 + 0.3, { size: 54, rot: -3 });
  } });

/* ================= 4 · extreme close-up: father's eyes behind glasses ================= */
D.shot({ id: "dadEyes", a: W("s2", 0), b: W("s2", 2), bg: { layers: [{ name: "b", depth: 0.15, svg: B.closeBack("dad") }] }, cam: { from: [0, 0, 0.02], to: [0, 0, 0.14] },
  build(S) {
    const t0 = S.t0, sk = "#e8b896", sh = "#c99573", dk = "#2e2630";
    const eye = (id, x) => `<g transform="translate(${x} 540)"><ellipse rx="150" ry="84" fill="#f6f0ea" ${st(10)}/><g clip-path="url(#dclip${id})"><g data-p="diris${id}"><circle r="64" cx="0" cy="2" fill="#4a3426"/><circle r="38" cy="2" fill="#16100f"/><circle cx="-22" cy="-20" r="16" fill="#fff"/><circle cx="26" cy="22" r="7" fill="#fff" opacity=".8"/></g><g data-p="dlid${id}"><rect x="-160" y="-100" width="320" height="104" fill="${sk}"/><path d="M-160 4Q0 40 160 4" fill="none" ${st(9)}/></g></g><defs><clipPath id="dclip${id}"><ellipse rx="150" ry="84"/></clipPath></defs>
      <path d="M-170 -86 Q0 -150 170 -90" fill="none" stroke="#3a2a1e" stroke-width="30" stroke-linecap="round"/><path d="M-150 96 Q0 150 150 96" stroke="${sh}" stroke-width="16" fill="none" opacity=".4" stroke-linecap="round"/></g>`;
    S.layer(`<rect x="-80" y="250" width="2080" height="600" fill="${sk}"/><rect x="-80" y="250" width="2080" height="90" fill="${sh}" opacity=".55"/><path d="M880 330 Q960 560 880 760 L1040 760 Q960 560 1040 330Z" fill="${sh}" opacity=".5"/>` +
      eye("L", 640) + eye("R", 1280) +
      `<g fill="none" stroke="${dk}" stroke-width="15"><circle cx="640" cy="540" r="215"/><circle cx="1280" cy="540" r="215"/><path d="M855 520Q960 470 1065 520"/><path d="M425 520 L-60 470M1495 520 L1980 470"/></g><g fill="#fff" opacity=".1"><circle cx="640" cy="540" r="213"/><circle cx="1280" cy="540" r="213"/></g>
      <g data-p="glint1"><path d="M560 380 L640 380 L520 700 L440 700Z" fill="#fff" opacity=".32" style="mix-blend-mode:screen"/></g><g data-p="glint2"><path d="M1200 380 L1280 380 L1160 700 L1080 700Z" fill="#fff" opacity=".32" style="mix-blend-mode:screen"/></g>`, 0.9);
    ["L", "R"].forEach((s) => { S.key("diris" + s, "--x", t0, -26, 0); S.key("diris" + s, "--x", t0 + 0.3, 30, 0.45, "sine.inOut"); S.key("diris" + s, "--x", t0 + 0.8, 0, 0.3); });
    ["L", "R"].forEach((s) => { S.key("dlid" + s, "--y", t0 + 0.55, 0, 0); S.key("dlid" + s, "--y", t0 + 0.55, 84, 0.07, "power1.in"); S.key("dlid" + s, "--y", t0 + 0.65, 0, 0.1); });
    S.key("glint1", "--x", t0, -120, 0); S.key("glint1", "--x", t0, 240, S.dur, "none"); S.key("glint2", "--x", t0, -120, 0); S.key("glint2", "--x", t0, 240, S.dur, "none");
    S.layer(`<path d="M-80 -80H2000V300Q960 230 -80 300Z M-80 780Q960 840 2000 780V1160H-80Z" fill="#07050b" opacity=".9"/>`, 1.3);
    grade(S, "office");
    light(S, 960, 540, 760, 260, "#ffd9a0", 0.35);
    lab(S, "dadTag", "YOUR FATHER", 960, 190, t0 + 0.12, { size: 52, rot: -2 });
  } });

/* ================= 5 · wide: father walks into his office (converging walls, window light) ================= */
D.shot({ id: "office", a: W("s2", 2), b: W("s2", 6), bg: B.office(), cam: { from: [-60, 6, 0.0], to: [40, -10, 0.18] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 340, Math.PI / 2, 800, 0.36, "#cfe0ff", 0.3), 0.45);
    S.layer(PR.desk(1180, 860, 520), 0.8);
    C.fog(S, { y: 700, h: 200, color: "#8fa4d0", op: 0.22, seed: 5, depth: 0.55, drift: 80 });
    const dad = S.actor("dad", DAD, 520, 860, 1.22, { seed: 9, pivot: [520, 860] });
    dad.k("self", "--x", t0, -760, 0); dad.walk(t0 + 0.02, t1 - 0.12, 1000, { arms: false, step: 0.26 }); dad.face(t0, "neutral", 0);
    dad.arm("R", t0, -14, -4, 0.05); dad.arm("R", t1 - 0.2, -60, -50, 0.18);
    S.layer(PR.briefcase(0, 0), 0.9); const bc = S.q("pr"); S.key(bc, "--x", t0, -200, 0); S.key(bc, "--y", t0, 760, 0); S.key(bc, "--x", t0 + 0.02, 780, t1 - t0 - 0.14, "none");
    C.dust(S, { n: 18, seed: 31, box: [500, 200, 900, 560], color: "#fff4d0", depth: 1.0, op: 0.55 });
    S.layer(FG.desk(), 1.5); S.layer(FG.post(60), 1.6);
    grade(S, "office");
    light(S, 960, 720, 700, 420, "#ffd9a0", 0.28);
    lab(S, "dadLabel", "A LAWYER", 1400, 330, D.W("s2", 3), { size: 56, rot: -2 });
  } });

/* ================= 6 · court steps at dusk: the note about the trial, father large in foreground ================= */
D.shot({ id: "note", a: W("s2", 6), b: W("s3", 0), bg: B.court(), cam: { from: [-50, 0, 0.0], to: [40, -6, 0.2], ease: "power1.inOut" },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    C.fog(S, { y: 780, h: 240, color: "#a8b8e0", op: 0.3, seed: 8, depth: 0.5, drift: 140 });
    S.layer(C.rays(300, -20, 1.2, 1300, 0.26, "#bcd0ff", 0.26), 0.35);
    const dad = S.actor("dad2", DAD, 470, 1030, 1.5, { seed: 12, expr: "neutral", depth: 1.0 });
    S.layer(FX.note("trial", ["O. J. Simpson", "defense team", "trial: 1995"], 1330, 470, { w: 640, size: 74, rot: -4 }), 1.0);
    S.fadeIn("trial", t0 + 0.1, 0.2); S.wipe("trial", t0 + 0.2, 1.1);
    dad.turn(t0 + 0.2, -8, -4, 0.5); dad.look(t0 + 0.2, 10, -2, 0.4); dad.face(t0 + 0.4, "determined", 0.3); dad.arm("R", t0 + 0.5, -20, -90, 0.5);
    const tSt = D.W("s2", 10);
    S.layer(K.P("stamp", 1330, 745, `<g transform="rotate(-6)"><rect x="-250" y="-46" width="500" height="92" rx="10" fill="none" stroke="#c4252d" stroke-width="9"/><text y="22" text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="64" fill="#c4252d" letter-spacing="4">DEFENSE TEAM</text></g>`), 1.0);
    S.pop("stamp", tSt, 0.25);
    S.layer(FG.heads(3, 7, 1130), 1.5);
    grade(S, "court");
    light(S, 1330, 470, 560, 380, "#b8ccff", 0.4); light(S, 470, 800, 460, 420, "#cfdcff", 0.22);
  } });

/* ================= 7 · wide-medium: age nine, parents turn and leave (perspective hall) ================= */
D.vhs(D.W("s3", 0), "1989", { strength: 0.3, pre: 0.03, post: 0.12, bars: 1, year: 0.35 });
D.shot({ id: "divorce", a: W("s3", 0), b: E("s3", 6), bg: B.home(), cam: { from: [0, 0, 0.0], to: [0, 14, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(960, 420, Math.PI / 2, 700, 0.3, "#ffe0a8", 0.3), 0.4);
    C.fog(S, { y: 700, h: 200, color: "#ffc88a", op: 0.2, seed: 14, depth: 0.55, drift: 70 });
    const dadc = S.actor("dadL", DAD, 640, 790, 0.82, { seed: 21, idle: false, pivot: [640, 790], depth: 0.6 }), mom = S.actor("momR", MOM, 1280, 790, 0.82, { seed: 22, idle: false, pivot: [1280, 790], depth: 0.6 });
    S.layer(K.P("suit", 0, 0, PR.suitcase(0, 0)), 0.6); S.key("suit", "--x", t0, 700, 0); S.key("suit", "--y", t0, 790, 0);
    const kid = S.actor("kid", YOU("child"), 960, 1040, 1.6, { seed: 5, expr: "worried", depth: 1.0 });
    dadc.face(t0, "sad", 0); mom.face(t0, "sad", 0);
    const tn = D.W("s3", 3), tp = D.W("s3", 4);
    dadc.turn(tp, 10, 3, 0.3); dadc.walk(tp + 0.35, t1 - 0.02, -620, { arms: false }); S.key("suit", "--x", tp + 0.35, 700 - 620, t1 - tp - 0.37, "none");
    mom.turn(tp + 0.15, -10, -3, 0.3); mom.walk(tp + 0.5, t1 - 0.02, 640);
    [dadc, mom].forEach((a) => { a.k("self", "--s", tp + 0.35, 1, 0); a.k("self", "--s", tp + 0.35, 0.7, t1 - tp - 0.37, "none"); });
    kid.turn(t0 + 0.4, 10, 5, 0.4); kid.look(t0 + 0.4, -11, 0, 0.3); kid.turn(tp, -12, -6, 0.4); kid.look(tp, 11, 0, 0.3); kid.face(tp + 0.2, "sad", 0.4);
    kid.arm("L", tp, 28, 10, 0.4); kid.arm("R", tp + 0.3, -28, -10, 0.4);
    S.layer(`<g data-p="dim"><rect width="1920" height="1080" fill="#101830" opacity="0"/></g>`, 0); const dm = S.q("dim").firstElementChild; S.key(dm, "opacity", tp, 0, 0); S.key(dm, "opacity", tp, 0.3, t1 - tp, "sine.inOut");
    S.layer(FG.couch(), 1.5); S.layer(FG.post(1860), 1.6);
    grade(S, "home");
    light(S, 960, 800, 520, 420, "#ffc88a", 0.35);
    lab(S, "ageLabel", "AGE 9 · 1989", 960, 220, tn, { size: 64, rot: -3 });
  } });

/* ================= 8 · close-up: the child's face, tears ================= */
D.shot({ id: "kidCry", a: E("s3", 6), b: W("s4", 0), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kid") }] }, cam: { from: [0, 0, 0.02], to: [-8, 6, 0.16] },
  build(S) {
    const t0 = S.t0;
    const kid = closeUp(S, "kidc", YOU("child"), 960, 500, 600, { depth: 0.9, seed: 6 });
    kid.face(t0, "sad", 0); kid.look(t0, 0, 6, 0); kid.face(t0 + 0.4, "cry", 0.4); kid.nod(t0 + 0.5, 12, 0.5);
    C.dust(S, { n: 12, seed: 41, box: [200, 100, 1500, 800], color: "#ffd9a0", depth: 1.1, op: 0.4 });
    S.layer(FG.curtain("L"), 1.6);
    grade(S, "home", { dark: 0.2, vig: 0.8 });
    light(S, 960, 470, 520, 420, "#ffc88a", 0.38);
  } });

/* ================= 9 · wedding garden: path, hedges and flower arch converge; couple under the arch ================= */
D.vhs(D.W("s4", 0), "1991", { strength: 0.5, post: 0.22, year: 0.4 });
D.shot({ id: "wedding", a: W("s4", 0), b: W("s4", 5), bg: B.garden(), cam: { from: [30, 0, 0.0], to: [-20, -8, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(1500, -40, 1.95, 1300, 0.3, "#fff0c0", 0.3), 0.35);
    C.fog(S, { y: 640, h: 200, color: "#fff1d0", op: 0.3, seed: 15, depth: 0.5, drift: 80 });
    const mom = S.actor("mom", MOMW, 900, 640, 0.62, { seed: 31, depth: 0.6, pivot: [900, 640] }), br = S.actor("bruce", BRUCEW, 1030, 640, 0.64, { seed: 32, depth: 0.6, pivot: [1030, 640] });
    mom.face(t0 + 0.4, "happy", 0.3); br.face(t0 + 0.4, "happy", 0.3); mom.arm("R", t0 + 0.6, 34, 40, 0.3); br.arm("L", t0 + 0.6, -34, -40, 0.3);
    [mom, br].forEach((a, i) => { a.k("self", "--s", t0, 1, 0); a.k("self", "--s", t0, 1.55, t1 - t0, "power1.inOut"); a.k("self", "--y", t0, 0, 0); a.k("self", "--y", t0, 150, t1 - t0, "power1.inOut"); });
    const kid = S.actor("kid2", YOU("child"), 1560, 1040, 1.35, { seed: 33, expr: "surprised", depth: 1.0 });
    kid.look(t0, -9, -6, 0); kid.turn(t0 + 0.2, -10, -4, 0.4); kid.face(t0 + 0.9, "happy", 0.4); kid.arm("L", t0 + 0.9, -40, -60, 0.4);
    S.layer(PR.heart("hrt", 960, 330), 1.1); S.pop("hrt", t0 + 0.7, 0.5); S.key("hrt", "--y", t0 + 1.1, -40, 0.9, "sine.out");
    confetti(S, t0 + 0.6, 20, 4);
    S.layer(FG.leaves("L"), 1.7);
    grade(S, "garden");
    light(S, 960, 640, 600, 380, "#fff0c0", 0.3);
    lab(S, "wedLabel", "1991 · THE WEDDING", 960, 200, t0 + 0.15, { size: 58, rot: 2 });
  } });

/* ================= 10 · detail: the wedding rings ================= */
D.shot({ id: "rings", a: W("s4", 5), b: W("s4", 7), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("rings") }] }, cam: { from: [-20, 0, 0.0], to: [14, -6, 0.18] },
  build(S) {
    const t0 = S.t0, ring = (x, y, r, rot) => `<g transform="translate(${x} ${y}) rotate(${rot})"><ellipse rx="${r}" ry="${r * 0.62}" fill="none" stroke="${OLN}" stroke-width="64"/><ellipse rx="${r}" ry="${r * 0.62}" fill="none" stroke="#e8b83a" stroke-width="48"/><ellipse rx="${r}" ry="${r * 0.62}" fill="none" stroke="#fff0a8" stroke-width="12" stroke-dasharray="120 280" opacity=".9"/></g>`;
    S.layer(`<ellipse cx="960" cy="800" rx="720" ry="170" fill="#5a1a26" ${st(9)}/><ellipse cx="960" cy="770" rx="560" ry="110" fill="#7a2432"/>`, 0.8);
    S.layer(`<g data-p="rA">${ring(860, 640, 190, -12)}</g><g data-p="rB">${ring(1060, 640, 170, 10)}</g>`, 0.95);
    S.key("rA", "--x", t0, -240, 0); S.key("rA", "--x", t0, 0, 0.55, "back.out(1.3)"); S.key("rB", "--x", t0, 240, 0); S.key("rB", "--x", t0, 0, 0.55, "back.out(1.3)");
    S.layer(PR.sparkle("sp1", 1000, 520), 1.1); S.layer(PR.sparkle("sp2", 800, 600, "#fff"), 1.1);
    S.pop("sp1", t0 + 0.4, 0.3); S.pop("sp2", t0 + 0.55, 0.3); S.key("sp1", "--r", t0 + 0.4, 90, 0.5, "none");
    C.dust(S, { n: 14, seed: 51, box: [200, 100, 1500, 700], color: "#ffe9b0", depth: 1.3, op: 0.6 });
    grade(S, "garden", { dark: 0.24, vig: 0.84 });
    light(S, 960, 640, 560, 300, "#ffe9b0", 0.42);
    lab(S, "rngLabel", "MARRIED · 1991", 960, 230, t0 + 0.1, { size: 54, rot: 2 });
  } });

/* ================= 11 · tracking wide: 1976 Montreal, Bruce sprints through the tape ================= */
D.shot({ id: "medal", a: W("s4", 7), b: W("s5", 0), bg: B.stadium(), cam: { from: [-110, 0, 0.02], to: [160, 0, 0.14] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, tB = D.W("s4", 8) + 0.1, x0 = 160, xF = 1560;
    C.fog(S, { y: 640, h: 160, color: "#e8f0ff", op: 0.22, seed: 17, depth: 0.5, drift: 160 });
    S.layer(`<g>${[1490, 1630].map((x) => `<g transform="translate(${x} 950)"><rect x="-8" y="-300" width="16" height="300" fill="#f3ead2" ${st(5)}/><rect x="-30" y="-340" width="60" height="44" fill="#fff" ${st(5)}/><path d="M-30 -340h20v22h-20zM10 -340h20v22h-20zM-10 -318h20v22h-20z" fill="${OLN}"/></g>`).join("")}</g>`, 0.95);
    S.layer(`<g data-p="finish"><g transform="translate(1560 950)"><path d="M-70 -250H70" stroke="#d9453f" stroke-width="12" stroke-linecap="round"/><path d="M-70 -250H70" stroke="#fff" stroke-width="4" stroke-dasharray="14 14"/></g></g>`, 0.95);
    S.layer(`<g data-p="rib1"><g transform="translate(1530 700)"><path d="M0 0Q-30 10 -60 40" stroke="#d9453f" stroke-width="12" fill="none" stroke-linecap="round"/></g></g><g data-p="rib2"><g transform="translate(1590 700)"><path d="M0 0Q30 10 60 40" stroke="#d9453f" stroke-width="12" fill="none" stroke-linecap="round"/></g></g>`, 1.0);
    ["rib1", "rib2"].forEach((n) => (S.q(n).style.visibility = "hidden"));
    const run = S.actor("runner", Object.assign({}, BRUCE, { top: "#f6f2e8", pants: "#2e3a5a", accent: "#3a6aa8" }), x0, 960, 1.2, { depth: 0.95, seed: 88, idle: false });
    run.k("self", "--x", t0, 0, 0); run.face(t0, "determined", 0); run.walk(t0 + 0.02, tB, xF - x0, { step: 0.16, amp: 42 });
    S.hideAt("finish", tB); S.show("rib1", tB, true); S.show("rib2", tB, true);
    [["rib1", -70], ["rib2", 70]].forEach(([n, r]) => { S.key(n, "--r", tB, 0, 0); S.key(n, "--r", tB, r, 0.7, "power2.out"); S.key(n, "--y", tB, 0, 0); S.key(n, "--y", tB, 80, 0.7, "power1.in"); });
    run.move(tB, xF - x0 + 140, undefined, t1 - tB, "power3.out");
    run.arm("L", tB + 0.25, 150, 30, 0.3, "back.out(1.6)"); run.arm("R", tB + 0.25, -150, -30, 0.3, "back.out(1.6)"); run.face(tB, "laugh", 0.2); run.hop(tB + 0.1, 26, 0.35);
    S.layer(FX.note("gold", ["Olympic decathlon", "GOLD · 1976"], 1330, 200, { w: 520, size: 52, rot: 3 }), 0.4); S.fadeIn("gold", t0 + 0.2, 0.2); S.wipe("gold", t0 + 0.3, 0.8);
    S.layer(K.P("medal", 400, 520, PR.medal(0, 0)), 1.0); S.pop("medal", tB + 0.15, 0.4);
    S.layer(PR.sparkle("sp1", 1500, 520), 1.1); S.layer(PR.sparkle("sp2", 1680, 640, "#fff"), 1.1);
    ["sp1", "sp2"].forEach((n, i) => { S.pop(n, tB + 0.05 + i * 0.12, 0.3); S.key(n, "--r", tB + 0.05 + i * 0.12, 90, 0.9, "none"); });
    S.layer(FG.heads(7, 9, 1130), 1.55);
    grade(S, "stadium");
    light(S, 900, 900, 760, 300, "#fff2c0", 0.3); light(S, 1500, 560, 520, 380, "#fff3b0", 0.3);
  } });

/* ================= 12 · close-up: adult Kim, 2007 ================= */
D.vhs(D.W("s5", 0), "2007", { strength: 0.5, post: 0.22, year: 0.4 });
D.shot({ id: "kim07", a: W("s5", 0), b: W("s5", 2), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kim07") }] }, cam: { from: [0, 0, 0.02], to: [0, 0, 0.16] },
  build(S) {
    const t0 = S.t0;
    S.layer(C.rays(1750, -40, 2.05, 1200, 0.3, "#fff1c4", 0.34), 0.4);
    const kim = closeUp(S, "kim07", YOU("w2007"), 960, 520, 560, { depth: 0.9, seed: 41, expr: "neutral" });
    kim.look(t0, 10, 0, 0); kim.look(t0 + 0.7, -4, 0, 0.4, "sine.inOut"); kim.turn(t0 + 0.2, -3, -3, 0.5); kim.face(t0 + 0.9, "smirk", 0.35);
    S.layer(`<g data-p="flash"><rect width="1920" height="1080" fill="#fff" opacity="0"/></g>`, 0); const fl = S.q("flash").firstElementChild;
    [0.45].forEach((d) => { S.key(fl, "opacity", t0 + d, 0, 0); S.key(fl, "opacity", t0 + d, 0.5, 0.03); S.key(fl, "opacity", t0 + d + 0.03, 0, 0.14); });
    C.dust(S, { n: 14, seed: 61, box: [200, 100, 1500, 800], color: "#fff1c4", depth: 1.1, op: 0.4 });
    S.layer(FG.curtain("R"), 1.6);
    grade(S, "studio", { tint: "#d2a8d8", ta: 0.28 });
    light(S, 940, 500, 520, 430, "#ffe2c0", 0.42);
  } });

/* ================= 13 · wide: living room, the crew arrives; camera body huge in the foreground ================= */
D.shot({ id: "crew", a: W("s5", 2), b: W("s5", 6), bg: B.living(), cam: { from: [60, 0, 0.0], to: [-30, 0, 0.18] },
  build(S) {
    const t0 = S.t0, t1 = S.t1;
    S.layer(C.rays(1160, 340, Math.PI / 2 + 0.2, 800, 0.4, "#fff1c4", 0.34), 0.45);
    C.fog(S, { y: 700, h: 200, color: "#fff1d0", op: 0.18, seed: 19, depth: 0.55, drift: 80 });
    const you = S.actor("kimL", YOU("w2007"), 640, 880, 0.95, { seed: 41, expr: "neutral", pivot: [640, 880] });
    const crew = S.actor("crew", CREW, 1500, 780, 0.75, { seed: 42, idle: false, pivot: [1500, 780], depth: 0.7 });
    crew.k("self", "--x", t0, 520, 0); crew.walk(t0 + 0.05, t1 - 0.05, -900, { arms: false, step: 0.28 }); crew.face(t0, "neutral", 0);
    crew.k("self", "--s", t0, 0.8, 0); crew.k("self", "--s", t0 + 0.05, 1.3, t1 - t0 - 0.1, "power1.in"); crew.k("self", "--y", t0 + 0.05, 120, t1 - t0 - 0.1, "power1.in");
    crew.arm("R", t0 + 0.05, -95, -105, 0.2); crew.arm("L", t0 + 0.05, 70, 70, 0.2);
    you.turn(t0 + 0.15, -10, -4, 0.4); you.look(t0 + 0.15, 12, 0, 0.3); you.face(t0 + 0.3, "surprised", 0.3); you.arm("L", t0 + 0.5, 70, 40, 0.4, "back.out(1.3)");
    S.layer(`<g data-p="fcam">${FG.cam()}</g>`, 1.55); S.key("fcam", "--x", t0, 600, 0); S.key("fcam", "--x", t0, 0, 0.7, "power3.out");
    S.layer(`<circle id="recdot" cx="1780" cy="110" r="18" fill="#e22"/><text x="1740" y="122" text-anchor="end" font-family='${FX.FONT}' font-weight="800" font-size="40" fill="#fff" stroke="#000" stroke-width="2">REC</text>`, 0);
    const rd = S.el.querySelector("#recdot"); for (let t = t0; t < t1; t += 0.4) S.key(rd, "opacity", t, Math.round((t - t0) / 0.4) % 2 ? 0.15 : 1, 0);
    grade(S, "glam", { tint: "#d0a070", ta: 0.3 });
    light(S, 640, 780, 520, 420, "#ffe2c0", 0.34);
    lab(S, "crewLabel", "CAMERAS MOVE IN", 800, 220, t0 + 0.12, { size: 56, rot: -3 });
  } });

/* ================= 14 · detail: lens + REC light; the family shows up in its reflection ================= */
D.shot({ id: "lens", a: W("s5", 6), b: W("s5", 10), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("lens") }] }, cam: { from: [0, 0, 0.0], to: [0, 0, 0.2] },
  build(S) {
    const t0 = S.t0, tf = D.W("s5", 7);
    const ring = (r, f, w) => `<circle cx="960" cy="540" r="${r}" fill="${f}" stroke="${OLN}" stroke-width="${w || 8}"/>`;
    S.layer(ring(430, "#14141c", 14) + ring(360, "#22222e") + ring(300, "#0c0c12") + ring(240, "#122038") + ring(170, "#1d3a64") + ring(95, "#08121f", 6) +
      `<path d="M960 120A420 420 0 0 1 1360 360" stroke="#8a8aa0" stroke-width="10" fill="none" opacity=".5"/>` +
      `<g data-p="refl"><ellipse cx="900" cy="470" rx="70" ry="38" fill="#fff" opacity=".42" transform="rotate(-28 900 470)"/><circle cx="1040" cy="610" r="22" fill="#fff" opacity=".28"/></g>` +
      `<g data-p="fam" opacity=".0">${[[860, 590, 0.9], [960, 570, 1.1], [1060, 598, 0.8]].map(([x, y, s]) => `<g transform="translate(${x} ${y}) scale(${s})"><circle r="18" fill="#ffd9b0"/><path d="M-26 70C-22 24 -10 18 0 18S22 24 26 70Z" fill="#ffd9b0"/></g>`).join("")}</g>`, 0.9);
    S.key("refl", "--x", t0, -40, 0); S.key("refl", "--x", t0, 50, S.dur, "none");
    S.fadeIn("fam", tf, 0.3); S.q("fam").setAttribute("opacity", "1");
    S.layer(`<g fill="none" stroke="#fff" stroke-width="7" opacity=".85"><path d="M140 160H260M140 160V280M1780 160H1660M1780 160V280M140 920H260M140 920V800M1780 920H1660M1780 920V800"/></g><circle id="rec2" cx="260" cy="250" r="17" fill="#e22"/><text x="292" y="262" font-family='${FX.FONT}' font-weight="800" font-size="40" fill="#fff" stroke="#000" stroke-width="2">REC</text><text x="1780" y="262" text-anchor="end" font-family='${FX.FONT}' font-weight="700" font-size="34" fill="#fff" opacity=".85">2007 · 00:00:21</text>`, 0.1);
    const rd = S.el.querySelector("#rec2"); for (let t = t0; t < S.t1; t += 0.35) S.key(rd, "opacity", t, Math.round((t - t0) / 0.35) % 2 ? 0.15 : 1, 0);
    grade(S, "mono", { tint: "#7088b0", ta: 0.2, dark: 0.1 });
    light(S, 960, 540, 520, 420, "#6a98e0", 0.28);
    lab(S, "famLabel", "YOUR FAMILY", 1400, 330, tf, { size: 54, rot: 2 });
  } });

/* ================= 15 · wide: reality-TV stage (truss, converging stage lines, audience silhouettes) ================= */
D.shot({ id: "onair", a: W("s5", 10), b: W("s6", 0), bg: B.stage(), cam: { from: [0, 0, 0.16], to: [0, -6, 0.02], ease: "power2.out" },
  build(S) {
    const t0 = S.t0;
    S.layer(PR.spot(300, 330, 10), 0.8); S.layer(PR.spot(1620, 330, 170), 0.8);
    S.layer(FX.cone(330, 330, 700, 900, 1220, 900, 370, 340, "#ffd9f0", 0.38), 0.7); S.layer(FX.cone(1590, 330, 1220, 900, 700, 900, 1550, 340, "#ffd9f0", 0.34), 0.7);
    C.fog(S, { y: 760, h: 240, color: "#c08ae8", op: 0.28, seed: 23, depth: 0.55, drift: 120 });
    const you = S.actor("kimT", YOU("w2007"), 960, 930, 1.12, { seed: 51, expr: "smirk", pivot: [960, 930] });
    you.arm("R", t0 + 0.25, -150, -20, 0.35, "back.out(1.5)"); you.face(t0 + 0.3, "laugh", 0.3);
    for (let t = t0 + 0.6, i = 0; t < S.t1 - 0.15; t += 0.28, i++) you.arm("R", t, i % 2 ? -150 : -120, i % 2 ? -20 : -55, 0.28, "sine.inOut");
    S.layer(FG.heads(5, 8, 1150), 1.45); S.layer(`<g transform="translate(1500 700) scale(1.6)">${FG.cam()}</g>`, 1.6);
    grade(S, "studio");
    light(S, 960, 760, 520, 380, "#ffe0f6", 0.34);
    lab(S, "tvLabel", "REALITY TV", 960, 210, D.W("s5", 10), { size: 68, rot: 2 });
  } });

/* ================= 16 · close-up: adult Kim, 2025 ================= */
D.vhs(D.W("s6", 0), "2025", { strength: 0.5, post: 0.22, year: 0.4 });
D.shot({ id: "kim25", a: W("s6", 0), b: W("s6", 2), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("kim25") }] }, cam: { from: [0, 0, 0.16], to: [0, 0, 0.03], ease: "power2.out" },
  build(S) {
    const t0 = S.t0;
    S.layer(C.rays(1700, -40, 2.0, 1200, 0.3, "#ffe2c0", 0.36), 0.4);
    const kim = closeUp(S, "kim25", YOU("w2025"), 960, 520, 560, { depth: 0.9, seed: 61, expr: "neutral" });
    kim.face(t0 + 0.25, "happy", 0.4); kim.look(t0, -8, 0, 0); kim.look(t0 + 0.5, 4, 0, 0.5, "sine.inOut"); kim.turn(t0 + 0.3, 3, 3, 0.6);
    C.dust(S, { n: 16, seed: 71, box: [200, 100, 1500, 800], color: "#fff1d0", depth: 1.1, op: 0.45 });
    S.layer(FG.curtain("L"), 1.6);
    grade(S, "glam");
    light(S, 940, 500, 520, 430, "#ffe9d0", 0.42);
  } });

/* ================= 17 · detail: fabric and tag ================= */
D.shot({ id: "skimsTag", a: W("s6", 2), b: W("s6", 5), bg: { layers: [{ name: "b", depth: 0.2, svg: B.closeBack("skims") }] }, cam: { from: [-30, 0, 0.0], to: [30, 0, 0.14] },
  build(S) {
    const t0 = S.t0, fold = (y, c, a) => `<path d="M-80 ${y}C400 ${y - 120} 900 ${y + 110} 1300 ${y - 40}S1800 ${y - 60} 2000 ${y + 30}V${y + 260}C1700 ${y + 190} 1300 ${y + 300} 900 ${y + 210}S300 ${y + 170} -80 ${y + 300}Z" fill="${c}" opacity="${a}"/>`;
    S.layer(`<rect x="-80" y="-80" width="2080" height="1240" fill="#cdb9a6"/>${fold(120, "#d8c4b0", 1)}${fold(330, "#c6ad98", 1)}${fold(560, "#d4bea8", 1)}${fold(780, "#bfa58f", 1)}<path d="M-80 400C500 330 1100 480 2000 380" stroke="#fff" stroke-width="22" opacity=".18" fill="none"/>`, 0.8);
    S.layer(`<g data-p="tagg"><g transform="translate(980 520) rotate(-5)"><rect x="-300" y="-110" width="600" height="220" rx="12" fill="#f4ecdf" ${st(8)}/><rect x="-278" y="-88" width="556" height="176" fill="none" stroke="#b79a82" stroke-width="3"/><text y="34" text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="104" fill="#2a1820" letter-spacing="12">SKIMS</text><circle cx="-262" cy="-92" r="10" fill="#cdb9a6" ${st(4)}/></g></g>`, 1.0);
    S.pop("tagg", D.W("s6", 4) - 0.15, 0.4); S.key("tagg", "--r", D.W("s6", 4) + 0.3, 2, 0.8, "sine.inOut");
    C.dust(S, { n: 12, seed: 81, box: [200, 100, 1500, 800], color: "#fff", depth: 1.2, op: 0.4 });
    grade(S, "glam", { tint: "#d8b8a0", ta: 0.24, dark: 0.12 });
    light(S, 960, 520, 700, 360, "#fff4e4", 0.4);
    lab(S, "brandLabel", "YOUR BRAND", 520, 250, D.W("s6", 3), { size: 54, rot: -3 });
  } });

/* ================= 18 · boutique wide + value card: $0.5B -> $5B lands on "billion" ================= */
D.shot({ id: "skims", a: W("s6", 5), b: "end", bg: B.boutique(), cam: { from: [0, 14, 0.0], to: [0, -8, 0.2] },
  build(S) {
    const t0 = S.t0, t1 = S.t1, tb = D.W("s6", 9);
    S.layer(C.rays(960, 300, Math.PI / 2, 800, 0.36, "#fff4e4", 0.26), 0.45);
    const you = S.actor("kimS", YOU("w2025"), 560, 900, 1.15, { seed: 61, expr: "happy", pivot: [560, 900] });
    you.arm("L", t0 + 0.4, 150, 20, 0.5, "back.out(1.6)"); you.arm("R", t0 + 0.4, -150, -20, 0.5, "back.out(1.6)"); you.talkWords("s6", t0);
    you.hop(tb - 0.2, 30, 0.4); you.face(tb - 0.2, "laugh", 0.3);
    for (let t = tb + 0.5, i = 0; t < t1 - 1.0; t += 0.7, i++) { you.hop(t, 20 + (i % 2) * 8, 0.38); you.arm("L", t + 0.4, i % 2 ? 150 : 120, i % 2 ? 20 : 50, 0.35, "sine.inOut"); you.arm("R", t + 0.4, i % 2 ? -120 : -150, i % 2 ? -50 : -20, 0.35, "sine.inOut"); }
    S.layer(`<g data-p="vcard"><g transform="translate(1500 540)"><rect x="-290" y="-130" width="580" height="260" rx="26" fill="#fffaf0" ${st(8)}/><rect x="-270" y="-110" width="540" height="220" rx="16" fill="none" stroke="#c9a24a" stroke-width="4" stroke-dasharray="14 10"/></g></g>`, 1.1);
    S.pop("vcard", t0 + 0.15, 0.4);
    const vals = ["$0.5B", "$1B", "$2B", "$3B", "$4B", "$5B"], x = 1500, y = 580, tc = tb - 6 * 0.2;
    S.layer(vals.map((v, i) => `<g data-p="v${i}" style="visibility:hidden"><g transform="translate(${x} ${y})"><text text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="170" fill="#c98a12" stroke="${OLN}" stroke-width="8" paint-order="stroke">${v}</text></g></g>`).join(""), 1.1);
    vals.forEach((v, i) => { const t = tc + i * 0.2; S.show("v" + i, t, true); if (i < vals.length - 1) S.hideAt("v" + i, t + 0.2); S.key("v" + i, "--s", t, 0.8, 0); S.key("v" + i, "--s", t, 1, 0.18, "back.out(2)"); });
    for (let i = 0; i < 5; i++) { S.layer(PR.coin("c" + i, 1260 + i * 110, 800), 1.2); S.pop("c" + i, tb + 0.1 + i * 0.1, 0.35); S.key("c" + i, "--y", tb + 0.4 + i * 0.1, -30 - (i % 2) * 24, 0.7, "sine.out"); }
    confetti(S, tb, 30, 9);
    S.layer(FG.post(1870), 1.6); S.layer(FG.leaves("L"), 1.7);
    grade(S, "glam");
    light(S, 560, 760, 520, 420, "#fff1d8", 0.34); light(S, 1500, 560, 520, 340, "#fff0b0", 0.3);
    lab(S, "skLabel", "BRAND VALUE · 2025", 1420, 280, t0 + 0.2, { size: 52, rot: -2 });
    S.layer(`<g data-p="fadeout"><rect width="1920" height="1080" fill="#000" opacity="1"/></g>`, 0);
    const fo = S.q("fadeout").firstElementChild; fo.style.opacity = "0"; S.key(fo, "opacity", t1 - 0.6, 0, 0); S.key(fo, "opacity", t1 - 0.6, 1, 0.58, "power1.in");
  } });
