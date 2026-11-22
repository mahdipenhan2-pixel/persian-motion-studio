#!/usr/bin/env python3
"""Offline sound design + mix for ONE chapter of the 6-minute documentary (numpy/scipy only: synthesised music and effects,
no samples, no third-party audio, no network, no TTS).
  make_audio_6min.py --chapter c1 --build <dir with <ch>/cues.json and <ch>/story/narration.wav> --timing <timing.json> --sfx <sfx6.json> --out ch.wav
Mix = narration (as generated) + music bed (ducked under speech) + effects generated from the cut / flash / whip / timeline-ruler cues
that the composition itself publishes, plus the hand-placed cues of sfx6.json anchored on script words."""
import argparse, json, wave
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
RNG = np.random.default_rng(20261122)
db = lambda x: 10 ** (x / 20)
tt = lambda d: np.arange(int(d * SR)) / SR
nrm = lambda x: x / (np.max(np.abs(x)) + 1e-9)
def lp(x, f, o=4): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=4): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def fit(x, n): return np.pad(x, (0, max(0, n - len(x))))[:n]

def reverb(x, tail=1.2, mix=0.3):
    n = int(tail * SR); ir = lp(RNG.standard_normal(n) * np.exp(-np.linspace(0, 6.5, n)), 5200)
    wet = fftconvolve(x, ir / np.sqrt(np.sum(ir ** 2)))[: len(x) + n]
    out = np.zeros(len(wet)); out[: len(x)] += x * (1 - mix); out += wet * mix * 1.2
    return out

def sweep(dur, f0, f1, q=1.4, shape="bell"):
    n = int(dur * SR); noise = RNG.standard_normal(n); out = np.zeros(n); B = 1024; zi = None
    for i in range(0, n, B):
        fc = f0 * (f1 / f0) ** (i / n); bw = fc / q
        sos = butter(2, [max(40, fc - bw), min(SR / 2 - 100, fc + bw)], "band", fs=SR, output="sos")
        z = np.zeros((sos.shape[0], 2)) if zi is None else zi
        seg, zi = sosfilt(sos, noise[i:i + B], zi=z); out[i:i + B] = seg
    u = np.linspace(0, 1, n)
    env = np.sin(np.pi * u) ** 2 if shape == "bell" else (u ** 2 if shape == "rise" else (1 - u) ** 1.5 * np.minimum(1, u * 40))
    return nrm(out) * env

def click(f=2400, d=0.03, a=1.0):
    t = tt(d); return a * (np.sin(2 * np.pi * f * t) * np.exp(-t * 180) + hp(RNG.standard_normal(len(t)), 3000) * np.exp(-t * 420) * 0.7)
def shutter():
    a, b = click(1500, 0.05), click(900, 0.06, 0.8); o = np.zeros(int(0.16 * SR)); o[: len(a)] += a; s = int(0.055 * SR); o[s:s + len(b)] += b[: len(o) - s]; return nrm(o)
def boom(d=1.5, f0=120, f1=38):
    t = tt(d); f = f1 + (f0 - f1) * np.exp(-t * 7); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6) + lp(RNG.standard_normal(len(t)), 240) * np.exp(-t * 14) * 0.6
    return nrm(reverb(x, 1.1, 0.22))[: int(d * SR)]
def stamp():
    t = tt(0.5); x = np.sin(2 * np.pi * (80 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 11) + lp(RNG.standard_normal(len(t)), 1800) * np.exp(-t * 60) * 0.8
    return nrm(reverb(x, 0.6, 0.2))
def slam():
    n = int(1.4 * SR); return nrm(fit(boom(1.4, 150, 42), n) + 0.8 * fit(stamp(), n) + 0.5 * fit(sweep(0.25, 6000, 400, 1.2, "fall"), n))
def ping(d=1.4, f=1318.5):
    t = tt(d); x = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.5 * t) + 0.25 * np.sin(2 * np.pi * f * 2 * t)) * np.exp(-t * 3.4) * np.minimum(1, t * 600)
    return nrm(reverb(x, 1.2, 0.35))
def tick(f=1900): return nrm(click(f, 0.035))
def route(d):
    t = tt(d); f = 420 * (3.4 ** (t / d)); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)
    return nrm(x * np.minimum(1, t * 40) * np.minimum(1, (d - t) * 18)) * 0.8
def coin():
    t = tt(0.5); return nrm((np.sin(2 * np.pi * 1760 * t) + 0.6 * np.sin(2 * np.pi * 2349 * t)) * np.exp(-t * 7) * np.minimum(1, t * 800))
def heart():
    n = int(0.9 * SR); o = np.zeros(n)
    for off, a in ((0.0, 1.0), (0.3, 0.7)):
        t = tt(0.3); o[int(off * SR):int(off * SR) + len(t)] += np.sin(2 * np.pi * 58 * t) * np.exp(-t * 16) * a
    return nrm(reverb(o, 0.5, 0.15))[:n]

SFX = {"whoosh_soft": lambda c: sweep(0.55, 900, 3200, 0.9), "whip": lambda c: sweep(0.5, 6000, 500, 0.8, "fall"), "swish": lambda c: sweep(0.32, 2500, 7500, 1.3),
       "whoosh_up": lambda c: sweep(c.get("dur", 1.2), 300, 5200, 1.0), "swell": lambda c: sweep(c.get("dur", 1.5), 150, 900, 0.7, "rise") * 0.8, "shutter": lambda c: shutter(), "boom": lambda c: boom(),
       "stamp": lambda c: stamp(), "slam": lambda c: slam(), "ping": lambda c: ping(), "route": lambda c: route(c.get("dur", 1.2)), "coin": lambda c: coin(), "heart": lambda c: heart(), "tick_hi": lambda c: tick(3000)}

def put(buf, x, at, g):
    s = int(round(at * SR)); e = min(len(buf), s + len(x))
    if 0 <= s < len(buf) and e > s: buf[s:e] += x[: e - s] * db(g)

# ------------------------------------------------------------------ music
NOTE = lambda m: 440.0 * 2 ** ((m - 69) / 12)
CH = {"Am": [57, 60, 64], "F": [53, 57, 60], "C": [48, 52, 55], "G": [55, 59, 62], "Dm": [50, 53, 57], "Bb": [58, 62, 65], "Em": [52, 55, 59], "Fmaj": [53, 57, 60]}

def pad(notes, d, bright=0.5):
    t = tt(d); x = np.zeros(len(t))
    for m in notes:
        for det in (-0.07, 0.0, 0.08):
            f = NOTE(m + 12) * 2 ** (det / 12)
            x += np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t + 0.6) * bright + 0.12 * np.sin(2 * np.pi * 3 * f * t) * bright
    x += 0.9 * np.sin(2 * np.pi * NOTE(notes[0] - 12) * t)            # root an octave below (bass body)
    env = np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.6) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.17 * t))
    return nrm(lp(x, 2200 + 2500 * bright)) * env

def pluck(m, d=1.1):
    t = tt(d); f = NOTE(m + 12); x = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6) + 0.15 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 9)) * np.exp(-t * 4.2) * np.minimum(1, t * 900)
    return nrm(reverb(x, 1.0, 0.3))[: len(t)]

def bell(m, d=2.6):
    t = tt(d); f = NOTE(m + 24); x = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * dk) for r, a, dk in ((1, 1, 1.6), (2.76, 0.5, 2.4), (5.4, 0.25, 3.4))) * np.minimum(1, t * 500)
    return nrm(reverb(x, 1.8, 0.45))[: len(t)]

def soft_kick(): t = tt(0.4); return nrm(np.sin(2 * np.pi * np.cumsum(46 + 70 * np.exp(-t * 28)) / SR) * np.exp(-t * 9))

def music(dur, plan):
    """plan: list of (t0, t1, prog, style); style: 'myst' | 'pulse' | 'warm' | 'tense' | 'bright' | 'end'"""
    buf = np.zeros(int(dur * SR) + SR * 4)
    for (a, b, prog, style) in plan:
        a, b = max(0, a), min(dur, b); span = b - a
        if span <= 0.2: continue
        per = 6.4 if style in ("warm", "bright", "end") else 6.4
        n = int(np.ceil(span / per))
        for k in range(n):
            ta = a + k * per; ch = CH[prog[k % len(prog)]]; dd = min(per + 1.2, b - ta + 1.2)
            put(buf, pad(ch, dd, 0.35 if style in ("myst", "tense") else 0.75), ta, -6 if style != "end" else -4)
            if style in ("warm", "bright", "pulse"):
                step = 0.8 if style != "warm" else 1.6
                pat = [0, 1, 2, 1, 0, 2, 1, 2] if style != "warm" else [0, 2, 1, 2]
                for j in range(int(per / step)):
                    tp = ta + j * step
                    if tp < b - 0.5: put(buf, pluck(ch[pat[j % len(pat)]] + (12 if style == "bright" else 0)), tp, -17 if style == "warm" else -15)
            if style == "pulse":
                for j in range(int(per / 0.8)):
                    tp = ta + j * 0.8
                    if tp < b - 0.3: put(buf, soft_kick(), tp, -14)
            if style in ("myst", "tense", "end"):
                for j, m in enumerate((ch[2], ch[1], ch[0], ch[2])):
                    tp = ta + 0.9 + j * 1.5
                    if tp < b - 1.0: put(buf, bell(m), tp, -15 if style in ("myst", "end") else -19)
                if style == "tense":
                    for j in range(int(per / 1.6)):
                        tp = ta + j * 1.6
                        if tp < b - 0.3: put(buf, soft_kick(), tp, -17)
    return buf[: int(dur * SR)]

def duck(nar, depth=0.5):
    w = int(0.05 * SR); env = np.sqrt(np.maximum(fftconvolve(nar ** 2, np.ones(w) / w, "same"), 0)); env = fftconvolve(env, np.ones(int(0.25 * SR)) / int(0.25 * SR), "same")
    on = (env > 0.012).astype(float)
    k = np.exp(-np.arange(int(0.8 * SR)) / (0.3 * SR)); g = fftconvolve(on, k / k.sum())[: len(on)]        # fast attack, slow release
    near = fftconvolve(on, np.ones(int(3.0 * SR)) / int(3.0 * SR), "same")                       # no speech within +-1.5 s: the music may come forward
    quiet = np.clip(1 - near * 6, 0, 1); quiet = fftconvolve(quiet, np.ones(int(0.5 * SR)) / int(0.5 * SR), "same")
    return (1 - depth * np.clip(g, 0, 1)) * (1 + 0.9 * quiet)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--chapter", required=True); ap.add_argument("--build", required=True); ap.add_argument("--timing", required=True)
    ap.add_argument("--sfx", required=True); ap.add_argument("--out", required=True); ap.add_argument("--music-db", type=float, default=-6.0); a = ap.parse_args()
    from pathlib import Path
    B = Path(a.build) / a.chapter
    with wave.open(str(B / "story" / "narration.wav")) as w:
        nr = w.getframerate(); nar = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768
    nar = np.interp(np.arange(int(len(nar) * SR / nr)) / SR, np.arange(len(nar)) / nr, nar)
    dur = len(nar) / SR
    timing = json.load(open(a.timing)); words = {}
    for s in timing["sentences"]:
        rows = [r for r in s["words"]]; nxt = s["offset"] + s["duration"]
        res = [None] * len(rows)
        for k in range(len(rows) - 1, -1, -1):
            r = rows[k]
            if r["abs_start"] is not None: res[k] = (r["abs_start"], r["abs_end"]); nxt = r["abs_start"]
            else: res[k] = (nxt, nxt)
        words[s["id"]] = res
    cues = json.load(open(B / "cues.json")); sfxcfg = json.load(open(a.sfx))
    W = lambda sid, i, edge=0: words[sid][i][edge]
    # --- music plan (times from the real sentence offsets)
    off = {s["id"]: s["offset"] for s in timing["sentences"]}
    plan = []
    for seg in sfxcfg["music"].get(a.chapter, []):
        t0 = W(*seg["from"]) if isinstance(seg["from"], list) else seg["from"]
        t1 = (W(*seg["to"]) if isinstance(seg["to"], list) else (dur if seg["to"] == "end" else seg["to"]))
        plan.append((t0, t1, seg["prog"], seg["style"]))
    mus = music(dur, plan) * db(a.music_db)
    mus *= duck(nar, 0.55)
    fade = np.ones(len(mus)); n_in, n_out = int(0.5 * SR), int(sfxcfg.get("fade_out", 1.4) * SR); fade[:n_in] = np.linspace(0, 1, n_in); fade[-n_out:] = np.linspace(1, 0, n_out); mus *= fade
    # --- effects
    fx = np.zeros(len(nar) + SR * 3)
    shots = cues["shots"]
    for i, (sid, t0, t1) in enumerate(shots):
        if i == 0: continue
        if any(abs(w[0] - t0) < 0.45 for w in cues["whip"]): continue                        # a whip cue already covers this cut
        put(fx, SFX["whoosh_soft"]({}), t0 - 0.12, -24 if sid.startswith(("map", "mz")) or True else -26)
    for (t, d) in cues["whip"]: put(fx, SFX["whip"]({}), t - 0.22, -16)
    for (t, pk, d) in cues["flash"]:
        if pk >= 0.7: put(fx, SFX["shutter"]({}), t, -19)
        elif pk >= 0.45: put(fx, SFX["swish"]({}), t - 0.02, -26)
        else: put(fx, SFX["stamp"]({}), t, -17)
    for (t0, t1) in cues["hud"]:
        n = max(3, int((t1 - t0) * 9))
        for j in range(n): put(fx, tick(1500 + 35 * j), t0 + (t1 - t0) * (j + 1) / n, -31)
    for sid, t0, t1 in shots:
        if sid.startswith("map"): put(fx, SFX["route"]({"dur": min(1.4, (t1 - t0) * 0.45)}), t0 + 0.4, -23)
    for c in sfxcfg["cues"].get(a.chapter, []):
        if c["type"] == "ticks":
            t0 = W(*c["t0"]) if isinstance(c["t0"], list) else c["t0"]; t1 = (W(*c["t1"]) if isinstance(c["t1"], list) else c["t1"]) if "t1" in c else t0 + c["dur"]
            for j in range(c["n"]): put(fx, tick(1500 + 40 * j), t0 + (t1 - t0) * (j + 1) / c["n"], c["db"])
            continue
        t = (W(*c["at"]) if isinstance(c["at"], list) else c["at"]) + c.get("off", 0)
        put(fx, SFX[c["type"]](c), t, c["db"])
    fx = fx[: len(nar)] * db(1)
    mix = nar + mus + fx
    sp = fftconvolve(nar ** 2, np.ones(int(0.05 * SR)) / int(0.05 * SR), "same") > 1e-4
    r = lambda x, m: 10 * np.log10(np.mean(x[m] ** 2) + 1e-12)
    print(f"  during speech: narration {r(nar, sp):.1f} dB  music {r(mus, sp):.1f} dB  fx {r(fx, sp):.1f} dB   | outside speech: music {r(mus, ~sp):.1f} dB  fx {r(fx, ~sp):.1f} dB")
    pk = np.max(np.abs(mix)); print(f"{a.chapter}: dur {dur:.2f}s  narration peak {np.max(np.abs(nar)):.3f}  music rms {np.sqrt(np.mean(mus ** 2)):.4f}  fx peak {np.max(np.abs(fx)):.3f}  mix peak {pk:.3f}")
    if pk > 0.97: mix = np.tanh(mix * 0.9)
    st = np.stack([mix, mix], 1)
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())
main()
