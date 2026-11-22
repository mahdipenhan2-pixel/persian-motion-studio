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
print("ALL OK")
