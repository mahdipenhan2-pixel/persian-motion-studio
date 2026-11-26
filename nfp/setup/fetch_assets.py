#!/usr/bin/env python3
"""NFP - fetch the free third-party assets a production needs, into FIXED folders of the repository (git-ignored: they
are downloaded, never committed). Separate from rendering: a production never downloads anything itself.

  python3 nfp/setup/fetch_assets.py [--only fonts,gsap,piper,whisper] [--check]

  fonts    ROOT/assets/fonts/*.woff2      Inter 400/700/800, Caveat 700, Vazirmatn 400/700 (the faces nfp/film/engine/
           compose.py uses) from the npm packages @fontsource/inter, @fontsource/caveat, @fontsource/vazirmatn 5.3.0 -
           SIL Open Font License 1.1 (each package's LICENSE is copied next to the fonts). run.py's default font folder.
  gsap     ROOT/assets/vendor/gsap/gsap.min.js   GSAP 3.12.5 from the npm package gsap@3.12.5 (the version the Film page
           names). GreenSock "Standard no-charge" license (https://gsap.com/standard-license) - free to use, not an
           open-source license: fetched, not committed. The orchestrator's default --gsap.
  piper    ROOT/assets/voices/piper/<voice>.onnx(.json)   Piper voices from huggingface.co/rhasspy/piper-voices (each
           voice's MODEL_CARD, with its dataset and license, is kept next to it): fa_IR-gyro-medium, fa_IR-amir-medium
           (Persian, male), en_US-lessac-medium (English, female), en_US-ryan-medium (English, male). The Voice Engine's
           piper provider reads this folder (or $NFP_PIPER_DIR). No free Persian female Piper voice is published.
  whisper  the faster-whisper "small" model into the Hugging Face cache (the model run.py whisper uses by default).
Python packages (pip, free): see nfp/setup/requirements.txt (faster-whisper, piper-tts, av 16.1 - av 19 is not
compatible with faster-whisper 1.2.1). Every download is free; nothing is paid, no key is used.
Writes ROOT/assets/SOURCES.json: what was fetched, from where, its version / revision and sha256.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
FONT_PKGS = {"@fontsource/inter": ("5.3.0", ["inter-latin-400-normal.woff2", "inter-latin-700-normal.woff2", "inter-latin-800-normal.woff2"]),
             "@fontsource/caveat": ("5.3.0", ["caveat-latin-700-normal.woff2"]),
             "@fontsource/vazirmatn": ("5.3.0", ["vazirmatn-arabic-400-normal.woff2", "vazirmatn-arabic-700-normal.woff2"])}
GSAP = ("gsap", "3.12.5")
PIPER_REPO = "rhasspy/piper-voices"
PIPER = {"fa_IR-gyro-medium": "fa/fa_IR/gyro/medium", "fa_IR-amir-medium": "fa/fa_IR/amir/medium",
         "en_US-lessac-medium": "en/en_US/lessac/medium", "en_US-ryan-medium": "en/en_US/ryan/medium"}
WHISPER_MODEL = "small"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def npm_pack(pkg, ver, tmp):
    r = subprocess.run(["npm", "pack", f"{pkg}@{ver}", "--silent", "--pack-destination", str(tmp)], capture_output=True, text=True, cwd=tmp)
    if r.returncode != 0:
        sys.exit(f"npm pack {pkg}@{ver} failed: {r.stderr.strip()[-300:]}")
    tgz = Path(tmp) / r.stdout.strip().splitlines()[-1]
    out = Path(tmp) / tgz.stem
    with tarfile.open(tgz) as t:
        t.extractall(out, filter="data")
    return out / "package"


def fonts(src):
    d = ASSETS / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for pkg, (ver, files) in FONT_PKGS.items():
            p = npm_pack(pkg, ver, tmp)
            for f in files:
                shutil.copyfile(p / "files" / f, d / f)
                src[f"fonts/{f}"] = {"from": f"npm {pkg}@{ver}", "license": "OFL-1.1", "sha256": sha(d / f)}
            lic = next((x for x in p.iterdir() if x.name.upper().startswith("LICENSE")), None)
            if lic:
                shutil.copyfile(lic, d / f"LICENSE-{pkg.split('/')[-1]}.txt")
    print(f"fonts: {len(list(d.glob('*.woff2')))} file(s) in {d}")


def gsap(src):
    d = ASSETS / "vendor" / "gsap"
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        p = npm_pack(*GSAP, tmp)
        shutil.copyfile(p / "dist" / "gsap.min.js", d / "gsap.min.js")
        shutil.copyfile(p / "README.md", d / "README.md")
    src["vendor/gsap/gsap.min.js"] = {"from": f"npm {GSAP[0]}@{GSAP[1]}", "license": "GreenSock Standard no-charge license",
                                      "sha256": sha(d / "gsap.min.js")}
    print(f"gsap: {d / 'gsap.min.js'}")


def piper(src):
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")      # plain https download (the Xet transfer hosts are not needed)
    from huggingface_hub import hf_hub_download
    d = ASSETS / "voices" / "piper"
    d.mkdir(parents=True, exist_ok=True)
    for name, rel in PIPER.items():
        for ext in (".onnx", ".onnx.json"):
            shutil.copyfile(hf_hub_download(PIPER_REPO, f"{rel}/{name}{ext}"), d / f"{name}{ext}")
        shutil.copyfile(hf_hub_download(PIPER_REPO, f"{rel}/MODEL_CARD"), d / f"{name}.MODEL_CARD")
        src[f"voices/piper/{name}.onnx"] = {"from": f"huggingface.co/{PIPER_REPO}/{rel}", "license": f"see {name}.MODEL_CARD",
                                            "sha256": sha(d / f"{name}.onnx")}
    print(f"piper: {len(PIPER)} voice(s) in {d}")


def whisper(src):
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from faster_whisper import WhisperModel
    WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    src["whisper"] = {"from": f"huggingface.co/Systran/faster-whisper-{WHISPER_MODEL}", "license": "MIT", "where": "Hugging Face cache"}
    print(f"whisper: faster-whisper '{WHISPER_MODEL}' in the Hugging Face cache")


def check():
    want = [ASSETS / "fonts" / f for _, fs in FONT_PKGS.values() for f in fs] + [ASSETS / "vendor" / "gsap" / "gsap.min.js"] \
        + [ASSETS / "voices" / "piper" / f"{n}.onnx" for n in PIPER]
    miss = [str(p.relative_to(ROOT)) for p in want if not p.exists()]
    print("all assets present" if not miss else "missing: " + ", ".join(miss))
    return 1 if miss else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="fonts,gsap,piper,whisper")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    sp = ASSETS / "SOURCES.json"
    src = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    for k in a.only.split(","):
        {"fonts": fonts, "gsap": gsap, "piper": piper, "whisper": whisper}[k.strip()](src)
    ASSETS.mkdir(exist_ok=True)
    sp.write_text(json.dumps(src, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return check()


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    sys.exit(main())
