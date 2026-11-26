#!/usr/bin/env python3
"""NFP Production Orchestrator - command line. One chapter of one Film project, from its files to a verified MP4 and one
QC report; every step is the existing engine's command (see README.md).

  python3 nfp/orchestrator/cli.py plan      --project <dir> [--chapter id] [--build dir]
  python3 nfp/orchestrator/cli.py preflight --project <dir> [...] [--fonts dir] [--gsap file]
  python3 nfp/orchestrator/cli.py run       --project <dir> [...] [--fonts dir] [--gsap file] [--until step] [--from step]
                                            [--force] [--allow-network]
  python3 nfp/orchestrator/cli.py status    --project <dir> [...]
  python3 nfp/orchestrator/cli.py report    --project <dir> [...]
  python3 nfp/orchestrator/cli.py run       --film <film.json> [--build dir] [--fonts dir] [--gsap file] [--force] [--allow-network]
  python3 nfp/orchestrator/cli.py plan|report --film <film.json> [--build dir]
                                            a film of several chapters (Film manifest, see film.py): every chapter is a
                                            normal Film project run as above, then the film is assembled (assemble.py)
                                            and verified (verify.py + Output QC) as one MP4: <build>/film/film.mp4

Nothing goes online (and nothing paid runs) without --allow-network: steps that would - the core's Gemini TTS, Gemini
voices of the Voice Engine, a HyperFrames that is not in the local npx cache - are BLOCKED with the forecast reason.
--fonts / --gsap default to $NFP_FONTS / $NFP_GSAP, else to the fixed asset folders ROOT/assets/fonts and
ROOT/assets/vendor/gsap/gsap.min.js filled by nfp/setup/fetch_assets.py. Exit: 0 complete (or the asked part of it), 1 failed or preflight
FAIL, 2 blocked, 3 usage, 4 complete but verify.py listed problems (see `report`).
`preflight` exits 1 on FAIL; `report` exits 0 for PASS / PASS_WITH_KNOWN_LIMITATIONS, otherwise 1.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from orchestrator import plan as PL         # noqa: E402
from orchestrator import preflight as PF    # noqa: E402
from orchestrator import runner as RN       # noqa: E402
from orchestrator import state as S         # noqa: E402


def _asset(rel):
    """The fixed asset folder (nfp/setup/fetch_assets.py fills it), when it is there."""
    p = PL.ROOT / "assets" / rel
    return str(p) if p.exists() else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "preflight", "run", "status", "report"])
    ap.add_argument("--project")
    ap.add_argument("--film")
    ap.add_argument("--chapter")
    ap.add_argument("--build")
    ap.add_argument("--fonts", default=os.environ.get("NFP_FONTS") or _asset("fonts"))
    ap.add_argument("--gsap", default=os.environ.get("NFP_GSAP") or _asset("vendor/gsap/gsap.min.js"))
    ap.add_argument("--until")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--browser")
    a = ap.parse_args(argv)
    if bool(a.project) == bool(a.film):
        print("ERROR: give exactly one of --project or --film", file=sys.stderr)
        return 3
    if a.film:
        return film_main(a)
    try:
        pl = PL.plan(a.project, a.chapter, a.build)
    except PL.PlanError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    fonts = str(Path(a.fonts).resolve()) if a.fonts else None
    gsap = str(Path(a.gsap).resolve()) if a.gsap else None
    if a.command == "plan":
        for s in pl["steps"]:
            print(f"{s['name']:8s} {' '.join(s['run']):18s} {s['engine']:10s} {s['cost']:9s} {s['why']}")
        print(f"build: {pl['build']}")
        return 0
    if a.command == "preflight":
        r = PF.preflight(pl, fonts=fonts, gsap=gsap)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 1 if r["status"] == "FAIL" else 0
    if a.command == "status":
        p = S.path(pl["build"])
        if not p.exists():
            print(f"no production state yet ({p})")
            return 0
        st = json.loads(p.read_text(encoding="utf-8"))
        print(f"status: {st['status']} (updated {st['updated']})")
        for s in pl["steps"]:
            r = st["steps"].get(s["name"], {})
            print(f"  {s['name']:8s} {r.get('status', '-'):8s} {r.get('executor', '')}  {r.get('detail') or r.get('reason') or ''}"[:200])
        return 0
    if a.command == "report":
        from orchestrator import report as RP
        rep = RP.report(pl, fonts=fonts, gsap=gsap)
        print(RP.summary(rep))
        return 0 if rep["verdict"] in ("PASS", "PASS_WITH_KNOWN_LIMITATIONS") else 1
    try:
        st = RN.run(pl, fonts=fonts, gsap=gsap, allow_network=a.allow_network, until=a.until, start=a.start, force=a.force,
                    browser=a.browser)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    print(f"run: {st['status']}  ({S.path(pl['build'])})")
    return {"complete": 0, "partial": 0, "blocked": 2, "complete_with_problems": 4}.get(st["status"], 1)


def film_main(a):
    from orchestrator import film as FM
    fonts = str(Path(a.fonts).resolve()) if a.fonts else None
    gsap = str(Path(a.gsap).resolve()) if a.gsap else None
    try:
        man = FM.load(a.film)
        root, pls = FM.plans(man, a.build)
    except FM.FilmError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if a.command == "plan":
        for c, pl in zip(man["chapters"], pls):
            print(f"chapter {c['id']}: {pl['project']} ({pl['chapter']}): {' -> '.join(s['name'] for s in pl['steps'])}")
        print(f"then: assemble -> verify -> output QC -> {root / 'film' / 'film.mp4'}")
        return 0
    if a.command == "report":
        rep = FM._read(root / "film" / "film_report.json")
        if not rep:
            print(f"no film report yet ({root / 'film'})")
            return 1
        print(FM.summary(rep))
        return 0 if rep["verdict"] in ("PASS", "PASS_WITH_KNOWN_LIMITATIONS") else 1
    if a.command != "run":
        print("ERROR: with --film: plan, run or report", file=sys.stderr)
        return 3
    try:
        st = FM.run_film(a.film, build=a.build, fonts=fonts, gsap=gsap, allow_network=a.allow_network, force=a.force, browser=a.browser)
    except FM.FilmError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"film: {st['status']}  ({root / 'film'})")
    return {"complete": 0, "complete_with_problems": 4, "blocked": 2}.get(st["status"], 1)


if __name__ == "__main__":
    sys.exit(main())
