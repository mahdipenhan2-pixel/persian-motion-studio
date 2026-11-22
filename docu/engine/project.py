"""Documentary project loader (16:9). A project = chapters of sentences + a shots.js that animates them.
Chapters exist because the locked Stage 2 core accepts at most 40 sentences / 180 s of narration per run."""
import json
import re
from pathlib import Path

DOCU = Path(__file__).resolve().parent.parent
ROOT = DOCU.parent
PROJECTS = DOCU / "projects"
DEFAULTS = ROOT / "studio" / "config" / "studio.defaults.json"
ID_RE = re.compile(r"[A-Za-z0-9-]+")
MAX_SENT = 40          # core limit per run
MAX_CHARS = 160        # core limit per sentence
MAX_CHAPTER_SECONDS = 165  # core limit is 180 s; keep a margin for gaps/tail


class ProjectError(ValueError):
    pass


def load(name_or_path):
    p = Path(name_or_path)
    if not p.suffix:
        p = PROJECTS / name_or_path / "project.json"
    if not p.exists():
        raise ProjectError(f"project file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["_name"], data["_dir"] = p.parent.name, str(p.parent)
    return validate(data)


def validate(p):
    m = p.get("meta") or {}
    if m.get("lang") != "en":
        raise ProjectError("meta.lang must be 'en' (this documentary line is English-narrated)")
    if (m.get("width"), m.get("height"), m.get("fps")) != (1920, 1080, 30):
        raise ProjectError("meta must be width 1920, height 1080, fps 30 (16:9 horizontal)")
    td = m.get("target_duration")
    if td is not None and not (5 <= float(td) <= 1800):
        raise ProjectError("meta.target_duration must be 5-1800 seconds")
    chs = p.get("chapters")
    if not isinstance(chs, list) or not chs:
        raise ProjectError("chapters must be a non-empty list")
    seen_c, seen_s = set(), set()
    for c in chs:
        if not ID_RE.fullmatch(c.get("id", "")) or c["id"] in seen_c:
            raise ProjectError(f"bad or duplicate chapter id: {c.get('id')}")
        seen_c.add(c["id"])
        ctd = c.get("target_duration")
        if ctd is not None and not (5 <= float(ctd) <= 400):
            raise ProjectError(f"chapter {c['id']}: target_duration must be 5-400 seconds")
        ss = c.get("sentences")
        if not isinstance(ss, list) or not 1 <= len(ss) <= MAX_SENT:
            raise ProjectError(f"chapter {c['id']}: 1-{MAX_SENT} sentences required (core limit)")
        for s in ss:
            if not re.fullmatch(r"[A-Za-z0-9-]+", s.get("id", "")) or s["id"] in seen_s:
                raise ProjectError(f"bad or duplicate sentence id: {s.get('id')}")
            seen_s.add(s["id"])
            if not s.get("text", "").strip() or len(s["text"]) > MAX_CHARS:
                raise ProjectError(f"sentence {s['id']}: text required and <= {MAX_CHARS} chars")
    p.setdefault("voice", {})
    return p


def chapter(p, cid=None):
    cid = cid or p["chapters"][0]["id"]
    for c in p["chapters"]:
        if c["id"] == cid:
            return c
    raise ProjectError(f"unknown chapter {cid}")


def core_script(p, c):
    return {"meta": {"language": "en", "title": p["meta"]["title"]},
            "sentences": [{"id": s["id"], "text": s["text"], **({"speak": s["speak"]} if s.get("speak") else {})} for s in c["sentences"]]}


def core_config(p, c):
    cfg = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    v = p.get("voice", {})
    cfg["tts"]["voice"] = v.get("voice", cfg["tts"]["voice"])
    cfg["tts"]["style"] = v.get("style", cfg["tts"]["style"])
    cfg["audio"].update({k: v for k, v in p.get("audio", {}).items()})
    cfg["audio"].update({k: v for k, v in (c.get("audio") or {}).items()})   # optional per-chapter lead-in / tail (e.g. title card, end card)
    cfg["whisper"]["language"] = "en"
    cfg["tts"]["max_requests_per_run"] = max(1, min(40, len(c["sentences"]) + 3))
    # The core validates its own vertical template; this documentary composes 1920x1080 itself and only uses
    # the core for audio, Whisper and alignment, so the core-facing video block stays at its fixed value.
    return cfg


def chapter_target(p, c):
    """video length of one chapter: its own target_duration if given, else the project's (backward compatible)"""
    v = c.get("target_duration")
    return float(v) if v is not None else (float(p["meta"]["target_duration"]) if p["meta"].get("target_duration") else None)
