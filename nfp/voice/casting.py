"""NFP Voice Engine - voice casting (nfp.voice.casting/1): which voice speaks for the narrator and for each character.

    c = load_casting("<project>/voices.cast.json")       # reads the C1 cast (read only) when cast_dir is given
    c["findings"]                                         # [{level, code, role, message}, ...]

File:
  {"schema": "nfp.voice.casting/1", "project": "<id>", "cast_dir": "<C1 cast folder, relative>",
   "rules": {"block_mismatch": false},
   "voices": {"prepared:ali": {...project voice...}},
   "narrator": {"voice": "synthetic:narrator", "style": "documentary"},
   "roles": {"lina": {"voice": "gemini:Kore", "fingerprint": "<C1 fingerprint>", "stages": {"child": "..."},
                      "expect": {"presentation": "female", "age": "adult"},
                      "override": {"reason": "..."}}}}

Suitability (the voice against what the character is):
  * what the character is comes from 'expect' when given, otherwise from the C1 build of each stage
    (woman -> female adult, man -> male adult, teen -> teen, child / baby -> child; teen / child: any presentation);
  * a mismatch of presentation or age is a WARNING by default;
  * in that default mode, 'override' with a non-empty 'reason' turns it into a recorded OVERRIDE (no warning);
  * with rules.block_mismatch: true every mismatch is a BLOCK (an error that stops the plan) - ABSOLUTE: an override
    does not lift it (the override is still validated: a reason is required);
  * a voice marked verified: false is always a warning (its attributes are not confirmed).
Integrity problems are ERRORS whatever the rules: unknown voice, unknown character, override without reason, a
fingerprint that differs from the C1 cast.lock.json (the character changed since it was cast - recast deliberately).
C1 is only read (registry.load_and_check: schema + identity lock); nothing of C1 is changed.
"""
import json
import re
import sys
from pathlib import Path

from .registry import VoiceError, load_registry

SCHEMA = "nfp.voice.casting/1"
TOP = {"schema", "project", "cast_dir", "rules", "voices", "narrator", "roles"}
ROLE_KEYS = {"voice", "fingerprint", "stages", "expect", "override"}
RULE_KEYS = {"block_mismatch"}
ROLE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
NARRATOR = "narrator"
BUILD_EXPECT = {"woman": {"presentation": "female", "age": "adult"}, "man": {"presentation": "male", "age": "adult"},
                "teen": {"presentation": None, "age": "teen"}, "child": {"presentation": None, "age": "child"},
                "baby": {"presentation": None, "age": "child"}, "kid": {"presentation": None, "age": "child"},
                "adult": {"presentation": "male", "age": "adult"}}


def _c1():
    nfp = Path(__file__).resolve().parent.parent
    if str(nfp) not in sys.path:
        sys.path.insert(0, str(nfp))
    from character import registry as REG          # C1, read only
    return REG


def finding(level, code, role, message):
    return {"level": level, "code": code, "role": role, "message": message}


def suitability(role, voice_id, voice, expect, override, block):
    """Findings for one (role, voice) pair against what the character is."""
    out, mism = [], []
    if expect.get("presentation") and voice["presentation"] != expect["presentation"]:
        mism.append(f"a {voice['presentation']} voice for a {expect['presentation']} character")
    if expect.get("age") and voice["age"] != expect["age"]:
        mism.append(f"an {voice['age']} voice for a {expect['age']} character" if voice["age"][0] in "aeiou"
                    else f"a {voice['age']} voice for a {expect['age']} character")
    for m in mism:
        if block:                       # project rule: absolute - an override cannot lift it
            out.append(finding("block", "voice_mismatch", role, f"'{voice_id}': {m} (blocked by rules.block_mismatch; "
                                                                "an override does not lift this rule - choose a fitting voice "
                                                                "or turn the rule off for the project)"))
        elif override:
            out.append(finding("override", "voice_mismatch_overridden", role, f"'{voice_id}': {m} - overridden: {override}"))
        else:
            out.append(finding("warning", "voice_mismatch", role, f"'{voice_id}': {m}"))
    if not voice["verified"]:
        out.append(finding("warning", "unverified_voice", role, f"'{voice_id}': its attributes are not verified yet "
                                                                f"({voice.get('source', 'no source')})"))
    return out


def load_casting(path):
    """Validated casting: {project, rules, registry, narrator, roles, findings, path}. VoiceError on errors/blocks."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise VoiceError(f"casting: cannot read {path}: {e}")
    errors, findings = [], []
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise VoiceError(f"casting: schema must be '{SCHEMA}'")
    extra = sorted(set(data) - TOP)
    if extra:
        errors.append(f"casting: unknown field(s) {', '.join(extra)}")
    rules = data.get("rules") or {}
    if not isinstance(rules, dict) or set(rules) - RULE_KEYS or not isinstance(rules.get("block_mismatch", False), bool):
        errors.append(f"casting.rules: only {sorted(RULE_KEYS)} (true/false) is allowed")
        rules = {}
    block = bool(rules.get("block_mismatch", False))
    reg = load_registry(extra=data.get("voices") or {})

    # C1 cast (read only): characters, their stages / builds and locked fingerprints
    chars, locked = {}, {}
    if data.get("cast_dir"):
        d = data["cast_dir"]
        if not isinstance(d, str) or Path(d).is_absolute() or ".." in Path(d).parts:
            raise VoiceError("casting.cast_dir must be a relative folder next to the casting file")
        REG = _c1()
        try:
            cast = REG.load_and_check(path.parent / d)      # schema + identity lock (cast.lock.json)
        except REG.CastError as e:
            raise VoiceError([f"casting: the C1 cast was refused: {p}" for p in e.problems])
        chars = {c["id"]: c for c in cast["characters"]}
        locked = {c["id"]: REG.fingerprint(c) for c in cast["characters"]}

    nar = data.get("narrator")
    if not isinstance(nar, dict) or not isinstance(nar.get("voice"), str):
        errors.append("casting.narrator: {\"voice\": \"<voice id>\"} is required")
        nar = None
    elif not reg.has(nar["voice"]):
        errors.append(f"casting.narrator: voice '{nar['voice']}' is not in the registry")
    elif not reg.get(nar["voice"])["verified"]:
        findings.append(finding("warning", "unverified_voice", NARRATOR, f"'{nar['voice']}': its attributes are not verified yet"))

    roles = data.get("roles") or {}
    if not isinstance(roles, dict):
        raise VoiceError("casting.roles must be an object")
    out_roles = {}
    for rid, r in roles.items():
        w = f"casting.roles.{rid}"
        if not ROLE_ID.match(rid) or rid == NARRATOR:
            errors.append(f"{w}: a role id must match {ROLE_ID.pattern} and cannot be '{NARRATOR}'")
            continue
        if not isinstance(r, dict):
            errors.append(f"{w} must be an object")
            continue
        extra = sorted(set(r) - ROLE_KEYS)
        if extra:
            errors.append(f"{w}: unknown field(s) {', '.join(extra)}")
        if data.get("cast_dir") and rid not in chars:
            errors.append(f"{w}: '{rid}' is not a character of the C1 cast ({', '.join(sorted(chars))})")
            continue
        if data.get("cast_dir"):
            if r.get("fingerprint") != locked[rid]:
                errors.append(f"{w}: fingerprint {str(r.get('fingerprint'))[:12]} differs from the C1 lock "
                              f"{locked[rid][:12]}: the character changed since it was cast - review and recast it")
        ov = r.get("override")
        reason = None
        if ov is not None:
            reason = ov.get("reason") if isinstance(ov, dict) else None
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{w}.override: a non-empty 'reason' is required")
                reason = None
        voices = {"*": r.get("voice")}
        for st, vid in (r.get("stages") or {}).items():
            if data.get("cast_dir") and st not in chars[rid]["stages"]:
                errors.append(f"{w}.stages: '{st}' is not a stage of '{rid}'")
                continue                                              # reported; never used further
            voices[st] = vid
        if not isinstance(voices["*"], str):
            errors.append(f"{w}: 'voice' is required")
            continue
        exp_given = r.get("expect")
        if exp_given is not None and (not isinstance(exp_given, dict) or set(exp_given) - {"presentation", "age"}):
            errors.append(f"{w}.expect: only presentation / age")
            exp_given = None
        for st, vid in voices.items():
            if not reg.has(vid):
                errors.append(f"{w}: voice '{vid}' is not in the registry")
                continue
            if exp_given:
                exp = exp_given
            elif data.get("cast_dir"):
                # the default voice ('*') speaks for every stage without a voice of its own
                sts = [st] if st != "*" else [s for s in chars[rid]["stages"] if s not in voices]
                if not sts:
                    continue                                                 # every stage has its own voice
                exps = [BUILD_EXPECT.get(chars[rid]["stages"][s]["build"], {}) for s in sts]
                if all(e == exps[0] for e in exps):
                    exp = exps[0]
                else:
                    exp = {}
                    findings.append(finding("warning", "stages_differ", rid, f"stages {', '.join(sts)} differ in age / "
                                            "presentation but share one voice; give them per-stage voices"))
            else:
                exp = {}
            findings += suitability(rid if st == "*" else f"{rid}@{st}", vid, reg.get(vid), exp, reason, block)
        out_roles[rid] = {"voice": voices["*"], "stages": {k: v for k, v in voices.items() if k != "*"},
                          "override": reason, "fingerprint": r.get("fingerprint")}
    blocks = [f["message"] for f in findings if f["level"] == "block"]
    if errors or blocks:
        raise VoiceError(errors + [f"BLOCK {f['role']}: {f['message']}" for f in findings if f["level"] == "block"])
    return {"schema": SCHEMA, "project": data.get("project"), "rules": {"block_mismatch": block}, "registry": reg,
            "narrator": nar, "roles": out_roles, "findings": findings, "path": str(path), "raw": data}
