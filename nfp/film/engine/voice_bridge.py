"""NFP Film - Voice Engine bridge (V4). The ONLY Film file that imports nfp/voice, and only for projects that ask for it.

project.json (optional; without it Film runs its legacy path and never imports this module):
  "voice": {"engine": "nfp.voice/1",
            "casting": "voices.cast.json",          # nfp.voice.casting/1, next to project.json
            "rate": 24000,                           # sentence WAV rate handed to the Stage 2 core
            "normalize": {} | false,                 # nfp/voice normalize settings ({} = defaults); default {}
            "qc": {} | false,                        # QC thresholds; default {}
            "cache": "<dir>" | true | false,         # audio cache folder (true = default cache outside the repo); default false
            "providers": {"gemini": {...}}}          # AI speech, OFF unless listed (gates in nfp/voice/providers/gemini.py)
  chapters[].sentences[]: "speaker" = 'narrator' or a Film actor key (characters[].actor), optional
                          "pause_before_ms" / "pause_after_ms" (silence inside that sentence's own file)

Flow of `run.py voice`: the chapter's sentences -> the Voice script (speaker = the actor's C1 character + stage) ->
nfp/voice plan -> produce into <build>/voice (normalize / QC / cache / manifest) -> ONLY after a complete success the
sentence WAVs are copied to <build>/audio/<id>.wav and a core-compatible tts_meta.json is written. From there the
unchanged Stage 2 core continues (prepare -> whisper -> align -> timing.json) and Film composes as before
(words.json, SRT, subtitles, C3 lip sync). Nothing here re-implements timing, alignment or lip sync.
A failure stops with a clear message and leaves <build>/audio untouched; no service is called as a fallback.
"""
import json
import shutil
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
NFP = ENGINE.parent.parent
ENGINE_ID = "nfp.voice/1"
KEYS = {"engine", "casting", "rate", "normalize", "qc", "cache", "providers", "voice", "style"}


class VoiceBridgeError(SystemExit):
    pass


def enabled(project):
    v = project.get("voice") or {}
    return isinstance(v, dict) and "engine" in v


def config(project):
    v = project["voice"]
    if v.get("engine") != ENGINE_ID:
        raise VoiceBridgeError(f"voice.engine must be '{ENGINE_ID}'")
    extra = sorted(set(v) - KEYS)
    if extra:
        raise VoiceBridgeError(f"voice: unknown field(s) {', '.join(extra)}")
    c = v.get("casting")
    if not isinstance(c, str) or Path(c).is_absolute() or ".." in Path(c).parts:
        raise VoiceBridgeError("voice.casting must be a relative path inside the project (e.g. voices.cast.json)")
    norm = v.get("normalize", {})
    qc = v.get("qc", {})
    cache = v.get("cache", False)
    for k, x in (("normalize", norm), ("qc", qc)):
        if x is not False and not isinstance(x, dict):
            raise VoiceBridgeError(f"voice.{k} must be an object or false")
    if not (cache is False or cache is True or isinstance(cache, str)):
        raise VoiceBridgeError("voice.cache must be a folder, true or false")
    return {"casting": Path(project["_dir"]) / c, "rate": v.get("rate", 24000), "normalize": None if norm is False else norm,
            "qc": None if qc is False else qc, "cache": cache, "providers": v.get("providers")}


def voice_script(project, chapter):
    """Film sentences -> Voice script: the speaker becomes the C1 character (+ stage) of the actor that speaks."""
    actors = {e["actor"]: e for e in project.get("characters") or []}
    out = []
    for s in chapter["sentences"]:
        spk = s.get("speaker", "narrator")
        row = {"id": s["id"], "text": s.get("speak") or s["text"]}
        if spk != "narrator":
            if spk not in actors:
                raise VoiceBridgeError(f"sentence {s['id']}: speaker '{spk}' is not an actor of project.characters")
            row["speaker"] = actors[spk]["character"]
            if actors[spk].get("stage"):
                row["stage"] = actors[spk]["stage"]
        for k in ("pause_before_ms", "pause_after_ms"):
            if k in s:
                row[k] = s[k]
        out.append(row)
    return {"language": project["meta"]["lang"], "sentences": out}


def _voice():
    if str(NFP) not in sys.path:
        sys.path.insert(0, str(NFP))
    import voice                                   # nfp/voice (imported only here, only for engine projects)
    from voice.cache import Cache
    return voice, Cache


def produce(project, chapter, build, providers=None):
    """Make the chapter's sentence audio with the Voice Engine and hand it to the Stage 2 core input (<build>/audio)."""
    cfg = config(project)
    voice, Cache = _voice()
    build = Path(build)
    work = build / "voice"
    try:
        casting = voice.load_casting(cfg["casting"])
        plan = voice.make_plan(casting, voice_script(project, chapter), base_dir=Path(project["_dir"]))
        if work.exists():
            shutil.rmtree(work)
        cache = None
        if cfg["cache"] is not False:
            cache = Cache(None if cfg["cache"] is True else (Path(project["_dir"]) / cfg["cache"]
                                                            if not Path(cfg["cache"]).is_absolute() else cfg["cache"]))
        m = voice.produce(plan, work, base_dir=Path(project["_dir"]), rate=cfg["rate"], normalize=cfg["normalize"],
                          qc=cfg["qc"], cache=cache, providers=providers if providers is not None else cfg["providers"])
    except voice.VoiceError as e:
        raise VoiceBridgeError("ERROR (voice): " + "\n  ".join(e.problems) + "\n  <build>/audio was not changed.")
    problems = voice.validate_manifest(work / "voice_manifest.json")
    if problems:
        raise VoiceBridgeError("ERROR (voice): manifest invalid: " + "; ".join(problems))
    # hand-over only after a complete success
    (build / "audio").mkdir(parents=True, exist_ok=True)
    for r in m["sentences"]:
        shutil.copyfile(work / r["file"], build / "audio" / f"{r['id']}.wav")
    meta = {"engine": ENGINE_ID, "model": "nfp.voice", "voice": "per-speaker (see voice/voice_manifest.json)",
            "requests_used": (m.get("providers") or {}).get("gemini", {}).get("requests_used", 0),
            "sentences": [{"id": r["id"], "speaker": r["speaker"], "voice": r["voice"], "hash": r["sha256"],
                           "cache_hit": (r.get("cache") or {}).get("hit", False), "duration": r["duration"]}
                          for r in m["sentences"]]}
    (build / "tts_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return m


def manifest_speakers(build):
    """{sentence id: C1 character or 'narrator'} from <build>/voice/voice_manifest.json (for cast_plan)."""
    p = Path(build) / "voice" / "voice_manifest.json"
    if not p.is_file():
        raise VoiceBridgeError("ERROR (voice): this project uses the Voice Engine but <build>/voice/voice_manifest.json is "
                               "missing - run `run.py voice` before prepare / compose")
    m = json.loads(p.read_text(encoding="utf-8"))
    return {r["id"]: r["speaker"] for r in m["sentences"]}
