#!/usr/bin/env python3
"""V2 tests of the NFP Voice Engine: normalization, quality control, audio cache. Offline: synthetic test tones and
prepared WAV files generated here with the installed FFmpeg / Python (no speech, no API, no download); every output
and the cache live in temporary folders, nothing is written to the repository.

  N normalization   any WAV (rate / channels / bit depth / float) -> mono 16-bit at the run rate; duration kept;
                    pauses exact; one constant gain to the target loudness, limited by true peak / max gain
  Q quality control clipping, peak, loudness / true peak, silence (start / end / inside), empty / silent / weak,
                    unreadable, wrong format, length vs expected; warning vs error; configurable thresholds
  C cache           miss / hit, byte-identical reuse without re-producing, key coverage, corruption / incomplete
                    entries discarded and rebuilt, concurrent runs, clearing only cache entries, manifest records
  X compatibility   produce() without V2 options = V1; normalized files go through the unchanged Stage 2 prepare
Run: python3 nfp/voice/tests/test_voice_v2.py
"""
import array
import io
import json
import math
import os
import shutil
import subprocess
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
from voice import VoiceError, load_casting, make_plan, produce, validate_manifest  # noqa: E402
from voice.audiotools import loudness  # noqa: E402
from voice.cache import Cache, CacheError, default_dir  # noqa: E402
from voice.normalize import settings  # noqa: E402
from voice.providers.synthetic import SyntheticProvider  # noqa: E402
from voice.qc import QCError, check_file, thresholds  # noqa: E402

FIX = HERE / "fixtures" / "voice-demo"
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def refused(fn, *needles, exc=(VoiceError,)):
    try:
        fn()
    except exc as e:
        text = "\n".join(getattr(e, "problems", [str(e)]))
        return all(n in text for n in needles), text.replace("\n", " | ")[:170]
    return False, "accepted"


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


def tone(path, rate=24000, seconds=1.5, amp=0.3, f=220, channels=1, codec="pcm_s16le", lead=0.0, gap=0.0):
    """A prepared test file made with FFmpeg: sine tone of peak amplitude `amp` (full scale = 1; lavfi sine itself is
    1/8, hence the factor 8), with optional leading silence / a silent gap in the middle."""
    amp = amp * 8
    flt = f"sine=f={f}:d={seconds}:sample_rate={rate},volume={amp}"
    if gap:
        flt = (f"sine=f={f}:d={seconds / 2}:sample_rate={rate},volume={amp},apad=pad_dur={gap}[a];"
               f"sine=f={f}:d={seconds / 2}:sample_rate={rate},volume={amp}[b];[a][b]concat=n=2:v=0:a=1")
    if lead:
        flt += f",adelay={int(lead * 1000)}"
    ff("-f", "lavfi", "-i", flt, "-ac", channels, "-ar", rate, "-c:a", codec, path)


def pcm_file(path, values, rate=24000):
    a = array.array("h", values)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes())


def project(td, recs):
    """A copy of the fixture whose sentences s2 / s3 use prepared recordings (rec/<id>.wav)."""
    project.n = getattr(project, "n", 0) + 1                 # a fresh folder per call: no project overwrites another
    d = Path(td) / f"proj{project.n}"
    shutil.copytree(FIX, d)
    (d / "rec").mkdir()
    s = json.loads((d / "script.json").read_text(encoding="utf-8"))
    for sid, maker in recs.items():
        maker(d / "rec" / f"{sid}.wav")
        next(x for x in s["sentences"] if x["id"] == sid)["audio"] = f"rec/{sid}.wav"
    (d / "script.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    c = load_casting(d / "voices.cast.json")
    return d, make_plan(c, s, base_dir=d)


def body(path, row):
    with wave.open(str(path), "rb") as w:
        r = w.getframerate()
        pcm = w.readframes(w.getnframes())
    a, b = int(round(row["pause_before_ms"] / 1000 * r)), int(round(row["pause_after_ms"] / 1000 * r))
    return pcm, pcm[2 * a:len(pcm) - 2 * b], pcm[:2 * a], pcm[len(pcm) - 2 * b:] if b else b""


def main():
    td = Path(tempfile.mkdtemp(prefix="nfp-voice-v2-"))
    try:
        run(td)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL VOICE V2 TESTS PASSED" if not f else "VOICE V2 TESTS FAILED"))
    sys.exit(1 if f else 0)


def run(td):
    print("== N normalization")
    d, plan = project(td, {"s2": lambda p: tone(p, rate=22050, channels=2, codec="pcm_s24le", amp=0.08),
                           "s3": lambda p: tone(p, rate=48000, codec="pcm_f32le", amp=0.5, seconds=2.0)})
    out = td / "n1"
    m = produce(plan, out, base_dir=d, normalize={})
    r2 = next(r for r in m["sentences"] if r["id"] == "s2")
    r3 = next(r for r in m["sentences"] if r["id"] == "s3")
    check(r2["normalize"]["input"]["rate"] == 22050 and r2["normalize"]["input"]["channels"] == 2 and r2["normalize"]["input"]["bits"] == 24
          and r2["normalize"]["downmixed"] and r2["normalize"]["resampled"] and r2["normalize"]["output"]["rate"] == 24000,
          f"22050 Hz stereo 24-bit -> 24000 Hz mono 16-bit; input / output specs recorded ({r2['normalize']['input']})")
    check(r3["normalize"]["input"]["codec"] == "pcm_f32le" and r3["normalize"]["requantized"],
          "48000 Hz 32-bit float WAV accepted and requantized to 16-bit")
    fmts = set()
    for r in m["sentences"]:
        with wave.open(str(out / r["file"]), "rb") as w:
            fmts.add((w.getnchannels(), w.getsampwidth(), w.getframerate()))
    check(fmts == {(1, 2, 24000)}, "every produced file: mono 16-bit 24000 Hz")
    dk = [abs(r["normalize"]["input"]["duration"] - (r["frames"] - (r["pause_before_ms"] + r["pause_after_ms"]) * 24) / 24000)
          for r in (r2, r3)]
    check(max(dk) <= 2 / 22050 + 2 / 24000, f"duration kept through conversion (max difference {max(dk) * 1000:.3f} ms)")
    pcm, b2, lead, tail = body(out / r2["file"], r2)
    check(lead == b"\0" * len(lead) and len(lead) == 2 * int(0.3 * 24000), "the planned 300 ms pause before s2 is exact silence of the right length")
    lv = {r["id"]: loudness(out / r["file"])["integrated_lufs"] for r in m["sentences"]}
    check(all(abs(v + 20) <= 0.5 for v in lv.values()), f"every sentence (synthetic + prepared) at the target -20 LUFS +-0.5: {lv}")
    tps = {r["id"]: loudness(out / r["file"])["true_peak_dbtp"] for r in m["sentences"]}
    check(all(v <= -1.4 for v in tps.values()), f"true peak <= -1.5 dBTP (+0.1 measurement) everywhere: {tps}")
    check(r2["normalize"]["loudness"]["gain_db"] > 0 and r2["normalize"]["loudness"]["before"]["integrated_lufs"] < -20,
          f"one constant gain recorded with the loudness before / after ({r2['normalize']['loudness']['gain_db']} dB)")
    check(validate_manifest(out / "voice_manifest.json") == [], "manifest with normalization details is valid")
    # quiet and hot inputs: the gain is limited and the limit recorded
    spiky = lambda p: pcm_file(p, [int(900 * math.sin(i / 6)) + (31000 if i % 6000 == 0 else 0) for i in range(36000)])  # noqa: E731
    d, plan = project(td, {"s2": lambda p: tone(p, amp=0.002), "s3": spiky})
    m = produce(plan, td / "n2", base_dir=d, normalize={})
    q2 = next(r for r in m["sentences"] if r["id"] == "s2")["normalize"]["loudness"]
    d0, plan0 = project(td, {"s2": lambda p: tone(p, amp=0.0002)})
    q0 = next(r for r in produce(plan0, td / "n2b", base_dir=d0, normalize={})["sentences"] if r["id"] == "s2")["normalize"]["loudness"]
    check(q0["gain_db"] == 0.0 and q0["limited_by"].startswith("not measurable") and q0["after"] == q0["before"],
          f"input below the EBU absolute gate (-70 LUFS): no gain, recorded as not measurable, record complete")
    q3 = next(r for r in m["sentences"] if r["id"] == "s3")["normalize"]["loudness"]
    check(q2["limited_by"] == "max_gain_db" and q2["gain_db"] == 20.0, f"very quiet input: gain capped at +20 dB, recorded ({q2['after']['integrated_lufs']} LUFS after)")
    check(q3["limited_by"] == "true_peak_max" and q3["after"]["true_peak_dbtp"] <= -1.4 and q3["after"]["integrated_lufs"] < -20,
          f"quiet voice with strong peaks: the gain stops at the true-peak limit, below the loudness target "
          f"({q3['gain_db']} dB; true peak after {q3['after']['true_peak_dbtp']} dBTP; {q3['after']['integrated_lufs']} LUFS)")
    m = produce(plan, td / "n3", base_dir=d, normalize={"loudness": False})
    check(all(r["normalize"]["loudness"] is None for r in m["sentences"]), "loudness: false -> format conversion only, no gain")
    for desc, kw, needle in (("unknown setting", {"x": 1}, "unknown setting"), ("target out of range", {"target_lufs": 3}, "target_lufs")):
        ok, msg = refused(lambda: produce(plan, td / "n4", base_dir=d, normalize=kw), needle)
        check(ok, f"normalize settings refused: {desc} ({msg[:80]})")
    for desc, maker, needle in (
            ("a FLAC file named .wav", lambda p: ff("-f", "lavfi", "-i", "sine=f=200:d=1", "-c:a", "flac", "-f", "flac", p), "not a WAV file"),
            ("a text file named .wav", lambda p: p.write_text("not audio"), "unreadable audio file"),
            ("a truncated WAV header", lambda p: p.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt "), "unreadable audio file")):
        d, plan = project(td, {"s2": maker})
        ok, msg = refused(lambda: produce(plan, td / "n5", base_dir=d, normalize={}), "s2", needle)
        check(ok, f"input refused with a clear, traceable message: {desc} ({msg[:110]})")

    print("\n== Q quality control")
    d, plan = project(td, {"s2": lambda p: tone(p, amp=0.3)})
    m = produce(plan, td / "q1", base_dir=d, normalize={}, qc={})
    rep = json.loads((td / "q1" / "qc_report.json").read_text(encoding="utf-8"))
    check(m["qc"]["summary"] == {"ok": 5, "warning": 0, "error": 0} and rep["schema"] == "nfp.voice.qc/1"
          and all(r["qc"] == "ok" for r in m["sentences"]),
          f"healthy files pass every check, nothing is rejected (summary {m['qc']['summary']}; {len(rep['files'][0]['checks'])} checks per file)")
    check({c["check"] for c in rep["files"][0]["checks"]} >= {"readable", "format", "duration", "signal", "clipping", "peak", "loudness",
                                                              "true_peak", "leading_silence", "trailing_silence", "internal_silence", "length_vs_expected"},
          "every check is recorded in the report with value, limit and level")
    clipped = lambda p: pcm_file(p, [32767 if (i // 20) % 2 else -32768 for i in range(36000)])  # noqa: E731
    d, plan = project(td, {"s3": clipped})
    ok, msg = refused(lambda: produce(plan, td / "q2", base_dir=d, normalize={"loudness": False}, qc={}), "QC failed", "s3: clipping")
    rep = json.loads((td / "q2" / "qc_report.json").read_text(encoding="utf-8"))
    check(ok and rep["summary"]["error"] == 1 and (td / "q2" / "voice_manifest.json").exists(),
          f"heavy clipping is an ERROR that stops the run; the report and manifest are still written ({msg[:70]})")
    few = lambda p: pcm_file(p, [32767 if i == 5000 else int(8000 * math.sin(i / 7)) for i in range(36000)])  # noqa: E731
    d, plan = project(td, {"s3": few})
    m = produce(plan, td / "q3", base_dir=d, normalize={"loudness": False}, qc={})
    st = next(r for r in m["sentences"] if r["id"] == "s3")["qc"]
    check(st == "warning", f"one full-scale sample: WARNING only, the file is not rejected ({st})")
    m = produce(plan, td / "q4", base_dir=d, normalize={"loudness": False}, qc={"clip_error_ratio": 1.0, "peak_warn_dbfs": 0.0})
    d2, plan2 = project(td, {"s3": clipped})
    m = produce(plan2, td / "q5", base_dir=d2, normalize={"loudness": False}, qc={"clip_error_ratio": 1.0})
    check(next(r for r in m["sentences"] if r["id"] == "s3")["qc"] == "warning", "thresholds are settings: with clip_error_ratio 1.0 the same clipping is only a warning")
    d, plan = project(td, {"s2": lambda p: tone(p, lead=2.0), "s3": lambda p: tone(p, seconds=2.0, gap=3.0)})
    m = produce(plan, td / "q6", base_dir=d, normalize={}, qc={})
    rep = {f["id"]: {c["check"]: c["level"] for c in f["checks"]} for f in json.loads((td / "q6" / "qc_report.json").read_text())["files"]}
    check(rep["s2"]["leading_silence"] == "warning" and rep["s3"]["internal_silence"] == "warning"
          and rep["s1"]["leading_silence"] == "ok" and m["qc"]["summary"]["error"] == 0,
          "unexpected 2 s silence at the start and 3 s inside: WARNINGS; planned pauses are not flagged")
    d, plan = project(td, {"s2": lambda p: pcm_file(p, [0] * 30000)})
    ok, msg = refused(lambda: produce(plan, td / "q7", base_dir=d, normalize={"loudness": False}, qc={}), "s2: signal")
    check(ok, f"a silent file is an ERROR ({msg[:80]})")
    d, plan = project(td, {"s2": lambda p: tone(p, amp=0.004)})
    m = produce(plan, td / "q8", base_dir=d, normalize={"loudness": False}, qc={})
    lv = next(c for c in json.loads((td / "q8" / "qc_report.json").read_text())["files"][1]["checks"] if c["check"] == "loudness")
    check(lv["level"] == "warning" and "very weak" in lv["message"] and m["qc"]["summary"]["error"] == 0,
          f"a very weak (but present) voice is a WARNING, not rejected ({lv['value']} LUFS)")
    t = thresholds()
    tone(td / "w22.wav", rate=22050)
    r = check_file(td / "w22.wav", 24000, t, "x")
    check(r["status"] == "error" and r["checks"][-1]["check"] == "format", "wrong sample rate / channels: format ERROR")
    (td / "broken.wav").write_bytes(b"RIFF....WAVE")
    check(check_file(td / "broken.wav", 24000, t, "x")["checks"][0] == {"check": "readable", "level": "error", "value": None, "limit": None,
          "message": check_file(td / "broken.wav", 24000, t, "x")["checks"][0]["message"]}, "broken file: readable ERROR")
    tone(td / "ok.wav", seconds=1.0)
    r = check_file(td / "ok.wav", 24000, t, "x", planned={"body_frames": 30000})
    check(r["status"] == "error" and any(c["check"] == "length_vs_expected" and c["level"] == "error" for c in r["checks"]),
          "produced length differs from speech + planned pauses: ERROR")
    pcm_file(td / "short.wav", [1000] * 2000)
    check(check_file(td / "short.wav", 24000, t, "x")["checks"][2]["level"] == "error", "empty / too short file (< 0.3 s): ERROR")
    ok, msg = refused(lambda: thresholds({"nope": 1}), "unknown threshold", exc=(QCError,))
    check(ok, f"unknown QC threshold refused ({msg[:60]})")

    print("\n== C cache")
    d, plan = project(td, {"s2": lambda p: tone(p, rate=22050, channels=2, amp=0.1)})
    cdir = td / "cache"
    calls = {"n": 0}
    orig = SyntheticProvider.produce

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)
    SyntheticProvider.produce = counting
    try:
        m1 = produce(plan, td / "c1", base_dir=d, normalize={}, qc={}, cache=Cache(cdir))
        n1 = calls["n"]
        m2 = produce(plan, td / "c2", base_dir=d, normalize={}, qc={}, cache=Cache(cdir))
        n2 = calls["n"] - n1
    finally:
        SyntheticProvider.produce = orig
    check(m1["cache"]["misses"] == 5 and m1["cache"]["hits"] == 0 and all(not r["cache"]["hit"] for r in m1["sentences"]),
          "first run: 5 misses, every file made and stored")
    check(m2["cache"]["hits"] == 5 and m2["cache"]["misses"] == 0 and n2 == 0 and all(r["cache"]["hit"] for r in m2["sentences"]),
          f"second run, same input: 5 hits, nothing re-produced (provider calls {n2})")
    check(all((td / "c1" / r["file"]).read_bytes() == (td / "c2" / r["file"]).read_bytes() for r in m1["sentences"])
          and [r["sha256"] for r in m1["sentences"]] == [r["sha256"] for r in m2["sentences"]],
          "cache hits give byte-identical files (same sha256)")
    check(validate_manifest(td / "c2" / "voice_manifest.json") == [] and m2["qc"]["summary"]["error"] == 0,
          "manifest records cache key + hit per sentence and the run's hit / miss counts; valid")
    s = json.loads((d / "script.json").read_text(encoding="utf-8"))
    s["sentences"][2]["pause_after_ms"] = 400
    p2 = make_plan(load_casting(d / "voices.cast.json"), s, base_dir=d)
    m3 = produce(p2, td / "c3", base_dir=d, normalize={}, cache=Cache(cdir))
    check(m3["cache"]["misses"] == 1 and m3["cache"]["hits"] == 4 and not next(r for r in m3["sentences"] if r["id"] == "s3")["cache"]["hit"],
          "a changed pause: only that sentence misses")
    m4 = produce(plan, td / "c4", base_dir=d, normalize={"target_lufs": -18}, cache=Cache(cdir))
    m5 = produce(plan, td / "c5", base_dir=d, rate=48000, normalize={}, cache=Cache(cdir))
    check(m4["cache"]["misses"] == 5 and m5["cache"]["misses"] == 5, "other normalization settings or sample rate: every key changes (misses)")
    tone(d / "rec" / "s2.wav", rate=22050, channels=2, amp=0.2)
    p3 = make_plan(load_casting(d / "voices.cast.json"), json.loads((d / "script.json").read_text(encoding="utf-8")), base_dir=d)
    m6 = produce(p3, td / "c6", base_dir=d, normalize={}, cache=Cache(cdir))
    check(next(r for r in m6["sentences"] if r["id"] == "s2")["cache"]["hit"] is False and m6["cache"]["hits"] == 4,
          "a changed prepared recording (new sha256): that sentence misses")
    # corruption / incomplete entries
    c = Cache(cdir)
    key = next(r for r in m6["sentences"] if r["id"] == "s1")["cache"]["key"]
    w = cdir / key[:2] / f"{key}.wav"
    raw = bytearray(w.read_bytes()); raw[-3] ^= 0x55; w.write_bytes(bytes(raw))
    m7 = produce(p3, td / "c7", base_dir=d, normalize={}, cache=Cache(cdir))
    check(m7["cache"]["discarded"] == 1 and m7["cache"]["misses"] == 1 and validate_manifest(td / "c7" / "voice_manifest.json") == []
          and Cache(cdir).get(key, 24000) is not None,
          "a corrupted cached file is detected (sha256), discarded, rebuilt; the new entry is valid")
    (cdir / key[:2] / f"{key}.json").unlink()
    c = Cache(cdir)
    check(c.get(key, 24000) is None and c.stats["discarded"] == 1 and not w.exists(), "WAV without its JSON (incomplete write): discarded, miss")
    produce(p3, td / "c8", base_dir=d, normalize={}, cache=Cache(cdir))
    (cdir / key[:2] / f"{key}.json").write_text('{"schema": "nfp.voice.cache/1", "key"', encoding="utf-8")
    c = Cache(cdir)
    check(c.get(key, 24000) is None and c.stats["discarded"] == 1, "truncated JSON: discarded, miss")
    # concurrent runs into one cache
    conc = td / "cconc"
    script = (f"import sys;sys.dont_write_bytecode=True;sys.path.insert(0,{str(NFP)!r});"
              f"from voice import load_casting,make_plan,produce;from voice.cache import Cache;import json;"
              f"from pathlib import Path;d=Path({str(d)!r});c=load_casting(d/'voices.cast.json');"
              f"p=make_plan(c,json.loads((d/'script.json').read_text()),base_dir=d);"
              f"produce(p,Path(sys.argv[1]),base_dir=d,normalize={{}},cache=Cache({str(conc)!r}))")
    Cache(conc)
    procs = [subprocess.Popen([sys.executable, "-B", "-c", script, str(td / f"cc{i}")]) for i in range(3)]
    codes = [p.wait() for p in procs]
    c = Cache(conc)
    ents = c.entries()
    leftovers = [p for p in conc.rglob("*") if ".tmp-" in p.name]
    check(codes == [0, 0, 0] and len(ents) == 5 and all(c.get(e.stem, 24000) for e in ents) and not leftovers,
          f"3 runs at the same time into one cache: all succeed, 5 valid entries, no temp files left (exit codes {codes})")
    # clearing
    (conc / "keep-me.txt").write_text("not a cache entry")
    n = Cache(conc).clear()
    check(n == 10 and (conc / "keep-me.txt").exists() and (conc / "NFP_VOICE_CACHE").exists() and not Cache(conc).entries(),
          f"cache-clear removes only the cache entries ({n} files); other files and the marker stay")
    foreign = td / "foreign"; foreign.mkdir(); (foreign / "project.txt").write_text("x")
    ok, msg = refused(lambda: Cache(foreign), "not an NFP voice cache", exc=(CacheError,))
    check(ok and (foreign / "project.txt").exists(), f"a non-empty folder that is not a cache is never used / cleared ({msg[:70]})")
    env = dict(os.environ); env.pop("NFP_VOICE_CACHE", None)
    dd = default_dir()
    check(ROOT not in dd.parents and dd != ROOT, f"default cache folder is outside the repository ({dd})")

    print("\n== X compatibility")
    d, plan = project(td, {})
    a = produce(plan, td / "x1", base_dir=d)
    keys_v2 = {"normalize", "qc", "cache"}
    check(not (set(a) & keys_v2) and all(not (set(r) & keys_v2) for r in a["sentences"]) and validate_manifest(td / "x1" / "voice_manifest.json") == [],
          "produce() without V2 options: exactly the V1 manifest (no new fields)")
    sys.path.insert(0, str(ROOT / "scripts"))
    import story_stage2 as core
    m = produce(make_plan(load_casting(FIX / "voices.cast.json"), json.loads((FIX / "script.json").read_text(encoding="utf-8")), base_dir=FIX),
                td / "x2", base_dir=FIX, normalize={}, qc={})
    b = td / "core"; (b / "audio").mkdir(parents=True)
    for r in m["sentences"]:
        shutil.copyfile(td / "x2" / r["file"], b / "audio" / f"{r['id']}.wav")
    cfg = json.loads((ROOT / "studio/config/studio.defaults.json").read_text(encoding="utf-8"))
    cfg["whisper"]["language"] = "en"
    (b / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (b / "script.json").write_text(json.dumps({"meta": {"language": "en", "title": "v2"},
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
    meta = json.loads((b / "audio_meta.json").read_text(encoding="utf-8")) if rc == 0 else {"sentences": []}
    ok = rc == 0 and all(abs(x["duration"] - r["duration"]) < 1e-9 for r, x in zip(m["sentences"], meta["sentences"]))
    check(ok, f"normalized files go through the unchanged Stage 2 prepare (exit {rc}, stderr {err.getvalue()!r})")


if __name__ == "__main__":
    main()
