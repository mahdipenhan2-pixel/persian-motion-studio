#!/usr/bin/env python3
"""NFP integration - ONE command makes a two-chapter Persian documentary with every engine, from real local speech to a
verified MP4 (offline after nfp/setup/fetch_assets.py; free; nothing sent anywhere):

  chapter 1  characters (Character C3 in the cast fixture's scenes: street, room, stage) + a full-frame title and a
             lower third (Graphics) + a music bed and a sound effect (Timeline audio clips) + karaoke subtitles (Subtitle)
  chapter 2  a Ken Burns still (Timeline T2), a route map with Location places (Map Motion + Location), a video clip
             (Timeline T4), an info card over the map (Graphics) + music, a sound effect, the characters' scenes between
  both       real narration and a second speaker from local Piper voices (Voice Engine, provider piper), real speech
             recognition (faster-whisper, the core's whisper step), alignment, subtitles, verify, Output QC

  the command:  python3 nfp/orchestrator/cli.py run --film <work>/film.json --build <work>/build
  then checked: film.mp4 decodes without an error, 1920x1080 30 fps h264 yuv420p + aac, 30 s = 900 frames (2 x 15 s);
  each chapter's engines report their part (cast instances, graphic clips, map clip, image / video clips, mixed audio
  clips) and in Chromium the page shows them at their time (DOM visibility); the film's frames at those times are the
  chapters' own frames (decoded md5); the music is in the film's audio; real Whisper times: the film's sentence onsets
  vs the merged timing (Output QC sync, reported); the film report's verdict and production readiness;
  a second run of the same command does nothing again; a fresh build of the same film (a second build folder)
  reproduces the same timing and verdict.
  python3 nfp/orchestrator/tests/test_orch_integration.py --work <dir outside the repository> [--keep]
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
ROOT = NFP.parent
sys.path[:0] = [str(HERE), str(NFP), str(NFP / "graphics" / "tests"), str(NFP / "film" / "tests"), str(NFP / "mapmotion" / "tests")]
import fixture as FX                              # noqa: E402
import test_graphics_g5_film as T5                # noqa: E402
import film_video_check as FVC                    # noqa: E402

RESULTS = []
CLI = HERE.parent / "cli.py"
CH2_TEXT = ["سفر ما از تهران آغاز می‌شود و آرام به سوی جنوب می‌رود.",
            "امید در خانه از راه‌های قدیمی و شهرهای کهن این سرزمین تعریف می‌کند.",
            "در پایان راه، کشتی‌ها در بندر آرام منتظر مسافران تازه هستند."]
PROBE = r"""
const { createRequire } = await import("node:module"); const fs = await import("node:fs");
const { chromium } = createRequire(import.meta.url)("playwright");
const [dir, out, spec] = process.argv.slice(2); const S = JSON.parse(spec); const errors = [];
const br = await chromium.launch(); const pg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
pg.on("pageerror", (e) => errors.push(String(e)));
await pg.route("**/*", (r) => r.request().url().startsWith("file:") ? r.continue() : r.abort());
await pg.goto("file://" + dir + "/index.html");
await pg.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 });
await pg.evaluate(async () => { await document.fonts.ready; });
const res = await pg.evaluate((S) => {
  const tl = window.__timelines.main;
  const shown = (e) => { for (let x = e; x && x.nodeType === 1; x = x.parentNode) { const cs = getComputedStyle(x);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) return false; } return true; };
  return S.map(([t, sel]) => { tl.seek(t, false); const els = [...document.querySelectorAll(sel)];
    return { t, sel, n: els.length, shown: els.filter(shown).length }; });
}, S);
fs.writeFileSync(out, JSON.stringify({ errors, res })); await br.close();
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jedit(p, fn):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    fn(d)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def audio_asset(aid, rel, d, dur):
    a = FVC.asset(aid, rel, d, "audio", None, None, dur)
    a["attribution"] = "Generated for the NFP integration test"
    return a


def make_media(work):
    T5.make_image(work / "wide.png", 3200, 1800)
    FVC.make_video(work / "v30.mp4", 30, 600, (1920, 1080))
    chord = "if(lt(mod(t\\,16)\\,4)\\,{a}\\,if(lt(mod(t\\,16)\\,8)\\,{b}\\,if(lt(mod(t\\,16)\\,12)\\,{c}\\,{d})))"
    f1, f2, f3 = (chord.format(a=x[0], b=x[1], c=x[2], d=x[3]) for x in ((220, 174.6, 261.6, 196), (261.6, 220, 329.6, 246.9), (329.6, 261.6, 392, 293.7)))
    expr = f"(0.22*sin(2*PI*{f1}*t)+0.16*sin(2*PI*{f2}*t)+0.12*sin(2*PI*{f3}*t))*(0.85+0.15*sin(2*PI*0.25*t))"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:c=stereo:d=16", str(work / "music.wav")], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anoisesrc=c=pink:r=48000:a=0.5:d=0.8", "-af",
                    "highpass=f=700,afade=t=in:d=0.2,afade=t=out:st=0.3:d=0.5", "-ac", "2", str(work / "whoosh.wav")], check=True)


def chapter(work, name, gclips, image, mapclip, video, sfx_at, texts=None, mode="final"):
    docs = {"info-fa": T5.gdoc("info-fa", mode="final", content={"title": "راه کاروان‌ها", "body": "از تهران تا بندر، راهی کهن و پرماجرا."})}
    d = T5.project(work, name, fixture="cast-fa", gclips=gclips, docs=docs, mode=mode, image=image, mapclip=mapclip, video=video)
    for f in ("music.wav", "whoosh.wav"):
        shutil.copyfile(work / f, d / "media" / f)
    jedit(d / "assets.json", lambda a: a["assets"].extend([audio_asset("music", "media/music.wav", d, 16.0),
                                                         audio_asset("whoosh", "media/whoosh.wav", d, 0.8)]))
    jedit(d / "timeline.json", lambda t: (t["tracks"].extend([{"id": "music", "kind": "audio"}, {"id": "sfx", "kind": "audio"}]),
                                          t["clips"].extend([{"id": "bed", "track": "music", "kind": "audio", "start": 0, "end": 450,
                                                              "asset": "music", "fade_in": 45, "fade_out": 45},
                                                             {"id": "hit", "track": "sfx", "kind": "audio", "start": sfx_at, "end": sfx_at + 24,
                                                              "asset": "whoosh", "gain_db": -10}])))
    pj = json.loads((d / "project.json").read_text(encoding="utf-8"))
    cast_dir = pj["cast"]["dir"]
    lock = json.loads((d / cast_dir / "cast.lock.json").read_text(encoding="utf-8"))["characters"]
    pj["voice"] = {"engine": "nfp.voice/1", "casting": "voices.cast.json", "normalize": {}, "qc": {}, "cache": str(work / "voice-cache")}
    pj["subtitles"] = {"mode": "karaoke"}
    pj["meta"]["title"] = "سفر به جنوب"
    for e in pj["characters"]:                       # an action on a shot's first frame collides with the base pose (C3 rule)
        for act in e.get("actions", []):
            if act.get("at") == ["s2", "w", 1]:
                act["at"] = ["s2", "w", 3]
    if texts:
        for s, t in zip(pj["chapters"][0]["sentences"], texts):
            s["text"] = t
    (d / "project.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "voices.cast.json").write_text(json.dumps({"schema": "nfp.voice.casting/1", "project": name, "cast_dir": cast_dir,
                                                   "rules": {"block_mismatch": False}, "narrator": {"voice": "piper:fa-amir"},
                                                   "roles": {"omid": {"voice": "piper:fa-gyro", "fingerprint": lock["omid"]}}},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def frame_md5(mp4, n):
    """md5 of decoded frame number n (by index, not by seeking: a seek may land on a neighbouring frame)."""
    return hashlib.md5(subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vf", f"select=eq(n\\,{n})", "-frames:v", "1", "-f", "rawvideo",
                                       "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    miss = subprocess.run([sys.executable, "-B", str(NFP / "setup" / "fetch_assets.py"), "--check"], capture_output=True, text=True)
    check(miss.returncode == 0, f"assets present (nfp/setup/fetch_assets.py --check): {miss.stdout.strip()}")
    git0 = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout

    print("== the production")
    make_media(work)
    chapter(work, "ch1", [("g-title", "title-fa", "pictures", 12, 72), ("g-lt", "lt-fa", "over", 300, 380)], False, False, False, 12)
    # chapter 2's map uses the M2g test's SYNTHETIC places (unverified sources): a draft timeline, as Map Motion requires
    chapter(work, "ch2", [("g-info", "info-fa", "over", 220, 300)], True, True, True, 180, CH2_TEXT, mode="draft")
    (work / "film.json").write_text(json.dumps({"schema": "nfp.film.manifest/1", "title": "سفر به جنوب",
                                                "chapters": [{"id": "c1", "project": "projects/ch1"}, {"id": "c2", "project": "projects/ch2"}]},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    env = dict(FX.CLEAN_ENV, PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-B", str(CLI), "run", "--film", str(work / "film.json"), "--build", str(work / "build")]
    print("     $ " + " ".join(cmd[2:]), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    (work / "run1.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    out = work / "build" / "film"
    rep = json.loads((out / "film_report.json").read_text(encoding="utf-8")) if (out / "film_report.json").exists() else {}
    check(p.returncode in (0, 4) and (out / "film.mp4").exists(), f"ONE command: exit {p.returncode}, {(p.stdout.strip().splitlines() or ['-'])[-1]}")
    if not (out / "film.mp4").exists():
        print(p.stdout[-3000:] + p.stderr[-2000:])
        return finish()

    print("\n== the MP4")
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out / "film.mp4"), "-f", "null", "-"], capture_output=True, text=True)
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(out / "film.mp4")],
                                   capture_output=True, text=True).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    au = next(s for s in pr["streams"] if s["codec_type"] == "audio")
    check(dec.returncode == 0 and not dec.stderr.strip(), "plays: the whole file decodes with no error")
    check((v["width"], v["height"], v["avg_frame_rate"], v["codec_name"], v["pix_fmt"], au["codec_name"]) == (1920, 1080, "30/1", "h264", "yuv420p", "aac")
          and int(v["nb_read_frames"]) == 900 and abs(float(pr["format"]["duration"]) - 30.0) < 0.05,
          f"{v['width']}x{v['height']} {v['avg_frame_rate']} {v['codec_name']} {v['pix_fmt']} + {au['codec_name']} {au.get('sample_rate')} Hz; "
          f"{v['nb_read_frames']} frames, {float(pr['format']['duration']):.3f} s")
    chs = rep.get("film", {}).get("chapters", [])
    check([c["id"] for c in chs] == ["c1", "c2"] and [c["duration"] for c in chs] == [15.0, 15.0] and chs[1]["offset"] == 15.0,
          f"2 chapters: {[(c['id'], c['offset'], c['duration']) for c in chs]}")

    print("\n== every engine in the production")
    b1, b2 = work / "build" / "c1", work / "build" / "c2"
    rd = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))   # noqa: E731
    vm = [rd(b / "voice" / "voice_manifest.json") for b in (b1, b2)]
    check(all(not m["synthetic"] and {r["provider"] for r in m["sentences"]} == {"piper"} for m in vm)
          and {r["voice"] for m in vm for r in m["sentences"]} == {"piper:fa-amir", "piper:fa-gyro"},
          f"Voice: real Piper speech, narrator piper:fa-amir + omid piper:fa-gyro ({sum(len(m['sentences']) for m in vm)} sentences)")
    st1, st2 = rd(b1 / "production.json"), rd(b2 / "production.json")
    check(all(s["steps"]["whisper"]["executor"] == "run.py whisper" and s["steps"]["whisper"]["status"] == "done" for s in (st1, st2)),
          "Whisper: the REAL whisper step (faster-whisper small, offline) in both chapters - no substitute")
    cr = [rd(b / "cast_report.json") for b in (b1, b2)]
    check(all(len(c["instances"]) == 4 for c in cr), f"Character: {cr[0]['summary']} / {cr[1]['summary']}")
    g1, g2 = rd(b1 / "graphics_qc.json"), rd(b2 / "graphics_qc.json")
    check([c["clip"] for c in g1["clips"]] == ["g-title", "g-lt"] and [c["clip"] for c in g2["clips"]] == ["g-info"],
          f"Graphics: {[c['clip'] for c in g1['clips']]} / {[c['clip'] for c in g2['clips']]}")
    mq = rd(b2 / "mapmotion_qc.json")
    check([c["clip"] for c in mq["clips"]] == ["map-a"] and mq["clips"][0]["status"] in ("OK", "WARN"), f"Map Motion + Location: map-a {mq['clips'][0]['status']}")
    am = [rd(b / "audio_mix.json") for b in (b1, b2)]
    check(all([c["clip"] for c in m["clips"]] == ["bed", "hit"] for m in am), f"Timeline audio: music bed + effect mixed in both ({am[0]['mixed']})")
    sj = [rd(b / "subtitles.json") for b in (b1, b2)]
    check(all(s["mode"] == "karaoke" and s["qc"]["status"] in ("OK", "WARN") for s in sj), f"Subtitles: karaoke, QC {[s['qc']['status'] for s in sj]}")

    print("\n== seen on the page at its time, and in the film at the same frame")
    specs = {b1: [(1.0, '[data-p^="gx-"]'), (5.5, "[data-nfp-actor]"), (11.0, '[data-p^="gx-"]'), (8.0, "[data-nfp-actor]")],
             b2: [(2.0, '[data-p="kb-i-a"]'), (9.0, '[data-p^="mmc-"]'), (8.5, '[data-p^="gx-"]'), (14.0, "#tlv-v-a"), (4.5, "[data-nfp-actor]")]}
    for b, sp in specs.items():
        (work / "probe.mjs").write_text(PROBE, encoding="utf-8")
        subprocess.run(["node", str(work / "probe.mjs"), str(b / "render-copy"), str(work / "probe.json"), json.dumps(sp)], check=True, timeout=300)
        r = rd(work / "probe.json")
        check(not r["errors"] and all(x["shown"] >= 1 for x in r["res"]), f"{b.name}: " + ", ".join(f"{x['sel']}@{x['t']}s shown {x['shown']}/{x['n']}" for x in r["res"]))
        off = 0 if b == b1 else 450
        same = [frame_md5(out / "film.mp4", round(t * 30) + off) == frame_md5(b / "story.mp4", round(t * 30)) for t, _ in sp]
        check(all(same), f"{b.name}: the film's frames at those times are the chapter's own frames ({sum(same)}/{len(same)})")

    print("\n== sound, sync, QC")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out / "film.mp4"), "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(work / "film.wav")], check=True)
    import numpy as np
    import wave
    with wave.open(str(work / "film.wav"), "rb") as w:
        y = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
    tf = rd(out / "timing.json")
    last1 = max(x["abs_end"] for s in tf["sentences"] if s["id"].startswith("c1.") for x in s["words"] if x.get("abs_end"))
    tail = y[int((last1 + 0.3) * 48000):int(14.0 * 48000)]
    lvl = 20 * np.log10(np.sqrt(np.mean(tail ** 2)) / 32768)
    check(lvl > -50, f"music in the film's audio after chapter 1's last word ({last1:.2f}-14.0 s): {lvl:.1f} dBFS")
    q = rd(out / "output_qc.json")
    offs = {r["sentence"]: r.get("offset_ms") for r in q["sync"]["sentences"]}
    check(q["sync"]["measured"] >= 4, f"sync (real Whisper times vs the film's audio): {offs} ms (limit 250, warning only)")
    print("INFO film report:\n" + (out / "film_report.md").read_text(encoding="utf-8"), flush=True)
    check(rep.get("verdict") in ("PASS", "PASS_WITH_KNOWN_LIMITATIONS"), f"film verdict {rep.get('verdict')}: {rep.get('reasons')}")
    check(not rep.get("substitutes"), f"no TEST-ONLY executor, no synthetic voice: production_ready = {rep.get('production_ready')}")

    print("\n== again")
    t0 = (out / "film.mp4").stat().st_mtime_ns
    p2 = subprocess.run(cmd, capture_output=True, text=True, env=env)
    s2 = rd(out / "film_state.json")
    check(p2.returncode == p.returncode and s2["assembly"] == "up_to_date" and (out / "film.mp4").stat().st_mtime_ns == t0
          and all(x["ran"] == [] for x in s2["chapters"].values()), "the same command again: nothing re-made (every step and the film up to date)")
    cmd2 = cmd[:-1] + [str(work / "build2")]
    p3 = subprocess.run(cmd2, capture_output=True, text=True, env=env)
    r3 = rd(work / "build2" / "film" / "film_report.json")
    t3 = rd(work / "build2" / "film" / "timing.json")
    same_t = [(s["id"], [w.get("abs_start") for w in s["words"]]) for s in t3["sentences"]] == [(s["id"], [w.get("abs_start") for w in s["words"]]) for s in tf["sentences"]]
    check(p3.returncode == p.returncode and r3["verdict"] == rep["verdict"] and same_t,
          f"a fresh build in another folder: exit {p3.returncode}, verdict {r3['verdict']}, identical word timing: {same_t}")
    git1 = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    check(git0 == git1, "nothing written into the repository (git status unchanged)")
    print(f"film: {out / 'film.mp4'}")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL INTEGRATION TESTS PASSED" if not f else "INTEGRATION TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
