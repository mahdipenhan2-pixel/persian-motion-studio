#!/usr/bin/env python3
"""Cast windows on a HALF frame: cast_plan.snap must round exactly as the Director's snap (kit/50_director.js,
Math.round(t * 30) / 30: halves go up). Python's round() goes to the even frame, so a shot starting at 9.35 s (frame
280.5) was planned to 280 while the page made it 281, and the cast bridge refused the page.
  A  parity: cast_plan.snap == the browser's Math.round(t * 30) / 30 for every millisecond 0..60 s and edge values
     (halves, just below / above halves, float artefacts) - evaluated in Node, compared exactly;
  B  no other change: on the cast fixtures (en, fa) with Film's synthetic timing, the cast fragment and report are
     byte-identical with the old Python-round snap (their times hold no half frame);
  C  the case that failed: a Persian Voice-Engine project (synthetic voices, offline; Whisper words from the synthetic
     word times - no recognition) whose s3 starts at 9.35 s: run.py voice / prepare / align / compose, then the page in
     Chromium: no page error, the main timeline exists, the 'room' / 'stage' windows meet at frame 281.
  python3 nfp/film/tests/film_cast_halfframe_check.py --gsap <gsap.min.js 3.12.5> --fonts <woff2 dir> --work <dir outside the repository>
"""
import argparse
import json
import math
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
from film_equivalence_check import CDN, synth_timing  # noqa: E402
import film_voice_check as FV  # noqa: E402
import cast_plan as CP  # noqa: E402
import project as P  # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def old_snap(t):
    return round(t * CP.FPS) / CP.FPS


PROBE = r"""
const { createRequire } = await import("node:module"); const fs = await import("node:fs");
const { chromium } = createRequire(import.meta.url)("playwright");
const [dir, out] = process.argv.slice(2); const errors = [];
const br = await chromium.launch(); const pg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
pg.on("pageerror", (e) => errors.push(String(e)));
await pg.route("**/*", (r) => r.request().url().startsWith("file:") ? r.continue() : r.abort());
await pg.goto("file://" + dir + "/index.html");
let tl = true;
try { await pg.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 }); } catch (e) { tl = false; }
fs.writeFileSync(out, JSON.stringify({ errors, timeline: tl, duration: tl ? await pg.evaluate(() => window.__timelines.main.duration()) : null }));
await br.close();
"""


def main():
    ap = argparse.ArgumentParser()
    for k in ("--gsap", "--fonts", "--work"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print("== A: parity with the browser's Math.round")
    ts = [i / 1000 for i in range(60001)]
    ts += [(k + 0.5) / 30 for k in range(0, 1800)] + [9.35, 0.05, 1 / 60, 0.49999999999999994 / 30, 280.5 / 30]
    ts += [math.nextafter(t, 0) for t in (9.35, 0.05, 280.5 / 30)] + [math.nextafter(t, 100) for t in (9.35, 0.05, 280.5 / 30)]
    (work / "ts.json").write_text(json.dumps(ts))
    js = subprocess.run(["node", "-e", "const ts=JSON.parse(require('fs').readFileSync(process.argv[1]));"
                         "process.stdout.write(JSON.stringify(ts.map(t=>Math.round(t*30)/30)))", str(work / "ts.json")],
                        capture_output=True, text=True, check=True)
    ref = json.loads(js.stdout)
    bad = [(t, CP.snap(t), r) for t, r in zip(ts, ref) if CP.snap(t) != r]
    check(not bad, f"cast_plan.snap == Math.round(t * 30) / 30 for {len(ts)} values (every ms of 60 s, halves, neighbours): "
                   f"{len(bad)} differ {bad[:3]}")
    check(CP.snap(9.35) == 281 / 30 and old_snap(9.35) == 280 / 30, f"9.35 s: frame 281 (as the page; the old round gave 280)")
    changed = [t for t in ts if old_snap(t) != CP.snap(t)]
    check(changed and all(abs(t * 30 - math.floor(t * 30) - 0.5) < 1e-9 for t in changed),
          f"only exact half frames change ({len(changed)} of {len(ts)} values; never any other time)")

    print("\n== B: no other change on the cast fixtures")
    for name in ("cast-en", "cast-fa"):
        proj = P.load(HERE / "fixtures" / name)
        ch = proj["chapters"][0]
        timing = synth_timing(ch)
        outs = []
        for fn in (CP.snap, old_snap):
            keep = CP.snap
            CP.snap = fn
            try:
                b = work / f"b-{name}-{fn.__name__}"
                b.mkdir()
                ke, fr, rep = CP.fragment(proj, ch, timing, b)
            finally:
                CP.snap = keep
            outs.append((ke, fr, json.dumps(rep, sort_keys=True)))
        check(outs[0] == outs[1], f"{name}: cast fragment, kit and report byte-identical with the old snap "
                                  f"({json.loads(outs[0][2])['summary']})")

    print("\n== C: the Persian project whose shot starts at 9.35 s")
    d = FV.voice_project(work, "cast-fa", "half-fa", {"narrator": "synthetic:narrator", "lina": "synthetic:female", "omid": "synthetic:male"}, {}, {})
    b = work / "b-half-fa"
    fonts = Path(a.fonts).resolve()
    rc = {}
    for cmd in ("voice", "prepare"):
        rc[cmd] = FV.run_cmd(cmd, d, b, fonts).returncode
    FV.fake_whisper(b)
    for cmd in ("align", "compose"):
        rc[cmd] = FV.run_cmd(cmd, d, b, fonts).returncode
    timing = json.loads((b / "timing.json").read_text(encoding="utf-8")) if (b / "timing.json").exists() else {"sentences": []}
    s3 = next((s for s in timing["sentences"] if s["id"] == "s3"), {})
    check(all(v == 0 for v in rc.values()) and s3.get("offset") == 9.35, f"run.py voice / prepare / align / compose: {rc}; s3 offset {s3.get('offset')} s (= frame 280.5)")
    rep = json.loads((b / "cast_report.json").read_text(encoding="utf-8"))
    win = {i["key"]: i["window"] for i in rep["instances"]}
    check(win.get("omid-room", [0, 0])[1] == 281 / 30 and win.get("omid-stage", [0])[0] == 281 / 30,
          f"cast windows meet at frame 281: room ends {win.get('omid-room')}, stage starts {win.get('omid-stage')}")
    page = (b / "story" / "index.html").read_text(encoding="utf-8")
    rdir = b / "render-copy"
    shutil.copytree(b / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, '<script src="gsap.min.js"></script>'), encoding="utf-8")
    shutil.copyfile(a.gsap, rdir / "gsap.min.js")
    (work / "probe.mjs").write_text(PROBE, encoding="utf-8")
    subprocess.run(["node", str(work / "probe.mjs"), str(rdir), str(work / "probe.json")], check=True, timeout=300)
    pr = json.loads((work / "probe.json").read_text(encoding="utf-8"))
    check(not pr["errors"] and pr["timeline"] and abs(pr["duration"] - 20.0) < 0.05,
          f"the page in Chromium: {len(pr['errors'])} page error(s) {pr['errors'][:1]}, timeline {pr['duration']} s")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL CAST HALF-FRAME TESTS PASSED" if not f else "CAST HALF-FRAME TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
