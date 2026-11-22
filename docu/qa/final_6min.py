#!/usr/bin/env python3
"""Final assembly of the 6-minute documentary from the three chapters (no network, no TTS, no API key).
Inputs : --data DIR  = published audio data of the chapters (DIR/<c1|c2|c3>/timing.json + narration.wav, made by the audio workflow)
Steps  : 0 structure check (analyze_6min.py, real timing)  ->  per chapter: silent video render (render_6min.py), synthesised music/effects mix
         (make_audio_6min.py), mux  ->  concat of the chapters  ->  two-pass loudnorm (-14 LUFS, true peak -1 dB)  ->  verification report.
Output : --out final.mp4 (1280x720, 30 fps, H.264 + AAC) and final_report.json next to it.  --dry-run prints the plan without running anything.
Nothing in the project, the audio cache or the approved chapter audio is written: everything goes to --work."""
import argparse, json, re, subprocess, sys
from pathlib import Path
DOCU = Path(__file__).resolve().parent.parent
QA = DOCU / "qa"
PROJECT = "kim-docu-6min"
LUFS, TP, LRA = -14.0, -1.0, 11.0


def plan(data, work, out, chapters, fps=30, scale=0.6667, workers=2):
    """the ordered list of (name, command) the assembly runs; pure function (used by the tests)"""
    work, data = Path(work), Path(data)
    steps = [("structure check", [sys.executable, str(QA / "analyze_6min.py"), "--data", str(data), "--out", str(work / "analyze")])]
    for ch in chapters:
        steps.append((f"{ch}: silent video", [sys.executable, str(QA / "render_6min.py"), "--data", str(data), "--chapter", ch, "--mp4", str(work / "video.mp4"), "--fps", f"{fps:g}", "--scale", f"{scale:g}", "--workers", str(workers), "--out", str(work / "build")]))
        steps.append((f"{ch}: music + effects mix", [sys.executable, str(QA / "make_audio_6min.py"), "--chapter", ch, "--build", str(work / "build"), "--timing", str(data / ch / "timing.json"), "--sfx", str(DOCU / "projects" / PROJECT / "sfx6.json"), "--out", str(work / f"audio_{ch}.wav")]))
        steps.append((f"{ch}: mux", ["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / f"video_{ch}.mp4"), "-i", str(work / f"audio_{ch}.wav"), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(work / f"chapter_{ch}.mp4")]))
    steps.append(("concat", ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-c", "copy", str(work / "concat.mp4")]))
    steps.append(("loudness pass 1", ["ffmpeg", "-hide_banner", "-nostats", "-i", str(work / "concat.mp4"), "-vn", "-af", f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"]))
    steps.append(("loudness pass 2 + final encode", ["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "concat.mp4"), "-c:v", "copy", "-af", "PASS2_FILTER", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]))
    return steps


def parse_loudnorm(text):
    """the JSON block that ffmpeg's loudnorm prints at the end of pass 1"""
    m = re.findall(r"\{[^{}]*\}", text, re.S)
    if not m: raise ValueError("no loudnorm JSON in the ffmpeg output")
    j = json.loads(m[-1])
    return {k: float(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}


def pass2_filter(meas):
    return f"loudnorm=I={LUFS}:TP={TP}:LRA={LRA}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true"


def probe(path):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration", "-of", "json", str(path)]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video"); a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    n, d = v["r_frame_rate"].split("/")
    return {"duration": float(j["format"]["duration"]), "width": v["width"], "height": v["height"], "fps": float(n) / float(d), "vcodec": v["codec_name"], "acodec": a["codec_name"]}


def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r); p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    return {"lufs": float(i[-1]), "true_peak": float(p[-1])}


XFADE = 0.5   # seconds of cross-dissolve between chapters; it lies inside the silent lead/tail of the chapters, no narration is covered


def xfade_filter(durs, x=XFADE):
    """video cross-dissolves between consecutive chapters (pixels mix, no black frame); returns (filter_complex, total_duration)"""
    parts, acc, last = [], durs[0], "0:v"
    for i in range(1, len(durs)):
        out = f"v{i}"
        parts.append(f"[{last}][{i}:v]xfade=transition=fade:duration={x}:offset={acc - x:.3f}[{out}]")
        acc += durs[i] - x; last = out
    return ";".join(parts), acc


def silent_film(a):
    """complete silent film: every chapter rendered by render_6min (real timing where --data has it, synthetic otherwise), joined with dissolves"""
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True); chs = a.chapters.split(","); vids = []
    for ch in chs:
        v = work / f"video_{ch}.mp4"
        if not v.exists():
            cmd = [sys.executable, str(QA / "render_6min.py"), "--chapter", ch, "--mp4", str(work / "video.mp4"), "--fps", f"{a.fps:g}", "--scale", f"{a.scale:g}", "--workers", str(a.workers), "--out", str(work / "build")] + (["--data", a.data] if a.data else ["--synth"])
            print("$", " ".join(cmd)); subprocess.run(cmd, check=True)
        vids.append(v)
    durs = [probe_v(v)["duration"] for v in vids]; fc, total = xfade_filter(durs)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + sum([["-i", str(v)] for v in vids], []) + ["-filter_complex", fc, "-map", f"[v{len(vids) - 1}]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(a.out)]
    print("$", " ".join(cmd)); subprocess.run(cmd, check=True)
    info = probe_v(a.out)
    bl = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(a.out), "-vf", "blackdetect=d=0.1:pix_th=0.06", "-an", "-f", "null", "-"], capture_output=True, text=True).stderr.count("black_start")
    rep = {"file": str(a.out), "chapters": dict(zip(chs, [round(d, 3) for d in durs])), "dissolve_s": XFADE, "expected_duration": round(total, 3), **info, "black_segments": bl}
    json.dump(rep, open(Path(a.out).with_suffix(".json"), "w"), indent=1); print(json.dumps(rep, indent=1))
    sys.exit(0 if bl == 0 and abs(info["duration"] - total) < 0.2 else 1)


def probe_v(path):
    j = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(path)]))
    v = j["streams"][0]; n, d = v["r_frame_rate"].split("/")
    return {"duration": float(j["format"]["duration"]), "width": v["width"], "height": v["height"], "fps": float(n) / float(d), "frames": int(v.get("nb_frames") or 0)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data"); ap.add_argument("--work", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--chapters", default="c1,c2,c3"); ap.add_argument("--fps", type=float, default=30); ap.add_argument("--scale", type=float, default=0.6667); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--silent", action="store_true", help="only the silent film (no audio mix, no loudness)")
    a = ap.parse_args(); work = Path(a.work); work.mkdir(parents=True, exist_ok=True); chs = a.chapters.split(",")
    if a.silent: return silent_film(a)
    steps = plan(a.data, work, a.out, chs, a.fps, a.scale, a.workers)
    meas = None
    for name, cmd in steps:
        print(f"== {name}\n$ {' '.join(cmd)}")
        if a.dry_run: continue
        if name == "concat": (work / "list.txt").write_text("".join(f"file '{work / f'chapter_{c}.mp4'}'\n" for c in chs))
        if name.startswith("loudness pass 1"):
            r = subprocess.run(cmd, capture_output=True, text=True); meas = parse_loudnorm(r.stderr); print("   measured:", meas); continue
        if name.startswith("loudness pass 2"):
            cmd = [pass2_filter(meas) if c == "PASS2_FILTER" else c for c in cmd]
        r = subprocess.run(cmd)
        if r.returncode: sys.exit(f"step failed: {name}")
    if a.dry_run: print("dry run: nothing was executed"); return
    info = probe(a.out); loud = measure(a.out)
    rep = {"file": str(a.out), **info, **loud, "checks": {"720p": (info["width"], info["height"]) == (1280, 720), "30fps": abs(info["fps"] - 30) < 0.01, "loudness_ok": abs(loud["lufs"] - LUFS) <= 1.0, "true_peak_ok": loud["true_peak"] <= TP + 0.3}}
    json.dump(rep, open(Path(a.out).with_name("final_report.json"), "w"), indent=1); print(json.dumps(rep, indent=1))
    sys.exit(0 if all(rep["checks"].values()) else 1)


if __name__ == "__main__":
    main()
