"""NFP Voice Engine - audio quality control (nfp.voice.qc/1). Every check is recorded with its value, its limit and
a level: ok | warning | error. Errors are things a video cannot be built from (unreadable, wrong format, empty,
silent, heavy clipping, wrong duration); everything a human might accept is a WARNING. Thresholds are settings.

    t = thresholds({"clip_error_ratio": 0.01})
    r = check_file(path, rate, t, planned={...})     # {"id", "file", "status", "checks": [...]}
"""
import wave

from .audiotools import AudioToolError, available, loudness, pcm_stats, silences

SCHEMA = "nfp.voice.qc/1"
DEFAULTS = {
    "min_duration_s": 0.3,           # the Stage 2 core's own bounds per sentence
    "max_duration_s": 60.0,
    "silent_peak_dbfs": -60.0,       # peak below this = no usable sound at all -> error
    "clip_error_ratio": 0.001,       # share of samples at full scale: above -> error, any -> warning
    "peak_warn_dbfs": -0.3,          # sample peak above this -> warning (no headroom)
    "true_peak_warn_dbtp": -1.0,     # EBU R128 true peak above this -> warning
    "weak_lufs": -40.0,              # integrated loudness below this -> warning (very weak, not rejected)
    "loudness_tolerance_lu": 2.0,    # after normalization: |I - target| above this -> warning
    "silence_dbfs": -50.0,           # what counts as silence for the span checks
    "lead_extra_warn_s": 1.0,        # leading silence longer than the planned pause by more than this -> warning
    "tail_extra_warn_s": 1.0,
    "internal_silence_warn_s": 2.0,  # a silent span inside the speech longer than this -> warning
    "duration_tolerance_samples": 2,  # produced length vs expected (body + pauses) -> error above this
}


class QCError(ValueError):
    pass


def thresholds(d=None):
    t = dict(DEFAULTS)
    t.update(d or {})
    extra = sorted(set(t) - set(DEFAULTS))
    if extra:
        raise QCError(f"qc: unknown threshold(s) {', '.join(extra)}")
    for k, v in t.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise QCError(f"qc.{k} must be a number")
    if not 0 < t["min_duration_s"] < t["max_duration_s"]:
        raise QCError("qc: min_duration_s must be > 0 and < max_duration_s")
    if not 0 <= t["clip_error_ratio"] <= 1:
        raise QCError("qc.clip_error_ratio must be 0..1")
    return t


def _c(check, level, value, limit, message):
    return {"check": check, "level": level, "value": value, "limit": limit, "message": message}


def check_file(path, rate, t, sid=None, planned=None):
    """planned (optional): pause_before_ms, pause_after_ms, body_frames (expected speech frames), target_lufs."""
    planned = planned or {}
    out = {"id": sid, "file": str(path), "checks": []}
    C = out["checks"]
    try:
        with wave.open(str(path), "rb") as w:
            ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            pcm = w.readframes(n)
    except (wave.Error, EOFError, OSError) as e:
        C.append(_c("readable", "error", None, None, f"unreadable or broken WAV: {e}"))
        return _status(out)
    C.append(_c("readable", "ok", None, None, "readable PCM WAV"))
    fmt_ok = (ch, sw, fr) == (1, 2, rate)
    C.append(_c("format", "ok" if fmt_ok else "error", {"channels": ch, "bits": 8 * sw, "rate": fr},
                {"channels": 1, "bits": 16, "rate": rate}, "mono 16-bit at the run's rate" if fmt_ok else
                "wrong sample rate / channel count / bit depth"))
    if not fmt_ok:
        return _status(out)
    dur = n / rate
    C.append(_c("duration", "ok" if t["min_duration_s"] <= dur <= t["max_duration_s"] else "error", round(dur, 6),
                [t["min_duration_s"], t["max_duration_s"]], "empty / too short / too long" if not
                t["min_duration_s"] <= dur <= t["max_duration_s"] else "length within bounds"))
    if n == 0:
        return _status(out)
    st = pcm_stats(pcm, rate)
    silent = st["peak_dbfs"] is None or st["peak_dbfs"] < t["silent_peak_dbfs"]
    C.append(_c("signal", "error" if silent else "ok", st["peak_dbfs"], t["silent_peak_dbfs"],
                "no usable sound (silent or nearly silent file)" if silent else "signal present"))
    if silent:
        return _status(out)
    lvl = "error" if st["clipped_ratio"] > t["clip_error_ratio"] else ("warning" if st["clipped"] else "ok")
    C.append(_c("clipping", lvl, {"samples": st["clipped"], "ratio": st["clipped_ratio"]}, t["clip_error_ratio"],
                {"ok": "no clipped samples", "warning": "a few samples at full scale",
                 "error": "clipping: too many samples at full scale"}[lvl]))
    C.append(_c("peak", "warning" if st["peak_dbfs"] > t["peak_warn_dbfs"] else "ok", st["peak_dbfs"], t["peak_warn_dbfs"],
                "sample peak without headroom" if st["peak_dbfs"] > t["peak_warn_dbfs"] else "sample peak with headroom"))
    if available():
        try:
            L = loudness(path)
        except AudioToolError as e:
            L = None
            C.append(_c("loudness", "warning", None, None, f"loudness not measured: {e}"))
        if L is not None:
            I, tp = L["integrated_lufs"], L["true_peak_dbtp"]
            if I is None:
                C.append(_c("loudness", "warning", None, t["weak_lufs"], "integrated loudness not measurable (too short / quiet)"))
            else:
                weak = I < t["weak_lufs"]
                tgt = planned.get("target_lufs")
                off = tgt is not None and abs(I - tgt) > t["loudness_tolerance_lu"]
                C.append(_c("loudness", "warning" if weak or off else "ok", I,
                            {"weak_below": t["weak_lufs"], "target": tgt, "tolerance": t["loudness_tolerance_lu"]},
                            "very weak voice" if weak else (f"{I} LUFS is off the target {tgt}" if off else "loudness fine")))
            if tp is not None:
                C.append(_c("true_peak", "warning" if tp > t["true_peak_warn_dbtp"] else "ok", tp, t["true_peak_warn_dbtp"],
                            "true peak above the limit" if tp > t["true_peak_warn_dbtp"] else "true peak fine"))
    else:
        C.append(_c("loudness", "warning", None, None, "loudness / true peak not measured: ffmpeg is not installed"))
    sp = silences(pcm, rate, t["silence_dbfs"])
    lead = sp[0][1] if sp and sp[0][0] == 0 else 0.0
    tail = round(dur - sp[-1][0], 3) if sp and abs(sp[-1][1] - round(dur, 3)) < 0.011 else 0.0
    pb, pa = planned.get("pause_before_ms", 0) / 1000, planned.get("pause_after_ms", 0) / 1000
    C.append(_c("leading_silence", "warning" if lead - pb > t["lead_extra_warn_s"] else "ok", {"measured": lead, "planned": pb},
                t["lead_extra_warn_s"], "unexpected long silence at the start" if lead - pb > t["lead_extra_warn_s"] else "start fine"))
    C.append(_c("trailing_silence", "warning" if tail - pa > t["tail_extra_warn_s"] else "ok", {"measured": tail, "planned": pa},
                t["tail_extra_warn_s"], "unexpected long silence at the end" if tail - pa > t["tail_extra_warn_s"] else "end fine"))
    inner = [round(b - a, 3) for a, b in sp if a > 0 and abs(b - round(dur, 3)) >= 0.011]
    longest = max(inner, default=0.0)
    C.append(_c("internal_silence", "warning" if longest > t["internal_silence_warn_s"] else "ok", longest,
                t["internal_silence_warn_s"], "unusually long silence inside the speech" if longest > t["internal_silence_warn_s"]
                else "no unusual silence inside"))
    if "body_frames" in planned:
        want = planned["body_frames"] + int(round(pb * rate)) + int(round(pa * rate))
        bad = abs(n - want) > t["duration_tolerance_samples"]
        C.append(_c("length_vs_expected", "error" if bad else "ok", n, want, f"produced {n} frames, expected {want} "
                    "(speech + planned pauses)" if bad else "length = speech + planned pauses"))
    return _status(out)


def _status(out):
    lv = [c["level"] for c in out["checks"]]
    out["status"] = "error" if "error" in lv else ("warning" if "warning" in lv else "ok")
    return out


def report(files, t):
    s = {"ok": 0, "warning": 0, "error": 0}
    for f in files:
        s[f["status"]] += 1
    return {"schema": SCHEMA, "thresholds": t, "files": files, "summary": s}
