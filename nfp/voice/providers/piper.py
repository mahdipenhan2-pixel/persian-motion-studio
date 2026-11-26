"""Piper provider: real speech from a local, free Piper voice (https://github.com/rhasspy/piper; ONNX, offline, no key,
no request). A voice in the registry names its model: {"provider": "piper", "params": {"model": "fa_IR-amir-medium"}}.

Models are read from ONE fixed folder - $NFP_PIPER_DIR, else ROOT/assets/voices/piper - filled by
nfp/setup/fetch_assets.py (downloads never happen here: a missing model is refused with the command that fetches it).
Each sentence: the text through `python -m piper` -> WAV at the voice's own rate -> mono 16-bit at the run's rate
(ffmpeg, as nfp/voice/normalize.convert) -> the planned pauses around it. The model file's sha256 is part of the plan's
cache key, so another model never reuses old audio.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .base import ProviderError, silence, write_wav

ROOT = Path(__file__).resolve().parents[3]


def model_dir():
    return Path(os.environ.get("NFP_PIPER_DIR") or ROOT / "assets" / "voices" / "piper")


def model_path(name):
    if not isinstance(name, str) or not name or "/" in name or "\\" in name or name.startswith("."):
        raise ProviderError(f"piper: bad model name {name!r}")
    p = model_dir() / f"{name}.onnx"
    if not p.is_file() or not p.with_suffix(".onnx.json").is_file():
        raise ProviderError(f"piper: model '{name}' not found in {model_dir()} - fetch it with "
                            "`python3 nfp/setup/fetch_assets.py --only piper` (free, from huggingface.co)")
    return p


def available():
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return False


class PiperProvider:
    name = "piper"

    def produce(self, row, out_path, rate, base_dir="."):
        if not available():
            raise ProviderError("piper: the piper-tts package is not installed (pip install -r nfp/setup/requirements.txt)")
        src = row["source"]
        model = model_path(src["model"])
        from ..normalize import convert
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "piper.wav"
            cmd = [sys.executable, "-m", "piper", "-m", str(model), "-f", str(raw)]
            if src.get("length_scale"):
                cmd += ["--length-scale", str(src["length_scale"])]
            r = subprocess.run(cmd, input=row["text"], capture_output=True, text=True, timeout=600)
            if r.returncode != 0 or not raw.is_file() or raw.stat().st_size <= 44:
                raise ProviderError(f"piper: synthesis failed ({(r.stderr or r.stdout).strip()[-300:]})")
            pcm, cinfo = convert(raw, rate)
        if len(pcm) < 2 * int(0.3 * rate):
            raise ProviderError(f"piper: {len(pcm) / 2 / rate:.2f}s of audio for '{row['text'][:40]}' - too short to be speech")
        info = write_wav(out_path, silence(row["pause_before_ms"] / 1000, rate) + pcm + silence(row["pause_after_ms"] / 1000, rate), rate)
        info["source_rate"] = cinfo["input"]["rate"]
        info["model"] = src["model"]
        return info
