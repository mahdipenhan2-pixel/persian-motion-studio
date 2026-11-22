#!/usr/bin/env python3
"""Synthesise the sound design for the documentary-style experiment (numpy/scipy only: no samples, no third-party audio,
no network, no TTS). Reads sfx.json cues, anchors them on the real word times, mixes them under the approved narration.
usage: make_sfx.py <sfx.json> <words.json> <narration.wav> <out.wav> [project.json]
With project.json the word anchors use script word indices (words the aligner missed take the next matched word's time)."""
import json, sys, wave
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
RNG = np.random.default_rng(20261122)


def db(x): return 10 ** (x / 20)
def t_axis(d): return np.arange(int(d * SR)) / SR
def norm(x): return x / (np.max(np.abs(x)) + 1e-9)
def lp(x, f): return sosfilt(butter(4, f, "low", fs=SR, output="sos"), x)
def hp(x, f): return sosfilt(butter(4, f, "high", fs=SR, output="sos"), x)
def bp(x, a, b): return sosfilt(butter(3, [a, b], "band", fs=SR, output="sos"), x)


def reverb(x, tail=0.9, mix=0.28):
    n = int(tail * SR); ir = RNG.standard_normal(n) * np.exp(-np.linspace(0, 6.5, n)); ir = lp(ir, 5200)
    wet = fftconvolve(x, ir / np.sqrt(np.sum(ir ** 2)))[: len(x) + n]
    out = np.zeros(len(wet)); out[: len(x)] += x * (1 - mix); out += wet * mix * 1.2
    return out


def sweep_noise(dur, f0, f1, q=2.2, shape="bell"):
    """band-passed noise whose centre frequency glides f0 -> f1 (block-wise, filter state carried over)"""
    n = int(dur * SR); noise = RNG.standard_normal(n); out = np.zeros(n); B = 512; zi = None
    for i in range(0, n, B):
        u = i / n; fc = f0 * (f1 / f0) ** u; bw = fc / q
        sos = butter(2, [max(40, fc - bw), min(SR / 2 - 100, fc + bw)], "band", fs=SR, output="sos")
        z = np.zeros((sos.shape[0], 2)) if zi is None or zi.shape[0] != sos.shape[0] else zi
        seg, zi = sosfilt(sos, noise[i:i + B], zi=z); out[i:i + B] = seg
    u = np.linspace(0, 1, n)
    env = np.sin(np.pi * u) ** 2 if shape == "bell" else (u ** 2 * (1 - u) ** 0.4 if shape == "rise" else (1 - u) ** 1.5 * np.minimum(1, u * 40))
    return norm(out) * env


def click(f=2400, d=0.03, amp=1.0):
    t = t_axis(d); return amp * (np.sin(2 * np.pi * f * t) * np.exp(-t * 180) + hp(RNG.standard_normal(len(t)), 3000) * np.exp(-t * 420) * 0.7)


def shutter():
    a = click(1500, 0.05); b = click(900, 0.06, 0.8); out = np.zeros(int(0.16 * SR)); out[: len(a)] += a; s = int(0.055 * SR); out[s:s + len(b)] += b[: len(out) - s]
    return norm(out)


def boom(d=1.5, f0=120, f1=38):
    t = t_axis(d); f = f1 + (f0 - f1) * np.exp(-t * 7); ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 2.6) + lp(RNG.standard_normal(len(t)), 240) * np.exp(-t * 14) * 0.6
    return norm(reverb(x, 1.1, 0.22))[: int(d * SR)]


def ping(d=1.4):
    t = t_axis(d); x = (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1976 * t) + 0.25 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 3.4) * np.minimum(1, t * 600)
    return norm(reverb(x, 1.2, 0.35))


def stamp():
    t = t_axis(0.5); x = np.sin(2 * np.pi * (80 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 11) + lp(RNG.standard_normal(len(t)), 1800) * np.exp(-t * 60) * 0.8
    return norm(reverb(x, 0.6, 0.2))


def fit(x, n):
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def slam():
    n = int(1.4 * SR)
    return norm(fit(boom(1.4, 150, 42), n) + 0.8 * fit(stamp(), n) + 0.5 * fit(sweep_noise(0.25, 6000, 400, 1.2, "fall"), n))


def tick(f=1900):
    return norm(click(f, 0.035))


def rewind(d=1.0):
    n = int(d * SR); t = t_axis(d); ns = sweep_noise(d, 4200, 650, 1.6, "fall"); flut = 0.55 + 0.45 * np.sin(2 * np.pi * 34 * t)
    whine = np.sin(2 * np.pi * np.cumsum(1900 * (0.16) ** (t / d)) / SR) * (1 - t / d) * 0.35
    return norm(ns * flut + whine)[:n]


def heart():
    n = int(0.9 * SR); out = np.zeros(n)
    for off, a in ((0.0, 1.0), (0.3, 0.7)):
        t = t_axis(0.3); th = np.sin(2 * np.pi * 58 * t) * np.exp(-t * 16) * a; s = int(off * SR); out[s:s + len(t)] += th
    return norm(reverb(out, 0.5, 0.15))[:n]


def drone(d):
    t = t_axis(d); x = sum(a * np.sin(2 * np.pi * f * t + p) for f, a, p in ((55, 1.0, 0), (82.4, 0.55, 1.1), (110.2, 0.4, 2.0), (165, 0.18, 0.5)))
    x *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.11 * t) ; x += lp(RNG.standard_normal(len(t)), 420) * 0.25
    env = np.minimum(1, t / 1.6) * np.minimum(1, (d - t) / 1.4)
    return norm(x) * env


def route(d):
    t = t_axis(d); f = 420 * (3.4 ** (t / d)); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + 0.3 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)
    return norm(x * np.minimum(1, t * 40) * np.minimum(1, (d - t) * 18)) * 0.8


def paper(d):
    return norm(sweep_noise(d, 2200, 6500, 0.9, "fall") * 0.9)


def mix_cue(buf, x, at, gain_db):
    s = int(round(at * SR)); e = min(len(buf), s + len(x))
    if s < len(buf) and e > s: buf[s:e] += x[: e - s] * db(gain_db)


def at_time(c, words):
    a = c["at"]
    if isinstance(a, list):
        sid, kind, i = a; t = words[sid][i][1] if kind == "w" else words[sid][i][2]
    else: t = a
    return t + c.get("off", 0)


def inv_ease(p):  # power2.inOut inverse
    a, b = 0.0, 1.0
    for _ in range(30):
        m = (a + b) / 2; v = 4 * m ** 3 if m < .5 else 1 - (-2 * m + 2) ** 3 / 2
        a, b = (m, b) if v < p else (a, m)
    return b


def by_script_index(words, project):
    out = {}
    for sent in project["chapters"][0]["sentences"]:
        rows, j, res = words[sent["id"]], 0, []
        for w in sent["text"].split():
            if j < len(rows) and rows[j][0].strip() == w.strip(): res.append(list(rows[j])); j += 1
            else: res.append(None)
        nxt = rows[-1][2]
        for k in range(len(res) - 1, -1, -1):
            if res[k] is None: res[k] = [sent["text"].split()[k], nxt, nxt]
            else: nxt = res[k][1]
        out[sent["id"]] = res
    return out


def main():
    cues = json.load(open(sys.argv[1]))["cues"]; words = json.load(open(sys.argv[2]))
    if len(sys.argv) > 5: words = by_script_index(words, json.load(open(sys.argv[5])))
    with wave.open(sys.argv[3]) as w:
        nar = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768; nsr = w.getframerate()
    nar = np.interp(np.arange(int(len(nar) * SR / nsr)) / SR, np.arange(len(nar)) / nsr, nar)
    dur = len(nar) / SR; buf = np.zeros(int((dur + 2) * SR))
    for c in cues:
        ty, g = c["type"], c["db"]
        if ty == "ticks":
            n = c["n"]
            for i in range(1, n + 1): mix_cue(buf, tick(1500 + 40 * i), c["t0"] + (c["t1"] - c["t0"]) * inv_ease(i / n), g)
            continue
        t = at_time(c, words) if "at" in c else 0
        x = {"drone": lambda: drone(c["dur"]), "swell": lambda: sweep_noise(c["dur"], 150, 900, 0.7, "rise") * 0.8, "whoosh_up": lambda: sweep_noise(c["dur"], 300, 5200, 1.0),
             "whoosh_soft": lambda: sweep_noise(0.5, 900, 3200, 0.9), "whip": lambda: sweep_noise(0.5, 6000, 500, 0.8), "swish": lambda: sweep_noise(0.3, 2500, 7500, 1.3),
             "ping": ping, "shutter": shutter, "boom": boom, "tick_hi": lambda: tick(3000), "slam": slam, "stamp": stamp, "rewind": lambda: rewind(c["dur"]),
             "heart": heart, "route": lambda: route(c["dur"]), "paper": lambda: paper(c["dur"])}[ty]()
        if ty == "whip": t -= 0.2
        if ty == "boom" and False: pass
        mix_cue(buf, x, t, g)
    sfx = buf[: len(nar)] * db(-6)
    mixed = nar + sfx
    pk = np.max(np.abs(mixed)); mixed = np.tanh(mixed * 1.0) if pk > 0.95 else mixed
    print(f"narration peak {np.max(np.abs(nar)):.3f}  sfx peak {np.max(np.abs(sfx)):.3f}  mix peak {np.max(np.abs(mixed)):.3f}")
    st = np.stack([mixed, mixed], 1)
    with wave.open(sys.argv[4], "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())
main()
