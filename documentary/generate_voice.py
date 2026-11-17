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
# ==========================================
# NFP DOCUMENTARY VOICE ENGINE
# ==========================================
ROOT = Path(__file__).resolve().parent
SCRIPT_FILE = ROOT / "script.json"
OUTPUT_DIR = ROOT / "output" / "audio"
CACHE_DIR = ROOT / ".cache" / "voice"
MODEL = "gemini-3.8-flash-lite-tts"
VOICE = "Charon"
API_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/interactions"
)
STYLE = (
    "Speak naturally in Persian (Farsi). "
    "Deep male cinematic documentary narrator. "
    "Calm, serious, authoritative and emotionally engaging. "
    "Clear Persian pronunciation and articulation. "
    "Measured pace with natural dramatic pauses. "
    "Professional documentary narration."
)
# ==========================================
# LOAD SCRIPT
# ==========================================
def load_scenes():
    if not SCRIPT_FILE.exists():
        raise FileNotFoundError(
            "documentary/script.json not found"
        )
    with SCRIPT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError(
            "script.json contains no scenes"
        )
    for scene in scenes:
        if not scene.get("id"):
            raise ValueError(
                "A scene is missing its ID"
            )
        narration = scene.get("narration")
        if not isinstance(narration, str):
            raise ValueError(
                f"Invalid narration in {scene.get('id')}"
            )
        if not narration.strip():
            raise ValueError(
                f"Empty narration in {scene.get('id')}"
            )
    return scenes
# ==========================================
# AUDIO CACHE
# ==========================================
def get_cache_path(text):
    source = (
        MODEL + "|" +
        VOICE + "|" +
        STYLE + "|" +
        text
    )
    digest = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    return CACHE_DIR / f"{digest}.wav"
# ==========================================
# GEMINI TTS REQUEST
# ==========================================
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
    # ======================================
    # EXTRACT GENERATED AUDIO
    # ======================================
    audio_data = None
    output_audio = result.get("output_audio")
    if isinstance(output_audio, dict):
        audio_data = output_audio.get("data")
    if not audio_data:
        response_data = result.get(
            "interaction",
            result
        )
        for step in response_data.get("steps", []):
            if step.get("type") == "model_output":
                for item in step.get("content", []):
                    if (
                        item.get("type") == "audio"
                        and item.get("data")
                    ):
                        audio_data = item["data"]
                        break
            if audio_data:
                break
    if not audio_data:
        raise RuntimeError(
            "Gemini response contains no audio data"
        )
    # ======================================
    # DECODE AUDIO
    # ======================================
    try:
        audio_bytes = base64.b64decode(
            audio_data,
            validate=True
        )
    except Exception as error:
        raise RuntimeError(
            f"Audio base64 decoding failed: {error}"
        )
    # ======================================
    # VERIFY WAV
    # ======================================
    if not audio_bytes.startswith(b"RIFF"):
        raise RuntimeError(
            "Returned audio is not a valid WAV file"
        )
    return audio_bytes
# ==========================================
# PROCESS ONE SCENE
# ==========================================
def process_scene(scene, api_key):
    scene_id = scene["id"]
    narration = scene["narration"].strip()
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )
    output_file = (
        OUTPUT_DIR / f"{scene_id}.wav"
    )
    cached_file = get_cache_path(narration)
    # Cache first
    if cached_file.exists():
        print(f"[CACHE HIT] {scene_id}")
        shutil.copy2(
            cached_file,
            output_file
        )
        return
    # Existing output
    if output_file.exists():
        print(f"[EXISTS] {scene_id}")
        return
    print(f"[GENERATING] {scene_id}")
    audio = generate_audio(
        narration,
        api_key
    )
    cached_file.write_bytes(audio)
    shutil.copy2(
        cached_file,
        output_file
    )
    print(f"[SAVED] {output_file}")
# ==========================================
# MAIN
# ==========================================
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
        raise ValueError(
            "Choose either --scene or --all"
        )
    scenes = load_scenes()
    if args.scene:
        scenes = [
            scene for scene in scenes
            if scene["id"] == args.scene
        ]
        if not scenes:
            raise ValueError(
                "Requested scene was not found"
            )
    elif not args.all:
        # Default: first scene only
        scenes = scenes[:1]
    # Dedicated documentary API secret
    api_key = os.getenv(
        "GEMINI_DOCUMENTARY_API_KEY"
    )
    if not api_key:
        raise RuntimeError(
            "GEMINI_DOCUMENTARY_API_KEY is missing"
        )
    for scene in scenes:
        process_scene(
            scene,
            api_key
        )
    print(
        "\nNFP DOCUMENTARY VOICE GENERATION COMPLETED"
    )
# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
