"""Prepared provider: a ready recording per sentence (a person's voice, an earlier TTS run, a licensed file).

The file must already be mono 16-bit PCM at the run's rate: this version does not convert (resampling / channel
mix / loudness are the next stage, render.py, with ffmpeg). A file in another format is refused with a clear
message that says what to convert. The planned pauses are added as silence around the recording; the recording's
samples are copied unchanged, and the source file's sha256 must still equal the one in the plan.
"""
from pathlib import Path

from .base import ProviderError, read_wav, silence, write_wav

MIN_S, MAX_S = 0.3, 60.0          # the same per-sentence bounds the Stage 2 core checks


class PreparedProvider:
    name = "prepared"

    def produce(self, row, out_path, rate, base_dir="."):
        from ..plan import sha256_file
        f = Path(base_dir) / row["source"]["file"]
        if sha256_file(f) != row["source"]["sha256"]:
            raise ProviderError(f"{row['id']}: '{row['source']['file']}' changed after planning (sha256 differs); plan again")
        w = read_wav(f)
        if w["channels"] != 1 or w["sample_width"] != 2:
            raise ProviderError(f"{row['id']}: '{row['source']['file']}' is {w['channels']} channel(s), {8 * w['sample_width']}-bit; "
                                "it must be converted to mono 16-bit PCM first")
        if w["rate"] != rate:
            raise ProviderError(f"{row['id']}: '{row['source']['file']}' is {w['rate']} Hz but this run is {rate} Hz; "
                                "it must be resampled first (all sentences of a video need one sample rate)")
        dur = w["frames"] / w["rate"]
        if not MIN_S <= dur <= MAX_S:
            raise ProviderError(f"{row['id']}: recording is {dur:.2f}s; a sentence must be {MIN_S}-{MAX_S}s")
        pcm = silence(row["pause_before_ms"] / 1000, rate) + w["pcm"] + silence(row["pause_after_ms"] / 1000, rate)
        info = write_wav(out_path, pcm, rate)
        info["source_rate"] = w["rate"]
        info["source_frames"] = w["frames"]
        return info
