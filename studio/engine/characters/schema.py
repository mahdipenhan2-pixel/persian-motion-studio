"""
NFP Studio - Character layer (C4): validation of the OPTIONAL character fields in project.json + slot placement.

  meta.cast            {dir, actors: {<actor id>: {character, stage, wardrobe, x, framing, detail}}}
  scene.characters     {slot, actors: [<actor id> | {actor, expr}], speaker, sentence_speakers, actions}

The unchanged studio/engine/project.py ignores these keys, so run.py / run_motion.py still build such a project,
only without characters. A project without them is never touched by this package.

Rules (studio/engine/characters/zones.json, measured from the real page):
  * 9:16 only (Studio has no 16:9 yet). The only character area is the bottom slot x 70-1010, y 1372-1650: every
    template fills the top zone, the caption band y 560-1360 belongs to the locked Stage 2 verify, the handle starts
    at y 1660. 'top' is reserved and refused.
  * the bottom slot is refused in a scene that uses it: template cta with note/handle, or a camera media frame
    'bottom'.
  * framing 'bust' (default): the hips sit on the slot's lower edge, legs are cut by the slot; 'full' only when the
    whole body fits and the face is still >= min_face_px tall.
  * the speaker of every sentence is 'narrator' (off screen: no mouth motion) unless the scene names an actor that is
    present in that scene.
Everything raises CastError with a clear message; nothing is silently adjusted.
"""
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
ZONES = json.loads((HERE / "zones.json").read_text(encoding="utf-8"))
ACTOR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
CAST_KEYS = {"dir", "actors"}
ACTOR_KEYS = {"character", "stage", "wardrobe", "x", "framing", "detail"}
SCENE_KEYS = {"slot", "actors", "speaker", "sentence_speakers", "actions"}
SCENE_ACTOR_KEYS = {"actor", "expr"}
# C3 actions a presenter may do inside the slot (no walking / running / sitting: the slot is a fixed strip)
SCENE_ACTIONS = {"look", "nod", "turn", "lean", "wave", "point", "expr", "blink", "arm", "arms_rest", "hop"}
NARRATOR = "narrator"


class CastError(ValueError):
    pass


def _obj(v, where):
    if not isinstance(v, dict):
        raise CastError(f"{where} must be an object")
    return v


def _unknown(d, allowed, where):
    extra = sorted(set(d) - set(allowed))
    if extra:
        raise CastError(f"{where}: unknown field(s) {', '.join(extra)}. Allowed: {', '.join(sorted(allowed))}")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def uses_characters(proj):
    """True when the project asks for characters at all (otherwise this package does nothing)."""
    return "cast" in proj.get("meta", {}) or any("characters" in s for s in proj.get("scenes", []))


def slot_geometry(fmt="9:16", slot="bottom"):
    f = ZONES["formats"].get(fmt)
    if f is None:
        raise CastError(f"characters: format '{fmt}' is not supported in this version (only 9:16; 16:9 is reserved)")
    s = f["slots"].get(slot)
    if s is None:
        raise CastError(f"characters: slot '{slot}' is not available ({f['slot_notes'].get(slot, 'unknown slot')})")
    return s


# ------------------------------------------------------------------------------------------------ placement
def placement(spec, x_frac, framing, slot, uses_wave=False, uses_point=False, hop_h=0):
    """Scale and feet position (slot coordinates) for one actor, or CastError if it cannot be shown properly."""
    M = ZONES["rig_metrics"]
    F = ZONES["framing"]
    b = M["builds"][spec["build"]]
    ext = M["extent"][f"{spec['build']}/{spec['hair']}"]
    top = ext["top"]                                    # negative, rig units above the feet
    G = M["gestures"][spec["build"]]                    # measured from the real rig (zones.json)
    top_needed = min(top, G["wave_top"]) if uses_wave else top
    w, h, m = slot["width"], slot["height"], F["margin_px"]
    face_rig = (176 + b["ch"]) * b["headS"]
    if framing == "bust":
        span = -top_needed - b["legH"]                  # hips -> head (or raised hand)
        s = min(F["bust_max_scale"], (h - m) / span)
        feet_y = h + b["legH"] * s                      # hips exactly on the lower slot edge
        if hop_h:
            raise CastError("hop is not available in bust framing (the hips sit on the slot edge)")
    elif framing == "full":
        shadow = 18
        span = -top_needed + shadow + hop_h
        s = min(F["full_max_scale"], (h - m) / span)
        feet_y = h - shadow * s - 2
    else:
        raise CastError(f"framing must be 'bust' or 'full', got {framing!r}")
    face = face_rig * s
    if face < F["min_face_px"]:
        raise CastError(f"framing '{framing}': the face would be only {face:.0f}px tall (minimum {F['min_face_px']}px); "
                        "use 'bust'")
    left, right = ext["left"], ext["right"]
    if uses_point:
        left, right = min(left, G["point_left"]), max(right, G["point_right"])
    cx = x_frac * w
    if cx + left * s < m or cx + right * s > w - m:
        raise CastError(f"x {x_frac}: the character ({left * s:.0f}..{right * s:.0f}px around its centre at scale "
                        f"{s:.2f}) would be cut by the slot edge (usable 0..{w}px); move it inwards")
    return {"scale": round(s, 4), "x": round(cx, 2), "y": round(feet_y, 2), "face_px": round(face, 1),
            "framing": framing}


# ------------------------------------------------------------------------------------------------ validation
def validate(proj, pdir, sentence_ids):
    """Validated character plan, or None when the project uses no characters. sentence_ids: all ids (sX_n)."""
    if not uses_characters(proj):
        return None
    from character.adapter import AdapterError, adapt, load_checked     # C3 adapter (C1 lock enforced)
    meta = proj["meta"]
    fmt = meta.get("format", "9:16")
    slot = slot_geometry(fmt, "bottom")
    if "cast" not in meta:
        raise CastError("scenes use 'characters' but meta.cast is missing")
    cast = _obj(meta["cast"], "meta.cast")
    _unknown(cast, CAST_KEYS, "meta.cast")
    d = cast.get("dir")
    if not isinstance(d, str) or not d or d.startswith(("/", "\\")) or ".." in Path(d).parts:
        raise CastError("meta.cast.dir must be a relative folder inside the project (no '..')")
    cdir = (Path(pdir) / d).resolve()
    if Path(pdir).resolve() not in cdir.parents:
        raise CastError("meta.cast.dir must stay inside the project folder")
    try:
        checked = load_checked(cdir)
    except AdapterError as e:
        raise CastError("meta.cast.dir: " + "; ".join(e.problems))
    actors_in = _obj(cast.get("actors"), "meta.cast.actors")
    if not actors_in:
        raise CastError("meta.cast.actors must name at least one actor")

    scenes = proj["scenes"]
    sents = {}
    for sid in sentence_ids:
        sc, n = sid.rsplit("_", 1)
        sents.setdefault(sc, []).append(int(n))
    # which actors appear where, and what they do there (needed for the placement checks)
    per_scene, uses = [], {a: {"wave": False, "point": False, "hop": 0} for a in actors_in}
    for sc in scenes:
        w = f"scene {sc['id']}"
        if "characters" not in sc:
            per_scene.append(None)
            continue
        ch = _obj(sc["characters"], f"{w}.characters")
        _unknown(ch, SCENE_KEYS, f"{w}.characters")
        slot_name = ch.get("slot", "bottom")
        if slot_name != "bottom":
            slot_geometry(fmt, slot_name)                       # raises with the reason
        if sc.get("template") == "cta" and any((sc.get("on_screen") or {}).get(k) for k in ("note", "handle")):
            raise CastError(f"{w}: template 'cta' with note/handle uses the bottom zone (y 1400-1630); "
                            "characters cannot share it")
        media = sc.get("media")
        if isinstance(media, dict) and media.get("frame") == "bottom":
            raise CastError(f"{w}: the camera media frame 'bottom' (y 1372-1640) uses the character slot")
        lst = ch.get("actors")
        if not isinstance(lst, list) or not lst:
            raise CastError(f"{w}.characters.actors must be a non-empty list")
        present = {}
        for i, a in enumerate(lst):
            if isinstance(a, str):
                a = {"actor": a}
            a = _obj(a, f"{w}.characters.actors[{i}]")
            _unknown(a, SCENE_ACTOR_KEYS, f"{w}.characters.actors[{i}]")
            aid = a.get("actor")
            if aid not in actors_in:
                raise CastError(f"{w}: actor '{aid}' is not declared in meta.cast.actors")
            if aid in present:
                raise CastError(f"{w}: actor '{aid}' listed twice")
            present[aid] = a.get("expr")
        speaker = ch.get("speaker", NARRATOR)
        if speaker != NARRATOR and speaker not in present:
            raise CastError(f"{w}: speaker '{speaker}' is not present in this scene (present: {', '.join(present)})")
        n_sent = sorted(sents.get(sc["id"], []))
        per_sentence = {n: speaker for n in n_sent}
        ss = ch.get("sentence_speakers", {})
        _obj(ss, f"{w}.characters.sentence_speakers")
        for k, v in ss.items():
            if not (isinstance(k, str) and k.isdigit() and int(k) in per_sentence):
                raise CastError(f"{w}.sentence_speakers: '{k}' is not a sentence number of this scene "
                                f"({', '.join(map(str, n_sent)) or 'none'})")
            if v != NARRATOR and v not in present:
                raise CastError(f"{w}.sentence_speakers['{k}']: '{v}' is not present in this scene")
            per_sentence[int(k)] = v
        acts = ch.get("actions", [])
        if not isinstance(acts, list):
            raise CastError(f"{w}.characters.actions must be a list")
        for j, ac in enumerate(acts):
            ac = _obj(ac, f"{w}.characters.actions[{j}]")
            if ac.get("actor") not in present:
                raise CastError(f"{w}.actions[{j}]: actor '{ac.get('actor')}' is not present in this scene")
            if ac.get("do") not in SCENE_ACTIONS:
                raise CastError(f"{w}.actions[{j}]: '{ac.get('do')}' is not available in the slot "
                                f"({', '.join(sorted(SCENE_ACTIONS))})")
            if not _num(ac.get("at")) or ac["at"] < 0:
                raise CastError(f"{w}.actions[{j}]: 'at' (seconds from the scene start, >= 0) is required")
            u = uses[ac["actor"]]
            u["wave"] |= ac["do"] == "wave"
            u["point"] |= ac["do"] == "point"
            if ac["do"] == "hop":
                u["hop"] = max(u["hop"], ac.get("h", 40))
        per_scene.append({"scene": sc["id"], "present": present,
                          "speakers": {f"{sc['id']}_{n}": per_sentence[n] for n in n_sent}, "actions": acts})

    actors = {}
    for idx, (aid, a) in enumerate(actors_in.items()):
        w = f"meta.cast.actors.{aid}"
        if not ACTOR_RE.match(aid) or aid == NARRATOR:
            raise CastError(f"{w}: actor ids must match {ACTOR_RE.pattern} and cannot be '{NARRATOR}'")
        a = _obj(a, w)
        _unknown(a, ACTOR_KEYS, w)
        x = a.get("x", 0.5)
        if not _num(x) or not 0 <= x <= 1:
            raise CastError(f"{w}.x must be a number 0..1 (position across the slot)")
        framing = a.get("framing", ZONES["framing"]["default"])
        try:
            ad = adapt(checked, a.get("character"), stage=a.get("stage"), wardrobe=a.get("wardrobe"),
                       instance=idx + 1, detail=a.get("detail"))
        except AdapterError as e:
            raise CastError(f"{w}: " + "; ".join(e.problems))
        try:
            place = placement(ad["spec"], x, framing, slot, uses[aid]["wave"], uses[aid]["point"], uses[aid]["hop"])
        except CastError as e:
            raise CastError(f"{w}: {e}")
        actors[aid] = {"character": a.get("character"), "stage": ad["stage"], "wardrobe": ad["wardrobe"],
                       "detail": bool(a.get("detail")), "placement": place, "fingerprint": ad["fingerprint"]}
    used = {aid for p in per_scene if p for aid in p["present"]}
    unused = sorted(set(actors) - used)
    if unused:
        raise CastError(f"meta.cast.actors declares actor(s) that appear in no scene: {', '.join(unused)}")
    return {"format": fmt, "slot": slot, "cast_dir": str(cdir), "cast_rel": d, "actors": actors, "scenes": per_scene}
