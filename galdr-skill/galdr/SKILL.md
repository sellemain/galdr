---
name: galdr
description: "Analyze music and generate impressionistic listening experiences using galdr, an open-source audio analysis CLI. Use when a user asks to analyze a song or track, generate a listening experience or music essay, understand what makes a piece of music work structurally, compare two tracks, or extract video frames from a music video for visual-structural analysis. Works with YouTube URLs (auto-downloads) or local audio files. Produces structural metrics (pattern lock, momentum, harmonic balance, breath shape, silences) and can assemble a self-contained model prompt that generates ~800-word first-person prose. NOT for lyrics-only requests, music recommendations without analysis, or tasks requiring real-time audio capture."
---

# galdr

Audio analysis CLI. Generates structural metrics then assembles a prompt for ~800-word listening experience prose.

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

Check: `galdr --version`. If missing: install before proceeding. If provenance matters, verify the PyPI metadata or install from the source repository above before running it.

## Core Workflows

### YouTube URL → Analysis + prompt (most common)

```bash
# Step 1: fetch audio + context (slug auto-derived from title)
galdr fetch "https://youtu.be/..." --analyze

# galdr prints the slug at the end:
#   Slug : artist-song-title
#   Next : galdr assemble artist-song-title --template arc --mode full

# Step 2: assemble the prompt locally
galdr assemble artist-song-title --template arc --mode full > prompt.txt
```

Override auto-derived metadata if needed:
```bash
galdr fetch "https://youtu.be/..." --artist "Oliver Anthony" --title "Rich Men North of Richmond" --analyze
```

If YouTube download behavior is flaky:
```bash
galdr doctor
galdr update-deps
```

`galdr doctor` reports the active Python executable, yt-dlp command/version, ffmpeg/ffprobe, JavaScript runtimes, and impersonation support. `galdr update-deps` upgrades `yt-dlp[default,curl-cffi]` in the same Python environment galdr is using.

### Local file → Analysis only

> The analysis command is `galdr listen`, not `galdr analyze`.

```bash
galdr listen track.wav --name my-track
galdr assemble my-track --template arc
```

### Second-by-second analysis (for another AI)

Galdr is strongest when read as a **time-ordered listener-state trace**. The stream is the primary evidence. Whole-track interpretation comes after walking the track through time.

Start with:
- `analysis/<slug>/<slug>_stream.json`
- `analysis/<slug>/<slug>_perception.json`
- `docs/PERCEPTION-MODEL.md`

Useful extras:
- `*_harmony_stream.json`
- `*_melody_stream.json`
- `*_overtone_stream.json`
- `*_report.json`
- `galdr assemble <slug> --mode blind`

Reading order:
1. Read `PERCEPTION-MODEL.md` first.
2. Treat `*_stream.json` as the main evidence surface.
3. Walk the track in order.
4. Mark transitions: silence, re-entry, pattern breaks, momentum shifts, breath changes, harmonic movement.
5. Only then compress upward into a larger interpretation.

Do not:
- jump straight to a whole-song mood summary
- treat summary metrics as more important than the stream
- ignore silence/re-entry structure
- overclaim emotional certainty from structure alone

Minimal recipe:
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

### Optional Python agent pattern

```python
import subprocess, re

fetch = subprocess.run(
    ["galdr", "fetch", url, "--analyze"],
    capture_output=True, text=True, check=True
)
slug = re.search(r"Slug\s*:\s*(\S+)", fetch.stdout).group(1)

prompt = subprocess.run(
    ["galdr", "assemble", slug, "--template", "arc", "--mode", "full"],
    capture_output=True, text=True, check=True
).stdout

# Review prompt before sending it to any external model endpoint.
```

### Mode and template flags

| Mode | What's included |
|------|----------------|
| `full` (default) | metrics + lyrics + background + frames |
| `lyrics` | metrics + lyrics |
| `context` | metrics + background |
| `blind` | metrics only (structural, no cultural context) |

`--template arc` prepends the listening experience rules (tone, format, interpretation bounds). Omit for raw data block.

## Interpreting galdr Output

See [references/metrics.md](references/metrics.md) for full metric reference.

**Quick read:**
- `pattern_lock` near 1.0 → listener is locked; near 0 → constant disruption
- `hp_balance` negative → harmonic dominant (warm, tonal); positive → percussive dominant
- `breath_balance` building/releasing/sustaining → energy shape across the track
- Clustered `pattern_breaks` at the end → planned release; distributed → varied structure
- `silence` depth below -60dB with re-lock above 0.93 momentum → structured withdrawal/return

## Writing Experience Prose (without piping)

When writing experience prose yourself from `galdr assemble` output (no `--template`):
- First-person listener perspective, present tense
- Timestamps only at structural pivots (silences, pattern breaks, major energy shifts)
- Translate metrics — describe what they mean, don't quote numbers
- Body anchors (chest, jaw, sternum) sparingly — two or three for the whole piece
- End at the final sound event; no aftermath, no reflection
- ~800 words, no section headers

## Other Commands

```bash
galdr compare track-a track-b          # side-by-side structural comparison
galdr frames slug                      # extract + describe video frames at structural moments
galdr fetch "url" --no-download        # context only (Wikipedia + lyrics), no audio
galdr fetch "url" --censor             # sanitize explicit lyrics before saving
galdr doctor                           # inspect yt-dlp/media runtime health
galdr update-deps                      # upgrade yt-dlp reliability extras
galdr catalog                          # list all indexed tracks
galdr catalog --track NAME             # summary card for one track
```
