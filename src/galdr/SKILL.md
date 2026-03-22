---
name: galdr
description: Analyze audio tracks to understand musical perception — how listener attention engages, holds, and dissolves over time. Use when asked to analyze a music or audio file, describe what a track does to a listener, compare two tracks, or build a catalog of perceptual data. Outputs momentum, breath, hp_balance, pattern_lock, temperament_alignment, and silence events as time-series data. Requires galdr installed (pip install galdr or pip install -e . from source). NOT for: audio editing, format conversion, or tasks that don't involve perceptual analysis.
---

# galdr

Models a listener's attention as music plays — how engagement builds, holds, and dissolves. Produces time-series perception data, harmony analysis, melody contour, and overtone structure.

## Install

```bash
pip install galdr
# or from source:
pip install -e /path/to/galdr
```

## Commands

### listen — full analysis pipeline

```bash
galdr listen <audio.wav> [--name NAME] [--analysis-dir DIR]
```

Outputs to `<analysis-dir>/<track-name>/`:
- `*_report.json` — tempo, beat regularity, energy arc, texture, dominant chroma
- `*_perception.json` — momentum stream, silences, `listener_locked`/`listener_floating` events, summary
- `*_stream.json` — per-hop time series (momentum, breath, hp_balance, pattern_lock, silence)
- `*_harmony.json` — temperament_alignment, tension, tonal center, major/minor
- `*_melody.json` — pitch range, center note, vocal presence
- `*_overtone.json` — series fit, richness, inharmonicity

Run only specific modules:
```bash
galdr listen track.wav --only perceive,report   # skip harmony, melody, overtone
galdr listen track.wav --skip overtone          # run all except overtone
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

Download audio and context via yt-dlp. With `--analyze`, runs the full analysis pipeline after download.

### frames — extract video frames at structural moments

```bash
galdr frames <track-name>
```

Extract and describe video frames at structural moments (pattern breaks, silences, momentum shifts).

## Interpreting Output

The metrics describe a listener's perceptual state through time — not the audio file as an object. See `docs/GETTING-STARTED.md` for metric definitions and `docs/PERCEPTION-MODEL.md` for worked examples.

The question after any analysis: **What is this music doing to the listener, and how does the music accomplish that?**
