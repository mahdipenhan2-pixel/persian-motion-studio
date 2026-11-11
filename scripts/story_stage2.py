#!/usr/bin/env python3
"""
NFP Story Studio - Stage 2: multi-sentence narrated video (30-60 s).

Commands (run in this order by .github/workflows/story-stage2.yml):
  check     validate inputs, show which sentences still need the Gemini API
  tts       Gemini TTS per sentence -> content-addressed cache (key only on a miss)
  prepare   build narration.wav (exact per-sentence offsets) + per-sentence Whisper inputs
  align     map Whisper word times onto the ORIGINAL script words, per sentence (strict)
  compose   write the HyperFrames composition + SRT
  verify    inspect the rendered MP4 (audio, size, highlight, blank-caption check)

Whisper itself runs in scripts/stage2_whisper.py (separate virtual environment).
Standard library only. The API key is never printed or written to disk.
"""
import argparse
import array
import base64
import difflib
import hashlib
import html
import json
import math
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORY = ROOT / "story"
BUILD = ROOT / "build" / "stage2"
CACHE = ROOT / ".cache" / "story"
AUDIO_CACHE = CACHE / "audio"
SCRIPT_PATH = STORY / "script.stage2.json"
CONFIG_PATH = STORY / "config.stage2.json"

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
# Models with a FREE-tier Standard price on the official pricing page (checked 2026-11-06).
FREE_STANDARD_MODELS = {
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
}
MAX_SENTENCES = 40
MAX_TEXT_CHARS = 160          # also keeps every sentence inside the caption area
MAX_REQUESTS_LIMIT = 40
MAX_TOTAL_SECONDS = 180
TOL = 0.05
BRACKET_MAX_RUN = 2           # at most this many consecutive unmatched words may be bracketed
BRACKET_MIN_PER_WORD = 0.08   # seconds of gap required per bracketed word
BRACKET_MAX_GAP = 1.5         # seconds
EDGE_SNAP_MS = 0.15           # Whisper edge further than this from the measured speech edge is snapped


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def gh_output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"file not found: {path}")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        die(f"invalid JSON in {path}: {e}")


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, check=False)
    except (FileNotFoundError, OSError) as e:
        die(f"could not run {cmd[0]}: {e}")
    if r.returncode != 0:
        die(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr.decode('utf-8', 'replace')[-1000:]}")
    return r.stdout


def num(v, name, lo, hi):
    if isinstance(v, bool):
        die(f"{name} must be a number")
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        die(f"{name} must be a number")
    if not math.isfinite(x) or not lo <= x <= hi:
        die(f"{name} must be between {lo} and {hi}")
    return x


# --------------------------------------------------------------------------
# Persian text
# --------------------------------------------------------------------------
_DIAC = re.compile("[\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]")
_MAP = {ord(a): b for a, b in {
    "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا",
    "ٱ": "ا", "آ": "ا", "ؤ": "و", "ئ": "ی"}.items()}
_MAP.update({0x06F0 + i: ord(str(i)) for i in range(10)})
_MAP.update({0x0660 + i: ord(str(i)) for i in range(10)})


def norm(text):
    """Letters/digits only. Used ONLY for matching, never for display."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    for ch in ("\u200c", "\u200d", "\u200e", "\u200f", "\u0640"):
        t = t.replace(ch, "")
    t = _DIAC.sub("", t).translate(_MAP).lower()
    return "".join(c for c in t if unicodedata.category(c)[0] in ("L", "N"))


def script_tokens(text):
    """Display tokens = whitespace-separated words of the ORIGINAL text (U+200C stays inside)."""
    return [{"i": i, "text": w, "norm": norm(w)} for i, w in enumerate(text.split())]


# --------------------------------------------------------------------------
# WAV helpers
# --------------------------------------------------------------------------
def ensure_wav(data):
    if not isinstance(data, bytes) or not data:
        die("audio response is empty")
    if data[:4] == b"RIFF":
        return data
    if len(data) % 2:
        die("headerless PCM audio has an odd length")
    tmp = BUILD / "_raw_wrap.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(data)
    out = tmp.read_bytes()
    tmp.unlink()
    return out


def wav_info(path):
    try:
        with wave.open(str(path), "rb") as w:
            info = {"channels": w.getnchannels(), "width": w.getsampwidth(),
                    "rate": w.getframerate(), "frames": w.getnframes()}
    except (wave.Error, EOFError, OSError) as e:
        die(f"{path} is not a readable WAV file: {e}")
    if info["channels"] != 1 or info["width"] != 2 or info["rate"] <= 0 or info["frames"] <= 0:
        die(f"{path}: expected non-empty mono 16-bit audio, found {info}")
    info["duration"] = info["frames"] / info["rate"]
    return info


def validate_wav(path):
    info = wav_info(path)
    if info["duration"] < 0.3:
        die(f"{path}: audio is suspiciously short ({info['duration']:.2f}s)")
    if info["duration"] > 60:
        die(f"{path}: a single sentence of {info['duration']:.0f}s is not expected")
    return info


def read_frames(path):
    with wave.open(str(path), "rb") as w:
        return w.readframes(w.getnframes())


def load_samples(path):
    info = wav_info(path)
    a = array.array("h")
    a.frombytes(read_frames(path))
    if sys.byteorder == "big":
        a.byteswap()
    return info["rate"], a


def speech_bounds(path, win=0.01):
    sr, a = load_samples(path)
    n = max(1, int(sr * win))
    rms = [math.sqrt(sum(x * x for x in a[i:i + n]) / max(1, len(a[i:i + n]))) for i in range(0, len(a), n)]
    peak = max(rms) if rms else 0
    idx = [i for i, v in enumerate(rms) if v > 0.08 * peak] if peak > 0 else []
    if not idx:
        return None, None, rms, win
    return idx[0] * win, (idx[-1] + 1) * win, rms, win


# --------------------------------------------------------------------------
# Config / script validation
# --------------------------------------------------------------------------
def sentence_hash(t, text):
    """Same payload as Stage 0, so identical sentences share cached audio."""
    payload = {"v": 1, "api": "interactions-default-wav", "model": t["model"],
               "voice": t["voice"], "style": t.get("style", ""), "text": text}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def load_inputs():
    cfg, script = load_json(CONFIG_PATH), load_json(SCRIPT_PATH)
    if not isinstance(cfg, dict) or not isinstance(script, dict):
        die("config and script must be JSON objects")
    for k in ("tts", "audio", "whisper", "alignment", "video"):
        if not isinstance(cfg.get(k), dict):
            die(f"config.{k} must be an object")
    t, a, al, v = cfg["tts"], cfg["audio"], cfg["alignment"], cfg["video"]
    if t.get("model") not in FREE_STANDARD_MODELS:
        die(f"model '{t.get('model')}' is not on the free-tier allow-list {sorted(FREE_STANDARD_MODELS)}")
    if not isinstance(t.get("voice"), str) or not t["voice"].strip():
        die("tts.voice must be a non-empty string")
    if not isinstance(t.get("style", ""), str):
        die("tts.style must be a string")
    t["_attempts"] = int(num(t.get("max_attempts", 1), "tts.max_attempts", 1, 6))
    t["_requests"] = int(num(t.get("max_requests_per_run", 1), "tts.max_requests_per_run", 1, MAX_REQUESTS_LIMIT))
    t["_spacing"] = num(t.get("request_spacing_sec", 8), "tts.request_spacing_sec", 0, 120)
    t["_timeout"] = int(num(t.get("timeout_sec", 90), "tts.timeout_sec", 5, 300))
    a["_lead"] = num(a.get("lead_in_ms"), "audio.lead_in_ms", 0, 5000) / 1000
    a["_gap"] = num(a.get("gap_ms"), "audio.gap_ms", 150, 3000) / 1000
    a["_tail"] = num(a.get("tail_ms"), "audio.tail_ms", 0, 10000) / 1000
    a["_pad"] = num(a.get("whisper_pad_ms"), "audio.whisper_pad_ms", 100, 1000) / 1000
    al["_min_word"] = num(al.get("min_word_match"), "alignment.min_word_match", 0, 1)
    al["_min_sentence"] = num(al.get("min_sentence_ratio"), "alignment.min_sentence_ratio", 0, 1)
    if al.get("on_unmatched") not in ("fail", "show_unhighlighted", "bracket"):
        die("alignment.on_unmatched must be 'fail', 'show_unhighlighted' or 'bracket'")
    wh = cfg["whisper"]
    if wh.get("model") not in ("small", "medium", "large-v3"):
        die("whisper.model must be 'small', 'medium' or 'large-v3'")
    if not isinstance(wh.get("language"), str) or not re.fullmatch(r"[a-z]{2,3}", wh["language"]):
        die("whisper.language must be a 2-3 letter code such as 'fa'")
    if wh.get("compute_type") not in ("int8", "float32"):
        die("whisper.compute_type must be 'int8' or 'float32'")
    if (v.get("width"), v.get("height"), v.get("fps")) != (1080, 1920, 30):
        die("Stage 2 template is fixed at 1080x1920 @ 30 fps")
    sents = script.get("sentences")
    if not isinstance(sents, list) or not 1 <= len(sents) <= MAX_SENTENCES:
        die(f"script.sentences must be a list of 1-{MAX_SENTENCES} items")
    seen = set()
    for s in sents:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", s["id"]):
            die("every sentence needs an id matching [A-Za-z0-9_-]+")
        if s["id"] in seen:
            die(f"duplicate sentence id {s['id']}")
        seen.add(s["id"])
        if not isinstance(s.get("text"), str) or not s["text"].strip():
            die(f"sentence {s['id']}: text must be a non-empty string")
        if s.get("speak") is not None and not isinstance(s["speak"], str):
            die(f"sentence {s['id']}: speak must be a string")
        if len(s["text"]) > MAX_TEXT_CHARS or len(s.get("speak") or "") > MAX_TEXT_CHARS:
            die(f"sentence {s['id']} is longer than {MAX_TEXT_CHARS} characters")
        if not script_tokens(s["text"]):
            die(f"sentence {s['id']} has no words")
    return cfg, script


def spoken(s):
    return s.get("speak") or s["text"]


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------
def cmd_check(_a):
    cfg, script = load_inputs()
    t = cfg["tts"]
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    need = 0
    print("Stage 2 configuration is valid.")
    print(f"  model: {t['model']} | voice: {t['voice']} | sentences: {len(script['sentences'])}")
    for s in script["sentences"]:
        h = sentence_hash(t, spoken(s))
        hit = (AUDIO_CACHE / f"{h}.wav").exists()
        need += 0 if hit else 1
        print(f"  {s['id']:>6}: {'cached ' if hit else 'API    '} {len(script_tokens(s['text'])):>2} words  {s['text'][:50]}")
    if need > t["_requests"]:
        die(f"{need} sentences need the API but tts.max_requests_per_run is {t['_requests']}. "
            "Raise it deliberately (after checking your free quota) or shorten the script.")
    print(f"API requests needed: {need} (budget {t['_requests']}, attempts per sentence {t['_attempts']})")
    print("Reminder: on the free tier Google may use the text you send to improve its products.")
    gh_output("api_needed", need)


# --------------------------------------------------------------------------
# tts
# --------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status, retryable, retry_after, short):
        super().__init__(short)
        self.status, self.retryable, self.retry_after, self.short = status, retryable, retry_after, short


def scrub(text, key):
    if not isinstance(text, str):
        return "API request failed"
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"(?i)(x-goog-api-key|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)[:400]


def audio_from_response(data):
    found = None
    inter = data.get("interaction", data) if isinstance(data, dict) else None
    if not isinstance(inter, dict):
        return None
    oa = inter.get("output_audio")
    if isinstance(oa, dict) and isinstance(oa.get("data"), str) and oa["data"]:
        found = oa["data"]
    for step in inter.get("steps", []) if isinstance(inter.get("steps"), list) else []:
        if isinstance(step, dict) and step.get("type") == "model_output":
            for c in step.get("content", []) if isinstance(step.get("content"), list) else []:
                if isinstance(c, dict) and c.get("type") == "audio" and isinstance(c.get("data"), str) and c["data"]:
                    found = c["data"]          # the documented example takes the LAST audio block
    return found


def synth_once(t, text, key):
    item = {"type": "text", "text": text}
    if t.get("style"):
        item["annotations"] = [{"type": "speech_metadata", "style": t["style"]}]
    body = {"model": t["model"], "input": [{"type": "user_input", "content": [item]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": t["voice"]}]}}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=t["_timeout"]) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(txt).get("error", {}).get("message", txt)
        except (ValueError, AttributeError):
            msg = txt
        try:
            ra = float(e.headers.get("Retry-After")) if e.headers.get("Retry-After") else None
        except ValueError:
            ra = None
        raise ApiError(e.code, e.code in (429, 500, 502, 503, 504), ra, scrub(str(msg), key))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise ApiError(0, True, None, scrub(str(e), key))
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(200, False, None, "Gemini returned invalid JSON")
    found = audio_from_response(data)
    if not found:
        raise ApiError(200, False, None, "Gemini response contained no recognized audio data")
    try:
        return ensure_wav(base64.b64decode(found))
    except ValueError:
        raise ApiError(200, False, None, "Gemini returned invalid base64 audio")


def synth_with_retry(t, text, key, budget):
    for n in range(1, t["_attempts"] + 1):
        if budget["left"] <= 0:
            die("request budget (tts.max_requests_per_run) exhausted; stopping. Already generated audio stays cached.")
        budget["left"] -= 1
        budget["used"] += 1
        try:
            print(f"  Gemini TTS attempt {n}/{t['_attempts']} (budget left after this: {budget['left']})")
            return synth_once(t, text, key)
        except ApiError as e:
            hint = " Free-tier quota/rate limit reached; no model fallback is used." if e.status == 429 else ""
            if not e.retryable or n == t["_attempts"]:
                die(f"Gemini API error (HTTP {e.status}): {e.short}.{hint}")
            wait = e.retry_after if e.retry_after is not None else min(60.0, 2 ** n + random.random())
            wait = max(1, min(wait, 60))
            print(f"  failed (HTTP {e.status}): {e.short}. Retrying in {wait:.0f}s.{hint}")
            time.sleep(wait)
    die("unreachable")


def cmd_tts(_a):
    cfg, script = load_inputs()
    t = cfg["tts"]
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    (BUILD / "audio").mkdir(parents=True, exist_ok=True)
    budget = {"left": t["_requests"], "used": 0}
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    meta, new_files, last_call = [], 0, None
    for s in script["sentences"]:
        h = sentence_hash(t, spoken(s))
        cached = AUDIO_CACHE / f"{h}.wav"
        if cached.exists():
            validate_wav(cached)
            print(f"{s['id']}: CACHE HIT ({h[:12]}) - no API request")
            hit = True
        else:
            if not key:
                die(f"{s['id']}: cache miss and GEMINI_API_KEY is empty. Add the repository secret first.")
            if last_call is not None and t["_spacing"] > 0:
                wait = t["_spacing"] - (time.time() - last_call)
                if wait > 0:
                    print(f"  waiting {wait:.0f}s between requests (free-tier rate limit)")
                    time.sleep(wait)
            print(f"{s['id']}: cache miss ({h[:12]}) - calling Gemini")
            wav = synth_with_retry(t, spoken(s), key, budget)
            last_call = time.time()
            tmp = cached.with_suffix(".tmp")
            tmp.write_bytes(wav)
            validate_wav(tmp)
            tmp.replace(cached)
            new_files += 1
            hit = False
        shutil.copyfile(cached, BUILD / "audio" / f"{s['id']}.wav")
        info = wav_info(BUILD / "audio" / f"{s['id']}.wav")
        meta.append({"id": s["id"], "hash": h, "cache_hit": hit, "duration": round(info["duration"], 3)})
    (BUILD / "tts_meta.json").write_text(json.dumps(
        {"model": t["model"], "voice": t["voice"], "requests_used": budget["used"], "sentences": meta}, indent=2),
        encoding="utf-8")
    gh_output("new_audio", new_files)
    print(f"Audio ready for {len(meta)} sentences; API requests used: {budget['used']}")


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------
def cmd_prepare(_a):
    cfg, script = load_inputs()
    a = cfg["audio"]
    lead, gap, tail, pad = a["_lead"], a["_gap"], a["_tail"], a["_pad"]
    infos = []
    for s in script["sentences"]:
        p = BUILD / "audio" / f"{s['id']}.wav"
        if not p.exists():
            die(f"missing audio for {s['id']}; run 'tts' first")
        infos.append((s, p, validate_wav(p)))
    rate = infos[0][2]["rate"]
    if any(i["rate"] != rate for _, _, i in infos):
        die("sentence audio files have different sample rates")
    sil = lambda sec: b"\x00\x00" * int(round(sec * rate))
    chunks, cursor, sents = [sil(lead)], lead, []
    (BUILD / "whisper_in").mkdir(parents=True, exist_ok=True)
    for n, (s, p, info) in enumerate(infos):
        frames = read_frames(p)
        sents.append({"id": s["id"], "offset": round(cursor, 6), "duration": info["duration"]})
        chunks.append(frames)
        cursor += info["duration"]
        if n < len(infos) - 1:
            chunks.append(sil(gap))
            cursor += gap
        padded = BUILD / f"_pad_{s['id']}.wav"
        with wave.open(str(padded), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(sil(pad) + frames + sil(pad))
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(padded), "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", str(BUILD / "whisper_in" / f"{s['id']}.wav")])
        padded.unlink()
    chunks.append(sil(tail))
    total = cursor + tail
    if total > MAX_TOTAL_SECONDS:
        die(f"total narration {total:.0f}s exceeds {MAX_TOTAL_SECONDS}s")
    with wave.open(str(BUILD / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(chunks))
    meta = {"sample_rate": rate, "lead": lead, "gap": gap, "tail": tail, "pad": pad,
            "total": round(total, 6), "sentences": sents}
    (BUILD / "audio_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    got = wav_info(BUILD / "narration.wav")["duration"]
    if abs(got - total) > 0.01:
        die("narration.wav duration does not match the computed timeline")
    print(f"narration.wav: {total:.2f}s, {len(sents)} sentences")
    for x in sents:
        print(f"  {x['id']:>6}: offset {x['offset']:.2f}s, speech {x['duration']:.2f}s")


# --------------------------------------------------------------------------
# align
# --------------------------------------------------------------------------
_SPECIAL = re.compile(r"^[\[\(<].*[\]\)>]$")


def whisper_words(path, pad, speech_dur):
    """Read one sentence's Whisper words; returns (words in SENTENCE-relative seconds, notes)."""
    data = load_json(path)
    raw = data.get("words") if isinstance(data, dict) else None
    notes = []
    if not isinstance(raw, list) or not raw:
        return [], ["Whisper returned no words for this sentence"]
    words, dropped = [], 0
    for w in raw:
        if not isinstance(w, dict) or not isinstance(w.get("text"), str):
            continue
        text = w["text"].strip()
        try:
            s, e = float(w["start"]), float(w["end"])
        except (KeyError, TypeError, ValueError):
            dropped += 1
            continue
        if not (math.isfinite(s) and math.isfinite(e)) or not text or _SPECIAL.match(text) or e <= s or s < 0:
            dropped += 1
            continue
        s, e = s - pad, e - pad
        if e <= 0 or s >= speech_dur + TOL:      # entirely inside the padding
            dropped += 1
            continue
        s, e = max(0.0, s), min(e, speech_dur)
        if e <= s:
            dropped += 1
            continue
        n = norm(text)
        if n:
            words.append({"text": text, "start": s, "end": e, "norm": n})
    words.sort(key=lambda x: (x["start"], x["end"]))
    if dropped:
        notes.append(f"{dropped} Whisper token(s) ignored (zero length, padding-only or malformed)")
    return words, notes


def align_words(toks, wwords, min_word_match):
    s_owner = [ti for ti, t in enumerate(toks) for _ in t["norm"]]
    r_owner = [(wi, k, len(w["norm"])) for wi, w in enumerate(wwords) for k in range(len(w["norm"]))]
    S = "".join(t["norm"] for t in toks)
    R = "".join(w["norm"] for w in wwords)
    sm = difflib.SequenceMatcher(None, S, R, autojunk=False)
    per = {i: [] for i in range(len(toks))}
    for a, b, size in sm.get_matching_blocks():
        for d in range(size):
            ti = s_owner[a + d]
            wi, k, L = r_owner[b + d]
            w = wwords[wi]
            span = w["end"] - w["start"]
            per[ti].append((w["start"] + span * k / L, w["start"] + span * (k + 1) / L, wi))
    users = {}
    for ti, lst in per.items():
        for _, _, wi in lst:
            users.setdefault(wi, set()).add(ti)
    rows = []
    for ti, t in enumerate(toks):
        n, lst = len(t["norm"]), per[ti]
        row = {"i": ti, "text": t["text"], "start": None, "end": None, "recognized": [],
               "matched_frac": None, "status": "skipped", "notes": []}
        if n == 0:
            row["notes"].append("punctuation only")
        else:
            frac = len(lst) / n
            wis = sorted({wi for _, _, wi in lst})
            row["matched_frac"] = round(frac, 3)
            row["recognized"] = [wwords[wi]["text"] for wi in wis]
            if frac < min_word_match:
                row["status"] = "unmatched"
                row["notes"].append("recognized text differs; NO timestamp assigned")
            else:
                row["start"], row["end"] = min(x[0] for x in lst), max(x[1] for x in lst)
                shared = any(len(users[wi]) > 1 for wi in wis)
                exact = len(wis) == 1 and not shared and wwords[wis[0]]["norm"] == t["norm"]
                row["status"] = "exact" if exact else "aligned"
                if frac < 1:
                    row["notes"].append("recognized text differs")
                if shared:
                    row["notes"].append("boundary ESTIMATED inside one recognized word")
                if len(wis) > 1:
                    row["notes"].append("spans several recognized words")
        rows.append(row)
    prev = None
    for r in rows:
        if r["start"] is None:
            continue
        if r["end"] - r["start"] < 0.02:
            r["end"] = r["start"] + 0.02
            r["notes"].append("very short; end padded to 20 ms")
        if prev is not None and r["start"] < prev - 0.05:
            r["notes"].append("overlaps previous word")
        prev = r["end"]
    return rows, sm.ratio()


def snap_edges(rows, onset, send):
    """A word cannot begin before speech begins or end after speech ends.
    Whisper often stretches the first/last word outward; clip it to the MEASURED speech edge."""
    timed = [r for r in rows if r["start"] is not None]
    if not timed or onset is None or send is None:
        return
    f, l = timed[0], timed[-1]
    if f["start"] < onset - EDGE_SNAP_MS:
        d = round((onset - f["start"]) * 1000)
        f["start"] = max(0.0, onset - 0.03)
        f["end"] = max(f["end"], f["start"] + 0.02)
        f["notes"].append(f"start moved to the measured speech onset (Whisper was {d} ms early)")
    if l["end"] > send + EDGE_SNAP_MS:
        d = round((l["end"] - send) * 1000)
        l["end"] = send + 0.03
        l["start"] = min(l["start"], l["end"] - 0.02)
        l["notes"].append(f"end moved to the measured speech end (Whisper was {d} ms late)")


def bracket_unmatched(rows, onset, send, speech_dur):
    """Opt-in (on_unmatched = bracket): a short run of words Whisper did not recognise gets the time
    window between its two timed neighbours (or the measured speech edge). Always flagged."""
    n, i = len(rows), 0
    while i < n:
        if rows[i]["status"] != "unmatched":
            i += 1
            continue
        j = i
        while j < n and rows[j]["status"] in ("unmatched", "skipped"):
            j += 1
        run_ = [r for r in rows[i:j] if r["status"] == "unmatched"]
        left = next((rows[k]["end"] for k in range(i - 1, -1, -1) if rows[k]["end"] is not None),
                    onset if onset is not None else 0.0)
        right = next((rows[k]["start"] for k in range(j, n) if rows[k]["start"] is not None),
                     send if send is not None else speech_dur)
        gap = right - left
        if len(run_) <= BRACKET_MAX_RUN and BRACKET_MIN_PER_WORD * len(run_) <= gap <= BRACKET_MAX_GAP:
            weights = [max(1, len(norm(r["text"]))) for r in run_]
            cur = left
            for r, w in zip(run_, weights):
                d = gap * w / sum(weights)
                r["start"], r["end"], cur = cur, cur + d, cur + d
                r["status"] = "bracketed"
                r["notes"] = [f"not recognized by Whisper; time BRACKETED between neighbours (gap {gap * 1000:.0f} ms)"]
        i = j


def cmd_align(_a):
    cfg, script = load_inputs()
    meta = load_json(BUILD / "audio_meta.json")
    al, pad = cfg["alignment"], meta["pad"]
    by_id = {x["id"]: x for x in meta["sentences"]}
    out_sents, overall = [], "OK"
    lines = []
    for s in script["sentences"]:
        m = by_id[s["id"]]
        offset, dur = m["offset"], m["duration"]
        toks = script_tokens(s["text"])
        wpath = BUILD / "whisper" / f"{s['id']}.json"
        if not wpath.exists():
            die(f"missing Whisper output for {s['id']}: {wpath}")
        words, notes = whisper_words(wpath, pad, dur)
        if not words:
            rows = [{"i": t["i"], "text": t["text"], "start": None, "end": None, "recognized": [],
                     "matched_frac": 0, "status": "unmatched" if t["norm"] else "skipped",
                     "notes": ["no recognized words"]} for t in toks]
            ratio = 0.0
        else:
            rows, ratio = align_words(toks, words, al["_min_word"])
        onset, send, rms, win = speech_bounds(BUILD / "audio" / f"{s['id']}.wav")
        snap_edges(rows, onset, send)
        if al["on_unmatched"] == "bracket":
            bracket_unmatched(rows, onset, send, dur)
        for r in rows:
            r["abs_start"] = None if r["start"] is None else round(r["start"] + offset, 3)
            r["abs_end"] = None if r["end"] is None else round(r["end"] + offset, 3)
            r["start"] = None if r["start"] is None else round(r["start"], 3)
            r["end"] = None if r["end"] is None else round(r["end"], 3)
        timed = [r for r in rows if r["start"] is not None]
        means = []
        for r in timed:
            a0 = max(0, int(r["start"] / win))
            seg = rms[a0:max(a0 + 1, int(math.ceil(r["end"] / win)))] or [0]
            means.append(sum(seg) / len(seg))
            r["_e"] = means[-1]
        med = statistics.median(means) if means else 0
        for r in timed:
            e = r.pop("_e")
            r["energy_rel"] = round(e / med, 2) if med > 0 else None
            if r["energy_rel"] is not None and r["energy_rel"] < 0.25:
                r["notes"].append("low audio energy in this window; check manually")
        counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("exact", "aligned", "bracketed", "unmatched", "skipped")}
        status, reasons = "OK", list(notes)
        if counts["aligned"]:
            status = "WARN"
            reasons.append(f"{counts['aligned']} word(s) aligned with differences or estimates")
        if counts["bracketed"]:
            status = "WARN" if status == "OK" else status
            reasons.append(f"{counts['bracketed']} word(s) not recognized by Whisper; time bracketed between neighbours")
        if counts["unmatched"]:
            reasons.append(f"{counts['unmatched']} word(s) could not be matched")
            status = "FAIL" if al["on_unmatched"] in ("fail", "bracket") else "WARN"
        if ratio < al["_min_sentence"]:
            status = "FAIL"
            reasons.append(f"match ratio {ratio:.2f} < {al['_min_sentence']}")
        summ = {"status": status, "reasons": reasons, "match_ratio": round(ratio, 3), "counts": counts}
        if onset is not None and timed:
            d0 = round((timed[0]["start"] - onset) * 1000)
            d1 = round((timed[-1]["end"] - send) * 1000)
            summ["first_word_vs_speech_onset_ms"], summ["last_word_vs_speech_end_ms"] = d0, d1
            reasons.append(f"first word vs measured speech onset: {d0} ms; last word vs speech end: {d1} ms")
            if abs(d0) > 300 or abs(d1) > 300:
                if status == "OK":
                    summ["status"] = status = "WARN"
                reasons.append("first/last word is still >300 ms away from the measured speech edge")
        if status == "FAIL":
            overall = "FAIL"
        elif status == "WARN" and overall == "OK":
            overall = "WARN"
        out_sents.append({"id": s["id"], "text": s["text"], "offset": offset, "duration": dur,
                          "words": rows, "summary": summ})
        lines += [f"### {s['id']} - {status} (match {ratio:.2f})", ""]
        lines += [f"- {x}" for x in reasons] + [""]
        lines += ["| # | script word | recognized | start s | end s | status | note |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['i']} | {r['text']} | {' + '.join(r['recognized'])} | "
                         f"{r['abs_start'] if r['abs_start'] is not None else '-'} | "
                         f"{r['abs_end'] if r['abs_end'] is not None else '-'} | {r['status']} | {'; '.join(r['notes'])} |")
        lines.append("")
    timing = {"stage": 2, "timestamp_reference": "narration.wav", "audio": meta,
              "sentences": out_sents, "summary": {"status": overall,
              "per_sentence": {x["id"]: x["summary"]["status"] for x in out_sents}}}
    (BUILD / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    report = "\n".join([f"## Stage 2 timing report - {overall}", ""] +
                       [f"- {x['id']}: {x['summary']['status']}" for x in out_sents] + [""] + lines) + "\n"
    (BUILD / "timing_report.md").write_text(report, encoding="utf-8")
    print(report)
    if overall == "FAIL":
        sys.exit(3)


# --------------------------------------------------------------------------
# compose
# --------------------------------------------------------------------------
def srt_time(t):
    ms = int(round(max(0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_compose(_a):
    cfg, script = load_inputs()
    timing = load_json(BUILD / "timing.json")
    if timing["summary"]["status"] == "FAIL":
        die("timing status is FAIL; refusing to build a video from unreliable timestamps.", 3)
    meta = timing["audio"]
    total, gap = float(meta["total"]), float(meta["gap"])
    story = BUILD / "story"
    (story / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    fonts = list((ROOT / "assets" / "fonts").glob("*.woff2"))
    if not fonts:
        die("assets/fonts/*.woff2 not found; the font installation step must run first")
    for f in fonts:
        shutil.copyfile(f, story / "assets" / "fonts" / f.name)
    shutil.copyfile(BUILD / "narration.wav", story / "narration.wav")
    fade = round(min(0.18, gap / 3), 3)
    html_parts, tl_sents, srt = [], [], []
    for n, s in enumerate(timing["sentences"]):
        spans, words = [], []
        timed = [r for r in s["words"] if r["abs_start"] is not None]
        if not timed:
            die(f"sentence {s['id']} has no timed words", 3)
        for r in s["words"]:
            wid = f"w-{s['id']}-{r['i']}"
            spans.append(f'<span class="w" id="{wid}">{html.escape(r["text"])}</span>')
            if r["abs_start"] is not None:
                words.append({"id": wid, "start": r["abs_start"], "end": r["abs_end"], "hl": True})
            elif r["status"] == "unmatched":
                # shown, never dropped; released (not highlighted) when the next timed word begins
                nxt = next((x["abs_start"] for x in s["words"][r["i"] + 1:] if x["abs_start"] is not None),
                           s["offset"] + s["duration"])
                words.append({"id": wid, "start": round(nxt, 3), "end": round(nxt + 0.06, 3), "hl": False})
        html_parts.append(f'<div class="sentence" id="sent-{s["id"]}">{" ".join(spans)}</div>')
        tl_sents.append({"id": s["id"], "start": s["offset"], "end": round(s["offset"] + s["duration"], 3),
                         "words": words})
        nxt_off = timing["sentences"][n + 1]["offset"] if n + 1 < len(timing["sentences"]) else total
        c0 = max(s["offset"], timed[0]["abs_start"] - 0.05)
        c1 = min(timed[-1]["abs_end"] + 0.15, nxt_off - 0.02)
        srt.append(f"{n + 1}\n{srt_time(c0)} --> {srt_time(max(c1, c0 + 0.2))}\n{s['text']}\n")
    data = {"duration": round(total, 3), "fade": fade, "sentences": tl_sents}
    data_js = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    title = script.get("meta", {}).get("title", "") if isinstance(script.get("meta"), dict) else ""
    tpl = (STORY / "template.stage2.html").read_text(encoding="utf-8")
    for ph in ("__DURATION__", "__TITLE_HTML__", "__SENTENCES_HTML__", "__TIMELINE_JSON__"):
        if ph not in tpl:
            die(f"template.stage2.html is missing placeholder {ph}")
    page = (tpl.replace("__DURATION__", f"{total:.3f}").replace("__TITLE_HTML__", html.escape(str(title)))
               .replace("__SENTENCES_HTML__", "\n    ".join(html_parts)).replace("__TIMELINE_JSON__", data_js))
    (story / "index.html").write_text(page, encoding="utf-8")
    (BUILD / "story.srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"Composition written ({total:.2f}s, {len(tl_sents)} sentences, fade {fade}s).")


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------
SEA = (79, 209, 197)
ROI = "crop=1080:800:0:560"        # caption area


def roi_frame(mp4, t, w, h):
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", str(mp4), "-frames:v", "1",
               "-vf", f"{ROI},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return raw


def sea_pixels(mp4, t, w=270, h=200):
    raw = roi_frame(mp4, t, w, h)
    n = sx = sy = 0
    for p in range(0, min(len(raw), w * h * 3) - 2, 3):
        if abs(raw[p] - SEA[0]) < 26 and abs(raw[p + 1] - SEA[1]) < 26 and abs(raw[p + 2] - SEA[2]) < 26:
            q = p // 3
            n, sx, sy = n + 1, sx + q % w, sy + q // w
    return n, (round(sx / n / w, 3) if n else None), (round(sy / n / h, 3) if n else None)


def text_presence(mp4, fps=4, w=135, h=100):
    raw = run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},{ROI},scale={w}:{h}",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    fs, out = w * h * 3, []
    for f in range(len(raw) // fs):
        b = raw[f * fs:(f + 1) * fs]
        out.append(sum(1 for p in range(0, fs, 3) if (b[p] + b[p + 1] + b[p + 2]) > 225) >= 15)
    return out, fps


def cmd_verify(_a):
    BUILD.mkdir(parents=True, exist_ok=True)
    res = {"problems": [], "verification_complete": False}

    def save():
        (BUILD / "verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        timing = load_json(BUILD / "timing.json")
        mp4 = BUILD / "story.mp4"
        if not mp4.exists() or mp4.stat().st_size == 0:
            die("story.mp4 is missing or empty", 4)
        probe = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                "-show_format", str(mp4)]))
        vs = [x for x in probe["streams"] if x.get("codec_type") == "video"]
        au = [x for x in probe["streams"] if x.get("codec_type") == "audio"]
        dur, exp = float(probe["format"]["duration"]), float(timing["audio"]["total"])
        res.update({"size_bytes": mp4.stat().st_size, "duration": round(dur, 3), "expected_duration": round(exp, 3)})
        if not vs:
            res["problems"].append("no video stream")
        else:
            v = vs[0]
            res["video"] = {"codec": v.get("codec_name"), "w": v.get("width"), "h": v.get("height"),
                            "fps": v.get("avg_frame_rate")}
            if (v.get("width"), v.get("height")) != (1080, 1920):
                res["problems"].append("wrong dimensions; expected 1080x1920")
            try:
                a_, b_ = map(int, v["avg_frame_rate"].split("/"))
                if abs(a_ / b_ - 30) > 0.1:
                    res["problems"].append(f"wrong frame rate {a_ / b_:.2f}")
            except (KeyError, ValueError, ZeroDivisionError):
                res["problems"].append("could not parse frame rate")
        if not au:
            res["problems"].append("NO AUDIO STREAM in the MP4")
        if abs(dur - exp) > 0.3:
            res["problems"].append(f"duration {dur:.2f}s differs from narration {exp:.2f}s")
        sents = timing["sentences"]
        timed_all = [r for s in sents for r in s["words"] if r["abs_start"] is not None]
        if au and timed_all:
            run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "24000",
                 "-c:a", "pcm_s16le", str(BUILD / "mp4_audio.wav")])
            onset, _, _, _ = speech_bounds(BUILD / "mp4_audio.wav")
            if onset is not None:
                res["mp4_audio_onset_vs_first_word_ms"] = round((timed_all[0]["abs_start"] - onset) * 1000)
        if vs:
            frames = BUILD / "frames"
            frames.mkdir(exist_ok=True)
            hl = []
            for s in sents:
                timed = [r for r in s["words"] if r["abs_start"] is not None]
                for r in timed:
                    mid = (r["abs_start"] + r["abs_end"]) / 2
                    n, cx, cy = sea_pixels(mp4, mid)
                    hl.append({"sentence": s["id"], "i": r["i"], "text": r["text"], "t": round(mid, 3),
                               "highlight_pixels": n, "x": cx, "y": cy})
                    if n < 150:
                        res["problems"].append(f"no highlight for {s['id']} word {r['i']} at {mid:.2f}s")
                t0 = timed[0]["abs_start"]
                before, _, _ = sea_pixels(mp4, t0 - 0.10)
                after, _, _ = sea_pixels(mp4, t0 + 0.10)
                hl.append({"sentence": s["id"], "first_word_onset_check": [before, after]})
                if before >= 150 or after < 150:
                    res["problems"].append(f"{s['id']}: first-word highlight not switching on within +/-100 ms")
                mid_s = s["offset"] + s["duration"] / 2
                run(["ffmpeg", "-y", "-v", "error", "-ss", f"{mid_s:.3f}", "-i", str(mp4), "-frames:v", "1",
                     "-vf", "scale=540:-1", str(frames / f"sentence_{s['id']}.png")])
            res["highlight"] = hl
            pres, fps = text_presence(mp4)
            blank, run_start = [], None
            for i, ok in enumerate(pres + [True]):
                t = i / fps
                should = any(s["offset"] - 0.05 <= t <= s["offset"] + s["duration"] + 0.05 for s in sents)
                bad = should and not ok
                if bad and run_start is None:
                    run_start = t
                if not bad and run_start is not None:
                    if t - run_start > 0.5:
                        blank.append([round(run_start, 2), round(t, 2)])
                    run_start = None
            res["blank_caption_spans"] = blank
            for a_, b_ in blank:
                res["problems"].append(f"caption missing while narration plays ({a_}s-{b_}s)")
        res["verification_complete"] = True
    except SystemExit as e:
        res["problems"].append(f"verification stopped with exit code {e.code}")
        save()
        raise
    except Exception as e:
        res["problems"].append(f"verification exception: {type(e).__name__}: {e}")
        save()
        die("verification could not be completed; see verify.json", 4)
    save()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res["problems"]:
        die("verification problems: " + "; ".join(res["problems"]), 4)
    print("VERIFY OK")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("check", cmd_check), ("tts", cmd_tts), ("prepare", cmd_prepare),
                     ("align", cmd_align), ("compose", cmd_compose), ("verify", cmd_verify)):
        sub.add_parser(name).set_defaults(fn=fn)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
