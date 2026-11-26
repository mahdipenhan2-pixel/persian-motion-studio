"""NFP Production Orchestrator - D2: preflight. Before any costly step, every document of the project is checked with its
OWN engine's public checks (nothing is re-implemented here), the environment's dependencies are looked up, and the
network / paid work the run would do is counted - without a single request.

  preflight(plan, fonts=None, gsap=None) -> nfp.orchestrator.preflight/1:
     {"status": OK | WARN | FAIL, "issues": [{level, engine, code, message}],                  the PROJECT's documents
      "environment": {name: {"ok", "detail", "needed_by": [steps]}},                           what this machine has
      "cost": {"network": {step: reason}, "gemini_requests": n | None}}                      what would go online

Engines and their checks (read-only; a check that needs word timing is said to run at compose):
  film       project.json (Film's loader), the shot file, the language's fonts in the fonts folder
  character  cast.json + cast.lock.json (registry.load_and_check); every characters[].character in the cast
  voice      voice block, casting, the Voice plan of the chapter (voice_bridge + nfp.voice); Gemini requests = cache
             misses of Gemini voices (nfp.voice estimate)     the core's TTS: sentences not in its audio cache, by the
             core's own load_inputs / sentence_hash (read-only: `run.py check` would create the cache folder)
  subtitles  the subtitles block (subtitles.settings)
  timeline   timeline.json + assets.json (timeline.validate with the files and a local ffprobe; anchors at compose)
  mapmotion  every map clip's bundle + its map plan without word timing (mapmotion.build; anchors at compose)
  graphics   every graphic clip's document for its track (graphics.filmclip.prepare)
Levels: error (the run would fail: FAIL), warning, info. Environment gaps are NOT project errors: they say which steps
cannot run here (the runner blocks those steps with the same reason).
"""
import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import plan as PL

PREFLIGHT_SCHEMA = "nfp.orchestrator.preflight/1"
HF_VERSION = "0.9.83"


def _paths():
    for p in (str(PL.ENGINE), str(PL.NFP), str(PL.ROOT / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)


def hyperframes_offline():
    """Is HyperFrames <HF_VERSION> in the local npx cache (npm offline: nothing is downloaded)?"""
    if not shutil.which("npx"):
        return False, "npx not installed"
    try:
        r = subprocess.run(["npx", "--yes", f"hyperframes@{HF_VERSION}", "--version"], capture_output=True, text=True, cwd="/tmp",
                           env=dict(os.environ, npm_config_offline="true"), timeout=180)
    except subprocess.TimeoutExpired:
        return False, "npx timed out"
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())[-80:]


def tts_requests(proj, ch):
    """The core's TTS requests a run would make (sentences not in its audio cache), with the core's OWN checks and hash
    (story_stage2.load_inputs / sentence_hash / spoken) on a temporary copy of the script / config - read-only: nothing is
    created in the repository (the core's own `check` would create its cache folder), nothing is sent."""
    import contextlib
    import io
    import tempfile
    import project as P
    import story_stage2 as core
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "script.json").write_text(json.dumps(P.core_script(proj, ch), ensure_ascii=False), encoding="utf-8")
        (td / "config.json").write_text(json.dumps(P.core_config(proj, ch), ensure_ascii=False), encoding="utf-8")
        keep = core.CONFIG_PATH, core.SCRIPT_PATH
        core.CONFIG_PATH, core.SCRIPT_PATH = td / "config.json", td / "script.json"
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                cfg, script = core.load_inputs()
        except SystemExit:
            raise ValueError(err.getvalue().strip().replace("ERROR: ", "") or "invalid") from None
        finally:
            core.CONFIG_PATH, core.SCRIPT_PATH = keep
    sents = script["sentences"]
    n = sum(not (core.AUDIO_CACHE / f"{core.sentence_hash(cfg['tts'], core.spoken(s))}.wav").exists() for s in sents)
    return n, len(sents)


def environment(pl, fonts=None, gsap=None):
    steps = {s["name"] for s in pl["steps"]}
    env = {}

    def put(name, ok, detail, needed_by):
        needed = [s for s in needed_by if s in steps]
        if needed:
            env[name] = {"ok": bool(ok), "detail": detail, "needed_by": needed}

    put("ffmpeg", shutil.which("ffmpeg"), shutil.which("ffmpeg") or "not installed", ["prepare", "audio", "verify", "render"])
    put("ffprobe", shutil.which("ffprobe"), shutil.which("ffprobe") or "not installed", ["prepare", "compose", "render", "verify"])
    fw = importlib.util.find_spec("faster_whisper") is not None
    put("faster_whisper", fw, "importable (its model may be fetched once on first use)" if fw else "the faster_whisper module is not installed", ["whisper"])
    put("node", shutil.which("node"), shutil.which("node") or "not installed", ["compose", "smoke", "render"])
    g = Path(gsap) if gsap else None
    put("gsap", g is not None and g.is_file(), str(g) if g else "no local GSAP copy given (--gsap or NFP_GSAP): the page loads it from a CDN",
        ["smoke", "render"])
    if "render" in steps:
        ok, detail = hyperframes_offline()
        put("hyperframes", ok, f"{HF_VERSION} in the local npx cache: {detail}" if ok else f"{HF_VERSION} is not in the local npx cache ({detail}): "
            "rendering would download it", ["render"])
    fdir = Path(fonts) if fonts else None
    put("fonts", fdir is not None and fdir.is_dir() and any(fdir.glob("*.woff2")), str(fdir) if fdir else "no fonts folder", ["compose"])
    return env


def preflight(pl, fonts=None, gsap=None):
    _paths()
    issues = []
    cost = {"network": {}, "gemini_requests": None}

    def add(level, engine, code, msg):
        issues.append({"level": level, "engine": engine, "code": code, "message": msg})

    import project as P
    proj = P.load(pl["project"])
    ch = P.chapter(proj, pl["chapter"])
    pdir = Path(proj["_dir"])
    f = pl["features"]
    # ---- film
    if not (pdir / proj["shots"]).is_file():
        add("error", "film", "shots_missing", f"the shot file {proj['shots']} is missing")
    if fonts:
        import compose as C
        need = [fn for _, _, fn in C.FONTS[proj["meta"]["lang"]]["faces"]]
        miss = sorted({fn for fn in need if not (Path(fonts) / fn).is_file()})
        if miss:
            add("warning", "film", "fonts_missing", f"the fonts folder lacks {', '.join(miss)} ({proj['meta']['lang']} text would use a fallback)")
    # ---- character
    if f["cast"]:
        sys.path.insert(0, str(PL.NFP))
        from character import registry as CR
        d = (proj.get("cast") or {}).get("dir")
        if d:
            try:
                cast = CR.load_and_check(pdir / d)
                for e in proj.get("characters") or []:
                    try:
                        CR.character(cast, e["character"])
                    except Exception as x:                                   # noqa: BLE001 - the engine's own message
                        add("error", "character", "unknown_character", f"characters[{e.get('actor')}]: {x}")
            except CR.CastError as e:
                for p_ in e.problems:
                    add("error", "character", "cast", p_)
        elif proj.get("characters"):
            add("error", "character", "cast_missing", "characters are listed but project.cast.dir is not given")
    # ---- voice / tts and their cost
    if f["voice_engine"]:
        import voice_bridge as VB
        try:
            cfg = VB.config(proj)
            voice, Cache = VB._voice()
            casting = voice.load_casting(cfg["casting"])
            vplan = voice.make_plan(casting, VB.voice_script(proj, ch), base_dir=pdir)
            cache = None
            if cfg["cache"] is not False:
                cache = Cache(None if cfg["cache"] is True else (pdir / cfg["cache"] if not Path(cfg["cache"]).is_absolute() else cfg["cache"]))
            from voice.manifest import estimate
            est = estimate(vplan, rate=cfg["rate"], normalize=cfg["normalize"], cache=cache, providers=cfg["providers"])
            n = sum(e["requests"] for e in est.values())
            cost["gemini_requests"] = n
            g = est.get("gemini")
            if g and g["to_make"]:
                if "gemini" not in (cfg["providers"] or {}):
                    add("error", "voice", "gemini_disabled", f"{len(g['to_make'])} sentence(s) use Gemini voices but voice.providers does not enable "
                                                             "Gemini (the Voice Engine would refuse them)")
                else:
                    cost["network"]["audio"] = f"Voice Engine: {n} Gemini TTS request(s) (cache misses)"
        except Exception as e:                                               # noqa: BLE001 - VoiceBridgeError / VoiceError / CacheError
            msg = "; ".join(getattr(e, "problems", []) or [str(e)])
            add("error", "voice", "voice", msg[:600])
    else:
        try:
            n, total = tts_requests(proj, ch)
            cost["gemini_requests"] = n
            if n:
                cost["network"]["audio"] = f"the core's Gemini TTS: {n} of {total} sentence(s) not in its audio cache = {n} request(s)"
        except ValueError as e:
            add("error", "voice", "tts_config", f"the core's tts settings: {e}")
    # ---- subtitles
    if f["subtitles"]:
        import subtitles as SB
        try:
            SB.settings(proj)
        except SB.SubtitleError as e:
            add("error", "subtitles", "settings", str(e))
    # ---- timeline (+ map / graphic clips)
    if f["timeline"]:
        import timeline_bridge as TB
        TL, _, _ = TB._tl()
        try:
            tcfg = TB.config(proj)
            doc = json.loads(tcfg["file"].read_text(encoding="utf-8"))
            adoc = json.loads(tcfg["assets"].read_text(encoding="utf-8")) if "assets" in tcfg else None
        except (SystemExit, OSError, ValueError) as e:
            add("error", "timeline", "files", str(e)[:400])
            doc = None
        if doc is not None:
            rep = TL.validate(doc, adoc, tcfg["assets"].parent if "assets" in tcfg else None, None, check_files=True, probe=TB.probe)
            for x in rep["issues"]:
                if x["level"] in ("error", "warning"):
                    add(x["level"], "timeline", x["code"], f"{x.get('clip') or x.get('asset') or x.get('track') or '-'}: {x['message']}")
            if any(x["code"] == "anchors_unchecked" or "anchor" in x["code"] for x in rep["issues"] if x["level"] == "info"):
                add("info", "timeline", "anchors_at_compose", "anchors are resolved against the word timing at compose")
            kinds = {t["id"]: t["kind"] for t in doc.get("tracks", []) if isinstance(t, dict)}
            for c in doc.get("clips", []) if isinstance(doc.get("clips"), list) else []:
                if not isinstance(c, dict):
                    continue
                if c.get("kind") == "graphic" and isinstance(c.get("ref"), str):
                    from graphics import filmclip as GF
                    try:
                        GF.prepare(GF.load(c["ref"], pdir), c, kinds.get(c.get("track")), doc.get("mode", "draft"))
                    except (ValueError, KeyError) as e:
                        add("error", "graphics", "graphic", f"clip {c.get('id')}: {e}"[:400])
                elif c.get("kind") == "map" and isinstance(c.get("ref"), str):
                    from mapmotion import filmclip as MF
                    import mapmotion as M
                    try:
                        docs = MF.load(c["ref"], pdir)
                        mp = M.build(docs["map"], docs["locations"], context=None, today=docs["today"])
                        for x in mp["qc"]["issues"]:
                            if x["level"] == "error":
                                add("error", "mapmotion", x["code"], f"clip {c.get('id')}: {x.get('element') or '-'}: {x['message']}"[:400])
                    except (ValueError, KeyError) as e:
                        add("error", "mapmotion", "map", f"clip {c.get('id')}: {e}"[:400])
                    add("info", "mapmotion", "at_compose", f"clip {c.get('id')}: its window, scene and labels are checked at compose (word timing, fonts)")
    env = environment(pl, fonts, gsap)
    if "hyperframes" in env and not env["hyperframes"]["ok"]:
        cost["network"]["render"] = "HyperFrames is not in the local npx cache: rendering would download it"
    if "faster_whisper" in env and env["faster_whisper"]["ok"]:
        cost["network"].setdefault("whisper", "faster-whisper may download its model on first use (once)")
    ne = sum(x["level"] == "error" for x in issues)
    nw = sum(x["level"] == "warning" for x in issues)
    return {"schema": PREFLIGHT_SCHEMA, "project": pl["project"], "chapter": pl["chapter"], "checked": datetime.date.today().isoformat(),
            "status": "FAIL" if ne else "WARN" if nw else "OK", "issues": issues, "environment": env, "cost": cost}
