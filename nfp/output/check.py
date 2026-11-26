#!/usr/bin/env python3
"""NFP Output / Verify - O1: a READ-ONLY quality check of a build's final MP4, next to Film's verify.py (which it never
changes, nor its verify.json). Offline: ffprobe / ffmpeg, the standard library, numpy (already needed by verify.py),
Film's project loader + Subtitle settings and nfp.voice.audiotools (read-only use).

  check(build, project=None, chapter=None, mp4="story.mp4", write=True) -> nfp.output.qc/1, written to
  <build>/output_qc.json (the only file it writes; temporary audio goes to a temporary folder)
  python3 nfp/output/check.py --build <dir> [--project <dir>] [--chapter id] [--mp4 story.mp4]   exit 0 OK / WARN, 1 FAIL

Sections (each issue: {level: error | warning | info, check, code, message}):
  technical   container + streams as delivered: H.264 / yuv420p / AAC, profile, sample rate, channels, faststart (moov
              before mdat), start time and length of each stream and their difference, bitrate (+ size per minute)
  loudness    integrated loudness (LUFS) and true peak (dBTP) of the MP4's audio, EBU R128 (ffmpeg ebur128): silent ->
              error, true peak above -1 dBTP -> warning, below -30 LUFS -> warning. No delivery target is assumed.
  sync        per sentence: the speech onset measured in the MP4's audio vs the first timed word of timing.json
              (verify.py checks this for the first word only). Measured only where the method is valid: the audio in
              the 0.25 s before the expected onset must be quiet (a pause separates the sentences); otherwise the
              sentence is "not_measurable" with the reason - never guessed. |offset| > 250 ms (verify.py's own limit)
              -> WARNING only: validated on synthetic test tones (sharp onsets), not yet on real speech / Whisper.
  subtitles   verify.py's caption-highlight check (karaoke yellow under the first word) only applies where that highlight
              is drawn: projects without a subtitles block (the old captions) and subtitles.mode "karaoke". For a mode
              the Subtitle Engine itself resolves to "sentence", "word" or "off" (subtitles.settings: explicit, or its
              default) the highlight problems in verify.json are listed as not_applicable WITH that reason, and a check
              for what that mode does draw replaces them:
                sentence / word  caption text visible (white text pixels in the caption band) at the middle of each
                                 sentence's longest word -> otherwise error
                off              no karaoke highlight pixels anywhere it was sampled -> otherwise error
              In every mode: "caption highlight already on before the first word" of a sentence whose first script
              word Whisper did not time (timing.json: no abs_start) is not_applicable too (rule estimated_first_word):
              verify.py checks from the first TIMED word, so the estimated word's own highlight comes before it.
              verify.json is read, never changed; every other verify.py problem stays as it is.
  inputs      what the result was made from, so a reader can tell whether it is still current (is_current):
              sha256 of the MP4, verify.json and timing.json, and the fingerprint of the project settings that decide
              the checks (meta, the chapter, the subtitles block as written AND as the Subtitle Engine resolves it)
Status: FAIL (any error) | WARN (any warning) | OK.
"""
import hashlib
import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NFP = HERE.parent
ROOT = NFP.parent
SCHEMA = "nfp.output.qc/1"
HL = (255, 214, 90)                 # the karaoke highlight colour (Film base.html / subtitle_layer.py)
HL_PX = 120                         # verify.py's HL_MIN_REF_PX: fewer highlight pixels than this = no highlight
TEXT_PX = 200                       # verify.py's cinematic check: fewer bright text pixels than this = no readable caption
SYNC_LIMIT_MS = 250                 # verify.py's limit for the first word
QUIET_BEFORE = 0.25                 # seconds that must be quiet before an expected onset for the onset to be measurable
HIGHLIGHT_PROBLEMS = ("caption highlight is not visible", "caption highlight not switching on", "caption highlight too large",
                      "caption highlight already on")


def sh(cmd, text=False):
    return subprocess.run(cmd, check=True, capture_output=True, text=text).stdout


def probe(mp4):
    return json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(mp4)], text=True))


def top_boxes(mp4):
    """Top-level ISO-BMFF boxes in file order (type names only)."""
    out = []
    with open(mp4, "rb") as f:
        size = Path(mp4).stat().st_size
        pos = 0
        while pos + 8 <= size and len(out) < 64:
            f.seek(pos)
            h = f.read(8)
            n, typ = int.from_bytes(h[:4], "big"), h[4:8].decode("latin-1")
            if n == 1:
                n = int.from_bytes(f.read(8), "big")
            elif n == 0:
                n = size - pos
            if n < 8:
                break
            out.append(typ)
            pos += n
    return out


def technical(mp4, issues):
    def add(level, code, msg):
        issues.append({"level": level, "check": "technical", "code": code, "message": msg})
    p = probe(mp4)
    fmt = p["format"]
    vs = [s for s in p["streams"] if s["codec_type"] == "video"]
    au = [s for s in p["streams"] if s["codec_type"] == "audio"]
    boxes = top_boxes(mp4)
    dur = float(fmt.get("duration") or 0)
    size = int(fmt.get("size") or Path(mp4).stat().st_size)
    t = {"container": fmt.get("format_name"), "duration": round(dur, 3), "bytes": size, "bitrate_kbps": round(int(fmt.get("bit_rate") or 0) / 1000),
         "megabytes_per_minute": round(size / 1e6 / dur * 60, 1) if dur else None, "boxes": boxes,
         "faststart": "moov" in boxes and ("mdat" not in boxes or boxes.index("moov") < boxes.index("mdat")), "video": None, "audio": None}
    if not vs:
        add("error", "no_video", "no video stream")
    else:
        v = vs[0]
        t["video"] = {"codec": v.get("codec_name"), "profile": v.get("profile"), "pix_fmt": v.get("pix_fmt"), "w": v.get("width"), "h": v.get("height"),
                      "fps": v.get("avg_frame_rate"), "start": float(v.get("start_time") or 0), "duration": float(v.get("duration") or dur)}
        if v.get("codec_name") != "h264":
            add("error", "video_codec", f"video codec {v.get('codec_name')}, expected h264")
        if v.get("pix_fmt") != "yuv420p":
            add("error", "pix_fmt", f"pixel format {v.get('pix_fmt')}, expected yuv420p (players and platforms)")
    if len(vs) > 1:
        add("warning", "video_streams", f"{len(vs)} video streams")
    if not au:
        add("error", "no_audio", "no audio stream")
    else:
        a = au[0]
        t["audio"] = {"codec": a.get("codec_name"), "profile": a.get("profile"), "rate": int(a.get("sample_rate") or 0), "channels": a.get("channels"),
                      "start": float(a.get("start_time") or 0), "duration": float(a.get("duration") or dur)}
        if a.get("codec_name") != "aac":
            add("error", "audio_codec", f"audio codec {a.get('codec_name')}, expected aac")
        if t["audio"]["rate"] not in (44100, 48000):
            add("warning", "sample_rate", f"audio sample rate {t['audio']['rate']} Hz (44100 / 48000 expected)")
        if a.get("channels") not in (1, 2):
            add("warning", "channels", f"{a.get('channels')} audio channels")
    if len(au) > 1:
        add("warning", "audio_streams", f"{len(au)} audio streams")
    if not t["faststart"]:
        add("warning", "faststart", f"moov after mdat (no faststart): playback over the web starts only after the whole file loads {boxes}")
    if t["video"] and t["audio"]:
        frame = 1 / 30
        ds = abs(t["video"]["start"] - t["audio"]["start"])
        dl = abs((t["video"]["start"] + t["video"]["duration"]) - (t["audio"]["start"] + t["audio"]["duration"]))
        t["stream_start_difference_s"], t["stream_end_difference_s"] = round(ds, 3), round(dl, 3)
        if ds > frame:
            add("error", "stream_start", f"audio starts {t['audio']['start']:.3f} s, video {t['video']['start']:.3f} s (difference {ds:.3f} s > 1 frame)")
        if dl > 2 * frame + 0.03:
            add("error", "stream_length", f"audio ends at {t['audio']['start'] + t['audio']['duration']:.3f} s, video at "
                                          f"{t['video']['start'] + t['video']['duration']:.3f} s (difference {dl:.3f} s)")
    add("info", "bitrate", f"{t['bitrate_kbps']} kb/s = {t['megabytes_per_minute']} MB per minute")
    return t


def loudness(mp4, has_audio, issues):
    if not has_audio:
        return None
    sys.path.insert(0, str(NFP)) if str(NFP) not in sys.path else None
    from voice import audiotools as A
    r = A.loudness(mp4)
    def add(level, code, msg):
        issues.append({"level": level, "check": "loudness", "code": code, "message": msg})
    i, tp = r["integrated_lufs"], r["true_peak_dbtp"]
    if i is None or tp is None or (tp is not None and tp < -70):
        add("error", "silent", f"the audio is silent (integrated {i} LUFS, true peak {tp} dBTP)")
    else:
        if tp > -1.0:
            add("warning", "true_peak", f"true peak {tp} dBTP above -1 dBTP (may clip after lossy encoding)")
        if i < -30:
            add("warning", "quiet", f"integrated loudness {i} LUFS below -30 LUFS (very quiet)")
        add("info", "measured", f"integrated {i} LUFS, true peak {tp} dBTP (no delivery target assumed)")
    return r


def mono(mp4, rate, tmp):
    wav = Path(tmp) / "a.raw"
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", str(wav)])
    return np.fromfile(wav, dtype="<i2").astype(np.float64)


def sync(mp4, timing, has_audio, issues, tmp, rate=24000, win=0.01):
    """Per sentence: onset in the MP4 audio vs the first timed word, where it can be measured (see the module doc)."""
    if not has_audio or not timing:
        return None
    a = mono(mp4, rate, tmp)
    n = int(rate * win)
    rms = np.sqrt(np.add.reduceat(a * a, np.arange(0, len(a), n)) / n) if len(a) else np.zeros(0)
    peak = float(rms.max()) if rms.size else 0.0
    rows = []
    sents = timing["sentences"]
    for k, s in enumerate(sents):
        timed = [w for w in s["words"] if w.get("abs_start") is not None]
        if not timed:
            rows.append({"sentence": s["id"], "status": "not_measurable", "reason": "no timed word"})
            continue
        exp = timed[0]["abs_start"]
        lo, hi = max(0.0, exp - 0.6), exp + 0.6
        i0, i1 = int(lo / win), min(len(rms), int(math.ceil(hi / win)))
        q = int(round(QUIET_BEFORE / win))
        seg = rms[max(0, i0 - q):i1]
        if peak <= 0 or seg.size == 0 or float(seg.max()) <= 0:
            rows.append({"sentence": s["id"], "status": "not_measurable", "expected": round(exp, 3), "reason": "no sound near the expected onset"})
            continue
        thr = 0.08 * float(seg.max())
        loud = rms > thr
        cands = [i for i in range(max(i0, q), i1) if loud[i] and not loud[i - q:i].any()]   # sound right after >= QUIET_BEFORE of quiet
        if not cands:
            rows.append({"sentence": s["id"], "status": "not_measurable", "expected": round(exp, 3),
                         "reason": f"no onset after a {QUIET_BEFORE} s pause within 0.6 s of the expected time (sentences not separated by a pause?)"})
            continue
        onset = min(cands, key=lambda i: abs(i * win - exp)) * win
        d = round((exp - onset) * 1000)
        row = {"sentence": s["id"], "status": "measured", "expected": round(exp, 3), "onset": round(onset, 3), "offset_ms": d}
        rows.append(row)
        if abs(d) > SYNC_LIMIT_MS:
            issues.append({"level": "warning", "check": "sync", "code": "sentence_offset",
                           "message": f"{s['id']}: voice onset {onset:.2f} s vs first caption word {exp:.2f} s ({d} ms, limit {SYNC_LIMIT_MS}; "
                                      "warning only: the method is not yet validated on real speech)"})
    m = [r["offset_ms"] for r in rows if r["status"] == "measured"]
    out = {"method": "speech onset (10 ms RMS above 8 % of the window's peak) in the MP4 audio vs the first timed word",
           "limit_ms": SYNC_LIMIT_MS, "sentences": rows, "measured": len(m), "not_measurable": len(rows) - len(m),
           "drift_ms": (m[-1] - m[0]) if len(m) > 1 else None}
    if rows and len(m) < len(rows):
        issues.append({"level": "info", "check": "sync", "code": "not_measurable",
                       "message": f"{len(rows) - len(m)} of {len(rows)} sentence onset(s) could not be measured (reasons per sentence)"})
    return out


def band(mp4, t, W=1920, H=1080):
    raw = sh(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", "crop=iw:ih*0.30:0:ih*0.70",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    h = int(round(H * 0.30))
    a = np.frombuffer(raw, dtype=np.uint8)
    if a.size < W * h * 3:
        return None
    a = a[: W * h * 3].reshape(h, W, 3).astype(int)
    return {"text_px": int((a.min(axis=2) > 228).sum()), "highlight_px": int((np.abs(a - np.array(HL)).max(axis=2) < 30).sum())}


def subtitle_mode(project, chapter):
    """(mode, source) - "legacy" when the project has no subtitles block; the Subtitle Engine's own settings otherwise."""
    if project is None:
        return None, "no project given"
    for p in (str(NFP / "film" / "engine"), str(NFP), str(ROOT / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import project as P
    proj = P.load(project)                       # validates the subtitles block itself (subtitles.settings)
    if "subtitles" not in proj:
        return "legacy", "no subtitles block: Film's own captions (karaoke highlight)"
    import subtitles as SB
    mode = SB.settings(proj)["mode"]
    return mode, "explicit subtitles.mode" if "mode" in proj["subtitles"] else f"Subtitle Engine default ({SB.DEFAULTS['mode']})"


def subtitles(mp4, build, timing, project, chapter, issues):
    mode, source = subtitle_mode(project, chapter)
    vj_path = Path(build) / "verify.json"
    vj = json.loads(vj_path.read_text(encoding="utf-8")) if vj_path.exists() else None
    raw = (vj or {}).get("problems", [])
    hl = [p for p in raw if any(k in p for k in HIGHLIGHT_PROBLEMS)]
    applies = mode in (None, "legacy", "karaoke")
    na = [] if applies else [{"problem": p, "rule": "mode", "reason": f"subtitles.mode '{mode}' ({source}) draws no karaoke highlight"} for p in hl]
    if applies and timing:                # a sentence that starts with a word Whisper did not time: its estimated slot lies
        lead = {}                         # before the first TIMED word, the one verify.py checks - that highlight is that word's
        for s in timing["sentences"]:
            W = s["words"]
            if W and W[0].get("abs_start") is None and any(w.get("abs_start") is not None for w in W):
                lead[s["id"]] = next(w for w in W if w.get("abs_start") is None)["text"]
        for p in hl:
            sid = p.split(":", 1)[0]
            if "caption highlight already on before the first word" in p and sid in lead:
                na.append({"problem": p, "rule": "estimated_first_word",
                           "reason": f"{sid} starts with '{lead[sid]}', which Whisper did not time: the highlight verify.py sees before "
                                     "the first timed word is that word's own estimated highlight"})
    out = {"mode": mode, "mode_source": source, "verify_json": str(vj_path) if vj else None, "verify_problems": raw,
           "highlight_check_applies": applies, "not_applicable": na,
           "still_applicable": [p for p in raw if p not in {x["problem"] for x in na}], "replacement": None}
    if mode is None:
        issues.append({"level": "info", "check": "subtitles", "code": "no_project", "message": "no project given: verify.py's problems are kept as they are"})
    if applies or not timing:
        return out
    rows = []
    for s in timing["sentences"]:
        timed = [w for w in s["words"] if w.get("abs_start") is not None]
        if not timed:
            continue
        w = max(timed, key=lambda r: (r.get("abs_end") or r["abs_start"]) - r["abs_start"])
        t = (w["abs_start"] + (w.get("abs_end") or w["abs_start"] + 0.2)) / 2
        b = band(mp4, t)
        row = {"sentence": s["id"], "t": round(t, 3), **(b or {"text_px": None, "highlight_px": None})}
        if b is None:
            row["problem"] = "frame could not be read"
        elif mode in ("sentence", "word") and b["text_px"] < TEXT_PX:
            row["problem"] = f"caption not visible ({b['text_px']} text px, at least {TEXT_PX})"
        elif mode == "off" and b["highlight_px"] >= HL_PX:
            row["problem"] = f"karaoke highlight drawn although subtitles are off ({b['highlight_px']} px)"
        else:
            row["problem"] = None
        if row["problem"]:
            issues.append({"level": "error", "check": "subtitles", "code": f"{mode}_caption", "message": f"{s['id']}: {row['problem']}"})
        rows.append(row)
    out["replacement"] = {"check": "caption visible at each sentence's longest word" if mode in ("sentence", "word")
                          else "no karaoke highlight at each sentence's longest word", "sentences": rows}
    return out


def sha256(path):
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def settings_fingerprint(project, chapter=None):
    """(sha256, info) of the project settings that decide the checks: meta, the chapter built, the subtitles block as
    written and as the Subtitle Engine resolves it (mode, defaults). (None, None) without a project."""
    if project is None:
        return None, None
    mode, source = subtitle_mode(project, chapter)
    import project as P
    proj = P.load(project)
    ch = P.chapter(proj, chapter)
    doc = {"meta": proj["meta"], "chapter": ch, "subtitles_block": proj.get("subtitles"), "subtitle_mode": mode}
    if "subtitles" in proj:
        import subtitles as SB
        doc["subtitles_resolved"] = SB.settings(proj)
    fp = hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
    return fp, {"chapter": ch["id"], "subtitle_mode": mode, "mode_source": source}


def inputs(build, project=None, chapter=None, mp4="story.mp4"):
    build = Path(build)
    fp, info = settings_fingerprint(project, chapter)
    return {"mp4_sha256": sha256(build / mp4), "verify_json_sha256": sha256(build / "verify.json"), "timing_sha256": sha256(build / "timing.json"),
            "project": str(project) if project else None, "settings_sha256": fp, "settings": info}


def is_current(qc, build, project=None, chapter=None, mp4="story.mp4"):
    """(True, []) when an output_qc.json document was made from exactly these files and project settings; otherwise
    (False, [what differs])."""
    if not isinstance(qc, dict) or qc.get("schema") != SCHEMA or not isinstance(qc.get("inputs"), dict):
        return False, ["not an output_qc.json with recorded inputs"]
    now, was = inputs(build, project, chapter, mp4), qc["inputs"]
    names = {"mp4_sha256": mp4, "verify_json_sha256": "verify.json", "timing_sha256": "timing.json", "project": "project",
             "settings_sha256": "project settings (meta / chapter / subtitles)"}
    diff = [f"{names[k]} changed since the check" for k in names if was.get(k) != now[k]]
    return not diff, diff


def check(build, project=None, chapter=None, mp4="story.mp4", write=True):
    build = Path(build)
    f = build / mp4
    issues = []
    rep = {"schema": SCHEMA, "build": str(build), "mp4": str(f), "project": str(project) if project else None,
           "inputs": inputs(build, project, chapter, mp4)}
    if not f.is_file() or f.stat().st_size == 0:
        issues.append({"level": "error", "check": "technical", "code": "missing", "message": f"{f} missing or empty"})
        rep.update(status="FAIL", issues=issues)
    else:
        tp = build / "timing.json"
        timing = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else None
        if timing is None:
            issues.append({"level": "info", "check": "sync", "code": "no_timing", "message": "no timing.json: sync and subtitle checks skipped"})
        tech = technical(f, issues)
        has_audio = tech["audio"] is not None
        tmp = tempfile.mkdtemp(prefix="nfp-output-")
        try:
            rep["technical"] = tech
            rep["loudness"] = loudness(f, has_audio, issues)
            rep["sync"] = sync(f, timing, has_audio, issues, tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        rep["subtitles"] = subtitles(f, build, timing, project, chapter, issues)
        levels = {i["level"] for i in issues}
        rep.update(status="FAIL" if "error" in levels else "WARN" if "warning" in levels else "OK", issues=issues)
    if write:
        (build / "output_qc.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", required=True)
    ap.add_argument("--project")
    ap.add_argument("--chapter")
    ap.add_argument("--mp4", default="story.mp4")
    a = ap.parse_args(argv)
    r = check(a.build, a.project, a.chapter, a.mp4)
    print(f"output check: {r['status']}  ({Path(a.build) / 'output_qc.json'})")
    for i in r["issues"]:
        print(f"  {i['level']:7s} {i['check']}/{i['code']}: {i['message']}")
    return 1 if r["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
