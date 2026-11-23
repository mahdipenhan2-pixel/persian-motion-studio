"""
NFP Character Engine - C3a: Character Adapter for the flat_cartoon_v2 rig.

    cast = load_checked("<project dir>")                 # C1 load + identity-lock check (the ONLY way in)
    a = adapt(cast, "zahra", stage="adult", wardrobe="formal", expr="happy", instance=1)
    a["spec"]          -> complete argument for K.chars.actor(spec): all 18 fields, explicit
    a["fingerprint"]   -> C1 identity fingerprint (goes onto the DOM as data-nfp-fp)
    a["dom_id"]        -> C1 isolation id (nfp-c-<project>-<id>-<n>)
    a["sources"]       -> where every field came from: "cast" | "neutral" | "derived" | "placement"
    a["warnings"]      -> e.g. a cast that explicitly chose a colour equal to a Kim default (allowed, but reported)

Rules (from renderers/flat_cartoon_v2/README.md):
  * every rig field is passed explicitly; the rig's own fallbacks (5 of which are the Kim character's identity) are
    never reached. Optional wardrobe fields left empty by the cast come from neutral_defaults.json; lip is derived
    from the character's own skin. Identity (skin, hair, eyes) and outfit/top are never invented: missing = error.
  * nothing filled in by the adapter may equal any rig default (Kim colours or generic placeholders) - checked.
  * the adapter only accepts a CheckedCast (produced by load_checked -> C1 load_and_check, identity lock enforced).
Python standard library only; no rig, browser or network is used.
"""
import json
import re
from pathlib import Path

from .. import registry as REG
from ..isolation import dom_id as _dom_id

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
STYLE = "flat_cartoon_v2"
NEUTRAL = json.loads((HERE / "neutral_defaults.json").read_text(encoding="utf-8"))
PROFILE = json.loads((PKG / "animation" / "profile_flat_cartoon_v2.json").read_text(encoding="utf-8"))
PROVENANCE = json.loads((PKG / "renderers" / STYLE / "PROVENANCE.json").read_text(encoding="utf-8"))
HEX = re.compile(r"^#[0-9a-f]{6}$")

# the exact argument K.chars.actor(spec) reads (rig/10_chars.js): nothing more, nothing less
RIG_SPEC_FIELDS = ("accent", "build", "detail", "earrings", "eyeColor", "glasses", "hair", "hairColor", "legs", "lip",
                   "outfit", "pants", "shoe", "shoeType", "skin", "sleeve", "top", "under")
COLOR_FIELDS = ("accent", "eyeColor", "hairColor", "lip", "pants", "shoe", "skin", "top", "under")
FLAG_FIELDS = ("detail", "earrings", "glasses")


class AdapterError(ValueError):
    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("\n".join(self.problems))


class CheckedCast:
    """A cast that passed C1 load_and_check (schema, catalogue, policy AND identity lock). Read-only wrapper."""
    __slots__ = ("_cast", "_dir", "_locked")

    def __init__(self, cast, project_dir, _token=None):
        if _token is not _TOKEN:
            raise AdapterError("CheckedCast can only be created by load_checked() (the identity lock must be checked)")
        import copy
        self._cast, self._dir = copy.deepcopy(cast), Path(project_dir)
        # fingerprints as verified against cast.lock.json at load time; adapt() re-checks every character against
        # them, so changing the wrapped data after the lock check is caught
        self._locked = {c["id"]: REG.fingerprint(c) for c in self._cast["characters"]}

    @property
    def project(self):
        return self._cast["project"]

    @property
    def project_dir(self):
        return self._dir

    def character_ids(self):
        return [c["id"] for c in self._cast["characters"]]

    def data(self):
        import copy
        return copy.deepcopy(self._cast)


_TOKEN = object()


def load_checked(project_dir):
    """C1 load_cast + cast.lock.json check. Any problem -> AdapterError listing every C1 problem."""
    try:
        cast = REG.load_and_check(project_dir)
    except REG.CastError as e:
        raise AdapterError([f"C1 rejected the cast: {p}" for p in e.problems])
    return CheckedCast(cast, project_dir, _token=_TOKEN)


def forbidden_rig_defaults():
    """Every colour the rig falls back to (Kim identity + generic placeholders), lower-case, from PROVENANCE.json."""
    kd = PROVENANCE["kim_identity_defaults"]
    kim = {v["value"].lower() for v in kd["values"]}
    generic = {v["value"].lower() for v in kd["generic_placeholders"] if v["value"].startswith("#")}
    return kim, generic


def _hex(v, where):
    if not isinstance(v, str) or not HEX.match(v.lower()):
        raise AdapterError(f"{where}: '{v}' is not a #rrggbb colour")
    return v.lower()


def _mix(a, b, t):
    x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{max(0, min(255, int(round(p + (q - p) * t)))):02x}" for p, q in zip(x, y))


def derive_lip(skin):
    r = NEUTRAL["lip_rule"]
    return _mix(skin, r["mix_with"], r["amount"])


def adapt(cast, cid, stage=None, wardrobe=None, expr=None, *, instance=None, detail=None):
    if not isinstance(cast, CheckedCast):
        raise AdapterError("adapt() needs a CheckedCast from load_checked(): a raw dict would bypass the identity lock")
    data = cast._cast
    try:
        res = REG.resolve(data, cid, stage=stage, wardrobe=wardrobe, expr=expr)
    except REG.CastError as e:
        raise AdapterError([f"C1: {p}" for p in e.problems])
    if res["fingerprint"] != cast._locked.get(cid):
        raise AdapterError(f"'{cid}': identity differs from the one checked against cast.lock.json at load time "
                           "(the cast data was changed after load_checked) - reload it")
    if res["style"] != STYLE:
        raise AdapterError(f"'{cid}': style '{res['style']}' has no adapter here (this adapter is {STYLE})")
    where = f"{res['project']}/{cid}"
    ident, body, wd = res["identity"], res["body"], res["wardrobe"]
    kim, generic = forbidden_rig_defaults()
    spec, src, warnings = {}, {}, []

    def put(field, value, origin):
        spec[field], src[field] = value, origin

    # identity: only ever from the locked cast
    for field, key in (("skin", "skin"), ("hairColor", "hair_color"), ("eyeColor", "eye_color")):
        if key not in ident:
            raise AdapterError(f"{where}: identity.{key} missing")
        put(field, _hex(ident[key], f"{where}.identity.{key}"), "cast")
    put("glasses", 1 if "glasses" in ident.get("marks", []) else 0, "cast")

    # body (life stage)
    for k in ("build", "hair"):
        if k not in body:
            raise AdapterError(f"{where}.stages.{res['stage']}: '{k}' missing")
    if body["build"] not in PROFILE["builds"]:
        raise AdapterError(f"{where}: build '{body['build']}' unknown to the rig")
    hair = PROFILE["hair_aliases"].get(body["hair"], body["hair"])
    if hair not in PROFILE["hair"]:
        raise AdapterError(f"{where}: hair '{body['hair']}' unknown to the rig")
    put("build", body["build"], "cast")
    put("hair", hair, "cast" if hair == body["hair"] else "cast(alias)")

    # wardrobe: outfit + top required; the rest from the cast, else neutral (never the rig)
    for k in ("outfit", "top"):
        if k not in wd:
            raise AdapterError(f"{where}.wardrobe.{res['wardrobe_name']}: '{k}' missing")
    if wd["outfit"] not in PROFILE["outfits"]:
        raise AdapterError(f"{where}: outfit '{wd['outfit']}' unknown to the rig")
    put("outfit", wd["outfit"], "cast")
    put("top", _hex(wd["top"], f"{where}.wardrobe.top"), "cast")
    N = NEUTRAL["wardrobe"]
    for field, key in (("pants", "pants"), ("shoe", "shoe"), ("accent", "accent")):
        if key in wd:
            put(field, _hex(wd[key], f"{where}.wardrobe.{key}"), "cast")
        else:
            put(field, N[key], "neutral")
    for field, key, allowed in (("shoeType", "shoe_type", PROFILE["shoe_types"]), ("sleeve", "sleeve", PROFILE["sleeves"]),
                                ("legs", "legs", PROFILE["legs"])):
        v = wd.get(key, N[key])
        if v not in allowed:
            raise AdapterError(f"{where}: {key} '{v}' unknown to the rig ({', '.join(allowed)})")
        put(field, v, "cast" if key in wd else "neutral")
    if "lip" in wd:
        put("lip", _hex(wd["lip"], f"{where}.wardrobe.lip"), "cast")
    else:
        put("lip", derive_lip(spec["skin"]), "derived")
    # 'under' (blazer inner colour) is not part of the C1 schema yet: always the neutral value (see README_C3.md)
    put("under", N["under"], "neutral")
    put("earrings", 1 if "earrings" in (wd.get("accessories") or []) else 0, "cast")
    put("detail", 1 if (detail if detail is not None else NEUTRAL["placement"]["detail"]) else 0, "placement")

    validate_rig_spec(spec, where)
    for f in COLOR_FIELDS:
        v = spec[f]
        if src[f] != "cast" and (v in kim or v in generic):
            raise AdapterError(f"{where}: adapter-filled {f} {v} equals a rig default - refusing (leak)")
        if src[f] == "cast" and v in kim:
            warnings.append(f"{f} {v} equals a Kim rig default, but it is the cast's own locked choice")
    expr_name = res["expr"]
    if expr_name not in PROFILE["expressions"]:
        raise AdapterError(f"{where}: expression '{expr_name}' unknown to the rig")
    return {
        "schema": "nfp.adapter.spec/1", "style": STYLE, "project": res["project"], "character": cid,
        "stage": res["stage"], "wardrobe": res["wardrobe_name"], "expr": expr_name,
        "fingerprint": res["fingerprint"],
        "dom_id": _dom_id(res["project"], cid, instance),
        "spec": {k: spec[k] for k in RIG_SPEC_FIELDS},
        "sources": {k: src[k] for k in RIG_SPEC_FIELDS},
        "warnings": warnings,
    }


def validate_rig_spec(spec, where="spec"):
    """A complete rig spec: exactly RIG_SPEC_FIELDS, colours #rrggbb, flags 0/1, vocabulary known to the rig."""
    problems = []
    if not isinstance(spec, dict):
        raise AdapterError(f"{where}: spec must be an object")
    missing = [f for f in RIG_SPEC_FIELDS if f not in spec]
    extra = sorted(set(spec) - set(RIG_SPEC_FIELDS))
    if missing:
        problems.append(f"{where}: missing rig field(s) {', '.join(missing)} (the rig would fall back to its defaults)")
    if extra:
        problems.append(f"{where}: unknown rig field(s) {', '.join(extra)}")
    for f in COLOR_FIELDS:
        if f in spec and not (isinstance(spec[f], str) and HEX.match(spec[f])):
            problems.append(f"{where}.{f}: '{spec.get(f)}' is not a lower-case #rrggbb colour")
    for f in FLAG_FIELDS:
        if f in spec and spec[f] not in (0, 1):
            problems.append(f"{where}.{f}: must be 0 or 1")
    for f, allowed in (("build", PROFILE["builds"]), ("hair", PROFILE["hair"]), ("outfit", PROFILE["outfits"]),
                       ("shoeType", PROFILE["shoe_types"]), ("sleeve", PROFILE["sleeves"]), ("legs", PROFILE["legs"])):
        if f in spec and spec[f] not in allowed:
            problems.append(f"{where}.{f}: '{spec[f]}' unknown to the rig")
    if problems:
        raise AdapterError(problems)
    return True
