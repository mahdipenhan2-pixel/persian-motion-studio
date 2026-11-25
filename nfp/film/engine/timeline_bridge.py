"""NFP Film - Timeline bridge (T2 + T4 + Map Motion M2g + Graphics G5): still images (Ken Burns), video clips, map clips
and graphic clips of nfp/timeline on the Film page.
The ONLY Film file that imports nfp/timeline, and only for projects that ask for it:

  project.json  "timeline": {"file": "timeline.json", "assets": "assets.json"}     (both inside the project folder)

compose.py (only when the block is present) appends the code made here to the project's shots, so it runs in the same
place, through the same public Director API as every shot: D.shot (frame window), S.layer (a layer at depth 0, under
the global grain / vignette / VHS post layers), S.q and D.key (scale and position, one ease, the clip's own duration).
Every image clip of a visual track becomes one full-frame shot drawn above the project's own shots for its window.

Before anything is drawn the timeline is checked by nfp/timeline (schema, frames, anchors against this video's word
timing, assets: file + sha256 + PNG / JPEG size, licence; camera: cover fit, no empty space, enlargement). Errors stop
compose; a draft (unverified) asset is allowed only in a draft timeline and is reported. The image files are copied
into story/assets/timeline/. Clip kinds that later stages draw (video, map, motion, animation, overlay images) are
refused with a clear message (map clips are drawn since M2g: see _maps); svg-shot / narration / subtitles / character
clips are data about the other engines and
draw nothing here. A timeline with no image clip adds nothing: the page is the page without the block.

T4 video clips (visual track, full frame): only what T3 proved frame-exact in a real HyperFrames 0.9.83 render is
accepted - H.264, yuv420p, constant 25 / 30 fps, starting at 0, no rotation (checked with ffprobe HERE, the only place
that runs ffprobe; nfp/timeline checks the facts). Each clip becomes a <video> straight under the page root (HyperFrames
needs that) placed UNDER the SVG layer: while it shows, the Director's world (every shot) is hidden through the public
D.key, so the page's own post layers - grain, vignette, scan lines, VHS cuts - lie over the video exactly as over any
shot. The video is always muted (its own sound never reaches the film), drawn 'cover' (aspect kept, no stretch), and
reads source frames in .. out - 1 of its file (frame mapping of HyperFrames, see nfp/timeline/videofile.py); a clip that
would run past the last frame is refused (no frozen last frame).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
NFP = ENGINE.parent.parent
KEYS = {"file", "assets"}
LATER = ("motion", "animation")


def _tl():
    if str(NFP) not in sys.path:
        sys.path.insert(0, str(NFP))
    import timeline as TL                          # nfp/timeline (imported only here, only for timeline projects)
    from timeline import kenburns as KB
    from timeline import imagefile as IF
    return TL, KB, IF


def config(project):
    v = project.get("timeline")
    if not isinstance(v, dict) or set(v) - KEYS or not isinstance(v.get("file"), str):
        raise SystemExit("ERROR (timeline): project.timeline must be {\"file\": \"timeline.json\", \"assets\": \"assets.json\"}")
    out = {}
    for k in KEYS:
        if k in v:
            if not isinstance(v[k], str) or Path(v[k]).is_absolute() or ".." in Path(v[k]).parts:
                raise SystemExit(f"ERROR (timeline): timeline.{k} must be a relative path inside the project")
            out[k] = Path(project["_dir"]) / v[k]
    return out


def _num(v):
    return repr(round(float(v), 6))


def probe(path):
    """ffprobe facts of a local video: streams, format and the time of every video packet (no network)."""
    def run(*args):
        r = subprocess.run(["ffprobe", "-v", "error", *args, "-of", "json", str(path)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "ffprobe failed").strip()[:200])
        return json.loads(r.stdout)
    info = run("-show_streams", "-show_format")
    pk = run("-select_streams", "v:0", "-show_entries", "packet=pts_time")
    return {"streams": info.get("streams", []), "format": info.get("format", {}),
            "packets": [x.get("pts_time") for x in pk.get("packets", [])]}


def fragment(project, words_doc, story_dir):
    """JS of the image / video clips (appended to the shots); '' when none. (T2 name; see build() for the video HTML.)"""
    return build(project, words_doc, story_dir)[0]


def build(project, words_doc, story_dir):
    """(JS appended to the shots, HTML placed under the page root before the SVG layer); ('', '') when nothing to draw.
    Images and videos are copied to story/assets/timeline/."""
    TL, KB, IF = _tl()
    from timeline import videofile as VF
    cfg = config(project)
    try:
        doc = json.loads(cfg["file"].read_text(encoding="utf-8"))
        adoc = json.loads(cfg["assets"].read_text(encoding="utf-8")) if "assets" in cfg else None
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"ERROR (timeline): cannot read the timeline / asset files: {e}")
    ctx = TL.Context.from_words(words_doc)
    rep = TL.validate(doc, adoc, cfg["assets"].parent if "assets" in cfg else None, ctx, check_files=True, probe=probe)
    errs = [x for x in rep["issues"] if x["level"] == "error"]
    if errs:
        raise SystemExit("ERROR (timeline): " + "; ".join(
            f"{x.get('clip') or x.get('asset') or x.get('track') or '-'}: {x['message']}" for x in errs[:12]))
    for x in rep["issues"]:
        if x["level"] == "warning":
            print(f"timeline warning: {x.get('clip') or x.get('asset') or '-'}: {x['message']}", file=sys.stderr)
    kinds = {t["id"]: t["kind"] for t in doc["tracks"]}
    assets = {a["id"]: a for a in (adoc or {}).get("assets", [])}
    todo, videos, maps, gfx_full, gfx_over = [], [], [], [], []
    for c in doc["clips"]:
        tk = kinds[c["track"]]
        if tk in ("visual", "overlay") and c["kind"] == "graphic":      # G5: nfp/graphics; the track gives the display
            (gfx_full if tk == "visual" else gfx_over).append(c)
            continue
        if tk in ("visual", "overlay") and c["kind"] == "map":          # M2g: nfp/mapmotion, full frame only
            if tk != "visual":
                raise SystemExit(f"ERROR (timeline): clip {c['id']}: map clips on an overlay track are not drawn yet (full-frame only)")
            maps.append(c)
            continue
        if tk in ("visual", "overlay") and c["kind"] in LATER:
            raise SystemExit(f"ERROR (timeline): clip {c['id']}: {c['kind']} clips are not drawn yet (T4 draws still images and videos)")
        if c["kind"] in ("image", "video"):
            if tk != "visual":
                raise SystemExit(f"ERROR (timeline): clip {c['id']}: {c['kind']} clips on an overlay track are not drawn yet (full-frame only)")
            (todo if c["kind"] == "image" else videos).append(c)
    for v in videos:
        for c in todo:
            if c["start"] < v["end"] and v["start"] < c["end"]:
                raise SystemExit(f"ERROR (timeline): video clip {v['id']} and image clip {c['id']} overlap (frames "
                                 f"{max(c['start'], v['start'])}..{min(c['end'], v['end']) - 1}): one full-frame picture at a time")
    for k, m in enumerate(maps):                                       # one full-frame picture at a time
        for o in videos + todo + maps[k + 1:]:
            if m["start"] < o["end"] and o["start"] < m["end"]:
                raise SystemExit(f"ERROR (timeline): {o['kind']} clip {o['id']} and map clip {m['id']} overlap (frames "
                                 f"{max(m['start'], o['start'])}..{min(m['end'], o['end']) - 1}): one full-frame picture at a time")
    for k, g in enumerate(gfx_full):                                    # a full-frame graphic is a picture too
        for o in videos + todo + maps + gfx_full[k + 1:]:
            if g["start"] < o["end"] and o["start"] < g["end"]:
                raise SystemExit(f"ERROR (timeline): {o['kind']} clip {o['id']} and full-frame graphic clip {g['id']} overlap (frames "
                                 f"{max(g['start'], o['start'])}..{min(g['end'], o['end']) - 1}): one full-frame picture at a time")
    if not todo and not videos and not maps and not gfx_full and not gfx_over:
        return "", ""
    js, html = "", ""
    if todo or videos:
        dst = Path(story_dir) / "assets" / "timeline"
        dst.mkdir(parents=True, exist_ok=True)
        js, html = (_images(todo, assets, cfg, dst, KB, IF) if todo else ""), ""
        if videos:
            js2, html = _videos(videos, assets, cfg, dst, KB, VF)
            js += js2
    if maps:
        js += _maps(maps, project, words_doc, story_dir, TL, doc.get("mode", "draft"))
    if gfx_full or gfx_over:
        js += _graphics(gfx_full, gfx_over, project, story_dir, doc.get("mode", "draft"))
    return js, html


def _graphics(full, over, project, story_dir, mode="draft"):
    """G5: graphic clips (nfp/graphics). Each clip's ref is a graphic document (nfp.graphics/1) inside the project; its
    track gives the display (visual: full frame - a Director shot; overlay: the graphics layer between #world and #post).
    Text is measured HERE (graphics.tools.measure: the local Chromium with the film's own font copies in
    story/assets/fonts; nothing is downloaded), as for map labels. Errors stop compose; warnings are printed; the QC of
    every graphic clip is written to <build>/graphics_qc.json."""
    from graphics import filmclip as GF                    # nfp/graphics (imported only here, only for graphic clips)
    from graphics.tools import measure as GM
    from mapmotion.tools.measure import FACES
    fonts = Path(story_dir) / "assets" / "fonts"
    done, report = {}, []
    for c in sorted(full + over, key=lambda c: (c["start"], c["id"])):
        tk = "visual" if c in full else "overlay"
        if not (isinstance(c.get("ref"), str) and c["ref"]):
            raise SystemExit(f"ERROR (graphic): clip {c['id']}: a graphic clip needs ref (its graphic document, nfp.graphics/1)")
        if c.get("asset") is not None:
            raise SystemExit(f"ERROR (graphic): clip {c['id']}: a graphic clip takes its data from ref, not from an asset")
        try:
            spec, warns = GF.prepare(GF.load(c["ref"], project["_dir"]), c, tk, mode)
            missing = [f for _, _, f in FACES if not (fonts / f).is_file()]
            if missing:
                raise ValueError(f"graphics need the film's local fonts: {', '.join(missing)} not in assets/fonts")
            metrics = GM.measure_graphic(spec, fonts)
            lay, warns2 = GF.finish(spec, metrics)
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            raise SystemExit(f"ERROR (graphic): clip {c['id']}: {e}")
        for x in warns + warns2:
            print(f"graphic warning: {c['id']}: {x.get('element') or '-'}: {x['code']}: {x['message']}", file=sys.stderr)
        done[c["id"]] = (c, spec, lay)
        report.append({"clip": c["id"], "ref": c["ref"], "frames": [c["start"], c["end"]], "display": spec["display"],
                       "kind": spec["kind"], "mode": spec["mode"], "draft_badge": spec["draft_badge"], "rect": lay["rect"],
                       "issues": warns + warns2, "text_measured_with": metrics.get("browser")})
    overlays = [done[c["id"]] for c in sorted(over, key=lambda c: (c["start"], c["id"]))]
    for a, b, f0, f1 in GF.clashes(overlays):
        raise SystemExit(f"ERROR (graphic): overlay clips {a} and {b} cover each other on frames {f0}..{f1}: overlays shown together must not overlap")
    css = GF.font_css_rel(FACES)
    js = "".join(GF.fullframe_js(*done[c["id"]], font_css=css) for c in sorted(full, key=lambda c: (c["start"], c["id"])))
    js += GF.overlay_js(overlays, font_css=css)
    (Path(story_dir).parent / "graphics_qc.json").write_text(
        json.dumps({"schema": "nfp.graphics.filmqc/1", "clips": report}, ensure_ascii=False, indent=1), encoding="utf-8")
    return js


def _maps(maps, project, words_doc, story_dir, TL, mode="draft"):
    """M2g: map clips (nfp/mapmotion) - each one Director shot for its frames (mapmotion.filmclip). The clip's ref is a
    map clip bundle (nfp.mapmotion.clip/1) inside the project. Label text is measured HERE (mapmotion.tools.measure: the
    local Chromium with the film's own font copies in story/assets/fonts; nothing is downloaded) - like ffprobe above,
    the bridge runs the outside programs, Map Motion's engine does not. Errors stop compose; warnings are printed like
    the timeline's own; the QC of every map clip is written to <build>/mapmotion_qc.json (next to verify.json).
    A final timeline takes only a final map and scene (their own final checks: verified locations and licences)."""
    from mapmotion import filmclip as FC                  # nfp/mapmotion (imported only here, only for map clips)
    from mapmotion.tools import measure as MS
    fonts = Path(story_dir) / "assets" / "fonts"
    ctx = TL.Context.from_words(words_doc)
    js, report = "", []
    for c in sorted(maps, key=lambda c: (c["start"], c["id"])):
        if not (isinstance(c.get("ref"), str) and c["ref"]):
            raise SystemExit(f"ERROR (map): clip {c['id']}: a map clip needs ref (its map clip bundle, nfp.mapmotion.clip/1)")
        if c.get("asset") is not None:
            raise SystemExit(f"ERROR (map): clip {c['id']}: a map clip takes its data from ref, not from an asset")
        try:
            docs = FC.load(c["ref"], project["_dir"])
            if mode == "final" and any(not isinstance(docs[k], dict) or docs[k].get("mode") != "final" for k in ("map", "scene")):
                raise ValueError("a final timeline needs the map and its scene in final mode (verified locations and licences)")
            prep = FC.prepare(docs, ctx, c)
            metrics = None
            if prep["texts"]:
                missing = [f for _, _, f in MS.FACES if not (fonts / f).is_file()]
                if missing:
                    raise ValueError(f"the map's labels need the film's local fonts: {', '.join(missing)} not in assets/fonts")
                metrics = MS.measure(prep["texts"], prep["size"], prep["weight"], fonts)
            sp = FC.finish(docs, prep, metrics)
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            raise SystemExit(f"ERROR (map): clip {c['id']}: {e}")
        warns = [x for x in sp["qc"]["issues"] if x["level"] == "warning"]
        for x in warns:
            print(f"map warning: {c['id']}: {x.get('element') or '-'}: {x['code']}: {x['message']}", file=sys.stderr)
        js += FC.shot_js(sp, prep["plan"], c["id"], FC.font_face_css_rel(MS.FACES) if prep["texts"] else "")
        report.append({"clip": c["id"], "ref": c["ref"], "frames": [c["start"], c["end"]], "status": sp["qc"]["status"],
                       "issues": sp["qc"]["issues"], "labels_measured_with": (metrics or {}).get("browser")})
    (Path(story_dir).parent / "mapmotion_qc.json").write_text(
        json.dumps({"schema": "nfp.mapmotion.filmqc/1", "clips": report}, ensure_ascii=False, indent=1), encoding="utf-8")
    return js


def _videos(videos, assets, cfg, dst, KB, VF):
    """<video> elements (root level, under the SVG) + the JS that hides the Director's world while one shows."""
    tags, wins = [], []
    for c in sorted(videos, key=lambda c: (c["start"], c["id"])):
        a = assets[c["asset"]]
        src = cfg["assets"].parent / a["local_path"]
        fx = VF.facts(probe(src))                     # validated above; the same facts again for in-point -> seconds
        name = f"{a['id']}.mp4"
        if not (dst / name).exists():
            shutil.copyfile(src, dst / name)
        _, Wc, Hc = KB.cover(fx["width"], fx["height"])
        first = c.get("in", 0)
        lo, out = VF.source_frames(c["start"], c["end"], first, fx["fps"])
        tags.append(f'  <video id="tlv-{c["id"]}" class="clip" src="assets/timeline/{name}" data-start="{c["start"] / 30!r}" '
                    f'data-duration="{(c["end"] - c["start"]) / 30!r}" data-media-start="{VF.media_start(first, fx["fps"])!r}" '
                    f'data-track-index="1" muted playsinline preload="auto" style="position:absolute;left:{_num((1920 - Wc) / 2)}px;'
                    f'top:{_num((1080 - Hc) / 2)}px;width:{_num(Wc)}px;height:{_num(Hc)}px;object-fit:fill"></video>'
                    f'<!-- frames {c["start"]}..{c["end"] - 1}: source frames {lo}..{out - 1} at {fx["fps"]} fps -->\n')
        if wins and wins[-1][1] >= c["start"]:
            wins[-1][1] = max(wins[-1][1], c["end"])
        else:
            wins.append([c["start"], c["end"]])
    lines = ["", "  /* ===== timeline (nfp/timeline T4): full-frame videos under the film look - the world is hidden while one shows ===== */"]
    for a0, a1 in wins:
        # display, not visibility: every shot sets visibility: visible on itself, which a hidden parent does not override
        lines.append(f"  D.key(D.world, \"display\", {a0 / 30!r}, \"none\", 0); D.key(D.world, \"display\", {a1 / 30!r}, \"inline\", 0);"
                     f"   // frames {a0}..{a1 - 1}")
    return "\n".join(lines) + "\n", "".join(tags)


def _images(todo, assets, cfg, dst, KB, IF):
    lines = ["", "  /* ===== timeline (nfp/timeline T2): still images, Ken Burns camera ===== */"]
    for c in sorted(todo, key=lambda c: (c["start"], c["id"])):
        a = assets[c["asset"]]
        src = cfg["assets"].parent / a["local_path"]
        fmt = IF.info(src)["format"]
        name = f"{a['id']}.{'jpg' if fmt == 'jpeg' else 'png'}"
        if not (dst / name).exists():
            shutil.copyfile(src, dst / name)
        w, h = a["width"], a["height"]
        _, Wc, Hc = KB.cover(w, h)
        cam = KB.expand(c.get("camera"), w, h)
        s0, x0, y0 = KB.transform(cam["from"], w, h)
        s1, x1, y1 = KB.transform(cam["to"], w, h)
        part = f"kb-{c['id']}"
        body = [f"S.layer('<g data-p=\"{part}\"><image href=\"assets/timeline/{name}\" x=\"0\" y=\"0\" width=\"{_num(Wc)}\" "
                f"height=\"{_num(Hc)}\" preserveAspectRatio=\"none\"/></g>', 0);",
                f"const e = S.q(\"{part}\");",
                f"D.key(e, \"--s\", S.t0, {_num(s0)}, 0); D.key(e, \"--x\", S.t0, {_num(x0)}, 0); D.key(e, \"--y\", S.t0, {_num(y0)}, 0);"]
        if (s0, x0, y0) != (s1, x1, y1):
            ease = json.dumps(cam["ease"])
            body.append(f"D.key(e, \"--s\", S.t0, {_num(s1)}, S.dur, {ease}); D.key(e, \"--x\", S.t0, {_num(x1)}, S.dur, {ease}); "
                        f"D.key(e, \"--y\", S.t0, {_num(y1)}, S.dur, {ease});")
        lines.append(f"  D.shot({{ id: \"tl-{c['id']}\", a: {_num(c['start'] / 30)}, b: {_num(c['end'] / 30)},   "
                     f"// frames {c['start']}..{c['end'] - 1}, {cam['preset']}\n    build(S) {{\n      " + "\n      ".join(body) + "\n    } });")
    return "\n".join(lines) + "\n"
