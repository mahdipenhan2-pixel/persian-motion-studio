#!/usr/bin/env python3
"""
NFP Story Studio - Stage 0 spike: ONE short Persian sentence.

Commands (run in this order by .github/workflows/story-stage0.yml):
  check     offline validation + free-tier guard rails (no network)
  tts       Gemini TTS -> cached WAV (GEMINI_API_KEY is needed only on a cache miss)
  prepare   build narration.wav + a 16 kHz copy for Whisper
  align     map Whisper word times onto the ORIGINAL script words (strict)
  compose   write the HyperFrames composition + SRT
  verify    inspect the rendered MP4 (audio, duration, highlight frames)

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
BUILD = ROOT / "build" / "stage0"
CACHE = ROOT / ".cache" / "story" / "audio"

SCRIPT_PATH = STORY / "script.stage0.json"
CONFIG_PATH = STORY / "config.json"

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

# Models allowed by the Stage 0 free-tier guard.
# Pricing and availability can change; this list is not a guarantee
# of unlimited free usage.
FREE_STANDARD_MODELS = {
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
}

MAX_TEXT_CHARS = 300


# --------------------------------------------------------------------------
# General helpers
# --------------------------------------------------------------------------

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_inputs():
    if not CONFIG_PATH.exists():
        die(f"configuration file not found: {CONFIG_PATH}")

    if not SCRIPT_PATH.exists():
        die(f"script file not found: {SCRIPT_PATH}")

    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        script = json.loads(SCRIPT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"invalid JSON input: {e}")

    return cfg, script


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError:
        die(f"required command not found: {cmd[0]}")

    if r.returncode != 0:
        die(
            f"command failed: {' '.join(map(str, cmd))}\n"
            f"{r.stderr.decode('utf-8', 'replace')[-800:]}"
        )

    return r.stdout


# --------------------------------------------------------------------------
# Persian text handling
# --------------------------------------------------------------------------

_DIACRITICS = re.compile(
    "[\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]"
)

_CHAR_MAP = {
    ord(a): b for a, b in {
        "ي": "ی",
        "ى": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "أ": "ا",
        "إ": "ا",
        "ٱ": "ا",
        "آ": "ا",
        "ؤ": "و",
        "ئ": "ی",
    }.items()
}

_CHAR_MAP.update({
    0x06F0 + i: ord(str(i)) for i in range(10)
})

_CHAR_MAP.update({
    0x0660 + i: ord(str(i)) for i in range(10)
})


def norm(text):
    """
    Letters/digits only, unified Persian letter forms.
    Used ONLY for matching.
    """

    t = unicodedata.normalize("NFKC", text)

    for ch in ("\u200c", "\u200d", "\u200e", "\u200f", "\u0640"):
        t = t.replace(ch, "")

    t = _DIACRITICS.sub("", t).translate(_CHAR_MAP).lower()

    return "".join(
        c for c in t
        if unicodedata.category(c)[0] in ("L", "N")
    )


def script_tokens(text):
    """
    Display tokens = whitespace-separated words of the ORIGINAL script text.
    The zero-width non-joiner (U+200C) stays inside words.
    """

    return [
        {
            "i": i,
            "text": w,
            "norm": norm(w)
        }
        for i, w in enumerate(text.split())
    ]


# --------------------------------------------------------------------------
# WAV helpers
# --------------------------------------------------------------------------

def ensure_wav(data):
    """
    Gemini 3.8 unary TTS normally returns WAV.
    Older TTS output may be headerless 24 kHz mono s16le PCM.
    """

    if data[:4] == b"RIFF":
        return data

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
            info = {
                "channels": w.getnchannels(),
                "width": w.getsampwidth(),
                "rate": w.getframerate(),
                "frames": w.getnframes(),
            }

    except (wave.Error, EOFError) as e:
        die(f"{path} is not a readable WAV file: {e}")

    if info["rate"] <= 0:
        die(f"invalid WAV sample rate in {path}")

    info["duration"] = info["frames"] / info["rate"]

    return info


def validate_wav(path):
    info = wav_info(path)

    if info["channels"] != 1 or info["width"] != 2:
        die(
            f"unexpected audio format {info} "
            "(expected mono 16-bit)"
        )

    if info["duration"] < 0.3:
        die(
            f"audio is suspiciously short "
            f"({info['duration']:.2f}s)"
        )

    return info


def load_samples(path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())

    a = array.array("h")
    a.frombytes(raw)

    if sys.byteorder == "big":
        a.byteswap()

    return sr, a


def window_rms(samples, sr, win=0.01):
    n = max(1, int(sr * win))
    out = []

    for i in range(0, len(samples), n):
        chunk = samples[i:i + n]

        out.append(
            math.sqrt(
                sum(x * x for x in chunk) / max(1, len(chunk))
            )
        )

    return out, win


def speech_bounds(path):
    sr, a = load_samples(path)

    r, win = window_rms(a, sr)

    peak = max(r) if r else 0

    if peak <= 0:
        return None, None, r, win

    thr = 0.08 * peak

    idx = [
        i for i, v in enumerate(r)
        if v > thr
    ]

    return (
        idx[0] * win,
        (idx[-1] + 1) * win,
        r,
        win
    )


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

def validate_basic(cfg, script):
    try:
        model = cfg["tts"]["model"]
    except (KeyError, TypeError):
        die("config.json is missing tts.model")

    if model not in FREE_STANDARD_MODELS:
        die(
            f"model '{model}' is not on the free-tier allow-list "
            f"{sorted(FREE_STANDARD_MODELS)}"
        )

    sents = script.get("sentences", [])

    if len(sents) != 1:
        die(
            f"Stage 0 allows exactly ONE sentence "
            f"(found {len(sents)})."
        )

    s = sents[0]

    if not re.fullmatch(r"[A-Za-z0-9_-]+", s.get("id", "")):
        die("sentence id must match [A-Za-z0-9_-]+")

    if not s.get("text", "").strip():
        die("sentence text is empty")

    if len(s.get("speak") or s["text"]) > MAX_TEXT_CHARS:
        die(
            f"sentence longer than {MAX_TEXT_CHARS} characters "
            "(Stage 0 guard)"
        )

    if not script_tokens(s["text"]):
        die("sentence has no words")

    return s


def cmd_check(_a):
    cfg, script = load_inputs()

    s = validate_basic(cfg, script)
    t = cfg["tts"]

    toks = script_tokens(s["text"])

    print("Stage 0 configuration is valid.")

    print(
        f"  model            : {t['model']} "
        "(check current official pricing before use)"
    )

    print(
        f"  voice / style    : "
        f"{t['voice']} / {t.get('style') or '(none)'}"
    )

    print(f"  sentence         : {s['text']}")
    print(f"  words            : {len(toks)}")

    attempts = min(
        int(t.get("max_attempts", 1)),
        int(t.get("max_requests_per_run", 1))
    )

    print(f"  max API attempts : {attempts}")

    print(
        f"  GEMINI_API_KEY   : "
        f"{'set' if os.environ.get('GEMINI_API_KEY') else 'not set in this step (fine)'}"
    )

    print(
        "Reminder: on the free tier Google may use "
        "the text you send to improve its products."
    )


# --------------------------------------------------------------------------
# tts (Gemini API, Interactions endpoint)
# --------------------------------------------------------------------------

class ApiError(Exception):

    def __init__(self, status, retryable, retry_after, short):
        super().__init__(short)

        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after
        self.short = short


def sentence_hash(t, text):
    payload = {
        "v": 1,
        "api": "interactions-default-wav",
        "model": t["model"],
        "voice": t["voice"],
        "style": t.get("style", ""),
        "text": text,
    }

    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def extract_audio_data(data):
    """
    Supports the current Interactions response:
        interaction.output_audio.data

    Also accepts a top-level output_audio object and
    the older steps/model_output response structure.
    """

    interaction = data.get("interaction", data)

    output_audio = interaction.get("output_audio")

    if isinstance(output_audio, dict):
        audio_data = output_audio.get("data")

        if audio_data:
            return audio_data

    for step in interaction.get("steps", []):
        if step.get("type") != "model_output":
            continue

        for content in step.get("content", []):
            if (
                content.get("type") == "audio"
                and content.get("data")
            ):
                return content["data"]

    return None


def synth_once(t, text, key):
    item = {
        "type": "text",
        "text": text,
    }

    if t.get("style"):
        item["annotations"] = [
            {
                "type": "speech_metadata",
                "style": t["style"],
            }
        ]

    body = {
        "model": t["model"],
        "input": [
            {
                "type": "user_input",
                "content": [item],
            }
        ],
        "response_format": {
            "type": "audio",
        },
        "generation_config": {
            "speech_config": [
                {
                    "voice": t["voice"],
                }
            ]
        },
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
    )

    try:
        with urllib.request.urlopen(
            req,
            timeout=t["timeout_sec"]
        ) as r:
            raw = r.read()

    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "replace")

        try:
            msg = json.loads(txt).get(
                "error", {}
            ).get("message", txt)

        except ValueError:
            msg = txt

        ra = e.headers.get("Retry-After")

        try:
            ra = float(ra) if ra else None

        except ValueError:
            ra = None

        raise ApiError(
            e.code,
            e.code in (429, 500, 502, 503, 504),
            ra,
            str(msg)[:400],
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError
    ) as e:

        raise ApiError(
            0,
            True,
            None,
            str(e)[:200],
        )

    try:
        data = json.loads(raw)

    except (ValueError, UnicodeDecodeError):
        raise ApiError(
            200,
            False,
            None,
            "Gemini returned an invalid JSON response",
        )

    found = extract_audio_data(data)

    if not found:
        raise ApiError(
            200,
            False,
            None,
            (
                "no audio data found in Gemini response "
                f"(top-level keys: {sorted(data)})"
            ),
        )

    try:
        decoded = base64.b64decode(found, validate=True)

    except (ValueError, TypeError):
        raise ApiError(
            200,
            False,
            None,
            "Gemini returned invalid base64 audio data",
        )

    return ensure_wav(decoded)


def synth_with_retry(t, text, key):
    attempts = min(
        int(t["max_attempts"]),
        int(t["max_requests_per_run"])
    )

    if attempts < 1:
        die("max_attempts and max_requests_per_run must be at least 1")

    for n in range(1, attempts + 1):

        try:
            print(
                f"Gemini TTS request {n}/{attempts} "
                f"(model {t['model']}) ..."
            )

            return synth_once(t, text, key), n

        except ApiError as e:
            hint = ""

            if e.status == 429:
                hint = (
                    " Free-tier quota/rate limit reached. "
                    "The script will NOT switch to another model."
                )

            if not e.retryable or n == attempts:
                die(
                    f"Gemini API error (HTTP {e.status}): "
                    f"{e.short}.{hint}"
                )

            wait = (
                e.retry_after
                or min(60.0, 2 ** n + random.random())
            )

            print(
                f"  failed (HTTP {e.status}): {e.short}. "
                f"Retrying in {wait:.0f}s.{hint}"
            )

            time.sleep(wait)

    die("unreachable")


def cmd_tts(_a):
    cfg, script = load_inputs()

    s = validate_basic(cfg, script)
    t = cfg["tts"]

    text = s.get("speak") or s["text"]

    h = sentence_hash(t, text)

    CACHE.mkdir(parents=True, exist_ok=True)

    cached = CACHE / f"{h}.wav"

    out = BUILD / "audio" / f"{s['id']}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    requests_made = 0

    if cached.exists():

        print(
            f"CACHE HIT ({h[:12]}) - no API request was made."
        )

        validate_wav(cached)

    else:

        key = os.environ.get(
            "GEMINI_API_KEY",
            ""
        ).strip()

        if not key:
            die(
                "cache miss and GEMINI_API_KEY is empty. "
                "Add it as a repository secret named GEMINI_API_KEY."
            )

        wav_data, requests_made = synth_with_retry(
            t,
            text,
            key
        )

        tmp = cached.with_suffix(".tmp")

        tmp.write_bytes(wav_data)

        validate_wav(tmp)

        tmp.replace(cached)

    shutil.copyfile(cached, out)

    info = wav_info(out)

    (BUILD / "tts_meta.json").write_text(
        json.dumps(
            {
                "hash": h,
                "cache_hit": requests_made == 0,
                "requests_made": requests_made,
                "model": t["model"],
                "voice": t["voice"],
                "audio": info,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Audio ready: {info['duration']:.2f}s, "
        f"{info['rate']} Hz, "
        f"requests made: {requests_made}"
    )


# --------------------------------------------------------------------------
# prepare
# --------------------------------------------------------------------------

def cmd_prepare(_a):
    cfg, script = load_inputs()

    s = validate_basic(cfg, script)

    BUILD.mkdir(parents=True, exist_ok=True)

    src = BUILD / "audio" / f"{s['id']}.wav"

    info = validate_wav(src)

    lead = cfg["audio"]["lead_in_ms"] / 1000
    tail = cfg["audio"]["tail_ms"] / 1000

    with wave.open(str(src), "rb") as w:
        frames = w.readframes(w.getnframes())

    sr = info["rate"]

    def silence(sec):
        return b"\x00\x00" * int(round(sec * sr))

    with wave.open(
        str(BUILD / "narration.wav"),
        "wb"
    ) as o:

        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(sr)

        o.writeframes(
            silence(lead) + frames + silence(tail)
        )

    total = lead + info["duration"] + tail

    meta = {
        "sample_rate": sr,
        "lead": lead,
        "tail": tail,
        "total": total,
        "sentences": [
            {
                "id": s["id"],
                "offset": lead,
                "duration": info["duration"],
            }
        ],
    }

    (BUILD / "audio_meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )

    run([
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(BUILD / "whisper_input.wav"),
    ])

    print(
        f"narration.wav: {total:.2f}s total "
        f"(lead-in {lead:.2f}s, "
        f"speech {info['duration']:.2f}s, "
        f"tail {tail:.2f}s)"
    )


# --------------------------------------------------------------------------
# align
# --------------------------------------------------------------------------

_SPECIAL = re.compile(r"^[\[\(<].*[\]\)>]$")


def _num(v):
    try:
        return float(v)

    except (TypeError, ValueError):
        return None


def _word_from(d):
    text = d.get(
        "text",
        d.get("word", d.get("token"))
    )

    if not isinstance(text, str):
        return None

    s = _num(d.get("start"))
    e = _num(d.get("end"))
    ms = False

    if s is None or e is None:

        off = d.get("offsets")

        if isinstance(off, dict):
            s = _num(off.get("from"))
            e = _num(off.get("to"))
            ms = True

    if s is None or e is None:
        return None

    if ms:
        s = s / 1000
        e = e / 1000

    return {
        "text": text.strip(),
        "start": s,
        "end": e,
        "explicit_ms": ms,
    }


def _collect(node, out):
    if isinstance(node, dict):

        if isinstance(node.get("words"), list):

            for w in node["words"]:

                if isinstance(w, dict):

                    ww = _word_from(w)

                    if ww:
                        out.append(ww)

            return

        for k in (
            "segments",
            "transcription",
            "results",
            "transcript"
        ):

            if k in node:
                _collect(node[k], out)

    elif isinstance(node, list):

        for it in node:

            if isinstance(it, dict) and "words" not in it:

                ww = _word_from(it)

                if ww:
                    out.append(ww)

            else:
                _collect(it, out)


def load_whisper_words(path, audio_duration):
    data = json.loads(
        Path(path).read_text(encoding="utf-8")
    )

    raw = []

    _collect(data, raw)

    if not raw:

        keys = (
            sorted(data)
            if isinstance(data, dict)
            else type(data).__name__
        )

        die(
            f"no word timings found in {path} "
            f"(top-level: {keys}). "
            "Upload transcript.json for inspection."
        )

    raw = [
        w for w in raw
        if w["text"] and not _SPECIAL.match(w["text"])
    ]

    if any(
        len(w["text"].split()) > 1
        for w in raw
    ):
        die(
            "transcript has segment-level timing only "
            "(no per-word timestamps)."
        )

    if not any(w["explicit_ms"] for w in raw):

        if max(w["end"] for w in raw) > audio_duration * 1.5 + 1:

            for w in raw:
                w["start"] = w["start"] / 1000
                w["end"] = w["end"] / 1000

    raw.sort(key=lambda w: w["start"])

    words = []

    for w in raw:

        w["norm"] = norm(w["text"])

        if w["norm"]:
            words.append(w)

    if not words:
        die("transcript contains no usable words")

    return words


def align_words(toks, wwords, min_word_match):
    s_owner = [
        ti
        for ti, t in enumerate(toks)
        for _ in t["norm"]
    ]

    r_owner = [
        (wi, k, len(w["norm"]))
        for wi, w in enumerate(wwords)
        for k in range(len(w["norm"]))
    ]

    S = "".join(t["norm"] for t in toks)
    R = "".join(w["norm"] for w in wwords)

    sm = difflib.SequenceMatcher(
        None,
        S,
        R,
        autojunk=False
    )

    per = {
        ti: []
        for ti in range(len(toks))
    }

    for a, b, size in sm.get_matching_blocks():

        for d in range(size):

            ti = s_owner[a + d]

            wi, k, L = r_owner[b + d]

            w = wwords[wi]

            span = w["end"] - w["start"]

            per[ti].append(
                (
                    w["start"] + span * k / L,
                    w["start"] + span * (k + 1) / L,
                    wi,
                )
            )

    users = {}

    for ti, lst in per.items():

        for _, _, wi in lst:

            users.setdefault(
                wi,
                set()
            ).add(ti)

    rows = []

    for ti, t in enumerate(toks):

        n = len(t["norm"])
        lst = per[ti]

        row = {
            "i": ti,
            "text": t["text"],
            "start": None,
            "end": None,
            "recognized": [],
            "matched_frac": None,
            "status": "skipped",
            "notes": [],
        }

        if n == 0:

            row["notes"].append(
                "punctuation only"
            )

        else:

            frac = len(lst) / n

            wis = sorted({
                wi for _, _, wi in lst
            })

            row["matched_frac"] = round(frac, 3)

            row["recognized"] = [
                wwords[wi]["text"]
                for wi in wis
            ]

            if frac < min_word_match:

                row["status"] = "unmatched"

                row["notes"].append(
                    "recognized text too different - "
                    "NO timestamp assigned"
                )

            else:

                row["start"] = min(
                    x[0] for x in lst
                )

                row["end"] = max(
                    x[1] for x in lst
                )

                shared = any(
                    len(users[wi]) > 1
                    for wi in wis
                )

                exact = (
                    len(wis) == 1
                    and not shared
                    and wwords[wis[0]]["norm"] == t["norm"]
                )

                row["status"] = (
                    "exact" if exact else "aligned"
                )

                if frac < 1:
                    row["notes"].append(
                        "recognized text differs"
                    )

                if shared:
                    row["notes"].append(
                        "boundary ESTIMATED inside one recognized word"
                    )

                if len(wis) > 1:
                    row["notes"].append(
                        "spans several recognized words"
                    )

        rows.append(row)

    prev_end = None

    for r in rows:

        if r["start"] is None:
            continue

        if r["end"] - r["start"] < 0.02:

            r["end"] = r["start"] + 0.02

            r["notes"].append(
                "very short word, end padded to 20 ms"
            )

        if (
            prev_end is not None
            and r["start"] < prev_end - 0.05
        ):

            r["notes"].append(
                "overlaps previous word"
            )

        prev_end = r["end"]

    return rows, sm.ratio()


def find_transcript(folder):
    p = folder / "transcript.json"

    if p.exists():
        return p

    cands = sorted(
        folder.glob("*.json"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if cands:
        return cands[0]

    listing = (
        [x.name for x in folder.iterdir()]
        if folder.exists()
        else "(folder missing)"
    )

    die(
        f"no transcript JSON in {folder}; "
        f"found: {listing}"
    )


def cmd_align(_a):
    cfg, script = load_inputs()

    s = validate_basic(cfg, script)

    meta = json.loads(
        (BUILD / "audio_meta.json").read_text(
            encoding="utf-8"
        )
    )

    sm_ = meta["sentences"][0]

    toks = script_tokens(s["text"])

    tpath = find_transcript(
        BUILD / "whisper"
    )

    words = load_whisper_words(
        tpath,
        sm_["duration"]
    )

    al = cfg["alignment"]

    rows, ratio = align_words(
        toks,
        words,
        al["min_word_match"]
    )

    offset = sm_["offset"]

    for r in rows:

        r["abs_start"] = (
            None
            if r["start"] is None
            else round(r["start"] + offset, 3)
        )

        r["abs_end"] = (
            None
            if r["end"] is None
            else round(r["end"] + offset, 3)
        )

        r["start"] = (
            None
            if r["start"] is None
            else round(r["start"], 3)
        )

        r["end"] = (
            None
            if r["end"] is None
            else round(r["end"], 3)
        )

    onset, offs, rms, win = speech_bounds(
        BUILD / "audio" / f"{s['id']}.wav"
    )

    timed = [
        r for r in rows
        if r["start"] is not None
    ]

    means = []

    for r in timed:

        a = int(r["start"] / win)

        b = max(
            int(r["start"] / win) + 1,
            int(r["end"] / win)
        )

        seg = rms[a:b] or [0]

        means.append(
            sum(seg) / len(seg)
        )

        r["_e"] = means[-1]

    med = (
        statistics.median(means)
        if means
        else 0
    )

    for r in timed:

        r["energy_rel"] = (
            round(r.pop("_e") / med, 2)
            if med
            else None
        )

        if (
            r["energy_rel"] is not None
            and r["energy_rel"] < 0.25
        ):

            r["notes"].append(
                "low audio energy inside this window "
                "(check manually)"
            )

    counts = {
        k: sum(
            1 for r in rows
            if r["status"] == k
        )
        for k in (
            "exact",
            "aligned",
            "unmatched",
            "skipped"
        )
    }

    status = "OK"
    reasons = []

    if counts["aligned"]:

        status = "WARN"

        reasons.append(
            f"{counts['aligned']} word(s) "
            "aligned with differences/estimates"
        )

    if counts["unmatched"]:

        status = "FAIL"

        reasons.append(
            f"{counts['unmatched']} word(s) "
            "could not be matched "
            "(no timestamp assigned)"
        )

    if ratio < al["min_sentence_ratio"]:

        status = "FAIL"

        reasons.append(
            f"sentence match ratio {ratio:.2f} "
            f"< {al['min_sentence_ratio']}"
        )

    summary = {
        "status": status,
        "reasons": reasons,
        "match_ratio": round(ratio, 3),
        "counts": counts,
    }

    if onset is not None and timed:

        summary["first_word_vs_speech_onset_ms"] = round(
            (timed[0]["start"] - onset) * 1000
        )

        summary["last_word_vs_speech_end_ms"] = round(
            (timed[-1]["end"] - offs) * 1000
        )

    timing = {
        "stage": 0,
        "transcript_file": str(
            tpath.relative_to(ROOT)
        ),
        "audio": meta,
        "sentence": {
            "id": s["id"],
            "text": s["text"],
            "offset": offset,
            "duration": sm_["duration"],
            "words": rows,
        },
        "summary": summary,
    }

    BUILD.mkdir(parents=True, exist_ok=True)

    (BUILD / "timing.json").write_text(
        json.dumps(
            timing,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8",
    )

    lines = [
        f"## Stage 0 timing report - {status}",
        "",
        f"- match ratio: **{ratio:.2f}** "
        f"(minimum {al['min_sentence_ratio']})",
        f"- words: exact {counts['exact']}, "
        f"aligned {counts['aligned']}, "
        f"unmatched {counts['unmatched']}, "
        f"skipped {counts['skipped']}",
    ]

    for k in (
        "first_word_vs_speech_onset_ms",
        "last_word_vs_speech_end_ms"
    ):

        if k in summary:
            lines.append(
                f"- {k}: {summary[k]} ms"
            )

    lines += [
        f"- {x}"
        for x in reasons
    ]

    lines += [
        "",
        "| # | script word | recognized | start s | end s | status | note |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in rows:

        lines.append(
            f"| {r['i']} | {r['text']} | "
            f"{' + '.join(r['recognized'])} | "
            f"{r['abs_start'] if r['abs_start'] is not None else '-'} | "
            f"{r['abs_end'] if r['abs_end'] is not None else '-'} | "
            f"{r['status']} | "
            f"{'; '.join(r['notes'])} |"
        )

    report = "\n".join(lines) + "\n"

    (BUILD / "timing_report.md").write_text(
        report,
        encoding="utf-8",
    )

    print(report)

    if status == "FAIL":
        sys.exit(3)


# --------------------------------------------------------------------------
# compose (HyperFrames composition + SRT)
# --------------------------------------------------------------------------

def srt_time(t):
    ms = int(round(t * 1000))

    return (
        f"{ms // 3600000:02d}:"
        f"{ms // 60000 % 60:02d}:"
        f"{ms // 1000 % 60:02d},"
        f"{ms % 1000:03d}"
    )


def cmd_compose(_a):
    cfg, script = load_inputs()

    timing = json.loads(
        (BUILD / "timing.json").read_text(
            encoding="utf-8"
        )
    )

    if timing["summary"]["status"] == "FAIL":

        die(
            "timing status is FAIL - refusing to build "
            "a video from unreliable timestamps.",
            3
        )

    sent = timing["sentence"]

    total = timing["audio"]["total"]

    story = BUILD / "story"

    (story / "assets" / "fonts").mkdir(
        parents=True,
        exist_ok=True
    )

    fonts = list(
        (ROOT / "assets" / "fonts").glob("*.woff2")
    )

    if not fonts:

        die(
            "assets/fonts/*.woff2 not found - "
            "the 'Get Persian font' workflow step must run first."
        )

    for f in fonts:

        shutil.copyfile(
            f,
            story / "assets" / "fonts" / f.name
        )

    shutil.copyfile(
        BUILD / "narration.wav",
        story / "narration.wav"
    )

    spans = []
    tw = []

    for r in sent["words"]:

        wid = f"w-{sent['id']}-{r['i']}"

        spans.append(
            f'<span class="w" id="{wid}">'
            f'{html.escape(r["text"])}'
            f'</span>'
        )

        if r["abs_start"] is not None:

            tw.append({
                "id": wid,
                "start": r["abs_start"],
                "end": r["abs_end"],
            })

    # Do not create an empty timeline.
    if not tw:

        die(
            "No usable word timestamps were produced; "
            "refusing to build an empty timeline.",
            3
        )

    sent_html = (
        f'<div class="sentence" id="sent-{sent["id"]}">'
        f'{" ".join(spans)}'
        f'</div>'
    )

    data = {
        "duration": round(total, 3),
        "sentences": [
            {
                "id": sent["id"],
                "start": tw[0]["start"],
                "end": tw[-1]["end"],
                "words": tw,
            }
        ],
    }

    data_js = json.dumps(
        data,
        ensure_ascii=False
    ).replace("<", "\\u003c")

    tpl = (
        STORY / "template.html"
    ).read_text(encoding="utf-8")

    page = (
        tpl.replace(
            "__DURATION__",
            f"{total:.3f}"
        )
        .replace(
            "__SENTENCES_HTML__",
            sent_html
        )
        .replace(
            "__TIMELINE_JSON__",
            data_js
        )
    )

    (story / "index.html").write_text(
        page,
        encoding="utf-8"
    )

    cue = (
        f"1\n"
        f"{srt_time(tw[0]['start'])} --> "
        f"{srt_time(tw[-1]['end'] + 0.15)}\n"
        f"{sent['text']}\n"
    )

    (BUILD / "story.srt").write_text(
        cue,
        encoding="utf-8"
    )

    print(
        f"Composition written to "
        f"{story / 'index.html'} "
        f"(duration {total:.2f}s, "
        f"{len(tw)} timed words)."
    )


# --------------------------------------------------------------------------
# verify (rendered MP4)
# --------------------------------------------------------------------------

SEA = (79, 209, 197)


def sea_pixels(mp4, t, w=270, h=480):
    """
    Sample the portrait video at 270x480.
    This preserves the 9:16 aspect ratio.
    """

    raw = run([
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{max(0, t):.3f}",
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        "-vf",
        f"scale={w}:{h}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ])

    n = 0
    sx = 0
    sy = 0

    for p in range(
        0,
        min(len(raw), w * h * 3) - 2,
        3
    ):

        if (
            abs(raw[p] - SEA[0]) < 26
            and abs(raw[p + 1] - SEA[1]) < 26
            and abs(raw[p + 2] - SEA[2]) < 26
        ):

            q = p // 3

            n += 1
            sx += q % w
            sy += q // w

    return (
        n,
        round(sx / n / w, 3) if n else None,
        round(sy / n / h, 3) if n else None,
    )


def cmd_verify(_a):
    timing = json.loads(
        (BUILD / "timing.json").read_text(
            encoding="utf-8"
        )
    )

    mp4 = BUILD / "story.mp4"

    if not mp4.exists() or mp4.stat().st_size == 0:

        die(
            "story.mp4 is missing or empty",
            4
        )

    probe = json.loads(
        run([
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(mp4),
        ])
    )

    video = [
        x for x in probe["streams"]
        if x["codec_type"] == "video"
    ]

    audio = [
        x for x in probe["streams"]
        if x["codec_type"] == "audio"
    ]

    dur = float(
        probe["format"]["duration"]
    )

    expected = timing["audio"]["total"]

    res = {
        "size_bytes": mp4.stat().st_size,
        "duration": round(dur, 3),
        "expected_duration": round(expected, 3),
        "video": [
            {
                "codec": v["codec_name"],
                "w": v["width"],
                "h": v["height"],
                "fps": v["r_frame_rate"],
            }
            for v in video
        ],
        "audio": [
            {
                "codec": a["codec_name"],
                "rate": a.get("sample_rate"),
            }
            for a in audio
        ],
        "problems": [],
    }

    if not video:

        res["problems"].append(
            "no video stream"
        )

    # Mandatory portrait resolution and frame-rate checks.
    if video:

        v = video[0]

        if (
            v["width"] != 1080
            or v["height"] != 1920
        ):

            res["problems"].append(
                f"wrong video dimensions: "
                f"{v['width']}x{v['height']} "
                "(expected 1080x1920)"
            )

        try:

            fps_num, fps_den = map(
                int,
                v["r_frame_rate"].split("/")
            )

            if fps_den == 0:
                raise ValueError("zero denominator")

            fps = fps_num / fps_den

            if abs(fps - 30) > 0.1:

                res["problems"].append(
                    f"wrong frame rate: "
                    f"{fps:.2f} fps (expected 30)"
                )

        except (ValueError, ZeroDivisionError):

            res["problems"].append(
                "could not parse video frame rate"
            )

    if not audio:

        res["problems"].append(
            "NO AUDIO STREAM in the MP4"
        )

    if abs(dur - expected) > 0.3:

        res["problems"].append(
            f"duration {dur:.2f}s differs "
            f"from narration {expected:.2f}s"
        )

    timed = [
        r
        for r in timing["sentence"]["words"]
        if r["abs_start"] is not None
    ]

    if audio:

        run([
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(mp4),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            str(BUILD / "mp4_audio.wav"),
        ])

        onset, _, _, _ = speech_bounds(
            BUILD / "mp4_audio.wav"
        )

        if onset is not None and timed:

            res["mp4_audio_onset_vs_first_word_ms"] = round(
                (timed[0]["abs_start"] - onset) * 1000
            )

    frames_dir = BUILD / "frames"

    frames_dir.mkdir(exist_ok=True)

    hl = []

    # Only inspect highlight frames when a video stream exists.
    if video:

        for r in timed:

            mid = (
                r["abs_start"] + r["abs_end"]
            ) / 2

            n, cx, cy = sea_pixels(
                mp4,
                mid
            )

            hl.append({
                "i": r["i"],
                "text": r["text"],
                "t": round(mid, 3),
                "highlight_pixels": n,
                "x": cx,
                "y": cy,
            })

            if n < 150:

                res["problems"].append(
                    f"no highlight visible for "
                    f"word {r['i']} at {mid:.2f}s"
                )

            run([
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{mid:.3f}",
                "-i",
                str(mp4),
                "-frames:v",
                "1",
                "-vf",
                "scale=540:-1",
                str(
                    frames_dir /
                    f"word_{r['i']:02d}.png"
                ),
            ])

        res["highlight"] = hl

        if timed:

            t0 = timed[0]["abs_start"]

            before, _, _ = sea_pixels(
                mp4,
                t0 - 0.10
            )

            after, _, _ = sea_pixels(
                mp4,
                t0 + 0.10
            )

            res[
                "first_word_highlight_pixels_100ms_before_vs_after"
            ] = [
                before,
                after,
            ]

            if before >= 150 or after < 150:

                res["problems"].append(
                    "first-word highlight does not switch on "
                    "within +/-100 ms of its start"
                )

    (BUILD / "verify.json").write_text(
        json.dumps(
            res,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            res,
            ensure_ascii=False,
            indent=2
        )
    )

    if res["problems"]:

        die(
            "verification problems: "
            + "; ".join(res["problems"]),
            4
        )

    print("VERIFY OK")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    sub = p.add_subparsers(
        dest="cmd",
        required=True
    )

    for name, fn in (
        ("check", cmd_check),
        ("tts", cmd_tts),
        ("prepare", cmd_prepare),
        ("align", cmd_align),
        ("compose", cmd_compose),
        ("verify", cmd_verify),
    ):

        sub.add_parser(name).set_defaults(
            fn=fn
        )

    args = p.parse_args()

    args.fn(args)


if __name__ == "__main__":
    main()
