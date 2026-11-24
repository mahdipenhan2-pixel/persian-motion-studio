#!/usr/bin/env python3
"""
NFP Character Engine - C3 command line (offline).

  python3 nfp/character/animation/cli.py plan  <actions.json> [--out keylist.json]
  python3 nfp/character/animation/cli.py check <keylist.json>
  python3 nfp/character/animation/cli.py demo  <actions.json> --html <page.html>

plan   action script -> KeyList (deterministic JSON; prints the digest and the lip-sync report)
check  validate any KeyList file
demo   one self-contained HTML page (rig + runtime + KeyList inlined, no external URL) with play / pause / seek,
       for looking at a plan in a local browser. It is a test page only: not connected to Studio or Docu.
"""
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG.parent))

from character.animation.keys import PlanError, dumps, validate_keylist  # noqa: E402
from character.animation.script import plan_file  # noqa: E402

RIG = PKG / "renderers" / "flat_cartoon_v2"


def demo_html(kl, title="NFP C3 demo"):
    css = (RIG / "rig.css").read_text(encoding="utf-8")
    js = [(RIG / "rig" / "00_core.js").read_text(encoding="utf-8"), (RIG / "rig" / "10_chars.js").read_text(encoding="utf-8"),
          (PKG / "runtime" / "character_runtime.js").read_text(encoding="utf-8"),
          (PKG / "runtime" / "character_player.js").read_text(encoding="utf-8")]     # live preview controls
    data = json.dumps(kl, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    w, h = kl["stage"]["width"], kl["stage"]["height"]
    scripts = "\n".join(f"<script>\n{s}\n</script>" for s in js)
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
{css}
html,body{{margin:0;background:#1d2430;color:#e9edf2;font:14px/1.5 system-ui,sans-serif}}
#wrap{{max-width:1100px;margin:0 auto;padding:16px}}
#stage{{width:100%;height:auto;display:block;background:linear-gradient(#cfe3ee,#eef4f0 70%,#c9d6b8 70%);border-radius:8px}}
#bar{{display:flex;gap:8px;align-items:center;margin-top:10px;direction:ltr}}
#bar input[type=range]{{flex:1}}
button{{background:#3b4a63;color:#fff;border:0;border-radius:6px;padding:6px 12px;cursor:pointer}}
#t{{font-variant-numeric:tabular-nums;min-width:120px}}
</style></head><body><div id="wrap">
<h3>{html.escape(title)}</h3>
<svg id="stage" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"></svg>
<div id="bar"><button id="play">play</button><button id="pause">pause</button><button id="resume">resume</button>
<button id="stop">stop</button><input id="seek" type="range" min="0" max="{kl['frames']}" value="0"><span id="t"></span></div>
</div>
{scripts}
<script id="nfp-keylist" type="application/json">{data}</script>
<script>
(function () {{
  const kl = JSON.parse(document.getElementById("nfp-keylist").textContent);
  const rt = NFPCharacterRuntime.create({{ svg: document.getElementById("stage"), keylist: kl }});
  NFPCharacterPlayer.attach(rt);                     // play / pause / resume / stop for this preview only
  window.NFP_RT = rt;
  const seekEl = document.getElementById("seek"), tEl = document.getElementById("t");
  const show = (t) => {{ tEl.textContent = t.toFixed(2) + " / " + rt.duration.toFixed(2) + " s"; seekEl.value = Math.round(t * rt.fps); }};
  show(0);
  document.getElementById("play").onclick = () => rt.play({{ onFrame: show }});
  document.getElementById("pause").onclick = () => {{ rt.pause(); show(rt.time()); }};
  document.getElementById("resume").onclick = () => rt.resume();
  document.getElementById("stop").onclick = () => {{ rt.stop(); show(rt.time()); }};
  seekEl.oninput = () => {{ rt.pause(); show(rt.seek(seekEl.value / rt.fps)); }};
}})();
</script></body></html>
"""


def main(argv):
    if len(argv) < 2 or argv[0] not in ("plan", "check", "demo"):
        print(__doc__)
        return 2
    cmd, path = argv[0], Path(argv[1])
    try:
        if cmd == "check":
            problems = validate_keylist(json.loads(path.read_text(encoding="utf-8")))
            print("OK" if not problems else "\n".join(problems))
            return 1 if problems else 0
        kl = plan_file(path)
    except PlanError as e:
        print("PLAN ERROR\n" + "\n".join(e.problems))
        return 1
    if cmd == "plan":
        out = argv[argv.index("--out") + 1] if "--out" in argv else None
        if out:
            Path(out).write_text(dumps(kl), encoding="utf-8")
        print(f"keys: {len(kl['keys'])}  frames: {kl['frames']} @ {kl['fps']} fps  digest: {kl['digest']}")
        for t in kl["lipsync"]["talks"]:
            print(f"talk {t['actor']}: {t['words']} words, {t['flaps']} mouth changes, max open offset "
                  f"{t['max_open_offset_frames']} frame(s), unresolved: {[u['text'] for u in t['unresolved_words']]}")
        return 0
    if "--html" not in argv:
        print("demo needs --html <page.html>")
        return 2
    out = Path(argv[argv.index("--html") + 1])
    out.write_text(demo_html(kl), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
