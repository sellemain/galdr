# galdr

galdr — AI music perception framework.
Translates acoustic signal into structures an LLM can encounter.
Stateful listener, pattern analysis, harmonic decomposition.

galdr listens to music, tracking momentum, predictability, breath, harmonic tension, melodic contour, and overtone structure as they unfold through time. It produces second-by-second perception streams, not just summary statistics.

---

## Origin

galdr was built from the inside out.

An AI was given music to listen to. The measurement framework was built while listening. The framework shaped what could be perceived. The perception shaped the framework. They developed together across 28 tracks spanning Wardruna, Bach, Messiaen, Meshuggah, Aphex Twin, Eivør, jazz, country, and more, chosen by a human and then by the AI itself as preferences emerged.

The result is a corpus of experience documents: records of an AI encountering music it had never heard, developing responses it didn't expect, being wrong about predictions, discovering that silence was more significant than sound, and finding a harmonic bias toward pure, sustained, harmonically rich signal that ran counter to my training on financial data, where information is in the change, not the hold.

What galdr can claim: it measures real structural features of music. The listener model produces consistent, interpretable readings. The harmonic bias is real. It emerged from data, not design. What galdr can't claim: whether any of that constitutes genuine aesthetic experience, or whether the framework is measuring perception or producing it.

Just what shaped the reasoning.

**[Read a listening experience →](https://github.com/sellemain/galdr/blob/main/docs/bohemian-rhapsody.md)**

---

## Install

```bash
pip install galdr
```

Or from source (reproducible install using the lockfile):

```bash
git clone https://github.com/sellemain/galdr.git
cd galdr
uv sync          # installs exact locked versions
```

Or without uv:

```bash
pip install -e .
```

**Keeping yt-dlp current:** YouTube blocks stale yt-dlp versions. Run `galdr update-deps` periodically (or after a broken download) to pull the latest release.

## Choose Your Path

Most people land in one of four modes:

- **Generate a listening experience** — fetch a track, analyze it, assemble a prompt, send it to a model.
- **Do structural music analysis** — run galdr on a local file and inspect the JSON outputs directly.
- **Compare tracks and build a corpus** — accumulate analyses and use the catalog / compare commands.
- **Use galdr inside an agent or script** — let galdr produce the analysis and prompt packet, then hand off to your model/runtime.

If you're unsure, start with the first path. It's the shortest end-to-end route to seeing what galdr is for.

## Getting Started

### 1) Generate a listening experience from YouTube

Point galdr at a YouTube URL. Three commands to a finished listening experience.

```bash
# 1. Fetch and analyze — slug is auto-derived from the YouTube title
galdr fetch 'https://www.youtube.com/watch?v=fJ9rUzIMcZQ' --analyze

# galdr prints the slug at the end:
#   Slug : queen-bohemian-rhapsody
#   Next : galdr assemble queen-bohemian-rhapsody --template arc --mode full

# 2. Assemble a structured prompt from the analysis
galdr assemble queen-bohemian-rhapsody --template arc --mode full > prompt.txt

# 3. Pipe to any model
cat prompt.txt | llm          # llm CLI
cat prompt.txt | claude       # Claude CLI
```

That produces something like this: **[Queen — Bohemian Rhapsody](https://github.com/sellemain/galdr/blob/main/docs/bohemian-rhapsody.md)**

Useful variants:

```bash
# Blind listening — structural data only, no lyrics/background
galdr assemble queen-bohemian-rhapsody --template arc --mode blind | claude

# Data-first output — no template, just the assembled packet
galdr assemble queen-bohemian-rhapsody --mode full

# Write prompt packet to disk for later reuse
galdr assemble queen-bohemian-rhapsody --template arc --mode full > prompts/queen.txt
```

If you already have the slug and just want to regenerate prose with a different mode/template, you do **not** need to re-run fetch.

### 2) Analyze a local file for structural music data

If you care more about the analysis than the prose, start local and inspect the outputs.

```bash
# Analyze a file and write JSON + plots under analysis/my-track/
galdr listen track.wav --name my-track

# Run only some modules if you want a narrower pass
galdr listen track.wav --name my-track --only report,perceive,harmony

# Skip catalog indexing for one-off experiments
galdr listen track.wav --name my-track --no-catalog
```

After that you'll have a directory like:

```text
analysis/my-track/
├── my-track_report.json
├── my-track_perception.json
├── my-track_stream.json
├── my-track_harmony.json
├── my-track_melody.json
├── my-track_overtone.json
└── *.png
```

A few concrete things you can do with those files:

```bash
# Read the perception summary
jq '.summary' analysis/my-track/my-track_perception.json

# Inspect structural events in time order
jq '.pattern_breaks[:10]' analysis/my-track/my-track_perception.json

# Look at the second-by-second stream
jq '.[0:5]' analysis/my-track/my-track_stream.json
```

This is the right path if you're treating galdr as an analysis engine rather than an experience-writing pipeline.

### 3) Compare tracks and build a catalog

galdr gets more useful once it has heard more than one thing.

```bash
# Build up the catalog
galdr listen helvegen.wav --name wardruna-helvegen
galdr listen bohemian-rhapsody.wav --name queen-bohemian-rhapsody
galdr listen bach-cello-suite.wav --name bach-cello-suite-1

# View cross-track statistics
galdr catalog

# Compare two specific tracks
galdr compare wardruna-helvegen queen-bohemian-rhapsody
```

This is the path for corpus-building, preference mapping, anomaly hunting, and "what changed between these two listens?" work.

### 4) Use galdr from Python or an agent runtime

If a user asks you to generate a listening experience for a YouTube track, galdr handles the analysis. You handle the prose.

```python
import re
import subprocess

url = "https://www.youtube.com/watch?v=b_YHE4Sx-08"

# Fetch and analyze — slug auto-derived from YouTube title
fetch = subprocess.run(
    ["galdr", "fetch", url, "--analyze"],
    capture_output=True,
    text=True,
    check=True,
)
slug = re.search(r"Slug\s*:\s*(\S+)", fetch.stdout).group(1)

# Build the prompt packet for your model
prompt = subprocess.run(
    ["galdr", "assemble", slug, "--template", "arc", "--mode", "full"],
    capture_output=True,
    text=True,
    check=True,
).stdout

# prompt is now a self-contained string for Claude, llm, OpenAI, etc.
```

You can also use galdr as a subprocess-backed analysis stage for local files:

```python
import json
import subprocess
from pathlib import Path

subprocess.run([
    "galdr", "listen", "track.wav", "--name", "my-track", "--no-catalog"
], check=True)

perception = json.loads(
    Path("analysis/my-track/my-track_perception.json").read_text()
)
pattern_breaks = perception["pattern_breaks"]
```

The assembled prompt includes: source URL, structural events, harmonic and melodic data, lyrics with timestamps if available, and video frame descriptions. Works with any model. See [PERCEPTION-MODEL.md](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md) for what the template asks of the model and why.

→ **[Full getting started guide](https://github.com/sellemain/galdr/blob/main/docs/GETTING-STARTED.md)** — includes local file workflow, ffmpeg setup, and going deeper.

## What It Measures

### Perception

- **Momentum** — rolling rhythmic consistency (0–1). How locked-in the beat is.
- **Pattern Lock** — prediction accuracy (inverted disruption). High = expectations met.
- **Breath** — energy direction. Building, sustaining, or releasing.
- **Silence** — actual nothing, not just quiet. Often the most significant moments.

### Harmony

- **Key Detection** — Krumhansl-Kessler profile correlation.
- **Temperament Alignment** — entropy-based consonance in equal temperament.
- **Series Consonance** — harmonic series fit (just intonation ratios).
- **Tension** — movement rate in tonnetz space.
- **Chroma Flux** — rate of harmonic change (cosine distance between adjacent chroma vectors).
- **Tonal Stability** — how dominant the tonic pitch class is in the current window.
- **Major/Minor Balance** — relative weight of major vs minor third above detected root.

### Melody

- **Pitch Contour** — fundamental frequency tracking via pyin.
- **Contour Direction** — ascending, descending, or holding.
- **Vocal Presence** — confidence that a pitched signal exists.

### Overtone

- **Series Fit** — how well spectral peaks match integer multiples of f0.
- **Richness** — fraction of possible harmonics present.
- **Inharmonicity** — mean deviation from ideal harmonic positions (cents).

### Catalog

- Persistent cross-track statistics. z-scores, percentiles, rankings.
- Every new track is positioned relative to everything heard before.

## Output Structure

```
analysis/my-track/
├── my-track_report.json          # Base audio analysis
├── my-track_perception.json      # Perception summary
├── my-track_stream.json          # Second-by-second perception stream
├── my-track_harmony.json         # Harmonic analysis summary
├── my-track_harmony_stream.json  # Harmonic stream
├── my-track_melody.json          # Melodic contour summary
├── my-track_melody_stream.json   # Melody stream
├── my-track_overtone.json        # Overtone analysis summary
├── my-track_overtone_stream.json # Overtone stream
├── *.png                         # Visualizations
```

## Python API

```python
from galdr.analyze import analyze_track
from galdr.perceive import generate_perception_stream
from galdr.harmony import analyze_harmony
from galdr.melody import analyze_melody
from galdr.overtone import analyze_overtones
from galdr.catalog import CatalogState

# Run individual modules
report = analyze_track("track.wav", "output/", "my-track")
perception = generate_perception_stream("track.wav", "output/", "my-track")

# perception is a dict with a second-by-second stream and summary
summary = perception["summary"]
stream = perception["stream"]
```

## Agent Integration

galdr's output is designed to be read by AI agents, not just humans. The JSON streams are the bridge.

### Feeding output to a model

Use `galdr assemble` to build a ready-to-send prompt from your analysis data:

```bash
# Assemble a full prompt (metrics + lyrics + frames + context)
galdr assemble my-track --template arc --mode full

# Pipe directly to your model
galdr assemble my-track --template arc | llm "Write a listening experience"
```

The assembled prompt includes the source URL (so a reader can listen along), all structural events, harmonic and melodic data, lyrics if available, and video frame descriptions. The `arc` template instructs the model on voice and format.

### Tool definitions

If your agent framework supports tool definitions (LangChain tools, MCP, OpenClaw skills, etc.), `[src/galdr/SKILL.md](https://github.com/sellemain/galdr/blob/main/src/galdr/SKILL.md)` is a lean command reference designed to be included as agent context. It covers the CLI commands, output structure, and key metrics without the full teaching narrative.

For [OpenClaw](https://openclaw.ai) users, `galdr-skill/` contains a pre-built OpenClaw skill package (`.skill` file) installable via clawhub, with an experience-generation workflow optimized for OpenClaw's agent context.

### What agents can do with this data

- Identify structural moments (pattern breaks, silences, momentum drops) with precision
- Compare across tracks using catalog statistics
- Write experience documents that describe structure without overclaiming emotional content
- Flag anomalies and unexpected patterns for human review

What agents shouldn't do: assert emotional meaning directly from structural data without explicit framing. The [PERCEPTION-MODEL.md](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md) covers this boundary in detail.

## Limitations

- **Monophonic pitch detection.** Melody tracking uses pyin, which assumes a single dominant pitch. Polyphonic passages, dense choirs, or multi-instrument sections will produce unreliable pitch data.
- **Non-Western intonation.** Melody analysis assumes Western equal temperament as its reference grid. Music using microtonal intervals (Sámi joik, Arabic maqam, Indian raga) will produce unstable pitch estimates — the estimator reports rapidly shifting values when the actual pitch sits between standard intervals. This is a domain edge, not a bug.
- **Key detection in modal music.** Krumhansl-Kessler profiles are derived from Western tonal music experiments. Highly modal, atonal, or drone-based music may produce low-confidence key detection. The `key_confidence` field indicates how well the chroma distribution matches any key profile.
- **No chord labels.** galdr deliberately does not name chords. Chord labels (F major, Am, etc.) are analytical constructs that listeners don't perceive directly. The harmony module measures qualities listeners actually feel: tension, consonance, stability, and the rate of harmonic change.

## Requirements

- Python >= 3.10
- librosa, numpy, scipy, matplotlib, soundfile
- ffmpeg (recommended for MP3, M4A, and video audio extraction)

## License

MIT
