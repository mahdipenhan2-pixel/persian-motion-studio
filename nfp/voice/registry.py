"""NFP Voice Engine - voice registry (nfp.voice.registry/1).

    reg = load_registry(extra=casting.get("voices"))     # built-in voices.json + the project's own voices
    v = reg.get("synthetic:female")                       # {"provider", "presentation", "age", "languages", ...}

A voice id is '<provider>:<name>'. Attributes describe how the voice is perceived (presentation, age) and which
languages it may speak (ISO 639 codes, '*' = any). New languages need no code change: a language is just a code.
Standard library only.
"""
import copy
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = "nfp.voice.registry/1"
PROVIDERS = {"synthetic", "prepared", "gemini", "piper"}
PRESENTATIONS = {"female", "male", "neutral"}
AGES = {"child", "teen", "adult", "elder"}
VOICE_ID = re.compile(r"^[a-z]+:[A-Za-z0-9_.-]{1,64}$")
LANG = re.compile(r"^([a-z]{2,3}|\*)$")
KEYS = {"provider", "presentation", "age", "languages", "verified", "params", "source", "license"}


class VoiceError(ValueError):
    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("\n".join(self.problems))


def validate_voice(vid, v, where="voice"):
    p = []
    if not VOICE_ID.match(vid or ""):
        p.append(f"{where}: id '{vid}' must look like '<provider>:<name>'")
    if not isinstance(v, dict):
        return p + [f"{where} '{vid}' must be an object"]
    extra = sorted(set(v) - KEYS)
    if extra:
        p.append(f"{where} '{vid}': unknown field(s) {', '.join(extra)}")
    if v.get("provider") not in PROVIDERS:
        p.append(f"{where} '{vid}': provider must be one of {sorted(PROVIDERS)}")
    elif VOICE_ID.match(vid or "") and vid.split(":", 1)[0] != v["provider"]:
        p.append(f"{where} '{vid}': the id prefix must equal the provider '{v['provider']}'")
    if v.get("presentation") not in PRESENTATIONS:
        p.append(f"{where} '{vid}': presentation must be one of {sorted(PRESENTATIONS)}")
    if v.get("age") not in AGES:
        p.append(f"{where} '{vid}': age must be one of {sorted(AGES)}")
    langs = v.get("languages")
    if not isinstance(langs, list) or not langs or not all(isinstance(x, str) and LANG.match(x) for x in langs):
        p.append(f"{where} '{vid}': languages must be a non-empty list of ISO 639 codes (or '*')")
    if not isinstance(v.get("verified"), bool):
        p.append(f"{where} '{vid}': verified must be true or false")
    if v.get("provider") == "synthetic" and not (isinstance(v.get("params"), dict) and isinstance(v["params"].get("f0"), (int, float))
                                                 and 50 <= v["params"]["f0"] <= 1000):
        p.append(f"{where} '{vid}': a synthetic voice needs params.f0 (50-1000 Hz)")
    if v.get("provider") == "piper" and not (isinstance(v.get("params"), dict) and isinstance(v["params"].get("model"), str)
                                             and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", v["params"]["model"])):
        p.append(f"{where} '{vid}': a piper voice needs params.model (the model's file name without .onnx)")
    return p


class Registry:
    def __init__(self, voices):
        self._v = voices

    def get(self, vid):
        if vid not in self._v:
            raise VoiceError(f"voice '{vid}' is not in the registry (known: {', '.join(sorted(self._v))})")
        return copy.deepcopy(self._v[vid])

    def has(self, vid):
        return vid in self._v

    def ids(self):
        return sorted(self._v)

    def speaks(self, vid, lang):
        langs = self._v[vid]["languages"]
        return "*" in langs or lang in langs


def load_registry(extra=None, path=None):
    """Built-in registry (voices.json) plus a project's own voices; a project may not redefine a built-in voice."""
    data = json.loads(Path(path or HERE / "voices.json").read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise VoiceError(f"registry: schema must be '{SCHEMA}'")
    voices, problems = {}, []
    for vid, v in data.get("voices", {}).items():
        problems += validate_voice(vid, v, "registry voice")
        voices[vid] = v
    for vid, v in (extra or {}).items():
        if vid in voices:
            problems.append(f"project voice '{vid}' redefines a built-in voice; choose another id")
            continue
        problems += validate_voice(vid, v, "project voice")
        voices[vid] = v
    if problems:
        raise VoiceError(problems)
    return Registry(voices)
