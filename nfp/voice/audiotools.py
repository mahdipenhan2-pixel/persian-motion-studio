"""NFP Voice Engine - the audio tools it relies on: ffprobe / ffmpeg (already installed; nothing is downloaded) and
small standard-library measurements of 16-bit mono PCM.

    probe(path)        -> {"format", "codec", "rate", "channels", "bits", "duration", "frames"}   (any WAV)
    loudness(path)     -> {"integrated_lufs", "true_peak_dbtp"} through ffmpeg ebur128 (EBU R128, true peak)
    pcm_stats(pcm, rate) / silences(...)   peak, clipping, RMS and silent spans of 16-bit mono PCM
If ffmpeg / ffprobe is missing, AudioToolError says so; there is no unapproved substitute.
"""
import array
import json
import math
import re
import shutil
import subprocess
import sys


class AudioToolError(ValueError):
    pass


def tool(name):
    p = shutil.which(name)
    if not p:
        raise AudioToolError(f"'{name}' is not installed: audio conversion / loudness measurement needs FFmpeg "
                             "(install it; the Voice Engine does not use a substitute)")
    return p


def available():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AudioToolError(f"{str(cmd[0]).rsplit('/', 1)[-1]} failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-400:]}")
    return r


def probe(path):
    """Format of any audio file; refuses anything that is not a WAV container with one audio stream."""
    r = subprocess.run([tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise AudioToolError(f"{path}: unreadable audio file ({(r.stderr or '').strip()[-200:] or 'ffprobe failed'})")
    d = json.loads(r.stdout or "{}")
    fmt = (d.get("format") or {}).get("format_name", "")
    streams = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    if "wav" not in fmt.split(","):
        raise AudioToolError(f"{path}: not a WAV file (container '{fmt or 'unknown'}'); only WAV input is supported")
    if len(streams) != 1:
        raise AudioToolError(f"{path}: expected exactly one audio stream, found {len(streams)}")
    s = streams[0]
    rate = int(s.get("sample_rate") or 0)
    dur = float(s.get("duration") or d["format"].get("duration") or 0)
    bits = int(s.get("bits_per_sample") or s.get("bits_per_raw_sample") or 0)
    if rate <= 0 or int(s.get("channels") or 0) <= 0:
        raise AudioToolError(f"{path}: invalid sample rate / channel count")
    return {"format": "wav", "codec": s.get("codec_name"), "rate": rate, "channels": int(s["channels"]), "bits": bits,
            "duration": round(dur, 6), "frames": int(s.get("duration_ts") or round(dur * rate))}


_I = re.compile(r"I:\s+(-?[\d.]+|-inf|nan)\s+LUFS")
_TP = re.compile(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf|nan)\s+dBFS", re.S)


def loudness(path):
    """Integrated loudness (LUFS) and true peak (dBTP, 4x oversampled) of a file, EBU R128 (ffmpeg ebur128)."""
    r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    if r.returncode != 0:
        raise AudioToolError(f"{path}: loudness measurement failed: {r.stderr.strip()[-300:]}")
    summary = r.stderr[r.stderr.rfind("Summary:"):]
    i, tp = _I.search(summary), _TP.search(summary)
    if not i or not tp:
        raise AudioToolError(f"{path}: could not read the ebur128 summary")
    num = lambda s: None if s in ("nan", "-inf") or float(s) <= -70 else float(s)  # noqa: E731  (below the absolute gate)
    return {"integrated_lufs": num(i.group(1)), "true_peak_dbtp": num(tp.group(1))}


def samples(pcm):
    a = array.array("h")
    a.frombytes(pcm)
    if sys.byteorder == "big":
        a.byteswap()
    return a


def dbfs(v):
    return round(20 * math.log10(v / 32768), 2) if v > 0 else None


def pcm_stats(pcm, rate, clip_level=32767):
    a = samples(pcm)
    n = len(a)
    if not n:
        return {"frames": 0, "peak": 0, "peak_dbfs": None, "clipped": 0, "clipped_ratio": 0.0, "rms_dbfs": None}
    peak = max(max(a), -min(a))
    clipped = sum(1 for x in a if x >= clip_level or x <= -clip_level - 1)
    rms = math.sqrt(sum(x * x for x in a) / n)
    return {"frames": n, "peak": peak, "peak_dbfs": dbfs(peak), "clipped": clipped, "clipped_ratio": round(clipped / n, 6),
            "rms_dbfs": dbfs(rms)}


def silences(pcm, rate, threshold_dbfs=-50.0, window=0.01):
    """Silent spans [(start s, end s)] - windows whose RMS is below threshold_dbfs."""
    a = samples(pcm)
    n = max(1, int(rate * window))
    lim = 32768 * 10 ** (threshold_dbfs / 20)
    spans, start = [], None
    for i in range(0, len(a), n):
        seg = a[i:i + n]
        quiet = math.sqrt(sum(x * x for x in seg) / len(seg)) < lim
        if quiet and start is None:
            start = i
        elif not quiet and start is not None:
            spans.append((round(start / rate, 3), round(i / rate, 3)))
            start = None
    if start is not None:
        spans.append((round(start / rate, 3), round(len(a) / rate, 3)))
    return spans
