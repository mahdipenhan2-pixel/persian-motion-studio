#!/usr/bin/env python3
"""Timing / structure check of the 6-minute documentary (no network, no TTS, no audio is touched).
For every chapter it builds the page with synthetic (or, with --data, real) timing in a scratch folder and reports:
  - errors / warnings of the timeline, shot list (anchored to sentence ids), gaps or overlaps between shots,
  - the longest shot (visual change at least every 25 s), share of cartoon (style A) vs documentary graphics (style B),
  - shot isolation: at the middle of every shot exactly one shot group is displayed (no element lingers from another shot),
  - robustness: the same checks with other narration paces (--paces), proving shots follow sentence times, not fixed seconds.
Exit code 1 on any hard failure. Usage: analyze_6min.py [--data DIR] [--paces 12.5,14.8,17] [--out DIR]"""
import argparse, json, re, sys
from pathlib import Path
DOCU = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DOCU / "qa")); sys.path.insert(0, str(DOCU / "engine"))
import render_6min as R, project as P  # noqa

STYLE_B = ("DOCUMENTARY GRAPHIC", "ANIMATED MAP")
MAX_SHOT = 25.0


def minor(w):
    """a flash/whip overlay key that had to move by less than 0.25 s (several flashes closer than their duration) - harmless, reported only as a note"""
    m = re.match(r"overlap on opacity at ([\d.]+) \(prev end ([\d.]+)\)", w)
    return bool(m) and float(m.group(2)) - float(m.group(1)) < 0.25


def analyse(proj, ch, out, data, cps, pw):
    R.SYNTH["cps"] = cps or R.SYNTH["cps"]
    build, info = R.prepare(proj, ch, out, data)
    b, pg, errs = R.open_page(pw, build)
    cues = pg.evaluate("window.__docuCues"); warns = pg.evaluate("window.__docuWarnings"); dur = pg.evaluate("window.__timelines.main.duration()")
    shots = cues["shots"]; rows = []; bad = []
    texts = pg.evaluate("Object.fromEntries([...document.querySelectorAll('g.shot')].map(g => [g.id.replace('shot-',''), g.textContent]))")
    for sid, t0, t1 in shots:
        tx = texts.get(sid, ""); style = "B" if any(k in tx for k in STYLE_B) else "A"
        rows.append({"id": sid, "t0": round(t0, 2), "t1": round(t1, 2), "len": round(t1 - t0, 2), "style": style})
    for (a, b2) in zip(shots, shots[1:]):
        if abs(a[2] - b2[1]) > 0.034: bad.append(f"gap/overlap between {a[0]} and {b2[0]}: {a[2]:.2f} vs {b2[1]:.2f}")
    if shots and shots[0][1] > 0.034: bad.append(f"first shot starts at {shots[0][1]:.2f}")
    if shots and abs(shots[-1][2] - info["duration"]) > 0.25: bad.append(f"last shot ends at {shots[-1][2]:.2f}, chapter video {info['duration']:.2f}")
    for r in rows:
        if r["len"] > MAX_SHOT: bad.append(f"shot {r['id']} lasts {r['len']} s (> {MAX_SHOT})")
        t = (r["t0"] + r["t1"]) / 2
        n = pg.evaluate(f"(() => {{ window.__timelines.main.time({t}); return [...document.querySelectorAll('g.shot')].filter(g => getComputedStyle(g).display !== 'none').map(g => g.id); }})()")
        if n != ["shot-" + r["id"]]: bad.append(f"isolation: at {t:.1f} s displayed {n}, expected shot-{r['id']}")
    ph = pg.evaluate("[...document.querySelectorAll('svg, #band, .cap, body > div')].some(e => /PLACEHOLDER/i.test(e.textContent || ''))")
    if ph: bad.append("text PLACEHOLDER found in the page")
    b.close()
    tA = sum(r["len"] for r in rows if r["style"] == "A"); tB = sum(r["len"] for r in rows if r["style"] == "B")
    return {"chapter": ch["id"], "duration": round(dur, 2), "shots": len(rows), "errors": errs[:5], "warnings": warns[:5], "longest": max(r["len"] for r in rows), "A_s": round(tA, 1), "B_s": round(tB, 1), "rows": rows, "notes": [w for w in warns if minor(w)], "problems": bad + [f"js error: {e}" for e in errs] + [f"warning: {w}" for w in warns if not minor(w)]}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--project", default="kim-docu-6min"); ap.add_argument("--data"); ap.add_argument("--paces", default="14.8"); ap.add_argument("--out", default="/tmp/docu_analyze"); ap.add_argument("--json")
    a = ap.parse_args(); proj = P.load(a.project); Path(a.out).mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    fail = False; allrep = {}
    with sync_playwright() as pw:
        for cps in [float(x) for x in a.paces.split(",")]:
            tot = {"A": 0, "B": 0, "dur": 0}
            print(f"== pace {cps} chars/s ==")
            for ch in proj["chapters"]:
                r = analyse(proj, ch, Path(a.out) / f"p{cps}", a.data, cps, pw); allrep[f"{cps}/{ch['id']}"] = r
                tot["A"] += r["A_s"]; tot["B"] += r["B_s"]; tot["dur"] += r["duration"]
                print(f" {r['chapter']}: {r['duration']:.1f} s, {r['shots']} shots, longest {r['longest']} s, A {r['A_s']} s / B {r['B_s']} s, problems {len(r['problems'])}, notes {len(r['notes'])}")
                for p in r["problems"]: print("   !", p); fail = True
            print(f" TOTAL {tot['dur']:.1f} s, style A {100 * tot['A'] / (tot['A'] + tot['B']):.0f} % / style B {100 * tot['B'] / (tot['A'] + tot['B']):.0f} %")
    if a.json: json.dump(allrep, open(a.json, "w"), indent=1)
    print("RESULT:", "FAIL" if fail else "OK"); sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
