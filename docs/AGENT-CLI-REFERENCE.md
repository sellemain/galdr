# galdr agent CLI reference

Music perception SDK for AI agents — turns tracks into listener-state traces: attention, pressure, silence, tempo confidence, harmony, melody, overtones.

## Install

Preferred trusted sources:
- PyPI: <https://pypi.org/project/galdr/>
- Source: <https://github.com/sellemain/galdr>

```bash
pip install galdr

# or from source:
git clone https://github.com/sellemain/galdr.git
cd galdr
pip install -e .
```

Agent skills and prompt references teach an agent how to use galdr; they do not install the `galdr` command itself. Check that the CLI is available with `galdr --version`. If provenance matters, verify the PyPI metadata or install from the source repository above before running it.

## Commands

### listen — full analysis pipeline

> The analysis command is `galdr listen`, not `galdr analyze`.

```bash
galdr listen <audio.wav> [--name NAME] [--analysis-dir DIR]
```

Outputs to `<analysis-dir>/<track-name>/`:
- `*_report.json` — pulse confidence, pulse, weight arc, texture, dominant chroma
- `*_perception.json` — attention-grip stream, silences, attention shift events, pressure summary
- `*_stream.json` — per-hop time series (attention, pressure, pressure_state, loudness_lufs, pressure_lufs_delta, texture, pattern, silence)
- `*_harmony.json` — harmonic pull, tonal anchor evidence, chroma motion, internal tonal-center evidence
- `*_melody.json` — foreground line, pitch contour, internal range/center evidence
- `*_overtone.json` — resonance/grain evidence: overtone fit, overtone density, inharmonicity

Run only specific modules:
```bash
galdr listen track.wav --only perceive,report   # skip harmony, melody, overtone
galdr listen track.wav --skip overtone          # run all except overtone
```

### Second-by-second analysis (for another AI)

Galdr is strongest when read as a **time-ordered listener-state trace**. The stream is the primary evidence. Whole-track interpretation comes after walking the track through time.

Start with:
- `*_stream.json`
- `*_perception.json`
- `docs/PERCEPTION-MODEL.md`

Useful extras:
- `*_harmony_stream.json`
- `*_melody_stream.json`
- `*_overtone_stream.json`
- `*_report.json`
- `galdr assemble <slug> --mode blind`

Recommended reading order:
1. Read `PERCEPTION-MODEL.md` first.
2. Read `*_stream.json` as the main evidence surface.
3. Walk the track in order.
4. Mark transitions: silence, re-entry, pattern breaks, attention shifts, pressure-motion changes, harmonic movement.
5. Translate pressure fields into listening language: comes forward, holds, releases, empties. Do not quote LUFS values in experience prose.
6. Compress upward into a larger arc only after the timed pass.

Do not:
- default to a whole-song mood summary first
- treat summary metrics as more important than the stream
- ignore silence/re-entry structure
- overclaim emotion from structure alone
- quote loudness/LUFS readings as if they were the experience
- decorate prior knowledge of the song instead of reading the evidence

Minimum practical workflow:
```bash
galdr listen track.wav --name my-track
jq '.[0:12]' analysis/my-track/my-track_stream.json
jq '.summary' analysis/my-track/my-track_perception.json
galdr assemble my-track --mode blind > prompt.txt
```

### Optional: send an assembled prompt to another model

Only do this if the operator explicitly wants model-written prose. Review the assembled prompt before piping it to `claude`, `llm`, or any other external model endpoint.

```bash
galdr assemble my-track --template arc --mode full | claude
galdr assemble my-track --template arc --mode full | llm
```

### compare — contrast two analyzed tracks

```bash
galdr compare <track_a_name> <track_b_name> [--analysis-dir DIR]
```

Both tracks must already be analyzed. Outputs comparison across all shared metrics.

### catalog — manage the track index

```bash
galdr catalog                      # list all indexed tracks
galdr catalog --track NAME         # summary card for one track
galdr catalog --rebuild            # rebuild index from analysis files
```

Catalog state lives at `~/.galdr/catalog_state.json`.

### assemble — build a model prompt from analysis data

```bash
galdr assemble <track-name> [--template arc|first|none] [--mode blind|lyrics|context|full]
```

Build a model prompt from analysis data. Template controls voice/format instructions; mode controls which data sections to include.

### fetch — download audio and context

```bash
galdr fetch <url> [--name NAME] [--analyze]
```

Download audio and context via yt-dlp. With `--analyze`, runs the full analysis pipeline after download. Audio and captions are downloaded separately, so caption failures do not block audio analysis.

### frames — extract video frames at structural moments

```bash
galdr frames <track-name>
```

Extract and describe video frames at structural moments (pattern breaks, silences, attention shifts).

### doctor / update-deps — YouTube download health

```bash
galdr doctor
galdr update-deps
```

Use `galdr doctor` when YouTube download behavior is flaky. It reports the active Python executable, yt-dlp command/version, ffmpeg/ffprobe, JavaScript runtimes, and impersonation support. Use `galdr update-deps` to upgrade `yt-dlp[default,curl-cffi]` in the same Python environment galdr is using.

## Interpreting Output

The metrics describe a listener's perceptual state through time — not the audio file as an object. See `docs/GETTING-STARTED.md` for metric definitions and `docs/PERCEPTION-MODEL.md` for worked examples.

The question after any analysis: **What is this music doing to the listener, and how does the music accomplish that?**
