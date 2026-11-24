"""Synthetic provider: a deterministic TEST TONE per word (harmonic tone at the voice's f0), no speech.

For offline tests only: file format, sample rate, silence and pauses, mixing several speakers, offsets and durations.
It is never meant for Whisper / word recognition tests (those need real speech: the Alignment test group).
Every word of the text is one burst whose length follows the word length; the burst times are returned as
'synthetic_words' so tests can check timing exactly.
"""
import array
import math

from .base import silence, write_wav

WORD_GAP = 0.04


class SyntheticProvider:
    name = "synthetic"

    def produce(self, row, out_path, rate, base_dir=None):
        f0 = float(row["source"]["f0"])
        lead, tail = row["pause_before_ms"] / 1000, row["pause_after_ms"] / 1000
        words, t, times = row["text"].split(), 0.0, []
        for w in words:
            d = 0.12 + 0.055 * len(w)
            times.append([round(t, 6), round(t + d, 6), w])
            t += d + WORD_GAP
        body = max(0.3, t - WORD_GAP)
        n = int(round(body * rate))
        a = array.array("h", [0]) * n
        for s, e, _ in times:
            i0, i1 = int(round(s * rate)), min(n, int(round(e * rate)))
            ramp = max(1, int(0.01 * rate))
            for k in range(i0, i1):
                env = min(1.0, (k - i0) / ramp, (i1 - k) / ramp)
                x = (k - i0) / rate
                a[k] = int(7000 * env * (math.sin(2 * math.pi * f0 * x) + 0.5 * math.sin(4 * math.pi * f0 * x)
                                         + 0.25 * math.sin(6 * math.pi * f0 * x)))
        pcm = silence(lead, rate) + a.tobytes() + silence(tail, rate)
        info = write_wav(out_path, pcm, rate)
        info["synthetic_words"] = [[round(s + lead, 6), round(e + lead, 6), w] for s, e, w in times]
        info["source_rate"] = rate
        return info
