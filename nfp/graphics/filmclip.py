"""NFP Graphics - G5: a graphic as a Timeline clip on the Film page. Standard library; no process, no file writing (the
Film side - engine/timeline_bridge.py - measures the text and writes the QC report, as it does for Map Motion).

The Timeline clip (nfp.timeline/1):  {"id": "g1", "track": "pictures", "kind": "graphic", "start": 60, "end": 180,
                                      "ref": "graphics/title.graphic.json"}
  - ref = a graphic document (nfp.graphics/1) inside the project folder; no asset;
  - the DISPLAY comes from the clip's track (one source of truth): a visual track = full frame, an overlay track = overlay;
  - the TIME is the clip's frames start .. end - 1 (the Timeline resolved its anchors against the film's word timing);
    the graphic only animates itself inside them (G4);
  - a final timeline takes only a final graphic (its own final checks: sourced numbers, contrast, measured text).
On the page (the layers chosen by the G0 experiment):
  full frame  one Director shot for the clip's frames (D.shot, its drawing one layer at depth 0, inside #world: a picture
              like an image or map clip, under the grain / vignette / VHS post layers and the subtitles)
  overlay     one <g id="nfp-gfx"> put by the page's script between #world and #post (svg.insertBefore(g, post)): above
              every shot / image / map / video, under the post layers and the subtitles (#subs); the film's base.html is
              not changed
Each graphic's handles are named after its CLIP (key "c-<clip id>"), so one graphic document may be used by several
clips. Animation: graphics.anim_js (D.key only). Fonts: the film's own copies (story/assets/fonts) by @font-face rules
with relative paths, in the graphics' own markup (an English film declares no Vazirmatn of its own).
"""
import json
from pathlib import Path

from . import model as MD
from . import render as RD
from . import safearea as SA
from .animate import anim_js
from .textlayout import layout

FPS = 30


def _inside(base, rel, what):
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ValueError(f"{what} must be a relative path inside the project")
    return base / rel


def load(ref, project_dir):
    """The graphic document a clip's ref names (inside the project folder)."""
    pdir = Path(project_dir).resolve()
    path = _inside(pdir, ref, "the graphic clip's ref")
    try:
        if not path.resolve().is_relative_to(pdir):
            raise ValueError("the graphic clip's ref leaves the project folder")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read the graphic document {ref}: {e}") from None


def key_of_clip(clip_id):
    return "c-" + RD.key_of(clip_id)


def display_of(track_kind):
    return {"visual": "fullframe", "overlay": "overlay"}[track_kind]


def prepare(doc, clip, track_kind, timeline_mode="draft"):
    """The resolved graphic for one clip -> (spec, warnings). Raises ValueError for anything that stops the film."""
    if timeline_mode == "final" and isinstance(doc, dict) and doc.get("mode", "draft") != "final":
        raise ValueError("a final timeline needs the graphic in final mode (sourced numbers, contrast, measured text)")
    r = MD.validate(doc, display_of(track_kind), clip["end"] - clip["start"])
    errs = [x for x in r["issues"] if x["level"] == "error"]
    if errs:
        raise ValueError("the graphic fails: " + "; ".join(f"{x.get('element') or '-'}: {x['code']}: {x['message']}" for x in errs[:6]))
    return r["graphic"], [x for x in r["issues"] if x["level"] == "warning"]


def finish(spec, metrics):
    """Layout (measured) + contrast -> (layout, warnings). Raises ValueError on an error (overflow, unmeasured text in a
    final graphic, low contrast in a final graphic, a box in the subtitle band ...)."""
    lay = layout(spec, metrics)
    issues = lay["issues"] + RD.contrast(spec, lay)
    errs = [x for x in issues if x["level"] == "error"]
    if errs or lay["status"] == "FAIL":
        raise ValueError("the graphic's layout fails: " + "; ".join(f"{x.get('element') or '-'}: {x['code']}: {x['message']}" for x in errs[:6]))
    return lay, [x for x in issues if x["level"] == "warning"]


def clashes(overlays):
    """Overlays shown at the same time whose drawings cover each other. overlays: [(clip, spec, lay)]."""
    return SA.check_overlays([(c["id"], c["start"], c["end"], RD.extent(s, l, margin=0)) for c, s, l in overlays])


def font_css_rel(faces, folder="assets/fonts"):
    """@font-face rules for the graphics' faces, pointing at the film's own font copies (relative to the page)."""
    return "".join(f'@font-face{{font-family:"{fam}";src:url("{folder}/{f}") format("woff2");font-weight:{w};font-style:normal;'
                   f'font-display:block}}' for fam, w, f in faces)


def _t(f):
    return repr(f / FPS)


def _markup(s):
    return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")


def fullframe_js(clip, spec, lay, font_css=""):
    """JS for one full-frame graphic clip: a Director shot for its frames + its animation (D.shot / S.layer / D.key)."""
    k = key_of_clip(clip["id"])
    svg = RD.render_svg(spec, lay, standalone=False, key=k) + (f"<style>{font_css}</style>" if font_css else "")
    return (f"\n  /* ===== graphic (nfp/graphics G5): clip {clip['id']}, full frame, frames {clip['start']}..{clip['end'] - 1} ===== */\n"
            f"  D.shot({{ id: \"gfx-{k}\", a: {_t(clip['start'])}, b: {_t(clip['end'])},\n    build(S) {{ S.layer({_markup(svg)}, 0); }} }});\n"
            "  " + anim_js(spec, lay, clip["start"], clip["end"], key=k).replace("\n", "\n  ").rstrip() + "\n")


def overlay_js(items, font_css=""):
    """JS for every overlay graphic clip: ONE layer <g id="nfp-gfx"> between #world and #post holding them all, then each
    one's animation. items: [(clip, spec, lay)] (in drawing order: later clips above earlier ones)."""
    if not items:
        return ""
    body = "".join(RD.render_svg(s, l, standalone=False, key=key_of_clip(c["id"])) for c, s, l in items)
    if font_css:
        body += f"<style>{font_css}</style>"
    js = ("\n  /* ===== graphics overlay layer (nfp/graphics G5): " + ", ".join(c["id"] for c, _, _ in items) + " ===== */\n"
          "  (() => {\n"
          "    const svg = document.getElementById(\"svg\"), post = document.getElementById(\"post\");\n"
          "    if (!svg || !post || post.parentNode !== svg) throw new Error(\"graphics overlay: the page has no #svg > #post\");\n"
          "    const g = document.createElementNS(\"http://www.w3.org/2000/svg\", \"g\");\n"
          "    g.setAttribute(\"id\", \"nfp-gfx\");\n"
          f"    g.innerHTML = {_markup(body)};\n"
          "    svg.insertBefore(g, post);\n"
          "  })();\n")
    for c, s, l in items:
        js += "  " + anim_js(s, l, c["start"], c["end"], key=key_of_clip(c["id"])).replace("\n", "\n  ").rstrip() + "\n"
    return js
