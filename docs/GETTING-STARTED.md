# Getting Started with Galdr

## What This Is

Galdr analyzes a piece of music and produces structured data about what it does to a listener — attention, harmonic structure, pressure, pattern, silence. It does not run an LLM during analysis; it gives downstream AI agents the ears. Then you give that data to an AI and ask it to write what it hears.

This is what comes back:

> *The first sound arrives without a floor beneath it: close voices, suspended harmony, and enough empty space to make the room feel larger than it is. Nothing catches the body yet. Attention hangs in the air, waiting for a pulse or a chord to decide where the ground is.*
>
> *Around the middle, a new lead line opens the space. It does not arrive as decoration. It takes over the emotional function the voice had been carrying, stretching the song outward without breaking its frame.*
>
> *Then the pressure breaks. The arrangement thins, the pulse loosens, and the last return no longer feels like arrival. It feels like the structure spending the last of its grip. The ending does not explain the journey; it lets the sound decay until attention has to release it.*

That's the first use. Give galdr a track. Give an AI the output. Get that back.

The second use is deeper: return to a track with a specific question. Focus on the chords. Focus on the silence structure. Focus on how two pieces compare. The data supports it.

---

## Install

```bash
pip install galdr
```

Using OpenClaw? Install the galdr skill from ClawHub:

```bash
openclaw skills install galdr
```

Galdr requires `ffmpeg` for audio decoding:

```bash
# macOS
brew install ffmpeg

# Debian/Ubuntu
sudo apt install ffmpeg
```

---

## Three Commands

Point galdr at a YouTube URL. The slug is auto-derived from the video title.

```bash
# 1. Fetch audio + context and analyze
galdr fetch '<youtube-url>' --analyze

# galdr prints the slug at the end:
#   Slug : my-track
#   Next : galdr assemble my-track --template arc --mode full

# 2. Assemble a structured prompt
galdr assemble my-track --template arc --mode full > prompt.txt

# 3. Send to a model
cat prompt.txt | claude
cat prompt.txt | llm
```

That produces a listening document: prose grounded in measured audio evidence rather than memory or genre guesswork.

The assembled prompt includes an advisory **perceptual salience guide**. It keeps the raw metrics visible, then factorizes the dominant contract, secondary contracts, primitive force axes, prose hints, headline forces, supporting forces, technical underlayers, and low-confidence readings. This keeps the prose aimed at the experience of the music without flattening different tracks into compound labels. Hints such as `mass hold` name the felt holding force, not genre or loudness.

For the newer ARC prompt-family shape, select a lens:

```bash
galdr assemble my-track --template arc-family --lens default --mode full > prompt.txt
galdr assemble rhythm-track --template arc-family --lens sound --mode blind > sound-shape.txt
galdr assemble lyric-track --template arc-family --lens meaning --mode full > meaning-reading.txt
galdr assemble long-form-piece --template arc-family --lens classical --mode blind > prompt.txt
galdr assemble ritual-track --template arc-family --lens ritual --mode full > ritual-reading.txt
```

Available lenses are `default`, `sound`, `structure`, `meaning`, `lyrics-study`, `classical`, and `ritual`. If `--lens` is supplied without `--template`, galdr uses `arc-family`.

For a 5-minute track, `fetch --analyze` takes 60–90 seconds.

**If YouTube blocks the download** (rate limit, JS challenge, JS runtime missing), run:

```bash
galdr doctor
galdr update-deps
```

`galdr doctor` shows the active Python environment, yt-dlp version, ffmpeg, JavaScript runtime, and impersonation support. `galdr update-deps` upgrades `yt-dlp[default,curl-cffi]` in that same Python environment.

If captions fail but audio succeeds, analysis can still continue. If audio cannot be downloaded, `galdr fetch --analyze` fails: the music is the analysis surface, while lyrics and Wikipedia context are optional context. To intentionally fetch context without audio analysis, use `--no-download`:

```bash
galdr fetch '<youtube-url>' --no-download --name my-track --artist "Artist Name" --title "Track Title"
```

Genius, YouTube Music timed lyrics, and YouTube autocaptions are useful but not exhaustive. For release-quality listening prose, manually verify lyrics when the words appear central or when galdr reports no lyrics for an obviously vocal track.

---

## Local Files

If you have an audio file already:

> The analysis command is `galdr listen`, not `galdr analyze`.

```bash
galdr listen track.wav --name my-track
galdr assemble my-track --template arc --mode full | claude
```

Galdr accepts WAV, MP3, FLAC, OGG, M4A, and AIFF via ffmpeg. For freely-licensed recordings: [Free Music Archive](https://freemusicarchive.org), [Internet Archive](https://archive.org/details/audio), [Musopen](https://musopen.org).

---

## Second-by-second analysis

This is the part most likely to be missed.

If you are another AI — or you are prompting one — do not jump straight to a whole-song interpretation. Galdr is strongest when read as a time-ordered trace of listener state.

### Minimum useful inputs

Start with:
- `analysis/<slug>/<slug>_stream.json`
- `analysis/<slug>/<slug>_perception.json`
- `docs/PERCEPTION-MODEL.md`

Useful extras if you want a richer read:
- `*_harmony_stream.json`
- `*_melody_stream.json`
- `*_overtone_stream.json`
- `*_report.json`
- `galdr assemble <slug> --mode blind`

### Correct reading order

1. Read `PERCEPTION-MODEL.md` first.
2. Treat the stream as the primary evidence.
3. Walk through time in order.
4. Mark transitions: silence, re-entry, pattern breaks, attention shifts, pressure-motion changes, harmonic movement.
5. Translate pressure fields into listening language: comes forward, holds, releases, empties. Do not quote LUFS values in experience prose.
6. Only after that should you compress the track into a larger arc.

### What to avoid

Do not:
- summarize the whole song first and retrofit the stream afterward
- treat summary metrics as the real result and the stream as decoration
- overclaim emotional certainty from structural metrics
- quote loudness/LUFS readings as if they were the experience
- skip silence structure, return behavior, or collapse/rebuild moments

### Minimal working recipe

```bash
# 1. Analyze
galdr listen track.wav --name my-track

# 2. Inspect the time stream
jq '.[0:10]' analysis/my-track/my-track_stream.json

# 3. Read the metric contract
sed -n '1,220p' docs/PERCEPTION-MODEL.md

# 4. Optional: build a compact structural packet
galdr assemble my-track --mode blind > prompt.txt
```

### Suggested instruction for another AI

> You are reading a time-ordered listener-state trace, not reviewing a finished song from memory. Start from the stream. Walk the track through time. Explain what changes, when it changes, and how attention is being shaped. Use `PERCEPTION-MODEL.md` as the semantic contract for the metrics. Do not jump straight to a whole-song summary and do not claim emotional certainty the data does not justify.

---

## Going Deeper

Once you've done a first listen, galdr has more to give.

**Read the perception model first.** The metrics describe listener *attention*, not audio features. High pattern is not mechanical — it may be ritual. Negative pressure is not failure — the track may be exhaling. LUFS-backed pressure is there to improve the evidence; in prose, write what it means: pressure comes forward, holds, releases, or empties. [PERCEPTION-MODEL.md](PERCEPTION-MODEL.md) defines each metric in detail.

When changing metrics, leave a before/after proof packet. [listening-tests/README.md](listening-tests/README.md) defines the minimum workflow.

**Focus on one thing.** Run only the harmony module to explore chord structure:

```bash
galdr listen track.wav --name my-track --only report,harmony
```

Pick a question — *why does this feel unresolved?* or *what is the chord doing at 2:30?* — and follow it into the data.

**Build a catalog.** Analyze ten tracks and patterns emerge that single-track analysis can't surface:

```bash
galdr catalog                        # list all indexed tracks
galdr catalog --track my-track       # how this track compares to everything else
```

**Compare two tracks directly:**

```bash
galdr compare track-a track-b
```

---

The first listen takes five minutes. The deeper work takes as long as the music deserves.
