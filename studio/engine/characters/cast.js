(() => {
  "use strict";
  /* NFP Studio character layer (C4): builds the characters of ONE KeyList (made and validated in Python by
     studio/engine/characters + the C3 planner) and replays it on the EXISTING main timeline, like camera.js.
     Hard guards: GSAP + rig + runtime present, rig.css really active, no characters already on the page, the layer is
     never inside the captions, and the timeline duration does not change. */
  const KL = __CAST_JSON__;
  const NS = "http://www.w3.org/2000/svg";
  if (typeof gsap === "undefined") throw new Error("cast: GSAP failed to load.");
  const tl = window.__timelines && window.__timelines["main"];
  if (!tl) throw new Error("cast: main timeline not found.");
  if (!window.K || !window.K.chars || !window.NFPCharacterRuntime) throw new Error("cast: rig or runtime not loaded.");
  if (document.querySelector("[data-nfp-actor]")) throw new Error("cast: characters are already on this page.");
  const svg = document.getElementById("nfp-cast-svg-bottom");
  if (!svg) throw new Error("cast: character slot not found.");
  if (svg.closest("#stage")) throw new Error("cast: the character layer must never be inside the captions.");

  // rig.css must be active: a [data-p] element with --r must get a real transform, otherwise every part stays still
  const probe = document.createElementNS(NS, "g");
  probe.setAttribute("data-p", "nfp-css-probe");
  probe.style.setProperty("--r", "10");
  svg.appendChild(probe);
  const active = getComputedStyle(probe).transform;
  probe.remove();
  if (!active || active === "none") throw new Error("cast: rig.css is not active (character parts would not move).");

  const before = tl.duration();
  const rt = window.NFPCharacterRuntime.create({ svg, keylist: KL });
  rt.toTimeline(gsap, tl);
  const after = tl.duration();
  if (Math.abs(after - before) > 1e-6) throw new Error("cast: timeline duration changed " + before + " -> " + after);
  window.__nfpCast = { actors: KL.actors.length, keys: KL.keys.length, digest: KL.digest, duration: after };
})();
