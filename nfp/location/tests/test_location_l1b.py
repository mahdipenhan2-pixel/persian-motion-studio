#!/usr/bin/env python3
"""L1b - Location Engine names: current / historical / alternative, languages, periods without a year zero,
name_at(location, year, lang), Persian letter normalization. Offline, no files written.

  python3 nfp/location/tests/test_location_l1b.py

Every name, period and coordinate here is SYNTHETIC test data ("Testabad" etc.), not a claim about a real place.
"""
import copy
import datetime
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent.parent), str(HERE)]
import location as L                       # noqa: E402
from test_location_l1a import place, doc   # noqa: E402  (the L1a record builder, unchanged)

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
YE, KAF = "ي", "ك"               # Arabic YEH / KAF


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def nm(text, lang, typ, frm=None, to=None, **kw):
    n = {"text": text, "lang": lang, "type": typ}
    if frm is not None:
        n["from"] = frm
    if to is not None:
        n["to"] = to
    n.update(kw)
    return n


def run(*rows):
    return L.validate(doc(*rows), today=TODAY)


def codes(rep, level=None):
    return [x["code"] for x in rep["issues"] if level is None or x["level"] == level]


# a synthetic place with a long history (all invented): BC name, a classical name across BC/AD, a medieval name,
# today's names in fa / en, an alias
HIST = [nm("Testa Antiqua", "la", "historical", -500, -1),
        nm("Testopolis", "la", "historical", 1, 640),
        nm("Testopolis", "en", "historical", -300, 640),
        nm("تست‌شهر کهن", "fa", "historical", 641, 1500),
        nm("تست‌آباد", "fa", "current", 1501),
        nm("Testabad", "en", "current", 1501),
        nm("Testaabad", "en", "alternative")]


def at(names, year, lang="fa", **kw):
    r = L.name_at(place(names=names), year, lang, **kw)
    return None if r is None else (r["text"], r["lang"], r["type"], r["fallback"])


def main():
    print("== compatibility with L1a")
    r = run(place())
    check(r["locations"]["test-place"] == "verified" and "no_names" in codes(r, "info") and r["status"] == "OK",
          "an L1a record without names: still valid and verified (names are optional), info 'no_names'")
    r = run(place(names=HIST))
    check(r["status"] == "OK" and r["locations"]["test-place"] == "verified" and not codes(r, "error"),
          f"a record with a full name history: valid, verified {codes(r, 'warning')}")
    check(L.name_at(place(), 2000, "fa") is None, "name_at on a record without names: None (no guessing)")
    check(set(L.NAME_TYPES) == {"current", "historical", "alternative"}, "name types: current, historical, alternative")

    print("\n== name_at: years, periods, BC / AD without a year zero")
    for year, lang, want in ((-500, "la", ("Testa Antiqua", "la", "historical", False)),
                             (-1, "la", ("Testa Antiqua", "la", "historical", False)),      # last BC year
                             (1, "la", ("Testopolis", "la", "historical", False)),         # AD 1 follows 1 BC directly
                             (640, "la", ("Testopolis", "la", "historical", False)),       # inclusive end
                             (-301, "en", ("Testa Antiqua", "la", "historical", True)),    # before the en period: other language
                             (-300, "en", ("Testopolis", "en", "historical", False)),      # inclusive start
                             (641, "fa", ("تست‌شهر کهن", "fa", "historical", False)),
                             (1500, "fa", ("تست‌شهر کهن", "fa", "historical", False)),
                             (1501, "fa", ("تست‌آباد", "fa", "current", False)),
                             (2026, "en", ("Testabad", "en", "current", False)),
                             (None, "fa", ("تست‌آباد", "fa", "current", False)),
                             (None, "en", ("Testabad", "en", "current", False))):
        check(at(HIST, year, lang) == want, f"year {year} ({lang}): {at(HIST, year, lang)}")
    check(at(HIST, -501, "fa") is None, "before every period (year -501): None")
    for bad in (0, 1.5, "1500", True):
        try:
            L.name_at(place(names=HIST), bad, "fa")
            ok = False
        except ValueError:
            ok = True
        check(ok, f"name_at refuses year {bad!r} (there is no year 0; whole years only)")

    print("\n== language fallback (fixed order)")
    check(at(HIST, 700, "en") == ("تست‌شهر کهن", "fa", "historical", True),
          "en wanted, only fa valid in 700: fa, marked fallback")
    check(at(HIST, 300, "fa") == ("Testopolis", "en", "historical", True),
          "fa wanted in 300: default order fa -> en -> fa -> others: the en name (fallback)")
    check(at(HIST, 300, "fa", fallback=["la"]) == ("Testopolis", "la", "historical", True),
          "a given fallback list is used in its order (fa -> la)")
    check(at(HIST, 300, "de") == ("Testopolis", "en", "historical", True), "an unknown language falls back to en first")
    only_ar = [nm("تستين", "ar", "current"), nm("Testbu", "tr", "current")]
    check(at(only_ar, 2000, "fa") == ("تستين", "ar", "current", True),
          "no fa / en name: the other languages in alphabetical order of their code (ar before tr)")
    check(at([nm("Testaabad", "en", "alternative")], 2000, "en") is None, "alternative names are never chosen by name_at")

    print("\n== simultaneous names: specificity, preferred, no ambiguity")
    spec = [nm("تست‌آباد", "fa", "current"), nm("تست‌آباد قدیم", "fa", "historical", 1800, 1900)]
    check(at(spec, 1850) == ("تست‌آباد قدیم", "fa", "historical", False) and at(spec, 1950)[0] == "تست‌آباد",
          "a dated historical name beats an undated current name inside its period; the current one outside it")
    tie = [nm("الف", "fa", "historical", 100, 300), nm("ب", "fa", "historical", 200, 400)]
    r = run(place(names=tie))
    check("ambiguous_names" in codes(r, "error") and r["locations"]["test-place"] == "draft" and "200..300" in json.dumps(r["issues"], ensure_ascii=False),
          "two names valid in the same years (200..300), same language and specificity: refused, the overlap is named")
    try:
        L.name_at(place(names=tie), 250, "fa")
        raised = False
    except L.names.NameError_:
        raised = True
    check(raised, "name_at on such unvalidated data raises instead of picking one")
    pref = copy.deepcopy(tie)
    pref[1]["preferred"] = True
    r = run(place(names=pref))
    check(not codes(r, "error") and at(pref, 250) == ("ب", "fa", "historical", False) and at(pref, 150)[0] == "الف",
          "exactly one marked preferred: accepted, it wins in the overlap; outside it the other name")
    both = copy.deepcopy(pref)
    both[0]["preferred"] = True
    check("ambiguous_names" in codes(run(place(names=both)), "error"), "both preferred: still ambiguous, refused")
    two_now = [nm("تست‌آباد", "fa", "current"), nm("تستاباد", "fa", "current")]
    check("ambiguous_names" in codes(run(place(names=two_now)), "error"), "two undated current names in one language: refused")
    check(not codes(run(place(names=[nm("الف", "fa", "historical", 100, 199), nm("ب", "fa", "historical", 200, 300)])), "error"),
          "touching periods (…199 / 200…) do not overlap")
    check(not codes(run(place(names=[nm("A", "en", "historical", -50, -1), nm("B", "en", "historical", 1, 50)])), "error"),
          "-50..-1 and 1..50: no overlap across the BC / AD change")
    check(not codes(run(place(names=[nm("Test", "en", "current"), nm("تست", "fa", "current")])), "error"),
          "the same time in two languages is not a conflict")

    print("\n== period checks")
    for n, code in ((nm("x", "en", "historical", 300, 100), "reversed_period"), (nm("x", "en", "historical", 0, 10), "year_zero"),
                    (nm("x", "en", "historical", -10, 0), "year_zero"), (nm("x", "en", "historical", 1.5, 10), "bad_year"),
                    (nm("x", "en", "historical", "300", 400), "bad_year"), (nm("x", "en", "historical", True, 10), "bad_year"),
                    (nm("x", "en", "historical", 100, 2027), "bad_year"), (nm("x", "en", "historical", -10001, 5), "bad_year"),
                    (nm("x", "en", "current", 100, 200), "current_ended")):
        r = run(place(names=[n]))
        check(code in codes(r, "error") and r["locations"]["test-place"] == "draft", f"{code}: from {n.get('from')!r} to {n.get('to')!r} ({n['type']})")
    check("undated_historical" in codes(run(place(names=[nm("x", "en", "historical"), nm("y", "en", "current")])), "warning"),
          "a historical name without a period: warning")

    print("\n== structure and languages")
    for n, code in (({"text": "x", "lang": "en"}, "schema"), (nm("x", "en", "current", colour=1), "schema"),
                    (nm("", "en", "current"), "schema"), (nm(5, "en", "current"), "schema"), (nm("x", "english", "current"), "bad_lang"),
                    (nm("x", "EN", "current"), "bad_lang"), (nm("x", None, "current"), "bad_lang"), (nm("x", "en", "official"), "bad_name_type"),
                    (nm("x", "en", "current", preferred="yes"), "schema"), (nm("x", "en", "current", note=3), "schema"), ("x", "schema")):
        check(code in codes(run(place(names=[n])), "error"), f"refused ({code}): {json.dumps(n, ensure_ascii=False)[:60]}")
    for lang in ("fa", "en", "ar", "la", "fa-Latn", "en-GB", "es-419"):
        check(not codes(run(place(names=[nm("x", lang, "current")])), "error"), f"language code {lang} accepted")
    check("schema" in codes(run(place(names="Testabad")), "error") and "no_names" in codes(run(place(names=[])), "warning"),
          "names not a list: refused; an empty list: warning")
    check("no_primary_name" in codes(run(place(names=[nm("x", "en", "alternative")])), "warning"), "only alternative names: warning")
    check("duplicate_name" in codes(run(place(names=[nm("Testabad", "en", "alternative"), nm("testabad", "en", "alternative")])), "warning"),
          "the same name twice (case-insensitive): warning")

    print("\n== Persian normalization: for display / matching, the stored text never changes")
    arabic = "ت" + YE + "ل" + KAF + "ه"          # 'tileke' written with Arabic YEH / KAF (synthetic)
    check(L.normalize_fa(arabic) == "تیلکه" and L.normalize_fa("تیلکه") == "تیلکه" and L.normalize_fa("abc") == "abc",
          "normalize_fa: Arabic YEH -> Persian YEH, Arabic KAF -> KEHEH; other text unchanged")
    check(L.normalize_fa("ى") == "ی", "ALEF MAKSURA -> Persian YEH")
    names = [nm(arabic, "fa", "current")]
    rec = place(names=names)
    before = json.dumps(rec, ensure_ascii=False)
    r = L.validate(doc(rec), today=TODAY)
    res = L.name_at(rec, None, "fa")
    check("arabic_letters" in codes(r, "warning") and json.dumps(rec, ensure_ascii=False) == before and rec["names"][0]["text"] == arabic,
          "an Arabic-letter Persian name: warning, and the record itself is not rewritten")
    check(res["text"] == arabic and res["display"] == "تیلکه", "name_at returns the stored text and a normalized 'display'")
    check("arabic_letters" not in codes(run(place(names=[nm(arabic, "ar", "current")])), "warning"),
          "the same letters in an Arabic (ar) name: no warning (they are right there)")
    check(L.name_at(place(names=[nm("Testabad", "en", "current")]), None, "en")["display"] == "Testabad",
          "display of a non-Persian name is the text itself")
    check("duplicate_name" in codes(run(place(names=[nm(arabic, "fa", "alternative"), nm("تیلکه", "fa", "alternative")])), "warning"),
          "duplicates are found across Arabic / Persian letter forms")
    check("name_not_nfc" in codes(run(place(names=[nm("Testé", "en", "current")])), "warning") and
          "name_spacing" in codes(run(place(names=[nm(" Testabad", "en", "current")])), "warning"),
          "non-NFC text and stray spaces: warnings (text kept as written)")

    print("\n== determinism and API")
    rep1 = json.dumps(run(place(names=HIST)), ensure_ascii=False)
    rep2 = json.dumps(run(place(names=HIST)), ensure_ascii=False)
    picks = [at(HIST, y, lg) for y in (-400, -1, 1, 300, 700, 1600, None) for lg in ("fa", "en", "la")]
    check(rep1 == rep2 and picks == [at(HIST, y, lg) for y in (-400, -1, 1, 300, 700, 1600, None) for lg in ("fa", "en", "la")],
          "deterministic reports and name choices")
    shuffled = place(names=list(reversed(HIST)))
    check([at(list(reversed(HIST)), y, lg) for y in (-400, 1, 700, 1600, None) for lg in ("fa", "en")] ==
          [at(HIST, y, lg) for y in (-400, 1, 700, 1600, None) for lg in ("fa", "en")] and not codes(run(shuffled), "error"),
          "the order the names are written in does not change any choice")
    rec = place(names=HIST)
    snap = copy.deepcopy(rec)
    L.name_at(rec, 700, "fa")
    L.validate(doc(rec), today=TODAY)
    check(rec == snap, "name_at / validate never modify the record")
    for k in ("validate", "check_point", "source_problems", "load", "SCHEMA", "FIELDS", "KINDS"):
        check(hasattr(L, k), f"L1a API kept: location.{k}")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL LOCATION L1b TESTS PASSED" if not f else "LOCATION L1b TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
