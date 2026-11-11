#!/usr/bin/env python3
"""
Stage 2: per-sentence Persian word timestamps with faster-whisper.

Runs inside the .venv-whisper virtual environment (see story-stage2.yml).
Whisper only supplies TIMING. The displayed text always comes from the script.
Results are cached by audio hash, so unchanged sentences are never re-transcribed.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "stage2"
CACHE = ROOT / ".cache" / "story" / "whisper"
CONFIG = ROOT / "story" / "config.stage2.json"


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["whisper"]
    model_name = str(cfg.get("model", "small"))
    language = str(cfg.get("language", "fa"))
    compute = str(cfg.get("compute_type", "int8"))
    inputs = sorted((BUILD / "whisper_in").glob("*.wav"))
    if not inputs:
        sys.exit("ERROR: no files in build/stage2/whisper_in")
    out_dir = BUILD / "whisper"
    out_dir.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    model = None
    empty = []
    for wav in inputs:
        sid = wav.stem
        key = hashlib.sha256(
            wav.read_bytes() + f"|v1|{model_name}|{language}|{compute}".encode("utf-8")
        ).hexdigest()
        cached = CACHE / f"{key}.json"
        if cached.exists():
            print(f"{sid}: whisper cache hit ({key[:12]})")
        else:
            if model is None:
                from faster_whisper import WhisperModel
                print(f"Loading Whisper model '{model_name}' ({compute}, CPU) ...")
                model = WhisperModel(model_name, device="cpu", compute_type=compute)
            segments, info = model.transcribe(
                str(wav), language=language, word_timestamps=True,
                condition_on_previous_text=False,
            )
            words = []
            for seg in segments:
                for w in seg.words or []:
                    words.append({"text": w.word, "start": float(w.start), "end": float(w.end)})
            tmp = cached.with_suffix(".tmp")
            tmp.write_text(json.dumps({"language": info.language, "words": words},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(cached)
            print(f"{sid}: transcribed {len(words)} words")
        shutil.copyfile(cached, out_dir / f"{sid}.json")
        if not json.loads(cached.read_text(encoding="utf-8"))["words"]:
            empty.append(sid)
    if empty:
        sys.exit(f"ERROR: Whisper returned no words for: {', '.join(empty)}")


if __name__ == "__main__":
    main()
