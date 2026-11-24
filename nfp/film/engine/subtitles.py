"""NFP Film - Subtitle Engine, stage S1: subtitle cues + readability QC as data (<build>/subtitles.json).

Reads the existing word timing (the core's timing.json, completed by untimed.estimate_untimed exactly as compose.py does,
i.e. the same words as words.json) and never writes timing.json, words.json or anything lip sync reads.
S1 does not change what is drawn on the video: compose.py is not involved; `run.py subs` writes the cue file.

project.json (optional; without it `subs` uses the defaults below):
  "subtitles": {"mode": "sentence" | "word" | "karaoke" | "off",
                "max_chars_per_line": 42, "max_lines": 2, "max_cps": 17,
                "min_duration": 0.833, "max_duration": 7.0, "min_gap": 0.067, "lead": 0.05, "tail": 0.15}

  sentence  one cue per sentence, split into several cues only when it does not fit max_lines x max_chars_per_line
  karaoke   the same cues + the timed words of each cue (for a highlight of the current word)
  word      one cue per spoken word (start/end = that word's time)
  off       (S3) nothing drawn on the video; the cues are the sentence-mode cues, for the SRT / VTT / ASS files

Lines break only between words (the core splits words on whitespace, so a ZWNJ / nim-fasele stays inside its word and is
never a break point); breaks prefer punctuation and pauses, keep the two lines balanced, never put a lone punctuation mark
at the start of a line, and avoid ending a line on a weak word (en: the/of/to..., fa: و/از/به...) or starting one with را.
Character counts ignore ZWNJ / ZWJ / direction marks and diacritics (they take no width of their own).
"""
import json
import re
import unicodedata
from pathlib import Path

from untimed import estimate_untimed

SCHEMA = "nfp.film.subtitles/1"
FPS = 30
MODES = ("sentence", "word", "karaoke", "off")
DEFAULTS = {"mode": "sentence", "max_chars_per_line": 42, "max_lines": 2, "max_cps": 17.0, "min_duration": 0.833,
            "max_duration": 7.0, "min_gap": 0.067, "lead": 0.05, "tail": 0.15}
LIMITS = {"max_chars_per_line": (16, 80), "max_lines": (1, 2), "max_cps": (5, 40), "min_duration": (0.2, 3.0),
          "max_duration": (2.0, 12.0), "min_gap": (0.0, 0.5), "lead": (0.0, 0.5), "tail": (0.0, 1.0)}
ZWNJ = "‌"
STRONG = set(".!?;:؟؛…")       # . ! ? ; : ؟ ؛ …
COMMA = set(",،")                         # , ،
CLOSERS = "\"')]}»”’"           # trailing quotes / brackets ignored when reading a word's punctuation
OPENERS = set("\"'([{«“‘")
WEAK_END = {"en": {"a", "an", "the", "to", "of", "and", "or", "in", "on", "at", "for", "with", "by", "from", "as", "but",
                   "that", "my", "your", "his", "her", "its", "our", "their"},
            "fa": {"و", "از", "به", "با", "در", "که", "تا",
                   "برای", "بر", "این", "آن", "یک", "هر"}}
NO_START = {"en": set(), "fa": {"را"}}                # را
GOOD_START = {"en": {"and", "but", "or", "so", "because", "which", "who", "when", "while"},
              "fa": {"و", "اما", "ولی", "که", "تا"}}
VERB_PREFIX = ("می‌", "نمی‌")       # the verb of a compound verb (بیدار می‌شود) should not open a line on its own
INF = float("inf")


class SubtitleError(ValueError):
    pass


def settings(project):
    """The project's subtitle settings merged over the defaults (validated)."""
    raw = project.get("subtitles", {})
    if not isinstance(raw, dict):
        raise SubtitleError("subtitles must be an object")
    extra = sorted(set(raw) - set(DEFAULTS))
    if extra:
        raise SubtitleError(f"subtitles: unknown field(s) {', '.join(extra)}")
    s = dict(DEFAULTS, **raw)
    if s["mode"] not in MODES:
        raise SubtitleError(f"subtitles.mode must be one of {', '.join(MODES)}")
    for k, (lo, hi) in LIMITS.items():
        v = s[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise SubtitleError(f"subtitles.{k} must be a number {lo}..{hi}")
    if not isinstance(s["max_lines"], int) or not isinstance(s["max_chars_per_line"], int):
        raise SubtitleError("subtitles.max_lines and max_chars_per_line must be integers")
    if s["min_duration"] >= s["max_duration"]:
        raise SubtitleError("subtitles.min_duration must be below max_duration")
    return s


# ---------- text ----------

def vis(text):
    """Characters a reader sees: ZWNJ / ZWJ / direction marks (Cf) and diacritics (Mn) take no width of their own."""
    return sum(1 for c in text if unicodedata.category(c) not in ("Cf", "Mn"))


def clean_word(text):
    """A word for display: a ZWNJ at a word edge joins nothing, so it is dropped; inner ZWNJs are kept as they are."""
    return text.strip(ZWNJ)


def is_punct(text):
    return bool(text) and all(unicodedata.category(c)[0] in "PS" for c in text)


def end_mark(text):
    t = text.rstrip(CLOSERS)
    return t[-1] if t else ""


def bare(text):
    return "".join(c for c in text if unicodedata.category(c)[0] not in "PS").replace(ZWNJ, "").lower()


def can_break(words, k):
    """May a line / cue end after words[k-1] and the next start with words[k]?"""
    nxt, prev = words[k]["text"], words[k - 1]["text"]
    if is_punct(nxt) and not set(nxt) <= OPENERS:
        return False                   # a closing / standalone mark stays with the word before it
    if prev and set(prev) <= OPENERS:
        return False                   # an opening quote / bracket stays with the word after it
    return True


def break_cost(words, k, lang):
    """Language cost of breaking between words[k-1] and words[k] (lower = more natural)."""
    a, b = words[k - 1]["text"], words[k]["text"]
    m = end_mark(a)
    cost = -8 if m in STRONG else -5 if m in COMMA else 0
    if bare(a) in WEAK_END.get(lang, ()):
        cost += 10
    if bare(b) in NO_START.get(lang, ()):
        cost += 12
    if bare(b) in GOOD_START.get(lang, ()):
        cost -= 3
    if lang == "fa" and b.startswith(VERB_PREFIX) and not m:
        cost += 4
    return cost


def line_text(words):
    return " ".join(w["text"] for w in words)


def layout(words, st, lang):
    """Best 1- or 2-line layout of a word run, or None if it cannot fit (a single over-long word is laid out anyway)."""
    mx = st["max_chars_per_line"]
    whole = line_text(words)
    if vis(whole) <= mx or len(words) == 1:
        return [whole], 0.0
    if st["max_lines"] < 2:
        return None
    best, best_cost = None, INF
    for k in range(1, len(words)):
        if not can_break(words, k):
            continue
        a, b = line_text(words[:k]), line_text(words[k:])
        la, lb = vis(a), vis(b)
        if la > mx or lb > mx:
            continue
        cost = abs(la - lb) + (1 if la > lb else 0) + break_cost(words, k, lang)   # balanced, slightly bottom-heavy
        if cost < best_cost:
            best, best_cost = [a, b], cost
    return (best, best_cost) if best else None


# ---------- words ----------

def timed_words(timing):
    """Per sentence: its words with times, from the core timing + estimate_untimed (= the words of words.json)."""
    t = estimate_untimed(timing)
    out = []
    for s in t["sentences"]:
        W = s["words"]
        rows = []
        for r in W:
            a, b, est = r.get("abs_start"), r.get("abs_end"), bool(r.get("est"))
            if a is None:                # still untimed (as compose.py: placed at the next timed word, not highlighted)
                a = next((x["abs_start"] for x in W[r["i"] + 1:] if x.get("abs_start") is not None), s["offset"] + s["duration"])
                a, b, est = round(a, 3), round(a + 0.06, 3), True
            text = clean_word(r["text"])
            if text:
                rows.append({"i": r["i"], "text": text, "start": a, "end": b, "est": est, "src": r["text"]})
        out.append({"id": s["id"], "offset": s["offset"], "end": round(s["offset"] + s["duration"], 3),
                    "text": s.get("text") or " ".join(r["text"] for r in W), "words": rows})
    return out


# ---------- cues ----------

def split_sentence(words, st, lang):
    """Split one sentence's words into cues (dynamic programming: fewest cues, good break points, readable pace)."""
    n = len(words)
    best = [0.0] + [INF] * n
    back = [0] * (n + 1)
    lay = {}
    for i in range(1, n + 1):
        for j in range(i - 1, -1, -1):
            if j and not can_break(words, j):
                continue
            L = layout(words[j:i], st, lang)
            if L is None:
                if i - j > 1 and vis(line_text(words[j:i])) > st["max_chars_per_line"] * st["max_lines"] + 10:
                    break                # longer runs only get longer
                continue
            dur = max(0.05, words[i - 1]["end"] - words[j]["start"])
            chars = vis(line_text(words[j:i]))
            cost = best[j] + 10 + L[1] * 0.2
            cost += 50 * max(0.0, dur + st["tail"] - st["max_duration"])
            cost += 2 * max(0.0, chars / dur - st["max_cps"])
            if i - j == 1 and n > 1:
                cost += 15
            elif chars < 12 and n > 1:
                cost += 6
            if i < n:                    # quality of the break after words[i-1]
                m = end_mark(words[i - 1]["text"])
                pause = words[i]["start"] - words[i - 1]["end"]
                cost += 0 if m in STRONG else 2 if m in COMMA else 3 if pause >= 0.3 else 8
                cost += max(0, break_cost(words, i, lang))
            if cost < best[i]:
                best[i], back[i], lay[i] = cost, j, L[0]
    chunks, i = [], n
    while i > 0:
        j = back[i]
        chunks.append((words[j:i], lay[i]))
        i = j
    return chunks[::-1]


def word_runs(words):
    """Word mode: one cue per spoken word; a standalone punctuation mark joins the word before it."""
    runs = []
    for w in words:
        if runs and is_punct(w["text"]) and not set(w["text"]) <= OPENERS:
            runs[-1].append(w)
        elif runs and runs[-1] and set(runs[-1][-1]["text"]) <= OPENERS:
            runs[-1].append(w)
        else:
            runs.append([w])
    return runs


def video_duration(project, chapter, timing):
    t = float(chapter.get("target_duration") or project["meta"].get("target_duration") or timing["audio"]["total"])
    return round(t * FPS) / FPS          # as compose.py


def build(project, chapter, timing):
    st = settings(project)
    lang = project["meta"]["lang"]
    mode = st["mode"]
    duration = video_duration(project, chapter, timing)
    sents = timed_words(timing)
    raw = []                             # (sentence, words, lines)
    for s in sents:
        if not s["words"]:
            continue
        if mode == "word":
            for run in word_runs(s["words"]):
                raw.append((s, run, [line_text(run)]))
        else:
            for run, lines in split_sentence(s["words"], st, lang):
                raw.append((s, run, lines))
    cues = []
    for n, (s, run, lines) in enumerate(raw):
        nxt = raw[n + 1] if n + 1 < len(raw) else None
        first, last = run[0]["start"], max(w["end"] for w in run)
        if mode == "word":
            start = first
            end = last + st["tail"]
            if nxt:
                ns = nxt[1][0]["start"]
                end = ns if ns - last < 0.3 else min(end, ns)
        else:
            first_of_sentence = n == 0 or raw[n - 1][0] is not s
            lo = s["offset"] if first_of_sentence else cues[-1]["end"] + st["min_gap"]   # as story.srt for a whole sentence
            start = min(max(first - st["lead"], lo), first)                              # never after its first word
            if cues and start < cues[-1]["end"]:
                start = cues[-1]["end"]
            hi = duration
            if nxt:
                ns = nxt[1][0]["start"] - st["lead"]
                hi = min(ns - st["min_gap"], nxt[0]["offset"] - 0.02) if nxt[0] is not s else ns - st["min_gap"]
            end = min(last + st["tail"], hi)
            end = max(end, last)                                   # never hide a word that is still spoken
            if end - start < st["min_duration"]:
                end = max(end, min(start + st["min_duration"], hi))  # short cues stay a little longer when there is room
        start, end = round(max(0.0, start), 3), round(end, 3)
        text = "\n".join(lines)
        flat = " ".join(lines)
        dur = round(end - start, 3)
        cue = {"i": len(cues) + 1, "sentence": s["id"], "start": start, "end": end, "duration": dur, "lines": lines,
               "text": text, "chars": vis(flat), "cps": round(vis(flat) / dur, 2) if dur > 0 else None}
        if mode in ("word", "karaoke"):
            cue["words"] = [{"i": w["i"], "text": w["text"], "start": w["start"], "end": w["end"], "est": w["est"]} for w in run]
        cues.append(cue)
    doc = {"schema": SCHEMA, "lang": lang, "dir": "rtl" if lang == "fa" else "ltr", "mode": mode, "fps": FPS,
           "duration": duration, "settings": st, "cues": cues}
    doc["qc"] = qc(doc, sents)
    return doc


# ---------- QC ----------

def qc(doc, sents):
    st, mode, lang = doc["settings"], doc["mode"], doc["lang"]
    issues = []

    def add(level, code, msg, cue=None, sentence=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("cue", cue), ("sentence", sentence),
                                         ("message", msg)) if v is not None})

    prev = None
    for c in doc["cues"]:
        i = c["i"]
        if c["end"] <= c["start"]:
            add("error", "bad_time", f"ends at {c['end']}s, not after its start {c['start']}s", i)
        if c["start"] < 0 or c["end"] > doc["duration"] + 1e-6:
            add("error", "outside_video", f"{c['start']}-{c['end']}s is outside the video (0-{doc['duration']}s)", i)
        if prev and c["start"] < prev["end"] - 1e-6:
            add("error", "overlap", f"starts at {c['start']}s before cue {prev['i']} ends ({prev['end']}s)", i)
        elif prev and mode != "word" and c["start"] - prev["end"] < st["min_gap"] - 1e-6:
            add("warning", "gap", f"only {round((c['start'] - prev['end']) * 1000)} ms after cue {prev['i']} "
                                  f"(min {round(st['min_gap'] * 1000)} ms)", i)
        if len(c["lines"]) > st["max_lines"]:
            add("error", "too_many_lines", f"{len(c['lines'])} lines (max {st['max_lines']})", i)
        for ln in c["lines"]:
            if vis(ln) > st["max_chars_per_line"]:
                add("warning", "line_too_long", f"a line of {vis(ln)} characters (max {st['max_chars_per_line']}): "
                                                f"a single word longer than a line", i)
        if mode != "word":
            if c["cps"] is not None and c["cps"] > st["max_cps"]:
                add("warning", "cps", f"{c['cps']} characters/s (max {st['max_cps']}): fast to read", i)
            if c["duration"] < st["min_duration"] - 1e-6:
                add("warning", "short", f"on screen {c['duration']}s (min {st['min_duration']}s)", i)
            if c["duration"] > st["max_duration"] + 1e-6:
                add("warning", "long", f"on screen {c['duration']}s (max {st['max_duration']}s)", i)
        for w in c.get("words", []):
            if w["start"] < c["start"] - 1e-6 or w["end"] > c["end"] + 1e-6:
                add("warning", "word_outside_cue", f"word '{w['text']}' ({w['start']}-{w['end']}s) is outside the cue", i)
        prev = c
    pw = None                            # the word timing itself must run forward (cues are only as good as it is)
    for s in sents:
        for w in s["words"]:
            if pw and w["start"] < pw[1]["end"] - 0.001:
                add("error", "word_overlap", f"word '{w['text']}' starts at {w['start']}s before '{pw[1]['text']}' "
                                             f"({pw[0]}) ends at {pw[1]['end']}s - check the alignment", sentence=s["id"])
            pw = (s["id"], w)
    est = sum(1 for s in sents for w in s["words"] if w["est"])
    if est:
        add("info", "estimated_words", f"{est} word(s) Whisper could not match have estimated times (est)")
    if lang == "fa":
        for s in sents:
            t = s["text"]
            if re.search(r"\s‌|‌\s", t):
                add("warning", "space_around_zwnj", "a space next to a nim-fasele (ZWNJ)", sentence=s["id"])
            if "‌‌" in t:
                add("warning", "double_zwnj", "two nim-fasele (ZWNJ) in a row", sentence=s["id"])
            if any(w["src"] != w["text"] for w in s["words"]):
                add("info", "edge_zwnj_removed", "a nim-fasele at a word edge joined nothing and was left out of the cue",
                    sentence=s["id"])
            if re.search(r"\s[،؛؟!.:]", t):
                add("warning", "space_before_punct", "a space before a punctuation mark", sentence=s["id"])
    n = {lv: sum(1 for x in issues if x["level"] == lv) for lv in ("error", "warning", "info")}
    return {"status": "FAIL" if n["error"] else "WARN" if n["warning"] else "OK", "cues": len(doc["cues"]),
            "errors": n["error"], "warnings": n["warning"], "infos": n["info"], "issues": issues}


def write(build, doc):
    p = Path(build) / "subtitles.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
