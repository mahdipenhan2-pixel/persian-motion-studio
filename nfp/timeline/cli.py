#!/usr/bin/env python3
"""NFP Timeline (T1) command line - checks only, nothing is rendered, fetched or changed.

  python3 nfp/timeline/cli.py check   <timeline.json> [--assets assets.json] [--words words.json] [--no-files]
  python3 nfp/timeline/cli.py resolve <timeline.json> --words words.json --out <new timeline.json>
  python3 nfp/timeline/cli.py assets  <assets.json> [--no-files]
Exit code 1 when the check fails (errors), 0 otherwise.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import timeline as TL                      # noqa: E402
from timeline import assets as AS          # noqa: E402


def show(rep):
    for x in rep["issues"]:
        where = " ".join(f"{k}={x[k]}" for k in ("track", "clip", "asset") if k in x)
        print(f"  {x['level'].upper():7} {x['code']:18} {where:24} {x['message']}")
    print(f"QC {rep['status']}: {rep['errors']} error(s), {rep['warnings']} warning(s), {rep['infos']} info")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("check", "resolve", "assets"))
    ap.add_argument("file")
    ap.add_argument("--assets")
    ap.add_argument("--words")
    ap.add_argument("--out")
    ap.add_argument("--no-files", action="store_true")
    a = ap.parse_args()
    data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    if a.command == "assets":
        st, issues = AS.check(data, Path(a.file).parent, check_files=not a.no_files)
        n = {lv: sum(1 for x in issues if x["level"] == lv) for lv in ("error", "warning", "info")}
        show({"issues": issues, "status": "FAIL" if n["error"] else "WARN" if n["warning"] else "OK",
              "errors": n["error"], "warnings": n["warning"], "infos": n["info"]})
        print("assets: " + ", ".join(f"{k} {v}" for k, v in st.items()))
        sys.exit(1 if n["error"] else 0)
    ctx = TL.Context.from_words(a.words) if a.words else None
    if a.command == "resolve":
        if not (ctx and a.out):
            sys.exit("ERROR: resolve needs --words and --out")
        Path(a.out).write_text(json.dumps(TL.resolve(data, ctx), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"resolved -> {a.out}")
        return
    adoc, abase = (json.loads(Path(a.assets).read_text(encoding="utf-8")), Path(a.assets).parent) if a.assets else (None, None)
    rep = TL.validate(data, adoc, abase, ctx, check_files=not a.no_files)
    show(rep)
    sys.exit(1 if rep["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
