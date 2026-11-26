"""NFP Production Orchestrator - D3: runs the plan's steps in order, each as its existing command in its OWN process
(run.py <command>) or as an orchestrator tool (smoke, render), and keeps <build>/production.json.

  run(pl, fonts=None, gsap=None, allow_network=False, until=None, start=None, force=False, executors=None, browser=None)
      -> the production state (see state.py)

Order: preflight first (written to <build>/preflight.json); a FAIL stops before any step. Then, per step:
  up to date   (last "done", same input fingerprint, outputs present)       -> left alone (Resume)
  cost guard   a step preflight lists under cost.network (Gemini TTS requests, a HyperFrames not cached ...) is BLOCKED
               unless allow_network=True; the run stops there and says why. Without allow_network every step's process
               also runs without GEMINI_API_KEY / GEMINI_FREE_TIER_CONFIRMED, with HF_HUB_OFFLINE=1 (faster-whisper cannot
               fetch a model) and npm_config_offline=true, so nothing goes online even by accident. The whisper step is
               therefore not blocked for its possible model download: it runs offline (a model not cached here = failed).
  environment  a step whose dependency is missing here (preflight.environment: faster_whisper, gsap, fonts ...) is
               BLOCKED with that reason - unless an executor for it was injected
  run          its log goes to <build>/orchestrator/logs/<step>.log; a non-zero exit or a missing output = failed, the
               run stops (later steps are not tried); the next run resumes at the first step that is not up to date
  verify       verify.py exits 1 when it lists problems: the step is then "problems" (not "failed": it ran to the end and
               wrote verify.json) and the run "complete_with_problems"; the QC report (report.py) separates known
               limitations from new problems - the runner does not judge them
  output       the same for the Output / Verify check (tools/output.py -> output_qc.json); a check that produced no result
               is "failed" for that step only (render keeps its "done"); the report then says INCOMPLETE, not FAIL
  start=name   that step and all later ones run again;  until=name  stop after it;  force  every step runs again
After every run (complete, failed or blocked) <build>/production_report.json / .md is written (report.py).
executors: {step name: fn(step, ctx) -> (ok, detail, log)} replaces how a step is executed (the tests' TEST-ONLY whisper
substitute); the state records the executor's name so a report can never present a substitute as the real step.
The orchestrator never edits an engine's file: it only reads their outputs to decide up-to-date-ness.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import plan as PL
from . import preflight as PF
from . import state as S

RUN = PL.ENGINE / "run.py"
SECRET_ENV = ("GEMINI_API_KEY", "GEMINI_FREE_TIER_CONFIRMED")
OFFLINE_ENFORCED = {"whisper"}     # runs without network instead of being blocked: HF_HUB_OFFLINE=1 (a model not yet cached = fails)


def step_env(fonts, allow_network):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    if fonts:
        env["NFP_FONTS"] = str(fonts)
    if not allow_network:
        for k in SECRET_ENV:
            env.pop(k, None)
        env.update(HF_HUB_OFFLINE="1", npm_config_offline="true")
    return env


def run_py(step, ctx):
    cmd = [sys.executable, "-B", str(RUN), step["run"][1], "--project", ctx["pl"]["project"], "--chapter", ctx["pl"]["chapter"],
           "--build", ctx["pl"]["build"]]
    p = subprocess.run(cmd, capture_output=True, text=True, env=ctx["env"])
    out = (p.stdout + p.stderr).strip()
    last = out.splitlines()[-1] if out else ""
    return p.returncode == 0, (f"exit {p.returncode}: {last}" if p.returncode else last)[:300], "$ " + " ".join(cmd[2:]) + "\n" + p.stdout + p.stderr


CHECK_STEPS = {"verify": "verify.json", "output": "output_qc.json"}   # exit 1 after writing this file = "problems", not "failed"


def tool(step, ctx):
    if step["run"][1] == "output":
        from .tools import output as O
        return O.output(ctx["pl"], ctx["pl"]["build"], ctx["env"])
    from .tools import render as R
    fn = {"smoke": R.smoke, "render": R.render}[step["run"][1]]
    return fn(ctx["pl"], ctx["pl"]["build"], ctx["gsap"], ctx.get("browser"))


def run(pl, fonts=None, gsap=None, allow_network=False, until=None, start=None, force=False, executors=None, browser=None, say=print):
    names = [s["name"] for s in pl["steps"]]
    for n in (until, start):
        if n is not None and n not in names:
            raise ValueError(f"unknown step {n!r}: {', '.join(names)}")
    executors = executors or {}
    build = Path(pl["build"])
    build.mkdir(parents=True, exist_ok=True)
    st = S.load(pl)
    run_rec = {"started": S.now(), "allow_network": allow_network, "ran": [], "up_to_date": [], "stopped_at": None}
    st["runs"].append(run_rec)
    st["allow_network"] = allow_network

    def end(status, stopped_at):
        _end(st, run_rec, status, stopped_at)
        from . import report as RP                 # D5: the build's one QC report, after every run (whatever its end)
        rep = RP.report(pl, fonts=fonts, gsap=gsap)
        say(f"report: {rep['verdict']} (production_ready: {rep['production_ready']}) -> {build / 'production_report.md'}")
        return st

    pre = PF.preflight(pl, fonts=fonts, gsap=gsap)
    (build / "preflight.json").write_text(json.dumps(pre, ensure_ascii=False, indent=1), encoding="utf-8")
    st["preflight"] = {"status": pre["status"], "errors": sum(i["level"] == "error" for i in pre["issues"]),
                       "warnings": sum(i["level"] == "warning" for i in pre["issues"]), "cost": pre["cost"]}
    if pre["status"] == "FAIL":
        bad = [f"{i['engine']}/{i['code']}: {i['message']}" for i in pre["issues"] if i["level"] == "error"]
        say(f"preflight FAIL ({len(bad)} error(s)) - nothing was run:\n  " + "\n  ".join(bad[:10]))
        return end("preflight_failed", None)

    proj, _ = PL.load(pl["project"], pl["chapter"])
    env = step_env(fonts, allow_network)
    logs = build / "orchestrator" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    ctx = {"pl": pl, "env": env, "fonts": fonts, "gsap": gsap, "browser": browser}
    rerun_from = names.index(start) if start else None
    for i, step in enumerate(pl["steps"]):
        name = step["name"]
        fp = S.fingerprint(step, pl, fonts, gsap, proj)
        prev = st["steps"].get(name, {})
        again = force or (rerun_from is not None and i >= rerun_from)
        if not again and prev.get("status") in ("done", "problems") and prev.get("inputs") == fp and S.outputs_exist(step, build):
            run_rec["up_to_date"].append(name)
            say(f"  {name:8s} up to date")
        else:
            why = _blocked(step, pre, allow_network, name in executors)
            if why:
                st["steps"][name] = dict(prev, status="blocked", reason=why, finished=S.now())
                say(f"  {name:8s} BLOCKED: {why}")
                return end("blocked", name)
            fn = executors.get(name) or (run_py if step["run"][0] == "run.py" else tool)
            label = getattr(fn, "label", None) or (" ".join(step["run"]) if fn in (run_py, tool) else fn.__name__)
            t0 = time.time()
            try:
                ok, detail, log = fn(step, ctx)
            except Exception as e:                       # an executor's crash is the step's failure, never the run's
                ok, detail, log = False, f"{type(e).__name__}: {e}"[:300], repr(e)
            missing = [o for o in step["outputs"] if not (build / o).exists()]
            if ok and missing:
                ok, detail = False, f"finished but did not write {', '.join(missing)}"
            status = "done" if ok else "failed"
            vj = build / CHECK_STEPS.get(name, "-")
            if not ok and name in CHECK_STEPS and not missing and vj.exists() and vj.stat().st_mtime >= t0:
                status = "problems"              # the check ran to the end and listed problems (exit 1): the QC report classifies them
            (logs / f"{name}.log").write_text(log or "", encoding="utf-8")
            st["steps"][name] = {"status": status, "inputs": fp if status != "failed" else None, "executor": label,
                                 "seconds": round(time.time() - t0, 2), "log": str(logs / f"{name}.log"), "detail": detail,
                                 "finished": S.now()}
            run_rec["ran"].append(name)
            say(f"  {name:8s} {status.upper() if status != 'done' else status} ({label}, {st['steps'][name]['seconds']} s): {detail}")
            if status == "failed":
                return end("failed", name)
        if name == until:
            return end("partial" if i < len(names) - 1 else _final(st), None)
    return end(_final(st), None)


def _blocked(step, pre, allow_network, injected):
    name = step["name"]
    if not allow_network and name in pre["cost"]["network"] and name not in OFFLINE_ENFORCED:
        return f"cost guard: {pre['cost']['network'][name]} - not run without --allow-network"
    if injected:
        return None
    gaps = [f"{k}: {v['detail']}" for k, v in pre["environment"].items() if not v["ok"] and name in v["needed_by"]]
    return "missing here - " + "; ".join(gaps) if gaps else None


def _final(st):
    return "complete_with_problems" if any(r.get("status") == "problems" for r in st["steps"].values()) else "complete"


def _end(st, run_rec, status, stopped_at):
    run_rec.update(finished=S.now(), status=status, stopped_at=stopped_at)
    st["status"] = status
    S.save(st)
    return st
