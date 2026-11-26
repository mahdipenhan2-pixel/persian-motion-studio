#!/usr/bin/env python3
"""Timeline T5 - audio clips' mix fields (model only, standard library): gain_db (-60..+6 dB, default -24), fade_in /
fade_out (whole frames >= 0, together at most the clip's length); only on audio clips; a timeline without them is
judged exactly as before.
  python3 nfp/timeline/tests/test_timeline_t5.py
"""
import copy
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from timeline import model as M  # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


ASSETS = {"schema": "nfp.assets/1", "assets": [{"id": "bed", "kind": "audio", "local_path": "bed.wav", "sha256": "0" * 64, "duration": 30,
                                               "author": "test", "license": "original", "retrieved_at": "2026-11-26", "modifications": "none",
                                               "license_verified": True, "width": None, "height": None, "source_url": None,
                                               "license_url": None, "attribution": None, "restrictions": [], "real_person": False}]}
BASE = {"schema": "nfp.timeline/1", "fps": 30, "duration": 300, "mode": "draft",
        "tracks": [{"id": "music", "kind": "audio"}, {"id": "pics", "kind": "visual"}],
        "clips": [{"id": "m1", "track": "music", "kind": "audio", "start": 0, "end": 300, "asset": "bed"}]}


def codes(doc, level="error"):
    r = M.validate(doc, ASSETS, ".", None, check_files=False)
    return sorted({i["code"] for i in r["issues"] if i["level"] == level})


def with_clip(**kw):
    d = copy.deepcopy(BASE)
    d["clips"][0].update(kw)
    return d


def main():
    check(codes(BASE) == [], f"an audio clip without mix fields: valid as before {codes(BASE)}")
    check(M.AUDIO_GAIN_DEFAULT == -24.0, "default level -24 dB")
    ok = with_clip(gain_db=-18.5, fade_in=30, fade_out=60)
    check(codes(ok) == [], "gain_db -18.5, fade_in 30, fade_out 60: valid")
    check(codes(with_clip(gain_db=6)) == [] and codes(with_clip(gain_db=-60)) == [], "the range ends -60 and +6 are allowed")
    for kw, code in (({"gain_db": 7}, "bad_gain"), ({"gain_db": -61}, "bad_gain"), ({"gain_db": True}, "bad_gain"), ({"gain_db": "loud"}, "bad_gain"),
                     ({"fade_in": -1}, "bad_fade"), ({"fade_out": 1.5}, "bad_fade"), ({"fade_in": 200, "fade_out": 101}, "bad_fade")):
        check(code in codes(with_clip(**kw)), f"{kw} refused ({code})")
    d = copy.deepcopy(BASE)
    d["clips"].append({"id": "p1", "track": "pics", "kind": "image", "start": 0, "end": 90, "asset": "bed", "gain_db": -10})
    check("audio_field" in codes(d), "gain_db on an image clip refused (audio clips only)")
    n = copy.deepcopy(BASE)
    n["clips"][0]["volume"] = 0.5
    check("schema" in codes(n), "an unknown field is still refused")
    f = len(RESULTS) - sum(RESULTS)
    print(f"\n{len(RESULTS)} checks: {len(RESULTS) - f} passed, {f} failed. " + ("ALL TIMELINE T5 TESTS PASSED" if not f else "TIMELINE T5 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
