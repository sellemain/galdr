# Point Your Agent at Galdr

Galdr is easiest when an AI agent does the technical work.

You do not need to learn the command line first. Copy the prompt below into Codex, Claude Code, Cursor, OpenClaw, or another agent that can read GitHub and run shell commands. Give it a YouTube URL or a local audio file.

## Copy This Prompt

```text
You are helping me use Galdr, an audio-listening tool for AI agents.

Use this repository as the guide:
https://github.com/sellemain/galdr

Handle the technical setup for me. Read the repo docs enough to use Galdr correctly.

First, check whether the `galdr` command is available. If it is missing, install Galdr from PyPI or run it from the source repo in a local environment. Also check that `ffmpeg` is available. If something cannot be installed from this environment, tell me exactly what is missing and stop.

Then use Galdr to listen to this song:
<URL or local file path>

Use the default ARC listening workflow:
- For a YouTube URL, run `galdr fetch "<url>" --analyze` and capture the printed slug.
- For a local audio file, run `galdr listen "<path>" --name "<slug>"`.
- Assemble the prompt with `galdr assemble <slug> --template arc --mode full > prompt.txt`.
- Read the assembled prompt and the generated `analysis/<slug>/<slug>_stream.json` in time order.
- Write from timestamped listener-state evidence: what changes, when it changes, and how attention is shaped.

Return:
1. A concise listening experience grounded in timestamped evidence.
2. The local paths to `prompt.txt`, `analysis/<slug>/<slug>_stream.json`, and `analysis/<slug>/index.html` if present.
3. Any setup problem or evidence limitation that affected the result.

Do not summarize the song from memory before reading the Galdr trace. Do not treat lyrics, captions, or background context as proof without checking them. Do not quote metric numbers as if they were the listening experience. Do not overclaim artist intent from structure alone. Do not download or process audio unless the user has appropriate rights or context.
```

That is the main path. The rest of this page is for people who want reusable agent instructions, focused readings, or manual command-line control.

## Reusable Agent Instructions

Use this in `AGENTS.md`, `CLAUDE.md`, Cursor rules, or the nearest equivalent when you want Galdr available in a project all the time.

```md
## Music Analysis With Galdr

When asked to analyze a song, performance, music video, or local audio file, use Galdr when available.

Galdr turns audio into time-ordered listener-state traces. Treat the traces as evidence, not decoration.

Default workflow:
1. Check `galdr --version`. If the command is missing, install Galdr from PyPI or run it from the source repo when the environment allows it. If setup is blocked, tell the operator exactly what is missing.
2. Check that `ffmpeg` is available before processing common audio/video formats.
3. For a YouTube URL, run `galdr fetch "<url>" --analyze` and capture the printed slug.
4. For a local file, run `galdr listen "<path>" --name "<slug>"`.
5. Assemble an ARC prompt with `galdr assemble <slug> --template arc --mode full > prompt.txt`.
6. Read the assembled prompt and `analysis/<slug>/<slug>_stream.json` in time order.
7. Write from timestamped evidence: what changes, when it changes, and how attention is shaped.
8. Return the listening experience plus the local paths to `prompt.txt`, `analysis/<slug>/<slug>_stream.json`, and `analysis/<slug>/index.html` when present.

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
- download or process audio unless the operator has appropriate rights or context
```

See `examples/agent/` for a minimal project-level instruction file.

## Focused Readings

For a specific kind of listening, add one sentence to the copied prompt:

```text
Use the sound lens. I want shape, density, pressure, space, body, and motion.
```

```text
Use the dance lens. I want groove, repetition, build/drop, and bodily use.
```

```text
Use the meaning lens. I want the human situation carried by sound, lyrics, and arrangement.
```

Available lenses are `sound`, `dance`, `structure`, `meaning`, `lyrics-study`, `classical`, and `ritual`.

## What a Good Run Leaves Behind

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

The answer should cite meaningful moments, not dump the files:

```text
At 0:42, pressure comes forward while the pattern stays locked, so the track feels more gathered than louder. Around 1:18, the surface thins and attention shifts upward; that is the first real release rather than a new section label.
```

## Manual Setup

You only need this section if you want to run Galdr yourself instead of asking an agent to do it.

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

## Quick Smoke Test

After setup, ask the agent to run a local file you control:

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
