#!/usr/bin/env python3
"""
NFP Story Studio - Stage 0
One short Persian sentence.

Commands:
  check
  tts
  prepare
  align
  compose
  verify

Python standard library only.
The API key is never printed or written to disk.
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

FREE_STANDARD_MODELS = {
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
}

MAX_TEXT_CHARS = 300
MAX_ATTEMPTS_LIMIT = 5
MAX_REQUESTS_LIMIT = 5
MAX_TIMEOUT = 300
MAX_AUDIO_SECONDS = 120
TIMESTAMP_TOLERANCE = 0.05


# --------------------------------------------------------------------------
# General helpers
# --------------------------------------------------------------------------

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def finite_number(value, name, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        die(f"{name} must be a valid number")

    if not math.isfinite(number):
        die(f"{name} must be finite")

    if minimum is not None and number < minimum:
        die(f"{name} must be >= {minimum}")

    if maximum is not None and number > maximum:
        die(f"{name} must be <= {maximum}")

    return number


def bounded_int(value, name, minimum, maximum):
    if isinstance(value, bool):
        die(f"{name} must be an integer")

    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        die(f"{name} must be an integer")

    if str(value).strip() not in (
        str(number),
        f"{number}.0"
    ):
        die(f"{name} must be an integer")

    if not minimum <= number <= maximum:
        die(
            f"{name} must be between "
            f"{minimum} and {maximum}"
        )

    return number


def load_json(path):
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        die(f"file not found: {path}")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        die(f"invalid JSON or text encoding in {path}: {e}")
    except OSError as e:
        die(f"cannot read {path}: {e}")


def load_inputs():
    cfg = load_json(CONFIG_PATH)
    script = load_json(SCRIPT_PATH)

    if not isinstance(cfg, dict):
        die("config.json must contain a JSON object")

    if not isinstance(script, dict):
        die("script.stage0.json must contain a JSON object")

    return cfg, script


def run(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False
        )
    except FileNotFoundError:
        die(f"required command not found: {cmd[0]}")
    except OSError as e:
        die(f"could not run {cmd[0]}: {e}")

    if result.returncode != 0:
        stderr = result.stderr.decode(
            "utf-8",
            "replace"
        )[-1200:]

        die(
            f"command failed: {' '.join(map(str, cmd))}\n"
            f"{stderr}"
        )

    return result.stdout


def require_dict(parent, key, name):
    value = parent.get(key)

    if not isinstance(value, dict):
        die(f"{name} must be a JSON object")

    return value


# --------------------------------------------------------------------------
# Persian text handling
# --------------------------------------------------------------------------

_DIACRITICS = re.compile(
    "[\u064B-\u065F\u0670\u06D6-\u06DC"
    "\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]"
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
    0x06F0 + i: ord(str(i))
    for i in range(10)
})

_CHAR_MAP.update({
    0x0660 + i: ord(str(i))
    for i in range(10)
})


def norm(text):
    if not isinstance(text, str):
        return ""

    t = unicodedata.normalize("NFKC", text)

    for ch in (
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u0640"
    ):
        t = t.replace(ch, "")

    t = _DIACRITICS.sub(
        "",
        t
    ).translate(_CHAR_MAP).lower()

    return "".join(
        c for c in t
        if unicodedata.category(c)[0] in ("L", "N")
    )


def script_tokens(text):
    return [
        {
            "i": i,
            "text": word,
            "norm": norm(word)
        }
        for i, word in enumerate(text.split())
    ]


# --------------------------------------------------------------------------
# WAV helpers
# --------------------------------------------------------------------------

def ensure_wav(data):
    """
    Accept a valid WAV or headerless 24 kHz mono s16le PCM.
    """

    if not isinstance(data, bytes) or not data:
        die("audio response is empty")

    if data[:4] == b"RIFF":
        return data

    if len(data) % 2:
        die("headerless PCM audio has an odd byte length")

    tmp = BUILD / "_raw_wrap.wav"
    tmp.parent.mkdir(parents=True, exist_ok=True)

    try:
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(data)

        result = tmp.read_bytes()

    except (wave.Error, OSError) as e:
        die(f"could not wrap PCM audio: {e}")

    finally:
        if tmp.exists():
            tmp.unlink()

    return result


def wav_info(path):
    try:
        with wave.open(str(path), "rb") as w:
            info = {
                "channels": w.getnchannels(),
                "width": w.getsampwidth(),
                "rate": w.getframerate(),
                "frames": w.getnframes(),
            }

    except (wave.Error, EOFError, OSError) as e:
        die(f"{path} is not a readable WAV file: {e}")

    if info["channels"] != 1:
        die(f"{path}: expected mono audio")

    if info["width"] != 2:
        die(f"{path}: expected 16-bit audio")

    if info["rate"] <= 0:
        die(f"{path}: invalid sample rate")

    if info["frames"] <= 0:
        die(f"{path}: WAV contains no audio frames")

    info["duration"] = (
        info["frames"] / info["rate"]
    )

    if (
        not math.isfinite(info["duration"])
        or info["duration"] > MAX_AUDIO_SECONDS
    ):
        die(f"{path}: invalid or excessive audio duration")

    return info


def validate_wav(path, expected_rate=None):
    info = wav_info(path)

    if expected_rate is not None:
        if info["rate"] != expected_rate:
            die(
                f"{path}: expected {expected_rate} Hz, "
                f"found {info['rate']} Hz"
            )

    if info["duration"] < 0.3:
        die(
            f"{path}: audio is suspiciously short "
            f"({info['duration']:.2f}s)"
        )

    return info


def load_samples(path):
    info = validate_wav(path)

    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())

    samples = array.array("h")
    samples.frombytes(raw)

    if sys.byteorder == "big":
        samples.byteswap()

    return info["rate"], samples


def window_rms(samples, sr, win=0.01):
    n = max(1, int(sr * win))
    out = []

    for i in range(0, len(samples), n):
        chunk = samples[i:i + n]

        out.append(
            math.sqrt(
                sum(x * x for x in chunk)
                / max(1, len(chunk))
            )
        )

    return out, win


def speech_bounds(path):
    sr, samples = load_samples(path)

    rms, win = window_rms(samples, sr)

    peak = max(rms) if rms else 0

    if peak <= 0:
        return None, None, rms, win

    threshold = 0.08 * peak

    indices = [
        i for i, value in enumerate(rms)
        if value > threshold
    ]

    if not indices:
        return None, None, rms, win

    return (
        indices[0] * win,
        (indices[-1] + 1) * win,
        rms,
        win
    )


# --------------------------------------------------------------------------
# Configuration validation
# --------------------------------------------------------------------------

def validate_basic(cfg, script):
    if not isinstance(cfg, dict):
        die("configuration must be an object")

    if not isinstance(script, dict):
        die("script must be an object")

    t = require_dict(cfg, "tts", "config.tts")
    audio = require_dict(cfg, "audio", "config.audio")
    alignment = require_dict(
        cfg,
        "alignment",
        "config.alignment"
    )

    model = t.get("model")

    if not isinstance(model, str):
        die("tts.model must be a string")

    if model not in FREE_STANDARD_MODELS:
        die(
            f"model '{model}' is not on the Stage 0 allow-list: "
            f"{sorted(FREE_STANDARD_MODELS)}"
        )

    voice = t.get("voice")

    if not isinstance(voice, str) or not voice.strip():
        die("tts.voice must be a non-empty string")

    style = t.get("style", "")

    if not isinstance(style, str):
        die("tts.style must be a string")

    timeout = bounded_int(
        t.get("timeout_sec", 90),
        "tts.timeout_sec",
        5,
        MAX_TIMEOUT
    )

    attempts = bounded_int(
        t.get("max_attempts", 1),
        "tts.max_attempts",
        1,
        MAX_ATTEMPTS_LIMIT
    )

    requests = bounded_int(
        t.get("max_requests_per_run", 1),
        "tts.max_requests_per_run",
        1,
        MAX_REQUESTS_LIMIT
    )

    lead = finite_number(
        audio.get("lead_in_ms"),
        "audio.lead_in_ms",
        0,
        5000
    )

    tail = finite_number(
        audio.get("tail_ms"),
        "audio.tail_ms",
        0,
        10000
    )

    min_word = finite_number(
        alignment.get("min_word_match"),
        "alignment.min_word_match",
        0,
        1
    )

    min_sentence = finite_number(
        alignment.get("min_sentence_ratio"),
        "alignment.min_sentence_ratio",
        0,
        1
    )

    sentences = script.get("sentences")

    if not isinstance(sentences, list):
        die("script.sentences must be a list")

    if len(sentences) != 1:
        die(
            "Stage 0 allows exactly ONE sentence "
            f"(found {len(sentences)})"
        )

    sentence = sentences[0]

    if not isinstance(sentence, dict):
        die("the sentence must be a JSON object")

    sid = sentence.get("id")

    if (
        not isinstance(sid, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", sid)
    ):
        die("sentence id must match [A-Za-z0-9_-]+")

    text = sentence.get("text")

    if not isinstance(text, str) or not text.strip():
        die("sentence text must be a non-empty string")

    speak = sentence.get("speak")

    if speak is not None and not isinstance(speak, str):
        die("sentence speak must be a string when provided")

    speak = speak or text

    if not speak.strip():
        die("sentence speak is empty")

    if len(speak) > MAX_TEXT_CHARS:
        die(
            f"sentence longer than {MAX_TEXT_CHARS} characters"
        )

    if not script_tokens(text):
        die("sentence has no words")

    if len(text) > MAX_TEXT_CHARS:
        die(
            f"display sentence longer than {MAX_TEXT_CHARS} characters"
        )

    # Keep normalized settings available to callers.
    t["_timeout"] = timeout
    t["_attempts"] = attempts
    t["_requests"] = requests

    audio["_lead"] = lead / 1000
    audio["_tail"] = tail / 1000

    alignment["_min_word"] = min_word
    alignment["_min_sentence"] = min_sentence

    return sentence


def cmd_check(_a):
    cfg, script = load_inputs()

    sentence = validate_basic(cfg, script)
    t = cfg["tts"]

    print("Stage 0 configuration is valid.")
    print(f"  model            : {t['model']}")
    print(
        f"  voice / style    : "
        f"{t['voice']} / {t.get('style') or '(none)'}"
    )
    print(f"  sentence         : {sentence['text']}")
    print(f"  words            : {len(script_tokens(sentence['text']))}")
    print(
        f"  max API attempts : "
        f"{min(t['_attempts'], t['_requests'])}"
    )
    print(
        "  GEMINI_API_KEY   : "
        f"{'set' if os.environ.get('GEMINI_API_KEY') else 'not set (allowed during offline check)'}"
    )
    print(
        "Reminder: model allow-list does not guarantee "
        "free pricing, quota, or unlimited availability."
    )


# --------------------------------------------------------------------------
# Gemini TTS
# --------------------------------------------------------------------------

class ApiError(Exception):

    def __init__(
        self,
        status,
        retryable,
        retry_after,
        short
    ):
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
    if not isinstance(data, dict):
        return None

    interaction = data.get("interaction", data)

    if not isinstance(interaction, dict):
        return None

    output_audio = interaction.get("output_audio")

    if isinstance(output_audio, dict):
        audio_data = output_audio.get("data")

        if isinstance(audio_data, str) and audio_data:
            return audio_data

    steps = interaction.get("steps", [])

    if not isinstance(steps, list):
        return None

    for step in steps:
        if not isinstance(step, dict):
            continue

        if step.get("type") != "model_output":
            continue

        content_list = step.get("content", [])

        if not isinstance(content_list, list):
            continue

        for content in content_list:
            if not isinstance(content, dict):
                continue

            if (
                content.get("type") == "audio"
                and isinstance(content.get("data"), str)
                and content["data"]
            ):
                return content["data"]

    return None


def scrub_secret(text, key):
    if not isinstance(text, str):
        return "API request failed"

    if key:
        text = text.replace(key, "[REDACTED]")

    text = re.sub(
        r"(?i)(x-goog-api-key|api[_-]?key)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text
    )

    return text[:400]


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

    request = urllib.request.Request(
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
            request,
            timeout=t["_timeout"]
        ) as response:
            raw = response.read()

    except urllib.error.HTTPError as e:
        txt = e.read().decode(
            "utf-8",
            "replace"
        )

        try:
            parsed = json.loads(txt)
            msg = parsed.get(
                "error",
                {}
            ).get("message", txt)
        except (ValueError, AttributeError):
            msg = txt

        retry_after = e.headers.get("Retry-After")

        try:
            retry_after = (
                float(retry_after)
                if retry_after
                else None
            )
        except (ValueError, TypeError):
            retry_after = None

        raise ApiError(
            e.code,
            e.code in (429, 500, 502, 503, 504),
            retry_after,
            scrub_secret(str(msg), key),
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
            scrub_secret(str(e), key),
        )

    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(
            200,
            False,
            None,
            "Gemini returned invalid JSON",
        )

    found = extract_audio_data(data)

    if not found:
        raise ApiError(
            200,
            False,
            None,
            "Gemini response contained no recognized audio data",
        )

    try:
        decoded = base64.b64decode(
            found,
            validate=True
        )
    except (ValueError, TypeError):
        raise ApiError(
            200,
            False,
            None,
            "Gemini returned invalid base64 audio",
        )

    return ensure_wav(decoded)


def synth_with_retry(t, text, key):
    attempts = min(
        t["_attempts"],
        t["_requests"]
    )

    for n in range(1, attempts + 1):
        try:
            print(
                f"Gemini TTS request {n}/{attempts} "
                f"(model {t['model']}) ..."
            )

            return synth_once(
                t,
                text,
                key
            ), n

        except ApiError as e:
            hint = ""

            if e.status == 429:
                hint = (
                    " Quota or rate limit reached. "
                    "No model fallback will be used."
                )

            if not e.retryable or n == attempts:
                die(
                    f"Gemini API error (HTTP {e.status}): "
                    f"{e.short}.{hint}"
                )

            wait = (
                e.retry_after
                if e.retry_after is not None
                else min(
                    60.0,
                    2 ** n + random.random()
                )
            )

            wait = max(1, min(wait, 60))

            print(
                f"Request failed: {e.short}. "
                f"Retrying in {wait:.0f}s."
            )

            time.sleep(wait)

    die("unreachable")


def cmd_tts(_a):
    cfg, script = load_inputs()

    s = validate_basic(cfg, script)
    t = cfg["tts"]

    text = s.get("speak") or s["text"]
    h = sentence_hash(t, text)

    CACHE.mkdir(
        parents=True,
        exist_ok=True
    )

    cached = CACHE / f"{h}.wav"

    out = BUILD / "audio" / f"{s['id']}.wav"
    out.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    requests_made = 0
    cache_hit = cached.exists()

    if cache_hit:
        print(
            f"CACHE HIT ({h[:12]}) - no API request."
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
                "Add the repository secret before running TTS."
            )

        wav_data, requests_made = synth_with_retry(
            t,
            text,
            key
        )

        tmp = cached.with_suffix(".tmp")

        try:
            tmp.write_bytes(wav_data)
            validate_wav(tmp)
            tmp.replace(cached)
        except OSError as e:
            if tmp.exists():
                tmp.unlink()
            die(f"could not save cached audio: {e}")

    shutil.copyfile(cached, out)

    info = validate_wav(out)

    BUILD.mkdir(
        parents=True,
        exist_ok=True
    )

    (BUILD / "tts_meta.json").write_text(
        json.dumps(
            {
                "hash": h,
                "cache_hit": cache_hit,
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

    BUILD.mkdir(
        parents=True,
        exist_ok=True
    )

    src = BUILD / "audio" / f"{s['id']}.wav"

    info = validate_wav(src)

    audio_cfg = cfg["audio"]

    lead = audio_cfg["_lead"]
    tail = audio_cfg["_tail"]

    with wave.open(str(src), "rb") as w:
        frames = w.readframes(w.getnframes())

    sr = info["rate"]

    def silence(seconds):
        return b"\x00\x00" * int(
            round(seconds * sr)
        )

    narration = BUILD / "narration.wav"

    with wave.open(str(narration), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sr)

        output.writeframes(
            silence(lead) + frames + silence(tail)
        )

    total = lead + info["duration"] + tail

    meta = {
        "sample_rate": sr,
        "lead": lead,
        "tail": tail,
        "total": total,
        "timestamp_reference": "narration.wav",
        "sentences": [
            {
                "id": s["id"],
                "offset": lead,
                "duration": info["duration"],
            }
        ],
    }

    (BUILD / "audio_meta.json").write_text(
        json.dumps(
            meta,
            indent=2
        ),
        encoding="utf-8",
    )

    run([
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(narration),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(BUILD / "whisper_input.wav"),
    ])

    validate_wav(
        narration
    )

    whisper_info = validate_wav(
        BUILD / "whisper_input.wav",
        expected_rate=16000
    )

    if abs(
        whisper_info["duration"] - total
    ) > 0.05:
        die(
            "Whisper audio duration does not match narration.wav"
        )

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


def _num(value):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _word_from(data):
    text = data.get(
        "text",
        data.get(
            "word",
            data.get("token")
        )
    )

    if not isinstance(text, str):
        return None

    start = _num(data.get("start"))
    end = _num(data.get("end"))
    milliseconds = False

    if start is None or end is None:
        offsets = data.get("offsets")

        if isinstance(offsets, dict):
            start = _num(offsets.get("from"))
            end = _num(offsets.get("to"))
            milliseconds = True

    if start is None or end is None:
        return None

    if milliseconds:
        start /= 1000
        end /= 1000

    return {
        "text": text.strip(),
        "start": start,
        "end": end,
        "explicit_ms": milliseconds,
    }


def _collect(node, out):
    if isinstance(node, dict):
        words = node.get("words")

        if isinstance(words, list):
            for word in words:
                if isinstance(word, dict):
                    parsed = _word_from(word)

                    if parsed:
                        out.append(parsed)

            return

        for key in (
            "segments",
            "transcription",
            "results",
            "transcript"
        ):
            if key in node:
                _collect(node[key], out)

    elif isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and "words" not in item:
                parsed = _word_from(item)

                if parsed:
                    out.append(parsed)
                else:
                    _collect(item, out)
            else:
                _collect(item, out)


def load_whisper_words(path, audio_duration):
    data = load_json(path)

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
            f"(top-level: {keys})"
        )

    raw = [
        word for word in raw
        if word["text"]
        and not _SPECIAL.match(word["text"])
    ]

    if any(
        len(word["text"].split()) > 1
        for word in raw
    ):
        die(
            "transcript contains segment-level timing only; "
            "per-word timestamps are required"
        )

    if not any(
        word["explicit_ms"]
        for word in raw
    ):
        max_end = max(
            word["end"]
            for word in raw
        )

        if max_end > audio_duration * 1.5 + 1:
            for word in raw:
                word["start"] /= 1000
                word["end"] /= 1000

    raw.sort(
        key=lambda word: (
            word["start"],
            word["end"]
        )
    )

    words = []
    previous_start = -1
    previous_end = -1

    for word in raw:
        start = word["start"]
        end = word["end"]

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
        ):
            die("Whisper returned non-finite timestamps")

        if start < 0:
            die("Whisper returned a negative timestamp")

        if end <= start:
            die("Whisper returned an invalid word duration")

        if end > audio_duration + TIMESTAMP_TOLERANCE:
            die(
                "Whisper timestamp exceeds padded audio duration"
            )

        if start < previous_start:
            die("Whisper timestamps are not ordered")

        if (
            previous_end >= 0
            and start < previous_end - 0.5
        ):
            die(
                "Whisper timestamps contain excessive overlap"
            )

        word["norm"] = norm(word["text"])

        if word["norm"]:
            words.append(word)

        previous_start = start
        previous_end = max(previous_end, end)

    if not words:
        die("transcript contains no usable words")

    return words


def align_words(toks, wwords, min_word_match):
    script_owner = [
        token_index
        for token_index, token in enumerate(toks)
        for _ in token["norm"]
    ]

    whisper_owner = [
        (word_index, position, len(word["norm"]))
        for word_index, word in enumerate(wwords)
        for position in range(len(word["norm"]))
    ]

    script_text = "".join(
        token["norm"]
        for token in toks
    )

    whisper_text = "".join(
        word["norm"]
        for word in wwords
    )

    matcher = difflib.SequenceMatcher(
        None,
        script_text,
        whisper_text,
        autojunk=False
    )

    per_token = {
        i: []
        for i in range(len(toks))
    }

    for a, b, size in matcher.get_matching_blocks():
        for d in range(size):
            token_index = script_owner[a + d]

            word_index, position, length = (
                whisper_owner[b + d]
            )

            word = wwords[word_index]

            span = word["end"] - word["start"]

            # Character-proportional boundaries are estimates,
            # not phonetic word-boundary measurements.
            per_token[token_index].append(
                (
                    word["start"]
                    + span * position / length,
                    word["start"]
                    + span * (position + 1) / length,
                    word_index,
                )
            )

    users = {}

    for token_index, entries in per_token.items():
        for _, _, word_index in entries:
            users.setdefault(
                word_index,
                set()
            ).add(token_index)

    rows = []

    for token_index, token in enumerate(toks):
        length = len(token["norm"])
        entries = per_token[token_index]

        row = {
            "i": token_index,
            "text": token["text"],
            "start": None,
            "end": None,
            "recognized": [],
            "matched_frac": None,
            "status": "skipped",
            "notes": [],
        }

        if length == 0:
            row["notes"].append("punctuation only")

        else:
            fraction = len(entries) / length

            word_indices = sorted({
                word_index
                for _, _, word_index in entries
            })

            row["matched_frac"] = round(
                fraction,
                3
            )

            row["recognized"] = [
                wwords[index]["text"]
                for index in word_indices
            ]

            if fraction < min_word_match:
                row["status"] = "unmatched"

                row["notes"].append(
                    "recognized text differs; "
                    "no timestamp assigned"
                )

            else:
                row["start"] = min(
                    start
                    for start, _, _ in entries
                )

                row["end"] = max(
                    end
                    for _, end, _ in entries
                )

                shared = any(
                    len(users[index]) > 1
                    for index in word_indices
                )

                exact = (
                    len(word_indices) == 1
                    and not shared
                    and wwords[word_indices[0]]["norm"]
                    == token["norm"]
                )

                row["status"] = (
                    "exact"
                    if exact
                    else "aligned"
                )

                if fraction < 1:
                    row["notes"].append(
                        "recognized text differs"
                    )

                if shared:
                    row["notes"].append(
                        "boundary ESTIMATED inside recognized word"
                    )

                if len(word_indices) > 1:
                    row["notes"].append(
                        "spans several recognized words"
                    )

        rows.append(row)

    previous_end = None

    for row in rows:
        if row["start"] is None:
            continue

        if row["end"] - row["start"] < 0.02:
            row["end"] = row["start"] + 0.02

            row["notes"].append(
                "very short word; end padded to 20 ms"
            )

        if (
            previous_end is not None
            and row["start"] < previous_end - 0.05
        ):
            row["notes"].append(
                "overlaps previous word"
            )

        previous_end = row["end"]

    return rows, matcher.ratio()


def find_transcript(folder):
    path = folder / "transcript.json"

    if path.exists():
        return path

    candidates = sorted(
        folder.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True
    )

    if candidates:
        return candidates[0]

    listing = (
        [item.name for item in folder.iterdir()]
        if folder.exists()
        else "(folder missing)"
    )

    die(
        f"no transcript JSON in {folder}; "
        f"found: {listing}"
    )


def cmd_align(_a):
    cfg, script = load_inputs()

    sentence = validate_basic(cfg, script)

    meta = load_json(
        BUILD / "audio_meta.json"
    )

    sm = meta["sentences"][0]

    offset = float(sm["offset"])
    speech_duration = float(sm["duration"])
    padded_duration = float(meta["total"])

    tokens = script_tokens(sentence["text"])

    transcript_path = find_transcript(
        BUILD / "whisper"
    )

    # Whisper analyzed the PADDED audio.
    # Its timestamps already include lead-in silence.
    # Do not add offset again.
    words = load_whisper_words(
        transcript_path,
        padded_duration
    )

    alignment = cfg["alignment"]

    rows, ratio = align_words(
        tokens,
        words,
        alignment["_min_word"]
    )

    for row in rows:
        if row["start"] is None:
            row["abs_start"] = None
            row["abs_end"] = None
            continue

        start = float(row["start"])
        end = float(row["end"])

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
            or end > padded_duration + TIMESTAMP_TOLERANCE
        ):
            die(
                f"invalid aligned timestamp for word "
                f"{row['i']}"
            )

        # These are absolute narration.wav timestamps.
        row["start"] = round(start, 3)
        row["end"] = round(end, 3)

        row["abs_start"] = row["start"]
        row["abs_end"] = row["end"]

    # RMS is measured against the ORIGINAL speech WAV.
    # Convert padded timestamps to original speech-relative time
    # only for this energy calculation.
    onset, speech_end, rms, win = speech_bounds(
        BUILD / "audio" / f"{sentence['id']}.wav"
    )

    timed = [
        row for row in rows
        if row["start"] is not None
    ]

    energies = []

    for row in timed:
        local_start = row["start"] - offset
        local_end = row["end"] - offset

        a = max(
            0,
            int(local_start / win)
        )

        b = max(
            a + 1,
            int(math.ceil(local_end / win))
        )

        segment = rms[a:b] or [0]

        energy = sum(segment) / len(segment)

        energies.append(energy)
        row["_energy"] = energy

    median_energy = (
        statistics.median(energies)
        if energies
        else 0
    )

    for row in timed:
        energy = row.pop("_energy")

        row["energy_rel"] = (
            round(energy / median_energy, 2)
            if median_energy > 0
            else None
        )

        if (
            row["energy_rel"] is not None
            and row["energy_rel"] < 0.25
        ):
            row["notes"].append(
                "low audio energy in this window; "
                "check manually"
            )

    counts = {
        key: sum(
            1 for row in rows
            if row["status"] == key
        )
        for key in (
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
            "aligned with differences or estimates"
        )

    if counts["unmatched"]:
        status = "FAIL"

        reasons.append(
            f"{counts['unmatched']} word(s) "
            "could not be matched"
        )

    if ratio < alignment["_min_sentence"]:
        status = "FAIL"

        reasons.append(
            f"sentence match ratio {ratio:.2f} "
            f"< {alignment['_min_sentence']}"
        )

    summary = {
        "status": status,
        "reasons": reasons,
        "match_ratio": round(ratio, 3),
        "counts": counts,
    }

    if onset is not None and timed:
        summary["first_word_vs_speech_onset_ms"] = round(
            (
                timed[0]["start"]
                - offset
                - onset
            ) * 1000
        )

        summary["last_word_vs_speech_end_ms"] = round(
            (
                timed[-1]["end"]
                - offset
                - speech_end
            ) * 1000
        )

    timing = {
        "stage": 0,
        "timestamp_reference": "narration.wav",
        "transcript_file": str(
            transcript_path.relative_to(ROOT)
        ),
        "audio": meta,
        "sentence": {
            "id": sentence["id"],
            "text": sentence["text"],
            "offset": offset,
            "duration": speech_duration,
            "words": rows,
        },
        "summary": summary,
    }

    BUILD.mkdir(
        parents=True,
        exist_ok=True
    )

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
        f"(minimum {alignment['_min_sentence']})",
        "- timestamp reference: narration.wav",
        f"- lead-in: {offset:.3f}s",
        (
            f"- words: exact {counts['exact']}, "
            f"aligned {counts['aligned']}, "
            f"unmatched {counts['unmatched']}, "
            f"skipped {counts['skipped']}"
        ),
    ]

    for key in (
        "first_word_vs_speech_onset_ms",
        "last_word_vs_speech_end_ms"
    ):
        if key in summary:
            lines.append(
                f"- {key}: {summary[key]} ms"
            )

    lines.extend(
        f"- {reason}"
        for reason in reasons
    )

    lines.extend([
        "",
        "| # | script word | recognized | start s | end s | status | note |",
        "|---|---|---|---|---|---|---|",
    ])

    for row in rows:
        lines.append(
            f"| {row['i']} | {row['text']} | "
            f"{' + '.join(row['recognized'])} | "
            f"{row['abs_start'] if row['abs_start'] is not None else '-'} | "
            f"{row['abs_end'] if row['abs_end'] is not None else '-'} | "
            f"{row['status']} | "
            f"{'; '.join(row['notes'])} |"
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
# compose
# --------------------------------------------------------------------------

def srt_time(seconds):
    milliseconds = int(round(seconds * 1000))

    return (
        f"{milliseconds // 3600000:02d}:"
        f"{milliseconds // 60000 % 60:02d}:"
        f"{milliseconds // 1000 % 60:02d},"
        f"{milliseconds % 1000:03d}"
    )


def cmd_compose(_a):
    cfg, script = load_inputs()

    validate_basic(cfg, script)

    timing = load_json(
        BUILD / "timing.json"
    )

    if timing["summary"]["status"] == "FAIL":
        die(
            "timing status is FAIL; refusing to build "
            "a video from unreliable timestamps.",
            3
        )

    sentence = timing["sentence"]
    total = float(timing["audio"]["total"])

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
            "assets/fonts/*.woff2 not found; "
            "the font installation step must run first"
        )

    for font in fonts:
        shutil.copyfile(
            font,
            story / "assets" / "fonts" / font.name
        )

    shutil.copyfile(
        BUILD / "narration.wav",
        story / "narration.wav"
    )

    spans = []
    timeline_words = []

    for row in sentence["words"]:
        word_id = (
            f"w-{sentence['id']}-{row['i']}"
        )

        spans.append(
            f'<span class="w" id="{word_id}">'
            f'{html.escape(row["text"])}'
            f'</span>'
        )

        if row["abs_start"] is not None:
            timeline_words.append({
                "id": word_id,
                "start": row["abs_start"],
                "end": row["abs_end"],
            })

    if not timeline_words:
        die(
            "No usable word timestamps were produced; "
            "refusing to build an empty timeline.",
            3
        )

    sentence_html = (
        f'<div class="sentence" '
        f'id="sent-{sentence["id"]}">'
        f'{" ".join(spans)}'
        f'</div>'
    )

    data = {
        "duration": round(total, 3),
        "sentences": [
            {
                "id": sentence["id"],
                "start": timeline_words[0]["start"],
                "end": timeline_words[-1]["end"],
                "words": timeline_words,
            }
        ],
    }

    data_js = json.dumps(
        data,
        ensure_ascii=False
    ).replace(
        "<",
        "\\u003c"
    )

    template_path = STORY / "template.html"

    try:
        template = template_path.read_text(
            encoding="utf-8"
        )
    except OSError as e:
        die(f"cannot read template.html: {e}")

    required = (
        "__DURATION__",
        "__SENTENCES_HTML__",
        "__TIMELINE_JSON__",
    )

    for placeholder in required:
        if placeholder not in template:
            die(
                f"template is missing placeholder {placeholder}"
            )

    page = (
        template
        .replace(
            "__DURATION__",
            f"{total:.3f}"
        )
        .replace(
            "__SENTENCES_HTML__",
            sentence_html
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
        "1\n"
        f"{srt_time(timeline_words[0]['start'])} --> "
        f"{srt_time(timeline_words[-1]['end'] + 0.15)}\n"
        f"{sentence['text']}\n"
    )

    (BUILD / "story.srt").write_text(
        cue,
        encoding="utf-8"
    )

    print(
        f"Composition written to {story / 'index.html'} "
        f"(duration {total:.2f}s, "
        f"{len(timeline_words)} timed words)."
    )


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

SEA = (79, 209, 197)


def sea_pixels(mp4, seconds, width=270, height=480):
    raw = run([
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{max(0, seconds):.3f}",
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:{height}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ])

    count = 0
    sx = 0
    sy = 0

    limit = min(
        len(raw),
        width * height * 3
    )

    for position in range(
        0,
        limit - 2,
        3
    ):
        if (
            abs(raw[position] - SEA[0]) < 26
            and abs(raw[position + 1] - SEA[1]) < 26
            and abs(raw[position + 2] - SEA[2]) < 26
        ):
            pixel = position // 3

            count += 1
            sx += pixel % width
            sy += pixel // width

    return (
        count,
        round(sx / count / width, 3) if count else None,
        round(sy / count / height, 3) if count else None,
    )


def parse_fps(value):
    if not isinstance(value, str) or "/" not in value:
        return None

    try:
        numerator, denominator = map(
            int,
            value.split("/", 1)
        )

        if denominator == 0:
            return None

        result = numerator / denominator

        return result if math.isfinite(result) else None

    except (ValueError, ZeroDivisionError):
        return None


def cmd_verify(_a):
    BUILD.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {
        "problems": [],
    }

    try:
        timing = load_json(
            BUILD / "timing.json"
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

        streams = probe.get("streams", [])

        video = [
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
        ]

        audio = [
            stream
            for stream in streams
            if stream.get("codec_type") == "audio"
        ]

        duration = finite_number(
            probe["format"]["duration"],
            "MP4 duration",
            0.1
        )

        expected = finite_number(
            timing["audio"]["total"],
            "expected audio duration",
            0.1
        )

        result.update({
            "size_bytes": mp4.stat().st_size,
            "duration": round(duration, 3),
            "expected_duration": round(expected, 3),
            "video": [],
            "audio": [],
        })

        if not video:
            result["problems"].append(
                "no video stream"
            )

        if not audio:
            result["problems"].append(
                "no audio stream"
            )

        if video:
            stream = video[0]

            result["video"] = [{
                "codec": stream.get("codec_name"),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "fps": stream.get("avg_frame_rate"),
                "r_frame_rate": stream.get("r_frame_rate"),
            }]

            if (
                stream.get("width") != 1080
                or stream.get("height") != 1920
            ):
                result["problems"].append(
                    "wrong video dimensions; expected 1080x1920"
                )

            fps = (
                parse_fps(stream.get("avg_frame_rate"))
                or parse_fps(stream.get("r_frame_rate"))
            )

            if fps is None:
                result["problems"].append(
                    "could not parse video frame rate"
                )
            elif abs(fps - 30) > 0.1:
                result["problems"].append(
                    f"wrong frame rate: {fps:.2f} fps"
                )

        if audio:
            result["audio"] = [
                {
                    "codec": stream.get("codec_name"),
                    "sample_rate": stream.get("sample_rate"),
                }
                for stream in audio
            ]

        if abs(duration - expected) > 0.3:
            result["problems"].append(
                f"duration {duration:.2f}s differs "
                f"from narration {expected:.2f}s"
            )

        timed = [
            row
            for row in timing["sentence"]["words"]
            if row.get("abs_start") is not None
        ]

        if audio:
            audio_path = BUILD / "mp4_audio.wav"

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
                str(audio_path),
            ])

            onset, _, _, _ = speech_bounds(
                audio_path
            )

            if onset is not None and timed:
                result["mp4_audio_onset_vs_first_word_ms"] = round(
                    (
                        timed[0]["abs_start"]
                        - onset
                    ) * 1000
                )

        frames_dir = BUILD / "frames"

        frames_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        highlights = []

        if video:
            for row in timed:
                midpoint = (
                    row["abs_start"] + row["abs_end"]
                ) / 2

                count, center_x, center_y = sea_pixels(
                    mp4,
                    midpoint
                )

                highlights.append({
                    "i": row["i"],
                    "text": row["text"],
                    "time": round(midpoint, 3),
                    "highlight_pixels": count,
                    "x": center_x,
                    "y": center_y,
                })

                if count < 150:
                    result["problems"].append(
                        f"no highlight visible for word "
                        f"{row['i']} at {midpoint:.2f}s"
                    )

                run([
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-ss",
                    f"{midpoint:.3f}",
                    "-i",
                    str(mp4),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=540:-1",
                    str(
                        frames_dir
                        / f"word_{row['i']:02d}.png"
                    ),
                ])

            result["highlight"] = highlights

        result["verification_complete"] = True

    except SystemExit as error:
        result["verification_complete"] = False
        result["problems"].append(
            f"verification stopped with exit code {error.code}"
        )

        (BUILD / "verify.json").write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8",
        )

        raise

    except Exception as error:
        result["verification_complete"] = False
        result["problems"].append(
            f"verification exception: {type(error).__name__}: {error}"
        )

        (BUILD / "verify.json").write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8",
        )

        die(
            "verification could not be completed; "
            "see verify.json",
            4
        )

    (BUILD / "verify.json").write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    if result["problems"]:
        die(
            "verification problems: "
            + "; ".join(result["problems"]),
            4
        )

    print("VERIFY OK")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(
        dest="cmd",
        required=True
    )

    for name, function in (
        ("check", cmd_check),
        ("tts", cmd_tts),
        ("prepare", cmd_prepare),
        ("align", cmd_align),
        ("compose", cmd_compose),
        ("verify", cmd_verify),
    ):
        subparsers.add_parser(name).set_defaults(
            fn=function
        )

    args = parser.parse_args()

    args.fn(args)


if __name__ == "__main__":
    main()
