#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFP Story Studio - Stage 1
Independent multi-sentence production engine.
Commands:
    check
    tts
    prepare
    transcribe
    align
    compose
    verify
"""
from __future__ import annotations
import base64
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
# ==================================================
# PATHS
# ==================================================
ROOT = Path(__file__).resolve().parent.parent
STORY = ROOT / "story"
BUILD = ROOT / "build" / "stage1"
CACHE = ROOT / ".cache" / "story" / "stage1" / "audio"
SCRIPT_PATH = STORY / "script.stage1.json"
CONFIG_PATH = STORY / "config.stage1.json"
TEMPLATE_PATH = STORY / "template.stage1.html"
WHISPER_DIR = BUILD / "whisper"
WHISPER_JSON = WHISPER_DIR / "transcript.json"
AUDIO_FILE = BUILD / "narration.wav"
WHISPER_AUDIO = BUILD / "whisper_input.wav"
TIMING_FILE = BUILD / "timing.json"
TIMING_REPORT = BUILD / "timing_report.md"
COMPOSE_DIR = BUILD / "story"
COMPOSE_HTML = COMPOSE_DIR / "index.html"
VIDEO_FILE = BUILD / "story.mp4"
VERIFY_FILE = BUILD / "verify.json"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/interactions"
)
ALLOWED_MODELS = {
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
}
# ==================================================
# GENERAL HELPERS
# ==================================================
def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)
def info(message: str) -> None:
    print(f"[STAGE 1] {message}")
def load_json(path: Path) -> dict:
    if not path.is_file():
        die(f"File not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        die(f"Could not read JSON {path}: {exc}")
def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )
def run_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout
    except FileNotFoundError:
        die(f"Command not found: {command[0]}")
    except subprocess.CalledProcessError as exc:
        die(
            f"Command failed: {' '.join(command)}\n"
            f"{exc.stderr}"
        )
def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        die(f"Required executable not found: {name}")
def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )
def normalize_fa(text: str) -> str:
    replacements = {
        "ي": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "\u0640": "",
        "\u200c": " ",
        "\u200f": "",
        "\u200e": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
def get_sentences() -> list[dict]:
    data = load_json(SCRIPT_PATH)
    sentences = data.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        die("The script must contain a non-empty sentences array.")
    return sentences
def get_config() -> dict:
    return load_json(CONFIG_PATH)
def build_narration_text(sentences: list[dict]) -> str:
    return "\n".join(
        sentence["text"].strip()
        for sentence in sentences
    )
# ==================================================
# WAV HELPERS
# ==================================================
def validate_wav(path: Path) -> dict:
    if not path.is_file():
        die(f"Audio file missing: {path}")
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            frames = wav.getnframes()
            sample_width = wav.getsampwidth()
            if channels < 1 or sample_rate < 1:
                die("Invalid WAV audio properties.")
            duration = frames / float(sample_rate)
            if duration <= 0:
                die("WAV file has zero duration.")
            return {
                "channels": channels,
                "sample_rate": sample_rate,
                "frames": frames,
                "sample_width": sample_width,
                "duration": duration
            }
    except wave.Error as exc:
        die(f"Invalid WAV file: {exc}")
# ==================================================
# VALIDATION
# ==================================================
def check() -> None:
    info("Checking Stage 1 inputs...")
    config = get_config()
    sentences = get_sentences()
    tts_config = config.get("tts", {})
    video_config = config.get("video", {})
    model = tts_config.get("model")
    if model not in ALLOWED_MODELS:
        die(f"TTS model is not approved: {model}")
    if not tts_config.get("voice"):
        die("TTS voice is missing.")
    if len(sentences) < 2:
        die("Stage 1 requires at least TWO sentences.")
    if len(sentences) > 30:
        die("Stage 1 allows a maximum of 30 sentences.")
    ids = set()
    total_chars = 0
    for sentence in sentences:
        sid = sentence.get("id")
        text = sentence.get("text", "").strip()
        if not sid or not text:
            die("Every sentence requires an id and text.")
        if sid in ids:
            die(f"Duplicate sentence id: {sid}")
        ids.add(sid)
        total_chars += len(text)
    if total_chars < 20:
        die("The complete narration text is too short.")
    width = int(video_config.get("width", 1080))
    height = int(video_config.get("height", 1920))
    fps = int(video_config.get("fps", 30))
    duration = int(video_config.get("duration_sec", 60))
    if width != 1080 or height != 1920:
        die("Stage 1 requires 1080x1920 video.")
    if fps != 30:
        die("Stage 1 requires 30 FPS.")
    if duration < 10 or duration > 60:
        die("Target duration must be between 10 and 60 seconds.")
    if int(tts_config.get("max_attempts", 1)) < 1:
        die("Invalid TTS max_attempts setting.")
    if int(tts_config.get("max_requests_per_run", 1)) < 1:
        die("Invalid TTS request limit.")
    info(f"Sentences: {len(sentences)}")
    info(f"Characters: {total_chars}")
    info(f"Target duration: {duration} seconds")
    info("Input validation successful.")
# ==================================================
# GEMINI TTS
# ==================================================
def extract_audio_from_response(data: dict) -> bytes:
    output_audio = data.get("output_audio")
    if not isinstance(output_audio, dict):
        die("Gemini response has no output_audio object.")
    encoded = output_audio.get("data")
    if not isinstance(encoded, str) or not encoded:
        die("Gemini response has no audio data.")
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as exc:
        die(f"Could not decode Gemini audio: {exc}")
def tts() -> None:
    info("Preparing Stage 1 narration...")
    check()
    config = get_config()
    sentences = get_sentences()
    tts_config = config["tts"]
    model = tts_config["model"]
    voice = tts_config["voice"]
    style = tts_config.get(
        "style",
        "clear, natural Persian narration"
    )
    narration = build_narration_text(sentences)
    digest = sha256_text(
        json.dumps(
            {
                "text": narration,
                "model": model,
                "voice": voice,
                "style": style
            },
            ensure_ascii=False,
            sort_keys=True
        )
    )
    CACHE.mkdir(parents=True, exist_ok=True)
    cached_audio = CACHE / f"{digest}.wav"
    if cached_audio.is_file():
        validate_wav(cached_audio)
        BUILD.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached_audio, AUDIO_FILE)
        info("Narration restored from cache.")
        return
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        die("GEMINI_API_KEY environment variable is missing.")
    max_attempts = int(
        tts_config.get("max_attempts", 4)
    )
    max_requests = int(
        tts_config.get("max_requests_per_run", 4)
    )
    timeout = int(
        tts_config.get("timeout_sec", 120)
    )
    # One API request for the complete narration.
    if max_requests < 1:
        die("TTS request limit must be at least one.")
    max_attempts = min(max_attempts, max_requests)
    payload = {
        "model": model,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": narration,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": style
                            }
                        ]
                    }
                ]
            }
        ],
        "response_format": {
            "type": "audio"
        },
        "generation_config": {
            "speech_config": [
                {
                    "voice": voice
                }
            ]
        }
    }
    request = urllib.request.Request(
        GEMINI_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )
    last_error = None
    for attempt in range(1, max_attempts + 1):
        info(f"Gemini TTS attempt {attempt}/{max_attempts}")
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout
            ) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )
            audio_data = extract_audio_from_response(
                response_data
            )
            if audio_data[:4] != b"RIFF":
                raise RuntimeError(
                    "Expected a WAV response from Gemini."
                )
            BUILD.mkdir(parents=True, exist_ok=True)
            AUDIO_FILE.write_bytes(audio_data)
            audio_info = validate_wav(AUDIO_FILE)
            shutil.copy2(AUDIO_FILE, cached_audio)
            save_json(
                BUILD / "tts_meta.json",
                {
                    "model": model,
                    "voice": voice,
                    "text_sha256": digest,
                    "audio_duration": audio_info["duration"],
                    "cached": False
                }
            )
            info("Narration generated successfully.")
            return
        except urllib.error.HTTPError as exc:
            last_error = (
                f"HTTP {exc.code}: "
                f"{exc.read().decode('utf-8', errors='replace')}"
            )
        except Exception as exc:
            last_error = str(exc)
        if attempt < max_attempts:
            time.sleep(min(2 ** attempt, 10))
    die(f"Gemini TTS failed: {last_error}")
# ==================================================
# AUDIO PREPARATION
# ==================================================
def prepare() -> None:
    info("Preparing audio for Whisper...")
    if not AUDIO_FILE.is_file():
        die("Narration audio missing. Run tts first.")
    validate_wav(AUDIO_FILE)
    config = get_config()
    audio_config = config.get("audio", {})
    lead_ms = int(audio_config.get("lead_in_ms", 300))
    tail_ms = int(audio_config.get("tail_ms", 800))
    if lead_ms < 0 or tail_ms < 0:
        die("Audio padding values cannot be negative.")
    BUILD.mkdir(parents=True, exist_ok=True)
    source = BUILD / "narration_48k.wav"
    lead = BUILD / "lead.wav"
    tail = BUILD / "tail.wav"
    padded = BUILD / "padded.wav"
    run_command([
        "ffmpeg", "-y",
        "-i", str(AUDIO_FILE),
        "-ac", "1",
        "-ar", "48000",
        "-c:a", "pcm_s16le",
        str(source)
    ])
    run_command([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=48000:cl=mono",
        "-t", str(lead_ms / 1000),
        "-c:a", "pcm_s16le",
        str(lead)
    ])
    run_command([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=48000:cl=mono",
        "-t", str(tail_ms / 1000),
        "-c:a", "pcm_s16le",
        str(tail)
    ])
    run_command([
        "ffmpeg", "-y",
        "-i", str(lead),
        "-i", str(source),
        "-i", str(tail),
        "-filter_complex",
        "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]",
        "-c:a", "pcm_s16le",
        str(padded)
    ])
    shutil.copy2(padded, AUDIO_FILE)
    run_command([
        "ffmpeg", "-y",
        "-i", str(AUDIO_FILE),
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(WHISPER_AUDIO)
    ])
    duration = validate_wav(AUDIO_FILE)["duration"]
    save_json(
        BUILD / "audio_meta.json",
        {
            "duration": duration,
            "lead_in_ms": lead_ms,
            "tail_ms": tail_ms,
            "sample_rate": 48000
        }
    )
    info(f"Prepared audio duration: {duration:.2f} seconds.")
# ==================================================
# WHISPER TRANSCRIPTION
# ==================================================
def transcribe() -> None:
    info("Running Persian Whisper transcription...")
    if not WHISPER_AUDIO.is_file():
        die("Whisper input missing. Run prepare first.")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("faster-whisper is not installed.")
    config = get_config()
    whisper_config = config.get("whisper", {})
    model_name = whisper_config.get("model", "small")
    language = whisper_config.get("language", "fa")
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8"
    )
    segments, _ = model.transcribe(
        str(WHISPER_AUDIO),
        language=language,
        word_timestamps=True,
        vad_filter=False
    )
    output_segments = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            words.append({
                "text": word.word.strip(),
                "start": float(word.start),
                "end": float(word.end)
            })
        output_segments.append({
            "start": float(segment.start),
            "end": float(segment.end),
            "text": segment.text.strip(),
            "words": words
        })
    if not output_segments:
        die("Whisper returned no segments.")
    save_json(
        WHISPER_JSON,
        {
            "language": language,
            "segments": output_segments
        }
    )
    info("Whisper transcription completed.")
# ==================================================
# WORD ALIGNMENT
# ==================================================
def load_whisper_words() -> list[dict]:
    data = load_json(WHISPER_JSON)
    words = []
    for segment in data.get("segments", []):
        for word in segment.get("words", []):
            text = str(word.get("text", "")).strip()
            if not text:
                continue
            start = float(word["start"])
            end = float(word["end"])
            if end <= start or start < 0:
                continue
            words.append({
                "text": text,
                "start": start,
                "end": end,
                "normalized": normalize_fa(text)
            })
    if not words:
        die("Whisper returned no usable word timestamps.")
    return words
def align() -> None:
    info("Aligning script with Whisper timestamps...")
    sentences = get_sentences()
    whisper_words = load_whisper_words()
    script_words = []
    for sentence in sentences:
        for token in sentence["text"].split():
            script_words.append({
                "sentence_id": sentence["id"],
                "text": token,
                "normalized": normalize_fa(token)
            })
    script_tokens = [
        item["normalized"] for item in script_words
    ]
    transcript_tokens = [
        item["normalized"] for item in whisper_words
    ]
    similarity = difflib.SequenceMatcher(
        None,
        script_tokens,
        transcript_tokens,
        autojunk=False
    ).ratio()
    config = get_config()
    minimum = float(
        config.get("alignment", {}).get(
            "min_word_match",
            0.6
        )
    )
    if similarity < minimum:
        die(
            f"Script/Whisper match too low: {similarity:.3f}"
        )
    matcher = difflib.SequenceMatcher(
        None,
        script_tokens,
        transcript_tokens,
        autojunk=False
    )
    matched = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            matched[block.a + offset] = block.b + offset
    result_sentences = []
    matched_count = 0
    total_count = len(script_words)
    cursor = 0
    for sentence in sentences:
        sentence_items = []
        while (
            cursor < total_count
            and script_words[cursor]["sentence_id"] == sentence["id"]
        ):
            sentence_items.append(
                (cursor, script_words[cursor])
            )
            cursor += 1
        timed_words = []
        for index, item in sentence_items:
            whisper_index = matched.get(index)
            if whisper_index is None:
                continue
            source = whisper_words[whisper_index]
            start = max(0.0, source["start"])
            end = max(start + 0.06, source["end"])
            timed_words.append({
                "id": f"word-{sentence['id']}-{index:04d}",
                "text": item["text"],
                "start": round(start, 3),
                "end": round(end, 3)
            })
            matched_count += 1
        if not timed_words:
            die(
                f"No words aligned for sentence {sentence['id']}"
            )
        result_sentences.append({
            "id": sentence["id"],
            "text": sentence["text"],
            "start": timed_words[0]["start"],
            "end": timed_words[-1]["end"],
            "words": timed_words
        })
    match_ratio = matched_count / max(1, total_count)
    if match_ratio < minimum:
        die(
            f"Word match ratio too low: {match_ratio:.3f}"
        )
    timing = {
        "language": "fa",
        "duration": validate_wav(AUDIO_FILE)["duration"],
        "match_ratio": round(match_ratio, 4),
        "sentences": result_sentences
    }
    save_json(TIMING_FILE, timing)
    report = [
        "# Stage 1 Timing Report",
        "",
        f"- Sentences: {len(result_sentences)}",
        f"- Script words: {total_count}",
        f"- Matched words: {matched_count}",
        f"- Match ratio: {match_ratio:.3f}",
        "",
        "## Sentence timing",
        ""
    ]
    for sentence in result_sentences:
        report.append(
            f"- {sentence['id']}: "
            f"{sentence['start']:.2f}s - "
            f"{sentence['end']:.2f}s"
        )
    TIMING_REPORT.write_text(
        "\n".join(report),
        encoding="utf-8"
    )
    info(f"Word match ratio: {match_ratio:.3f}")
    info("Alignment completed.")
# ==================================================
# SUBTITLE AND SCENE GENERATION
# ==================================================
def make_sentence_html(
    sentence: dict,
    index: int
) -> str:
    words_html = []
    for word in sentence["words"]:
        words_html.append(
            '<span class="w" '
            f'id="{escape_html(word["id"])}" '
            f'data-start="{word["start"]}" '
            f'data-end="{word["end"]}">'
            f'{escape_html(word["text"])}'
            '</span>'
        )
    return (
        f'<section class="scene scene-{index % 4}" '
        f'id="sent-{escape_html(sentence["id"])}" '
        f'data-scene-index="{index}">'
        f'<div class="scene-number">{index + 1:02d}</div>'
        f'<div class="sentence">'
        + " ".join(words_html)
        + '</div></section>'
    )
def create_srt(timing: dict) -> str:
    def timestamp(seconds: float) -> str:
        milliseconds = int(round(seconds * 1000))
        hours = milliseconds // 3600000
        milliseconds %= 3600000
        minutes = milliseconds // 60000
        milliseconds %= 60000
        secs = milliseconds // 1000
        milliseconds %= 1000
        return (
            f"{hours:02d}:{minutes:02d}:"
            f"{secs:02d},{milliseconds:03d}"
        )
    entries = []
    counter = 1
    for sentence in timing["sentences"]:
        for word in sentence["words"]:
            entries.extend([
                str(counter),
                f"{timestamp(word['start'])} --> "
                f"{timestamp(word['end'])}",
                word["text"],
                ""
            ])
            counter += 1
    return "\n".join(entries)
def compose() -> None:
    info("Building Stage 1 composition...")
    if not TEMPLATE_PATH.is_file():
        die(f"Stage 1 template missing: {TEMPLATE_PATH}")
    if not TIMING_FILE.is_file():
        die("Timing data missing. Run align first.")
    timing = load_json(TIMING_FILE)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    duration = float(timing["duration"])
    if duration <= 0 or duration > 65:
        die("Narration duration is outside the allowed range.")
    scenes_html = []
    for index, sentence in enumerate(timing["sentences"]):
        scenes_html.append(
            make_sentence_html(sentence, index)
        )
    replacements = {
        "__DURATION__": f"{duration:.3f}",
        "__SCENES_HTML__": "\n".join(scenes_html),
        "__TIMELINE_JSON__": json.dumps(
            timing,
            ensure_ascii=False,
            separators=(",", ":")
        )
    }
    for placeholder, value in replacements.items():
        if placeholder not in template:
            die(f"Template placeholder missing: {placeholder}")
        template = template.replace(placeholder, value)
    COMPOSE_DIR.mkdir(parents=True, exist_ok=True)
    COMPOSE_HTML.write_text(
        template,
        encoding="utf-8"
    )
    shutil.copy2(
        AUDIO_FILE,
        COMPOSE_DIR / "narration.wav"
    )
    (BUILD / "story.srt").write_text(
        create_srt(timing),
        encoding="utf-8"
    )
    info(f"Created {len(scenes_html)} scenes.")
    info("Composition ready.")
# ==================================================
# MP4 VERIFICATION
# ==================================================
def verify() -> None:
    info("Verifying Stage 1 MP4...")
    require_tool("ffprobe")
    if not VIDEO_FILE.is_file():
        die(f"Video file not found: {VIDEO_FILE}")
    result = run_command([
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(VIDEO_FILE)
    ])
    data = json.loads(result)
    streams = data.get("streams", [])
    video_stream = next(
        (
            stream for stream in streams
            if stream.get("codec_type") == "video"
        ),
        None
    )
    audio_stream = next(
        (
            stream for stream in streams
            if stream.get("codec_type") == "audio"
        ),
        None
    )
    if not video_stream:
        die("MP4 has no video stream.")
    if not audio_stream:
        die("MP4 has no audio stream.")
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    if width != 1080 or height != 1920:
        die(f"Unexpected dimensions: {width}x{height}")
    duration = float(
        data.get("format", {}).get("duration", 0)
    )
    if duration <= 0 or duration > 65:
        die(f"Unexpected duration: {duration:.2f}s")
    fps_string = video_stream.get("r_frame_rate", "0/1")
    try:
        numerator, denominator = fps_string.split("/")
        fps = float(numerator) / float(denominator)
    except Exception:
        fps = 0.0
    if abs(fps - 30) > 0.1:
        die(f"Unexpected frame rate: {fps:.2f}")
    verification = {
        "verification_complete": True,
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "duration_sec": round(duration, 3),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": audio_stream.get("codec_name"),
        "audio_sample_rate": audio_stream.get("sample_rate"),
        "problems": []
    }
    save_json(VERIFY_FILE, verification)
    info("MP4 verification successful.")
# ==================================================
# COMMAND ROUTER
# ==================================================
COMMANDS = {
    "check": check,
    "tts": tts,
    "prepare": prepare,
    "transcribe": transcribe,
    "align": align,
    "compose": compose,
    "verify": verify
}
def main() -> None:
    if len(sys.argv) != 2:
        die(
            "Usage: python3 scripts/story_stage1.py "
            "<check|tts|prepare|transcribe|align|compose|verify>"
        )
    command = sys.argv[1].strip().lower()
    action = COMMANDS.get(command)
    if action is None:
        die(f"Unknown command: {command}")
    action()
if __name__ == "__main__":
    main()
