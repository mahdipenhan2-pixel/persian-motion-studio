#!/usr/bin/env python3
"""T2 - Ken Burns camera + image headers in nfp/timeline (no Film, no browser). Temp folders only; test images are made
here with the standard library (PNG) or hand-built headers (JPEG / EXIF).

  python3 nfp/timeline/tests/test_timeline_t2.py
"""
import hashlib
import math
import shutil
import struct
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent.parent), str(HERE)]
import timeline as TL                        # noqa: E402
from timeline import kenburns as KB          # noqa: E402
from timeline import imagefile as IF         # noqa: E402
from test_timeline_t1 import tiny_png, full, tl  # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def jpeg_header(w, h, orientation=None):
    """SOI + optional APP1 Exif (IFD0 Orientation) + SOF0 + EOI: enough for a header reader (not a decodable image)."""
    out = b"\xff\xd8"
    if orientation is not None:
        tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1) + struct.pack("<HHIHH", 0x0112, 3, 1, orientation, 0) + b"\0\0\0\0"
        seg = b"Exif\0\0" + tiff
        out += b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    sof = struct.pack(">BHHB", 8, h, w, 3) + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    return out + b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof + b"\xff\xd9"


def inside(cam, w, h):
    """Every interpolated frame of the move stays inside the image (checked numerically at 61 points)."""
    _, Wc, Hc = KB.cover(w, h)
    for k in range(61):
        e = KB.ease(cam["ease"], k / 60)
        s0, X0, Y0 = KB.transform(cam["from"], w, h)
        s1, X1, Y1 = KB.transform(cam["to"], w, h)
        s, X, Y = s0 + (s1 - s0) * e, X0 + (X1 - X0) * e, Y0 + (Y1 - Y0) * e
        if X > 1e-6 or Y > 1e-6 or X + s * Wc < 1920 - 1e-6 or Y + s * Hc < 1080 - 1e-6:
            return False
    return True


def main():
    tmp = Path(tempfile.mkdtemp(prefix="nfp-timeline-t2-"))
    print("== image headers (PNG / JPEG / EXIF)")
    (tmp / "a.png").write_bytes(tiny_png(48, 27))
    (tmp / "b.jpg").write_bytes(jpeg_header(4000, 3000))
    (tmp / "c.jpg").write_bytes(jpeg_header(4000, 3000, orientation=6))
    (tmp / "d.gif").write_bytes(b"GIF89a" + b"\0" * 20)
    check(IF.info(tmp / "a.png") == {"format": "png", "width": 48, "height": 27, "orientation": 1}, "PNG size from IHDR")
    check(IF.info(tmp / "b.jpg") == {"format": "jpeg", "width": 4000, "height": 3000, "orientation": 1}, "JPEG size from SOF0")
    check(IF.info(tmp / "c.jpg")["orientation"] == 6, "JPEG EXIF orientation read (6 = rotated 90 degrees)")
    try:
        IF.info(tmp / "d.gif")
        ok = False
    except IF.ImageError:
        ok = True
    check(ok, "GIF (or anything not PNG / JPEG) is refused")

    print("\n== cover fit (no stretching, no empty space at scale 1)")
    for w, h in ((3840, 2160), (2400, 1800), (2000, 3000), (6000, 1500), (1920, 1080)):
        c, Wc, Hc = KB.cover(w, h)
        check(abs(Wc / Hc - w / h) < 1e-12 and Wc >= 1920 - 1e-9 and Hc >= 1080 - 1e-9 and (abs(Wc - 1920) < 1e-9 or abs(Hc - 1080) < 1e-9),
              f"{w}x{h}: drawn {Wc:.1f}x{Hc:.1f} - same aspect ratio, covers 1920x1080, one side exact")

    print("\n== presets")
    W, H, F = 3840, 2160, 90
    st = KB.expand(None, W, H)
    check(st["from"] == st["to"] == {"scale": 1.0, "x": 0.5, "y": 0.5} and KB.check(st, W, H, F) == [], "no camera = still image, centred")
    zi = KB.expand({"preset": "zoom-in", "amount": 0.15}, W, H)
    zo = KB.expand({"preset": "zoom-out", "amount": 0.15}, W, H)
    check(zi["from"]["scale"] == 1.0 and zi["to"]["scale"] == 1.15 and zo["from"] == zi["to"] and zo["to"] == zi["from"],
          "zoom-in 1 -> 1.15 and zoom-out its mirror")
    zf = KB.expand({"preset": "zoom-in", "amount": 0.2, "focus": {"x": 0.02, "y": 0.98}}, W, H)
    lo = KB.bounds(1.2, *KB.cover(W, H)[1:])
    check(abs(zf["to"]["x"] - lo[0][0]) < 1e-12 and abs(zf["to"]["y"] - lo[1][1]) < 1e-12, "a focus near the edge is pulled inside (no empty space)")
    pr = KB.expand({"preset": "pan-right"}, W, H)
    pl = KB.expand({"preset": "pan-left"}, W, H)
    pu = KB.expand({"preset": "pan-up"}, W, H)
    pd = KB.expand({"preset": "pan-down"}, W, H)
    s_r, X0, _ = KB.transform(pr["from"], W, H)
    _, X1, _ = KB.transform(pr["to"], W, H)
    _, _, Y0 = KB.transform(pd["from"], W, H)
    _, _, Y1 = KB.transform(pd["to"], W, H)
    check(pr["to"]["x"] > pr["from"]["x"] and pl["from"] == pr["to"] and abs((X0 - X1) - 0.12 * 1920) < 1e-6,
          f"pan-right: the view travels right, the picture {X0 - X1:.1f} px left (0.12 x 1920); pan-left is its mirror")
    check(pd["to"]["y"] > pd["from"]["y"] and pu["from"] == pd["to"] and abs((Y0 - Y1) - 0.12 * 1080) < 1e-6,
          f"pan-down / pan-up: {Y0 - Y1:.1f} px vertical travel (0.12 x 1080)")
    for w, h in ((6000, 1500), (2400, 3600)):
        p = KB.expand({"preset": "pan-right" if w > h else "pan-down"}, w, h)
        _, a, b = KB.transform(p["from"], w, h)
        _, c, d = KB.transform(p["to"], w, h)
        check(abs(math.hypot(c - a, d - b) - 0.12 * (1920 if w > h else 1080)) < 1e-6 and not [x for x in KB.check(p, w, h, F) if x[0] != "info"],
              f"{w}x{h}: a pan preset stays calm on a {'wide' if w > h else 'tall'} image ({math.hypot(c - a, d - b):.0f} px in 3 s)")
    combo = KB.expand({"from": {"scale": 1.0, "x": 0.5, "y": 0.5}, "to": {"scale": 1.25, "x": 0.45, "y": 0.55}, "ease": "power1.inOut"}, W, H)
    check(combo["preset"] == "custom" and KB.check(combo, W, H, 60) == [], "a combined move (zoom + pan) from / to")
    cams = (None, {"preset": "zoom-in"}, {"preset": "zoom-out"}, {"preset": "pan-left"}, {"preset": "pan-right"},
            {"preset": "pan-up"}, {"preset": "pan-down"}, {"preset": "zoom-in", "amount": 0.3, "focus": {"x": 0, "y": 1}}, combo)
    sizes = ((3840, 2160), (2400, 1800), (2400, 3600), (6000, 1500))
    check(all(inside(KB.expand(c, w, h) if c is not combo else c, w, h) for w, h in sizes for c in cams),
          f"{len(cams)} moves x {len(sizes)} aspect ratios: every interpolated frame stays inside the image")

    print("\n== camera checks")
    bad = KB.expand({"from": {"scale": 1.0, "x": 0.3, "y": 0.5}, "to": {"scale": 1.0, "x": 0.5, "y": 0.5}}, W, H)
    check([x[1] for x in KB.check(bad, W, H, F)] == ["empty_space"], "from x 0.3 at scale 1 on a 16:9 image -> empty space, refused")
    check({x[1] for x in KB.check(KB.expand({"from": {"scale": 0.9}}, W, H), W, H, F)} == {"bad_camera"}, "scale below 1 refused")
    check(("warning", "upscale") == KB.check(KB.expand(None, 1600, 900), 1600, 900, F)[0][:2], "a 1600x900 image (1.2x enlarged): warning")
    check(("error", "upscale") == KB.check(KB.expand(None, 800, 450), 800, 450, F)[0][:2], "an 800x450 image (2.4x enlarged): refused")
    check(("warning", "upscale") == KB.check(KB.expand({"preset": "zoom-in", "amount": 0.8}, 1920, 1080), 1920, 1080, F)[0][:2]
          and ("error", "upscale") == KB.check(KB.expand({"preset": "zoom-in", "amount": 1.2}, 1920, 1080), 1920, 1080, F)[0][:2],
          "zooming a 1920x1080 image to 1.8x warns, to 2.2x is refused")
    fast = KB.expand({"from": {"scale": 1.3, "x": 0.4, "y": 0.5}, "to": {"scale": 1.3, "x": 0.6, "y": 0.5}}, W, H)
    check("fast_pan" in [x[1] for x in KB.check(fast, W, H, 30)], "a fast pan (1 s) is reported")
    check("fast_zoom" in [x[1] for x in KB.check(KB.expand({"preset": "zoom-in", "amount": 0.5}, W, H), W, H, 45)], "a fast zoom is reported")
    for cam in ({"preset": "spin"}, {"preset": "zoom-in", "amount": 0}, {"preset": "zoom-in", "ease": "bounce"}, {"from": {"z": 1}},
                {"to": {"scale": 1}}, {"preset": "static", "focus": {"x": 2}}, "zoom", {"preset": "pan-right", "speed": 1}):
        try:
            KB.expand(cam, W, H)
            ok = False
        except KB.CameraError:
            ok = True
        check(ok, f"malformed camera refused: {cam}")
    check(all(abs(KB.ease(n, 0)) < 1e-12 and abs(KB.ease(n, 1) - 1) < 1e-12 and abs(KB.ease(n, 0.5) - 0.5) < 1e-12 for n in KB.EASES),
          "eases run 0 -> 1 through 0.5 (GSAP formulas)")

    print("\n== timeline QC with cameras")
    media = tmp / "p" / "media"
    media.mkdir(parents=True)
    (media / "small.png").write_bytes(tiny_png(64, 36))
    (media / "rot.jpg").write_bytes(jpeg_header(4000, 3000, orientation=6))
    (media / "ok.jpg").write_bytes(jpeg_header(4000, 3000))
    (media / "fake.png").write_bytes(b"not an image")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    reg = {"schema": "nfp.assets/1", "assets": [
        full("small", "media/small.png", sha(media / "small.png"), width=64, height=36),
        full("rot", "media/rot.jpg", sha(media / "rot.jpg"), width=4000, height=3000),
        full("ok", "media/ok.jpg", sha(media / "ok.jpg"), width=4000, height=3000),
        full("wrongsize", "media/ok.jpg", sha(media / "ok.jpg"), width=3000, height=2000),
        full("fake", "media/fake.png", sha(media / "fake.png"), width=10, height=10)]}
    st, iss = TL.check_assets(reg, tmp / "p")
    codes = {(x.get("asset"), x["code"]) for x in iss if x["level"] == "error"}
    check(st["ok"] == "verified" and {("rot", "exif_rotation"), ("wrongsize", "size_mismatch"), ("fake", "unsupported_format")} <= codes,
          "assets: real size, EXIF rotation and format read from the file")
    clip = lambda **k: dict({"id": "c", "track": "pic", "kind": "image", "start": 0, "end": 90, "asset": "ok"}, **k)
    r = TL.validate(tl([clip(camera={"preset": "zoom-in"})]), {"schema": "nfp.assets/1", "assets": reg["assets"][2:3]}, tmp / "p")
    check(r["status"] == "OK", "an image clip with a zoom-in on a verified 4000x3000 JPEG: OK")
    for c, code in ((clip(asset="small"), "upscale"), (clip(camera={"from": {"scale": 1, "x": 0.1, "y": 0.5}}), "empty_space"),
                    (clip(camera={"preset": "wobble"}), "bad_camera"),
                    ({"id": "m", "track": "pic", "kind": "map", "start": 0, "end": 9, "camera": {"preset": "zoom-in"}}, "camera_not_allowed")):
        r = TL.validate(tl([c]), reg, tmp / "p")
        check(code in [x["code"] for x in r["issues"] if x["level"] == "error"], f"{code}: refused in the timeline")
    shutil.rmtree(tmp)
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL TIMELINE T2 TESTS PASSED" if not f else "TIMELINE T2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
