"""Caption parsing and deduplication helpers for galdr."""

import re
from pathlib import Path


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
            lines.append({"ts": current_ts, "start": current_start, "text": " ".join(current_words)})
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
                segments.append({
                    "start": round(start, 2),
                    "ts": fmt_ts(start),
                    "text": text,
                })
        i += 1
    return segments


# Backward-compatible private aliases for older internal imports/tests.
_parse_ts = parse_ts
_fmt_ts = fmt_ts
_dedup_captions_with_timestamps = dedup_captions_with_timestamps
_dedup_rolling_captions = dedup_rolling_captions
