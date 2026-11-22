#!/usr/bin/env python3
"""Local render of the short documentary-style experiment (no network, no Gemini/TTS, no GitHub Actions).
  render_style_test.py kim-docu-style --words words.json --audio narration.wav --times 1,2,3        (screenshots)
  render_style_test.py kim-docu-style --words words.json --audio narration.wav --mp4 out.mp4 [--sfx sfx.wav]
words.json = real word timings of the approved narration ({sid:[[word,start,end],...]}); narration.wav = the approved
narration (cut from an already delivered render), so the audio is never regenerated."""
import argparse, json, subprocess, sys, wave
from pathlib import Path
DOCU = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOCU / "engine"))
import project as P, compose as C  # noqa


def timing_from_words(ch, words, total):
    sents = []
    for s in ch["sentences"]:
        rows = words[s["id"]]; ws = s["text"].split(); out = []
        j = 0
        for i, w in enumerate(ws):   # sequential match: words the aligner missed stay unmatched, later words keep their script index
            r = None
            if j < len(rows) and rows[j][0].strip() == w.strip(): r = rows[j]; j += 1
            out.append({"i": i, "text": w, "abs_start": r[1] if r else None, "abs_end": r[2] if r else None, "status": "ok" if r else "unmatched"})
        timed = [x for x in out if x["abs_start"] is not None]
        sents.append({"id": s["id"], "text": s["text"], "offset": timed[0]["abs_start"], "duration": round(timed[-1]["abs_end"] - timed[0]["abs_start"] + (0.7 if s["id"] == "s6" else 0.0), 3), "words": out})
    return {"summary": {"status": "OK"}, "audio": {"total": total, "gap": 0.3}, "sentences": sents}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--words", required=True); ap.add_argument("--audio", required=True)
    ap.add_argument("--times"); ap.add_argument("--mp4"); ap.add_argument("--sfx"); ap.add_argument("--out", required=True); ap.add_argument("--size", default="1920x1080")
    a = ap.parse_args()
    proj = P.load(a.project); ch = proj["chapters"][0]; out = Path(a.out); build = out / "build"; build.mkdir(parents=True, exist_ok=True)
    total = float(proj["meta"]["target_duration"]); timing = timing_from_words(ch, json.load(open(a.words)), total)
    (build / "timing.json").write_text(json.dumps(timing))
    info = C.compose(proj, ch, timing, build, None, a.audio, local=True, shim=DOCU / "qa" / "gsap_shim.js")
    print(info)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page(viewport={"width": 1920, "height": 1080})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto("file://" + str(build / "story" / "index.html")); pg.wait_for_timeout(600)
        print("errors:", errs[:6]); wr = pg.evaluate("window.__docuWarnings"); print("warnings:", len(wr), wr[:10]); print("timeline duration", pg.evaluate("window.__timelines.main.duration()"))
        if a.times:
            for t in a.times.split(","):
                pg.evaluate(f"window.__timelines.main.time({float(t)})"); pg.wait_for_timeout(50)
                pg.screenshot(path=str(out / f"f_{float(t):05.2f}.png"))
        if a.mp4:
            fr = out / "frames"; fr.mkdir(exist_ok=True)
            for f in fr.glob("*.png"): f.unlink()
            n = int(round(info["duration"] * 30))
            for i in range(n):
                pg.evaluate(f"window.__timelines.main.time({i / 30})"); pg.screenshot(path=str(fr / f"{i:05d}.png"))
            w, h = a.size.split("x"); vf = [] if (w, h) == ("1920", "1080") else ["-vf", f"scale={w}:{h}:flags=lanczos"]
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", str(fr / "%05d.png")]
            cmd += ["-i", a.sfx] if a.sfx else []
            cmd += vf + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-r", "30"]
            cmd += (["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest"] if a.sfx else []) + ["-movflags", "+faststart", a.mp4]
            subprocess.run(cmd, check=True)
        b.close()
main()
