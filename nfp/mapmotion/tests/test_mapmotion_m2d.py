#!/usr/bin/env python3
"""M2d - Map Motion animation data: routes drawn over time on M1's timing with a moving marker, points / areas
appearing (cut / fade), one state per video frame. Checked by properties: the drawn distance never goes back and
reaches every stop exactly at M1's stop frame, the tip lies on the drawn line at its drawn share of the pixel length,
the heading is the line's direction, a seam crossing moves the tip to the other piece. Offline. SYNTHETIC data.

  python3 nfp/mapmotion/tests/test_mapmotion_m2d.py
"""
import datetime
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def errs(sp):
    return [i for i in sp["qc"]["issues"] if i["level"] == "error"]


def seg_dist(px, py, a, b):
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - a["x"]) * dx + (py - a["y"]) * dy) / L))
    return math.hypot(px - a["x"] - t * dx, py - a["y"] - t * dy), t


def main():
    locs = ldoc(loc("a", 10.5, 20.5), loc("b", 14.5, 28.5), loc("c", 9.5, 34.5), loc("w", 1.5, 178.5), loc("e", 2.5, -178.5))
    md = {"schema": "nfp.mapmotion/1", "id": "anim-map", "mode": "draft", "window": {"start": 0, "end": 300},
          "labels": {"lang": "en", "year": None}, "viewport": {"bounds": {"north": 80, "south": -80, "west": -180, "east": 180}},
          "points": [{"id": "pa", "location": "a", "start": 10, "end": 200, "label": False}, {"id": "pb", "location": "b", "start": 40, "end": 300, "label": False},
                     {"id": "pc", "location": "c", "start": 0, "end": 300, "label": False}],
          "routes": [{"id": "r3", "stops": ["a", "b", "c"], "start": 30, "end": 150, "samples": 16},
                     {"id": "rs", "stops": ["w", "e"], "start": 100, "end": 220, "samples": 16}],
          "areas": [{"id": "ar", "location": "b", "source": "uncertainty", "start": 50, "end": 250}]}
    locs["locations"][1]["uncertainty_m"] = 40000
    locs["locations"][1]["precision"] = "approximate"
    plan = M.build(md, locs, today=TODAY)
    geo = M.geometry(plan)
    check(plan["qc"]["status"] != "FAIL" and not [i for i in geo["issues"] if i["level"] == "error"], "synthetic plan and geometry are usable")
    scene = {"schema": "nfp.mapmotion.scene/1", "id": "anim-scene", "map": "anim-map"}

    def run(anim, **extra):
        return M.resolve(dict(scene, animation=anim, **extra), plan, geo)

    print("== the drawn distance follows M1's timing")
    for ez in ("linear", "in-out"):
        sp = run({"routes": {"r3": {"ease": ez, "marker": "plane"}}})
        an = sp["animation"]
        r = next(x for x in plan["routes"] if x["id"] == "r3")
        cum = [0.0]
        for lg in r["legs"]:
            cum.append(cum[-1] + lg["distance_m"])
        ss = {f["frame"]: f["routes"][0]["s_m"] for f in an["frames"]}
        check(not errs(sp) and len(an["frames"]) == 300, f"{ez}: one animation state per frame of the window")
        check(all(ss[f] == 0 for f in range(0, r["start"])) and all(abs(ss[f] - round(cum[-1], 2)) < 0.02 for f in range(r["end"], 300)),
              f"{ez}: nothing drawn before the start frame; fully drawn from the end frame on")
        check(all(ss[f + 1] >= ss[f] for f in range(299)), f"{ez}: the drawn distance never goes back")
        check(all(abs(ss[sfk] - round(cum[k], 2)) < 0.02 for k, sfk in enumerate(r["stop_frames"][:-1])),
              f"{ez}: each stop is reached exactly at M1's stop frame {r['stop_frames']}")
        a, b = r["stop_frames"][0], r["stop_frames"][1]
        inc = [ss[f + 1] - ss[f] for f in range(a, b - 1)]
        if ez == "linear":
            check(max(inc) - min(inc) < 0.05, "linear: constant speed along a leg")
        else:
            check(inc[0] < inc[len(inc) // 2] and inc[-1] < inc[len(inc) // 2], "in-out: slow off the stop and into the next, fast in between")
        fr = [f["routes"][0]["fraction"] for f in an["frames"]]
        check(fr[0] == 0 and fr[-1] == 1 and all(0 <= x <= 1 for x in fr), f"{ez}: fraction 0..1")

    print("\n== pieces and the tip of the line")
    sp = run({"routes": {"r3": {"marker": "plane"}, "rs": {"marker": "ship"}}})
    an = sp["animation"]
    pieces = {r["id"]: r["pieces"] for r in sp["routes"]}
    ok_on, ok_share, ok_head, ok_mono = True, True, True, True
    worst_on = worst_share = worst_head = 0.0
    prev = {}
    for f in an["frames"]:
        for ri, rr in enumerate(f["routes"]):
            pcs = pieces[rr["id"]]
            if any(not 0 <= x <= 1 for x in rr["pieces"]) or any(x < prev.get((rr["id"], k), 0) for k, x in enumerate(rr["pieces"])):
                ok_mono = False
            for k, x in enumerate(rr["pieces"]):
                prev[(rr["id"], k)] = x
            h = rr["head"]
            if h is None:
                continue
            pc = pcs[h["piece"]]
            best = min((seg_dist(h["x"], h["y"], v, w) + (i,) for i, (v, w) in enumerate(zip(pc, pc[1:]))), key=lambda z: z[0])
            worst_on = max(worst_on, best[0])
            i = best[2]
            lens = [math.hypot(w["x"] - v["x"], w["y"] - v["y"]) for v, w in zip(pc, pc[1:])]
            along = sum(lens[:i]) + lens[i] * best[1]
            share = rr["pieces"][h["piece"]]
            if 0 < share < 1:
                worst_share = max(worst_share, abs(along - share * sum(lens)))
                v, w = pc[i], pc[i + 1]
                want = math.degrees(math.atan2(w["y"] - v["y"], w["x"] - v["x"]))
                worst_head = max(worst_head, abs((h["heading_deg"] - want + 180) % 360 - 180))
    check(ok_mono, "every piece's drawn share is 0..1 and never goes back")
    check(worst_on < 0.002, f"the tip lies on its piece of the drawn line (largest distance {worst_on:.2e} px)")
    check(worst_share < 0.01, f"the tip is at the drawn share of the piece's pixel length (largest error {worst_share:.2e} px)")
    check(worst_head < 1e-3, f"heading = the direction of the line at the tip (largest error {worst_head:.2e} degrees)")
    rs_plan = next(x for x in plan["routes"] if x["id"] == "rs")
    heads = [(f["frame"], f["routes"][1]["head"]) for f in an["frames"]]
    pc_seq = [h["piece"] for fr_, h in heads if h]
    W, kx, x0 = plan["frame"]["width"], plan["projection"]["px_per_deg_lon"], (plan["frame"]["width"] - 360 * plan["projection"]["px_per_deg_lon"]) / 2
    check(len(pieces["rs"]) == 2 and pc_seq == sorted(pc_seq) and pc_seq[0] == 0 and pc_seq[-1] == 1,
          "a route over the seam: the tip moves from the first piece to the second, never back")
    sh = [f["routes"][1]["pieces"] for f in an["frames"]]
    check(all(b == 0 or a == 1 for a, b in sh), "the second piece starts only once the first is fully drawn")
    xs = [h["x"] for fr_, h in heads if h]
    jumps = [abs(b - a) for a, b in zip(xs, xs[1:])]
    check(max(jumps) > 0.9 * 360 * kx and sorted(jumps)[-2] < 10, f"its tip jumps once, edge to edge (x0 {x0:.0f}), and moves smoothly otherwise")
    check(all(h is None for fr_, h in heads if fr_ < rs_plan["start"]) and all(h is not None for fr_, h in heads if fr_ >= rs_plan["start"]),
          "the marker appears at the route's start frame and stays (at the last stop) after its end")
    last = heads[-1][1]
    end_pt = pieces["rs"][-1][-1]
    check(abs(last["x"] - end_pt["x"]) < 1e-3 and abs(last["y"] - end_pt["y"]) < 1e-3, "after the end the tip is on the last stop")
    sp_none = run({})
    check(all(rr["head"] is None for f in sp_none["animation"]["frames"] for rr in f["routes"]), "marker 'none' (the default): no tip")
    sp_hidden = run({"routes": {"r3": {"marker": "plane"}}}, routes={"r3": {"show": False}})
    check(all(f["routes"][0]["head"] is None for f in sp_hidden["animation"]["frames"]), "a hidden route has no tip")

    print("\n== points and areas appearing")
    sp = run({"points": {"pa": {"appear": "fade", "fade_frames": 20}}, "areas": {"ar": {"appear": "fade", "fade_frames": 30}}})
    op = lambda pid: [next(p["opacity"] for p in f["points"] if p["id"] == pid) for f in sp["animation"]["frames"]]
    pb = op("pb")
    check(all(pb[f] == 0 for f in range(40)) and all(pb[f] == 1 for f in range(40, 300)), "cut (default): 0 before start, 1 from the start frame")
    pa = op("pa")
    check(pa[9] == 0 and pa[10] == 0.05 and pa[29] == 1 and all(pa[f] == 1 for f in range(29, 180)) and pa[199] == 0.05 and pa[200] == 0,
          "fade 20: 1/20 at the start frame, full after 20 frames, back to 0 at the end frame")
    check(all(pa[f + 1] >= pa[f] for f in range(10, 100)) and all(pa[f + 1] <= pa[f] for f in range(100, 299)), "fade: up, then down, never jumping")
    ar = [f["areas"][0]["opacity"] for f in sp["animation"]["frames"]]
    check(ar[49] == 0 and 0 < ar[50] < ar[60] < ar[80] == 1 and ar[249] > 0 and ar[250] == 0, "area fade 30")
    sp = run({}, points={"pc": {"show": False}})
    check(all(next(p["opacity"] for p in f["points"] if p["id"] == "pc") == 0 for f in sp["animation"]["frames"]), "a hidden point stays at 0")
    sp = run({"defaults": {"appear": "fade", "fade_frames": 10}})
    check(sp["animation"]["points"][0] == {"id": "pa", "appear": "fade", "fade_frames": 10} and not errs(sp), "defaults apply to every element")

    print("\n== errors")
    for anim, what in (([], "not an object"), ({"speed": 1}, "an unknown key"), ({"defaults": {"glow": 1}}, "an unknown default"),
                       ({"routes": {"nope": {}}}, "an unknown route"), ({"points": {"nope": {}}}, "an unknown point"),
                       ({"routes": {"r3": {"ease": "in"}}}, "ease 'in' (routes take linear / in-out)"), ({"routes": {"r3": {"marker": "rocket"}}}, "marker 'rocket'"),
                       ({"routes": {"r3": {"color": "#000000"}}}, "a style key in animation"), ({"points": {"pa": {"appear": "pop"}}}, "appear 'pop'"),
                       ({"points": {"pa": {"appear": "fade", "fade_frames": -1}}}, "fade_frames -1"),
                       ({"points": {"pa": {"appear": "fade", "fade_frames": True}}}, "fade_frames bool"),
                       ({"points": {"pa": {"appear": "fade", "fade_frames": 301}}}, "fade_frames 301"),
                       ({"points": {"pa": {"appear": "fade", "fade_frames": 100}}}, "a fade longer than half of the point's 190 frames"),
                       ({"defaults": {"marker": "rocket"}}, "a bad default marker")):
        sp = run(anim)
        check(sp["qc"]["status"] == "FAIL" and any(i["code"] in ("animation", "unknown_element") for i in errs(sp)), f"refused: {what}")

    print("\n== determinism, compatibility, boundaries")
    a1 = json.dumps(run({"routes": {"r3": {"ease": "in-out", "marker": "plane"}}})["animation"], sort_keys=True)
    check(a1 == json.dumps(run({"routes": {"r3": {"ease": "in-out", "marker": "plane"}}})["animation"], sort_keys=True), "deterministic")
    sp = run({})
    sp_noanim = M.resolve(scene, plan, geo)
    check(json.dumps({k: v for k, v in sp.items() if k != "animation"}, sort_keys=True) == json.dumps({k: v for k, v in sp_noanim.items() if k != "animation"}, sort_keys=True),
          "the animation adds a block and changes nothing else in the scene plan")
    t = (NFP / "mapmotion" / "animate.py").read_text(encoding="utf-8")
    mods = {a_ or b_ for a_, b_ in re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", t, re.M)}
    check(mods <= {"math", ".camera"}, f"animate.py imports only the standard library and mapmotion {sorted(mods)}")
    check(not re.search(r"urllib|socket|subprocess|write_text|open\(|date\.today|import random|random\.", t), "animate.py: no network, files, clock, randomness")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    check(all(k in rd for k in ("M2d", "animation", "fade_frames", "heading_deg", "M2e")), "README documents M2d and the remaining stages")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2d TESTS PASSED" if not f else "MAP MOTION M2d TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
