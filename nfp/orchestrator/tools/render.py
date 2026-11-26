"""NFP Production Orchestrator - D4: the two steps run.py has no command for. Both work on a RENDER COPY of the composed
page (<build>/render-copy: story/ with the CDN GSAP tag replaced by a local gsap.min.js - the same one-line change Film's
own render tests make); the product page <build>/story is never changed.

  smoke(pl, build, gsap)          the page in Chromium (Playwright, every non-file request refused): page errors, the
                                  Director's warnings (window.__docuWarnings), the main timeline's length against
                                  words.json's duration -> <build>/smoke.json. Fails on a page error, a missing timeline or
                                  a length mismatch; warnings are reported, not failed (the QC report classifies them).
  render(pl, build, gsap, browser) HyperFrames <HF_VERSION> lint + render with npm OFFLINE (nothing is downloaded: a
                                  HyperFrames that is not in the local npx cache makes the step fail, it is never fetched)
                                  -> <build>/story.mp4, <build>/render.json (lint result, ffprobe summary).
Each returns (ok, detail, log_text).
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

HF_VERSION = "0.9.83"
CDN = '<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>'
LOCAL = '<script src="gsap.min.js"></script>'
BROWSER = "/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"

SMOKE = r"""
const { createRequire } = await import("node:module"); const fs = await import("node:fs");
const { chromium } = createRequire(import.meta.url)("playwright");
const [dir, out] = process.argv.slice(2); const errors = [], refused = [];
const br = await chromium.launch(); const pg = await (await br.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
pg.on("pageerror", (e) => errors.push(String(e)));
await pg.route("**/*", (r) => { const u = r.request().url(); if (u.startsWith("file:") || u.startsWith("data:")) return r.continue(); refused.push(u); return r.abort(); });
await pg.goto("file://" + dir + "/index.html");
let has = true;
try { await pg.waitForFunction(() => !!(window.__timelines && window.__timelines.main), null, { timeout: 20000 }); } catch (e) { has = false; }
await pg.evaluate(async () => { await document.fonts.ready; });
const r = await pg.evaluate((has) => {
  const tl = has ? window.__timelines.main : null;
  if (tl) { for (const t of [0, tl.duration() / 2, Math.max(0, tl.duration() - 0.05)]) tl.seek(t, false); }
  return { timeline: !!tl, duration: tl ? Math.round(tl.duration() * 1000) / 1000 : null, warnings: window.__docuWarnings || [],
           fonts: [...document.fonts].filter(x => x.status === "loaded").map(x => x.family + " " + x.weight).sort() };
}, has);
r.errors = errors; r.refused_requests = refused; fs.writeFileSync(out, JSON.stringify(r)); await br.close();
"""


def render_copy(build, gsap):
    build = Path(build)
    page = (build / "story" / "index.html").read_text(encoding="utf-8")
    if page.count(CDN) != 1:
        raise ValueError(f"the composed page has {page.count(CDN)} GSAP CDN tag(s), expected exactly 1")
    rdir = build / "render-copy"
    if rdir.exists():
        shutil.rmtree(rdir)
    shutil.copytree(build / "story", rdir)
    (rdir / "index.html").write_text(page.replace(CDN, LOCAL), encoding="utf-8")
    shutil.copyfile(gsap, rdir / "gsap.min.js")
    return rdir


def smoke(pl, build, gsap, browser=None):
    build = Path(build)
    if not gsap or not Path(gsap).is_file():
        return False, "no local GSAP copy (--gsap): the page cannot be checked offline", ""
    rdir = render_copy(build, gsap)
    script = build / "orchestrator" / "smoke.mjs"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(SMOKE, encoding="utf-8")
    out = build / "orchestrator" / "smoke.raw.json"
    p = subprocess.run(["node", str(script), str(rdir), str(out)], capture_output=True, text=True, timeout=300)
    log = p.stdout + p.stderr
    if p.returncode != 0 or not out.exists():
        return False, f"Chromium probe failed (exit {p.returncode})", log
    r = json.loads(out.read_text(encoding="utf-8"))
    expect = json.loads((build / "words.json").read_text(encoding="utf-8"))["duration"] if (build / "words.json").exists() else None
    problems = []
    if r["errors"]:
        problems.append(f"{len(r['errors'])} page error(s): {r['errors'][0][:200]}")
    if not r["timeline"]:
        problems.append("no main timeline (window.__timelines.main)")
    elif expect is not None and abs(r["duration"] - float(expect)) > 0.05:
        problems.append(f"timeline {r['duration']} s, words.json {expect} s")
    res = {"schema": "nfp.orchestrator.smoke/1", "ok": not problems, "problems": problems, "timeline_seconds": r["duration"],
           "expected_seconds": expect, "page_errors": r["errors"], "director_warnings": r["warnings"],
           "refused_requests": r["refused_requests"], "fonts_loaded": r["fonts"]}
    (build / "smoke.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    detail = "; ".join(problems) if problems else (f"timeline {r['duration']} s, 0 page errors, {len(r['warnings'])} Director warning(s), "
                                                   f"{len(r['refused_requests'])} outside request(s) refused")
    return not problems, detail, log


def ffprobe(mp4):
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(mp4)],
                                   capture_output=True, text=True, check=True).stdout)
    v = next((s for s in pr["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), {})
    return {"width": v.get("width"), "height": v.get("height"), "fps": v.get("avg_frame_rate"), "video_codec": v.get("codec_name"),
            "audio_codec": a.get("codec_name"), "seconds": round(float(pr["format"]["duration"]), 3), "bytes": int(pr["format"]["size"])}


def render(pl, build, gsap, browser=None):
    build = Path(build)
    if not gsap or not Path(gsap).is_file():
        return False, "no local GSAP copy (--gsap): rendering offline needs it", ""
    rdir = render_copy(build, gsap)
    env = dict(os.environ, npm_config_offline="true", HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    browser = browser or os.environ.get("HYPERFRAMES_BROWSER_PATH") or (BROWSER if Path(BROWSER).exists() else None)
    if browser:
        env["HYPERFRAMES_BROWSER_PATH"] = browser
    npx = ["npx", "--yes", f"hyperframes@{HF_VERSION}"]
    lint = subprocess.run(npx + ["lint"], cwd=rdir, env=env, capture_output=True, text=True, timeout=600)
    out = build / "story.mp4"
    if out.exists():
        out.unlink()
    r = subprocess.run(npx + ["render", "--output", str(out), "--fps", "30", "--quality", "standard"], cwd=rdir, env=env,
                       capture_output=True, text=True, timeout=7200)
    log = "== lint\n" + lint.stdout + lint.stderr + "\n== render\n" + r.stdout + r.stderr
    if r.returncode != 0 or not out.exists():
        return False, f"HyperFrames render failed (exit {r.returncode}): {(r.stdout + r.stderr).strip()[-200:]}", log
    probe = ffprobe(out)
    lint_tail = " | ".join((lint.stdout + lint.stderr).strip().splitlines()[-2:])[:300]
    res = {"schema": "nfp.orchestrator.render/1", "hyperframes": HF_VERSION, "offline": True, "lint_exit": lint.returncode,
           "lint": lint_tail, "mp4": str(out), "ffprobe": probe}
    (build / "render.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, (f"{probe['width']}x{probe['height']} {probe['fps']} {probe['video_codec']} + {probe['audio_codec']}, {probe['seconds']} s, "
                  f"{probe['bytes'] // 1024} KB (lint exit {lint.returncode})"), log
