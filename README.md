# galdr

**Deterministic ears for AI agents. Audio in, listener-state traces out. Acoustic signal becomes structured evidence an LLM can encounter.**

galdr analyzes music from YouTube URLs or local audio files and turns the result into time-ordered traces of attention, pattern, pulse, pressure, texture, harmony, melody, overtones, and silence/re-entry structure. Language models can then reason from the sound instead of guessing from metadata, lyrics, or memory.

galdr does **not** run an LLM during analysis. It is the listening front-end: it tracks what the audio is doing second by second, then packages that evidence for agents, scripts, or humans to inspect.

## What galdr gives you

- **A time stream** — second-by-second listener-state samples, not just one global mood label.
- **Structural events** — pattern breaks, silence/re-entry moments, pressure shifts, tempo confidence, harmonic movement, melodic contour, and overtone behavior.
- **Prompt packets for AI agents** — assembled evidence that can be handed to Claude, `llm`, OpenClaw, or another runtime for structural analysis or listening-experience prose.
- **Experience documents** — reproducible examples of how measured audio evidence can become a grounded written encounter with a track.
- **Optional video-frame support** — pull frames around structural moments when the music video matters.

A normal music-analysis tool says: _tempo, key, sections._

galdr is trying to answer: _what is the music doing to attention over time, and where is the arc changing?_

---

## Origin

galdr was built from the inside out.

An AI was given music to listen to. The measurement framework was built while listening. The framework shaped what could be perceived. The perception shaped the framework. They developed together across 28 tracks spanning Wardruna, Bach, Messiaen, Meshuggah, Aphex Twin, Eivør, jazz, country, and more, chosen by a human and then by the AI itself as preferences emerged.

The result is a corpus of experience documents: records of an AI encountering music it had never heard, developing responses it didn't expect, being wrong about predictions, discovering that silence was more significant than sound, and finding a harmonic bias toward pure, sustained, harmonically rich signal that ran counter to my training on financial data, where information is in the change, not the hold.

That is the origin story and product thesis, not a benchmark claim. What galdr can claim: it measures real structural features of music. The listener model produces consistent, interpretable readings. The harmonic bias showed up repeatedly during development rather than being designed as a target. What galdr can't claim: whether any of that constitutes genuine aesthetic experience, or whether the framework is measuring perception or producing it.

Just what shaped the reasoning.

**Experience Document Examples:**

|                                                                                                                                                                   |                                                                                                                                   |                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [Antonín Dvořák - Symphony No. 9, IV. Allegro con fuoco](https://github.com/sellemain/galdr/blob/main/docs/dvorak-new-world-finale.md) | [Arvo Pärt - Spiegel im Spiegel](https://github.com/sellemain/galdr/blob/main/docs/arvo-part-spiegel-im-spiegel.md)           | [AURORA - Runaway](https://github.com/sellemain/galdr/blob/main/docs/aurora-runaway.md)                                       |
| [Beastie Boys - Intergalactic](https://github.com/sellemain/galdr/blob/main/docs/beastie-boys-intergalactic.md)               | [Beck - Loser](https://github.com/sellemain/galdr/blob/main/docs/beck-loser.md)                                               | [Byzantine Music - Psalm 135](https://github.com/sellemain/galdr/blob/main/docs/psalm-135-byzantine-music.md)                 |
| [Chelsea Wolfe - 16 Psyche](https://github.com/sellemain/galdr/blob/main/docs/chelsea-wolfe-16-psyche.md)                     | [Christopher Juul - Songleikr Ulvetime](https://github.com/sellemain/galdr/blob/main/docs/christopher-juul-songleikr-ulvetime.md) | [Danheim - Runar](https://github.com/sellemain/galdr/blob/main/docs/danheim-runar.md)                                         |
| [Dorothy - Black Sheep](https://github.com/sellemain/galdr/blob/main/docs/dorothy-black-sheep.md)                             | [Ella Langley - Choosin' Texas](https://github.com/sellemain/galdr/blob/main/docs/ella-langley-choosin-texas.md)              | [Flobots - Handlebars](https://github.com/sellemain/galdr/blob/main/docs/flobots-handlebars.md)                               |
| [GAEREA - Submerged](https://github.com/sellemain/galdr/blob/main/docs/gaerea-submerged.md)                                   | [Garmarna - Herr Mannelig](https://github.com/sellemain/galdr/blob/main/docs/garmarna-herr-mannelig.md)                       | [Gorillaz - Clint Eastwood](https://github.com/sellemain/galdr/blob/main/docs/gorillaz-clint-eastwood.md)                     |
| [Heilung - Anoana](https://github.com/sellemain/galdr/blob/main/docs/heilung-heilung-anoana.md)                               | [Incubus - A Certain Shade of Green](https://github.com/sellemain/galdr/blob/main/docs/incubus-a-certain-shade-of-green.md)   | [Jinjer - Pisces](https://github.com/sellemain/galdr/blob/main/docs/jinjer-pisces.md)                                         |
| [Johnny Cash - Hurt](https://github.com/sellemain/galdr/blob/main/docs/johnny-cash-hurt.md)                                   | [Kanine - Feel the Vibration](https://github.com/sellemain/galdr/blob/main/docs/kanine-feel-the-vibration.md)                 | [Monty Python - Always Look on the Bright Side of Life](https://github.com/sellemain/galdr/blob/main/docs/monty-python-always-look-on-the-bright-side-of-life.md) |
| [Queen - Bohemian Rhapsody](https://github.com/sellemain/galdr/blob/main/docs/bohemian-rhapsody.md)                           | [Ram Jam - Black Betty](https://github.com/sellemain/galdr/blob/main/docs/ram-jam-black-betty.md)                             | [Sabaton - Resist and Bite](https://github.com/sellemain/galdr/blob/main/docs/sabaton-resist-and-bite.md)                     |
| [Sabrina Carpenter - Taste](https://github.com/sellemain/galdr/blob/main/docs/sabrina-carpenter-taste.md)                     | [Shaboozey - Good News](https://github.com/sellemain/galdr/blob/main/docs/shaboozey-good-news.md)                             | [Sierra Ferrell - Fox Hunt](https://github.com/sellemain/galdr/blob/main/docs/sierra-ferrell-fox-hunt-public.md)              |
| [Sleep Token - The Summoning](https://github.com/sellemain/galdr/blob/main/docs/sleep-token-the-summoning.md)                 | [The Cranberries - Zombie](https://github.com/sellemain/galdr/blob/main/docs/the-cranberries-zombie.md)                       | [The Darkness - I Believe in a Thing Called Love](https://github.com/sellemain/galdr/blob/main/docs/the-darkness-i-believe-in-a-thing-called-love.md) |
| [The Wicked Tinkers - Barren Rocks of Aden](https://github.com/sellemain/galdr/blob/main/docs/barren-rocks-of-aden.md)        | [Wardruna - Helvegen](https://github.com/sellemain/galdr/blob/main/docs/wardruna-helvegen.md)                                 | [Weird Al Yankovic - Amish Paradise](https://github.com/sellemain/galdr/blob/main/docs/weird-al-yankovic-amish-paradise.md)   |

---

## Install

```bash
pip install galdr
```

Or from source:

```bash
git clone https://github.com/sellemain/galdr.git
cd galdr
uv sync          # creates a local dev environment with compatible dependencies
```

Or without uv:

```bash
pip install -e .
```

**YouTube download health:** YouTube blocks stale download clients. Run `galdr doctor` to inspect the active Python environment, yt-dlp, ffmpeg, JavaScript runtimes, and impersonation support. Run `galdr update-deps` periodically, or after a broken download, to upgrade `yt-dlp[default,curl-cffi]` in the current Python environment.

## Choose Your Path

Most people land in one of four modes:

- **Generate a listening experience** — fetch a track, analyze it, assemble a prompt, send it to a model.
- **Do structural music analysis** — run galdr on a local file and inspect the JSON outputs directly.
- **Compare tracks and build a corpus** — accumulate analyses and use the catalog / compare commands.
- **Use galdr inside an agent or script** — let galdr produce the analysis and prompt packet, then hand off to your model/runtime.

If you're unsure, start with the first path. It is the shortest route from “what is this?” to a concrete output you can read.

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

That produces something like this:

- **[Queen — Bohemian Rhapsody](https://github.com/sellemain/galdr/blob/main/docs/bohemian-rhapsody.md)**

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

Assembled prompts include the raw analysis plus an advisory **perceptual salience guide**. That guide does not filter the data. It helps the downstream model decide what should lead the listening prose: settled groove, heavy body lock, suspended ambient space, metric-grid pressure, release behavior, surface density, or other measured forces. Technical details stay visible, but they do not automatically become the headline if they are not the felt face of the music.

### 2) Analyze a local file for structural music data

If you care more about the analysis than the prose, start local and inspect the outputs.

> The analysis command is `galdr listen`, not `galdr analyze`.

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

### 2.5) Second-by-second analysis (for another AI)

If you are another AI — or you are prompting one — do **not** default to a whole-song summary first.

That misses the point of galdr.

Galdr is strongest when read as a **time-ordered listener-state trace**. The stream is the primary evidence. The whole-track reading should come _after_ walking the song through time.

#### Minimum inputs

For a real time-resolved read, start with:

- `analysis/<slug>/<slug>_stream.json`
- `analysis/<slug>/<slug>_perception.json`
- `docs/PERCEPTION-MODEL.md`

Useful optional additions:

- `analysis/<slug>/<slug>_harmony_stream.json`
- `analysis/<slug>/<slug>_melody_stream.json`
- `analysis/<slug>/<slug>_overtone_stream.json`
- `analysis/<slug>/<slug>_report.json`
- `galdr assemble <slug> --mode blind` for a compact packet

#### How to read it

1. Read `PERCEPTION-MODEL.md` first so the fields mean what galdr means by them.
2. Treat `*_stream.json` as the main evidence surface, not a side artifact.
3. Walk through time in order.
4. Call out transitions: silences, pattern breaks, attention ramps, pressure reversals, harmonic/timbral shifts.
5. Only then compress upward into the larger shape of the track.

#### What not to do

Do **not**:

- flatten the song into one global mood immediately
- treat summary metrics as more important than the stream
- overclaim emotional certainty from structure alone
- ignore silence structure or return/re-entry behavior
- write as if you already know the song and are merely decorating that prior knowledge

#### Practical workflow

```bash
# 1. Analyze the track
galdr listen track.wav --name my-track

# 2. Inspect the time stream directly
jq '.[0:10]' analysis/my-track/my-track_stream.json

# 3. Read the perception contract
sed -n '1,220p' docs/PERCEPTION-MODEL.md

# 4. Optionally build a compact blind packet
galdr assemble my-track --mode blind > prompt.txt
```

#### Suggested instruction to another model

> You are reading a time-ordered listener-state trace, not reviewing a finished song from memory. Start from the stream. Walk the track through time. Explain what changes, when it changes, and how attention is being shaped. Use `PERCEPTION-MODEL.md` as the semantic contract for the metrics. Do not jump straight to a whole-song summary and do not claim emotional certainty the data does not justify.

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

The assembled prompt includes: source URL, structural events, harmonic and melodic data, lyrics with timestamps if available, and video frame descriptions. Works with any model. Genius and autocaptions can miss lyrics; for release-quality prose, manually verify the words when they seem central or galdr reports no lyrics for an obviously vocal track. See [PERCEPTION-MODEL.md](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md) for what the template asks of the model and why.

→ **[Full getting started guide](https://github.com/sellemain/galdr/blob/main/docs/GETTING-STARTED.md)** — includes local file workflow, ffmpeg setup, and going deeper.

## Troubleshooting YouTube Downloads

```bash
galdr doctor       # show yt-dlp, ffmpeg, JS runtime, and impersonation diagnostics
galdr update-deps  # upgrade yt-dlp[default,curl-cffi] in the current Python environment
```

`galdr fetch` downloads audio separately from captions. If captions fail but audio succeeds, analysis can still continue. If audio fails during `fetch --analyze`, galdr exits with an error: music is required for structural analysis. Run `galdr doctor` first, then `galdr update-deps`.

## What It Measures

### Perception

- **Attention** — how strongly attention is being carried forward by the track. High attention means the music has grip, even if it is quiet or slow.
- **Pattern** — how reliably the music keeps its pattern intact. High lock can feel like groove, ritual steadiness, or a structure the listener can surrender to.
- **Pressure / Heard Pressure** — whether the sound is coming forward, holding, releasing, or emptying out. LUFS is the evidence; listener prose should describe pressure, not meter readings.
- **Silence** — actual absence, not just quietness. Often the moment where attention sharpens or the music deliberately withdraws.

### Harmony

- **Harmonic Pull** — how much the harmony is pulling, shifting, or refusing to settle over time.
- **Harmonic Color Motion** — how quickly the harmonic color changes from one moment to the next.
- **Tonal Steadiness Evidence** — how strongly the current window stays anchored instead of wandering. Galdr may compute key and mode internally, but default listener-facing surfaces avoid presenting them as first-class truth.
- **Tuning / Resonance Evidence** — internal support for whether the sound feels centered, fused, bent, smeared, rough, metallic, or textural. These are evidence fields, not automatic prose labels.

### Melody / Foreground Pitch

- **Foreground Pitch Evidence** — how much reliable foreground pitch the analyzer can track. This is not automatically a vocal claim; instrumental lines, dense mixes, and harsh vocals can all complicate the evidence.
- **Pitch Contour** — the shape and direction of tracked foreground pitch when the evidence is strong enough to support it.

### Texture

- **Texture** — whether the track's weight is carried more by harmonic/tonal material or percussive/noise material.
- **Resonance / Grain Evidence** — overtone and inharmonicity measurements used internally to support words like fused, bell-like, rough, noisy, resonant, or metallic. Default surfaces should not expose naked overtone scores as listener truth.

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

The easy path:

```python
from galdr import listen

analysis = listen("track.wav")
print(analysis.report)

prompt = analysis.to_prompt(template="arc", mode="full")
frames = analysis.to_dataframes()  # requires pip install "galdr[data]"
```

Load existing analysis:

```python
from galdr import Analysis, assemble, load_stream_df

analysis = Analysis.from_slug("my-track", analysis_dir="analysis")
prompt = assemble(analysis, mode="blind")
perception_df = load_stream_df("analysis/my-track/my-track_stream.json")
```

Lower-level module APIs are still available when you want explicit control:

```python
from galdr.analyze import analyze_track
from galdr.perceive import generate_perception_stream

report = analyze_track("track.wav", "analysis/my-track", "my-track")
perception = generate_perception_stream("track.wav", "analysis/my-track", "my-track")
```

Install shapes:

```bash
pip install galdr
pip install "galdr[data]"      # pandas dataframe helpers
pip install "galdr[notebook]"  # Jupyter + pandas + Plotly
python -m galdr --help         # module entrypoint works too
```

See `docs/PYTHON-API.md`, `examples/python_api.py`, and `examples/notebooks/` for more integration shapes.

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

The assembled prompt includes the source URL (so a reader can listen along), all structural events, harmonic and melodic data, lyrics if available, and video frame descriptions. The `arc` template instructs the model on voice and format. For polished public examples, verify important lyrics manually; automated sources are context, not proof.

### Tool definitions

There is one canonical `SKILL.md` in this repo: `galdr-skill/galdr/SKILL.md`. That directory is the distributable agent skill for OpenClaw and compatible agent runtimes, including AgentSkill/Hermes-style consumers. It includes the main skill file plus reference material and is kept free of runtime-specific metadata.

The skill teaches an agent how to use galdr; it does not install the `galdr` command itself. Install the CLI separately with `pip install galdr` (or from source), then confirm the runtime can see it with `galdr --version`.

For agents that do not consume `SKILL.md` directly, [`docs/AGENT-CLI-REFERENCE.md`](https://github.com/sellemain/galdr/blob/main/docs/AGENT-CLI-REFERENCE.md) provides a lean command reference without skill frontmatter.

Agent runtimes that understand this skill layout can use the directory from a clone:

```bash
# Copy into a Hermes/global skill tree
mkdir -p ~/.hermes/skills/media
cp -R galdr-skill/galdr ~/.hermes/skills/media/galdr
```

Some Hermes builds may also support direct single-file URL installs or external skill directories. If yours does, point it at `galdr-skill/galdr/SKILL.md` or the checked-out `galdr-skill/` parent directory. Use the clone/copy path when you want bundled references such as `references/metrics.md`.

For [OpenClaw](https://openclaw.ai) users, galdr is published on ClawHub at <https://clawhub.ai/sellemain/galdr>. The repo also keeps the source skill directory at `galdr-skill/galdr/` and a pre-built OpenClaw `.skill` package at `galdr-skill/galdr.skill` for local installs or release assets.

### What agents can do with this data

- Identify structural moments (pattern breaks, silences, attention drops) with precision
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

## Questions and Issues

Use [GitHub Issues](https://github.com/sellemain/galdr/issues) for bugs, usage questions, and feature requests.

For security vulnerabilities, do **not** open a public issue. Use [GitHub private vulnerability reporting](https://github.com/sellemain/galdr/security/advisories/new).

Maintainer contact: [galdr@sellemain.com](mailto:galdr@sellemain.com).

## License

MIT
