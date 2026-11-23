"""
Camera move catalogue and the safety mathematics that keeps every move out of the caption band.

All numbers are computed here, in Python, so the browser side (camera.js) only replays fixed values: the result is
deterministic and seekable, which HyperFrames requires (no random numbers, no timers, no infinite repeats).

Coordinates are the 1080x1920 composition. A state is {"s": scale, "x": px, "y": px}; scale is applied around the
centre of the element it moves (transform-origin 50% 50%).

Two kinds of target:
  media     an image inside a clipped frame (top 0-548 or bottom 1372-1920). Moves are free but must never reveal
            the frame's empty edge ("coverage"): |x| <= (s-1)*W/2 and |y| <= (s-1)*H/2.
  scene     the existing scene graphics (.zt top zone 110-540, .zb bottom zone 1400-1630, .deco), wrapped in one
            layer centred on (540, 960). Moves are small and always keep the zone edges out of the caption band.
"""
import hashlib

WIDTH, HEIGHT = 1080, 1920
CENTER_X, CENTER_Y = WIDTH / 2, HEIGHT / 2
CAPTION_BAND = (560, 1360)              # measured by the locked Stage 2 verify step (crop=1080:800:0:560)
BAND_MARGIN = 8                         # graphics/media must stay at least this far from the band
TOP_ZONE = (110, 540)                   # .zt in base.html
BOTTOM_ZONE = (1400, 1630)              # .zb in base.html
SIDE_ZONE = (70, 1010)                  # left/right padding of .zt/.zb

# Media frames: full width, outside the caption band (with margin), and never over the progress bar (#track,
# y 64-72) or the handle line (#handle, from y 1660), which live in the background layer below the scenes.
FRAMES = {
    "top": {"top": 96, "bottom": 548},
    "bottom": {"top": 1372, "bottom": 1640},
}
RESERVED = {"progress bar": (64, 72), "handle": (1660, 1710)}

MOVES = ("none", "zoom-in", "zoom-out", "push-in", "pull-out", "pan-left", "pan-right", "pan-up", "pan-down",
         "pan-start", "pan-end", "ken-burns")
TARGETS = ("media", "scene")
EASES = ("none", "sine.inOut", "power1.inOut", "power2.inOut", "power1.out", "power2.out")
DEFAULT_EASE = {
    "zoom-in": "sine.inOut", "zoom-out": "sine.inOut",
    "push-in": "power2.inOut", "pull-out": "power2.inOut",
    "pan-left": "sine.inOut", "pan-right": "sine.inOut", "pan-up": "sine.inOut", "pan-down": "sine.inOut",
    "pan-start": "sine.inOut", "pan-end": "sine.inOut",
    "ken-burns": "sine.inOut", "none": "none",
}
TRANSITIONS = ("fade", "slide", "zoom-through", "wipe")
TRANSITION_DEFAULT_SEC = 0.35
TRANSITION_LIMITS = (0.15, 0.6)
SPEED_LIMITS = (0.25, 4.0)
TRANSITION_MAX_SCALE = 1.02          # a whole-scene zoom; kept small so frames never cover the progress bar

IDENTITY = {"s": 1.0, "x": 0.0, "y": 0.0}


class CameraError(ValueError):
    pass


def _r(v):
    return round(float(v), 4)


def _state(s=1.0, x=0.0, y=0.0):
    return {"s": _r(s), "x": _r(x), "y": _r(y)}


def resolve_direction(move, lang):
    """pan-start / pan-end follow the reading direction: in RTL (fa) the start side is the right."""
    rtl = lang == "fa"
    if move == "pan-start":
        return "pan-right" if rtl else "pan-left"
    if move == "pan-end":
        return "pan-left" if rtl else "pan-right"
    return move


def variant_of(scene_id):
    """Stable 0-3 variant for Ken Burns, derived from the scene id (never random)."""
    return int(hashlib.sha256(str(scene_id).encode("utf-8")).hexdigest()[:8], 16) % 4


# ------------------------------------------------------------------------------------------------ media moves
def _media_states(move, i, frame, variant):
    fw = WIDTH
    fh = frame["bottom"] - frame["top"]
    if move == "none":
        return _state(), _state()
    if move in ("zoom-in", "zoom-out"):
        z = 1.0 + 0.06 + 0.24 * i
        a, b = _state(1.0), _state(z)
        return (a, b) if move == "zoom-in" else (b, a)
    if move in ("push-in", "pull-out"):
        z = 1.0 + 0.10 + 0.30 * i
        drift = -0.35 * (z - 1.0) * fh / 2          # a slight rise, always inside coverage
        a, b = _state(1.0), _state(z, 0, drift)
        return (a, b) if move == "push-in" else (b, a)
    if move in ("pan-left", "pan-right", "pan-up", "pan-down"):
        s = 1.08 + 0.12 * i
        if move in ("pan-left", "pan-right"):
            amp = 0.9 * (s - 1.0) * fw / 2
            # camera moves left -> picture slides right
            a, b = (_state(s, -amp), _state(s, amp)) if move == "pan-left" else (_state(s, amp), _state(s, -amp))
        else:
            amp = 0.9 * (s - 1.0) * fh / 2
            a, b = (_state(s, 0, -amp), _state(s, 0, amp)) if move == "pan-up" else (_state(s, 0, amp), _state(s, 0, -amp))
        return a, b
    if move == "ken-burns":
        s_small = 1.06
        s_big = 1.06 + 0.10 + 0.16 * i
        dx = 1 if variant in (0, 2) else -1
        dy = 1 if variant in (0, 1) else -1
        ax = 0.8 * (s_small - 1.0) * fw / 2
        ay = 0.8 * (s_small - 1.0) * fh / 2
        a = _state(s_small, -dx * ax, -dy * ay)
        b = _state(s_big, dx * ax, dy * ay)
        return (a, b) if variant in (0, 3) else (b, a)
    raise CameraError(f"unknown move '{move}'")


# ------------------------------------------------------------------------------------------------ scene moves
def _scene_states(move, i):
    if move == "none":
        return _state(), _state()
    if move in ("zoom-in", "zoom-out"):
        z = 1.0 + 0.008 + 0.016 * i                # never below 1.0 (band); at most 1.024 (progress bar / handle)
        a, b = _state(1.0), _state(z)
        return (a, b) if move == "zoom-in" else (b, a)
    if move in ("push-in", "pull-out"):
        z = 1.0 + 0.010 + 0.014 * i
        a, b = _state(1.0), _state(z)
        return (a, b) if move == "push-in" else (b, a)
    if move in ("pan-left", "pan-right"):
        amp = 10 + 30 * i
        return (_state(1, -amp), _state(1, amp)) if move == "pan-left" else (_state(1, amp), _state(1, -amp))
    if move in ("pan-up", "pan-down"):
        amp = 4 + 8 * i                            # at most 12 px: keeps 540 <= 552 and 1400 >= 1368
        return (_state(1, 0, -amp), _state(1, 0, amp)) if move == "pan-up" else (_state(1, 0, amp), _state(1, 0, -amp))
    if move == "ken-burns":
        z = 1.0 + 0.008 + 0.016 * i
        amp = 8 + 16 * i
        return _state(1.0, -amp), _state(z, amp)
    raise CameraError(f"unknown move '{move}'")


# ------------------------------------------------------------------------------------------------ safety
def scene_edges(state):
    """Where the zone edges land after a scene-graphics state (scale around the composition centre)."""
    s, x, y = state["s"], state["x"], state["y"]
    ty = lambda v: CENTER_Y + (v - CENTER_Y) * s + y
    tx = lambda v: CENTER_X + (v - CENTER_X) * s + x
    return {
        "top_zone_top": ty(TOP_ZONE[0]), "top_zone_bottom": ty(TOP_ZONE[1]),
        "bottom_zone_top": ty(BOTTOM_ZONE[0]), "bottom_zone_bottom": ty(BOTTOM_ZONE[1]),
        "left": tx(SIDE_ZONE[0]), "right": tx(SIDE_ZONE[1]),
    }


def check_scene_state(state, where="scene"):
    if state["s"] < 1.0 - 1e-9:
        raise CameraError(f"{where}: scene scale {state['s']} < 1 would move zone edges towards the caption band")
    e = scene_edges(state)
    if e["top_zone_bottom"] > CAPTION_BAND[0] - BAND_MARGIN:
        raise CameraError(f"{where}: top zone would reach y={e['top_zone_bottom']:.1f} (limit {CAPTION_BAND[0] - BAND_MARGIN})")
    if e["bottom_zone_top"] < CAPTION_BAND[1] + BAND_MARGIN:
        raise CameraError(f"{where}: bottom zone would reach y={e['bottom_zone_top']:.1f} (limit {CAPTION_BAND[1] + BAND_MARGIN})")
    if e["top_zone_top"] < 0 or e["bottom_zone_bottom"] > HEIGHT:
        raise CameraError(f"{where}: scene graphics would leave the frame vertically")
    if e["top_zone_top"] < RESERVED["progress bar"][1] + 4 or e["bottom_zone_bottom"] > RESERVED["handle"][0] - 4:
        raise CameraError(f"{where}: scene graphics would cover the progress bar or the handle line")
    if e["left"] < 0 or e["right"] > WIDTH:
        raise CameraError(f"{where}: scene graphics would leave the frame horizontally")


def check_composite(cam_state, frame_name, scene_scale, where="transition"):
    """A scene-level transition (scale around the centre, never below 1) on top of a camera state: frames and zone
    edges must still stay out of the caption band and off the progress bar / handle line."""
    if scene_scale < 1.0:
        raise CameraError(f"{where}: transition scale below 1")
    k = lambda y: CENTER_Y + (y - CENTER_Y) * scene_scale
    if cam_state is not None:
        e = scene_edges(cam_state)
        edges = [k(e["top_zone_top"]), k(e["top_zone_bottom"]), k(e["bottom_zone_top"]), k(e["bottom_zone_bottom"])]
        if edges[1] > CAPTION_BAND[0] - BAND_MARGIN or edges[2] < CAPTION_BAND[1] + BAND_MARGIN:
            raise CameraError(f"{where}: graphics would enter the caption band during the transition")
        if edges[0] < RESERVED["progress bar"][1] or edges[3] > RESERVED["handle"][0]:
            raise CameraError(f"{where}: graphics would cover the progress bar or handle during the transition")
    if frame_name is not None:
        f = FRAMES[frame_name]
        top, bottom = k(f["top"]), k(f["bottom"])
        if f["bottom"] <= CAPTION_BAND[0] and bottom > CAPTION_BAND[0] - BAND_MARGIN:
            raise CameraError(f"{where}: media frame would reach the caption band")
        if top < RESERVED["progress bar"][1] and f["top"] < CAPTION_BAND[0]:
            raise CameraError(f"{where}: media frame would cover the progress bar")
        if bottom > RESERVED["handle"][0]:
            raise CameraError(f"{where}: media frame would cover the handle line")


def check_media_state(state, frame, where="media"):
    fh = frame["bottom"] - frame["top"]
    s = state["s"]
    if s < 1.0 - 1e-9:
        raise CameraError(f"{where}: media scale {s} < 1 would show the empty frame edge")
    if abs(state["x"]) > (s - 1.0) * WIDTH / 2 + 1e-6 or abs(state["y"]) > (s - 1.0) * fh / 2 + 1e-6:
        raise CameraError(f"{where}: media move would reveal the frame edge (coverage)")


def check_frame(frame_name):
    f = FRAMES[frame_name]
    if not (f["bottom"] <= CAPTION_BAND[0] - BAND_MARGIN or f["top"] >= CAPTION_BAND[1] + BAND_MARGIN):
        raise CameraError(f"media frame '{frame_name}' overlaps the caption band")
    for name, (a, b) in RESERVED.items():
        if f["top"] < b and f["bottom"] > a:
            raise CameraError(f"media frame '{frame_name}' would cover the {name}")


# ------------------------------------------------------------------------------------------------ public
def plan_move(move, target, intensity=0.5, speed=1.0, lang="fa", scene_id="", frame="top"):
    """
    Return {"move", "target", "from", "to", "travel"} with both end states already safety-checked.

    intensity 0..1 sets how far the camera travels. speed (0.25-4) sets the velocity: speed > 1 finishes the
    full travel in span/speed seconds and then holds; speed < 1 travels proportionally less over the whole span.
    """
    if move not in MOVES:
        raise CameraError(f"unknown move '{move}'. Available: {', '.join(MOVES)}")
    if target not in TARGETS:
        raise CameraError(f"unknown target '{target}'. Available: {', '.join(TARGETS)}")
    i = float(intensity)
    sp = float(speed)
    if not 0.0 <= i <= 1.0:
        raise CameraError("intensity must be between 0 and 1")
    if not SPEED_LIMITS[0] <= sp <= SPEED_LIMITS[1]:
        raise CameraError(f"speed must be between {SPEED_LIMITS[0]} and {SPEED_LIMITS[1]}")
    eff = i * min(1.0, sp)
    real = resolve_direction(move, lang)
    if target == "media":
        check_frame(frame)
        a, b = _media_states(real, eff, FRAMES[frame], variant_of(scene_id))
        check_media_state(a, FRAMES[frame], f"{scene_id} from")
        check_media_state(b, FRAMES[frame], f"{scene_id} to")
    else:
        a, b = _scene_states(real, eff)
        check_scene_state(a, f"{scene_id} from")
        check_scene_state(b, f"{scene_id} to")
    travel = 1.0 / sp if sp > 1.0 else 1.0        # fraction of the scene span used for the move
    return {"move": move, "resolved": real, "target": target, "from": a, "to": b, "travel": round(travel, 4)}


def plan_transition(kind, lang="fa", duration=None):
    """Incoming/outgoing states for a scene transition. Scale is never below 1 and nothing moves vertically."""
    if kind not in TRANSITIONS:
        raise CameraError(f"unknown transition '{kind}'. Available: {', '.join(TRANSITIONS)}")
    d = TRANSITION_DEFAULT_SEC if duration is None else float(duration)
    if not TRANSITION_LIMITS[0] <= d <= TRANSITION_LIMITS[1]:
        raise CameraError(f"transition duration must be between {TRANSITION_LIMITS[0]} and {TRANSITION_LIMITS[1]} s")
    forward = -1 if lang == "fa" else 1             # RTL: the next scene enters from the left
    if kind == "fade":
        return {"kind": "fade", "duration": d}
    if kind == "slide":
        return {"kind": "slide", "duration": d, "in_from": _state(1, 90 * forward), "out_to": _state(1, -90 * forward)}
    if kind == "zoom-through":
        return {"kind": "zoom-through", "duration": d, "in_from": _state(TRANSITION_MAX_SCALE),
                "out_to": _state(TRANSITION_MAX_SCALE)}
    # wipe: reveal from the reading start side
    start = "inset(0% 0% 0% 100%)" if lang == "fa" else "inset(0% 100% 0% 0%)"
    return {"kind": "wipe", "duration": d, "clip_from": start, "clip_to": "inset(0% 0% 0% 0%)"}
