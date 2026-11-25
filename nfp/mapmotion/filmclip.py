"""NFP Map Motion - M2g: a map as a Timeline clip on the Film page. Standard library; no process, no file writing (the
Film side - engine/timeline_bridge.py - measures the label text and writes the QC report).

The Timeline clip (nfp.timeline/1, unchanged contract):  {"id": "m1", "track": "pictures", "kind": "map",
                                                          "start": 60, "end": 360, "ref": "maps/route.clip.json"}
  on a visual track (full frame); ref = a map clip bundle inside the project (no asset):
  {"schema": "nfp.mapmotion.clip/1", "map": "route.map.json", "locations": "locations.json", "scene": "route.scene.json",
   "assets": "assets.json", "today": "2026-11-25"}          paths relative to the bundle, inside the project folder
  - "today": the date Location review dates are checked against (M1 needs it; never the system clock);
  - "assets" is only needed when the scene has a basemap;
  - the map's window (video frames, its own anchors resolved with the film's word timing) must be EXACTLY the clip's
    frames start..end - one source of truth for when the map is on screen.
On the page the map is ONE Director shot for the clip's frames (D.shot), its drawing one layer at depth 0 (S.layer: not
moved by the Director's own camera, under the film's grain / vignette / VHS post layers), animated only through the
public D.key:
  - the map's camera (M2c): the group under it carries the camera's matrix as --x / --y / --s (base.html maps them to
    translate(x, y) scale(s) about 0 0: exactly the matrix [s, 0, 0, s, x, y]), keyed on the frames where it changes;
  - what a frame changes (M2d routes drawn so far, areas, markers, M2f labels) is drawn per frame by render.py's own
    layer functions (the same drawing as render_svg and the preview) and shown with D.key(el, "display", ...) only on
    its frames; consecutive identical frames share one element.
Frame f is shown at t = f / 30 s, the same time the Timeline's image and video clips use.
Labels use the film's local fonts (Vazirmatn / Inter woff2, copied by compose to story/assets/fonts): font_face_css_rel
writes their @font-face rules with those relative paths.
"""
import datetime
import json
from pathlib import Path

from . import render as R
from .camera import matrix
from .geometry import geometry
from .model import build
from .scene import resolve
from .svg import el, num

CLIP_SCHEMA = "nfp.mapmotion.clip/1"
BUNDLE_KEYS = {"schema", "map", "locations", "scene", "assets", "today"}
FPS = 30


def _inside(base, rel, what):
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError(f"{what} must be a relative path inside the project")
    return base / rel


def load(ref, project_dir):
    """The clip bundle and its documents. ref: the clip's ref (relative to the project folder)."""
    pdir = Path(project_dir).resolve()
    path = _inside(pdir, ref, "the map clip's ref")
    try:
        if not path.resolve().is_relative_to(pdir):
            raise ValueError("the map clip's ref leaves the project folder")
        b = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read the map clip bundle {ref}: {e}") from None
    if not isinstance(b, dict) or b.get("schema") != CLIP_SCHEMA or set(b) - BUNDLE_KEYS or not {"map", "locations", "scene", "today"} <= set(b):
        raise ValueError(f"{ref}: a map clip bundle is {{schema: {CLIP_SCHEMA}, map, locations, scene, assets, today}}")
    try:
        today = datetime.date.fromisoformat(b["today"])
    except (TypeError, ValueError):
        raise ValueError(f"{ref}: today must be a date YYYY-MM-DD") from None
    base = path.parent
    docs = {}
    for k in ("map", "locations", "scene", "assets"):
        if k not in b:
            continue
        p = _inside(base, b[k], f"{ref}: {k}")
        if not p.resolve().is_relative_to(pdir):
            raise ValueError(f"{ref}: {k} leaves the project folder")
        try:
            docs[k] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ValueError(f"{ref}: cannot read {k} ({b[k]}): {e}") from None
        if k == "assets":
            docs["assets_dir"] = p.parent
    docs["today"] = today
    return docs


def prepare(docs, context, clip):
    """Plan (M1), geometry (M2a) and a first scene plan (without text measurement) of a clip; the label texts to
    measure. Raises ValueError for anything that stops the film (a FAIL plan, a window that is not the clip's frames)."""
    plan = build(docs["map"], docs["locations"], context=context, today=docs["today"])
    errs = [x for x in plan["qc"]["issues"] if x["level"] == "error"]
    if errs:
        raise ValueError("the map plan fails: " + "; ".join(f"{x.get('element') or '-'}: {x['message']}" for x in errs[:6]))
    w = plan["window"]
    if (w["start"], w["end"]) != (clip["start"], clip["end"]):
        raise ValueError(f"the map's window is frames {w['start']}..{w['end'] - 1}, the clip's {clip['start']}..{clip['end'] - 1}: "
                         "they must be the same")
    geo = geometry(plan)
    bad = [x for x in geo["issues"] if x["level"] == "error"]
    if bad:
        raise ValueError("the map geometry fails: " + "; ".join(x["message"] for x in bad[:4]))
    sp0 = resolve(docs["scene"], plan, geo, docs.get("assets"), docs.get("assets_dir"))
    st = sp0["labels"]["style"]
    return {"plan": plan, "geometry": geo, "texts": sorted({t["text"] for t in sp0["labels"]["texts"].values()}),
            "size": st["size"], "weight": st["weight"], "draft": sp0}


def finish(docs, prep, metrics):
    """The final scene plan (with the measured label sizes). Raises ValueError when its QC fails."""
    sp = resolve(docs["scene"], prep["plan"], prep["geometry"], docs.get("assets"), docs.get("assets_dir"), metrics=metrics)
    errs = [x for x in sp["qc"]["issues"] if x["level"] == "error"]
    if errs:
        raise ValueError("the map scene fails: " + "; ".join(f"{x.get('element') or '-'}: {x['code']}: {x['message']}" for x in errs[:6]))
    return sp


def font_face_css_rel(faces, folder="assets/fonts"):
    """@font-face rules for the label faces, pointing at the film's own font copies (relative to the page)."""
    return "".join(f'@font-face{{font-family:"{fam}";src:url("{folder}/{f}") format("woff2");font-weight:{w};font-style:normal;'
                   f'font-display:block}}' for fam, w, f in faces)


def _runs(items):
    """[(frame, content)] -> [(first frame, end frame (exclusive), content)] for consecutive equal contents."""
    out = []
    for f, c in items:
        if out and out[-1][2] == c and out[-1][1] == f:
            out[-1][1] = f + 1
        else:
            out.append([f, f + 1, c])
    return out


def _t(f):
    return repr(f / FPS)


def shot_js(sp, plan, clip_id, font_css=""):
    """JS (Director API only) drawing the map of a clip; appended to the film's shots like the Timeline's image clips."""
    W, H = sp["frame"]["width"], sp["frame"]["height"]
    w0, w1 = plan["window"]["start"], plan["window"]["end"]
    bm = R.basemap_paths(sp, plan)
    # one-to-one (two clip ids never share a key): letters, digits and "-" stay, any other character is _<hex code>_
    key = "".join(ch if (ch.isascii() and ch.isalnum()) or ch == "-" else f"_{ord(ch):x}_" for ch in clip_id)
    dyn, scr, cam = [], [], []
    for i, f in enumerate(range(w0, w1)):
        cf = sp["camera"]["frames"][i]
        state = {"cx": cf["cx"], "cy": cf["cy"], "zoom": cf["zoom"]}
        an = sp["animation"]["frames"][i]
        d, heads = R.layer_map_dynamic(sp, f, an)
        mk, lb = R.layer_screen(sp, state, f, an, heads)
        dyn.append((f, d))
        scr.append((f, mk + (lb or "")))
        m = matrix(state, sp["frame"])
        cam.append((f, (round(m[0], 6), round(m[4], 6), round(m[5], 6))))
    dyn_runs, scr_runs = _runs(dyn), _runs(scr)
    hidden = (("style", "display:none"),)
    inner = [el("rect", (("width", W), ("height", H), ("fill", sp["style"]["colors"]["background"])))]
    inner.append(el("g", (("data-p", f"mmc-{key}"),), R.layer_map_static(sp, plan, bm) +
                    "".join(el("g", (("data-p", f"mmd-{key}-{k}"),) + hidden, c) for k, (_, _, c) in enumerate(dyn_runs))))
    inner += [el("g", (("data-p", f"mms-{key}-{k}"),) + hidden, c) for k, (_, _, c) in enumerate(scr_runs)]
    inner.append(R.attribution(sp, bm))
    if font_css:
        inner.append(el("style", (), font_css))
    markup = json.dumps("".join(inner), ensure_ascii=False).replace("</", "<\\/")
    body = [f"S.layer({markup}, 0);", f"const c = S.q(\"mmc-{key}\");"]
    last = None
    for f, (s, x, y) in cam:
        if (s, x, y) != last:
            body.append(f"D.key(c, \"--s\", {_t(f)}, {num(s)}, 0); D.key(c, \"--x\", {_t(f)}, {num(x)}, 0); D.key(c, \"--y\", {_t(f)}, {num(y)}, 0);")
            last = (s, x, y)
    for name, runs in (("mmd", dyn_runs), ("mms", scr_runs)):
        for k, (a, b, _) in enumerate(runs):
            body.append(f"D.key(S.q(\"{name}-{key}-{k}\"), \"display\", {_t(a)}, \"inline\", 0); "
                        f"D.key(S.q(\"{name}-{key}-{k}\"), \"display\", {_t(b)}, \"none\", 0);")
    return (f"\n  /* ===== map (nfp/mapmotion M2g): clip {clip_id}, frames {w0}..{w1 - 1}, scene {sp['scene']} ===== */\n"
            f"  D.shot({{ id: \"map-{key}\", a: {_t(w0)}, b: {_t(w1)},\n    build(S) {{\n      " + "\n      ".join(body) + "\n    } });\n")
