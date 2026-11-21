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
print("ALL OK")
