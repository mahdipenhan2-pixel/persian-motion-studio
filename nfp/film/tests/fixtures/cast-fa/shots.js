/* Film cast fixture (Persian): the same generic sets, C3 characters placed with K.film.cast at their place in the layer order. */
const FX = K.fx, PR = FX.props, C = K.cine;
const W = (sid, i) => [sid, "w", i];

D.shot({ id: "street", a: 0.3, b: W("s2", 0), bg: K.bg.street(), cam: { from: [-40, 10, 0], to: [60, -10, 0.12] },
  build(S) {
    C.fog(S, { y: 760, seed: 3 });
    K.film.cast(S, "lina-street");
    S.layer(C.look("dusk"), 0);
  } });

D.shot({ id: "room", a: W("s2", 0), b: W("s3", 0), bg: K.bg.livingRoom(), cam: { from: [0, 0, 0.05], to: [-50, 0, 0.18] },
  build(S) {
    K.film.cast(S, "omid-room");
    K.film.cast(S, "lina-room");
    S.layer(C.look("home"), 0);
    S.layer(C.key(600, 420, 520, 300, "#ffcf8a", 0.35), 0);
  } });

D.shot({ id: "stage", a: W("s3", 0), b: "end", bg: K.bg.studio(), cam: { from: [30, 0, 0.1], to: [-30, 0, 0.22] },
  build(S) {
    K.film.cast(S, "omid-stage");
    S.layer(C.look("studio"), 0);
    S.layer(FX.label("lbfa", "صحنهٔ آخر", 1450, 230), 1.1); S.pop("lbfa", S.at(0.2), 0.35);
  } });
