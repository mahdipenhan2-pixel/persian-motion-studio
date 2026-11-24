#!/usr/bin/env python3
"""
T3 + T4 for the Studio character layer (C4), run locally: no GitHub Actions, no Gemini, no TTS, no API.

  python3 studio/tests/characters_render_check.py --timing <real timing.json of motion-demo-fa> \
      --fonts <dir with vazirmatn woff2> --gsap <local gsap.min.js 3.12.5> --work <dir outside the repo> [--render]

1. composes cast-demo-fa twice into <work>: 'plain' = the same project WITHOUT character fields through run_motion.py,
   'cast' = run_cast.py. The word timing is the REAL Whisper timing of the motion-demo-fa narration (same sentences);
   narration.wav is a SYNTHETIC tone at those word times (as in camera_local_check.py): the real Gemini audio exists
   only in the Actions cache and is not used here.
2. render copies: the only change against the product page is the cdnjs GSAP line -> local copy. Two test variants of
   the cast page: 'ref' (cast.js emptied: no characters) and 'nocss' (rig.css removed).
3. T3: studio/tests/characters_page_check.mjs (browser) + pixel checks on its screenshots:
   cast vs ref differ ONLY inside the character slot; cast vs plain are identical above y 1360 (top zone, captions).
4. T4 (--render): HyperFrames lint + render (cast, ref, plain) -> MP4; the LOCKED Stage 2 verify on cast and plain;
   word highlight identical; caption band of the cast video = plain video; outside the slot cast video = ref video;
   the speaker's mouth area moves while that actor speaks and stays still while the other actor speaks.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "studio" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HERE))

import project as P  # noqa: E402
import run_cast as RC  # noqa: E402
import run_motion as RM  # noqa: E402
import story_stage2 as core  # noqa: E402
from camera_local_check import CDN, HF_VERSION, synth_narration  # noqa: E402
from characters import schema as CS  # noqa: E402
from character.animation.keys import PROFILE, sample, to_frame  # noqa: E402

DEMO = "cast-demo-fa"
RESULTS = []


def check(ok, msg):
    RESULTS.append((bool(ok), msg))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def compose(kind, project_path, work, timing, fonts):
    proj = P.load(str(project_path))
    theme = P.load_theme(proj["meta"]["theme"])
    b = work / kind
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    (b / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
    synth_narration(timing, b / "narration.wav")
    pdir = Path(project_path).parent
    if kind == "plain":
        RM.compose_with_camera(proj, theme, b, fonts, b / "narration.wav", pdir)
    else:
        RC.compose_with_cast(proj, theme, b, fonts, b / "narration.wav", pdir)
    return proj, theme, b


def render_copy(build, gsap, name="render", edit=None):
    src, dst = build / "story", build / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    page = (src / "index.html").read_text(encoding="utf-8")
    if page.count(CDN) != 1:
        raise SystemExit("expected exactly one cdnjs GSAP script tag")
    new = page.replace(CDN, '<script src="gsap.min.js"></script>')
    if edit:
        new = edit(new)
    (dst / "index.html").write_text(new, encoding="utf-8")
    shutil.copyfile(gsap, dst / "gsap.min.js")
    return dst, page, new


def line_diff(a, b):
    la, lb = a.splitlines(), b.splitlines()
    return [i for i, (x, y) in enumerate(zip(la, lb)) if x != y], len(la) - len(lb)


def strip_cast(p):
    p["meta"].pop("cast", None)
    for s in p["scenes"]:
        s.pop("characters", None)


def mouth_point(actor):
    """Mouth centre of an actor in page pixels (from the rig geometry and the actor's placement)."""
    M = CS.ZONES["rig_metrics"]["builds"][actor["spec"]["build"]]
    lash2 = PROFILE["face"][actor["spec"]["build"]]["ex"] == 20            # woman face: mouth at -30, else -34
    y_head = -M["legH"] - M["torsoH"] - M["neck"] + 8
    my = y_head + M["headS"] * (-30 if lash2 else -34) + 4
    slot = CS.slot_geometry()
    return slot["x"] + actor["x"], slot["y"] + actor["y"] + actor["scale"] * my


def video_crop(mp4, crop, fps=10):
    import numpy as np
    w, h, x, y = crop
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},crop={w}:{h}:{x}:{y}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(float)


def main():
    ap = argparse.ArgumentParser()
    for k in ("--timing", "--fonts", "--gsap", "--work"):
        ap.add_argument(k, required=True)
    ap.add_argument("--browser", default="/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell")
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)
    timing = json.loads(Path(a.timing).read_text(encoding="utf-8"))
    fonts = Path(a.fonts)

    # ---- compose
    src = work / "projects" / "plain-src"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(P.PROJECTS / DEMO, src)
    pj = json.loads((src / "project.json").read_text(encoding="utf-8"))
    strip_cast(pj)
    (src / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=2), encoding="utf-8")
    _, theme, plain = compose("plain", src / "project.json", work, timing, fonts)
    _, _, cast = compose("cast", P.PROJECTS / DEMO / "project.json", work, timing, fonts)
    kl = json.loads((cast / "cast_keylist.json").read_text(encoding="utf-8"))

    # ---- render copies
    cdir, prod, new = render_copy(cast, a.gsap)
    d, n = line_diff(prod, new)
    check(len(d) == 1 and n == 0, "cast render copy differs from the product page in exactly 1 line (GSAP source)")
    pdir_, prod_p, new_p = render_copy(plain, a.gsap)
    js_start = new.index('<script id="nfp-cast-js">')
    js_end = new.index("</script>", js_start)
    rdir, _, _ = render_copy(cast, a.gsap, "ref", lambda s: s[:new.index('<script id="nfp-cast-js">')] +
                             '<script id="nfp-cast-js">\nwindow.__nfpCastRef = true;\n' + s[js_end:])
    rig_css = (ROOT / "nfp" / "character" / "renderers" / "flat_cartoon_v2" / "rig.css").read_text(encoding="utf-8")
    check(new.count(rig_css) == 1, "rig.css is embedded exactly once in the cast page")
    ndir, _, _ = render_copy(cast, a.gsap, "nocss", lambda s: s.replace(rig_css, ""))

    # ---- expectations from the KeyList (Python sampler)
    frames = list(range(0, kl["frames"] + 1, 3))
    exp = {"n_actors": len(kl["actors"]), "frames": frames, "actors": {}, "words": [],
           "rig_metrics": CS.ZONES["rig_metrics"], "shot_times": [round(0.4 + k * (kl["duration"] - 0.8) / 23, 2) for k in range(24)]}
    for act in kl["actors"]:
        exp["actors"][act["id"]] = {"visible": [], "mouth": []}
    for f in frames:
        s = sample(kl, f)
        for act in kl["actors"]:
            st = s[act["id"]]
            exp["actors"][act["id"]]["visible"].append(int(st.get("self", {}).get("visible", 1)))
            exp["actors"][act["id"]]["mouth"].append(st.get("mouth", {}).get("shape", "neutral"))
    for t in kl["lipsync"]["talks"]:
        for sent in timing["sentences"]:
            if sent["id"] not in t["sentences"]:
                continue
            for w in sent["words"]:
                if w["abs_start"] is not None and (t["estimated_used"] or w.get("timing_quality") != "estimated"):
                    exp["words"].append({"actor": t["actor"], "f": to_frame(w["abs_start"], 30), "text": w["text"]})
    (work / "t3_expect.json").write_text(json.dumps(exp, ensure_ascii=False), encoding="utf-8")

    # ---- T3 (browser) + pixel checks
    t3 = work / "t3"
    r = subprocess.run(["node", str(HERE / "characters_page_check.mjs"), "--cast", str(cdir), "--ref", str(rdir),
                        "--plain", str(pdir_), "--nocss", str(ndir), "--expect", str(work / "t3_expect.json"),
                        "--out", str(t3)])
    check(r.returncode == 0, "T3 browser page check (characters_page_check.mjs)")
    import numpy as np
    from PIL import Image
    slot = CS.slot_geometry()
    outside, band_top, deco_side = [], [], []
    for t in exp["shot_times"]:
        c = np.asarray(Image.open(t3 / f"cast_{t:.2f}.png").convert("RGB")).astype(int)
        rf = np.asarray(Image.open(t3 / f"ref_{t:.2f}.png").convert("RGB")).astype(int)
        pl = np.asarray(Image.open(t3 / f"plain_{t:.2f}.png").convert("RGB")).astype(int)
        diff = np.abs(c - rf).sum(axis=2) > 0
        diff[slot["y"]:slot["y"] + slot["height"], slot["x"]:slot["x"] + slot["width"]] = False
        outside.append(int(diff.sum()))
        band_top.append(int((np.abs(c[560:1360] - pl[560:1360]).sum(axis=2) > 0).sum()))
        dz = np.abs(rf[:560] - pl[:560]).max(axis=2)
        deco_side.append((int((dz > 0).sum()), int(dz.max())))
    check(max(outside) == 0, f"cast vs ref page: 0 differing pixels outside the slot at {len(outside)} times (max {max(outside)})")
    check(max(band_top) == 0, f"caption band y 560-1360: cast page identical to the page without characters at "
                              f"{len(band_top)} times (max {max(band_top)} differing pixels)")
    worst = max(deco_side)
    print(f"INFO approved .deco hiding (no characters involved: ref vs plain, top zone y<560): differing pixels at "
          f"{sum(1 for n_, _ in deco_side if n_)} of {len(deco_side)} times, worst {worst[0]} px / max {worst[1]}/255 "
          "(rasterisation of the camera-scaled scene; the deco itself is below y 1440)")

    if a.render:
        t4(a, theme, {"cast": (cast, cdir), "ref": (cast, rdir), "plain": (plain, pdir_)}, kl, timing)
    fails = [m for ok, m in RESULTS if not ok]
    print(f"\n{len(RESULTS)} checks, " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
    sys.exit(1 if fails else 0)


def t4(a, theme, builds, kl, timing):
    import numpy as np
    env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=a.browser, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    npx = ["npx", "--yes", f"hyperframes@{HF_VERSION}"]
    lint = subprocess.run(npx + ["lint"], cwd=builds["cast"][1], env=env, capture_output=True, text=True)
    (builds["cast"][0] / "lint.log").write_text(lint.stdout + lint.stderr, encoding="utf-8")
    tail = (lint.stdout + lint.stderr).strip().splitlines()[-3:]
    check(lint.returncode == 0, f"HyperFrames {HF_VERSION} lint of the cast page: exit {lint.returncode} ({' | '.join(tail)[:300]})")
    mp4 = {}
    for kind, (b, rdir) in builds.items():
        out = b / f"{kind}.mp4"
        r = subprocess.run(npx + ["render", "--output", str(out), "--fps", "30", "--quality", "standard"], cwd=rdir, env=env,
                           capture_output=True, text=True)
        (b / f"render_{kind}.log").write_text(r.stdout + r.stderr, encoding="utf-8")
        done = [ln for ln in (r.stdout + r.stderr).splitlines() if "rendered in" in ln]
        check(r.returncode == 0 and out.exists(), f"{kind}: HyperFrames {HF_VERSION} render -> MP4 {'; '.join(done) or (r.stdout + r.stderr)[-300:]}")
        if r.returncode != 0:
            return
        mp4[kind] = out
    verify = {}
    for kind in ("cast", "plain"):
        b = builds[kind][0]
        shutil.copyfile(mp4[kind], b / "story.mp4")
        core.BUILD = b
        core.SEA = tuple(theme["highlight_rgb"])
        try:
            core.cmd_verify(None)
        except SystemExit:
            pass
        v = json.loads((b / "verify.json").read_text(encoding="utf-8"))
        verify[kind] = v
        check(v.get("problems") == [] and v.get("verification_complete") is True,
              f"{kind}: LOCKED Stage 2 verify -> problems {v.get('problems')}, complete {v.get('verification_complete')}, "
              f"{v.get('video')}, duration {v.get('duration')} / {v.get('expected_duration')}")
    hc = [(x["sentence"], x["i"], x["highlight_pixels"], x["x"], x["y"]) for x in verify["cast"].get("highlight", []) if "i" in x]
    hp = [(x["sentence"], x["i"], x["highlight_pixels"], x["x"], x["y"]) for x in verify["plain"].get("highlight", []) if "i" in x]
    if hc and hp and len(hc) == len(hp):
        maxd = max(abs(p[2] - q[2]) for p, q in zip(hc, hp))
        posd = max(max(abs((p[3] or 0) - (q[3] or 0)), abs((p[4] or 0) - (q[4] or 0))) for p, q in zip(hc, hp))
        check(maxd <= 40 and posd <= 0.01, f"word highlight identical with characters: {len(hc)} words, max pixel-count "
                                           f"difference {maxd}, max centroid shift {posd}")
    else:
        check(False, f"word highlight lists comparable ({len(hc)} vs {len(hp)})")
    slot = CS.slot_geometry()
    band = video_crop(mp4["cast"], (1080, 800, 0, 560), 4), video_crop(mp4["plain"], (1080, 800, 0, 560), 4)
    bd = [float(np.abs(x - y).mean()) for x, y in zip(*band)]
    check(len(bd) > 100 and max(bd) < 2.0, f"caption band of the cast video = plain video ({len(bd)} frames, mean abs diff max "
                                           f"{max(bd):.2f}/255)")
    # outside the slot: cast video = ref video (regions above and beside the slot, and below it)
    regions = {"above": (1080, slot["y"], 0, 0), "left": (slot["x"], slot["height"], 0, slot["y"]),
               "right": (1080 - slot["x"] - slot["width"], slot["height"], slot["x"] + slot["width"], slot["y"]),
               "below": (1080, 1920 - slot["y"] - slot["height"], 0, slot["y"] + slot["height"])}
    worst = {}
    for k, cr in regions.items():
        x, y = video_crop(mp4["cast"], cr, 4), video_crop(mp4["ref"], cr, 4)
        worst[k] = round(max(float(np.abs(p - q).mean()) for p, q in zip(x, y)), 3)
    check(max(worst.values()) < 0.5, f"outside the slot the cast video = the video without characters (worst mean diff per "
                                     f"region {worst}, /255)")
    inside = video_crop(mp4["cast"], (slot["width"], slot["height"], slot["x"], slot["y"]), 4)
    inside_ref = video_crop(mp4["ref"], (slot["width"], slot["height"], slot["x"], slot["y"]), 4)
    check(max(float(np.abs(p - q).mean()) for p, q in zip(inside, inside_ref)) > 5.0, "the characters are visible in the slot of the video")
    # mouth motion in the video: speaking windows vs the same actor listening while the other actor speaks
    talks = {}
    for t in kl["lipsync"]["talks"]:
        talks.setdefault(t["actor"], []).append((t["first_frame"] / 30, t["last_frame"] / 30))
    report = {}
    for act in kl["actors"]:
        mx, my = mouth_point(act)
        cw, ch = 64, 44
        frames = video_crop(mp4["cast"], (cw, ch, int(mx - cw / 2), int(my - ch / 2)), 10)
        ch_ = [float(np.abs(frames[i + 1] - frames[i]).mean()) for i in range(len(frames) - 1)]
        tt = lambda i: (i + 0.5) / 10  # noqa: E731
        vis = lambda t: sample(kl, int(t * 30))[act["id"]].get("self", {}).get("visible", 1) == 1 and \
            sample(kl, int(t * 30))[act["id"]].get("self", {}).get("opacity", 1) >= 0.99  # noqa: E731
        # frames where the head / body / stage position of this actor moves (nod, turn, lean, hop, ...) are left out:
        # the crop measures the MOUTH, and a moving head would change it without any lip motion
        moving = [(k["t"] - 0.1, k["t"] + k["dur"] + 0.1) for k in kl["keys"]
                  if k["actor"] == act["id"] and k["df"] > 0 and k["part"] in ("head", "root", "self", "torso")
                  and k["prop"] in ("--x", "--y", "--r", "--s") and not k["src"].startswith("idle")]
        still = lambda t: not any(a_ <= t <= b_ for a_, b_ in moving)  # noqa: E731
        own = [c for i, c in enumerate(ch_) if any(a_ + 0.1 <= tt(i) <= b_ - 0.1 for a_, b_ in talks.get(act["id"], []))
               and vis(tt(i)) and still(tt(i))]
        others = [(a_, b_) for o, v in talks.items() if o != act["id"] for a_, b_ in v]
        quiet = [c for i, c in enumerate(ch_) if any(a_ + 0.1 <= tt(i) <= b_ - 0.1 for a_, b_ in others)
                 and vis(tt(i)) and still(tt(i))]
        report[act["id"]] = {"speaking_mean": round(float(np.mean(own)), 2) if own else None,
                             "listening_mean": round(float(np.mean(quiet)), 2) if quiet else None, "n": [len(own), len(quiet)],
                             "excluded_head_motion_windows": len(moving)}
    ok = all(r["speaking_mean"] and r["listening_mean"] is not None and r["speaking_mean"] > 3 * r["listening_mean"] + 0.5
             for r in report.values())
    check(ok, f"lip sync in the MP4: the mouth area changes while that actor speaks, much less while the other speaks {report}")
    (builds["cast"][0] / "t4_report.json").write_text(json.dumps({"verify_cast": verify["cast"].get("problems"),
                                                                  "verify_plain": verify["plain"].get("problems"), "band": bd,
                                                                  "outside": worst, "mouth": report}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
