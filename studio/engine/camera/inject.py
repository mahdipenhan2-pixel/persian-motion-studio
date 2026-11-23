"""
Extend a composed Studio page (index.html written by the UNCHANGED compose.py) with camera motion.

What is added, and where:
  </head>                          -> <style id="nfp-camera-css"> (camera.css with theme colours)
  <div class="scene" id="scene-X"> -> media frame as the first child; scene graphics wrapped in .cam-graphics
                                      when the scene-graphics target is used
  </body>                          -> <script id="nfp-camera"> (camera.js + the pre-computed plan)

The caption layer (<section id="stage">) is never touched. All tween times and values are computed here from the
page's own timeline data (const DATA = ...), so camera.js only replays numbers.
"""
import hashlib
import html
import json
import re
from pathlib import Path

from . import presets as PR
from .presets import CameraError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
MIN_MOVE_SEC = 0.3


def check_anchor_files():
    """Stop if base.html / compose.py changed since the anchors were verified."""
    spec = json.loads((HERE / "ANCHORS.json").read_text(encoding="utf-8"))
    changed = []
    for rel, want in spec["files"].items():
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        if got != want:
            changed.append(rel)
    if changed:
        raise CameraError("camera anchors are unverified because these files changed: " + ", ".join(changed)
                          + ". Run python3 studio/tests/test_camera.py t2 and update studio/engine/camera/ANCHORS.json.")


def _once(page, needle):
    n = page.count(needle)
    if n != 1:
        raise CameraError(f"anchor {needle!r} found {n} times in index.html (expected exactly 1)")
    return page.index(needle)


def read_timeline_data(page):
    i = _once(page, "const DATA = ") + len("const DATA = ")
    data, _ = json.JSONDecoder().raw_decode(page[i:])
    for k in ("duration", "fade", "scenes", "sentences"):
        if k not in data:
            raise CameraError(f"timeline data has no '{k}'")
    return data


def _scene_block(page, scene_id):
    """(start, inner_start, inner_end, end) of <div class="scene" id="scene-ID">...</div> using balanced div counting."""
    opener = f'<div class="scene" id="scene-{scene_id}">'
    start = _once(page, opener)
    inner_start = start + len(opener)
    depth, pos = 1, inner_start
    tag = re.compile(r"<div\b|</div>")
    while depth:
        m = tag.search(page, pos)
        if not m:
            raise CameraError(f"scene-{scene_id}: closing </div> not found")
        depth += 1 if m.group(0) == "<div" else -1
        pos = m.end()
    inner_end = pos - len("</div>")
    return start, inner_start, inner_end, pos


def _hex_rgb(v):
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", str(v).strip())
    if not m:
        raise CameraError(f"theme --bg must be a #rrggbb colour, got {v!r}")
    h = m.group(1)
    return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))


def scene_spans(data):
    """Visible window of every scene: from its fade-in to the next scene's start (same rules as base.html)."""
    total, fade = float(data["duration"]), float(data["fade"])
    scenes = data["scenes"]
    spans = {}
    for i, sc in enumerate(scenes):
        t0 = 0.0 if i == 0 else max(0.0, float(sc["start"]) - fade)
        t1 = float(scenes[i + 1]["start"]) if i + 1 < len(scenes) else total
        spans[sc["id"]] = (round(t0, 4), round(min(t1, total), 4))
    return spans


def _props(state):
    return {"scale": state["s"], "x": state["x"], "y": state["y"]}


def build_plan(plan, data, media_src):
    """Turn the validated camera plan into absolute-time tweens: {"duration", "sets", "tweens", "report"}."""
    total = float(data["duration"])
    spans = scene_spans(data)
    order = [s["id"] for s in data["scenes"]]
    by_id = {s["id"]: s for s in plan["scenes"]}
    if set(order) != set(by_id):
        raise CameraError("camera plan and timeline scenes do not match")
    sets, tweens, report = [], [], []
    for idx, sid in enumerate(order):
        sc = by_id[sid]
        t0, t1 = spans[sid]
        row = {"scene": sid, "visible": [t0, t1], "media": media_src.get(sid),
               "frame": sc["media"]["frame"] if sc["media"] else None, "move": None, "transition": None}
        mv = sc["move"]
        if mv is not None and mv["resolved"] != "none":
            el = f"caml-{sid}" if mv["target"] == "media" else f"camg-{sid}"
            avail = t1 - t0 - mv["delay"]
            base = avail if mv["duration"] is None else min(mv["duration"], avail)
            d = round(base * mv["travel"], 4)
            if d >= MIN_MOVE_SEC:
                t = round(t0 + mv["delay"], 4)
                sets.append({"el": el, "props": _props(mv["from"])})
                tweens.append({"el": el, "t": t, "d": d, "from": _props(mv["from"]), "to": _props(mv["to"]),
                               "ease": mv["ease"], "kind": "camera"})
                row["move"] = {"move": mv["move"], "resolved": mv["resolved"], "target": mv["target"], "t": t, "d": d,
                               "from": mv["from"], "to": mv["to"], "ease": mv["ease"]}
            else:
                row["move"] = {"move": mv["move"], "skipped": f"only {max(0.0, avail):.2f}s available"}
        tr = sc["transition"]
        if idx > 0 and tr is not None and tr["kind"] != "fade":
            prev = order[idx - 1]
            t = t0
            d = round(min(tr["duration"], total - t), 4)
            if d > 0:
                inc, out = f"scene-{sid}", f"scene-{prev}"
                scale = max(tr.get("in_from", PR.IDENTITY)["s"], tr.get("out_to", PR.IDENTITY)["s"])
                for other in (sc, by_id[prev]):     # both scenes are scaled while the transition runs
                    m = other["move"]
                    states = [m["from"], m["to"]] if m is not None and m["target"] == "scene" else [None]
                    for st in states:
                        PR.check_composite(st, other["media"]["frame"] if other["media"] else None, scale,
                                           f"{other['id']} during the {tr['kind']} into {sid}")
                if tr["kind"] == "wipe":
                    sets.append({"el": inc, "props": {"clipPath": tr["clip_from"]}})
                    tweens.append({"el": inc, "t": t, "d": d, "from": {"clipPath": tr["clip_from"]},
                                   "to": {"clipPath": tr["clip_to"]}, "ease": "power2.out", "kind": "transition-in"})
                else:
                    sets.append({"el": inc, "props": _props(tr["in_from"])})
                    tweens.append({"el": inc, "t": t, "d": d, "from": _props(tr["in_from"]), "to": _props(PR.IDENTITY),
                                   "ease": "power2.out", "kind": "transition-in"})
                    tweens.append({"el": out, "t": t, "d": d, "from": _props(PR.IDENTITY), "to": _props(tr["out_to"]),
                                   "ease": "power2.in", "kind": "transition-out"})
                row["transition"] = {"kind": tr["kind"], "t": t, "d": d}
        report.append(row)
    for tw in tweens:
        if tw["t"] < 0 or tw["t"] + tw["d"] > total + 1e-6:
            raise CameraError(f"{tw['el']}: tween {tw['t']}+{tw['d']}s is outside the video (0-{total}s)")
    # the same element may carry several tweens only one after another (seek-safe)
    by_el = {}
    for tw in sorted(tweens, key=lambda x: x["t"]):
        last = by_el.get(tw["el"])
        if last is not None and tw["t"] < last - 1e-6:
            raise CameraError(f"{tw['el']}: overlapping tweens")
        by_el[tw["el"]] = tw["t"] + tw["d"]
    return {"duration": total, "sets": sets, "tweens": tweens, "report": report}


def _media_html(sid, media, src):
    fx, fy = media["focus"]
    fit = "cover" if media["fit"] == "cover" else "contain"
    return (f'<div class="cam-media cam-frame-{media["frame"]}" id="camm-{sid}">'
            f'<div class="cam-layer" id="caml-{sid}">'
            f'<img class="cam-img" src="{html.escape(src, quote=True)}" alt="" '
            f'style="object-fit:{fit};object-position:{fx * 100:.1f}% {fy * 100:.1f}%"></div>'
            f'<div class="cam-scrim"></div></div>')


def apply(page, plan, theme, media_src):
    """Return (new_page, compiled) for a validated plan; media_src maps scene id -> path relative to the page."""
    data = read_timeline_data(page)
    _once(page, 'window.__timelines["main"] = tl;')
    _once(page, '<section id="stage"')
    compiled = build_plan(plan, data, media_src)

    # 1. scenes: media frame + graphics wrapper (from the last scene backwards so offsets stay valid)
    for sc in reversed(plan["scenes"]):
        sid = sc["id"]
        wants_media = sc["media"] is not None
        wants_wrap = sc["move"] is not None and sc["move"]["target"] == "scene"
        if not (wants_media or wants_wrap):
            continue
        _, a, b, _ = _scene_block(page, sid)
        inner = page[a:b]
        if wants_wrap:
            inner = f'<div class="cam-graphics" id="camg-{sid}">{inner}</div>'
        if wants_media:
            inner = _media_html(sid, sc["media"], media_src[sid]) + inner
        page = page[:a] + inner + page[b:]

    # 2. stylesheet
    r, g, b = _hex_rgb(theme["vars"]["--bg"])
    css = (HERE / "camera.css").read_text(encoding="utf-8").replace("__BG_RGB__", f"{r},{g},{b}")
    i = _once(page, "</head>")
    page = page[:i] + f'<style id="nfp-camera-css">\n{css}</style>\n' + page[i:]

    # 3. script, after the main timeline script
    js_data = json.dumps({"duration": compiled["duration"], "sets": compiled["sets"], "tweens": compiled["tweens"]},
                         ensure_ascii=False).replace("<", "\\u003c")
    js = (HERE / "camera.js").read_text(encoding="utf-8")
    if js.count("__CAMERA_JSON__") != 1:
        raise CameraError("camera.js must contain exactly one __CAMERA_JSON__ placeholder")
    js = js.replace("__CAMERA_JSON__", js_data)
    i = _once(page, "</body>")
    page = page[:i] + f'<script id="nfp-camera">\n{js}</script>\n' + page[i:]
    return page, compiled
