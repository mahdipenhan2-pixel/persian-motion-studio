#!/usr/bin/env python3
"""NFP Voice Engine command line (offline; no API, no TTS).

  python3 nfp/voice/cli.py check   <casting.json>                         casting findings (warnings / overrides)
  python3 nfp/voice/cli.py plan    <casting.json> <script.json> [--out plan.json]
  python3 nfp/voice/cli.py produce <casting.json> <script.json> --out <dir> [--rate 24000]
  python3 nfp/voice/cli.py validate <dir>/voice_manifest.json
  produce options (V2): --normalize ['{"target_lufs": -20}']  --qc ['{"clip_error_ratio": 0.001}']  --cache [DIR]
  python3 nfp/voice/cli.py estimate <casting.json> <script.json> [--normalize] [--cache [DIR]]
                                                   sentences each provider would have to make (no request, no file)
  AI speech (V3, OFF by default): produce ... --allow-tts gemini [--model M] [--max-requests N]
      needs GEMINI_FREE_TIER_CONFIRMED=YES and GEMINI_API_KEY in the environment; checked before any request
  python3 nfp/voice/cli.py cache-stats [--cache DIR]     entries of the cache (default $NFP_VOICE_CACHE or ~/.cache/nfp-voice)
  python3 nfp/voice/cli.py cache-clear [--cache DIR]     delete the cache entries only (never project files)
Exit code 1 on errors or blocks (the messages say why).
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from voice import VoiceError, load_casting, make_plan, produce, validate_manifest  # noqa: E402


def show(findings):
    for f in findings:
        print(f"  {f['level'].upper():<8} {f['role']}: {f['message']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "plan", "estimate", "produce", "validate", "cache-stats", "cache-clear"])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--rate", type=int, default=24000)
    ap.add_argument("--normalize", nargs="?", const="{}", help="JSON settings (normalize.DEFAULTS) - normalize sources")
    ap.add_argument("--qc", nargs="?", const="{}", help="JSON thresholds (qc.DEFAULTS) - write qc_report.json")
    ap.add_argument("--cache", nargs="?", const="", help="use the audio cache (folder; default $NFP_VOICE_CACHE or ~/.cache/nfp-voice)")
    ap.add_argument("--allow-tts", choices=["gemini"], help="enable AI speech for 'gemini' voices (real requests: approval only)")
    ap.add_argument("--model", help="Gemini TTS model (free-tier allow-list only)")
    ap.add_argument("--max-requests", type=int, help="request budget of this run")
    a = ap.parse_args()
    from voice.cache import Cache, CacheError
    from voice.manifest import estimate
    providers = None
    if a.allow_tts == "gemini":
        cfg = {}
        if a.model:
            cfg["model"] = a.model
        if a.max_requests is not None:
            cfg["max_requests"] = a.max_requests
        providers = {"gemini": cfg}
    try:
        if a.command in ("cache-stats", "cache-clear"):
            c = Cache(a.cache or None)
            if a.command == "cache-stats":
                print(f"{c.dir}: {len(c.entries())} entr(y/ies)")
            else:
                print(f"{c.dir}: {c.clear()} file(s) deleted")
            return
        if not a.files:
            sys.exit("give the casting file (and the script)")
        if a.command == "validate":
            p = validate_manifest(a.files[0])
            print("OK" if not p else "\n".join(p))
            sys.exit(1 if p else 0)
        c = load_casting(a.files[0])
        if a.command == "check":
            print(f"OK casting {c['project']}: narrator {c['narrator']['voice']}, {len(c['roles'])} role(s), "
                  f"block_mismatch {c['rules']['block_mismatch']}")
            show(c["findings"])
            return
        script = json.loads(Path(a.files[1]).read_text(encoding="utf-8"))
        plan = make_plan(c, script, base_dir=Path(a.files[1]).parent)
        if a.command == "plan":
            text = json.dumps(plan, ensure_ascii=False, indent=1, sort_keys=True)
            Path(a.out).write_text(text + "\n", encoding="utf-8") if a.out else print(text)
            show(plan["findings"])
            return
        if a.command == "estimate":
            e = estimate(plan, rate=a.rate, normalize=json.loads(a.normalize) if a.normalize is not None else None,
                         cache=Cache(a.cache or None) if a.cache is not None else None, providers=providers)
            for prov, x in sorted(e.items()):
                print(f"  {prov:<10} {x['sentences']} sentence(s), {x['cached']} cached, to make: {', '.join(x['to_make']) or '-'}"
                      + (f"  -> {x['requests']} API request(s)" if prov == "gemini" else ""))
            return
        if not a.out:
            sys.exit("produce needs --out <dir>")
        m = produce(plan, a.out, base_dir=Path(a.files[1]).parent, rate=a.rate,
                    normalize=json.loads(a.normalize) if a.normalize is not None else None,
                    qc=json.loads(a.qc) if a.qc is not None else None,
                    cache=Cache(a.cache or None) if a.cache is not None else None, providers=providers)
        print(f"OK {len(m['sentences'])} sentence(s), {len(m['speakers'])} speaker(s), {m['sample_rate']} Hz -> {a.out}")
        if "cache" in m:
            print(f"  cache {m['cache']['dir']}: {m['cache']['hits']} hit(s), {m['cache']['misses']} miss(es), "
                  f"{m['cache']['discarded']} discarded")
        if "qc" in m:
            print(f"  QC {m['qc']['summary']} -> {a.out}/qc_report.json")
        show(m["findings"])
    except CacheError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except VoiceError as e:
        print("ERROR:\n  " + "\n  ".join(e.problems), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
