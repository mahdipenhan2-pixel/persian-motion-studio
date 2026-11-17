import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SCRIPT_FILE = ROOT / "script.json"
OUTPUT_DIR = ROOT / "output" / "audio"
CACHE_DIR = ROOT / ".cache" / "voice"

MODEL = "gemini-3.8-flash-tts"
VOICE = "Charon"

STYLE = (
    "Deep male cinematic documentary narrator. "
    "Calm, serious, powerful and emotionally engaging. "
    "Natural Persian pronunciation, clear articulation, "
    "measured pace, dramatic pauses, professional narration."
)

API_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)


def load_script():
    if not SCRIPT_FILE.exists():
        raise FileNotFoundError("documentary/script.json not found")

    with SCRIPT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("script.json has no scenes")

    for scene in scenes:
        if not scene.get("id"):
            raise ValueError("A scene is missing its id")

        narration = scene.get("narration")

        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(
                f"Scene {scene.get('id')} has no narration"
            )

    return scenes


def cache_path(text):
    content = f"{MODEL}|{VOICE}|{STYLE}|{text}"
    digest = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    return CACHE_DIR / f"{digest}.wav"


def generate_audio(text, api_key):
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{
                "text": text,
                "speechMetadata": {
                    "style": STYLE
                }
            }]
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "voice": VOICE
                }
            }
        }
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=180
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        details = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"Gemini API error {error.code}: {details}"
        )

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Network error: {error.reason}"
        )

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError("Gemini returned no audio")

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    for part in parts:
        audio_data = (
            part.get("inlineData", {}).get("data")
        )

        if audio_data:
            audio = base64.b64decode(audio_data)

            if not audio.startswith(b"RIFF"):
                raise RuntimeError(
                    "Expected WAV audio, but received another format"
                )

            return audio

    raise RuntimeError("No audio data found in response")


def process_scene(scene, api_key):
    scene_id = scene["id"]
    narration = scene["narration"].strip()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / f"{scene_id}.wav"
    cached_file = cache_path(narration)

    if cached_file.exists():
        print(f"[CACHE HIT] {scene_id}")
        shutil.copy2(cached_file, output_file)
        return

    if output_file.exists():
        print(f"[EXISTS] {scene_id}")
        return

    print(f"[GENERATING] {scene_id}")

    audio = generate_audio(narration, api_key)

    cached_file.write_bytes(audio)
    shutil.copy2(cached_file, output_file)

    print(f"[SAVED] {output_file}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scene",
        help="Generate one scene by ID"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all scenes"
    )

    args = parser.parse_args()

    if args.scene and args.all:
        raise ValueError("Choose --scene or --all")

    scenes = load_script()

    if args.scene:
        scenes = [
            s for s in scenes
            if s["id"] == args.scene
        ]

        if not scenes:
            raise ValueError("Scene ID not found")

    elif not args.all:
        scenes = scenes[:1]

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from environment"
        )

    for scene in scenes:
        process_scene(scene, api_key)

    print("\nVOICE GENERATION COMPLETED")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
