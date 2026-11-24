#!/usr/bin/env python3
"""S2 - SRT / VTT / ASS from subtitles.json (engine/subtitle_export.py), offline; uses the local ffmpeg / ffprobe only.

  python3 nfp/film/tests/film_subtitle_export_check.py --fonts <dir with woff2> --work <dir outside the repository>

  L legacy   compose output byte-identical to the committed Film (HEAD); compose imports neither subtitle module
  F formats  for en + fa and sentence / karaoke / word: parse every file back -> same cues, same lines (ZWNJ,
             punctuation), SRT / VTT times = subtitles.json to the millisecond, ASS to the centisecond (its format),
             karaoke word times (VTT timestamps, ASS \\t offsets) = the word times to the millisecond
  X ffmpeg   ffprobe reads all three formats with the same cue count and start times; libass draws the exported
             Persian lines exactly like its own right-to-left reference (pixel-identical) and English unchanged
  R run      `run.py subs` writes the three files from subtitles.json (the single source), leaves story.srt /
             timing.json / words.json / the page unchanged, and writes none after a QC failure
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FILM = HERE.parent
ROOT = FILM.parent.parent
sys.path[:0] = [str(FILM / "engine"), str(HERE)]
import project as P                       # noqa: E402
import subtitles as SB                    # noqa: E402
import subtitle_export as SX              # noqa: E402
from film_equivalence_check import synth_timing          # noqa: E402
from film_subtitle_check import compose_outputs, mk_timing, proj, ENV   # noqa: E402

RESULTS = []
RUN = FILM / "engine" / "run.py"
ZWNJ, RLE, PDF = "\u200c", "\u202b", "\u202c"


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def t2ms(s):
    h, m, rest = s.replace(",", ".").split(":")
    sec, frac = rest.split(".")
    return ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(frac.ljust(3, "0")[:3]) if len(frac) == 3 else \
        ((int(h) * 60 + int(m)) * 60 + int(sec)) * 1000 + int(frac) * 10


def unwrap(line, rtl):
    if rtl:
        assert line.startswith(RLE) and line.endswith(PDF), line
        return line[1:-1]
    assert RLE not in line and PDF not in line, line
    return line


def parse_srt(text):
    out = []
    for block in text.lstrip("\ufeff").strip("\n").split("\n\n"):
        rows = block.split("\n")
        a, b = rows[1].split(" --> ")
        out.append((int(rows[0]), t2ms(a), t2ms(b), rows[2:]))
    return out


def parse_vtt(text):
    assert text.startswith("WEBVTT\n\n")
    out = []
    for block in text[8:].strip("\n").split("\n\n"):
        rows = block.split("\n")
        a, b = rows[1].split(" --> ")
        out.append((rows[0], t2ms(a), t2ms(b), rows[2:]))
    return out


def vtt_plain(line):
    stamps = [t2ms(x) for x in re.findall(r"<(\d\d:\d\d:\d\d\.\d\d\d)>", line)]
    s = re.sub(r"<[^>]*>", "", line).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return s, stamps


def parse_ass(text):
    head, events = text.split("[Events]")
    out = []
    for ln in events.split("\n"):
        if ln.startswith("Dialogue: "):
            f = ln[10:].split(",", 9)
            out.append((t2ms(f[1]), t2ms(f[2]), f[9]))
    return head, out


def ass_plain(text):
    tags = re.findall(r"\{([^}]*)\}", text)
    return re.sub(r"\{[^}]*\}", "", text).split("\\N"), tags


def export_dir(doc, work, name):
    d = work / "F" / name
    d.mkdir(parents=True, exist_ok=True)
    src = d / "subtitles.json"
    src.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return SX.export(src, d / "out")


def check_formats(doc, files, label):
    rtl = doc["dir"] == "rtl"
    cues = doc["cues"]
    jl = [c["lines"] for c in cues]
    raw = {f: Path(p).read_bytes() for f, p in files.items()}
    txt = {f: b.decode("utf-8-sig") for f, b in raw.items()}
    ok_enc = raw["srt"].startswith(b"\xef\xbb\xbf") and raw["ass"].startswith(b"\xef\xbb\xbf") and \
        not raw["vtt"].startswith(b"\xef\xbb\xbf") and all(b"\r" not in b for b in raw.values())
    # SRT
    S = parse_srt(txt["srt"])
    srt_ok = [n for n, *_ in S] == list(range(1, len(cues) + 1)) and \
        [(a, b) for _, a, b, _ in S] == [(SX.ms(c["start"]), SX.ms(c["end"])) for c in cues] and \
        [[unwrap(x, rtl) for x in rows] for *_, rows in S] == jl
    # VTT
    V = parse_vtt(txt["vtt"])
    vlines, vstamps = [], []
    for *_, rows in V:
        pl = [vtt_plain(unwrap(x, rtl)) for x in rows]
        vlines.append([p for p, _ in pl])
        vstamps.append([s for _, st in pl for s in st])
    want_st = [[SX.ms(w["start"]) for w in c.get("words", []) if SX.ms(c["start"]) < SX.ms(w["start"]) < SX.ms(c["end"])]
               if doc["mode"] == "karaoke" else [] for c in cues]
    vtt_ok = [(a, b) for _, a, b, _ in V] == [(SX.ms(c["start"]), SX.ms(c["end"])) for c in cues] and vlines == jl and vstamps == want_st
    # ASS
    head, A = parse_ass(txt["ass"])
    font = {"en": "Inter", "fa": "Vazirmatn"}[doc["lang"]]
    head_ok = "PlayResX: 1920" in head and "PlayResY: 1080" in head and "WrapStyle: 2" in head and f"Style: Default,{font},56," in head
    alines, tag_ok = [], True
    for (a, b, text), c in zip(A, cues):
        lines = [unwrap(x, rtl) for x in text.split("\\N")]
        plain = [ass_plain(x)[0][0] for x in lines]
        alines.append(plain)
        if doc["mode"] == "karaoke":
            tags = [t for x in lines for t in ass_plain(x)[1]]
            offs = [tuple(int(v) for v in re.findall(r"\\t\((\d+),\1,", t)) for t in tags]
            base = a                                       # event start (centiseconds, as ms)
            tag_ok &= [(o[0] + base, o[1] + base) for o in offs] == [(SX.ms(w["start"]), SX.ms(w["end"])) for w in c["words"]]
    ass_ok = head_ok and len(A) == len(cues) and alines == jl and tag_ok and \
        all(0 <= SX.ms(c["start"]) - a <= 9 and 0 <= SX.ms(c["end"]) - b <= 9 for (a, b, _), c in zip(A, cues)) and \
        all(A[i + 1][0] >= A[i][1] for i in range(len(A) - 1))
    zw = sum(ln.count(ZWNJ) for c in cues for ln in c["lines"])
    zw_ok = all(t.count(ZWNJ) == zw for t in txt.values())
    check(ok_enc, f"{label}: UTF-8 (SRT / ASS with BOM, VTT without), LF line ends")
    check(srt_ok, f"{label}: SRT - {len(S)} cues, times = subtitles.json to the ms, lines identical")
    check(vtt_ok, f"{label}: VTT - times to the ms, lines identical"
                  + (f", {sum(map(len, vstamps))} karaoke timestamps = word starts" if doc["mode"] == "karaoke" else ""))
    check(ass_ok, f"{label}: ASS - 1920x1080, {font}, times = centiseconds rounded down (<= 9 ms), no overlap, lines identical"
                  + (", word highlight offsets = word times to the ms" if doc["mode"] == "karaoke" else ""))
    check(zw_ok and (not rtl or all(RLE in t for t in txt.values())),
          f"{label}: {zw} nim-fasele kept in every file" + ("; every Persian line wrapped RLE...PDF" if rtl else "; no direction marks"))
    return txt


def ffprobe_starts(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return [round(float(x.strip(",")) * 1000) for x in r.stdout.split()] if r.returncode == 0 else None


def render(sub_filter, work, name):
    """One 1920x1080 frame at t=1 s with libass, as raw RGB bytes."""
    out = work / "X" / f"{name}.rgb"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x303040:s=1920x1080:d=2",
                        "-vf", sub_filter, "-ss", "1", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-y", str(out)],
                       capture_output=True, text=True, cwd=work / "X")
    if r.returncode != 0:
        raise SystemExit(r.stderr)
    return out.read_bytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work).resolve()
    if ROOT in work.parents or work == ROOT:
        sys.exit("--work must be outside the repository")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    head_rev = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(f"== L legacy (byte-identical to the committed Film {head_rev[:7]})")
    head = work / "head"
    head.mkdir()
    arch = subprocess.run(["git", "-C", str(ROOT), "archive", head_rev], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(head)], input=arch.stdout, check=True)
    for fx in ("neutral-en", "cast-en", "cast-fa"):
        f = FILM / "tests/fixtures" / fx
        old, _ = compose_outputs(head, f, work / "L" / fx / "old", a.fonts)
        new, imp = compose_outputs(ROOT, f, work / "L" / fx / "new", a.fonts)
        check(old == new and len(new) >= 3 and not imp, f"{fx}: {', '.join(sorted(new))} byte-identical to {head_rev[:7]}")
    src = (FILM / "engine/compose.py").read_text(encoding="utf-8")
    guarded = re.findall(r'    if "subtitles" in project:[^\n]*\n        import subtitle_layer as SL\n', src)
    check("subtitle_export" not in src and src.count("import subtitle") == 1 and len(guarded) == 1,
          "compose.py never uses the export module; the S3 display layer is imported only for projects with a subtitles block")

    print("\n== F formats")
    docs = {}
    for fx in ("neutral-en", "cast-fa"):
        pr = P.load(FILM / "tests/fixtures" / fx)
        ch = pr["chapters"][0]
        tm = synth_timing(ch)
        for mode in SB.MODES:
            pr["subtitles"] = {"mode": mode}
            doc = SB.build(pr, ch, tm)
            files = export_dir(doc, work, f"{fx}-{mode}")
            docs[(fx, mode)] = (doc, files)
            check_formats(doc, files, f"{fx} {mode}")
    long_fa = ("کتاب‌های قدیمی کتابخانه را دوباره می‌خوانیم، چون داستان‌هایشان هنوز برای بچه‌ها و بزرگ‌ترها "
               "خواندنی است و هیچ‌کس نمی‌خواهد آن‌ها فراموش شوند.")
    doc = SB.build(proj("fa", mode="karaoke"), {}, mk_timing([("s1", long_fa), ("s2", "پیام Netflix امروز رسید؛ ۲۹۴ نفر آمدند!")]))
    check_formats(doc, export_dir(doc, work, "fa-long"), "fa two-line cues + English word + Persian digits")
    doc = SB.build(proj("en", mode="karaoke"), {}, mk_timing([("s1", 'He said "A < B & C > D" {not a tag} \\ ok.')]))
    files = export_dir(doc, work, "escape")
    t = {f: Path(p).read_text(encoding="utf-8-sig") for f, p in files.items()}
    check("&lt;" in t["vtt"] and "&amp;" in t["vtt"] and "&gt;" in t["vtt"] and "A < B & C > D" in t["srt"]
          and "(not" in t["ass"] and "{not" not in t["ass"] and "\u29f5" in t["ass"],
          "special characters: VTT escapes & < >, SRT keeps them, ASS turns { } \\ into harmless look-alikes")
    a1 = {f: sha(p) for f, p in export_dir(docs[("cast-fa", "karaoke")][0], work, "again").items()}
    a0 = {f: sha(p) for f, p in docs[("cast-fa", "karaoke")][1].items()}
    check(a0 == a1, "deterministic: the same subtitles.json gives the same three files")
    bad = dict(docs[("neutral-en", "sentence")][0])
    bad["qc"] = dict(bad["qc"], status="FAIL")
    try:
        SX.export(bad, work / "F" / "bad")
        ok = False
    except SX.ExportError:
        ok = not (work / "F" / "bad").exists()
    check(ok, "a subtitles.json that failed QC is not exported")

    print("\n== X ffmpeg / libass (local tools only)")
    for (fx, mode), (doc, files) in sorted(docs.items()):
        if mode == "word" and fx == "cast-fa":
            continue
        want = [SX.ms(c["start"]) for c in doc["cues"]]
        got = {f: ffprobe_starts(p) for f, p in files.items()}
        ok = got["srt"] == want and got["vtt"] == want and got["ass"] is not None and len(got["ass"]) == len(want) and \
            all(0 <= y - x <= 9 for x, y in zip(got["ass"], want))
        check(ok, f"{fx} {mode}: ffprobe reads SRT / VTT / ASS - {len(want)} cues at the same start times")
    (work / "X").mkdir()
    fonts = work / "X" / "fonts"
    fonts.mkdir()
    for f in Path(a.fonts).glob("*.woff2"):
        shutil.copyfile(f, fonts / f.name)
    mixed = "پیام Netflix امروز رسید، و همه خوشحال شدند."
    doc = SB.build(proj("fa"), {}, mk_timing([("s1", mixed)], lead=0.5))
    files = export_dir(doc, work, "render-fa")
    shutil.copyfile(files["ass"], work / "X" / "fa.ass")
    shutil.copyfile(files["srt"], work / "X" / "fa.srt")
    ref = (work / "X" / "fa.ass").read_text(encoding="utf-8-sig").replace(RLE, "").replace(PDF, "")
    (work / "X" / "fa_ref.ass").write_text(ref.replace("160,160,62,1", "160,160,62,-1"), encoding="utf-8")
    (work / "X" / "fa_plain.ass").write_text(ref, encoding="utf-8")
    ours = render("ass=fa.ass:fontsdir=fonts", work, "ours")
    refimg = render("ass=fa_ref.ass:fontsdir=fonts", work, "ref")
    plain = render("ass=fa_plain.ass:fontsdir=fonts", work, "plain")
    bg = render("null", work, "bg")
    check(ours == refimg and ours != bg and plain != refimg,
          "libass: the exported Persian ASS line is pixel-identical to libass's own right-to-left layout "
          "(without the direction marks it would be drawn left-to-right)")
    (work / "X" / "fa_plain.srt").write_text((work / "X" / "fa.srt").read_text(encoding="utf-8-sig").replace(RLE, "").replace(PDF, ""), encoding="utf-8")
    st = ":force_style='Fontname=Vazirmatn,Fontsize=24'"
    s_ours = render("subtitles=fa.srt:fontsdir=fonts" + st, work, "srt_ours")
    s_ref = render("subtitles=fa_plain.srt:fontsdir=fonts:force_style='Fontname=Vazirmatn,Fontsize=24,Encoding=-1'", work, "srt_ref")
    s_plain = render("subtitles=fa_plain.srt:fontsdir=fonts" + st, work, "srt_plain")
    check(s_ours == s_ref and s_ours != bg and s_plain != s_ref,
          "libass: the exported Persian SRT is drawn right-to-left too (pixel-identical to the RTL reference)")
    doc = SB.build(proj("en"), {}, mk_timing([("s1", "The street wakes up slowly, as the evening light turns gold.")], lead=0.5))
    files = export_dir(doc, work, "render-en")
    shutil.copyfile(files["ass"], work / "X" / "en.ass")
    e = render("ass=en.ass:fontsdir=fonts", work, "en")
    check(e != bg and RLE not in Path(files["ass"]).read_text(encoding="utf-8-sig"), "libass: the English ASS draws, with no direction marks")
    for name, flt in (("fa_ours", "ass=fa.ass:fontsdir=fonts"), ("en_ours", "ass=en.ass:fontsdir=fonts")):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x303040:s=1920x1080:d=2",
                        "-vf", flt, "-ss", "1", "-frames:v", "1", "-y", str(work / "X" / f"{name}.png")], cwd=work / "X", check=True)
    print(f"   frames for a visual look: {work / 'X' / 'fa_ours.png'} {work / 'X' / 'en_ours.png'}")

    print("\n== R run.py subs")
    pdir = work / "projects" / "subs-fa"
    shutil.copytree(FILM / "tests/fixtures/cast-fa", pdir)
    pj = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    pj["subtitles"] = {"mode": "karaoke"}
    (pdir / "project.json").write_text(json.dumps(pj, ensure_ascii=False), encoding="utf-8")
    b = work / "L/cast-fa/new"
    (b / "timing.json").write_text(json.dumps(synth_timing(P.load(pdir)["chapters"][0]), ensure_ascii=False), encoding="utf-8")
    keep = ("timing.json", "words.json", "story.srt", "story/index.html", "cast_report.json")
    before = {f: sha(b / f) for f in keep}
    r = subprocess.run([sys.executable, "-B", str(RUN), "subs", "--project", str(pdir), "--build", str(b)],
                       capture_output=True, text=True, env=ENV)
    names = sorted(p.name for p in (b / "subtitles").glob("*")) if (b / "subtitles").exists() else []
    check(r.returncode == 0 and names == ["subtitles.fa.ass", "subtitles.fa.srt", "subtitles.fa.vtt"],
          f"run.py subs -> <build>/subtitles/{names}")
    check({f: sha(b / f) for f in keep} == before and (b / "story.srt").read_bytes() != (b / "subtitles/subtitles.fa.srt").read_bytes(),
          "story.srt, timing.json, words.json, the page and the cast report are unchanged; story.srt is a separate file")
    doc = json.loads((b / "subtitles.json").read_text(encoding="utf-8"))
    check_formats(doc, {f: b / "subtitles" / f"subtitles.fa.{f}" for f in SX.FORMATS}, "run.py output")
    doc["cues"][0]["lines"][0] = doc["cues"][0]["lines"][0].replace("خیابان", "کوچه")
    doc["cues"][0]["words"][0]["text"] = "کوچه"
    (b / "subtitles.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    SX.export(b / "subtitles.json", b / "subtitles")
    t = {f: (b / "subtitles" / f"subtitles.fa.{f}").read_text(encoding="utf-8-sig") for f in SX.FORMATS}
    check(all("کوچه" in x and "خیابان" not in x for x in t.values()), "single source: an edit in subtitles.json appears in all three files")
    T = json.loads((b / "timing.json").read_text(encoding="utf-8"))
    s2 = T["sentences"][1]
    for w in s2["words"]:
        w["abs_start"] -= 3.0
        w["abs_end"] -= 3.0
    (b / "timing.json").write_text(json.dumps(T, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, "-B", str(RUN), "subs", "--project", str(pdir), "--build", str(b)],
                       capture_output=True, text=True, env=ENV)
    check(r.returncode != 0 and "no SRT / VTT / ASS written" in r.stderr and not (b / "subtitles").exists(),
          "QC failure: clear error, no (stale) SRT / VTT / ASS left")
    srcx = (FILM / "engine/subtitle_export.py").read_text(encoding="utf-8")
    imports = sorted(set(re.findall(r"^(?:from|import) (\w+)", srcx, re.M)))
    check(set(imports) <= {"json", "shutil", "pathlib"}, f"subtitle_export.py: standard library only {imports}")

    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL SUBTITLE S2 TESTS PASSED" if not f else "SUBTITLE S2 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
