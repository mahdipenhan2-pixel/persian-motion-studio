#!/usr/bin/env python3
"""
NFP Character Engine - command line (C1, offline, standard library only).

  python3 nfp/character/cli.py check   <project_dir>             validate cast.json + identity lock
  python3 nfp/character/cli.py lock    <project_dir> [--write]   show the lock; --write creates/updates it deliberately
  python3 nfp/character/cli.py resolve <project_dir> <id> [--stage S] [--wardrobe W] [--expr E]
  python3 nfp/character/cli.py scan    <root> [<root> ...]       isolation check over <root>/*/cast.json

Exit code 0 = OK, 1 = problems found (each printed on its own line).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from character import isolation as ISO  # noqa: E402
from character import registry as REG  # noqa: E402


def _fail(problems):
    for p in problems:
        print(f"PROBLEM {p}")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("project")
    lk = sub.add_parser("lock"); lk.add_argument("project"); lk.add_argument("--write", action="store_true")
    r = sub.add_parser("resolve"); r.add_argument("project"); r.add_argument("id")
    r.add_argument("--stage"); r.add_argument("--wardrobe"); r.add_argument("--expr")
    s = sub.add_parser("scan"); s.add_argument("roots", nargs="+")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "check":
            cast = REG.load_and_check(a.project)
            print(f"OK {cast['project']}: {len(cast['characters'])} character(s), identities match cast.lock.json")
            for ch in cast["characters"]:
                print(f"   {ch['id']:<24} {REG.fingerprint(ch)[:16]}  stages: {', '.join(ch['stages'])}  "
                      f"wardrobe: {', '.join(ch['wardrobe'])}")
            return 0
        if a.cmd == "lock":
            cast = REG.load_cast(a.project)
            lock = REG.make_lock(cast)
            text = json.dumps(lock, ensure_ascii=False, indent=2) + "\n"
            if a.write:
                (Path(a.project) / "cast.lock.json").write_text(text, encoding="utf-8")
                print(f"wrote {Path(a.project) / 'cast.lock.json'}")
            else:
                print(text, end="")
            return 0
        if a.cmd == "resolve":
            cast = REG.load_and_check(a.project)
            print(json.dumps(REG.resolve(cast, a.id, a.stage, a.wardrobe, a.expr), ensure_ascii=False, indent=2))
            return 0
        if a.cmd == "scan":
            rep = ISO.scan(a.roots)
            if rep["problems"]:
                return _fail(rep["problems"])
            print(f"OK {rep['projects']} project(s), {rep['characters']} character(s), no unintended copies")
            return 0
    except REG.CastError as e:
        return _fail(e.problems)
    return 2


if __name__ == "__main__":
    sys.exit(main())
