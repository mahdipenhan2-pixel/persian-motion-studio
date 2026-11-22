#!/usr/bin/env python3
"""Local QA / render for the multi-chapter project (default kim-docu-6min). No network, no TTS.
  render_6min.py --synth --times c1:1,c1:6,c2:10        screenshots of chapters at chapter-relative seconds (synthetic timing, QA only)
  render_6min.py --data DIR --times ...                 real timing (DIR/<chapter>/timing.json, narration.wav published by the audio workflow)
  render_6min.py --data DIR --chapter c1 --mp4 out.mp4  render one chapter silently (frames from the shim timeline), optional --workers N
"""
import argparse, json, subprocess, sys, wave, shutil, concurrent.futures as cf
from pathlib import Path
DOCU = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOCU / "engine"))
import project as P, compose as C  # noqa

def synth(ch, au, cps=14.0, gap=0.3):
    gap = au.get("gap_ms", 300) / 1000.0
    cur, sents = au["lead_in_ms"] / 1000.0, []
    for s in ch["sentences"]:
        dur = round(len(s["text"]) / cps, 3); words = s["text"].split(); tot = sum(len(w) for w in words); acc = 0; rows = []
        for i, w in enumerate(words):
            a = cur + dur * acc / tot; acc += len(w); b = cur + dur * acc / tot
            rows.append({"i": i, "text": w, "abs_start": round(a, 3), "abs_end": round(b, 3), "status": "ok"})
        sents.append({"id": s["id"], "text": s["text"], "offset": round(cur, 3), "duration": dur, "words": rows}); cur += dur + gap
    total = cur - gap + au["tail_ms"] / 1000.0
    return {"summary": {"status": "OK"}, "audio": {"total": round(total, 3), "gap": gap}, "sentences": sents}

def prepare(proj, ch, out, data):
    build = Path(out) / ch["id"]; build.mkdir(parents=True, exist_ok=True)
    core = P.core_config(proj, ch) if hasattr(P, "core_config") else {}
    au = {**{"lead_in_ms": 300, "tail_ms": 500, "gap_ms": 300}, **(proj.get("audio") or {}), **(ch.get("audio") or {})}
    if data and (Path(data) / ch["id"] / "timing.json").exists():
        timing = json.load(open(Path(data) / ch["id"] / "timing.json")); wav = Path(data) / ch["id"] / "narration.wav"; real = True
    else:
        timing = synth(ch, au); wav = build / "silent.wav"; real = False
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * int(24000 * timing["audio"]["total"]))
    if ch.get("target_duration") is None:
        ch = dict(ch); ch["target_duration"] = round(float(timing["audio"]["total"]) * 30 + 0.49) / 30   # whole frames, never shorter than the narration
    info = C.compose(proj, ch, timing, build, None, wav, local=True, shim=DOCU / "qa" / "gsap_shim.js")
    info["real"] = real; info["audio"] = au
    return build, info

def open_page(pw, build, w=1920, h=1080, scale=1.0):
    b = pw.chromium.launch(args=["--no-sandbox"]); pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto("file://" + str(build / "story" / "index.html")); pg.wait_for_timeout(700)
    return b, pg, errs

def render_range(args):
    build, i0, i1, fr, scale, fmt = args
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b, pg, errs = open_page(pw, build, scale=scale)
        for i in range(i0, i1):
            pg.evaluate(f"window.__timelines.main.time({i / 30})")
            pg.screenshot(path=str(fr / f"{i:05d}.{fmt}"), **({"quality": 94} if fmt == "jpg" else {}))
        b.close()
    return i1 - i0

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--project", default="kim-docu-6min"); ap.add_argument("--data"); ap.add_argument("--synth", action="store_true")
    ap.add_argument("--chapter"); ap.add_argument("--every", type=float); ap.add_argument("--from", dest="t_from", type=float, default=0.8); ap.add_argument("--times"); ap.add_argument("--mp4"); ap.add_argument("--workers", type=int, default=2); ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default="/tmp/claude-0/-home-claude/a96ae5db-0896-5ec2-a45b-c8f2c5d499bb/scratchpad/q6")
    a = ap.parse_args()
    proj = P.load(a.project); Path(a.out).mkdir(parents=True, exist_ok=True)
    chs = [c for c in proj["chapters"] if not a.chapter or c["id"] == a.chapter]
    from playwright.sync_api import sync_playwright
    for ch in chs:
        build, info = prepare(proj, ch, a.out, None if a.synth else a.data)
        print(ch["id"], info)
        with sync_playwright() as pw:
            b, pg, errs = open_page(pw, build)
            json.dump(pg.evaluate("window.__docuCues"), open(build / "cues.json", "w"))
            print(" errors:", errs[:6]); wr = pg.evaluate("window.__docuWarnings"); print(" warnings:", len(wr), wr[:10]); print(" timeline", pg.evaluate("window.__timelines.main.duration()"))
            tl = [x for x in (a.times or "").split(",") if x.startswith(ch["id"] + ":")]
            if a.every:
                t = a.t_from
                while t < info["duration"] - 0.2: tl.append(f"{ch['id']}:{t:.2f}"); t += a.every
            for t in tl:
                s = float(t.split(":")[1]); pg.evaluate(f"window.__timelines.main.time({s})"); pg.wait_for_timeout(40)
                pg.screenshot(path=str(Path(a.out) / f"{ch['id']}_{s:06.2f}.png"))
            b.close()
        if a.every:
            from PIL import Image, ImageDraw
            fs = sorted(Path(a.out).glob(f"{ch['id']}_*.png")); per = 9
            for k in range(0, len(fs), per):
                sh = Image.new("RGB", (1920, 1080)); d = ImageDraw.Draw(sh)
                for j, f in enumerate(fs[k:k + per]):
                    im = Image.open(f).resize((640, 360)); sh.paste(im, ((j % 3) * 640, (j // 3) * 360)); d.text(((j % 3) * 640 + 6, (j // 3) * 360 + 340), f.stem, fill=(255, 255, 0))
                sh.save(Path(a.out) / f"sheet_{ch['id']}_{k // per + 1}.png")
        if a.mp4:
            n = int(round(info["duration"] * 30)); fr = Path(a.out) / f"frames_{ch['id']}"; shutil.rmtree(fr, ignore_errors=True); fr.mkdir()
            step = (n + a.workers - 1) // a.workers; jobs = [(build, k * step, min(n, (k + 1) * step), fr, a.scale, "jpg") for k in range(a.workers)]
            with cf.ProcessPoolExecutor(a.workers) as ex: list(ex.map(render_range, jobs))
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", str(fr / "%05d.jpg"), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", a.mp4.replace(".mp4", f"_{ch['id']}.mp4")], check=True)
main()
