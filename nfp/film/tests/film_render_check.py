#!/usr/bin/env python3
"""F8 - a real short render of a Film page: 1920x1080, 30 fps, H.264 + AAC, verified by engine/verify.py.

  python3 nfp/film/tests/film_render_check.py --gsap <local gsap.min.js 3.12.5> --fonts <dir> --work <dir outside repo>

The 10-second variant of the Persian cast fixture (2 sentences, 2 shots, 3 C3 characters, the man speaks s2) is composed
with a SYNTHETIC tone narration at the word times (no TTS, no API); the only change for the local render is the GSAP
tag (cdnjs -> local copy). HyperFrames lint + render; ffprobe; verify.py (size, fps, duration, audio onset, caption
highlight, exposure, cuts) with the expected size fixed at 1920x1080; there is no 720p step anywhere in nfp/film.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(FILM / "engine"))
sys.path.insert(0, str(ROOT / "nfp"))
sys.path.insert(0, str(ROOT / "scripts"))
HF_VERSION = "0.9.83"          # the HyperFrames version every NFP render test uses (studio/tests/camera_local_check.py)


def synth_narration(timing, path, rate=24000):
    """A SYNTHETIC narration: a 196 Hz tone on every timed word (no TTS). Same idea as studio/tests/camera_local_check.py;
    written here because importing that module would load Studio's 9:16 project.py under the same module name."""
    import array
    import math
    import wave
    n = int(round(float(timing["audio"]["total"]) * rate))
    a = array.array("h", [0]) * n
    for s in timing["sentences"]:
        for w in s["words"]:
            if w["abs_start"] is None:
                continue
            i0, i1 = int(w["abs_start"] * rate), min(n, int(w["abs_end"] * rate))
            for k in range(i0, i1):
                env = min(1.0, (k - i0) / 240, (i1 - k) / 240)
                a[k] = int(9000 * env * math.sin(2 * math.pi * 196 * (k - i0) / rate))
    with wave.open(str(path), "wb") as wv:
        wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(rate); wv.writeframes(a.tobytes())

from film_cast_check import variant  # noqa: E402
from film_equivalence_check import CDN, synth_timing  # noqa: E402
import cast_plan as CP  # noqa: E402
import compose as C  # noqa: E402
import project as P  # noqa: E402

RESULTS = []
BROWSER = "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def ten_seconds(p):
    p["meta"]["target_duration"] = 10
    p["chapters"][0]["sentences"] = p["chapters"][0]["sentences"][:2]
    p["characters"] = [e for e in p["characters"] if e["shot"] != "stage"]
    for e in p["characters"]:
        if e["shot"] == "room":
            e["to"] = "end"


def ten_seconds_shots(s):
    s = s.replace('b: W("s3", 0), bg: K.bg.livingRoom()', 'b: "end", bg: K.bg.livingRoom()')
    return s[:s.index('D.shot({ id: "stage"')]


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    ap.add_argument("--browser", default=BROWSER)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    work.mkdir(parents=True, exist_ok=True)
    src = variant(work, "render-fa", ten_seconds, ten_seconds_shots, base=HERE / "fixtures" / "cast-fa")
    proj = P.load(src)
    ch = proj["chapters"][0]
    timing = synth_timing(ch)
    b = work / "render"
    if b.exists():
        shutil.rmtree(b)
    b.mkdir(parents=True)
    (b / "timing.json").write_text(json.dumps(timing, ensure_ascii=False), encoding="utf-8")
    synth_narration(timing, b / "narration.wav")
    ke, fr, rep = CP.fragment(proj, ch, timing, b)
    info = C.compose(proj, ch, timing, b, a.fonts, b / "narration.wav", cast_fragment=fr, kit_extra=ke)
    check(info["duration"] == 10.0 and info["lang"] == "fa" and rep and len(rep["instances"]) == 3,
          f"10 s Persian page with {len(rep['instances'])} C3 characters composed ({rep['summary']})")
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    rdir = b / "render-copy"
    shutil.copytree(b / "story", rdir)
    new = page.replace(CDN, '<script src="gsap.min.js"></script>')
    diff = [i for i, (x, y) in enumerate(zip(page.splitlines(), new.splitlines())) if x != y]
    check(page.count(CDN) == 1 and len(diff) == 1, "render copy differs from the product page in exactly 1 line (GSAP source)")
    (rdir / "index.html").write_text(new, encoding="utf-8")
    shutil.copyfile(a.gsap, rdir / "gsap.min.js")

    env = dict(os.environ, HYPERFRAMES_BROWSER_PATH=a.browser, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    npx = ["npx", "--yes", f"hyperframes@{HF_VERSION}"]
    lint = subprocess.run(npx + ["lint"], cwd=rdir, env=env, capture_output=True, text=True)
    tail = " | ".join((lint.stdout + lint.stderr).strip().splitlines()[-2:])
    check(lint.returncode == 0 and re.search(r"\b0 error", lint.stdout + lint.stderr), f"HyperFrames {HF_VERSION} lint: {tail[:200]}")
    out = b / "story.mp4"
    r = subprocess.run(npx + ["render", "--output", str(out), "--fps", "30", "--quality", "standard"], cwd=rdir, env=env,
                       capture_output=True, text=True)
    (b / "render.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    done = [ln for ln in (r.stdout + r.stderr).splitlines() if "rendered in" in ln]
    check(r.returncode == 0 and out.exists(), f"HyperFrames render -> MP4 {'; '.join(done)[:160] or (r.stdout + r.stderr)[-300:]}")
    if r.returncode != 0:
        sys.exit(1)
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(out)],
                                   capture_output=True, text=True, check=True).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    check((v["width"], v["height"], v["avg_frame_rate"], v["codec_name"]) == (1920, 1080, "30/1", "h264") and au and au[0]["codec_name"] == "aac"
          and abs(float(pr["format"]["duration"]) - 10.0) < 0.1,
          f"ffprobe: {v['width']}x{v['height']} {v['avg_frame_rate']} {v['codec_name']} + {au[0]['codec_name'] if au else 'NO AUDIO'}, "
          f"{float(pr['format']['duration']):.2f}s, {int(pr['format']['size']) // 1024} KB")
    import verify as V
    try:
        V.verify(proj, ch, b, mp4_name="story.mp4", expect=(1920, 1080), tag="")
    except SystemExit:
        pass
    res = json.loads((b / "verify.json").read_text(encoding="utf-8"))
    check(res.get("problems") == [], f"verify.py on the MP4: problems {res.get('problems')}; video {res.get('video')}; "
                                     f"audio onset vs first word {res.get('mp4_audio_onset_vs_first_word_ms')} ms")
    film_src = "".join(p.read_text(encoding="utf-8") for p in (FILM / "engine").glob("*.py") if p.name != "verify.py")
    check(not re.search(r"1280|720p|scale=", film_src) and "expect=(1920, 1080)" in (FILM / "engine" / "run.py").read_text(encoding="utf-8"),
          "no 720p step in nfp/film: no scaling in the engine, run.py verifies 1920x1080 only")
    for t in (0.5, 5.0, 9.8):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", str(work / f"frame_{t}.png")], check=True)
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL RENDER TESTS PASSED" if not f else "RENDER TESTS FAILED"))
    print(f"mp4: {out}")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
