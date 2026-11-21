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
              "-vf", "crop=1920:260:0:820,scale=480:65", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    a = np.frombuffer(out, dtype=np.uint8)
    if a.size < 480 * 65 * 3:
        return 0
    a = a[: 480 * 65 * 3].reshape(65, 480, 3).astype(int)
    return int((np.abs(a - np.array(HL)).max(axis=2) < 30).sum())


def verify(proj, ch, build):
    import story_stage2 as core
    build = Path(build)
    mp4 = build / "story.mp4"
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
        if (v["width"], v["height"]) != (1920, 1080):
            res["problems"].append(f"wrong size {v['width']}x{v['height']}; expected 1920x1080 (16:9)")
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

    # caption highlight really switches on with each sentence's first word (+/-100 ms)
    hl = []
    for s in timing["sentences"]:
        timed = [r for r in s["words"] if r["abs_start"] is not None]
        t0 = timed[0]["abs_start"]
        before, after = hl_pixels(mp4, t0 - 0.12), hl_pixels(mp4, t0 + 0.12)
        hl.append({"sentence": s["id"], "before": before, "after": after})
        if before >= 120 or after < 120:
            res["problems"].append(f"{s['id']}: caption highlight not switching on at the first word")
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
    res["problems_count"] = len(res["problems"])

    # contact sheet for human review
    fr = build / "frames"
    fr.mkdir(exist_ok=True)
    n = 12
    for i in range(n):
        t = dur * (i + 0.5) / n
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=640:-1", str(fr / f"t_{i:02d}.png")])
    try:
        sh(["ffmpeg", "-y", "-v", "error", "-framerate", "1", "-i", str(fr / "t_%02d.png"), "-vf", "tile=4x3", "-frames:v", "1", str(build / "contact_sheet.png")])
    except subprocess.CalledProcessError:
        res["notes"].append("contact sheet could not be built")
    (build / "verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res["problems"]:
        sys.exit("VERIFY: " + "; ".join(res["problems"]))
    print("VERIFY OK")
