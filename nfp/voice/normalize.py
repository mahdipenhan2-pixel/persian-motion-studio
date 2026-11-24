"""NFP Voice Engine - audio normalization: any valid WAV -> the engine's format, with an optional loudness match.

    s = settings({"target_lufs": -20})                 # validated, complete settings (defaults below)
    pcm, info = convert(src_path, rate)                # mono 16-bit PCM at `rate` (FFmpeg); input specs in info
    pcm, info = match_loudness(pcm, rate, s)           # one constant gain (no compressor / limiter)

Rules:
  * input: a WAV file (any PCM / float sample format, any rate, any channel count); anything else is refused;
  * format: mono (FFmpeg's channel average), 16-bit PCM, the run's sample rate (FFmpeg's resampler); the duration
    stays the same within two samples - checked, an error otherwise;
  * loudness: the integrated loudness (EBU R128, ffmpeg ebur128) is moved to target_lufs with ONE constant gain,
    limited so that the true peak stays <= true_peak_max and the gain within +-max_gain_db; whatever limited it is
    recorded. Silence stays silence (0 x gain = 0), so planned pauses and their lengths are untouched;
  * pauses are added by the caller AFTER normalization, so they are exact.
"""
import math
import os
import subprocess
import tempfile

from .audiotools import AudioToolError, loudness, probe, samples, tool
from .providers.base import write_wav

SCHEMA = "nfp.voice.normalize/1"
DEFAULTS = {"loudness": True, "target_lufs": -20.0, "true_peak_max": -1.5, "max_gain_db": 20.0}


def settings(d=None):
    s = dict(DEFAULTS)
    s.update(d or {})
    extra = sorted(set(s) - set(DEFAULTS))
    if extra:
        raise AudioToolError(f"normalize: unknown setting(s) {', '.join(extra)}")
    if not isinstance(s["loudness"], bool):
        raise AudioToolError("normalize.loudness must be true or false")
    for k, lo, hi in (("target_lufs", -40.0, -5.0), ("true_peak_max", -12.0, 0.0), ("max_gain_db", 0.0, 40.0)):
        if not isinstance(s[k], (int, float)) or isinstance(s[k], bool) or not lo <= s[k] <= hi:
            raise AudioToolError(f"normalize.{k} must be a number {lo}..{hi}")
        s[k] = float(s[k])
    return s


def convert(src, rate):
    """Any WAV -> mono 16-bit PCM bytes at `rate`; returns (pcm, info with the input specs)."""
    spec = probe(src)
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", str(src), "-map", "0:a:0", "-ac", "1", "-ar", str(rate),
                        "-sample_fmt", "s16", "-f", "s16le", "-"], capture_output=True)
    if r.returncode != 0:
        raise AudioToolError(f"{src}: conversion failed: {r.stderr.decode(errors='replace').strip()[-300:]}")
    pcm = r.stdout
    frames = len(pcm) // 2
    out_dur = frames / rate
    if spec["duration"] <= 0 or abs(out_dur - spec["duration"]) > 2 / rate + 2 / spec["rate"]:
        raise AudioToolError(f"{src}: duration changed in conversion ({spec['duration']}s -> {out_dur:.6f}s)")
    return pcm, {"input": spec, "converted": {"rate": rate, "channels": 1, "bits": 16, "frames": frames,
                                              "duration": round(out_dur, 6)},
                 "resampled": spec["rate"] != rate, "downmixed": spec["channels"] != 1,
                 "requantized": not (spec["codec"] == "pcm_s16le" and spec["bits"] == 16)}


def measure(pcm, rate):
    fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="nfp-voice-")
    os.close(fd)
    try:
        write_wav(tmp, pcm, rate)
        return loudness(tmp)
    finally:
        os.unlink(tmp)


def apply_gain(pcm, gain_db):
    a = samples(pcm)
    k = 10 ** (gain_db / 20)
    clamped = 0
    for i, x in enumerate(a):
        y = int(round(x * k))
        if y > 32767:
            y, clamped = 32767, clamped + 1
        elif y < -32768:
            y, clamped = -32768, clamped + 1
        a[i] = y
    return a.tobytes(), clamped


def match_loudness(pcm, rate, s):
    """One constant gain towards target_lufs, limited by true_peak_max and max_gain_db; every limit is recorded."""
    before = measure(pcm, rate)
    info = {"target_lufs": s["target_lufs"], "before": before, "gain_db": 0.0, "limited_by": None,
            "clamped_samples": 0, "after": before}             # complete record in every case
    if before["integrated_lufs"] is None:
        info["limited_by"] = "not measurable (silent or too short for EBU R128 gating)"
        return pcm, info
    g = s["target_lufs"] - before["integrated_lufs"]
    if before["true_peak_dbtp"] is not None and before["true_peak_dbtp"] + g > s["true_peak_max"]:
        g, info["limited_by"] = s["true_peak_max"] - before["true_peak_dbtp"], "true_peak_max"
    if abs(g) > s["max_gain_db"]:
        g, info["limited_by"] = math.copysign(s["max_gain_db"], g), "max_gain_db"
    g = round(g, 2)
    out, clamped = apply_gain(pcm, g) if g else (pcm, 0)
    info.update(gain_db=g, clamped_samples=clamped, after=measure(out, rate) if g else before)
    return out, info
