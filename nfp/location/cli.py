#!/usr/bin/env python3
"""NFP Location Engine command line (L1c). Reads a locations.json; changes nothing; no network.

  python3 nfp/location/cli.py check      <locations.json> [--today YYYY-MM-DD] [--near-m 50] [--name-m 5000]
  python3 nfp/location/cli.py status     <locations.json> [--today YYYY-MM-DD]
  python3 nfp/location/cli.py parents    <locations.json> [--id <location id>]
  python3 nfp/location/cli.py duplicates <locations.json> [--near-m 50] [--name-m 5000]

  check       every issue (errors, warnings, info) and the QC result
  status      verified / draft for each location, with the reason of each draft
  parents     the parent chain of each location (or of --id) up to its root; parent errors
  duplicates  possible duplicates with distance and reason (nothing is merged)
Exit code: 0 = no errors (warnings allowed), 1 = errors in the file, 2 = the file cannot be read / bad arguments.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import location as L                       # noqa: E402
from location import hierarchy as HI       # noqa: E402


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("check", "status", "parents", "duplicates"))
    ap.add_argument("file")
    ap.add_argument("--today", help="the date reviews / accessed dates are compared with (default: today)")
    ap.add_argument("--near-m", type=float, default=L.duplicates.NEAR_M, help="same place if closer than this (metres)")
    ap.add_argument("--name-m", type=float, default=L.duplicates.NAME_M, help="same name and closer than this (metres)")
    ap.add_argument("--id", help="parents: only this location")
    a = ap.parse_args()
    try:
        doc = json.loads(Path(a.file).read_text(encoding="utf-8"))
    except OSError as e:
        fail(f"cannot read {a.file}: {e.strerror or e}")
    except json.JSONDecodeError as e:
        fail(f"{a.file} is not valid JSON: line {e.lineno}, column {e.colno}: {e.msg}")
    try:
        today = datetime.date.fromisoformat(a.today) if a.today else None
    except ValueError:
        fail(f"--today {a.today!r} is not a date like 2026-11-25")
    try:
        rep = L.validate(doc, today=today, near_m=a.near_m, name_m=a.name_m)
    except ValueError as e:
        fail(str(e))
    errors = rep["errors"]
    if a.command == "check":
        for x in rep["issues"]:
            print(f"  {x['level'].upper():7} {x['code']:22} {x.get('location', '-'):24} {x['message']}")
    elif a.command == "status":
        why = {}
        for x in rep["issues"]:
            if x["code"] == "draft":
                why.setdefault(x.get("location"), []).append(x["message"].split(": ", 1)[1])
        for lid, st in rep["locations"].items():
            print(f"  {st:9} {lid}" + (f"   ({'; '.join(why[lid])})" if lid in why else ""))
        n = sum(1 for s in rep["locations"].values() if s == "verified")
        print(f"{n} verified, {len(rep['locations']) - n} draft")
    elif a.command == "parents":
        index = {r["id"]: r for r in doc.get("locations", []) if isinstance(r, dict) and isinstance(r.get("id"), str)} \
            if isinstance(doc, dict) and isinstance(doc.get("locations"), list) else {}
        if a.id and a.id not in index:
            fail(f"no location {a.id!r} in {a.file}")
        for lid in [a.id] if a.id else sorted(index):
            try:
                chain = HI.ancestors(index, lid)
                rel = (index[lid].get("parent") or {}).get("relation") if isinstance(index[lid].get("parent"), dict) else None
                print(f"  {lid}" + (f"  -{rel}->  " + "  ->  ".join(chain) if chain else "  (no parent)"))
            except ValueError as e:
                print(f"  {lid}  ! {e}")
        par = {"parent_self", "unknown_parent", "parent_cycle", "bad_parent", "bad_relation", "outside_parent", "extent_outside_parent"}
        for x in rep["issues"]:
            if x["code"] in par:
                print(f"  {x['level'].upper():7} {x['code']:22} {x.get('location', '-'):24} {x['message']}")
        errors = sum(1 for x in rep["issues"] if x["code"] in par and x["level"] == "error")
    else:
        for d in rep["duplicates"]:
            print(f"  {d['reason']:15} {d['a']}  <->  {d['b']}   {d['distance_m']:.1f} m   {d['detail']}")
        print(f"{len(rep['duplicates'])} possible duplicate pair(s) (near: {a.near_m:g} m, same name: {a.name_m:g} m); nothing merged")
        errors = 0
    print(f"QC {rep['status']}: {rep['errors']} error(s), {rep['warnings']} warning(s), {rep['infos']} info")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
