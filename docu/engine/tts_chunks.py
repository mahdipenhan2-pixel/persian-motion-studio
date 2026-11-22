#!/usr/bin/env python3
"""Chunked narration for the documentary: ONE Gemini TTS request per run of consecutive uncached sentences,
then the continuous audio is cut back into per-sentence files so the locked core pipeline (tts -> prepare ->
whisper -> align) runs unchanged.

  generate  (system python, needs GEMINI_API_KEY)  1 request per run; raw chunk is saved at once (.cache/story/chunks)
  split     (whisper venv, NO API key)             Whisper word times -> cut at the quietest point between sentences
                                                   -> per-sentence WAVs written to the core cache under the core's own hash
  selftest  (no API at all)                        builds a continuous file from approved audio (chapter 1) and checks the cutter

Rules kept here:
  * the locked core (scripts/story_stage2.py) is imported, never modified; sentences already in the cache are never regenerated
    and never overwritten
  * same model / voice / style / API call (core.synth_once) as the per-sentence path
  * the free-tier spacing is >= 25 s (3 requests per minute) and an HTTP 429 stops ALL new requests at once (exit code 3)
  * nothing is routed around a limit; no retry after 429
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

ENGINE = Path(__file__).resolve().parent
ROOT = ENGINE.parent.parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ROOT / "scripts"))

import run as R  # noqa: E402  (documentary runner: only its setup() is used)
import story_stage2 as core  # noqa: E402  (locked core, imported unchanged)

CHUNKS = core.CACHE / "chunks"
HOP = 0.010              # energy frame (s)
LEAD, TAIL = 0.27, 0.375  # measured median silence around the approved chapter-1 sentences (s)
EXIT_QUOTA = 3


# ----------------------------------------------------------------------------- planning
def plan_runs(script, t, max_words=200):
    """Contiguous runs of sentences that are NOT in the core cache (cached sentences are boundaries)."""
    runs, cur = [], []
    for s in script["sentences"]:
        h = core.sentence_hash(t, core.spoken(s))
        if (core.AUDIO_CACHE / f"{h}.wav").exists():
            if cur:
                runs.append(cur)
            cur = []
            continue
        cur.append({"id": s["id"], "text": s["text"], "speak": core.spoken(s), "hash": h})
        if sum(len(x["speak"].split()) for x in cur) >= max_words:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    out = []
    for r in runs:
        text = " ".join(x["speak"] for x in r)
        payload = {"v": 1, "model": t["model"], "voice": t["voice"], "style": t.get("style", ""), "text": text}
        key = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        out.append({"sentences": r, "text": text, "key": key, "path": CHUNKS / f"chunk-{key[:24]}.wav"})
    return out


# ----------------------------------------------------------------------------- audio helpers
def read_wav(path):
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2, "expected mono 16-bit"
        return w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)


def write_wav(path, rate, x):
    pcm = np.clip(np.round(x), -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def rms_track(x, rate):
    n = max(1, int(rate * HOP))
    m = len(x) // n
    if m == 0:
        return np.zeros(1)
    return np.sqrt(np.mean(x[:m * n].reshape(m, n) ** 2, axis=1))


# ----------------------------------------------------------------------------- the cutter
def find_cut(rms, a, b, lo, hi, peak):
    """Best cut time between speech end `a` and next speech start `b` (Whisper times, seconds).
    Look inside [lo, hi]; prefer the longest quiet run (< 5 % of peak), cut at its centre; else the quietest frame."""
    i0, i1 = max(0, int(lo / HOP)), min(len(rms), int(math.ceil(hi / HOP)) + 1)
    if i1 - i0 < 2:
        c = (a + b) / 2
        return c, 0.0, "narrow-window"
    seg = rms[i0:i1]
    quiet = seg < 0.05 * peak
    best, run = (0, None), None
    for k, q in enumerate(list(quiet) + [False]):
        if q and run is None:
            run = k
        if not q and run is not None:
            if k - run > best[0]:
                best = (k - run, run)
            run = None
    if best[1] is not None and best[0] >= 3:         # >= 30 ms of real quiet
        k0, ln = best[1], best[0]
        return (i0 + k0 + ln / 2) * HOP, ln * HOP, "quiet-run"
    k = int(np.argmin(np.convolve(seg, np.ones(3) / 3, mode="same")))
    return (i0 + k + 0.5) * HOP, 0.0, "quietest-frame"


def split_chunk(rate, x, words, sents, min_word=0.6, lead=LEAD, tail=TAIL):
    """x: continuous samples. words: [{text,start,end,norm}] from Whisper (chunk time). sents: [{id,text}].
    Returns (pieces, report). pieces[i] = float samples of sentence i (lead/tail silence matched to chapter 1)."""
    toks, owner = [], []
    for si, s in enumerate(sents):
        for t in core.script_tokens(s["text"]):
            t = dict(t)
            t["i"] = len(toks)
            toks.append(t)
            owner.append(si)
    rows, ratio = core.align_words(toks, words, min_word)
    n = len(sents)
    rep = {"match_ratio": round(ratio, 3), "sentences": [], "warnings": [], "ok": True}
    first, last = [None] * n, [None] * n
    for r, si in zip(rows, owner):
        if r["start"] is None:
            continue
        first[si] = r["start"] if first[si] is None else min(first[si], r["start"])
        last[si] = r["end"] if last[si] is None else max(last[si], r["end"])
    cover = []
    for si in range(n):
        idx = [k for k, o in enumerate(owner) if o == si and toks[k]["norm"]]
        got = sum(1 for k in idx if rows[k]["start"] is not None)
        cover.append(got / max(1, len(idx)))
    if any(f is None for f in first) or min(cover) < 0.8:
        rep["ok"] = False
        rep["warnings"].append(f"sentence coverage too low: {[round(c, 2) for c in cover]}")
        return None, rep
    rms = rms_track(x, rate)
    peak = float(np.percentile(rms, 99)) or 1.0
    total = len(x) / rate
    cuts = [0.0]
    for si in range(n - 1):
        a, b = last[si], first[si + 1]
        if b < a:                                   # Whisper overlap: use the middle of the overlap
            a, b = b, a
            rep["warnings"].append(f"{sents[si]['id']}|{sents[si + 1]['id']}: Whisper words overlap")
        lo, hi = max(a - 0.20, (first[si] + last[si]) / 2), min(b + 0.20, (first[si + 1] + last[si + 1]) / 2)
        c, quiet, how = find_cut(rms, a, b, lo, hi, peak)
        if quiet < 0.05:
            rep["warnings"].append(f"{sents[si]['id']}|{sents[si + 1]['id']}: no real pause here (quiet {quiet * 1000:.0f} ms, {how})")
        cuts.append(c)
        rep.setdefault("cuts", []).append({"between": f"{sents[si]['id']}|{sents[si + 1]['id']}", "t": round(c, 3), "gap_ms": round((b - a) * 1000), "quiet_ms": round(quiet * 1000), "how": how,
                                              "whisper_end": round(a, 3), "whisper_start": round(b, 3), "window": [round(lo, 3), round(hi, 3)]})
    cuts.append(total)
    pieces = []
    fade = int(rate * 0.006)
    for si in range(n):
        i0, i1 = int(cuts[si] * rate), int(cuts[si + 1] * rate)
        seg = x[i0:i1].copy()
        r = rms_track(seg, rate)
        pk = r.max() if len(r) else 0
        idx = np.where(r > 0.08 * pk)[0] if pk > 0 else []
        if len(idx) == 0:
            rep["ok"] = False
            rep["warnings"].append(f"{sents[si]['id']}: silent segment")
            return None, rep
        on, off = idx[0] * HOP, (idx[-1] + 1) * HOP
        have_lead, have_tail = on, len(seg) / rate - off
        s0 = int(max(0, on - lead) * rate)
        s1 = int(min(len(seg) / rate, off + tail) * rate)
        core_part = seg[s0:s1].copy()
        core_part[:fade] *= np.linspace(0, 1, min(fade, len(core_part)))
        core_part[-fade:] *= np.linspace(1, 0, min(fade, len(core_part)))
        pad_l = int(max(0.0, lead - have_lead) * rate)
        pad_t = int(max(0.0, tail - have_tail) * rate)
        piece = np.concatenate([np.zeros(pad_l), core_part, np.zeros(pad_t)])
        words_n = len(sents[si]["text"].split())
        wps = words_n / max(0.1, off - on)
        rep["sentences"].append({"id": sents[si]["id"], "speech_s": round(off - on, 2), "wps": round(wps, 2),
                                 "coverage": round(cover[si], 2), "natural_lead_ms": round(have_lead * 1000), "natural_tail_ms": round(have_tail * 1000)})
        if not 1.3 <= wps <= 4.8:
            rep["ok"] = False
            rep["warnings"].append(f"{sents[si]['id']}: implausible pace {wps:.2f} words/s")
        pieces.append(piece)
    return pieces, rep


# ----------------------------------------------------------------------------- whisper
def whisper_chunk(path, wcfg):
    """Word timestamps of a chunk (cached next to the chunk). Runs only where faster-whisper is installed."""
    cache = Path(str(path) + ".whisper.json")
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        from faster_whisper import WhisperModel
        model = WhisperModel(str(wcfg.get("model", "small")), device="cpu", compute_type=str(wcfg.get("compute_type", "int8")))
        segs, info = model.transcribe(str(path), language=wcfg.get("language", "en"), word_timestamps=True, condition_on_previous_text=False)
        words = [{"text": w.word, "start": float(w.start), "end": float(w.end)} for sg in segs for w in (sg.words or [])]
        data = {"language": info.language, "words": words}
        tmp = cache.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache)
    out = []
    for w in data["words"]:
        nm = core.norm(w["text"])
        if nm and w["end"] > w["start"]:
            out.append({"text": w["text"].strip(), "start": w["start"], "end": w["end"], "norm": nm})
    return out


# ----------------------------------------------------------------------------- commands
def cmd_generate(a):
    proj, ch, build = R.setup(a.project, a.chapter)
    cfg, script = core.load_inputs()
    t = cfg["tts"]
    t["_timeout"] = max(float(t.get("_timeout", 120)), 240.0)   # a run is up to ~1 minute of speech; a timeout would waste a request
    CHUNKS.mkdir(parents=True, exist_ok=True)
    runs = plan_runs(script, t, a.max_words)
    print(f"chapter {ch['id']}: {len(runs)} run(s) of uncached sentences: {[len(r['sentences']) for r in runs]}")
    todo = [r for r in runs if not r["path"].exists()]
    if not todo:
        print("every run already has its raw chunk - no API request needed")
        return 0
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        core.die("GEMINI_API_KEY is empty (generate needs it; split does not)")
    used, last_call, log = 0, None, []
    for r in todo:
        ids = [s["id"] for s in r["sentences"]]
        for attempt in range(1, a.attempts + 1):
            if used >= a.max_requests:
                print(f"request budget of this run ({a.max_requests}) reached; stopping. Saved chunks stay cached.")
                return 1
            if last_call is not None:
                wait = a.spacing - (time.time() - last_call)
                if wait > 0:
                    print(f"  waiting {wait:.0f}s (free tier: 3 requests per minute)")
                    time.sleep(wait)
            used += 1
            print(f"{ids[0]}..{ids[-1]} ({len(ids)} sentences, {len(r['text'].split())} words): request {used}/{a.max_requests}")
            last_call = time.time()
            try:
                wav = core.synth_once(t, r["text"], key)
            except core.ApiError as e:
                log.append({"ids": ids, "status": e.status})
                if e.status == 429:
                    print(f"HTTP 429: {e.short}\nSTOP: free-tier limit reached. No further request is sent in this run.")
                    (build / "chunks_log.json").write_text(json.dumps({"requests": used, "log": log}), encoding="utf-8")
                    return EXIT_QUOTA
                if not e.retryable or attempt == a.attempts:
                    core.die(f"Gemini API error (HTTP {e.status}): {e.short}")
                print(f"  transient error (HTTP {e.status}): {e.short}; one more try after the spacing")
                continue
            tmp = r["path"].with_suffix(".tmp")
            tmp.write_bytes(wav)
            info = core.wav_info(tmp)
            tmp.replace(r["path"])
            log.append({"ids": ids, "status": 200, "seconds": round(info["duration"], 2)})
            print(f"  saved {r['path'].name}: {info['duration']:.1f}s")
            break
    (build / "chunks_log.json").write_text(json.dumps({"requests": used, "log": log}), encoding="utf-8")
    return 0


def cmd_split(a):
    proj, ch, build = R.setup(a.project, a.chapter)
    cfg, script = core.load_inputs()
    t, al = cfg["tts"], cfg["alignment"]
    runs = plan_runs(script, t, a.max_words)
    if not runs:
        print(f"chapter {ch['id']}: nothing to split (every sentence is already cached)")
        return 0
    reports, bad = [], 0
    for r in runs:
        ids = [s["id"] for s in r["sentences"]]
        if not r["path"].exists():
            print(f"{ids[0]}..{ids[-1]}: no raw chunk yet (not generated) - skipped")
            bad += 1
            continue
        rate, x = read_wav(r["path"])
        words = whisper_chunk(r["path"], cfg["whisper"])
        pieces, rep = split_chunk(rate, x, words, r["sentences"], al["_min_word"])
        rep["run"] = ids
        reports.append(rep)
        for w in rep["warnings"]:
            print(f"  warning: {w}")
        if pieces is None or not rep["ok"]:
            print(f"{ids[0]}..{ids[-1]}: REJECTED, nothing written to the sentence cache (raw chunk kept)")
            bad += 1
            continue
        for s, piece in zip(r["sentences"], pieces):
            dst = core.AUDIO_CACHE / f"{s['hash']}.wav"
            if dst.exists():
                continue                                        # never overwrite approved audio
            core.AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".tmp")
            write_wav(tmp, rate, piece)
            core.validate_wav(tmp)
            tmp.replace(dst)
        print(f"{ids[0]}..{ids[-1]}: {len(ids)} sentence files written to the cache")
    (build / "chunk_report.json").write_text(json.dumps(reports, indent=1), encoding="utf-8")
    return 1 if bad else 0


# ----------------------------------------------------------------------------- self test (no API)
def make_continuous(data_dir, gap_s, jitter_ms, seed=1):
    """Continuous test file from APPROVED chapter-1 sentences: only the speech (+ 40 ms) of each sentence, joined with a
    short natural pause. Ground truth = true speech end / next start. Whisper words come from the real chapter-1 Whisper timing."""
    rng = np.random.default_rng(seed)
    timing = json.loads((Path(data_dir) / "timing.json").read_text(encoding="utf-8"))
    rate, a = read_wav(Path(data_dir) / "narration.wav")
    parts, words, truth, sents, pos = [], [], [], [], 0.0
    for k, s in enumerate(timing["sentences"]):
        seg = a[int(s["offset"] * rate):int((s["offset"] + s["duration"]) * rate)]
        r = rms_track(seg, rate)
        idx = np.where(r > 0.08 * r.max())[0]
        on, off = max(0.0, idx[0] * HOP - 0.04), min(len(seg) / rate, (idx[-1] + 1) * HOP + 0.04)
        piece = seg[int(on * rate):int(off * rate)]
        for w in s["words"]:
            if w["abs_start"] is None:
                continue
            ws, we = w["abs_start"] - s["offset"] - on + pos, w["abs_end"] - s["offset"] - on + pos
            j = lambda: float(rng.uniform(-jitter_ms, jitter_ms)) / 1000
            ws, we = ws + j(), we + j()
            if we > ws:
                words.append({"text": w["text"], "start": max(0.0, ws), "end": we, "norm": core.norm(w["text"])})
        truth.append({"end": pos + len(piece) / rate - 0.04, "start": pos + 0.04})   # speech (8%-threshold) inside the piece
        parts.append(piece)
        pos += len(piece) / rate
        sents.append({"id": s["id"], "text": s["text"]})
        if k < len(timing["sentences"]) - 1:
            n = int(gap_s * rate)
            parts.append(rng.normal(0, 6, n))                 # quiet room tone
            pos += gap_s
    return rate, np.concatenate(parts), words, truth, sents


def cmd_selftest(a):
    ok_all = True
    for gap in a.gaps:
        for jit in a.jitters:
            rate, x, words, truth, sents = make_continuous(a.data, gap, jit)
            if a.whisper == "real":
                tmp = Path(a.workdir) / f"selftest_{int(gap * 1000)}.wav"
                tmp.parent.mkdir(parents=True, exist_ok=True)
                write_wav(tmp, rate, x)
                words = whisper_chunk(tmp, {"model": "small", "language": "en", "compute_type": "int8"})
            pieces, rep = split_chunk(rate, x, words, sents)
            if pieces is None:
                print(f"gap {gap * 1000:.0f} ms jitter {jit} ms: REJECTED {rep['warnings']}")
                ok_all = False
                continue
            errs, inside = [], 0
            for c, (t0, t1) in zip(rep["cuts"], zip(truth[:-1], truth[1:])):
                lo, hi = t0["end"], t1["start"]
                inside += lo - 0.005 <= c["t"] <= hi + 0.005
                errs.append(c["t"] - (lo + hi) / 2)
            n = len(rep["cuts"])
            for c, (t0, t1) in zip(rep["cuts"], zip(truth[:-1], truth[1:])):
                if not t0["end"] - 0.005 <= c["t"] <= t1["start"] + 0.005:
                    print(f"   MISS {c['between']}: cut {c['t']} s | true pause {t0['end']:.3f}..{t1['start']:.3f} | whisper last-word end {c['whisper_end']} / next-word start {c['whisper_start']} | window {c['window']} | {c['how']} quiet {c['quiet_ms']} ms")
            bad_dur = [p for p in pieces if len(p) < 0.5 * rate]
            ok = inside == n and not bad_dur and rep["ok"]
            ok_all &= ok
            print(f"gap {gap * 1000:>4.0f} ms | word-time jitter ±{jit:>3} ms | cuts inside the true pause: {inside}/{n} | "
                  f"mean |offset from pause centre| {np.mean(np.abs(errs)) * 1000:5.1f} ms | match {rep['match_ratio']} | {'OK' if ok else 'FAIL'}")
            if a.whisper == "real":
                print("   whisper words:", len(words), "| cuts:", [(c['between'], c['t']) for c in rep['cuts'][:3]], "...")
    print("SELFTEST", "PASSED" if ok_all else "FAILED")
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("generate", "split"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--chapter", required=True)
        p.add_argument("--max-words", type=int, default=200)
        if name == "generate":
            p.add_argument("--spacing", type=float, default=25.0)
            p.add_argument("--max-requests", type=int, default=7)
            p.add_argument("--attempts", type=int, default=2)
    p = sub.add_parser("selftest")
    p.add_argument("--data", required=True, help="folder with approved chapter-1 narration.wav + timing.json")
    p.add_argument("--whisper", choices=["timing", "real"], default="timing")
    p.add_argument("--gaps", type=float, nargs="+", default=[0.12, 0.3, 0.6])
    p.add_argument("--jitters", type=int, nargs="+", default=[0, 60, 120])
    p.add_argument("--workdir", default="build/selftest")
    a = ap.parse_args()
    sys.exit({"generate": cmd_generate, "split": cmd_split, "selftest": cmd_selftest}[a.cmd](a))


if __name__ == "__main__":
    main()
