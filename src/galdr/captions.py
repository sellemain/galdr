"""Caption parsing and deduplication helpers for galdr."""

from dataclasses import asdict, dataclass
import re
from pathlib import Path


MUSIC_NOTE_GLYPHS = "♪♫♬♩"
STAGE_WORDS = (
    "music|instrumental|piano|guitar|drum|drums|solo|applause|cheering|"
    "laughter|audience|intro|outro|chanting|singing|vocalizing"
)
STAGE_MARKER_RE = re.compile(
    rf"\b({STAGE_WORDS})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TimedCaptionCue:
    """Raw timed caption cue plus a conservative lyric-evidence classification."""

    start: float
    end: float | None
    ts: str
    text: str
    normalized_text: str
    kind: str
    confidence: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_ts(ts: str) -> float:
    """Parse VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except (ValueError, IndexError):
        return 0.0


def fmt_ts(secs: float) -> str:
    """Format seconds as M:SS.ss for caption timestamps."""
    m = int(secs) // 60
    s = secs % 60
    return f"{m}:{s:05.2f}"


def _strip_caption_markup(text: str) -> str:
    """Remove VTT/HTML tags and normalize whitespace."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = clean.replace("&amp;", "&").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", clean).strip()


def _strip_lyric_wrappers(text: str) -> str:
    """Remove music-note wrapper glyphs without treating them as stage markers."""
    clean = text.strip()
    clean = clean.strip(MUSIC_NOTE_GLYPHS + " \t")
    clean = re.sub(rf"^[{re.escape(MUSIC_NOTE_GLYPHS)}\s]+", "", clean)
    clean = re.sub(rf"[{re.escape(MUSIC_NOTE_GLYPHS)}\s]+$", "", clean)
    return re.sub(r"\s+", " ", clean).strip()


def classify_caption_text(text: str) -> dict:
    """Classify one caption cue as timed lyric evidence or non-lyric caption text.

    This is deliberately conservative. Raw timed captions are still useful, but
    lyric/audio convergence prose should only use cues marked as ``lyric`` with
    accepted confidence. Short ASR shards and explicit stage/instrumental cues
    stay caption evidence rather than lyric evidence.
    """
    raw = _strip_caption_markup(text)
    normalized = _strip_lyric_wrappers(raw)
    bracketed_stage = bool(re.fullmatch(r"[\[(].*[\])]", normalized)) and STAGE_MARKER_RE.search(
        normalized.strip("[]() ")
    )
    if not bracketed_stage:
        normalized = re.sub(
            rf"[\[(][^\])]*(?:{STAGE_WORDS})[^\])]*[\])]",
            " ",
            normalized,
            flags=re.IGNORECASE,
        )
        normalized = re.sub(r"\s+", " ", normalized).strip()
    lowered = normalized.lower()

    if not normalized:
        return {
            "normalized_text": "",
            "kind": "empty",
            "confidence": "rejected",
            "reason": "empty cue",
        }

    bracketed = bool(re.fullmatch(r"[\[(].*[\])]", normalized))
    marker_text = normalized.strip("[]() ")
    if bracketed and STAGE_MARKER_RE.search(marker_text):
        return {
            "normalized_text": normalized,
            "kind": "stage",
            "confidence": "rejected",
            "reason": "explicit stage/instrumental marker",
        }
    if STAGE_MARKER_RE.search(lowered) and not re.search(
        r"\b(i|you|we|me|my|your|love|want|need|got|get)\b", lowered
    ):
        return {
            "normalized_text": normalized,
            "kind": "stage",
            "confidence": "rejected",
            "reason": "instrumental/stage wording",
        }

    words = re.findall(r"[A-Za-z][A-Za-z']*", normalized)
    lexical_words = [w for w in words if len(w.strip("'")) >= 2]
    if len(lexical_words) >= 4:
        return {
            "normalized_text": normalized,
            "kind": "lyric",
            "confidence": "high",
            "reason": "four-or-more lexical words",
        }
    if len(lexical_words) >= 3 and any(
        w.lower() in {"i", "you", "we", "me", "my", "your"} for w in words
    ):
        return {
            "normalized_text": normalized,
            "kind": "lyric",
            "confidence": "medium",
            "reason": "short lyric-like phrase with pronoun context",
        }
    return {
        "normalized_text": normalized,
        "kind": "caption",
        "confidence": "low",
        "reason": "too short or fragmentary for lyric timing evidence",
    }


def dedup_captions_with_timestamps(segments: list[dict]) -> list[dict]:
    """Produce timestamped lines from rolling YouTube auto-caption segments."""
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
            lines.append(
                {"ts": current_ts, "start": current_start, "text": " ".join(current_words)}
            )
            current_words = []
            current_ts = ""
    if current_words:
        lines.append({"ts": current_ts, "start": current_start, "text": " ".join(current_words)})

    return lines


def dedup_rolling_captions(segments: list[dict]) -> str:
    """Build clean full_text from rolling YouTube auto-caption segments."""
    result_words: list[str] = []
    for seg in segments:
        new_words = seg["text"].split()
        if not new_words:
            continue
        if not result_words:
            result_words.extend(new_words)
            continue
        max_overlap = min(len(result_words), len(new_words))
        overlap_len = 0
        for k in range(max_overlap, 0, -1):
            if result_words[-k:] == new_words[:k]:
                overlap_len = k
                break
        result_words.extend(new_words[overlap_len:])
    return " ".join(result_words)


def parse_vtt(vtt_path: Path) -> list[dict]:
    """Parse a VTT file into deduplicated timestamped segments."""
    lines = vtt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    segments = []
    dedup_window = 5
    recent_texts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            parts = line.split("-->")
            start = parse_ts(parts[0])
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                clean = re.sub(r"<[^>]+>", "", lines[i].strip())
                if clean:
                    text_lines.append(clean)
                i += 1
            text = " ".join(text_lines).strip()
            if text and text not in recent_texts:
                recent_texts.append(text)
                if len(recent_texts) > dedup_window:
                    recent_texts.pop(0)
                segments.append(
                    {
                        "start": round(start, 2),
                        "ts": fmt_ts(start),
                        "text": text,
                    }
                )
        i += 1
    return segments


def parse_vtt_cues(vtt_path: Path) -> list[dict]:
    """Parse raw VTT cues with start/end times and lyric-confidence metadata.

    Unlike :func:`parse_vtt`, this preserves cue end times and non-lyric cues.
    It is an internal evidence layer for 0.4 lyric timing work, not a prompt
    formatting surface.
    """
    lines = vtt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    cues: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            parts = line.split("-->", maxsplit=1)
            start = parse_ts(parts[0])
            end_text = parts[1].strip().split()[0] if parts[1].strip() else ""
            end = parse_ts(end_text) if end_text else None
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip():
                clean = _strip_caption_markup(lines[i].strip())
                if clean:
                    text_lines.append(clean)
                i += 1
            text = " ".join(text_lines).strip()
            classification = classify_caption_text(text)
            cue = TimedCaptionCue(
                start=round(start, 2),
                end=round(end, 2) if end is not None else None,
                ts=fmt_ts(start),
                text=text,
                normalized_text=classification["normalized_text"],
                kind=classification["kind"],
                confidence=classification["confidence"],
                reason=classification["reason"],
            )
            cues.append(cue.to_dict())
        i += 1
    return cues


def timed_lyric_segments(cues: list[dict], *, include_medium: bool = True) -> list[dict]:
    """Return only timed cues accepted as lyric evidence."""
    accepted = {"high"}
    if include_medium:
        accepted.add("medium")
    return [
        {
            "start": cue.get("start"),
            "end": cue.get("end"),
            "ts": cue.get("ts"),
            "text": cue.get("normalized_text") or cue.get("text", ""),
            "source": "timed-caption",
            "confidence": cue.get("confidence"),
        }
        for cue in cues
        if cue.get("kind") == "lyric" and cue.get("confidence") in accepted
    ]


# Backward-compatible private aliases for older internal imports/tests.
_parse_ts = parse_ts
_fmt_ts = fmt_ts
_dedup_captions_with_timestamps = dedup_captions_with_timestamps
_dedup_rolling_captions = dedup_rolling_captions
_parse_vtt_cues = parse_vtt_cues
