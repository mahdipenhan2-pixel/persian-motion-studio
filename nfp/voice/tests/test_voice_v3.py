#!/usr/bin/env python3
"""V3 tests of the NFP Voice Engine: the AI speech provider (Gemini adapter) - fully offline.

No request leaves this machine: every test uses a FAKE transport (a function that returns a prepared response), a
fake key and fake gates. The fake "speech" is a synthetic test tone; nothing here is real AI speech.

  A off by default   gemini voices are refused unless the run enables the provider; no transport call
  B gates           free-model allow-list, GEMINI_FREE_TIER_CONFIRMED, API key, budget - all checked BEFORE any request
  C request         byte-identical to the locked core's request (core synth_once with a patched urlopen); key only in
                    the header; one request per sentence with the speaker's voice; spacing between requests
  D responses       headerless PCM / WAV / other rate + stereo (normalize) / invalid JSON / no audio / bad base64 /
                    odd PCM / HTTP 500 (key scrubbed) / HTTP 429 stops the run at once, no retry
  E cache + V2      cache hits send nothing; the model is part of the key; earlier synthetic keys unchanged; QC and
                    manifest; files go through the unchanged Stage 2 prepare; the key never appears in any output
  F estimate / CLI  requests needed are counted without any request; the CLI refuses without the gates
Run: python3 nfp/voice/tests/test_voice_v3.py
"""
import array
import base64
import contextlib
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
from voice.cache import Cache  # noqa: E402
from voice.manifest import estimate  # noqa: E402
from voice.providers.gemini import API_URL, FREE_MODELS, GeminiProvider, request_body  # noqa: E402

FIX = HERE / "fixtures" / "voice-demo"
KEY = "test-key-NOT-REAL-0123456789"
GATES = {"GEMINI_FREE_TIER_CONFIRMED": "YES", "GEMINI_API_KEY": KEY}
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def refused(fn, *needles):
    try:
        fn()
    except VoiceError as e:
        text = "\n".join(e.problems)
        return all(n in text for n in needles), text.replace("\n", " | ")[:170]
    return False, "accepted"


def tone_pcm(seconds=1.2, rate=24000, f=180.0, amp=6000):
    n = int(seconds * rate)
    return array.array("h", [int(amp * math.sin(2 * math.pi * f * k / rate) * min(1, k / 240, (n - k) / 240)) for k in range(n)]).tobytes()


def wav_bytes(pcm, rate, channels=1):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(pcm if channels == 1 else b"".join(pcm[i:i + 2] * 2 for i in range(0, len(pcm), 2)))
    return b.getvalue()


def response(audio):
    return json.dumps({"interaction": {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": base64.b64encode(audio).decode()}]}]}}).encode()


class FakeTransport:
    """Records every request; answers with a synthetic tone (or a scripted status / body)."""
    def __init__(self, script=None):
        self.calls, self.script = [], list(script or [])

    def __call__(self, url, headers, body, timeout):
        req = json.loads(body)
        self.calls.append({"url": url, "headers": dict(headers), "body": req, "raw": body})
        if self.script:
            return self.script.pop(0)
        voice = req["generation_config"]["speech_config"][0]["voice"]
        f = {"Kore": 220.0, "Charon": 120.0, "Puck": 140.0}.get(voice, 180.0)
        return 200, response(tone_pcm(f=f))


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


def gemini_project(td, block=False):
    """The fixture with Gemini voices: narrator Charon, lina Kore, omid Puck; sara stays synthetic (mixed providers)."""
    gemini_project.n = getattr(gemini_project, "n", 0) + 1
    d = Path(td) / f"g{gemini_project.n}"
    shutil.copytree(FIX, d)
    c = json.loads((d / "voices.cast.json").read_text(encoding="utf-8"))
    c["narrator"]["voice"] = "gemini:Charon"
    c["roles"]["lina"]["voice"] = "gemini:Kore"
    c["roles"]["omid"]["voice"] = "gemini:Puck"
    (d / "voices.cast.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    cast = load_casting(d / "voices.cast.json")
    return d, make_plan(cast, json.loads((d / "script.json").read_text(encoding="utf-8")), base_dir=d)


def prov(transport, env=None, clock=None, **cfg):
    clock = clock or Clock()
    return GeminiProvider(dict({"spacing_s": 25.0}, **cfg), transport=transport, env=GATES if env is None else env,
                          sleep=clock.sleep, clock=clock)


def main():
    td = Path(tempfile.mkdtemp(prefix="nfp-voice-v3-"))
    try:
        run(td)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL VOICE V3 TESTS PASSED" if not f else "VOICE V3 TESTS FAILED"))
    sys.exit(1 if f else 0)


def run(td):
    d, plan = gemini_project(td)
    gem = [r["id"] for r in plan["sentences"] if r["provider"] == "gemini"]

    print("== A off by default")
    ok, msg = refused(lambda: produce(plan, td / "a1", base_dir=d), "no connection in this version unless it is explicitly enabled")
    check(ok and gem == ["s1", "s2", "s3", "s5"], f"gemini voices without an enabled provider are refused ({msg[:90]})")

    print("\n== B gates (all before any request)")
    for desc, env, cfg, needle in (
            ("no free-tier confirmation", {"GEMINI_API_KEY": KEY}, {}, "GEMINI_FREE_TIER_CONFIRMED"),
            ("confirmation but no key", {"GEMINI_FREE_TIER_CONFIRMED": "YES"}, {}, "GEMINI_API_KEY is not set"),
            ("budget smaller than the sentences to make", GATES, {"max_requests": 2}, "budget of this run is 2")):
        t = FakeTransport()
        ok, msg = refused(lambda: produce(plan, td / "b", base_dir=d, providers={"gemini": prov(t, env=env, **cfg)}), needle)
        check(ok and not t.calls, f"refused, 0 requests sent: {desc} ({msg[:80]})")
    for desc, cfg, needle in (("a model outside the free-tier allow-list", {"model": "gemini-2.5-pro"}, "free-tier allow-list"),
                              ("an unknown setting", {"temperature": 1}, "unknown setting"),
                              ("a budget above 40", {"max_requests": 99}, "1..40")):
        ok, msg = refused(lambda: produce(plan, td / "b", base_dir=d, providers={"gemini": cfg}), needle)
        check(ok, f"refused: {desc} ({msg[:80]})")
    check(FREE_MODELS == ("gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview"),
          "the free-model allow-list is the core's list")

    print("\n== C request")
    sys.path.insert(0, str(ROOT / "scripts"))
    import story_stage2 as core
    captured = {}

    class Resp:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    real = core.urllib.request.urlopen
    core.urllib.request.urlopen = lambda req, timeout=None: (captured.update(url=req.full_url, body=req.data, headers=dict(req.header_items())), Resp(response(tone_pcm())))[1]
    try:
        core.synth_once({"model": "gemini-3.8-flash-tts", "voice": "Charon", "style": "documentary", "_timeout": 5}, "The valley is quiet.", KEY)
    finally:
        core.urllib.request.urlopen = real
    ours = json.dumps(request_body("gemini-3.8-flash-tts", "Charon", "The valley is quiet.", "documentary")).encode("utf-8")
    check(captured["body"] == ours and captured["url"] == API_URL,
          "the request is byte-identical to the locked core's request (core synth_once, network patched out)")
    clock = Clock()
    t = FakeTransport()
    p = prov(t, clock=clock)
    m = produce(plan, td / "c1", base_dir=d, providers={"gemini": p})
    sent = [(c["body"]["generation_config"]["speech_config"][0]["voice"], c["body"]["input"][0]["content"][0]["text"]) for c in t.calls]
    want = [(r["voice"].split(":")[1], r["text"]) for r in plan["sentences"] if r["provider"] == "gemini"]
    check(sent == want and len(t.calls) == 4, f"one request per AI sentence, each with its speaker's voice: {[v for v, _ in sent]}")
    check(all(c["headers"]["x-goog-api-key"] == KEY and KEY not in c["url"] for c in t.calls),
          "the key travels only in the x-goog-api-key header, never in the URL")
    check(t.calls[0]["body"]["input"][0]["content"][0].get("annotations") == [{"type": "speech_metadata", "style": "documentary"}]
          and "annotations" not in t.calls[1]["body"]["input"][0]["content"][0],
          "the narrator's style is sent as speech metadata; sentences without a style send none")
    check(clock.slept == [25.0, 25.0, 25.0], f"25 s spacing between requests (free-tier rate), none before the first: {clock.slept}")
    fa = next(c for c in t.calls if "در این دره" in c["body"]["input"][0]["content"][0]["text"])
    check(fa["body"]["generation_config"]["speech_config"][0]["voice"] == "Kore", "the Persian sentence goes out as UTF-8 text with lina's voice")

    print("\n== D responses")
    fmts = set()
    for r in m["sentences"]:
        with wave.open(str(td / "c1" / r["file"]), "rb") as w:
            fmts.add((w.getnchannels(), w.getsampwidth(), w.getframerate()))
    g = {r["id"]: r for r in m["sentences"]}
    check(fmts == {(1, 2, 24000)} and g["s2"]["generation"] == {"model": "gemini-3.8-flash-tts", "requested": True, "source_rate": 24000}
          and "generation" not in g["s4"], "headerless PCM decoded to mono 16-bit 24 kHz; generation recorded only for AI sentences")
    with wave.open(str(td / "c1" / g["s5"]["file"]), "rb") as w:
        lead = w.readframes(int(0.5 * 24000))
    check(lead == b"\0" * len(lead) and g["s5"]["frames"] == int(1.2 * 24000) + int(0.5 * 24000),
          "the planned 500 ms pause before s5 is added around the AI audio, exactly")
    check(m["providers"] == {"gemini": {"model": "gemini-3.8-flash-tts", "max_requests": 8, "requests_used": 4}}
          and validate_manifest(td / "c1" / "voice_manifest.json") == [], "manifest: provider summary (4 requests used) and valid")
    t = FakeTransport([(200, response(wav_bytes(tone_pcm(rate=48000), 48000, channels=2)))] * 4)
    ok, msg = refused(lambda: produce(plan, td / "d1", base_dir=d, providers={"gemini": prov(t)}), "enable normalize")
    check(ok, f"a 48 kHz stereo WAV answer without normalize: refused, says what to do ({msg[:90]})")
    t = FakeTransport([(200, response(wav_bytes(tone_pcm(rate=48000), 48000, channels=2)))] * 4)
    m2 = produce(plan, td / "d2", base_dir=d, providers={"gemini": prov(t)}, normalize={}, qc={})
    s2 = next(r for r in m2["sentences"] if r["id"] == "s2")
    check(s2["normalize"]["input"]["rate"] == 48000 and s2["normalize"]["downmixed"] and m2["qc"]["summary"]["error"] == 0
          and abs(s2["normalize"]["loudness"]["after"]["integrated_lufs"] + 20) <= 0.5,
          f"... with normalize: converted to 24 kHz mono, -20 LUFS, QC without errors ({m2['qc']['summary']})")
    for desc, script, needle in (
            ("invalid JSON", [(200, b"<html>")], "not valid JSON"),
            ("no audio in the response", [(200, b'{"interaction": {"steps": []}}')], "contains no audio"),
            ("invalid base64", [(200, b'{"interaction": {"output_audio": {"data": "@@@"}}}')], "not valid base64"),
            ("odd-length PCM", [(200, response(b"\x01\x02\x03"))], "odd length"),
            ("HTTP 500 that echoes the key", [(500, f'{{"error": "bad key {KEY}"}}'.encode())], "HTTP 500")):
        t = FakeTransport(script)
        try:
            produce(plan, td / "d3", base_dir=d, providers={"gemini": prov(t)})
            ok, msg = False, "accepted"
        except VoiceError as e:
            msg = "\n".join(e.problems)
            ok = needle in msg and KEY not in msg
        check(ok, f"refused with a clear message, key never shown: {desc} ({msg[:80]})")
    cdir = td / "cache"
    t = FakeTransport([(200, response(tone_pcm()))] + [(429, b'{"error": {"message": "Resource has been exhausted (quota)"}}')] * 5)
    ok, msg = refused(lambda: produce(plan, td / "d4", base_dir=d, providers={"gemini": prov(t)}, cache=Cache(cdir)), "HTTP 429", "nothing is retried")
    check(ok and len(t.calls) == 2, f"HTTP 429: the run stops at once, no retry (requests sent: {len(t.calls)}) ({msg[:80]})")

    print("\n== E cache + V2 together")
    t = FakeTransport()
    m3 = produce(plan, td / "e1", base_dir=d, providers={"gemini": prov(t)}, cache=Cache(cdir))
    check(len(t.calls) == 3 and m3["cache"]["hits"] == 1 and m3["providers"]["gemini"]["requests_used"] == 3,
          f"after the 429 stop, the next run reuses the cached first sentence and asks only for the rest ({len(t.calls)} requests)")
    t = FakeTransport()
    m4 = produce(plan, td / "e2", base_dir=d, providers={"gemini": prov(t)}, cache=Cache(cdir))
    check(not t.calls and m4["cache"]["hits"] == 5 and all(not r["generation"]["requested"] for r in m4["sentences"] if r["provider"] == "gemini"),
          "same input again: every sentence from the cache, 0 requests")
    t = FakeTransport()
    produce(plan, td / "e3", base_dir=d, providers={"gemini": prov(t, model="gemini-3.8-flash-lite-tts")}, cache=Cache(cdir))
    check(len(t.calls) == 4, "another model: the 4 AI sentences miss (the model is part of the cache key); the synthetic one hits")
    c_out = [p for p in (td / "e1").rglob("*") if p.is_file()] + [p for p in cdir.rglob("*") if p.is_file()]
    leak = [str(p) for p in c_out if KEY.encode() in p.read_bytes()]
    check(not leak, f"the API key appears in no produced file, manifest, report or cache entry ({len(c_out)} files checked)")
    syn = Cache(td / "cache2")
    base_plan = make_plan(load_casting(FIX / "voices.cast.json"), json.loads((FIX / "script.json").read_text(encoding="utf-8")), base_dir=FIX)
    produce(base_plan, td / "e5", base_dir=FIX, cache=syn)
    m6 = produce(base_plan, td / "e6", base_dir=FIX, cache=syn, providers={"gemini": prov(FakeTransport())})
    check(m6["cache"]["hits"] == 5, "enabling the provider does not change the cache keys of synthetic / prepared sentences (V2 caches stay valid)")
    b = td / "core"; (b / "audio").mkdir(parents=True)
    for r in m["sentences"]:
        shutil.copyfile(td / "c1" / r["file"], b / "audio" / f"{r['id']}.wav")
    cfg = json.loads((ROOT / "studio/config/studio.defaults.json").read_text(encoding="utf-8"))
    cfg["whisper"]["language"] = "en"
    (b / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    (b / "script.json").write_text(json.dumps({"meta": {"language": "en", "title": "v3"},
                                               "sentences": [{"id": r["id"], "text": r["text"]} for r in m["sentences"]]}, ensure_ascii=False), encoding="utf-8")
    core.BUILD, core.SCRIPT_PATH, core.CONFIG_PATH = b, b / "script.json", b / "config.json"
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        try:
            core.cmd_prepare(None); rc = 0
        except SystemExit as e:
            rc = e.code
    check(rc == 0, f"AI + synthetic sentence files go through the unchanged Stage 2 prepare (exit {rc} {err.getvalue()!r})")

    print("\n== F estimate / CLI")
    e = estimate(plan, cache=Cache(cdir), providers={"gemini": {}})
    check(e["gemini"]["requests"] == 0 and e["gemini"]["cached"] == 4, f"estimate with a warm cache: 0 requests needed ({e['gemini']['requests']})")
    e = estimate(plan, providers={"gemini": {}})
    check(e["gemini"]["requests"] == 4 and e["gemini"]["to_make"] == ["s1", "s2", "s3", "s5"] and e["synthetic"]["sentences"] == 1,
          "estimate without a cache: 4 requests (s1 s2 s3 s5), 1 synthetic sentence - computed without any request")
    env = {k: v for k, v in os.environ.items() if k not in ("GEMINI_API_KEY", "GEMINI_FREE_TIER_CONFIRMED")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run([sys.executable, "-B", str(VOICE / "cli.py"), "estimate", str(d / "voices.cast.json"), str(d / "script.json"),
                        "--allow-tts", "gemini"], capture_output=True, text=True, env=env)
    check(r.returncode == 0 and "4 API request(s)" in r.stdout, f"CLI estimate: {r.stdout.strip().splitlines()[0] if r.stdout else r.stderr[:100]}")
    r = subprocess.run([sys.executable, "-B", str(VOICE / "cli.py"), "produce", str(d / "voices.cast.json"), str(d / "script.json"),
                        "--out", str(td / "f1"), "--allow-tts", "gemini"], capture_output=True, text=True, env=env)
    check(r.returncode == 1 and "GEMINI_FREE_TIER_CONFIRMED" in r.stderr and not (td / "f1" / "audio").exists(),
          "CLI produce with --allow-tts but without the gates: refused before any request or file")


if __name__ == "__main__":
    main()
