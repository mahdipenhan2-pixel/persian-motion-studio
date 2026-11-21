/* Director: turns shot descriptions + real sentence timing into one paused GSAP timeline.
   Rules (determinism): only fromTo/set, no random at runtime (seeded rng), no infinite repeats.
   All animated properties are CSS custom properties (--x --y --r --s --sx --sy) or opacity/visibility/display;
   CSS in base.html maps them to transforms around each part's own pivot. */
(function (K) {
  "use strict";
  const FPS = 30, snap = (t) => Math.round(t * FPS) / FPS;
  const DEF = { "--s": 1, "--sx": 1, "--sy": 1, opacity: 1 };
  const EASE = "power2.inOut";

  function Director(DATA, tl, world) {
    const byId = {}; DATA.sentences.forEach((s) => (byId[s.id] = s));
    const warns = [];
    const D = { tl, DATA, warns, shots: [], world };
    const state = new Map(); // el -> {prop: {v, end}}

    D.T = (sid, f) => { const s = byId[sid]; if (!s) throw new Error("unknown sentence " + sid); return snap(s.start + (s.end - s.start) * (f || 0)); };

    /** one animated value on one element; chronological per (el,prop) */
    function key(el, prop, t, val, dur, ease) {
      if (!el) throw new Error("key: missing element for " + prop);
      let m = state.get(el); if (!m) { m = {}; state.set(el, m); }
      let st = m[prop];
      if (!st) { st = m[prop] = { v: DEF[prop] !== undefined ? DEF[prop] : 0, end: 0 }; }
      dur = dur === undefined ? 0.3 : dur;
      if (t < st.end - 1e-6) { warns.push(`overlap on ${prop} at ${t.toFixed(2)} (prev end ${st.end.toFixed(2)})`); t = st.end; }
      if (dur <= 0.0001) tl.set(el, { [prop]: val }, t);
      else tl.fromTo(el, { [prop]: st.v }, { [prop]: val, duration: dur, ease: ease || EASE, immediateRender: false }, t);
      st.v = val; st.end = t + Math.max(dur, 0);
    }
    D.key = key;
    const setv = (el, props, t) => tl.set(el, props, t);

    function shot(o) {
      const TT = (x) => (typeof x === "number" ? snap(x) : x === "end" ? snap(DATA.duration) : D.T(x[0], x[1]));
      const t0 = TT(o.a), t1 = TT(o.b);
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("id", "shot-" + o.id); g.setAttribute("class", "shot"); g.style.visibility = "hidden";
      world.appendChild(g);
      const S = { id: o.id, el: g, t0, t1, dur: t1 - t0, actors: {}, D };
      S.at = (f) => snap(t0 + (t1 - t0) * f);
      S.ts = D.T;
      S.q = (name) => { const e = g.querySelector('[data-p="' + name + '"]'); if (!e) throw new Error(`shot ${o.id}: part '${name}' not found`); return e; };
      S.layer = (svg, depth) => { const l = document.createElementNS("http://www.w3.org/2000/svg", "g"); l.setAttribute("class", "lay"); l.style.setProperty("--d", depth === undefined ? 1 : depth); l.innerHTML = svg; g.appendChild(l); return l; };
      S.key = (nameOrEl, prop, t, val, dur, ease) => key(typeof nameOrEl === "string" ? S.q(nameOrEl) : nameOrEl, prop, t, val, dur, ease);
      S.show = (name, t, on) => setv(S.q(name), { visibility: on === false ? "hidden" : "visible" }, t);
      S.hideAt = (name, t) => S.show(name, t, false);
      S.pop = (name, t, dur) => { const e = S.q(name); e.style.visibility = "hidden"; key(e, "--s", t, 0, 0); setv(e, { visibility: "visible" }, t); key(e, "--s", t, 1, dur || 0.35, "back.out(2)"); };
      S.fadeIn = (name, t, dur) => { const e = S.q(name); e.style.opacity = "0"; key(e, "opacity", t, 0, 0); key(e, "opacity", t, 1, dur || 0.3, "power1.out"); };
      S.fadeOut = (name, t, dur) => { const e = S.q(name); key(e, "opacity", t, 0, dur || 0.3, "power1.in"); };
      S.wipe = (name, t, dur) => key(S.q(name + "_wipe"), "--sx", t, 0, dur || 0.9, "power1.inOut");

      // background layers + shot-level light
      (o.bg ? o.bg.layers : []).forEach((l) => S.layer(l.svg, l.depth));

      /* ---------- actors ---------- */
      S.actor = (id, spec, x, y, scale, opt) => {
        opt = opt || {};
        const wrap = S.layer(`<g data-p="${id}"><g transform="translate(${x} ${y}) scale(${scale || 1})">${K.chars.actor(spec)}</g></g>`, opt.depth === undefined ? 0.9 : opt.depth);
        const root = wrap.querySelector('[data-p="' + id + '"]');
        const eyeEx = (K.chars.FACE[spec.build] || K.chars.FACE.child).ey;
        const A = { id, el: root, x, y, scale: scale || 1, spec, mouth: "neutral", t: t0 };
        A.p = (n) => { const e = root.querySelector('[data-p="' + n + '"]'); if (!e) throw new Error(`actor ${id}: no part ${n}`); return e; };
        A.k = (part, prop, t, val, dur, ease) => key(part === "self" ? root : A.p(part), prop, t, val, dur, ease);
        A.move = (t, dx, dy, dur, ease) => { A.k("self", "--x", t, dx, dur, ease || "power2.inOut"); if (dy !== undefined) A.k("self", "--y", t, dy, dur, ease || "power2.inOut"); };
        A.appear = (t, dur) => { setv(root, { visibility: "visible" }, t); A.k("self", "--s", t, 0, 0); A.k("self", "--s", t, 1, dur || 0.4, "back.out(1.6)"); };
        A.hideAt = (t) => setv(root, { visibility: "hidden" }, t);
        A.hiddenUntil = (t) => { root.style.visibility = "hidden"; setv(root, { visibility: "visible" }, t); };
        A.faceNow = (t, name, dur) => {
          const e = K.chars.EXPR[name]; if (!e) throw new Error("expr " + name); dur = dur === undefined ? 0.22 : dur;
          A.k("browL", "--y", t, e.by, dur); A.k("browR", "--y", t, e.by, dur);
          A.k("browL", "--r", t, -e.br, dur); A.k("browR", "--r", t, e.br, dur);
          A.k("eyeL", "--sy", t, e.ey, dur); A.k("eyeR", "--sy", t, e.ey, dur);
          A.k("blush", "opacity", t, e.blush, dur);
          const tr = A.root_x("tears"), sw = A.root_x("sweat");
          if (tr) setv(tr, { display: e.tears ? "inline" : "none" }, t); if (sw) setv(sw, { display: e.sweat ? "inline" : "none" }, t);
          if (A.mouth !== e.mouth) { setv(A.q1(A.mouth), { display: "none" }, t); setv(A.q1(e.mouth), { display: "inline" }, t); A.mouth = e.mouth; }
        };
        A.root_x = (n) => root.querySelector('[data-x="' + n + '"]');
        A.q1 = (m) => root.querySelector('[data-m="' + m + '"]');
        A.face = A.faceNow;
        A.mouthOnly = (t, m) => { if (A.mouth !== m) { setv(A.q1(A.mouth), { display: "none" }, t); setv(A.q1(m), { display: "inline" }, t); A.mouth = m; } };
        A.look = (t, dx, dy, dur) => { A.k("irisL", "--x", t, dx, dur); A.k("irisR", "--x", t, dx, dur); A.k("irisL", "--y", t, 2 + dy, dur); A.k("irisR", "--y", t, 2 + dy, dur); };
        A.turn = (t, deg, dx, dur, ease) => { A.k("head", "--r", t, deg, dur, ease); A.k("head", "--x", t, dx || 0, dur, ease); };
        A.nod = (t, amp, dur) => { A.k("head", "--y", t, amp, dur / 2, "power2.out"); A.k("head", "--y", t + dur / 2, 0, dur / 2, "power2.inOut"); };
        A.arm = (side, t, r, fr, dur, ease) => { A.k("arm" + side, "--r", t, r, dur, ease); if (fr !== undefined) A.k("fore" + side, "--r", t, fr, dur, ease); };
        A.armsRest = (t, dur) => { A.arm("L", t, 4, 4, dur); A.arm("R", t, -4, -4, dur); };
        A.lean = (t, deg, dur) => A.k("torso", "--r", t, deg, dur);
        A.hop = (t, h, dur) => { A.k("root", "--y", t, -h, dur / 2, "power2.out"); A.k("root", "--y", t + dur / 2, 0, dur / 2, "power2.in"); };
        A.shiver = (t0_, t1_, amp) => { for (let t = t0_, i = 0; t < t1_; t += 0.07, i++) A.k("root", "--x", t, (i % 2 ? amp : -amp), 0.07, "none"); A.k("root", "--x", t1_, 0, 0.07); };
        A.blinkAt = (t) => { A.k("lidL", "--y", t, 2 * eyeEx + 2, 0.06, "power1.in"); A.k("lidR", "--y", t, 2 * eyeEx + 2, 0.06, "power1.in"); A.k("lidL", "--y", t + 0.08, 0, 0.1, "power1.out"); A.k("lidR", "--y", t + 0.08, 0, 0.1, "power1.out"); };
        A.autoBlink = (a, b, seed) => { const r = K.rng(seed || 1); for (let t = a + 0.6 + r() * 1.6; t < b - 0.3; t += 2.4 + r() * 2.2) A.blinkAt(snap(t)); };
        A.breathe = (a, b, amp) => { amp = amp || 0.022; let up = true; for (let t = a; t < b; t += 1.2) { A.k("torso", "--sy", t, up ? 1 + amp : 1, 1.2, "sine.inOut"); up = !up; } };
        /** natural walk: opposite leg/arm swing, knee flex on the swing leg, foot lift, body bob + sway, head counter-tilt, hair lag */
        A.walk = (a, b, dx, o2) => {
          o2 = o2 || {}; const step = o2.step || 0.3, amp = o2.amp || 20, dir = dx >= 0 ? 1 : -1, f = -dir; // hip rotation sign for "forward"
          const x0 = state.get(root) && state.get(root)["--x"] ? state.get(root)["--x"].v : 0;
          const hair = root.querySelector('[data-p="hairBack"]'), arms = o2.arms !== false;
          A.k("self", "--x", a, x0 + dx, b - a, "none");
          let s = 1; // s>0: left leg swings forward
          for (let t = a; t < b - 0.01; t += step) {
            const d = Math.min(step, b - t), h = d / 2, sw = (side, fwd) => {
              const th = "leg" + side, sh = "shin" + side, so = "shoe" + side;
              if (fwd) { A.k(th, "--r", t, f * amp * 1.0, d, "sine.inOut"); A.k(sh, "--r", t, -f * amp * 1.3, h, "sine.out"); A.k(sh, "--r", t + h, 0, h, "sine.in"); A.k(so, "--r", t, -f * 10, h, "sine.out"); A.k(so, "--r", t + h, 0, h, "sine.in"); A.k(th, "--y", t, -12, h, "sine.out"); A.k(th, "--y", t + h, 0, h, "sine.in"); }
              else { A.k(th, "--r", t, -f * amp * 0.8, d, "sine.inOut"); A.k(sh, "--r", t, 0, d, "none"); A.k(th, "--y", t, 0, d, "none"); A.k(so, "--r", t, f * 8, d, "sine.inOut"); }
            };
            sw("L", s > 0); sw("R", s < 0);
            if (arms) { A.k("armL", "--r", t, 4 - s * f * amp * 1.1, d, "sine.inOut"); A.k("armR", "--r", t, -4 + s * f * amp * 1.1, d, "sine.inOut"); A.k("foreL", "--r", t, s > 0 ? 8 : 26, d, "sine.inOut"); A.k("foreR", "--r", t, s > 0 ? -26 : -8, d, "sine.inOut"); }
            A.k("root", "--y", t, -10, h, "sine.out"); A.k("root", "--y", t + h, 0, h, "sine.in");
            A.k("torso", "--r", t, s * 2.6, d, "sine.inOut"); A.k("head", "--r", t, -s * 1.6, d, "sine.inOut");
            if (hair) A.k(hair, "--r", t + 0.05, -s * 4, d, "sine.inOut");
            s = -s;
          }
          ["legL", "legR", "shinL", "shinR", "shoeL", "shoeR"].forEach((n) => { A.k(n, "--r", b, 0, 0.2); });
          A.k("legL", "--y", b, 0, 0.2); A.k("legR", "--y", b, 0, 0.2);
          if (arms) { A.k("armL", "--r", b, 4, 0.2); A.k("armR", "--r", b, -4, 0.2); A.k("foreL", "--r", b, 4, 0.2); A.k("foreR", "--r", b, -4, 0.2); }
          A.k("torso", "--r", b, 0, 0.2); A.k("head", "--r", b, 0, 0.2); if (hair) A.k(hair, "--r", b + 0.05, 0, 0.3);
        };
        /** word-timed mouth flaps for one sentence (lip-sync as far as 2D swap-mouths allow) */
        A.talkWords = (sid, from, to) => {
          const sn = byId[sid]; if (!sn) return; const shapes = ["open", "small", "o", "open", "small"];
          sn.words.forEach((w, i) => { if (!w.hl) return; if (from !== undefined && w.start < from) return; if (to !== undefined && w.end > to) return;
            const d = w.end - w.start, n = Math.max(1, Math.round(d / 0.13));
            for (let k = 0; k < n; k++) { const t = snap(w.start + (d * k) / n); A.mouthOnly(t, shapes[(i + k) % shapes.length]); A.k("head", "--y", t, k % 2 ? 0 : 2, 0.06); A.mouthOnly(snap(Math.min(w.end, t + (d / n) * 0.62)), "small"); }
            A.mouthOnly(snap(w.end + 0.02), "neutral"); });
        };
        // base pose
        A.k("armL", "--r", t0, 4, 0); A.k("armR", "--r", t0, -4, 0);
        A.k("irisL", "--y", t0, 2, 0); A.k("irisR", "--y", t0, 2, 0);
        if (opt.expr) A.faceNow(t0, opt.expr, 0);
        S.actors[id] = A;
        if (opt.idle !== false) { A.autoBlink(t0, t1, opt.seed || id.length * 7 + 3); A.breathe(t0, t1); }
        return A;
      };

      /* ---------- camera ---------- */
      const cam = o.cam || {};
      const c0 = cam.from || [0, 0, 0], c1 = cam.to || c0;
      key(g, "--cx", t0, c0[0], 0); key(g, "--cy", t0, c0[1], 0); key(g, "--cz", t0, c0[2], 0);
      const camEase = cam.ease || "power1.inOut";
      key(g, "--cx", t0, c1[0], t1 - t0, camEase); key(g, "--cy", t0, c1[1], t1 - t0, camEase); key(g, "--cz", t0, c1[2], t1 - t0, camEase);
      S.camTo = null;

      if (o.build) o.build(S);
      if (o.grade) S.layer(K.fx.grade(o.grade[0], o.grade[1]), 0);
      if (o.light) S.layer(o.light, 0.5);

      // visibility window
      setv(g, { visibility: "visible" }, t0);
      setv(g, { visibility: "hidden" }, t1);
      D.shots.push(S);
      return S;
    }
    D.shot = shot;

    /* ---------- VHS transition at a cut ---------- */
    D.vhs = (tCut, year, o) => {
      o = o || {}; const str = o.strength === undefined ? 1 : o.strength, nBars = o.bars === undefined ? 6 : o.bars;
      const ov = document.getElementById("vhsov"), r = K.rng(Math.round(tCut * 100) + 11);
      const a = snap(tCut - (o.pre === undefined ? 0.1 : o.pre)), b = snap(tCut + (o.post === undefined ? 0.3 : o.post));
      setv(ov, { visibility: "visible" }, a); setv(ov, { visibility: "hidden" }, b);
      setv(world, { filter: "url(#vhs)" }, a); setv(world, { filter: "none" }, b);
      const flash = document.getElementById("vhsflash");
      key(flash, "opacity", a, 0, 0); key(flash, "opacity", tCut, 0.55 * str, 0.05); key(flash, "opacity", tCut + 0.05, 0, 0.18);
      const dm = document.getElementById("vhsD"), tb = document.getElementById("vhsT");
      const amps = [60, 110, 40, 95, 30, 10, 0].map((v) => Math.round(v * str));
      amps.forEach((v, i) => { const t = snap(a + i * (b - a) / amps.length); tl.set(dm, { attr: { scale: v } }, t); tl.set(tb, { attr: { seed: 3 + Math.floor(r() * 90) } }, t); });
      for (let i = 0; i < 6; i++) { const bar = ov.querySelector('[data-p="vb' + i + '"]'); if (i >= nBars) { setv(bar, { visibility: "hidden" }, a); continue; }
        for (let k = 0, t = a; t < b; k++, t = snap(t + 0.066)) { key(bar, "--y", t, Math.round((r() - 0.5) * 700), 0); key(bar, "--x", t, Math.round((r() - 0.5) * 120), 0); } }
      if (year) { const y = document.createElementNS("http://www.w3.org/2000/svg", "text");
        ["x:1810", "y:150"].forEach((p) => { const [k, v] = p.split(":"); y.setAttribute(k, v); });
        y.setAttribute("text-anchor", "end"); y.setAttribute("font-family", K.fx.FONT); y.setAttribute("font-weight", "800"); y.setAttribute("font-size", "84");
        y.setAttribute("fill", "#fff"); y.setAttribute("stroke", "#000"); y.setAttribute("stroke-width", "3"); y.setAttribute("letter-spacing", "3");
        y.textContent = year; y.style.visibility = "hidden"; ov.appendChild(y);
        setv(y, { visibility: "visible" }, snap(tCut - 0.03)); setv(y, { visibility: "hidden" }, snap(tCut + (o.year === undefined ? 0.5 : o.year))); }
    };

    /* ---------- grain: pre-rendered tile jumped 10x per second ---------- */
    D.grain = (el) => { const r = K.rng(5); for (let t = 0; t < DATA.duration; t += 0.1) { const tt = snap(t); key(el, "--x", tt, Math.floor(r() * 256), 0); key(el, "--y", tt, Math.floor(r() * 256), 0); } };
    return D;
  }
  K.Director = Director; K.snap = snap;
})(window.K);
