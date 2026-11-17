import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCRIPT_FILE = ROOT / "script.json"
OUTPUT_DIR = ROOT / "output" / "audio"
CACHE_DIR = ROOT / ".cache" / "voice"

MODEL = "gemini-3.8-flash-lite-tts"
VOICE = "Charon"

STYLE = (
    "Speak in Persian (Farsi). "
    "Deep male cinematic documentary narrator. "
    "Calm, serious, authoritative and emotionally engaging. "
    "Natural Persian pronunciation, clear articulation, "
    "measured pace and professional documentary delivery."
)

API_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/interactions"
)


def load_scenes():
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


def cache_file(text):
    source = f"{MODEL}|{VOICE}|{STYLE}|{text}"

    digest = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()

    return CACHE_DIR / f"{digest}.wav"


def generate_audio(text, api_key):
    payload = {
        "model": MODEL,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": STYLE
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
                    "voice": VOICE
                }
            ]
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
            timeout=240
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

    audio_data = (
       result.get("output_audio", {}).get("data").  
    )

    audio = base64.b64decode(audio_data)

    if not audio.startswith(b"RIFF"):
        raise RuntimeError(
            "Expected WAV audio but received another format"
        )

    return audio


def process_scene(scene, api_key):
    scene_id = scene["id"]
    narration = scene["narration"].strip()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    output = OUTPUT_DIR / f"{scene_id}.wav"
    cached = cache_file(narration)

    if cached.exists():
        print(f"[CACHE HIT] {scene_id}")
        shutil.copy2(cached, output)
        return

    if output.exists():
        print(f"[EXISTS] {scene_id}")
        return

    print(f"[GENERATING] {scene_id}")

    audio = generate_audio(narration, api_key)

    cached.write_bytes(audio)
    shutil.copy2(cached, output)

    print(f"[SAVED] {output}")


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

    scenes = load_scenes()

    if args.scene:
        scenes = [
            scene for scene in scenes
            if scene["id"] == args.scene
        ]

        if not scenes:
            raise ValueError("Scene ID not found")

    elif not args.all:
        scenes = scenes[:1]

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing"
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
