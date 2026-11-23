#!/usr/bin/env python3
"""
T3 + T4 for the Camera Motion Engine, run locally (no GitHub Actions, no Gemini, no TTS).

  python3 studio/tests/camera_local_check.py --project motion-demo-fa --timing timing.json \
      --fonts <dir with vazirmatn-arabic-400/700-normal.woff2> --gsap <gsap.min.js 3.12.5> --work <dir> [--render]

1. composes the project twice into <work>: plain (unchanged compose.py) and camera (run_motion.compose_with_camera)
2. narration.wav: a SYNTHETIC tone track at the word times of --timing (only to give the MP4 an audio stream and a
   measurable speech onset; it is not speech and nothing is sent anywhere)
3. T3: studio/tests/camera_timeline_check.mjs (Playwright) compares both pages
4. T4 (--render): renders both with HyperFrames into MP4, runs the LOCKED Stage 2 verify on each, then measures in
   the video that the camera moves (media/graphics regions change) while the caption band matches the plain video.

The rendered copies differ from the product page in exactly one line: the cdnjs GSAP <script> points to a local copy
of the same GSAP version, because cdnjs is not reachable in every sandbox. The product index.html is not modified.
"""
import argparse
import array
import json
import math
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "studio" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))

import compose as C  # noqa: E402
import project as P  # noqa: E402
import run_motion as RM  # noqa: E402
import story_stage2 as core  # noqa: E402
from camera import presets as PR  # noqa: E402

CDN = '<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>'
HF_VERSION = "0.9.83"
RESULTS = []


def check(ok, msg):
    RESULTS.append((ok, msg))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def synth_narration(timing, path, rate=24000):
    total = float(timing["audio"]["total"])
    n = int(round(total * rate))
    a = array.array("h", [0]) * n
    for s in timing["sentences"]:
        for w in s["words"]:
            if w["abs_start"] is None:
                continue
            i0, i1 = int(w["abs_start"] * rate), min(n, int(w["abs_end"] * rate))
            ln = max(1, i1 - i0)
            for k in range(i0, i1):
                env = min(1.0, (k - i0) / 240, (i1 - k) / 240)
                a[k] = int(9000 * env * math.sin(2 * math.pi * 196 * (k - i0) / rate))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(a.tobytes())


def compose_both(name, timing, fonts, work):
    proj = P.load(name)
    theme = P.load_theme(proj["meta"]["theme"])
    out = {}
    for kind in ("plain", "camera"):
        b = work / kind
        if b.exists():
            shutil.rmtree(b)
        b.mkdir(parents=True)
        (b / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
        synth_narration(timing, b / "narration.wav")
        if kind == "plain":
            C.compose(P.load(name), theme, timing, b, fonts, b / "narration.wav")
        else:
            _, compiled = RM.compose_with_camera(P.load(name), theme, b, fonts, b / "narration.wav", P.PROJECTS / name)
            check(compiled is not None and len(compiled["tweens"]) > 0, f"camera compose: {len(compiled['tweens'])} tweens")
        out[kind] = b
    return proj, theme, out


def local_copy(build, gsap):
    """story/ -> render/ with the GSAP script pointed at a local file (the only difference)."""
    src, dst = build / "story", build / "render"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    page = (dst / "index.html").read_text(encoding="utf-8")
    if page.count(CDN) != 1:
        raise SystemExit("expected exactly one cdnjs GSAP script tag")
    (dst / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(gsap, dst / "gsap.min.js")
    a = (src / "index.html").read_text(encoding="utf-8").splitlines()
    b = (dst / "index.html").read_text(encoding="utf-8").splitlines()
    diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    check(len(a) == len(b) and len(diff) == 1, "render copy differs from the product page in exactly 1 line (GSAP source)")
    return dst


def frames(mp4, times, crop=None, w=270, h=480):
    vf = (crop + "," if crop else "") + f"scale={w}:{h}"
    import numpy as np
    out = []
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", vf,
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        out.append(np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(float))
    return out


def t4(proj, theme, builds, args):
    import numpy as np
    env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=args.browser, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    verify = {}
    for kind, b in builds.items():
        rdir = local_copy(b, args.gsap)
        cmd = ["npx", "--yes", f"hyperframes@{HF_VERSION}", "render", "--output", str(b / "story.mp4"), "--fps", "30",
               "--quality", "standard"]
        r = subprocess.run(cmd, cwd=rdir, env=env, capture_output=True, text=True)
        (b / "render.log").write_text(r.stdout + r.stderr, encoding="utf-8")
        tail = [ln for ln in (r.stdout + r.stderr).splitlines() if "rendered in" in ln]
        check(r.returncode == 0 and (b / "story.mp4").exists(), f"{kind}: HyperFrames {HF_VERSION} render {'; '.join(tail) or r.stderr[-300:]}")
        if r.returncode != 0:
            return
        core.BUILD = b
        core.SEA = tuple(theme["highlight_rgb"])
        try:
            core.cmd_verify(None)
        except SystemExit:
            pass
        v = json.loads((b / "verify.json").read_text(encoding="utf-8"))
        verify[kind] = v
        check(v.get("problems") == [] and v.get("verification_complete") is True,
              f"{kind}: locked Stage 2 verify -> problems {v.get('problems')}, complete {v.get('verification_complete')}, "
              f"{v.get('video')}, duration {v.get('duration')} / {v.get('expected_duration')}")

    # caption highlight measured by verify is the same with and without camera
    hc = [(x["sentence"], x["i"], x["highlight_pixels"], x["x"], x["y"]) for x in verify["camera"]["highlight"] if "i" in x]
    hp = [(x["sentence"], x["i"], x["highlight_pixels"], x["x"], x["y"]) for x in verify["plain"]["highlight"] if "i" in x]
    maxd = max(abs(a[2] - b[2]) for a, b in zip(hc, hp))
    posd = max(max(abs((a[3] or 0) - (b[3] or 0)), abs((a[4] or 0) - (b[4] or 0))) for a, b in zip(hc, hp))
    check(len(hc) == len(hp) and maxd <= 40 and posd <= 0.01,
          f"word highlight identical with camera: {len(hc)} words, max pixel-count difference {maxd}, max centroid shift {posd}")

    # the caption band of the camera video matches the plain video; the media / graphics regions move
    plan = json.loads((builds["camera"] / "camera_plan.json").read_text(encoding="utf-8"))
    total = float(json.loads((builds["camera"] / "timing.json").read_text(encoding="utf-8"))["audio"]["total"])
    ts = [round(0.5 + k * (total - 1.0) / 39, 3) for k in range(40)]
    band = "crop=1080:800:0:560"
    cb, pb = frames(builds["camera"] / "story.mp4", ts, band, 270, 200), frames(builds["plain"] / "story.mp4", ts, band, 270, 200)
    diffs = [float(np.abs(a - b).mean()) for a, b in zip(cb, pb)]
    check(max(diffs) < 2.0, f"caption band of the camera video = plain video at 40 times (mean abs diff max {max(diffs):.2f}/255, avg {sum(diffs) / len(diffs):.2f})")
    report = {"band_diff": diffs, "moves": []}
    for row in plan:
        mv = row.get("move")
        if not mv or "t" not in mv:
            continue
        a, z = mv["t"] + 0.6, mv["t"] + mv["d"] - 0.25
        # media: exactly its own frame (geometry from presets.FRAMES); scene graphics: the top zone y 110-540
        if mv["target"] == "media":
            f = PR.FRAMES[row["frame"]]
            fr = f"crop=1080:{f['bottom'] - f['top']}:0:{f['top']}"
        else:
            fr = "crop=1080:430:0:110"
        c = frames(builds["camera"] / "story.mp4", [a, z], fr, 360, 183)
        p = frames(builds["plain"] / "story.mp4", [a, z], fr, 360, 183)
        mc, mp = float(np.abs(c[0] - c[1]).mean()), float(np.abs(p[0] - p[1]).mean())
        report["moves"].append({"scene": row["scene"], "move": mv["move"], "target": mv["target"], "camera_change": mc, "plain_change": mp})
        check(mc > 3.0 and mc > 3 * mp + 1.0,
              f"{row['scene']} {mv['move']} on {mv['target']}: visible in the video (frame change {mc:.1f} vs {mp:.1f} without camera)")
    (builds["camera"] / "t4_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--timing", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--gsap", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--browser", default="/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell")
    ap.add_argument("--render", action="store_true")
    args = ap.parse_args()
    work = Path(args.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    timing = json.loads(Path(args.timing).read_text(encoding="utf-8"))
    proj, theme, builds = compose_both(args.project, timing, Path(args.fonts), work)
    r = subprocess.run(["node", str(HERE / "camera_timeline_check.mjs"),
                        "--camera", str(builds["camera"] / "story" / "index.html"),
                        "--plain", str(builds["plain"] / "story" / "index.html"),
                        "--plan", str(builds["camera"] / "camera_plan.json"),
                        "--gsap", args.gsap, "--out", str(work / "t3")],
                       env=dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "")))
    check(r.returncode == 0, "T3 browser timeline check")
    if args.render:
        t4(proj, theme, builds, args)
    fails = [m for ok, m in RESULTS if not ok]
    print(f"\n{len(RESULTS)} checks, " + ("ALL PASSED" if not fails else f"{len(fails)} FAILED"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
