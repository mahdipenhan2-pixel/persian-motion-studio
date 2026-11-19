"""
project.json loading and validation, and the bridge to the locked Stage 2 core.

A project is a list of scenes. Each scene has narration (one or more sentences) and a visual
template. The Stage 2 core only understands a flat list of sentences, so every narration is split
into sentences with ids "<scene>_<n>" and the core is driven with that generated list.
"""
import json
import re
from pathlib import Path

import scene_templates as st

STUDIO = Path(__file__).resolve().parent.parent
ROOT = STUDIO.parent
PROJECTS = STUDIO / "projects"
THEMES = Path(__file__).resolve().parent / "themes"
DEFAULTS = STUDIO / "config" / "studio.defaults.json"

LANGS = {"fa": "rtl", "en": "ltr"}
MAX_SCENES = 20
MAX_SENTENCE_CHARS = 160  # limit of the locked core; keeps every caption inside its band
ID_RE = re.compile(r"[A-Za-z0-9-]+")
_SPLIT = re.compile(r"(?<=[.!?\u061F\u2026])\s+")


class ProjectError(ValueError):
    pass


def split_sentences(text):
    parts = [p.strip() for p in _SPLIT.split(text.strip()) if p.strip()]
    return parts


def load(name_or_path):
    p = Path(name_or_path)
    if not p.suffix:
        p = PROJECTS / name_or_path / "project.json"
    if not p.exists():
        raise ProjectError(f"project file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProjectError(f"{p.name} is not valid JSON: {e}")
    data["_name"] = p.parent.name
    return validate(data)


def load_theme(name):
    p = THEMES / f"{name}.json"
    if not p.exists():
        avail = ", ".join(sorted(x.stem for x in THEMES.glob("*.json")))
        raise ProjectError(f"theme '{name}' not found. Available: {avail}")
    t = json.loads(p.read_text(encoding="utf-8"))
    for k in ("vars", "cream_rgb", "ink_rgb", "highlight_rgb"):
        if k not in t:
            raise ProjectError(f"theme {name} is missing '{k}'")
    return t


def validate(p):
    if not isinstance(p, dict):
        raise ProjectError("project.json must be an object")
    meta = p.get("meta")
    if not isinstance(meta, dict):
        raise ProjectError("meta must be an object")
    if meta.get("lang") not in LANGS:
        raise ProjectError(f"meta.lang must be one of {sorted(LANGS)}")
    if meta.get("format", "9:16") != "9:16":
        raise ProjectError("meta.format: only '9:16' is supported in this version (16:9 comes with the documentary phase)")
    if not isinstance(meta.get("title"), str) or not meta["title"].strip():
        raise ProjectError("meta.title must be a non-empty string")
    meta.setdefault("format", "9:16")
    meta.setdefault("theme", "dark-green")
    if not isinstance(meta.get("handle", ""), str):
        raise ProjectError("meta.handle must be a string")
    load_theme(meta["theme"])
    voice = p.setdefault("voice", {})
    if not isinstance(voice, dict):
        raise ProjectError("voice must be an object")
    if "voice" in voice and (not isinstance(voice["voice"], str) or not voice["voice"].strip()):
        raise ProjectError("voice.voice must be a non-empty string")
    if "style" in voice and not isinstance(voice["style"], str):
        raise ProjectError("voice.style must be a string")

    scenes = p.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= MAX_SCENES:
        raise ProjectError(f"scenes must be a list of 1-{MAX_SCENES} items")
    seen, n_sent = set(), 0
    for i, sc in enumerate(scenes):
        w = f"scenes[{i}]"
        if not isinstance(sc, dict):
            raise ProjectError(f"{w} must be an object")
        sid = sc.get("id")
        if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
            raise ProjectError(f"{w}.id must match [A-Za-z0-9-]+ (no underscore)")
        if sid in seen:
            raise ProjectError(f"duplicate scene id '{sid}'")
        seen.add(sid)
        narr = sc.get("narration")
        if not isinstance(narr, str) or not narr.strip():
            raise ProjectError(f"{w}.narration must be a non-empty string")
        for j, s in enumerate(split_sentences(narr)):
            if len(s) > MAX_SENTENCE_CHARS:
                raise ProjectError(f"{w} ('{sid}') sentence {j + 1} is {len(s)} characters; "
                                   f"the limit is {MAX_SENTENCE_CHARS}. Split it with a full stop.")
            n_sent += 1
        try:
            st.validate(sc.get("template"), sc.get("on_screen"), f"{w} ('{sid}')")
        except st.SceneError as e:
            raise ProjectError(str(e))
    if n_sent > 40:
        raise ProjectError(f"{n_sent} sentences in total; this version supports at most 40")
    return p


def sentences(p):
    """Flat sentence list for the Stage 2 core: ids are '<scene>_<n>'."""
    out = []
    for sc in p["scenes"]:
        for n, text in enumerate(split_sentences(sc["narration"]), 1):
            out.append({"id": f"{sc['id']}_{n}", "text": text})
    return out


def core_script(p):
    return {"meta": {"language": p["meta"]["lang"], "title": p["meta"]["title"]}, "sentences": sentences(p)}


def core_config(p):
    cfg = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    cfg["tts"]["voice"] = p["voice"].get("voice", cfg["tts"]["voice"])
    cfg["tts"]["style"] = p["voice"].get("style", cfg["tts"]["style"])
    cfg["whisper"]["language"] = p["meta"]["lang"]
    # Budget = every sentence new + 3 spare requests for retries (a retry also spends budget in the core).
    # The workflow's free-tier gate still decides whether any API request may run at all.
    cfg["tts"]["max_requests_per_run"] = max(1, min(40, len(sentences(p)) + 3))
    return cfg
