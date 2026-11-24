"""Estimated times for script words that Whisper could not match (mostly numbers it writes as digits: "$4 billion", "294").

The core timing.json leaves such words without times, so the karaoke subtitle never highlighted them and a caption could end
before the narrator did. This helper gives each run of untimed words an ESTIMATED slot inside the gap between its timed
neighbours (or the measured speech end) - never outside it, never overlapping a timed word. Nothing is invented elsewhere:
timed words are not touched, the audio is not touched, and the words are flagged est=True. Used by compose.py and assemble.py.
"""
import copy
import re


def _need(text):
    n = len(re.sub(r"[^\w]", "", text, flags=re.UNICODE))
    return min(0.7, max(0.12, 0.08 + 0.075 * n))


def estimate_untimed(timing):
    """Returns a deep copy of a core timing.json in which every untimed word has an estimated abs_start/abs_end (est=True)."""
    t = copy.deepcopy(timing)
    for s in t["sentences"]:
        W = s["words"]
        timed = [w for w in W if w.get("abs_start") is not None]
        if not timed or len(timed) == len(W):
            continue
        late = (s.get("summary") or {}).get("last_word_vs_speech_end_ms")
        speech_end = timed[-1]["abs_end"] + (max(0, -late) / 1000.0 if isinstance(late, (int, float)) else 0.0)
        speech_end = min(speech_end, s["offset"] + s["duration"] - 0.1)
        i = 0
        while i < len(W):
            if W[i].get("abs_start") is not None:
                i += 1
                continue
            j = i
            while j < len(W) and W[j].get("abs_start") is None:
                j += 1
            run = W[i:j]
            need = [_need(w["text"]) for w in run]
            right = W[j]["abs_start"] if j < len(W) else speech_end
            left = W[i - 1]["abs_end"] if i > 0 else max(s["offset"], right - sum(need))
            window = right - left
            if window < 0.05 * len(run) and j < len(W):
                # no gap at all: Whisper's boundary of the next word is "estimated" and swallows the untimed word
                # (e.g. "dollars" inside the span of "in"). Take only the surplus of that word's own span.
                nw = W[j]
                spare = (nw["abs_end"] - nw["abs_start"]) - _need(nw["text"])
                take = min(sum(need), spare)
                if take >= 0.6 * sum(need):
                    left, right, window = nw["abs_start"], nw["abs_start"] + take, take
                    nw["abs_start"], nw["start"], nw["est"] = round(right, 3), round(right - s["offset"], 3), True
            if window >= 0.05 * len(run):
                scale = min(1.0, window / sum(need))
                cur = left
                for w, d in zip(run, need):
                    d *= scale
                    w["abs_start"], w["abs_end"] = round(cur, 3), round(cur + d, 3)
                    w["start"], w["end"] = round(w["abs_start"] - s["offset"], 3), round(w["abs_end"] - s["offset"], 3)
                    w["est"] = True
                    cur += d
            i = j
    return t
