"""NFP Film - build the 16:9 HyperFrames composition from project + Stage 2 timing.

Derived from docu/engine/compose.py (docu-16x9-test30, see PROVENANCE.json). Changes:
  * kit: the rig (00_core, 10_chars) is read from C2 (nfp/character/renderers/flat_cartoon_v2/rig, byte-identical to the
    documentary kit files); the style kit from nfp/film/kit. The story-specific scene sets of the source engine (21_scenes, 42_scenes_cine) are not part
    of Film (a cleaned scene library is a later stage).
  * language: 'en' (Inter, LTR) or 'fa' (Vazirmatn with Inter for Latin, RTL); SVG text of the art follows the language.
  * word timing is written as its own data file (words.json, nfp.film.words/1) - the exact source for subtitles,
    highlights and lip sync. story.srt is only a side output and never read back.
  * optional characters (cast_plan.py): the bridge 55_cast_bridge.js + its data join the kit (they must exist before
    the shots run), the C3 runtime + KeyLists are added after the page's own scripts; without characters the page has
    no character code at all.
"""
import html
import json
import shutil
import wave
from pathlib import Path

from untimed import estimate_untimed

ENGINE = Path(__file__).resolve().parent
FILM = ENGINE.parent
ROOT = FILM.parent.parent
RIG = ROOT / "nfp" / "character" / "renderers" / "flat_cartoon_v2" / "rig"
KIT = [("00_core", RIG), ("10_chars", RIG), ("20_backgrounds", FILM / "kit"), ("40_fx", FILM / "kit"),
       ("41_cine", FILM / "kit"), ("50_director", FILM / "kit")]
FPS = 30
CDN_GSAP = '<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>'
FONTS = {
    "en": {"faces": [("Inter", 400, "inter-latin-400-normal.woff2"), ("Inter", 700, "inter-latin-700-normal.woff2"),
                     ("Inter", 800, "inter-latin-800-normal.woff2"), ("Caveat", 700, "caveat-latin-700-normal.woff2")],
           "body": '"Inter", "Noto Sans", "DejaVu Sans", sans-serif', "css": ""},
    "fa": {"faces": [("Vazirmatn", 400, "vazirmatn-arabic-400-normal.woff2"), ("Vazirmatn", 700, "vazirmatn-arabic-700-normal.woff2"),
                     ("Vazirmatn", 800, "vazirmatn-arabic-700-normal.woff2"),
                     ("Inter", 400, "inter-latin-400-normal.woff2"), ("Inter", 700, "inter-latin-700-normal.woff2"),
                     ("Inter", 800, "inter-latin-800-normal.woff2")],
           "body": '"Vazirmatn", "Inter", "Noto Sans", sans-serif',
           # SVG labels of the kit name Inter / Caveat in their own attributes; CSS beats presentation attributes, so
           # Persian art text gets Vazirmatn without touching the byte-identical kit files.
           "css": '  #art text { font-family: "Vazirmatn", "Inter", "Noto Sans", sans-serif !important; }\n'
                  '  .sentence { direction: rtl; unicode-bidi: plaintext; }'},
}


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


def font_faces(fonts_dir, lang):
    names = {p.name for p in Path(fonts_dir).glob("*.woff2")}
    return "\n".join(f'  @font-face {{ font-family: "{f}"; src: url("assets/fonts/{fn}") format("woff2"); font-weight: {w}; font-style: normal; font-display: block; }}'
                     for f, w, fn in FONTS[lang]["faces"] if fn in names)


def words_data(project, timing, target):
    """Exact word timing (the source of truth for subtitles, highlights and lip sync), as its own document."""
    return {"schema": "nfp.film.words/1", "lang": project["meta"]["lang"], "fps": FPS, "duration": target,
            "sentences": [{"id": s["id"], "text": s.get("text", ""), "offset": s["offset"], "duration": s["duration"],
                           "words": [{"i": r["i"], "text": r["text"], "start": r["abs_start"], "end": r["abs_end"],
                                      "timed": r["abs_start"] is not None, "estimated": bool(r.get("est"))}
                                     for r in s["words"]]} for s in timing["sentences"]]}


def compose(project, chapter, timing, build, fonts_dir, narration_wav, cast_fragment="", kit_extra=""):
    if timing["summary"]["status"] == "FAIL":
        raise SystemExit("timing status is FAIL; refusing to build a video from unreliable timestamps.")
    lang = project["meta"]["lang"]
    sub_doc = None
    if "subtitles" in project:          # S3: drawn from <build>/subtitles.json; without the block nothing below changes
        import subtitle_layer as SL
        sub_doc = SL.load_checked(project, chapter, timing, build)
    timing = estimate_untimed(timing)   # words Whisper could not match (numbers) get estimated slots, flagged est=True
    build = Path(build)
    out = build / "story"
    (out / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    if fonts_dir and Path(fonts_dir).exists():
        for f in Path(fonts_dir).glob("*.woff2"):
            shutil.copyfile(f, out / "assets" / "fonts" / f.name)
    shutil.copyfile(FILM / "assets" / "noise.png", out / "assets" / "noise.png")
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
        text = s.get("text") or " ".join(r["text"] for r in s["words"])
        srt.append(f"{n + 1}\n{srt_time(c0)} --> {srt_time(max(c1, c0 + 0.2))}\n{text}\n")

    kit = "\n".join((d / f"{k}.js").read_text(encoding="utf-8") for k, d in KIT)
    if kit_extra:                       # character bridge (+ its data): must exist before the shots run
        kit += "\n" + kit_extra
    shots = (Path(project["_dir"]) / project["shots"]).read_text(encoding="utf-8")
    tl_html = ""
    if "timeline" in project:           # T2 / T4: still images and videos of nfp/timeline; without the block nothing changes
        import timeline_bridge as TB
        tl_js, tl_html = TB.build(project, words_data(project, timing, target), out)
        shots += tl_js
    data = {"duration": target, "fade": 0.18, "sentences": sents}
    page = (ENGINE / "base.html").read_text(encoding="utf-8")
    if sub_doc is not None:
        page = SL.patch_template(page, sub_doc)
        spans_html = [SL.cues_html(sub_doc)]
    F = FONTS[lang]
    rep = {"__LANG__": lang, "__DIR__": "rtl" if lang == "fa" else "ltr", "__BODY_FONT__": F["body"], "__LANG_CSS__": F["css"],
           "__FONT_FACES__": font_faces(out / "assets" / "fonts", lang), "__DURATION__": f"{target:.3f}", "__GSAP__": CDN_GSAP,
           "__SENTENCES_HTML__": "\n    ".join(spans_html), "__KIT__": kit, "__SHOTS__": shots,
           "__TIMELINE_JSON__": json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")}
    for k in ("__LANG__", "__DIR__", "__BODY_FONT__", "__LANG_CSS__", "__FONT_FACES__", "__DURATION__", "__GSAP__", "__SENTENCES_HTML__"):
        if page.count(k) < 1:
            raise SystemExit(f"base.html: placeholder {k} missing")
        page = page.replace(k, rep[k])
    for k in ("__KIT__", "__SHOTS__", "__TIMELINE_JSON__"):   # code/data last: they may contain other placeholders' text
        page = page.replace(k, rep[k])
    if tl_html:                         # T4: video clips straight under the page root, under the SVG layer
        if page.count('  <section id="art"') != 1:
            raise SystemExit("page must contain exactly one art section")
        page = page.replace('  <section id="art"', tl_html + '  <section id="art"', 1)
    if cast_fragment:
        if page.count("</body>") != 1:
            raise SystemExit("page must contain exactly one </body>")
        page = page.replace("</body>", cast_fragment + "</body>")
    (out / "index.html").write_text(page, encoding="utf-8")
    (build / "words.json").write_text(json.dumps(words_data(project, timing, target), ensure_ascii=False, indent=1), encoding="utf-8")
    (build / "story.srt").write_text("\n".join(srt), encoding="utf-8")
    return {"duration": target, "sentences": len(sents), "narration": round(total, 2), "lang": lang}
