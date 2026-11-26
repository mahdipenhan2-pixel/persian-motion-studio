#!/usr/bin/env python3
"""V1 tests of the NFP Voice Engine - offline, synthetic data only, no API / TTS / download, nothing written to the
repository (every output goes to a temporary folder).

  A registry      built-in voices valid; project voices; unknown voice / bad attributes refused
  B casting       C1 lock read (read only); WARNING by default; OVERRIDE with a reason; BLOCK only with block_mismatch;
                  override without reason, unknown character / voice, changed fingerprint -> errors; stages; unverified
  C plan          several speakers and sentences (fa + en); speaker -> voice -> source; pauses; language check;
                  prepared files; deterministic; cache key reacts to what changes the audio
  D providers     synthetic: mono 16-bit, rate, exact pauses, distinct pitch per speaker, deterministic;
                  prepared: samples copied unchanged + pauses; wrong rate / stereo / changed file refused
  E manifest      produced + valid; tampering, missing file, wrong schema detected
  F core          the produced files go through the UNCHANGED Stage 2 prepare (read-only import, temp folder)
  G independence  nfp/voice imports nothing of Film / Studio / network; core and C1 untouched
Run: python3 nfp/voice/tests/test_voice_v1.py
"""
import array
import copy
import io
import json
import math
import re
import shutil
import sys
import tempfile
import wave
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
VOICE = HERE.parent
NFP = VOICE.parent
ROOT = NFP.parent
sys.path.insert(0, str(NFP))
from voice import VoiceError, load_casting, load_registry, make_plan, produce, validate_manifest  # noqa: E402
from voice.casting import BUILD_EXPECT  # noqa: E402

FIX = HERE / "fixtures" / "voice-demo"
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def refused(fn, *needles):
    try:
        fn()
    except VoiceError as e:
        text = "\n".join(e.problems)
        return all(n in text for n in needles), text.splitlines()[0][:150]
    return False, "accepted"


def casting_variant(td, mutate):
    d = Path(td) / "proj"
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FIX, d)
    c = json.loads((d / "voices.cast.json").read_text(encoding="utf-8"))
    mutate(c)
    (d / "voices.cast.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    return d


def script():
    return json.loads((FIX / "script.json").read_text(encoding="utf-8"))


def levels(findings, code=None):
    return sorted({f["level"] for f in findings if code is None or f["code"] == code})


def pitch(path, t0, t1):
    """Dominant frequency (Hz) of a tone segment from zero crossings."""
    with wave.open(str(path), "rb") as w:
        r = w.getframerate()
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
    seg = a[int(t0 * r):int(t1 * r)]
    z = sum(1 for i in range(1, len(seg)) if (seg[i - 1] < 0) != (seg[i] < 0))
    return z / 2 / ((t1 - t0))


def tone_wav(path, rate, seconds, channels=1, f=180.0):
    n = int(rate * seconds)
    a = array.array("h", [int(6000 * math.sin(2 * math.pi * f * k / rate)) for k in range(n)])
    data = a.tobytes() if channels == 1 else b"".join(a[i:i + 1].tobytes() * 2 for i in range(n))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data)


def main():
    print("== A registry")
    reg = load_registry()
    check(len(reg.ids()) == 16 and len([v for v in reg.ids() if v.startswith("piper:")]) == 4 and reg.get("synthetic:male")["presentation"] == "male" and reg.speaks("synthetic:male", "de"),
          f"built-in registry valid ({len(reg.ids())} voices); synthetic voices speak any language ('*'), new languages need no code")
    check(not reg.get("gemini:Kore")["verified"] and reg.speaks("gemini:Kore", "fa") and not reg.speaks("gemini:Kore", "de"),
          "Gemini voices are listed with verified: false and their languages")
    ok, msg = refused(lambda: reg.get("gemini:Nobody"), "not in the registry")
    check(ok, f"unknown voice refused ({msg[:80]})")
    for desc, v, needle in (("bad presentation", {"provider": "prepared", "presentation": "robot", "age": "adult", "languages": ["en"], "verified": True}, "presentation"),
                            ("prefix != provider", {"provider": "synthetic", "presentation": "male", "age": "adult", "languages": ["en"], "verified": True, "params": {"f0": 100}}, "prefix"),
                            ("bad language code", {"provider": "prepared", "presentation": "male", "age": "adult", "languages": ["english"], "verified": True}, "ISO 639"),
                            ("redefines a built-in voice", None, "redefines")):
        extra = {"synthetic:male": {}} if v is None else {("prepared:x" if "prefix" not in desc else "prepared:y"): v}
        ok, msg = refused(lambda: load_registry(extra=extra), needle)
        check(ok, f"project voice refused: {desc} ({msg[:90]})")

    print("\n== B casting (warning / override / block)")
    c = load_casting(FIX / "voices.cast.json")
    check(c["findings"] == [] and sorted(c["roles"]) == ["lina", "omid", "sara"] and c["narrator"]["voice"] == "synthetic:narrator",
          "fixture casting: C1 cast read and lock checked, 3 roles + narrator, no findings (every voice fits)")
    with tempfile.TemporaryDirectory() as td:
        d = casting_variant(td, lambda x: x["roles"]["omid"].update(voice="synthetic:female"))
        c2 = load_casting(d / "voices.cast.json")
        w = [f for f in c2["findings"] if f["role"] == "omid"]
        check(levels(w) == ["warning"] and w[0]["code"] == "voice_mismatch" and "female voice for a male character" in w[0]["message"],
              f"default: a man with a female voice is a WARNING, nothing is blocked ({w[0]['message'][:70]})")
        d = casting_variant(td, lambda x: x["roles"]["omid"].update(voice="synthetic:female", override={"reason": "voice-over by a female narrator, decided by the director"}))
        c3 = load_casting(d / "voices.cast.json")
        w = [f for f in c3["findings"] if f["role"] == "omid"]
        check(levels(w) == ["override"] and "decided by the director" in w[0]["message"],
              "manual override with a reason: recorded as OVERRIDE (no warning), the reason is kept")
        d = casting_variant(td, lambda x: x["roles"]["omid"].update(voice="synthetic:female", override={"reason": " "}))
        ok, msg = refused(lambda: load_casting(d / "voices.cast.json"), "non-empty 'reason'")
        check(ok, f"override without a reason is an error ({msg[:80]})")
        d = casting_variant(td, lambda x: (x["roles"]["omid"].update(voice="synthetic:female"), x["rules"].update(block_mismatch=True)))
        ok, msg = refused(lambda: load_casting(d / "voices.cast.json"), "BLOCK omid", "block_mismatch")
        check(ok, f"block_mismatch: true -> the mismatch is BLOCKED ({msg[:90]})")
        d = casting_variant(td, lambda x: (x["roles"]["omid"].update(voice="synthetic:female", override={"reason": "intended"}),
                                           x["rules"].update(block_mismatch=True)))
        ok, msg = refused(lambda: load_casting(d / "voices.cast.json"), "BLOCK omid", "override does not lift")
        check(ok, f"block_mismatch is ABSOLUTE: an override with a reason does not lift it ({msg[:100]})")
        d = casting_variant(td, lambda x: (x["roles"]["omid"].update(voice="synthetic:female", override={"reason": ""}),
                                           x["rules"].update(block_mismatch=True)))
        ok, msg = refused(lambda: load_casting(d / "voices.cast.json"), "non-empty 'reason'", "BLOCK omid")
        check(ok, "block_mismatch + an override without reason: both the invalid override and the block are reported")
        d = casting_variant(td, lambda x: x["rules"].update(block_mismatch=True))
        check(load_casting(d / "voices.cast.json")["findings"] == [],
              "block_mismatch with fitting voices: nothing is blocked (the rule only stops real mismatches)")
        d = casting_variant(td, lambda x: x["roles"]["sara"].pop("stages"))
        c5 = load_casting(d / "voices.cast.json")
        codes = sorted({f["code"] for f in c5["findings"] if f["role"] == "sara"})
        check(codes == ["stages_differ"], f"one voice for a child and an adult stage: warning 'stages_differ' ({codes})")
        d = casting_variant(td, lambda x: x["roles"]["sara"]["stages"].update(child="synthetic:male"))
        w = [f for f in load_casting(d / "voices.cast.json")["findings"] if f["role"] == "sara@child"]
        check(levels(w) == ["warning"] and "adult voice for a child character" in w[0]["message"],
              f"age is checked per stage: an adult voice for the child stage warns ({w[0]['message'][:60] if w else ''})")
        d = casting_variant(td, lambda x: x["roles"]["lina"].update(voice="gemini:Kore"))
        w = [f for f in load_casting(d / "voices.cast.json")["findings"] if f["role"] == "lina"]
        check([f["code"] for f in w] == ["unverified_voice"], "a voice with verified: false is reported (warning), its fit is still checked")
        d = casting_variant(td, lambda x: x["roles"]["lina"].update(voice="synthetic:male", expect={"presentation": "male", "age": "adult"}))
        check(not [f for f in load_casting(d / "voices.cast.json")["findings"] if f["role"] == "lina"],
              "an explicit 'expect' replaces the C1 build inference (no guess from the build)")
        for desc, mut, needles in (
                ("unknown voice", lambda x: x["roles"]["lina"].update(voice="synthetic:ghost"), ("not in the registry",)),
                ("unknown character", lambda x: x["roles"].update(nobody={"voice": "synthetic:male"}), ("not a character of the C1 cast",)),
                ("changed character (fingerprint)", lambda x: x["roles"]["lina"].update(fingerprint="0" * 64), ("differs from the C1 lock",)),
                ("stage the character does not have", lambda x: x["roles"]["lina"].update(stages={"elder": "synthetic:male"}), ("not a stage",)),
                ("role named narrator", lambda x: x["roles"].update(narrator={"voice": "synthetic:male"}), ("cannot be 'narrator'",)),
                ("no narrator", lambda x: x.pop("narrator"), ("narrator",)),
                ("unknown rule", lambda x: x["rules"].update(strict=True), ("casting.rules",)),
                ("unknown field", lambda x: x["roles"]["lina"].update(colour=1), ("unknown field",))):
            d = casting_variant(td, mut)
            ok, msg = refused(lambda: load_casting(d / "voices.cast.json"), *needles)
            check(ok, f"casting error: {desc} ({msg[:90]})")
        d = casting_variant(td, lambda x: None)
        cj = json.loads((d / "voice-demo-cast" / "cast.json").read_text(encoding="utf-8"))
        cj["characters"][0]["identity"]["skin"] = "#000000"
        (d / "voice-demo-cast" / "cast.json").write_text(json.dumps(cj), encoding="utf-8")
        ok, msg = refused(lambda: load_casting(d / "voices.cast.json"), "C1 cast was refused", "identity changed")
        check(ok, f"the C1 identity lock is enforced through C1 itself ({msg[:90]})")

    print("\n== C plan (several speakers, fa + en)")
    p = make_plan(c, script(), base_dir=FIX)
    sp = {r["id"]: (r["speaker"], r["voice"], r["language"]) for r in p["sentences"]}
    check(sp == {"s1": ("narrator", "synthetic:narrator", "en"), "s2": ("lina", "synthetic:female", "fa"), "s3": ("omid", "synthetic:male", "en"),
                 "s4": ("sara", "synthetic:child", "en"), "s5": ("narrator", "synthetic:narrator", "en")},
          f"5 sentences, 4 speakers: each sentence -> its speaker -> that speaker's voice (stage voice for sara@child), per-sentence language")
    check(p["speakers"]["narrator"]["sentences"] == ["s1", "s5"] and len(p["speakers"]) == 4, f"speakers summary {list(p['speakers'])}")
    check(make_plan(c, script(), base_dir=FIX) == p and len(p["digest"]) == 64, "deterministic: same input -> identical plan (digest)")
    keys = {r["id"]: r["cache_key"] for r in p["sentences"]}
    s2 = script(); s2["sentences"][2]["pause_after_ms"] = 300
    keys2 = {r["id"]: r["cache_key"] for r in make_plan(c, s2, base_dir=FIX)["sentences"]}
    check(keys2["s3"] != keys["s3"] and all(keys2[k] == keys[k] for k in keys if k != "s3"),
          "cache key changes only for the sentence whose audio changes (a pause)")
    s3 = script(); s3["sentences"][1]["speaker"] = "ghost"
    ok, msg = refused(lambda: make_plan(c, s3, base_dir=FIX), "speaker 'ghost'")
    check(ok, f"unknown speaker refused ({msg[:80]})")
    s4 = script(); s4["sentences"][0]["pause_before_ms"] = 9000
    ok, msg = refused(lambda: make_plan(c, s4, base_dir=FIX), "pause")
    check(ok, f"pause outside 0..5000 ms refused ({msg[:80]})")
    with tempfile.TemporaryDirectory() as td:
        d = casting_variant(td, lambda x: x["roles"]["lina"].update(voice="gemini:Kore"))
        cg = load_casting(d / "voices.cast.json")
        sg = script(); sg["sentences"][1]["language"] = "de"
        pg = make_plan(cg, sg, base_dir=d)
        check(levels(pg["findings"], "language_mismatch") == ["warning"], "a voice not listed for the sentence language: warning")
        d = casting_variant(td, lambda x: (x["roles"]["lina"].update(voice="gemini:Kore"), x["rules"].update(block_mismatch=True)))
        ok, msg = refused(lambda: make_plan(load_casting(d / "voices.cast.json"), sg, base_dir=d), "BLOCK lina", "language")
        check(ok, f"... and blocked with block_mismatch ({msg[:80]})")
        d = casting_variant(td, lambda x: x["roles"]["lina"].update(voice="gemini:Kore", override={"reason": "German line read by the host"}))
        pl = make_plan(load_casting(d / "voices.cast.json"), sg, base_dir=d)
        check(levels(pl["findings"], "language_mismatch_overridden") == ["override"] and not levels(pl["findings"], "language_mismatch"),
              "warning mode: an override with a reason turns the language warning into a recorded OVERRIDE")
        d = casting_variant(td, lambda x: (x["roles"]["lina"].update(voice="gemini:Kore", override={"reason": "German line read by the host"}),
                                           x["rules"].update(block_mismatch=True)))
        ok, msg = refused(lambda: make_plan(load_casting(d / "voices.cast.json"), sg, base_dir=d), "BLOCK lina", "override does not lift")
        check(ok, f"block_mismatch is absolute for languages too: the override does not lift it ({msg[:80]})")
        check(make_plan(cg, script(), base_dir=d)["sentences"][1]["provider"] == "gemini",
              "a Gemini voice can be cast and planned for review (provider 'gemini')")

    print("\n== D providers + E manifest")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out"
        m = produce(p, out, base_dir=FIX, rate=24000)
        check(validate_manifest(out / "voice_manifest.json") == [] and len(m["sentences"]) == 5 and m["synthetic"],
              "manifest produced and valid: 5 sentence files, marked synthetic")
        infos = []
        for r in m["sentences"]:
            with wave.open(str(out / r["file"]), "rb") as w:
                infos.append((w.getnchannels(), w.getsampwidth(), w.getframerate()))
        check(set(infos) == {(1, 2, 24000)}, "every file is mono 16-bit 24000 Hz (the format the core accepts)")
        exact = True
        for r in m["sentences"]:
            sw = m["synthetic_words"][r["id"]]
            a = array.array("h")
            with wave.open(str(out / r["file"]), "rb") as w:
                a.frombytes(w.readframes(w.getnframes()))
            lead = int(round(r["pause_before_ms"] / 1000 * 24000))
            tail = int(round(r["pause_after_ms"] / 1000 * 24000))
            exact &= all(v == 0 for v in a[:lead]) and (tail == 0 or all(v == 0 for v in a[-tail:])) and abs(sw[0][0] - r["pause_before_ms"] / 1000) < 1e-6
        check(exact, "pauses before / after are exact silence of the planned length inside each sentence file")
        f0 = {r["speaker"] + (f"@{r['stage']}" if r["stage"] else ""): round(pitch(out / r["file"], *m["synthetic_words"][r["id"]][0][:2]))
              for r in m["sentences"]}
        check(all(abs(f0[k] - v) / v < 0.03 for k, v in {"narrator": 160, "lina": 220, "omid": 110, "sara@child": 300}.items()),
              f"each speaker sounds different: measured pitch {f0} Hz")
        out2 = Path(td) / "out2"
        produce(p, out2, base_dir=FIX, rate=24000)
        check(all((out / r["file"]).read_bytes() == (out2 / r["file"]).read_bytes() for r in m["sentences"]),
              "deterministic: producing twice gives byte-identical files")
        m48 = produce(p, Path(td) / "out48", base_dir=FIX, rate=48000)
        check(m48["sample_rate"] == 48000 and all(abs(a["duration"] - b["duration"]) <= 1 / 24000 for a, b in zip(m["sentences"], m48["sentences"])),
              "another run rate (48000 Hz): same durations, one rate for every sentence")
        # tampering
        bad = Path(td) / "bad"; shutil.copytree(out, bad)
        raw = bytearray((bad / "audio" / "s3.wav").read_bytes()); raw[-2] ^= 0x7F
        (bad / "audio" / "s3.wav").write_bytes(bytes(raw))
        (bad / "audio" / "s4.wav").unlink()
        pr = validate_manifest(bad / "voice_manifest.json")
        check(any("s3" in x and "sha256" in x for x in pr) and any("s4" in x and "missing" in x for x in pr),
              f"validation detects a changed file and a missing file ({len(pr)} problems)")
        mj = json.loads((out / "voice_manifest.json").read_text(encoding="utf-8")); mj["schema"] = "x"
        (bad / "voice_manifest.json").write_text(json.dumps(mj), encoding="utf-8")
        check(validate_manifest(bad / "voice_manifest.json") == ["manifest: schema must be 'nfp.voice.manifest/1'"], "wrong schema refused")

        # prepared recordings (made here, synthetic): exact copy + pauses; wrong format refused
        proj = Path(td) / "prep"; shutil.copytree(FIX, proj); (proj / "rec").mkdir()
        tone_wav(proj / "rec" / "s2.wav", 24000, 1.5)
        cj = json.loads((proj / "voices.cast.json").read_text(encoding="utf-8"))
        cj["roles"]["lina"]["voice"] = "prepared:host-recording"
        (proj / "voices.cast.json").write_text(json.dumps(cj), encoding="utf-8")
        cp = load_casting(proj / "voices.cast.json")
        sc = script()
        ok, msg = refused(lambda: make_plan(cp, sc, base_dir=proj), "needs 'audio'")
        check(ok, f"a prepared-recording voice without a file for its sentence is refused ({msg[:80]})")
        sc["sentences"][1]["audio"] = "rec/s2.wav"
        pp = make_plan(cp, sc, base_dir=proj)
        check(pp["sentences"][1]["provider"] == "prepared" and len(pp["sentences"][1]["source"]["sha256"]) == 64,
              "sentence with 'audio': provider 'prepared', the file's sha256 is in the plan")
        mp = produce(pp, Path(td) / "outp", base_dir=proj, rate=24000)
        with wave.open(str(proj / "rec" / "s2.wav"), "rb") as w:
            src = w.readframes(w.getnframes())
        got = (Path(td) / "outp" / "audio" / "s2.wav").read_bytes()
        with wave.open(str(Path(td) / "outp" / "audio" / "s2.wav"), "rb") as w:
            got = w.readframes(w.getnframes())
        lead = int(0.3 * 24000) * 2
        check(got[:lead] == b"\0" * lead and got[lead:lead + len(src)] == src and len(got) == lead + len(src),
              "prepared audio: the recording's samples are copied unchanged, the planned 300 ms pause is added before it")
        check(validate_manifest(Path(td) / "outp" / "voice_manifest.json") == [] and mp["sentences"][1]["source"]["file"] == "rec/s2.wav",
              "manifest of a mixed project (synthetic + prepared) is valid")
        tone_wav(proj / "rec" / "s2.wav", 22050, 1.5)
        ok, msg = refused(lambda: produce(pp, Path(td) / "x", base_dir=proj), "changed after planning")
        check(ok, f"a recording changed after planning is refused ({msg[:70]})")
        for desc, kw, needle in (("22050 Hz in a 24000 Hz run", {"rate": 22050, "channels": 1}, "resampled first"),
                                 ("stereo", {"rate": 24000, "channels": 2}, "mono 16-bit")):
            tone_wav(proj / "rec" / "s2.wav", kw["rate"], 1.5, channels=kw["channels"])
            pq = make_plan(cp, sc, base_dir=proj)
            ok, msg = refused(lambda: produce(pq, Path(td) / "y", base_dir=proj, rate=24000), needle)
            check(ok, f"prepared {desc} refused with what to convert ({msg[:90]})")
        cg = load_casting(casting_variant(td, lambda x: x["roles"]["lina"].update(voice="gemini:Kore")) / "voices.cast.json")
        ok, msg = refused(lambda: produce(make_plan(cg, script(), base_dir=FIX), Path(td) / "z", base_dir=FIX), "no connection in this version")
        check(ok, f"producing a Gemini voice is refused: no API in this version ({msg[:80]})")

        print("\n== F the produced files through the UNCHANGED Stage 2 prepare (temp folder)")
        sys.path.insert(0, str(ROOT / "scripts"))
        import story_stage2 as core
        b = Path(td) / "core"; (b / "audio").mkdir(parents=True)
        for r in m["sentences"]:
            shutil.copyfile(out / r["file"], b / "audio" / f"{r['id']}.wav")
        cfg = json.loads((ROOT / "studio/config/studio.defaults.json").read_text(encoding="utf-8"))
        cfg["whisper"]["language"] = "en"          # set per project (Film / Studio do the same); empty in the defaults
        (b / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (b / "script.json").write_text(json.dumps({"meta": {"language": "en", "title": "v1"},
                                                   "sentences": [{"id": r["id"], "text": r["text"]} for r in m["sentences"]]}, ensure_ascii=False), encoding="utf-8")
        core.BUILD, core.SCRIPT_PATH, core.CONFIG_PATH = b, b / "script.json", b / "config.json"
        err, old = io.StringIO(), sys.stderr
        sys.stderr = err
        try:
            core.cmd_prepare(None); rc = 0
        except SystemExit as e:
            rc = e.code
        finally:
            sys.stderr = old
        meta = json.loads((b / "audio_meta.json").read_text(encoding="utf-8")) if rc == 0 else {}
        a = cfg["audio"]; cur, ok = a["lead_in_ms"] / 1000, rc == 0
        for r, x in zip(m["sentences"], meta.get("sentences", [])):
            ok &= abs(x["offset"] - cur) < 1e-6 and abs(x["duration"] - r["duration"]) < 1e-9
            cur += r["duration"] + a["gap_ms"] / 1000
        check(ok, f"the core's prepare accepts all 5 multi-speaker files; offsets / durations exact (exit {rc}, stderr {err.getvalue()!r})")

    print("\n== G independence")
    files = {str(p.relative_to(VOICE)): p.read_text(encoding="utf-8") for p in VOICE.rglob("*.py") if "tests" not in p.parts}
    src = "".join(files.values())
    check(not re.search(r"^\s*(from|import)\s+(film|studio|story_stage2|stage2_whisper)\b", src, re.M),
          "nfp/voice (outside its tests) imports nothing of Film, Studio or the Stage 2 core")
    net = sorted(f for f, s in files.items() if re.search(r"^\s*(from|import)\s+(urllib|http|requests|socket)\b", s, re.M))
    check(net == ["providers/gemini.py"], f"network code only in the AI provider adapter (V3, off by default): {net}")
    check(set(BUILD_EXPECT) >= {"woman", "man", "teen", "child", "baby"}, "every C1 build has an expected voice type")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL VOICE V1 TESTS PASSED" if not f else "VOICE V1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
