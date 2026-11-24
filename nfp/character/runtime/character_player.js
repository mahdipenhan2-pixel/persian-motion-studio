/* NFP Character Engine - C3d: live playback for a runtime made by NFPCharacterRuntime.create (browser previews only).

   Load after runtime/character_runtime.js, then attach to ONE runtime instance:
     const rt = NFPCharacterRuntime.create({ svg, keylist });
     NFPCharacterPlayer.attach(rt [, { clock, requestAnimationFrame, cancelAnimationFrame }]);
     rt.play({from, to, rate, onFrame, onEnd})   real-time playback, clamped to [from, to]
     rt.pause() / rt.resume() / rt.stop()        stop() returns to `from`; rt.time() and rt.playing() report the state

   Only the instance passed to attach() gets these methods (no prototype or global runtime is changed). This file reads
   the wall clock and schedules animation frames on purpose; it is never embedded in rendered pages (HyperFrames
   seeks the timeline built by rt.toTimeline instead), so the deterministic core stays free of clocks. */
(function (g) {
  "use strict";
  const finite = (v) => typeof v === "number" && Number.isFinite(v);

  function attach(rt, opts) {
    if (!rt || typeof rt.seek !== "function" || typeof rt.time !== "function" || !finite(rt.duration) || typeof rt.dispose !== "function")
      throw new Error("NFPCharacterPlayer.attach: pass a runtime made by NFPCharacterRuntime.create");
    if (["play", "pause", "resume", "stop", "playing"].some((m) => m in rt))
      throw new Error("NFPCharacterPlayer.attach: a player is already attached to this runtime");
    opts = opts || {};
    const duration = rt.duration, seek = rt.seek;
    const clock = opts.clock || (() => (g.performance ? g.performance.now() : Date.now()));
    const raf = opts.requestAnimationFrame || (g.requestAnimationFrame ? g.requestAnimationFrame.bind(g) : (cb) => setTimeout(() => cb(clock()), 16));
    const caf = opts.cancelAnimationFrame || (g.cancelAnimationFrame ? g.cancelAnimationFrame.bind(g) : clearTimeout);
    let play = null, handle = null;
    const gone = () => (typeof rt.disposed === "function" ? rt.disposed() : false);

    function tick() {
      if (!play || play.paused) return;
      const t = play.base + ((clock() - play.started) / 1000) * play.rate;
      if (t >= play.to) {
        seek(play.to); const end = play.onEnd; play.paused = true; play.ended = true; handle = null;
        if (play.onFrame) play.onFrame(play.to);
        if (end) end(play.to);
        return;
      }
      seek(t);
      if (play.onFrame) play.onFrame(t);
      handle = raf(tick);
    }
    function tickFreeze() {
      const t = play.base + ((clock() - play.started) / 1000) * play.rate;
      seek(Math.min(play.to, t)); play.paused = true;
    }

    rt.playing = () => !!(play && !play.paused);
    rt.play = (o) => {
      o = o || {};
      if (gone()) throw new Error("play: the runtime was disposed");
      const from = o.from !== undefined ? o.from : 0, to = o.to !== undefined ? o.to : duration, rate = o.rate !== undefined ? o.rate : 1;
      if (!finite(from) || !finite(to) || from < 0 || to > duration || !(to > from)) throw new Error("play: need 0 <= from < to <= " + duration);
      if (!finite(rate) || rate <= 0 || rate > 16) throw new Error("play: rate must be a number in (0, 16] (playback only runs forward)");
      if (handle) caf(handle);
      play = { from, to, base: from, rate, started: clock(), paused: false, onFrame: o.onFrame, onEnd: o.onEnd };
      seek(from);
      handle = raf(tick);
      return rt;
    };
    rt.pause = () => {
      if (play && !play.paused) { if (handle) caf(handle); handle = null; tickFreeze(); }
      return rt;
    };
    rt.resume = () => {
      if (play && play.paused && !play.ended) { play.base = rt.time(); play.started = clock(); play.paused = false; handle = raf(tick); }
      return rt;
    };
    rt.stop = () => {
      if (handle) caf(handle); handle = null;
      const from = play ? play.from : 0; play = null; if (!gone()) seek(from);
      return rt;
    };
    const coreDispose = rt.dispose;
    rt.dispose = () => { rt.stop(); coreDispose(); };      // as before: stop playback (back to `from`), then remove
    return rt;
  }

  g.NFPCharacterPlayer = { version: "c3-player-1", attach };
})(typeof window !== "undefined" ? window : globalThis);
