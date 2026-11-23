"""
NFP Character Engine - C3b: motion presets for the flat_cartoon_v2 rig (pure Python, deterministic).

Every preset writes keys into a Track for one actor, on the frame grid, using only parts and properties that the
real rig has (animation/profile_flat_cartoon_v2.json). The motions are re-implemented from the behaviour of the
docu Director (walk, blink, breathe, look, turn, nod, arm, lean, hop, shiver, face) - no Director code is loaded.

Honest limits (also in the profile under "unsupported"):
  * sit/stand is an APPROXIMATION: the rig has no hip pivot and is drawn front-on, so the thighs swing toward the
    facing side and the body is lowered so the feet stay on the ground. A seat must be drawn by the scene.
  * wave/point move the whole arm and forearm; there are no fingers or hand shapes.
  * turn only tilts/shifts the head in 2D.
"""
import math

from .keys import PROFILE, PlanError, rnd, to_frame


class Actor:
    """Planning context of one placed character."""

    def __init__(self, aid, adapted, x, y, scale, seed, fps):
        self.id, self.a, self.fps = aid, adapted, fps
        self.spec = adapted["spec"]
        self.build = self.spec["build"]
        self.geom = PROFILE["geometry"][self.build]
        self.face = PROFILE["face"][self.build]
        self.long_hair = self.spec["hair"] in PROFILE["long_hair"]
        self.x, self.y, self.scale, self.seed = x, y, scale, seed
        self.expr = adapted["expr"]
        self.seated = False
        self.last_x = None         # stage offset where the character stood when it last exited
        self.visible = True
        self.windows = []          # [(f_on, f_off)] visible intervals, closed at the end
        self.on_since = 0
        self.rest_events = []      # (f, mouth) from expression changes
        self.speech = []           # lip-sync segments
        self.notes = []

    def fr(self, seconds, where):
        return to_frame(seconds, self.fps, where)


def _k(T, A, part, prop, f, val, df=0, ease="none", src=""):
    return T.add(A.id, part, prop, f, val, df, ease, src)


def _need(A, f, src, standing=False):
    if not A.visible:
        raise PlanError(f"{src} @frame {f}: '{A.id}' is not on stage (enter first)")
    if standing and A.seated:
        raise PlanError(f"{src} @frame {f}: '{A.id}' is seated (stand first)")


def _min(df, n, src):
    if df < n:
        raise PlanError(f"{src}: needs at least {n} frames, got {df}")


# ------------------------------------------------------------------------------------------------ setup
def base_pose(T, A):
    for k in PROFILE["base_pose"]:
        _k(T, A, k["part"], k["prop"], 0, k["val"], 0, "none", "base_pose")
    if A.expr != "neutral":
        expression(T, A, 0, 0, A.expr, src="initial_expr")
    else:
        A.rest_events.append((0, "neutral"))


def hide_initially(T, A):
    _k(T, A, "self", "visible", 0, 0, 0, "none", "hidden_until_enter")
    A.visible, A.windows = False, []


# ------------------------------------------------------------------------------------------------ face
def expression(T, A, f, df, name, src="expr"):
    e = PROFILE["expressions"].get(name)
    if e is None:
        raise PlanError(f"{src}: unknown expression '{name}' ({', '.join(PROFILE['expressions'])})")
    ease = "power1.inOut" if df else "none"
    for side, sgn in (("L", -1), ("R", 1)):
        _k(T, A, "brow" + side, "--y", f, e["by"], df, ease, src)
        _k(T, A, "brow" + side, "--r", f, sgn * e["br"], df, ease, src)
        _k(T, A, "eye" + side, "--sy", f, e["ey"], df, ease, src)
    _k(T, A, "blush", "opacity", f, e["blush"], df, ease, src)
    for x in ("tears", "sweat"):
        want = 1 if e.get(x) else 0
        if T.value_at(A.id, x, "display", f) != want:
            _k(T, A, x, "display", f, want, 0, "none", src)
    A.expr = name
    A.rest_events.append((f, e["mouth"]))
    return f + df


def blink(T, A, f, src="blink"):
    travel = 2 * A.face["ey"] + 2
    for s in ("L", "R"):
        _k(T, A, "lid" + s, "--y", f, travel, 2, "power1.in", src)
        _k(T, A, "lid" + s, "--y", f + 2, 0, 3, "power1.out", src)
    return f + 5


def look(T, A, f, df, dir=None, dx=None, dy=None, src="look"):
    lim = A.face["ex"] - A.face["ir"]
    if dir is not None:
        table = {"left": (-lim, 0), "right": (lim, 0), "up": (0, -0.6 * lim), "down": (0, 0.6 * lim), "center": (0, 0)}
        if dir not in table:
            raise PlanError(f"{src}: dir must be one of {', '.join(table)}")
        dx, dy = table[dir]
    dx, dy = dx or 0, dy or 0
    if abs(dx) > lim + 1e-9 or abs(dy) > lim + 1e-9:
        raise PlanError(f"{src}: iris offset ({dx}, {dy}) leaves the eye (limit {lim} for build '{A.build}')")
    ease = "power2.inOut" if df else "none"
    for s in ("L", "R"):
        _k(T, A, "iris" + s, "--x", f, dx, df, ease, src)
        _k(T, A, "iris" + s, "--y", f, 2 + dy, df, ease, src)
    return f + df


def turn(T, A, f, df, deg, dx=0, src="turn"):
    if abs(deg) > 25:
        raise PlanError(f"{src}: head tilt {deg} deg is beyond the 2D rig's range (|deg| <= 25)")
    _k(T, A, "head", "--r", f, deg, df, "power2.inOut", src)
    _k(T, A, "head", "--x", f, dx, df, "power2.inOut", src)
    return f + df


def nod(T, A, f, df, amp=8, src="nod"):
    _min(df, 4, src)
    h = df // 2
    _k(T, A, "head", "--y", f, amp, h, "power2.out", src)
    _k(T, A, "head", "--y", f + h, 0, df - h, "power2.inOut", src)
    return f + df


# ------------------------------------------------------------------------------------------------ body
REST_ARM = {"L": (4, 4), "R": (-4, -4)}


def arm(T, A, f, df, side, r, fore=None, ease="power2.inOut", src="arm"):
    sides = ("L", "R") if side == "both" else (side,)
    for s in sides:
        if s not in ("L", "R"):
            raise PlanError(f"{src}: side must be L, R or both")
        rr = r if side != "both" or s == "L" else -r
        _k(T, A, "arm" + s, "--r", f, rr, df, ease, src)
        if fore is not None:
            ff = fore if side != "both" or s == "L" else -fore
            _k(T, A, "fore" + s, "--r", f, ff, df, ease, src)
    return f + df


def arms_rest(T, A, f, df, sides=("L", "R"), src="arms_rest"):
    for s in sides:
        _k(T, A, "arm" + s, "--r", f, REST_ARM[s][0], df, "power2.inOut", src)
        _k(T, A, "fore" + s, "--r", f, REST_ARM[s][1], df, "power2.inOut", src)
    return f + df


def wave(T, A, f, df, side="R", src="wave"):
    """Raise one arm, swing the forearm back and forth, lower it again (whole-arm gesture, no hand shape)."""
    _min(df, 36, src)
    sg = -1 if side == "R" else 1
    up, down = 12, 12
    _k(T, A, "arm" + side, "--r", f, sg * 150, up, "sine.inOut", src)
    _k(T, A, "fore" + side, "--r", f, sg * 20, up, "sine.inOut", src)
    t, i, end = f + up, 0, f + df - down
    while t + 6 <= end:
        _k(T, A, "fore" + side, "--r", t, sg * (-25 if i % 2 == 0 else 25), 6, "sine.inOut", src)
        t, i = t + 6, i + 1
    _k(T, A, "arm" + side, "--r", end, REST_ARM[side][0], f + df - end, "sine.inOut", src)
    _k(T, A, "fore" + side, "--r", t, REST_ARM[side][1], f + df - t, "sine.inOut", src)
    return f + df


def point(T, A, f, df, side="R", hold=1.0, src="point"):
    """Arm stretched sideways (an arm direction, not a finger)."""
    _min(df, 8, src)
    sg = -1 if side == "R" else 1
    h = int(round(hold * A.fps))
    _k(T, A, "arm" + side, "--r", f, sg * 80, df, "power2.out", src)
    _k(T, A, "fore" + side, "--r", f, sg * 10, df, "power2.out", src)
    if h > 0:
        arms_rest(T, A, f + df + h, 8, (side,), src)
        return f + df + h + 8
    return f + df


def lean(T, A, f, df, deg, src="lean"):
    if abs(deg) > 20:
        raise PlanError(f"{src}: lean {deg} deg too far for the rig (|deg| <= 20)")
    _k(T, A, "torso", "--r", f, deg, df, "power2.inOut", src)
    return f + df


def hop(T, A, f, df, h=40, src="hop"):
    _min(df, 6, src)
    a = df // 2
    _k(T, A, "root", "--y", f, -h, a, "power2.out", src)
    _k(T, A, "root", "--y", f + a, 0, df - a, "power2.in", src)
    return f + df


def shiver(T, A, f, df, amp=3, src="shiver"):
    _min(df, 4, src)
    t, i = f, 0
    while t + 2 <= f + df - 2:
        _k(T, A, "root", "--x", t, amp if i % 2 else -amp, 2, "none", src)
        t, i = t + 2, i + 1
    _k(T, A, "root", "--x", t, 0, f + df - t, "none", src)
    return f + df


def move(T, A, f, df, dx=0, dy=0, src="move"):
    """Slide on stage without stepping (e.g. carried by a vehicle). Relative to the current position."""
    x0 = T.value_at(A.id, "self", "--x", f)
    y0 = T.value_at(A.id, "self", "--y", f)
    ease = "power2.inOut" if df else "none"
    if df == 0 and A.visible:
        raise PlanError(f"{src}: an instant move while visible is a position jump (give it a duration)")
    _k(T, A, "self", "--x", f, x0 + dx, df, ease, src)
    if dy:
        _k(T, A, "self", "--y", f, y0 + dy, df, ease, src)
    return f + df


# ------------------------------------------------------------------------------------------------ locomotion
GAITS = {
    "walk": {"step": 0.3, "amp": 20, "knee": 1.3, "lift": -12, "bob": -10, "arm": 1.1, "fore": (8, 26), "lean": 0,
             "sway": 2.6},
    "run": {"step": 0.2, "amp": 30, "knee": 1.6, "lift": -18, "bob": -16, "arm": 1.3, "fore": (60, 80), "lean": 6,
            "sway": 2.0},
}


def locomote(T, A, f, df, dx, gait="walk", step=None, amp=None, arms=True, src=None):
    """Opposite leg/arm swing, knee flex and foot lift on the swing leg, body bob, torso sway, head counter-tilt, hair
    lag. The stage position moves linearly by exactly dx. Legs and hips return to rest; torso lean, head tilt and the
    arm pose return to what they were BEFORE the walk (a lean or raised arm is resumed, not reset). No drift."""
    src = src or gait
    _need(A, f, src, standing=True)
    G = dict(GAITS[gait])
    step = step or G["step"]
    amp = amp if amp is not None else G["amp"]
    sf = max(4, int(round(step * A.fps)))
    n = max(1, int(round(df / sf)))
    bounds = [f + int(round(i * df / n)) for i in range(n + 1)]
    if min(b - a for a, b in zip(bounds, bounds[1:])) < 4:
        raise PlanError(f"{src}: {df} frames is too short for a {gait} (at least 4 frames per step)")
    d = 1 if dx >= 0 else -1
    fs = -d                                   # hip rotation sign for "forward"
    stride = abs(dx) / n                      # stage px covered per step
    natural = 2 * A.geom["legH"] * math.sin(math.radians(amp)) * A.scale
    if stride > 1.6 * natural:
        A.notes.append({"foot_slide_risk": {"action": src, "stride_px": rnd(stride), "natural_stride_px": rnd(natural),
                                            "note": "the body travels much further per step than the legs swing: feet "
                                                    "will appear to slide. Use more time, a smaller dx or 'run'."}})
    x0 = T.value_at(A.id, "self", "--x", f)
    torso0, head0 = T.value_at(A.id, "torso", "--r", f), T.value_at(A.id, "head", "--r", f)
    arms0 = {p: T.value_at(A.id, p, "--r", f) for p in ("armL", "armR", "foreL", "foreR")} if arms else {}
    _k(T, A, "self", "--x", f, x0 + dx, df, "none", src)
    s = 1
    for a, b in zip(bounds, bounds[1:]):
        dd = b - a
        h = dd // 2
        for side, fwd in (("L", s > 0), ("R", s < 0)):
            th, sh, so = "leg" + side, "shin" + side, "shoe" + side
            if fwd:
                _k(T, A, th, "--r", a, fs * amp, dd, "sine.inOut", src)
                _k(T, A, sh, "--r", a, -fs * amp * G["knee"], h, "sine.out", src)
                _k(T, A, sh, "--r", a + h, 0, dd - h, "sine.in", src)
                _k(T, A, so, "--r", a, -fs * 10, h, "sine.out", src)
                _k(T, A, so, "--r", a + h, 0, dd - h, "sine.in", src)
                _k(T, A, th, "--y", a, G["lift"], h, "sine.out", src)
                _k(T, A, th, "--y", a + h, 0, dd - h, "sine.in", src)
            else:
                _k(T, A, th, "--r", a, -fs * amp * 0.8, dd, "sine.inOut", src)
                _k(T, A, sh, "--r", a, 0, dd, "none", src)
                _k(T, A, th, "--y", a, 0, dd, "none", src)
                _k(T, A, so, "--r", a, fs * 8, dd, "sine.inOut", src)
        if arms:
            fo = G["fore"]
            _k(T, A, "armL", "--r", a, 4 - s * fs * amp * G["arm"], dd, "sine.inOut", src)
            _k(T, A, "armR", "--r", a, -4 + s * fs * amp * G["arm"], dd, "sine.inOut", src)
            _k(T, A, "foreL", "--r", a, fo[0] if s > 0 else fo[1], dd, "sine.inOut", src)
            _k(T, A, "foreR", "--r", a, -fo[1] if s > 0 else -fo[0], dd, "sine.inOut", src)
        _k(T, A, "root", "--y", a, G["bob"], h, "sine.out", src)
        _k(T, A, "root", "--y", a + h, 0, dd - h, "sine.in", src)
        _k(T, A, "torso", "--r", a, torso0 + d * G["lean"] + s * G["sway"], dd, "sine.inOut", src)
        _k(T, A, "head", "--r", a, head0 - s * 1.6, dd, "sine.inOut", src)
        if A.long_hair:
            _k(T, A, "hairBack", "--r", a + 1, -s * 4, dd, "sine.inOut", src)
        s = -s
    e = f + df
    back = 6
    need = back + (10 if A.long_hair else 0)     # long hair settles one frame later over 9 frames
    if e + need > T.frames:
        raise PlanError(f"{src}: needs {need} frames after the last step to settle; the timeline ends first")
    for nme in ("legL", "legR", "shinL", "shinR", "shoeL", "shoeR"):
        _k(T, A, nme, "--r", e, 0, back, "power1.inOut", src + ":settle")
    _k(T, A, "legL", "--y", e, 0, back, "power1.inOut", src + ":settle")
    _k(T, A, "legR", "--y", e, 0, back, "power1.inOut", src + ":settle")
    for p, v in arms0.items():
        _k(T, A, p, "--r", e, v, back, "power2.inOut", src + ":settle")
    _k(T, A, "torso", "--r", e, torso0, back, "power1.inOut", src + ":settle")
    _k(T, A, "head", "--r", e, head0, back, "power1.inOut", src + ":settle")
    if A.long_hair:
        _k(T, A, "hairBack", "--r", e + 1, 0, 9, "power1.inOut", src + ":settle")
    return e + back


# ------------------------------------------------------------------------------------------------ sit / stand (approximation)
def sit(T, A, f, df, facing="right", angle=80, src="sit"):
    _need(A, f, src, standing=True)
    _min(df, 8, src)
    if facing not in ("left", "right"):
        raise PlanError(f"{src}: facing must be left or right")
    fs = -1 if facing == "right" else 1
    L1 = int(round(A.geom["legH"] * 0.5))
    drop = L1 * (1 - math.cos(math.radians(angle)))
    ease = "power2.inOut"
    for s in ("L", "R"):
        _k(T, A, "leg" + s, "--r", f, fs * angle, df, ease, src)
        _k(T, A, "shin" + s, "--r", f, -fs * angle, df, ease, src)
    _k(T, A, "root", "--y", f, drop, df, ease, src)
    _k(T, A, "torso", "--r", f, fs * 4, df, ease, src)
    for s in ("L", "R"):
        _k(T, A, "arm" + s, "--r", f, fs * 25, df, ease, src)
        _k(T, A, "fore" + s, "--r", f, fs * 35, df, ease, src)
    A.seated = True
    seat_y = A.y + (-A.geom["legH"] + drop) * A.scale          # the hip line, where the thighs rest
    A.notes.append({"sit_approximation": {"frame": f, "facing": facing, "thigh_angle": angle,
                                          "body_lowered_by": rnd(drop),
                                          "seat_top_stage_y": rnd(seat_y),
                                          "note": "approximate profile-style sit on a front-view rig (no hip pivot); "
                                                  "the scene must draw the seat"}})
    return f + df


def stand(T, A, f, df, src="stand"):
    if not A.seated:
        raise PlanError(f"{src} @frame {f}: '{A.id}' is not seated")
    _min(df, 8, src)
    ease = "power2.inOut"
    for s in ("L", "R"):
        _k(T, A, "leg" + s, "--r", f, 0, df, ease, src)
        _k(T, A, "shin" + s, "--r", f, 0, df, ease, src)
    _k(T, A, "root", "--y", f, 0, df, ease, src)
    _k(T, A, "torso", "--r", f, 0, df, ease, src)
    arms_rest(T, A, f, df, src=src)
    A.seated = False
    return f + df


# ------------------------------------------------------------------------------------------------ entrance / exit
def enter(T, A, f, df, style="pop", from_dx=-700, gait="walk", src="enter"):
    if A.visible:
        raise PlanError(f"{src} @frame {f}: '{A.id}' is already on stage")
    if f < 1:
        raise PlanError(f"{src}: an entrance needs at least one hidden frame before it (t >= 1 frame)")
    prep = f - 1                              # set up while still hidden: no visible jump
    if style == "pop":
        _min(df, 4, src)
        if T.value_at(A.id, "self", "--s", prep) != 0:
            _k(T, A, "self", "--s", prep, 0, 0, "none", src + ":prep")
        _k(T, A, "self", "visible", f, 1, 0, "none", src)
        _k(T, A, "self", "--s", f, 1, df, "back.out(1.6)", src)
        end = f + df
    elif style == "fade":
        _min(df, 4, src)
        if T.value_at(A.id, "self", "opacity", prep) != 0:
            _k(T, A, "self", "opacity", prep, 0, 0, "none", src + ":prep")
        _k(T, A, "self", "visible", f, 1, 0, "none", src)
        _k(T, A, "self", "opacity", f, 1, df, "power1.inOut", src)
        end = f + df
    elif style == "walk":
        # arrive where the character last stood on stage (0 = its placement x before any exit)
        x_home = A.last_x if A.last_x is not None else T.value_at(A.id, "self", "--x", prep)
        _k(T, A, "self", "--x", prep, x_home + from_dx, 0, "none", src + ":prep")
        _k(T, A, "self", "visible", f, 1, 0, "none", src)
        A.visible = True
        end = locomote(T, A, f, df, -from_dx, gait=gait, src=src + ":" + gait)
    else:
        raise PlanError(f"{src}: style must be pop, fade or walk")
    A.visible, A.on_since = True, f
    return end


def exit_(T, A, f, df, style="pop", dx=700, gait="walk", src="exit"):
    _need(A, f, src)
    A.last_x = T.value_at(A.id, "self", "--x", f)
    if style == "pop":
        _min(df, 4, src)
        _k(T, A, "self", "--s", f, 0, df, "back.in(1.6)", src)
        off = f + df
    elif style == "fade":
        _min(df, 4, src)
        _k(T, A, "self", "opacity", f, 0, df, "power1.inOut", src)
        off = f + df
    elif style == "walk":
        locomote(T, A, f, df, dx, gait=gait, src=src + ":" + gait)
        off = f + df
    else:
        raise PlanError(f"{src}: style must be pop, fade or walk")
    _k(T, A, "self", "visible", off, 0, 0, "none", src)
    A.windows.append((A.on_since, off))
    A.visible = False
    return off


# ------------------------------------------------------------------------------------------------ idle (filled in last)
def mulberry32(seed):
    """Same PRNG as rig/00_core.js K.rng: deterministic, seedable."""
    s = seed & 0xFFFFFFFF

    def r():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = s
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return r


def _imul(a, b):
    return (a * b) & 0xFFFFFFFF


def breathe(T, A, a, b, amp=0.022, src="breathe"):
    """Torso --sy cycles of 1.2 s, always ending back at rest (an even number of half cycles)."""
    cyc = int(round(1.2 * A.fps))
    n = (b - a) // cyc
    n -= n % 2
    t, up, made = a, True, 0
    for _ in range(n):
        if not T.free(A.id, "torso", "--sy", t, cyc):
            break
        _k(T, A, "torso", "--sy", t, 1 + amp if up else 1, cyc, "sine.inOut", src)
        t, up, made = t + cyc, not up, made + 1
    if made % 2:                                   # stopped early on a busy channel: close the cycle if possible
        if T.free(A.id, "torso", "--sy", t, cyc) and t + cyc <= b:
            _k(T, A, "torso", "--sy", t, 1, cyc, "sine.inOut", src)
        else:
            raise PlanError(f"{src}: could not return the breath to rest before frame {b}")
    return made


def auto_blink(T, A, a, b, src="idle_blink"):
    r = mulberry32(A.seed)
    t = a / A.fps + 0.6 + r() * 1.6
    made = 0
    while t < b / A.fps - 0.3:
        f = to_frame(t, A.fps)
        if f + 5 <= b and all(T.free(A.id, "lid" + s, "--y", f, 5) for s in ("L", "R")):
            blink(T, A, f, src)
            made += 1
        t += 2.4 + r() * 2.2
    return made
