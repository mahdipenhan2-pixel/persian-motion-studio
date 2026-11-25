#!/usr/bin/env python3
"""M2g - Map Motion on the Film page through nfp/timeline (engine/timeline_bridge.py + mapmotion/filmclip.py), proven on a
real HyperFrames render. Uses the Film test harness read-only (fixtures, compose, synthetic narration).

  python3 nfp/mapmotion/tests/test_mapmotion_m2g_film.py --gsap <local gsap.min.js 3.12.5> --fonts <dir> --work <dir outside repo>

  L legacy   an image-only timeline composes byte-identically with the committed bridge (HEAD) and with this one; a
             project without a timeline is untouched; no map file is written without a map clip
  Q errors   a map clip on an overlay track, without ref, with an asset, a broken bundle, a window that is not the clip,
             a failing plan, a failing scene, missing fonts for labels -> compose stops with a clear message
  P page     in the browser, on EVERY frame of the clip: the map's camera group carries the camera's matrix, exactly one
             frame fragment per layer is shown (none outside the clip), the markers and labels are where the scene plan
             puts them, the local fonts are loaded, no page error, no Director warning
  R render   HyperFrames 1920x1080 30 fps -> ffprobe, verify.py, and the MP4's own pixels: the route drawn up to its tip,
             the plane marker at the tip, label text, the map gone outside its clip
SYNTHETIC data only (map, places, basemap); every file goes to --work, outside the repository.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
ROOT = NFP.parent
FILM = NFP / "film"
sys.path[:0] = [str(FILM / "engine"), str(FILM / "tests"), str(NFP), str(NFP / "location" / "tests"), str(ROOT / "scripts")]
import timeline_bridge as TB                            # noqa: E402
import mapmotion as M                                   # noqa: E402
from mapmotion import camera as CAM                     # noqa: E402
from mapmotion import filmclip as FC                    # noqa: E402
from mapmotion.tools import measure as MS               # noqa: E402
from film_equivalence_check import CDN                  # noqa: E402
from film_render_check import HF_VERSION, BROWSER       # noqa: E402
from film_timeline_check import compose_dir, make_image, sha   # noqa: E402
from test_location_l1c import loc                       # noqa: E402
from test_location_l1a import doc as ldoc               # noqa: E402

RESULTS = []
CLIP = (60, 360)
TODAY = "2026-11-25"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def named(i, lat, lon, fa, en):
    return loc(i, lat, lon, names=[{"text": fa, "lang": "fa", "type": "current"}, {"text": en, "lang": "en", "type": "current"}])


def write_map(d, window=CLIP, scene_edit=None, map_edit=None, fail_location=False):
    """The map clip bundle and its documents in <project>/maps (synthetic)."""
    m = d / "maps"
    m.mkdir(exist_ok=True)
    land = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "land"}, "geometry": {
        "type": "Polygon", "coordinates": [[[44, 24], [63, 24], [63, 40], [44, 40], [44, 24]]]}}]}
    (m / "land.geojson").write_text(json.dumps(land), encoding="utf-8")
    assets = {"schema": "nfp.assets/1", "assets": [{"id": "land", "kind": "map", "local_path": "land.geojson",
              "sha256": hashlib.sha256((m / "land.geojson").read_bytes()).hexdigest(), "width": None, "height": None, "duration": None,
              "source_url": None, "author": "NFP test (synthetic)", "license": "original", "license_url": None, "retrieved_at": TODAY,
              "modifications": "none", "license_verified": True, "attribution": "Synthetic basemap (test)", "restrictions": [], "real_person": False}]}
    (m / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
    places = [("teh", 35.6892, 51.3890, "تهران", "Tehran"), ("isf", 32.6546, 51.6680, "اصفهان", "Isfahan"),
              ("shi", 29.5918, 52.5837, "شیراز", "Shiraz"), ("ban", 27.1832, 56.2666, "بندر عباس", "Bandar Abbas")]
    (m / "locations.json").write_text(json.dumps(ldoc(*[named(*p) for p in places]), ensure_ascii=False), encoding="utf-8")
    ids = [p[0] for p in places]
    md = {"schema": "nfp.mapmotion/1", "id": "film-map", "mode": "draft", "window": {"start": window[0], "end": window[1]},
          "labels": {"lang": "fa", "year": None, "fallback": ["en"]}, "viewport": {"fit": {"locations": ids, "pad_deg": 1.5}},
          "points": [{"id": p, "location": "nowhere" if (fail_location and p == "isf") else p, "start": window[0], "end": window[1]} for p in ids],
          "routes": [{"id": "r", "stops": ["teh", "isf", "shi", "ban"], "start": window[0], "end": window[0] + 210, "samples": 16}],
          "areas": []}
    if map_edit:
        map_edit(md)
    (m / "film.map.json").write_text(json.dumps(md, ensure_ascii=False), encoding="utf-8")
    sc = {"schema": "nfp.mapmotion.scene/1", "id": "film-scene", "map": "film-map", "graticule": {"show": True, "step_deg": 5},
          "basemap": [{"id": "land", "asset": "land", "role": "land"}], "labels": {"size": 26, "weight": 700},
          # a camera that follows the route leg by leg and keeps moving to the clip's end: Film's verify.py flags any
          # stretch of ~2.5 s whose top 84 % (above the caption band) barely changes at 192x108 - a drawn route alone,
          # a map hold or motion only under the captions are "near-static" to it (see README, M2g limits)
          "camera": {"keyframes": [{"frame": window[0], "view": {"full": True}},
                                   {"frame": window[0] + 40, "view": {"points": ["teh", "isf"], "pad_px": 200}, "ease": "linear"},
                                   {"frame": window[0] + 100, "view": {"points": ["isf", "shi"], "pad_px": 200}, "ease": "linear"},
                                   {"frame": window[0] + 175, "view": {"points": ["shi", "ban"], "pad_px": 200}, "ease": "linear"},
                                   {"frame": window[1] - 1, "view": {"full": True}, "ease": "linear"}]},
          "animation": {"routes": {"r": {"marker": "plane", "ease": "in-out"}}}}
    if scene_edit:
        scene_edit(sc)
    (m / "film.scene.json").write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
    (m / "film.clip.json").write_text(json.dumps({"schema": FC.CLIP_SCHEMA, "map": "film.map.json", "locations": "locations.json",
                                                  "scene": "film.scene.json", "assets": "assets.json", "today": TODAY}), encoding="utf-8")


def map_project(work, name, clip_edit=None, image=True, with_map=True, tl_edit=None, **kw):
    """The Film fixture (neutral-en) with a timeline: one map clip (+ a still image after it)."""
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FILM / "tests/fixtures/neutral-en", d)
    write_map(d, **kw)
    (d / "media").mkdir()
    shutil.copyfile(work / "wide.png", d / "media" / "wide.png")
    reg = {"schema": "nfp.assets/1", "assets": [{"id": "wide", "kind": "image", "local_path": "media/wide.png", "sha256": sha(d / "media/wide.png"),
           "width": 3200, "height": 1800, "duration": None, "source_url": None, "author": "NFP test", "license": "original", "license_url": None,
           "retrieved_at": TODAY, "modifications": "none", "license_verified": True, "attribution": "Test media: NFP", "restrictions": [], "real_person": False}]}
    clip = {"id": "map-a", "track": "pictures", "kind": "map", "start": CLIP[0], "end": CLIP[1], "ref": "maps/film.clip.json"}
    if clip_edit:
        clip_edit(clip)
    clips = ([clip] if with_map else []) + ([{"id": "i-a", "track": "pictures", "kind": "image", "start": 380, "end": 440, "asset": "wide", "camera": {"preset": "zoom-in"}}] if image else [])
    tl = {"schema": "nfp.timeline/1", "fps": 30, "duration": 450, "mode": "draft",
          "tracks": [{"id": "pictures", "kind": "visual"}, {"id": "over", "kind": "overlay"}], "clips": clips}
    if tl_edit:
        tl_edit(tl)
    (d / "assets.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    pj = json.loads((d / "project.json").read_text(encoding="utf-8"))
    pj["timeline"] = {"file": "timeline.json", "assets": "assets.json"}
    (d / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def try_compose(d, b, fonts):
    try:
        compose_dir(d, b, fonts)
        return "composed"
    except SystemExit as e:
        return str(e)


def with_bridge(src_text, fn):
    """Run fn with timeline_bridge replaced by the given source (the committed one), then restore."""
    spec = importlib.util.spec_from_loader("timeline_bridge", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(FILM / "engine" / "timeline_bridge.py")
    exec(compile(src_text, mod.__file__, "exec"), mod.__dict__)
    keep = sys.modules.get("timeline_bridge")
    sys.modules["timeline_bridge"] = mod
    try:
        return fn()
    finally:
        sys.modules["timeline_bridge"] = keep


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    ap.add_argument("--browser", default=BROWSER)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    make_image(work / "wide.png", 3200, 1800)
    fonts = Path(a.fonts).resolve()

    print("== L legacy: projects without a map clip")
    head_src = subprocess.run(["git", "show", "HEAD:nfp/film/engine/timeline_bridge.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    t2 = map_project(work, "images-only", with_map=False)           # a T2 timeline: one still image, no map clip
    for label, src in (("image-only timeline (T2)", t2), ("no timeline block", None)):
        if src is None:
            src = work / "projects" / "plain"
            if src.exists():
                shutil.rmtree(src)
            shutil.copytree(FILM / "tests/fixtures/neutral-en", src)
        bo, bn = work / f"b-old-{label[:2]}", work / f"b-new-{label[:2]}"
        with_bridge(head_src, lambda: compose_dir(src, bo, fonts))
        compose_dir(src, bn, fonts)
        same = all((bo / "story" / f).read_bytes() == (bn / "story" / f).read_bytes() for f in ("index.html",)) and \
            sorted(p.relative_to(bo).as_posix() for p in bo.rglob("*") if p.is_file()) == sorted(p.relative_to(bn).as_posix() for p in bn.rglob("*") if p.is_file())
        check(same and not (bn / "mapmotion_qc.json").exists(),
              f"{label}: the page and every file byte-identical with the committed bridge (HEAD) and this one; no map file")

    print("\n== Q errors stop compose")
    cases = [("overlay", dict(clip_edit=lambda c: c.update(track="over")), "overlay track"),
             ("noref", dict(clip_edit=lambda c: c.pop("ref")), "needs ref"),
             ("asset", dict(clip_edit=lambda c: c.update(asset="wide")), None),
             ("window", dict(window=(60, 300)), "must be the same"),
             ("plan", dict(fail_location=True), "plan fails"),
             ("scene", dict(scene_edit=lambda s: s.update(style={"preset": "neon"})), "scene fails")]
    for name, kw, want in cases:
        d = map_project(work, f"q-{name}", **kw)
        msg = try_compose(d, work / f"b-q-{name}", fonts)
        check(msg != "composed" and (want is None or want in msg), f"{name}: stopped - {msg[:110]}")
    second = {"id": "pictures-2", "kind": "visual"}
    over_cases = [("image", {"id": "i-b", "track": "pictures-2", "kind": "image", "start": 100, "end": 160, "asset": "wide", "camera": {"preset": "zoom-in"}}),
                  ("map", {"id": "map-b", "track": "pictures-2", "kind": "map", "start": CLIP[0], "end": CLIP[1], "ref": "maps/film.clip.json"})]
    for kind, extra in over_cases:
        d = map_project(work, f"q-over-{kind}", tl_edit=lambda tl, e=extra: (tl["tracks"].append(second), tl["clips"].append(e)))
        msg = try_compose(d, work / f"b-q-over-{kind}", fonts)
        check("ERROR (timeline)" in msg and "overlap" in msg and "map clip" in msg,
              f"a map clip overlapping {kind} clip on another visual track: stopped - {msg[:110]}")
    d = map_project(work, "q-final", tl_edit=lambda tl: tl.update(mode="final"))
    msg = try_compose(d, work / "b-q-final", fonts)
    check("ERROR (map)" in msg and "final mode" in msg, f"a final timeline with a draft map: stopped - {msg[:110]}")
    d = map_project(work, "q-bundle")
    (d / "maps" / "film.clip.json").write_text(json.dumps({"schema": "nfp.mapmotion.clip/9"}), encoding="utf-8")
    msg = try_compose(d, work / "b-q-bundle", fonts)
    check("ERROR (map)" in msg and "bundle" in msg, f"a broken bundle: stopped - {msg[:100]}")
    nofont = work / "fonts-no-vazir"
    nofont.mkdir()
    for f in fonts.glob("*.woff2"):
        if "vazirmatn" not in f.name:
            shutil.copyfile(f, nofont / f.name)
    d = map_project(work, "q-fonts")
    msg = try_compose(d, work / "b-q-fonts", nofont)
    check("local fonts" in msg and "vazirmatn" in msg, f"labels without the local Vazirmatn files: stopped - {msg[:110]}")

    print("\n== P the page")
    d = map_project(work, "film-map")
    b = work / "b-map"
    proj, ch, timing = compose_dir(d, b, fonts)
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    qc = json.loads((b / "mapmotion_qc.json").read_text(encoding="utf-8"))
    check(page.count('D.shot({ id: "map-map-a"') == 1 and qc["clips"][0]["clip"] == "map-a" and qc["clips"][0]["status"] in ("OK", "WARN")
          and qc["clips"][0]["labels_measured_with"], f"one map shot on the page; QC written next to the build: {qc['clips'][0]['status']} "
                                                      f"{[i['code'] for i in qc['clips'][0]['issues']]}, labels measured with Chromium {qc['clips'][0]['labels_measured_with']}")
    check(page.count("tl-i-a") >= 1, "the image clip after the map is still drawn (T2 path unchanged)")
    # the scene plan the bridge used, rebuilt the same way, for the expectations below
    docs = FC.load("maps/film.clip.json", d)
    import timeline as TL
    words = json.loads((b / "words.json").read_text(encoding="utf-8"))
    prep = FC.prepare(docs, TL.Context.from_words(words), {"start": CLIP[0], "end": CLIP[1]})
    sp = FC.finish(docs, prep, MS.measure(prep["texts"], prep["size"], prep["weight"], b / "story/assets/fonts"))
    ids = {re.search(r'D\.shot\(\{ id: "([^"]+)"', FC.shot_js(sp, prep["plan"], cid)).group(1) for cid in ("a.b", "a_b", "a-b")}
    check(len(ids) == 3, f"clip ids that differ give different shot ids on the page {sorted(ids)}")
    try:
        MS.measure(prep["texts"], prep["size"], prep["weight"], b / "story/assets/fonts", timeout=0.001)
        tmsg = "no error"
    except RuntimeError as e:
        tmsg = str(e)
    check("longer than" in tmsg, f"a measurement that runs out of time stops with a clear message ({tmsg[:70]})")
    rdir = b / "render-copy"
    shutil.copytree(b / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(a.gsap, rdir / "gsap.min.js")
    probe_js = r"""
const { createRequire } = await import("node:module"); const fs = await import("node:fs");
const { chromium } = createRequire(import.meta.url)("playwright");
const [dir, out, a, b] = process.argv.slice(2); const errors = [];
const br = await chromium.launch(); const pg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
pg.on("pageerror", (e) => errors.push(String(e)));
await pg.route("**/*", (r) => r.request().url().startsWith("file:") ? r.continue() : r.abort());
await pg.goto("file://" + dir + "/index.html");
await pg.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
await pg.evaluate(async () => { await document.fonts.ready; });
const r = await pg.evaluate(([A, B]) => {
  const tl = window.__timelines.main, rows = [];
  const cam = document.querySelector('[data-p="mmc-map-a"]');
  const shown = (sel) => [...document.querySelectorAll(sel)].filter(e => getComputedStyle(e).display !== "none" &&
                                                                      e.closest('g.lay') && getComputedStyle(e.closest('svg')).display !== 'none');
  for (let f = A - 2; f < B + 2; f++) {
    tl.seek(f / 30, false);
    const vis = getComputedStyle(cam).visibility !== "hidden" && cam.getBoundingClientRect().width > 0;
    const m = new DOMMatrix(getComputedStyle(cam).transform);
    const dyn = shown('[data-p^="mmd-map-a-"]').length, scr = shown('[data-p^="mms-map-a-"]');
    const labels = scr.length ? [...scr[0].querySelectorAll("text")].map(t => { const q = t.getBoundingClientRect(); return [t.dataset.label, q.left, q.top, q.right, q.bottom]; }) : [];
    rows.push({ f, vis, m: [m.a, m.b, m.c, m.d, m.e, m.f], dyn, scr: scr.length, labels });
  }
  return { rows, warns: window.__docuWarnings || [], fonts: [...document.fonts].filter(x => x.status === "loaded").map(x => x.family + " " + x.weight).sort() };
}, [+a, +b]);
r.errors = errors; fs.writeFileSync(out, JSON.stringify(r)); await br.close();"""
    (work / "page.mjs").write_text(probe_js, encoding="utf-8")
    r = subprocess.run(["node", str(work / "page.mjs"), str(rdir), str(work / "page.json"), str(CLIP[0]), str(CLIP[1])],
                       capture_output=True, text=True, cwd=str(FILM / "tests"))
    R = json.loads((work / "page.json").read_text(encoding="utf-8")) if r.returncode == 0 else {"rows": [], "errors": [r.stderr[-300:]], "warns": [], "fonts": []}
    rows = {x["f"]: x for x in R["rows"]}
    inside = [f for f in range(*CLIP)]
    cam_err = max((max(abs(p - q) for p, q in zip(rows[f]["m"], sp["camera"]["frames"][f - CLIP[0]]["matrix"])) for f in inside), default=99)
    check(R["rows"] and cam_err < 0.01, f"every frame of the clip: the camera group's matrix = the scene plan's (largest difference {cam_err:.1e} px; "
                                         "the browser's CSS values are single precision)")
    check(all(rows[f]["dyn"] == 1 and rows[f]["scr"] == 1 for f in inside) and all(rows[f]["dyn"] == 0 and rows[f]["scr"] == 0 for f in (CLIP[0] - 1, CLIP[1], CLIP[1] + 1)),
          "exactly one frame fragment per layer on every clip frame, none just before or after the clip")
    worst = 0.0
    for f in inside[::7]:
        want = {x["id"]: x for x in sp["labels"]["frames"][f - CLIP[0]]["labels"] if x["shown"]}
        got = {x[0]: x[1:] for x in rows[f]["labels"]}
        if set(want) != set(got):
            worst = 99
            break
        for k, (l, t, rr, bb) in got.items():
            box = want[k]["box"]
            pad = sp["labels"]["style"]["padding"] + sp["labels"]["style"]["halo_width"] / 2
            worst = max(worst, abs(l - box[0] - pad), abs(rr - box[0] - box[2] + pad), abs(t - box[1] - pad), abs(bb - box[1] - box[3] + pad))
    check(worst < 1.0, f"the labels on the page are the placed ones, in their boxes, zoomed or not (largest difference {worst:.3f} px)")
    check({"Vazirmatn 700", "Inter 700"} <= set(R["fonts"]) and not R["errors"] and not R["warns"],
          f"the film's local fonts are loaded {R['fonts']}; no page error {R['errors'][:1]}, no Director warning {R['warns'][:1]}")

    print("\n== R real render 1080p30 (HyperFrames, local)")
    env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=a.browser, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    npx = ["npx", "--yes", f"hyperframes@{HF_VERSION}"]
    lint = subprocess.run(npx + ["lint"], cwd=rdir, env=env, capture_output=True, text=True)
    check(lint.returncode == 0 and re.search(r"\b0 error", lint.stdout + lint.stderr), f"HyperFrames {HF_VERSION} lint: {(lint.stdout + lint.stderr).strip().splitlines()[-1:]}")
    out = b / "story.mp4"
    rr = subprocess.run(npx + ["render", "--output", str(out), "--fps", "30", "--quality", "standard"], cwd=rdir, env=env, capture_output=True, text=True)
    (b / "render.log").write_text(rr.stdout + rr.stderr, encoding="utf-8")
    check(rr.returncode == 0 and out.exists(), f"HyperFrames render -> {out.name} {[ln for ln in (rr.stdout + rr.stderr).splitlines() if 'rendered in' in ln][-1:]}")
    if rr.returncode != 0:
        return finish()
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(out)],
                                   capture_output=True, text=True, check=True).stdout)
    v = next(s_ for s_ in pr["streams"] if s_["codec_type"] == "video")
    check((v["width"], v["height"], v["avg_frame_rate"], v["codec_name"]) == (1920, 1080, "30/1", "h264") and abs(float(pr["format"]["duration"]) - 15.0) < 0.1
          and int(v.get("nb_frames", 0)) == 450, f"ffprobe: {v['width']}x{v['height']} {v['avg_frame_rate']} {v['codec_name']}, {float(pr['format']['duration']):.2f} s, {v.get('nb_frames')} frames")
    import verify as V
    try:
        V.verify(proj, ch, b, mp4_name="story.mp4", expect=(1920, 1080), tag="")
    except SystemExit:
        pass
    vr = json.loads((b / "verify.json").read_text(encoding="utf-8"))
    check(vr.get("problems") == [], f"verify.py on the MP4: problems {vr.get('problems')}")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 1080, 1920, 3)
    red = lambda px: int(px[0]) - (int(px[1]) + int(px[2])) / 2
    route = sp["routes"][0]
    tests = []
    on = lambda x, y: 8 <= x < 1912 and 8 <= y < 1072
    def along(pts, d0, d1, step=5.0):
        """Points on a screen polyline at path distances d0..d1 from its first point."""
        out, acc = [], 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            L = math.hypot(x1 - x0, y1 - y0)
            d = max(d0, acc)
            while d <= min(d1, acc + L) and L > 0:
                t_ = (d - acc) / L
                out.append((x0 + t_ * (x1 - x0), y0 + t_ * (y1 - y0)))
                d += step
            acc += L
        return out
    for i in range(5, len(sp["animation"]["frames"]), 5):
        f = CLIP[0] + i
        st = sp["camera"]["frames"][i]
        an = sp["animation"]["frames"][i]["routes"][0]
        h = an["head"]
        if h is None or h.get("piece", 0) != 0:
            continue
        X, Y = CAM.to_screen(st, sp["frame"], h["x"], h["y"])
        pc = route["pieces"][0]
        scr = lambda vs: [CAM.to_screen(st, sp["frame"], v_["x"], v_["y"]) for v_ in vs]
        back = [(X, Y)] + scr([v_ for v_ in pc if v_["s_m"] < an["s_m"] - 1][::-1])
        fwd = [(X, Y)] + scr([v_ for v_ in pc if v_["s_m"] > an["s_m"] + 1])
        # the stop pins are red too: a pixel sample means "route" / "plane" only away from them (>= 40 px)
        pins = [CAM.to_screen(st, sp["frame"], x, p_["y"]) for p_ in sp["points"] for x in p_["x"]]
        # ... and the film's caption band + its dark gradient lie over the map's lowest quarter (y > 800): not sampled
        free = lambda P: on(*P) and P[1] < 800 and all(math.hypot(P[0] - q[0], P[1] - q[1]) >= 40 for q in pins)
        bh = next((P for P in along(back, 40, 400) if free(P)), None)
        ah = next((P for P in along(fwd, 60, 600) if free(P)), None)
        if free((X, Y)) and bh:
            tests.append((f, X, Y, bh[0], bh[1], ah))
    check(len(tests) >= 3 and sum(t_[5] is not None for t_ in tests) >= 2,
          f"{len(tests)} MP4 frames with the route's tip on screen away from the stop pins to check "
          f"({sum(t_[5] is not None for t_ in tests)} with a not-yet-drawn route sample)")
    for f, X, Y, Xb, Yb, ah in tests:
        fr = frames[f]
        win = lambda x, y, r_=3: fr[max(0, int(y) - r_):int(y) + r_ + 1, max(0, int(x) - r_):int(x) + r_ + 1].reshape(-1, 3)
        tip = max(red(px) for px in win(X, Y, 4))
        line = max(red(px) for px in win(Xb, Yb, 3))
        not_yet = max(red(px) for px in win(*ah, 3)) if ah else -999
        check(tip > 60 and line > 60 and not_yet < 40, f"MP4 frame {f}: the plane at the tip ({X:.0f}, {Y:.0f}) and the drawn route behind it are red "
                                                       f"({tip:.0f}, {line:.0f}); ahead of the tip no route yet ({not_yet:.0f})")
    f = CLIP[0] + 150
    lab = [x for x in sp["labels"]["frames"][150]["labels"] if x["shown"]][0]
    bx = lab["box"]
    patch = frames[f][int(bx[1]):int(bx[1] + bx[3]), int(bx[0]):int(bx[0] + bx[2])].astype(int)
    dark = int((patch.sum(axis=2) < 200).sum())
    check(dark > 50, f"MP4 frame {f}: the label '{sp['labels']['texts'][lab['id']]['text']}' is drawn in its box ({dark} dark text pixels)")
    last_map, after = frames[CLIP[1] - 1].astype(int), frames[CLIP[1] + 1].astype(int)
    diff = float(np.abs(last_map - after).mean())
    check(diff > 15, f"the frame right after the clip is no longer the map (mean colour difference {diff:.1f} from the clip's last frame)")
    shutil.copyfile(out, work / "map-film.mp4")
    for f in (CLIP[0] + 30, CLIP[0] + 150, CLIP[0] + 260):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", f"select=eq(n\\,{f})", "-frames:v", "1", str(work / f"mp4-frame-{f}.png")], check=True)
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2g FILM TESTS PASSED" if not f else "MAP MOTION M2g FILM TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
