#!/usr/bin/env python3
"""G5 - graphic clips on the Film page through the Timeline (nfp/film/engine/timeline_bridge.py), end to end:
  L  backwards compatibility: an image-only timeline, a map timeline and a project without a timeline compose to the
     SAME bytes (page and every file) with the committed bridge (HEAD) and this one; no graphics file
  Q  errors stop compose: no ref, an asset, a broken document, an overlay-only kind on a visual track, a draft graphic in a
     final timeline, a full-frame graphic over an image, overlays covering each other, text that overflows, missing fonts
  P  the composed page in Chromium (English and Persian films): one Director shot per full-frame graphic, ONE overlay
     layer between #world and #post, every graphic shown exactly on its clip's frames (hidden before / from its end),
     its lines where the layout put them (also an English graphic in a Persian film, whose page forces Vazirmatn on
     #art text), only our web fonts, no Director warning, no page error, overlay shown while a video plays
  R  a real HyperFrames render of the English film and of the same film without its graphic clips: 1920x1080 30 fps,
     the graphics only change pixels inside their own extent and only on their clip's frames, the subtitle band never,
     verify.py finds nothing the film without graphics does not
  python3 nfp/graphics/tests/test_graphics_g5_film.py --gsap <gsap.min.js> --fonts <woff2 folder> --work <dir outside the repo>
"""
import argparse
import json
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
sys.path[:0] = [str(FILM / "engine"), str(FILM / "tests"), str(NFP), str(NFP / "location" / "tests"), str(NFP / "mapmotion" / "tests"),
                str(ROOT / "scripts")]
import graphics as G                                    # noqa: E402
from graphics import filmclip as GF                     # noqa: E402
from graphics import render as R                        # noqa: E402
from graphics.tools import measure as MS                # noqa: E402
from film_equivalence_check import CDN                  # noqa: E402
from film_render_check import HF_VERSION, BROWSER       # noqa: E402
from film_timeline_check import compose_dir, make_image, sha   # noqa: E402
import film_video_check as FV                           # noqa: E402
import test_mapmotion_m2g_film as MT                    # noqa: E402

RESULTS = []
TODAY = "2026-11-25"
IMG, MAP, VID = (20, 110), (180, 390), (400, 450)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


SRC = [{"id": "s1", "title": "Port records", "publisher": "Port Authority", "date": "2019", "verified": True}]
GDOCS = {
    "lt-en": {"lang": "en", "kind": "lower-third", "content": {"title": "Maryam Ahmadi", "subtitle": "Historian, University of Tehran"},
              "animation": {"in": {"type": "fade", "frames": 9}, "out": {"type": "fade", "frames": 9}}},
    "title-fa": {"lang": "fa", "kind": "title", "content": {"title": "فصل دوم: بندر", "subtitle": "سال‌های ۱۳۳۰ تا ۱۳۴۰"},
                 "animation": {"in": {"type": "wipe", "frames": 12}, "out": {"type": "fade", "frames": 9}}},
    "info-fa": {"lang": "fa", "kind": "info-card", "mode": "draft", "content": {"title": "بندر قدیمی", "body": "در سال ۱۳۳۲ نزدیک ۴۰ کشتی پهلو گرفت."},
                "animation": {"in": {"type": "slide", "frames": 12}, "out": {"type": "slide", "frames": 9}}},
    "callout-en": {"lang": "en", "kind": "callout", "content": {"body": "The old pier, rebuilt in 1958", "source": "s1"}, "sources": SRC,
                   "place": {"at": [700, 420]}, "animation": {"in": {"type": "pop", "frames": 10}, "out": {"type": "pop", "frames": 8}}},
    "lt-fa": {"lang": "fa", "kind": "lower-third", "content": {"title": "مریم احمدی", "subtitle": "تاریخ‌نگار، دانشگاه تهران"},
              "animation": {"in": {"type": "wipe", "frames": 8}, "out": {"type": "wipe", "frames": 8}}},
}
# clip id, graphic, track, start, end
GCLIPS = [("g-lt", "lt-en", "over", 30, 100), ("g-title", "title-fa", "pictures", 120, 175),
          ("g-info", "info-fa", "over", 200, 290), ("g-call", "callout-en", "over", 300, 370), ("g-vid", "lt-fa", "over", 405, 447)]


def gdoc(name, **kw):
    d = dict({"schema": "nfp.graphics/1", "id": name, "mode": "final"}, **copy_(GDOCS[name]))
    d.update(kw)
    return d


def copy_(x):
    return json.loads(json.dumps(x))


def project(work, name, fixture="neutral-en", gclips=GCLIPS, docs=None, mode="draft", image=True, mapclip=True, video=True,
            extra_clips=(), tl_edit=None):
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FILM / "tests/fixtures" / fixture, d)
    (d / "media").mkdir()
    shutil.copyfile(work / "wide.png", d / "media" / "wide.png")
    reg = {"schema": "nfp.assets/1", "assets": [FV.asset("wide", "media/wide.png", d, "image", 3200, 1800)]}
    clips = []
    if image:
        clips.append({"id": "i-a", "track": "pictures", "kind": "image", "start": IMG[0], "end": IMG[1], "asset": "wide", "camera": {"preset": "zoom-in"}})
    if mapclip:
        MT.write_map(d, window=MAP)
        clips.append({"id": "map-a", "track": "pictures", "kind": "map", "start": MAP[0], "end": MAP[1], "ref": "maps/film.clip.json"})
    if video:
        shutil.copyfile(work / "v30.mp4", d / "media" / "v30.mp4")
        reg["assets"].append(FV.asset("v30", "media/v30.mp4", d, "video", 1920, 1080, 20.0))
        clips.append({"id": "v-a", "track": "pictures", "kind": "video", "start": VID[0], "end": VID[1], "asset": "v30"})
    (d / "graphics").mkdir()
    docs = docs or {}
    for cid, g, tr, s, e in gclips:
        (d / "graphics" / f"{g}.json").write_text(json.dumps(docs.get(g) or gdoc(g), ensure_ascii=False), encoding="utf-8")
        clips.append({"id": cid, "track": tr, "kind": "graphic", "start": s, "end": e, "ref": f"graphics/{g}.json"})
    clips += list(extra_clips)
    tl = {"schema": "nfp.timeline/1", "fps": 30, "duration": 450, "mode": mode,
          "tracks": [{"id": "pictures", "kind": "visual"}, {"id": "over", "kind": "overlay"}], "clips": clips}
    if tl_edit:
        tl_edit(tl)
    (d / "assets.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps(tl, indent=1, ensure_ascii=False), encoding="utf-8")
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


PROBE = r"""
const { createRequire } = await import("node:module"); const fs = await import("node:fs");
const { chromium } = createRequire(import.meta.url)("playwright");
const [dir, out, framesArg, keysArg] = process.argv.slice(2); const errors = [];
const br = await chromium.launch(); const pg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
pg.on("pageerror", (e) => errors.push(String(e)));
await pg.route("**/*", (r) => r.request().url().startsWith("file:") ? r.continue() : r.abort());
await pg.goto("file://" + dir + "/index.html");
await pg.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
await pg.evaluate(async () => { await document.fonts.ready; });
const frames = framesArg.split(",").map(Number), keys = keysArg.split(",");
const r = await pg.evaluate(([frames, keys]) => {
  const tl = window.__timelines.main, rows = [];
  const lay = document.getElementById("nfp-gfx");
  const order = lay ? { prev: lay.previousElementSibling && lay.previousElementSibling.id, next: lay.nextElementSibling && lay.nextElementSibling.id,
                        parent: lay.parentNode.id } : null;
  const shown = (e) => { for (let x = e; x && x.nodeType === 1; x = x.parentNode) { const cs = getComputedStyle(x);
    if (cs.display === "none" || cs.visibility === "hidden") return false; } return true; };
  for (const f of frames) {
    tl.seek(f / 30, false);
    const vis = {};
    for (const k of keys) { const e = document.querySelector('[data-p="gx-' + k + '"]'); vis[k] = e ? shown(e) : null; }
    const lines = [...document.querySelectorAll('text[data-p^="gx-"]')].filter(shown).map(t => {
      const xs = []; for (let i = 0; i < t.getNumberOfChars(); i++) xs.push(t.getStartPositionOfChar(i).x, t.getEndPositionOfChar(i).x);
      const m = t.getScreenCTM(); return { p: t.dataset.p, x0: Math.min(...xs) * m.a + m.e, x1: Math.max(...xs) * m.a + m.e }; });
    const world = getComputedStyle(document.getElementById("world")).display;
    rows.push({ f, vis, lines, world });
  }
  return { rows, order, warns: window.__docuWarnings || [], fonts: [...document.fonts].filter(x => x.status === "loaded").map(x => x.family + " " + x.weight).sort() };
}, [frames, keys]);
const cdp = await pg.context().newCDPSession(pg); await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
const root = (await cdp.send("DOM.getDocument", { depth: -1 })).root.nodeId;
const { nodeIds } = await cdp.send("DOM.querySelectorAll", { nodeId: root, selector: 'text[data-p^="gx-"]' });
const sys = new Set();
for (const id of nodeIds) { const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId: id }); fonts.filter(x => !x.isCustomFont).forEach(x => sys.add(x.familyName)); }
r.system_fonts = [...sys]; r.errors = errors; fs.writeFileSync(out, JSON.stringify(r)); await br.close();
"""


def render_copy(b, gsap):
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    rdir = b / "render-copy"
    if rdir.exists():
        shutil.rmtree(rdir)
    shutil.copytree(b / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(gsap, rdir / "gsap.min.js")
    return rdir


def expectations(d, b, fonts):
    """The graphics the bridge drew, rebuilt the same way: {clip id: (clip, spec, lay)}."""
    tl = json.loads((d / "timeline.json").read_text(encoding="utf-8"))
    tracks = {t["id"]: t["kind"] for t in tl["tracks"]}
    out = {}
    for c in tl["clips"]:
        if c["kind"] != "graphic":
            continue
        spec, _ = GF.prepare(GF.load(c["ref"], d), c, tracks[c["track"]], tl["mode"])
        lay, _ = GF.finish(spec, MS.measure_graphic(spec, b / "story/assets/fonts"))
        out[c["id"]] = (c, spec, lay)
    return out


def probe(work, rdir, frames, keys, name):
    (work / "probe.mjs").write_text(PROBE, encoding="utf-8")
    out = work / f"{name}.json"
    r = subprocess.run(["node", str(work / "probe.mjs"), str(rdir), str(out), ",".join(map(str, frames)), ",".join(keys)],
                       capture_output=True, text=True, cwd=str(FILM / "tests"))
    return json.loads(out.read_text(encoding="utf-8")) if r.returncode == 0 else {"rows": [], "errors": [r.stderr[-300:]], "warns": [], "fonts": [], "system_fonts": [], "order": None}


def check_page(R_, exp, label):
    rows = {x["f"]: x for x in R_["rows"]}
    timing_bad, span = [], 0.0
    for cid, (c, spec, lay) in exp.items():
        k = GF.key_of_clip(cid)
        for f in (c["start"] - 1, c["start"], (c["start"] + c["end"]) // 2, c["end"] - 1, c["end"]):
            if f in rows and rows[f]["vis"].get(k) != (c["start"] <= f < c["end"]):
                timing_bad.append((cid, f, rows[f]["vis"].get(k)))
        mid = rows[(c["start"] + c["end"]) // 2]
        want = {f"gx-{k}-{b['role']}-{n}": ln for b in lay["blocks"] for n, ln in enumerate(b["lines"])}
        got = {x["p"]: x for x in mid["lines"] if x["p"] in want}
        if set(got) != set(want):
            span = 99
        for p, ln in want.items():
            if p in got:
                span = max(span, abs(got[p]["x0"] - ln["x0"]), abs(got[p]["x1"] - ln["x1"]))
    check(not timing_bad, f"{label}: every graphic shown exactly on its clip's frames, hidden just before and from its end {timing_bad[:3]}")
    check(span < 1.0, f"{label}: at mid clip every line where the layout put it (largest difference {span:.3f} px)")
    check(not R_["errors"] and not R_["warns"] and not R_["system_fonts"],
          f"{label}: no page error {R_['errors'][:1]}, no Director warning {R_['warns'][:1]}, only our web fonts drew text {R_['system_fonts']}")


def png_frames(mp4):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 1080, 1920, 3)


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    make_image(work / "wide.png", 3200, 1800)
    FV.make_video(work / "v30.mp4", 30, 600, (1920, 1080))
    fonts = Path(a.fonts).resolve()

    print("== L legacy: projects without a graphic clip")
    head_src = subprocess.run(["git", "show", "HEAD:nfp/film/engine/timeline_bridge.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    plain = work / "projects" / "plain"
    shutil.copytree(FILM / "tests/fixtures/neutral-en", plain)
    legacy = [("image-only timeline (T2)", project(work, "img-only", gclips=[], mapclip=False, video=False)),
              ("image + map + video timeline (M2g, T4)", project(work, "img-map-vid", gclips=[])), ("no timeline block", plain)]
    for label, src in legacy:
        bo, bn = work / f"b-old-{src.name}", work / f"b-new-{src.name}"
        MT.with_bridge(head_src, lambda: compose_dir(src, bo, fonts))
        compose_dir(src, bn, fonts)
        files = lambda b: sorted(p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file())
        same = files(bo) == files(bn) and all((bo / p).read_bytes() == (bn / p).read_bytes() for p in files(bo) if p.startswith("story/"))
        check(same and not (bn / "graphics_qc.json").exists(), f"{label}: the page and every story file byte-identical with the committed bridge; no graphics file")

    print("\n== Q errors stop compose")
    cases = [
        ("no ref", dict(extra_clips=[{"id": "g-x", "track": "over", "kind": "graphic", "start": 10, "end": 40}], gclips=[]), "needs ref"),
        ("an asset", dict(extra_clips=[{"id": "g-x", "track": "over", "kind": "graphic", "start": 10, "end": 40, "ref": "graphics/x.json", "asset": "wide"}],
                          gclips=[]), "asset"),
        ("a broken document", dict(docs={"lt-en": {"schema": "nfp.graphics/9"}}, gclips=[GCLIPS[0]]), "ERROR (graphic)"),
        ("a lower third on a visual track", dict(gclips=[("g-lt", "lt-en", "pictures", 120, 170)]), "only as overlay"),
        ("a draft graphic in a final timeline", dict(gclips=[GCLIPS[2]], mode="final"), "final mode"),
        # on a SECOND visual track: on the same track the Timeline itself already refuses the overlap (case below)
        ("a full-frame graphic over an image", dict(gclips=[("g-title", "title-fa", "pictures-2", 60, 100)],
                                                    tl_edit=lambda tl: tl["tracks"].append({"id": "pictures-2", "kind": "visual"})), "one full-frame picture"),
        ("a full-frame graphic over an image, same track", dict(gclips=[("g-title", "title-fa", "pictures", 60, 100)]), "allows no overlap"),
        ("overlays covering each other", dict(gclips=[("g-lt", "lt-en", "over", 30, 100), ("g-lt2", "lt-en", "over", 60, 90)]), "cover each other"),
        ("text that overflows", dict(docs={"lt-en": gdoc("lt-en", content={"title": "Maryam " * 11})}, gclips=[GCLIPS[0]]), "text_overflow"),
    ]
    for name, kw, want in cases:
        d = project(work, "q-" + name.replace(" ", "-").replace(",", ""), mapclip=False, video=False, **kw)    # only the case's own subject
        msg = try_compose(d, work / ("b-q-" + name.replace(" ", "-")), fonts)
        check(msg != "composed" and want in msg, f"{name}: stopped - {msg[:120]}")
    nofont = work / "fonts-no-vazir"
    nofont.mkdir()
    for f in fonts.glob("*.woff2"):
        if "vazirmatn" not in f.name:
            shutil.copyfile(f, nofont / f.name)
    msg = try_compose(project(work, "q-fonts", gclips=[GCLIPS[0]], mapclip=False, video=False), work / "b-q-fonts", nofont)
    check("ERROR (graphic)" in msg and "local fonts" in msg, f"graphics without the film's local fonts: stopped - {msg[:100]}")
    d = project(work, "final-ok", gclips=[GCLIPS[0], GCLIPS[3]], mode="final", image=True, mapclip=False, video=False)
    check(try_compose(d, work / "b-final-ok", fonts) == "composed", "a final timeline with final, sourced graphics composes")

    print("\n== P the composed page (English film)")
    d = project(work, "film-en")
    b = work / "b-en"
    proj, ch, _ = compose_dir(d, b, fonts)
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    qc = json.loads((b / "graphics_qc.json").read_text(encoding="utf-8"))
    check(page.count('D.shot({ id: "gfx-c-g-title"') == 1 and page.count('setAttribute("id", "nfp-gfx")') == 1 and
          [x["clip"] for x in qc["clips"]] == ["g-lt", "g-title", "g-info", "g-call", "g-vid"] and
          {x["clip"]: x["display"] for x in qc["clips"]} == {"g-lt": "overlay", "g-title": "fullframe", "g-info": "overlay", "g-call": "overlay", "g-vid": "overlay"},
          "one Director shot for the full-frame title, ONE overlay layer; QC written next to the build; display from the track")
    check(next(x for x in qc["clips"] if x["clip"] == "g-info")["draft_badge"], "the draft info card (unsourced number) carries the draft badge")
    exp = expectations(d, b, fonts)
    rdir = render_copy(b, a.gsap)
    frames = sorted({f for c, _, _ in exp.values() for f in (c["start"] - 1, c["start"], (c["start"] + c["end"]) // 2, c["end"] - 1, c["end"])})
    keys = [GF.key_of_clip(c) for c in exp]
    P = probe(work, rdir, frames, keys, "page-en")
    check(P["order"] == {"prev": "world", "next": "post", "parent": "svg"}, f"the overlay layer sits between #world and #post: {P['order']}")
    check_page(P, exp, "English film")
    row = next((x for x in P["rows"] if x["f"] == (405 + 447) // 2), None)
    check(row and row["world"] == "none" and row["vis"][GF.key_of_clip("g-vid")], "while the video plays (#world hidden) the overlay is shown")

    print("\n== P the composed page (Persian film: #art text forces Vazirmatn first)")
    dfa = project(work, "film-fa", fixture="cast-fa", gclips=[("g-lt", "lt-en", "over", 30, 100), ("g-title", "title-fa", "pictures", 120, 175)],
                  image=False, mapclip=False, video=False)
    bfa = work / "b-fa"
    compose_dir(dfa, bfa, fonts)
    check('#art text { font-family: "Vazirmatn"' in (bfa / "story/index.html").read_text(encoding="utf-8"), "the Persian film's page has its #art text !important font rule")
    expfa = expectations(dfa, bfa, fonts)
    rfa = render_copy(bfa, a.gsap)
    fr = sorted({f for c, _, _ in expfa.values() for f in (c["start"] - 1, c["start"], (c["start"] + c["end"]) // 2, c["end"] - 1, c["end"])})
    Pfa = probe(work, rfa, fr, [GF.key_of_clip(c) for c in expfa], "page-fa")
    check_page(Pfa, expfa, "Persian film (an English lower third measured Inter-first is drawn Inter-first)")
    if a.no_render:
        return finish()

    print("\n== R real render 1080p30 (HyperFrames, local), with and without the graphic clips")
    d0 = project(work, "film-en-nogfx", gclips=[])
    b0 = work / "b-en-nogfx"
    proj0, ch0, _ = compose_dir(d0, b0, fonts)
    r0 = render_copy(b0, a.gsap)
    env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=BROWSER, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    npx = ["npx", "--yes", f"hyperframes@{HF_VERSION}"]
    outs = {}
    for name, rd, bb in (("with", rdir, b), ("without", r0, b0)):
        lint = subprocess.run(npx + ["lint"], cwd=rd, env=env, capture_output=True, text=True)
        out = bb / "story.mp4"
        rr = subprocess.run(npx + ["render", "--output", str(out), "--fps", "30", "--quality", "standard"], cwd=rd, env=env, capture_output=True, text=True)
        check(lint.returncode == 0 and re.search(r"\b0 error", lint.stdout + lint.stderr) and rr.returncode == 0 and out.exists(),
              f"{name} graphics: lint 0 errors, HyperFrames render {[ln for ln in (rr.stdout + rr.stderr).splitlines() if 'rendered in' in ln][-1:]}")
        outs[name] = out
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(outs["with"])],
                                   capture_output=True, text=True, check=True).stdout)
    v = next(s_ for s_ in pr["streams"] if s_["codec_type"] == "video")
    check((v["width"], v["height"], v["avg_frame_rate"], int(v.get("nb_frames", 0))) == (1920, 1080, "30/1", 450),
          f"ffprobe: {v['width']}x{v['height']} {v['avg_frame_rate']} {v.get('nb_frames')} frames")
    A_, B_ = png_frames(outs["with"]).astype(np.int16), png_frames(outs["without"]).astype(np.int16)
    active = lambda f: [(c, s, l) for c, s, l in exp.values() if c["start"] <= f < c["end"]]
    # The two MP4s are encoded separately: H.264 makes slightly different decisions on the film grain (seen even on frames
    # before the first graphic: a 32 px block's mean difference up to ~4). So the test is per 32 x 32 block, not a frame
    # mean: outside the graphics' own extent (+32 px) and in the subtitle band no block may differ by more than BLOCK
    # (above the noise measured here, ~7, far below a drawn graphic: 86..190 per block).
    BLOCK = 12.0
    noise = []
    out_bad, band_bad, in_ok = [], [], []
    for f in range(0, 450, 3):
        diff = np.abs(A_[f] - B_[f]).max(axis=2).astype(float)
        m = np.ones((1080, 1920), bool)
        ff = any(s["display"] == "fullframe" for _, s, _ in active(f))
        for c, s, l in active(f):
            if s["display"] == "overlay":
                x, y, w, h = R.extent(s, l)
                m[max(0, int(y) - 32):int(y + h) + 32, max(0, int(x) - 32):int(x + w) + 32] = False
        blocks = np.where(m, diff, 0)[:1056].reshape(33, 32, 60, 32).mean(axis=(1, 3))
        if not active(f):
            noise.append(float(blocks.max()))
        if not ff and blocks.max() > BLOCK:
            out_bad.append((f, round(float(blocks.max()), 1)))
        if not ff and blocks[26:].max() > BLOCK:            # rows 832.. : the subtitle band
            band_bad.append((f, round(float(blocks[26:].max()), 1)))
        for c, s, l in active(f):
            if s["display"] == "overlay" and c["start"] + s["animation"]["in"]["frames"] <= f < c["end"] - s["animation"]["out"]["frames"]:
                x, y, w, h = R.extent(s, l, margin=0)
                in_ok.append(float(diff[int(y):int(y + h), int(x):int(x + w)].mean()) > 8)
    check(not out_bad, f"graphics change nothing beyond their own extent, and nothing outside their clips: every 32 px block <= {BLOCK:g} "
                       f"(codec noise on frames without any graphic: up to {max(noise):.1f}) {out_bad[:4]}")
    check(not band_bad, f"the subtitle band is the same with and without graphics (every block <= {BLOCK:g}) {band_bad[:4]}")
    check(in_ok and all(in_ok), f"every fully shown overlay is really drawn in the MP4 over image / map / video ({sum(in_ok)} frames)")
    c, s, l = exp["g-title"]
    fmid = (c["start"] + c["end"]) // 2
    bgc = np.array(R._rgb(s["style"]["colors"]["background"]))
    px = A_[fmid][540, 960 - 700]
    check(np.abs(px - bgc).max() < 25 and np.abs(A_[fmid] - B_[fmid]).mean() > 10, f"the full-frame title replaces the picture (background {px.tolist()} ~ {bgc.tolist()})")
    import verify as V
    probs = {}
    for name, pj, chp, bb in (("with", proj, ch, b), ("without", proj0, ch0, b0)):
        try:
            V.verify(pj, chp, bb, mp4_name="story.mp4", expect=(1920, 1080), tag="")
        except SystemExit:
            pass
        probs[name] = [re.sub(r"\[\[.*", "", p) for p in json.loads((bb / "verify.json").read_text(encoding="utf-8")).get("problems", [])]
    new = [p for p in probs["with"] if p not in probs["without"]]
    check(not new, f"verify.py finds nothing new with graphics (with: {probs['with']}; without: {probs['without']})")
    shutil.copyfile(outs["with"], work / "graphics-film.mp4")
    for f in (60, 150, 245, 335, 425):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(outs["with"]), "-vf", f"select=eq(n\\,{f})", "-frames:v", "1", str(work / f"mp4-frame-{f}.png")], check=True)
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G5 FILM TESTS PASSED" if not f else "GRAPHICS G5 FILM TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
