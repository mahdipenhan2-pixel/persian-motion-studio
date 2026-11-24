"""NFP Studio - Character layer (C4): optional, additive characters for Studio 9:16 pages.
A project without character fields is never touched (run_cast.py output == run_motion.py output, byte for byte).
Uses the Character Engine in nfp/character (C1 data + lock, C2 rig, C3 planner/runtime) without modifying it."""
import sys
from pathlib import Path

_NFP = Path(__file__).resolve().parents[3] / "nfp"
if str(_NFP) not in sys.path:
    sys.path.insert(0, str(_NFP))          # 'character' = nfp/character (read-only use)
