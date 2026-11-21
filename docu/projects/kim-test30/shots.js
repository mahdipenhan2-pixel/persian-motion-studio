/* Shots for the 30-second style test. Runs inside base.html with D (director), K (kit), DATA. */
/* Kim, one identity (jet-black hair, strong brows, brown eyes, warm tan skin) with real age stages */
const KIM = { skin: "#d99a73", hairColor: "#1c1210", eyeColor: "#5a3320", accent: "#e4483f" };
const YOU = (stage, extra) => Object.assign({}, KIM, ({
  baby:  { build: "baby",  hair: "baby_tuft",  outfit: "babygrow", top: "#f6e7a8", pants: "#f6e7a8", shoe: "#f6e7a8", legs: "pants", sleeve: "none" },
  child: { build: "child", hair: "child_pony", outfit: "sweat80s", top: "#f2a7b8", pants: "#6a7ec2", shoe: "#f2efe8" },
  teen:  { build: "teen",  hair: "teen_long",  outfit: "crop",     top: "#efe0cc", pants: "#4a6aa0", shoe: "#f2efe8", earrings: 1, sleeve: "short" },
  w2007: { build: "woman", hair: "long_straight", outfit: "tee2007", top: "#2b2b33", pants: "#3b5a8a", shoe: "#2b2230", earrings: 1, sleeve: "short" },
  w2025: { build: "woman", hair: "long_straight", outfit: "dress", top: "#b89b86", legs: "bare", shoe: "#c9a58a", shoeType: "pump", sleeve: "none", earrings: 1, lip: "#c4666b" },
})[stage], extra || {});
const DAD = { build: "man", skin: "#e8b896", hair: "short_man", hairColor: "#4a3426", top: "#2f3a4f", pants: "#262b3a", outfit: "suit", glasses: 1, accent: "#a63a3a" };
const MOM = { build: "woman", skin: "#e5ae88", hair: "big80s", hairColor: "#241713", top: "#b4434a", pants: "#2b2230", outfit: "blazer", accent: "#f3c64a", earrings: 1, lip: "#b23a4a", sleeve: "long" };
const BRUCE = { build: "man", skin: "#e9b996", hair: "slick", hairColor: "#6a4a2e", top: "#3a6aa8", pants: "#2e3a5a", outfit: "track", accent: "#f6f2e8", shoe: "#f6f2e8" };
const CREW = { build: "man", skin: "#c98f6a", hair: "short_man", hairColor: "#1f1512", top: "#35353f", pants: "#22222a", outfit: "track", accent: "#6a6a78" };
const NURSE = { build: "woman", skin: "#e9c0a0", hair: "bob", hairColor: "#5a3a26", top: "#e9f3f2", legs: "bare", outfit: "dress", shoe: "#f2efe8", sleeve: "none" };
const FX = K.fx, PR = FX.props;
const lab = (S, id, text, x, y, t, o) => { S.layer(FX.label(id, text, x, y, o), 1.15); S.pop(id, t, 0.38); };
const FLOOR = 815;
const mix = (a, b) => K.mixc ? K.mixc(a, b, 0.5) : a;

/* ---------- small local props ---------- */
const palm = (x, flip) => `<g transform="translate(${x} 1120) scale(${flip ? -1 : 1} 1)">
  <path d="M0 0C20 -260 -20 -520 30 -760" stroke="#2a1a18" stroke-width="46" fill="none" stroke-linecap="round"/>
  <path d="M0 0C20 -260 -20 -520 30 -760" stroke="#4a3228" stroke-width="30" fill="none" stroke-linecap="round"/>
  <g transform="translate(30 -760)">${[-70, -35, 0, 35, 70, 105, -105].map((a, i) => `<path d="M0 0C${60} -40 ${150} -20 ${210} 50C${130} 0 ${50} -10 0 0Z" transform="rotate(${a - 30})" fill="${i % 2 ? "#1e4a3a" : "#26604a"}" stroke="#101c18" stroke-width="5"/>`).join("")}</g></g>`;
const car = (c) => `<g><path d="M-120 0V-46Q-110 -60 -60 -62L-30 -100H60L96 -62Q126 -58 126 -40V0Z" fill="${c}" stroke="#2a1820" stroke-width="6" stroke-linejoin="round"/>
  <path d="M-24 -92L-48 -62H30V-92Z M44 -92V-62H88L62 -92Z" fill="#cfe7ee" stroke="#2a1820" stroke-width="4"/>
  ${[-70, 70].map((x) => K.P("wh" + (x < 0 ? "A" : "B"), x, 4, `<circle r="26" fill="#222" stroke="#000" stroke-width="4"/><circle r="10" fill="#bbb"/><path d="M-26 0H26M0 -26V26" stroke="#888" stroke-width="3"/>`)).join("")}</g>`;
const mobile = (x, y) => `<g transform="translate(${x} ${y})"><path d="M0 -400V-140" stroke="#2a1820" stroke-width="5"/>
  ${[[-110, 0, "#e4483f"], [0, 40, "#f3c64a"], [110, 0, "#4c8a5a"]].map(([dx, dy, c], i) => `<g transform="translate(0 -140)"><path d="M0 0L${dx} ${dy + 70}" stroke="#2a1820" stroke-width="3"/>
    <g data-p="mob${i}" transform="translate(${dx} ${dy + 70})"><circle r="26" fill="${c}" stroke="#2a1820" stroke-width="5"/><path d="M-9 -9Q0 -20 9 -9" stroke="#fff" stroke-width="4" fill="none" opacity=".6"/></g></g>`).join("")}</g>`;
const confetti = (S, t0, n, seed) => { const r = K.rng(seed); const cols = ["#f3c64a", "#e4483f", "#4c8a5a", "#3d6a9c", "#fff"];
  let m = ""; for (let i = 0; i < n; i++) m += `<g transform="translate(${Math.round(160 + r() * 1600)} -40)"><g data-p="cf${i}"><rect x="-9" y="-5" width="18" height="10" fill="${cols[i % 5]}" stroke="#2a1820" stroke-width="2"/></g></g>`;
  S.layer(m, 1.2);
  for (let i = 0; i < n; i++) { const e = S.q("cf" + i), d = 2.2 + r() * 1.6, st = t0 + r() * 1.2;
    S.key(e, "--y", st, 0, 0); S.key(e, "--y", st, 1180, d, "none"); S.key(e, "--x", st, 0, 0); S.key(e, "--x", st, (r() - 0.5) * 260, d, "sine.inOut"); S.key(e, "--r", st, 0, 0); S.key(e, "--r", st, (r() - 0.5) * 900, d, "none"); } };

/* ===================== SHOT 1: Los Angeles, sunset (title + establishing) ===================== */
D.shot({ id: "la", a: 0, b: [ "s1", 0.42 ], bg: K.bg.laStreet({ sky1: "#ff7a4a", sky2: "#ffd08a", bld: "#4a3552", bld2: "#6e4a63", road: "#3a3340" }),
  cam: { from: [-70, 0, 0.16], to: [190, -20, 0.34] },
  build(S) {
    S.layer(palm(-30, false), 1.5); S.layer(palm(1880, true), 1.55);
    S.layer(`<g transform="translate(0 868)"><g data-p="car1" ><g>${car("#c4453f")}</g></g></g>`, 0.9);
    S.key("car1", "--x", S.t0, -300, 0); S.key("car1", "--x", S.t0, 2300, S.dur * 1.25, "none");
    ["whA", "whB"].forEach((n) => { S.key(n, "--r", S.t0, 0, 0); S.key(n, "--r", S.t0, 1440, S.dur * 1.25, "none"); });
    // nurse carries newborn Kim out of the hospital: both big and clear in frame
    const nurse = S.actor("nurse", NURSE, 300, 900, 1.0, { depth: 0.9, seed: 77, idle: false }); nurse.face(S.t0, "happy", 0);
    const bw = S.t1 - S.t0 - 0.2;
    nurse.walk(S.t0 + 0.1, S.t0 + 0.1 + bw, 760, { arms: false, step: 0.34, amp: 16 });
    nurse.arm("L", S.t0, -48, -78, 0.01); nurse.arm("R", S.t0, 48, 78, 0.01);
    const kimB = S.actor("kimBaby", YOU("baby"), 330, 648, 0.95, { depth: 0.9, seed: 5, idle: false });
    kimB.k("self", "--x", S.t0 + 0.1, 760, bw, "none"); kimB.face(S.t0, "happy", 0); kimB.look(S.t0, 0, -4, 0);
    S.layer(`<g data-p="bundle"><g transform="translate(330 676)"><path d="M-88 -46Q0 -86 88 -46L102 40Q0 74 -102 40Z" fill="#fbf6ea" stroke="#2a1820" stroke-width="6" stroke-linejoin="round"/><path d="M-70 -20Q0 -46 70 -20M-80 8Q0 -18 80 8" stroke="#f2a7b8" stroke-width="7" fill="none" stroke-linecap="round"/></g></g>`, 0.9);
    S.key("bundle", "--x", S.t0 + 0.1, 0, 0); S.key("bundle", "--x", S.t0 + 0.1, 760, bw, "none");
    S.layer(FX.glow(1450, 560, 700, 420, "#ffd7a0", 0.55), 0.1);
    // title card (pops in, holds, leaves)
    S.layer(`<g data-p="title"><g transform="translate(960 190)"><rect x="-640" y="-58" width="1280" height="116" rx="18" fill="#fff" stroke="#2a1820" stroke-width="7"/>
      <text x="0" y="18" text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="50" fill="#2a1820">WHAT IF YOU WERE BORN AS KIM KARDASHIAN?</text></g></g>`, 0.1);
    S.pop("title", S.t0 + 0.25, 0.45); S.key("title", "opacity", S.t0 + 1.9, 0, 0.3, "power1.in");
    lab(S, "laLabel", "LOS ANGELES · 1980", 1380, 560, S.t0 + 1.35, { size: 52, rot: 3 });
  }, grade: ["#ffb27a", 0.28] });

/* ===================== SHOT 2: the nursery - baby "you" in the crib ===================== */
D.vhs(D.T("s1", 0.42), "1980");
D.shot({ id: "crib", a: ["s1", 0.42], b: ["s2", 0.0], bg: K.bg.nursery(),
  cam: { from: [40, 20, 0.1], to: [-30, -10, 0.22] },
  build(S) {
    S.layer(mobile(1000, 330), 0.75);
    S.layer(PR.crib(960, 900), 0.9);
    const baby = S.actor("baby", YOU("baby"), 960, 892, 1.85, { depth: 0.9, seed: 4 });
    S.layer(PR.blanket(960, 905), 0.9);
    // mobile swings; baby follows it with her eyes and reaches up
    const sw = (n, dt) => { for (let i = 0, t = S.t0; t < S.t1; i++, t += 0.9) { S.key("mob" + n, "--r", t + dt, (i % 2 ? 14 : -14), 0.9, "sine.inOut"); } };
    [0, 1, 2].forEach((i) => { try { sw(i, i * 0.15); } catch (e) {} });
    baby.face(S.t0, "neutral", 0); baby.look(S.t0, -9, -8, 0); baby.look(S.t0 + 0.7, 9, -8, 0.8, "sine.inOut"); baby.look(S.t0 + 1.5, 0, 0, 0.4);
    baby.turn(S.t0 + 0.4, -6, -4, 0.6); baby.turn(S.t0 + 1.3, 5, 4, 0.7);
    baby.arm("R", S.t0 + 0.6, -150, -20, 0.5, "back.out(1.4)"); baby.arm("R", S.t0 + 1.3, -120, -40, 0.4); baby.arm("L", S.t0 + 0.9, 140, 30, 0.5, "back.out(1.4)");
    baby.face(S.t0 + 1.0, "happy", 0.3);
    lab(S, "bornLabel", "OCT 21, 1980", 1480, 330, S.t0 + 0.5, { size: 54, rot: 3 });
    S.layer(FX.glow(960, 500, 760, 420, "#ffe2b0", 0.45), 0.4);
  }, grade: ["#ffd9a8", 0.22] });

/* ===================== SHOT 3: father walks into his office ===================== */
D.vhs(D.T("s2", 0.0));
D.shot({ id: "dadOffice", a: ["s2", 0.0], b: ["s2", 0.58], bg: K.bg.lawOffice(),
  cam: { from: [-90, 0, 0.06], to: [60, -10, 0.16] },
  build(S) {
    S.layer(PR.desk(1000, 880, 560), 0.92); S.layer(PR.scales(1450, 790), 0.8);
    const dad = S.actor("dad", DAD, 520, FLOOR, 1.12, { seed: 9 });
    dad.k("self", "--x", S.t0, -800, 0); dad.walk(S.t0 + 0.05, S.t0 + 1.35, 900, { arms: false });
    dad.face(S.t0, "neutral", 0);
    S.layer(PR.briefcase(0, 0), 0.9); const bc = S.q("pr");
    S.key(bc, "--x", S.t0, -185, 0); S.key(bc, "--y", S.t0, 690, 0); S.key(bc, "--x", S.t0 + 0.05, 715, 1.3, "none");
    dad.arm("R", S.t0 + 0.0, -14, -4, 0.05);
    dad.arm("R", S.t0 + 1.4, -72, -64, 0.35);
    S.key(bc, "--x", S.t0 + 1.4, 830, 0.35, "power2.out"); S.key(bc, "--y", S.t0 + 1.4, 715, 0.35, "power2.in");
    dad.arm("R", S.t0 + 1.85, -6, -6, 0.4); dad.nod(S.t0 + 1.9, 10, 0.5); dad.face(S.t0 + 1.9, "smirk", 0.3);
    lab(S, "dadLabel", "YOUR FATHER · LAWYER", 1300, 340, S.t0 + 1.1, { size: 46, rot: -2 });
  }, grade: ["#9fb8dd", 0.25] });

/* ===================== SHOT 4: handwritten note about the trial ===================== */
D.shot({ id: "note", a: ["s2", 0.58], b: ["s3", 0.0], bg: K.bg.courthouse(),
  cam: { from: [20, 0, 0.0], to: [-20, 0, 0.1] },
  build(S) {
    const dad = S.actor("dad2", DAD, 440, FLOOR + 40, 1.25, { seed: 12, expr: "neutral" });
    S.layer(FX.note("trial", ["O. J. Simpson", "defense team", "trial: 1995"], 1260, 450, { w: 620, size: 74, rot: -4 }), 1.0);
    S.fadeIn("trial", S.t0 + 0.2, 0.2); S.wipe("trial", S.t0 + 0.35, 1.0);
    dad.turn(S.t0 + 0.2, -8, -4, 0.5); dad.look(S.t0 + 0.2, 10, -2, 0.4); dad.face(S.t0 + 0.4, "determined", 0.3);
    dad.arm("R", S.t0 + 0.5, -20, -90, 0.5);
    S.layer(FX.glow(1260, 450, 520, 360, "#9fc0ff", 0.4), 0.9);
  }, grade: ["#8aa0d8", 0.18] });

/* ===================== SHOT 5: age nine, the parents leave ===================== */
D.vhs(D.T("s3", 0.0), "1989", { strength: 0.3, pre: 0.03, post: 0.12, bars: 1, year: 0.35 });
D.shot({ id: "divorce", a: ["s3", 0.0], b: ["s4", 0.0], bg: K.bg.home80s(),
  cam: { from: [0, 0, 0.06], to: [0, 20, 0.2] },
  build(S) {
    const kid = S.actor("kid", YOU("child"), 960, FLOOR + 20, 1.32, { seed: 5, expr: "worried" });
    const dad = S.actor("dadL", DAD, 560, FLOOR, 1.05, { seed: 21, idle: false });
    const mom = S.actor("momR", MOM, 1360, FLOOR, 1.05, { seed: 22, idle: false });
    S.layer(K.P("suit", 0, 0, PR.suitcase(0, 0)), 0.9);
    S.key("suit", "--x", S.t0, 650, 0); S.key("suit", "--y", S.t0, 880, 0); S.key("suit", "--x", S.t0 + 0.9, 650 - 700, S.t1 - 0.95 - S.t0, "none");
    lab(S, "ageLabel", "AGE 9 · 1989", 960, 250, S.t0 + 0.3, { size: 64, rot: -3 });
    // parents turn away and walk off; kid's head follows each of them, expression sinks
    dad.face(S.t0, "sad", 0); mom.face(S.t0, "sad", 0);
    dad.turn(S.t0 + 0.5, 10, 3, 0.3); dad.walk(S.t0 + 0.9, S.t1 - 0.05, -700, { arms: false }); dad.arm('R', S.t0 + 0.9, -12, -4, 0.2); dad.arm('L', S.t0 + 0.9, 20, 20, 0.2);
    mom.turn(S.t0 + 0.7, -10, -3, 0.3); mom.walk(S.t0 + 1.0, S.t1 - 0.05, 700);
    kid.turn(S.t0 + 0.5, 12, 6, 0.4); kid.look(S.t0 + 0.5, -11, 0, 0.3);
    kid.turn(S.t0 + 1.2, -12, -6, 0.4); kid.look(S.t0 + 1.2, 11, 0, 0.3);
    kid.turn(S.t0 + 1.9, 0, 0, 0.4); kid.look(S.t0 + 1.9, 0, 6, 0.4);
    kid.face(S.t0 + 1.3, "sad", 0.5); kid.arm("L", S.t0 + 0.5, 28, 10, 0.4); kid.arm("R", S.t0 + 1.2, -28, -10, 0.4);
    // dim the light while they go
    S.layer(`<g data-p="dim"><rect width="1920" height="1080" fill="#101830" opacity="0"/></g>`, 0);
    const dm = S.q("dim").firstElementChild; S.key(dm, "opacity", S.t0 + 0.8, 0, 0); S.key(dm, "opacity", S.t0 + 0.8, 0.28, S.dur - 1.0, "sine.inOut");
    S.layer(FX.cone(1500, 0, 1920, 0, 1920, 900, 1100, 900, "#ffd9a0", 0.25), 0.6);
  } });

/* ===================== SHOT 6: 1991 wedding in the garden (mother marries Bruce) ===================== */
const MOMW = Object.assign({}, MOM, { outfit: "dress", top: "#f6f1e8", legs: "bare", shoe: "#f6f1e8", shoeType: "pump", sleeve: "none", lip: "#b23a4a" });
const BRUCEW = Object.assign({}, BRUCE, { outfit: "suit", top: "#2b2f3d", pants: "#2b2f3d", accent: "#c43b3b", shoe: "#1a1a22" });
D.vhs(D.T("s4", 0.0), "1991");
D.shot({ id: "wedding", a: ["s4", 0.0], b: ["s4", 0.62], bg: K.bg.weddingYard(),
  cam: { from: [50, 0, 0.06], to: [-30, -10, 0.17] },
  build(S) {
    const mom = S.actor("mom", MOMW, 850, FLOOR, 1.08, { seed: 31 });
    const br = S.actor("bruce", BRUCEW, 1070, FLOOR, 1.1, { seed: 32 });
    const kid = S.actor("kid2", YOU("child"), 1560, FLOOR + 20, 1.3, { seed: 33, expr: "surprised" });
    br.k("self", "--x", S.t0, 800, 0); br.move(S.t0, 0, undefined, 0.9, "power3.out");
    mom.k("self", "--x", S.t0, -600, 0); mom.move(S.t0, 0, undefined, 0.9, "power3.out");
    mom.face(S.t0 + 0.9, "happy", 0.3); br.face(S.t0 + 0.9, "happy", 0.3);
    mom.arm("R", S.t0 + 0.9, 34, 40, 0.3); br.arm("L", S.t0 + 0.9, -34, -40, 0.3); // they join hands under the arch
    mom.turn(S.t0 + 1.0, 6, 2, 0.4); br.turn(S.t0 + 1.0, -6, -2, 0.4);
    S.layer(PR.heart("hrt", 960, 330), 1.1); S.pop("hrt", S.t0 + 1.0, 0.5); S.key("hrt", "--y", S.t0 + 1.5, -40, 1.0, "sine.out");
    kid.look(S.t0, -9, -6, 0); kid.turn(S.t0 + 0.3, -10, -4, 0.4); kid.face(S.t0 + 1.3, "happy", 0.4); kid.arm("L", S.t0 + 1.3, -40, -60, 0.4);
    lab(S, "wedLabel", "1991 · THE WEDDING", 960, 215, S.t0 + 0.7, { size: 58, rot: 2 });
    confetti(S, S.t0 + 1.0, 26, 4);
    S.layer(FX.glow(960, 520, 800, 400, "#ffd7a0", 0.4), 0.4);
  }, grade: ["#ffc890", 0.22] });

/* ===================== SHOT 7: 1976 Montreal - Bruce sprints through the finish tape ===================== */
D.shot({ id: "medal", a: ["s4", 0.62], b: ["s5", 0.0], bg: K.bg.stadium(),
  cam: { from: [-80, 0, 0.04], to: [120, 0, 0.12], ease: "power1.inOut" },
  build(S) {
    const tB = S.t0 + Math.max(1.0, S.dur * 0.6), x0 = 180, xF = 1560;
    // finish gate: two posts with checkered tops; ribbon between them
    S.layer(`<g>${[1490, 1630].map((x) => `<g transform="translate(${x} 950)"><rect x="-8" y="-300" width="16" height="300" fill="#f3ead2" stroke="#2a1820" stroke-width="5"/><rect x="-30" y="-340" width="60" height="44" fill="#fff" stroke="#2a1820" stroke-width="5"/><path d="M-30 -340h20v22h-20zM10 -340h20v22h-20zM-10 -318h20v22h-20z" fill="#2a1820"/></g>`).join("")}</g>`, 0.95);
    S.layer(`<g data-p="finish"><g transform="translate(1560 950)"><path d="M-70 -250H70" stroke="#d9453f" stroke-width="12" stroke-linecap="round"/><path d="M-70 -250H70" stroke="#fff" stroke-width="4" stroke-dasharray="14 14"/></g></g>`, 0.95);
    S.layer(`<g transform="translate(1560 953)"><path d="M-110 0H110" stroke="#fff" stroke-width="10"/><path d="M-110 0H110" stroke="#2a1820" stroke-width="4" stroke-dasharray="14 14"/></g>`, 0.8);
    S.layer(`<g data-p="rib1"><g transform="translate(1530 700)"><path d="M0 0Q-30 10 -60 40" stroke="#d9453f" stroke-width="12" fill="none" stroke-linecap="round"/></g></g><g data-p="rib2"><g transform="translate(1590 700)"><path d="M0 0Q30 10 60 40" stroke="#d9453f" stroke-width="12" fill="none" stroke-linecap="round"/></g></g>`, 1.0);
    ["rib1", "rib2"].forEach((n) => S.q(n).style.visibility = "hidden");
    // the runner: big, sprinting, arms pumping
    const run = S.actor("runner", Object.assign({}, BRUCE, { top: "#f6f2e8", pants: "#2e3a5a", accent: "#3a6aa8" }), x0, 960, 1.15, { depth: 0.95, seed: 88, idle: false });
    run.k("self", "--x", S.t0, 0, 0); run.face(S.t0, "determined", 0);
    run.walk(S.t0 + 0.05, tB, xF - x0, { step: 0.17, amp: 40 });
    run.k("self", "--y", S.t0, 0, 0);
    // break the tape
    S.hideAt("finish", tB); S.show("rib1", tB, true); S.show("rib2", tB, true);
    S.key("rib1", "--r", tB, 0, 0); S.key("rib1", "--r", tB, -70, 0.7, "power2.out"); S.key("rib1", "--y", tB, 0, 0); S.key("rib1", "--y", tB, 80, 0.7, "power1.in");
    S.key("rib2", "--r", tB, 0, 0); S.key("rib2", "--r", tB, 70, 0.7, "power2.out"); S.key("rib2", "--y", tB, 0, 0); S.key("rib2", "--y", tB, 80, 0.7, "power1.in");
    run.move(tB, xF - x0 + 120, undefined, S.t1 - tB, "power3.out");
    run.arm("L", tB + 0.2, 150, 30, 0.3, "back.out(1.6)"); run.arm("R", tB + 0.2, -150, -30, 0.3, "back.out(1.6)"); run.face(tB, "laugh", 0.2); run.hop(tB + 0.1, 26, 0.35);
        S.layer(FX.note("gold", ["Olympic decathlon", "GOLD · 1976"], 1560, 470, { w: 520, size: 52, rot: 3 }), 0.4);
    S.fadeIn("gold", S.t0 + 0.3, 0.2); S.wipe("gold", S.t0 + 0.45, 0.8);
    S.layer(K.P("medal", 400, 520, PR.medal(0, 0)), 1.0); S.pop("medal", tB + 0.15, 0.4);
    S.layer(PR.sparkle("sp1", 1500, 520), 1.1); S.layer(PR.sparkle("sp2", 1680, 640, "#fff"), 1.1); S.layer(PR.sparkle("sp3", 1420, 600, "#ffd24a"), 1.1);
    ["sp1", "sp2", "sp3"].forEach((n, i) => { S.pop(n, tB + 0.05 + i * 0.12, 0.3); S.key(n, "--r", tB + 0.05 + i * 0.12, 90, 0.9, "none"); });
    S.layer(FX.glow(1500, 560, 600, 420, "#fff3b0", 0.35), 0.3);
  } });

/* ===================== SHOT 8: cameras move in ===================== */
D.vhs(D.T("s5", 0.0), "2007");
D.shot({ id: "crew", a: ["s5", 0.0], b: ["s5", 0.56], bg: K.bg.tvHome(),
  cam: { from: [90, 0, 0.06], to: [-30, 0, 0.16] },
  build(S) {
    S.layer(FX.cone(1920, 150, 1920, 520, 1000, 960, 1500, 940, "#fff1c4", 0.5), 0.6);
    const you = S.actor("teen", YOU("w2007"), 620, FLOOR + 10, 1.18, { seed: 41, expr: "neutral" });
    const crew = S.actor("crew", CREW, 1500, FLOOR, 1.1, { seed: 42, idle: false });
    crew.k("self", "--x", S.t0, 700, 0); crew.walk(S.t0 + 0.1, S.t0 + 1.7, -1130, { arms: false }); crew.face(S.t0, "neutral", 0);
    crew.arm("R", S.t0 + 0.05, -95, -105, 0.2); crew.arm("L", S.t0 + 0.05, 70, 70, 0.2);
    S.layer(PR.camera("cam", 0, 0), 0.95); const cam = S.q("cam");
    S.key(cam, "--x", S.t0, 1500 + 700 - 120, 0); S.key(cam, "--x", S.t0 + 0.1, 1500 - 430 - 120, 1.6, "none"); S.key(cam, "--y", S.t0, 600, 0);
    you.turn(S.t0 + 0.3, -10, -4, 0.4); you.look(S.t0 + 0.3, 12, 0, 0.3); you.face(S.t0 + 0.5, "surprised", 0.3);
    you.arm("L", S.t0 + 0.8, 70, 40, 0.4, "back.out(1.3)");
    you.face(S.t0 + 1.6, "smirk", 0.4);
    lab(S, "crewLabel", "2007 · CAMERAS MOVE IN", 760, 250, S.t0 + 0.5, { size: 56, rot: -3 });
    S.layer(`<g transform="translate(0 0)"><circle id="recdot" cx="1780" cy="110" r="18" fill="#e22"/><text x="1740" y="122" text-anchor="end" font-family='${FX.FONT}' font-weight="800" font-size="40" fill="#fff" stroke="#000" stroke-width="2">REC</text></g>`, 0);
    const rd = S.el.querySelector("#recdot"); for (let t = S.t0; t < S.t1; t += 0.5) { S.key(rd, "opacity", t, (Math.round((t - S.t0) / 0.5) % 2) ? 0.15 : 1, 0); }
  }, grade: ["#ffc890", 0.2] });

/* ===================== SHOT 9: on camera ===================== */
D.shot({ id: "onair", a: ["s5", 0.56], b: ["s6", 0.0], bg: K.bg.tvStage(),
  cam: { from: [0, 0, 0.2], to: [0, 0, 0.06], ease: "power2.out" },
  build(S) {
    const you = S.actor("teen2", YOU("w2007"), 960, FLOOR + 30, 1.2, { seed: 51, expr: "smirk" });
    S.layer(PR.spot(300, 330, 10), 0.9); S.layer(PR.spot(1620, 330, 170), 0.9);
    S.layer(FX.cone(330, 330, 700, 880, 1200, 880, 370, 340, "#ffd9f0", 0.35), 0.8);
    S.layer(FX.cone(1590, 330, 1200, 880, 700, 880, 1550, 340, "#ffd9f0", 0.3), 0.8);
    you.arm("R", S.t0 + 0.35, -150, -20, 0.4, "back.out(1.5)"); you.face(S.t0 + 0.4, "laugh", 0.3); you.talkWords("s5", D.T("s5", 0.62));
    for (let t = S.t0 + 0.8, i = 0; t < S.t1 - 0.2; t += 0.3, i++) you.arm("R", t, i % 2 ? -150 : -120, i % 2 ? -20 : -55, 0.3, "sine.inOut"); // waves
    S.layer(`<g transform="translate(1640 700) scale(2.4)">${PR.camera("fcam", 0, 0)}</g>`, 1.5);
    lab(S, "tvLabel", "REALITY TV", 960, 220, S.t0 + 0.25, { size: 68, rot: 2 });
  }, grade: ["#d9a0ff", 0.15] });

/* ===================== SHOT 10: SKIMS ===================== */
D.vhs(D.T("s6", 0.0), "2025");
D.shot({ id: "skims", a: ["s6", 0.0], b: "end", bg: K.bg.boutique(),
  cam: { from: [0, 20, 0.08], to: [0, -10, 0.18] },
  build(S) {
    const you = S.actor("teen3", YOU("w2025"), 560, FLOOR + 20, 1.2, { seed: 61, expr: "happy" });
    you.arm("L", S.t0 + 0.4, 150, 20, 0.5, "back.out(1.6)"); you.arm("R", S.t0 + 0.4, -150, -20, 0.5, "back.out(1.6)"); you.hop(S.t0 + 0.9, 30, 0.4); you.face(S.t0 + 0.9, "laugh", 0.3); you.talkWords("s6");
    for (let t = S.t0 + 1.9, i = 0; t < S.t1 - 1.2; t += 0.9, i++) { you.hop(t, 22 + (i % 2) * 8, 0.4); you.arm("L", t + 0.45, i % 2 ? 150 : 120, i % 2 ? 20 : 50, 0.4, "sine.inOut"); you.arm("R", t + 0.45, i % 2 ? -120 : -150, i % 2 ? -50 : -20, 0.4, "sine.inOut"); }
    lab(S, "skLabel", "BRAND VALUE · 2025", 1420, 330, S.t0 + 0.3, { size: 52, rot: -2 });
    S.layer(`<g data-p="vcard"><g transform="translate(1500 560)"><rect x="-290" y="-130" width="580" height="260" rx="26" fill="#fffaf0" stroke="#2a1820" stroke-width="8"/><rect x="-270" y="-110" width="540" height="220" rx="16" fill="none" stroke="#c9a24a" stroke-width="4" stroke-dasharray="14 10"/></g></g>`, 1.1);
    S.pop("vcard", S.t0 + 0.5, 0.4);
    const vals = ["$0.5B", "$1B", "$2B", "$3B", "$4B", "$5B"]; const x = 1500, y = 600;
    S.layer(vals.map((v, i) => `<g data-p="v${i}" style="visibility:hidden"><g transform="translate(${x} ${y})"><text text-anchor="middle" font-family='${FX.FONT}' font-weight="800" font-size="170" fill="#c98a12" stroke="#2a1820" stroke-width="8" paint-order="stroke">${v}</text></g></g>`).join(""), 1.1);
    const step = Math.max(0.28, (S.dur - 2.6) / 6);
    vals.forEach((v, i) => { const t = S.t0 + 0.9 + i * 0.32; S.show("v" + i, t, true); if (i < vals.length - 1) S.hideAt("v" + i, t + 0.32); S.key("v" + i, "--s", t, 0.8, 0); S.key("v" + i, "--s", t, 1, 0.25, "back.out(2)"); });
    for (let i = 0; i < 6; i++) { S.layer(PR.coin("c" + i, 1240 + i * 100, 800), 1.2); S.pop("c" + i, S.t0 + 2.1 + i * 0.1, 0.35); S.key("c" + i, "--y", S.t0 + 2.4 + i * 0.1, -30 - (i % 2) * 24, 0.7, "sine.out"); }
    confetti(S, S.t0 + 1.9, 36, 9);
    S.layer(`<g data-p="fadeout"><rect width="1920" height="1080" fill="#000" opacity="1"/></g>`, 0);
    const fo = S.q("fadeout").firstElementChild; fo.style.opacity = "0"; S.key(fo, "opacity", S.t1 - 0.6, 0, 0); S.key(fo, "opacity", S.t1 - 0.6, 1, 0.58, "power1.in");
  } });
