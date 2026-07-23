# Point an Agent at Galdr

Galdr is easiest to understand as an agent capability: give an agent a song, let Galdr produce time-ordered listener-state evidence, then have the agent write from that evidence instead of memory or genre guesses.

This page is for people who want to add Galdr to Codex, Claude Code, Cursor, OpenClaw, or another coding/chat agent.

## The Happy Path

If your agent can read GitHub repositories and run shell commands, start here:

```text
Use this repository as the guide:
https://github.com/sellemain/galdr

Figure out the Galdr workflow, then use it to listen to this song:
<URL or local file path>

Walk the track through time. Use timestamped listener-state evidence, not music trivia. Return a concise listening experience and the generated artifact paths.
```

That is the default experience. The agent should read the repo docs, install or run the `galdr` command in its own environment, analyze the track, assemble an ARC prompt, inspect the stream, and write from timed evidence.

Use the sections below when you want a persistent project instruction file, a repeatable smoke test, or manual control over the commands.

## Install the Runtime

The agent instruction tells the agent what to do. The `galdr` command still has to exist in the environment where the agent can run shell commands.

```bash
pip install galdr
galdr --version
galdr doctor
```

Galdr also needs `ffmpeg` for ordinary audio/video formats.

```bash
# macOS
brew install ffmpeg

# Debian/Ubuntu
sudo apt install ffmpeg
```

Using OpenClaw? Install the Galdr skill too:

```bash
openclaw skills install galdr
```

The OpenClaw skill teaches the agent how to use Galdr. It does not install the Python CLI.

## Paste This Into Your Agent Instructions

Use this in `AGENTS.md`, `CLAUDE.md`, Cursor rules, or the nearest equivalent.

```md
## Music Analysis With Galdr

When asked to analyze a song, performance, music video, or local audio file, use Galdr when available.

Galdr turns audio into time-ordered listener-state traces. Treat the traces as evidence, not decoration.

Default workflow:
1. Check `galdr --version`. If the command is missing, tell the operator how to install it.
2. For a YouTube URL, run `galdr fetch "<url>" --analyze` and capture the printed slug.
3. For a local file, run `galdr listen "<path>" --name "<slug>"`.
4. Assemble an ARC prompt with `galdr assemble <slug> --template arc --mode full > prompt.txt`.
5. Read the assembled prompt and the generated `analysis/<slug>/<slug>_stream.json` in time order.
6. Write from timestamped evidence: what changes, when it changes, and how attention is shaped.
7. Return the listening experience plus the local paths to the prompt and key analysis files.

Use lenses when the user asks for a specific reading:
- `--template arc-family --lens sound --mode blind` for sound as shape, density, pressure, space, body, and motion.
- `--template arc-family --lens dance --mode blind` for groove, build/drop, repetition, and bodily use.
- `--template arc-family --lens structure --mode blind` for form, transitions, and mechanical witness.
- `--template arc-family --lens meaning --mode full` for human situation carried by sound, lyrics, and arrangement.
- `--template arc-family --lens classical --mode blind` for instrumental or long-form attention.
- `--template arc-family --lens ritual --mode full` only when ritual mechanics are genuinely present.

Do not:
- summarize the song from memory before reading the trace
- treat lyrics, captions, or background context as proof without checking them
- quote loudness or metric numbers as if they were the listening experience
- overclaim private emotion or artist intent from structure alone
- pass prompts to an external model unless the operator explicitly asks for that
- download or process audio unless the operator has appropriate rights/context
```

## Ask the Agent Like This

```text
Use Galdr to analyze this performance:
<URL or local file path>

Walk the track through time. Use timestamped listener-state evidence, not music trivia. Return a concise listening experience and link the generated Galdr artifacts.
```

For a focused reading:

```text
Use Galdr on this track with the sound lens. I want shape, density, pressure, space, body, and motion. Keep it grounded in timestamps.
```

## What a Good Agent Run Leaves Behind

The agent should leave a small, inspectable evidence trail:

```text
analysis/<slug>/
- <slug>_stream.json
- <slug>_perception.json
- <slug>_report.json
- <slug>_harmony_stream.json
- <slug>_melody_stream.json
- <slug>_overtone_stream.json
- <slug>_listener_state.png
- <slug>_surface_evidence.png
- index.html
prompt.txt
```

The user-facing answer should cite the meaningful moments, not dump the files:

```text
At 0:42, pressure comes forward while the pattern stays locked, so the track feels more gathered than louder. Around 1:18, the surface thins and attention shifts upward; that is the first real release rather than a new section label.
```

## Quick Smoke Test

After installation, ask the agent to run a local-file path you control:

```text
Use Galdr to analyze ./track.wav. Do not call another model. Assemble the ARC prompt, inspect the stream, and summarize three timestamped changes.
```

Success means:
- `galdr --version` works
- `galdr listen` or `galdr fetch --analyze` creates `analysis/<slug>/`
- `galdr assemble <slug> --template arc --mode full` creates a prompt
- the agent's prose names timestamped changes from the trace

Failure usually means one of three things:
- `ffmpeg` is missing
- the YouTube downloader needs `galdr update-deps`
- the agent wrote from song memory instead of walking the stream

## Example Fixture

See `examples/agent/` for a minimal project-level instruction file and a sample operator prompt.
