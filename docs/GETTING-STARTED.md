# Getting Started with Galdr

## What This Is

Galdr analyzes a piece of music and produces structured data about what it does to a listener — momentum, harmonic structure, breath, pattern, silence. Then you give that data to an AI and ask it to write what it hears.

This is what comes back:

> *The voices arrive before anything else—unaccompanied, stacked in close harmony, asking questions that float without a floor beneath them. "Is this the real life? Is this just fantasy?" The absence of instruments makes the air feel pressurized. You're waiting for something to catch you, and nothing does. Just voices in the dark, layered and intimate, until a piano enters and suddenly there's ground.*
>
> *Around 2:37, the guitar enters—not suddenly, but like a door opening into a different room. The solo doesn't comment on the lyrics; it extends the ache into wordless space, bending notes that feel like questions without answers.*
>
> *Then the storm breaks. The piano comes back alone, and the voice re-enters softened, exhausted: "Nothing really matters, anyone can see." The final phrase floats, untethered again, back to where the song began: voices without ground. Around 5:44, small pattern breaks ripple through—the structure loosening, letting go. Eight seconds of nothing close the piece, the sound decaying into stillness.*

— Queen, *Bohemian Rhapsody*

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
galdr fetch 'https://www.youtube.com/watch?v=fJ9rUzIMcZQ' --analyze

# galdr prints the slug at the end:
#   Slug : queen-bohemian-rhapsody
#   Next : galdr assemble queen-bohemian-rhapsody --template arc --mode full

# 2. Assemble a structured prompt
galdr assemble queen-bohemian-rhapsody --template arc --mode full > prompt.txt

# 3. Send to a model
cat prompt.txt | claude
cat prompt.txt | llm
```

That produces something like this: **[Queen — Bohemian Rhapsody](bohemian-rhapsody.md)**

For a 5-minute track, `fetch --analyze` takes 60–90 seconds.

**If YouTube blocks the download** (rate limit, JS runtime missing), galdr will still fetch lyrics and Wikipedia context and print the slug. You can proceed with `galdr assemble` — the prompt will have lyrics and background but no structural analysis. To skip audio entirely and fetch context only:

```bash
galdr fetch 'https://www.youtube.com/watch?v=fJ9rUzIMcZQ' --no-download --name queen-bohemian-rhapsody --artist "Queen" --title "Bohemian Rhapsody"
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
