#!/usr/bin/env python3
"""G1 - the graphic document (nfp.graphics/1): schema, kinds and displays, text fields, data sources (draft / final),
data shapes, style presets, safe area / subtitle band / vignette, overlay clashes, enter / exit animation. Synthetic data,
standard library only.
  python3 nfp/graphics/tests/test_graphics_g1.py
"""
import copy
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
NFP = HERE.parent.parent
sys.path.insert(0, str(NFP))
import graphics as G                     # noqa: E402
from graphics import safearea as SA      # noqa: E402

RESULTS = []


def check(ok, msg):
    RESULTS.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


SRC = [{"id": "s1", "title": "Statistical Yearbook", "publisher": "Statistical Centre", "url": "https://example.org/y", "date": "2024-05-01", "verified": True},
       {"id": "s2", "title": "Field notes", "publisher": "NFP", "verified": False}]


def doc(kind_, **kw):
    kind = kind_
    d = {"schema": "nfp.graphics/1", "id": f"g-{kind}", "mode": "final", "lang": "fa", "kind": kind}
    d.update({"title": {"content": {"title": "فصل اول: بندر", "subtitle": "۱۳۳۲"}},
              "lower-third": {"content": {"title": "مریم احمدی", "subtitle": "Historian, University of Tehran"}},
              "info-card": {"content": {"title": "بندر", "body": "بندر قدیمی در جنوب.\nامروز موزه است."}},
              "quote": {"content": {"body": "دریا همه چیز را به یاد دارد.", "attribution": "یک ماهیگیر", "source": "s1"}, "sources": SRC[:1]},
              "callout": {"content": {"body": "اسکلهٔ قدیمی"}, "place": {"at": [800, 400]}},
              "comparison": {"data": {"unit": "%", "source": "s1", "items": [{"label": "۱۹۹۰", "value": 31.5}, {"label": "۲۰۲۰", "value": 54}]},
                             "sources": SRC[:1]},
              "bar": {"data": {"source": "s1", "items": [{"label": "A", "value": 3}, {"label": "B", "value": -1.5}]}, "sources": SRC[:1]},
              "column": {"data": {"source": "s1", "items": [{"label": "A", "value": 3}]}, "sources": SRC[:1]},
              "line": {"data": {"source": "s1", "series": [{"label": "شمال", "points": [{"x": "1990", "value": 1}, {"x": "2000", "value": 2}]},
                                                          {"label": "جنوب", "points": [{"x": "1990", "value": 3}, {"x": "2000", "value": 2.5}]}]},
                       "sources": SRC[:1]},
              "counter": {"content": {"title": "کشتی در سال"}, "data": {"value": 1250, "source": "s1"}, "sources": SRC[:1]}}[kind])
    d.update(kw)
    return d


def codes(r, level=None):
    return [i["code"] for i in r["issues"] if level is None or i["level"] == level]


def main():
    print("== A every kind: a valid document, in every display it allows")
    for k in G.KINDS:
        for disp in G.DISPLAYS[k]:
            r = G.validate(doc(k), disp, clip_frames=90)
            ok = r["status"] == "OK" and r["graphic"] and r["graphic"]["display"] == disp and r["graphic"]["schema"] == G.SPEC_SCHEMA
            check(ok, f"{k} / {disp}: {r['status']} {codes(r)}")
    r = G.validate(doc("title"))
    check(r["status"] == "OK" and r["graphic"] is None, "without a display the document is checked but not resolved (the track decides it)")
    r1, r2 = G.validate(doc("line"), "overlay", 120), G.validate(doc("line"), "overlay", 120)
    check(r1 == r2 and json.loads(json.dumps(r1)) == r1, "deterministic and plain JSON")

    print("\n== B display comes from the track: overlay-only kinds")
    for k in ("lower-third", "callout"):
        r = G.validate(doc(k), "fullframe")
        check("display" in codes(r, "error") and r["graphic"] is None, f"{k} on a visual (full-frame) track: error")
    try:
        G.validate(doc("title"), "side")
        check(False, "an unknown display is refused")
    except ValueError:
        check(True, "an unknown display is refused (a caller error)")

    print("\n== C schema and text")
    cases = [("unknown key", dict(colour="red"), "schema"), ("schema", dict(schema="nfp.graphics/2"), "schema"),
             ("id", dict(id="-bad id"), "schema"), ("mode", dict(mode="publish"), "schema"), ("no lang", dict(lang=None), "schema"),
             ("kind", dict(kind="pie"), "schema")]
    for name, kw, code in cases:
        d = doc("title", **kw)
        if kw.get("lang", 1) is None:
            d.pop("lang")
        r = G.validate(d, "fullframe")
        check(r["status"] == "FAIL" and code in codes(r, "error"), f"{name}: FAIL ({code})")
    r = G.validate(doc("title", content={"subtitle": "x"}), "fullframe")
    check(any("needs content 'title'" in i["message"] for i in r["issues"]), "a missing required text is an error")
    r = G.validate(doc("title", content={"title": "x", "body": "y"}), "fullframe")
    check(any("has no content 'body'" in i["message"] for i in r["issues"]), "a text a kind does not take is an error")
    r = G.validate(doc("title", content={"title": "  "}), "fullframe")
    check("schema" in codes(r, "error"), "empty text is an error")
    r = G.validate(doc("title", content={"title": "a\nb"}), "fullframe")
    check(any("control" in i["message"] for i in r["issues"]), "a line break in a title is an error ...")
    check(G.validate(doc("info-card"), "fullframe")["status"] == "OK", "... in a body it is allowed")
    r = G.validate(doc("title", content={"title": "x" * 81}), "fullframe")
    check("text_length" in codes(r, "error"), "text longer than its limit (title 80) is an error")

    print("\n== D sources: final vs draft")
    d = doc("bar")
    d["data"].pop("source")
    r = G.validate(d, "fullframe")
    check(codes(r, "error").count("unsourced") == 2, "final: every unsourced number is an error (2 items)")
    d["mode"] = "draft"
    r = G.validate(d, "fullframe")
    check(r["status"] == "WARN" and codes(r, "warning").count("unsourced") == 2 and r["graphic"]["draft_badge"],
          "draft: a warning each, and the graphic is marked draft (draft_badge)")
    d = doc("bar")
    d["data"]["items"][1]["source"] = "s2"
    d["sources"] = SRC
    r = G.validate(d, "fullframe")
    check("unverified_source" in codes(r, "error"), "final: a number from an unverified source is an error")
    d["mode"] = "draft"
    r = G.validate(d, "fullframe")
    check("unverified_source" in codes(r, "warning") and r["graphic"]["draft_badge"], "draft: a warning, marked draft")
    d["data"]["items"][1]["source"] = "s9"
    r = G.validate(d, "fullframe")
    check("unknown_source" in codes(r, "error"), "an unknown source id is an error even in draft")
    d = doc("bar")
    d["data"]["items"][0]["source"] = "s2"
    d["sources"] = SRC
    d["mode"] = "draft"
    r = G.validate(d, "fullframe")
    g = r["graphic"]
    check(g["data"]["items"][0]["source"] == "s2" and g["data"]["items"][1]["source"] == "s1", "an item's own source overrides data.source")
    d = doc("title", sources=SRC[:1])
    r = G.validate(d, "fullframe")
    check(r["status"] == "WARN" and "unused_source" in codes(r, "warning"), "an unused source is a warning")
    for bad, code in ((dict(url="ftp://x"), "url"), (dict(date="5/1/2024"), "date"), (dict(verified="yes"), "verified"), (dict(publisher=""), "publisher")):
        s = dict(SRC[0], **bad)
        r = G.validate(doc("quote", sources=[s]), "fullframe")
        check(any(code in i["message"] for i in r["issues"] if i["level"] == "error"), f"a source with a bad {code}: error")
    r = G.validate(doc("quote", content={"body": "x", "attribution": "y"}), "fullframe")
    check("unsourced" in codes(r, "error"), "a quote always needs a source")
    r = G.validate(doc("info-card", content={"body": "در سال ۱۳۳۲ بسته شد."}), "fullframe")
    check("unsourced" in codes(r, "error"), "an info-card whose text has a number (Persian digits) needs a source in final")
    r = G.validate(doc("callout", content={"body": "about 40 ships"}), "overlay")
    check("unsourced" in codes(r, "error"), "... a callout with Latin digits too")
    check(G.validate(doc("info-card"), "fullframe")["status"] == "OK", "an info-card without numbers needs none")
    check(G.validate(doc("title"), "fullframe")["status"] == "OK", "a title with a year needs none (a heading, not a statistic)")

    print("\n== E data shapes")
    for kind, n, ok in (("comparison", 1, False), ("comparison", 5, False), ("bar", 12, True), ("bar", 13, False), ("column", 0, False)):
        d = doc(kind)
        d["data"]["items"] = [{"label": f"L{i}", "value": i} for i in range(n)]
        r = G.validate(d, "fullframe")
        check((r["status"] == "OK") == ok, f"{kind} with {n} items: {'OK' if ok else 'error'}")
    for bad in (float("nan"), float("inf"), True, "3", None):
        d = doc("bar")
        d["data"]["items"][0]["value"] = bad
        check("data" in codes(G.validate(d, "fullframe"), "error"), f"value {bad!r}: error")
    d = doc("bar")
    d["data"]["items"][1]["label"] = "A"
    check(any("duplicate label" in i["message"] for i in G.validate(d, "fullframe")["issues"]), "duplicate labels: error")
    d = doc("line")
    d["data"]["series"][1]["points"][1]["x"] = "2010"
    check(any("same x labels" in i["message"] for i in G.validate(d, "fullframe")["issues"]), "line series with different x: error")
    d = doc("line")
    d["data"]["series"][1].pop("label")
    check(any("needs a label" in i["message"] for i in G.validate(d, "fullframe")["issues"]), "several series without labels: error")
    d = doc("line")
    d["data"]["series"] = d["data"]["series"][:1]
    d["data"]["series"][0]["points"] = d["data"]["series"][0]["points"][:1]
    check(any("2..60 points" in i["message"] for i in G.validate(d, "fullframe")["issues"]), "a series of one point: error")
    d = doc("counter")
    d["data"]["items"] = []
    check(any("has no 'items'" in i["message"] for i in G.validate(d, "fullframe")["issues"]), "data keys follow the kind (counter has no items)")
    check(any("has no data" in i["message"] for i in G.validate(doc("title", data={"value": 1}), "fullframe")["issues"]), "a text kind with data: error")
    g = G.validate(doc("comparison"), "fullframe")["graphic"]
    check(g["data"]["format"] == {"digits": "fa", "decimals": 0} and g["data"]["unit"] == "%", "digits 'auto' follow lang (fa)")
    g = G.validate(doc("comparison", lang="en"), "fullframe")["graphic"]
    check(g["data"]["format"]["digits"] == "en", "... and en for an English graphic")
    d = doc("comparison")
    d["data"]["format"] = {"digits": "en", "decimals": 4}
    check("schema" in codes(G.validate(d, "fullframe"), "error"), "decimals beyond 3: error")
    g = G.validate(doc("counter"), "fullframe")["graphic"]
    check(g["data"]["value"] == 1250 and g["data"]["from"] == 0, "a counter counts from 0 by default")

    print("\n== F style presets")
    for p in G.PRESETS:
        g = G.validate(doc("title", style={"preset": p}), "fullframe")["graphic"]
        check(g["style"]["preset"] == p and all(re.fullmatch(r"#[0-9a-f]{6}", g["style"]["colors"][k]) for k in ("text", "accent", "panel")),
              f"preset {p}")
    g = G.validate(doc("title", style={"accent": "#ABCDEF", "scale": 1.25}), "fullframe")["graphic"]
    check(g["style"]["colors"]["accent"] == "#abcdef" and g["style"]["type"]["title"]["size"] == 110.0, "override accent, scale 1.25 (title 88 -> 110 px)")
    gf, go = G.validate(doc("title"), "fullframe")["graphic"], G.validate(doc("title"), "overlay")["graphic"]
    check(gf["style"]["type"]["title"]["size"] > go["style"]["type"]["title"]["size"], "full-frame type is larger than overlay type")
    check({t["weight"] for g in (gf, go) for t in g["style"]["type"].values()} <= {400, 700}, "only weights 400 / 700 (the film's local faces)")
    check(gf["style"]["font"].startswith("Vazirmatn") and G.validate(doc("title", lang="en"), "fullframe")["graphic"]["style"]["font"].startswith("Inter"),
          "font order follows lang (fa: Vazirmatn first, en: Inter first)")
    for bad in ({"preset": "neon"}, {"accent": "red"}, {"scale": 2}, {"panel_opacity": 1.5}, {"font": "Arial"}):
        check(G.validate(doc("title", style=bad), "fullframe")["status"] == "FAIL", f"style {bad}: error")

    print("\n== G place: safe area, subtitle band, vignette")
    check("schema" in codes(G.validate(doc("title", place={"anchor": "top"}), "fullframe"), "error"), "a full-frame graphic takes no place")
    g = G.validate(doc("lower-third"), "overlay")["graphic"]
    check(g["place"]["anchor"] == "bottom-right", "lower third in Persian: bottom-right by default (reading starts on the right)")
    g = G.validate(doc("lower-third", lang="en"), "overlay")["graphic"]
    check(g["place"]["anchor"] == "bottom-left", "... bottom-left in English")
    r = G.validate(doc("lower-third", place={"rect": [200, 700, 700, 160]}), "overlay")
    check("subtitle_band" in codes(r, "error"), "a box reaching into the subtitle band (y >= 830): error")
    r = G.validate(doc("lower-third", place={"rect": [40, 600, 700, 160]}), "overlay")
    check("outside_safe_area" in codes(r, "error"), "a box left of title-safe (x < 96): error")
    r = G.validate(doc("lower-third", place={"rect": [96, 54, 500, 120]}), "overlay")
    check(r["status"] == "WARN" and "vignette" in codes(r, "warning"), "a box in the top-left corner: allowed, vignette warning")
    r = G.validate(doc("lower-third", place={"rect": [200, 600, 700, 160]}), "overlay")
    check(r["status"] == "OK" and r["graphic"]["place"]["rect"] == [200.0, 600.0, 700.0, 160.0], "a box inside the safe area: OK")
    r = G.validate(doc("lower-third", place={"rect": [200, 600, 700, 160], "anchor": "top"}), "overlay")
    check("schema" in codes(r, "error"), "anchor and rect together: error")
    r = G.validate(doc("lower-third", place={"anchor": "middle"}), "overlay")
    check("schema" in codes(r, "error"), "an unknown anchor: error")
    check(any("needs place.at" in i["message"] for i in G.validate(doc("callout", place={}), "overlay")["issues"]), "a callout without at: error")
    check("outside_safe_area" in codes(G.validate(doc("callout", place={"at": [800, 900]}), "overlay"), "error"), "a callout pointing into the band: error")
    check(any("only for a callout" in i["message"] for i in G.validate(doc("lower-third", place={"at": [1, 1]}), "overlay")["issues"]),
          "at on another kind: error")

    print("\n== H safe area constants and the measured vignette")
    check(SA.ALLOWED == (96, 54, 1728, 776) and SA.ALLOWED[1] + SA.ALLOWED[3] == SA.BAND[1] and SA.RESERVED[0]["rect"] == [0, 830, 1920, 250],
          "allowed area x 96..1824, y 54..830 ends where the subtitle band starts")
    # G0 real HyperFrames render (scratchpad/g0-work/result.json): an opaque test colour under the film's post layers (V2)
    # vs above them (V3, unchanged 254 / 253): light lost at the frame corner, the centre and inside a lower third
    measured = {(70, 70): 1 - 146.3 / 254, (960, 520): 1 - 247.2 / 254, (550, 695): 1 - 245.6 / 253}
    worst = max(abs(SA.vignette_at(*p) - v) for p, v in measured.items())
    check(worst < 0.02, f"vignette_at matches the G0 render (corner {SA.vignette_at(70, 70):.3f} vs {measured[(70, 70)]:.3f}; "
                        f"largest difference {worst:.3f})")
    clash = SA.check_overlays([("a", 0, 60, [100, 100, 300, 100]), ("b", 30, 90, [350, 150, 200, 100]),
                               ("c", 60, 120, [100, 100, 300, 100]), ("d", 0, 60, [400, 0, 100, 100])])
    check(clash == [("a", "b", 30, 59), ("b", "c", 60, 89)], f"overlays at the same time must not cover each other; touching / after is fine {clash}")

    print("\n== I animation")
    g = G.validate(doc("title"), "fullframe", 60)["graphic"]
    check(g["animation"] == {"in": {"type": "fade", "frames": 9, "direction": None}, "out": {"type": "fade", "frames": 9, "direction": None}},
          "default: fade in / out, 9 frames each")
    g = G.validate(doc("lower-third", animation={"in": {"type": "slide", "frames": 12}, "out": {"type": "wipe", "frames": 8}}), "overlay")["graphic"]
    check(g["animation"]["in"]["direction"] == "left" and g["animation"]["out"]["direction"] == "left", "slide / wipe direction follows Persian reading by default")
    r = G.validate(doc("title", animation={"in": {"type": "fade", "frames": 30}, "out": {"type": "fade", "frames": 30}}), "fullframe", 60)
    check("animation_too_long" in codes(r, "error"), "enter + exit that fill the whole clip: error")
    check(G.validate(doc("title", animation={"in": {"type": "none"}}), "fullframe", 10)["graphic"]["animation"]["in"]["frames"] == 0, "type none: 0 frames")
    for bad in ({"in": {"type": "spin"}}, {"in": {"type": "fade", "frames": 0}}, {"in": {"type": "fade", "direction": "left"}},
                {"in": {"type": "slide", "direction": "diagonal"}}, {"in": {"type": "fade", "frames": 91}}, {"middle": {}}):
        check(G.validate(doc("title", animation=bad), "fullframe")["status"] == "FAIL", f"animation {bad}: error")

    print("\n== J independence")
    src = "".join(p.read_text(encoding="utf-8") for p in (NFP / "graphics").glob("*.py"))
    imports = set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", src, re.M))
    check(imports <= {"math", "re", "unicodedata", "decimal", "xml.sax.saxutils", "json", "pathlib", ".", ".model", ".safearea", ".styles", ".text", ".textlayout", ".svg", ".render", ".animate", ".filmclip"}, f"standard library only, no process / network / other engine {sorted(imports)}")
    return finish()


def finish():
    n = len(RESULTS)
    f = n - sum(RESULTS)
    print(f"\n{n} checks: {n - f} passed, {f} failed. " + ("ALL GRAPHICS G1 TESTS PASSED" if not f else "GRAPHICS G1 TESTS FAILED"))
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
