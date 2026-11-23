"""
NFP Character Engine - C3c: word-timing normaliser (pure Python, no audio, no network).

Turns any of the word-timing formats the project already produces into ONE internal shape:

    {"schema": "nfp.words/1", "source": <format>, "sentences": [{"id", "words": [{"i", "text", "t0", "t1", "quality",
     "note"}]}], "report": {...}}

    quality: exact | aligned | estimated | unresolved      (t0/t1 are None exactly when quality is unresolved)

Accepted inputs (detected automatically, or forced with source=):
  studio   - Stage 2 timing.json: sentences[].words[] with abs_start/abs_end, status, timing_quality
  docu     - Docu DATA: sentences[].words[] with start/end/hl (hl:false entries are placeholders, not real timings)
  whisper  - faster-whisper / OpenAI style: segments[].words[] with word/start/end
  words    - Stage 2 Whisper cache or any {"words": [...]} / plain list of {text|word, start|t0, end|t1}

Rules: a word without a valid interval never receives an invented time - it becomes 'unresolved' and is listed
in the report. All timed words of the whole document are put in time order first (the order of sentences or words
in the file never changes the result); then a word overlapping the previous one is clipped to start where the
previous ends (and counted), or made unresolved if nothing is left (e.g. an exact duplicate).
Docu DATA has no word text: the word id is never used as text; such words get duration-based neutral mouth flaps.
Text is kept in logical (spoken) order; RTL is a display property only and is never reversed here.
"""
import math
import unicodedata

QUALITIES = ("exact", "aligned", "estimated", "unresolved")


class TimingError(ValueError):
    pass


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def detect(data):
    if isinstance(data, list):
        return "words"
    if not isinstance(data, dict):
        raise TimingError("timing must be a JSON object or a list of words")
    if isinstance(data.get("sentences"), list):
        words = [w for s in data["sentences"] if isinstance(s, dict) for w in (s.get("words") or [])]
        if any(isinstance(w, dict) and ("abs_start" in w or "timing_quality" in w) for w in words):
            return "studio"
        if any(isinstance(w, dict) and "hl" in w for w in words):
            return "docu"
        return "studio" if not words else "generic_sentences"
    if isinstance(data.get("segments"), list):
        return "whisper"
    if isinstance(data.get("words"), list):
        return "words"
    raise TimingError("unknown timing format (expected sentences[], segments[] or words[])")


def _studio_quality(w):
    q = w.get("timing_quality")
    if q in ("exact", "estimated"):
        return q
    if q in ("unresolved", "none"):
        return "unresolved"
    return {"exact": "exact", "aligned": "aligned", "bracketed": "estimated"}.get(w.get("status"), "unresolved")


def _word(text, t0, t1, quality, note=None):
    return {"text": unicodedata.normalize("NFC", str(text or "")).strip(), "t0": t0, "t1": t1, "quality": quality,
            "note": note}


def _from_sentences(data, kind, offset):
    out = []
    for si, s in enumerate(data["sentences"]):
        sid = str(s.get("id", f"s{si + 1}"))
        ws = []
        for w in s.get("words") or []:
            if kind == "studio":
                q = _studio_quality(w)
                t0, t1 = w.get("abs_start"), w.get("abs_end")
                note = None
                if q == "unresolved":
                    note = "skipped token" if w.get("status") == "skipped" else "no timing from alignment (unmatched)"
                ws.append(_word(w.get("text"), t0, t1, q, note))
            elif kind == "docu":
                # Docu DATA words carry an element id, not the spoken text: the id is NEVER used as text. Without
                # text, lipsync.py falls back to duration-based neutral open/small flaps.
                text = next((w[k] for k in ("text", "word", "w") if isinstance(w.get(k), str) and w[k].strip()), "")
                note = None if text else "no word text in the Docu data: mouth shapes from duration only"
                if w.get("hl") is False:
                    ws.append(_word(text, None, None, "unresolved", "docu placeholder (hl:false), not a real timing"))
                else:
                    ws.append(_word(text, w.get("start"), w.get("end"), "aligned", note))
            else:
                ws.append(_generic(w))
        out.append({"id": sid, "words": ws})
    return _shift(out, offset)


def _generic(w):
    if not isinstance(w, dict):
        return _word("", None, None, "unresolved", "not a word object")
    text = w.get("text", w.get("word", w.get("w", "")))
    t0 = next((w[k] for k in ("t0", "start", "abs_start") if k in w), None)
    t1 = next((w[k] for k in ("t1", "end", "abs_end") if k in w), None)
    q = w.get("quality") if w.get("quality") in QUALITIES else "aligned"
    return _word(text, t0, t1, q)


def _shift(sentences, offset):
    if offset:
        for s in sentences:
            for w in s["words"]:
                if _num(w["t0"]) and _num(w["t1"]):
                    w["t0"], w["t1"] = w["t0"] + offset, w["t1"] + offset
    return sentences


def normalize(data, source=None, offset=0.0, sentence_id="s1"):
    kind = source or detect(data)
    if kind in ("studio", "docu", "generic_sentences"):
        sentences = _from_sentences(data, kind, offset)
    elif kind == "whisper":
        ws = [_generic(w) for seg in data["segments"] for w in (seg.get("words") or [])]
        sentences = _shift([{"id": sentence_id, "words": ws}], offset)
    elif kind == "words":
        lst = data if isinstance(data, list) else data["words"]
        sentences = _shift([{"id": sentence_id, "words": [_generic(w) for w in lst]}], offset)
    else:
        raise TimingError(f"unknown source '{kind}'")

    rep = {"source": kind, "words": 0, "timed": 0, "estimated": 0, "unresolved": [], "reordered": 0, "clipped": 0}
    timed = []
    for si, s in enumerate(sentences):
        for i, w in enumerate(s["words"]):
            w["i"] = i
            rep["words"] += 1
            if w["quality"] != "unresolved":
                t0, t1 = w["t0"], w["t1"]
                if not (_num(t0) and _num(t1)) or t0 < 0 or t1 <= t0:
                    w.update(t0=None, t1=None, quality="unresolved", note=f"invalid interval ({t0}, {t1})")
            if w["quality"] == "unresolved":
                w["t0"] = w["t1"] = None
            else:
                timed.append((si, i, w))
    # time order over the WHOLE document first (file order of sentences or words never matters), then overlaps
    order = sorted(timed, key=lambda x: (x[2]["t0"], x[2]["t1"], x[0], x[1]))
    rep["reordered"] = sum(1 for a, b in zip(timed, order) if a[2] is not b[2])
    prev_end = None
    for _, _, w in order:
        if prev_end is not None and w["t0"] < prev_end - 1e-9:
            if w["t1"] > prev_end + 1e-9:
                w["t0"] = prev_end
                w["note"] = "start clipped to the previous word's end (overlap)"
                rep["clipped"] += 1
            else:
                w.update(t0=None, t1=None, quality="unresolved", note="completely overlapped by the previous word")
                continue
        prev_end = w["t1"]
    for s in sentences:
        s["order"] = [w["i"] for w in sorted((w for w in s["words"] if w["quality"] != "unresolved"),
                                             key=lambda w: (w["t0"], w["i"]))]
        for w in s["words"]:
            if w["quality"] == "unresolved":
                rep["unresolved"].append({"sentence": s["id"], "i": w["i"], "text": w["text"], "note": w["note"]})
            else:
                rep["timed"] += 1
                rep["estimated"] += w["quality"] == "estimated"
                w["t0"], w["t1"] = round(w["t0"], 6), round(w["t1"], 6)
    return {"schema": "nfp.words/1", "source": kind, "sentences": sentences, "report": rep}


def timed_words(doc, sentence_ids=None):
    """Timed words in time order, optionally only some sentences: [(sentence_id, word)]."""
    out = []
    for s in doc["sentences"]:
        if sentence_ids is not None and s["id"] not in sentence_ids:
            continue
        for w in s["words"]:
            if w["quality"] != "unresolved":
                out.append((s["id"], w))
    out.sort(key=lambda x: (x[1]["t0"], x[1]["i"]))
    return out
