"""NFP Timeline - timeline.json (nfp.timeline/1): tracks and clips in whole frames at 30 fps. Data + QC only (no render).

  {"schema": "nfp.timeline/1", "fps": 30, "duration": 450,             duration in frames
   "mode": "draft" | "final",                                          final: clips may not use draft (unverified) assets
   "tracks": [{"id": "pictures", "kind": "visual", "coverage": false, "overlap": false}, ...],
   "clips": [{"id": "c-harbour", "track": "pictures", "kind": "image", "start": 9, "end": 140,
              "anchors": {"start": 0.3, "end": ["s2", "w", 0]},       optional: where start / end come from
              "asset": "harbour-1952", "in": 0, "ref": "...", "note": "..."}]}

  track kinds  narration, visual, overlay, subtitles, characters, audio
  clip kinds   visual / overlay: image, video, map, motion, animation, svg-shot, graphic;  narration: narration;
               subtitles: subtitles;  characters: character;  audio: audio
  overlap      default: not allowed on narration / visual / subtitles, allowed on overlay / characters / audio
  coverage     only when a track sets "coverage": true is every frame 0..duration required to be covered; otherwise
               gaps are intentional and only listed as info
  in           (video / audio clips) first frame used from the media; in + length must fit the media's duration
  in / out     (T4, video clips, with a probe) SOURCE frames in the video's own frame rate: the clip reads source frames
               in .. out - 1 (out optional; if given it must equal what [start, end) reads at speed 1); reading past the
               last frame is an error (no freeze); see videofile.py
  camera       (T2, image clips) Ken Burns move over the clip: see kenburns.py (none = still); checked against the
               image's real pixel size: no stretching, no empty space, limited enlargement, calm speed
Times: start < end, 0 <= start, end <= duration (end is exclusive: a clip [9, 140) shows frames 9..139).
"""
import math

from . import anchors as AN
from . import assets as AS
from . import kenburns as KB
from . import videofile as VF

SCHEMA = "nfp.timeline/1"
FPS = AN.FPS
TRACK_KINDS = ("narration", "visual", "overlay", "subtitles", "characters", "audio")
PICTURE_KINDS = ("image", "video", "map", "motion", "animation", "svg-shot", "graphic")
CLIP_KINDS = {"visual": PICTURE_KINDS, "overlay": PICTURE_KINDS, "narration": ("narration",), "subtitles": ("subtitles",),
              "characters": ("character",), "audio": ("audio",)}
OVERLAP_DEFAULT = {"narration": False, "visual": False, "subtitles": False, "overlay": True, "characters": True, "audio": True}
ASSET_KINDS = {"image": ("image",), "video": ("video",), "map": ("map", "image"), "motion": ("motion", "video"),
               "animation": ("animation", "video"), "audio": ("audio",)}
ASSET_REQUIRED = ("image", "video", "audio")
NO_ASSET = ("svg-shot", "narration", "subtitles", "character", "graphic")
HAS_IN = ("video", "audio")
CLIP_FIELDS = {"id", "track", "kind", "start", "end", "anchors", "asset", "in", "out", "ref", "note", "camera"}
TRACK_FIELDS = {"id", "kind", "coverage", "overlap"}
TOP_FIELDS = {"schema", "fps", "duration", "mode", "tracks", "clips"}


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def validate(doc, assets_doc=None, assets_base=None, context=None, check_files=True, probe=None):
    """QC of a timeline (+ its asset registry, + anchors against word timing when a Context is given; + video files when a
    probe is given: probe(path) -> ffprobe JSON, see videofile.py).
    -> {"status": OK|WARN|FAIL, "errors", "warnings", "infos", "issues": [...], "assets": {id: verified|draft}}"""
    issues = []

    def add(level, code, msg, clip=None, track=None, asset=None):
        issues.append({k: v for k, v in (("level", level), ("code", code), ("clip", clip), ("track", track),
                                         ("asset", asset), ("message", msg)) if v is not None})

    statuses = {}
    if assets_doc is not None:
        statuses, a_issues = AS.check(assets_doc, assets_base or ".", check_files=check_files)
        issues += a_issues
    asset_rows = {a["id"]: a for a in (assets_doc or {}).get("assets", []) if isinstance(a, dict) and isinstance(a.get("id"), str)}
    video = {}                          # T4: asset id -> ffprobe facts of a usable video file
    if probe is not None and assets_doc is not None:
        from pathlib import Path
        for vid, row in asset_rows.items():
            lp = row.get("local_path")
            if row.get("kind") != "video" or not isinstance(lp, str) or vid not in statuses:
                continue
            f = Path(assets_base or ".") / lp
            if not f.is_file() or ".." in Path(lp).parts or Path(lp).is_absolute():
                continue                                 # reported by the asset check
            try:
                fx = VF.facts(probe(f))
            except Exception as e:                       # ffprobe missing / unreadable file
                issues.append({"level": "error", "code": "video_probe", "asset": vid, "message": f"{lp}: cannot be probed ({e})"})
                statuses[vid] = "draft"
                continue
            bad = VF.check(fx)
            if not bad:
                if (row.get("width"), row.get("height")) != (fx["width"], fx["height"]):
                    bad.append(f"{fx['width']}x{fx['height']} pixels, recorded {row.get('width')}x{row.get('height')}")
                d = row.get("duration")
                if not (isinstance(d, (int, float)) and not isinstance(d, bool) and abs(d - fx["frames"] / float(fx["fps"])) <= 1 / float(fx["fps"])):
                    bad.append(f"{fx['frames']} frames at {fx['fps']} fps = {fx['frames'] / float(fx['fps']):.3f} s, recorded duration {d}")
            if bad:
                issues.append({"level": "error", "code": "video_file", "asset": vid, "message": f"{lp}: " + "; ".join(bad)})
                statuses[vid] = "draft"
            else:
                video[vid] = fx
                if fx["audio"]:
                    issues.append({"level": "info", "code": "video_audio", "asset": vid,
                                   "message": f"{lp} has {fx['audio']} audio stream(s): video clips are always muted"})

    def done():
        n = {lv: sum(1 for x in issues if x["level"] == lv) for lv in ("error", "warning", "info")}
        return {"status": "FAIL" if n["error"] else "WARN" if n["warning"] else "OK", "errors": n["error"],
                "warnings": n["warning"], "infos": n["info"], "issues": issues, "assets": statuses}

    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        add("error", "schema", f"timeline must have schema {SCHEMA}")
        return done()
    extra = sorted(set(doc) - TOP_FIELDS)
    if extra:
        add("error", "schema", f"unknown top-level field(s) {', '.join(extra)}")
    if doc.get("fps") != FPS:
        add("error", "fps", f"fps must be {FPS}")
    dur = doc.get("duration")
    if not _int(dur) or dur <= 0:
        add("error", "bad_duration", "duration must be a whole number of frames > 0")
        return done()
    if context is not None and context.frames != dur:
        add("error", "duration_mismatch", f"duration {dur} frames, but the video (words.json) is {context.frames} frames")
    mode = doc.get("mode", "draft")
    if mode not in ("draft", "final"):
        add("error", "schema", "mode must be 'draft' or 'final'")
    # tracks
    tracks = {}
    for t in doc.get("tracks") if isinstance(doc.get("tracks"), list) else []:
        tid = t.get("id") if isinstance(t, dict) else None
        if not isinstance(tid, str) or not AS.ID_RE.fullmatch(tid):
            add("error", "bad_id", f"bad track id {tid!r}")
            continue
        if tid in tracks:
            add("error", "duplicate_id", f"track id {tid!r} is used twice", track=tid)
            continue
        ex = sorted(set(t) - TRACK_FIELDS)
        if ex:
            add("error", "schema", f"unknown field(s) {', '.join(ex)}", track=tid)
        if t.get("kind") not in TRACK_KINDS:
            add("error", "bad_kind", f"track kind must be one of {', '.join(TRACK_KINDS)}", track=tid)
            continue
        for k in ("coverage", "overlap"):
            if k in t and not isinstance(t[k], bool):
                add("error", "schema", f"{k} must be true or false", track=tid)
        tracks[tid] = {"kind": t["kind"], "coverage": t.get("coverage") is True,
                       "overlap": t.get("overlap", OVERLAP_DEFAULT[t["kind"]]) is True}
    if not isinstance(doc.get("tracks"), list) or not tracks:
        add("error", "schema", "tracks must be a non-empty list")
    # clips
    seen, per_track = set(), {}
    clips = doc.get("clips")
    if not isinstance(clips, list):
        add("error", "schema", "clips must be a list")
        clips = []
    for c in clips:
        cid = c.get("id") if isinstance(c, dict) else None
        if not isinstance(cid, str) or not AS.ID_RE.fullmatch(cid):
            add("error", "bad_id", f"bad clip id {cid!r}")
            continue
        if cid in seen:
            add("error", "duplicate_id", f"clip id {cid!r} is used twice", clip=cid)
            continue
        seen.add(cid)
        ex = sorted(set(c) - CLIP_FIELDS)
        if ex:
            add("error", "schema", f"unknown field(s) {', '.join(ex)}", clip=cid)
        tr = tracks.get(c.get("track"))
        if tr is None:
            add("error", "unknown_track", f"unknown track {c.get('track')!r}", clip=cid)
            continue
        kind = c.get("kind")
        if kind not in CLIP_KINDS[tr["kind"]]:
            add("error", "bad_kind", f"a {tr['kind']} track takes {', '.join(CLIP_KINDS[tr['kind']])} clips, not {kind!r}", clip=cid)
            continue
        a0, a1 = c.get("start"), c.get("end")
        if not _int(a0) or not _int(a1):
            add("error", "bad_time", "start and end must be whole frame numbers", clip=cid)
            continue
        if a0 < 0 or a1 <= a0:
            add("error", "bad_time", f"start {a0} / end {a1}: need 0 <= start < end", clip=cid)
            continue
        if a1 > dur:
            add("error", "outside_video", f"ends at frame {a1}, after the end of the video ({dur})", clip=cid)
        # anchors
        an = c.get("anchors")
        if an is not None:
            if not isinstance(an, dict) or not an or set(an) - {"start", "end"}:
                add("error", "bad_anchor", "anchors must be an object with start and / or end", clip=cid)
            else:
                for k, v in an.items():
                    if not AN.is_anchor_shape(v):
                        add("error", "bad_anchor", f"{k}: {v!r} is not an anchor", clip=cid)
                    elif context is not None:
                        try:
                            f = context.resolve(v)
                        except AN.AnchorError as e:
                            add("error", "bad_anchor", f"{k}: {e}", clip=cid)
                            continue
                        if f != c[k]:
                            add("error", "anchor_mismatch", f"{k} is frame {c[k]} but its anchor {v!r} resolves to frame {f}", clip=cid)
                if context is None:
                    add("info", "anchors_unchecked", "anchors not resolved (no word timing given)", clip=cid)
        # asset
        aid = c.get("asset")
        if kind in NO_ASSET and aid is not None:
            add("error", "asset_not_allowed", f"a {kind} clip takes no asset", clip=cid)
        elif aid is not None:
            if assets_doc is None or aid not in asset_rows:
                add("error", "unknown_asset", f"asset {aid!r} is not in the asset registry", clip=cid)
            else:
                ak = asset_rows[aid].get("kind")
                if ak not in ASSET_KINDS.get(kind, ()):
                    add("error", "asset_kind", f"a {kind} clip cannot use a {ak} asset", clip=cid)
                st = statuses.get(aid, "draft")
                if st != "verified":
                    add("error" if mode == "final" else "warning", "draft_asset",
                        f"asset {aid!r} is a draft (licence / file not verified)" + (" - not allowed in a final timeline" if mode == "final" else ""),
                        clip=cid)
        elif kind in ASSET_REQUIRED:
            add("error", "asset_required", f"a {kind} clip needs an asset", clip=cid)
        if kind in ("svg-shot", "character", "graphic") and not (isinstance(c.get("ref"), str) and c["ref"]):
            add("error", "ref_required", f"a {kind} clip needs ref ({ {'svg-shot': 'the shot id', 'character': 'the actor key', 'graphic': 'its graphic document, nfp.graphics/1'}[kind] })", clip=cid)
        # in-point
        if "in" in c:
            if kind not in HAS_IN:
                add("error", "in_not_allowed", f"'in' is only for {' / '.join(HAS_IN)} clips", clip=cid)
            elif not _int(c["in"]) or c["in"] < 0:
                add("error", "bad_time", "in must be a whole frame number >= 0", clip=cid)
        if "out" in c and kind != "video":
            add("error", "out_not_allowed", "'out' is only for video clips", clip=cid)
        if kind == "video" and aid in video:          # T4: exact source frames from the probed file
            fx = video[aid]
            first = c.get("in", 0)
            if _int(first) and first >= 0:
                lo, out = VF.source_frames(a0, a1, first, fx["fps"])
                if "out" in c and c["out"] != out:
                    add("error", "bad_out", f"out {c['out']!r}: frames {a0}..{a1 - 1} from in {first} read source frames "
                                            f"{lo}..{out - 1} at speed 1, so out must be {out}", clip=cid)
                if out > fx["frames"]:
                    add("error", "beyond_media", f"reads source frames {lo}..{out - 1} but the video has frames 0..{fx['frames'] - 1} "
                                                 f"(past its end the last frame would freeze)", clip=cid)
            w, h = fx["width"], fx["height"]
            for lv, code, msg in KB.check(KB.expand(None, w, h), w, h, a1 - a0):
                add(lv, code, msg.replace("image", "video"), clip=cid)
        elif kind == "video" and aid in asset_rows and probe is None:
            add("info", "video_unprobed", "video file not probed here (the Film bridge always probes before a render): "
                                          "frame-exact in / out and format not checked", clip=cid)
        if kind in HAS_IN and aid in asset_rows and not (kind == "video" and probe is not None):
            md = asset_rows[aid].get("duration")
            first = c.get("in", 0) if _int(c.get("in", 0)) else 0
            if isinstance(md, (int, float)) and not isinstance(md, bool) and md > 0:
                avail = math.floor(md * FPS + 1e-6)
                if first + (a1 - a0) > avail:
                    add("error", "beyond_media", f"uses media frames {first}..{first + a1 - a0 - 1} but the media has {avail} frames", clip=cid)
        # camera (T2: still images)
        if "camera" in c and kind != "image":
            add("error", "camera_not_allowed", "camera is only for image clips (T2)", clip=cid)
        elif kind == "image":
            row = asset_rows.get(aid) if aid is not None else None
            w, h = (row or {}).get("width"), (row or {}).get("height")
            if not (_int(w) and _int(h) and w > 0 and h > 0):
                if row is not None:
                    add("warning", "camera_unchecked", "the image size is unknown: the camera cannot be checked", clip=cid)
            else:
                try:
                    cam = KB.expand(c.get("camera"), w, h)
                except KB.CameraError as e:
                    add("error", "bad_camera", str(e), clip=cid)
                else:
                    for lv, code, msg in KB.check(cam, w, h, a1 - a0):
                        add(lv, code, msg, clip=cid)
        per_track.setdefault(c["track"], []).append((a0, a1, cid))
    # overlap / coverage per track
    for tid, tr in tracks.items():
        rows = sorted(per_track.get(tid, []))
        if not tr["overlap"]:
            end_max, last = -1, None
            for a0, a1, cid in rows:
                if a0 < end_max:
                    add("error", "overlap", f"frames {a0}..{min(a1, end_max) - 1} overlap clip {last!r} (track {tid} allows no overlap)",
                        clip=cid, track=tid)
                if a1 > end_max:
                    end_max, last = a1, cid
        gaps, cur = [], 0
        for a0, a1, _ in rows:
            if a0 > cur:
                gaps.append((cur, a0))
            cur = max(cur, a1)
        if cur < dur:
            gaps.append((cur, dur))
        if gaps:
            txt = ", ".join(f"{a}..{b - 1}" for a, b in gaps[:6]) + (" ..." if len(gaps) > 6 else "")
            if tr["coverage"]:
                add("error", "gap", f"{len(gaps)} uncovered stretch(es): frames {txt} (track requires full coverage)", track=tid)
            elif rows:
                add("info", "gap", f"{len(gaps)} gap(s) (allowed): frames {txt}", track=tid)
    return done()


def resolve(doc, context):
    """A copy of the timeline whose clip start / end are set from their anchors (and duration from the context)."""
    import copy
    out = copy.deepcopy(doc)
    out["duration"] = context.frames
    for c in out.get("clips", []):
        for k, v in (c.get("anchors") or {}).items():
            c[k] = context.resolve(v)
    return out
