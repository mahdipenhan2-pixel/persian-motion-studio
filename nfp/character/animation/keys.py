"""
NFP Character Engine - C3b: the KeyList model (pure Python, deterministic).

A KeyList is the whole animation of one or more characters as plain JSON (schema/keylist.v1.json):
    {part, prop, t, val, dur, ease}  + actor, f/df (exact frame numbers), from (value before the key), src (who made it)
Times live on an integer frame grid (default 30 fps): t = f / fps, dur = df / fps. Nothing depends on the clock,
random numbers (only a seeded PRNG) or the network, so the same input always gives byte-identical JSON.

Channel = (actor, part, prop). Rules enforced while planning (Track.add) and re-checked on any KeyList
(validate_keylist):
  * no two keys of one channel overlap in time (a tween [f, f+df) and a set at f' conflict when f <= f' < f+df);
  * discrete props (mouth shape, display, visible) are only set, never tweened;
  * every key ends inside the timeline; eases come from a fixed list implemented identically here and in the runtime;
  * 'from' of a key equals the channel's previous value (continuity), starting from the rig's rest value.
"""
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / "profile_flat_cartoon_v2.json").read_text(encoding="utf-8"))
KEYLIST_SCHEMA = "nfp.anim.keylist/1"
EPS = 1e-9


class PlanError(ValueError):
    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("\n".join(self.problems))


# ------------------------------------------------------------------------------------------------ time grid
def to_frame(t, fps, where="time"):
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
        raise PlanError(f"{where}: '{t}' is not a finite number of seconds")
    return int(math.floor(t * fps + 0.5 + EPS))


def ftime(f, fps):
    return round(f / fps, 6)


def rnd(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        v = round(float(v), 4)
        return 0.0 if v == 0 else v
    return v


# ------------------------------------------------------------------------------------------------ eases
def _back_out(s):
    return lambda p: (p - 1) * (p - 1) * ((s + 1) * (p - 1) + s) + 1


def _back_in(s):
    return lambda p: p * p * ((s + 1) * p - s)


EASES = {
    "none": lambda p: p,
    "sine.in": lambda p: 1 - math.cos(p * math.pi / 2),
    "sine.out": lambda p: math.sin(p * math.pi / 2),
    "sine.inOut": lambda p: -(math.cos(math.pi * p) - 1) / 2,
    "power1.in": lambda p: p * p,
    "power1.out": lambda p: 1 - (1 - p) * (1 - p),
    "power1.inOut": lambda p: 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2,
    "power2.in": lambda p: p ** 3,
    "power2.out": lambda p: 1 - (1 - p) ** 3,
    "power2.inOut": lambda p: 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2,
    "back.out(1.6)": _back_out(1.6),
    "back.in(1.6)": _back_in(1.6),
}
assert sorted(EASES) == sorted(PROFILE["eases"]), "eases out of sync with the profile"


# ------------------------------------------------------------------------------------------------ channels
NUMERIC = set(PROFILE["numeric_props"])
DISCRETE = set(PROFILE["discrete_props"])
RIG_PARTS = set(PROFILE["parts"]) | set(PROFILE["optional_parts"])
PART_PROPS = {"self": {"--x", "--y", "--s", "opacity", "visible"}, "mouth": {"shape"},
              "tears": {"display"}, "sweat": {"display"}, "blush": {"opacity"}}


def allowed_props(part):
    if part in PART_PROPS:
        return PART_PROPS[part]
    if part in RIG_PARTS:
        return {"--x", "--y", "--r", "--s", "--sx", "--sy"}
    return set()


def rest_value(part, prop):
    return PROFILE["rest_overrides"].get(f"{part}.{prop}", PROFILE["rest"][prop])


def _conflict(a, b):
    """a, b = (f, df). Sets are points, tweens are half-open intervals."""
    (f1, d1), (f2, d2) = a, b
    if d1 == 0 and d2 == 0:
        return f1 == f2
    if d1 == 0:
        return f2 <= f1 < f2 + d2
    if d2 == 0:
        return f1 <= f2 < f1 + d1
    return f1 < f2 + d2 and f2 < f1 + d1


class Track:
    """The planning ledger: every key of every channel, checked as it is added."""

    def __init__(self, fps, frames):
        self.fps, self.frames = fps, frames
        self.ch = {}

    def add(self, actor, part, prop, f, val, df=0, ease="none", src=""):
        where = f"{src or 'key'} @frame {f}: {actor}.{part}.{prop}"
        if prop not in allowed_props(part):
            raise PlanError(f"{where}: '{prop}' cannot be animated on part '{part}'")
        if not isinstance(f, int) or not isinstance(df, int) or f < 0 or df < 0:
            raise PlanError(f"{where}: frames must be non-negative integers (f={f}, df={df})")
        if f + df > self.frames:
            raise PlanError(f"{where}: ends at frame {f + df}, after the timeline ({self.frames} frames)")
        if ease not in EASES:
            raise PlanError(f"{where}: unknown ease '{ease}'")
        if prop in DISCRETE and df != 0:
            raise PlanError(f"{where}: '{prop}' is discrete and can only be set (dur 0)")
        if prop in NUMERIC and (isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val)):
            raise PlanError(f"{where}: value '{val}' is not a finite number")
        lst = self.ch.setdefault((actor, part, prop), [])
        for k in lst:
            if _conflict((f, df), (k["f"], k["df"])):
                raise PlanError(f"{where}: overlaps '{k['src']}' (frames {k['f']}..{k['f'] + k['df']}) on the same "
                                f"channel - two motions cannot drive one property at once")
        lst.append({"actor": actor, "part": part, "prop": prop, "f": f, "df": df, "val": rnd(val), "ease": ease,
                    "src": src})
        return f + df

    def free(self, actor, part, prop, f, df):
        return not any(_conflict((f, df), (k["f"], k["df"])) for k in self.ch.get((actor, part, prop), []))

    def value_at(self, actor, part, prop, f):
        """Settled value of a channel at frame f (used to chain motions, e.g. where a walk starts)."""
        cur = rest_value(part, prop)
        for k in sorted(self.ch.get((actor, part, prop), []), key=lambda k: k["f"]):
            if k["f"] > f:
                break
            if k["f"] + k["df"] > f:
                raise PlanError(f"{actor}.{part}.{prop} is still moving at frame {f} ('{k['src']}')")
            cur = k["val"]
        return cur

    def finalize(self):
        keys = []
        for (actor, part, prop), lst in self.ch.items():
            prev = rnd(rest_value(part, prop))
            for k in sorted(lst, key=lambda k: k["f"]):
                k = dict(k)
                k["from"] = prev
                k["t"], k["dur"] = ftime(k["f"], self.fps), ftime(k["df"], self.fps)
                prev = k["val"]
                keys.append(k)
        keys.sort(key=lambda k: (k["f"], k["actor"], k["part"], k["prop"]))
        return keys


# ------------------------------------------------------------------------------------------------ sampling
def channels(keys):
    out = {}
    for k in keys:
        out.setdefault((k["actor"], k["part"], k["prop"]), []).append(k)
    for v in out.values():
        v.sort(key=lambda k: k["f"])
    return out


def sample_channel(lst, part, prop, fr):
    """Value at (fractional) frame fr - the same rule as runtime/character_runtime.js seek()."""
    cur = lst[0]["from"] if lst else rest_value(part, prop)
    for k in lst:
        if k["f"] > fr + EPS:
            break
        if k["df"] == 0 or fr >= k["f"] + k["df"] - EPS:
            cur = k["val"]
        else:
            p = (fr - k["f"]) / k["df"]
            cur = k["from"] + (k["val"] - k["from"]) * EASES[k["ease"]](p)
    return cur


def sample(keylist, fr):
    """{actor: {part: {prop: value}}} for every keyed channel at frame fr."""
    out = {}
    for (a, part, prop), lst in channels(keylist["keys"]).items():
        out.setdefault(a, {}).setdefault(part, {})[prop] = sample_channel(lst, part, prop, fr)
    return out


# ------------------------------------------------------------------------------------------------ canonical form
def _norm(o):
    """Canonical numbers: an integral float is written as an integer (4.0 -> 4), exactly as JavaScript writes it,
    so the runtime can recompute the same digest (runtime/character_runtime.js digestOf)."""
    if isinstance(o, float) and not isinstance(o, bool) and math.isfinite(o) and o.is_integer():
        return int(o)
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm(v) for v in o]
    return o


def canonical(obj):
    return json.dumps(_norm(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def dumps(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1) + "\n"


# ------------------------------------------------------------------------------------------------ validation
KEY_FIELDS = {"actor", "part", "prop", "t", "f", "val", "from", "dur", "df", "ease", "src"}
FPS = 30                                    # the only frame rate C3 supports (see README_C3.md)
ACTOR_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
DOM_ID = re.compile(r"^nfp-c-[a-z0-9-]{1,200}$")
FP_RE = re.compile(r"^[0-9a-f]{64}$")
POS_LIMIT, SCALE_MAX = 100000, 20


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def spec_fingerprint(spec, style="flat_cartoon_v2"):
    """The C1 identity fingerprint recomputed from a rig spec, with C1's own fingerprint(). Exact for the current
    catalogue, where face is always 'default' and 'glasses' is the only mark (the rig spec carries no face field)."""
    from ..registry import fingerprint
    return fingerprint({"style": style, "identity": {"skin": spec["skin"], "hair_color": spec["hairColor"],
                                                      "eye_color": spec["eyeColor"],
                                                      "marks": ["glasses"] if spec["glasses"] == 1 else []}})


def validate_actor(a, where):
    """Everything about a placed character that ends up in the DOM: id, DOM id, position, scale, full rig spec,
    and that the fingerprint really belongs to the spec's identity."""
    from ..adapter.flat_cartoon_v2 import AdapterError, validate_rig_spec
    P = []
    if not isinstance(a, dict):
        return [f"{where}: must be an object"]
    if not (isinstance(a.get("id"), str) and ACTOR_ID.match(a["id"])):
        P.append(f"{where}: id must match {ACTOR_ID.pattern}")
    if not (isinstance(a.get("dom_id"), str) and DOM_ID.match(a["dom_id"])):
        P.append(f"{where}: dom_id must match {DOM_ID.pattern}")
    for k in ("x", "y"):
        if not (_finite(a.get(k)) and abs(a[k]) <= POS_LIMIT):
            P.append(f"{where}: {k} must be a finite number within +-{POS_LIMIT}")
    if not (_finite(a.get("scale")) and 0 < a["scale"] <= SCALE_MAX):
        P.append(f"{where}: scale must be a number in (0, {SCALE_MAX}]")
    try:
        validate_rig_spec(a.get("spec"), f"{where}.spec")
    except AdapterError as e:
        return P + e.problems
    if not (isinstance(a.get("fingerprint"), str) and FP_RE.match(a["fingerprint"])):
        P.append(f"{where}: fingerprint must be 64 lower-case hex characters")
    elif a["fingerprint"] != spec_fingerprint(a["spec"]):
        P.append(f"{where}: fingerprint does not belong to this spec's identity (skin/hair/eyes/glasses) - forged or stale")
    return P


def validate_keylist(kl):
    """Independent check of any KeyList (also one not made by this planner). Returns a list of problems."""
    P = []
    if not isinstance(kl, dict) or kl.get("schema") != KEYLIST_SCHEMA:
        return [f"schema must be '{KEYLIST_SCHEMA}'"]
    fps, frames = kl.get("fps"), kl.get("frames")
    if fps != FPS:
        return [f"fps must be {FPS}: C3 is only built and tested for {FPS} fps"]
    if not isinstance(frames, int) or isinstance(frames, bool) or frames <= 0:
        return ["frames must be a positive integer"]
    if not isinstance(kl.get("digest"), str):
        P.append("digest missing")
    else:
        try:
            if kl["digest"] != digest({k: v for k, v in kl.items() if k != "digest"}):
                P.append("digest does not match the content (the KeyList was edited after planning)")
        except (ValueError, TypeError) as e:
            P.append(f"content is not canonical JSON ({e})")
    if not isinstance(kl.get("actors"), list) or not kl["actors"] or not isinstance(kl.get("keys"), list):
        return P + ["actors (non-empty list) and keys (list) are required"]
    actors = {}
    for i, a in enumerate(kl["actors"]):
        ap = validate_actor(a, f"actors[{i}]")
        P.extend(ap)
        if not ap:
            if a["id"] in actors or a["dom_id"] in {x["dom_id"] for x in actors.values()}:
                P.append(f"actors[{i}]: duplicate id or dom_id")
            actors[a["id"]] = a
    if len(actors) != len(kl["actors"]):
        return P
    long_hair = set(PROFILE["long_hair"])
    prev_sort = None
    for i, k in enumerate(kl.get("keys", [])):
        w = f"key {i}"
        if not isinstance(k, dict) or set(k) != KEY_FIELDS:
            P.append(f"{w}: fields wrong")
            continue
        if k["actor"] not in actors:
            P.append(f"{w}: unknown actor '{k['actor']}'")
            continue
        if not isinstance(k["part"], str) or not isinstance(k["prop"], str) or k["prop"] not in allowed_props(k["part"]):
            P.append(f"{w}: '{k['prop']}' not allowed on part '{k['part']}'")
            continue
        if k["part"] == "hairBack" and actors[k["actor"]]["spec"]["hair"] not in long_hair:
            P.append(f"{w}: hairBack keyed but '{k['actor']}' has no long hair")
        if not (isinstance(k["f"], int) and isinstance(k["df"], int) and not isinstance(k["f"], bool)
                and k["f"] >= 0 and k["df"] >= 0):
            P.append(f"{w}: f/df must be non-negative integers")
            continue
        if k["t"] != ftime(k["f"], fps) or k["dur"] != ftime(k["df"], fps):
            P.append(f"{w}: t/dur not on the {fps} fps frame grid")
        if k["f"] + k["df"] > frames:
            P.append(f"{w}: ends after the timeline")
        if k["ease"] not in EASES:
            P.append(f"{w}: unknown ease '{k['ease']}'")
        if k["prop"] in DISCRETE and k["df"] != 0:
            P.append(f"{w}: discrete prop tweened")
        for fld in ("val", "from"):
            v = k[fld]
            if k["prop"] in NUMERIC and not _finite(v):
                P.append(f"{w}: {fld} must be a finite number")
            elif k["prop"] == "shape" and v not in PROFILE["mouths"]:
                P.append(f"{w}: unknown mouth '{v}'")
            elif k["prop"] in ("display", "visible") and v not in (0, 1):
                P.append(f"{w}: {fld} must be 0 or 1")
        if not isinstance(k["src"], str):
            P.append(f"{w}: src must be a string")
        s = (k["f"], k["actor"], k["part"], k["prop"])
        if prev_sort is not None and s < prev_sort:
            P.append(f"{w}: keys not sorted by (f, actor, part, prop)")
        prev_sort = s
    good = [k for k in kl.get("keys", []) if isinstance(k, dict) and set(k) == KEY_FIELDS and k["actor"] in actors
            and isinstance(k["f"], int) and isinstance(k["df"], int)]
    for (a, part, prop), lst in channels(good).items():
        prev = rnd(rest_value(part, prop)) if prop in allowed_props(part) else None
        for j, k in enumerate(lst):
            if k["from"] != prev:
                P.append(f"{a}.{part}.{prop} @frame {k['f']}: from {k['from']} != previous value {prev} (discontinuity)")
            if j and _conflict((k["f"], k["df"]), (lst[j - 1]["f"], lst[j - 1]["df"])):
                P.append(f"{a}.{part}.{prop} @frame {k['f']}: overlaps the previous key")
            prev = k["val"]
    return P


def visible_at(chs, actor, fr):
    lst = chs.get((actor, "self", "visible"), [])
    return sample_channel(lst, "self", "visible", fr) if lst else 1


def jumps(kl):
    """Instant changes of a continuous value while the character is visible (frame > 0). Should be empty."""
    chs = channels(kl["keys"])
    out = []
    for (a, part, prop), lst in chs.items():
        if prop not in NUMERIC:
            continue
        for k in lst:
            if k["df"] == 0 and k["f"] > 0 and k["val"] != k["from"] and visible_at(chs, a, k["f"] - 1):
                out.append(f"{a}.{part}.{prop} jumps {k['from']} -> {k['val']} at frame {k['f']} ({k['src']})")
    return out
