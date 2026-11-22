"""Build the 16:9 HyperFrames composition from project + Stage 2 timing."""
import html
import json
import shutil
import subprocess
import wave
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
KIT = ["00_core", "10_chars", "20_backgrounds", "21_scenes", "40_fx", "41_cine", "42_scenes_cine", "50_director"]
FPS = 30


def srt_time(t):
    ms = int(round(max(0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def pad_wav(src, dst, seconds):
    """Pad narration with silence to the exact target length (whole frames)."""
    with wave.open(str(src), "rb") as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    want = int(round(seconds * rate))
    if n > want:
        raise SystemExit(f"narration ({n / rate:.2f}s) is longer than the video target ({seconds}s)")
    with wave.open(str(dst), "wb") as o:
        o.setnchannels(ch); o.setsampwidth(sw); o.setframerate(rate)
        o.writeframes(data + b"\x00" * (sw * ch * (want - n)))


def font_faces(fonts_dir):
    names = {p.name for p in Path(fonts_dir).glob("*.woff2")}
    spec = [("Inter", 400, "inter-latin-400-normal.woff2"), ("Inter", 700, "inter-latin-700-normal.woff2"),
            ("Inter", 800, "inter-latin-800-normal.woff2"), ("Caveat", 700, "caveat-latin-700-normal.woff2")]
    return "\n".join(f'  @font-face {{ font-family: "{f}"; src: url("assets/fonts/{fn}") format("woff2"); font-weight: {w}; font-style: normal; font-display: block; }}'
                     for f, w, fn in spec if fn in names)


def compose(project, chapter, timing, build, fonts_dir, narration_wav, local=False, shim=None):
    if timing["summary"]["status"] == "FAIL":
        raise SystemExit("timing status is FAIL; refusing to build a video from unreliable timestamps.")
    build = Path(build)
    out = build / "story"
    (out / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    if fonts_dir and Path(fonts_dir).exists():
        for f in Path(fonts_dir).glob("*.woff2"):
            shutil.copyfile(f, out / "assets" / "fonts" / f.name)
    shutil.copyfile(ENGINE / "assets" / "noise.png", out / "assets" / "noise.png")
    target = float(chapter.get("target_duration") or project["meta"].get("target_duration") or timing["audio"]["total"])
    target = round(target * FPS) / FPS
    pad_wav(narration_wav, out / "narration.wav", target)

    sents, srt, spans_html = [], [], []
    S = timing["sentences"]
    total = float(timing["audio"]["total"])
    for n, s in enumerate(S):
        timed = [r for r in s["words"] if r["abs_start"] is not None]
        if not timed:
            raise SystemExit(f"sentence {s['id']} has no timed words")
        spans, words = [], []
        for r in s["words"]:
            wid = f"w-{s['id']}-{r['i']}"
            spans.append(f'<span class="w" id="{wid}">{html.escape(r["text"])}</span>')
            if r["abs_start"] is not None:
                words.append({"id": wid, "start": r["abs_start"], "end": r["abs_end"], "hl": True})
            else:
                nxt = next((x["abs_start"] for x in s["words"][r["i"] + 1:] if x["abs_start"] is not None), s["offset"] + s["duration"])
                words.append({"id": wid, "start": round(nxt, 3), "end": round(nxt + 0.06, 3), "hl": False})
        spans_html.append(f'<div class="sentence" id="sent-{s["id"]}">{" ".join(spans)}</div>')
        sents.append({"id": s["id"], "start": s["offset"], "end": round(s["offset"] + s["duration"], 3), "words": words})
        nxt_off = S[n + 1]["offset"] if n + 1 < len(S) else total
        c0 = max(s["offset"], timed[0]["abs_start"] - 0.05)
        c1 = min(timed[-1]["abs_end"] + 0.15, nxt_off - 0.02)
        srt.append(f"{n + 1}\n{srt_time(c0)} --> {srt_time(max(c1, c0 + 0.2))}\n{s['text']}\n")

    kit = "\n".join((ENGINE / "kit" / f"{k}.js").read_text(encoding="utf-8") for k in KIT)
    shots = (Path(project["_dir"]) / project["shots"]).read_text(encoding="utf-8")
    data = {"duration": target, "fade": 0.18, "sentences": sents}
    page = (ENGINE / "base.html").read_text(encoding="utf-8")
    gsap = ('<script src="gsap_shim.js"></script>' if local else '<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>')
    if local:
        shutil.copyfile(shim, out / "gsap_shim.js")
    rep = {"__FONT_FACES__": font_faces(out / "assets" / "fonts"), "__DURATION__": f"{target:.3f}", "__GSAP__": gsap,
           "__SENTENCES_HTML__": "\n    ".join(spans_html), "__KIT__": kit, "__SHOTS__": shots,
           "__TIMELINE_JSON__": json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")}
    for k in ("__FONT_FACES__", "__DURATION__", "__GSAP__", "__SENTENCES_HTML__"):
        page = page.replace(k, rep[k])
    for k in ("__KIT__", "__SHOTS__", "__TIMELINE_JSON__"):   # code/data last: they may contain other placeholders' text
        page = page.replace(k, rep[k])
    (out / "index.html").write_text(page, encoding="utf-8")
    (build / "story.srt").write_text("\n".join(srt), encoding="utf-8")
    return {"duration": target, "sentences": len(sents), "narration": round(total, 2)}
