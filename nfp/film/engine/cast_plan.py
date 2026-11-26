"""NFP Film - characters for a Film page through C1-C3 (no change to C1, C2 or C3).

Project fields (all optional; a project without them gets no character code at all):

  "cast": {"dir": "cast"}                         C1 cast folder inside the project (cast.json + cast.lock.json)
  "characters": [                                 one entry = one character in one shot (DATA, not code)
     {"shot": "street", "actor": "ana", "character": "zahra", "stage": "adult", "wardrobe": "casual",
      "from": 0.3, "to": ["s2", "w", 0],          the shot window (must equal the shot's a / b in shots.js)
      "x": 700, "y": 960, "scale": 0.9, "depth": 0.9, "expr": "neutral", "idle": true, "seed": 7, "detail": 0,
      "actions": [{"do": "walk", "at": ["s1", "w", 3], "dur": 1.5, "dx": 260}, {"do": "nod", "at": 2.0}]}]
  chapters[].sentences[].speaker                  an actor (mouth moves, only inside its own shot) or "narrator"
                                                  (default: nobody's mouth moves)

In shots.js the character is placed where it belongs in the layer order (in front of the set, under the grade):
      K.film.cast(S, "ana")                       inside the build() of the shot named in the entry

Times: a number (s), "end", [sid, "w", i] / [sid, "e", i] (word start / end) or [sid, f] (fraction of a sentence) -
exactly the Director's anchors (D.W / D.We / D.T, snapped to frames), computed from the same timing.
Every instance is planned by the C3 planner (C1 identity lock + visual guard through the C3 adapter) in the shot's
own time, then moved to the shot start; the moved KeyList is re-validated by C3's own validate_keylist. All C3 actions
are available (enter, exit, walk, run, move, blink, breathe, look, turn, nod, arm, arms_rest, wave, point, lean, hop,
shiver, expr, sit, stand); speech ('talk') comes only from the sentence speakers.
Voice rule (legacy, single TTS voice): a speaking character must fit the project's single TTS voice
(studio/engine/characters/voices.json: a 'man' never speaks with a female voice, a 'woman' never with a male one).
With the Voice Engine (voice.engine, V4) each speaker has its own voice (nfp/voice casting); then the rule is: the
sentence audio in <build>/voice/voice_manifest.json was made for the very character whose mouth moves.
"""
import json
import math
from pathlib import Path

from untimed import estimate_untimed

ENGINE = Path(__file__).resolve().parent
FILM = ENGINE.parent
ROOT = FILM.parent.parent
FPS = 30
NARRATOR = "narrator"
HALF = 0.5 / FPS
ENTRY_KEYS = {"shot", "actor", "character", "stage", "wardrobe", "from", "to", "x", "y", "scale", "depth", "expr",
              "idle", "seed", "detail", "actions"}
RUNTIME = ROOT / "nfp" / "character" / "runtime" / "character_runtime.js"
BRIDGE = FILM / "kit" / "55_cast_bridge.js"
VOICES = ROOT / "studio" / "engine" / "characters" / "voices.json"


class CastError(SystemExit):
    pass


def snap(t):
    """The Director's snap (kit/50_director.js: Math.round(t * FPS) / FPS): a half frame goes UP, as in JavaScript -
    Python's round() would go to the even frame (9.35 s = frame 280.5 -> 280, the page 281) and the page would refuse
    the planned shot window."""
    x = t * FPS
    f = math.floor(x)
    return (f + 1 if x - f >= 0.5 else f) / FPS


def page_sentences(timing):
    """The sentences as the page's DATA has them (same rules as compose.py: estimated slots for untimed words)."""
    out = {}
    for s in estimate_untimed(timing)["sentences"]:
        words = []
        for r in s["words"]:
            if r["abs_start"] is not None:
                words.append((r["abs_start"], r["abs_end"]))
            else:
                nxt = next((x["abs_start"] for x in s["words"][r["i"] + 1:] if x["abs_start"] is not None), s["offset"] + s["duration"])
                words.append((round(nxt, 3), round(nxt + 0.06, 3)))
        out[s["id"]] = {"start": s["offset"], "end": round(s["offset"] + s["duration"], 3), "words": words}
    return out


def anchor(x, sents, duration, where):
    """Director anchors: number | 'end' | [sid,'w',i] | [sid,'e',i] | [sid, fraction]."""
    if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x):
        return snap(x)
    if x == "end":
        return snap(duration)
    if isinstance(x, list) and x and x[0] in sents:
        s = sents[x[0]]
        if len(x) == 3 and x[1] in ("w", "e") and isinstance(x[2], int) and 0 <= x[2] < len(s["words"]):
            return snap(s["words"][x[2]][0 if x[1] == "w" else 1])
        if len(x) == 2 and isinstance(x[1], (int, float)) and not isinstance(x[1], bool):
            return snap(s["start"] + (s["end"] - s["start"]) * x[1])
    raise CastError(f"characters: {where}: bad time anchor {x!r} (number, 'end', [sid,'w',i], [sid,'e',i] or [sid, f])")


def local_timing(timing, t0, t1):
    """Word timing of the sentences fully inside [t0, t1], moved to the shot's own time. A shot starts on the frame
    grid, so a sentence (or its first word) may begin up to half a frame before it: such times are clamped to 0
    (otherwise C3 would see a negative start, call the word an invalid interval and leave it without a mouth)."""
    loc = lambda v: None if v is None else round(max(0.0, v - t0), 6)  # noqa: E731
    out = []
    for s in timing["sentences"]:
        if s["offset"] >= t0 - HALF and s["offset"] + s["duration"] <= t1 + HALF:
            out.append({"id": s["id"], "offset": loc(s["offset"]), "duration": s["duration"],
                        "words": [dict(w, abs_start=loc(w["abs_start"]), abs_end=loc(w["abs_end"])) for w in s["words"]]})
    return {"sentences": out}


def shift(kl, f0, frames):
    """Move a KeyList planned in shot time to the video timeline; re-validated by C3 afterwards."""
    from character.animation.keys import digest, ftime
    k2 = {k: v for k, v in kl.items() if k != "digest"}
    k2["keys"] = [dict(k, f=k["f"] + f0, t=ftime(k["f"] + f0, FPS)) for k in kl["keys"]]
    k2["frames"], k2["duration"] = frames, round(frames / FPS, 6)
    k2["lipsync"] = dict(kl["lipsync"], talks=[dict(t, first_frame=t["first_frame"] + f0, last_frame=t["last_frame"] + f0)
                                               for t in kl["lipsync"]["talks"]])
    k2["digest"] = digest(k2)
    return k2


def voice_rule(project, builds):
    v = (project.get("voice") or {}).get("voice")
    cat = json.loads(VOICES.read_text(encoding="utf-8"))
    if v not in cat["voices"]:
        raise CastError(f"characters: the project voice '{v}' is not in {VOICES.relative_to(ROOT)}; a speaking character needs "
                        "a voice whose gender is known")
    g = cat["voices"][v]
    for actor, build in builds.items():
        if g not in cat["build_voice"][build]:
            raise CastError(f"characters: '{actor}' ({build}) would speak with the {g} voice '{v}' - not allowed; "
                            "let the narrator say that sentence")


def fragment(project, chapter, timing, build):
    """(kit_extra JS, page fragment, report) for the project's characters, or ('', '', None) without characters."""
    if not project.get("cast") and not project.get("characters"):
        return "", "", None
    from character.adapter import AdapterError, load_checked
    from character.animation.keys import PlanError, validate_keylist
    from character.animation.script import plan
    pdir = Path(project["_dir"]).resolve()
    cast = project.get("cast") or {}
    d = cast.get("dir")
    if not isinstance(d, str) or not d or Path(d).is_absolute() or ".." in Path(d).parts:
        raise CastError("cast.dir must be a relative folder inside the project")
    cdir = (pdir / d).resolve()
    try:
        load_checked(cdir)                       # C1 lock + visual identity guard, before anything is planned
    except AdapterError as e:
        raise CastError("cast: " + "; ".join(e.problems))
    entries = project.get("characters") or []
    if not isinstance(entries, list) or not entries:
        raise CastError("characters must be a non-empty list when a cast is given")
    duration = float(chapter.get("target_duration") or project["meta"].get("target_duration") or timing["audio"]["total"])
    duration = round(duration * FPS) / FPS
    frames = int(round(duration * FPS))
    sents = page_sentences(timing)
    ids = [s["id"] for s in chapter["sentences"]]
    speakers = {s["id"]: s.get("speaker", NARRATOR) for s in chapter["sentences"]}
    keys_seen, instances, counters, talks_done, builds = set(), [], {}, {}, {}
    for n, e in enumerate(entries):
        w = f"characters[{n}]"
        if not isinstance(e, dict):
            raise CastError(f"{w} must be an object")
        extra = sorted(set(e) - ENTRY_KEYS)
        if extra:
            raise CastError(f"{w}: unknown field(s) {', '.join(extra)}")
        for k in ("shot", "actor", "character", "from", "to", "x", "y"):
            if k not in e:
                raise CastError(f"{w}: '{k}' is required")
        key = e["actor"]
        if key in keys_seen:
            raise CastError(f"{w}: actor '{key}' is used by more than one entry; one entry = one character in one shot "
                            "(use a different actor name per shot, e.g. ana-street, ana-room)")
        keys_seen.add(key)
        t0, t1 = anchor(e["from"], sents, duration, f"{w}.from"), anchor(e["to"], sents, duration, f"{w}.to")
        if not 0 <= t0 < t1 <= duration + 1e-9:
            raise CastError(f"{w}: the window {t0}-{t1}s is empty or outside the video (0-{duration}s)")
        counters[e["character"]] = counters.get(e["character"], 0) + 1
        acts = []
        for j, a in enumerate(e.get("actions") or []):
            if not isinstance(a, dict) or "do" not in a or "at" not in a:
                raise CastError(f"{w}.actions[{j}]: needs 'do' and 'at'")
            if a["do"] == "talk":
                raise CastError(f"{w}.actions[{j}]: speech comes from the sentence speakers, not from actions")
            t = anchor(a["at"], sents, duration, f"{w}.actions[{j}].at")
            if not t0 - 1e-9 <= t < t1:
                raise CastError(f"{w}.actions[{j}]: at {t}s is outside the shot window {t0}-{t1}s")
            x = {k: v for k, v in a.items() if k != "at"}
            x.update(actor=key, t=round(t - t0, 6))
            acts.append(x)
        for sid in ids:
            if speakers[sid] != key:
                continue
            s = sents[sid]
            if not (s["start"] >= t0 - HALF and s["end"] <= t1 + HALF):      # frame grid: half a frame of tolerance
                continue
            acts.append({"actor": key, "do": "talk", "t": round(max(0.0, s["start"] - t0), 6), "sentences": [sid]})
            talks_done[sid] = key
        acts.sort(key=lambda a: a["t"])
        actor = {"id": key, "cast": str(cdir), "character": e["character"], "instance": counters[e["character"]],
                 "x": e["x"], "y": e["y"], "scale": e.get("scale", 1.0), "idle": e.get("idle", True)}
        for k in ("stage", "wardrobe", "expr", "seed", "detail"):
            if k in e:
                actor[k] = e[k]
        doc = {"schema": "nfp.anim.actions/1", "fps": FPS, "duration": round(t1 - t0, 6),
               "stage": {"width": 1920, "height": 1080}, "actors": [actor], "actions": acts}
        try:
            kl = plan(doc, base_dir=str(pdir), timing=local_timing(timing, t0, t1))
        except (PlanError, AdapterError) as err:
            probs = err.problems if hasattr(err, "problems") else [str(err)]
            raise CastError(f"{w} ('{key}' in shot '{e['shot']}'): C3 refused the plan:\n  " + "\n  ".join(map(str, probs)))
        kl = shift(kl, int(round(t0 * FPS)), frames)
        probs = validate_keylist(kl)
        if probs:
            raise CastError(f"{w}: the moved KeyList failed C3 validation: " + "; ".join(probs[:5]))
        builds[key] = kl["actors"][0]["spec"]["build"]
        depth = e.get("depth", 0.9)
        if not (isinstance(depth, (int, float)) and 0 <= depth <= 2):
            raise CastError(f"{w}.depth must be 0..2")
        instances.append({"key": key, "shot": e["shot"], "t0": t0, "t1": t1, "depth": depth, "keylist": kl})
    missing = [sid for sid in ids if speakers[sid] != NARRATOR and sid not in talks_done]
    unknown = sorted({speakers[sid] for sid in ids} - keys_seen - {NARRATOR})
    if unknown:
        raise CastError(f"speaker(s) {', '.join(unknown)} are not characters of this chapter (use 'narrator' or an actor)")
    if missing:
        raise CastError("sentence(s) " + ", ".join(f"{sid} ({speakers[sid]})" for sid in missing) + " are spoken by a character "
                        "that is not on screen for the whole sentence; widen its shot window or let the narrator say it")
    spk = {talks_done[s] for s in talks_done}
    if spk and "engine" in (project.get("voice") or {}):
        # Voice Engine project: every speaker has its own voice, already checked by the Voice casting (warning /
        # override / block). Here only: the audio really was made for the character that moves its mouth.
        import voice_bridge as VB
        made = VB.manifest_speakers(build)
        actor_char = {e["actor"]: e["character"] for e in entries}
        wrong = [f"{sid} (mouth: {talks_done[sid]} = {actor_char[talks_done[sid]]}, audio: {made.get(sid)})"
                 for sid in sorted(talks_done) if made.get(sid) != actor_char[talks_done[sid]]]
        quiet = [sid for sid in ids if speakers[sid] == NARRATOR and made.get(sid) not in (None, NARRATOR)]
        if wrong or quiet:
            raise CastError("characters: the voice audio does not match the speakers - run `run.py voice` again: "
                            + "; ".join(wrong + [f"{s} is narrated but its audio is a character" for s in quiet]))
    elif spk:
        voice_rule(project, {a: builds[a] for a in spk})
    data = {"version": 1, "instances": [{"key": i["key"], "shot": i["shot"], "t0": i["t0"], "t1": i["t1"], "depth": i["depth"]}
                                        for i in instances]}
    kit_extra = ("window.__NFP_FILM_CAST = " + json.dumps(data).replace("<", "\\u003c") + ";\n"
                 + BRIDGE.read_text(encoding="utf-8"))
    rt = RUNTIME.read_text(encoding="utf-8")
    kls = {i["key"]: i["keylist"] for i in instances}
    for s in (rt,):
        if "</script" in s.lower():
            raise CastError("runtime contains '</script'")
    kls_js = json.dumps(kls, ensure_ascii=False).replace("<", "\\u003c")
    frag = ('<script id="nfp-film-c3-runtime">\n' + rt + '\n</script>\n'
            '<script id="nfp-film-cast-mount">\nwindow.K.film.mount(' + kls_js + ');\n</script>\n')
    report = {"summary": f"{len(instances)} instance(s), speakers {sorted(spk) or ['narrator only']}",
              "instances": [{"key": i["key"], "shot": i["shot"], "window": [i["t0"], i["t1"]], "keys": len(i["keylist"]["keys"]),
                             "dom_id": i["keylist"]["actors"][0]["dom_id"], "from_frame": int(round(i["t0"] * FPS)), "fingerprint": i["keylist"]["actors"][0]["fingerprint"],
                             "talks": i["keylist"]["lipsync"]["talks"]} for i in instances],
              "speakers": speakers}
    return kit_extra, frag, report
