"""Photo-slot gate: a slot may carry a photo only with a complete, verified licence record. Returns a list of problems."""
import json
from pathlib import Path

NEED = ("author", "license", "license_url", "source_url", "retrieved", "modifications")


def check(project_dir):
    f = Path(project_dir) / "photo_slots.json"
    if not f.exists():
        return []
    bad = []
    for s in json.loads(f.read_text(encoding="utf-8"))["slots"]:
        if s.get("status") == "placeholder":
            if s.get("src"):
                bad.append(f"{s['id']}: placeholder slot must not have a src")
            continue
        if s.get("status") != "licensed":
            bad.append(f"{s['id']}: status must be 'placeholder' or 'licensed'")
            continue
        missing = [k for k in NEED if not s.get(k)]
        if missing or s.get("license_verified") is not True or not s.get("src"):
            bad.append(f"{s['id']}: licensed slot needs src, license_verified=true and {', '.join(missing) or 'all licence fields'}")
    return bad
