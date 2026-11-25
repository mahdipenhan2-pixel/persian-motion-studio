"""NFP Film - project loader (16:9, 1920x1080, 30 fps). Derived from docu/engine/project.py (docu-16x9-test30, see
PROVENANCE.json); changes: language 'en' (default) or 'fa', per-sentence speaker, optional cast + characters per shot.

A project = chapters of sentences + a shots.js that animates them (+ optional characters as DATA, planned by C3).
Chapters exist because the locked Stage 2 core accepts at most 40 sentences / 180 s of narration per run."""
import json
import re
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
FILM = ENGINE.parent
ROOT = FILM.parent.parent
DEFAULTS = ROOT / "studio" / "config" / "studio.defaults.json"
ID_RE = re.compile(r"[A-Za-z0-9-]+")
LANGS = {"en": {"dir": "ltr"}, "fa": {"dir": "rtl"}}
MAX_SENT = 40              # core limit per run
MAX_CHARS = 160            # core limit per sentence
MAX_CHAPTER_SECONDS = 165  # core limit is 180 s; keep a margin for gaps/tail
TOP_KEYS = {"meta", "voice", "audio", "shots", "chapters", "sources", "cast", "characters", "subtitles", "timeline"}
SENT_KEYS = {"id", "text", "speak", "speaker", "pause_before_ms", "pause_after_ms"}


class ProjectError(ValueError):
    pass


def load(name_or_path):
    p = Path(name_or_path)
    if p.is_dir():
        p = p / "project.json"
    if not p.exists():
        raise ProjectError(f"project file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    data["_name"], data["_dir"] = p.parent.name, str(p.parent)
    return validate(data)


def validate(p):
    extra = sorted(set(k for k in p if not k.startswith("_")) - TOP_KEYS)
    if extra:
        raise ProjectError(f"unknown top-level field(s): {', '.join(extra)}")
    m = p.get("meta") or {}
    lang = m.setdefault("lang", "en")
    if lang not in LANGS:
        raise ProjectError(f"meta.lang must be one of {sorted(LANGS)} (got {lang!r})")
    if (m.get("width"), m.get("height"), m.get("fps")) != (1920, 1080, 30):
        raise ProjectError("meta must be width 1920, height 1080, fps 30 (16:9, 1080p30)")
    td = m.get("target_duration")
    if td is not None and not (5 <= float(td) <= 1800):
        raise ProjectError("meta.target_duration must be 5-1800 seconds")
    if not isinstance(p.get("shots"), str) or not p["shots"].endswith(".js"):
        raise ProjectError("shots must name the project's .js shot file")
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
            extra = sorted(set(s) - SENT_KEYS)
            if extra:
                raise ProjectError(f"sentence {s.get('id')}: unknown field(s) {', '.join(extra)}")
            if not ID_RE.fullmatch(s.get("id", "")) or s["id"] in seen_s:
                raise ProjectError(f"bad or duplicate sentence id: {s.get('id')}")
            seen_s.add(s["id"])
            if not s.get("text", "").strip() or len(s["text"]) > MAX_CHARS:
                raise ProjectError(f"sentence {s['id']}: text required and <= {MAX_CHARS} chars")
            for k in ("pause_before_ms", "pause_after_ms"):
                if k in s and not (isinstance(s[k], int) and not isinstance(s[k], bool) and 0 <= s[k] <= 5000):
                    raise ProjectError(f"sentence {s['id']}: {k} must be an integer 0..5000")
            if ("pause_before_ms" in s or "pause_after_ms" in s) and "engine" not in (p.get("voice") or {}):
                raise ProjectError(f"sentence {s['id']}: pauses need the Voice Engine (voice.engine); the core's tts has no pauses")
    if "subtitles" in p:                # S1: checked by the subtitle module, imported only for projects that have the block
        import subtitles
        try:
            subtitles.settings(p)
        except subtitles.SubtitleError as e:
            raise ProjectError(str(e))
    tl = p.get("timeline")              # T2: checked fully by engine/timeline_bridge.py (nfp/timeline) at compose
    if tl is not None and (not isinstance(tl, dict) or set(tl) - {"file", "assets"} or not isinstance(tl.get("file"), str)):
        raise ProjectError('timeline must be {"file": "timeline.json", "assets": "assets.json"}')
    p.setdefault("voice", {})
    return p


def lang_dir(p):
    return LANGS[p["meta"]["lang"]]["dir"]


def chapter(p, cid=None):
    cid = cid or p["chapters"][0]["id"]
    for c in p["chapters"]:
        if c["id"] == cid:
            return c
    raise ProjectError(f"unknown chapter {cid}")


def core_script(p, c):
    return {"meta": {"language": p["meta"]["lang"], "title": p["meta"]["title"]},
            "sentences": [{"id": s["id"], "text": s["text"], **({"speak": s["speak"]} if s.get("speak") else {})} for s in c["sentences"]]}


def core_config(p, c):
    cfg = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    v = p.get("voice", {})
    cfg["tts"]["voice"] = v.get("voice", cfg["tts"]["voice"])
    cfg["tts"]["style"] = v.get("style", cfg["tts"]["style"])
    cfg["audio"].update({k: v for k, v in p.get("audio", {}).items()})
    cfg["audio"].update({k: v for k, v in (c.get("audio") or {}).items()})
    cfg["whisper"]["language"] = p["meta"]["lang"]
    cfg["tts"]["max_requests_per_run"] = max(1, min(40, len(c["sentences"]) + 3))
    # The core validates its own vertical template; Film composes 1920x1080 itself and only uses the core for audio,
    # Whisper and alignment, so the core-facing video block stays at its fixed value.
    return cfg


def chapter_target(p, c):
    v = c.get("target_duration")
    return float(v) if v is not None else (float(p["meta"]["target_duration"]) if p["meta"].get("target_duration") else None)
