"""
NFP Character Engine - registry (C1: data layer, independent of any renderer / rig).

A project's characters live in <project>/cast.json (schema nfp.cast/1, see schema/cast.v1.json) and their locked
identities in <project>/cast.lock.json. This module:

  load_cast(project_dir)          read + validate (schema, style catalogue, cross-references, policy)
  fingerprint(character)          SHA-256 of the canonical IDENTITY (+ style) - what must never drift
  check_lock(cast, lock)          every character's identity matches its locked fingerprint
  make_lock(cast)                 the lock content (written only on an explicit request, see cli.py)
  resolve(cast, id, stage, wardrobe, expr)   renderer-neutral spec: identity + stage + wardrobe + expression
  validate_usage(cast, usage)     a scene/shot reference: may pick stage/wardrobe/expr, can never touch identity

Python standard library only. Nothing is downloaded; no renderer is loaded.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

from .policy import check_policy

HERE = Path(__file__).resolve().parent
PARTS_DIR = HERE / "parts"
SCHEMA_ID = "nfp.cast/1"
LOCK_SCHEMA_ID = "nfp.cast.lock/1"
FINGERPRINT_VERSION = 1

ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SLOT_RE = re.compile(r"^[a-z][a-z0-9_-]{0,23}$")
STYLE_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DERIVED_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}/[a-z][a-z0-9-]{0,39}$")

TOP_KEYS = {"schema", "project", "characters"}
CHAR_KEYS = {"id", "display_name", "role", "style", "derived_from", "identity", "stages", "wardrobe", "defaults", "provenance"}
CHAR_REQUIRED = {"id", "display_name", "style", "identity", "stages", "wardrobe", "defaults", "provenance"}
IDENTITY_KEYS = {"skin", "hair_color", "eye_color", "face", "marks"}
IDENTITY_REQUIRED = {"skin", "hair_color", "eye_color"}
FACE_KEYS = {"shape", "brows", "nose"}
STAGE_KEYS = {"build", "hair"}
WARDROBE_KEYS = {"outfit", "top", "pants", "shoe", "shoe_type", "sleeve", "legs", "accent", "lip", "accessories"}
WARDROBE_REQUIRED = {"outfit", "top"}
DEFAULT_KEYS = {"stage", "wardrobe", "expr"}
PROVENANCE_KEYS = {"real_person", "depiction", "sources", "notes"}
USAGE_KEYS = {"character", "stage", "wardrobe", "expr"}
MAX_CHARACTERS, MAX_STAGES, MAX_WARDROBE, MAX_LIST = 40, 12, 24, 8


class CastError(ValueError):
    """Raised with every problem found (one per line), so a cast can be fixed in one pass."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


# ------------------------------------------------------------------------------------------------ catalogues
_CATALOGUES = {}


def catalogue(style):
    if style not in _CATALOGUES:
        p = PARTS_DIR / f"{style}.json"
        if not STYLE_RE.match(str(style)) or not p.is_file():
            return None
        _CATALOGUES[style] = json.loads(p.read_text(encoding="utf-8"))
    return _CATALOGUES[style]


def available_styles():
    return sorted(p.stem for p in PARTS_DIR.glob("*.json"))


# ------------------------------------------------------------------------------------------------ validation
class _V:
    def __init__(self):
        self.problems = []

    def err(self, where, msg):
        self.problems.append(f"{where}: {msg}")

    def obj(self, v, where):
        if not isinstance(v, dict):
            self.err(where, "must be an object")
            return False
        return True

    def keys(self, d, allowed, required, where):
        for k in sorted(set(d) - allowed):
            self.err(where, f"unknown field '{k}' (allowed: {', '.join(sorted(allowed))})")
        for k in sorted(required - set(d)):
            self.err(where, f"missing required field '{k}'")

    def text(self, v, where, lo, hi):
        if not isinstance(v, str) or not lo <= len(v.strip()) <= hi or (lo and not v.strip()):
            self.err(where, f"must be a string of {lo}-{hi} characters")
            return False
        return True

    def hexc(self, v, where):
        if not isinstance(v, str) or not HEX_RE.match(v):
            self.err(where, "must be a #rrggbb colour")

    def enum(self, v, allowed, where, what):
        if v not in allowed:
            self.err(where, f"'{v}' is not a {what} of this style (allowed: {', '.join(allowed)})")

    def strlist(self, v, allowed, where, what):
        if not isinstance(v, list) or len(v) > MAX_LIST or len(set(map(str, v))) != len(v):
            self.err(where, f"must be a list of at most {MAX_LIST} different {what}")
            return
        for i, x in enumerate(v):
            self.enum(x, allowed, f"{where}[{i}]", what)


def _validate_character(V, c, where):
    if not V.obj(c, where):
        return
    V.keys(c, CHAR_KEYS, CHAR_REQUIRED, where)
    if not (isinstance(c.get("id"), str) and ID_RE.match(c["id"])):
        V.err(f"{where}.id", "must match [a-z][a-z0-9-]{0,39}")
    if "display_name" in c:
        V.text(c["display_name"], f"{where}.display_name", 1, 40)
    if "role" in c:
        V.text(c["role"], f"{where}.role", 0, 40)
    if "derived_from" in c and not (isinstance(c["derived_from"], str) and DERIVED_RE.match(c["derived_from"])):
        V.err(f"{where}.derived_from", "must be '<project>/<character id>'")
    style = c.get("style")
    cat = catalogue(style) if isinstance(style, str) else None
    if cat is None:
        V.err(f"{where}.style", f"unknown style '{style}' (available: {', '.join(available_styles())})")

    ident = c.get("identity")
    if V.obj(ident, f"{where}.identity"):
        V.keys(ident, IDENTITY_KEYS, IDENTITY_REQUIRED, f"{where}.identity")
        for k in ("skin", "hair_color", "eye_color"):
            if k in ident:
                V.hexc(ident[k], f"{where}.identity.{k}")
        if "face" in ident and V.obj(ident["face"], f"{where}.identity.face"):
            V.keys(ident["face"], FACE_KEYS, set(), f"{where}.identity.face")
            if cat:
                for k in FACE_KEYS & set(ident["face"]):
                    V.enum(ident["face"][k], cat["face"][k], f"{where}.identity.face.{k}", f"face {k}")
        if "marks" in ident and cat:
            V.strlist(ident["marks"], cat["marks"], f"{where}.identity.marks", "marks")

    stages = c.get("stages")
    if V.obj(stages, f"{where}.stages"):
        if not 1 <= len(stages) <= MAX_STAGES:
            V.err(f"{where}.stages", f"must have 1-{MAX_STAGES} stages")
        for name, st in stages.items():
            w = f"{where}.stages.{name}"
            if not SLOT_RE.match(name):
                V.err(w, "stage name must match [a-z][a-z0-9_-]{0,23}")
            if V.obj(st, w):
                V.keys(st, STAGE_KEYS, STAGE_KEYS, w)
                if cat:
                    if "build" in st:
                        V.enum(st["build"], cat["builds"], f"{w}.build", "build")
                    if "hair" in st:
                        V.enum(st["hair"], cat["hair"], f"{w}.hair", "hair style")

    ward = c.get("wardrobe")
    if V.obj(ward, f"{where}.wardrobe"):
        if not 1 <= len(ward) <= MAX_WARDROBE:
            V.err(f"{where}.wardrobe", f"must have 1-{MAX_WARDROBE} outfits")
        for name, o in ward.items():
            w = f"{where}.wardrobe.{name}"
            if not SLOT_RE.match(name):
                V.err(w, "wardrobe name must match [a-z][a-z0-9_-]{0,23}")
            if V.obj(o, w):
                V.keys(o, WARDROBE_KEYS, WARDROBE_REQUIRED, w)
                for k in ("top", "pants", "shoe", "accent", "lip"):
                    if k in o:
                        V.hexc(o[k], f"{w}.{k}")
                if cat:
                    if "outfit" in o:
                        V.enum(o["outfit"], cat["outfits"], f"{w}.outfit", "outfit")
                    for k, key in (("shoe_type", "shoe_types"), ("sleeve", "sleeves"), ("legs", "legs")):
                        if k in o:
                            V.enum(o[k], cat[key], f"{w}.{k}", k.replace("_", " "))
                    if "accessories" in o:
                        V.strlist(o["accessories"], cat["accessories"], f"{w}.accessories", "accessories")

    d = c.get("defaults")
    if V.obj(d, f"{where}.defaults"):
        V.keys(d, DEFAULT_KEYS, DEFAULT_KEYS, f"{where}.defaults")
        if isinstance(stages, dict) and "stage" in d and d["stage"] not in stages:
            V.err(f"{where}.defaults.stage", f"'{d['stage']}' is not one of this character's stages")
        if isinstance(ward, dict) and "wardrobe" in d and d["wardrobe"] not in ward:
            V.err(f"{where}.defaults.wardrobe", f"'{d['wardrobe']}' is not one of this character's outfits")
        if cat and "expr" in d:
            V.enum(d["expr"], cat["expressions"], f"{where}.defaults.expr", "expression")

    prov = c.get("provenance")
    if V.obj(prov, f"{where}.provenance"):
        V.keys(prov, PROVENANCE_KEYS, {"real_person"}, f"{where}.provenance")
        if "real_person" in prov and not isinstance(prov["real_person"], bool):
            V.err(f"{where}.provenance.real_person", "must be true or false")


def validate_cast(data, project=None):
    """Return the validated cast (deep copy). Raise CastError listing every problem."""
    V = _V()
    if not V.obj(data, "cast"):
        raise CastError(V.problems)
    V.keys(data, TOP_KEYS, TOP_KEYS, "cast")
    if data.get("schema") != SCHEMA_ID:
        V.err("cast.schema", f"must be '{SCHEMA_ID}'")
    pid = data.get("project")
    if not (isinstance(pid, str) and PROJECT_RE.match(pid)):
        V.err("cast.project", "must match [a-z0-9][a-z0-9-]{0,63}")
    elif project is not None and pid != project:
        V.err("cast.project", f"is '{pid}' but the file belongs to project '{project}'")
    chars = data.get("characters")
    if not isinstance(chars, list) or not 1 <= len(chars) <= MAX_CHARACTERS:
        V.err("cast.characters", f"must be a list of 1-{MAX_CHARACTERS} characters")
        chars = []
    seen = set()
    for i, c in enumerate(chars):
        _validate_character(V, c, f"characters[{i}]")
        cid = c.get("id") if isinstance(c, dict) else None
        if isinstance(cid, str):
            if cid in seen:
                V.err(f"characters[{i}].id", f"duplicate id '{cid}' in this project")
            seen.add(cid)
    if not V.problems:
        for i, c in enumerate(chars):
            for p in check_policy(c, catalogue(c["style"])):
                V.err(f"characters[{i}] ('{c['id']}')", p)
    if V.problems:
        raise CastError(V.problems)
    return copy.deepcopy(data)


def load_cast(project_dir):
    """Read <project_dir>/cast.json; the project id must equal the folder name."""
    project_dir = Path(project_dir)
    p = project_dir / "cast.json"
    if not p.is_file():
        raise CastError([f"{p}: not found"])
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CastError([f"{p}: invalid JSON ({e})"])
    return validate_cast(data, project=project_dir.name)


# ------------------------------------------------------------------------------------------------ identity
def canonical_identity(c):
    """Everything that makes a character recognisable, normalised (case, order) - and nothing else."""
    ident = c["identity"]
    out = {"skin": ident["skin"].lower(), "hair_color": ident["hair_color"].lower(),
           "eye_color": ident["eye_color"].lower(), "style": c["style"]}
    face = ident.get("face") or {}
    out["face"] = {k: face.get(k, "default") for k in sorted(FACE_KEYS)}
    out["marks"] = sorted(ident.get("marks") or [])
    return out


def fingerprint(c):
    blob = json.dumps({"v": FINGERPRINT_VERSION, "identity": canonical_identity(c)}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def make_lock(cast):
    return {"schema": LOCK_SCHEMA_ID, "project": cast["project"],
            "characters": {c["id"]: fingerprint(c) for c in sorted(cast["characters"], key=lambda c: c["id"])}}


def check_lock(cast, lock):
    """Return a list of problems (empty = every identity matches its lock)."""
    problems = []
    if not isinstance(lock, dict) or lock.get("schema") != LOCK_SCHEMA_ID:
        return [f"cast.lock.json: schema must be '{LOCK_SCHEMA_ID}'"]
    if lock.get("project") != cast["project"]:
        problems.append(f"cast.lock.json: belongs to project '{lock.get('project')}', not '{cast['project']}'")
    locked = lock.get("characters") if isinstance(lock.get("characters"), dict) else {}
    current = {c["id"]: fingerprint(c) for c in cast["characters"]}
    for cid in sorted(current):
        if cid not in locked:
            problems.append(f"'{cid}': not in cast.lock.json (new character: lock it deliberately)")
        elif locked[cid] != current[cid]:
            problems.append(f"'{cid}': identity changed since it was locked "
                            f"({locked[cid][:12]} -> {current[cid][:12]}); appearance must not drift")
    for cid in sorted(set(locked) - set(current)):
        problems.append(f"'{cid}': locked but no longer in cast.json")
    return problems


def load_and_check(project_dir):
    """load_cast + lock check: the normal entry point for a build. Raises CastError on any problem."""
    project_dir = Path(project_dir)
    cast = load_cast(project_dir)
    lp = project_dir / "cast.lock.json"
    if not lp.is_file():
        raise CastError([f"{lp}: missing (create it deliberately: python3 nfp/character/cli.py lock <project> --write)"])
    try:
        lock = json.loads(lp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise CastError([f"{lp}: invalid JSON ({e})"])
    problems = check_lock(cast, lock)
    if problems:
        raise CastError(problems)
    return cast


# ------------------------------------------------------------------------------------------------ usage
def character(cast, cid):
    for c in cast["characters"]:
        if c["id"] == cid:
            return c
    raise CastError([f"unknown character '{cid}' (cast: {', '.join(c['id'] for c in cast['characters'])})"])


def validate_usage(cast, usage, where="usage"):
    """A scene/shot reference. Anything outside character/stage/wardrobe/expr (e.g. skin) is refused."""
    V = _V()
    if not V.obj(usage, where):
        raise CastError(V.problems)
    extra = sorted(set(usage) - USAGE_KEYS)
    for k in extra:
        if k in IDENTITY_KEYS or k in {"hairColor", "eyeColor", "hair_colour"}:
            V.err(where, f"'{k}' is part of the locked identity and cannot be overridden in a scene")
        else:
            V.err(where, f"unknown field '{k}' (allowed: {', '.join(sorted(USAGE_KEYS))})")
    if "character" not in usage:
        V.err(where, "missing 'character'")
        raise CastError(V.problems)
    try:
        c = character(cast, usage["character"])
    except CastError as e:
        raise CastError([f"{where}: {p}" for p in e.problems] + V.problems)
    if "stage" in usage and usage["stage"] not in c["stages"]:
        V.err(f"{where}.stage", f"'{usage['stage']}' is not a stage of '{c['id']}' ({', '.join(c['stages'])})")
    if "wardrobe" in usage and usage["wardrobe"] not in c["wardrobe"]:
        V.err(f"{where}.wardrobe", f"'{usage['wardrobe']}' is not an outfit of '{c['id']}' ({', '.join(c['wardrobe'])})")
    if "expr" in usage:
        V.enum(usage["expr"], catalogue(c["style"])["expressions"], f"{where}.expr", "expression")
    if V.problems:
        raise CastError(V.problems)
    return c


def resolve(cast, cid, stage=None, wardrobe=None, expr=None):
    """Renderer-neutral spec. Identity always comes from the cast - a scene can never change it."""
    usage = {"character": cid}
    for k, v in (("stage", stage), ("wardrobe", wardrobe), ("expr", expr)):
        if v is not None:
            usage[k] = v
    c = validate_usage(cast, usage)
    st = stage or c["defaults"]["stage"]
    wd = wardrobe or c["defaults"]["wardrobe"]
    return {
        "character": c["id"], "project": cast["project"], "style": c["style"],
        "fingerprint": fingerprint(c),
        "identity": canonical_identity(c),
        "stage": st, "body": copy.deepcopy(c["stages"][st]),
        "wardrobe_name": wd, "wardrobe": copy.deepcopy(c["wardrobe"][wd]),
        "expr": expr or c["defaults"]["expr"],
    }
