# Audio Sample Tool — design

Standalone build of a future Live Actions tool (`runtime: "host"`, matching the
`tts_vocal.py` pattern). Built here first; ported into `Live Actions Helper\tools\`
once the standalone UX is proven.

## Scope (v1)

17 operations across 4 categories, each a pure `run(input_path, fields, settings)`
function that shells out to ffmpeg and returns `{ok, message, path, ...}`. No
Tkinter or file-picker logic inside an op — that keeps every op reusable from a
future webview dialog or a batch runner without rewriting.

**Trim, Fades & Levels** — Trim/Cut, Auto-Trim Silence, Fade In/Out, Gain (dB),
Normalize (Peak or two-pass LUFS via `loudnorm`)

**Convert** — one combined Convert/Resample op (format, sample rate, channels,
bit depth — one ffmpeg pass; blank field = keep source)

**Reverse, Pitch & Time** — Reverse, and one combined Pitch & Time Stretch op
(semitones + tempo%, both via `rubberband` in one pass — this ffmpeg build has
`librubberband`, so no `asetrate`/`atempo` phase-artifact fallback is needed)

**Effects** (100% wet, not a dry/wet mix — utility processors, not plugin
replacements) — Echo/Delay (`aecho`), Chorus, Tremolo, Vibrato,
EQ/Tone Shape (`highpass`/`lowpass`/`bass`/`treble`), Bitcrusher/Lo-Fi (`acrusher`)

**Generators** (no input file) — Tone (`sine`), Noise (`anoisesrc`,
white/pink/brown), Silence (`anullsrc`)

## Non-negotiables (from design review)

- **Bit-depth/sample-rate preservation.** Every op except Convert probes the
  source with ffprobe and forces a matching `-c:a` (`pcm_s16le`/`pcm_s24le`/
  `pcm_s32le`/`pcm_f32le`) so ffmpeg's defaults never silently downgrade a
  24-bit source to 16-bit.
- **Two-pass loudnorm.** LUFS normalize runs a measurement pass
  (`print_format=json`) then an apply pass with `measured_*` + `linear=true`,
  not a one-pass estimate.
- **Real time-field parsing.** `parse_time()` accepts `SS(.ms)`, `MM:SS(.ms)`,
  `HH:MM:SS(.ms)` and rejects anything else with a specific error — no silent
  misinterpretation of "1:30".
- **ffmpeg stderr surfaces on failure.** Ops never return a bare "failed" —
  the last ~500 chars of stderr ride along in `message`.
- **Preview.** The result panel has Play/Stop (`winsound`, Windows-only,
  matches this project's platform) so a trim/pitch edit can be auditioned
  immediately, not just saved.
- **Output naming.** `<Op>-<SourceStem>-N.ext` (generators: `<Op>-Sample-N.ext`),
  numbered like `TTS-Sample-N.wav` already does in Live Actions.

## Files

- `theme.py` — copy of Live Actions' "Obsidian Emerald Studio" color/font
  tokens, so porting the UI later is closer to copy-paste.
- `ffmpeg_util.py` — resolve ffmpeg/ffprobe, run subprocess, probe source
  format, build preserving codec args, parse time fields, pick output paths.
- `ops/trim_levels.py`, `ops/convert.py`, `ops/pitch_time.py`,
  `ops/effects.py`, `ops/generators.py` — one module per category.
- `ops/registry.py` — flat list + category grouping for the UI.
- `audio_sample_tool.py` — Tkinter app: input file picker, grouped operation
  list (click → settings pane), Run, result row with Play/Stop/Save As/Open
  Folder.

## Explicitly deferred to v2

Batch processing (ops are already stateless file-in/file-out, so this is
additive later), dry/wet mix on effects, any filter not listed above.

## Port-to-Live-Actions notes (not decided now)

Final integration shape (webview dialog vs. a new "list" tool-screen type in
`helper.py`) is a decision for port time, once this standalone UI is used on
real samples. The `run(input_path, fields, settings)` contract will not need
to change either way.
