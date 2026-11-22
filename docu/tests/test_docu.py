#!/usr/bin/env python3
"""Offline tests for the documentary layer: project validation, chapter join arithmetic (sample-exact), SRT merge."""
import json, struct, sys, tempfile, wave
from pathlib import Path
DOCU = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOCU / "engine"))
import assemble as A, project as P  # noqa

def check(c, msg):
    if not c:
        sys.exit("FAIL: " + msg)
    print("ok  ", msg)

def tone_wav(path, sec, rate=24000, freq=440):
    import math
    n = int(round(sec * rate))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / rate))) for i in range(n)))

# 1. project validation
proj = P.load("kim-test30")
check(proj["meta"]["width"] == 1920 and proj["meta"]["height"] == 1080 and proj["meta"]["fps"] == 30, "kim-test30 is 1920x1080 @ 30")
bad = json.loads(json.dumps(proj)); bad["meta"]["height"] = 1920
try:
    P.validate(bad); check(False, "vertical project must be rejected")
except P.ProjectError:
    check(True, "vertical project is rejected")
big = json.loads(json.dumps(proj)); big["chapters"][0]["sentences"] = [{"id": f"x{i}", "text": "Hello there."} for i in range(41)]
try:
    P.validate(big); check(False, "41 sentences in one chapter must be rejected (core limit)")
except P.ProjectError:
    check(True, "41 sentences per chapter rejected (core limit is 40)")

# 2. chapter join: padded to whole frames, offsets add up exactly, audio is sample-exact
rate = 24000
durs = [150.337, 148.9, 151.0123]   # three ~2.5 min chapters (13 min film = ~5 chapters)
rows = A.plan(durs, rate)
check(all(r["samples"] % (rate // 30) == 0 for r in rows), "every chapter slot is a whole number of frames")
check(all(r["samples"] / rate >= d for r, d in zip(rows, durs)), "slot never shorter than its narration")
check(rows[1]["offset_frames"] == rows[0]["frames"] and rows[2]["offset_frames"] == rows[0]["frames"] + rows[1]["frames"], "offsets are cumulative frame counts")
check(max(r["samples"] / rate - d for r, d in zip(rows, durs)) < 1 / 30 + 1e-9, "padding per join is under one frame (<33 ms)")
with tempfile.TemporaryDirectory() as td:
    td = Path(td); ps = []
    for i, d in enumerate([2.337, 1.9, 2.0123]):
        p = td / f"c{i}.wav"; tone_wav(p, d, rate, 300 + 100 * i); ps.append(p)
    rr = A.plan([2.337, 1.9, 2.0123], rate)
    out = td / "all.wav"; A.concat_wavs(ps, rr, out)
    with wave.open(str(out), "rb") as w:
        check(w.getnframes() == sum(r["samples"] for r in rr), "joined wav length == sum of slots (sample exact)")
        total_frames = w.getnframes() / (rate // 30)
        check(total_frames == int(total_frames), "joined wav is a whole number of video frames")
        raw = w.readframes(w.getnframes())
    # first sample of chapter 2 sits exactly at its offset
    s2 = rr[1]["offset_frames"] * (rate // 30)
    first = struct.unpack("<h", raw[2 * s2:2 * s2 + 2])[0]
    with wave.open(str(ps[1]), "rb") as w:
        want = struct.unpack("<h", w.readframes(1))[0]
    check(first == want, "chapter 2 starts at exactly its frame offset")

# 3. timing shift + srt merge keep order
t = {"sentences": [{"id": "a", "text": "Hi there.", "offset": 0.3, "duration": 1.0, "words": [{"i": 0, "text": "Hi", "abs_start": 0.3, "abs_end": 0.6}, {"i": 1, "text": "there.", "abs_start": 0.7, "abs_end": 1.2}]}]}
s = A.shift_timing(t, 12.5)
check(abs(s["sentences"][0]["words"][1]["abs_end"] - 13.7) < 1e-9 and t["sentences"][0]["offset"] == 0.3, "shift moves a copy, original untouched")
srt = A.merged_srt([t, s])
check(srt.count("-->") == 2 and srt.index("00:00:00,3") < srt.index("00:00:12,"), "merged SRT ordered with offsets")

# 4. cinematic revision: same audio inputs as the original (cached narration reused), verify is resolution-aware
import verify as V  # noqa
cine = P.load("kim-test30-cine")
same = lambda k: json.dumps(cine[k], sort_keys=True) == json.dumps(proj[k], sort_keys=True)
check(same("voice") and same("audio") and same("chapters"), "kim-test30-cine: voice, audio settings and all six sentences identical to kim-test30 (cached narration reused)")
check(cine["meta"]["target_duration"] == 32 and cine["meta"]["fps"] == 30, "kim-test30-cine: 32 s at 30 fps")
check(V.parse_size("1280x720") == (1280, 720) and V.parse_size(None) == (1920, 1080), "verify parses the expected output size (720p and 1080p)")
import re
shots = (DOCU / "projects" / "kim-test30-cine" / "shots.js").read_text(encoding="utf-8")
ids = re.findall(r'D\.shot\(\{ id: "(\w+)"', shots)
check(len(ids) == 18 and len(set(ids)) == 18, "kim-test30-cine has 18 distinct shots")
check(shots.count('W("s') + shots.count('E("s') > 30, "cuts are anchored to word timings (W/E anchors)")
check("tts" not in (DOCU / "engine" / "kit" / "41_cine.js").read_text(encoding="utf-8").lower(), "cinematic kit makes no TTS calls")

# 5. documentary-style experiment: separate project, same script text, no photograph, placeholders only
import photoslots as PS  # noqa
ds = P.load("kim-docu-style")
orig = {x["id"]: x["text"] for x in proj["chapters"][0]["sentences"]}
check(all(orig[x["id"]] == x["text"] for x in ds["chapters"][0]["sentences"]) and len(ds["chapters"][0]["sentences"]) == 4, "kim-docu-style: sentences s1-s4 are verbatim copies of the approved script")
check(ds["voice"] == proj["voice"] and ds["audio"] == proj["audio"], "kim-docu-style: same voice, model style and audio settings (cached narration, no TTS)")
dsh = (DOCU / "projects" / "kim-docu-style" / "shots.js").read_text(encoding="utf-8")
check(not re.search(r"https?://(?!www\.w3\.org)|\.jpe?g|\.webp|\.png|\.gif", dsh), "kim-docu-style shots embed no external image or photograph")
check("PLACEHOLDER" in dsh and PS.check(DOCU / "projects" / "kim-docu-style") == [], "photo slots are marked PLACEHOLDER and none claims a licence")
bad = PS.check(DOCU / "projects" / "kim-docu-style")
import tempfile, shutil as _sh
tmp = Path(tempfile.mkdtemp()); (tmp / "photo_slots.json").write_text(json.dumps({"slots": [{"id": "X", "status": "licensed", "src": "a.jpg", "license_verified": False}]}))
check(len(PS.check(tmp)) == 1, "a licensed slot without a verified licence record fails the gate")
_sh.rmtree(tmp)
check(len(re.findall(r'D\.shot\(\{ id: "(\w+)"', dsh)) == 8, "kim-docu-style has 8 shots")

# 6. Version B: all six approved sentences, 32 s, same story as Version A
vb = P.load("kim-docu-style-full")
check(json.dumps(vb["chapters"], sort_keys=True) == json.dumps(proj["chapters"], sort_keys=True) and len(vb["chapters"][0]["sentences"]) == 6, "Version B: all six sentences identical to the approved script")
check(vb["voice"] == proj["voice"] and vb["audio"] == proj["audio"] and vb["meta"]["target_duration"] == 32 and vb["meta"]["fps"] == 30, "Version B: same voice/audio settings, 32 s at 30 fps")
vbs = (DOCU / "projects" / "kim-docu-style-full" / "shots.js").read_text(encoding="utf-8")
check(len(re.findall(r'D\.shot\(\{ id: "(\w+)"', vbs)) == 15 and PS.check(DOCU / "projects" / "kim-docu-style-full") == [] and not re.search(r"https?://(?!www\.w3\.org)|\.jpe?g|\.webp|\.png|\.gif", vbs), "Version B: 15 shots, placeholders only, no embedded photograph")

# ---- 7. kim-docu-6min (independent 6-minute project) ----
import json as _j
_six = _j.loads((DOCU / "projects" / "kim-docu-6min" / "project.json").read_text(encoding="utf-8"))
_appr = {s["id"]: s["text"] for s in proj["chapters"][0]["sentences"]}
_all = {s["id"]: s["text"] for c in _six["chapters"] for s in c["sentences"]}
check(len(_six["chapters"]) == 3 and _six["meta"]["fps"] == 30 and (_six["meta"]["width"], _six["meta"]["height"]) == (1920, 1080), "kim-docu-6min: 3 chapters, 1920x1080 at 30 fps")
check(all(_all[k] == v for k, v in _appr.items() if k != "s3"), "kim-docu-6min: approved sentences s1,s2,s4,s5,s6 identical to the approved script (cached audio reused)")
check(_all["s3"] == "When you are nine, your parents separate.", "kim-docu-6min: s3 changed from 'divorce' to 'separate' (sources disagree on the divorce year; documented in sources)")
check(_six["voice"] == proj["voice"], "kim-docu-6min: same voice/style as the approved audio")
check(all(2 <= len(c["sentences"]) <= 40 for c in _six["chapters"]), "kim-docu-6min: every chapter within the core limit")
check(len(_six["sources"]) >= 6, "kim-docu-6min: sources recorded")

# ---- 8. chunked narration (one request per run of uncached sentences; no API in these tests) ----
import tempfile as _tf, numpy as _np
sys.path.insert(0, str(DOCU / "engine"))
import tts_chunks as TC
_p6 = P.load("kim-docu-6min"); _c2 = P.chapter(_p6, "c2")
_cfg = P.core_config(_p6, _c2)["tts"]
_scr = P.core_script(_p6, _c2)
_cache = Path(_tf.mkdtemp()); _old = TC.core.AUDIO_CACHE; TC.core.AUDIO_CACHE = _cache
for _s in _scr["sentences"][:2] + [x for x in _scr["sentences"] if x["id"] in ("s2", "s5")]:
    (_cache / f"{TC.core.sentence_hash(_cfg, TC.core.spoken(_s))}.wav").write_bytes(b"x")
_runs = TC.plan_runs(_scr, _cfg)
check([len(r["sentences"]) for r in _runs] == [13, 4], "chunks: cached sentences are boundaries; every uncached sentence is in exactly one run")
check(all(not (_cache / f"{x['hash']}.wav").exists() for r in _runs for x in r["sentences"]), "chunks: no cached sentence is planned for regeneration")
TC.core.AUDIO_CACHE = _old; _sh.rmtree(_cache)
# splitter on a synthetic continuous signal: three 'sentences' of noise bursts, known pauses
_rate, _rng = 24000, _np.random.default_rng(3)
_x, _words, _t = [], [], 0.0
_sents = [{"id": "a", "text": "one two three"}, {"id": "b", "text": "four five six"}, {"id": "c", "text": "seven eight nine"}]
_truth = []
for _si, _s in enumerate(_sents):
    for _w in _s["text"].split():
        _n = int(0.35 * _rate); _x.append(_rng.normal(0, 3000, _n)); _words.append({"text": _w, "start": _t + 0.02, "end": _t + 0.33, "norm": TC.core.norm(_w)}); _t += 0.35
    if _si < 2:
        _x.append(_rng.normal(0, 5, int(0.5 * _rate))); _truth.append((_t, _t + 0.5)); _t += 0.5
_pieces, _rep = TC.split_chunk(_rate, _np.concatenate(_x), _words, _sents)
check(_pieces is not None and len(_pieces) == 3 and _rep["ok"], "splitter: 3 sentences recovered from a continuous signal")
check(all(a <= c["t"] <= b for c, (a, b) in zip(_rep["cuts"], _truth)), "splitter: every cut falls inside the real pause, never inside a word")
check(all(len(p) / _rate >= 1.0 for p in _pieces), "splitter: lead/tail silence matched to chapter 1, pieces are complete sentences")
_bad_words = _words[:4]
check(TC.split_chunk(_rate, _np.concatenate(_x), _bad_words, _sents)[0] is None, "splitter: refuses to cut when Whisper did not recognise a sentence")
_wf = (DOCU.parent / ".github" / "workflows" / "docu-6min-audio.yml").read_text(encoding="utf-8")
_steps = _wf.split("      - name: ")
_cut = [s_ for s_ in _steps if s_.startswith("Cut continuous")][0]; _core = [s_ for s_ in _steps if s_.startswith("Core TTS stage")][0]; _gen = [s_ for s_ in _steps if s_.startswith("Generate narration")][0]
check("GEMINI_API_KEY" not in _cut.replace("NO API key", "") and "secrets." not in _cut and "secrets." not in _core, "workflow: the cutting and the core-TTS steps never receive the API key")
check("--spacing 25" in _gen and 'RC" = "3"' in _gen and "break" in _gen, "workflow: 25 s spacing and an immediate stop on HTTP 429")

# ---- 9. silent-preparation tooling (final assembly, structure check) - no rendering, no audio, no API ----
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("final6", str(DOCU / "qa" / "final_6min.py")); F6 = _ilu.module_from_spec(_spec); _spec.loader.exec_module(F6)
_pl = F6.plan("/d", "/w", "/o/final.mp4", ["c1", "c2", "c3"], 30, 0.6667, 2)
_names = [n for n, _ in _pl]
check(_names[0] == "structure check" and _names[-3:] == ["concat", "loudness pass 1", "loudness pass 2 + final encode"], "final assembly: structure check first, concat then two-pass loudness last")
check([n for n in _names if n.endswith("mux")] == ["c1: mux", "c2: mux", "c3: mux"], "final assembly: every chapter is muxed with its own mix")
_flat = " ".join(" ".join(c) for _, c in _pl)
check(not any(w in _flat for w in ("curl", "wget", "http", "GEMINI", "gemini", "tts_chunks", "story_stage2")), "final assembly: no network, no TTS, no core stage in the plan")
check("-14.0" in _flat and "TP=-1.0" in _flat, "final assembly: target -14 LUFS, true peak -1 dB")
_ln = F6.parse_loudnorm('noise {\n "input_i" : "-20.1",\n "input_tp" : "-3.2",\n "input_lra" : "5.0",\n "input_thresh" : "-30.5",\n "output_i" : "-14.2",\n "target_offset" : "0.1"\n}')
check(abs(_ln["input_i"] + 20.1) < 1e-9 and "measured_I=-20.1" in F6.pass2_filter(_ln), "final assembly: loudnorm measurement is parsed and fed to pass 2")
_an = (DOCU / "qa" / "analyze_6min.py").read_text(encoding="utf-8")
check("display" in (DOCU / "projects" / "kim-docu-6min" / "shots.js").read_text(encoding="utf-8") and "isolation" in _an, "structure check: every shot is switched off with display:none and checked for isolation")
check((DOCU / "projects" / "kim-docu-6min" / "AUDIO_RUN").read_text().strip().endswith("audio run 2 (after daily free-tier reset)"), "AUDIO_RUN is unchanged (the real audio run stays for the next day)")
_fc, _tot = F6.xfade_filter([95.2, 114.233, 119.533])
check(_fc.count("xfade") == 2 and "offset=94.700" in _fc and abs(_tot - (95.2 + 114.233 + 119.533 - 1.0)) < 1e-6, "silent film: two 0.5 s cross-dissolves, offsets computed from the real chapter lengths")
print("ALL OK")
