# Galdr Agent Fixture

This directory is a minimal example for people who want to point a coding or chat agent at Galdr.

For a first run, use the happy-path prompt in [`docs/AGENT-ONBOARDING.md`](../../docs/AGENT-ONBOARDING.md).

For a repeatable project setup, copy `AGENTS.md` into a small project where your agent can run shell commands, then ask:

```text
Use Galdr to analyze ./track.wav. Walk the track through time and return three timestamped changes plus the artifact paths.
```

For YouTube:

```text
Use Galdr to analyze this performance:
<url>

Walk the track through time. Use timestamped listener-state evidence, not music trivia. Return a concise listening experience and link the generated Galdr artifacts.
```

Expected run shape:

```bash
galdr --version
galdr listen ./track.wav --name track
galdr assemble track --template arc --mode full > prompt.txt
```

Or:

```bash
galdr fetch "<url>" --analyze
galdr assemble <printed-slug> --template arc --mode full > prompt.txt
```

The important output is not the command transcript. It is an agent answer grounded in `analysis/<slug>/<slug>_stream.json`, with local artifact paths preserved for review.
