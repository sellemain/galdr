"""YouTube Music timed lyric helpers.

This uses ytmusicapi's unofficial YouTube Music browser API emulation. Treat
results as useful timing evidence, not as a canonical lyric authority.
"""

from dataclasses import asdict, is_dataclass
from urllib.parse import parse_qs, urlparse

from .captions import fmt_ts

try:  # pragma: no cover - exercised through monkeypatchable module global.
    from ytmusicapi import YTMusic
except Exception:  # pragma: no cover
    YTMusic = None


def extract_youtube_video_id(url: str | None) -> str | None:
    """Return the 11-character YouTube video id from a watch or short URL."""
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.endswith("youtu.be"):
        candidate = parsed.path.lstrip("/").split("/", maxsplit=1)[0]
        return candidate if len(candidate) == 11 else None
    if host.endswith("youtube.com"):
        candidate = parse_qs(parsed.query).get("v", [None])[0]
        return candidate if candidate and len(candidate) == 11 else None
    return None


def _line_to_dict(line) -> dict:
    if is_dataclass(line):
        return asdict(line)
    if isinstance(line, dict):
        return dict(line)
    if hasattr(line, "__dict__"):
        return vars(line)
    return {"text": str(line)}


def _normalize_timed_lines(lines: list) -> list[dict]:
    normalized: list[dict] = []
    for idx, raw_line in enumerate(lines):
        line = _line_to_dict(raw_line)
        text = str(line.get("text") or "").strip()
        if not text or text in {"♪", "♫"}:
            continue
        start_ms = line.get("start_time")
        if start_ms is None:
            continue
        try:
            start = round(float(start_ms) / 1000.0, 2)
            end_ms = line.get("end_time")
            end = round(float(end_ms) / 1000.0, 2) if end_ms is not None else None
        except (TypeError, ValueError):
            continue
        normalized.append(
            {
                "start": start,
                "end": end,
                "ts": fmt_ts(start),
                "text": text,
                "source": "youtube-music-timed-lyrics",
                "confidence": "provider-timed",
                "line_id": line.get("id", idx),
            }
        )
    return normalized


def fetch_youtube_music_timed_lyrics(video_id: str) -> dict:
    """Fetch normalized timed lyrics for a YouTube video id.

    Returns a small result dict and never raises. ytmusicapi is useful but not
    a stable vendor API, so all parse/network/provider failures degrade to
    ``found=False``.
    """
    if YTMusic is None:
        return {"found": False, "reason": "ytmusicapi unavailable"}
    try:
        ytmusic = YTMusic()
        watch = ytmusic.get_watch_playlist(videoId=video_id)
        browse_id = watch.get("lyrics") if isinstance(watch, dict) else None
        if not browse_id:
            return {"found": False, "reason": "no YouTube Music lyrics browse id"}
        lyrics = ytmusic.get_lyrics(browse_id, timestamps=True)
        if not lyrics or not isinstance(lyrics, dict):
            return {"found": False, "reason": "no YouTube Music lyrics payload"}
        if not lyrics.get("hasTimestamps"):
            return {"found": False, "reason": "YouTube Music lyrics are not timed"}
        timed_lines = _normalize_timed_lines(lyrics.get("lyrics") or [])
        if not timed_lines:
            return {"found": False, "reason": "no usable YouTube Music timed lyric lines"}
        return {
            "found": True,
            "source": "youtube-music-timed-lyrics",
            "provider": "youtube-music",
            "provider_source": lyrics.get("source"),
            "lyrics_browse_id": browse_id,
            "video_id": video_id,
            "has_timestamps": True,
            "line_count": len(timed_lines),
            "timed_lines": timed_lines,
        }
    except Exception as exc:
        return {
            "found": False,
            "reason": "YouTube Music timed lyrics fetch failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
