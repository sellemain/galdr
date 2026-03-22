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

## Get a Track

Galdr accepts WAV, MP3, FLAC, OGG, M4A, and AIFF. If you have a file, use it directly. To pull from YouTube:

```bash
pip install yt-dlp
yt-dlp -x --audio-format mp3 -o "track.%(ext)s" "https://youtube.com/watch?v=..."
```

For freely-licensed recordings: [Free Music Archive](https://freemusicarchive.org), [Internet Archive](https://archive.org/details/audio), [Musopen](https://musopen.org).

---

## Analyze It

```bash
galdr listen track.mp3 --name my-track
```

This runs the full pipeline — audio analysis, perception, harmony, melody, overtone — and writes JSON output to `analysis/my-track/`. For a 4-minute track, expect 30–60 seconds.

---

## Your First Listen

Open `analysis/my-track/my-track_report.json` and `my-track_perception.json`. You'll find tempo, momentum, pattern lock, breath balance, detected key, and structural events.

Now take that data and give it to an AI using the prompt in [FIRST-LISTEN.md](FIRST-LISTEN.md).

The prompt is short. The instruction at the end is: *write what it does — not what it is. To the body, to attention, to time. No format. Just what you hear.*

That's it. That's the first use.

---

## Going Deeper

Once you've done a first listen, galdr has more to give.

**Read the perception model first.** The metrics describe listener *attention*, not audio features. High pattern_lock is not mechanical — it may be ritual. Negative breath is not failure — the track may be exhaling. [PERCEPTION-MODEL.md](PERCEPTION-MODEL.md) defines each metric in detail.

**Focus on one thing.** Run only the harmony module to explore chord structure:

```bash
galdr listen track.mp3 --only report,harmony
```

Pick a question — *why does this feel unresolved?* or *what is the chord doing at 2:30?* — and follow it into the data. The deeper experience documents in [PERCEPTION-MODEL.md](PERCEPTION-MODEL.md) show what this looks like.

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
