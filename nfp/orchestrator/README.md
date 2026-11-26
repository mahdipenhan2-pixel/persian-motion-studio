# NFP Production Orchestrator

Coordinates the **existing** engines of one Film production — one chapter of one project, from its files to a verified
MP4 and one QC report. It owns only: the order of the steps, their state (Resume), the cost guard and the integrated
report. Every step is the engine's own command, run unchanged in its own process; no engine's work is re-implemented
or moved here. Standard library + the tools Film already uses (Node / Playwright, HyperFrames, ffmpeg).

```
python3 nfp/orchestrator/cli.py plan      --project <dir> [--chapter id] [--build dir]
python3 nfp/orchestrator/cli.py preflight --project <dir> [--fonts dir] [--gsap gsap.min.js]
python3 nfp/orchestrator/cli.py run       --project <dir> [--fonts dir] [--gsap file] [--until step] [--from step] [--force] [--allow-network]
python3 nfp/orchestrator/cli.py status    --project <dir>
python3 nfp/orchestrator/cli.py report    --project <dir>
```
`--fonts` / `--gsap` default to `$NFP_FONTS` / `$NFP_GSAP`; the build folder defaults to run.py's
(`build/film/<name>/<chapter>`). Exit codes of `run`: 0 complete (or the part asked with `--until`), 1 failed /
preflight FAIL, 2 blocked, 3 usage, 4 complete but verify.py listed problems (see `report`).
`preflight` exits 1 on FAIL; `report` exits 0 for PASS / PASS_WITH_KNOWN_LIMITATIONS, otherwise 1. `--browser` sets the
Chromium binary HyperFrames renders with (default: `$HYPERFRAMES_BROWSER_PATH`, else the local headless shell).

## Setup (once, free)

```
pip install -r nfp/setup/requirements.txt        # faster-whisper, piper-tts, av 16.1 (av 19 breaks faster-whisper 1.2.1)
python3 nfp/setup/fetch_assets.py                # fonts, GSAP 3.12.5, Piper voices, the Whisper model -> ROOT/assets (git-ignored)
python3 nfp/setup/fetch_assets.py --check
```
`--fonts` / `--gsap` then default to `ROOT/assets/fonts` and `ROOT/assets/vendor/gsap/gsap.min.js`; the Piper provider
reads `ROOT/assets/voices/piper`. GSAP is under GreenSock's no-charge license (fetched, not committed).

## A film of several chapters (film.py)

```
python3 nfp/orchestrator/cli.py run --film film.json [--build dir]    # every chapter, then the assembled, verified film
```
`film.json` (`nfp.film.manifest/1`) lists chapters, each a standard Film project (<= 40 sentences / 180 s, the core's
limit per run): `{"schema": "nfp.film.manifest/1", "title": "...", "chapters": [{"id": "c1", "project": "ch1"}, ...]}`.
Each chapter runs exactly as above into `<build>/<id>`; then `<build>/film/film.mp4` is assembled with Film's
`assemble.py` (whole-frame audio slots, no drift at a join; video stream copy), checked with verify.py and the Output
check, and reported in `<build>/film/film_report.md` (a black frame verify.py lists only at a chapter join is that join's
fade: not applicable). A film is as long as its chapters; an unchanged film is not assembled again.

## Steps (plan.py)

| step | runs | engine | cost |
|---|---|---|---|
| audio | `run.py voice` (projects with `voice.engine`) or `run.py tts` (the core's Gemini TTS) | voice / core | network? |
| fit | `run.py fit` | film | light |
| prepare | `run.py prepare` | core | local |
| whisper | `run.py whisper` (faster-whisper) | core | heavy |
| align | `run.py align` | core | local |
| subs | `run.py subs` (only with a `subtitles` block) | subtitles | light |
| compose | `run.py compose` (Character, Timeline, Map Motion, Graphics via Film's bridges) | film | local |
| smoke | `tools/render.py smoke`: the page in Chromium, outside requests refused | orchestrator | local |
| render | `tools/render.py render`: HyperFrames 0.9.83, **npm offline** | film | heavy |
| verify | `run.py verify` (Film's verify.py) | film | local |
| output | `tools/output.py`: `nfp/output/check.py` in its own process (technical, loudness, sync, subtitle mode) | output | local |

smoke and render work on `<build>/render-copy` (story/ with the CDN GSAP tag replaced by the local copy, the same one-line
change Film's render tests make); `<build>/story` is never changed.

## Preflight (preflight.py)

Before anything runs, every document is checked with its **own engine's** public checks: Film's loader and fonts,
Character registry, Voice plan / casting, Subtitle settings, Timeline validate (files + ffprobe), Map Motion build and
Graphics prepare of every clip. Errors are attributed to their engine. Environment gaps (faster-whisper, GSAP copy,
fonts, HyperFrames cache, node, ffmpeg) are reported separately with the steps that need them. The cost forecast counts
the Gemini requests without sending one (the core's cache misses with its own hash; the Voice Engine's estimate).

## Cost guard and network

Nothing online or paid runs without `--allow-network`:
- a step preflight lists under `cost.network` (the core's Gemini TTS with uncached sentences, Gemini voices enabled in
  `voice.providers`, a HyperFrames not in the npx cache) is **blocked** with that reason;
- every step's process runs without `GEMINI_API_KEY` / `GEMINI_FREE_TIER_CONFIRMED`, with `HF_HUB_OFFLINE=1` and
  `npm_config_offline=true`. The whisper step is therefore not blocked for its possible model download: it runs offline,
  and a model not cached here makes it fail.

## State and Resume (state.py, runner.py)

`<build>/production.json` keeps every step's status, input fingerprint, executor, time and log
(`<build>/orchestrator/logs/<step>.log`). A step is up to date when it last ended `done` (or `problems`), its inputs'
fingerprint (file **contents** of the project keys, files, earlier outputs, code, fonts, GSAP its plan names) is unchanged
and its outputs exist. A failed run resumes at the first step that is not up to date. The audio step never depends on
code, so a code change never re-makes (possibly paid) audio. verify.py exits 1 when it lists problems: that step is
`problems` (it ran to the end), the run `complete_with_problems`, and the report classifies them. The output step
works the same way (its check exits 1 after writing `output_qc.json`); an output check that produced no result is
`failed` for that step only - render keeps its `done`.

## Report (report.py)

After every run: `<build>/production_report.json` and `.md`, built from the files the runner and engines wrote
(preflight, steps, Voice QC, Subtitle QC, cast report, Map Motion / Graphics QC, smoke, ffprobe, verify, output QC).
verify.py's problems are split into **known limitations** (`report.KNOWN`: documented, with their source and what a
person should look at; they do not fail), **not applicable** (caption-highlight problems in a project whose subtitle
mode draws no karaoke highlight - sentence, word, off - only when the output QC is current and the check replacing them
passed) and **new problems** (they fail).

The output QC (`output_qc.json`) is used only when it is **current**: `nfp/output/check.py is_current` compares the sha256
of story.mp4, verify.json and timing.json and the fingerprint of the project settings that decide the checks (meta, the
chapter, the subtitles block as written and as the Subtitle Engine resolves it) with what the check recorded. An output
error fails the report (a defect of the delivered file); warnings - sync offsets included, not yet validated on real
speech - are listed and do not change the verdict; no current result (not run, failed, stale) makes it INCOMPLETE,
never FAIL. Verdicts: PASS, PASS_WITH_KNOWN_LIMITATIONS, FAIL, BLOCKED, INCOMPLETE. `production_ready` is false whenever
a TEST-ONLY executor or synthetic voices made part of the build.

## Tests (offline)

```
python3 nfp/orchestrator/tests/test_orch_d0.py --fonts <woff2> --work <dir>          # process model, run.py steps by hand
python3 nfp/orchestrator/tests/test_orch_d1.py --work <dir>                          # plan
python3 nfp/orchestrator/tests/test_orch_d2.py --fonts <woff2> --gsap <js> --work <dir>  # preflight
python3 nfp/orchestrator/tests/test_orch_d3.py --fonts <woff2> --gsap <js> --work <dir>  # runner, Resume, cost guard, CLI
python3 nfp/orchestrator/tests/test_orch_d4.py --fonts <woff2> --gsap <js> --work <dir>  # smoke, REAL render, verify
python3 nfp/orchestrator/tests/test_orch_d5.py --fonts <woff2> --gsap <js> --work <dir>  # the report
python3 nfp/orchestrator/tests/test_orch_o2.py --fonts <woff2> --gsap <js> --work <dir>  # the output step
python3 nfp/orchestrator/tests/test_orch_film.py --fonts <woff2> --gsap <js> --work <dir>  # a film of chapters (assembly)
python3 nfp/orchestrator/tests/test_orch_integration.py --work <dir>   # ONE command: every engine, real speech, a 2-chapter film
```
`--work` must be outside the repository. D0-D5, O2 and the film test use synthetic voices (test tones) and a
**TEST-ONLY whisper substitute** (`tests/fixture.py`) that writes Whisper words from the synthetic voice's recorded word
times; it is injected as an executor, recorded under its own name in production.json, and makes every report
`production_ready: NO`. The integration test uses neither: real Piper speech and the real whisper step (assets of
nfp/setup/fetch_assets.py).

## Limits

- One chapter per project run; several chapters are a film (film.py).
- Real speech: local Piper voices + faster-whisper (integration test). Gemini TTS has never run (no key; off by default).
- Found by D4 and fixed in Film (`cast_plan.snap`): a shot starting exactly on a half frame (e.g. 9.35 s = frame 280.5)
  was rounded to even by `cast_plan.py` but up by the Director (`Math.round`), and the cast page threw. D4 now renders
  that Persian fixture unchanged; the rounding is tested by `nfp/film/tests/film_cast_halfframe_check.py`.
