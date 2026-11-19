"""Build the HyperFrames composition (index.html), SRT and fonts from the project + Stage 2 timing."""
import html
import json
import shutil
from pathlib import Path

import scene_templates as st
from icons import svg

ENGINE = Path(__file__).resolve().parent
PLACEHOLDERS = ("__LANG__", "__DIR__", "__FONT_FACES__", "__THEME_VARS__", "__PROGRESS_ORIGIN__", "__HANDLE_HTML__",
                "__CAPTION_SIZE__", "__CAPTION_LH__", "__CREAM__", "__HL__", "__INK__", "__DURATION__",
                "__SCENES_HTML__", "__SENTENCES_HTML__", "__TIMELINE_JSON__")


def srt_time(t):
    ms = int(round(max(0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def font_faces(fonts_dir):
    names = {p.name for p in fonts_dir.glob("*.woff2")}
    faces = []
    spec = [("Vazirmatn", 400, "vazirmatn-arabic-400-normal.woff2"), ("Vazirmatn", 700, "vazirmatn-arabic-700-normal.woff2"),
            ("Inter", 400, "inter-latin-400-normal.woff2"), ("Inter", 700, "inter-latin-700-normal.woff2")]
    for fam, w, fn in spec:
        if fn in names:
            faces.append(f'  @font-face {{ font-family: "{fam}"; src: url("assets/fonts/{fn}") format("woff2");'
                         f' font-weight: {w}; font-style: normal; font-display: block; }}')
    return "\n".join(faces), names


def rgb(t):
    return ",".join(str(int(x)) for x in t)


def compose(project, theme, timing, build, fonts_dir, narration_wav):
    if timing["summary"]["status"] == "FAIL":
        raise SystemExit("timing status is FAIL; refusing to build a video from unreliable timestamps.")
    fonts_dir = Path(fonts_dir)
    faces, names = font_faces(fonts_dir)
    if not any(n.startswith("vazirmatn") for n in names):
        raise SystemExit("assets/fonts/vazirmatn-*.woff2 not found; the font installation step must run first")
    story = Path(build) / "story"
    (story / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    for f in fonts_dir.glob("*.woff2"):
        shutil.copyfile(f, story / "assets" / "fonts" / f.name)
    shutil.copyfile(narration_wav, story / "narration.wav")

    lang = project["meta"]["lang"]
    meta = timing["audio"]
    total, gap = float(meta["total"]), float(meta["gap"])
    fade = round(min(0.18, gap / 3), 3)

    # ---- sentences / captions (same word-level logic as the locked Stage 2 composer) ----
    html_parts, tl_sents, srt = [], [], []
    sents = timing["sentences"]
    for n, s in enumerate(sents):
        spans, words = [], []
        timed = [r for r in s["words"] if r["abs_start"] is not None]
        if not timed:
            raise SystemExit(f"sentence {s['id']} has no timed words")
        for r in s["words"]:
            wid = f"w-{s['id']}-{r['i']}"
            spans.append(f'<span class="w" id="{wid}">{html.escape(r["text"])}</span>')
            if r["abs_start"] is not None:
                words.append({"id": wid, "start": r["abs_start"], "end": r["abs_end"], "hl": True,
                              "quality": r.get("timing_quality", "unknown")})
            elif r["status"] == "unmatched":
                nxt = next((x["abs_start"] for x in s["words"][r["i"] + 1:] if x["abs_start"] is not None),
                           s["offset"] + s["duration"])
                words.append({"id": wid, "start": round(nxt, 3), "end": round(nxt + 0.06, 3), "hl": False})
        html_parts.append(f'<div class="sentence" id="sent-{s["id"]}">{" ".join(spans)}</div>')
        tl_sents.append({"id": s["id"], "start": s["offset"], "end": round(s["offset"] + s["duration"], 3), "words": words})
        nxt_off = sents[n + 1]["offset"] if n + 1 < len(sents) else total
        c0 = max(s["offset"], timed[0]["abs_start"] - 0.05)
        c1 = min(timed[-1]["abs_end"] + 0.15, nxt_off - 0.02)
        srt.append(f"{n + 1}\n{srt_time(c0)} --> {srt_time(max(c1, c0 + 0.2))}\n{s['text']}\n")

    # ---- scenes ----
    by_scene = {}
    for s in sents:
        by_scene.setdefault(s["id"].rsplit("_", 1)[0], []).append(s)
    scene_parts, tl_scenes = [], []
    for sc in project["scenes"]:
        group = by_scene.get(sc["id"])
        if not group:
            raise SystemExit(f"scene {sc['id']} has no timed sentences")
        top, bottom = st.render(sc["template"], sc["on_screen"])
        di = st.deco_icon(sc)
        deco = f'<div class="deco">{svg(di, 360)}</div>' if di else ""
        scene_parts.append(f'<div class="scene" id="scene-{sc["id"]}">{deco}<div class="zt">{top}</div>'
                           f'<div class="zb">{bottom}</div></div>')
        tl_scenes.append({"id": sc["id"], "start": group[0]["offset"],
                          "end": round(group[-1]["offset"] + group[-1]["duration"], 3)})

    data = {"duration": round(total, 3), "fade": fade, "scenes": tl_scenes, "sentences": tl_sents}
    data_js = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    handle = project["meta"].get("handle", "").strip()
    rtl = lang == "fa"
    values = {
        "__LANG__": lang, "__DIR__": "rtl" if rtl else "ltr", "__FONT_FACES__": faces,
        "__THEME_VARS__": "\n".join(f"    {k}: {v};" for k, v in theme["vars"].items()),
        "__PROGRESS_ORIGIN__": "right" if rtl else "left",
        "__HANDLE_HTML__": f'<div id="handle">{html.escape(handle)}</div>' if handle else "",
        "__CAPTION_SIZE__": "72" if rtl else "66", "__CAPTION_LH__": "1.8" if rtl else "1.5",
        "__CREAM__": rgb(theme["cream_rgb"]), "__HL__": rgb(theme["highlight_rgb"]), "__INK__": rgb(theme["ink_rgb"]),
        "__DURATION__": f"{total:.3f}", "__SCENES_HTML__": "\n    ".join(scene_parts),
        "__SENTENCES_HTML__": "\n    ".join(html_parts), "__TIMELINE_JSON__": data_js,
    }
    page = (ENGINE / "base.html").read_text(encoding="utf-8")
    for ph in PLACEHOLDERS:
        if ph not in page:
            raise SystemExit(f"base.html is missing placeholder {ph}")
    # data first: it may contain '__'-like text only inside JSON strings, so substitute it last
    for k in PLACEHOLDERS:
        if k not in ("__TIMELINE_JSON__", "__SCENES_HTML__", "__SENTENCES_HTML__"):
            page = page.replace(k, values[k])
    for k in ("__SCENES_HTML__", "__SENTENCES_HTML__", "__TIMELINE_JSON__"):
        page = page.replace(k, values[k])
    (story / "index.html").write_text(page, encoding="utf-8")
    (Path(build) / "story.srt").write_text("\n".join(srt), encoding="utf-8")
    return {"duration": total, "scenes": len(tl_scenes), "sentences": len(tl_sents), "fade": fade}
