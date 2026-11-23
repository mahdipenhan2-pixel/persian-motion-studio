"""
NFP Character Engine - C3c: word-timed lip sync for the 12 swap mouths of the flat_cartoon_v2 rig.

Input: normalised words (timing_normalize.py). Output: one speech segment per talk action, i.e. mouth keys
[(frame, shape)] where shape is a rig mouth or "@rest" (= the character's current expression mouth, closed).

Rules
  * only timed words (exact / aligned / estimated) move the mouth; unresolved words get NO invented time - the
    mouth simply stays as it is around them, and they are listed in the report;
  * a word opens the mouth on frame round(t0 * fps): at most half a frame (< 1 frame) from the real word start;
  * inside a word the mouth changes once per estimated syllable (never faster than every 3 frames);
  * a pause longer than 0.15 s closes the mouth at the word end; a shorter pause half-closes it ("small");
  * after the last word the mouth closes at round(t1 * fps).
Shape choice (a first, deliberately simple mapping - not phoneme recognition):
  Persian  آ ا أ إ َ  -> open    و ؤ ُ  -> o    ی ي ئ ِ  -> small   (short vowels are rarely written: a syllable with
           no vowel letter alternates open / small, which follows the mostly 'a/e' implicit vowels)
  English  a -> open    o u w -> o    e i y -> small    (consonant-only chunk: alternates open / small)
Text is used in logical (spoken) order; right-to-left display order is irrelevant here.
"""
import re
import unicodedata

from .keys import PROFILE, PlanError, to_frame

SILENCE = 0.15
MIN_FLAP = 3
CLOSED = set(PROFILE["closed_mouths"])

FA_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی", "ۀ": "ه", "ة": "ه"})
FA_STRIP = re.compile(r"[ـ‌‍‎‏؜]")      # tatweel, ZWNJ/ZWJ, bidi marks
FA_LETTER = re.compile(r"[ء-يپچژکگیۀَُِ]")
FA_OPEN, FA_ROUND, FA_SPREAD = set("آاأإَ"), set("وؤُ"), set("یئِ")
EN_OPEN, EN_ROUND, EN_SPREAD = set("a"), set("ouw"), set("eiy")
FA_DIAC = set("َُِ")


def lang_of(text):
    if re.search(r"[؀-ۿ]", text):
        return "fa"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "other"


def letters(text):
    lg = lang_of(text)
    if lg == "fa":
        t = FA_STRIP.sub("", unicodedata.normalize("NFC", text).translate(FA_MAP))
        return lg, [c for c in t if FA_LETTER.match(c)]
    if lg == "en":
        return lg, [c for c in text.lower() if "a" <= c <= "z"]
    return lg, []


def syllables(text):
    lg, L = letters(text)
    if lg == "en":
        w = "".join(L)
        n = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
            n -= 1
        return max(1, n)
    if lg == "fa":
        base = [c for c in L if c not in FA_DIAC]
        return max(1, int(round(len(base) / 2.3))) if base else 0     # Persian digits only: decided by duration
    return 0          # digits / symbols: decided by duration


def _class(chunk, lg):
    s = set(chunk)
    if lg == "fa":
        sets = (FA_OPEN, FA_ROUND, FA_SPREAD)
    else:
        sets = (EN_OPEN, EN_ROUND, EN_SPREAD)
    for shape, st in zip(("open", "o", "small"), sets):
        if s & st:
            return shape
    return None


def word_shapes(text, n):
    """n mouth shapes for one word, in spoken order."""
    lg, L = letters(text)
    if not L or lg == "other":
        return [("open", "small")[k % 2] for k in range(n)]
    out = []
    for k in range(n):
        a, b = round(k * len(L) / n), round((k + 1) * len(L) / n)
        c = _class(L[a:b] or L[-1:], lg)
        if c is None:
            c = "small" if out and out[-1] == "open" else "open"
        if out and out[-1] == c:                       # keep the mouth visibly moving between syllables
            c = "small" if c != "small" else "open"
        out.append(c)
    return out


def plan_speech(words, fps, offset=0.0, viseme=True):
    """words: [(sentence_id, word)] timed, in time order (timing_normalize.timed_words).
    Returns (mouth_keys [(frame, shape, src)], report)."""
    keys, rep = [], {"flaps": 0, "words": 0, "estimated_words": [], "too_short": [], "max_open_offset_frames": 0.0}
    if not words:
        raise PlanError("talk: no timed words to lip-sync (every word is unresolved or the selection is empty)")
    last_f = -1
    for j, (sid, w) in enumerate(words):
        t0, t1 = w["t0"] + offset, w["t1"] + offset
        f0, f1 = to_frame(t0, fps), to_frame(t1, fps)
        if f0 <= last_f:
            f0 = last_f + 1
        if f1 <= f0:
            rep["too_short"].append({"sentence": sid, "i": w["i"], "text": w["text"]})
            f1 = f0 + 1
        src = "lipsync:" + w["quality"]
        if w["quality"] == "estimated":
            rep["estimated_words"].append({"sentence": sid, "i": w["i"], "text": w["text"]})
        n_syl = syllables(w["text"]) or max(1, (f1 - f0) // 5)
        n = max(1, min(n_syl, (f1 - f0) // MIN_FLAP))
        shapes = word_shapes(w["text"], n) if viseme else [("open", "small", "o")[(w["i"] + k) % 3] for k in range(n)]
        if keys and keys[-1][1] == shapes[0]:
            shapes[0] = "small" if shapes[0] != "small" else "open"
        for k in range(n):
            fk = f0 + int(round(k * (f1 - f0) / n))
            keys.append((fk, shapes[k], src))
        rep["flaps"] += n
        rep["words"] += 1
        rep["max_open_offset_frames"] = max(rep["max_open_offset_frames"], round(abs(f0 - t0 * fps), 4))
        nxt = words[j + 1][1] if j + 1 < len(words) else None
        if nxt is None or (nxt["t0"] + offset) - t1 > SILENCE + 1e-9:
            keys.append((f1, "@rest", src + ":close"))
            last_f = f1
        else:
            g0 = to_frame(nxt["t0"] + offset, fps)
            if g0 - f1 >= 2:
                keys.append((f1, "small", src + ":pause"))
                last_f = f1
            else:
                last_f = keys[-1][0]
    frames = [k[0] for k in keys]
    if frames != sorted(frames) or len(set(frames)) != len(frames):
        raise PlanError("lipsync: internal error, mouth keys not strictly increasing")
    return keys, rep


def closed(shape):
    return shape if shape in CLOSED else "neutral"
