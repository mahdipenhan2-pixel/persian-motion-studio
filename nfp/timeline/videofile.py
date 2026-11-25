"""NFP Timeline - video files for video clips (T4): what ffprobe reports, checked against what was proven frame-exact.

T3 measured HyperFrames 0.9.83 frame by frame on real renders: H.264, yuv420p, constant 25 or 30 fps, starting at 0,
no rotation -> 0 frame error. Only that is accepted; everything else is refused with a clear reason (nothing assumed).

This module does not run ffprobe (nfp/timeline runs no programs): the caller hands in ffprobe's JSON
  {"streams": [...], "format": {...}, "packets": [<pts_time of every video packet>]}
(ffprobe -show_streams -show_format, and -select_streams v:0 -show_entries packet=pts_time); see Film's timeline_bridge.

Frame mapping (HyperFrames: frameIndex = floor((t - start + 1e-5) * fps) from data-media-start): a clip on timeline
frames [start, end) with source in-point `in` (a source frame) shows on timeline frame k the source frame
    in + floor((k - start) * fps / 30)
so it reads source frames in .. out - 1 with out = in + floor((end - 1 - start) * fps / 30) + 1, and must have out <= frames
(past the last frame HyperFrames would freeze it - refused, never silently held).
"""
from fractions import Fraction

TIMELINE_FPS = 30
CODECS = ("h264",)
PIX_FMTS = ("yuv420p",)
RATES = (Fraction(25), Fraction(30))


class VideoError(ValueError):
    pass


def _rate(s):
    try:
        n, d = str(s).split("/")
        return Fraction(int(n), int(d)) if int(d) else None
    except (ValueError, TypeError):
        return None


def facts(probe):
    """ffprobe JSON -> {codec, pix_fmt, width, height, fps (Fraction), frames, duration, start, rotation, audio, cfr, problems}."""
    streams = probe.get("streams") or []
    video = [s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")]
    out = {"problems": [], "audio": sum(1 for s in streams if s.get("codec_type") == "audio")}
    if len(video) != 1:
        out["problems"].append(f"{len(video)} video streams (exactly 1 needed)")
        return out
    v = video[0]
    r, avg = _rate(v.get("r_frame_rate")), _rate(v.get("avg_frame_rate"))
    rot = 0
    for sd in v.get("side_data_list") or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    rot = rot or int((v.get("tags") or {}).get("rotate", 0) or 0)
    pts = sorted(float(p) for p in probe.get("packets") or [] if p is not None)
    out.update({"codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"), "width": v.get("width"), "height": v.get("height"),
                "fps": r, "avg_fps": avg, "frames": len(pts), "start": float(v.get("start_time") or 0.0), "rotation": rot,
                "duration": float(v.get("duration") or (probe.get("format") or {}).get("duration") or 0.0)})
    # constant frame rate: every packet exactly one frame after the previous one
    cfr = bool(r) and r == avg and len(pts) >= 2 and all(abs((b - a) - 1 / float(r)) < 0.25 / float(r) for a, b in zip(pts, pts[1:]))
    out["cfr"] = cfr
    out["first_pts"] = pts[0] if pts else None
    return out


def check(f):
    """Problems (list of str) that make a video unusable for frame-exact clips."""
    p = list(f["problems"])
    if p:
        return p
    if f["codec"] not in CODECS:
        p.append(f"codec {f['codec']!r}: only H.264 is tested")
    if f["pix_fmt"] not in PIX_FMTS:
        p.append(f"pixel format {f['pix_fmt']!r}: only yuv420p is tested")
    if f["fps"] not in RATES:
        p.append(f"frame rate {f['fps']}: only 25 and 30 fps are tested")
    if not f["cfr"]:
        p.append(f"variable frame rate (r {f['fps']}, avg {f['avg_fps']}, packet times not evenly spaced): only constant frame rate")
    if abs(f["start"]) > 1e-3 or (f["first_pts"] is not None and abs(f["first_pts"]) > 1e-3):
        p.append(f"the video starts at {f['start']:.3f} s, not 0 (untested offset)")
    if f["rotation"]:
        p.append(f"rotation {f['rotation']} degrees in the file: re-encode it upright")
    if not (isinstance(f["width"], int) and isinstance(f["height"], int) and f["width"] > 0 and f["height"] > 0):
        p.append("no valid width / height")
    if f["frames"] < 1:
        p.append("no video frames")
    elif f["fps"] in RATES and abs(f["frames"] / float(f["fps"]) - f["duration"]) > 1.5 / float(f["fps"]):
        p.append(f"{f['frames']} frames at {f['fps']} fps do not fill the stated {f['duration']:.3f} s")
    return p


def source_frames(start, end, first, fps):
    """(first source frame, out = last + 1) read by a clip on timeline frames [start, end) from in-point `first`."""
    return first, first + ((end - 1 - start) * Fraction(fps) / TIMELINE_FPS).__floor__() + 1


def shown(k, start, first, fps):
    """Source frame on timeline frame k (k inside the clip)."""
    return first + ((k - start) * Fraction(fps) / TIMELINE_FPS).__floor__()


def media_start(first, fps):
    """data-media-start (seconds) for in-point `first`: exactly on that frame's start."""
    return float(Fraction(first) / Fraction(fps))
