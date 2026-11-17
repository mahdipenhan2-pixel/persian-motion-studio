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


DOC_DIR = Path(__file__).resolve().parent

SCRIPT_FILE = DOC_DIR / "script.json"
OUTPUT_DIR = DOC_DIR / "output" / "audio"
CACHE_DIR = DOC_DIR / ".cache" / "voice"

MODEL = os.getenv(
    "GEMINI_TTS_MODEL",
    "gemini-3.8-flash-tts"
)

VOICE = os.getenv(
    "GEMINI_TTS_VOICE",
    "Charon"
)

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
        raise FileNotFoundError(
            f"Missing script: {SCRIPT_FILE}"
        )

    with SCRIPT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError(
            "script.json must contain a non-empty scenes list."
        )

    for scene in scenes:
        if not scene.get("id"):
            raise ValueError("A scene is missing its id.")

        if not scene.get("narration", "").strip():
            raise ValueError(
                f"Scene {scene.get('id')} has no narration."
            )

    return scenes


def cache_filename(text):
    content = (
        MODEL + "|" +
        VOICE + "|" +
        STYLE + "|" +
        text
    )

    digest = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    return CACHE_DIR / f"{digest}.wav"


def generate_audio(text, api_key):
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": text,
                        "speechMetadata": {
                            "style": STYLE
                        }
                    }
                ]
            }
        ],
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
            f"Gemini API error ({error.code}): {details}"
        )

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Network error: {error.reason}"
        )

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini returned no audio candidates."
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    for part in parts:
        audio_data = (
            part.get("inlineData", {})
            .get("data")
        )

        if audio_data:
            audio_bytes = base64.b64decode(
                audio_data
            )

            if not audio_bytes.startswith(b"RIFF"):
                raise RuntimeError(
                    "The returned audio is not a valid WAV file."
                )

            return audio_bytes

    raise RuntimeError(
        "No audio data found in Gemini response."
    )


def process_scene(scene, api_key):
    scene_id = scene["id"]
    narration = scene["narration"].strip()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / f"{scene_id}.wav"
    cached_file = cache_filename(narration)

    if cached_file.exists():
        print(f"[CACHE HIT] {scene_id}")

        shutil.copy2(
            cached_file,
            output_file
        )

        return

    print(f"[GENERATING] {scene_id}")

    audio = generate_audio(
        narration,
        api_key
    )

    cached_file.write_bytes(audio)
    shutil.copy2(cached_file, output_file)

    print(f"[SAVED] {output_file}")

    time.sleep(2)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scene",
        help="Generate only one scene by its ID."
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate audio for all scenes."
    )

    args = parser.parse_args()

    scenes = load_script()

    if args.all and args.scene:
        raise ValueError(
            "Use either --all or --scene, not both."
        )

    if args.scene:
        scenes = [
            scene for scene in scenes
            if scene["id"] == args.scene
        ]

        if not scenes:
            raise ValueError(
                f"Scene not found: {args.scene}"
            )

    elif not args.all:
        scenes = scenes[:1]

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is missing."
        )

    for scene in scenes:
        process_scene(scene, api_key)

    print("\nVOICE GENERATION COMPLETED.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
