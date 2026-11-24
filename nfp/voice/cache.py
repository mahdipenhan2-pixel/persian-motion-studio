"""NFP Voice Engine - audio cache (nfp.voice.cache/1): finished sentence files, reused when nothing that changes them
has changed.

    c = Cache(dir)                         # default: $NFP_VOICE_CACHE or ~/.cache/nfp-voice (never inside the repo)
    key = render_key(row, rate, normalize_settings)
    hit = c.get(key, rate)                 # None on a miss; an invalid / incomplete entry is discarded and counted
    c.put(key, wav_path, info)

Key: sha256 of the plan's cache_key (provider, voice, style, language, text, pauses, prepared file sha256) PLUS the
output format, the normalization settings, the voice's own parameters and the engine's render version - everything
that changes the produced file. An entry = <key>.wav + <key>.json (written last = commit marker). On every hit the
JSON, the key, the WAV's sha256, its format and frame count are checked; anything else is discarded (corrupt) and
rebuilt. Writes go to a unique temp file in the same folder and are moved in with os.replace (atomic), so runs at
the same time never see half a file. clear() deletes only cache entries inside a folder marked as an NFP voice cache.
"""
import hashlib
import json
import os
import shutil
import uuid
import wave
from pathlib import Path

SCHEMA = "nfp.voice.cache/1"
RENDER_VERSION = "nfp.voice.render/1"
MARKER = "NFP_VOICE_CACHE"


class CacheError(ValueError):
    pass


def default_dir():
    return Path(os.environ.get("NFP_VOICE_CACHE") or Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "nfp-voice")


def render_key(row, rate, normalize, voice_params=None):
    blob = {"v": RENDER_VERSION, "plan_cache_key": row["cache_key"], "rate": rate, "channels": 1, "bits": 16,
            "normalize": normalize, "voice_params": voice_params or {}}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


class Cache:
    def __init__(self, path=None):
        self.dir = Path(path) if path else default_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        m = self.dir / MARKER
        if not m.exists():
            if any(self.dir.iterdir()):
                raise CacheError(f"{self.dir} is not empty and not an NFP voice cache (no {MARKER} marker); "
                                 "use an empty or dedicated folder")
            m.write_text(f"{SCHEMA}\nThis folder is an NFP Voice Engine cache; its entries can be deleted with "
                         "`python3 nfp/voice/cli.py cache-clear`.\n", encoding="utf-8")
        self.stats = {"hits": 0, "misses": 0, "discarded": 0}

    def _paths(self, key):
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise CacheError(f"bad cache key {key!r}")
        d = self.dir / key[:2]
        return d, d / f"{key}.wav", d / f"{key}.json"

    def _discard(self, key, why):
        d, w, j = self._paths(key)
        for p in (j, w):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        self.stats["discarded"] += 1
        self.last_discard = why

    def get(self, key, rate):
        """Validated entry {"path", "meta"} or None (miss). Invalid entries are removed and counted."""
        d, w, j = self._paths(key)
        if not j.exists():
            if w.exists():
                self._discard(key, "WAV without its JSON (incomplete write)")
            self.stats["misses"] += 1
            return None
        try:
            meta = json.loads(j.read_text(encoding="utf-8"))
            ok = (meta.get("schema") == SCHEMA and meta.get("key") == key and w.exists() and _sha(w) == meta.get("sha256"))
            if ok:
                with wave.open(str(w), "rb") as f:
                    ok = (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()) == (1, 2, rate, meta["frames"])
        except (ValueError, OSError, wave.Error, EOFError, KeyError):
            ok = False
        if not ok:
            self._discard(key, "corrupt or incomplete entry")
            self.stats["misses"] += 1
            return None
        self.stats["hits"] += 1
        return {"path": w, "meta": meta}

    def peek(self, key, rate):
        """True when a complete, valid entry exists - without counting a hit / miss and without deleting anything."""
        d, w, j = self._paths(key)
        try:
            meta = json.loads(j.read_text(encoding="utf-8"))
            if meta.get("schema") != SCHEMA or meta.get("key") != key or _sha(w) != meta.get("sha256"):
                return False
            with wave.open(str(w), "rb") as f:
                return (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()) == (1, 2, rate, meta["frames"])
        except (ValueError, OSError, wave.Error, EOFError, KeyError):
            return False

    def put(self, key, wav, info):
        d, w, j = self._paths(key)
        d.mkdir(parents=True, exist_ok=True)
        tag = f".tmp-{os.getpid()}-{uuid.uuid4().hex}"
        tw, tj = w.with_name(w.name + tag), j.with_name(j.name + tag)
        shutil.copyfile(wav, tw)
        with wave.open(str(tw), "rb") as f:
            frames = f.getnframes()
        meta = {"schema": SCHEMA, "key": key, "sha256": _sha(tw), "frames": frames, "info": info}
        tj.write_text(json.dumps(meta, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        os.replace(tw, w)            # WAV first, JSON last: the JSON is the commit marker
        os.replace(tj, j)
        return meta

    def entries(self):
        return sorted(p for p in self.dir.glob("??/*.json") if len(p.stem) == 64)

    def clear(self):
        """Delete every cache entry (and stale temp files) - only inside this marked cache folder."""
        if not (self.dir / MARKER).exists():
            raise CacheError(f"{self.dir} is not an NFP voice cache; nothing deleted")
        n = 0
        for sub in self.dir.iterdir():
            if sub.is_dir() and len(sub.name) == 2 and all(c in "0123456789abcdef" for c in sub.name):
                for p in sub.iterdir():
                    stem = p.name.split(".")[0]
                    if len(stem) == 64 and (p.suffix in (".wav", ".json") or ".tmp-" in p.name):
                        p.unlink()
                        n += 1
                try:
                    sub.rmdir()
                except OSError:
                    pass
        return n
