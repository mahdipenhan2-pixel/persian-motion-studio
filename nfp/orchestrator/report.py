"""NFP Production Orchestrator - D5: one QC report of one build, made only from what the engines and the runner wrote
(nothing is re-checked or re-judged here except the classification of verify.py's problems).

  report(pl, fonts=None, gsap=None, write=True) -> nfp.orchestrator.report/1, written to <build>/production_report.json
                                                   and <build>/production_report.md
  summary(rep) -> the readable text

Sources (each optional; a missing one is said, never invented):
  production.json (runner: steps, executors)   preflight.json (or a fresh preflight)   voice/voice_manifest.json (Voice QC)
  subtitles.json (Subtitle QC)   cast_report.json (Character)   mapmotion_qc.json / graphics_qc.json (Timeline clips)
  smoke.json   render.json (ffprobe)   verify.json (Film's verify.py)   output_qc.json (nfp/output/check.py)
verify.py's problems are split into
  known_limitations  problems this project has documented and accepted (KNOWN below, with where) - still listed, and
                     each says what a person should look at; they do not fail the report
  not_applicable     caption-highlight problems the Output check found not to apply to the project's subtitle mode
                     (sentence / word / off), and only when (a) output_qc.json is CURRENT - made from this MP4,
                     verify.json, timing.json and these project settings (output.check.is_current: sha256 + settings
                     fingerprint) - and (b) the check that replaces them for that mode passed
  pending_output_qc  the same caption-highlight problems while no CURRENT output QC exists for a project whose subtitle
                     mode (Subtitle Engine settings) draws no highlight: listed, they make the report INCOMPLETE (not
                     FAIL, not PASS) until a current output QC confirms or rejects them; karaoke / no subtitles block: new
  new_problems       everything else - they fail it
Output QC (output_qc.json), used only when current: an error -> FAIL (a defect of the delivered file); warnings (sync
offsets included: not yet validated on real speech) are listed and do not change the verdict; no current result
(the step failed, did not run, or its inputs changed since) -> INCOMPLETE, never FAIL - a missing check says nothing
about the film, and the render step keeps its own status.
Verdict: PASS | PASS_WITH_KNOWN_LIMITATIONS | FAIL | BLOCKED | INCOMPLETE. "production_ready" is false whenever a
TEST-ONLY executor or synthetic voices (test tones) made part of the build - such a build proves the pipeline, not a film.
"""
import json
import re
import sys
from pathlib import Path

from . import plan as PL
from . import preflight as PF

REPORT_SCHEMA = "nfp.orchestrator.report/1"
KNOWN = [
    {"id": "verify.near_static", "pattern": r"^long near-static stretches",
     "source": "Film verify.py motion check; accepted for map holds / quiet shots in M2g (nfp/mapmotion README, M2g limits)",
     "look_at": "watch the listed stretches: a quiet shot is fine, a frozen picture is not"},
    {"id": "verify.highlight_first_word", "pattern": r"caption highlight too large for the first word",
     "source": "Film verify.py highlight check; documented in nfp/timeline/README.md (T4)",
     "look_at": "check the first caption word of the sentence named: the highlight box should fit that word"},
]


def _read(p):
    p = Path(p)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {"_unreadable": str(p)}


def classify(problems):
    known, new = [], []
    for pr in problems:
        k = next((k for k in KNOWN if re.search(k["pattern"], pr)), None)
        (known if k else new).append({"problem": pr, **({"id": k["id"], "source": k["source"], "look_at": k["look_at"]} if k else {})})
    return known, new


def output_qc(pl, b):
    """(output_qc document, None) when <build>/output_qc.json is current for this build and project; else (None, why)."""
    q = _read(b / "output_qc.json")
    if q is None:
        return None, "no output_qc.json (the output step has not run)"
    if str(PL.NFP) not in sys.path:
        sys.path.insert(0, str(PL.NFP))
    try:
        from output import check as OC
        ok, diff = OC.is_current(q, b, pl["project"], pl["chapter"])
    except Exception as e:                       # the report never crashes on it; it says so
        return None, f"output_qc.json could not be validated ({type(e).__name__}: {e})"[:300]
    return (q, None) if ok else (None, "output_qc.json is stale: " + "; ".join(diff))


def _subtitle_mode(pl):
    """The subtitle mode as the Subtitle Engine resolves it for this project (output.check.subtitle_mode), or None."""
    try:
        from output import check as OC
        return OC.subtitle_mode(pl["project"], pl["chapter"])[0]
    except Exception:
        return None


def report(pl, fonts=None, gsap=None, write=True):
    b = Path(pl["build"])
    reasons, notes, substitutes = [], [], []
    st = _read(b / "production.json")
    pre = _read(b / "preflight.json") or PF.preflight(pl, fonts=fonts, gsap=gsap)
    rep = {"schema": REPORT_SCHEMA, "project": pl["project"], "chapter": pl["chapter"], "build": str(b)}

    rep["preflight"] = {"status": pre["status"], "errors": [i for i in pre["issues"] if i["level"] == "error"],
                        "warnings": [i for i in pre["issues"] if i["level"] == "warning"],
                        "environment_gaps": {k: v for k, v in pre["environment"].items() if not v["ok"]}, "cost": pre["cost"]}
    if pre["status"] == "FAIL":
        reasons.append(f"preflight: {len(rep['preflight']['errors'])} error(s)")

    steps = []
    for s in pl["steps"]:
        r = (st or {}).get("steps", {}).get(s["name"], {})
        steps.append({"step": s["name"], "engine": s["engine"], "status": r.get("status", "not run"), "executor": r.get("executor"),
                      "detail": r.get("detail") or r.get("reason"), "seconds": r.get("seconds")})
        if (r.get("executor") or "").startswith("TEST-ONLY"):
            substitutes.append(f"{s['name']}: {r['executor']}")
    rep["production"] = {"state": "production.json" if st else "none (not run by the orchestrator)", "status": (st or {}).get("status"),
                         "steps": steps}
    failed = [x["step"] for x in steps if x["status"] == "failed" and x["step"] != "output"]   # output: see below (INCOMPLETE)
    blocked = [x for x in steps if x["status"] == "blocked"]
    if failed:
        reasons.append(f"failed step(s): {', '.join(failed)}")

    eng = {}
    m = _read(b / "voice" / "voice_manifest.json")
    if m:
        q = (m.get("qc") or {}).get("summary", {})
        eng["voice"] = {"qc": q, "synthetic": bool(m.get("synthetic")), "findings": m.get("findings", [])}
        if q.get("error"):
            reasons.append(f"voice QC: {q['error']} error(s)")
        if m.get("synthetic"):
            substitutes.append("voice: synthetic voices (test tones, not speech)")
    t = _read(b / "tts_meta.json")
    if t and not m:
        eng["tts"] = {"model": t.get("model"), "voice": t.get("voice"), "sentences": len(t.get("sentences", []))}
    s = _read(b / "subtitles.json")
    if s:
        q = s.get("qc") or {}
        eng["subtitles"] = {k: q.get(k) for k in ("status", "cues", "errors", "warnings")} | {"issues": q.get("issues", [])[:20]}
        if q.get("errors"):
            reasons.append(f"subtitles QC: {q['errors']} error(s)")
    c = _read(b / "cast_report.json")
    if c:
        eng["character"] = {"summary": c.get("summary"), "instances": len(c.get("instances", [])),
                            "unresolved_words": sum(len(tk.get("unresolved_words", [])) for i in c.get("instances", []) for tk in i.get("talks", []))}
    mq = _read(b / "mapmotion_qc.json")
    if mq:
        clips = mq.get("clips", [])
        eng["mapmotion"] = {"clips": [{"clip": x["clip"], "status": x.get("status"), "issues": len(x.get("issues", []))} for x in clips]}
        bad = [x["clip"] for x in clips if str(x.get("status")).upper() in ("FAIL", "ERROR")]
        if bad:
            reasons.append(f"map QC failed: {', '.join(bad)}")
    gq = _read(b / "graphics_qc.json")
    if gq:
        eng["graphics"] = {"clips": [{"clip": x["clip"], "kind": x.get("kind"), "mode": x.get("mode"), "issues": x.get("issues", [])} for x in gq.get("clips", [])]}
    rep["engines"] = eng

    sm = _read(b / "smoke.json")
    rep["smoke"] = sm and {k: sm.get(k) for k in ("ok", "problems", "timeline_seconds", "expected_seconds", "director_warnings", "refused_requests")}
    if sm and not sm.get("ok"):
        reasons.append("smoke: " + "; ".join(sm.get("problems", []))[:300])
    rj = _read(b / "render.json")
    rep["render"] = rj and {"mp4": rj.get("mp4"), "hyperframes": rj.get("hyperframes"), "offline": rj.get("offline"), "ffprobe": rj.get("ffprobe"),
                            "lint_exit": rj.get("lint_exit")}
    incomplete = []
    oq, why = output_qc(pl, b)
    ostep = next((x for x in steps if x["step"] == "output"), None)
    if oq:
        errs = [i for i in oq["issues"] if i["level"] == "error"]
        warns = [i for i in oq["issues"] if i["level"] == "warning"]
        t, sy, sb = oq.get("technical") or {}, oq.get("sync") or {}, oq.get("subtitles") or {}
        rep["output"] = {"status": oq["status"], "current": True, "errors": errs, "warnings": warns,
                         "technical": {k: t.get(k) for k in ("video", "audio", "faststart", "bitrate_kbps", "megabytes_per_minute",
                                                             "stream_start_difference_s", "stream_end_difference_s")},
                         "loudness": oq.get("loudness"),
                         "sync": {"measured": sy.get("measured"), "not_measurable": sy.get("not_measurable"), "limit_ms": sy.get("limit_ms"),
                                  "offsets_ms": {r["sentence"]: r.get("offset_ms") for r in sy.get("sentences", [])}},
                         "subtitles": {"mode": sb.get("mode"), "mode_source": sb.get("mode_source"),
                                       "replacement": (sb.get("replacement") or {}).get("check")}}
        if errs:
            reasons.append(f"output QC: {len(errs)} error(s): {errs[0]['check']}/{errs[0]['code']}: {errs[0]['message']}"[:300])
        if ostep and ostep["status"] == "failed":
            notes.append(f"the last output step failed ({ostep['detail']}); the output QC shown is an earlier one, still current for these files")
    else:
        rep["output"] = {"status": None, "current": False, "why": why, "step": ostep and ostep["status"]}
        incomplete.append(f"output QC: {why}" + (f" (output step: {ostep['status']}: {ostep['detail']})" if ostep and ostep["status"] == "failed" else ""))
    vj = _read(b / "verify.json")
    if vj:
        probs = list(vj.get("problems", []))
        na = []
        sb = (oq or {}).get("subtitles") or {}
        rows = (sb.get("replacement") or {}).get("sentences")
        rows_ok = bool(rows) and not any(r.get("problem") for r in rows)
        if oq and sb.get("not_applicable"):         # mode rule: only when the mode's own check passed; estimated_first_word: a fact
            for x in sb["not_applicable"]:
                if x["problem"] in probs and (x.get("rule") == "estimated_first_word" or rows_ok):
                    probs.remove(x["problem"])
                    na.append(x)
        pending = []
        if oq is None and any("caption highlight" in p for p in probs):
            mode = _subtitle_mode(pl)
            if mode in ("sentence", "word", "off"):       # the project says the highlight is not drawn; only a current output QC can confirm
                pending = [p for p in probs if "caption highlight" in p]
                probs = [p for p in probs if p not in pending]
                incomplete.append(f"verify: {len(pending)} caption-highlight problem(s) wait for a current output QC (subtitles.mode '{mode}')")
            else:
                notes.append("verify.py's caption-highlight problems are kept as new: the project's captions draw the highlight")
        known, new = classify(probs)
        rep["verify"] = {"file_checked": vj.get("file_checked"), "duration": vj.get("duration"), "video": vj.get("video"),
                         "audio_onset_vs_first_word_ms": vj.get("mp4_audio_onset_vs_first_word_ms"), "known_limitations": known,
                         "not_applicable": na, "pending_output_qc": pending, "new_problems": new, "notes": vj.get("notes", [])}
        if new:
            reasons.append(f"verify: {len(new)} new problem(s)")
    else:
        rep["verify"] = None
    if vj and rj and st and (st.get("steps", {}).get("render", {}).get("finished") or "") > (st.get("steps", {}).get("verify", {}).get("finished") or "~"):
        notes.append("verify.json is older than the last render: run the verify step again")

    if reasons:
        verdict = "FAIL"
    elif blocked:
        verdict = "BLOCKED"
        reasons.append("; ".join(f"{x['step']}: {x['detail']}" for x in blocked))
    elif vj is None or any(x["status"] == "not run" for x in steps) or incomplete:
        verdict = "INCOMPLETE"
        if vj is None or any(x["status"] == "not run" for x in steps):
            reasons.append("not every step has run" + ("" if vj else " (no verify.json)"))
        reasons += incomplete
    else:
        verdict = "PASS_WITH_KNOWN_LIMITATIONS" if rep["verify"]["known_limitations"] else "PASS"
    rep.update(verdict=verdict, reasons=reasons, notes=notes, substitutes=substitutes,
               production_ready=verdict in ("PASS", "PASS_WITH_KNOWN_LIMITATIONS") and not substitutes)
    if write:
        b.mkdir(parents=True, exist_ok=True)
        (b / "production_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        (b / "production_report.md").write_text(summary(rep) + "\n", encoding="utf-8")
    return rep


def summary(rep):
    L = [f"# Production report - {Path(rep['project']).name} / {rep['chapter']}", "",
         f"verdict: {rep['verdict']}   production_ready: {'yes' if rep['production_ready'] else 'NO'}"]
    for r in rep["reasons"]:
        L.append(f"  reason: {r}")
    for s in rep["substitutes"]:
        L.append(f"  NOT A PRODUCTION BUILD - {s}")
    for n in rep["notes"]:
        L.append(f"  note: {n}")
    p = rep["preflight"]
    L += ["", f"## preflight: {p['status']} ({len(p['errors'])} error(s), {len(p['warnings'])} warning(s))"]
    L += [f"  - {i['engine']}/{i['code']}: {i['message']}" for i in p["errors"] + p["warnings"]]
    L += [f"  - environment: {k} missing ({v['detail']}) - needed by {', '.join(v['needed_by'])}" for k, v in p["environment_gaps"].items()]
    if p["cost"]["network"]:
        L += [f"  - online / paid: {k}: {v}" for k, v in p["cost"]["network"].items()]
    L += ["", f"## steps ({rep['production']['state']}; status {rep['production']['status']})"]
    L += [f"  {x['step']:8s} {x['status']:9s} {x['executor'] or '':22s} {(x['detail'] or '')[:110]}" for x in rep["production"]["steps"]]
    L += ["", "## engines"]
    for k, v in rep["engines"].items():
        L.append(f"  {k}: {json.dumps(v, ensure_ascii=False)[:240]}")
    if rep["smoke"]:
        L += ["", f"## smoke: {'ok' if rep['smoke']['ok'] else 'FAILED'} - timeline {rep['smoke']['timeline_seconds']} s, "
                  f"{len(rep['smoke']['director_warnings'] or [])} Director warning(s), {len(rep['smoke']['refused_requests'] or [])} outside request(s) refused"]
    if rep["render"]:
        f = rep["render"]["ffprobe"] or {}
        L += ["", f"## render: {rep['render']['mp4']}", f"  {f.get('width')}x{f.get('height')} {f.get('fps')} {f.get('video_codec')} + {f.get('audio_codec')}, "
                                                        f"{f.get('seconds')} s, HyperFrames {rep['render']['hyperframes']} offline"]
    v = rep["verify"]
    if v:
        L += ["", f"## verify.py: {len(v['new_problems'])} new problem(s), {len(v['known_limitations'])} known limitation(s), "
                  f"{len(v.get('not_applicable', []))} not applicable"]
        L += [f"  NEW: {x['problem']}" for x in v["new_problems"]]
        L += [f"  not applicable: {x['problem']}\n      reason: {x['reason']}" for x in v.get("not_applicable", [])]
        L += [f"  waiting for a current output QC: {x}" for x in v.get("pending_output_qc", [])]
        L += [f"  known ({x['id']}): {x['problem']}\n      source: {x['source']}\n      look at: {x['look_at']}" for x in v["known_limitations"]]
    o = rep.get("output") or {}
    if o.get("current"):
        t = o["technical"]
        vv, aa, lo, sy = t.get("video") or {}, t.get("audio") or {}, o.get("loudness") or {}, o["sync"]
        L += ["", f"## output QC: {o['status']} ({len(o['errors'])} error(s), {len(o['warnings'])} warning(s))",
              f"  video {vv.get('codec')} {vv.get('profile')} {vv.get('pix_fmt')}; audio {aa.get('codec')} {aa.get('rate')} Hz x{aa.get('channels')}; "
              f"faststart {t.get('faststart')}; {t.get('bitrate_kbps')} kb/s ({t.get('megabytes_per_minute')} MB/min)",
              f"  loudness {lo.get('integrated_lufs')} LUFS, true peak {lo.get('true_peak_dbtp')} dBTP",
              f"  sync: {sy['measured']} sentence(s) measured, {sy['not_measurable']} not measurable; offsets {sy['offsets_ms']} ms (limit {sy['limit_ms']}, warning only)",
              f"  subtitles: mode {o['subtitles']['mode']} ({o['subtitles']['mode_source']})"
              + (f"; replaced check: {o['subtitles']['replacement']}" if o["subtitles"]["replacement"] else "")]
        L += [f"  ERROR {i['check']}/{i['code']}: {i['message']}" for i in o["errors"]]
        L += [f"  warning {i['check']}/{i['code']}: {i['message']}" for i in o["warnings"]]
    elif o:
        L += ["", f"## output QC: none current - {o['why']}"]
    return "\n".join(L)
