#!/usr/bin/env python3
"""
Draw the illustration images of studio/projects/motion-demo-fa locally (no network, no AI, no stock photos).

  python3 studio/tests/make_motion_demo_assets.py

Deterministic: the same code always writes byte-identical PNG files (no random numbers). Images are 1.5x the media
frame (1620x822 for a 1080x548 frame) so Ken Burns / zoom stay sharp. Pure Python + numpy + zlib.
"""
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "projects" / "motion-demo-fa" / "assets"
W, H = 1620, 822


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    path.write_bytes(png)


def gradient(top, bottom):
    t = np.linspace(0, 1, H)[:, None, None]
    img = np.array(top, float)[None, None, :] * (1 - t) + np.array(bottom, float)[None, None, :] * t
    return np.repeat(img, W, axis=1)


def ridge(x, base, waves):
    y = np.full_like(x, base, dtype=float)
    for amp, freq, phase in waves:
        y += amp * np.sin(freq * x + phase)
    return y


def paint_ridge(img, base, waves, colour, haze=0.0, sky=None):
    x = np.arange(W, dtype=float)
    top = ridge(x, base, waves)
    yy = np.arange(H, dtype=float)[:, None]
    mask = yy >= top[None, :]
    col = np.array(colour, float)
    if sky is not None and haze > 0:
        col = col * (1 - haze) + np.array(sky, float) * haze
    img[mask] = col
    return img


def glow(img, cx, cy, r, colour, strength):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** 2 * strength
    img[:] = img * (1 - a[..., None]) + np.array(colour, float)[None, None, :] * a[..., None]
    return img


def stars(img, seed_pts):
    for k in range(seed_pts):
        # deterministic pseudo-positions from a fixed integer sequence (no RNG)
        x = (k * 7919) % W
        y = (k * 104729) % int(H * 0.45)
        b = 140 + (k * 37) % 100
        img[y, x] = [b, b, min(255, b + 20)]
    return img


def hindukush_dusk():
    img = gradient((28, 32, 78), (214, 128, 92))
    img = glow(img, 1180, 560, 420, (255, 196, 120), 0.75)
    img = paint_ridge(img, 470, [(60, 0.004, 0.3), (26, 0.013, 1.1), (9, 0.041, 0.2)], (92, 70, 110), 0.25, (214, 128, 92))
    img = paint_ridge(img, 560, [(70, 0.0032, 2.0), (30, 0.011, 0.4), (10, 0.037, 1.7)], (58, 44, 82))
    img = paint_ridge(img, 660, [(48, 0.0045, 4.1), (22, 0.017, 2.2), (8, 0.05, 0.9)], (30, 24, 50))
    return img


def ridges_night():
    img = gradient((8, 14, 40), (44, 58, 110))
    img = stars(img, 900)
    img = glow(img, 420, 210, 260, (230, 232, 255), 0.55)
    img = paint_ridge(img, 500, [(80, 0.003, 1.3), (35, 0.012, 0.2), (12, 0.044, 2.5)], (52, 62, 104))
    img = paint_ridge(img, 600, [(60, 0.0041, 0.7), (28, 0.015, 1.9), (9, 0.052, 0.4)], (32, 38, 72))
    img = paint_ridge(img, 700, [(40, 0.006, 2.9), (18, 0.02, 0.8), (6, 0.06, 1.3)], (16, 20, 42))
    return img


def valley_dawn():
    img = gradient((250, 206, 150), (120, 96, 140))
    img = glow(img, 810, 330, 380, (255, 236, 190), 0.8)
    img = paint_ridge(img, 380, [(70, 0.0035, 0.1), (25, 0.014, 2.4), (8, 0.045, 0.6)], (176, 132, 140), 0.2, (250, 206, 150))
    img = paint_ridge(img, 500, [(55, 0.0042, 1.6), (20, 0.016, 0.9), (7, 0.05, 2.0)], (122, 92, 116))
    img = paint_ridge(img, 640, [(30, 0.005, 3.3), (14, 0.019, 1.4), (5, 0.06, 0.3)], (70, 54, 82))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("hindukush-dusk.png", hindukush_dusk), ("ridges-night.png", ridges_night),
                     ("valley-dawn.png", valley_dawn)):
        rgb = np.clip(fn(), 0, 255).astype(np.uint8)
        write_png(OUT / name, rgb)
        print(f"wrote {OUT / name} ({(OUT / name).stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())
