"""NFP Graphics - G4: enter / exit animation of a drawn graphic (render.py), with the Director's own primitive only:
D.key(element, property, time, value, duration, ease) (nfp/film/kit/50_director.js - unchanged). Standard library; no
process. Timing is the clip's (the Timeline's): a graphic only animates itself inside its clip's frames.

  plan(spec, lay, start, end, key=None) -> the keys [{p, prop, frame, value, frames, ease}] (plain data, frame-exact)
  anim_js(spec, lay, start, end, key=None) -> JS: those keys as D.key calls on the graphic's data-p handles

The animated handles (render.py): gx-<key> (the root: display), gx-<key>-body (opacity, --x, --y, --s), gx-<key>-clipr
(the clip rectangle = render.extent: --x, --y, --sx, --sy); a counter's number states gx-<key>-count-<j> (display, G7:
the count runs over the enter frames). Nothing else is ever keyed: panel, text, rules, a full-frame background keep their
drawn state. The Director's [data-p] CSS turns --x/--y/--s/--sx/--sy into
translate(x, y) scale(s * sx, s * sy) about the frame origin (0 0), so a scale about a point c is keyed together with
--x = c (1 - s): both use the same ease and duration, which keeps the pivot exact on every frame.

Frames (FPS 30; frame f is at f / 30 s; clip = frames start .. end - 1):
  - the root is display:none before `start` and from `end` on (the graphic never outlives its clip), inline in between;
  - enter over frames start .. start + n_in - 1 (frame start = the first, still hidden / folded state), fully shown
    on from start + n_in; exit over end - n_out .. end - 1 (frame end - n_out = still fully shown); n_in + n_out < clip
    length (graphics.validate checks it), so at least one frame is fully shown;
  none   cut in at start, cut out at end
  fade   body opacity 0 -> 1 / 1 -> 0                                        power1.out / power1.in (the Director's fadeIn / fadeOut)
  pop    body scale 0.6 -> 1 about the extent's centre + opacity (first half)  back.out(1.4) / back.in(1.4): the Director's
         pop eases with back.out(2), whose overshoot (~4 % here, ~8 px on a lower third) would reach the clip's edge; 1.4
         overshoots ~2 %, inside render.CLIP_MARGIN, so the clip never cuts the graphic
  wipe   the clip rectangle grows from 0 (enter) / shrinks to 0 (exit) along `direction`         power1.inOut (the Director's wipe)
  slide  the body moves SLIDE_PX along `direction` + fades, inside its own clip (never outside its area)   power2.out / power2.in
`direction` is where the moving edge goes: "left" = leftwards (G1 default for Persian, the way it reads), "right"
(English), "up", "down". wipe enter "left": revealed from the right edge leftwards; exit "left": hidden from the right
edge leftwards. slide enter "left": comes in from the right moving left; exit "left": leaves moving left.
"""
import json

from .render import extent, key_of

FPS = 30
POP_FROM = 0.6
SLIDE_PX = 60
EASES = {"fade": ("power1.out", "power1.in"), "pop": ("back.out(1.4)", "back.in(1.4)"), "wipe": ("power1.inOut", "power1.inOut"),
         "slide": ("power2.out", "power2.in")}


def _t(f):
    return f / FPS


def plan(spec, lay, start, end, key=None):
    if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end):
        raise ValueError("the clip is frames start .. end - 1 with whole numbers 0 <= start < end")
    a = spec["animation"]
    n_in, n_out = a["in"]["frames"], a["out"]["frames"]
    if n_in + n_out >= end - start:
        raise ValueError(f"enter {n_in} + exit {n_out} frames leave no fully shown frame in a clip of {end - start} frames")
    k = key or key_of(spec["id"])
    root, body, clipr = f"gx-{k}", f"gx-{k}-body", f"gx-{k}-clipr"
    ex = extent(spec, lay)
    cx, cy = ex[0] + ex[2] / 2, ex[1] + ex[3] / 2
    edge = {"left": ex[0], "right": ex[0] + ex[2], "top": ex[1], "bottom": ex[1] + ex[3]}
    keys = []

    def key_(p, prop, frame, value, frames=0, ease=None):
        keys.append({"p": p, "prop": prop, "frame": frame, "value": value, "frames": frames, "ease": ease})

    # visibility: hidden before the clip, shown for its frames, hidden from its end on
    if start > 0:
        key_(root, "display", 0, "none")
    key_(root, "display", start, "inline")

    def side(kind, n, f0, enter):
        """keys of one side: enter (f0 = start) or exit (f0 = end - n)."""
        if kind == "none" or n == 0:
            return
        ease = EASES[kind][0 if enter else 1]
        d = a["in" if enter else "out"]["direction"]
        if kind == "fade":
            key_(body, "opacity", f0, 0 if enter else 1)
            key_(body, "opacity", f0, 1 if enter else 0, n, ease)
        elif kind == "pop":
            s0, s1 = (POP_FROM, 1) if enter else (1, POP_FROM)
            for prop, v0, v1 in (("--s", s0, s1), ("--x", cx * (1 - s0), cx * (1 - s1)), ("--y", cy * (1 - s0), cy * (1 - s1))):
                key_(body, prop, f0, round(v0, 4))
                key_(body, prop, f0, round(v1, 4), n, ease)
            half = max(1, n // 2)
            if enter:
                key_(body, "opacity", f0, 0)
                key_(body, "opacity", f0, 1, half, "power1.out")
            else:
                key_(body, "opacity", f0 + n - half, 1)
                key_(body, "opacity", f0 + n - half, 0, half, "power1.in")
        elif kind == "wipe":
            horiz = d in ("left", "right")
            sc, off = ("--sx", "--x") if horiz else ("--sy", "--y")
            # the fixed edge: enter "left" grows from the right edge, exit "left" keeps the left edge (and so on)
            fixed = {("left", True): "right", ("left", False): "left", ("right", True): "left", ("right", False): "right",
                     ("up", True): "bottom", ("up", False): "top", ("down", True): "top", ("down", False): "bottom"}[(d, enter)]
            e = edge[fixed]
            v0, v1 = (0, 1) if enter else (1, 0)
            key_(clipr, sc, f0, v0)
            key_(clipr, off, f0, round(e * (1 - v0), 4))
            key_(clipr, sc, f0, v1, n, ease)
            key_(clipr, off, f0, round(e * (1 - v1), 4), n, ease)
        elif kind == "slide":
            prop = "--x" if d in ("left", "right") else "--y"
            sign = -1 if d in ("left", "up") else 1                       # the motion's sign along its axis
            v0, v1 = (-sign * SLIDE_PX, 0) if enter else (0, sign * SLIDE_PX)
            key_(body, prop, f0, v0)
            key_(body, prop, f0, v1, n, ease)
            key_(body, "opacity", f0, 0 if enter else 1)
            key_(body, "opacity", f0, 1 if enter else 0, n, "power1.out" if enter else "power1.in")

    side(a["in"]["type"], n_in, start, True)
    side(a["out"]["type"], n_out, end - n_out, False)
    cnt = lay.get("count")
    if cnt:
        # G7 counter: enter frame start + i shows state frames[i]; from start + n on the final value (exactly the data) until
        # the clip's end. The drawing shows the final state and hides the others; consecutive equal frames are one run.
        runs = []
        for i, st_ in enumerate(cnt["frames"]):
            f = start + i
            if runs and runs[-1][0] == st_ and runs[-1][2] == f:
                runs[-1][2] = f + 1
            else:
                runs.append([st_, f, f + 1])
        runs[-1][2] = end
        for st_ in sorted({r[0] for r in runs}):
            p = f"gx-{k}-count-{st_}"
            mine = [r for r in runs if r[0] == st_]
            if st_ == cnt["final"] and mine[0][1] > start:
                key_(p, "display", start, "none")
            for _, f0, f1 in mine:
                key_(p, "display", f0, "inline")
                if f1 < end:
                    key_(p, "display", f1, "none")
    key_(root, "display", end, "none")
    # the Director keys each (element, property) chronologically: order by time, keeping the order above for equal times
    order = {id(x): i for i, x in enumerate(keys)}
    keys.sort(key=lambda x: (x["frame"], order[id(x)]))
    return keys


def anim_js(spec, lay, start, end, key=None):
    """JS for the film page (D = the Director in scope): the plan's keys as D.key calls."""
    k = key or key_of(spec["id"])
    rows = []
    for x in plan(spec, lay, start, end, key=k):
        args = [f'q({json.dumps(x["p"])})', json.dumps(x["prop"]), repr(_t(x["frame"])), json.dumps(x["value"]), repr(_t(x["frames"]))]
        if x["ease"]:
            args.append(json.dumps(x["ease"]))
        rows.append(f"D.key({', '.join(args)});")
    return (f"/* graphic {spec['id']} (nfp/graphics G4): frames {start}..{end - 1}, in {spec['animation']['in']['type']}, "
            f"out {spec['animation']['out']['type']} */\n"
            f"(() => {{ const q = (p) => {{ const e = document.querySelector('[data-p=\"' + p + '\"]'); "
            f"if (!e) throw new Error('graphic part ' + p + ' not found'); return e; }};\n  " + "\n  ".join(rows) + "\n})();\n")
