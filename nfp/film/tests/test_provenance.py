#!/usr/bin/env python3
"""F1 - provenance of nfp/film (offline, standard library only).

  * every 'copied' file is byte-identical to the hash recorded in PROVENANCE.json (and, when the source commit is
    available in the local git object store, to the source file itself);
  * every 'referenced' file (the C2 rig files) still has the recorded hash, i.e. is still the documentary kit file;
  * every 'derived' file exists and lists its changes;
  * no file of nfp/film carries Kim-specific story material (names, brands, palettes); PROVENANCE.json and README.md
    name the source on purpose and are not scanned. Known harmless mentions inside
    byte-identical copies (a comment in 41_cine.js) are listed explicitly, so anything new is caught.
Run: python3 nfp/film/tests/test_provenance.py
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FILM = Path(__file__).resolve().parent.parent
ROOT = FILM.parent.parent
PROV = json.loads((FILM / "PROVENANCE.json").read_text(encoding="utf-8"))
RESULTS = []
KIM = re.compile(r"(?i)kim|kardash|skims|kanye|jenner|calabasas|hollywood|simpson|cochran")
KNOWN = {"kit/41_cine.js": 1}      # 1 comment: "the old kim-test30 never calls it" (file is a byte-identical copy)


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def source_bytes(path):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{PROV['source']['commit']}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def main():
    bad = [c["path"] for c in PROV["copied"] if sha(FILM / c["path"]) != c["sha256"]]
    check(not bad and len(PROV["copied"]) == 9, f"{len(PROV['copied'])} copied files have their recorded sha256 {bad or ''}")
    src = [(c["path"], source_bytes(c["source"])) for c in PROV["copied"]]
    avail = [(p, b) for p, b in src if b is not None]
    if avail:
        diff = [p for p, b in avail if hashlib.sha256(b).hexdigest() != sha(FILM / p)]
        check(not diff, f"copied files are byte-identical to the source commit {PROV['source']['commit'][:7]} "
                        f"({len(avail)} checked) {diff or ''}")
    else:
        print("INFO source commit not in the local object store: compared with the recorded hashes only")
    badr = [r["used_from"] for r in PROV["referenced"] if sha(ROOT / r["used_from"]) != r["sha256"]]
    check(not badr and len(PROV["referenced"]) == 2, f"referenced C2 rig files still equal the documentary kit files {badr or ''}")
    for d in PROV["derived"]:
        check((FILM / d["path"]).exists() and d.get("source") and d.get("changes"),
              f"derived file {d['path']} exists and lists its changes (from {d.get('source')})")
    hits = {}
    for p in sorted(FILM.rglob("*")):
        rel = str(p.relative_to(FILM))
        if p.is_dir() or rel.startswith("tests/") or rel in ("PROVENANCE.json", "README.md") or p.suffix in (".png",):
            continue
        n = len(KIM.findall(p.read_text(encoding="utf-8", errors="replace")))
        if n != KNOWN.get(rel, 0):
            hits[rel] = n
    check(not hits, f"no Kim-specific story material in nfp/film (known harmless comment only) {hits or ''}")
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL PROVENANCE TESTS PASSED" if not f else "PROVENANCE TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
