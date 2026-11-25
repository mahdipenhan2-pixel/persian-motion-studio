"""NFP Location Engine - L1b: names of a place (current, historical, alternative), Persian letter normalization, and
name_at(location, year, lang). Standard library only.

A location MAY carry (optional; an L1a record without it stays valid and keeps its status):
  "names": [{"text": "...", "lang": "fa",               BCP 47-like code: fa, en, ar, la, fa-Latn, en-GB, ...
             "type": "current" | "historical" | "alternative",
             "from": -330 | null, "to": 640 | null,      whole years, both ends INCLUDED, null = open / unknown
             "preferred": true | false,                   breaks a tie between names that would compete (optional)
             "note": "..." | null}]                       (optional)

Year convention (no year zero): 1 = AD 1 / 1 CE, -1 = 1 BC / 1 BCE, -330 = 330 BC. Year 0 does not exist and is refused
everywhere; -1 is followed directly by 1. Years are proleptic-Gregorian / Julian calendar years as written by the source
(no calendar conversion: Hijri / Solar Hijri years must be converted before they are recorded).
  current      the name in use today: 'to' must be empty (still in use)
  historical   a former name: its period should be given
  alternative  another spelling / exonym / alias, used for search and matching - never chosen by name_at()

name_at(location, year=None, lang="fa", fallback=None) -> {"text", "display", "lang", "type", "from", "to", "fallback"} | None
  1. candidates: current / historical names valid in `year` (from <= year <= to; an empty end is open).
     year None = "today": only current names.
  2. language order: `lang`, then the `fallback` list (default: "en", "fa"), then every other language in alphabetical
     order of its code - the first language with a candidate wins; "fallback" in the result says whether it was used.
  3. within that language the most specific name wins: a name with both years given before one with one year, before one
     with none (a dated historical name beats an undated current one for an old year). Still a tie: the one marked
     "preferred". validate() refuses data where a tie could remain, so the choice is never random or ambiguous.
  "text" is the stored text, unchanged; "display" is the same text with Persian letters normalized (fa only).

Persian normalization (normalize_fa): Arabic YEH U+064A -> Persian YEH U+06CC, Arabic KAF U+0643 -> KEHEH U+06A9 (and
ALEF MAKSURA U+0649 -> U+06CC). It is applied only for display / matching; the stored text is never rewritten, a 'fa'
name containing the Arabic letters gets a warning.
"""
import re
import unicodedata

TYPES = ("current", "historical", "alternative")
PRIMARY = ("current", "historical")
NAME_KEYS = {"text", "lang", "type", "from", "to", "preferred", "note"}
NAME_REQUIRED = ("text", "lang", "type")
LANG_RE = re.compile(r"[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|\d{3}))?")
MIN_YEAR = -10000
DEFAULT_FALLBACK = ("en", "fa")
FA_MAP = {"ي": "ی", "ى": "ی", "ك": "ک"}
FA_ARABIC = re.compile("[يىك]")


class NameError_(ValueError):
    pass


def normalize_fa(text):
    """Persian letters normalized for display / matching (YEH, ALEF MAKSURA -> U+06CC, KAF -> U+06A9). Returns a new
    string; the input is not changed."""
    return "".join(FA_MAP.get(c, c) for c in text)


def _is_fa(lang):
    return lang == "fa" or lang.startswith("fa-")


def _year(v):
    return isinstance(v, int) and not isinstance(v, bool)


def covers(n, year):
    a, b = n.get("from"), n.get("to")
    return (a is None or a <= year) and (b is None or year <= b)


def specificity(n):
    return (n.get("from") is not None) + (n.get("to") is not None)


def _overlap(a, b):
    """Do two names' periods share at least one year? (None ends are open; year 0 never counts)."""
    lo = max(x for x in (a.get("from"), b.get("from"), MIN_YEAR) if x is not None)
    his = [x for x in (a.get("to"), b.get("to")) if x is not None]
    hi = min(his) if his else 10 ** 9
    return None if lo > hi else (lo, hi)


def check_names(names, today_year):
    """Issues of a names list: [(level, code, message)]. Structural problems use the code 'schema'."""
    out = []
    if not isinstance(names, list):
        return [("error", "schema", "names must be a list")]
    if not names:
        return [("warning", "no_names", "names is empty")]
    good = []
    for i, n in enumerate(names, 1):
        where = f"name {i}"
        if not isinstance(n, dict):
            out.append(("error", "schema", f"{where} must be an object"))
            continue
        miss = [k for k in NAME_REQUIRED if k not in n]
        extra = sorted(set(n) - NAME_KEYS)
        if miss or extra:
            out.append(("error", "schema", f"{where}: " + "; ".join(x for x in (
                f"missing field(s) {', '.join(miss)}" if miss else "", f"unknown field(s) {', '.join(extra)}" if extra else "") if x)))
            continue
        ok = True
        t = n["text"]
        if not isinstance(t, str) or not t.strip():
            out.append(("error", "schema", f"{where}: text must be non-empty text"))
            ok = False
        else:
            where = f"name {i} ({t!r})"
            if t != t.strip() or "  " in t:
                out.append(("warning", "name_spacing", f"{where}: leading / trailing / double spaces"))
            if unicodedata.normalize("NFC", t) != t:
                out.append(("warning", "name_not_nfc", f"{where}: not in Unicode NFC form"))
        if not isinstance(n["lang"], str) or not LANG_RE.fullmatch(n["lang"]):
            out.append(("error", "bad_lang", f"{where}: lang {n['lang']!r} is not a language code like fa, en, ar, fa-Latn"))
            ok = False
        if n["type"] not in TYPES:
            out.append(("error", "bad_name_type", f"{where}: type must be one of {', '.join(TYPES)}"))
            ok = False
        for k in ("from", "to"):
            v = n.get(k)
            if v is None:
                continue
            if not _year(v):
                out.append(("error", "bad_year", f"{where}: {k} {v!r} must be a whole year (or null)"))
                ok = False
            elif v == 0:
                out.append(("error", "year_zero", f"{where}: {k} is 0 - there is no year zero (1 BC = -1, AD 1 = 1)"))
                ok = False
            elif v < MIN_YEAR or v > today_year:
                out.append(("error", "bad_year", f"{where}: {k} {v} is outside {MIN_YEAR}..{today_year}"))
                ok = False
        if ok and _year(n.get("from")) and _year(n.get("to")) and n["from"] > n["to"]:
            out.append(("error", "reversed_period", f"{where}: from {n['from']} is after to {n['to']}"))
            ok = False
        if "preferred" in n and not isinstance(n["preferred"], bool):
            out.append(("error", "schema", f"{where}: preferred must be true or false"))
            ok = False
        if "note" in n and n["note"] is not None and not isinstance(n["note"], str):
            out.append(("error", "schema", f"{where}: note must be text or null"))
            ok = False
        if ok and n["type"] == "current" and n.get("to") is not None:
            out.append(("error", "current_ended", f"{where}: a current name cannot have an end ('to'); make it historical"))
            ok = False
        if ok and n["type"] == "historical" and n.get("from") is None and n.get("to") is None:
            out.append(("warning", "undated_historical", f"{where}: a historical name without a period is never chosen "
                                                         f"before a dated one"))
        if ok and isinstance(t, str) and isinstance(n["lang"], str) and _is_fa(n["lang"]) and FA_ARABIC.search(t):
            out.append(("warning", "arabic_letters", f"{where}: Arabic YEH / KAF in a Persian name - shown as "
                                                     f"{normalize_fa(t)!r}; the stored text is not changed"))
        if ok:
            good.append((i, n))
    # duplicates (same normalized text, language and type)
    seen = {}
    for i, n in good:
        key = (normalize_fa(n["text"].strip()).casefold(), n["lang"], n["type"])
        if key in seen:
            out.append(("warning", "duplicate_name", f"name {i} repeats name {seen[key]} ({n['text']!r}, {n['lang']}, {n['type']})"))
        else:
            seen[key] = i
    # ties name_at() could not decide: same language, both current / historical, overlapping, same specificity,
    # not exactly one of them preferred
    prim = [(i, n) for i, n in good if n["type"] in PRIMARY]
    for x in range(len(prim)):
        for y in range(x + 1, len(prim)):
            (i, a), (j, b) = prim[x], prim[y]
            if a["lang"] != b["lang"] or specificity(a) != specificity(b):
                continue
            ov = _overlap(a, b)
            if ov is None:
                continue
            if bool(a.get("preferred")) == bool(b.get("preferred")):
                span = "always" if ov == (MIN_YEAR, 10 ** 9) else f"years {ov[0]}..{ov[1] if ov[1] < 10 ** 9 else 'today'}"
                out.append(("error", "ambiguous_names", f"names {i} ({a['text']!r}) and {j} ({b['text']!r}) are both valid "
                                                        f"in '{a['lang']}' ({span}) with the same specificity: mark exactly "
                                                        f"one of them \"preferred\""))
    if good and not any(n["type"] in PRIMARY for _, n in good):
        out.append(("warning", "no_primary_name", "only alternative names: name_at() has nothing to choose"))
    return out


def name_at(location, year=None, lang="fa", fallback=None):
    """The name of `location` in `year` (None = today) and `lang`, by the rules in the module text; None if there is no
    current / historical name valid in that year in any language. Raises ValueError for year 0 or a non-integer year,
    and NameError_ if (unvalidated) data leaves a tie."""
    if year is not None and (not _year(year) or year == 0):
        raise ValueError(f"year must be a whole year other than 0 (1 BC = -1, AD 1 = 1), not {year!r}")
    names = [n for n in (location.get("names") or []) if isinstance(n, dict) and n.get("type") in PRIMARY
             and isinstance(n.get("text"), str) and isinstance(n.get("lang"), str)]
    if year is None:
        cands = [n for n in names if n["type"] == "current"]
    else:
        cands = [n for n in names if covers(n, year)]
    order = [lang] + [x for x in (DEFAULT_FALLBACK if fallback is None else fallback) if x != lang]
    order += sorted({n["lang"] for n in cands} - set(order))
    for lg in order:
        pool = [n for n in cands if n["lang"] == lg]
        if not pool:
            continue
        top = max(specificity(n) for n in pool)
        pool = [n for n in pool if specificity(n) == top]
        if len(pool) > 1:
            pref = [n for n in pool if n.get("preferred") is True]
            if len(pref) != 1:
                raise NameError_(f"{len(pool)} names tie for {lg} in {year}: {[n['text'] for n in pool]} (mark one preferred)")
            pool = pref
        n = pool[0]
        return {"text": n["text"], "display": normalize_fa(n["text"]) if _is_fa(n["lang"]) else n["text"], "lang": n["lang"],
                "type": n["type"], "from": n.get("from"), "to": n.get("to"), "fallback": lg != lang}
    return None
