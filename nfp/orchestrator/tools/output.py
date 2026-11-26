"""NFP Production Orchestrator - O2: the "output" step. Runs the Output / Verify check (nfp/output/check.py, unchanged
and still usable on its own) as its OWN process on the build's final MP4; it writes <build>/output_qc.json.

  output(pl, build) -> (ok, detail, log)    ok = the check ran and found no error (OK / WARN)
A check that ran and found errors exits 1 after writing output_qc.json: the runner records that as "problems" (like
verify.py's); a check that did not produce a result (crash, missing tool) is a "failed" step - the report then says the
output QC did not run (INCOMPLETE), never that the film failed.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

CHECK = Path(__file__).resolve().parents[2] / "output" / "check.py"


def output(pl, build, env=None):
    cmd = [sys.executable, "-B", str(CHECK), "--build", str(build), "--project", pl["project"], "--chapter", pl["chapter"]]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env or dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=3600)
    log = "$ " + " ".join(cmd[2:]) + "\n" + p.stdout + p.stderr
    qc = Path(build) / "output_qc.json"
    if p.returncode not in (0, 1) or not qc.exists():
        return False, f"output check did not run (exit {p.returncode}): {(p.stderr or p.stdout).strip()[-200:]}", log
    try:
        r = json.loads(qc.read_text(encoding="utf-8"))
    except ValueError:
        return False, "output_qc.json unreadable", log
    errs = [i for i in r.get("issues", []) if i["level"] == "error"]
    warns = [i for i in r.get("issues", []) if i["level"] == "warning"]
    detail = f"{r.get('status')}: {len(errs)} error(s), {len(warns)} warning(s)" + (f" - {errs[0]['check']}/{errs[0]['code']}: {errs[0]['message']}" if errs
                                                                                   else f" - {warns[0]['check']}/{warns[0]['code']}" if warns else "")
    return p.returncode == 0 and r.get("status") != "FAIL", detail[:300], log
