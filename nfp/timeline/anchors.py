"""NFP Timeline - anchors -> integer frames (30 fps), the same results as the Film Director (kit/50_director.js).

Anchor forms (exactly the Director's, see Director.shot -> TT):
  12.5              seconds                            snap(x)
  "end"             end of the video                   snap(DATA.duration)
  [sid, "w", i]     start of word i of sentence sid    D.W(sid, i) = snap(word.start)
  [sid, "e", i]     end of word i                      D.We(sid, i) = snap(word.end)
  [sid, f]          fraction f of sentence sid         D.T(sid, f) = snap(start + (end - start) * f)
The Director snaps with JavaScript Math.round(t * 30) / 30; here the frame number is Math.round(t * 30), computed with
the same IEEE double arithmetic and JavaScript's rounding rule (halves round up, also for negative numbers) - NOT
Python's round() (halves to even).

The word timing comes from words.json (nfp.film.words/1, written by Film's compose.py): the Director's DATA.sentences
is made from the same timing in the same way (sentence start = offset, end = round(offset + duration, 3); a word that
was never timed sits at the next timed word's start for 0.06 s). Only this data contract is used - no Film code.
Stricter than the Director (reported as errors, not resolved differently): a fraction must be 0..1, an index an integer.
"""
import json
import math
from pathlib import Path

FPS = 30


class AnchorError(ValueError):
    pass


def js_round(x):
    """JavaScript Math.round: the nearest integer, halves towards +infinity."""
    r = math.floor(x)
    return int(r + 1 if x - r >= 0.5 else r)


def frame(seconds):
    return js_round(seconds * FPS)


class Context:
    """What anchors are resolved against: sentence windows and word times (seconds) and the video duration."""

    def __init__(self, sentences, duration):
        self.duration = float(duration)
        self.by_id = {s["id"]: s for s in sentences}

    @classmethod
    def from_words(cls, words):
        """From a words.json document (dict) or its path."""
        if not isinstance(words, dict):
            words = json.loads(Path(words).read_text(encoding="utf-8"))
        if words.get("schema") != "nfp.film.words/1":
            raise AnchorError("not a words.json (nfp.film.words/1)")
        if words.get("fps", FPS) != FPS:
            raise AnchorError(f"words.json fps must be {FPS}")
        sents = []
        for s in words["sentences"]:
            W = s["words"]
            rows = []
            for k, w in enumerate(W):
                if w.get("start") is not None:
                    rows.append((w["start"], w["end"]))
                else:                                   # as compose.py: placed at the next timed word (or sentence end)
                    nxt = next((x["start"] for x in W[w["i"] + 1:] if x.get("start") is not None), s["offset"] + s["duration"])
                    rows.append((round(nxt, 3), round(nxt + 0.06, 3)))
            sents.append({"id": s["id"], "start": s["offset"], "end": round(s["offset"] + s["duration"], 3), "words": rows})
        return cls(sents, words["duration"])

    @property
    def frames(self):
        return frame(self.duration)

    def resolve(self, a):
        """Anchor -> frame number (int). Raises AnchorError for an anchor the Director would reject (or that is invalid)."""
        if isinstance(a, bool):
            raise AnchorError(f"bad anchor {a!r}")
        if isinstance(a, (int, float)):
            if not math.isfinite(a) or a < 0:
                raise AnchorError(f"time {a!r} must be a number >= 0")
            return frame(a)
        if a == "end":
            return frame(self.duration)
        if isinstance(a, list) and a and isinstance(a[0], str):
            s = self.by_id.get(a[0])
            if s is None:
                raise AnchorError(f"unknown sentence {a[0]!r}")
            if len(a) == 3 and a[1] in ("w", "e"):
                i = a[2]
                if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(s["words"]):
                    raise AnchorError(f"no word {i!r} in {a[0]}")
                return frame(s["words"][i][0 if a[1] == "w" else 1])
            if len(a) == 2 and not isinstance(a[1], bool) and isinstance(a[1], (int, float)):
                f = a[1]
                if not 0 <= f <= 1:
                    raise AnchorError(f"fraction {f!r} of {a[0]} must be 0..1")
                return frame(s["start"] + (s["end"] - s["start"]) * (f or 0))
        raise AnchorError(f"bad anchor {a!r} (number, 'end', [sid, 'w'|'e', i] or [sid, fraction])")


def is_anchor_shape(a):
    """Shape only (no timing needed): could this be an anchor?"""
    if isinstance(a, bool):
        return False
    if isinstance(a, (int, float)) or a == "end":
        return True
    return isinstance(a, list) and len(a) in (2, 3) and isinstance(a[0], str) and (
        (len(a) == 3 and a[1] in ("w", "e")) or (len(a) == 2 and isinstance(a[1], (int, float)) and not isinstance(a[1], bool)))
