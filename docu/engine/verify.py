"""Verify the rendered 16:9 MP4 (not just that a file exists): format, duration, audio, voice/caption sync,
motion (no long near-static stretches (film grain keeps the baseline above 0.5)), no black frames, plus a contact sheet for human review."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HL = (255, 214, 90)   # subtitle word highlight colour (see base.html)


def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True).stdout


def raw_frames(mp4, fps, w, h, vf="", pix="gray"):
    nb = 1 if pix == "gray" else 3
    out = sh(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},{vf}scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", pix, "-"])
    a = np.frombuffer(out, dtype=np.uint8)
    n = len(a) // (w * h * nb)
    return a[: n * w * h * nb].reshape(n, h, w) if nb == 1 else a[: n * w * h * nb].reshape(n, h, w, 3)


def hl_pixels(mp4, t):
    out = sh(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(mp4), "-frames:v", "1",
              "-vf", "crop=iw:ih*260/1080:0:ih*820/1080,scale=480:65", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    a = np.frombuffer(out, dtype=np.uint8)
    if a.size < 480 * 65 * 3:
        return 0
    a = a[: 480 * 65 * 3].reshape(65, 480, 3).astype(int)
    return int((np.abs(a - np.array(HL)).max(axis=2) < 30).sum())


HL_MIN_REF_PX = 120      # the calibration word (long) must show at least this many highlight pixels at 480x65
HL_ON_RANGE = (0.5, 2.0)  # first word pixels / expected pixels (from pixels per letter of the reference word)
HL_OFF_MAX = 0.25         # before the word starts: at most this share of the expected pixels
HL_FALLBACK_PX = 40       # one-word sentences: absolute minimum


def _letters(r):
    t = str(r.get("text") or r.get("word") or r.get("script") or r.get("token") or "")
    return max(1, sum(ch.isalnum() for ch in t))


def _word_end(timed, i):
    r = timed[i]
    e = r.get("abs_end")
    if e is None and i + 1 < len(timed):
        e = timed[i + 1]["abs_start"]
    return e if e is not None else r["abs_start"] + 0.2


def sample_time(t0, t1):
    """Middle of a word, but at least ~1 frame after it starts and ~1 frame before it ends, so short words get a real chance to be seen."""
    dur = max(t1 - t0, 0.0)
    t = t0 + min(max(dur * 0.5, 0.04), 0.15)
    return min(t, t1 - 0.03) if dur > 0.07 else t0 + dur * 0.5


def judge_highlight(first_letters, first_px, before_px, ref_letters, ref_px):
    """Pure decision rule (unit-testable). Returns (problem or None, expected_px)."""
    if ref_letters:
        if ref_px < HL_MIN_REF_PX:
            return "caption highlight is not visible (reference word shows %d px)" % ref_px, None
        exp = ref_px / ref_letters * first_letters
    else:
        exp = float(HL_FALLBACK_PX)
    if first_px < exp * HL_ON_RANGE[0]:
        return "caption highlight not switching on at the first word (%d px, expected about %d)" % (first_px, round(exp)), exp
    if first_px > exp * HL_ON_RANGE[1]:
        return "caption highlight too large for the first word (%d px, expected about %d)" % (first_px, round(exp)), exp
    if before_px > exp * HL_OFF_MAX:
        return "caption highlight already on before the first word (%d px)" % before_px, exp
    return None, exp


def check_highlight(mp4, sid, timed):
    t0, t1 = timed[0]["abs_start"], _word_end(timed, 0)
    first_px = hl_pixels(mp4, sample_time(t0, t1))
    before_px = hl_pixels(mp4, t0 - 0.12)
    others = [(i, r) for i, r in enumerate(timed) if i > 0]
    ref_letters = ref_px = 0
    ref_word = None
    if others:
        i, r = max(others, key=lambda x: _letters(x[1]))
        ref_letters = _letters(r)
        ref_px = hl_pixels(mp4, sample_time(r["abs_start"], _word_end(timed, i)))
        ref_word = str(r.get("text") or r.get("word") or r.get("script") or "")
    problem, exp = judge_highlight(_letters(timed[0]), first_px, before_px, ref_letters, ref_px)
    return {"sentence": sid, "first_word_letters": _letters(timed[0]), "first_word_s": round(t1 - t0, 3),
            "before": before_px, "first_word_px": first_px, "reference_word": ref_word, "reference_px": ref_px,
            "expected_px": None if exp is None else round(exp), "problem": problem}


def parse_size(txt, default=(1920, 1080)):
    try:
        w, h = str(txt).lower().split("x")
        return int(w), int(h)
    except Exception:
        return default


def luma(rgb):
    """relative luminance of an sRGB uint8 array (0..1)"""
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def cinematic_checks(mp4, timing, dur, W, H, res):
    """Looks like a film? brightness / contrast / crushed shadows, shot count + length, cut timing against the spoken words,
    subtitle position and contrast. Measured on the delivered file at its own resolution."""
    out = {}
    # ---- exposure on the art area (top 78%), 10 fps, 256x144
    fr = raw_frames(mp4, 10, 256, 144)
    art = fr[:, :112, :].astype(np.float64)
    p = art.reshape(-1)
    out["exposure"] = {"mean_luma": round(float(p.mean()), 1), "p5": int(np.percentile(p, 5)), "p95": int(np.percentile(p, 95)),
                       "contrast_p95_minus_p5": int(np.percentile(p, 95) - np.percentile(p, 5)),
                       "crushed_share_lt12": round(float((p < 12).mean()), 3), "clipped_share_gt245": round(float((p > 245).mean()), 3),
                       "dark_share_lt60": round(float((p < 60).mean()), 3)}
    pf = art.mean(axis=(1, 2))
    out["exposure"]["darkest_frame_mean"] = round(float(pf.min()), 1)
    out["exposure"]["brightest_frame_mean"] = round(float(pf.max()), 1)
    # ---- cuts: full 30 fps on a small gray frame; a cut is a spike far above its neighbourhood, clustered within 0.5 s
    g = raw_frames(mp4, 30, 192, 108)[:, :84, :].astype(np.int16)
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
    raw = [i for i in range(len(d)) if d[i] > 14 and d[i] > 4 * np.median(d[max(0, i - 6): i + 7])]
    cuts = []
    for i in raw:
        t = (i + 1) / 30.0
        if not cuts or t - cuts[-1] > 0.3:
            cuts.append(t)
    shots = len(cuts) + 1
    edges = [0.0] + cuts + [dur]
    lens = [b - a for a, b in zip(edges, edges[1:])]
    out["shots"] = {"count": shots, "average_s": round(dur / shots, 2), "shortest_s": round(min(lens), 2), "longest_s": round(max(lens), 2), "cut_times": [round(c, 2) for c in cuts]}
    # ---- every cut must sit on a spoken-word boundary (or sentence edge / the silence between sentences) : no random cuts
    bounds = []
    for s in timing["sentences"]:
        bounds += [s["offset"], s["offset"] + s["duration"]]
        for r in s["words"]:
            if r.get("abs_start") is not None:
                bounds += [r["abs_start"], r["abs_end"] if r.get("abs_end") is not None else r["abs_start"]]
    off = []
    for c in cuts:
        near = min(abs(c - b) for b in bounds)
        # a cut inside a gap between sentences is allowed too (silence)
        in_gap = any(timing["sentences"][i]["offset"] + timing["sentences"][i]["duration"] <= c <= timing["sentences"][i + 1]["offset"] for i in range(len(timing["sentences"]) - 1))
        if near > 0.2 and not in_gap:
            off.append(round(c, 2))
    out["cut_timing"] = {"max_distance_allowed_s": 0.2, "cuts_off_word_boundary": off}
    # ---- subtitles: position inside the safe area + contrast against what is behind them, one frame per sentence
    subs = []
    for s in timing["sentences"]:
        timed = [r for r in s["words"] if r.get("abs_start") is not None]
        t = (timed[0]["abs_start"] + timed[-1]["abs_start"]) / 2.0
        raw_ = sh(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", "crop=iw:ih*0.30:0:ih*0.70", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        h2 = int(round(H * 0.30)); a = np.frombuffer(raw_, dtype=np.uint8)
        if a.size < W * h2 * 3:
            subs.append({"sentence": s["id"], "problem": "frame could not be read"}); continue
        a = a[: W * h2 * 3].reshape(h2, W, 3)
        L = luma(a); gray = a.astype(int)
        mask = ((gray.min(axis=2) > 228)) | ((np.abs(gray - np.array(HL)).max(axis=2) < 40))
        ys, xs = np.nonzero(mask)
        if len(xs) < 200:
            subs.append({"sentence": s["id"], "problem": "no readable subtitle pixels"}); continue
        x0, x1, y0, y1 = int(np.percentile(xs, 1)), int(np.percentile(xs, 99)), int(np.percentile(ys, 1)), int(np.percentile(ys, 99))
        bg = L[y0:y1 + 1, x0:x1 + 1][~mask[y0:y1 + 1, x0:x1 + 1]]
        lt = float(L[mask].mean()); lb = float(bg.mean()) if bg.size else 0.0
        ratio = (lt + 0.05) / (lb + 0.05)
        row = {"sentence": s["id"], "left_pct": round(100 * x0 / W, 1), "right_pct": round(100 * x1 / W, 1), "bottom_pct": round(100 * (0.70 * H + y1) / H, 1), "contrast_ratio": round(ratio, 1)}
        bad = []
        if x0 < 0.04 * W or x1 > 0.96 * W: bad.append("text outside the horizontal safe area")
        if 0.70 * H + y1 > 0.97 * H: bad.append("text too close to the bottom edge")
        if ratio < 4.5: bad.append(f"low subtitle contrast {ratio:.1f}:1")
        row["problem"] = "; ".join(bad) or None
        subs.append(row)
    out["subtitles"] = subs
    return out


def verify(proj, ch, build, mp4_name="story.mp4", expect=None, tag=""):
    import story_stage2 as core
    build = Path(build)
    expect = expect or (1920, 1080)
    mp4 = build / mp4_name
    res = {"problems": [], "notes": []}
    if not mp4.exists() or mp4.stat().st_size == 0:
        sys.exit("ERROR: story.mp4 missing or empty")
    probe = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(mp4)]))
    vs = [s for s in probe["streams"] if s["codec_type"] == "video"]
    au = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    dur = float(probe["format"]["duration"])
    target = float(proj["meta"].get("target_duration") or 0)
    res.update({"size_bytes": mp4.stat().st_size, "duration": round(dur, 3), "target": target})
    if not vs:
        res["problems"].append("no video stream")
    else:
        v = vs[0]
        res["video"] = {"codec": v["codec_name"], "w": v["width"], "h": v["height"], "fps": v["avg_frame_rate"]}
        if (v["width"], v["height"]) != tuple(expect):
            res["problems"].append(f"wrong size {v['width']}x{v['height']}; expected {expect[0]}x{expect[1]} (16:9)")
        a_, b_ = map(int, v["avg_frame_rate"].split("/"))
        if abs(a_ / b_ - 30) > 0.1:
            res["problems"].append(f"wrong fps {a_ / b_:.2f}")
    if not au:
        res["problems"].append("NO AUDIO STREAM")
    if target and abs(dur - target) > 0.2:
        res["problems"].append(f"duration {dur:.2f}s, target {target}s")

    timing = core.load_json(build / "timing.json")
    first = next(r for s in timing["sentences"] for r in s["words"] if r["abs_start"] is not None)
    if au:
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(build / "mp4_audio.wav")])
        onset, _, _, _ = core.speech_bounds(build / "mp4_audio.wav")
        if onset is None:
            res["problems"].append("mp4 audio is silent")
        else:
            d = round((first["abs_start"] - onset) * 1000)
            res["mp4_audio_onset_vs_first_word_ms"] = d
            if abs(d) > 250:
                res["problems"].append(f"voice onset differs from first caption word by {d} ms")

    # caption highlight really switches on with each sentence's first word.
    # The highlight box grows with the word, so a fixed pixel count wrongly fails 2-letter words ("In", "By").
    # Method: calibrate pixels-per-letter on the longest other word of the same sentence (sampled at its middle),
    # then require the first word to show about that many pixels per letter, and nothing before it starts.
    hl = []
    for s in timing["sentences"]:
        timed = [r for r in s["words"] if r["abs_start"] is not None]
        hl.append(check_highlight(mp4, s["id"], timed))
        if hl[-1]["problem"]:
            res["problems"].append(f"{s['id']}: {hl[-1]['problem']}")
    res["highlight"] = hl

    # motion: sample 6 fps, compare consecutive frames in the art area (top 78%)
    g = raw_frames(mp4, 6, 192, 108)
    art = g[:, :84, :].astype(np.int16)
    diffs = np.abs(np.diff(art, axis=0)).mean(axis=(1, 2))
    cuts = int((diffs > 25).sum())
    static, run0 = [], None
    for i, d in enumerate(list(diffs) + [99]):
        if d < 1.2 and run0 is None:
            run0 = i
        if d >= 1.2 and run0 is not None:
            if (i - run0) / 6 > 2.5:
                static.append([round(run0 / 6, 2), round(i / 6, 2)])
            run0 = None
    res["motion"] = {"mean_frame_change": round(float(diffs.mean()), 3), "hard_cuts_detected": cuts, "static_spans_over_2_5s": static}
    if static:
        res["problems"].append(f"long near-static stretches (film grain keeps the baseline above 0.5): {static}")
    lum = g.mean(axis=(1, 2))
    dark = [round(i / 6, 2) for i, v in enumerate(lum) if v < 6 and 1 < i / 6 < dur - 1]
    if dark:
        res["problems"].append(f"black frames at {dark[:6]}")
    # cinematic checks (exposure, shots, cut timing, subtitle box) run on every file; they only FAIL the run for projects that ask for them
    cine = cinematic_checks(mp4, timing, dur, expect[0], expect[1], res)
    res.update(cine); res["file_checked"] = mp4_name
    th = proj["meta"].get("verify_cine")
    if th:
        e, sh_ = cine["exposure"], cine["shots"]
        if not (th["mean_luma"][0] <= e["mean_luma"] <= th["mean_luma"][1]): res["problems"].append(f"mean brightness {e['mean_luma']} outside {th['mean_luma']}")
        if e["crushed_share_lt12"] > th["crushed_max"]: res["problems"].append(f"crushed shadows {e['crushed_share_lt12']} > {th['crushed_max']}")
        if e["clipped_share_gt245"] > th["clipped_max"]: res["problems"].append(f"clipped highlights {e['clipped_share_gt245']} > {th['clipped_max']}")
        if e["contrast_p95_minus_p5"] < th["contrast_min"]: res["problems"].append(f"flat contrast {e['contrast_p95_minus_p5']} < {th['contrast_min']}")
        if not (th["shots"][0] <= sh_["count"] <= th["shots"][1]): res["problems"].append(f"shot count {sh_['count']} outside {th['shots']}")
        if not (th["avg_shot_s"][0] <= sh_["average_s"] <= th["avg_shot_s"][1]): res["problems"].append(f"average shot {sh_['average_s']}s outside {th['avg_shot_s']}")
        if cine["cut_timing"]["cuts_off_word_boundary"]: res["problems"].append(f"cuts not on a word boundary: {cine['cut_timing']['cuts_off_word_boundary']}")
        for row in cine["subtitles"]:
            if row.get("problem"): res["problems"].append(f"{row['sentence']} subtitles: {row['problem']}")
    res["problems_count"] = len(res["problems"])

    # contact sheet for human review
    fr = build / "frames"
    fr.mkdir(exist_ok=True)
    n = 12
    for i in range(n):
        t = dur * (i + 0.5) / n
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=640:-1", str(fr / f"t_{i:02d}.png")])
    try:
        sh(["ffmpeg", "-y", "-v", "error", "-framerate", "1", "-i", str(fr / "t_%02d.png"), "-vf", "tile=4x3", "-frames:v", "1", str(build / f"contact_sheet{tag}.png")])
    except subprocess.CalledProcessError:
        res["notes"].append("contact sheet could not be built")
    (build / f"verify{tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res["problems"]:
        sys.exit("VERIFY: " + "; ".join(res["problems"]))
    print("VERIFY OK")
