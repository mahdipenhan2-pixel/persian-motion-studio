"""
Validation of the OPTIONAL camera fields in project.json. Projects without them are untouched.

  meta.camera_default   {move, target, intensity, speed, ease, transition}     applies to every scene without "camera"
  scene.camera          {move, target, intensity, speed, ease, duration, delay, transition_in}
  scene.media           {src, frame, fit, focus}

The existing studio/engine/project.py validator ignores these keys, so the old runner (run.py) still renders such a
project, only without motion. Everything here raises CameraError with a clear message.
"""
import re
from pathlib import Path

from . import presets as PR
from .presets import CameraError

MEDIA_EXT = {".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8", ".png": b"\x89PNG", ".webp": b"RIFF", ".svg": None}
MEDIA_MAX_BYTES = 8 * 1024 * 1024
FITS = ("cover", "contain")

CAMERA_KEYS = {"move", "target", "intensity", "speed", "ease", "duration", "delay", "transition_in"}
DEFAULT_KEYS = {"move", "target", "intensity", "speed", "ease", "transition"}
MEDIA_KEYS = {"src", "frame", "fit", "focus"}
TRANSITION_KEYS = {"type", "duration"}


def _obj(v, where):
    if not isinstance(v, dict):
        raise CameraError(f"{where} must be an object")
    return v


def _unknown(d, allowed, where):
    extra = sorted(set(d) - set(allowed))
    if extra:
        raise CameraError(f"{where}: unknown field(s) {', '.join(extra)}. Allowed: {', '.join(sorted(allowed))}")


def _num(v, where, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise CameraError(f"{where} must be a number")
    if not lo <= float(v) <= hi:
        raise CameraError(f"{where} must be between {lo} and {hi}")
    return float(v)


def has_camera(project):
    if isinstance(project.get("meta"), dict) and "camera_default" in project["meta"]:
        return True
    return any(isinstance(sc, dict) and ("camera" in sc or "media" in sc) for sc in project.get("scenes", []))


def _transition(t, where, lang):
    if t is None:
        return None
    if isinstance(t, str):
        t = {"type": t}
    _obj(t, where)
    _unknown(t, TRANSITION_KEYS, where)
    if "duration" in t:
        _num(t["duration"], f"{where}.duration", *PR.TRANSITION_LIMITS)
    try:
        return PR.plan_transition(t.get("type", "fade"), lang, t.get("duration"))
    except CameraError as e:
        raise CameraError(f"{where}: {e}")


def check_media(m, where, project_dir):
    _obj(m, where)
    _unknown(m, MEDIA_KEYS, where)
    src = m.get("src")
    if not isinstance(src, str) or not src.strip():
        raise CameraError(f"{where}.src must be a file path inside the project folder (for example assets/photo.jpg)")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src) or src.startswith(("/", "\\")) or "\\" in src:
        raise CameraError(f"{where}.src must be a relative path inside the project folder; URLs and absolute paths are not allowed")
    parts = Path(src).parts
    if ".." in parts or not parts or parts[0] != "assets":
        raise CameraError(f"{where}.src must live under the project's assets/ folder")
    ext = Path(src).suffix.lower()
    if ext not in MEDIA_EXT:
        raise CameraError(f"{where}.src: only {', '.join(sorted(MEDIA_EXT))} files are supported")
    frame = m.get("frame", "top")
    if frame not in PR.FRAMES:
        raise CameraError(f"{where}.frame must be one of {', '.join(PR.FRAMES)}")
    fit = m.get("fit", "cover")
    if fit not in FITS:
        raise CameraError(f"{where}.fit must be one of {', '.join(FITS)}")
    focus = m.get("focus", [0.5, 0.5])
    if not (isinstance(focus, list) and len(focus) == 2):
        raise CameraError(f"{where}.focus must be [x, y] with values between 0 and 1")
    fx = _num(focus[0], f"{where}.focus[0]", 0, 1)
    fy = _num(focus[1], f"{where}.focus[1]", 0, 1)
    path = None
    if project_dir is not None:
        root = Path(project_dir).resolve()
        path = (root / src).resolve()
        if root not in path.parents:
            raise CameraError(f"{where}.src leaves the project folder")
        if not path.is_file():
            raise CameraError(f"{where}.src file not found: {src}")
        if path.is_symlink() or path.stat().st_size == 0:
            raise CameraError(f"{where}.src must be a regular, non-empty file")
        if path.stat().st_size > MEDIA_MAX_BYTES:
            raise CameraError(f"{where}.src is larger than {MEDIA_MAX_BYTES // (1024 * 1024)} MB")
        head = path.read_bytes()[:512]
        magic = MEDIA_EXT[ext]
        if magic is not None and not head.startswith(magic):
            raise CameraError(f"{where}.src does not look like a real {ext} file")
        if ext == ".svg":
            text = path.read_text(encoding="utf-8", errors="replace")
            if "<svg" not in text[:2048] or re.search(r"<script|javascript:|https?://(?!www\.w3\.org)", text, re.I):
                raise CameraError(f"{where}.src: SVG must be a plain drawing (no scripts, no external links)")
    return {"src": src, "frame": frame, "fit": fit, "focus": [fx, fy], "path": path}


def _camera(c, where, lang, scene_id, media, allow_transition_key):
    allowed = CAMERA_KEYS if not allow_transition_key else DEFAULT_KEYS
    _obj(c, where)
    _unknown(c, allowed, where)
    move = c.get("move", "none")
    target = c.get("target", "media" if media else "scene")
    if target == "media" and media is None:
        raise CameraError(f"{where}.target is 'media' but the scene has no media")
    intensity = _num(c.get("intensity", 0.5), f"{where}.intensity", 0, 1)
    speed = _num(c.get("speed", 1.0), f"{where}.speed", *PR.SPEED_LIMITS)
    ease = c.get("ease", PR.DEFAULT_EASE.get(move, "sine.inOut"))
    if ease not in PR.EASES:
        raise CameraError(f"{where}.ease must be one of {', '.join(PR.EASES)}")
    duration = _num(c["duration"], f"{where}.duration", 0.5, 600) if "duration" in c else None
    delay = _num(c["delay"], f"{where}.delay", 0, 600) if "delay" in c else 0.0
    try:
        plan = PR.plan_move(move, target, intensity, speed, lang, scene_id, media["frame"] if media else "top")
    except CameraError as e:
        raise CameraError(f"{where}: {e}")
    plan.update({"ease": ease, "duration": duration, "delay": delay, "intensity": intensity, "speed": speed})
    return plan


def validate(project, project_dir=None):
    """
    Return a normalized camera plan {"lang", "scenes": [{id, media, move, transition}]} or None when the project
    uses no camera feature at all (then the output must stay byte-identical to the plain Studio runner).
    """
    if not has_camera(project):
        return None
    lang = project["meta"]["lang"]
    default = project["meta"].get("camera_default")
    if default is not None:
        _obj(default, "meta.camera_default")
        _unknown(default, DEFAULT_KEYS, "meta.camera_default")
    out = []
    for n, sc in enumerate(project["scenes"]):
        sid = sc["id"]
        where = f"scenes[{n}] ('{sid}')"
        media = check_media(sc["media"], f"{where}.media", project_dir) if "media" in sc else None
        if "camera" in sc:
            cam = sc["camera"]
            move = _camera(cam, f"{where}.camera", lang, sid, media, False)
            trans_cfg = cam.get("transition_in") if isinstance(cam, dict) else None
        elif default is not None:
            d = {k: v for k, v in default.items() if k != "transition"}
            if d.get("target") == "media" and media is None:
                d["target"] = "scene"               # a default media move falls back to the graphics on media-less scenes
            move = _camera(d, "meta.camera_default", lang, sid, media, True)
            trans_cfg = default.get("transition")
        else:
            move = None
            trans_cfg = None
        if n == 0 and trans_cfg is not None and isinstance(sc.get("camera"), dict) and "transition_in" in sc["camera"]:
            raise CameraError(f"{where}.camera.transition_in: the first scene has no previous scene to transition from")
        transition = _transition(trans_cfg, f"{where} transition", lang) if n > 0 else None
        out.append({"id": sid, "media": media, "move": move, "transition": transition})
    return {"lang": lang, "scenes": out}
