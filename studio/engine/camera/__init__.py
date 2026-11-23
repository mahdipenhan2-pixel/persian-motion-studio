"""
NFP Studio - Camera Motion Engine (additive module).

Nothing in this package edits an existing Studio file. studio/engine/run_motion.py composes a project with the
unchanged studio/engine/compose.py and then adds camera motion, media frames and scene transitions to the
generated index.html at fixed anchor points (camera/inject.py).

Layout rule inherited from the locked Stage 2 verify step: nothing except captions may ever appear in the caption
band y 560-1360. Media frames stay outside it and every scene-graphics move is checked mathematically.
"""
