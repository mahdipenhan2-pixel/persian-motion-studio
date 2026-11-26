"""NFP Production Orchestrator - D3: the production state of one build (<build>/production.json) and the input
fingerprints that decide whether a step is up to date. Standard library; writes only inside the build folder.

  production.json  nfp.orchestrator.production/1:
     {"schema", "project", "chapter", "build", "status", "updated", "preflight": {status, errors, warnings},
      "allow_network": bool, "steps": {name: {"status": done | failed | blocked | skipped, "inputs": sha256,
                                               "executor", "seconds", "log", "reason", "finished"}},
      "runs": [{"started", "finished", "status", "ran": [names], "up_to_date": [names], "stopped_at"}]}
A step is up to date when its last status is "done", the fingerprint of its inputs is unchanged and its outputs exist.
Fingerprints hash file CONTENTS (not times): a re-made upstream output that is byte-identical leaves downstream steps up to
date; a changed one makes them run again.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path

from . import plan as PL

STATE_SCHEMA = "nfp.orchestrator.production/1"
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def path(build):
    return Path(build) / "production.json"


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def load(pl):
    p = path(pl["build"])
    if p.exists():
        st = json.loads(p.read_text(encoding="utf-8"))
        if st.get("schema") == STATE_SCHEMA and st.get("project") == pl["project"] and st.get("chapter") == pl["chapter"]:
            return st
    return {"schema": STATE_SCHEMA, "project": pl["project"], "chapter": pl["chapter"], "build": pl["build"], "status": "new",
            "updated": now(), "steps": {}, "runs": []}


def save(st):
    st["updated"] = now()
    p = path(st["build"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _hash_path(h, p, exclude=()):
    p = Path(p)
    if not p.exists():
        h.update(b"<missing>")
        return
    if p.is_file():
        h.update(p.read_bytes())
        return
    for dp, dns, fns in os.walk(p):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and Path(dp, d).resolve() not in exclude)
        for fn in sorted(fns):
            f = Path(dp, fn)
            if f.suffix == ".pyc":
                continue
            h.update(str(f.relative_to(p)).encode("utf-8") + b"\0")
            h.update(hashlib.sha256(f.read_bytes()).digest())


def fingerprint(step, pl, fonts=None, gsap=None, proj=None):
    """sha256 of everything the step's input specs name (see plan.py)."""
    if proj is None:
        proj, ch = PL.load(pl["project"], pl["chapter"])
    else:
        ch = next(c for c in proj["chapters"] if c["id"] == pl["chapter"])
    pdir, build = Path(pl["project"]), Path(pl["build"])
    exclude = {build.resolve()}                     # a build folder inside the project folder is not an input of itself
    h = hashlib.sha256()
    for spec in step["inputs"]:
        kind, args = spec[0], spec[1:]
        h.update(json.dumps(spec).encode("utf-8"))
        if kind == "project":
            h.update(json.dumps({k: (ch if k == "chapter" else proj.get(k)) for k in args}, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
        elif kind in ("file", "dir"):
            _hash_path(h, pdir / args[0], exclude)
        elif kind == "build":
            _hash_path(h, build / args[0])
        elif kind == "code":
            for a in args:
                _hash_path(h, PL.ROOT / a)
        elif kind == "fonts":
            _hash_path(h, fonts) if fonts else h.update(b"<none>")
        elif kind == "gsap":
            _hash_path(h, gsap) if gsap else h.update(b"<none>")
        else:
            raise ValueError(f"unknown input spec {spec}")
    return h.hexdigest()


def outputs_exist(step, build):
    return all((Path(build) / o).exists() for o in step["outputs"])
