"""Chapter assembly for long documentaries (the locked core handles <=40 sentences / 180 s per run, so a 13-minute
film is built from chapters). This module only does arithmetic and file joining; it never touches the core.

Sync rule: every chapter's narration is padded with silence to a WHOLE NUMBER OF VIDEO FRAMES, so the video chunk
(frames) and the audio chunk (samples) of every chapter have exactly the same length. The global offset of a chapter
is then the sum of the padded lengths before it, and word/sentence times are shifted by exactly that offset."""
import math
import wave

FPS = 30


def samples_per_frame(rate):
    if rate % FPS:
        raise ValueError(f"sample rate {rate} is not a multiple of {FPS}; cannot align audio to whole frames")
    return rate // FPS


def padded_frames(duration_sec, rate):
    """whole frames needed to contain a chapter whose narration lasts duration_sec"""
    return int(math.ceil(round(duration_sec * rate) / samples_per_frame(rate)))


def plan(durations, rate):
    """-> list of {frames, samples, offset_sec, offset_frames} per chapter"""
    out, f0 = [], 0
    spf = samples_per_frame(rate)
    for d in durations:
        fr = padded_frames(d, rate)
        out.append({"frames": fr, "samples": fr * spf, "offset_frames": f0, "offset_sec": f0 / FPS})
        f0 += fr
    return out


def concat_wavs(paths, plan_rows, out_path):
    """Join chapter narrations (each padded to its planned frame count) into one wav."""
    rate = None
    with wave.open(str(out_path), "wb") as o:
        for p, row in zip(paths, plan_rows):
            with wave.open(str(p), "rb") as w:
                if rate is None:
                    rate = w.getframerate(); o.setnchannels(w.getnchannels()); o.setsampwidth(w.getsampwidth()); o.setframerate(rate)
                elif w.getframerate() != rate:
                    raise ValueError("chapters have different sample rates")
                data = w.readframes(w.getnframes()); n = w.getnframes()
                if n > row["samples"]:
                    raise ValueError("chapter audio longer than its planned slot")
                o.writeframes(data + b"\x00" * (w.getsampwidth() * w.getnchannels() * (row["samples"] - n)))
    return rate


def shift_timing(timing, offset_sec):
    """copy of a core timing.json with every absolute time moved by offset_sec"""
    import copy
    t = copy.deepcopy(timing)
    for s in t["sentences"]:
        s["offset"] = round(s["offset"] + offset_sec, 6)
        for w in s["words"]:
            for k in ("abs_start", "abs_end"):
                if w.get(k) is not None:
                    w[k] = round(w[k] + offset_sec, 6)
    return t


def srt_time(t):
    ms = int(round(max(0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def merged_srt(shifted_timings):
    rows, n = [], 0
    for t in shifted_timings:
        S = t["sentences"]
        for i, s in enumerate(S):
            timed = [w for w in s["words"] if w["abs_start"] is not None]
            c0 = max(s["offset"], timed[0]["abs_start"] - 0.05)
            c1 = timed[-1]["abs_end"] + 0.15
            if i + 1 < len(S):
                c1 = min(c1, S[i + 1]["offset"] - 0.02)
            n += 1
            rows.append(f"{n}\n{srt_time(c0)} --> {srt_time(max(c1, c0 + 0.2))}\n{s['text']}\n")
    return "\n".join(rows)
