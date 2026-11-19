# Locked core (Phase 0)

These files are the proven Stage 2 pipeline. **Do not edit them.** The Studio layer (`studio/`) reuses them
without changing a byte, and `studio/tests/test_studio.py` fails if any of them changes
(hashes in `studio/CORE_HASHES.json`).

- `scripts/story_stage2.py`: Gemini TTS (cached), audio timeline, Persian-safe alignment, verify
- `scripts/stage2_whisper.py`: per-sentence word timestamps
- `scripts/test_stage2_alignment.py`: offline alignment tests
- `story/template.stage2.html`, `story/config.stage2.json`, `story/script.stage2.json`
- `.github/workflows/story-stage2.yml`

Rule: new behaviour goes into `studio/` (new files). If the core really must change, write the reason here first,
change one thing, run both workflows, and only then update `studio/CORE_HASHES.json`.

`story_stage0.py` / `story_stage1.py` and their files are left as they are and are not part of the core.
