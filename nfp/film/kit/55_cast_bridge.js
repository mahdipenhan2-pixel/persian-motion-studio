/* NFP Film - bridge between the Director (50_director.js) and the C3 character runtime (nfp/character/runtime).
   Loaded with the kit only when a project has characters; its data (window.__NFP_FILM_CAST) is written by
   engine/cast_plan.py in front of this file.

     K.film.cast(S, key)   inside a shot's build(): makes the parallax layer of that character at its depth, at this
                           point of the layer order (so the shot's own grade and light layers added later cover it,
                           exactly like a Director actor). The shot and its window must match the planned instance.
     K.film.mount(kls)     after the page's timeline exists: one C3 runtime per instance on its layer, keys added to
                           the main timeline with C3's own toTimeline; nothing is re-planned here.
   Guards: every planned instance placed exactly once, in its own shot; rig CSS active; the timeline length unchanged. */
(function (K) {
  "use strict";
  const DATA = window.__NFP_FILM_CAST;
  if (!DATA || DATA.version !== 1 || !Array.isArray(DATA.instances)) throw new Error("K.film: character data missing");
  const byKey = {}, placed = {};
  DATA.instances.forEach((i) => { byKey[i.key] = i; });

  function cast(S, key) {
    const inst = byKey[key];
    if (!inst) throw new Error("K.film.cast: '" + key + "' is not a planned character of this chapter");
    if (placed[key]) throw new Error("K.film.cast: '" + key + "' placed twice");
    if (S.id !== inst.shot) throw new Error("K.film.cast: '" + key + "' belongs to shot '" + inst.shot + "', not '" + S.id + "'");
    if (Math.abs(S.t0 - inst.t0) > 1 / 60 || Math.abs(S.t1 - inst.t1) > 1 / 60)
      throw new Error("K.film.cast: '" + key + "' was planned for " + inst.t0 + "-" + inst.t1 + "s but shot '" + S.id + "' runs " + S.t0 + "-" + S.t1 + "s");
    const layer = S.layer("", inst.depth);
    layer.setAttribute("data-nfp-film-cast", key);
    placed[key] = layer;
    return layer;
  }

  function mount(keylists) {
    const tl = window.__timelines && window.__timelines.main;
    if (!tl) throw new Error("K.film.mount: main timeline not found");
    if (typeof gsap === "undefined" || !window.NFPCharacterRuntime) throw new Error("K.film.mount: GSAP or the C3 runtime is not loaded");
    const missing = DATA.instances.filter((i) => !placed[i.key]).map((i) => i.key);
    if (missing.length) throw new Error("K.film.mount: not placed in shots.js (K.film.cast(S, key) missing): " + missing.join(", "));
    const extra = Object.keys(keylists).filter((k) => !byKey[k]);
    if (extra.length) throw new Error("K.film.mount: KeyLists without a planned instance: " + extra.join(", "));
    // the rig needs the [data-p] transform rule (base.html): a probe must get a real transform
    const host = placed[DATA.instances[0].key], probe = document.createElementNS("http://www.w3.org/2000/svg", "g");
    probe.setAttribute("data-p", "nfp-film-probe"); probe.style.setProperty("--r", "10"); host.appendChild(probe);
    const t = getComputedStyle(probe).transform; probe.remove();
    if (!t || t === "none") throw new Error("K.film.mount: the rig CSS is not active (character parts would not move)");
    const before = tl.duration();
    DATA.instances.forEach((i) => {
      const kl = keylists[i.key];
      if (!kl) throw new Error("K.film.mount: no KeyList for '" + i.key + "'");
      window.NFPCharacterRuntime.create({ svg: placed[i.key], keylist: kl }).toTimeline(gsap, tl);
    });
    if (Math.abs(tl.duration() - before) > 1e-6) throw new Error("K.film.mount: timeline length changed " + before + " -> " + tl.duration());
    window.__nfpFilmCast = { instances: DATA.instances.length, keys: DATA.instances.reduce((n, i) => n + keylists[i.key].keys.length, 0), duration: tl.duration() };
  }

  K.film = { cast, mount };
})(window.K);
