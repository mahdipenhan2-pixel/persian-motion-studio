"""
NFP Character Engine - C3b/C3c: action script -> KeyList (the planner entry point).

    from character.animation.script import plan_file
    keylist = plan_file("nfp/character/examples/demo-anim/actions.json")

An action script (schema/action_script.v1.json) names characters from a LOCKED C1 cast (through the C3a adapter),
places them on a stage, and lists timed actions. The planner:
  1. loads every cast with adapter.load_checked (identity lock enforced) and adapts each actor to a full rig spec;
  2. puts the rest pose at frame 0 (and hides actors whose first action is an entrance);
  3. runs the actions in time order (stable for equal times); any two motions on the same property that overlap in
     time are refused with a clear error - nothing is silently shifted or dropped;
  4. fills idle (breathing, seeded blinks) only where the channels are free;
  5. merges expression mouths and lip sync into one mouth channel (speech wins while talking; the expression mouth
     returns, closed, at every pause > 0.15 s and at the end);
  6. validates the result (keys.validate_keylist) and returns it. Same input -> byte-identical output.
"""
import json
from pathlib import Path

from ..adapter import AdapterError, adapt, load_checked
from . import lipsync as LS
from . import presets as PR
from . import timing_normalize as TN
from .keys import (ACTOR_ID, FPS, KEYLIST_SCHEMA, POS_LIMIT, SCALE_MAX, PlanError, Track, digest, to_frame,
                   validate_keylist)

ACTION_SCHEMA = "nfp.anim.actions/1"
ACTIONS = {
    "enter": {"dur": 0.5, "opt": {"style", "from_dx", "gait"}},
    "exit": {"dur": 0.5, "opt": {"style", "dx", "gait"}},
    "walk": {"dur": None, "req": {"dx"}, "opt": {"step", "amp", "arms"}},
    "run": {"dur": None, "req": {"dx"}, "opt": {"step", "amp", "arms"}},
    "move": {"dur": None, "opt": {"dx", "dy"}},
    "blink": {"dur": 0, "opt": set()},
    "breathe": {"dur": None, "opt": {"amp"}},
    "look": {"dur": 0.25, "opt": {"dir", "dx", "dy"}},
    "turn": {"dur": 0.3, "req": {"deg"}, "opt": {"dx"}},
    "nod": {"dur": 0.4, "opt": {"amp"}},
    "arm": {"dur": 0.3, "req": {"side", "r"}, "opt": {"fore", "ease"}},
    "arms_rest": {"dur": 0.3, "opt": set()},
    "wave": {"dur": 1.4, "opt": {"side"}},
    "point": {"dur": 0.35, "opt": {"side", "hold"}},
    "lean": {"dur": 0.3, "req": {"deg"}, "opt": set()},
    "hop": {"dur": 0.4, "opt": {"h"}},
    "shiver": {"dur": 0.6, "opt": {"amp"}},
    "expr": {"dur": 0.22, "req": {"name"}, "opt": set()},
    "sit": {"dur": 0.6, "opt": {"facing", "angle"}},
    "stand": {"dur": 0.6, "opt": set()},
    "talk": {"dur": None, "opt": {"sentences", "offset", "viseme", "estimated"}},
}
ACTOR_KEYS = {"id", "cast", "character", "stage", "wardrobe", "expr", "instance", "x", "y", "scale", "idle", "seed",
              "detail"}


def _num(v):
    import math
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _seed(text):
    import hashlib
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def plan_file(path):
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    return plan(doc, base_dir=path.parent)


def plan(doc, base_dir=".", timing=None):
    base_dir = Path(base_dir)
    P = []
    if not isinstance(doc, dict) or doc.get("schema") != ACTION_SCHEMA:
        raise PlanError(f"action script: schema must be '{ACTION_SCHEMA}'")
    fps = doc.get("fps", FPS)
    if fps != FPS:
        raise PlanError(f"action script: fps {fps} is not supported - C3 is built and tested for {FPS} fps only "
                        f"(frame-based timings such as blinks, mouth flaps and settles are defined on the {FPS} fps grid)")
    dur = doc.get("duration")
    if not _num(dur) or dur <= 0:
        raise PlanError("action script: 'duration' (seconds, > 0) is required")
    frames = to_frame(dur, fps, "duration")
    stage = doc.get("stage") or {"width": 1920, "height": 1080}
    if not (isinstance(stage, dict) and _num(stage.get("width")) and _num(stage.get("height"))):
        raise PlanError("action script: stage needs numeric width and height")

    # ---- timing (word timestamps) ----
    words = None
    if timing is not None:
        words = TN.normalize(timing)
    elif doc.get("timing") is not None:
        t = doc["timing"]
        if isinstance(t, str):
            tp = (base_dir / t).resolve()
            if not tp.is_file():
                raise PlanError(f"timing file not found: {t}")
            t = json.loads(tp.read_text(encoding="utf-8"))
        words = TN.normalize(t)

    # ---- actors ----
    casts, actors, out_actors = {}, {}, []
    for i, a in enumerate(doc.get("actors") or []):
        w = f"actors[{i}]"
        if not isinstance(a, dict):
            P.append(f"{w}: must be an object")
            continue
        extra = sorted(set(a) - ACTOR_KEYS)
        if extra:
            P.append(f"{w}: unknown field(s) {', '.join(extra)}")
        for k in ("id", "cast", "character"):
            if not isinstance(a.get(k), str) or not a.get(k):
                P.append(f"{w}: '{k}' (string) is required")
        if P:
            continue
        if not ACTOR_ID.match(a["id"]):
            P.append(f"{w}: id '{a['id']}' must match {ACTOR_ID.pattern}")
            continue
        if a["id"] in actors:
            P.append(f"{w}: duplicate actor id '{a['id']}'")
            continue
        cdir = (base_dir / a["cast"]).resolve()
        try:
            if cdir not in casts:
                casts[cdir] = load_checked(cdir)
            ad = adapt(casts[cdir], a["character"], stage=a.get("stage"), wardrobe=a.get("wardrobe"),
                       expr=a.get("expr"), instance=a.get("instance", i + 1), detail=a.get("detail"))
        except AdapterError as e:
            P.extend(f"{w}: {p}" for p in e.problems)
            continue
        x, y, sc = a.get("x", stage["width"] / 2), a.get("y", stage["height"] * 0.85), a.get("scale", 1.0)
        if not (_num(x) and _num(y) and _num(sc) and abs(x) <= POS_LIMIT and abs(y) <= POS_LIMIT and 0 < sc <= SCALE_MAX):
            P.append(f"{w}: x, y must be numbers within +-{POS_LIMIT} and scale in (0, {SCALE_MAX}]")
            continue
        seed = a.get("seed", _seed(a["id"]))
        if not isinstance(seed, int) or isinstance(seed, bool):
            P.append(f"{w}: seed must be an integer")
            continue
        A = PR.Actor(a["id"], ad, x, y, sc, seed, fps)
        A.idle = a.get("idle", True) is not False
        actors[a["id"]] = A
        out_actors.append({"id": a["id"], "dom_id": ad["dom_id"], "fingerprint": ad["fingerprint"],
                           "project": ad["project"], "character": ad["character"], "stage": ad["stage"],
                           "wardrobe": ad["wardrobe"], "expr": ad["expr"], "spec": ad["spec"],
                           "sources": ad["sources"], "x": x, "y": y, "scale": sc, "seed": seed,
                           "warnings": ad["warnings"]})
    if not actors and not P:
        P.append("action script: at least one actor is required")
    if P:
        raise PlanError(P)

    # ---- actions: validate + order ----
    acts = []
    for i, x in enumerate(doc.get("actions") or []):
        w = f"actions[{i}]"
        if not isinstance(x, dict):
            P.append(f"{w}: must be an object")
            continue
        do = x.get("do")
        if do not in ACTIONS:
            P.append(f"{w}: unknown action '{do}' (known: {', '.join(sorted(ACTIONS))})")
            continue
        spec = ACTIONS[do]
        if x.get("actor") not in actors:
            P.append(f"{w}: unknown actor '{x.get('actor')}'")
            continue
        if not _num(x.get("t")) or x["t"] < 0 or x["t"] > dur:
            P.append(f"{w}: 't' must be a time inside the timeline (0..{dur} s)")
            continue
        allowed = {"actor", "do", "t", "dur"} | spec.get("req", set()) | spec.get("opt", set())
        extra = sorted(set(x) - allowed)
        if extra:
            P.append(f"{w} ({do}): unknown field(s) {', '.join(extra)}")
        missing = sorted(spec.get("req", set()) - set(x))
        if missing:
            P.append(f"{w} ({do}): missing {', '.join(missing)}")
        d = x.get("dur", spec["dur"])
        if do != "talk" and (d is None or not _num(d) or d < 0):
            P.append(f"{w} ({do}): 'dur' (seconds) is required")
        acts.append((to_frame(x["t"], fps, f"{w}.t"), i, x))
    if P:
        raise PlanError(P)
    acts.sort(key=lambda a: (a[0], a[1]))

    T = Track(fps, frames)
    first = {}
    for f, i, x in acts:
        first.setdefault(x["actor"], x["do"])
    for A in actors.values():
        PR.base_pose(T, A)
        if first.get(A.id) == "enter":
            PR.hide_initially(T, A)
        else:
            A.on_since = 0

    talks = []
    for f, i, x in acts:
        A, do = actors[x["actor"]], x["do"]
        src = f"actions[{i}]:{do}"
        d = x.get("dur", ACTIONS[do]["dur"])
        df = to_frame(d, fps, f"{src}.dur") if d is not None else None
        try:
            if do == "enter":
                PR.enter(T, A, f, df, x.get("style", "pop"), x.get("from_dx", -700), x.get("gait", "walk"), src)
            elif do == "exit":
                PR.exit_(T, A, f, df, x.get("style", "pop"), x.get("dx", 700), x.get("gait", "walk"), src)
            elif do in ("walk", "run"):
                PR.locomote(T, A, f, df, x["dx"], gait=do, step=x.get("step"), amp=x.get("amp"),
                            arms=x.get("arms", True), src=src)
            else:
                PR._need(A, f, src)
                if do == "move":
                    PR.move(T, A, f, df, x.get("dx", 0), x.get("dy", 0), src)
                elif do == "blink":
                    PR.blink(T, A, f, src)
                elif do == "breathe":
                    if A.idle:
                        raise PlanError(f"{src}: actor has idle on (idle already breathes); set idle:false to script it")
                    PR.breathe(T, A, f, f + df, x.get("amp", 0.022), src)
                elif do == "look":
                    PR.look(T, A, f, df, x.get("dir"), x.get("dx"), x.get("dy"), src)
                elif do == "turn":
                    PR.turn(T, A, f, df, x["deg"], x.get("dx", 0), src)
                elif do == "nod":
                    PR.nod(T, A, f, df, x.get("amp", 8), src)
                elif do == "arm":
                    PR.arm(T, A, f, df, x["side"], x["r"], x.get("fore"), x.get("ease", "power2.inOut"), src)
                elif do == "arms_rest":
                    PR.arms_rest(T, A, f, df, src=src)
                elif do == "wave":
                    PR.wave(T, A, f, df, x.get("side", "R"), src)
                elif do == "point":
                    PR.point(T, A, f, df, x.get("side", "R"), x.get("hold", 1.0), src)
                elif do == "lean":
                    PR.lean(T, A, f, df, x["deg"], src)
                elif do == "hop":
                    PR._need(A, f, src, standing=True)
                    PR.hop(T, A, f, df, x.get("h", 40), src)
                elif do == "shiver":
                    PR.shiver(T, A, f, df, x.get("amp", 3), src)
                elif do == "expr":
                    PR.expression(T, A, f, df, x["name"], src)
                elif do == "sit":
                    PR.sit(T, A, f, df, x.get("facing", "right"), x.get("angle", 80), src)
                elif do == "stand":
                    PR.stand(T, A, f, df, src)
                elif do == "talk":
                    talks.append((f, i, x, A, src))
        except PlanError as e:
            raise PlanError([p if p.startswith(src) else f"{src}: {p}" for p in e.problems])

    for A in actors.values():
        if A.visible:
            A.windows.append((A.on_since, frames))

    # ---- lip sync ----
    lip_reports = []
    for f, i, x, A, src in talks:
        if words is None:
            raise PlanError(f"{src}: talk needs word timings ('timing' in the action script)")
        sel = x.get("sentences")
        if sel is not None and (not isinstance(sel, list) or not all(isinstance(s, str) for s in sel)):
            raise PlanError(f"{src}: 'sentences' must be a list of sentence ids")
        known = {s["id"] for s in words["sentences"]}
        if sel is not None and set(sel) - known:
            raise PlanError(f"{src}: unknown sentence(s) {sorted(set(sel) - known)}")
        use_est = x.get("estimated", True)
        if not isinstance(use_est, bool):
            raise PlanError(f"{src}: 'estimated' must be true or false")
        tw = TN.timed_words(words, None if sel is None else set(sel))
        skipped_est = [{"sentence": sid, "i": w["i"], "text": w["text"]} for sid, w in tw if w["quality"] == "estimated"] \
            if not use_est else []
        if not use_est:
            tw = [(sid, w) for sid, w in tw if w["quality"] != "estimated"]
        off = x.get("offset", 0.0)
        mk, rep = LS.plan_speech(tw, fps, offset=off, viseme=x.get("viseme", True))
        if mk[0][0] < f:
            raise PlanError(f"{src}: speech starts at frame {mk[0][0]}, before the talk action (frame {f})")
        if mk[-1][0] >= frames:
            raise PlanError(f"{src}: speech ends after the timeline")
        if not any(a <= mk[0][0] and mk[-1][0] <= b for a, b in A.windows):
            raise PlanError(f"{src}: '{A.id}' is not on stage for the whole speech "
                            f"(frames {mk[0][0]}..{mk[-1][0]})")
        for seg in A.speech:
            if not (mk[-1][0] < seg[0][0] or seg[-1][0] < mk[0][0]):
                raise PlanError(f"{src}: overlaps another talk of '{A.id}'")
        A.speech.append(mk)
        sel_ids = set(sel) if sel is not None else known
        unres = [u for u in words["report"]["unresolved"] if u["sentence"] in sel_ids]
        lip_reports.append({"actor": A.id, "action": i, "sentences": sorted(sel_ids), "first_frame": mk[0][0],
                            "last_frame": mk[-1][0], "unresolved_words": unres, "estimated_used": use_est,
                            "estimated_skipped": skipped_est, **rep})

    # ---- idle (fills free channels only) ----
    idle_report = {}
    for A in actors.values():
        b_total, k_total = 0, 0
        if A.idle:
            for a, b in A.windows:
                b_total += PR.breathe(T, A, a, b, src="idle_breathe")
                k_total += PR.auto_blink(T, A, a, b)
        idle_report[A.id] = {"breath_half_cycles": b_total, "blinks": k_total}

    # ---- mouth channel: expressions + speech ----
    for A in actors.values():
        _mouth(T, A)

    keys = T.finalize()
    kl = {
        "schema": KEYLIST_SCHEMA, "fps": fps, "frames": frames, "duration": round(frames / fps, 6),
        "stage": {"width": stage["width"], "height": stage["height"]},
        "actors": out_actors, "keys": keys,
        "lipsync": {"timing": words["report"] if words else None, "talks": lip_reports},
        "idle": idle_report,
        "notes": [dict(actor=A.id, **n) for A in actors.values() for n in A.notes],
    }
    kl["digest"] = digest(kl)
    problems = validate_keylist(kl)
    if problems:
        raise PlanError(["internal: planned KeyList failed validation"] + problems)
    return kl


def _mouth(T, A):
    """One mouth channel: rest (expression) mouths, overridden by speech; '@rest' = current expression, closed."""
    events = [(f, 1, "rest", m, "expr") for f, m in A.rest_events]
    spans = []
    for seg in A.speech:
        spans.append((seg[0][0], seg[-1][0]))
        events += [(f, 0, "speech", s, src) for f, s, src in seg]
    events.sort(key=lambda e: (e[0], e[1]))
    rest, shown, out = "neutral", "neutral", []

    def in_speech(f):
        return any(a <= f < b for a, b in spans)

    for f, _, kind, val, src in events:
        if kind == "rest":
            rest = val
            if in_speech(f):
                continue                              # applied when the speech closes
            want = val
        else:
            want = LS.closed(rest) if val == "@rest" else val
        if out and out[-1][0] == f:
            out[-1] = (f, want, src)                  # same frame: the later event wins (speech close uses new rest)
        elif want != shown:
            out.append((f, want, src))
        shown = out[-1][1] if out else shown
    prev = "neutral"
    for f, shape, src in out:
        if shape != prev:
            T.add(A.id, "mouth", "shape", f, shape, 0, "none", src)
            prev = shape
