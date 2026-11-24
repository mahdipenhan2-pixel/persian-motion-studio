"""NFP Voice Engine - produce the sentence audio of a plan and describe it (voice_manifest.json, nfp.voice.manifest/1).

    m = produce(plan, out_dir, base_dir=".", rate=24000)   # out_dir/audio/<id>.wav + out_dir/voice_manifest.json
    problems = validate_manifest(out_dir / "voice_manifest.json")

The manifest is the hand-over to the rest of NFP: per sentence the speaker, voice, provider, source (and its hash),
the pauses, the exact duration / frames of the produced file and its sha256. Word timing is NOT in it: words come
from the Stage 2 alignment as before (timing.json / words.json); the manifest only says who speaks which sentence.
"""
import hashlib
import json
import shutil
import wave
from pathlib import Path

from .plan import SCHEMA as PLAN_SCHEMA, VERSION
from .providers import PROVIDERS, ProviderError
from .providers.base import read_wav
from .registry import VoiceError

SCHEMA = "nfp.voice.manifest/1"
RATES = {16000, 22050, 24000, 44100, 48000}
SENT_FIELDS = {"id", "text", "language", "speaker", "stage", "voice", "provider", "source", "style", "pause_before_ms",
               "pause_after_ms", "cache_key", "file", "sha256", "rate", "frames", "duration"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _render_params(r, prov_cfg):
    """What besides the plan's cache_key changes a sentence file: the source details (+ the AI model)."""
    if r["provider"] == "gemini":
        return dict(r["source"], model=prov_cfg["model"])
    return r["source"]


def estimate(plan, rate=24000, normalize=None, cache=None, providers=None):
    """How many sentences each provider would have to make (cache misses) - no request, no file written."""
    from .cache import render_key
    from .normalize import settings as norm_settings
    from .providers.gemini import settings as gemini_settings
    ns = norm_settings(normalize) if normalize is not None else None
    gcfg = gemini_settings(_gemini_config(providers)) if _gemini_enabled(providers) else gemini_settings({})
    out = {}
    for r in plan["sentences"]:
        hit = False
        if cache is not None:
            hit = cache.peek(render_key(r, rate, ns, _render_params(r, gcfg)), rate)
        e = out.setdefault(r["provider"], {"sentences": 0, "cached": 0, "to_make": [], "requests": 0})
        e["sentences"] += 1
        if hit:
            e["cached"] += 1
        else:
            e["to_make"].append(r["id"])
            if r["provider"] == "gemini":
                e["requests"] += 1
    return out


def _gemini_enabled(providers):
    return bool(providers) and "gemini" in providers


def _gemini_config(providers):
    from .providers.gemini import GeminiProvider
    g = providers["gemini"]
    return g.s if isinstance(g, GeminiProvider) else g


def produce(plan, out_dir, base_dir=".", rate=24000, normalize=None, qc=None, cache=None, providers=None):
    """Sentence files + voice_manifest.json. Optional (V2), each independent:
         normalize  dict of normalize.settings  -> any WAV -> engine format + one constant loudness gain
         qc         dict of qc.thresholds       -> qc_report.json; any QC error stops the run (after writing the report)
         cache      a cache.Cache               -> finished files reused by render key (hit / miss recorded)
         providers  {"gemini": settings | GeminiProvider} (V3) -> enables AI speech for 'gemini' voices; OFF by default.
                    Before the first request: free-model check, the GEMINI_FREE_TIER_CONFIRMED gate, the API key and
                    the budget (sentences to make > max_requests -> refused, nothing sent). HTTP 429 stops the run.
       Without them the result is exactly the V1 result."""
    if plan.get("schema") != PLAN_SCHEMA:
        raise VoiceError(f"produce: a plan ({PLAN_SCHEMA}) is required")
    if rate not in RATES:
        raise VoiceError(f"produce: rate must be one of {sorted(RATES)}")
    from .audiotools import AudioToolError
    from .cache import render_key
    from .normalize import settings as norm_settings
    from .qc import QCError, check_file, report as qc_report, thresholds
    try:
        ns = norm_settings(normalize) if normalize is not None else None
        qt = thresholds(qc) if qc is not None else None
    except (AudioToolError, QCError) as e:
        raise VoiceError(str(e))
    gprov = None
    if _gemini_enabled(providers):
        from .providers.gemini import GeminiProvider
        try:
            g = providers["gemini"]
            gprov = g if isinstance(g, GeminiProvider) else GeminiProvider(g)
            need = estimate(plan, rate, normalize, cache, {"gemini": gprov})
            n = need.get("gemini", {}).get("requests", 0)
            if n > gprov.s["max_requests"]:
                raise VoiceError(f"gemini: {n} sentence(s) would need a request but the budget of this run is "
                                 f"{gprov.s['max_requests']} - nothing was sent (raise max_requests deliberately)")
            if n:
                gprov.check_gates()                     # before ANY request
        except ProviderError as e:
            raise VoiceError(str(e))
    out = Path(out_dir)
    (out / "audio").mkdir(parents=True, exist_ok=True)
    rows, extra, qcs = [], {}, []
    for r in plan["sentences"]:
        cls = PROVIDERS.get(r["provider"])
        if r["provider"] == "gemini" and gprov is not None:
            cls = gprov
        if cls is None:
            raise VoiceError(f"{r['id']}: provider '{r['provider']}' has no connection in this version unless it is "
                             "explicitly enabled (providers={'gemini': {...}} / --allow-tts gemini; a real request needs "
                             "approval); use a prepared recording ('audio') or a synthetic voice")
        f = out / "audio" / f"{r['id']}.wav"
        key = render_key(r, rate, ns, _render_params(r, gprov.s if gprov else None)) if cache is not None else None
        hit = cache.get(key, rate) if cache is not None else None
        try:
            if hit:
                shutil.copyfile(hit["path"], f)
                info = hit["meta"]["info"]
            elif r["provider"] == "gemini":
                info = _ai_sentence(r, f, rate, ns, gprov)
            elif ns is None:
                info = cls().produce(r, f, rate, base_dir=base_dir)
                info["body_frames"] = info["frames"] - _pause_frames(r, rate)
            else:
                info = _normalized(r, f, rate, base_dir, ns, cls)
            if cache is not None and not hit:
                cache.put(key, f, info)
        except (ProviderError, AudioToolError) as e:
            raise VoiceError(f"{r['id']}: {e}")
        row = {k: r[k] for k in ("id", "text", "language", "speaker", "stage", "voice", "provider", "source", "style",
                                 "pause_before_ms", "pause_after_ms", "cache_key")}
        row.update(file=f"audio/{r['id']}.wav", sha256=_sha(f), rate=info["rate"], frames=info["frames"], duration=info["duration"])
        if ns is not None:
            row["normalize"] = info.get("normalize")
        if cache is not None:
            row["cache"] = {"key": key, "hit": bool(hit)}
        if r["provider"] == "gemini":
            row["generation"] = {"model": info.get("model"), "requested": not hit, "source_rate": info.get("source_rate")}
        if qt is not None:
            q = check_file(f, rate, qt, r["id"], planned={"pause_before_ms": r["pause_before_ms"], "pause_after_ms": r["pause_after_ms"],
                                                          "body_frames": info["body_frames"],
                                                          "target_lufs": ns["target_lufs"] if ns and ns["loudness"] else None})
            qcs.append(q)
            row["qc"] = q["status"]
        rows.append(row)
        if "synthetic_words" in info:
            extra[r["id"]] = info["synthetic_words"]
    m = {"schema": SCHEMA, "version": VERSION, "project": plan.get("project"), "language": plan["language"],
         "sample_rate": rate, "channels": 1, "sample_width": 2, "plan_digest": plan["digest"], "rules": plan["rules"],
         "speakers": plan["speakers"], "sentences": rows, "findings": plan["findings"],
         "synthetic": bool(extra), "synthetic_words": extra}
    if ns is not None:
        m["normalize"] = ns
    if cache is not None:
        m["cache"] = {"schema": "nfp.voice.cache/1", "dir": str(cache.dir), **cache.stats}
    if gprov is not None:
        m["providers"] = {"gemini": {"model": gprov.s["model"], "max_requests": gprov.s["max_requests"],
                                     "requests_used": gprov.used}}
    if qt is not None:
        rep = qc_report(qcs, qt)
        (out / "qc_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        m["qc"] = {"report": "qc_report.json", "summary": rep["summary"]}
    (out / "voice_manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if qt is not None and rep["summary"]["error"]:
        errs = [f"{q['id']}: {c['check']}: {c['message']}" for q in qcs for c in q["checks"] if c["level"] == "error"]
        raise VoiceError(["QC failed (see qc_report.json):"] + errs)
    return m


def _ai_sentence(r, f, rate, ns, prov):
    """AI speech for one sentence: provider -> (normalize) -> planned pauses around it -> file."""
    import tempfile
    from .providers.base import read_wav, silence, write_wav
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "ai.wav"
        pinfo = prov.produce(r, raw, rate)
        if ns is not None:
            from .normalize import convert, match_loudness
            pcm, cinfo = convert(raw, rate)
            linfo = None
            if ns["loudness"]:
                pcm, linfo = match_loudness(pcm, rate, ns)
            norm = {"input": cinfo["input"], "resampled": cinfo["resampled"], "downmixed": cinfo["downmixed"],
                    "requantized": cinfo["requantized"], "loudness": linfo}
        else:
            w = read_wav(raw)
            if (w["channels"], w["sample_width"], w["rate"]) != (1, 2, rate):
                raise ProviderError(f"the AI audio is {w['channels']} ch / {8 * w['sample_width']}-bit / {w['rate']} Hz; "
                                    f"this run is mono 16-bit {rate} Hz - enable normalize to convert it")
            pcm, norm = w["pcm"], None
    info = write_wav(f, silence(r["pause_before_ms"] / 1000, rate) + pcm + silence(r["pause_after_ms"] / 1000, rate), rate)
    info["body_frames"] = len(pcm) // 2
    info.update(model=pinfo["model"], source_rate=pinfo["source_rate"])
    if norm is not None:
        norm["output"] = {"rate": rate, "channels": 1, "bits": 16, "frames": info["frames"], "duration": info["duration"]}
        info["normalize"] = norm
    return info


def _pause_frames(r, rate):
    return int(round(r["pause_before_ms"] / 1000 * rate)) + int(round(r["pause_after_ms"] / 1000 * rate))


def _normalized(r, f, rate, base_dir, ns, cls):
    """Source -> engine format -> one constant loudness gain -> planned pauses around it -> file."""
    import tempfile
    from .normalize import convert, match_loudness
    from .providers.base import silence, write_wav
    if r["provider"] == "prepared":
        src = Path(base_dir) / r["source"]["file"]
        from .plan import sha256_file
        if sha256_file(src) != r["source"]["sha256"]:
            raise ProviderError(f"'{r['source']['file']}' changed after planning (sha256 differs); plan again")
        pcm, cinfo = convert(src, rate)
        words = None
    else:                                           # synthetic: made at the run's rate, without pauses
        with tempfile.TemporaryDirectory() as td:
            body = dict(r, pause_before_ms=0, pause_after_ms=0)
            pinfo = cls().produce(body, Path(td) / "b.wav", rate, base_dir=base_dir)
            with wave.open(str(Path(td) / "b.wav"), "rb") as w:
                pcm = w.readframes(w.getnframes())
        cinfo = {"input": {"format": "synthetic", "rate": rate, "channels": 1, "bits": 16, "frames": len(pcm) // 2,
                           "duration": round(len(pcm) / 2 / rate, 6)}, "resampled": False, "downmixed": False, "requantized": False}
        words = pinfo["synthetic_words"]
    linfo = None
    if ns["loudness"]:
        pcm, linfo = match_loudness(pcm, rate, ns)
    lead = r["pause_before_ms"] / 1000
    info = write_wav(f, silence(lead, rate) + pcm + silence(r["pause_after_ms"] / 1000, rate), rate)
    info["body_frames"] = len(pcm) // 2
    info["normalize"] = {"input": cinfo["input"], "resampled": cinfo["resampled"], "downmixed": cinfo["downmixed"],
                         "requantized": cinfo["requantized"], "loudness": linfo,
                         "output": {"rate": rate, "channels": 1, "bits": 16, "frames": info["frames"], "duration": info["duration"]}}
    if words is not None:
        info["synthetic_words"] = [[round(s + lead, 6), round(e + lead, 6), w] for s, e, w in words]
    return info


def validate_manifest(path):
    """Problems (empty = valid): schema, fields, ids, one sample rate, files present, format, frames, sha256, speakers."""
    p, path = [], Path(path)
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"manifest: cannot read {path}: {e}"]
    if m.get("schema") != SCHEMA:
        return [f"manifest: schema must be '{SCHEMA}'"]
    rate = m.get("sample_rate")
    if rate not in RATES or m.get("channels") != 1 or m.get("sample_width") != 2:
        p.append("manifest: sample_rate / channels / sample_width invalid")
    rows = m.get("sentences")
    if not isinstance(rows, list) or not rows:
        return p + ["manifest: sentences must be a non-empty list"]
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids):
        p.append("manifest: duplicate sentence ids")
    for r in rows:
        w = f"manifest {r.get('id')}"
        miss = sorted(SENT_FIELDS - set(r))
        if miss:
            p.append(f"{w}: missing field(s) {', '.join(miss)}")
            continue
        f = path.parent / r["file"]
        if not f.is_file():
            p.append(f"{w}: file {r['file']} missing")
            continue
        if _sha(f) != r["sha256"]:
            p.append(f"{w}: {r['file']} changed (sha256 differs)")
        try:
            a = read_wav(f)
        except ProviderError as e:
            p.append(f"{w}: {e}")
            continue
        if (a["channels"], a["sample_width"], a["rate"]) != (1, 2, rate):
            p.append(f"{w}: {r['file']} is not mono 16-bit at {rate} Hz")
        if a["frames"] != r["frames"] or abs(a["frames"] / a["rate"] - r["duration"]) > 1e-6:
            p.append(f"{w}: frames / duration differ from the file")
        if r["speaker"] not in m.get("speakers", {}) or r["id"] not in m["speakers"][r["speaker"]]["sentences"]:
            p.append(f"{w}: speaker '{r['speaker']}' not listed in speakers")
        c = r.get("cache")
        if c is not None and not (isinstance(c, dict) and isinstance(c.get("hit"), bool) and isinstance(c.get("key"), str)
                                  and len(c["key"]) == 64):
            p.append(f"{w}: cache must be {{key: <sha256>, hit: true|false}}")
        if "normalize" in m and not isinstance(r.get("normalize"), dict):
            p.append(f"{w}: normalize details missing")
        if "qc" in m and r.get("qc") not in ("ok", "warning", "error"):
            p.append(f"{w}: qc status missing")
    if "qc" in m and not (path.parent / m["qc"].get("report", "")).is_file():
        p.append("manifest: qc_report.json missing")
    return p
