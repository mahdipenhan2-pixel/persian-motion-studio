# kim-docu-style: documentary motion-graphics experiment (18.5 s)

Separate from `kim-test30` and `kim-test30-cine` (both untouched; no shared engine/kit file was modified).
Script: sentences s1-s4 copied verbatim from the approved script. Voice/model/style/audio settings identical, so cached narration is reused (no Gemini/TTS request).

Style pillars shown: animated timeline + year counter (HUD, rolls forwards and backwards), stylised map motion (zoom to Los Angeles, route to Montreal),
photo-frame layouts with camera movement (push-in, tilt, parallax, sheen), transitions (camera flash, whip pan, VHS rewind, map zoom-through, slide-in),
sound design (synthesised by `docu/qa/make_sfx.py`, cues in `sfx.json`), and cartoon reconstruction where no photo exists (birth, father, divorce, wedding).

Photos: NONE. Slots P-02 (1995 trial) and P-04 (1976 Montreal) are clearly marked PLACEHOLDER. `photo_slots.json` + `docu/engine/photoslots.py` refuse any slot
that carries a photo without a complete, verified licence record (author, licence, licence URL, source URL, retrieval date, modifications).

Map: hand-simplified outlines drawn in code (Albers projection), not survey data; for style only.

Local render (no network, no Actions):
  python3 docu/qa/make_sfx.py docu/projects/kim-docu-style/sfx.json words.json narration.wav mix.wav
  python3 docu/qa/render_style_test.py kim-docu-style --words words.json --audio narration.wav --mp4 out.mp4 --sfx mix.wav --out <dir>
