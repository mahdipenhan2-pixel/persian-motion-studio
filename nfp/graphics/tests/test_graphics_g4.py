#!/usr/bin/env python3
"""G4 - the animation plan without a browser: only the root / body / clip handles are keyed (never panel, text, rules or a
full-frame background), the root is hidden before and from the clip's end, enter / exit start and end on the right frames,
at least one fully shown frame, every allowed type, wipe / slide directions follow the language (Persian leftwards,
English rightwards) and an explicit direction, pop scales about the extent's centre, keys are chronological per
(handle, property) as the Director requires, the JS is the plan's D.key calls, deterministic.
  python3 nfp/graphics/tests/test_graphics_g4.py
"""
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(HERE)]
import graphics as G                      # noqa: E402
from graphics import animate as A         # noqa: E402
from graphics import render as R          # noqa: E402
from test_graphics_g2 import measured     # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def make(kind="lower-third", display="overlay", lang="fa", anim=None, **kw):
    d = {"schema": "nfp.graphics/1", "id": f"g-{kind}-{lang}", "mode": "final", "lang": lang, "kind": kind,
         "content": {"title": "مریم احمدی" if lang == "fa" else "Maryam Ahmadi", "subtitle": "تاریخ‌نگار" if lang == "fa" else "Historian"}}
    if anim is not None:
        d["animation"] = anim
    d.update(kw)
    r = G.validate(d, display, 90)
    assert r["graphic"], r["issues"]
    sp = r["graphic"]
    return sp, G.layout(sp, measured(sp))


def by(keys, p=None, prop=None):
    return [k for k in keys if (p is None or k["p"].endswith(p)) and (prop is None or k["prop"] == prop)]


def main():
    S, E = 30, 120
    print("== A visibility and frames")
    for t in ("none", "fade", "pop", "wipe", "slide"):
        sp, lay = make(anim={"in": {"type": t, "frames": 12}, "out": {"type": t, "frames": 9}} if t != "none" else {"in": {"type": "none"}, "out": {"type": "none"}})
        keys = A.plan(sp, lay, S, E)
        k = R.key_of(sp["id"])
        handles = {x["p"] for x in keys}
        disp = [(x["frame"], x["value"]) for x in by(keys, prop="display")]
        check(handles <= {f"gx-{k}", f"gx-{k}-body", f"gx-{k}-clipr"} and disp == [(0, "none"), (S, "inline"), (E, "none")],
              f"{t}: only root / body / clip keyed {sorted(h.split(k)[-1] or 'root' for h in handles)}; hidden before {S}, shown {S}..{E - 1}, hidden from {E}")
        anim = [x for x in keys if x["prop"] != "display"]
        if t == "none":
            check(not anim, "none: nothing but the cut in / cut out")
            continue
        ins = [x for x in anim if x["frame"] < S + 12]
        outs = [x for x in anim if x["frame"] >= E - 9]
        check(all(x["frame"] == S for x in ins) and max(x["frame"] + x["frames"] for x in ins) == S + 12
              and min(x["frame"] for x in outs) >= E - 9 and max(x["frame"] + x["frames"] for x in outs) == E
              and len(ins) + len(outs) == len(anim),
              f"{t}: enter keys from frame {S} ending at {S + 12}; exit keys within {E - 9}..{E} (ends exactly at the clip's end)")
        last = {}
        ok = True
        for x in keys:
            kk = (x["p"], x["prop"])
            if kk in last and x["frame"] < last[kk] - 1e-9:
                ok = False
            last[kk] = x["frame"] + x["frames"]
        check(ok, f"{t}: keys are chronological per (handle, property) - no Director overlap")
    sp, lay = make()
    check(by(A.plan(sp, lay, 0, 60), prop="display")[0] == {"p": f"gx-{R.key_of(sp['id'])}", "prop": "display", "frame": 0, "value": "inline", "frames": 0, "ease": None},
          "a clip starting at frame 0: shown from frame 0 (no hidden key first)")
    sp, lay = make(anim={"in": {"type": "fade", "frames": 30}, "out": {"type": "fade", "frames": 30}})
    try:
        A.plan(sp, lay, 0, 60)
        check(False, "enter + exit filling the clip are refused")
    except ValueError:
        check(True, "enter 30 + exit 30 in a 60-frame clip: refused (no fully shown frame)")
    keys = A.plan(sp, lay, 0, 61)
    check(max(x["frame"] + x["frames"] for x in keys if x["frame"] < 30 and x["prop"] != "display") == 30 and min(x["frame"] for x in keys if x["frame"] >= 30 and x["prop"] != "display") == 31,
          "enter 30 + exit 30 in 61 frames: exactly frame 30 fully shown")
    for bad in ((10, 10), (-1, 5), (5, 2.5)):
        try:
            A.plan(sp, lay, *bad)
            check(False, f"clip {bad} refused")
        except ValueError:
            check(True, f"clip frames {bad}: refused")

    print("\n== B directions")
    sp, lay = make(lang="fa", anim={"in": {"type": "wipe", "frames": 10}, "out": {"type": "wipe", "frames": 10}})
    ex = R.extent(sp, lay)
    keys = A.plan(sp, lay, S, E)
    xin = [x for x in by(keys, "-clipr", "--x") if x["frame"] == S]
    check(sp["animation"]["in"]["direction"] == "left" and xin[0]["value"] == round(ex[0] + ex[2], 4) and xin[1]["value"] == 0,
          "Persian wipe in (left): the clip grows from the right edge (--x = right edge x (1 - sx), sx 0 -> 1)")
    xout = [x for x in by(keys, "-clipr", "--x") if x["frame"] == E - 10]
    check(xout[-1]["value"] == round(ex[0] * (1 - 0), 4) and by(keys, "-clipr", "--sx")[-1]["value"] == 0,
          "Persian wipe out (left): hidden from the right towards the left (the left edge stays)")
    sp, lay = make(lang="en", anim={"in": {"type": "wipe", "frames": 10}, "out": {"type": "wipe", "frames": 10}})
    ex = R.extent(sp, lay)
    keys = A.plan(sp, lay, S, E)
    check(sp["animation"]["in"]["direction"] == "right" and by(keys, "-clipr", "--x")[0]["value"] == round(ex[0], 4),
          "English wipe in (right): grows from the left edge")
    for lang, d, sign in (("fa", None, +1), ("en", None, -1), ("fa", "up", None), ("en", "down", None)):
        anim = {"in": dict({"type": "slide", "frames": 12}, **({"direction": d} if d else {})), "out": dict({"type": "slide", "frames": 12}, **({"direction": d} if d else {}))}
        sp, lay = make(lang=lang, anim=anim)
        keys = A.plan(sp, lay, S, E)
        prop = "--y" if d in ("up", "down") else "--x"
        v0 = by(keys, "-body", prop)[0]["value"]
        vend = by(keys, "-body", prop)[-1]["value"]
        want0 = {None: sign * A.SLIDE_PX if sign else None, "up": A.SLIDE_PX, "down": -A.SLIDE_PX}[d]
        check(v0 == want0 and vend == -want0 and not by(keys, "-body", "--y" if prop == "--x" else "--x"),
              f"slide {lang} {d or 'default'}: enters from {v0:+} px along {prop[2:]}, leaves to {vend:+} px (moving {d or sp['animation']['in']['direction']}), the other axis untouched")

    print("\n== C pop pivot, fade values, full frame, JS")
    sp, lay = make(anim={"in": {"type": "pop", "frames": 12}, "out": {"type": "pop", "frames": 12}})
    ex = R.extent(sp, lay)
    cx, cy = ex[0] + ex[2] / 2, ex[1] + ex[3] / 2
    keys = A.plan(sp, lay, S, E)
    s0 = by(keys, "-body", "--s")[0]["value"]
    x0, y0 = by(keys, "-body", "--x")[0]["value"], by(keys, "-body", "--y")[0]["value"]
    check(s0 == A.POP_FROM and abs(x0 - cx * (1 - s0)) < 1e-3 and abs(y0 - cy * (1 - s0)) < 1e-3
          and {x["ease"] for x in by(keys, "-body", "--s") + by(keys, "-body", "--x") if x["frames"]} == {"back.out(1.4)", "back.in(1.4)"},
          f"pop: scale {s0} about the extent's centre ({cx:.0f}, {cy:.0f}): --x / --y = c (1 - s), the same ease as --s")
    sp, lay = make(anim={"in": {"type": "fade", "frames": 9}, "out": {"type": "fade", "frames": 6}})
    op = [(x["frame"], x["value"], x["frames"]) for x in by(A.plan(sp, lay, S, E), "-body", "opacity")]
    check(op == [(S, 0, 0), (S, 1, 9), (E - 6, 1, 0), (E - 6, 0, 6)], f"fade: opacity 0 -> 1 over 9 frames, 1 -> 0 over the last 6 {op}")
    sp, lay = make("title", "fullframe", content={"title": "فصل اول"}, anim={"in": {"type": "slide", "frames": 12}, "out": {"type": "fade", "frames": 9}})
    keys = A.plan(sp, lay, S, E)
    svg = R.render_svg(sp, lay)
    k = R.key_of(sp["id"])
    check(not any(x["p"].endswith("-bg") for x in keys) and svg.index(f'gx-{k}-bg') < svg.index(f'gx-{k}-body'),
          "full frame: the background is outside the body and never keyed (it cuts with the clip)")
    js = A.anim_js(sp, lay, S, E)
    calls = re.findall(r"D\.key\(q\(\"([^\"]+)\"\), \"([^\"]+)\", ([\d.e-]+), ", js)
    check(len(calls) == len(keys) and all(c[0] == x["p"] and c[1] == x["prop"] and abs(float(c[2]) - x["frame"] / 30) < 1e-12 for c, x in zip(calls, keys)),
          f"anim_js: one D.key per planned key, at frame / 30 s ({len(calls)} calls)")
    check(A.anim_js(sp, lay, S, E) == js and A.plan(sp, lay, S, E, key="clip-7")[0]["p"] == "gx-clip-7", "deterministic; a caller-given key names the handles")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G4 TESTS PASSED" if not f else "GRAPHICS G4 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
