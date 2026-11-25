#!/usr/bin/env python3
"""T4 - video clips of nfp/timeline on the Film page (engine/timeline_bridge.py), proven on a real HyperFrames render.

  python3 nfp/film/tests/film_video_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir> --work <dir outside repo>

Test videos are made locally with ffmpeg (the T3 method): every source frame carries its own number as a 12-bit barcode
(row 1) and its inverse (row 2); the decoder compares the two rows, so the film look laid over the video (grain,
vignette) cannot fake a frame number. The 30 fps source also carries a loud 1 kHz tone that must NOT reach the film.

  L legacy   no timeline block -> byte-identical to the committed Film (HEAD); an image-only timeline (T2) composes
             byte-identically to before T4; nothing is inserted without video clips
  Q files    ffprobe gate: 24 fps, variable frame rate, MPEG-4 part 2, yuv444p, a start offset, a rotation flag, wrong
             size / duration in the registry, a missing file, reading past the last frame, a wrong 'out', a video over
             an image, a video on an overlay track -> compose stops with a clear message
  P page     <video> elements straight under the root, before the SVG layer, muted, frame window + in-point exact;
             the Director's world hidden exactly on the video frames (browser, every frame)
  R render   HyperFrames 1920x1080 30 fps: ffprobe, verify.py; on EVERY frame the decoded source frame = the plan
             (30 fps and 25 fps sources, in-points, back-to-back cut, gaps, a clip ending on the source's last frame,
             a clip to the end of the video); no barcode outside the windows (no freeze, no early frame); the 1 kHz tone
             absent from the film's sound; vignette and grain lie over the video
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
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path[:0] = [str(FILM / "engine"), str(HERE), str(ROOT / "nfp"), str(ROOT / "scripts")]
import project as P                                     # noqa: E402
import timeline_bridge as TB                            # noqa: E402
from timeline import videofile as VF                    # noqa: E402
from film_equivalence_check import CDN                  # noqa: E402
from film_render_check import HF_VERSION, BROWSER       # noqa: E402
from film_subtitle_check import compose_outputs         # noqa: E402
from film_timeline_check import compose_dir, make_image, sha, CLIPS as T2_CLIPS, make_project as t2_project  # noqa: E402

RESULTS = []
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# id, file, fps, frames, size, extra ffmpeg output args
GOOD = {"v30": ("v30.mp4", 30, 600, (1920, 1080)), "v25": ("v25.mp4", 25, 500, (1280, 720))}
# clip id, asset, start, end, in
VCLIPS = [("v-a", "v30", 15, 75, 0),           # from the first frame
          ("v-b", "v30", 90, 150, 150),        # mid-source in-point, after a gap
          ("v-c", "v25", 150, 195, 0),         # 25 fps, cut straight after v-b
          ("v-d", "v30", 300, 330, 570),       # ends exactly on the source's last frame (599)
          ("v-e", "v25", 380, 450, 7)]         # 25 fps, in-point 7 (0.28 s), to the end of the video
IMG = ("i-a", "wide", 210, 270)                # a T2 still image between them


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", *args], check=True)


def make_video(path, fps, frames, size, tone=False, extra_in=(), extra_out=(), vf_extra=""):
    w, h = size
    bits = "mod(floor(N/pow(2,floor(X*12/W))),2)"
    geq = f"lum='if(lt(Y,H/6),255*{bits},if(lt(Y,H/3),255*(1-{bits}),70))'"
    vf = f"format=gray,geq={geq},drawtext=fontfile={FONT}:text='%{{n}}':fontsize={h // 4}:fontcolor=white:x=(w-tw)/2:y={h // 2},format=yuv420p{vf_extra}"
    args = [*extra_in, "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}"]
    if tone:
        args += ["-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=48000"]
    args += ["-frames:v", str(frames), "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "60", "-bf", "2"]
    if tone:
        args += ["-c:a", "aac", "-b:a", "128k", "-t", str(frames / fps)]
    ff(*args, *extra_out, "-y", str(path))


def decode(frame):
    """Source frame number from the barcode (full-frame 16:9 video), or None. Rows compared with each other."""
    r1, r2 = frame[90].astype(int).mean(axis=1), frame[270].astype(int).mean(axis=1)
    n = 0
    for b in range(12):
        x = int((b + 0.5) * 1920 / 12)
        a, c = r1[x - 20:x + 20].mean(), r2[x - 20:x + 20].mean()
        if abs(a - c) < 60:
            return None
        n |= (1 if a > c else 0) << b
    return n


def asset(aid, rel, base, kind, w, h, dur=None):
    return {"id": aid, "kind": kind, "local_path": rel, "sha256": sha(base / rel), "width": w, "height": h, "duration": dur,
            "source_url": None, "author": "NFP test", "license": "original", "license_url": None, "retrieved_at": "2026-11-24",
            "modifications": "none", "license_verified": True, "attribution": "Test media: NFP", "restrictions": [], "real_person": False}


def project(work, name, vclips, image=True, edit=None, extra=(), videos=None):
    d = work / "projects" / name
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(FILM / "tests/fixtures/neutral-en", d)
    (d / "media").mkdir()
    reg = {"schema": "nfp.assets/1", "assets": []}
    for aid, (f, fps, frames, (w, h)) in (videos or GOOD).items():
        shutil.copyfile(work / "videos" / f, d / "media" / f)
        reg["assets"].append(asset(aid, f"media/{f}", d, "video", w, h, frames / fps))
    shutil.copyfile(work / "videos" / "wide.png", d / "media" / "wide.png")
    reg["assets"].append(asset("wide", "media/wide.png", d, "image", 3200, 1800))
    clips = [dict({"id": c, "track": "pictures", "kind": "video", "start": s, "end": e, "asset": a}, **({"in": i} if i else {}))
             for c, a, s, e, i in vclips]
    if image:
        clips.append({"id": IMG[0], "track": "pictures", "kind": "image", "start": IMG[2], "end": IMG[3], "asset": IMG[1],
                      "camera": {"preset": "zoom-in"}})
    tl = {"schema": "nfp.timeline/1", "fps": 30, "duration": 450, "mode": "final",
          "tracks": [{"id": "pictures", "kind": "visual"}, {"id": "over", "kind": "overlay"}], "clips": clips + list(extra)}
    if edit:
        edit(reg, tl, d)
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


def expected(k):
    for cid, aid, s, e, first in VCLIPS:
        if s <= k < e:
            return cid, VF.shown(k, s, first, GOOD[aid][1])
    return None, None


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
    vd = work / "videos"
    vd.mkdir(parents=True)
    make_video(vd / "v30.mp4", 30, 600, (1920, 1080), tone=True)
    make_video(vd / "v25.mp4", 25, 500, (1280, 720))
    make_video(vd / "v24.mp4", 24, 96, (1280, 720))
    make_video(vd / "vfr.mp4", 30, 90, (1280, 720), vf_extra=",setpts='N/30/TB+if(gte(N\\,40)\\,0.05/TB\\,0)'", extra_out=("-fps_mode", "vfr"))
    ff("-i", str(vd / "v25.mp4"), "-frames:v", "50", "-c:v", "mpeg4", "-q:v", "3", "-y", str(vd / "mpeg4.mp4"))
    ff("-i", str(vd / "v25.mp4"), "-frames:v", "50", "-c:v", "libx264", "-pix_fmt", "yuv444p", "-y", str(vd / "yuv444.mp4"))
    ff("-i", str(vd / "v25.mp4"), "-frames:v", "50", "-c:v", "libx264", "-output_ts_offset", "0.5", "-y", str(vd / "offset.mp4"))
    rot_ok = subprocess.run(["ffmpeg", "-v", "error", "-display_rotation", "90", "-i", str(vd / "v25.mp4"), "-c", "copy", "-y",
                             str(vd / "rotated.mp4")], capture_output=True).returncode == 0
    make_image(vd / "wide.png", 3200, 1800)
    for f in ("v30.mp4", "v25.mp4"):
        fx = VF.facts(TB.probe(vd / f))
        check(not VF.check(fx), f"test video {f}: {fx['codec']} {fx['pix_fmt']} {fx['width']}x{fx['height']} {fx['fps']} fps CFR, "
                                f"{fx['frames']} frames, audio streams {fx['audio']} - accepted by the gate")

    head_rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(f"\n== L legacy (byte-identical to the committed Film {head_rev[:7]}) and T2 unchanged")
    head = work / "head"
    head.mkdir()
    arch = subprocess.run(["git", "-C", str(ROOT), "archive", head_rev], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(head)], input=arch.stdout, check=True)
    for fx in ("neutral-en", "cast-en", "cast-fa"):
        f = FILM / "tests/fixtures" / fx
        old, _ = compose_outputs(head, f, work / "L" / fx / "old", a.fonts)
        new, _ = compose_outputs(ROOT, f, work / "L" / fx / "new", a.fonts)
        check(old == new and len(new) >= 3, f"{fx}: {', '.join(sorted(new))} byte-identical to {head_rev[:7]}")
    # an image-only (T2) timeline: the page made by the T2 bridge (kept in the scratch baseline) vs now
    (work / "images").mkdir()
    for aid, (w, h, ext) in {"wide": (3200, 1800, "png"), "four3": (2400, 1800, "jpg"), "tall": (2400, 3600, "png"),
                             "pano": (6000, 1500, "jpg"), "small": (800, 450, "png")}.items():
        make_image(work / "images" / f"{aid}.{ext}", w, h)
    t2p = t2_project(work, "t2-images", T2_CLIPS)
    compose_dir(t2p, work / "builds/t2-now", a.fonts)
    old_bridge = work / "t2bridge"
    old_bridge.mkdir()
    tar = Path(os.environ.get("T4_PRE_TAR", ""))
    if tar.is_file():
        subprocess.run(["tar", "-x", "-C", str(old_bridge), "-f", str(tar)], check=True)
        r = subprocess.run([sys.executable, "-B", "-c",
                            "import sys, json; sys.path[:0] = sys.argv[1:4]; import film_timeline_check as T; "
                            "from pathlib import Path; T.compose_dir(Path(sys.argv[4]), Path(sys.argv[5]), sys.argv[6])",
                            str(old_bridge / "nfp/film/engine"), str(old_bridge / "nfp"), str(FILM / "tests"), str(t2p),
                            str(work / "builds/t2-before"), a.fonts],
                           capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=f"{old_bridge / 'nfp/film/engine'}:{old_bridge / 'nfp'}:{ROOT / 'scripts'}"))
        same = r.returncode == 0 and (work / "builds/t2-before/story/index.html").read_bytes() == (work / "builds/t2-now/story/index.html").read_bytes()
        check(same, f"an image-only timeline (T2): the page is byte-identical to the one the T2 bridge made {r.stderr[-200:]}")
    else:
        check(False, "T4_PRE_TAR (the files before T4) not given: the T2 page cannot be compared")
    page = (work / "builds/t2-now/story/index.html").read_text(encoding="utf-8")
    check("<video" not in page and "timeline (nfp/timeline T4)" not in page, "without video clips nothing of T4 is in the page")

    print("\n== Q file gate and frame rules (compose stops)")
    bad_videos = {"v24": ("v24.mp4", 24, 96, (1280, 720)), "vfr": ("vfr.mp4", 30, 90, (1280, 720)),
                  "mp4v": ("mpeg4.mp4", 25, 50, (1280, 720)), "y444": ("yuv444.mp4", 25, 50, (1280, 720)),
                  "offs": ("offset.mp4", 25, 50, (1280, 720))}
    if rot_ok:
        bad_videos["rot"] = ("rotated.mp4", 25, 500, (1280, 720))
    for aid, want in (("v24", "only 25 and 30 fps"), ("vfr", "variable frame rate"), ("mp4v", "only H.264"),
                      ("y444", "only yuv420p"), ("offs", "not 0"), ("rot", "rotation")):
        if aid not in bad_videos:
            print(f"   (skipped {aid}: this ffmpeg cannot write the rotation flag)")
            continue
        d = project(work, f"bad-{aid}", [(f"c-{aid}", aid, 15, 30, 0)], image=False, videos={aid: bad_videos[aid]})
        msg = try_compose(d, work / "builds" / f"bad-{aid}", a.fonts)
        check(want in msg and "ERROR (timeline)" in msg, f"{aid}: {msg[:150]}")
    cases = [
        ("past-end", [("c", "v30", 300, 340, 570)], None, "past its end the last frame would freeze"),
        ("bad-out", [("c", "v30", 15, 75, 0)], lambda reg, tl, d: tl["clips"][0].update(out=61), "out must be 60"),
        ("size", [("c", "v30", 15, 75, 0)], lambda reg, tl, d: reg["assets"][0].update(width=1280, height=720), "recorded 1280x720"),
        ("duration", [("c", "v30", 15, 75, 0)], lambda reg, tl, d: reg["assets"][0].update(duration=19.0), "recorded duration 19.0"),
        ("missing", [("c", "v30", 15, 75, 0)], lambda reg, tl, d: (d / "media/v30.mp4").unlink(), "file not found"),
        ("over-image", [("c", "v30", 200, 240, 0)], None, "overlap"),
        ("overlay", [], lambda reg, tl, d: tl["clips"].append({"id": "o", "track": "over", "kind": "video", "start": 0, "end": 30,
                                                                "asset": "v30"}), "overlay track"),
    ]
    for name, vc, edit, want in cases:
        d = project(work, f"err-{name}", vc, image=(name == "over-image"), edit=edit)
        msg = try_compose(d, work / "builds" / f"err-{name}", a.fonts)
        check(want in msg, f"{name}: {msg[:160]}")
    d = project(work, "exact-end", [("c", "v30", 300, 330, 570)], image=False,
                edit=lambda reg, tl, d: tl["clips"][0].update(out=600))
    check(try_compose(d, work / "builds/exact-end", a.fonts) == "composed", "a clip ending exactly on the last source frame (out = 600 = frames) is accepted")

    print("\n== P page")
    src = project(work, "video", VCLIPS)
    b = work / "builds/video"
    proj, ch, timing = compose_dir(src, b, a.fonts)
    page = (b / "story/index.html").read_text(encoding="utf-8")
    tags = re.findall(r"<video [^>]*>", page)
    art = page.index('<section id="art"')
    ok = len(tags) == len(VCLIPS) and all(page.index(t) < art for t in tags) and all(" muted " in t and "data-has-audio" not in t for t in tags)
    for (cid, aid, s, e, first), t in zip(VCLIPS, tags):
        fps = GOOD[aid][1]
        ok &= (f'id="tlv-{cid}"' in t and f'data-start="{s / 30!r}"' in t and f'data-duration="{(e - s) / 30!r}"' in t
               and f'data-media-start="{float(Fraction(first, fps))!r}"' in t)
    check(ok, f"{len(tags)} <video> under the root before the SVG layer, muted, frame window and in-point exact")
    check(sorted(p.name for p in (b / "story/assets/timeline").iterdir()) == ["v25.mp4", "v30.mp4", "wide.png"]
          and sha(b / "story/assets/timeline/v30.mp4") == sha(work / "videos/v30.mp4"), "the media copied unchanged to story/assets/timeline")
    rdir = b / "render-copy"
    shutil.copytree(b / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(a.gsap, rdir / "gsap.min.js")
    probe_js = r"""
const { createRequire } = await import("node:module"); const fs = await import("node:fs");
const { chromium } = createRequire(import.meta.url)("playwright");
const [dir, out] = process.argv.slice(2); const errors = [];
const br = await chromium.launch(); const pg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
pg.on("pageerror", (e) => errors.push(String(e)));
await pg.route("**/*", (r) => r.request().url().startsWith("file:") ? r.continue() : r.abort());
await pg.goto("file://" + dir + "/index.html");
await pg.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
const r = await pg.evaluate(() => { const tl = window.__timelines.main, w = document.getElementById("world"), v = [];
  for (let f = 0; f <= 450; f++) { tl.seek(f / 30, false); const b = w.getBoundingClientRect();
    v.push(getComputedStyle(w).display !== "none" && b.width > 0 && b.height > 0 ? "visible" : "hidden"); }
  return { vis: v, warns: window.__docuWarnings || [], dur: tl.duration() }; });
r.errors = errors; fs.writeFileSync(out, JSON.stringify(r)); await br.close();"""
    (work / "page.mjs").write_text(probe_js, encoding="utf-8")
    r = subprocess.run(["node", str(work / "page.mjs"), str(rdir), str(work / "page.json")], capture_output=True, text=True,
                       cwd=str(HERE))
    R = json.loads((work / "page.json").read_text(encoding="utf-8")) if r.returncode == 0 else {"vis": [], "errors": [r.stderr[-300:]]}
    want = ["hidden" if expected(k)[0] else "visible" for k in range(451)]
    want[450] = "visible"
    check(R["vis"] == want and not R["errors"] and not R.get("warns") and abs(R.get("dur", 0) - 15) < 1e-9,
          f"browser: the Director's world (every shot in it) is not drawn exactly on the {sum(1 for x in want if x == 'hidden')} video frames, "
          f"shown on all others; no errors / warnings {R['errors'][:1]}")

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
                                              f"{[ln for ln in (rr.stdout + rr.stderr).splitlines() if 'rendered in' in ln][-1:] or (rr.stdout + rr.stderr)[-300:]}")
    if rr.returncode != 0:
        sys.exit(1)
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(out)],
                                   capture_output=True, text=True, check=True).stdout)
    v = next(s_ for s_ in pr["streams"] if s_["codec_type"] == "video")
    au = [s_ for s_ in pr["streams"] if s_["codec_type"] == "audio"]
    check((v["width"], v["height"], v["avg_frame_rate"], v["codec_name"]) == (1920, 1080, "30/1", "h264") and len(au) == 1 and
          au[0]["codec_name"] == "aac" and abs(float(pr["format"]["duration"]) - 15.0) < 0.1 and int(v.get("nb_frames", 0)) == 450,
          f"ffprobe: {v['width']}x{v['height']} {v['avg_frame_rate']} {v['codec_name']} + {[x['codec_name'] for x in au]}, "
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
    got = [decode(f) for f in frames]
    for cid, aid, s, e, first in VCLIPS:
        exact = [k for k in range(s, e) if got[k] == VF.shown(k, s, first, GOOD[aid][1])]
        lo, hi = VF.source_frames(s, e, first, GOOD[aid][1])
        check(len(exact) == e - s, f"{cid} ({aid}, {GOOD[aid][1]} fps): frames {s}..{e - 1} show source frames {lo}..{hi - 1} - "
                                   f"{len(exact)}/{e - s} exact {[(k, got[k]) for k in range(s, e) if k not in exact][:4]}")
    outside = [k for k in range(450) if expected(k)[0] is None and got[k] is not None]
    check(not outside, f"no video frame outside the clip windows (gaps, the image clip, before / after): {outside[:6]}")
    check(got[329] == 599 and got[330] is None, f"the clip ending on the last source frame shows 599 on its last frame, nothing after "
                                                f"(no freeze): frame 329 -> {got[329]}, 330 -> {got[330]}")
    check(got[149] == 209 and got[150] == 0, f"back-to-back cut v-b -> v-c on frame 150: 149 -> {got[149]}, 150 -> {got[150]}")
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-ac", "1", "-ar", "48000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    sig = np.frombuffer(pcm, np.int16).astype(float)
    seg = sig[int(0.5 * 48000):int(2.5 * 48000)]                    # 0.5 - 2.5 s: video v-a with the 1 kHz tone in its file
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1 / 48000)
    tone = spec[(freqs > 990) & (freqs < 1010)].max()
    voice = spec[(freqs > 186) & (freqs < 206)].max()
    src = subprocess.run(["ffmpeg", "-v", "error", "-i", str(work / "videos/v30.mp4"), "-ac", "1", "-ar", "48000", "-t", "2", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    s2 = np.frombuffer(src, np.int16).astype(float)
    src_tone = np.abs(np.fft.rfft(s2 * np.hanning(len(s2))))[(np.fft.rfftfreq(len(s2), 1 / 48000) > 990) & (np.fft.rfftfreq(len(s2), 1 / 48000) < 1010)].max()
    check(src_tone > 1e6 and tone < voice / 100 and tone < src_tone / 1000,
          f"the video's own 1 kHz tone does not reach the film (tone/voice {tone / voice:.5f}; vs the file {tone / src_tone:.6f})")
    flat = frames[100:110, 400:500].astype(float).mean(axis=3)       # flat grey band of v-b (source value 70, no digits)
    centre = flat[:, :, 860:1060].mean()
    edge = flat[:, :, 20:120].mean()
    grain = np.abs(np.diff(frames[100:110, 400:500, 860:1060].astype(float).mean(axis=3), axis=0)).mean()
    src_f = subprocess.run(["ffmpeg", "-v", "error", "-i", str(work / "videos/v30.mp4"), "-vf", "select='between(n\\,85\\,94)'", "-vsync", "0",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    sf = np.frombuffer(src_f, np.uint8).reshape(-1, 1080, 1920, 3)[:, 400:500, 860:1060].astype(float).mean(axis=3)
    src_grain = np.abs(np.diff(sf, axis=0)).mean()
    check(edge < centre * 0.95 and grain > src_grain + 1.0,
          f"the film look lies over the video: vignette (edge {edge:.1f} vs centre {centre:.1f}), grain (frame-to-frame change "
          f"{grain:.2f} vs {src_grain:.2f} in the file)")
    shutil.copyfile(out, work / "timeline_t4_1080p30.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-vf", "select='eq(n\\,74)+eq(n\\,80)+eq(n\\,149)+eq(n\\,150)+eq(n\\,240)+eq(n\\,329)+eq(n\\,330)+eq(n\\,449)',"
                    "scale=480:270,tile=4x2", "-frames:v", "1", "-y", str(work / "sheet.png")], check=True)
    print(f"   MP4: {work / 'timeline_t4_1080p30.mp4'}   sheet: {work / 'sheet.png'}")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL FILM VIDEO T4 TESTS PASSED" if not f else "FILM VIDEO T4 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
