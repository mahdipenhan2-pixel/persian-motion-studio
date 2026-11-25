#!/usr/bin/env python3
"""M2e - a REAL render: the SVGs drawn by the local Chromium (Playwright, already installed; nothing is downloaded) and
pixel colours read back from a canvas at places computed independently from the plan's projection - land on both sides
of the seam and over the pole, sea, the drawn route, the undrawn part of a route, a zoomed frame, the markers.
Needs node and its playwright module (the environment's own); without them the test says so and fails.
SYNTHETIC data; every file goes to a temporary folder outside the project.

  python3 nfp/mapmotion/tests/test_mapmotion_m2e_render.py
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path[:0] = [str(NFP), str(NFP / "location" / "tests"), str(HERE)]
import mapmotion as M                          # noqa: E402
from mapmotion import camera as CAM            # noqa: E402
from mapmotion import render as R              # noqa: E402
import m2e_fixture as FX                       # noqa: E402

RESULTS = []
JS = r"""
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage();
  const out = [];
  for (const j of jobs) {
    out.push(await p.evaluate(async ([svg, pts]) => {
      const img = new Image();
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
      await img.decode();
      const c = document.createElement('canvas'); c.width = 1920; c.height = 1080;
      const g = c.getContext('2d'); g.drawImage(img, 0, 0);
      return pts.map(([x, y]) => Array.from(g.getImageData(Math.round(x), Math.round(y), 1, 1).data).slice(0, 3));
    }, [j.svg, j.points]));
  }
  await b.close();
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def near(a, b, tol=6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def main():
    node = shutil.which("node")
    if not node:
        check(False, "node is not installed: the real render cannot run")
        return finish()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        plan, geo, sp = FX.build(td)
        proj = M.projection_from_plan(plan)
        bm = R.basemap_paths(sp, plan)
        c = sp["style"]["colors"]
        P = lambda lat, lon: proj.project(lat, lon)
        route = sp["routes"][0]
        pc = route["pieces"][0]
        mids = [((v["x"] + w["x"]) / 2, (v["y"] + w["y"]) / 2) for v, w in zip(pc, pc[1:])]
        jobs, names = [], []

        def job(name, frame, pts):
            jobs.append({"svg": R.render_svg(sp, plan, frame, bm), "points": [list(p) for p in pts]})
            names.append(name)

        static_pts = [(5, 5), P(35, 50), P(-20, 172), P(-20, -170), P(-78, 15), P(40, -145), mids[len(mids) // 2],   # off the 30-degree grid lines
                      P(-20.5, 160.5)]                                             # point w (a dot)
        job("static", None, static_pts)
        an = sp["animation"]["frames"][45]["routes"][0]
        st45 = sp["camera"]["frames"][45]
        drawn_mid = [m for m in mids[:2]]
        ahead = mids[-1]
        job("f45", 45, [CAM.to_screen(st45, sp["frame"], *drawn_mid[0]), CAM.to_screen(st45, sp["frame"], *ahead)])
        st90 = sp["camera"]["frames"][90]
        job("f90", 90, [CAM.to_screen(st90, sp["frame"], *mids[len(mids) // 2]), CAM.to_screen(st90, sp["frame"], *P(35, 50))])
        h199 = sp["animation"]["frames"][199]["routes"][1]["head"]                   # at 150 the tip is off screen (camera zoomed east)
        st199 = sp["camera"]["frames"][199]
        job("f199", 199, [CAM.to_screen(st199, sp["frame"], h199["x"], h199["y"])])
        (td / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        (td / "probe.js").write_text(JS, encoding="utf-8")
        r = subprocess.run([node, str(td / "probe.js"), str(td / "jobs.json"), str(td / "out.json")], capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            check(False, f"Chromium render failed: {(r.stderr or r.stdout)[-300:]}")
            return finish()
        out = dict(zip(names, json.loads((td / "out.json").read_text(encoding="utf-8"))))
        s = out["static"]
        check(near(s[0], rgb(c["background"])), f"static: the background colour outside the map {s[0]}")
        check(near(s[1], rgb(c["land"])), f"static: land inside the eastern continent {s[1]}")
        check(near(s[2], rgb(c["land"])) and near(s[3], rgb(c["land"])), f"static: the island over the antimeridian is land on BOTH edges {s[2]} {s[3]}")
        check(near(s[4], rgb(c["land"])), f"static: the polar land, closed along the pole line {s[4]}")
        check(near(s[5], rgb(c["background"])), f"static: open sea is not land {s[5]}")
        check(near(s[6], rgb(route["color"])), f"static: the route's colour on the route {s[6]}")
        check(near(s[7], rgb(sp["points"][3]["color"])), f"static: the dot marker of point w at its place {s[7]}")
        f45 = out["f45"]
        check(near(f45[0], rgb(route["color"])) and near(f45[1], rgb(c["land"])),
              f"frame 45 (zoomed, partly drawn): the route is drawn behind the tip {f45[0]}, not yet ahead of it {f45[1]}")
        f90 = out["f90"]
        check(near(f90[0], rgb(route["color"])) and near(f90[1], rgb(c["land"])), f"frame 90: route and land where the camera puts them {f90}")
        f199 = out["f199"]
        check(near(f199[0], rgb(sp["routes"][1]["color"]), tol=40), f"frame 199: the ship marker at the tip of the route over the seam {f199[0]}")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL MAP MOTION M2e RENDER TESTS PASSED" if not f else "MAP MOTION M2e RENDER TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
