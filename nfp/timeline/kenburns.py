"""NFP Timeline - Ken Burns camera for still images (T2): presets, the 'cover' fit, and the no-empty-space rule.

A still image is first fitted to COVER the 1920x1080 frame (aspect ratio kept, the overflow cropped, never stretched):
cover = max(1920 / w, 1080 / h), drawn at Wc x Hc = w*cover x h*cover. The camera then looks at it with
  scale  >= 1    (1 = the cover fit, 1.2 = 20 % closer)
  x, y   0..1    the image point at the centre of the frame (0.5, 0.5 = image centre)
so the image group is drawn with   translate(X, Y) scale(scale),   X = 960 - scale*x*Wc,   Y = 540 - scale*y*Hc.
No empty space: x must stay in [960/(scale*Wc), 1 - 960/(scale*Wc)] (y likewise with 540 and Hc). Both ends are checked;
the Director interpolates scale, X and Y with the same ease and duration, and the 'inside' conditions are linear in
(scale, X, Y), so every frame in between is inside too.

camera (clip field, optional; none = static):
  {"preset": "static" | "zoom-in" | "zoom-out" | "pan-left" | "pan-right" | "pan-up" | "pan-down",
   "amount": 0.12,                    zoom: scale change (1 -> 1.12); pan: zoom 1 + amount, travel amount x 1920 px
                                      (horizontal) / x 1080 px (vertical) on screen - a 16:9 image's whole room
   "focus": {"x": 0.5, "y": 0.5},     zoom: the point zoomed into / out of; pan: the line the pan travels along
   "ease": "sine.inOut"}
  {"from": {"scale": 1, "x": 0.4, "y": 0.5}, "to": {"scale": 1.15, "x": 0.6, "y": 0.45}, "ease": "sine.inOut"}   any combination
"""
import math

OUT_W, OUT_H, FPS = 1920, 1080, 30
PRESETS = ("static", "zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down")
EASES = ("sine.inOut", "power1.inOut", "power2.inOut", "none")
DEFAULT_AMOUNT = 0.12
MAX_SCALE = 4.0
UPSCALE_WARN, UPSCALE_MAX = 1.0, 2.0          # screen pixels per image pixel: > 1 softens, > 2 refused
PAN_WARN = 150.0                              # px / s on screen
ZOOM_WARN = 0.15                              # |ln(scale change)| per second
EPS = 1e-9


class CameraError(ValueError):
    pass


def cover(w, h):
    c = max(OUT_W / w, OUT_H / h)
    return c, w * c, h * c


def bounds(scale, Wc, Hc):
    hx, hy = OUT_W / (2 * scale * Wc), OUT_H / (2 * scale * Hc)
    return (hx, 1 - hx), (hy, 1 - hy)


def _clamp(v, lo, hi):
    return min(max(v, lo), hi)


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise CameraError(f"{name} must be a number")
    return float(v)


def _point(p, name):
    if not isinstance(p, dict) or set(p) - {"scale", "x", "y"} or not p:
        raise CameraError(f"{name} must be an object with scale / x / y")
    return {"scale": _num(p.get("scale", 1.0), f"{name}.scale"), "x": _num(p.get("x", 0.5), f"{name}.x"),
            "y": _num(p.get("y", 0.5), f"{name}.y")}


def expand(camera, w, h):
    """camera (None, preset or from/to) -> {"from": {scale, x, y}, "to": {...}, "ease": str, "preset": str}."""
    _, Wc, Hc = cover(w, h)
    cam = {"preset": "static"} if camera is None else camera
    if not isinstance(cam, dict):
        raise CameraError("camera must be an object")
    ease = cam.get("ease", "sine.inOut")
    if ease not in EASES:
        raise CameraError(f"ease must be one of {', '.join(EASES)}")
    if "preset" in cam:
        extra = set(cam) - {"preset", "amount", "focus", "ease"}
        if extra:
            raise CameraError(f"unknown camera field(s) {', '.join(sorted(extra))}")
        p = cam["preset"]
        if p not in PRESETS:
            raise CameraError(f"preset must be one of {', '.join(PRESETS)}")
        a = _num(cam.get("amount", DEFAULT_AMOUNT if p != "static" else 0.0), "amount")
        if not 0 <= a <= MAX_SCALE - 1:
            raise CameraError(f"amount must be 0..{MAX_SCALE - 1:g}")
        f = cam.get("focus", {"x": 0.5, "y": 0.5})
        if not isinstance(f, dict) or set(f) - {"x", "y"}:
            raise CameraError("focus must be an object with x / y")
        fx, fy = _num(f.get("x", 0.5), "focus.x"), _num(f.get("y", 0.5), "focus.y")
        if not (0 <= fx <= 1 and 0 <= fy <= 1):
            raise CameraError("focus x / y must be 0..1")

        def at(s, x, y):
            (x0, x1), (y0, y1) = bounds(s, Wc, Hc)
            return {"scale": s, "x": _clamp(x, x0, x1), "y": _clamp(y, y0, y1)}

        if p == "static":
            a0 = a1 = at(1.0 + a, fx, fy)
        elif p in ("zoom-in", "zoom-out"):
            if a <= 0:
                raise CameraError("a zoom needs amount > 0")
            lo, hi = at(1.0, fx, fy), at(1.0 + a, fx, fy)
            a0, a1 = (lo, hi) if p == "zoom-in" else (hi, lo)
        else:
            # a pan travels amount x frame width (height) on screen, centred on the focus and kept inside the image:
            # exactly the room a 16:9 image has at this zoom, so wide / tall images do not race across
            s = 1.0 + a
            (x0, x1), (y0, y1) = bounds(s, Wc, Hc)

            def span(c, lo, hi, want):
                d = min(want, hi - lo)
                if d <= EPS:
                    raise CameraError(f"no room to {p} at this zoom - raise amount")
                start = _clamp(c - d / 2, lo, hi - d)
                return start, start + d

            if p in ("pan-left", "pan-right"):
                u0, u1 = span(fx, x0, x1, a * OUT_W / (s * Wc))
                y = _clamp(fy, y0, y1)
                a0, a1 = {"scale": s, "x": u0, "y": y}, {"scale": s, "x": u1, "y": y}
                if p == "pan-left":
                    a0, a1 = a1, a0
            else:
                v0, v1 = span(fy, y0, y1, a * OUT_H / (s * Hc))
                x = _clamp(fx, x0, x1)
                a0, a1 = {"scale": s, "x": x, "y": v0}, {"scale": s, "x": x, "y": v1}
                if p == "pan-up":
                    a0, a1 = a1, a0
        return {"preset": p, "from": a0, "to": a1, "ease": ease}
    extra = set(cam) - {"from", "to", "ease"}
    if extra or "from" not in cam:
        raise CameraError("camera needs either preset or from / to" + (f" (unknown {', '.join(sorted(extra))})" if extra else ""))
    a0 = _point(cam["from"], "from")
    a1 = _point(cam.get("to", cam["from"]), "to")
    return {"preset": "custom", "from": a0, "to": a1, "ease": ease}


def check(cam, w, h, frames):
    """Issues of an expanded camera for an image of w x h pixels shown for `frames` frames: [(level, code, message)]."""
    c, Wc, Hc = cover(w, h)
    out = []
    for end in ("from", "to"):
        p = cam[end]
        if not 1.0 - EPS <= p["scale"] <= MAX_SCALE:
            out.append(("error", "bad_camera", f"{end}.scale {p['scale']:g} must be 1..{MAX_SCALE:g} (1 = the image covers the frame)"))
            continue
        (x0, x1), (y0, y1) = bounds(p["scale"], Wc, Hc)
        if not (x0 - EPS <= p["x"] <= x1 + EPS and y0 - EPS <= p["y"] <= y1 + EPS):
            out.append(("error", "empty_space", f"{end} (scale {p['scale']:g}, x {p['x']:.4f}, y {p['y']:.4f}) would show empty "
                                                f"space: at this scale x must be {x0:.4f}..{x1:.4f} and y {y0:.4f}..{y1:.4f}"))
    if any(x[0] == "error" for x in out):
        return out
    eff = c * max(cam["from"]["scale"], cam["to"]["scale"])
    if eff > UPSCALE_MAX + EPS:
        out.append(("error", "upscale", f"the image ({w}x{h}) would be enlarged {eff:.2f}x (max {UPSCALE_MAX:g}x) - use a "
                                        f"larger original or less zoom"))
    elif eff > UPSCALE_WARN + EPS:
        out.append(("warning", "upscale", f"the image ({w}x{h}) is enlarged {eff:.2f}x at its closest: it will look soft"))
    secs = frames / FPS
    a0, a1 = cam["from"], cam["to"]
    moving = any(abs(a0[k] - a1[k]) > EPS for k in a0)
    if moving:
        s_avg = (a0["scale"] + a1["scale"]) / 2
        pan = math.hypot((a1["x"] - a0["x"]) * Wc, (a1["y"] - a0["y"]) * Hc) * s_avg / secs
        zoom = abs(math.log(a1["scale"] / a0["scale"])) / secs
        if pan > PAN_WARN:
            out.append(("warning", "fast_pan", f"the camera travels {pan:.0f} px/s (calm: <= {PAN_WARN:g}) - lengthen the clip or move less"))
        if zoom > ZOOM_WARN:
            out.append(("warning", "fast_zoom", f"zoom rate {zoom:.3f}/s (calm: <= {ZOOM_WARN:g}) - lengthen the clip or zoom less"))
        if secs < 1.0:
            out.append(("warning", "short_move", f"a camera move in only {secs:.2f} s"))
    return out


def transform(p, w, h):
    """(scale, X, Y) of the image group for one camera point."""
    _, Wc, Hc = cover(w, h)
    return p["scale"], OUT_W / 2 - p["scale"] * p["x"] * Wc, OUT_H / 2 - p["scale"] * p["y"] * Hc


def ease(name, t):
    """GSAP's ease curves used here (for tests and previews)."""
    t = min(max(t, 0.0), 1.0)
    if name == "none":
        return t
    if name == "sine.inOut":
        return -(math.cos(math.pi * t) - 1) / 2
    if name == "power1.inOut":
        return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
    if name == "power2.inOut":
        return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
    raise CameraError(f"unknown ease {name}")
