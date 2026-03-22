# Getting Started with Galdr

## What This Is

Galdr analyzes a piece of music and produces structured data about what it does to a listener — momentum, harmonic structure, breath, pattern, silence. Then you give that data to an AI and ask it to write what it hears.

This is what comes back:

> *It holds you with almost nothing. Five seconds of a piano so quiet the analysis can't even find the harmony in it, and the listener is more locked in than at any other point in the piece. 0.999. You're held by the absence of the thing that hasn't started yet. The room before the door opens.*
>
> *Then it opens wrong. E major — not the key, not even close to the key. The first real sound is the most tense moment in the entire three minutes. It doesn't ease you in. It starts from the place most music builds toward, and then it falls.*
>
> *The cycle starts, and the cycle is the piece. Bm to D to Em to G, over and over. Every time the progression reaches D, something in the body rises a quarter inch. Every time it passes through to Em and G, it sets back down. Not disappointed. Just — not lifted. The piece lives in the space between sad and not-sad, and it never chooses.*
>
> *Time doesn't pass in this piece. It pools.*

— Yann Tiersen, *Comptine d'un autre été*

That's the first use. Give galdr a track. Give an AI the output. Get that back.

The second use is deeper: return to a track with a specific question. Focus on the chords. Focus on the silence structure. Focus on how two pieces compare. The data supports it.

---

## Install

```bash
pip install galdr
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
galdr fetch 'https://www.youtube.com/watch?v=sqZgyvAfhqg' --analyze

# galdr prints the slug at the end:
#   Slug : oliver-anthony-rich-men-north-of-richmond
#   Next : galdr assemble oliver-anthony-rich-men-north-of-richmond --template arc --mode full

# 2. Assemble a structured prompt
galdr assemble oliver-anthony-rich-men-north-of-richmond --template arc --mode full > prompt.txt

# 3. Send to a model
cat prompt.txt | claude
cat prompt.txt | llm
```

That produces something like this: **[Rich Men North of Richmond](rich-men-north-of-richmond.md)**

For a 4-minute track, `fetch --analyze` takes 30–60 seconds.

**If YouTube blocks the download** (rate limit, JS runtime missing), galdr will still fetch lyrics and Wikipedia context and print the slug. You can proceed with `galdr assemble` — the prompt will have lyrics and background but no structural analysis. To skip audio entirely and fetch context only:

```bash
galdr fetch 'https://www.youtube.com/watch?v=sqZgyvAfhqg' --no-download --name oliver-anthony-rich-men-north-of-richmond --artist "Oliver Anthony" --title "Rich Men North of Richmond"
```

---

## Local Files

If you have an audio file already:

```bash
galdr listen track.wav --name my-track
galdr assemble my-track --template arc --mode full | claude
```

Galdr accepts WAV, MP3, FLAC, OGG, M4A, and AIFF via ffmpeg. For freely-licensed recordings: [Free Music Archive](https://freemusicarchive.org), [Internet Archive](https://archive.org/details/audio), [Musopen](https://musopen.org).

---

## Going Deeper

Once you've done a first listen, galdr has more to give.

**Read the perception model first.** The metrics describe listener *attention*, not audio features. High pattern_lock is not mechanical — it may be ritual. Negative breath is not failure — the track may be exhaling. [PERCEPTION-MODEL.md](PERCEPTION-MODEL.md) defines each metric in detail.

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
