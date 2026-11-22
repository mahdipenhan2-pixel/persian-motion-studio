#!/usr/bin/env python3
"""Local QA: synthetic timing (14 chars/s) -> compose with the GSAP stand-in -> screenshots / mp4 (silent).
usage: local_render.py <project> --times 1,2,3 | --mp4 out.mp4 [--every N]"""
import argparse, json, math, subprocess, sys, wave
from pathlib import Path
DOCU = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOCU / "engine"))
import project as P, compose as C  # noqa

def synth_timing(ch, cps=14.0, lead=0.3, gap=0.3, tail=0.5):
    cur, sents = lead, []
    for s in ch["sentences"]:
        dur = round(len(s["text"]) / cps, 3); words = s["text"].split()
        tot = sum(len(w) for w in words); acc = 0; rows = []
        for i, w in enumerate(words):
            a = cur + dur * acc / tot; acc += len(w); b = cur + dur * acc / tot
            rows.append({"i": i, "text": w, "abs_start": round(a, 3), "abs_end": round(b, 3), "status": "ok"})
        sents.append({"id": s["id"], "text": s["text"], "offset": round(cur, 3), "duration": dur, "words": rows}); cur += dur + gap
    total = cur - gap + tail
    return {"summary": {"status": "OK"}, "audio": {"total": round(total, 3), "gap": gap}, "sentences": sents}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--times"); ap.add_argument("--mp4"); ap.add_argument("--every", type=int, default=1); ap.add_argument("--words", help="json {sid:[[word,start,end],..]} taken from the real timing report")
    ap.add_argument("--out", default="/tmp/claude-0/-home-claude/a96ae5db-0896-5ec2-a45b-c8f2c5d499bb/scratchpad/qa")
    a = ap.parse_args()
    proj = P.load(a.project); ch = proj["chapters"][0]
    build = Path(a.out) / "build"; build.mkdir(parents=True, exist_ok=True)
    timing = synth_timing(ch)
    if a.words:  # real word times (from the CI timing report) instead of the synthetic 14 chars/s
        wd = json.load(open(a.words)); cur = []
        for s in timing["sentences"]:
            rows = wd[s["id"]]; ws = s["text"].split()
            out = []
            for i, w in enumerate(ws):
                r = rows[i] if i < len(rows) and rows[i][0].strip() == w.strip() else None
                out.append({"i": i, "text": w, "abs_start": r[1] if r else None, "abs_end": r[2] if r else None, "status": "ok" if r else "unmatched"})
            timed = [x for x in out if x["abs_start"] is not None]
            s["offset"] = timed[0]["abs_start"]; s["duration"] = round(timed[-1]["abs_end"] - timed[0]["abs_start"] + (0.7 if s["id"] == "s6" else 0.0), 3); s["words"] = out
        timing["audio"]["total"] = 31.7
    (build / "timing.json").write_text(json.dumps(timing))
    with wave.open(str(build / "narration.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * int(24000 * timing["audio"]["total"]))
    info = C.compose(proj, ch, timing, build, None, build / "narration.wav", local=True, shim=DOCU / "qa" / "gsap_shim.js")
    print(info)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page(viewport={"width": 1920, "height": 1080})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto("file://" + str(build / "story" / "index.html")); pg.wait_for_timeout(500)
        print("errors:", errs[:5]); print("warnings:", pg.evaluate("window.__docuWarnings").__len__(), pg.evaluate("window.__docuWarnings")[:8])
        dur = pg.evaluate("window.__timelines.main.duration()"); print("timeline duration", dur)
        if a.times:
            for t in a.times.split(","):
                pg.evaluate(f"window.__timelines.main.time({float(t)})"); pg.wait_for_timeout(60)
                pg.screenshot(path=str(Path(a.out) / f"f_{float(t):05.2f}.png"))
        if a.mp4:
            fr = Path(a.out) / "frames"; fr.mkdir(exist_ok=True)
            for f in fr.glob("*.png"): f.unlink()
            n = int(round(info["duration"] * 30))
            for i in range(0, n, a.every):
                pg.evaluate(f"window.__timelines.main.time({i / 30})"); pg.screenshot(path=str(fr / f"{i // a.every:05d}.png"))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(30 / a.every), "-i", str(fr / "%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", a.mp4], check=True)
        b.close()
main()
