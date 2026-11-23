(() => {
  "use strict";
  /* NFP Camera Motion Engine: replays pre-computed, deterministic tweens on the existing main timeline.
     Every value and time was computed and safety-checked in Python (studio/engine/camera). Captions
     (#stage) are never targeted. The timeline duration must not change. */
  const CAM = __CAMERA_JSON__;
  if (typeof gsap === "undefined") throw new Error("camera: GSAP failed to load.");
  const tl = window.__timelines && window.__timelines["main"];
  if (!tl) throw new Error("camera: main timeline not found.");
  const total = Number(CAM.duration);
  if (!Number.isFinite(total) || total <= 0) throw new Error("camera: invalid duration.");
  const before = tl.duration();
  const byId = (id) => {
    const el = document.getElementById(id);
    if (!el) throw new Error("camera: element not found: " + id);
    if (el.closest("#stage")) throw new Error("camera: captions must never move: " + id);
    return el;
  };

  CAM.sets.forEach((it) => tl.set(byId(it.el), it.props, 0));
  CAM.tweens.forEach((it) => {
    const t = Number(it.t);
    const d = Number(it.d);
    if (!Number.isFinite(t) || !Number.isFinite(d) || t < 0 || d <= 0 || t + d > total + 1e-6) {
      throw new Error("camera: tween outside the video: " + it.el);
    }
    tl.fromTo(byId(it.el), it.from, { ...it.to, duration: d, ease: it.ease, immediateRender: false }, t);
  });

  const after = tl.duration();
  if (Math.abs(after - before) > 1e-6) throw new Error("camera: timeline duration changed " + before + " -> " + after);
  window.__nfpCamera = { tweens: CAM.tweens.length, duration: after };
})();
