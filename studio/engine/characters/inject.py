"""
Extend a composed Studio page (index.html from the UNCHANGED compose.py, optionally already extended by the camera
engine) with characters. Additive only; called only for projects that use characters.

What is added, and where:
  </head>                 -> <style id="nfp-cast-css">  rig.css (C2) + cast.css + slot geometry + .deco hidden only in
                                                        the scenes that show characters + the moved text box (.zb)
                                                        of cta scenes with note/handle and characters
  <section id="stage"     -> <div id="nfp-cast"> with the bottom slot (overflow:hidden) and its <svg>, placed right
                             before the captions: above the scenes, below the captions
  </body>                 -> rig (C2 00_core.js + 10_chars.js), runtime (C3), cast.js with the KeyList
The captions (<section id="stage">) and the scenes are never edited.
"""
import hashlib
import json
from pathlib import Path

from camera import inject as CI                     # _once / read_timeline_data (read-only reuse)

from .schema import CastError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
NFPC = ROOT / "nfp" / "character"
RIG = NFPC / "renderers" / "flat_cartoon_v2"
EMBEDDED_JS = [RIG / "rig" / "00_core.js", RIG / "rig" / "10_chars.js", NFPC / "runtime" / "character_runtime.js"]


def check_anchor_files():
    spec = json.loads((HERE / "ANCHORS.json").read_text(encoding="utf-8"))
    changed = [rel for rel, want in spec["files"].items()
               if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != want]
    if changed:
        raise CastError("character anchors are unverified because these files changed: " + ", ".join(changed)
                        + ". Run python3 studio/tests/test_characters.py and update studio/engine/characters/ANCHORS.json.")


def _once(page, needle):
    try:
        return CI._once(page, needle)
    except Exception as e:                         # CameraError -> CastError with the same message
        raise CastError(str(e))


def _script(text, ident):
    if "</script" in text.lower():
        raise CastError(f"{ident}: embedded script contains '</script'")
    return f'<script id="{ident}">\n{text}\n</script>\n'


def apply(page, keylist, slot, deco_scenes, text_boxes=None):
    """Return the page with the character layer added. text_boxes: {scene id: {left, right}} for cta scenes whose
    bottom text moves beside the characters (schema.cta_layout)."""
    text_boxes = text_boxes or {}
    if 'id="nfp-cast' in page or "data-nfp-actor" in page:
        raise CastError("this page already contains a character layer")
    _once(page, 'window.__timelines["main"] = tl;')
    data = CI.read_timeline_data(page)
    if keylist["duration"] > float(data["duration"]) + 1e-9:
        raise CastError(f"character timeline ({keylist['duration']}s) is longer than the page ({data['duration']}s)")
    ids = {s["id"] for s in data["scenes"]}
    for sid in list(deco_scenes) + list(text_boxes):
        if sid not in ids:
            raise CastError(f"scene {sid} is not in the page")

    # 1. stylesheet
    css = (RIG / "rig.css").read_text(encoding="utf-8") + "\n" + (HERE / "cast.css").read_text(encoding="utf-8")
    css += (f"  #nfp-cast-slot-bottom {{ left: {slot['x']}px; top: {slot['y']}px; width: {slot['width']}px; "
            f"height: {slot['height']}px; }}\n")
    css += "".join(f"  #scene-{sid} .deco {{ visibility: hidden; }}\n" for sid in deco_scenes)
    css += "".join(f"  #scene-{sid} .zb {{ left: {b['left']}px; right: {b['right']}px; }}\n"
                   for sid, b in sorted(text_boxes.items()))
    i = _once(page, "</head>")
    page = page[:i] + f'<style id="nfp-cast-css">\n{css}</style>\n' + page[i:]

    # 2. layer, right before the captions
    layer = (f'<div id="nfp-cast" aria-hidden="true"><div class="nfp-cast-slot" id="nfp-cast-slot-bottom">'
             f'<svg id="nfp-cast-svg-bottom" xmlns="http://www.w3.org/2000/svg" width="{slot["width"]}" '
             f'height="{slot["height"]}" viewBox="0 0 {slot["width"]} {slot["height"]}"></svg></div></div>\n  ')
    i = _once(page, '<section id="stage"')
    page = page[:i] + layer + page[i:]

    # 3. scripts, after every existing script (camera included)
    js = (HERE / "cast.js").read_text(encoding="utf-8")
    if js.count("__CAST_JSON__") != 1:
        raise CastError("cast.js must contain exactly one __CAST_JSON__ placeholder")
    data_js = json.dumps(keylist, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
    scripts = "".join(_script(p.read_text(encoding="utf-8"), f"nfp-cast-{p.stem.replace('_', '-')}") for p in EMBEDDED_JS)
    scripts += _script(js.replace("__CAST_JSON__", data_js), "nfp-cast-js")
    i = _once(page, "</body>")
    page = page[:i] + scripts + page[i:]
    return page
