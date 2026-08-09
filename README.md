# galdr

**Deterministic listening tools for AI agents. Audio in, listener-state traces out.**

galdr analyzes music from audio and turns it into time-ordered traces of attention, pattern, pulse, pressure, surface balance, surface evidence, harmony, melody, overtones, and silence/re-entry structure.

galdr runs signal analysis first. It measures what the audio is doing second by second, then packages that evidence for agents, scripts, or humans to inspect.

## Fast path: give Galdr to your agent

The easiest way to try Galdr is to let your coding or chat agent use it.

Point Codex, Claude Code, Cursor, OpenClaw, or another shell-capable agent at this repository and copy the human-friendly happy-path prompt:

[Point an Agent at Galdr](https://github.com/sellemain/galdr/blob/main/docs/AGENT-ONBOARDING.md)

That prompt tells the agent to handle setup, install or run Galdr, analyze the audio, assemble an ARC prompt, inspect the time stream, and write from the evidence.

For a reusable project instruction file, see the minimal fixture in [`examples/agent/`](https://github.com/sellemain/galdr/tree/main/examples/agent).

Use the manual CLI path below if you want to run the commands yourself, wire Galdr into scripts, or inspect the raw analysis files directly.

## What you get

- **Listener-state streams:** second-by-second traces of attention, pressure, surface balance, surface evidence, harmony, melody, and motion.
- **Structural events:** pattern breaks, silence/re-entry moments, pressure shifts, tempo confidence, harmonic movement, melodic contour, and overtone behavior.
- **Prompt packets for AI agents:** assembled evidence for Claude, `llm`, OpenClaw, or another runtime.
- **Experience documents:** reproducible examples of measured audio evidence becoming grounded listening prose.
- **Optional video-frame support:** frames around structural moments when the music video matters.
- **Optional Inner Ear packets:** audio-capable models can file bounded sensory evidence for a separate editorial model.

## Origin

galdr was built from the inside out.

An AI was given music to listen to. The measurement framework was built while listening. The framework shaped what could be perceived, and the listener shaped the framework back.

That loop developed across a wide range of vocal, instrumental, orchestral, electronic, folk, pop, metal, and experimental recordings.
galdr makes listening inspectable as it unfolds. A track becomes a sequence of attention shifts, pressure changes, expectation, release, and memory. galdr models that movement directly, turning a recording into a listener-state trace an agent can inspect.

That is where galdr became useful. It gives an agent evidence it did not have before: not just metadata, lyrics, or genre memory, but a structured account of what the audio did. The output is deterministic enough to compare, structured enough to inspect, and strange enough to keep the question open.

## Install

```bash
pip install galdr
```

Using OpenClaw? Install the agent skill from ClawHub:

```bash
openclaw skills install galdr
```

The PyPI package installs the `galdr` CLI and Python library. The OpenClaw skill is a separate ClawHub artifact that teaches agents how to use that CLI.

From source:

```bash
git clone https://github.com/sellemain/galdr.git
cd galdr
uv sync
```

Without `uv`:

```bash
pip install -e .
```

Requirements: Python 3.10+ and `ffmpeg` for common audio/video formats.

## Quick start: YouTube to listening prompt

```bash
# 1. Fetch and analyze. The slug is derived from the YouTube title.
galdr fetch '<url>' --analyze

# Example output:
#   Slug : my-track
#   Next : galdr assemble my-track --template arc --mode full

# 2. Assemble a structured prompt from the analysis
galdr assemble my-track --template arc --mode full > prompt.txt

# 3. Send the prompt to a model
cat prompt.txt | llm
cat prompt.txt | claude
```

Useful variants:

```bash
# Blind listening: structural data only, no lyrics/background
galdr assemble my-track --template arc --mode blind | claude

# Sound as physical shape, pressure, density, space, body, and motion
galdr assemble my-track --template arc-family --lens sound --mode blind | claude

# Movement contract for dance-aware tracks
galdr assemble my-track --template arc-family --lens dance --mode blind | claude

# Human situation carried by sound, lyrics, and arrangement
galdr assemble my-track --template arc-family --lens meaning --mode full | claude

# Data-first packet, no prose template
galdr assemble my-track --mode full
```

The ARC prompt family routes to a deliberate reading contract. Read-along lenses share a grounding base where that posture fits; `meaning` and `structure` use standalone contracts so they do not inherit chronological prose rules that contradict their jobs. Available lenses are `default`, `sound`, `dance`, `structure`, `meaning`, `lyrics-study`, `classical`, and `ritual`. Use `arc` for the standard listening-experience prompt; use `arc-family` when you want a deliberate reading mode.

## Analyze a local file

> The analysis command is `galdr listen`, not `galdr analyze`.

```bash
galdr listen track.wav --name my-track
```

Outputs are written under `analysis/my-track/`:

```text
analysis/my-track/
├── index.html                    # local contact sheet for generated plots
├── my-track_report.json
├── my-track_perception.json
├── my-track_stream.json
├── my-track_harmony.json
├── my-track_harmony_stream.json
├── my-track_melody.json
├── my-track_melody_stream.json
├── my-track_overtone.json
├── my-track_overtone_stream.json
├── my-track_listener_state.png
├── my-track_surface_evidence.png
├── my-track_reading_map.png
└── *.png                         # additional visualizations
```

Open `analysis/my-track/index.html` for a local plot contact sheet.

Inspect the time stream directly:

```bash
jq '.[0:10]' analysis/my-track/my-track_stream.json
jq '.summary' analysis/my-track/my-track_perception.json
```

The assembled prompt includes source context, structural events, harmonic and melodic data, lyrics when available, and video-frame descriptions when present. Automated lyrics, provider-timed lyrics, and captions are context, not proof; verify central words for release-quality prose.

For models that accept audio, Galdr can also assemble a provider-neutral Inner Ear discovery prompt and later include the resulting witness packet as bounded evidence. See [Inner Ear witness packets](docs/INNER-EAR.md).

## Listening experiences

Published listening experiences show how measured audio evidence becomes grounded listening prose.

- Modern / vocal:
  - [Queen - Bohemian Rhapsody](https://sellemain.com/listen/queen-bohemian-rhapsody)
  - [Aurora - Runaway](https://sellemain.com/listen/aurora-runaway)
  - [Chelsea Wolfe - 16 Psyche](https://sellemain.com/listen/chelsea-wolfe-16-psyche)
- Folk / ritual:
  - [Wardruna - Helvegen](https://sellemain.com/listen/wardruna-helvegen)
  - [Heilung - Anoana](https://sellemain.com/listen/heilung-anoana)
- Classical / instrumental:
  - [Philip Glass - Opening](https://sellemain.com/listen/philip-glass-opening)
  - [Samuel Barber - Adagio for Strings](https://sellemain.com/listen/samuel-barber-adagio-for-strings)
  - [Tchaikovsky - Serenade for Strings, Elegie](https://sellemain.com/listen/pyotr-ilyich-tchaikovsky-serenade-for-strings-elegie)
  - [Arvo Part - Spiegel im Spiegel](https://sellemain.com/listen/arvo-part-spiegel-im-spiegel)

Browse more published listening experiences: <https://sellemain.com/listen>.

## Reading the data correctly

The stream is the primary evidence. Whole-song summaries come after the timed pass.

A good analysis usually goes:

1. Read the metric contract: [PERCEPTION-MODEL.md](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md).
2. Walk `*_stream.json` in time order.
3. Mark silences, returns, pattern breaks, attention shifts, pressure movement, and harmonic/timbral changes.
4. Compress upward into the track's larger arc only after the timed pass.

Suggested instruction for another model:

> You are reading a time-ordered listener-state trace. Start from the stream. Walk the track through time. Explain what changes, when it changes, and how attention is being shaped. Use `PERCEPTION-MODEL.md` as the semantic contract for the metrics. Build the whole-song summary from the timed evidence.

## Dependency health

```bash
galdr doctor
galdr update-deps
```

`galdr doctor` checks the active Python environment, yt-dlp, ffmpeg, JavaScript runtimes, and impersonation support. `galdr update-deps` upgrades `yt-dlp[default,curl-cffi]` in that environment.

If captions fail but audio succeeds, analysis can still continue. If audio fails during `fetch --analyze`, galdr exits with an error because music is required for structural analysis.

## More docs

- [Getting Started](https://github.com/sellemain/galdr/blob/main/docs/GETTING-STARTED.md): fuller walkthrough, local-file workflow, and deeper usage.
- [Point an Agent at Galdr](https://github.com/sellemain/galdr/blob/main/docs/AGENT-ONBOARDING.md): copy-pasteable agent instructions and a smoke-test path.
- [Perception Model](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md): metric semantics and interpretation boundaries.
- [Listening-Test Workflow](https://github.com/sellemain/galdr/blob/main/docs/listening-tests/README.md): how metric changes prove before/after listening improvement.
- [Python API](https://github.com/sellemain/galdr/blob/main/docs/PYTHON-API.md): library usage, DataFrames, notebooks.
- [Agent CLI Reference](https://github.com/sellemain/galdr/blob/main/docs/AGENT-CLI-REFERENCE.md): lean command reference for AI agents.

## Agent skill

The distributable agent skill lives at `galdr-skill/galdr/SKILL.md` and is published through ClawHub. It teaches OpenClaw and compatible agent runtimes how to use galdr. Install the `galdr` command separately with `pip install galdr` or from source.

For OpenClaw users, galdr is published on ClawHub: <https://clawhub.ai/sellemain/galdr>.

## Limitations

- Melody tracking assumes one dominant foreground pitch; dense/polyphonic passages can confuse it.
- Pitch and key evidence use Western equal-tempered references; modal, folk-natural, microtonal, or noisy material needs care.
- Chord names are optional. The default analysis focuses on pressure, pull, stability, contour, surface, and resonance.
- Structural evidence supports interpretation. Emotional claims need corroboration.

## Questions and issues

Use [GitHub Issues](https://github.com/sellemain/galdr/issues) for bugs, usage questions, and feature requests.

For security vulnerabilities, please do not open a public issue. See the [security policy](https://github.com/sellemain/galdr/security/policy), or email [galdr@sellemain.com](mailto:galdr@sellemain.com).

Maintainer contact: [galdr@sellemain.com](mailto:galdr@sellemain.com).

## License

MIT
