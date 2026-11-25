#!/usr/bin/env python3
"""T1 - Timeline Engine data + QC: nfp.timeline/1, nfp.assets/1, anchors -> frames. Offline, temp folders only.

  python3 nfp/timeline/tests/test_timeline_t1.py
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TLDIR = HERE.parent
NFP = TLDIR.parent
sys.path.insert(0, str(NFP))
import timeline as TL                    # noqa: E402
from timeline import assets as AS        # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def codes(rep, level=None):
    return [x["code"] for x in rep["issues"] if level is None or x["level"] == level]


WORDS = {"schema": "nfp.film.words/1", "lang": "en", "fps": 30, "duration": 15.0, "sentences": [
    {"id": "s1", "text": "One two three.", "offset": 0.3, "duration": 2.0, "words": [
        {"i": 0, "text": "One", "start": 0.3, "end": 0.8, "timed": True, "estimated": False},
        {"i": 1, "text": "two", "start": 0.8, "end": 1.4, "timed": True, "estimated": False},
        {"i": 2, "text": "three.", "start": 1.4, "end": 2.3, "timed": True, "estimated": False}]},
    {"id": "s2", "text": "Four 294 six.", "offset": 2.6, "duration": 3.017, "words": [
        {"i": 0, "text": "Four", "start": 2.6, "end": 3.1, "timed": True, "estimated": False},
        {"i": 1, "text": "294", "start": None, "end": None, "timed": False, "estimated": False},
        {"i": 2, "text": "six.", "start": 4.25, "end": 5.617, "timed": True, "estimated": False}]}]}


def tracks(**over):
    T = [{"id": "narr", "kind": "narration"}, {"id": "pic", "kind": "visual"}, {"id": "ov", "kind": "overlay"},
         {"id": "sub", "kind": "subtitles"}, {"id": "chars", "kind": "characters"}, {"id": "snd", "kind": "audio"}]
    for t in T:
        t.update(over.get(t["id"], {}))
    return T


def tl(clips, **kw):
    d = {"schema": "nfp.timeline/1", "fps": 30, "duration": 450, "mode": "draft", "tracks": tracks(), "clips": clips}
    d.update(kw)
    return d


def asset(aid, kind="image", **kw):
    a = {"id": aid, "kind": kind, "local_path": None, "sha256": None, "width": 1920 if kind != "audio" else None,
         "height": 1080 if kind != "audio" else None, "duration": None, "source_url": None, "author": None, "license": None,
         "license_url": None, "retrieved_at": None, "modifications": None, "license_verified": False, "attribution": None,
         "restrictions": [], "real_person": False}
    a.update(kw)
    return a


def full(aid, path, sha, kind="image", **kw):
    return asset(aid, kind, local_path=path, sha256=sha, source_url="https://commons.example.org/wiki/File:X.jpg",
                 author="A. Photographer", license="CC BY 4.0", license_url="https://creativecommons.org/licenses/by/4.0/",
                 retrieved_at="2026-11-20", modifications="cropped to 16:9", license_verified=True,
                 attribution="Photo: A. Photographer (CC BY 4.0)", **kw)


def tiny_png(w, h):
    import struct
    import zlib
    rows = []
    for y in range(h):
        row = bytearray(b"\0")                     # filter type 0, then RGB per pixel
        for x in range(w):
            row += bytes((x * 255 // max(1, w - 1), y * 255 // max(1, h - 1), 128))
        rows.append(bytes(row))
    raw = b"".join(rows)
    chunk = lambda k, d: struct.pack(">I", len(d)) + k + d + struct.pack(">I", zlib.crc32(k + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="nfp-timeline-t1-"))
    media = tmp / "proj" / "media"
    media.mkdir(parents=True)
    png = tiny_png(1920, 1080)                     # a real PNG (the T2 checks read its header and size)
    (media / "harbour.png").write_bytes(png)
    (media / "parade.mp4").write_bytes(b"fake-video-bytes" * 20)
    (media / "music.wav").write_bytes(b"RIFF-test" * 10)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    s_png, s_mp4, s_wav = sha(media / "harbour.png"), sha(media / "parade.mp4"), sha(media / "music.wav")
    base = tmp / "proj"
    ctx = TL.Context.from_words(WORDS)

    print("== schema and structure")
    clips = [{"id": "n1", "track": "narr", "kind": "narration", "start": 9, "end": 69, "ref": "s1"},
             {"id": "v1", "track": "pic", "kind": "svg-shot", "start": 0, "end": 78, "ref": "street"},
             {"id": "v2", "track": "pic", "kind": "map", "start": 78, "end": 200},
             {"id": "v3", "track": "pic", "kind": "motion", "start": 200, "end": 300},
             {"id": "v4", "track": "pic", "kind": "animation", "start": 300, "end": 450},
             {"id": "o1", "track": "ov", "kind": "motion", "start": 30, "end": 90},
             {"id": "u1", "track": "sub", "kind": "subtitles", "start": 9, "end": 140, "ref": "subtitles.json"},
             {"id": "k1", "track": "chars", "kind": "character", "start": 0, "end": 78, "ref": "omid-room"},
             {"id": "a1", "track": "snd", "kind": "audio", "start": 0, "end": 300, "asset": "music"}]
    adoc = {"schema": "nfp.assets/1", "assets": [full("music", "media/music.wav", s_wav, "audio", width=None, height=None, duration=12.0)]}
    rep = TL.validate(tl(clips), adoc, base, ctx)
    check(rep["status"] == "OK" and not codes(rep, "error") and not codes(rep, "warning"),
          f"all six track kinds and every clip kind (image, video, map, motion, animation, svg-shot ...): QC OK {codes(rep)}")
    for bad, code in (({"schema": "nfp.timeline/2"}, "schema"), ({"fps": 25}, "fps"), ({"duration": 15.0}, "bad_duration"),
                      ({"duration": 0}, "bad_duration"), ({"extra": 1}, "schema"), ({"mode": "publish"}, "schema"),
                      ({"tracks": []}, "schema")):
        r = TL.validate(tl([], **bad))
        check(code in codes(r, "error"), f"refused: {bad} -> {code}")
    r = TL.validate(tl([], tracks=tracks() + [{"id": "pic", "kind": "visual"}, {"id": "x", "kind": "music"}]))
    check({"duplicate_id", "bad_kind"} <= set(codes(r, "error")), "duplicate track id and unknown track kind refused")
    r = TL.validate(tl([{"id": "n", "track": "pic", "kind": "narration", "start": 0, "end": 9},
                        {"id": "s", "track": "pic", "kind": "svg-shot", "start": 9, "end": 20},
                        {"id": "c", "track": "chars", "kind": "character", "start": 0, "end": 9},
                        {"id": "z", "track": "nope", "kind": "image", "start": 0, "end": 9},
                        {"id": "q", "track": "pic", "kind": "map", "start": 0, "end": 9, "colour": "red"}]))
    check(codes(r, "error").count("ref_required") == 2 and {"bad_kind", "unknown_track", "schema"} <= set(codes(r, "error")),
          "wrong clip kind for the track, missing ref (svg-shot / character), unknown track, unknown field refused")

    print("\n== ids and times")
    r = TL.validate(tl([{"id": "a", "track": "ov", "kind": "map", "start": 0, "end": 9},
                        {"id": "a", "track": "ov", "kind": "map", "start": 20, "end": 30},
                        {"id": "bad id", "track": "ov", "kind": "map", "start": 0, "end": 9},
                        {"id": "-x", "track": "ov", "kind": "map", "start": 0, "end": 9}]))
    check(codes(r, "error").count("duplicate_id") == 1 and codes(r, "error").count("bad_id") == 2, "duplicate and malformed clip ids refused")
    for c, code in (({"start": 1.5, "end": 9}, "bad_time"), ({"start": -1, "end": 9}, "bad_time"), ({"start": 9, "end": 9}, "bad_time"),
                    ({"start": 20, "end": 10}, "bad_time"), ({"start": True, "end": 9}, "bad_time"), ({"start": 400, "end": 460}, "outside_video")):
        r = TL.validate(tl([dict({"id": "c", "track": "ov", "kind": "map"}, **c)]))
        check(code in codes(r, "error"), f"invalid time {c} -> {code}")
    r = TL.validate(tl([{"id": "c", "track": "ov", "kind": "map", "start": 440, "end": 450}]))
    check(r["status"] in ("OK", "WARN") and not codes(r, "error"), "a clip ending exactly at the video end is valid (end is exclusive)")

    print("\n== anchors")
    good = {"id": "c", "track": "pic", "kind": "map", "start": ctx.resolve(0.3), "end": ctx.resolve(["s2", "w", 0]),
            "anchors": {"start": 0.3, "end": ["s2", "w", 0]}}
    r = TL.validate(tl([good]), context=ctx)
    check(not codes(r, "error") and (good["start"], good["end"]) == (9, 78), f"anchors resolve to the recorded frames ({good['start']}, {good['end']})")
    r = TL.validate(tl([dict(good, end=79)]), context=ctx)
    check("anchor_mismatch" in codes(r, "error"), "a frame that does not match its anchor is refused")
    for an in ({"start": ["s9", "w", 0]}, {"start": ["s1", "w", 7]}, {"start": ["s1", 1.4]}, {"start": "begin"}, {"middle": 3}, {}):
        r = TL.validate(tl([dict(good, anchors=an)]), context=ctx)
        check("bad_anchor" in codes(r, "error"), f"bad anchor refused: {an}")
    r = TL.validate(tl([good]))
    check("anchors_unchecked" in codes(r, "info") and not codes(r, "error"), "without word timing anchors are only shape-checked (info)")
    check([ctx.resolve(x) for x in (0, 1 / 60, 0.05, "end", ["s1", "e", 2], ["s1", 0.5], ["s2", "w", 1], ["s2", "e", 1])]
          == [0, 1, 2, 450, 69, 39, 128, 129],
          "anchor -> frame: 0, 1/60 s (half frame rounds up like Math.round), 0.05 s, end, word end, fraction, never-timed word (next word's start, +0.06 s)")
    check(TL.js_round(2.5) == 3 and TL.js_round(-2.5) == -2 and TL.js_round(0.49999999999999994) == 0,
          "JavaScript rounding rule (not Python's round-half-even)")
    r = TL.validate(tl([good], duration=451), context=ctx)
    check("duration_mismatch" in codes(r, "error"), "timeline duration must equal the video's (words.json)")
    res = TL.resolve(tl([{"id": "c", "track": "pic", "kind": "map", "start": 0, "end": 1, "anchors": {"start": ["s1", "w", 1], "end": "end"}}],
                        duration=1), ctx)
    check(res["duration"] == 450 and (res["clips"][0]["start"], res["clips"][0]["end"]) == (24, 450)
          and not codes(TL.validate(res, context=ctx), "error"), "resolve(): frames and duration filled in from anchors")

    print("\n== overlap and gaps")
    r = TL.validate(tl([{"id": "a", "track": "pic", "kind": "map", "start": 0, "end": 100},
                        {"id": "b", "track": "pic", "kind": "map", "start": 90, "end": 200}]))
    check("overlap" in codes(r, "error"), "overlap on a visual track refused")
    r = TL.validate(tl([{"id": "a", "track": "pic", "kind": "map", "start": 0, "end": 100},
                        {"id": "b", "track": "pic", "kind": "map", "start": 100, "end": 200}]))
    check("overlap" not in codes(r), "clips that touch (end = next start) do not overlap")
    r = TL.validate(tl([{"id": "a", "track": "ov", "kind": "map", "start": 0, "end": 100},
                        {"id": "b", "track": "ov", "kind": "motion", "start": 50, "end": 150},
                        {"id": "c", "track": "chars", "kind": "character", "start": 0, "end": 99, "ref": "x"},
                        {"id": "d", "track": "chars", "kind": "character", "start": 0, "end": 99, "ref": "y"}]))
    check("overlap" not in codes(r), "overlay and character tracks allow overlap (stacked graphics, several characters)")
    r = TL.validate(tl([{"id": "a", "track": "ov", "kind": "map", "start": 0, "end": 100},
                        {"id": "b", "track": "ov", "kind": "map", "start": 50, "end": 150}], tracks=tracks(ov={"overlap": False})))
    check("overlap" in codes(r, "error"), "a track can forbid overlap explicitly")
    gapped = [{"id": "a", "track": "pic", "kind": "map", "start": 0, "end": 100},
              {"id": "b", "track": "pic", "kind": "map", "start": 130, "end": 450}]
    r = TL.validate(tl(gapped))
    check(r["status"] == "OK" and "gap" in codes(r, "info"), "an intentional gap is allowed (listed as info only)")
    r = TL.validate(tl(gapped, tracks=tracks(pic={"coverage": True})))
    check("gap" in codes(r, "error") and "100..129" in json.dumps(r["issues"]), "coverage: true -> the gap (frames 100..129) is an error")
    r = TL.validate(tl([{"id": "a", "track": "pic", "kind": "map", "start": 0, "end": 450}], tracks=tracks(pic={"coverage": True})))
    check(not codes(r, "error"), "coverage: true and fully covered -> no error")

    print("\n== assets: local files, hashes, licences, drafts")
    ok = full("harbour", "media/harbour.png", s_png, width=1920, height=1080)
    st, iss = AS.check({"schema": "nfp.assets/1", "assets": [ok]}, base)
    check(st == {"harbour": "verified"} and not [x for x in iss if x["level"] == "error"], "complete record + file + sha256 -> verified")
    cases = [
        (dict(ok, local_path="media/missing.png"), "missing_file"),
        (dict(ok, sha256="0" * 64), "sha256_mismatch"),
        (dict(ok, sha256="ABC"), "bad_sha256"),
        (dict(ok, local_path="../outside.png"), "bad_path"),
        (dict(ok, local_path="/etc/hosts"), "bad_path"),
        (dict(ok, retrieved_at="20/11/2026"), "bad_date"),
        (dict(ok, source_url="commons page"), "bad_url"),
        (dict(ok, restrictions=["no-derivatives"]), "restriction"),
        (dict(ok, duration=3.0), "bad_duration"),
        (dict(ok, kind="poster"), "bad_kind"),
        (dict(ok, width=0), "bad_size"),
    ]
    for a, code in cases:
        st, iss = AS.check({"schema": "nfp.assets/1", "assets": [a]}, base)
        check(code in [x["code"] for x in iss if x["level"] == "error"] and st.get(a["id"]) == "draft",
              f"{code}: refused, asset stays a draft")
    os.symlink("/etc/hosts", media / "link.png")
    st, iss = AS.check({"schema": "nfp.assets/1", "assets": [dict(ok, local_path="media/link.png")]}, base)
    check("bad_path" in [x["code"] for x in iss], "a symlink leading out of the project is refused")
    for a, why in ((dict(ok, author=None), "author"), (dict(ok, license_verified=False), "license_verified"),
                   (dict(ok, attribution=""), "attribution"), (dict(ok, sha256=None), "pinned"), (asset("x"), "missing")):
        st, iss = AS.check({"schema": "nfp.assets/1", "assets": [a]}, base)
        draft = [x["message"] for x in iss if x["code"] == "draft"]
        check(st[a["id"]] == "draft" and draft and why in draft[0] and not [x for x in iss if x["level"] == "error"],
              f"incomplete record ({why}): registered as a draft, no error")
    orig = dict(ok, id="anim-1", kind="animation", license="original", source_url=None, license_url=None, author="NFP studio",
                attribution="Animation: NFP studio", modifications="none")
    st, _ = AS.check({"schema": "nfp.assets/1", "assets": [orig]}, base)
    check(st["anim-1"] == "verified", "license 'original' (own animation): no source / licence URL needed")
    st, iss = AS.check({"schema": "nfp.assets/1", "assets": [ok, ok, dict(ok, id="y", colour=1), {"id": "z"}]}, base)
    cs = [x["code"] for x in iss if x["level"] == "error"]
    check("duplicate_id" in cs and cs.count("schema") >= 2, "duplicate asset id, unknown field and missing fields refused")
    st, iss = AS.check({"schema": "nfp.assets/1", "assets": [dict(ok, real_person=True)]}, base)
    check(st["harbour"] == "verified" and "real_person" in [x["code"] for x in iss], "real person: recorded and flagged (info)")
    st, iss = AS.check({"schema": "nfp.assets/1", "assets": [ok]}, base, check_files=False)
    check(st["harbour"] == "draft", "without a file check nothing is verified")

    print("\n== timeline + assets")
    reg = {"schema": "nfp.assets/1", "assets": [
        ok, full("parade", "media/parade.mp4", s_mp4, "video", duration=10.0),
        dict(full("draft-map", "media/harbour.png", s_png, "map"), license_verified=False),
        full("music", "media/music.wav", s_wav, "audio", width=None, height=None, duration=12.0)]}
    clips = [{"id": "p1", "track": "pic", "kind": "image", "start": 0, "end": 90, "asset": "harbour"},
             {"id": "p2", "track": "pic", "kind": "video", "start": 90, "end": 300, "asset": "parade", "in": 60},
             {"id": "p3", "track": "ov", "kind": "map", "start": 0, "end": 60, "asset": "draft-map"}]
    r = TL.validate(tl(clips), reg, base)
    check(not codes(r, "error") and "draft_asset" in codes(r, "warning") and r["assets"]["parade"] == "verified",
          "draft mode: a clip on a draft asset is a warning")
    r = TL.validate(tl(clips, mode="final"), reg, base)
    check("draft_asset" in codes(r, "error"), "final mode: a clip on a draft asset is an error")
    r = TL.validate(tl(clips[:2], mode="final"), reg, base)
    check(r["status"] == "OK", "final mode with verified assets only: OK")
    for c, code in (({"id": "x", "track": "pic", "kind": "image", "start": 0, "end": 9, "asset": "nope"}, "unknown_asset"),
                    ({"id": "x", "track": "pic", "kind": "image", "start": 0, "end": 9, "asset": "parade"}, "asset_kind"),
                    ({"id": "x", "track": "pic", "kind": "image", "start": 0, "end": 9}, "asset_required"),
                    ({"id": "x", "track": "pic", "kind": "svg-shot", "start": 0, "end": 9, "ref": "s", "asset": "harbour"}, "asset_not_allowed"),
                    ({"id": "x", "track": "pic", "kind": "video", "start": 0, "end": 120, "asset": "parade", "in": 200}, "beyond_media"),
                    ({"id": "x", "track": "pic", "kind": "image", "start": 0, "end": 9, "asset": "harbour", "in": 3}, "in_not_allowed"),
                    ({"id": "x", "track": "pic", "kind": "video", "start": 0, "end": 9, "asset": "parade", "in": -1}, "bad_time")):
        r = TL.validate(tl([c]), reg, base)
        check(code in codes(r, "error"), f"{code}: refused")
    r = TL.validate(tl([{"id": "x", "track": "pic", "kind": "video", "start": 0, "end": 240, "asset": "parade", "in": 60}]), reg, base)
    check(not codes(r, "error"), "a video clip that fits its media (in 60 + 240 frames <= 300) is valid")

    print("\n== photoslots.py compatibility (Film's licence gate, read-only)")
    sys.path.insert(0, str(NFP / "film" / "engine"))
    import photoslots
    d = tmp / "slots"
    d.mkdir()
    (d / "photo_slots.json").write_text(json.dumps({"slots": [AS.to_photo_slot(ok), AS.to_photo_slot(asset("x"))]}), encoding="utf-8")
    check(photoslots.check(d) == [], "a verified asset is a valid 'licensed' photo slot; a draft a valid placeholder")
    (d / "photo_slots.json").write_text(json.dumps({"slots": [AS.to_photo_slot(dict(ok, author=None))]}), encoding="utf-8")
    check(photoslots.check(d) != [] and AS.check({"schema": "nfp.assets/1", "assets": [dict(ok, author=None)]}, base)[0]["harbour"] == "draft",
          "the same missing licence field fails both gates")

    print("\n== command line, determinism, independence")
    (base / "timeline.json").write_text(json.dumps(tl(clips[:2], mode="final")), encoding="utf-8")
    (base / "assets.json").write_text(json.dumps(reg), encoding="utf-8")
    (base / "words.json").write_text(json.dumps(WORDS), encoding="utf-8")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cli = lambda *a: subprocess.run([sys.executable, "-B", str(TLDIR / "cli.py"), *map(str, a)], capture_output=True, text=True, env=env)
    r1 = cli("check", base / "timeline.json", "--assets", base / "assets.json", "--words", base / "words.json")
    (base / "bad.json").write_text(json.dumps(tl(clips, mode="final")), encoding="utf-8")
    r2 = cli("check", base / "bad.json", "--assets", base / "assets.json")
    r3 = cli("assets", base / "assets.json")
    r4 = cli("resolve", base / "timeline.json", "--words", base / "words.json", "--out", base / "resolved.json")
    check(r1.returncode == 0 and "QC OK" in r1.stdout and r2.returncode == 1 and "draft_asset" in r2.stdout
          and r3.returncode == 0 and r4.returncode == 0 and (base / "resolved.json").exists(),
          "cli check / assets / resolve: exit 0 on OK, 1 on errors")
    a1 = json.dumps(TL.validate(tl(clips), reg, base, ctx))
    a2 = json.dumps(TL.validate(tl(clips), reg, base, ctx))
    check(a1 == a2, "deterministic: the same input gives the same report")
    src = "".join(p.read_text(encoding="utf-8") for p in TLDIR.glob("*.py"))
    mods = sorted(set(re.findall(r"^\s*(?:from|import) ([\w.]+)", src, re.M)))
    allowed = {"argparse", "copy", "fractions", "hashlib", "json", "math", "pathlib", "re", "struct", "sys",
               ".", ".anchors", ".assets", ".model", ".imagefile", ".kenburns", ".videofile", "timeline", "timeline.assets"}
    check(set(mods) <= allowed, f"nfp/timeline imports only the standard library and itself {mods}")
    check(not re.search(r"urllib|requests|http\.client|socket|subprocess", src), "no network or process code in nfp/timeline")
    shutil.rmtree(tmp)
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL TIMELINE T1 TESTS PASSED" if not f else "TIMELINE T1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
