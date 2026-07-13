"""galdr fetch — download audio and context for a track.

Downloads audio via yt-dlp, fetches Wikipedia context for artist and song,
parses auto-captions for lyrics. Writes everything to analysis/{slug}/context.json.

This primes the model's associative network before it encounters galdr metrics.
"""

import json
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path

from .captions import (
    dedup_captions_with_timestamps,
    dedup_rolling_captions,
    fmt_ts as _fmt_ts,
    parse_ts as _parse_ts,
    parse_vtt,
    parse_vtt_cues,
    timed_lyric_segments,
)
from .provenance import file_sha256, utc_now_iso
from .youtube_music import extract_youtube_video_id, fetch_youtube_music_timed_lyrics


_CONTEXT_CONFIDENCE_MINIMUM = {"high": 3, "medium": 2, "low": 1, "rejected": 0}
_CONTEXT_MATCH_WORD_STOP = {
    "the", "and", "with", "feat", "featuring", "official", "video", "audio",
    "lyrics", "lyric", "live", "remastered", "remaster", "hd", "hq", "music",
    "band", "song", "composition", "musician", "singer",
}
_GENIUS_TRANSLATION_MARKERS = (
    "translation",
    "translations",
    "translated",
    "deutsche übersetzung",
    "deutsche ubersetzung",
    "übersetzung",
    "ubersetzung",
    "traducción",
    "traduccion",
    "tradução",
    "traducao",
    "traduzione",
    "traduction",
    "romanization",
    "romanized",
)
_GENIUS_TRANSLATION_ARTISTS = (
    "genius english translations",
    "genius deutsche übersetzungen",
    "genius deutsche ubersetzungen",
    "genius translations",
)


def _match_tokens(text: str) -> set[str]:
    """Normalize title/artist text into useful identity-match tokens."""
    text = text.lower()
    text = re.sub(r"[’']s\b", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return {
        token
        for token in text.split()
        if len(token) > 2 and token not in _CONTEXT_MATCH_WORD_STOP
    }


def _identity_match_score(expected: str, candidate: str) -> tuple[float, list[str]]:
    """Return token-overlap score and human-readable match reasons."""
    expected_tokens = _match_tokens(expected)
    candidate_tokens = _match_tokens(candidate)
    if not expected_tokens:
        return 0.0, ["no expected identity tokens"]
    overlap = expected_tokens & candidate_tokens
    score = len(overlap) / len(expected_tokens)
    reasons = [f"matched tokens: {', '.join(sorted(overlap))}"] if overlap else ["no identity-token overlap"]
    return score, reasons


def _confidence_from_score(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    if score > 0:
        return "low"
    return "rejected"


def _is_genius_translation_hit(hit: dict) -> tuple[bool, str | None]:
    """Return whether a Genius search result is a translation/romanization page.

    These pages can score as perfect identity matches because Genius often puts
    the original artist and title inside the translated page title while the
    primary artist is a generic translation account.
    """
    title = str(hit.get("title") or "")
    artist = str(hit.get("artist") or "")
    full_title = str(hit.get("full_title") or "")
    url = str(hit.get("url") or "")
    haystack = " ".join([title, artist, full_title, url]).lower()
    artist_l = artist.lower()
    bracketed_title = re.search(
        r"[\[(][^\])]*(translation|übersetzung|ubersetzung|traducción|traduccion|tradução|traducao|traduzione|traduction|romanized|romanization)[^\])]*[\])]",
        title.lower(),
    )
    if bracketed_title:
        return True, f"translation marker in title: {bracketed_title.group(0)}"
    for marker in _GENIUS_TRANSLATION_ARTISTS:
        if marker in artist_l:
            return True, f"translation artist: {artist}"
    for marker in _GENIUS_TRANSLATION_MARKERS:
        if marker in haystack:
            return True, f"translation marker: {marker}"
    return False, None


_EJS_FAILURE_MARKERS = (
    "remote components challenge solver",
    "challenge solving failed",
    "n challenge",
    "some formats may be missing",
    "ejs",
)


def _yt_dlp_base_cmd(remote_components: bool = False) -> list[str]:
    """Return yt-dlp command for the current Python environment.

    Using ``python -m yt_dlp`` avoids accidentally picking up a stale system
    yt-dlp binary from PATH when galdr is installed in a virtual environment.
    """
    cmd = [sys.executable, "-m", "yt_dlp"]
    if remote_components:
        cmd += ["--remote-components", "ejs:github"]
    for runtime in ("node", "deno", "phantomjs"):
        path = shutil.which(runtime)
        if path:
            cmd += ["--js-runtimes", f"{runtime}:{path}"]
            break
    return cmd


def _looks_like_ejs_failure(stderr: str) -> bool:
    """Return True when yt-dlp failed in a YouTube JS challenge/EJS path."""
    text = (stderr or "").lower()
    return any(marker in text for marker in _EJS_FAILURE_MARKERS)


def _run_yt_dlp(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run yt-dlp and retry once with remote EJS components for challenge failures.

    The first attempt relies on locally installed yt-dlp EJS support. If YouTube
    still reports challenge/EJS failure, retry once with yt-dlp's explicit
    remote EJS component source. This downloads solver code from GitHub, so the
    retry is logged visibly.
    """
    cmd = _yt_dlp_base_cmd() + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode == 0 or not _looks_like_ejs_failure(result.stderr):
        return result

    print("  [yt-dlp] YouTube challenge/EJS failure detected; retrying with remote EJS components from GitHub")
    retry_cmd = _yt_dlp_base_cmd(remote_components=True) + args
    retry = subprocess.run(retry_cmd, capture_output=True, text=True, timeout=timeout)
    if retry.returncode == 0:
        return retry

    retry.stderr = (
        f"{result.stderr}\n"
        "--- remote EJS retry stderr ---\n"
        f"{retry.stderr}"
    )
    return retry


# ─── Input validation ─────────────────────────────────────────────────────────

# Accepts standard youtube.com and youtu.be URLs only.
# Prevents option-like strings from being interpreted by yt-dlp as flags.
_YOUTUBE_URL_RE = re.compile(
    r"^https?://(www\.)?(youtube\.com/watch\?.*v=|youtu\.be/)[A-Za-z0-9_\-]{11}"
)

_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_youtube_url(url: str) -> str:
    """Reject URLs that don't look like YouTube watch links.

    Prevents option-like strings (e.g. '--exec rm -rf /') from being passed
    to yt-dlp as positional arguments.
    """
    if not _YOUTUBE_URL_RE.match(url):
        raise ValueError(
            f"Invalid YouTube URL: {url!r}. Expected a youtube.com/watch or youtu.be link."
        )
    return url


def validate_slug(slug: str) -> str:
    """Reject slugs that could escape the analysis directory.

    Safe for use by library callers (not just the CLI entrypoint).
    """
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug {slug!r}. Slugs may only contain letters, digits, "
            "dots, hyphens, and underscores."
        )
    parts = slug.replace("\\", "/").split("/")
    if any(p in (".", "..") or p == "" for p in parts):
        raise ValueError(f"Invalid slug: {slug!r}")
    return slug


# ─── YouTube / audio ─────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert a title string to a filesystem-safe slug.

    "Katy Perry - Chained To The Rhythm (Official) ft. Skip Marley"
    → "katy-perry-chained-to-the-rhythm"
    """
    text = text.lower()
    # Remove parenthetical suffixes: (Official), (Official Video), (Lyrics), etc.
    text = re.sub(r"\([^)]*\)", "", text)
    # Remove common suffix tags after pipe or brackets
    text = re.sub(r"\[[^\]]*\]", "", text)
    # Normalise separator characters to spaces
    text = re.sub(r"[–—/|]+", " ", text)
    # Strip ft./feat. and everything after
    text = re.sub(r"\bft\..*$|\bfeat\..*$", "", text)
    # Keep only letters, digits, spaces, hyphens
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    # Collapse whitespace → hyphens, strip leading/trailing
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:80]  # reasonable max length


def get_youtube_metadata(url: str) -> dict:
    """Fetch video metadata from YouTube without downloading audio.

    Returns dict with 'title', 'uploader', 'channel' keys (strings).
    Raises RuntimeError on failure (with stderr context).
    """
    url = validate_youtube_url(url)
    result = _run_yt_dlp(["--dump-json", "--no-playlist", url], timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata failed: {result.stderr[:300]}")
    info = json.loads(result.stdout)
    return {
        "title": info.get("title", ""),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "channel": info.get("channel") or info.get("uploader") or "",
    }


def derive_artist_title(yt_title: str, uploader: str) -> tuple[str, str]:
    """Split a YouTube title into (artist, song_title).

    Handles common formats:
      "Artist - Song Title" → ("Artist", "Song Title")
      "Song Title" (no dash) → (uploader, "Song Title")
    """
    # Try "Artist - Title" or "Artist — Title"
    m = re.match(r"^(.+?)\s*[-–—]\s*(.+)$", yt_title)
    if m:
        artist_part = m.group(1).strip()
        title_part = m.group(2).strip()
        # Strip parentheticals/suffixes from title_part
        title_part = re.sub(r"\s*[\(\[].*", "", title_part).strip()
        return artist_part, title_part
    # No separator — use uploader as artist
    clean_title = re.sub(r"\s*[\(\[].*", "", yt_title).strip()
    return uploader, clean_title


def _caption_language_tag(path: Path, slug: str) -> str:
    stem = path.name
    prefix = f"{slug}."
    suffix = ".vtt"
    if stem.startswith(prefix) and stem.endswith(suffix):
        return stem[len(prefix) : -len(suffix)]
    return ""


def _preferred_caption_file(candidates: list[Path], slug: str) -> Path | None:
    """Pick the most useful downloaded VTT for lyric timing.

    Manual original-language captions often sit next to English translations.
    Prefer a non-English manual track when one exists; otherwise fall back to
    English/manual or English auto-caption tracks.
    """
    usable = [path for path in sorted(candidates) if "live_chat" not in path.name]
    if not usable:
        return None
    for path in usable:
        lang = _caption_language_tag(path, slug).lower()
        if lang and not lang.startswith("en"):
            return path
    return usable[0]


def download_youtube(url: str, audio_dir: Path, slug: str) -> dict:
    """Download audio and captions from a YouTube URL via yt-dlp.

    Audio and captions are deliberately separate calls. YouTube caption requests
    can fail with rate limits or missing subtitles; that should not block audio
    analysis when the media download itself succeeded.
    """
    url = validate_youtube_url(url)
    slug = validate_slug(slug)
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_out = audio_dir / f"{slug}.%(ext)s"

    audio_args = [
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--output", str(audio_out),
        "--no-playlist",
        url,
    ]

    print(f"  [yt-dlp] {url}")
    audio_result = _run_yt_dlp(audio_args, timeout=300)
    if audio_result.returncode != 0:
        audio_stderr = audio_result.stderr[:500]
        print(f"  [yt-dlp] stderr: {audio_result.stderr[:300]}")
        # Surface a clearer error for common cases
        if "Video unavailable" in audio_result.stderr:
            print(f"  [yt-dlp] Video unavailable — likely removed, region-locked, or private.")
        elif "Sign in" in audio_result.stderr or "age" in audio_result.stderr.lower():
            print(f"  [yt-dlp] Age-gated or login required — try a SoundCloud URL instead.")
    else:
        audio_stderr = None

    audio_file = audio_dir / f"{slug}.mp3"

    captions_stderr = None
    if audio_file.exists():
        manual_captions_args = [
            "--skip-download",
            "--write-subs",
            "--sub-langs", "all,-live_chat",
            "--sub-format", "vtt",
            "--output", str(audio_out),
            "--no-playlist",
            url,
        ]
        captions_result = _run_yt_dlp(manual_captions_args, timeout=120)
        if captions_result.returncode != 0:
            captions_stderr = captions_result.stderr[:500]
            print(f"  [yt-dlp] manual captions unavailable: {captions_result.stderr[:300]}")

        if not list(audio_dir.glob(f"{slug}.*.vtt")):
            auto_captions_args = [
                "--skip-download",
                "--write-auto-subs",
                "--sub-langs", "en.*,en",
                "--sub-format", "vtt",
                "--output", str(audio_out),
                "--no-playlist",
                url,
            ]
            captions_result = _run_yt_dlp(auto_captions_args, timeout=120)
            if captions_result.returncode != 0:
                captions_stderr = captions_result.stderr[:500]
                print(f"  [yt-dlp] auto captions unavailable: {captions_result.stderr[:300]}")

    # yt-dlp language tag varies (en, en-US, en-orig, etc.) — find whatever landed
    vtt_candidates = sorted(audio_dir.glob(f"{slug}.*.vtt"))
    vtt_file = _preferred_caption_file(vtt_candidates, slug) or audio_dir / f"{slug}.en.vtt"

    return {
        "audio_file": str(audio_file) if audio_file.exists() else None,
        "captions_file": str(vtt_file) if vtt_file.exists() else None,
        "download_ok": audio_file.exists(),
        "downloaded_at": utc_now_iso() if audio_file.exists() else None,
        "audio_sha256": file_sha256(audio_file) if audio_file.exists() else None,
        "stderr": audio_stderr or captions_stderr,
        "audio_stderr": audio_stderr,
        "captions_stderr": captions_stderr,
    }


# ─── VTT lyrics parsing ───────────────────────────────────────────────────────

# Caption parsing lives in galdr.captions. Keep private aliases for compatibility.
_dedup_captions_with_timestamps = dedup_captions_with_timestamps
_dedup_rolling_captions = dedup_rolling_captions


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

    return _sanitize_lyric_lines(lyric_lines), sections


_GENIUS_NOISE_PATTERNS = (
    re.compile(r"^See .{1,80}? LiveGet tickets as low as \$?\d+", re.IGNORECASE),
    re.compile(r"^You might also like$", re.IGNORECASE),
    re.compile(r"^Embed$", re.IGNORECASE),
    re.compile(r"^\d*Embed$", re.IGNORECASE),
)


def _sanitize_lyric_lines(lines: list[str]) -> list[str]:
    """Remove scraper UI/CTA residue from extracted lyric lines."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if any(pattern.search(line) for pattern in _GENIUS_NOISE_PATTERNS):
            continue
        if "LiveGet tickets" in line or "Get tickets as low as" in line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return cleaned


def _genius_search(artist: str, title: str) -> dict | None:
    """Search Genius and return the best non-translation hit metadata, or None."""
    query = urllib.parse.quote(f"{artist} {title}")
    url = f"https://genius.com/api/search?q={query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "galdr/0.1 (music-perception)"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        hits = data.get("response", {}).get("hits", [])
        rejected: list[dict] = []
        for raw_hit in hits:
            result = raw_hit["result"]
            path = result.get("path")
            hit = {
                "url": f"https://genius.com{path}" if path else None,
                "title": result.get("title") or result.get("full_title") or "",
                "artist": (result.get("primary_artist") or {}).get("name", ""),
                "full_title": result.get("full_title", ""),
            }
            is_translation, reason = _is_genius_translation_hit(hit)
            if is_translation:
                rejected.append({**hit, "reason": reason})
                continue
            hit["rejected_translation_hits"] = rejected
            return hit
    except Exception:
        pass
    return None


def _score_genius_hit(hit: dict, artist: str, title: str) -> dict:
    candidate = " ".join(
        str(hit.get(part) or "")
        for part in ("title", "artist", "full_title")
    )
    title_score, title_reasons = _identity_match_score(title, candidate)
    artist_score, artist_reasons = _identity_match_score(artist, candidate)
    score = round((title_score * 0.7) + (artist_score * 0.3), 3)
    confidence = _confidence_from_score(score)
    return {
        "confidence": confidence,
        "match_score": score,
        "match_reasons": [
            f"title {title_score:.2f}: {'; '.join(title_reasons)}",
            f"artist {artist_score:.2f}: {'; '.join(artist_reasons)}",
        ],
        "use_in_prompt": _CONTEXT_CONFIDENCE_MINIMUM[confidence] >= 2,
    }


def fetch_genius_lyrics(artist: str, title: str) -> dict:
    """Fetch clean lyrics from Genius with identity confidence metadata."""
    genius_hit = _genius_search(artist, title)
    if not genius_hit or not genius_hit.get("url"):
        return {"found": False, "reason": "no non-translation Genius match"}
    genius_url = genius_hit["url"]
    confidence = _score_genius_hit(genius_hit, artist, title)
    if not confidence["use_in_prompt"]:
        return {
            "found": False,
            "url": genius_url,
            "reason": "low confidence Genius match",
            **confidence,
            "candidate_title": genius_hit.get("title", ""),
            "candidate_artist": genius_hit.get("artist", ""),
            "rejected_translation_hits": genius_hit.get("rejected_translation_hits", []),
        }
    try:
        req = urllib.request.Request(
            genius_url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        html_text = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
        lyric_lines, sections = _parse_genius_html(html_text)
        if not lyric_lines:
            return {"found": False, "url": genius_url, "reason": "no lyrics extracted", **confidence}
        return {
            "found": True,
            "url": genius_url,
            "lines": lyric_lines,
            "sections": sections,
            **confidence,
            "candidate_title": genius_hit.get("title", ""),
            "candidate_artist": genius_hit.get("artist", ""),
            "rejected_translation_hits": genius_hit.get("rejected_translation_hits", []),
        }
    except Exception as e:
        return {"found": False, "url": genius_url, "error": str(e), **confidence}


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


def wikipedia_search(query: str, limit: int = 5) -> list[str]:
    """Return candidate Wikipedia article titles for a query."""
    try:
        data = _wiki_request({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(limit),
        })
        results = data.get("query", {}).get("search", [])
        return [result["title"] for result in results if result.get("title")]
    except Exception:
        return []


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


def _looks_like_disambiguation_stub(result: dict) -> bool:
    """Return True when a Wikipedia intro is a disambiguation/list page."""
    extract = str(result.get("extract", "")).strip().lower()
    title = str(result.get("title", "")).strip().lower()
    if "disambiguation" in title:
        return True
    if not extract:
        return False
    first_line = extract.splitlines()[0].strip() if extract.splitlines() else extract
    return (
        first_line in {f"{title} may refer to:", f"{title} or {title}s may refer to:"}
        or first_line.endswith(" may refer to:")
        or first_line.endswith(" may also refer to:")
    )


def _score_wikipedia_result(
    result: dict,
    expected_name: str,
    entity_type: str,
    expected_artist: str | None = None,
) -> dict:
    """Attach confidence metadata to a Wikipedia intro result.

    Song titles are often ambiguous (``Dreams``, ``Alright``, translated
    titles, etc.). Title overlap alone is not enough for a prompt-safe song
    context when we know the artist, so require artist evidence for song pages
    before allowing them into prompts.
    """
    if not result.get("found"):
        return {"confidence": "rejected", "match_score": 0.0, "match_reasons": ["not found"], "use_in_prompt": False}
    if _looks_like_disambiguation_stub(result):
        return {
            "confidence": "rejected",
            "match_score": 0.0,
            "match_reasons": ["Wikipedia disambiguation stub"],
            "use_in_prompt": False,
        }

    title_score, title_reasons = _identity_match_score(expected_name, result.get("title", ""))
    extract_score, extract_reasons = _identity_match_score(expected_name, result.get("extract", ""))
    score = round(max(title_score, min(1.0, title_score + (extract_score * 0.25))), 3)
    confidence = _confidence_from_score(score)

    match_reasons = [
        f"title {title_score:.2f}: {'; '.join(title_reasons)}",
        f"extract {extract_score:.2f}: {'; '.join(extract_reasons)}",
    ]

    if entity_type == "song" and expected_artist:
        artist_score, artist_reasons = _identity_match_score(
            expected_artist,
            f"{result.get('title', '')} {result.get('extract', '')}",
        )
        match_reasons.append(f"artist {artist_score:.2f}: {'; '.join(artist_reasons)}")
        if artist_score <= 0:
            return {
                "confidence": "rejected",
                "match_score": score,
                "match_reasons": match_reasons + ["song context lacks expected artist evidence"],
                "use_in_prompt": False,
            }

    # Song/composition pages can be valid with partial title matches, especially
    # traditional titles that pick up a related article. Artist pages should be
    # stricter; wrong artist context is usually worse than no context.
    use_in_prompt = _CONTEXT_CONFIDENCE_MINIMUM[confidence] >= (1 if entity_type == "song" else 2)
    return {
        "confidence": confidence,
        "match_score": score,
        "match_reasons": match_reasons,
        "use_in_prompt": use_in_prompt,
    }


def _looks_like_wrong_article(result: dict, expected_name: str) -> bool:
    """Return True if the Wikipedia result is clearly about something else."""
    scored = _score_wikipedia_result(result, expected_name, "artist")
    return scored["confidence"] == "rejected"


def _with_wikipedia_confidence(
    result: dict,
    expected_name: str,
    entity_type: str,
    expected_artist: str | None = None,
) -> dict:
    if not result.get("found"):
        return result
    return {
        **result,
        **_score_wikipedia_result(
            result,
            expected_name,
            entity_type,
            expected_artist=expected_artist,
        ),
    }


def fetch_wikipedia_context(
    name: str,
    entity_type: str = "artist",
    exact_title: str | None = None,
    expected_artist: str | None = None,
) -> dict:
    """Fetch Wikipedia intro with smart disambiguation and fallbacks.

    entity_type: "artist" or "song"
    exact_title: override — use this Wikipedia title directly (skip all fallbacks)
    expected_artist: for song contexts, require artist evidence before prompt use
    """
    if exact_title:
        result = fetch_wikipedia_intro(exact_title)
        if result.get("found"):
            scored = _score_wikipedia_result(
                result,
                name,
                entity_type,
                expected_artist=expected_artist,
            )
            return {
                **result,
                **scored,
            }
        return result

    # Try candidates in order. For artists, prefer music-qualified pages before
    # bare titles; bare titles are often disambiguation or non-music concepts.
    if entity_type == "artist":
        candidates = [f"{name} (band)", f"{name} (musician)", f"{name} (singer)", name]
        search_query = f"{name} band musician"
    else:
        candidates = [name, f"{name} (song)", f"{name} (composition)"]
        if expected_artist:
            candidates = [
                f"{name} ({expected_artist} song)",
                f"{name} ({expected_artist})",
                *candidates,
            ]
            search_query = f"{name} {expected_artist} song music"
        else:
            search_query = f"{name} song music"

    for candidate in candidates:
        result = fetch_wikipedia_intro(candidate)
        if result.get("found") and not _looks_like_wrong_article(result, name):
            scored = _with_wikipedia_confidence(
                result,
                name,
                entity_type,
                expected_artist=expected_artist,
            )
            if scored.get("use_in_prompt"):
                return scored

    # Search fallback: inspect several candidates and choose the highest-scoring
    # prompt-usable result instead of blindly accepting the first hit.
    best_result = None
    best_score = -1.0
    for found_title in wikipedia_search(search_query):
        result = fetch_wikipedia_intro(found_title)
        if not result.get("found"):
            continue
        scored = _with_wikipedia_confidence(
            result,
            name,
            entity_type,
            expected_artist=expected_artist,
        )
        if not scored.get("use_in_prompt"):
            continue
        score = float(scored.get("match_score", 0.0))
        if score > best_score:
            best_result = scored
            best_score = score
    if best_result:
        return best_result

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
    slug = validate_slug(slug)
    if url and not skip_download:
        url = validate_youtube_url(url)

    context = {
        "slug": slug,
        "artist": artist,
        "title": title,
        "youtube_url": url,
        "source": {
            "kind": "youtube" if url else "local",
            "url": url,
            "source_id": slug,
            "created_at": utc_now_iso(),
        },
    }

    # 1. Download audio + captions
    caption_segments: list[dict] = []
    timed_caption_lines: list[dict] = []
    if url and not skip_download:
        print(f"\n[fetch] Downloading: {artist} — {title}")
        dl = download_youtube(url, audio_dir, slug)
        context["download"] = dl
        if dl["audio_file"]:
            context["audio_file"] = dl["audio_file"]
            context["source"].update({
                "audio_path": dl["audio_file"],
                "downloaded_at": dl.get("downloaded_at"),
                "audio_sha256": dl.get("audio_sha256"),
            })
            print(f"  Audio: {dl['audio_file']}")
        else:
            print("  Audio download failed")

        # Parse captions — always, for timestamps
        if not skip_lyrics and dl.get("captions_file"):
            vtt_path = Path(dl["captions_file"])
            if vtt_path.exists():
                caption_segments = parse_vtt(vtt_path)
                caption_cues = parse_vtt_cues(vtt_path)
                timed_caption_lines = timed_lyric_segments(caption_cues)
                print(
                    f"  Captions: {len(caption_segments)} segments; "
                    f"{len(timed_caption_lines)} timed lyric cues accepted"
                )
            else:
                print("  Captions: VTT file missing")

    # 2. Lyrics sources — stored separately, merged in assemble
    if not skip_lyrics:
        caption_lines: list[dict] = []
        if timed_caption_lines:
            caption_lines = timed_caption_lines
            print(f"  Caption lines: {len(caption_lines)} accepted as timed lyric evidence")
        elif caption_segments:
            print("  Caption lines: none accepted as timed lyric evidence")

        timed_lines: list[dict] = []
        timed_lyrics_source: dict | None = None
        if url:
            video_id = extract_youtube_video_id(url)
            if video_id:
                print(f"\n[fetch] YouTube Music timed lyrics: {video_id}")
                ytmusic = fetch_youtube_music_timed_lyrics(video_id)
                if ytmusic.get("found"):
                    timed_lines = ytmusic.get("timed_lines", [])
                    timed_lyrics_source = {
                        "source": ytmusic.get("source"),
                        "provider": ytmusic.get("provider"),
                        "provider_source": ytmusic.get("provider_source"),
                        "lyrics_browse_id": ytmusic.get("lyrics_browse_id"),
                        "video_id": ytmusic.get("video_id"),
                        "has_timestamps": ytmusic.get("has_timestamps"),
                        "line_count": ytmusic.get("line_count"),
                    }
                    print(
                        f"  YouTube Music: {len(timed_lines)} timed lines"
                        + (
                            f" ({ytmusic.get('provider_source')})"
                            if ytmusic.get("provider_source")
                            else ""
                        )
                    )
                else:
                    print(
                        "  YouTube Music: "
                        f"{ytmusic.get('reason') or ytmusic.get('error') or 'not found'}"
                    )

        print(f"\n[fetch] Genius: {artist} — {title}")
        genius = fetch_genius_lyrics(artist, title)

        if genius["found"]:
            genius_lines = genius["lines"]
            print(f"  Genius: {len(genius_lines)} lines ({genius['url']})")
            if timed_lines:
                source = "genius+youtube-music-timed-lyrics"
            elif caption_lines:
                source = "genius+autocaptions"
            else:
                source = "genius"
            genius_text = "\n".join(genius_lines)
            if censor:
                genius_text = censor_lyrics(genius_text)
                timed_lines = [
                    {**line, "text": censor_lyrics(line["text"])}
                    if isinstance(line, dict)
                    else censor_lyrics(line)
                    for line in timed_lines
                ]
                caption_lines = [
                    {**cl, "text": censor_lyrics(cl["text"])} if isinstance(cl, dict) else censor_lyrics(cl)
                    for cl in caption_lines
                ]
                print("  Lyrics censored (--censor)")
            context["lyrics"] = {
                "source": source,
                "genius_url": genius.get("url"),
                "confidence": genius.get("confidence"),
                "match_score": genius.get("match_score"),
                "match_reasons": genius.get("match_reasons", []),
                "use_in_prompt": genius.get("use_in_prompt", True),
                "candidate_title": genius.get("candidate_title"),
                "candidate_artist": genius.get("candidate_artist"),
                "genius_text": genius_text,
                "timed_lines": timed_lines,              # provider-timed line evidence
                "timed_lyrics_source": timed_lyrics_source,
                "caption_lines": caption_lines,          # timestamped, may have ASR errors
                "full_text": genius_text,                # backward compat for assemble.py
            }

        elif timed_lines or caption_lines:
            if timed_lines:
                full_text = "\n".join(line["text"] for line in timed_lines)
            else:
                full_text = dedup_rolling_captions(caption_segments)
            if censor:
                full_text = censor_lyrics(full_text)
                timed_lines = [
                    {**line, "text": censor_lyrics(line["text"])}
                    if isinstance(line, dict)
                    else censor_lyrics(line)
                    for line in timed_lines
                ]
                caption_lines = [
                    {**cl, "text": censor_lyrics(cl["text"])} if isinstance(cl, dict) else censor_lyrics(cl)
                    for cl in caption_lines
                ]
                print("  Lyrics censored (--censor)")
            source = "youtube-music-timed-lyrics" if timed_lines else "youtube-auto-captions"
            print(
                f"  Genius failed ({genius.get('reason') or genius.get('error', 'not found')})"
                f" — {'YouTube Music timed lyrics' if timed_lines else 'captions'} only"
            )
            context["lyrics"] = {
                "source": source,
                "timed_lines": timed_lines,
                "timed_lyrics_source": timed_lyrics_source,
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
            title, entity_type="song", exact_title=wiki_song, expected_artist=artist
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
