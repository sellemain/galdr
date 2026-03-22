"""galdr fetch — download audio and context for a track.

Downloads audio via yt-dlp, fetches Wikipedia context for artist and song,
parses auto-captions for lyrics. Writes everything to analysis/{slug}/context.json.

This primes the model's associative network before it encounters galdr metrics.
"""

import json
import re
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path


# ─── YouTube / audio ─────────────────────────────────────────────────────────

def download_youtube(url: str, audio_dir: Path, slug: str) -> dict:
    """Download audio and auto-captions from a YouTube URL via yt-dlp."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_out = audio_dir / f"{slug}.%(ext)s"

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--output", str(audio_out),
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "vtt",
        "--no-playlist",
        url,
    ]

    print(f"  [yt-dlp] {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [yt-dlp] stderr: {result.stderr[:300]}")

    audio_file = audio_dir / f"{slug}.mp3"
    # yt-dlp writes VTT as {slug}.en.vtt
    vtt_file = audio_dir / f"{slug}.en.vtt"

    return {
        "audio_file": str(audio_file) if audio_file.exists() else None,
        "captions_file": str(vtt_file) if vtt_file.exists() else None,
        "download_ok": audio_file.exists(),
        "stderr": result.stderr[:500] if result.returncode != 0 else None,
    }


# ─── VTT lyrics parsing ───────────────────────────────────────────────────────

def _parse_ts(ts: str) -> float:
    """Parse VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except (ValueError, IndexError):
        return 0.0


def _fmt_ts(secs: float) -> str:
    m = int(secs) // 60
    s = secs % 60
    return f"{m}:{s:05.2f}"


def _dedup_captions_with_timestamps(segments: list[dict]) -> list[dict]:
    """Produce timestamped lines from rolling YouTube auto-caption segments.

    YouTube captions use a sliding window — each segment overlaps the previous
    by 2–4 words. This function uses the same overlap logic as
    _dedup_rolling_captions but returns one entry per novel chunk, timestamped
    to the moment the new words first appear. Chunks are then merged into
    natural lines (~8–12 words each).

    Returns list of {"ts": str, "start": float, "text": str}.
    """
    # Phase 1: collect novel-word chunks with timestamps
    chunks: list[dict] = []
    seen_words: list[str] = []
    for seg in segments:
        new_words = seg["text"].split()
        if not new_words:
            continue
        max_overlap = min(len(seen_words), len(new_words))
        overlap_len = 0
        for k in range(max_overlap, 0, -1):
            if seen_words[-k:] == new_words[:k]:
                overlap_len = k
                break
        novel = new_words[overlap_len:]
        if novel:
            chunks.append({"ts": seg["ts"], "start": seg["start"], "words": novel})
            seen_words.extend(novel)

    # Phase 2: merge chunks into ~8-word lines
    lines: list[dict] = []
    current_words: list[str] = []
    current_ts = ""
    current_start = 0.0
    line_size = 8

    for chunk in chunks:
        if not current_ts:
            current_ts = chunk["ts"]
            current_start = chunk["start"]
        current_words.extend(chunk["words"])
        if len(current_words) >= line_size:
            lines.append({"ts": current_ts, "start": current_start, "text": " ".join(current_words)})
            current_words = []
            current_ts = ""
    if current_words:
        lines.append({"ts": current_ts, "start": current_start, "text": " ".join(current_words)})

    return lines


def _dedup_rolling_captions(segments: list[dict]) -> str:
    """Build clean full_text from rolling YouTube auto-caption segments.

    YouTube auto-captions use a sliding window — each segment overlaps
    heavily with the previous one. Naively joining all segments produces
    text where each phrase appears 2-3x.

    Strategy: for each segment, find the longest suffix of the
    accumulated text that matches a prefix of the new segment, and only
    append what's new past that overlap.
    """
    result_words: list[str] = []
    for seg in segments:
        new_words = seg["text"].split()
        if not new_words:
            continue
        if not result_words:
            result_words.extend(new_words)
            continue
        # Find the longest overlap: tail of result_words matches prefix of new_words
        max_overlap = min(len(result_words), len(new_words))
        overlap_len = 0
        for k in range(max_overlap, 0, -1):
            if result_words[-k:] == new_words[:k]:
                overlap_len = k
                break
        result_words.extend(new_words[overlap_len:])
    return " ".join(result_words)


def parse_vtt(vtt_path: Path) -> list[dict]:
    """Parse a VTT file into deduplicated timestamped segments.

    YouTube auto-captions use a sliding window — consecutive cues overlap.
    We deduplicate within a small rolling window to collapse these duplicates
    while preserving genuine repetition (choruses, repeated lines).
    """
    lines = vtt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    segments = []
    # Only deduplicate against the last N segments — enough to catch sliding
    # window overlaps but not so large that chorus repetitions get stripped.
    DEDUP_WINDOW = 5
    recent_texts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            parts = line.split("-->")
            start = _parse_ts(parts[0])
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                # Strip VTT inline tags like <c>, </c>, <00:00:01.000>
                clean = re.sub(r"<[^>]+>", "", lines[i].strip())
                if clean:
                    text_lines.append(clean)
                i += 1
            text = " ".join(text_lines).strip()
            if text and text not in recent_texts:
                recent_texts.append(text)
                if len(recent_texts) > DEDUP_WINDOW:
                    recent_texts.pop(0)
                segments.append({
                    "start": round(start, 2),
                    "ts": _fmt_ts(start),
                    "text": text,
                })
        i += 1
    return segments


# ─── Genius lyrics ───────────────────────────────────────────────────────────

def _normalize_for_align(text: str) -> list[str]:
    """Lowercase and tokenize for word-overlap comparison. Drops single chars."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [w for w in text.split() if len(w) > 1]


def _word_overlap(words_a: list[str], words_b: list[str]) -> float:
    """Jaccard similarity between two word lists."""
    if not words_a or not words_b:
        return 0.0
    set_a = set(words_a)
    set_b = set(words_b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _parse_genius_html(html_text: str) -> tuple[list[str], list[str]]:
    """Extract lyric lines and section names from Genius HTML.

    Returns (lyric_lines, sections) where lyric_lines is a flat list of clean
    sung text (section headers like [Chorus] removed), and sections is a list
    of the section names found for reference.

    Genius renders lyrics across 2–4 data-lyrics-container divs. Later
    containers are often duplicates of earlier ones — we deduplicate by
    comparing the first 3 lines of each container.
    """
    import html as htmllib

    positions = [m.start() for m in re.finditer(r'data-lyrics-container="true"', html_text)]
    if not positions:
        return [], []

    # Markers that reliably signal the end of lyrics content on Genius pages
    _end_markers = ["You might also like", "EmbedCancel", "Ask a question", "CreditsReleased"]

    container_lines: list[list[str]] = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else pos + 30000
        # Truncate at Genius metadata/Q&A section if it appears before `end`
        for marker in _end_markers:
            marker_pos = html_text.find(marker, pos)
            if 0 < marker_pos < end:
                end = marker_pos
        chunk = html_text[pos:end]
        chunk = re.sub(r"<br\s*/?>", "\n", chunk)
        chunk = re.sub(r"<[^>]+>", "", chunk)    # strip complete tags
        chunk = re.sub(r"<[^>]*$", "", chunk)     # strip incomplete trailing tag
        chunk = htmllib.unescape(chunk)
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        container_lines.append(lines)

    # Deduplicate containers whose first 3 lines are identical
    seen_starts: set[tuple] = set()
    all_lines: list[str] = []
    for lines in container_lines:
        key = tuple(lines[:3])
        if key in seen_starts:
            continue
        seen_starts.add(key)
        all_lines.extend(lines)

    # Filter Genius UI noise and lines that are clearly not lyrics (prose sentences)
    _noise = {
        "Embed", "Cancel", "How to Format Lyrics", "Lyrics should be",
        "Type out all", "Use the paragraph", "data-lyrics-container",
        "You might also like",
    }
    all_lines = [
        ln for ln in all_lines
        if not any(n in ln for n in _noise)
        and len(ln) < 200  # lyrics lines are short; prose/metadata is long
    ]

    # Separate section headers [Verse 1], [Chorus] etc. from sung lines
    section_pat = re.compile(r"^\[(.+?)\]$")
    lyric_lines: list[str] = []
    sections: list[str] = []
    for line in all_lines:
        m = section_pat.match(line)
        if m:
            sections.append(m.group(1))
        else:
            lyric_lines.append(line)

    return lyric_lines, sections


def _genius_search(artist: str, title: str) -> str | None:
    """Search Genius and return the lyrics page URL, or None."""
    query = urllib.parse.quote(f"{artist} {title}")
    url = f"https://genius.com/api/search?q={query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "galdr/0.1 (music-perception)"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        hits = data.get("response", {}).get("hits", [])
        if hits:
            path = hits[0]["result"]["path"]
            return f"https://genius.com{path}"
    except Exception:
        pass
    return None


def fetch_genius_lyrics(artist: str, title: str) -> dict:
    """Fetch clean lyrics from Genius. Returns dict with found, lines, url."""
    genius_url = _genius_search(artist, title)
    if not genius_url:
        return {"found": False}
    try:
        req = urllib.request.Request(
            genius_url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        html_text = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
        lyric_lines, sections = _parse_genius_html(html_text)
        if not lyric_lines:
            return {"found": False, "url": genius_url, "reason": "no lyrics extracted"}
        return {"found": True, "url": genius_url, "lines": lyric_lines, "sections": sections}
    except Exception as e:
        return {"found": False, "url": genius_url, "error": str(e)}


def align_lyrics_to_captions(
    lyric_lines: list[str],
    caption_segments: list[dict],
    window: int = 15,
    min_score: float = 0.12,
) -> list[dict]:
    """Match clean Genius lyric lines to autocaption segments to borrow timestamps.

    Sequential constraint: each match must be at or after the previous one.
    For repeated choruses, the pointer advances naturally through the verse
    between occurrences, so the second chorus correctly finds the later timestamp.

    After a good match: pointer stays at match position (next line searches from there).
    After a poor match: pointer creeps forward by 1 to avoid getting stuck.

    Returns list of dicts: {text, start, ts, align_score}
    start/ts are None when no good match is found (score < min_score).
    """
    if not caption_segments:
        return [{"text": ln, "start": None, "ts": None, "align_score": 0.0} for ln in lyric_lines]

    cap_words = [_normalize_for_align(seg["text"]) for seg in caption_segments]

    result: list[dict] = []
    cap_idx = 0

    for line in lyric_lines:
        line_words = _normalize_for_align(line)
        if not line_words:
            result.append({"text": line, "start": None, "ts": None, "align_score": 0.0})
            continue

        search_end = min(cap_idx + window, len(caption_segments))
        best_score = 0.0
        best_idx = cap_idx

        for i in range(cap_idx, search_end):
            score = _word_overlap(line_words, cap_words[i])
            if score > best_score:
                best_score = score
                best_idx = i

        if best_score >= min_score:
            seg = caption_segments[best_idx]
            result.append({
                "text": line,
                "start": seg["start"],
                "ts": seg["ts"],
                "align_score": round(best_score, 3),
            })
            cap_idx = best_idx  # stay at match; next line searches from here
        else:
            result.append({"text": line, "start": None, "ts": None, "align_score": 0.0})
            cap_idx = min(cap_idx + 1, len(caption_segments) - 1)  # creep forward

    return result


# ─── Wikipedia ───────────────────────────────────────────────────────────────

def _wiki_request(params: dict) -> dict:
    base = "https://en.wikipedia.org/w/api.php"
    params["format"] = "json"
    url = f"{base}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "galdr/0.1 (music-perception)"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def wikipedia_search(query: str) -> str | None:
    """Return the best-matching Wikipedia article title for a query."""
    try:
        data = _wiki_request({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": "1",
        })
        results = data.get("query", {}).get("search", [])
        return results[0]["title"] if results else None
    except Exception:
        return None


def fetch_wikipedia_intro(title: str, max_chars: int = 2000) -> dict:
    """Fetch the lead/intro section of a Wikipedia article (full intro, not just summary)."""
    try:
        data = _wiki_request({
            "action": "query",
            "prop": "extracts",
            "exintro": "true",
            "explaintext": "true",
            "titles": title,
            "redirects": "1",
        })
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                return {"found": False}
            extract = page.get("extract", "").strip()
            article_title = page.get("title", title)
            return {
                "found": True,
                "title": article_title,
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(article_title.replace(' ', '_'))}",
                "extract": extract[:max_chars],
                "extract_chars": len(extract),
            }
    except Exception as e:
        return {"found": False, "error": str(e)}
    return {"found": False}


def _looks_like_wrong_article(result: dict, expected_name: str) -> bool:
    """Return True if the Wikipedia result is clearly about something else."""
    if not result.get("found"):
        return False
    title = result.get("title", "").lower()
    name_lower = expected_name.lower()
    # If the article title contains none of the words from the query name, suspect
    name_words = set(w for w in name_lower.split() if len(w) > 2)
    title_words = set(title.split())
    return bool(name_words) and not name_words.intersection(title_words)


def fetch_wikipedia_context(
    name: str,
    entity_type: str = "artist",
    exact_title: str | None = None,
) -> dict:
    """Fetch Wikipedia intro with smart disambiguation and fallbacks.

    entity_type: "artist" or "song"
    exact_title: override — use this Wikipedia title directly (skip all fallbacks)
    """
    if exact_title:
        return fetch_wikipedia_intro(exact_title)

    # Try candidates in order
    if entity_type == "artist":
        candidates = [name, f"{name} (band)", f"{name} (musician)", f"{name} (singer)"]
        search_query = f"{name} band musician"
    else:
        candidates = [name, f"{name} (song)", f"{name} (composition)"]
        search_query = f"{name} song music"

    for candidate in candidates:
        result = fetch_wikipedia_intro(candidate)
        if result.get("found") and not _looks_like_wrong_article(result, name):
            return result

    # Search fallback
    found_title = wikipedia_search(search_query)
    if found_title:
        result = fetch_wikipedia_intro(found_title)
        if result.get("found"):
            return result

    return {"found": False, "queried": name}


# ─── Main fetch pipeline ──────────────────────────────────────────────────────

_CENSOR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bnigga(s)?\b', re.IGNORECASE), 'n***a'),
    (re.compile(r'\bnigger(s)?\b', re.IGNORECASE), 'n*****'),
    (re.compile(r'\bmotherfuck\w*', re.IGNORECASE), 'mf'),
    (re.compile(r'\bfucking\b', re.IGNORECASE), 'f***ing'),
    (re.compile(r'\bfucked\b', re.IGNORECASE), 'f***ed'),
    (re.compile(r'\bfucker(s)?\b', re.IGNORECASE), 'f***er'),
    (re.compile(r'\bfuck\b', re.IGNORECASE), 'f***'),
    (re.compile(r'\bshit\b', re.IGNORECASE), 's***'),
    (re.compile(r'\bbitch(es)?\b', re.IGNORECASE), 'b****'),
    (re.compile(r'\bcunt\b', re.IGNORECASE), 'c***'),
]


def censor_lyrics(text: str) -> str:
    """Replace explicit terms with asterisked placeholders to avoid content filter rejections."""
    for pattern, replacement in _CENSOR_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def fetch_track(
    slug: str,
    artist: str,
    title: str,
    analysis_dir: Path,
    audio_dir: Path,
    url: str | None = None,
    skip_download: bool = False,
    skip_wikipedia: bool = False,
    skip_lyrics: bool = False,
    wiki_artist: str | None = None,
    wiki_song: str | None = None,
    censor: bool = False,
) -> dict:
    """Full fetch pipeline. Returns context dict and writes context.json."""

    context = {
        "slug": slug,
        "artist": artist,
        "title": title,
        "youtube_url": url,
    }

    # 1. Download audio + captions
    caption_segments: list[dict] = []
    if url and not skip_download:
        print(f"\n[fetch] Downloading: {artist} — {title}")
        dl = download_youtube(url, audio_dir, slug)
        context["download"] = dl
        if dl["audio_file"]:
            context["audio_file"] = dl["audio_file"]
            print(f"  Audio: {dl['audio_file']}")
        else:
            print("  Audio download failed")

        # Parse captions — always, for timestamps
        if not skip_lyrics and dl.get("captions_file"):
            vtt_path = Path(dl["captions_file"])
            if vtt_path.exists():
                caption_segments = parse_vtt(vtt_path)
                print(f"  Captions: {len(caption_segments)} segments")
            else:
                print("  Captions: VTT file missing")

    # 2. Genius lyrics + captions — stored separately, merged in assemble
    if not skip_lyrics:
        caption_lines: list[dict] = []
        if caption_segments:
            caption_lines = _dedup_captions_with_timestamps(caption_segments)
            print(f"  Caption lines: {len(caption_lines)} (from {len(caption_segments)} segments)")

        print(f"\n[fetch] Genius: {artist} — {title}")
        genius = fetch_genius_lyrics(artist, title)

        if genius["found"]:
            genius_lines = genius["lines"]
            print(f"  Genius: {len(genius_lines)} lines ({genius['url']})")
            source = "genius+autocaptions" if caption_lines else "genius"
            genius_text = "\n".join(genius_lines)
            if censor:
                genius_text = censor_lyrics(genius_text)
                caption_lines = [
                    {**cl, "text": censor_lyrics(cl["text"])} if isinstance(cl, dict) else censor_lyrics(cl)
                    for cl in caption_lines
                ]
                print("  Lyrics censored (--censor)")
            context["lyrics"] = {
                "source": source,
                "genius_url": genius.get("url"),
                "genius_text": genius_text,
                "caption_lines": caption_lines,          # timestamped, may have ASR errors
                "full_text": genius_text,                # backward compat for assemble.py
            }

        elif caption_lines:
            full_text = _dedup_rolling_captions(caption_segments)
            if censor:
                full_text = censor_lyrics(full_text)
                caption_lines = [
                    {**cl, "text": censor_lyrics(cl["text"])} if isinstance(cl, dict) else censor_lyrics(cl)
                    for cl in caption_lines
                ]
                print("  Lyrics censored (--censor)")
            print(f"  Genius failed ({genius.get('reason') or genius.get('error', 'not found')}) — captions only")
            context["lyrics"] = {
                "source": "youtube-auto-captions",
                "caption_lines": caption_lines,
                "full_text": full_text,
                "genius_text": None,
            }

        else:
            context["lyrics"] = {"source": "none", "caption_lines": [], "genius_text": None, "full_text": ""}
            print("  Lyrics: none available")

    # 3. Wikipedia artist context
    if not skip_wikipedia:
        print(f"\n[fetch] Wikipedia: {artist}")
        artist_wiki = fetch_wikipedia_context(
            artist, entity_type="artist", exact_title=wiki_artist
        )
        context["artist_context"] = artist_wiki
        if artist_wiki["found"]:
            print(f"  Artist: {artist_wiki['title']} ({artist_wiki['extract_chars']} chars available, {len(artist_wiki['extract'])} stored)")
        else:
            print(f"  Artist: not found")

        print(f"[fetch] Wikipedia: {title}")
        song_wiki = fetch_wikipedia_context(
            title, entity_type="song", exact_title=wiki_song
        )
        context["song_context"] = song_wiki
        if song_wiki["found"]:
            print(f"  Song:   {song_wiki['title']} ({song_wiki['extract_chars']} chars available, {len(song_wiki['extract'])} stored)")
        else:
            print(f"  Song:   not found")

    # 3. Write context.json
    out_dir = analysis_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    context_path = out_dir / "context.json"
    context_path.write_text(json.dumps(context, indent=2, ensure_ascii=False))
    print(f"\n[fetch] Saved: {context_path}")

    return context
