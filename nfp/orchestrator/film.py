"""NFP Production Orchestrator - a FILM of several chapters (Film manifest). Each chapter is one standard Film project
(nfp/film: <= 40 sentences / 180 s - the locked Stage 2 core's limit per run), produced by the usual runner from audio to
its own verified MP4; the film is then assembled from those chapter MP4s with Film's own assemble.py, and the WHOLE film
is checked again with Film's verify.py and the Output / Verify check. Nothing about a chapter project changes: a film is
just a list of them, so a film of any length is a list of chapters.

  film.json  nfp.film.manifest/1:
     {"schema": "nfp.film.manifest/1", "title": "...",
      "chapters": [{"id": "c1", "project": "chapter-1"}, {"id": "c2", "project": "chapter-2", "chapter": "c1"}, ...]}
     project: a Film project folder relative to film.json; chapter: which chapter of that project (default its first).
     Chapters may share files with relative paths (a cast folder, a voice cache); every chapter must have the same
     language and the same subtitle settings (the film is one subtitle style), and every chapter id is unique.

  run_film(manifest, build=None, fonts, gsap, allow_network, force, executors, say) -> the film state
     <build>/<chapter id>/      each chapter's normal build (production.json, story.mp4, production_report.json ...)
     <build>/film/film.mp4      the assembled film:
        video  the chapter MP4s' video streams joined as they are (ffmpeg concat, stream copy, the chapters' own track
               timescale; refused unless every chapter's video stream has the same codec / size / fps / pixel format)
        audio  each chapter's audio decoded and cut to its chapter's exact length (whole frames), joined with
               assemble.plan / assemble.concat_wavs (every chapter's audio slot = its video frames exactly: no drift at a
               join), encoded once (AAC 192k)
        timing.json  every chapter's timing moved by its offset (assemble.shift_timing), ids "<chapter>.<sentence>";
        film.srt     assemble.merged_srt;  verify.json + contact_sheet.png (Film's verify.py on film.mp4, target = the
        sum of the chapters);  output_qc.json (nfp/output/check.py on film.mp4)
     <build>/film/film_report.json / .md   the chapters' verdicts + the film's own verify / output QC (report.classify;
        "black frames" that verify.py lists only within 0.5 s of a chapter join are that join's fade - not applicable;
        any other black frame, or a full list of 6, stays a new problem)
     <build>/film/film_state.json   the input fingerprint of the assembly: an unchanged film is not assembled again.
Default build: ROOT/build/film/<manifest folder name>. A chapter that does not end complete (or complete_with_problems)
stops the film there with that chapter's own status; the film is assembled only from complete chapters.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import plan as PL
from . import report as RP
from . import runner as RN
from . import state as S

SCHEMA = "nfp.film.manifest/1"
STATE_SCHEMA = "nfp.film.state/1"
REPORT_SCHEMA = "nfp.film.report/1"
DONE = ("complete", "complete_with_problems")


class FilmError(ValueError):
    pass


def _engine():
    for p in (str(PL.ENGINE), str(PL.NFP), str(PL.ROOT / "scripts")):
        if p not in sys.path:
            sys.path.insert(0, p)


def load(path):
    p = Path(path)
    p = p / "film.json" if p.is_dir() else p
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise FilmError(f"film manifest: cannot read {p}: {e}") from None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise FilmError(f"film manifest: schema must be {SCHEMA}")
    extra = sorted(set(doc) - {"schema", "title", "chapters", "note"})
    if extra:
        raise FilmError(f"film manifest: unknown field(s) {', '.join(extra)}")
    chs = doc.get("chapters")
    if not isinstance(chs, list) or not chs:
        raise FilmError("film manifest: chapters must be a non-empty list")
    seen, out = set(), []
    for c in chs:
        if not isinstance(c, dict) or set(c) - {"id", "project", "chapter"} or not isinstance(c.get("id"), str) or not isinstance(c.get("project"), str):
            raise FilmError(f"film manifest: each chapter is {{id, project[, chapter]}}: {c!r}")
        if c["id"] in seen or not c["id"].replace("-", "").replace("_", "").isalnum():
            raise FilmError(f"film manifest: bad or duplicate chapter id {c['id']!r}")
        seen.add(c["id"])
        out.append({"id": c["id"], "project": str((p.parent / c["project"]).resolve()), "chapter": c.get("chapter")})
    return {"path": str(p.resolve()), "dir": str(p.parent.resolve()), "title": doc.get("title") or p.parent.name, "chapters": out,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def plans(man, build=None):
    root = Path(build) if build else PL.ROOT / "build" / "film" / Path(man["dir"]).name
    pls = []
    for c in man["chapters"]:
        try:
            pl = PL.plan(c["project"], c["chapter"], build=str(root / c["id"]))
        except PL.PlanError as e:
            raise FilmError(f"chapter {c['id']}: {e}") from None
        pls.append(pl)
    _engine()
    import project as P
    import subtitles as SB
    langs, subs = set(), set()
    for c, pl in zip(man["chapters"], pls):
        proj = P.load(pl["project"])
        langs.add(proj["meta"]["lang"])
        subs.add(json.dumps(SB.settings(proj), sort_keys=True) if "subtitles" in proj else "none")
    if len(langs) > 1:
        raise FilmError(f"film manifest: the chapters have different languages {sorted(langs)}")
    if len(subs) > 1:
        raise FilmError("film manifest: the chapters have different subtitle settings (a film has one subtitle style)")
    return root, pls


def _fp(pls, man):
    h = hashlib.sha256(man["sha256"].encode())
    for pl in pls:
        b = Path(pl["build"])
        for f in ("story.mp4", "timing.json", "words.json"):
            S._hash_path(h, b / f)
    for code in ("nfp/orchestrator/film.py", "nfp/film/engine/assemble.py", "nfp/film/engine/verify.py", "nfp/output"):
        S._hash_path(h, PL.ROOT / code)
    return h.hexdigest()


def _ff(*args):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        raise FilmError(f"ffmpeg: {r.stderr.strip()[-300:]}")


def assemble(man, pls, out, say=print):
    """film.mp4 + timing.json + film.srt from the chapter builds (see the module doc)."""
    _engine()
    import assemble as AS
    out.mkdir(parents=True, exist_ok=True)
    durs, timings = [], []
    for pl in pls:
        b = Path(pl["build"])
        durs.append(float(json.loads((b / "words.json").read_text(encoding="utf-8"))["duration"]))
        timings.append(json.loads((b / "timing.json").read_text(encoding="utf-8")))
    a0 = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels", "-of", "json",
                                    str(Path(pls[0]["build"]) / "story.mp4")], capture_output=True, text=True).stdout)["streams"][0]
    rate, ch = int(a0["sample_rate"]), int(a0["channels"])
    specs = []
    for pl in pls:                                # the stream copy needs identical video streams
        v = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                       "stream=codec_name,width,height,pix_fmt,avg_frame_rate,time_base,profile", "-of", "json",
                                       str(Path(pl["build"]) / "story.mp4")], capture_output=True, text=True).stdout)["streams"][0]
        specs.append(v)
    if any(x != specs[0] for x in specs):
        raise FilmError(f"the chapter MP4s' video streams differ (cannot be joined without re-encoding): {specs}")
    tscale = specs[0]["time_base"].split("/")[1]
    rows = AS.plan(durs, rate)                    # whole frames per chapter; audio slot = frames x samples per frame
    for r, d in zip(rows, durs):
        if abs(r["frames"] / AS.FPS - d) > 1e-6:
            raise FilmError(f"a chapter of {d} s is not a whole number of frames")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        wavs = []
        for i, (pl, r) in enumerate(zip(pls, rows)):
            w = td / f"a{i}.wav"
            _ff("-i", Path(pl["build"]) / "story.mp4", "-vn", "-ac", ch, "-ar", rate, "-c:a", "pcm_s16le", "-t", f"{r['samples'] / rate:.6f}", w)
            wavs.append(w)
        AS.concat_wavs(wavs, rows, td / "audio.wav")
        lst = td / "list.txt"
        lst.write_text("".join(f"file '{Path(pl['build']) / 'story.mp4'}'\n" for pl in pls), encoding="utf-8")
        total = sum(r["frames"] for r in rows) / AS.FPS     # ONE command (a second stream-copy remux drops the last frame's duration);
        # -copyts: the concat demuxer's continuous timestamps as they are (both streams start at 0, no 21 ms video delay)
        _ff("-f", "concat", "-safe", "0", "-i", lst, "-i", td / "audio.wav", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-t", f"{total:.6f}", "-video_track_timescale", tscale, "-copyts", "-movflags", "+faststart", out / "film.mp4")
    shifted = []
    for c, t, r in zip(man["chapters"], timings, rows):
        st = AS.shift_timing(t, r["offset_sec"])
        for s in st["sentences"]:
            s["id"] = f"{c['id']}.{s['id']}"
        shifted.append(st)
    merged = dict(timings[0], sentences=[s for t in shifted for s in t["sentences"]],
                  audio=dict(timings[0]["audio"], total=round(sum(durs), 6), sentences=[]),
                  film={"chapters": [{"id": c["id"], "offset": r["offset_sec"], "duration": d, "frames": r["frames"]}
                                     for c, r, d in zip(man["chapters"], rows, durs)]})
    (out / "timing.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "film.srt").write_text(AS.merged_srt(shifted), encoding="utf-8")
    say(f"  assembled {len(pls)} chapter(s): {round(sum(durs), 3)} s, {sum(r['frames'] for r in rows)} frames -> {out / 'film.mp4'}")
    return {"duration": round(sum(durs), 6), "frames": sum(r["frames"] for r in rows), "rate": rate, "channels": ch,
            "chapters": merged["film"]["chapters"]}


VERIFY = r"""
import json, sys
sys.path[:0] = sys.argv[1:4]
import project as P, verify as V
proj = P.load(sys.argv[4])
ch = {"id": "film", "target_duration": float(sys.argv[6])}
try:
    V.verify(proj, ch, sys.argv[5], mp4_name="film.mp4", expect=(1920, 1080), tag="")
except SystemExit as e:
    sys.exit(1 if e.code else 0)
"""


def verify_film(pl0, out, total, env):
    """Film's own verify.py on film.mp4 (its own process), against the merged timing and the film's total length."""
    p = subprocess.run([sys.executable, "-B", "-c", VERIFY, str(PL.ENGINE), str(PL.NFP), str(PL.ROOT / "scripts"), pl0["project"], str(out), str(total)],
                       capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def output_film(pl0, out, env):
    p = subprocess.run([sys.executable, "-B", str(PL.NFP / "output" / "check.py"), "--build", str(out), "--project", pl0["project"],
                        "--chapter", pl0["chapter"], "--mp4", "film.mp4"], capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def run_film(path, build=None, fonts=None, gsap=None, allow_network=False, force=False, executors=None, browser=None, say=print):
    man = load(path)
    root, pls = plans(man, build)
    out = root / "film"
    st = {"schema": STATE_SCHEMA, "manifest": man["path"], "build": str(root), "chapters": {}, "status": "running"}
    for c, pl in zip(man["chapters"], pls):
        say(f"== chapter {c['id']} ({Path(pl['project']).name})")
        cst = RN.run(pl, fonts=fonts, gsap=gsap, allow_network=allow_network, force=force, executors=executors, browser=browser, say=say)
        st["chapters"][c["id"]] = {"status": cst["status"], "build": pl["build"], "ran": cst["runs"][-1]["ran"]}
        if cst["status"] not in DONE:
            st.update(status=cst["status"], stopped_at=c["id"])
            return _finish(man, pls, out, st, None, say)
    fp = _fp(pls, man)
    old = _read(out / "film_state.json")
    have = all((out / f).exists() for f in ("film.mp4", "timing.json", "verify.json", "output_qc.json"))
    if not force and old and old.get("inputs") == fp and have:
        say("== film: up to date (no chapter changed)")
        st.update(status=old.get("status", "complete"), assembled=old.get("assembled"), assembly="up_to_date", inputs=fp)
        return _finish(man, pls, out, st, old.get("assembled"), say)
    say("== film: assembly, verify, output QC")
    env = RN.step_env(fonts, allow_network)
    info = assemble(man, pls, out, say)
    vrc, vlog = verify_film(pls[0], out, info["duration"], env)
    orc, olog = output_film(pls[0], out, env)
    (out / "logs").mkdir(exist_ok=True)
    (out / "logs" / "verify.log").write_text(vlog, encoding="utf-8")
    (out / "logs" / "output.log").write_text(olog, encoding="utf-8")
    probs = vrc != 0 or orc != 0
    if not (out / "verify.json").exists() or not (out / "output_qc.json").exists():
        st.update(status="failed", stopped_at="film")
    else:
        st.update(status="complete_with_problems" if probs else "complete")
    st.update(assembled=info, assembly="done", inputs=fp)
    return _finish(man, pls, out, st, info, say)


def _read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _finish(man, pls, out, st, info, say):
    out.mkdir(parents=True, exist_ok=True)
    (out / "film_state.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    rep = report(man, pls, out, st, info)
    say(f"film report: {rep['verdict']} (production_ready: {rep['production_ready']}) -> {out / 'film_report.md'}")
    return st


def report(man, pls, out, st, info):
    reasons, notes, chapters = [], [], []
    for c, pl in zip(man["chapters"], pls):
        r = _read(Path(pl["build"]) / "production_report.json")
        chapters.append({"id": c["id"], "project": pl["project"], "verdict": r and r["verdict"], "production_ready": bool(r and r["production_ready"]),
                         "reasons": (r or {}).get("reasons", []), "substitutes": (r or {}).get("substitutes", []),
                         "status": st["chapters"].get(c["id"], {}).get("status", "not run")})
    bad = [x for x in chapters if x["verdict"] == "FAIL"]
    if bad:
        reasons += [f"chapter {x['id']}: FAIL - {'; '.join(x['reasons'])[:200]}" for x in bad]
    vj = _read(out / "verify.json") if info else None
    oq = _read(out / "output_qc.json") if info else None
    current = False
    if oq:
        if str(PL.NFP) not in sys.path:
            sys.path.insert(0, str(PL.NFP))
        from output import check as OC
        current, why = OC.is_current(oq, out, pls[0]["project"], pls[0]["chapter"], mp4="film.mp4")
        if not current:
            notes.append("film output QC is stale: " + "; ".join(why))
    verify = None
    if vj:
        probs = list(vj.get("problems", []))
        na = []
        sb = (oq or {}).get("subtitles") or {}
        rows = (sb.get("replacement") or {}).get("sentences")
        rows_ok = bool(rows) and not any(r.get("problem") for r in rows)
        if current and sb.get("not_applicable"):         # mode rule: only when the mode's own check passed; estimated_first_word: a fact
            for x in sb["not_applicable"]:
                if x["problem"] in probs and (x.get("rule") == "estimated_first_word" or rows_ok):
                    probs.remove(x["problem"])
                    na.append(x)
        joins = [c["offset"] for c in (info or {}).get("chapters", [])[1:]]
        for pr in list(probs):                    # each chapter page fades from / to black: a dip at a join is the transition
            if pr.startswith("black frames at ") and joins:
                try:
                    ts = json.loads(pr[len("black frames at "):])
                except ValueError:
                    continue
                if len(ts) < 6 and all(min(abs(t - j) for j in joins) <= 0.5 for t in ts):    # verify.py lists at most 6
                    probs.remove(pr)
                    na.append({"problem": pr, "reason": f"chapter transition: each chapter's own fade from / to black at the join(s) {joins} s"})
        known, new = RP.classify(probs)
        verify = {"duration": vj.get("duration"), "video": vj.get("video"), "known_limitations": known, "not_applicable": na, "new_problems": new,
                  "audio_onset_vs_first_word_ms": vj.get("mp4_audio_onset_vs_first_word_ms")}
        if new:
            reasons.append(f"film verify: {len(new)} new problem(s): {new[0]['problem'][:120]}")
    output = None
    if oq and current:
        errs = [i for i in oq["issues"] if i["level"] == "error"]
        output = {"status": oq["status"], "errors": errs, "warnings": [i for i in oq["issues"] if i["level"] == "warning"],
                  "technical": oq.get("technical"), "loudness": oq.get("loudness"),
                  "sync": {k: (oq.get("sync") or {}).get(k) for k in ("measured", "not_measurable", "limit_ms")}}
        if errs:
            reasons.append(f"film output QC: {len(errs)} error(s): {errs[0]['check']}/{errs[0]['code']}: {errs[0]['message']}"[:300])
    subs = sorted({s for x in chapters for s in x["substitutes"]})
    if reasons:
        verdict = "FAIL"
    elif st["status"] == "blocked" or any(x["verdict"] == "BLOCKED" for x in chapters):
        verdict = "BLOCKED"
        reasons.append(f"stopped at {st.get('stopped_at')}: " + "; ".join(r for x in chapters for r in x["reasons"])[:300])
    elif st["status"] not in DONE or not vj or not (oq and current) or any(x["verdict"] in (None, "INCOMPLETE") for x in chapters):
        verdict = "INCOMPLETE"
        reasons.append(f"film not complete (status {st['status']}" + (f", stopped at {st.get('stopped_at')}" if st.get("stopped_at") else "") + ")")
    else:
        lim = verify["known_limitations"] or any(x["verdict"] == "PASS_WITH_KNOWN_LIMITATIONS" for x in chapters)
        verdict = "PASS_WITH_KNOWN_LIMITATIONS" if lim else "PASS"
    rep = {"schema": REPORT_SCHEMA, "manifest": man["path"], "title": man["title"], "build": st["build"], "status": st["status"],
           "assembly": st.get("assembly"), "film": info, "chapters": chapters, "verify": verify, "output": output, "verdict": verdict,
           "reasons": reasons, "notes": notes, "substitutes": subs,
           "production_ready": verdict in ("PASS", "PASS_WITH_KNOWN_LIMITATIONS") and not subs and all(x["production_ready"] for x in chapters)}
    (out / "film_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "film_report.md").write_text(summary(rep) + "\n", encoding="utf-8")
    return rep


def summary(rep):
    f = rep.get("film") or {}
    L = [f"# Film report - {rep['title']}", "", f"verdict: {rep['verdict']}   production_ready: {'yes' if rep['production_ready'] else 'NO'}"]
    L += [f"  reason: {r}" for r in rep["reasons"]] + [f"  note: {n}" for n in rep["notes"]]
    L += [f"  NOT A PRODUCTION BUILD - {s}" for s in rep["substitutes"]]
    L += ["", f"## film: {f.get('duration')} s, {f.get('frames')} frames, {len(rep['chapters'])} chapter(s); assembly {rep.get('assembly')}"]
    for c in f.get("chapters", []):
        L.append(f"  {c['id']}: from {c['offset']:.3f} s, {c['duration']} s ({c['frames']} frames)")
    L += ["", "## chapters"] + [f"  {x['id']:8s} {x['status'] or '-':24s} {x['verdict'] or '-':28s} {Path(x['project']).name}" for x in rep["chapters"]]
    v = rep.get("verify")
    if v:
        L += ["", f"## film verify.py: {len(v['new_problems'])} new, {len(v['known_limitations'])} known, {len(v['not_applicable'])} not applicable"]
        L += [f"  NEW: {x['problem']}" for x in v["new_problems"]] + [f"  known ({x['id']}): {x['problem']}" for x in v["known_limitations"]]
        L += [f"  not applicable: {x['problem']}" for x in v["not_applicable"]]
    o = rep.get("output")
    if o:
        t = o.get("technical") or {}
        L += ["", f"## film output QC: {o['status']} ({len(o['errors'])} error(s), {len(o['warnings'])} warning(s))",
              f"  {json.dumps(t.get('video'))}  audio {json.dumps(t.get('audio'))}", f"  loudness {o.get('loudness')}; sync {o.get('sync')}"]
        L += [f"  ERROR {i['check']}/{i['code']}: {i['message']}" for i in o["errors"]] + [f"  warning {i['check']}/{i['code']}: {i['message']}" for i in o["warnings"]]
    return "\n".join(L)
