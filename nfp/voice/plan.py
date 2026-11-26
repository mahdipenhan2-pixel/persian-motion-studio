"""NFP Voice Engine - voice plan (nfp.voice.plan/1): for every sentence WHO speaks it, with WHICH voice, from WHICH source.

    p = make_plan(casting, script, base_dir)

script (the project's sentences, any language):
  {"language": "en", "sentences": [
     {"id": "s1", "text": "...", "speaker": "narrator"},
     {"id": "s2", "text": "...", "speaker": "lina", "stage": "adult", "language": "fa",
      "pause_before_ms": 300, "pause_after_ms": 0, "style": "warm", "audio": "rec/s2.wav"}]}

  speaker   'narrator' (default) or a role of the casting
  audio     a prepared recording for that sentence (relative to base_dir): provider 'prepared', whatever the voice
  pauses    silence added before / after the sentence INSIDE its own file (the unchanged core keeps such silence and
            the word times stay exact - V0 / L0)
Sources: 'synthetic' (offline test tones), 'prepared' (files), 'piper' (real speech from a local, free Piper model). A 'gemini' voice can be cast and planned for review,
but this version has no API connection: producing it is refused with a clear message.
cache_key = sha256 of everything that changes the audio (provider, voice, style, language, text, pauses, prepared file
hash); the same input always gives the same plan (sorted, no clock).
"""
import hashlib
import json
import re
from pathlib import Path

from .casting import NARRATOR, finding
from .registry import LANG, VoiceError

SCHEMA = "nfp.voice.plan/1"
VERSION = "nfp.voice/1"
SENT_KEYS = {"id", "text", "speaker", "stage", "language", "pause_before_ms", "pause_after_ms", "style", "audio"}
SID = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_PAUSE_MS = 5000


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def cache_key(**parts):
    return hashlib.sha256(json.dumps(dict(parts, v=VERSION), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def make_plan(casting, script, base_dir="."):
    base = Path(base_dir)
    reg, roles, block = casting["registry"], casting["roles"], casting["rules"]["block_mismatch"]
    if not isinstance(script, dict) or not isinstance(script.get("sentences"), list) or not script["sentences"]:
        raise VoiceError("script: 'sentences' must be a non-empty list")
    lang0 = script.get("language")
    if not isinstance(lang0, str) or not LANG.match(lang0) or lang0 == "*":
        raise VoiceError("script.language must be an ISO 639 code such as 'en' or 'fa'")
    errors, findings, rows, seen = [], list(casting["findings"]), [], set()
    for n, s in enumerate(script["sentences"]):
        w = f"script.sentences[{n}]"
        if not isinstance(s, dict):
            errors.append(f"{w} must be an object")
            continue
        extra = sorted(set(s) - SENT_KEYS)
        if extra:
            errors.append(f"{w}: unknown field(s) {', '.join(extra)}")
        sid = s.get("id")
        if not isinstance(sid, str) or not SID.match(sid) or sid in seen:
            errors.append(f"{w}: bad or duplicate id {sid!r}")
            continue
        seen.add(sid)
        if not isinstance(s.get("text"), str) or not s["text"].strip():
            errors.append(f"{sid}: text is required")
            continue
        lang = s.get("language", lang0)
        if not isinstance(lang, str) or not LANG.match(lang) or lang == "*":
            errors.append(f"{sid}: language must be an ISO 639 code")
            continue
        spk = s.get("speaker", NARRATOR)
        if spk == NARRATOR:
            if not casting["narrator"]:
                errors.append(f"{sid}: no narrator voice in the casting")
                continue
            vid, override, stage = casting["narrator"]["voice"], None, None
        elif spk in roles:
            stage = s.get("stage")
            vid = roles[spk]["stages"].get(stage, roles[spk]["voice"]) if stage else roles[spk]["voice"]
            override = roles[spk]["override"]
        else:
            errors.append(f"{sid}: speaker '{spk}' is not 'narrator' or a role of the casting ({', '.join(sorted(roles)) or 'none'})")
            continue
        voice = reg.get(vid)
        pb, pa = s.get("pause_before_ms", 0), s.get("pause_after_ms", 0)
        if not all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= MAX_PAUSE_MS for x in (pb, pa)):
            errors.append(f"{sid}: pause_before_ms / pause_after_ms must be integers 0..{MAX_PAUSE_MS}")
            continue
        if not reg.speaks(vid, lang):
            msg = f"sentence {sid}: voice '{vid}' is not listed for language '{lang}' ({', '.join(voice['languages'])})"
            role = spk
            if block:                   # absolute, like the casting rule: an override cannot lift it
                findings.append(finding("block", "language_mismatch", role, msg + " (blocked by rules.block_mismatch; "
                                                                               "an override does not lift this rule)"))
            elif override:
                findings.append(finding("override", "language_mismatch_overridden", role, msg + f" - overridden: {override}"))
            else:
                findings.append(finding("warning", "language_mismatch", role, msg))
        if "audio" in s:
            a = s["audio"]
            if not isinstance(a, str) or Path(a).is_absolute() or ".." in Path(a).parts:
                errors.append(f"{sid}: audio must be a relative path inside the project")
                continue
            f = base / a
            if not f.is_file():
                errors.append(f"{sid}: prepared audio '{a}' not found")
                continue
            source = {"kind": "prepared", "file": a, "sha256": sha256_file(f)}
        elif voice["provider"] == "synthetic":
            source = {"kind": "synthetic", "f0": voice["params"]["f0"]}
        elif voice["provider"] == "prepared":
            errors.append(f"{sid}: voice '{vid}' is a prepared-recording voice: the sentence needs 'audio'")
            continue
        elif voice["provider"] == "piper":            # local real speech; the model file must be there (no download here)
            from .providers.base import ProviderError
            from .providers.piper import model_path
            try:
                mp = model_path(voice["params"]["model"])
            except ProviderError as e:
                errors.append(f"{sid}: {e}")
                continue
            source = {"kind": "piper", "model": voice["params"]["model"], "model_sha256": sha256_file(mp),
                      **({"length_scale": voice["params"]["length_scale"]} if voice["params"].get("length_scale") else {})}
        else:
            source = {"kind": voice["provider"]}       # planned for review; producing it is refused (no API in this version)
        style = s.get("style") or (casting["narrator"].get("style") if spk == NARRATOR and casting["narrator"] else None)
        rows.append({"id": sid, "text": s["text"], "language": lang, "speaker": spk, "stage": stage, "voice": vid,
                     "provider": source["kind"], "source": source, "style": style, "pause_before_ms": pb, "pause_after_ms": pa,
                     "cache_key": cache_key(provider=source["kind"], voice=vid, style=style, language=lang, text=s["text"],
                                            pause_before_ms=pb, pause_after_ms=pa,
                                            file_sha256=source.get("sha256") or source.get("model_sha256"))})
    blocks = [f for f in findings if f["level"] == "block"]
    if errors or blocks:
        raise VoiceError(errors + [f"BLOCK {f['role']}: {f['message']}" for f in blocks])
    speakers = {}
    for r in rows:
        speakers.setdefault(r["speaker"], {"voice_ids": [], "sentences": []})
        if r["voice"] not in speakers[r["speaker"]]["voice_ids"]:
            speakers[r["speaker"]]["voice_ids"].append(r["voice"])
        speakers[r["speaker"]]["sentences"].append(r["id"])
    plan = {"schema": SCHEMA, "version": VERSION, "project": casting.get("project"), "language": lang0,
            "rules": casting["rules"], "sentences": rows, "speakers": speakers, "findings": findings}
    plan["digest"] = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return plan
