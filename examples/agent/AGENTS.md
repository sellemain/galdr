# Agent Instructions: Galdr Music Analysis

When the user asks for music analysis in this project, use Galdr if the `galdr` command is available.

Galdr produces listener-state evidence from audio. The stream is the primary source. Do not start from a whole-song mood summary or prior knowledge of the song.

Workflow:
1. Run `galdr --version`.
2. For a local file, run `galdr listen "<path>" --name "<slug>"`.
3. For a YouTube URL, run `galdr fetch "<url>" --analyze` and capture the printed slug.
4. Run `galdr assemble <slug> --template arc --mode full > prompt.txt`.
5. Read `analysis/<slug>/<slug>_stream.json` and `analysis/<slug>/<slug>_perception.json` in time order.
6. Write a concise listening experience with timestamped observations.
7. Return the paths to `prompt.txt`, `analysis/<slug>/<slug>_stream.json`, and `analysis/<slug>/index.html` when present.

Use `galdr assemble <slug> --template arc-family --lens <lens> --mode <mode>` for focused readings:
- `sound` with `blind` mode for shape, pressure, density, space, body, and motion.
- `dance` with `blind` mode for groove, repetition, build/drop, and bodily use.
- `structure` with `blind` mode for form and transition mechanics.
- `meaning` with `full` mode for human situation carried by sound, lyrics, and arrangement.
- `classical` with `blind` mode for instrumental or long-form attention.
- `ritual` with `full` mode only when the recording actually has ritual mechanics.

Do not invent musical claims that are not supported by the trace. Do not quote metric values as prose. Do not pass prompts to an external model unless the operator explicitly asks.
