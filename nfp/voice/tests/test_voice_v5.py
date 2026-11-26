#!/usr/bin/env python3
"""Voice Engine V5 - the local Piper provider (real speech, free, offline), checked with REAL speech recognition:
  registry: the piper voices are valid, a piper voice without params.model is refused;
  plan: a piper sentence names its model and the model file's sha256 (part of the cache key); a missing model is
  refused with the command that fetches it ($NFP_PIPER_DIR pointing at an empty folder);
  produce, Persian and English, two speakers each with DIFFERENT Piper voices: mono 16-bit files at the run's rate, the
  planned pauses as silence, real speech (faster-whisper "small" recognises the text: similarity >= 0.6 Persian /
  0.85 English), the two voices of a language sound different (not the same samples); a second run is a cache hit;
  Gemini stays off (a gemini voice without voice.providers is refused when producing).
Needs the assets of nfp/setup/fetch_assets.py (piper voices, whisper model) and nfp/setup/requirements.txt; says so
and fails if they are missing (nothing is downloaded by the test).
  python3 nfp/voice/tests/test_voice_v5.py --work <dir outside the repository>
"""
import argparse
import difflib
import json
import os
import shutil
import sys
import wave
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
ROOT = NFP.parent
sys.path.insert(0, str(NFP))
from voice import casting as CA                   # noqa: E402
from voice import manifest as MA                  # noqa: E402
from voice import plan as PLN                     # noqa: E402
from voice import registry as RG                  # noqa: E402
from voice.cache import Cache                     # noqa: E402
from voice.providers import piper as PP           # noqa: E402

RESULTS = []
TEXT = {"fa": ["امروز داستان یک شهر قدیمی را تعریف می‌کنیم.", "خیابان‌ها پر از نور و صدای مردم است."],
        "en": ["Today we tell the story of an old harbour town.", "The streets are full of light and voices."]}
VOICES = {"fa": ("piper:fa-amir", "piper:fa-gyro"), "en": ("piper:en-lessac", "piper:en-ryan")}


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def cast(work, doc):
    p = Path(work) / f"{doc['project']}.cast.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return CA.load_casting(p)


def norm(t):
    return "".join(c for c in t if c.isalnum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    missing = [n for n in ("fa_IR-amir-medium", "fa_IR-gyro-medium", "en_US-lessac-medium", "en_US-ryan-medium") if not (PP.model_dir() / f"{n}.onnx").exists()]
    if missing or not PP.available():
        check(False, f"assets missing ({missing or 'piper-tts'}): run nfp/setup/fetch_assets.py and pip install -r nfp/setup/requirements.txt")
        return finish()

    print("== registry")
    reg = RG.load_registry()
    check(all(reg.get(v)["provider"] == "piper" for pair in VOICES.values() for v in pair), "the four piper voices are in the registry")
    bad = RG.validate_voice("piper:x", {"provider": "piper", "presentation": "male", "age": "adult", "languages": ["fa"], "verified": False})
    check(any("params.model" in p for p in bad), f"a piper voice without params.model is refused: {bad[:1]}")

    from faster_whisper import WhisperModel
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    wm = WhisperModel("small", device="cpu", compute_type="int8")
    for lang in ("fa", "en"):
        print(f"\n== {lang}: two speakers, two Piper voices, real speech")
        nv, rv = VOICES[lang]
        casting = cast(work, {"schema": "nfp.voice.casting/1", "project": f"v5-{lang}", "rules": {"block_mismatch": False},
                              "narrator": {"voice": nv}, "roles": {"guest": {"voice": rv}}})
        script = {"language": lang, "sentences": [{"id": "s1", "text": TEXT[lang][0], "pause_before_ms": 300},
                                                 {"id": "s2", "text": TEXT[lang][1], "speaker": "guest", "pause_after_ms": 200}]}
        plan = PLN.make_plan(casting, script, base_dir=str(work))
        rows = {r["id"]: r for r in plan["sentences"]}
        check(all(r["provider"] == "piper" and len(r["source"]["model_sha256"]) == 64 for r in rows.values())
              and rows["s1"]["source"]["model"] != rows["s2"]["source"]["model"],
              f"plan: {rows['s1']['voice']} ({rows['s1']['source']['model']}) / {rows['s2']['voice']} ({rows['s2']['source']['model']})")
        cache = Cache(work / f"cache-{lang}")
        out = work / f"out-{lang}"
        m = MA.produce(plan, out, base_dir=str(work), rate=24000, cache=cache)
        files = {r["id"]: out / r["file"] for r in m["sentences"]}
        fmt = []
        for sid, f in files.items():
            with wave.open(str(f), "rb") as w:
                fmt.append((w.getnchannels(), w.getsampwidth(), w.getframerate()))
        check(set(fmt) == {(1, 2, 24000)} and not m["synthetic"], f"mono 16-bit 24000 Hz files, not synthetic: {sorted(set(fmt))}")
        with wave.open(str(files["s1"]), "rb") as w:
            lead = w.readframes(int(0.28 * 24000))
        check(max(abs(int.from_bytes(lead[i:i + 2], "little", signed=True)) for i in range(0, len(lead), 2)) == 0,
              "s1: the planned 300 ms pause is silence at the start")
        for sid, f in files.items():
            segs, _ = wm.transcribe(str(f), language=lang)
            heard = " ".join(s.text for s in segs).strip()
            ratio = difflib.SequenceMatcher(None, norm(heard), norm(rows[sid]["text"])).ratio()
            check(ratio >= (0.6 if lang == "fa" else 0.85), f"{sid} REAL speech, Whisper heard: '{heard}' (similarity {ratio:.2f})")
        with wave.open(str(files["s1"]), "rb") as w1, wave.open(str(files["s2"]), "rb") as w2:
            check(w1.readframes(24000) != w2.readframes(24000), "the two speakers' files are different audio")
        m2 = MA.produce(plan, work / f"out2-{lang}", base_dir=str(work), rate=24000, cache=cache)
        check(all(r["cache"]["hit"] for r in m2["sentences"]), "a second run: every sentence from the cache (no synthesis)")

    print("\n== a missing model, Gemini off")
    keep = os.environ.get("NFP_PIPER_DIR")
    os.environ["NFP_PIPER_DIR"] = str(work / "empty")
    (work / "empty").mkdir()
    try:
        PLN.make_plan(cast(work, {"schema": "nfp.voice.casting/1", "project": "x", "rules": {"block_mismatch": False},
                                  "narrator": {"voice": "piper:fa-amir"}, "roles": {}}),
                      {"language": "fa", "sentences": [{"id": "s1", "text": "سلام"}]}, base_dir=str(work))
        check(False, "a missing model is refused")
    except RG.VoiceError as e:
        check("fetch_assets.py" in str(e), f"a missing model is refused with the fetch command: {str(e)[:110]}")
    finally:
        os.environ.pop("NFP_PIPER_DIR") if keep is None else os.environ.update(NFP_PIPER_DIR=keep)
    gplan = PLN.make_plan(cast(work, {"schema": "nfp.voice.casting/1", "project": "g", "rules": {"block_mismatch": False},
                                      "narrator": {"voice": "gemini:Charon"}, "roles": {}}),
                          {"language": "fa", "sentences": [{"id": "s1", "text": "سلام دنیا"}]}, base_dir=str(work))
    try:
        MA.produce(gplan, work / "g", base_dir=str(work))
        check(False, "gemini without voice.providers is refused")
    except RG.VoiceError as e:
        check("no connection" in str(e) or "explicitly enabled" in str(e), "Gemini stays off: a gemini voice without voice.providers is refused, nothing sent")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL VOICE V5 TESTS PASSED" if not f else "VOICE V5 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
