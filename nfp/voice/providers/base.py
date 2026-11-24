"""Common output format and helpers of the Voice Engine providers (standard library only)."""
import wave

FORMAT = {"channels": 1, "sample_width": 2, "rate": 24000}      # mono 16-bit PCM; the rate can be chosen per run


class ProviderError(ValueError):
    pass


def silence(seconds, rate):
    return b"\x00\x00" * int(round(seconds * rate))


def write_wav(path, pcm, rate):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return {"rate": rate, "frames": len(pcm) // 2, "duration": round(len(pcm) / 2 / rate, 6)}


def read_wav(path):
    try:
        with wave.open(str(path), "rb") as w:
            return {"channels": w.getnchannels(), "sample_width": w.getsampwidth(), "rate": w.getframerate(),
                    "frames": w.getnframes(), "pcm": w.readframes(w.getnframes())}
    except (wave.Error, EOFError, OSError) as e:
        raise ProviderError(f"{path}: not a readable PCM WAV file ({e})")
