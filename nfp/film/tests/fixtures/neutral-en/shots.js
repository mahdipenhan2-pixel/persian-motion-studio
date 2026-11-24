/* Neutral style fixture (no story, no real person, no brand): exercises the generic Film kit only -
   layered backgrounds, camera moves with parallax, colour looks, fog, dust, light rays and key lights,
   labels, a handwritten note, props, a VHS cut and the global grain/vignette. Anchors hang on word timings. */
const FX = K.fx, PR = FX.props, C = K.cine;
const W = (sid, i) => [sid, "w", i];
const SPEC = { build: "man", hair: "short_man", outfit: "track", skin: "#9a6a4a", hairColor: "#3a2f28", eyeColor: "#2f4a3a",
  top: "#3f6a5a", pants: "#2c2c34", shoe: "#e8e2d6", accent: "#c8a24a", lip: "#9a5a50", under: "#e9e4da",
  detail: 0, earrings: 0, glasses: 0, legs: "pants", sleeve: "long", shoeType: "sneaker" };

D.shot({ id: "street", a: 0.3, b: W("s2", 0), bg: K.bg.street(), cam: { from: [-40, 10, 0], to: [60, -10, 0.12] },
  build(S) {
    S.layer(C.look("dusk"), 0);
    C.fog(S, { y: 760, seed: 3 });
    S.layer(C.rays(1500, 120, 2.3, 900, 0.18, "#ffe0b0", 0.35), 0.4);
    const A = S.actor("walker", SPEC, 700, 960, 0.9, { depth: 0.9 });
    A.walk(S.at(0.15), S.at(0.75), 260);
    S.layer(FX.label("lb1", "EVENING", 1450, 230), 1.1); S.pop("lb1", S.at(0.3), 0.35);
  } });

D.shot({ id: "room", a: W("s2", 0), b: W("s3", 0), bg: K.bg.livingRoom(), cam: { from: [0, 0, 0.05], to: [-50, 0, 0.18] },
  build(S) {
    S.layer(C.look("home"), 0);
    S.layer(C.key(600, 420, 520, 300, "#ffcf8a", 0.35), 0);
    C.dust(S, { seed: 5 });
    S.layer(PR.desk(1300, 980, 420), 0.8);
    S.layer(FX.note("nt", ["remember", "this place"], 1400, 380), 1.05); S.fadeIn("nt", S.at(0.2), 0.3); S.wipe("nt", S.at(0.25), 0.9);
  } });

D.vhs(D.W("s3", 0), "1987");

D.shot({ id: "stage", a: W("s3", 0), b: "end", bg: K.bg.studio(), cam: { from: [30, 0, 0.1], to: [-30, 0, 0.22] },
  build(S) {
    S.layer(C.look("studio"), 0);
    S.layer(PR.spot(300, 200, 30) + PR.spot(1620, 200, 150), 1.0);
    S.layer(PR.sparkle("sp1", 960, 300), 1.1); S.pop("sp1", S.at(0.3), 0.3);
  } });
