#!/usr/bin/env python3
"""V4 - Voice Engine inside Film (engine/voice_bridge.py), offline: synthetic voices and a FAKE Gemini transport only.

  python3 nfp/film/tests/film_voice_check.py --fonts <dir with woff2> --work <dir outside the repository>

  L legacy    projects without voice.engine compose byte-identically to the committed Film (3d714cd, taken with
              `git archive` into --work); the Voice Engine is never imported for them; `voice` is refused
  V voice     en + fa projects with two character speakers + narrator: `run.py voice` -> <build>/audio + tts_meta.json
              -> unchanged core prepare (whisper_in) -> align (with hand-made Whisper words from the synthetic word
              times) -> compose: words.json, SRT, C3 lip sync for the speaking actors; pauses before / after sentences
              land in the word times; warm cache; `tts` refused; a speaker mismatch is refused at compose
  P provider  missing gates -> refused before any request, <build>/audio untouched; fake HTTP 429 -> stops, audio
              untouched; fake Gemini success -> delivered; no real request (fake transport only)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
RESULTS = []
RUN = FILM / "engine" / "run.py"
CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GEMINI_FREE_TIER_CONFIRMED")}
CLEAN_ENV["PYTHONDONTWRITEBYTECODE"] = "1"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sh(*args, env=None):
    return subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True, env=env or CLEAN_ENV)


def run_cmd(cmd, proj, build, fonts=None):
    env = dict(CLEAN_ENV)
    if fonts:
        env["NFP_FONTS"] = str(fonts)
    return sh(RUN, cmd, "--project", proj, "--build", build, env=env)


SYNTH = r"""
import json, sys, wave
eng, proj_path, build = sys.argv[1:4]
sys.path.insert(0, eng); sys.path.insert(0, sys.argv[4]); sys.path.insert(0, sys.argv[5])
import project as P, compose as C, cast_plan as CP
proj = P.load(proj_path); ch = proj["chapters"][0]
cur, sents = 0.3, []
for s in ch["sentences"]:
    dur = round(len(s["text"]) / 14.0, 3); words = s["text"].split(); tot = sum(len(w) for w in words); acc = 0; rows = []
    for i, w in enumerate(words):
        a = cur + dur * acc / tot; acc += len(w); b = cur + dur * acc / tot
        rows.append({"i": i, "text": w, "abs_start": round(a, 3), "abs_end": round(b, 3), "status": "exact"})
    sents.append({"id": s["id"], "text": s["text"], "offset": round(cur, 3), "duration": dur, "words": rows}); cur += dur + 0.3
timing = {"summary": {"status": "OK"}, "audio": {"total": round(cur + 0.2, 3), "gap": 0.3}, "sentences": sents}
with wave.open(build + "/narration.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * int(24000 * timing["audio"]["total"]))
ke, fr, rep = CP.fragment(proj, ch, timing, build)
C.compose(proj, ch, timing, build, sys.argv[6], build + "/narration.wav", cast_fragment=fr, kit_extra=ke)
if rep: open(build + "/cast_report.json", "w", encoding="utf-8").write(json.dumps(rep, ensure_ascii=False, indent=1))
print(json.dumps(sorted(m for m in sys.modules if m in ("voice", "voice_bridge") or m.startswith("voice."))))
"""


def legacy_outputs(eng, fixture, build, fonts, root=ROOT):
    build.mkdir(parents=True, exist_ok=True)
    r = sh("-c", SYNTH, eng, fixture / "project.json", build, root / "scripts", root / "nfp", fonts)
    if r.returncode != 0:
        raise SystemExit(f"legacy compose failed ({eng}):\n{r.stderr[-1500:]}")
    files = {f: (build / f).read_bytes() for f in ("story/index.html", "words.json", "story.srt") if (build / f).exists()}
    if (build / "cast_report.json").exists():
        files["cast_report.json"] = (build / "cast_report.json").read_bytes()
    return files, json.loads(r.stdout.strip().splitlines()[-1])


def voice_project(work, base, name, voices, speakers, pauses, providers=None, cache=True):
    """A copy of a Film cast fixture that uses the Voice Engine."""
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(HERE / "fixtures" / base, d)
    p = json.loads((d / "project.json").read_text(encoding="utf-8"))
    cast_dir = p["cast"]["dir"]
    lock = json.loads((d / cast_dir / "cast.lock.json").read_text(encoding="utf-8"))["characters"]
    p["voice"] = {"engine": "nfp.voice/1", "casting": "voices.cast.json", "normalize": {}, "qc": {},
                  "cache": str(work / "voice-cache") if cache else False}
    if providers:
        p["voice"]["providers"] = providers
    p["meta"]["target_duration"] = 20   # synthetic tones run a little longer than the fixture's 15 s target
    for s in p["chapters"][0]["sentences"]:
        if s["id"] in speakers:
            s["speaker"] = speakers[s["id"]]
        s.update(pauses.get(s["id"], {}))
    (d / "project.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    casting = {"schema": "nfp.voice.casting/1", "project": name, "cast_dir": cast_dir, "rules": {"block_mismatch": False},
               "narrator": {"voice": voices["narrator"]},
               "roles": {c: {"voice": v, "fingerprint": lock[c]} for c, v in voices.items() if c != "narrator"}}
    (d / "voices.cast.json").write_text(json.dumps(casting, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def fake_whisper(build):
    """Whisper words made from the synthetic word times in the manifest (the speech is a test tone: no real
    recognition is possible or claimed); format = stage2_whisper output, times include the core's padding."""
    m = json.loads((build / "voice" / "voice_manifest.json").read_text(encoding="utf-8"))
    pad = json.loads((build / "audio_meta.json").read_text(encoding="utf-8"))["pad"]
    (build / "whisper").mkdir(exist_ok=True)
    for sid, words in m["synthetic_words"].items():
        (build / "whisper" / f"{sid}.json").write_text(json.dumps(
            {"language": "x", "words": [{"text": w, "start": round(s + pad, 4), "end": round(e + pad, 4)} for s, e, w in words]},
            ensure_ascii=False), encoding="utf-8")
    return m


def audio_snapshot(build):
    return {p.name: p.read_bytes() for p in sorted((build / "audio").glob("*.wav"))} if (build / "audio").exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print("== L legacy (byte-identical to the committed Film 3d714cd)")
    head = work / "head"
    arch = subprocess.run(["git", "-C", str(ROOT), "archive", "3d714cdcbb9bb4bacba51517f9ac724eabffc908"], capture_output=True)
    head.mkdir()
    subprocess.run(["tar", "-x", "-C", str(head)], input=arch.stdout, check=True)
    for fx in ("neutral-en", "cast-en", "cast-fa"):
        old, _ = legacy_outputs(head / "nfp/film/engine", FILM / "tests/fixtures" / fx, work / "legacy" / fx / "old", a.fonts, head)
        new, mods = legacy_outputs(FILM / "engine", FILM / "tests/fixtures" / fx, work / "legacy" / fx / "new", a.fonts)
        check(old == new and len(new) >= 3 and mods == [],
              f"{fx}: page, words.json, SRT{', cast report' if 'cast_report.json' in new else ''} byte-identical to 3d714cd; "
              f"Voice Engine not imported ({mods})")
    r = run_cmd("voice", FILM / "tests/fixtures/cast-en", work / "b-legacy")
    check(r.returncode != 0 and "needs voice.engine" in (r.stderr + r.stdout), "`voice` on a legacy project is refused clearly")
    shutil.copytree(FILM / "tests/fixtures/cast-en", work / "projects" / "pause-legacy")
    pj = json.loads((work / "projects/pause-legacy/project.json").read_text(encoding="utf-8"))
    pj["chapters"][0]["sentences"][0]["pause_before_ms"] = 300
    (work / "projects/pause-legacy/project.json").write_text(json.dumps(pj), encoding="utf-8")
    r = run_cmd("plan", work / "projects/pause-legacy", work / "b-pl")
    check(r.returncode != 0 and "pauses need the Voice Engine" in (r.stderr + r.stdout), "pauses without the Voice Engine are refused")

    for lang, base in (("en", "cast-en"), ("fa", "cast-fa")):
        print(f"\n== V voice project ({lang})")
        d = voice_project(work, base, f"voice-{lang}", {"narrator": "synthetic:narrator", "lina": "synthetic:female", "omid": "synthetic:male"},
                          {}, {"s1": {"pause_before_ms": 400}, "s3": {"pause_after_ms": 300}})
        b = work / f"b-{lang}"
        r = run_cmd("voice", d, b)
        ok = r.returncode == 0
        check(ok, f"run.py voice: {(r.stdout + r.stderr).strip().splitlines()[-1][:150] if (r.stdout + r.stderr).strip() else ''}")
        if not ok:
            continue
        m = json.loads((b / "voice" / "voice_manifest.json").read_text(encoding="utf-8"))
        spk = {x["id"]: x["speaker"] for x in m["sentences"]}
        check(spk == {"s1": "narrator", "s2": "omid", "s3": "omid"} and {x["id"]: x["voice"] for x in m["sentences"]}["s2"] == "synthetic:male",
              f"each sentence made by its speaker's voice: {spk} (actor key -> C1 character)")
        same = all((b / "audio" / f"{x['id']}.wav").read_bytes() == (b / "voice" / x["file"]).read_bytes() for x in m["sentences"])
        tm = json.loads((b / "tts_meta.json").read_text(encoding="utf-8"))
        check(same and [x["id"] for x in tm["sentences"]] == ["s1", "s2", "s3"] and m["qc"]["summary"]["error"] == 0,
              f"the WAVs are handed to <build>/audio unchanged; core-compatible tts_meta.json; QC {m['qc']['summary']}")
        r = run_cmd("fit", d, b)
        check(r.returncode == 0, f"core-path `fit` reads the Voice tts_meta.json ({r.stdout.strip()[:80]})")
        r = run_cmd("prepare", d, b)
        wi = sorted(p.name for p in (b / "whisper_in").glob("*.wav")) if (b / "whisper_in").exists() else []
        check(r.returncode == 0 and wi == ["s1.wav", "s2.wav", "s3.wav"], f"unchanged core prepare: narration.wav + Whisper input per sentence {wi}")
        fake_whisper(b)
        r = run_cmd("align", d, b)
        T = json.loads((b / "timing.json").read_text(encoding="utf-8")) if r.returncode == 0 else None
        meta = json.loads((b / "audio_meta.json").read_text(encoding="utf-8"))
        off = {x["id"]: x["offset"] for x in meta["sentences"]}
        sw = m["synthetic_words"]
        errs = [abs(w["abs_start"] - (off[s["id"]] + sw[s["id"]][i][0])) for s in (T or {"sentences": []})["sentences"]
                for i, w in enumerate(s["words"]) if w["abs_start"] is not None]
        first = T["sentences"][0]["words"][0]["abs_start"] if T else None
        check(T and T["summary"]["status"] == "OK" and max(errs) <= 0.0015 and abs(first - (off["s1"] + 0.4)) <= 0.0015,
              f"unchanged core align: {len(errs)} words at offset + time in file (max error {max(errs or [9]) * 1000:.2f} ms); "
              f"the 400 ms pause before s1 is in the word times (first word {first}s)")
        s3 = next(x for x in m["sentences"] if x["id"] == "s3")
        check(abs(s3["duration"] - (s3["frames"] / 24000)) < 1e-9 and sw["s3"][-1][1] + 0.3 <= s3["duration"] + 1e-6,
              "the 300 ms pause after s3 is silence inside its own file")
        r = run_cmd("compose", d, b, fonts=a.fonts)
        W = json.loads((b / "words.json").read_text(encoding="utf-8")) if r.returncode == 0 else None
        rep = json.loads((b / "cast_report.json").read_text(encoding="utf-8")) if r.returncode == 0 else None
        talks = {i["key"]: [s for t in i["talks"] for s in t["sentences"]] for i in rep["instances"]} if rep else {}
        check(r.returncode == 0 and W["schema"] == "nfp.film.words/1" and W["lang"] == lang and (b / "story.srt").exists()
              and talks.get("omid-room") == ["s2"] and talks.get("omid-stage") == ["s3"] and talks.get("lina-street") == [],
              f"compose: words.json ({lang}) + SRT from the aligned timing; C3 lip sync only for the speaking actors {talks}")
        r = run_cmd("tts", d, b)
        check(r.returncode != 0 and "run `voice` instead" in (r.stderr + r.stdout), "`tts` refused for a Voice Engine project")
        r = run_cmd("voice", d, b)
        m2 = json.loads((b / "voice" / "voice_manifest.json").read_text(encoding="utf-8"))
        check(r.returncode == 0 and m2["cache"]["hits"] == 3 and m2["cache"]["misses"] == 0
              and [x["sha256"] for x in m2["sentences"]] == [x["sha256"] for x in m["sentences"]],
              f"warm cache: 3 hits, identical audio ({m2['cache']})")
        mf = json.loads((b / "voice" / "voice_manifest.json").read_text(encoding="utf-8"))
        mf["sentences"][1]["speaker"] = "lina"
        (b / "voice" / "voice_manifest.json").write_text(json.dumps(mf), encoding="utf-8")
        r = run_cmd("compose", d, b, fonts=a.fonts)
        check(r.returncode != 0 and "does not match the speakers" in (r.stderr + r.stdout),
              "audio made for another character than the one that moves its mouth: compose refuses")
        if lang == "en":
            b2 = work / "b-nomanifest"
            r = run_cmd("compose", d, b2, fonts=a.fonts)
            check(r.returncode != 0, "a Voice Engine project composed before `voice` stops with a clear error")

    print("\n== P provider (fake Gemini only)")
    d = voice_project(work, "cast-en", "voice-gemini", {"narrator": "gemini:Charon", "lina": "gemini:Kore", "omid": "gemini:Puck"},
                      {}, {}, providers={"gemini": {"max_requests": 8}}, cache=False)
    b = work / "b-gemini"
    (b / "audio").mkdir(parents=True)
    (b / "audio" / "keep.wav").write_bytes(b"previous audio")
    before = audio_snapshot(b)
    r = run_cmd("voice", d, b)
    check(r.returncode != 0 and "GEMINI_FREE_TIER_CONFIRMED" in (r.stderr + r.stdout) and audio_snapshot(b) == before
          and not (b / "voice" / "audio").exists(),
          "Gemini enabled but the gates closed (no key / confirmation in the environment): refused before any request; "
          "<build>/audio untouched")
    sys.path.insert(0, str(FILM / "engine"))
    sys.path.insert(0, str(ROOT / "nfp"))
    sys.path.insert(0, str(HERE.parent.parent / "voice" / "tests"))
    import project as P
    import voice_bridge as VB
    from voice.providers.gemini import GeminiProvider
    from test_voice_v3 import FakeTransport, response, tone_pcm  # noqa: E402  (the V3 fake: synthetic tone)
    proj = P.load(d)
    gates = {"GEMINI_FREE_TIER_CONFIRMED": "YES", "GEMINI_API_KEY": "fake-key-for-test"}
    t = FakeTransport([(200, response(tone_pcm()))] + [(429, b'{"error": {"message": "quota"}}')] * 3)
    try:
        VB.produce(proj, proj["chapters"][0], b, providers={"gemini": GeminiProvider({"spacing_s": 0}, transport=t, env=gates)})
        ok, msg = False, "accepted"
    except SystemExit as e:
        msg = str(e)
        ok = "HTTP 429" in msg and "was not changed" in msg
    check(ok and len(t.calls) == 2 and audio_snapshot(b) == before,
          f"fake HTTP 429: the run stops after 2 requests (no retry), <build>/audio untouched ({msg.splitlines()[0][:70]})")
    t = FakeTransport()
    m = VB.produce(proj, proj["chapters"][0], b, providers={"gemini": GeminiProvider({"spacing_s": 0}, transport=t, env=gates)})
    voices = [c["body"]["generation_config"]["speech_config"][0]["voice"] for c in t.calls]
    check(len(t.calls) == 3 and voices == ["Charon", "Puck", "Puck"] and m["providers"]["gemini"]["requests_used"] == 3
          and all(t_["url"].startswith("https://generativelanguage") for t_ in t.calls) and (b / "audio" / "s2.wav").exists(),
          f"fake Gemini: one request per sentence with the speaker's voice {voices}; audio handed over to <build>/audio")
    check(all(c["headers"]["x-goog-api-key"] == "fake-key-for-test" for c in t.calls),
          "only the fake transport was called (the test never opens a network connection)")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL FILM VOICE TESTS PASSED" if not f else "FILM VOICE TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
