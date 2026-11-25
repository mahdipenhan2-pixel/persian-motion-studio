"""NFP Graphics - G1: the safe area of the 16:9 Film frame (1920x1080). Standard library; data + checks only.

All rectangles are [x, y, w, h] in frame pixels (the reserved-rect format of nfp.host/1, ARCHITECTURE.md section 5).
  TITLE_SAFE   the 90 % title-safe area                         x 96..1824, y 54..1026
  BAND         Film's subtitle band (#band, subtitle_layer.py)   y 830..1080 - reserved: no graphic enters it
  ALLOWED      where a graphic (full frame or overlay) may draw  x 96..1824, y 54..830
Vignette: Film's post layer (kit 40_fx.js: a radial gradient over the frame's bounding box, r = 75 %, clear up to 0.55,
#0a0508 at 0.62 opacity at the edge) + 5 % scan lines on every other 2 px row. vignette_at(x, y) is the share of light a
graphic loses there (G0 measured it in a real render: frame corner 42 %, centre 2.5 %, see tests).
"""
import math

FRAME = (1920, 1080)
TITLE_SAFE = (96, 54, 1728, 972)
BAND = (0, 830, 1920, 250)
ALLOWED = (96, 54, 1728, 776)
RESERVED = ({"id": "subtitles", "rect": list(BAND), "verified_by": "G0 real render (nfp/graphics/README.md section 4)"},)
VIGNETTE_WARN = 0.20            # a text box loses more light than this at one of its corners -> warning
SCAN = 0.025                    # scan lines: 5 % black on half the rows


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def is_rect(r):
    return isinstance(r, (list, tuple)) and len(r) == 4 and all(_num(v) for v in r) and r[2] > 0 and r[3] > 0


def inside(r, area, tol=1e-9):
    return r[0] >= area[0] - tol and r[1] >= area[1] - tol and r[0] + r[2] <= area[0] + area[2] + tol and r[1] + r[3] <= area[1] + area[3] + tol


def intersects(a, b):
    """Positive-area overlap (touching edges do not count)."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def vignette_at(x, y):
    """Share of light lost at frame point (x, y) under Film's vignette + scan lines (0 = none, 1 = black)."""
    u, v = (x - FRAME[0] / 2) / FRAME[0], (y - FRAME[1] / 2) / FRAME[1]
    t = math.hypot(u, v) / 0.75
    a = 0.0 if t <= 0.55 else 0.62 * min(1.0, (t - 0.55) / 0.45)
    return 1 - (1 - a) * (1 - SCAN)


def vignette_of(r):
    """The worst (largest) light loss over a rectangle: at one of its corners (the gradient grows outwards)."""
    return max(vignette_at(x, y) for x in (r[0], r[0] + r[2]) for y in (r[1], r[1] + r[3]))


def check_rect(r, where, add):
    """Errors / warnings for one graphic box. add(level, code, message, element)."""
    if not is_rect(r):
        add("error", "rect", "a rect is [x, y, w, h] with w, h > 0", where)
        return False
    if intersects(r, BAND):
        add("error", "subtitle_band", f"{list(r)} enters the subtitle band (y >= {BAND[1]})", where)
        return False
    if not inside(r, ALLOWED):
        add("error", "outside_safe_area", f"{list(r)} is outside the graphics safe area {list(ALLOWED)} "
                                          f"(x {ALLOWED[0]}..{ALLOWED[0] + ALLOWED[2]}, y {ALLOWED[1]}..{ALLOWED[1] + ALLOWED[3]})", where)
        return False
    vg = vignette_of(r)
    if vg > VIGNETTE_WARN:
        add("warning", "vignette", f"{list(r)}: the film's vignette darkens a corner of it by {vg:.0%} (> {VIGNETTE_WARN:.0%})", where)
    return True


def check_overlays(items):
    """Overlays shown at the same time must not cover each other. items: [(id, start, end, rect)] with frames
    [start, end). -> [(id_a, id_b, first common frame, last common frame)] for every clash."""
    out = []
    for i, (a, s0, e0, r0) in enumerate(items):
        for b, s1, e1, r1 in items[i + 1:]:
            if s0 < e1 and s1 < e0 and intersects(r0, r1):
                out.append((a, b, max(s0, s1), min(e0, e1) - 1))
    return out
