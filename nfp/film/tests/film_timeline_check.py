#!/usr/bin/env python3
"""T2 - still images of nfp/timeline on the Film page (engine/timeline_bridge.py): Ken Burns, frames, legacy, a real render.

  python3 nfp/film/tests/film_timeline_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir> --work <dir outside repo>
                                                [--no-render]

Test images are made locally with ffmpeg (PNG + JPEG, 16:9, 4:3, portrait, panorama, too small): a colour gradient with a
white disk in the middle (radius = shorter side / 10), so position, size and roundness can be measured on screen.

  L legacy   no timeline block -> page / words.json / story.srt / cast report byte-identical to the committed Film (HEAD);
             compose does not load the bridge; a timeline with no image clip adds nothing to the page
  P page     6 clips (still, zoom-in, zoom-out, pan right, pan up, zoom + pan) in the browser, EVERY frame from start-1 to
             end: visible exactly on frames start..end-1; scale / position = the planned Ken Burns value at that frame
             (GSAP ease); the image box covers 1920x1080 on every frame (no empty space) with its own aspect ratio; per
             frame steps smooth; screenshots: the disk is round (no stretch) and no background shows at the edges
  E errors   missing image, wrong sha256, wrong size, unsupported kind (video clip), enlargement > 2x, draft asset in a
             final timeline: compose stops with a clear message
  R render   HyperFrames render (1920x1080, 30 fps, H.264 + AAC), verify.py, and in the MP4 the disk appears on the
             clip's first frame, is gone after its last, and its position / size follow the plan frame by frame
"""
import argparse
import hashlib
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
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path[:0] = [str(FILM / "engine"), str(HERE), str(ROOT / "nfp"), str(ROOT / "scripts")]
import project as P                                   # noqa: E402
import compose as C                                   # noqa: E402
import cast_plan as CP                                # noqa: E402
from timeline import kenburns as KB                   # noqa: E402
from film_equivalence_check import synth_timing, CDN  # noqa: E402
from film_render_check import synth_narration, HF_VERSION, BROWSER  # noqa: E402
from film_subtitle_check import compose_outputs, ENV  # noqa: E402

RESULTS = []
IMAGES = {"wide": (3200, 1800, "png"), "four3": (2400, 1800, "jpg"), "tall": (2400, 3600, "png"),
          "pano": (6000, 1500, "jpg"), "small": (800, 450, "png")}
CLIPS = [("c-still", "wide", 15, 60, None),
         ("c-zoomin", "four3", 60, 120, {"preset": "zoom-in", "amount": 0.15}),
         ("c-zoomout", "wide", 135, 195, {"preset": "zoom-out", "amount": 0.15}),
         ("c-panright", "pano", 195, 255, {"preset": "pan-right"}),
         ("c-panup", "tall", 300, 360, {"preset": "pan-up"}),
         ("c-combo", "four3", 375, 435, {"from": {"scale": 1.0, "x": 0.5, "y": 0.5}, "to": {"scale": 1.25, "x": 0.45, "y": 0.55},
                                         "ease": "power1.inOut"})]


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_image(path, w, h):
    disk = "lt(hypot(X-W/2,Y-H/2),min(W,H)/10)"
    vf = (f"format=rgb24,geq=r='if({disk},255,60+150*X/W)':g='if({disk},255,60+150*Y/H)':b='if({disk},255,200)'")
    args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}", "-vf", vf, "-frames:v", "1", "-y"]
    if str(path).endswith(".jpg"):
        args += ["-pix_fmt", "yuvj444p", "-q:v", "2"]
    subprocess.run(args + [str(path)], check=True)


def asset_row(aid, rel, base):
    w, h, _ = IMAGES[aid]
    return {"id": aid, "kind": "image", "local_path": rel, "sha256": sha(base / rel), "width": w, "height": h, "duration": None,
            "source_url": None, "author": "NFP test", "license": "original", "license_url": None, "retrieved_at": "2026-11-24",
            "modifications": "none", "license_verified": True, "attribution": "Test image: NFP", "restrictions": [], "real_person": False}


def make_project(work, name, clips, mode="final", assets_edit=None, extra_clips=(), timeline=True):
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FILM / "tests/fixtures/neutral-en", d)
    (d / "media").mkdir()
    for aid, (w, h, ext) in IMAGES.items():
        shutil.copyfile(work / "images" / f"{aid}.{ext}", d / "media" / f"{aid}.{ext}")
    reg = {"schema": "nfp.assets/1", "assets": [asset_row(aid, f"media/{aid}.{ext}", d) for aid, (w, h, ext) in IMAGES.items()]}
    if assets_edit:
        assets_edit(reg, d)
    tl = {"schema": "nfp.timeline/1", "fps": 30, "duration": 450, "mode": mode,
          "tracks": [{"id": "pictures", "kind": "visual"}, {"id": "voice", "kind": "narration"}],
          "clips": [dict({"id": cid, "track": "pictures", "kind": "image", "start": a, "end": b, "asset": aid},
                         **({"camera": cam} if cam else {})) for cid, aid, a, b, cam in clips] + list(extra_clips)}
    (d / "assets.json").write_text(json.dumps(reg, indent=1), encoding="utf-8")
    (d / "timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    if timeline:
        pj = json.loads((d / "project.json").read_text(encoding="utf-8"))
        pj["timeline"] = {"file": "timeline.json", "assets": "assets.json"}
        (d / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def compose_dir(src, b, fonts, narration=False):
    proj = P.load(src)
    ch = proj["chapters"][0]
    timing = synth_timing(ch)
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    (b / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
    synth_narration(timing, b / "narration.wav")
    ke, fr, _ = CP.fragment(proj, ch, timing, b)
    C.compose(proj, ch, timing, b, fonts, b / "narration.wav", cast_fragment=fr, kit_extra=ke)
    return proj, ch, timing


def try_compose(src, b, fonts):
    try:
        compose_dir(src, b, fonts)
        return "composed"
    except SystemExit as e:
        return str(e)


def plan(cid, aid, a, b, cam):
    w, h, _ = IMAGES[aid]
    c = KB.expand(cam, w, h)
    s0, x0, y0 = KB.transform(c["from"], w, h)
    s1, x1, y1 = KB.transform(c["to"], w, h)
    _, Wc, Hc = KB.cover(w, h)

    def at(f):
        e = KB.ease(c["ease"], (f - a) / (b - a)) if (s0, x0, y0) != (s1, x1, y1) else 0.0
        s, x, y = s0 + (s1 - s0) * e, x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
        return s, x, y, x + s * Wc / 2, y + s * Hc / 2, s * KB.cover(w, h)[0] * min(w, h) / 10   # disk centre + radius
    return at, Wc, Hc


def disk(img):
    """Centre and radius of the white disk in an RGB array (pixels with all channels > 232), or None."""
    m = (img[..., 0] > 232) & (img[..., 1] > 232) & (img[..., 2] > 232)
    n = int(m.sum())
    if n < 50:
        return None
    ys, xs = np.nonzero(m)
    return float(xs.mean()), float(ys.mean()), math.sqrt(n / math.pi), float(xs.max() - xs.min() + 1), float(ys.max() - ys.min() + 1)


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    ap.add_argument("--browser", default=BROWSER)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    (work / "images").mkdir(parents=True)
    for aid, (w, h, ext) in IMAGES.items():
        make_image(work / "images" / f"{aid}.{ext}", w, h)

    head_rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(f"== L legacy (byte-identical to the committed Film {head_rev[:7]})")
    head = work / "head"
    head.mkdir()
    arch = subprocess.run(["git", "-C", str(ROOT), "archive", head_rev], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(head)], input=arch.stdout, check=True)
    for fx in ("neutral-en", "cast-en", "cast-fa"):
        f = FILM / "tests/fixtures" / fx
        old, _ = compose_outputs(head, f, work / "L" / fx / "old", a.fonts)
        new, _ = compose_outputs(ROOT, f, work / "L" / fx / "new", a.fonts)
        check(old == new and len(new) >= 3, f"{fx}: {', '.join(sorted(new))} byte-identical to {head_rev[:7]}")
    probe = ("import sys, json; sys.path[:0] = sys.argv[1:4]; import project as P, compose as C; from film_equivalence_check import "
             "synth_timing; p = P.load(sys.argv[4]); ch = p['chapters'][0]; t = synth_timing(ch); import pathlib, wave; b = pathlib.Path(sys.argv[5]); "
             "b.mkdir(parents=True); w = wave.open(str(b/'n.wav'), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); "
             "w.writeframes(b'\\0\\0' * int(24000 * t['audio']['total'])); w.close(); C.compose(p, ch, t, b, '', b/'n.wav'); "
             "print(json.dumps(sorted(m for m in sys.modules if m.startswith('timeline'))))")
    r = subprocess.run([sys.executable, "-B", "-c", probe, str(FILM / "engine"), str(FILM / "tests"), str(ROOT / "scripts"),
                        str(FILM / "tests/fixtures/neutral-en"), str(work / "L/probe")], capture_output=True, text=True, env=ENV)
    check(r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "[]", f"a project without a timeline block never loads the "
                                                                          f"bridge or nfp/timeline ({r.stdout.strip()[-60:] or r.stderr[-200:]})")
    none_d = make_project(work, "no-images", [], extra_clips=[
        {"id": "shot-street", "track": "pictures", "kind": "svg-shot", "start": 0, "end": 78, "ref": "street"},
        {"id": "n1", "track": "voice", "kind": "narration", "start": 9, "end": 140, "ref": "s1"}])
    plain = make_project(work, "plain", [], timeline=False)
    compose_dir(none_d, work / "builds/no-images", a.fonts)
    compose_dir(plain, work / "builds/plain", a.fonts)
    check((work / "builds/no-images/story/index.html").read_bytes() == (work / "builds/plain/story/index.html").read_bytes()
          and not (work / "builds/no-images/story/assets/timeline").exists(),
          "a timeline with no image clip (only svg-shot / narration data): the page is the page without the block")

    print("\n== P page (browser, every frame)")
    src = make_project(work, "kenburns", CLIPS)
    b = work / "builds/kenburns"
    proj, ch, timing = compose_dir(src, b, a.fonts)
    page = (b / "story/index.html").read_text(encoding="utf-8")
    check(page.count('D.shot({ id: "tl-') == len(CLIPS) and len(list((b / "story/assets/timeline").iterdir())) == 4,
          f"{len(CLIPS)} image shots appended to the project's shots; the 4 used images copied to story/assets/timeline")
    rdir = b / "render-copy"
    shutil.copytree(b / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(a.gsap, rdir / "gsap.min.js")
    shots = []
    for cid, aid, s, e, cam in CLIPS:
        shots += [{"id": cid, "frame": s}, {"id": cid, "frame": (s + e) // 2}, {"id": cid, "frame": e - 1}]
    cfg = {"dir": str(rdir), "clips": [{"id": c[0], "start": c[2], "end": c[3]} for c in CLIPS], "shots": shots,
           "out": str(work / "page.json"), "out_dir": str(work / "shots")}
    (work / "shots").mkdir()
    (work / "page.cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(["node", str(HERE / "film_timeline_page.mjs"), str(work / "page.cfg.json")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("browser check failed:\n" + r.stderr[-2500:])
    R = json.loads((work / "page.json").read_text(encoding="utf-8"))
    check(not R["errors"] and R["network_requests"] == 0 and abs(R["duration"] - 15.0) < 1e-9 and not R["warns"],
          f"page runs without errors, warnings or network; timeline length {R['duration']} s")
    from PIL import Image
    for cid, aid, s, e, cam in CLIPS:
        x = R["clips"][cid]
        at, Wc, Hc = plan(cid, aid, s, e, cam)
        w, h, ext = IMAGES[aid]
        rows = {r_["f"]: r_ for r_ in x["rows"]}
        vis_ok = all(rows[f]["vis"] == ("visible" if s <= f < e else "hidden") for f in rows)
        check(x["found"] and x["par"] == "none" and abs(x["w"] / x["h"] - w / h) < 1e-5 and vis_ok,
              f"{cid} ({aid} {w}x{h} {ext}, {(cam or {}).get('preset', 'custom' if cam else 'still')}): visible exactly on frames "
              f"{s}..{e - 1}; drawn {x['w']:.0f}x{x['h']:.0f} (aspect {w / h:.4f} kept)")
        err, cover_bad, steps = 0.0, 0, []
        prev = None
        for f in range(s, e):
            r_ = rows[f]
            ps, px, py, *_ = at(f)
            err = max(err, abs(r_["s"] - ps) * 1000, abs(r_["x"] - px), abs(r_["y"] - py))
            L, T, Rr, Bb = r_["box"]
            if L > 0.01 or T > 0.01 or Rr < 1919.99 or Bb < 1079.99 or abs((Rr - L) / (Bb - T) - w / h) > 1e-4:
                cover_bad += 1
            if prev:
                steps.append(math.hypot(r_["x"] - prev["x"], r_["y"] - prev["y"]) + abs(r_["s"] - prev["s"]) * 1000)
            prev = r_
        moving = cam is not None
        smooth = not moving or (max(steps) < 3 * (sum(steps) / len(steps)) + 0.5 and max(steps) < 25)
        check(err < 0.01 and cover_bad == 0 and smooth,
              f"{cid}: every frame = the planned Ken Burns value (max error {err:.4f} px), the image covers the frame on all "
              f"{e - s} frames, steady steps (largest {max(steps or [0]):.2f}, mean {sum(steps or [0]) / max(1, len(steps)):.2f})")
        ok_px, round_ok = True, True
        for f in (s, (s + e) // 2, e - 1):
            img = np.asarray(Image.open(R["shots"][f"{cid}-{f}"]).convert("RGB")).astype(int)
            edge = np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])
            if (np.abs(edge - np.array([10, 5, 8])).sum(axis=1) < 30).any():
                ok_px = False
            dk = disk(img)
            _, _, _, ecx, ecy, er = at(f)
            if dk is None or abs(dk[0] - ecx) > 1.5 or abs(dk[1] - ecy) > 1.5 or abs(dk[3] / dk[4] - 1) > 0.02 or abs(dk[2] - er) > 2:
                round_ok = False
        check(ok_px and round_ok, f"{cid}: screenshots - no background at any edge; the disk is round, where and as large as planned")

    print("\n== E errors (compose stops)")
    cases = [
        ("missing", lambda reg, d: (d / "media/wide.png").unlink(), CLIPS[:1], "file not found"),
        ("sha", lambda reg, d: reg["assets"][0].update(sha256="0" * 64), CLIPS[:1], "sha256 is"),
        ("size", lambda reg, d: reg["assets"][0].update(width=3000), CLIPS[:1], "pixels, recorded"),
        ("small", None, [("c-small", "small", 15, 60, None)], "enlarged 2.40x"),
        ("draft", lambda reg, d: reg["assets"][0].update(license_verified=False), CLIPS[:1], "not allowed in a final timeline"),
        ("empty", None, [("c-e", "wide", 15, 60, {"from": {"scale": 1, "x": 0.2, "y": 0.5}})], "would show empty space"),
    ]
    for name, edit, clips, want in cases:
        d = make_project(work, f"err-{name}", clips, assets_edit=edit)
        msg = try_compose(d, work / "builds" / f"err-{name}", a.fonts)
        check(want in msg and "ERROR (timeline)" in msg, f"{name}: {msg[:130]}")
    d = make_project(work, "err-video", [], extra_clips=[{"id": "v", "track": "pictures", "kind": "map", "start": 0, "end": 30}])
    msg = try_compose(d, work / "builds/err-video", a.fonts)
    check("not drawn yet" in msg, f"a clip kind of a later stage (map / video): {msg[:110]}")
    d = make_project(work, "draft-ok", CLIPS[:1], mode="draft", assets_edit=lambda reg, d: reg["assets"][0].update(license_verified=False))
    check(try_compose(d, work / "builds/draft-ok", a.fonts) == "composed", "a draft timeline may preview a draft asset (reported as a warning)")

    if a.no_render:
        print("\n(render skipped)")
    else:
        print("\n== R real render 1080p30 (HyperFrames, local)")
        env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=a.browser, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
        npx = ["npx", "--yes", f"hyperframes@{HF_VERSION}"]
        lint = subprocess.run(npx + ["lint"], cwd=rdir, env=env, capture_output=True, text=True)
        check(lint.returncode == 0 and re.search(r"\b0 error", lint.stdout + lint.stderr),
              f"HyperFrames {HF_VERSION} lint: {' | '.join((lint.stdout + lint.stderr).strip().splitlines()[-2:])[:160]}")
        out = b / "story.mp4"
        rr = subprocess.run(npx + ["render", "--output", str(out), "--fps", "30", "--quality", "standard"], cwd=rdir, env=env,
                            capture_output=True, text=True)
        (b / "render.log").write_text(rr.stdout + rr.stderr, encoding="utf-8")
        check(rr.returncode == 0 and out.exists(), f"HyperFrames render -> {out.name} "
                                                  f"{[ln for ln in (rr.stdout + rr.stderr).splitlines() if 'rendered in' in ln][-1:] or (rr.stdout + rr.stderr)[-200:]}")
        if rr.returncode != 0:
            sys.exit(1)
        pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(out)],
                                       capture_output=True, text=True, check=True).stdout)
        v = next(s_ for s_ in pr["streams"] if s_["codec_type"] == "video")
        au = [s_ for s_ in pr["streams"] if s_["codec_type"] == "audio"]
        check((v["width"], v["height"], v["avg_frame_rate"], v["codec_name"]) == (1920, 1080, "30/1", "h264") and au and
              au[0]["codec_name"] == "aac" and abs(float(pr["format"]["duration"]) - 15.0) < 0.1 and int(v.get("nb_frames", 450)) == 450,
              f"ffprobe: {v['width']}x{v['height']} {v['avg_frame_rate']} {v['codec_name']} + {au[0]['codec_name'] if au else 'NO AUDIO'}, "
              f"{float(pr['format']['duration']):.2f} s, {v.get('nb_frames')} frames")
        import verify as V
        try:
            V.verify(proj, ch, b, mp4_name="story.mp4", expect=(1920, 1080), tag="")
        except SystemExit:
            pass
        vr = json.loads((b / "verify.json").read_text(encoding="utf-8"))
        check(vr.get("problems") == [], f"verify.py on the MP4: problems {vr.get('problems')}")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 1080, 1920, 3)
        check(len(frames) == 450, f"{len(frames)} decoded frames")
        for cid, aid, s, e, cam in CLIPS:
            at, _, _ = plan(cid, aid, s, e, cam)
            worst, missing = 0.0, []
            for f in range(s, e):
                dk = disk(frames[f, :850].astype(int))
                _, _, _, ecx, ecy, er = at(f)
                if dk is None:
                    missing.append(f)
                    continue
                worst = max(worst, abs(dk[0] - ecx), abs(dk[1] - ecy), abs(dk[2] - er))
            def this_disk(f, ref):
                """Is THIS clip's disk (its planned place and size) on frame f? (the scene itself may have white parts:
                a label, a light ray - those are not the clip's image)"""
                d = disk(frames[f, :850].astype(int))
                _, _, _, ecx, ecy, er = at(ref)
                return d is not None and abs(d[0] - ecx) < 20 and abs(d[1] - ecy) < 20 and abs(d[2] - er) < 0.1 * er
            before = this_disk(s - 1, s) if s - 1 not in [c[3] - 1 for c in CLIPS] else "next"
            after = this_disk(e, e - 1) if e not in [c[2] for c in CLIPS] else "next"
            check(not missing and worst < 4 and before in (False, "next") and after in (False, "next"),
                  f"{cid}: in the MP4 the disk is on every frame {s}..{e - 1}"
                  f"{'' if before == 'next' else f', not on {s - 1}'}{'' if after == 'next' else f', not on {e}'}; "
                  f"position / size within {worst:.2f} px of the plan")
        shutil.copyfile(out, work / "timeline_t2_1080p30.mp4")
        print(f"   MP4: {work / 'timeline_t2_1080p30.mp4'}")
    print(f"   screenshots: {work / 'shots'}")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL FILM TIMELINE T2 TESTS PASSED" if not f else "FILM TIMELINE T2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
