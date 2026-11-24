"""
NFP Studio - Character layer (C4): validated character plan + the composed page's timeline -> ONE KeyList per video.

Every actor is ONE element for the whole video (so DOM ids can never collide between scenes). It is visible in the
scenes that list it: consecutive scenes keep it on screen; otherwise it fades in with the scene's own fade-in and
fades out before the next scene starts. Times come from the page's own timeline data (const DATA, the same rules as
base.html / camera.inject.scene_spans) and the real word timings (timing.json). The KeyList is planned by the C3
planner (nfp/character/animation), whose C1 adapter enforces the identity lock.
"""
import math

from camera import inject as CI                           # read-only helpers: scene spans of the page timeline
from character.animation.keys import PlanError
from character.animation.script import plan as c3_plan

from .schema import NARRATOR, CastError

FPS = 30
FADE = 0.3          # character fade in / out (s)


def video_duration(data):
    """Largest frame-grid duration that does not exceed the page timeline (the timeline must never grow)."""
    return math.floor(float(data["duration"]) * FPS + 1e-9) / FPS


def intervals(order, per_scene, aid, spans, dur):
    """Visible intervals of one actor: runs of consecutive scenes that list it."""
    out, cur = [], None
    for sid in order:
        p = per_scene.get(sid)
        here = p is not None and aid in p["present"]
        if here:
            t0, t1 = spans[sid]
            cur = [t0, t1, [sid]] if cur is None else [cur[0], t1, cur[2] + [sid]]
        elif cur is not None:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return [[a, min(b, dur), s] for a, b, s in out]


def action_script(plan, data, timing):
    dur = video_duration(data)
    spans = CI.scene_spans(data)
    order = [s["id"] for s in data["scenes"]]
    per_scene = {p["scene"]: p for p in plan["scenes"] if p}
    missing = set(per_scene) - set(order)
    if missing:
        raise CastError(f"scenes with characters are not in the page timeline: {', '.join(sorted(missing))}")
    offsets = {s["id"]: float(s["offset"]) for s in timing["sentences"]}
    actors, actions, report = [], [], {"duration": dur, "actors": {}, "speakers": {}, "deco_hidden": []}
    for aid, a in plan["actors"].items():
        ivs = intervals(order, per_scene, aid, spans, dur)
        first_expr = per_scene[ivs[0][2][0]]["present"][aid]          # expression of the actor's FIRST scene only
        pl = a["placement"]
        actors.append({"id": aid, "cast": plan["cast_rel"], "character": a["character"], "stage": a["stage"],
                       "wardrobe": a["wardrobe"], "instance": len(actors) + 1, "x": pl["x"], "y": pl["y"],
                       "scale": pl["scale"], "idle": True, "detail": a["detail"],
                       "expr": first_expr or "neutral"})
        cur_expr = first_expr or "neutral"
        for k, (t0, t1, sids) in enumerate(ivs):
            if t1 - t0 < 2 * FADE + 0.2:
                raise CastError(f"actor '{aid}': visible for only {t1 - t0:.2f}s in {', '.join(sids)} (too short)")
            if t0 > 1e-6:
                actions.append({"actor": aid, "do": "enter", "t": round(t0, 4), "style": "fade", "dur": FADE})
            if t1 < dur - 1e-6:
                actions.append({"actor": aid, "do": "exit", "t": round(t1 - FADE, 4), "style": "fade", "dur": FADE})
            for j, sid in enumerate(sids):
                e = per_scene[sid]["present"][aid]
                if not e or e == cur_expr:
                    continue
                # first scene of an interval: after the fade-in; later scenes: at the scene's own fade-in
                t = t0 + FADE if j == 0 else spans[sid][0]
                actions.append({"actor": aid, "do": "expr", "t": round(t, 4), "name": e})
                cur_expr = e
        report["actors"][aid] = {"intervals": [[round(a_, 3), round(b_, 3), s] for a_, b_, s in ivs],
                                 "placement": pl, "fingerprint": a["fingerprint"]}
    talk = {}
    for sid in order:
        p = per_scene.get(sid)
        if not p:
            continue
        report["deco_hidden"].append(sid)
        s0, s1 = spans[sid]
        for sent, who in p["speakers"].items():
            report["speakers"][sent] = who
            if who == NARRATOR:
                continue
            if sent not in offsets:
                raise CastError(f"sentence {sent} has no timing in timing.json")
            talk.setdefault(who, []).append(sent)
            actions.append({"actor": who, "do": "talk", "t": round(max(s0, offsets[sent]), 4), "sentences": [sent]})
        for ac in p["actions"]:
            t = s0 + float(ac["at"])
            if t >= min(s1, dur):
                raise CastError(f"scene {sid}: action '{ac['do']}' at +{ac['at']}s starts after the scene ends")
            x = {k: v for k, v in ac.items() if k != "at"}
            x["t"] = round(t, 4)
            actions.append(x)
    slot = plan["slot"]
    doc = {"schema": "nfp.anim.actions/1", "fps": FPS, "duration": dur,
           "stage": {"width": slot["width"], "height": slot["height"]}, "actors": actors, "actions": actions}
    report["talks"] = talk
    return doc, report


def build_keylist(plan, data, timing, project_dir):
    doc, report = action_script(plan, data, timing)
    try:
        kl = c3_plan(doc, base_dir=project_dir, timing=timing)
    except PlanError as e:
        raise CastError("character plan refused by the C3 planner:\n" + "\n".join(e.problems))
    report["keys"] = len(kl["keys"])
    report["digest"] = kl["digest"]
    report["lipsync"] = kl["lipsync"]["talks"]
    report["notes"] = kl["notes"]
    return kl, doc, report
