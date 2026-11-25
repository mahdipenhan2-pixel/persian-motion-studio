"""NFP Location Engine - L1a: locations.json (nfp.locations/1), the base record of a place and its QC. Data only.

  {"schema": "nfp.locations/1",
   "locations": [{
     "id": "harbour-town",                       letters / digits / . _ - (starts with a letter or digit), <= 80
     "kind": "city",                             see KINDS
     "point": {"lat": 0.0, "lon": 0.0},          decimal degrees, numbers (never text); lat -90..90, lon -180..180
     "datum": "WGS84",                           only WGS84
     "precision": "exact",                       exact | approximate | centroid | uncertain
     "uncertainty_m": 250,                       radius in metres (>= 0) or null when unknown
     "sources": [{"type": "gazetteer", "title": "...", "author": null, "url": "https://...", "accessed": "2026-11-25",
                  "page": null, "license": null, "citation": null}],
     "reviewed": {"by": "...", "date": "2026-11-25"} | null,
     "confidence": {"level": "high" | "medium" | "low", "reason": "..."} | null,
     "notes": "" | null}]}

Every field is required (null where allowed), unknown fields are refused - nothing is silently assumed.

Status (computed, never stored):
  verified  valid coordinates AND at least one COMPLETE source AND reviewed (by + a real, non-future date) AND a
            confidence level with a reason. A source is complete when it says what it is (type + title) and where it can
            be found again: a citation, an author + page, or a URL with the date it was accessed. A URL alone proves
            nothing about the place and never makes a source complete.
  draft     anything else (allowed to be registered; later stages may refuse drafts in final work).
Lat / lon possibly swapped (lat out of range but the swapped pair valid) is a WARNING added to the range error: the
engine cannot know which value was meant. A swap where both values are in range is not detectable without a containing
area (L1c: parent / extent).

L1b: an optional "names" list (current / historical / alternative names, languages, periods, no year zero) - see
names.py; checked here, and name_at() picks a name for a year and language. A record without "names" is a valid L1a
record and keeps exactly the status it had (names do not change verified / draft; their errors do, like any error).

L1c (all optional): "parent" {id, relation} (hierarchy.py), "extent" {north, south, east, west} (geo.py, the date line
handled), "distinct_from" [ids] (places the user states are different although near / alike), possible duplicates
(duplicates.py: warnings only, never merged), and the command line (cli.py). Errors in them make the record a draft like
any error; warnings (outside the parent, near duplicates) do not.
"""
import datetime
import json
import math
import re
from pathlib import Path

from . import duplicates as DUP
from . import geo as GEO
from . import hierarchy as HI
from . import names as NM

SCHEMA = "nfp.locations/1"
KINDS = ("city", "town", "village", "region", "country", "river", "mountain", "sea", "lake", "site", "building",
         "battlefield", "route-point", "other")
PRECISIONS = ("exact", "approximate", "centroid", "uncertain")
LEVELS = ("high", "medium", "low")
SOURCE_TYPES = ("gazetteer", "map", "book", "article", "survey", "field", "archive", "other")
FIELDS = ("id", "kind", "point", "datum", "precision", "uncertainty_m", "sources", "reviewed", "confidence", "notes")
OPTIONAL = ("names", "parent", "extent", "distinct_from")      # L1b, L1c
SOURCE_FIELDS = ("type", "title", "author", "url", "accessed", "page", "license", "citation")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
URL_RE = re.compile(r"https?://[^\s/]+\S*")
MAX_DECIMALS = 7          # ~1 cm: more digits than any survey gives is false precision
EXACT_MIN_DECIMALS = 3    # ~100 m: fewer digits cannot be 'exact'
EXACT_MAX_UNCERTAINTY = 1000.0


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _text(v):
    return isinstance(v, str) and v.strip() != ""


def _decimals(v):
    """Digits after the decimal point as written (JSON numbers keep their shortest repr in Python)."""
    s = repr(float(v))
    if "e" in s or "E" in s:
        m, e = s.lower().split("e")
        d = len(m.split(".")[1]) if "." in m else 0
        return max(0, d - int(e))
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def _date(v, today):
    """(ok, problem) for a YYYY-MM-DD string: a real calendar date, not after `today`."""
    if not isinstance(v, str) or not DATE_RE.fullmatch(v):
        return False, "must be YYYY-MM-DD"
    try:
        d = datetime.date.fromisoformat(v)
    except ValueError:
        return False, "is not a real calendar date"
    if d > today:
        return False, f"is in the future (after {today.isoformat()})"
    return True, None


def check_point(p):
    """Coordinate problems of a point: [(level, code, message)]. Empty = valid coordinates."""
    out = []
    if not isinstance(p, dict) or set(p) != {"lat", "lon"}:
        return [("error", "bad_point", "point must be an object with exactly lat and lon")]
    lat, lon = p["lat"], p["lon"]
    for k, v in (("lat", lat), ("lon", lon)):
        if isinstance(v, str):
            out.append(("error", "not_a_number", f"{k} {v!r} is text: coordinates must be numbers"))
        elif not _num(v):
            out.append(("error", "not_a_number", f"{k} {v!r} is not a number"))
        elif not math.isfinite(v):
            out.append(("error", "not_finite", f"{k} is {v!r} (NaN / infinity is not a coordinate)"))
    if out:
        return out
    lat_ok, lon_ok = -90 <= lat <= 90, -180 <= lon <= 180
    if not lat_ok:
        out.append(("error", "lat_range", f"lat {lat!r} is outside -90..90"))
    if not lon_ok:
        out.append(("error", "lon_range", f"lon {lon!r} is outside -180..180"))
    if not lat_ok and -90 <= lon <= 90 and -180 <= lat <= 180:
        out.append(("warning", "maybe_swapped", f"lat {lat!r} / lon {lon!r} would be valid the other way round: "
                                                 f"are latitude and longitude swapped?"))
    if lat_ok and lon_ok:
        if lat == 0 and lon == 0:
            out.append(("warning", "null_island", "0, 0 is in the open ocean: usually a missing value, not a place"))
        for k, v in (("lat", lat), ("lon", lon)):
            if isinstance(v, float) and _decimals(v) > MAX_DECIMALS:
                out.append(("warning", "false_precision", f"{k} {v!r} has {_decimals(v)} decimals (more than {MAX_DECIMALS}: "
                                                           f"finer than any source gives)"))
    return out


def source_problems(s, today):
    """Why a source is not complete ([] = complete); malformed parts are reported as errors separately."""
    need = []
    if s.get("type") not in SOURCE_TYPES:
        need.append("type")
    if not _text(s.get("title")):
        need.append("title")
    url_ok = isinstance(s.get("url"), str) and URL_RE.fullmatch(s["url"]) is not None
    acc_ok = isinstance(s.get("accessed"), str) and _date(s["accessed"], today)[0]
    where = _text(s.get("citation")) or (_text(s.get("author")) and _text(s.get("page"))) or (url_ok and acc_ok)
    if not where:
        need.append("where to find it again (a citation, an author + page, or a URL with its accessed date)")
    return need


def validate(doc, today=None, near_m=DUP.NEAR_M, name_m=DUP.NAME_M):
    """QC of a locations.json document -> {status, errors, warnings, infos, issues, locations: {id: verified|draft},
    duplicates: [...]}. near_m / name_m: duplicate thresholds in metres (see duplicates.py)."""
    today = today or datetime.date.today()
    for k, v in (("near_m", near_m), ("name_m", name_m)):
        if not _num(v) or not math.isfinite(v) or v < 0:
            raise ValueError(f"{k} must be a number of metres >= 0")
    issues, status = [], {}
    index, points, extents, dups = {}, {}, {}, []

    def add(level, code, msg, loc=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("location", loc), ("message", msg)) if v is not None})

    def done():
        n = {lv: sum(1 for x in issues if x["level"] == lv) for lv in ("error", "warning", "info")}
        return {"status": "FAIL" if n["error"] else "WARN" if n["warning"] else "OK", "errors": n["error"],
                "warnings": n["warning"], "infos": n["info"], "issues": issues, "locations": status, "duplicates": dups}

    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        add("error", "schema", f"locations file must have schema {SCHEMA}")
        return done()
    extra = sorted(set(doc) - {"schema", "locations"})
    if extra:
        add("error", "schema", f"unknown top-level field(s) {', '.join(extra)}")
    rows = doc.get("locations")
    if not isinstance(rows, list):
        add("error", "schema", "locations must be a list")
        return done()
    for r in rows:
        if not isinstance(r, dict):
            add("error", "schema", "every location must be an object")
            continue
        lid = r.get("id")
        if not isinstance(lid, str) or not ID_RE.fullmatch(lid):
            add("error", "bad_id", f"bad location id {lid!r}")
            continue
        if lid in status:
            add("error", "duplicate_id", f"location id {lid!r} is used twice", lid)
            continue
        status[lid] = "draft"
        index[lid] = r
        ok = True
        missing = [k for k in FIELDS if k not in r]
        extra = sorted(set(r) - set(FIELDS) - set(OPTIONAL))
        if missing:
            add("error", "schema", f"missing field(s) {', '.join(missing)} (use null where allowed)", lid)
            ok = False
        if extra:
            add("error", "schema", f"unknown field(s) {', '.join(extra)}", lid)
            ok = False
        if r.get("kind") not in KINDS:
            add("error", "bad_kind", f"kind must be one of {', '.join(KINDS)}", lid)
            ok = False
        if r.get("datum") != "WGS84":
            add("error", "bad_datum", f"datum {r.get('datum')!r}: only WGS84 (convert before recording)", lid)
            ok = False
        prec = r.get("precision")
        if prec not in PRECISIONS:
            add("error", "bad_precision", f"precision must be one of {', '.join(PRECISIONS)}", lid)
            ok = False
        # coordinates
        point_ok = "point" in r
        for lv, code, msg in check_point(r.get("point")) if "point" in r else []:
            add(lv, code, msg, lid)
            if lv == "error":
                point_ok = False
        ok &= point_ok
        # uncertainty
        u = r.get("uncertainty_m")
        if u is not None and (not _num(u) or not math.isfinite(u) or u < 0):
            add("error", "bad_uncertainty", "uncertainty_m must be a number of metres >= 0, or null", lid)
            ok = False
        elif prec in PRECISIONS:
            if u is None and prec != "exact":
                add("warning", "no_uncertainty", f"precision {prec} without uncertainty_m: how far off can it be?", lid)
            if prec == "exact" and _num(u) and u > EXACT_MAX_UNCERTAINTY:
                add("warning", "precision_mismatch", f"precision exact but uncertainty_m {u:g} m", lid)
            if prec == "exact" and point_ok and isinstance(r["point"], dict):
                low = [k for k in ("lat", "lon") if _decimals(r["point"][k]) < EXACT_MIN_DECIMALS]
                if low:
                    add("warning", "precision_mismatch", f"precision exact but {' / '.join(low)} has fewer than "
                                                         f"{EXACT_MIN_DECIMALS} decimals", lid)
        # names (L1b, optional)
        if "names" in r:
            for lv, code, msg in NM.check_names(r["names"], today.year):
                add(lv, code, msg, lid)
                if lv == "error":
                    ok = False
        else:
            add("info", "no_names", "no names (an L1a record): name_at() has nothing to show", lid)
        # notes
        if "notes" in r and r["notes"] is not None and not isinstance(r["notes"], str):
            add("error", "schema", "notes must be text or null", lid)
            ok = False
        # sources
        complete = 0
        srcs = r.get("sources")
        if not isinstance(srcs, list):
            add("error", "schema", "sources must be a list ([] if none yet)", lid)
            ok, srcs = False, []
        for i, s in enumerate(srcs):
            if not isinstance(s, dict):
                add("error", "schema", f"source {i + 1} must be an object", lid)
                ok = False
                continue
            ex, mi = sorted(set(s) - set(SOURCE_FIELDS)), [k for k in SOURCE_FIELDS if k not in s]
            if ex or mi:
                add("error", "schema", f"source {i + 1}: " + "; ".join(x for x in (
                    f"unknown field(s) {', '.join(ex)}" if ex else "", f"missing field(s) {', '.join(mi)}" if mi else "") if x), lid)
                ok = False
                continue
            for k in ("title", "author", "page", "license", "citation"):
                if s[k] is not None and not isinstance(s[k], str):
                    add("error", "schema", f"source {i + 1}: {k} must be text or null", lid)
                    ok = False
            if s["type"] is not None and s["type"] not in SOURCE_TYPES:
                add("error", "bad_source_type", f"source {i + 1}: type must be one of {', '.join(SOURCE_TYPES)}", lid)
                ok = False
            if s["url"] is not None and not (isinstance(s["url"], str) and URL_RE.fullmatch(s["url"])):
                add("error", "bad_url", f"source {i + 1}: url must be an http(s) address or null", lid)
                ok = False
            if s["accessed"] is not None:
                good, why = _date(s["accessed"], today)
                if not good:
                    add("error", "bad_date", f"source {i + 1}: accessed {s['accessed']!r} {why}", lid)
                    ok = False
            need = source_problems(s, today)
            if need:
                add("info", "incomplete_source", f"source {i + 1} is not complete: missing " + ", ".join(need), lid)
            else:
                complete += 1
        # review + confidence
        rv = r.get("reviewed")
        rv_ok = False
        if rv is not None:
            if not isinstance(rv, dict) or set(rv) != {"by", "date"}:
                add("error", "schema", "reviewed must be {by, date} or null", lid)
                ok = False
            else:
                good, why = _date(rv["date"], today)
                if not good:
                    add("error", "bad_date", f"reviewed.date {rv['date']!r} {why}", lid)
                    ok = False
                if not _text(rv["by"]):
                    add("error", "schema", "reviewed.by must name who checked it", lid)
                    ok = False
                rv_ok = good and _text(rv["by"])
        cf = r.get("confidence")
        cf_ok = False
        if cf is not None:
            if not isinstance(cf, dict) or set(cf) != {"level", "reason"}:
                add("error", "schema", "confidence must be {level, reason} or null", lid)
                ok = False
            elif cf["level"] not in LEVELS:
                add("error", "bad_confidence", f"confidence.level must be one of {', '.join(LEVELS)}", lid)
                ok = False
            elif not _text(cf["reason"]):
                add("error", "schema", "confidence.reason must say why", lid)
                ok = False
            else:
                cf_ok = True
                if cf["level"] == "low":
                    add("warning", "low_confidence", f"low confidence: {cf['reason']}", lid)
        # L1c: parent (shape here, links after the loop), extent, distinct_from
        if "parent" in r:
            for lv, code, msg in HI.check_shape(r["parent"]):
                add(lv, code, msg, lid)
                ok = False
        if "extent" in r:
            ext_bad = False
            for lv, code, msg in GEO.check_extent(r["extent"]):
                add(lv, code, msg, lid)
                if lv == "error":
                    ok, ext_bad = False, True
            if not ext_bad:
                extents[lid] = r["extent"]
                if point_ok and not GEO.contains_point(r["extent"], r["point"]["lat"], r["point"]["lon"]):
                    add("warning", "point_outside_extent", "the point is outside the location's own extent", lid)
        if "distinct_from" in r:
            dfr = r["distinct_from"]
            if not isinstance(dfr, list) or not all(isinstance(x, str) and x for x in dfr):
                add("error", "schema", "distinct_from must be a list of location ids", lid)
                ok = False
            elif lid in dfr:
                add("error", "bad_distinct", "distinct_from lists the location itself", lid)
                ok = False
        if point_ok:
            points[lid] = (r["point"]["lat"], r["point"]["lon"])
        reasons = []
        if not point_ok:
            reasons.append("coordinates not valid")
        if complete == 0:
            reasons.append("no complete source")
        if not rv_ok:
            reasons.append("not reviewed (by + date)")
        if not cf_ok:
            reasons.append("no confidence level with a reason")
        if ok and not reasons:
            status[lid] = "verified"
        else:
            add("info", "draft", "draft (not verified): " + "; ".join(reasons or ["errors above"]), lid)
    # L1c cross-record checks: parents, distinct_from targets, possible duplicates
    for lid, found in HI.check_links(index, points, extents).items():
        for lv, code, msg in found:
            add(lv, code, msg, lid)
            if lv == "error" and status.get(lid) == "verified":
                status[lid] = "draft"
                add("info", "draft", "draft (not verified): parent errors", lid)
    related = set()
    for lid, r in index.items():
        try:
            for anc in HI.ancestors(index, lid):
                related.add(tuple(sorted((lid, anc))))
        except ValueError:
            pass
        for other in r.get("distinct_from") or [] if isinstance(r.get("distinct_from"), list) else []:
            if isinstance(other, str) and other != lid:
                if other not in index:
                    add("error", "bad_distinct", f"distinct_from names {other!r}, which is not in this file", lid)
                    if status.get(lid) == "verified":
                        status[lid] = "draft"
                        add("info", "draft", "draft (not verified): distinct_from errors", lid)
                related.add(tuple(sorted((lid, other))))
    for a, b, code, d, why in DUP.find(index, points, related, near_m, name_m):
        dups.append({"a": a, "b": b, "reason": code, "distance_m": round(d, 2), "detail": why})
        for x, y in ((a, b), (b, a)):
            add("warning", code, f"possible duplicate of {y!r}: {why} ({d:.1f} m apart) - nothing merged; if they are "
                                 f"different places, add one id to the other's distinct_from (one side is enough, "
                                 f"not both)", x)
    return done()


def load(path):
    """Read a locations.json (NaN / Infinity tokens are read as numbers so that validate() reports them)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
