"""NFP Timeline - asset registry (assets.json, nfp.assets/1): local media and where it came from. Data + checks only:
nothing here searches, downloads or fetches anything; files must already be inside the project.

  {"schema": "nfp.assets/1",
   "assets": [{"id": "harbour-1952", "kind": "image",               image | video | map | animation | motion | audio
               "local_path": "media/harbour.jpg",                  relative to assets.json, inside its folder
               "sha256": "<64 hex>", "width": 3000, "height": 2000, "duration": null,   duration in seconds (video/audio)
               "source_url": "https://...", "author": "...", "license": "CC BY-SA 4.0", "license_url": "https://...",
               "retrieved_at": "2026-11-20", "modifications": "cropped to 16:9" | "none",
               "license_verified": true, "attribution": "Photo: ... (CC BY-SA 4.0)",
               "restrictions": ["no-derivatives" | "editorial-only" | "non-commercial" | ...], "real_person": false}]}

Status (computed, never stored): 'verified' only when the licence record is complete, license_verified is true and the
file exists with the recorded sha256; otherwise 'draft' (allowed to be registered; a timeline in 'final' mode refuses
clips on drafts). Licence fields = photoslots.py's (author, license, license_url, source_url, retrieved, modifications,
license_verified, src) with local_path = src and retrieved_at = retrieved; to_photo_slot() gives that record.
license "original" = the project's own work (made for this film): source_url / license_url are not needed.
"""
import hashlib
import json
import re
from pathlib import Path

from . import imagefile

SCHEMA = "nfp.assets/1"
KINDS = ("image", "video", "map", "animation", "motion", "audio")
FIELDS = ("id", "kind", "local_path", "sha256", "width", "height", "duration", "source_url", "author", "license",
          "license_url", "retrieved_at", "modifications", "license_verified", "attribution", "restrictions", "real_person")
LICENCE = ("author", "license", "license_url", "source_url", "retrieved_at", "modifications", "attribution")
ORIGINAL = "original"
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
SHA_RE = re.compile(r"[0-9a-f]{64}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
URL_RE = re.compile(r"https?://\S+")
VISUAL = ("image", "video", "map", "animation", "motion")
TIMED = ("video", "audio", "animation", "motion")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")), p.parent


def check(doc, base_dir, check_files=True):
    """-> (statuses {id: 'verified'|'draft'}, issues [{level, code, asset, message}])."""
    issues, status = [], {}

    def add(level, code, msg, aid=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("asset", aid), ("message", msg)) if v is not None})

    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        add("error", "schema", f"assets file must have schema {SCHEMA}")
        return status, issues
    extra = sorted(set(doc) - {"schema", "assets"})
    if extra:
        add("error", "schema", f"unknown top-level field(s) {', '.join(extra)}")
    rows = doc.get("assets")
    if not isinstance(rows, list):
        add("error", "schema", "assets must be a list")
        return status, issues
    base = Path(base_dir).resolve()
    for a in rows:
        if not isinstance(a, dict):
            add("error", "schema", "every asset must be an object")
            continue
        aid = a.get("id")
        if not isinstance(aid, str) or not ID_RE.fullmatch(aid):
            add("error", "bad_id", f"bad asset id {aid!r}")
            continue
        if aid in status:
            add("error", "duplicate_id", f"asset id {aid!r} is used twice", aid)
            continue
        missing_keys = [k for k in FIELDS if k not in a]
        extra = sorted(set(a) - set(FIELDS))
        if extra:
            add("error", "schema", f"unknown field(s) {', '.join(extra)}", aid)
        if missing_keys:
            add("error", "schema", f"missing field(s) {', '.join(missing_keys)} (use null when unknown)", aid)
        status[aid] = "draft"
        ok = not extra and not missing_keys
        kind = a.get("kind")
        if kind not in KINDS:
            add("error", "bad_kind", f"kind must be one of {', '.join(KINDS)}", aid)
            ok = False
        # media facts
        for k in ("width", "height"):
            v = a.get(k)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v <= 0):
                add("error", "bad_size", f"{k} must be a positive integer or null", aid)
                ok = False
        if kind in VISUAL and kind != "map" and (a.get("width") is None or a.get("height") is None):
            add("warning", "no_size", "width / height unknown", aid)
        d = a.get("duration")
        if d is not None and (isinstance(d, bool) or not isinstance(d, (int, float)) or d <= 0):
            add("error", "bad_duration", "duration must be seconds > 0 or null", aid)
            ok = False
        if kind in ("video", "audio") and d is None:
            add("warning", "no_duration", "duration unknown: clip lengths cannot be checked against the media", aid)
        if kind == "image" and d is not None:
            add("error", "bad_duration", "an image has no duration", aid)
            ok = False
        for k in ("license_verified", "real_person"):
            if not isinstance(a.get(k), bool):
                add("error", "schema", f"{k} must be true or false", aid)
                ok = False
        r = a.get("restrictions")
        if not isinstance(r, list) or not all(isinstance(x, str) and x for x in r):
            add("error", "schema", "restrictions must be a list of strings ([] if none)", aid)
            ok = False
            r = []
        # local file
        file_ok, fpath = False, None
        lp, sha = a.get("local_path"), a.get("sha256")
        if sha is not None and (not isinstance(sha, str) or not SHA_RE.fullmatch(sha)):
            add("error", "bad_sha256", "sha256 must be 64 lowercase hex characters or null", aid)
            ok, sha = False, None
        if lp is not None:
            if not isinstance(lp, str) or not lp or Path(lp).is_absolute() or ".." in Path(lp).parts or "\\" in lp:
                add("error", "bad_path", "local_path must be a relative path inside the project (no .., not absolute)", aid)
                ok = False
            elif check_files:
                f = (base / lp)
                try:
                    inside = f.resolve().is_relative_to(base)
                except OSError:
                    inside = False
                if not inside:
                    add("error", "bad_path", "local_path leaves the project folder", aid)
                    ok = False
                elif not f.is_file():
                    add("error", "missing_file", f"file not found: {lp}", aid)
                    ok = False
                else:
                    fpath = f
                if fpath is not None and sha is not None:
                    got = sha256_file(f)
                    if got != sha:
                        add("error", "sha256_mismatch", f"{lp}: sha256 is {got[:12]}..., recorded {sha[:12]}...", aid)
                        ok = False
                    else:
                        file_ok = True
                elif fpath is not None:
                    add("warning", "no_sha256", "no sha256 recorded: the file cannot be pinned", aid)
        # T2: the pixels of a still image (format, real size, orientation) - read from the file header
        if fpath is not None and kind in ("image", "map"):
            try:
                im = imagefile.info(fpath)
            except (imagefile.ImageError, OSError) as e:
                im = None
                if kind == "image":
                    add("error", "unsupported_format", f"{lp}: {e} (images must be PNG or JPEG)", aid)
                    ok = False
            if im:
                if (a.get("width"), a.get("height")) != (im["width"], im["height"]):
                    add("error", "size_mismatch", f"{lp} is {im['width']}x{im['height']} pixels, recorded "
                                                  f"{a.get('width')}x{a.get('height')}", aid)
                    ok = False
                if im["orientation"] != 1:
                    add("error", "exif_rotation", f"{lp} carries EXIF orientation {im['orientation']}: re-save it upright "
                                                  f"(browsers would rotate it, its stored size would not)", aid)
                    ok = False
        # licence (complete record -> may be verified)
        lic = a.get("license")
        need = [k for k in LICENCE if not (isinstance(a.get(k), str) and a.get(k).strip())]
        if lic == ORIGINAL:
            need = [k for k in need if k not in ("source_url", "license_url")]
        for k in ("source_url", "license_url"):
            v = a.get(k)
            if isinstance(v, str) and v.strip() and not URL_RE.fullmatch(v):
                add("error", "bad_url", f"{k} must be an http(s) URL", aid)
                ok = False
        ra = a.get("retrieved_at")
        if isinstance(ra, str) and ra and not DATE_RE.fullmatch(ra):
            add("error", "bad_date", "retrieved_at must be YYYY-MM-DD", aid)
            ok = False
        if "no-derivatives" in r and isinstance(a.get("modifications"), str) and a["modifications"].strip().lower() not in ("", "none"):
            add("error", "restriction", "the licence allows no derivatives but modifications are recorded", aid)
            ok = False
        if a.get("real_person") is True:
            add("info", "real_person", "shows a real person: the project's real-person policy applies", aid)
        reasons = []
        if need:
            reasons.append("missing " + ", ".join(need))
        if a.get("license_verified") is not True:
            reasons.append("license_verified is not true")
        if lp is None or sha is None:
            reasons.append("no pinned local file (local_path + sha256)")
        elif check_files and not file_ok:
            reasons.append("local file not confirmed")
        if not check_files and lp is not None and sha is not None:
            reasons.append("files not checked")
        if ok and not reasons:
            status[aid] = "verified"
        else:
            add("info", "draft", "draft (not verified): " + "; ".join(reasons or ["errors above"]), aid)
    return status, issues


def to_photo_slot(a):
    """The same licence record in photoslots.py's form (slot status 'licensed' or 'placeholder')."""
    licensed = a.get("license_verified") is True and bool(a.get("local_path"))
    return {"id": a["id"], "status": "licensed" if licensed else "placeholder",
            **({"src": a["local_path"], "author": a.get("author"), "license": a.get("license"), "license_url": a.get("license_url"),
                "source_url": a.get("source_url"), "retrieved": a.get("retrieved_at"), "modifications": a.get("modifications"),
                "license_verified": a.get("license_verified")} if licensed else {})}
