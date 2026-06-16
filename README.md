# galdr

**Deterministic listening tools for AI agents. Audio in, listener-state traces out.**

galdr analyzes music from YouTube URLs or local audio files and turns it into time-ordered traces of attention, pattern, pulse, pressure, surface balance, surface evidence, harmony, melody, overtones, and silence/re-entry structure.

galdr runs signal analysis first. It measures what the audio is doing second by second, then packages that evidence for agents, scripts, or humans to inspect.

## What you get

- **Listener-state streams:** second-by-second traces of attention, pressure, surface balance, surface evidence, harmony, melody, and motion.
- **Structural events:** pattern breaks, silence/re-entry moments, pressure shifts, tempo confidence, harmonic movement, melodic contour, and overtone behavior.
- **Prompt packets for AI agents:** assembled evidence for Claude, `llm`, OpenClaw, or another runtime.
- **Experience documents:** reproducible examples of measured audio evidence becoming grounded listening prose.
- **Optional video-frame support:** frames around structural moments when the music video matters.

## Origin

galdr was built from the inside out.

An AI was given music to listen to. The measurement framework was built while listening. The framework shaped what could be perceived, and the listener shaped the framework back.

That loop developed across many tracks including Wardruna, Bach, Messiaen, Meshuggah, Aphex Twin, Eivør, jazz, country, pop, metal, folk, and more.
galdr makes listening inspectable as it unfolds. A track becomes a sequence of attention shifts, pressure changes, expectation, release, and memory. galdr models that movement directly, turning a recording into a listener-state trace an agent can inspect.

That is where galdr became useful. It gives an agent evidence it did not have before: not just metadata, lyrics, or genre memory, but a structured account of what the audio did. The output is deterministic enough to compare, structured enough to inspect, and strange enough to keep the question open.

## Install

```bash
pip install galdr
```

Using OpenClaw? Install the agent skill from ClawHub:

```bash
clawhub install galdr
```

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
galdr fetch 'https://www.youtube.com/watch?v=fJ9rUzIMcZQ' --analyze

# Example output:
#   Slug : queen-bohemian-rhapsody
#   Next : galdr assemble queen-bohemian-rhapsody --template arc --mode full

# 2. Assemble a structured prompt from the analysis
galdr assemble queen-bohemian-rhapsody --template arc --mode full > prompt.txt

# 3. Send the prompt to a model
cat prompt.txt | llm
cat prompt.txt | claude
```

Useful variants:

```bash
# Blind listening: structural data only, no lyrics/background
galdr assemble queen-bohemian-rhapsody --template arc --mode blind | claude

# Data-first packet, no prose template
galdr assemble queen-bohemian-rhapsody --mode full
```

## Analyze a local file

> The analysis command is `galdr listen`, not `galdr analyze`.

```bash
galdr listen track.wav --name my-track
```

Outputs are written under `analysis/my-track/`:

```text
analysis/my-track/
├── my-track_report.json
├── my-track_perception.json
├── my-track_stream.json
├── my-track_harmony.json
├── my-track_harmony_stream.json
├── my-track_melody.json
├── my-track_melody_stream.json
├── my-track_overtone.json
├── my-track_overtone_stream.json
└── *.png
```

Inspect the time stream directly:

```bash
jq '.[0:10]' analysis/my-track/my-track_stream.json
jq '.summary' analysis/my-track/my-track_perception.json
```

The assembled prompt includes source context, structural events, harmonic and melodic data, lyrics when available, and video-frame descriptions when present. Automated lyrics and captions are context, not proof; verify central words for release-quality prose.

## Listening experiences

The repo also includes examples where measured audio evidence becomes grounded listening prose.

Selected examples:

- [Queen: Bohemian Rhapsody](https://github.com/sellemain/galdr/blob/main/docs/bohemian-rhapsody.md)
- [Wardruna: Helvegen](https://github.com/sellemain/galdr/blob/main/docs/wardruna-helvegen.md)
- [Arvo Pärt: Spiegel im Spiegel](https://github.com/sellemain/galdr/blob/main/docs/arvo-part-spiegel-im-spiegel.md)
- [Dvořák: Symphony No. 9, IV. Allegro con fuoco](https://github.com/sellemain/galdr/blob/main/docs/dvorak-new-world-finale.md)
- [Heilung: Anoana](https://github.com/sellemain/galdr/blob/main/docs/heilung-heilung-anoana.md)
- [Chelsea Wolfe: 16 Psyche](https://github.com/sellemain/galdr/blob/main/docs/chelsea-wolfe-16-psyche.md)

Browse published listening experiences: <https://sellemain.com/listen>.

## Reading the data correctly

The stream is the primary evidence. Whole-song summaries come after the timed pass.

A good analysis usually goes:

1. Read the metric contract: [PERCEPTION-MODEL.md](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md).
2. Walk `*_stream.json` in time order.
3. Mark silences, returns, pattern breaks, attention shifts, pressure movement, and harmonic/timbral changes.
4. Compress upward into the track's larger arc only after the timed pass.

Suggested instruction for another model:

> You are reading a time-ordered listener-state trace. Start from the stream. Walk the track through time. Explain what changes, when it changes, and how attention is being shaped. Use `PERCEPTION-MODEL.md` as the semantic contract for the metrics. Build the whole-song summary from the timed evidence.

## YouTube download health

```bash
galdr doctor
galdr update-deps
```

`galdr doctor` checks the active Python environment, yt-dlp, ffmpeg, JavaScript runtimes, and impersonation support. `galdr update-deps` upgrades `yt-dlp[default,curl-cffi]` in that environment.

If captions fail but audio succeeds, analysis can still continue. If audio fails during `fetch --analyze`, galdr exits with an error because music is required for structural analysis.

## More docs

- [Getting Started](https://github.com/sellemain/galdr/blob/main/docs/GETTING-STARTED.md): fuller walkthrough, local-file workflow, and deeper usage.
- [Perception Model](https://github.com/sellemain/galdr/blob/main/docs/PERCEPTION-MODEL.md): metric semantics and interpretation boundaries.
- [Python API](https://github.com/sellemain/galdr/blob/main/docs/PYTHON-API.md): library usage, DataFrames, notebooks.
- [Agent CLI Reference](https://github.com/sellemain/galdr/blob/main/docs/AGENT-CLI-REFERENCE.md): lean command reference for AI agents.

## Agent skill

The distributable agent skill lives at `galdr-skill/galdr/SKILL.md`. It teaches OpenClaw and compatible agent runtimes how to use galdr. Install the `galdr` command separately.

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
