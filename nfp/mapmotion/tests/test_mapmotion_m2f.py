#!/usr/bin/env python3
"""M2f - Map Motion labels (no browser here; test_mapmotion_m2f_render.py measures and renders in Chromium): placement
checked by geometry, independently of the placer - no label overlaps another label, a marker or a drawn route; every
label inside the screen; stable when nothing moves; hidden (and reported) only when there is no room; direction of
Persian / English / mixed text; labels change no geometry, timing or camera value. Offline. SYNTHETIC data and
synthetic metrics (the real ones come from measure.py).

  python3 nfp/mapmotion/tests/test_mapmotion_m2f.py
"""
import datetime
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import camera as CAM            # noqa: E402
from mapmotion import labels as LB             # noqa: E402
from mapmotion import render as R              # noqa: E402
from test_location_l1c import loc              # noqa: E402
from test_location_l1a import doc as ldoc      # noqa: E402

RESULTS = []
TODAY = datetime.date(2026, 11, 25)
NSP = "{http://www.w3.org/2000/svg}"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def named(i, lat, lon, fa, en):
    return loc(i, lat, lon, names=[{"text": fa, "lang": "fa", "type": "current"}, {"text": en, "lang": "en", "type": "current"}])


PLACES = [("teh", 35.6892, 51.3890, "تهران", "Tehran"), ("qom", 34.6416, 50.8746, "قم", "Qom"), ("isf", 32.6546, 51.6680, "اصفهان", "Isfahan"),
          ("kas", 33.9850, 51.4100, "کاشان ۱۴۰۵", "Kashan"), ("shi", 29.5918, 52.5837, "شیراز", "Shiraz"),
          ("ban", 27.1832, 56.2666, "بندر عباس", "Bandar Abbas"), ("yaz", 31.8974, 54.3569, "یزد (Yazd)", "Yazd"),
          ("ker", 30.2839, 57.0834, "ایستگاه A12 کرمان & <x>", "Kerman")]


def setup(window=180, extra_points=(), camera=None, scene_extra=None, metrics_fn=None, mode="draft", year_lang="fa"):
    locs = ldoc(*[named(*p) for p in PLACES])
    ids = [p[0] for p in PLACES]
    md = {"schema": "nfp.mapmotion/1", "id": "label-map", "mode": "draft", "window": {"start": 0, "end": window},
          "labels": {"lang": year_lang, "year": None, "fallback": ["en"]}, "viewport": {"fit": {"locations": ids, "pad_deg": 1.0}},
          "points": [{"id": p, "location": p, "start": 0, "end": window} for p in ids] + list(extra_points),
          "routes": [{"id": "r", "stops": ["teh", "isf", "shi", "ban"], "start": 10, "end": 120, "samples": 16}], "areas": []}
    plan = M.build(md, locs, today=TODAY)
    geo = M.geometry(plan)
    scene = {"schema": "nfp.mapmotion.scene/1", "id": "label-scene", "map": "label-map", "mode": mode,
             "animation": {"routes": {"r": {"marker": "plane"}}}}
    if camera:
        scene["camera"] = camera
    scene.update(scene_extra or {})
    sp0 = M.resolve(scene, plan, geo)
    metrics = None
    if metrics_fn:
        st = sp0["labels"]["style"]
        metrics = {"schema": "nfp.mapmotion.labelmetrics/1", "browser": "synthetic", "fonts": {},
                   "items": [{"text": t["text"], "size": st["size"], "weight": st["weight"], "direction": t["direction"],
                              **metrics_fn(t["text"], st["size"])} for t in sp0["labels"]["texts"].values()]}
    return plan, geo, scene, M.resolve(scene, plan, geo, metrics=metrics)


SYN = lambda text, size: {"width": 0.55 * size * len(text), "ascent": 1.05 * size, "descent": 0.55 * size}


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def seg_box(p, q, b, n=200):
    """Independent test: sample the segment densely and see if any sample is strictly inside the box."""
    return any(b[0] < p[0] + (q[0] - p[0]) * i / n < b[2] and b[1] < p[1] + (q[1] - p[1]) * i / n < b[3] for i in range(n + 1))


def audit(sp, plan):
    """Independent geometric audit of every placed label, every frame and the static map. Returns problem counts."""
    W, H = sp["frame"]["width"], sp["frame"]["height"]
    probs = {"label_label": 0, "label_marker": 0, "label_route": 0, "off_screen": 0, "placed": 0}
    shots = [(None, sp["labels"]["static"])] + [(f["frame"], f["labels"]) for f in sp["labels"]["frames"]]
    for frame, rows in shots:
        if frame is None:
            st = {"cx": W / 2, "cy": H / 2, "zoom": 1.0}
            op = {p["id"]: 1.0 if p["show"] else 0.0 for p in sp["points"]}
            drawn = [[(v["x"], v["y"]) for v in pc] for r in sp["routes"] for pc in r["pieces"]]
            heads = [(r["pieces"][-1][-1]["x"], r["pieces"][-1][-1]["y"]) for r in sp["routes"]]
        else:
            i = frame - plan["window"]["start"]
            cf = sp["camera"]["frames"][i]
            st = {"cx": cf["cx"], "cy": cf["cy"], "zoom": cf["zoom"]}
            an = sp["animation"]["frames"][i]
            op = {x["id"]: x["opacity"] for x in an["points"]}
            drawn = [R._prefix(pc, s) for r, ra in zip(sp["routes"], an["routes"]) for pc, s in zip(r["pieces"], ra["pieces"])]
            heads = [(ra["head"]["x"], ra["head"]["y"]) for ra in an["routes"] if ra["head"]]
        boxes = [(x["box"][0], x["box"][1], x["box"][0] + x["box"][2], x["box"][1] + x["box"][3]) for x in rows if x["shown"]]
        probs["placed"] += len(boxes)
        mks = []
        for p in sp["points"]:
            if op.get(p["id"], 0) > 0 and p["show"] and p["marker"] != "none":
                for x in p["x"]:
                    X, Y = CAM.to_screen(st, sp["frame"], x, p["y"])
                    mks.append(LB.marker_box(p["marker"], X, Y, p["size"]))
        for hx, hy in heads:
            X, Y = CAM.to_screen(st, sp["frame"], hx, hy)
            mks.append((X - 10, Y - 10, X + 10, Y + 10))
        segs = []
        for path in drawn:
            ps = [CAM.to_screen(st, sp["frame"], x, y) for x, y in path]
            segs += list(zip(ps, ps[1:]))
        for i, b in enumerate(boxes):
            probs["label_label"] += sum(overlap(b, c) for c in boxes[i + 1:])
            probs["label_marker"] += sum(overlap(b, m) for m in mks)
            probs["label_route"] += any(seg_box(p, q, b) for p, q in segs)
            probs["off_screen"] += not (b[0] >= 8 - 1e-6 and b[1] >= 8 - 1e-6 and b[2] <= W - 8 + 1e-6 and b[3] <= H - 8 + 1e-6)
    return probs


def main():
    print("== direction of the text")
    for s, d in (("تهران", "rtl"), ("Tehran", "ltr"), ("یزد (Yazd)", "rtl"), ("London (لندن)", "ltr"), ("۱۴۰۵", "ltr"),
                 ("2026 تهران", "rtl"), ("ایستگاه A12", "rtl"), ("", "ltr"), ("۲۰۲۶ Tehran", "ltr"), ("(۱۴۰۵) کاشان", "rtl")):
        check(LB.direction(s) == d, f"{s!r}: {d} (first strong character)")

    print("\n== placement: no overlap with labels, markers, drawn routes; inside the screen")
    cam = {"keyframes": [{"frame": 0, "view": {"full": True}}, {"frame": 90, "view": {"points": ["teh", "qom", "kas"], "pad_px": 160}},
                         {"frame": 150, "view": {"full": True}}]}
    plan, geo, scene, sp = setup(camera=cam, metrics_fn=SYN)
    pr = audit(sp, plan)
    check(pr["placed"] > 500, f"{pr['placed']} labels placed over the static map and 180 frames (camera zoom in and out, route drawn)")
    for k in ("label_label", "label_marker", "label_route", "off_screen"):
        check(pr[k] == 0, f"independent audit: {k.replace('_', ' / ')} problems: {pr[k]}")
    check(sp["labels"]["static"][0]["pos"] == "E", "the first point (highest priority) takes its first choice, E, on the static map")
    pairs = [(x["id"], x["pos"]) for x in sp["labels"]["static"] if x["shown"]]
    check(len(pairs) == len(PLACES), f"static map: all {len(PLACES)} labels placed {pairs}")
    sp_still = setup(metrics_fn=SYN)[3]
    seqs = {}
    for f in sp_still["labels"]["frames"]:
        for x in f["labels"]:
            if x["shown"]:
                seqs.setdefault(x["id"], []).append(x["pos"])
    moves = sum(sum(1 for a, b in zip(v, v[1:]) if a != b) for v in seqs.values())
    pr2 = audit(sp_still, plan)
    # independent: a label may change place only if its previous place is blocked in the new frame
    W_, H_ = sp_still["frame"]["width"], sp_still["frame"]["height"]
    unjust = 0
    frames_ = sp_still["labels"]["frames"]
    for fa, fb in zip(frames_, frames_[1:]):
        pa = {x["id"]: x for x in fa["labels"] if x["shown"]}
        rows_b = [x for x in fb["labels"] if x["shown"]]
        for k_, x in enumerate(rows_b):
            if x["id"] in pa and pa[x["id"]]["pos"] != x["pos"]:
                old = pa[x["id"]]["box"]
                ob = (old[0], old[1], old[0] + old[2], old[1] + old[3])
                i = fb["frame"] - plan["window"]["start"]
                an = sp_still["animation"]["frames"][i]
                segs = [s_ for r_, ra in zip(sp_still["routes"], an["routes"]) for pc, sh in zip(r_["pieces"], ra["pieces"])
                        for path in [R._prefix(pc, sh)] for s_ in zip(path, path[1:])]
                higher = [(y["box"][0], y["box"][1], y["box"][0] + y["box"][2], y["box"][1] + y["box"][3]) for y in rows_b[:k_]]
                head = an["routes"][0]["head"]
                blocked = any(seg_box(p_, q_, ob) for p_, q_ in segs) or any(overlap(ob, h_) for h_ in higher) or \
                          (head and overlap(ob, (head["x"] - 10, head["y"] - 10, head["x"] + 10, head["y"] + 10)))
                unjust += not blocked
    check(pr2["label_route"] == 0 and moves > 0 and unjust == 0,
          f"fixed camera, the route drawn over 110 frames: {moves} label moves, each one because its old place became blocked ({unjust} without reason)")
    tight = {"keyframes": [{"frame": 0, "view": {"center": {"lat": 35.6892, "lon": 51.389}, "zoom": 20}}]}
    sp_t = setup(camera=tight, metrics_fn=SYN)[3]
    off = [x for f in sp_t["labels"]["frames"] for x in f["labels"] if x.get("offscreen")]
    check(off and not [i for i in sp_t["qc"]["issues"] if i["code"] == "label_hidden" and i.get("element") in {x["id"] for x in off}],
          "points the camera does not show: no label, and not reported as hidden")
    crowd = [{"id": f"c{i}", "location": "teh", "start": 0, "end": 180} for i in range(14)]
    sp_c = setup(extra_points=crowd, metrics_fn=SYN)[3]
    hid = [i for i in sp_c["qc"]["issues"] if i["code"] == "label_hidden"]
    pr3 = audit(sp_c, plan)
    check(hid and pr3["label_label"] == 0 and pr3["label_marker"] == 0, f"14 more labels on Tehran: the ones without room are hidden and reported ({len(hid)} warnings), still no overlap")

    print("\n== settings, metrics, QC")
    sp_off = setup(scene_extra={"show": {"labels": False}}, metrics_fn=SYN)[3]
    check(not sp_off["labels"]["static"] and all(not f["labels"] for f in sp_off["labels"]["frames"]), "show.labels false: no label anywhere")
    sp_one = setup(scene_extra={"points": {"teh": {"label": False}}}, metrics_fn=SYN)[3]
    check("teh" not in [x["id"] for x in sp_one["labels"]["static"]] and "qom" in [x["id"] for x in sp_one["labels"]["static"]], "a point's own label: false")
    sp_est = setup()[3]
    est = [i for i in sp_est["qc"]["issues"] if i["code"] == "label_metrics_estimated"]
    check(est and est[0]["level"] == "warning" and not any(t["measured"] for t in sp_est["labels"]["texts"].values()),
          "without a measurement: estimated sizes, a warning in draft")
    sp_fin = setup(mode="final")[3]
    check(any(i["code"] == "label_metrics_estimated" and i["level"] == "error" for i in sp_fin["qc"]["issues"]), "...and an error in final")
    st = setup(metrics_fn=SYN)[3]["labels"]["style"]
    check(st["size"] == 22 and st["weight"] == 400 and st["font_family"] == "Vazirmatn, Inter, sans-serif" and st["halo_color"] == M.PRESETS["documentary-light"]["colors"]["background"],
          "defaults: 22 px, weight 400, Vazirmatn then Inter, halo in the map's background colour")
    sp_cfg = setup(scene_extra={"labels": {"size": 30, "weight": 700, "halo": {"color": "#000000", "width": 5}, "padding": 6, "offset": 10}}, metrics_fn=SYN)[3]
    s2 = sp_cfg["labels"]["style"]
    b = sp_cfg["labels"]["static"][0]["box"]
    check(s2["size"] == 30 and s2["weight"] == 700 and s2["halo_color"] == "#000000" and abs(b[3] - (1.6 * 30 + 2 * (6 + 2.5))) < 1e-6,
          "size, weight, halo and padding set; box height = ascent + descent + 2 (padding + halo / 2)")
    for cfg, what in (([], "not an object"), ({"font": "Arial"}, "an unknown key"), ({"size": 4}, "size 4"), ({"weight": 500}, "weight 500 (no such font file)"),
                      ({"halo": {"color": "white"}}, "a colour name"), ({"offset": -1}, "offset -1")):
        sp_b = setup(scene_extra={"labels": cfg})[3]
        check(any(i["code"] == "labels" and i["level"] == "error" for i in sp_b["qc"]["issues"]), f"refused: labels {what}")
    _, _, sc, _ = setup()
    plan_, geo_ = setup()[0:2]
    bad = M.resolve(sc, plan_, geo_, metrics={"schema": "x"})
    check(any(i["code"] == "labels" for i in bad["qc"]["issues"]), "a metrics document of the wrong schema: refused")

    print("\n== labels change nothing else; determinism; drawing")
    a = setup(camera=cam, metrics_fn=SYN)[3]
    b2 = setup(camera=cam, scene_extra={"show": {"labels": False}}, metrics_fn=SYN)[3]
    strip = lambda s: {k: v for k, v in s.items() if k not in ("labels", "qc", "points")}
    check(json.dumps(strip(a), sort_keys=True) == json.dumps(strip(b2), sort_keys=True),
          "geometry, routes, camera and animation are the same with and without labels")
    check(json.dumps(a["labels"], sort_keys=True) == json.dumps(setup(camera=cam, metrics_fn=SYN)[3]["labels"], sort_keys=True), "deterministic")
    svg = R.render_svg(a, plan, 90, font_css="@font-face{font-family:Test}")
    root = ET.fromstring(svg)
    texts = root.findall(f".//{NSP}g[@id='labels']/{NSP}text")
    row = {x["id"]: x for x in a["labels"]["frames"][90]["labels"] if x["shown"]}
    check(len(texts) == len(row) and all(t.get("text-anchor") == "middle" and t.get("paint-order") == "stroke" for t in texts),
          f"frame 90: one <text> per placed label ({len(texts)}), centred, halo under the text")
    ker = [t for t in root.iter(NSP + "text") if t.get("data-label") == "ker"]
    check((not ker or (ker[0].text == "ایستگاه A12 کرمان & <x>" and ker[0].get("direction") == "rtl")) and "&amp; &lt;x&gt;" in R.render_svg(a, plan, None),
          "special characters escaped (& <), direction rtl")
    check(root.find(f"{NSP}defs/{NSP}style") is not None and "@font-face" in root.find(f"{NSP}defs/{NSP}style").text, "the font CSS is embedded in the SVG")
    t0 = [t for t in texts if t.get("data-label") == "teh"]
    check(t0 and abs(float(t0[0].get("x")) - row["teh"]["x"]) < 1e-3 and abs(float(t0[0].get("y")) - row["teh"]["y"]) < 1e-3, "the text is drawn where it was placed")

    print("\n== boundaries")
    for f in ("labels.py",):
        t = (NFP / "mapmotion" / f).read_text(encoding="utf-8")
        mods = {a_ or b_ for a_, b_ in re.findall(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", t, re.M)}
        check(mods <= {"math", "unicodedata", ".", ".render", ".scene"}, f"{f} imports only the standard library and mapmotion {sorted(mods)}")
        check(not re.search(r"urllib|socket|subprocess|write_text|open\(|date\.today|import random|random\.", t), f"{f}: no network, process, files, clock, randomness")
    t = (NFP / "mapmotion" / "tools" / "measure.py").read_text(encoding="utf-8")
    check("subprocess" in t and not re.search(r"urllib|socket|https?://(?!www\.w3\.org/2000/svg)|npm |pip install", t),
          "tools/measure.py (outside the engine core): the only module that runs a program (local node + playwright); no network, no download (the SVG namespace URL is not a request)")
    rd = (NFP / "mapmotion" / "README.md").read_text(encoding="utf-8")
    check(not (NFP / "mapmotion" / "measure.py").exists() and all(k_ in rd for k_ in ("M2f", "tools/measure.py", "Vazirmatn", "label_hidden", "label_metrics_estimated", "rtl")), "README documents M2f")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2f TESTS PASSED" if not f else "MAP MOTION M2f TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
