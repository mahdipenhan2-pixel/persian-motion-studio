"""NFP Film - Subtitle Engine, stage S3: draw the cues of <build>/subtitles.json on the video.

Used by compose.py ONLY for projects with a "subtitles" block; every other project is composed exactly as before
(and removing the block brings the old subtitles back). Nothing here touches DATA.sentences (Director, C3 lip sync),
words.json, timing.json or story.srt.

How: in the page template (base.html, unchanged) the subtitle CSS and the subtitle script are each found between fixed
markers and replaced by this layer; the sentence spans are replaced by cue elements. Same look as before: the same
bottom band, font (Inter / Vazirmatn through the page font), size, weight, shadow, colours, fade and word highlight.

  sentence  each cue's lines in white, fading in / out like the old sentences
  karaoke   each cue's lines; the word being spoken is highlighted exactly like the old subtitles (dim -> yellow
            while spoken -> white), at the word times of subtitles.json
  word      one word at a time, on at its start and off at its end (no fade between back-to-back words)
  off       no subtitles and no band on the video
Lines never wrap (white-space: nowrap): what S1 laid out (max 2 lines) is what is shown.
"""
import html
import json
from pathlib import Path

import subtitles as SB

CSS_START, CSS_END = "  /* subtitles: bottom band", "</style>"
JS_START, JS_END = "  /* Subtitles: a sentence shows", "  // keep the master timeline"
FADE = 0.18                      # as compose.py's DATA.fade

CSS = """  /* subtitles (Subtitle Engine S3, from subtitles.json): bottom band, the old look; mode __MODE__ */
  #subs { pointer-events: none; }
  #band { position: absolute; left: 0; right: 0; bottom: 0; height: 250px;
          background: linear-gradient(to top, rgba(6,3,5,.88), rgba(6,3,5,0)); }
  .cue { position: absolute; left: 160px; right: 160px; bottom: 62px; text-align: center; opacity: 0;
         font-size: 56px; font-weight: 700; line-height: 1.32; color: #fff; text-shadow: 0 3px 10px rgba(0,0,0,.7); }
  .cue .ln { display: block; white-space: nowrap; }
  .w { display: inline; color: rgba(255,255,255,.62); background-color: rgba(255,214,90,0);
       padding: 0 .12em; margin: 0 -.12em; border-radius: .2em; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
__OFF__"""

JS = """  /* Subtitles (Subtitle Engine S3): the cues of subtitles.json; karaoke words highlighted at their spoken time */
  const SUBS = __SUBS_JSON__;
  const OFF = { color: "rgba(255,255,255,0.62)", backgroundColor: "rgba(255,214,90,0)" };
  const ON = { color: "rgba(30,18,10,1)", backgroundColor: "rgba(255,214,90,1)" };
  const DONE = { color: "rgba(255,255,255,1)", backgroundColor: "rgba(255,214,90,0)" };
  SUBS.cues.forEach((c, n) => {
    const el = document.getElementById("cue-" + c.i);
    if (SUBS.mode === "word") {
      tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.001, ease: "none", immediateRender: false }, c.start);
      tl.fromTo(el, { opacity: 1 }, { opacity: 0, duration: 0.001, ease: "none", immediateRender: false }, Math.max(c.start + 0.001, c.end - 0.001));
      return;
    }
    const prevEnd = n ? SUBS.cues[n - 1].end : 0;
    const fin = Math.min(SUBS.fade, Math.max(0.001, c.start - prevEnd));        // never visible together with the cue before
    const fout = Math.min(SUBS.fade, Math.max(0.001, (c.end - c.start) / 4));
    tl.fromTo(el, { opacity: 0 }, { opacity: 1, duration: fin, ease: "power2.out", immediateRender: false }, Math.max(0, c.start - fin));
    (c.words || []).forEach((w) => {
      const we = document.getElementById(w.id);
      const hold = Math.max(0.06, w.end - w.start);
      tl.fromTo(we, OFF, Object.assign({ duration: 0.05, ease: "none", immediateRender: false }, ON), w.start);
      tl.fromTo(we, ON, Object.assign({ duration: 0.12, ease: "none", immediateRender: false }, DONE), w.start + hold);
    });
    tl.fromTo(el, { opacity: 1 }, { opacity: 0, duration: fout, ease: "power1.in", immediateRender: false }, c.end - fout);
  });
"""


def load_checked(project, chapter, timing, build):
    """<build>/subtitles.json, refused if missing, failed QC, or not made from this timing + these settings."""
    p = Path(build) / "subtitles.json"
    if not p.is_file():
        raise SystemExit(f"ERROR: this project has a subtitles block but {p} is missing - run `run.py subs` before compose")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema") != SB.SCHEMA:
        raise SystemExit(f"ERROR: {p} is not a subtitles.json ({SB.SCHEMA})")
    if doc["qc"]["status"] == "FAIL":
        raise SystemExit(f"ERROR: {p} failed QC - fix it and run `run.py subs` again")
    fresh = json.loads(json.dumps(SB.build(project, chapter, timing), ensure_ascii=False))
    if fresh != doc:
        raise SystemExit(f"ERROR: {p} does not match the current timing / subtitle settings - run `run.py subs` again")
    return doc


def cues_html(doc):
    if doc["mode"] == "off":
        return ""
    out = []
    for c in doc["cues"]:
        if doc["mode"] == "karaoke":
            words, k, lines = c["words"], 0, []
            for ln in c["lines"]:
                n = len(ln.split(" "))
                lines.append(" ".join(f'<span class="w" id="cw-{c["i"]}-{j}">{html.escape(w["text"])}</span>'
                                      for j, w in enumerate(words[k:k + n], k)))
                k += n
            if k != len(words):
                raise SystemExit(f"ERROR: subtitles.json cue {c['i']}: its words do not match its lines")
        else:
            lines = [html.escape(ln) for ln in c["lines"]]
        out.append(f'<div class="cue" id="cue-{c["i"]}">' + "".join(f'<span class="ln">{x}</span>' for x in lines) + "</div>")
    return "\n    ".join(out)


def timeline_data(doc):
    cues = []
    for c in doc["cues"]:
        row = {"i": c["i"], "start": c["start"], "end": c["end"]}
        if doc["mode"] == "karaoke":
            row["words"] = [{"id": f"cw-{c['i']}-{j}", "start": w["start"], "end": w["end"]} for j, w in enumerate(c["words"])]
        cues.append(row)
    return {"mode": doc["mode"], "fade": FADE, "cues": [] if doc["mode"] == "off" else cues}


def _swap(page, start, end, new):
    if page.count(start) != 1 or page.count(end) < 1:
        raise SystemExit(f"base.html: subtitle marker {start.strip()!r} not found exactly once")
    a = page.index(start)
    b = page.index(end, a)
    return page[:a] + new + page[b:]


def patch_template(page, doc):
    """The base.html template with its subtitle CSS and script replaced by this layer (before placeholders are filled)."""
    css = CSS.replace("__MODE__", doc["mode"]).replace("__OFF__", "  #band { display: none; }\n" if doc["mode"] == "off" else "")
    js = JS.replace("__SUBS_JSON__", json.dumps(timeline_data(doc), ensure_ascii=False).replace("<", "\\u003c"))
    page = _swap(page, CSS_START, CSS_END, css)
    return _swap(page, JS_START, JS_END, js)
