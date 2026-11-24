"""NFP Film - Subtitle Engine, stage S2: SRT, WebVTT and ASS files from ONE source, <build>/subtitles.json (S1).

  export(<build>/subtitles.json, <build>/subtitles) -> subtitles.<lang>.srt / .vtt / .ass

Nothing here times, splits or re-words anything: every cue, line and word time comes from subtitles.json as it is.
The old <build>/story.srt (written by compose.py) is a different file and is never touched.

  times     SRT / VTT keep the millisecond of subtitles.json exactly; ASS event times are centiseconds (the format's own
            resolution, rounded down: at most 9 ms early), karaoke word changes inside an ASS event are exact
            milliseconds again (\\t offsets from the rounded event start)
  text      the cue lines as they are (ZWNJ / nim-fasele, punctuation, digits). Persian lines are wrapped in RLE ... PDF
            (U+202B ... U+202C, invisible) so that players that lay subtitles out left-to-right by default (libass for
            SRT, ASS with Encoding 1, ...) still show them right-to-left; the visible text is unchanged
  karaoke   VTT: a <hh:mm:ss.mmm> timestamp before each word (WebVTT's own karaoke); ASS: each word dim until it is
            spoken, highlighted while it is spoken, white after (the Film page's colours); SRT has no word timing
            and shows the cue lines only
  ASS style 1920x1080 like the video, font Inter (en) / Vazirmatn (fa), 56 px bold, bottom-centre, margins as the page
"""
import json
import shutil
from pathlib import Path

RLE, PDF = "‫", "‬"
FORMATS = ("srt", "vtt", "ass")
FONT = {"en": "Inter", "fa": "Vazirmatn"}
WHITE, DIM, YELLOW, OUTLINE, SHADOW = "&H00FFFFFF", "&H61FFFFFF", "&H005AD6FF", "&H00000000", "&H80000000"   # &HAABBGGRR


class ExportError(ValueError):
    pass


def ms(t):
    return int(round(float(t) * 1000))


def srt_time(t):
    m = ms(t)
    return f"{m // 3600000:02d}:{m // 60000 % 60:02d}:{m // 1000 % 60:02d},{m % 1000:03d}"


def vtt_time(t):
    return srt_time(t).replace(",", ".")


def ass_cs(t):
    # centiseconds, rounded DOWN from the exact millisecond: monotonic, so back-to-back cues never overlap and no word of
    # a karaoke event starts before its (rounded) event start - the \t offsets inside it stay exact to the millisecond
    return ms(t) // 10


def ass_time(t):
    c = ass_cs(t)
    return f"{c // 360000}:{c // 6000 % 60:02d}:{c // 100 % 60:02d}.{c % 100:02d}"


def rtl(doc, line):
    return RLE + line + PDF if doc["dir"] == "rtl" else line


def load(src):
    doc = json.loads(Path(src).read_text(encoding="utf-8")) if not isinstance(src, dict) else src
    if doc.get("schema") != "nfp.film.subtitles/1":
        raise ExportError("not a subtitles.json (nfp.film.subtitles/1)")
    if doc["qc"]["status"] == "FAIL":
        raise ExportError("subtitles.json failed QC - fix the errors before exporting")
    return doc


def word_lines(cue):
    """The cue's words, line by line (line text = its words joined by single spaces, as subtitles.py builds it)."""
    words, out, k = cue.get("words") or [], [], 0
    for ln in cue["lines"]:
        n = len(ln.split(" "))
        out.append(words[k:k + n])
        k += n
    if k != len(words) or any(" ".join(w["text"] for w in grp) != ln for grp, ln in zip(out, cue["lines"])):
        raise ExportError(f"cue {cue['i']}: its words do not match its lines")
    return out


def to_srt(doc):
    blocks = [f"{n}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n" + "\n".join(rtl(doc, ln) for ln in c["lines"]) + "\n"
              for n, c in enumerate(doc["cues"], 1)]
    return "\n".join(blocks)


def vtt_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_vtt(doc):
    out = ["WEBVTT", ""]
    karaoke = doc["mode"] == "karaoke"
    for n, c in enumerate(doc["cues"], 1):
        if karaoke:
            lines = []
            for grp in word_lines(c):
                parts = []
                for w in grp:
                    t = vtt_escape(w["text"])
                    if ms(c["start"]) < ms(w["start"]) < ms(c["end"]):
                        t = f"<{vtt_time(w['start'])}>" + t       # WebVTT karaoke: the word becomes 'past' at its time
                    parts.append(t)
                lines.append(rtl(doc, " ".join(parts)))
        else:
            lines = [rtl(doc, vtt_escape(ln)) for ln in c["lines"]]
        out += [str(n), f"{vtt_time(c['start'])} --> {vtt_time(c['end'])}"] + lines + [""]
    return "\n".join(out)


def ass_escape(s):
    # ASS has no escape that every renderer honours: braces would start an override block and a backslash a tag
    return s.replace("\\", "⧵").replace("{", "(").replace("}", ")")


def to_ass(doc):
    lang = doc["lang"]
    font = FONT.get(lang, "Inter")
    style = lambda name, primary: (f"Style: {name},{font},56,{primary},{DIM},{OUTLINE},{SHADOW},-1,0,0,0,100,100,0,0,1,2,1,2,"
                                   f"160,160,62,1")
    head = ["[Script Info]", "; NFP Film subtitles (nfp.film.subtitles/1 -> ASS)", "ScriptType: v4.00+",
            "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709",
            f"Language: {lang}", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            style("Default", WHITE), "",
            "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ev = []
    karaoke = doc["mode"] == "karaoke"
    for c in doc["cues"]:
        if karaoke:
            base = ass_cs(c["start"]) * 10                         # \t offsets count from the (rounded) event start
            lines = []
            for grp in word_lines(c):
                parts = []
                for w in grp:
                    a = max(0, ms(w["start"]) - base)
                    b = max(a, ms(w["end"]) - base)
                    parts.append(f"{{\\1c{DIM}\\t({a},{a},\\1c{YELLOW})\\t({b},{b},\\1c{WHITE})}}" + ass_escape(w["text"]))
                lines.append(rtl(doc, " ".join(parts)))
            text = "\\N".join(lines)
        else:
            text = "\\N".join(rtl(doc, ass_escape(ln)) for ln in c["lines"])
        ev.append(f"Dialogue: 0,{ass_time(c['start'])},{ass_time(c['end'])},Default,,0,0,0,,{text}")
    return "\n".join(head + ev) + "\n"


WRITERS = {"srt": to_srt, "vtt": to_vtt, "ass": to_ass}


def export(src, out_dir):
    """Write all three formats from subtitles.json into out_dir; returns {format: path}. Only after all three are
    built in memory are the files written (into a temporary folder first, then moved into place)."""
    doc = load(src)
    texts = {f: WRITERS[f](doc) for f in FORMATS}
    out_dir = Path(out_dir)
    tmp = out_dir.parent / (out_dir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    paths = {}
    for f, t in texts.items():
        name = f"subtitles.{doc['lang']}.{f}"
        (tmp / name).write_text(t, encoding="utf-8-sig" if f in ("srt", "ass") else "utf-8", newline="\n")
        paths[f] = out_dir / name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tmp.rename(out_dir)
    return paths


def remove(out_dir):
    """Drop previous exports (used when a new subtitles.json fails QC, so no stale files stay next to it)."""
    if Path(out_dir).exists():
        shutil.rmtree(out_dir)
