#!/usr/bin/env python3
"""
C3b tests: deterministic animation planner (offline; no browser, no network, no API).

  python3 nfp/character/tests/test_animation.py

C. repeatability (same input -> byte-identical KeyList, also in a fresh process, equal to the committed golden file),
   key order, continuity (no jumps, bounded per-frame speed), walking (no drift, limbs back at rest), running, idle,
   combinations (allowed and refused overlaps), timeline range, every action type, sit/stand approximation,
   independent validation of tampered KeyLists, contracts (schemas, profile vs C1 catalogue).
"""
import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG.parent))

from character.animation import keys as KY  # noqa: E402
from character.animation.keys import PROFILE, PlanError, canonical, jumps, sample, validate_keylist  # noqa: E402
from character.animation.script import ACTIONS, plan, plan_file  # noqa: E402

DEMO = PKG / "examples" / "demo-anim"
CAST = "../demo-cast"
RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg)


def script(actions, duration=8.0, actors=None, timing=None, **kw):
    d = {"schema": "nfp.anim.actions/1", "fps": 30, "duration": duration,
         "actors": actors or [{"id": "z", "cast": CAST, "character": "zahra", "x": 600, "y": 1000, "seed": 3}],
         "actions": actions}
    if timing is not None:
        d["timing"] = timing
    d.update(kw)
    return d


def run(actions, **kw):
    return plan(script(actions, **kw), base_dir=DEMO)


def fails(actions, needle, **kw):
    try:
        run(actions, **kw)
    except PlanError as e:
        hit = next((p for p in e.problems if needle in p), None)
        return hit is not None, (hit or e.problems[0])[:160]
    return False, "no error"


def at(kl, actor, part, prop, fr):
    return sample(kl, fr).get(actor, {}).get(part, {}).get(prop, KY.rest_value(part, prop))


def max_speed(kl, actor, part, prop):
    """largest change between two consecutive frames on which the character is visible"""
    chs = KY.channels(kl["keys"])
    lst = chs.get((actor, part, prop), [])
    if not lst:
        return 0.0
    vis = [KY.visible_at(chs, actor, f) for f in range(kl["frames"] + 1)]
    vals = [KY.sample_channel(lst, part, prop, f) for f in range(kl["frames"] + 1)]
    return max([abs(vals[f + 1] - vals[f]) for f in range(kl["frames"]) if vis[f] and vis[f + 1]] or [0.0])


LIMBS = ["legL", "legR", "shinL", "shinR", "shoeL", "shoeR", "torso", "head", "root"]


def main():
    print("== C1 repeatability")
    a, b = plan_file(DEMO / "actions.json"), plan_file(DEMO / "actions.json")
    check(canonical(a) == canonical(b) and a["digest"] == b["digest"], f"same input -> identical KeyList (digest {a['digest'][:16]})")
    golden = json.loads((DEMO / "keylist.json").read_text(encoding="utf-8"))
    check(canonical(golden) == canonical(a), "equals the committed golden examples/demo-anim/keylist.json (regression)")
    env = dict(os.environ, PYTHONHASHSEED="12345")
    code = ("import sys; sys.path.insert(0, %r); from character.animation.script import plan_file; "
            "print(plan_file(%r)['digest'])") % (str(PKG.parent), str(DEMO / "actions.json"))
    other = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env).stdout.strip()
    check(other == a["digest"], "a fresh process with a different hash seed gives the same digest")
    s1 = run([], actors=[{"id": "z", "cast": CAST, "character": "zahra", "seed": 1}])
    s2 = run([], actors=[{"id": "z", "cast": CAST, "character": "zahra", "seed": 2}])
    blink_frames = lambda kl: [k["f"] for k in kl["keys"] if k["part"] == "lidL" and k["val"] != 0]  # noqa: E731
    check(blink_frames(s1) != blink_frames(s2) and blink_frames(s1) == blink_frames(run([], actors=[
        {"id": "z", "cast": CAST, "character": "zahra", "seed": 1}])), "blinks depend only on the seed (seeded PRNG, no clock)")

    print("\n== C2 key order, validity, continuity")
    check(validate_keylist(a) == [], f"the demo KeyList passes the independent validator ({len(a['keys'])} keys)")
    order = [(k["f"], k["actor"], k["part"], k["prop"]) for k in a["keys"]]
    check(order == sorted(order) and all(k["t"] == round(k["f"] / 30, 6) for k in a["keys"]),
          "keys sorted by (frame, actor, part, prop); every time on the 30 fps grid")
    check(jumps(a) == [], "no instant jump of any continuous value while the character is visible")
    sp = {p: round(max_speed(a, "zahra", "self", p), 3) for p in ("--x", "--y")}
    rs = round(max(max_speed(a, "zahra", part, "--r") for part in ("legL", "legR", "armL", "armR", "torso", "head")), 3)
    check(sp["--x"] <= 30 and sp["--y"] <= 30 and rs <= 30,
          f"bounded per-frame motion: stage position <= {max(sp.values())} px/frame, limb rotation <= {rs} deg/frame")

    print("\n== C3 walking")
    w = run([{"actor": "z", "do": "walk", "t": 1, "dur": 2.4, "dx": 300}, {"actor": "z", "do": "walk", "t": 4, "dur": 2.4, "dx": -300}],
            actors=[{"id": "z", "cast": CAST, "character": "zahra", "idle": False}])
    end = w["frames"]
    check(at(w, "z", "self", "--x", 30 * 3.4) == 300 and at(w, "z", "self", "--x", end) == 0,
          "walk moves exactly dx (+300 then -300 -> back at 0): no drift")
    rest_ok = all(at(w, "z", p, "--r", end) == 0 for p in LIMBS) and at(w, "z", "root", "--y", end) == 0 and \
        at(w, "z", "armL", "--r", end) == 4 and at(w, "z", "armR", "--r", end) == -4
    check(rest_ok, "after walking every limb, the torso, the head and the hips are back at the rest pose")
    mid = [at(w, "z", "legL", "--r", f) for f in range(30, 102)]
    check(max(mid) > 15 and min(mid) < -12 and at(w, "z", "self", "--x", 66) not in (0, 300),
          f"legs really swing during the walk (legL {min(mid):.1f}..{max(mid):.1f} deg) while the body travels")
    xs = [at(w, "z", "self", "--x", f) for f in range(30, 103)]
    check(all(b2 >= a2 for a2, b2 in zip(xs, xs[1:])), "stage position moves monotonically during a walk (no backward step)")
    k_hair = [k for k in w["keys"] if k["part"] == "hairBack"]
    kk = run([{"actor": "k", "do": "walk", "t": 1, "dur": 1.2, "dx": 100}],
             actors=[{"id": "k", "cast": CAST, "character": "karim"}])
    check(k_hair and not [k for k in kk["keys"] if k["part"] == "hairBack"],
          "long hair lags behind on a walk (zahra); a short-haired character gets no hairBack keys (karim)")

    slide = run([{"actor": "z", "do": "walk", "t": 1, "dur": 1.2, "dx": 1400}])
    check(any("foot_slide_risk" in n for n in slide["notes"]) and not w["notes"],
          "a walk covering far more ground than the legs swing is reported as a foot-slide risk (normal walks are not)")

    print("\n== C4 running")
    r = run([{"actor": "z", "do": "run", "t": 1, "dur": 1.6, "dx": 500}], actors=[{"id": "z", "cast": CAST, "character": "zahra", "idle": False}])
    steps = len([k for k in r["keys"] if k["part"] == "root" and k["prop"] == "--y" and k["val"] < 0])
    wsteps = len([k for k in w["keys"] if k["part"] == "root" and k["prop"] == "--y" and k["val"] < 0]) // 2
    check(at(r, "z", "self", "--x", r["frames"]) == 500 and steps == 8 and wsteps == 8,
          f"run: 1.6 s -> {steps} steps (0.2 s each) vs walk 2.4 s -> {wsteps} steps (0.3 s); exact distance")
    lean = [at(r, "z", "torso", "--r", f) for f in range(31, 78)]
    check(sum(lean) / len(lean) > 3 and all(at(r, "z", p, "--r", r["frames"]) == 0 for p in LIMBS),
          f"run leans forward (mean torso {sum(lean) / len(lean):.1f} deg) and settles back to rest")

    print("\n== C5 idle")
    idle = run([], duration=12)
    br = [k for k in idle["keys"] if k["src"] == "idle_breathe"]
    bl = [k for k in idle["keys"] if k["src"] == "idle_blink"]
    check(len(br) % 2 == 0 and len(br) >= 8 and br[-1]["val"] == 1 and len(bl) >= 4,
          f"idle = breathing ({len(br)} half cycles, ends at rest) + seeded blinks ({len(bl) // 4} blinks)")
    off = run([], duration=12, actors=[{"id": "z", "cast": CAST, "character": "zahra", "idle": False}])
    check(not [k for k in off["keys"] if k["src"].startswith("idle")], "idle:false -> no automatic motion at all")
    ok, msg = fails([{"actor": "z", "do": "breathe", "t": 1, "dur": 3}], "idle on")
    check(ok, f"scripted breathing on top of idle is refused, not doubled ({msg})")

    print("\n== C6 combinations")
    combo = run([{"actor": "z", "do": "walk", "t": 1, "dur": 2.4, "dx": 200},
                 {"actor": "z", "do": "look", "t": 1.5, "dir": "left"},
                 {"actor": "z", "do": "expr", "t": 1.6, "name": "happy"},
                 {"actor": "z", "do": "blink", "t": 2.0},
                 {"actor": "z", "do": "nod", "t": 2.2, "dur": 0.4},
                 {"actor": "z", "do": "wave", "t": 4, "dur": 1.4}])
    check(validate_keylist(combo) == [] and jumps(combo) == [],
          "walk + look + expression + blink + nod at the same time, then a wave: valid, continuous")
    ok, msg = fails([{"actor": "z", "do": "walk", "t": 1, "dur": 2, "dx": 200}, {"actor": "z", "do": "lean", "t": 1.5, "deg": 8}], "overlaps")
    check(ok, f"two motions on one property at once (walk + lean on torso) are refused ({msg})")
    ok, msg = fails([{"actor": "z", "do": "arm", "t": 1, "side": "R", "r": -60, "dur": 1}, {"actor": "z", "do": "wave", "t": 1.5}], "overlaps")
    check(ok, f"arm + wave on the same arm at once are refused ({msg})")

    print("\n== C7 timeline range")
    for desc, acts, needle in (
        ("an action after the end", [{"actor": "z", "do": "nod", "t": 9}], "inside the timeline"),
        ("a walk running past the end", [{"actor": "z", "do": "walk", "t": 7, "dur": 2, "dx": 100}], "after the timeline"),
        ("a settle that does not fit", [{"actor": "z", "do": "walk", "t": 6.5, "dur": 1.3, "dx": 100}], "settle"),
        ("an entrance at t=0", [{"actor": "z", "do": "enter", "t": 0}], "hidden frame"),
        ("an entrance for a character already on stage (first action was not an entrance)",
         [{"actor": "z", "do": "enter", "t": 3}, {"actor": "z", "do": "nod", "t": 1}], "already on stage"),
        ("a talk while hidden (after an exit)", [{"actor": "z", "do": "exit", "t": 1}, {"actor": "z", "do": "talk", "t": 3}],
         "not on stage"),
        ("an action after the exit", [{"actor": "z", "do": "exit", "t": 1}, {"actor": "z", "do": "nod", "t": 3}], "not on stage"),
        ("a negative time", [{"actor": "z", "do": "nod", "t": -1}], "inside the timeline"),
        ("an unknown action", [{"actor": "z", "do": "dance", "t": 1}], "unknown action"),
        ("an unknown actor", [{"actor": "q", "do": "nod", "t": 1}], "unknown actor"),
        ("an unknown field", [{"actor": "z", "do": "nod", "t": 1, "speed": 2}], "unknown field"),
        ("a head tilt beyond the rig", [{"actor": "z", "do": "turn", "t": 1, "deg": 60}], "beyond"),
        ("eyes looking out of the eye", [{"actor": "z", "do": "look", "t": 1, "dx": 40}], "leaves the eye"),
    ):
        ok, msg = fails(acts, needle)
        check(ok, f"refused: {desc} ({msg})")
    fr = run([{"actor": "z", "do": "nod", "t": 7.6, "dur": 0.4}])
    check(max(k["f"] + k["df"] for k in fr["keys"]) <= fr["frames"], "a motion ending exactly at the last frame is accepted")

    print("\n== C8 every action, sit/stand, entrance/exit")
    everything = run([
        {"actor": "z", "do": "enter", "t": 0.2, "style": "pop", "dur": 0.5},
        {"actor": "z", "do": "look", "t": 1, "dir": "right"}, {"actor": "z", "do": "turn", "t": 1, "deg": 8},
        {"actor": "z", "do": "nod", "t": 1.5}, {"actor": "z", "do": "blink", "t": 1.2},
        {"actor": "z", "do": "arm", "t": 2, "side": "both", "r": 40, "fore": 30}, {"actor": "z", "do": "arms_rest", "t": 2.6},
        {"actor": "z", "do": "point", "t": 3.1, "side": "L", "hold": 0.4}, {"actor": "z", "do": "lean", "t": 3.2, "deg": -6},
        {"actor": "z", "do": "lean", "t": 3.8, "deg": 0}, {"actor": "z", "do": "hop", "t": 4.2},
        {"actor": "z", "do": "shiver", "t": 4.8}, {"actor": "z", "do": "expr", "t": 5, "name": "nervous"},
        {"actor": "z", "do": "move", "t": 5.5, "dur": 0.5, "dx": 50}, {"actor": "z", "do": "run", "t": 6.1, "dur": 0.8, "dx": 120},
        {"actor": "z", "do": "sit", "t": 7.3}, {"actor": "z", "do": "wave", "t": 8, "side": "L"},
        {"actor": "z", "do": "stand", "t": 9.6}, {"actor": "z", "do": "walk", "t": 10.3, "dur": 1.2, "dx": -100},
        {"actor": "z", "do": "exit", "t": 12, "style": "fade", "dur": 0.5},
        {"actor": "z", "do": "enter", "t": 12.8, "style": "fade", "dur": 0.4},
        {"actor": "z", "do": "exit", "t": 13.5, "style": "pop", "dur": 0.4}], duration=14.5)
    used = {k["src"].split(":")[1] for k in everything["keys"] if k["src"].startswith("actions[")}
    check(validate_keylist(everything) == [] and jumps(everything) == [] and
          used >= set(ACTIONS) - {"breathe", "talk", "exit", "walk"} | {"walk"},
          f"every action type plans into a valid, jump-free KeyList ({len(used)} action types used)")
    check(at(everything, "z", "self", "visible", 3) == 0 and at(everything, "z", "self", "visible", 10) == 1
          and at(everything, "z", "self", "visible", 380) == 0 and at(everything, "z", "self", "visible", 395) == 1
          and at(everything, "z", "self", "visible", 434) == 0,
          "visibility: hidden before the entrance, shown after, hidden by exit, re-entered, hidden again")
    check(at(everything, "z", "tears", "display", 160) == 0 and at(everything, "z", "sweat", "display", 160) == 1,
          "expression extras: 'nervous' shows sweat, not tears")
    s = run([{"actor": "z", "do": "sit", "t": 1}, {"actor": "z", "do": "stand", "t": 3}])
    L1 = round(PROFILE["geometry"]["woman"]["legH"] * 0.5)
    drop = at(s, "z", "root", "--y", 60)
    check(abs(drop - L1 * (1 - math.cos(math.radians(80)))) < 1e-3 and at(s, "z", "legL", "--r", 60) == -80
          and at(s, "z", "shinL", "--r", 60) == 80 and at(s, "z", "root", "--y", s["frames"]) == 0,
          f"sit approximation: thighs 80 deg, shins vertical, body lowered {drop:.2f} px so feet stay down; stand restores")
    check(s["notes"] and "approximate" in s["notes"][0]["sit_approximation"]["note"],
          "the plan reports sitting as an approximation (with the seat height for the scene)")
    ok, msg = fails([{"actor": "z", "do": "sit", "t": 1}, {"actor": "z", "do": "walk", "t": 2, "dur": 1, "dx": 50}], "seated")
    check(ok, f"walking while seated is refused ({msg})")

    print("\n== C9 the validator catches broken KeyLists")
    base = copy.deepcopy(a)

    def tampered(fn):
        x = copy.deepcopy(base)
        fn(x)
        return validate_keylist(x)
    i = next(i for i, k in enumerate(base["keys"]) if k["df"] > 3 and k["part"] == "legL")
    for desc, fn, needle in (
        ("an overlapping key", lambda x: x["keys"].insert(i + 1, dict(x["keys"][i], f=x["keys"][i]["f"] + 1,
                                                                        t=round((x["keys"][i]["f"] + 1) / 30, 6))), "overlap"),
        ("a broken 'from' (discontinuity)", lambda x: x["keys"][i].update({"from": 99}), "discontinuity"),
        ("unsorted keys", lambda x: x["keys"].reverse(), "not sorted"),
        ("an unknown part", lambda x: x["keys"][i].update(part="tail"), "not allowed"),
        ("a tweened mouth", lambda x: next(k for k in x["keys"] if k["part"] == "mouth").update(df=3, dur=0.1), "discrete"),
        ("a key off the frame grid", lambda x: x["keys"][i].update(t=x["keys"][i]["t"] + 0.01), "frame grid"),
        ("a key past the end", lambda x: x["keys"][-1].update(df=9999), "after the timeline"),
        ("hairBack on short hair", lambda x: x["actors"][0]["spec"].update(hair="short_man"), "no long hair"),
    ):
        probs = tampered(fn)
        check(any(needle in p for p in probs), f"detected: {desc} ({next((p for p in probs if needle in p), probs[:1])})")

    print("\n== C10 contracts")
    sch = json.loads((PKG / "schema" / "action_script.v1.json").read_text(encoding="utf-8"))
    kls = json.loads((PKG / "schema" / "keylist.v1.json").read_text(encoding="utf-8"))
    check(sorted(sch["properties"]["actions"]["items"]["properties"]["do"]["enum"]) == sorted(ACTIONS),
          "action_script.v1.json lists exactly the planner's actions")
    check(set(kls["properties"]["keys"]["items"]["required"]) == KY.KEY_FIELDS and
          sorted(kls["properties"]["keys"]["items"]["properties"]["ease"]["enum"]) == sorted(KY.EASES) and
          kls["properties"]["actors"]["items"]["properties"]["spec"]["required"] == sorted(PROFILE_SPEC()),
          "keylist.v1.json matches the key fields, eases and the 18 rig spec fields")
    cat = json.loads((PKG / "parts" / "flat_cartoon_v2.json").read_text(encoding="utf-8"))
    check(PROFILE["builds"] == cat["builds"] and PROFILE["outfits"] == cat["outfits"] and
          sorted(PROFILE["hair"] + list(PROFILE["hair_aliases"])) == sorted(cat["hair"]) and
          list(PROFILE["expressions"]) == cat["expressions"],
          "the animation profile agrees with the C1 style catalogue (builds, outfits, hair, expressions)")
    check(all(abs(KY.EASES[e](0)) < 1e-12 and abs(KY.EASES[e](1) - 1) < 1e-12 for e in KY.EASES),
          f"all {len(KY.EASES)} eases start at 0 and end at 1")

    print("\n== C11 audit fixes: validation, identity, fps, walk/re-entry behaviour")
    for fps in (24, 25, 60):
        ok, msg = fails([{"actor": "z", "do": "nod", "t": 1}], "only", fps=fps)
        check(ok, f"fps {fps} is refused with a clear reason ({msg[:95]})")
    check(run([{"actor": "z", "do": "wave", "t": 1}], fps=30)["fps"] == 30, "fps 30 is accepted (the default wave fits)")

    def edited(fn, resign=True):
        x = copy.deepcopy(a)
        fn(x)
        if resign:
            try:
                x["digest"] = KY.digest(x)
            except ValueError:
                pass            # non-finite numbers cannot be canonical JSON: the validator must still answer
        return validate_keylist(x)
    for desc, fn, needle in (
        ("an empty eye colour (would fall back to Kim's)", lambda x: x["actors"][0]["spec"].update(eyeColor=""), "eyeColor"),
        ("a null skin", lambda x: x["actors"][0]["spec"].update(skin=None), "skin"),
        ("an upper-case colour", lambda x: x["actors"][0]["spec"].update(top="#ABCDEF"), "top"),
        ("a missing spec field", lambda x: x["actors"][0]["spec"].pop("lip"), "missing rig field"),
        ("x as a string", lambda x: x["actors"][0].update(x="760"), "x must be"),
        ("y = NaN", lambda x: x["actors"][0].update(y=float("nan")), "y must be"),
        ("scale 0", lambda x: x["actors"][0].update(scale=0), "scale must be"),
        ("scale 1e6", lambda x: x["actors"][0].update(scale=1e6), "scale must be"),
        ("an actor id with markup", lambda x: x["actors"][0].update(id="<b>"), "id must match"),
        ("actor id __proto__", lambda x: x["actors"][0].update(id="__proto__"), "id must match"),
        ("a dom_id with a quote", lambda x: x["actors"][0].update(dom_id='a" onclick="x'), "dom_id must match"),
        ("a forged fingerprint", lambda x: x["actors"][0].update(fingerprint="f" * 64), "does not belong"),
        ("a swapped identity colour", lambda x: x["actors"][0]["spec"].update(skin="#d99a73"), "does not belong"),
        ("a non-numeric value", lambda x: next(k for k in x["keys"] if k["prop"] == "--r").update(val="1"), "finite number"),
        ("a bad visible value", lambda x: next(k for k in x["keys"] if k["prop"] == "visible").update(val=2), "0 or 1"),
    ):
        probs = edited(fn)
        check(any(needle in p_ for p_ in probs), f"validator refuses {desc} ({next((p_ for p_ in probs if needle in p_), probs[:1])})")
    check(any("digest does not match" in p_ for p_ in edited(lambda x: x["actors"][0].update(x=761), resign=False))
          and any("digest missing" in p_ for p_ in edited(lambda x: x.pop("digest"), resign=False)),
          "an edit without a new digest, or a missing digest, is refused")
    check(KY.spec_fingerprint(a["actors"][0]["spec"]) == json.loads((PKG / "examples" / "demo-cast" / "cast.lock.json")
                                                                    .read_text(encoding="utf-8"))["characters"]["zahra"],
          "the fingerprint recomputed from the rig spec equals cast.lock.json (C1's own fingerprint function)")
    check(KY.canonical({"a": 4.0, "b": [1.5, -0.0, 2]}) == '{"a":4,"b":[1.5,0,2]}',
          "canonical JSON writes integral numbers as integers (same bytes as the JavaScript runtime)")
    for desc, actor, needle in (("an actor id with markup", {"id": "<x>", "cast": CAST, "character": "zahra"}, "must match"),
                                ("x = NaN", {"id": "z", "cast": CAST, "character": "zahra", "x": float("nan")}, "x, y must be"),
                                ("scale 50", {"id": "z", "cast": CAST, "character": "zahra", "scale": 50}, "scale in")):
        ok, msg = fails([], needle, actors=[actor])
        check(ok, f"planner refuses {desc} ({msg[:90]})")

    pose = run([{"actor": "z", "do": "lean", "t": 0.5, "deg": 8}, {"actor": "z", "do": "turn", "t": 0.5, "deg": 10},
                {"actor": "z", "do": "arm", "t": 0.5, "side": "R", "r": -60, "fore": -20},
                {"actor": "z", "do": "walk", "t": 1.5, "dur": 1.2, "dx": 100}])
    end = pose["frames"]
    check(at(pose, "z", "torso", "--r", end) == 8 and at(pose, "z", "head", "--r", end) == 10 and
          at(pose, "z", "armR", "--r", end) == -60 and at(pose, "z", "legL", "--r", end) == 0 and jumps(pose) == [],
          "after a walk the earlier lean, head tilt and raised arm are resumed (legs back at rest, no jump)")
    re_ = run([{"actor": "z", "do": "walk", "t": 0.5, "dur": 1.2, "dx": 200},
               {"actor": "z", "do": "exit", "t": 2.5, "style": "walk", "dx": 800, "dur": 2},
               {"actor": "z", "do": "enter", "t": 5, "style": "walk", "from_dx": 900, "dur": 2}], duration=8)
    check(at(re_, "z", "self", "--x", re_["frames"]) == 200 and jumps(re_) == [],
          "re-entering with a walk arrives where the character stood before it exited (x 200), not off-stage")
    short = run([{"actor": "k", "do": "walk", "t": 1, "dur": 6.6, "dx": 300}], duration=7.8,
                actors=[{"id": "k", "cast": CAST, "character": "karim"}])
    ok, msg = fails([{"actor": "z", "do": "walk", "t": 1, "dur": 6.6, "dx": 300}], "settle", duration=7.8)
    check(validate_keylist(short) == [] and ok,
          "settle room depends on hair: short hair needs 6 frames after a walk, long hair 16 (refused when missing)")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL ANIMATION TESTS PASSED" if not f else "ANIMATION TESTS FAILED"))
    sys.exit(1 if f else 0)


def PROFILE_SPEC():
    from character.adapter import RIG_SPEC_FIELDS
    return RIG_SPEC_FIELDS


if __name__ == "__main__":
    main()
