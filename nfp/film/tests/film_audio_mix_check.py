#!/usr/bin/env python3
"""Film + Timeline T5 - music and sound effects (Timeline "audio" clips) mixed offline under the narration
(engine/timeline_bridge.py _audio), measured on the composed page's audio and on a REAL rendered MP4:
  the music is in the mix at its gain_db (the difference to the unmixed narration measures -24 dB +- 1 dB against the
  source file), its fade-in / fade-out are there, the sound effect is at its frame and its own gain; the narration stays
  dominant (>= 15 dB above the music where it speaks) and sample-exact where no clip plays; nothing clips (peak
  <= -1 dBFS + rounding); length, rate, channels unchanged; audio_mix.json records every clip;
  backward compatibility: a timeline with an audio track but no audio clip, and a project without a timeline, give a
  byte-identical narration.wav and page;
  the real HyperFrames render (offline, local GSAP) carries the music: the MP4's audio after the last word is the music
  bed (not silence), and before it is the narration.
  python3 nfp/film/tests/film_audio_mix_check.py --gsap <gsap.min.js> --fonts <woff2 dir> --work <dir outside the repository>
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path[:0] = [str(FILM / "engine"), str(HERE), str(ROOT / "nfp"), str(ROOT / "scripts")]
from film_equivalence_check import CDN   # noqa: E402
import film_timeline_check as FT         # noqa: E402

RESULTS = []
FIX = HERE / "fixtures" / "neutral-en"
HF = "0.9.83"
BROWSER = "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pcm(path):
    with wave.open(str(path), "rb") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
        return a.reshape(-1, w.getnchannels()).mean(axis=1) if w.getnchannels() > 1 else a, w.getframerate(), w.getnchannels()


def rms_db(a):
    r = float(np.sqrt(np.mean(a * a))) if a.size else 0.0
    return 20 * np.log10(r / 32768) if r > 0 else -200.0


def asset(aid, f, dur):
    return {"id": aid, "kind": "audio", "local_path": f"media/{Path(f).name}", "sha256": sha(f), "width": None, "height": None, "duration": dur,
            "source_url": None, "author": "NFP test (generated)", "license": "original", "license_url": None, "retrieved_at": "2026-11-26",
            "modifications": "none", "license_verified": True, "attribution": "Generated for the NFP tests", "restrictions": [], "real_person": False}


def project(work, name, clips):
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FIX, d)
    (d / "media").mkdir()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "aevalsrc='0.25*sin(2*PI*220*t)+0.18*sin(2*PI*277.2*t)+0.15*sin(2*PI*329.6*t)':s=48000:c=stereo:d=16",
                    str(d / "media" / "bed.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=c=pink:r=48000:a=0.6:d=0.7", "-af",
                    "highpass=f=900,afade=t=in:d=0.15,afade=t=out:st=0.25:d=0.45", "-ac", "2", str(d / "media" / "whoosh.wav")], check=True)
    (d / "assets.json").write_text(json.dumps({"schema": "nfp.assets/1", "assets": [asset("bed", d / "media" / "bed.wav", 16.0),
                                                                                     asset("whoosh", d / "media" / "whoosh.wav", 0.7)]}), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps({"schema": "nfp.timeline/1", "fps": 30, "duration": 450, "mode": "final",
                                                 "tracks": [{"id": "music", "kind": "audio"}, {"id": "sfx", "kind": "audio"}],
                                                 "clips": clips}), encoding="utf-8")
    pj = json.loads((d / "project.json").read_text(encoding="utf-8"))
    pj["timeline"] = {"file": "timeline.json", "assets": "assets.json"}
    (d / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


MUSIC = {"id": "bed", "track": "music", "kind": "audio", "start": 0, "end": 450, "asset": "bed", "fade_in": 60, "fade_out": 45}
SFX = {"id": "hit", "track": "sfx", "kind": "audio", "start": 300, "end": 321, "asset": "whoosh", "gain_db": -12}


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    fonts = Path(a.fonts).resolve()

    print("== backward compatibility")
    b0 = work / "b-plain"
    FT.compose_dir(FIX, b0, fonts)
    e = project(work, "empty-audio", [])
    be = work / "b-empty"
    FT.compose_dir(e, be, fonts)
    check(sha(b0 / "story" / "narration.wav") == sha(be / "story" / "narration.wav") and not (be / "audio_mix.json").exists()
          and (b0 / "story" / "index.html").read_text(encoding="utf-8") == (be / "story" / "index.html").read_text(encoding="utf-8"),
          "a timeline with an audio track but no audio clip: narration.wav and the page byte-identical to the project without a timeline")

    print("\n== music + a sound effect mixed")
    m = project(work, "mixed", [MUSIC, SFX])
    bm = work / "b-mixed"
    _, _, timing = FT.compose_dir(m, bm, fonts)
    x, rate, ch = pcm(bm / "story" / "narration.wav")
    o, rate0, ch0 = pcm(b0 / "story" / "narration.wav")
    check((rate, ch, len(x)) == (rate0, ch0, len(o)), f"rate {rate} Hz, {ch} channel(s), {len(x)} samples: unchanged")
    mix = json.loads((bm / "audio_mix.json").read_text(encoding="utf-8"))
    check([c["clip"] for c in mix["clips"]] == ["bed", "hit"] and mix["clips"][0]["gain_db"] == -24.0 and mix["clips"][1]["gain_db"] == -12.0,
          f"audio_mix.json: {[(c['clip'], c['gain_db'], c['start_s']) for c in mix['clips']]}")
    d = x - o
    src, srate, _ = pcm(m / "media" / "bed.wav")
    s = lambda t0, t1: slice(int(t0 * rate), int(t1 * rate))              # noqa: E731
    ref = rms_db(src[int(4 * srate):int(8 * srate)])
    got = rms_db(d[s(4, 8)])
    check(abs((got - ref) - (-24.0)) <= 1.0, f"music level in the mix: {got:.1f} dBFS vs its source {ref:.1f} dBFS = {got - ref:+.1f} dB (gain -24)")
    check(rms_db(d[s(0, 0.4)]) < got - 6 and rms_db(d[s(14.2, 14.95)]) < got - 3, "fade-in at the start and fade-out at the end are there")
    mo = project(work, "music-only", [MUSIC])
    bo = work / "b-music-only"
    FT.compose_dir(mo, bo, fonts)
    y0, _, _ = pcm(bo / "story" / "narration.wav")
    fx = x - y0                                                          # the sound effect alone
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(m / "media" / "whoosh.wav"), "-af", "pan=mono|c0=0.5*c0+0.5*c1", "-ar", str(rate),
                    str(work / "whoosh-ref.wav")], check=True)                  # the source at the mix's rate (no energy above rate / 2)
    wsrc, wrate, _ = pcm(work / "whoosh-ref.wav")
    on = np.nonzero(np.abs(fx) > 30)[0]
    lvl = rms_db(fx[s(10.0, 10.7)]) - rms_db(wsrc[: int(0.7 * wrate)])
    check(on.size and abs(on[0] / rate - 10.0) <= 1 / 30 and abs(lvl - (-12.0)) <= 1.0 and not np.abs(fx[: int(9.99 * rate)]).any(),
          f"the sound effect alone: starts at {on[0] / rate if on.size else None:.3f} s (frame 300 = 10.000 s), level {lvl:+.1f} dB vs its source (gain -12), nothing before it")
    speech = [(r["abs_start"], r["abs_end"]) for t in timing["sentences"] for r in t["words"] if r["abs_start"] is not None]
    sp = np.concatenate([o[s(a0, a1)] for a0, a1 in speech])
    mu = np.concatenate([d[s(a0, a1)] for a0, a1 in speech if a0 > 2.2 and not 9.9 < a0 < 10.8])
    check(rms_db(sp) - rms_db(mu) >= 15, f"narration dominant: {rms_db(sp):.1f} dBFS narration vs {rms_db(mu):.1f} dBFS music where it speaks")
    peak = float(np.abs(x).max()) / 32768
    check(peak <= 0.891 + 2 / 32768, f"no clipping: peak {20 * np.log10(peak):.2f} dBFS (limiter at -1 dBFS)")

    hot = project(work, "hot", [dict(MUSIC, gain_db=6), dict(SFX, gain_db=6)])
    bh = work / "b-hot"
    FT.compose_dir(hot, bh, fonts)
    xh, _, _ = pcm(bh / "story" / "narration.wav")
    mh = json.loads((bh / "audio_mix.json").read_text(encoding="utf-8"))
    check(mh["limited"] and float(np.abs(xh).max()) / 32768 <= 0.891 + 2 / 32768 and not mix["limited"],
          f"music and effect at +6 dB would clip: the limiter acts (peak {20 * np.log10(float(np.abs(xh).max()) / 32768):.2f} dBFS); "
          "the normal mix above was not limited")

    print("\n== a real render carries the mix")
    page = (bm / "story" / "index.html").read_text(encoding="utf-8")
    rdir = bm / "render-copy"
    shutil.copytree(bm / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(a.gsap, rdir / "gsap.min.js")
    env = dict(os.environ, npm_config_offline="true", HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1", HYPERFRAMES_BROWSER_PATH=BROWSER)
    mp4 = bm / "story.mp4"
    r = subprocess.run(["npx", "--yes", f"hyperframes@{HF}", "render", "--output", str(mp4), "--fps", "30", "--quality", "standard"],
                       cwd=rdir, env=env, capture_output=True, text=True)
    check(r.returncode == 0 and mp4.exists(), f"HyperFrames {HF} render (offline): exit {r.returncode}")
    if mp4.exists():
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(work / "mp4.wav")], check=True)
        y, _, _ = pcm(work / "mp4.wav")
        last = max(a1 for _, a1 in speech)
        tail, rate2 = y[int((last + 0.4) * 48000):int(14.0 * 48000)], 48000
        check(rms_db(tail) > -50, f"after the last word ({last:.2f} s) the MP4 carries the music bed: {rms_db(tail):.1f} dBFS (not silence)")
        so = [y[int(a0 * rate2):int(a1 * rate2)] for a0, a1 in speech]
        check(rms_db(np.concatenate(so)) - rms_db(tail) >= 15, "in the MP4 the narration stays >= 15 dB above the bed")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL FILM AUDIO MIX TESTS PASSED" if not f else "FILM AUDIO MIX TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
