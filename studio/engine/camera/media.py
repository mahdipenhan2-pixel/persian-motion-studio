"""Copy validated media files next to the composed page (story/assets/media/). Nothing is downloaded."""
import hashlib
import re
import shutil
from pathlib import Path


def copy_media(plan, story_dir):
    """Return {scene_id: relative src} after copying each validated file once (name = content hash + safe stem)."""
    out_dir = Path(story_dir) / "assets" / "media"
    result = {}
    for sc in plan["scenes"]:
        m = sc["media"]
        if m is None:
            continue
        src = Path(m["path"])
        data = src.read_bytes()
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", src.stem)[:40] or "media"
        name = f"{hashlib.sha256(data).hexdigest()[:12]}-{stem}{src.suffix.lower()}"
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / name
        if not dst.exists():
            shutil.copyfile(src, dst)
        result[sc["id"]] = f"assets/media/{name}"
    return result
