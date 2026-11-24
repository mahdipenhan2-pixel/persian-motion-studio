"""Gemini TTS provider (V3) - OFF by default; nothing here sends a request unless every gate below is open.

The request is the same one the locked Stage 2 core sends (scripts/story_stage2.py, synth_once): the Interactions API,
one sentence per request, the voice name from the registry ('gemini:Kore' -> 'Kore'), the style as speech metadata.
The core is not imported (the Voice Engine stays independent); its format is mirrored here.

Gates (all must be open, checked before ANY request):
  1. enabled      the run explicitly enables the provider (produce(..., providers={"gemini": {...}}) / CLI --allow-tts gemini)
  2. free model   the model is on FREE_MODELS (the same allow-list the core uses; checked 2026-11-06 there)
  3. confirmed    GEMINI_FREE_TIER_CONFIRMED=YES in the environment (the same human confirmation the workflows ask for)
  4. key          GEMINI_API_KEY in the environment (never logged, never written; scrubbed from every message)
  5. budget       at most max_requests requests per run; spacing_s seconds between requests
A cache hit never reaches the provider (produce() checks the cache first). HTTP 429 (rate / free-tier quota) stops the
whole run at once: no retry, no fallback model. Already produced sentences stay in the cache.
The network call goes through `transport` (default: urllib), so tests use a fake transport and never touch the network.
"""
import base64
import json
import os
import re
import time

from .base import ProviderError, write_wav

API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
FREE_MODELS = ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview")
DEFAULTS = {"model": "gemini-3.8-flash-tts", "max_requests": 8, "spacing_s": 25.0, "timeout_s": 90}
PCM_RATE = 24000                       # headerless PCM from the API is 24 kHz mono 16-bit (as the core assumes)


class QuotaError(ProviderError):
    """HTTP 429: stop the run, never retry."""


def scrub(text, key):
    text = str(text)
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"(?i)(x-goog-api-key|api[_-]?key|key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)[:400]


def settings(d):
    s = dict(DEFAULTS)
    s.update(d or {})
    extra = sorted(set(s) - set(DEFAULTS))
    if extra:
        raise ProviderError(f"gemini: unknown setting(s) {', '.join(extra)}")
    if s["model"] not in FREE_MODELS:
        raise ProviderError(f"gemini: model '{s['model']}' is not on the free-tier allow-list {list(FREE_MODELS)}")
    if not (isinstance(s["max_requests"], int) and 1 <= s["max_requests"] <= 40):
        raise ProviderError("gemini.max_requests must be an integer 1..40")
    if not (isinstance(s["spacing_s"], (int, float)) and 0 <= s["spacing_s"] <= 120):
        raise ProviderError("gemini.spacing_s must be 0..120 seconds")
    return s


def request_body(model, voice_name, text, style=None):
    item = {"type": "text", "text": text}
    if style:
        item["annotations"] = [{"type": "speech_metadata", "style": style}]
    return {"model": model, "input": [{"type": "user_input", "content": [item]}], "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice_name}]}}


def audio_from_response(data):
    """The audio block of an Interactions response (the last one, as in the documented example / the core)."""
    inter = data.get("interaction", data) if isinstance(data, dict) else None
    if not isinstance(inter, dict):
        return None
    found = None
    oa = inter.get("output_audio")
    if isinstance(oa, dict) and isinstance(oa.get("data"), str) and oa["data"]:
        found = oa["data"]
    for step in inter.get("steps", []) if isinstance(inter.get("steps"), list) else []:
        if isinstance(step, dict) and step.get("type") == "model_output":
            for c in step.get("content", []) if isinstance(step.get("content"), list) else []:
                if isinstance(c, dict) and c.get("type") == "audio" and isinstance(c.get("data"), str) and c["data"]:
                    found = c["data"]
    return found


def urllib_transport(url, headers, body, timeout):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        return 0, str(e).encode()


class GeminiProvider:
    """One instance per run: it carries the budget and the spacing clock."""
    name = "gemini"

    def __init__(self, config=None, transport=None, env=None, sleep=time.sleep, clock=time.monotonic):
        self.s = settings(config)
        self.env = os.environ if env is None else env
        self.transport = transport or urllib_transport
        self.sleep, self.clock = sleep, clock
        self.used, self.last = 0, None

    def check_gates(self):
        if self.env.get("GEMINI_FREE_TIER_CONFIRMED") != "YES":
            raise ProviderError("gemini: stopped before any request - set GEMINI_FREE_TIER_CONFIRMED=YES only after "
                                "checking that the API project has no billing (free tier)")
        if not self.env.get("GEMINI_API_KEY", "").strip():
            raise ProviderError("gemini: GEMINI_API_KEY is not set; no request was sent")

    def produce(self, row, out_path, rate, base_dir=None):
        self.check_gates()
        key = self.env["GEMINI_API_KEY"].strip()
        if self.used >= self.s["max_requests"]:
            raise ProviderError(f"gemini: request budget of this run ({self.s['max_requests']}) is used up; stopping "
                                "(produced sentences stay cached)")
        if self.last is not None and self.s["spacing_s"] > 0:
            wait = self.s["spacing_s"] - (self.clock() - self.last)
            if wait > 0:
                self.sleep(wait)
        voice_name = row["voice"].split(":", 1)[1]
        body = json.dumps(request_body(self.s["model"], voice_name, row["text"], row.get("style"))).encode("utf-8")
        self.used += 1
        status, raw = self.transport(API_URL, {"Content-Type": "application/json", "x-goog-api-key": key}, body,
                                     self.s["timeout_s"])
        self.last = self.clock()
        if status == 429:
            raise QuotaError(f"gemini: HTTP 429 (free-tier quota / rate limit) - the run stops, nothing is retried: "
                             f"{scrub(raw[:300].decode('utf-8', 'replace'), key)}")
        if status != 200:
            raise ProviderError(f"gemini: HTTP {status}: {scrub(raw[:300].decode('utf-8', 'replace'), key)}")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ProviderError("gemini: the response is not valid JSON")
        b64 = audio_from_response(data)
        if not b64:
            raise ProviderError("gemini: the response contains no audio")
        try:
            audio = base64.b64decode(b64, validate=True)
        except ValueError:
            raise ProviderError("gemini: the response audio is not valid base64")
        if not audio:
            raise ProviderError("gemini: the response audio is empty")
        if audio[:4] == b"RIFF":
            out_path.write_bytes(audio)
            from .base import read_wav
            w = read_wav(out_path)
            info = {"rate": w["rate"], "frames": w["frames"], "duration": round(w["frames"] / w["rate"], 6),
                    "channels": w["channels"], "sample_width": w["sample_width"]}
        else:
            if len(audio) % 2:
                raise ProviderError("gemini: headerless PCM audio has an odd length")
            info = write_wav(out_path, audio, PCM_RATE)
            info.update(channels=1, sample_width=2)
        info.update(source_rate=info["rate"], requests_used=self.used, model=self.s["model"])
        return info
