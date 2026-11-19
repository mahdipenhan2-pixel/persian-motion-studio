#!/usr/bin/env python3
"""
Offline tests for the Studio layer (no API, no network, no browser). Run: python3 studio/tests/test_studio.py

1. every project.json under studio/projects validates
2. invalid projects are rejected with a clear message
3. generated script/config are accepted by the LOCKED Stage 2 core validator
4. composition builds from synthetic timing, has no leftover placeholders, and contains every sentence/scene
5. the locked core files were not modified (hashes in studio/CORE_HASHES.json)
"""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "studio" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))

import compose as C  # noqa: E402
import project as P  # noqa: E402
import story_stage2 as core  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def rejects(proj, needle, label):
    try:
        P.validate(copy.deepcopy(proj))
    except P.ProjectError as e:
        check(needle in str(e), f"rejects {label} ({e})")
        return
    check(False, f"rejects {label} (was accepted)")


def fake_timing(proj):
    cursor, rows = 0.3, []
    for s in P.sentences(proj):
        toks = s["text"].split()
        dur = 0.4 * len(toks)
        words = [{"i": i, "text": t, "abs_start": round(cursor + i * dur / len(toks), 3),
                  "abs_end": round(cursor + (i + 0.9) * dur / len(toks), 3), "status": "exact", "timing_quality": "exact"}
                 for i, t in enumerate(toks)]
        rows.append({"id": s["id"], "text": s["text"], "offset": round(cursor, 3), "duration": round(dur, 3), "words": words})
        cursor += dur + 0.35
    return {"audio": {"total": round(cursor + 0.8, 3), "gap": 0.35}, "sentences": rows, "summary": {"status": "OK"}}


def main():
    names = sorted(p.parent.name for p in (ROOT / "studio" / "projects").glob("*/project.json"))
    check(len(names) >= 1, f"found projects: {', '.join(names)}")
    for n in names:
        try:
            proj = P.load(n)
        except P.ProjectError as e:
            check(False, f"project {n} validates ({e})")
            continue
        check(True, f"project {n} validates")

        # 3. the locked core accepts what we generate
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "script.json").write_text(json.dumps(P.core_script(proj), ensure_ascii=False), encoding="utf-8")
            (td / "config.json").write_text(json.dumps(P.core_config(proj), ensure_ascii=False), encoding="utf-8")
            core.SCRIPT_PATH, core.CONFIG_PATH = td / "script.json", td / "config.json"
            try:
                core.load_inputs()
                check(True, f"{n}: generated script/config pass the locked core validator")
            except SystemExit as e:
                check(False, f"{n}: core validator rejected generated input ({e})")

            # 4. composition
            fonts = td / "fonts"
            fonts.mkdir()
            (fonts / "vazirmatn-arabic-400-normal.woff2").write_bytes(b"x")
            (fonts / "vazirmatn-arabic-700-normal.woff2").write_bytes(b"x")
            (td / "narration.wav").write_bytes(b"RIFF")
            theme = P.load_theme(proj["meta"]["theme"])
            timing = fake_timing(proj)
            info = C.compose(proj, theme, timing, td, fonts, td / "narration.wav")
            page = (td / "story" / "index.html").read_text(encoding="utf-8")
            left = [t for t in C.PLACEHOLDERS if t in page]
            check(not left, f"{n}: no leftover placeholders {left}")
            check(all(f'id="sent-{s["id"]}"' in page for s in timing["sentences"]), f"{n}: every sentence is in the page")
            check(all(f'id="scene-{sc["id"]}"' in page for sc in proj["scenes"]), f"{n}: every scene is in the page")
            check(info["scenes"] == len(proj["scenes"]), f"{n}: scene count matches")
            srt = (td / "story.srt").read_text(encoding="utf-8")
            check(srt.count(" --> ") == len(timing["sentences"]), f"{n}: SRT has one cue per sentence")

    # 2. negative tests
    base = P.load(names[0])
    p = copy.deepcopy(base); p["meta"]["format"] = "16:9"; rejects(p, "9:16", "16:9 (not supported yet)")
    p = copy.deepcopy(base); p["meta"]["lang"] = "de"; rejects(p, "meta.lang", "unknown language")
    p = copy.deepcopy(base); p["scenes"][0]["template"] = "nope"; rejects(p, "unknown", "unknown template")
    p = copy.deepcopy(base); p["scenes"][1]["id"] = p["scenes"][0]["id"]; rejects(p, "duplicate", "duplicate scene id")
    p = copy.deepcopy(base); p["scenes"][0]["id"] = "s_1"; rejects(p, "no underscore", "underscore in scene id")
    p = copy.deepcopy(base); p["scenes"][0]["narration"] = "کلمه " * 60; rejects(p, "limit", "over-long sentence")
    p = copy.deepcopy(base); p["scenes"][0]["on_screen"]["icon"] = "banana"; rejects(p, "not an icon", "unknown icon")
    p = copy.deepcopy(base); p["scenes"][0]["on_screen"]["title"] = "ا" * 60; rejects(p, "limit", "over-long title")
    p = copy.deepcopy(base); p["meta"]["theme"] = "missing"; rejects(p, "theme", "unknown theme")
    p = copy.deepcopy(base); p["scenes"] = []; rejects(p, "scenes", "empty scene list")

    # sentence splitting
    check(P.split_sentences("الف. ب؟ ج!") == ["الف.", "ب؟", "ج!"], "Persian sentence splitting")
    check(P.split_sentences("One. Two? Three!") == ["One.", "Two?", "Three!"], "English sentence splitting")

    # 5. locked core untouched
    hashes = ROOT / "studio" / "CORE_HASHES.json"
    if hashes.exists():
        want = json.loads(hashes.read_text(encoding="utf-8"))
        for rel, h in want.items():
            got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            check(got == h, f"locked core unchanged: {rel}")
    else:
        check(False, "studio/CORE_HASHES.json is missing")

    print("\n" + ("ALL TESTS PASSED" if not FAILS else f"{len(FAILS)} TEST(S) FAILED"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
