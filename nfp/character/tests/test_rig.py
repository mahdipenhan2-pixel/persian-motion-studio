#!/usr/bin/env python3
"""
C2 tests for the flat_cartoon_v2 rig (offline; no API, no network).

  python3 nfp/character/tests/test_rig.py

1. provenance: the two rig files hash exactly as recorded in PROVENANCE.json and, when git can see the source
   commit, exactly as the source blobs on docu-16x9-test30 @ fa94f06 (reported as SKIPPED - never faked - otherwise)
2. scope: only the two rig files were copied; nothing from the Director, effects, scenes, base.html or Kim projects
3. rig.css holds the six @property registrations and the [data-p] transform rule
4. the Kim-dependent defaults are documented (PROVENANCE.json and README.md)
5. the browser check (rig_render_check.mjs, local Chromium): vocabulary, all combinations, parts, mouth shapes,
   determinism, CSS transforms, no Kim colour leak. Reported as SKIPPED if node/Playwright is unavailable.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parent.parent
R = PKG / "renderers" / "flat_cartoon_v2"
PROV = json.loads((R / "PROVENANCE.json").read_text(encoding="utf-8"))
RESULTS = []


def check(ok, msg, status=None):
    status = status or ("PASS" if ok else "FAIL")
    RESULTS.append((status, msg))
    print(f"{status} {msg}")


def main():
    print("== C2 provenance and scope")
    for f in PROV["files"]:
        p = R / f["path"]
        data = p.read_bytes() if p.is_file() else b""
        got = hashlib.sha256(data).hexdigest()
        check(got == f["sha256"] and len(data) == f["bytes"] and f["modified"] is False,
              f"{f['path']}: SHA-256 {got[:16]}... = PROVENANCE.json, {len(data)} bytes, unmodified")

    commit = PROV["source"]["commit"]
    git = shutil.which("git")
    reachable = git and subprocess.run([git, "-C", str(REPO), "cat-file", "-e", f"{commit}^{{commit}}"],
                                       capture_output=True).returncode == 0
    if reachable:
        for f in PROV["files"]:
            blob = subprocess.run([git, "-C", str(REPO), "cat-file", "blob", f"{commit}:{f['source_path']}"],
                                  capture_output=True, check=True).stdout
            check(hashlib.sha256(blob).hexdigest() == f["sha256"] and blob == (R / f["path"]).read_bytes(),
                  f"{f['path']}: byte-identical to {f['source_path']} @ {commit[:7]} on {PROV['source']['branch']}")
    else:
        check(True, f"source comparison against {commit[:7]}: git object not available here (hashes above still bind the files)", "SKIPPED")

    rig_files = sorted(str(p.relative_to(R / "rig")) for p in (R / "rig").rglob("*") if p.is_file())
    check(rig_files == ["00_core.js", "10_chars.js"], f"only the two rig files were copied ({', '.join(rig_files)})")
    names = {p.name for p in PKG.rglob("*") if p.is_file()}
    forbidden = {"50_director.js", "40_fx.js", "20_backgrounds.js", "21_scenes.js", "41_cine.js", "42_scenes_cine.js",
                 "base.html", "shots.js", "project.json", "photo_slots.json", "sfx.json", "sfx6.json"}
    check(not (names & forbidden), "no Director, effects, scenes, base.html or Kim project file inside nfp/character")
    kim_assets = [p for p in PKG.rglob("*") if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".mp4", ".woff2"}]
    check(not kim_assets, f"no images, audio, video or fonts were moved ({len(kim_assets)} found)")

    print("\n== rig.css")
    import re
    css = re.sub(r"/\*.*?\*/", "", (R / "rig.css").read_text(encoding="utf-8"), flags=re.S)   # rules only, not comments
    props = [f"@property --{p}" for p in ("x", "y", "r", "s", "sx", "sy")]
    check(all(p in css for p in props) and css.count("inherits: false") == 6, "six @property registrations, all inherits:false")
    check("[data-p]" in css and "transform-origin: 0 0" in css and "rotate(calc(var(--r) * 1deg))" in css,
          "[data-p] transform rule (translate, rotate, scale around the part's pivot)")
    check(".lay" not in css and "font" not in css.lower() and "#root" not in css, "rig.css contains no layout, parallax or font rule")

    print("\n== Kim-dependent defaults are documented")
    readme = (R / "README.md").read_text(encoding="utf-8")
    vals = PROV["kim_identity_defaults"]["values"]
    check(len(vals) == 5 and all(v["value"] in readme for v in vals),
          f"all {len(vals)} Kim identity defaults are listed in PROVENANCE.json and README.md ({', '.join(v['value'] for v in vals)})")
    rig_src = (R / "rig" / "10_chars.js").read_text(encoding="utf-8")
    check(all(v["value"] in rig_src for v in vals), "every documented default really exists in the rig source")

    print("\n== browser check (local Chromium, no network)")
    node = shutil.which("node")
    if not node:
        check(True, "node is not installed here: browser check not run", "SKIPPED")
    else:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "rig.json"
            r = subprocess.run([node, str(HERE / "rig_render_check.mjs"), "--out", str(out)], capture_output=True, text=True)
            sys.stdout.write("   " + r.stdout.replace("\n", "\n   ").rstrip() + "\n")
            if "Cannot find module 'playwright'" in r.stderr or "Cannot find package 'playwright'" in r.stderr:
                check(True, "Playwright is not available here: browser check not run", "SKIPPED")
            else:
                rep = json.loads(out.read_text()) if out.is_file() else None
                check(r.returncode == 0 and rep and rep["fails"] == 0,
                      f"browser check: {len(rep['results']) if rep else 0} checks over {rep['renders'] if rep else 0} renders"
                      + ("" if r.returncode == 0 else f" (stderr: {r.stderr[-300:]})"))

    p = sum(1 for s, _ in RESULTS if s == "PASS")
    f = sum(1 for s, _ in RESULTS if s == "FAIL")
    s = sum(1 for s, _ in RESULTS if s == "SKIPPED")
    print(f"\n{len(RESULTS)} checks: {p} passed, {f} failed, {s} skipped. " + ("ALL RIG TESTS PASSED" if not f else "RIG TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
