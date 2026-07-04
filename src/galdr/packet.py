"""Generic evidence packet assembly for galdr tracks.

Packets are deliberately data containers, not prose products.  They gather
analysis artifacts, time-indexed observations, source metadata, and context into
one generic shape that downstream consumers can render however they need.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .arc import derive_arc_scales, select_arc_scale
from .assemble import load_analysis, load_context
from .provenance import utc_now_iso
from .section_arc import derive_section_arc_events

PACKET_SCHEMA_VERSION = "evidence_packet_v0"


_ANALYSIS_MODULES = ("report", "perception", "harmony", "melody", "overtone")


def _round(value: Any, digits: int = 3) -> float | None:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _artifact_entry(path: Path, *, kind: str, role: str, payload: Any | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": path.stem,
        "kind": kind,
        "role": role,
        "path": str(path),
        "exists": path.exists(),
    }
    if path.exists():
        entry["size_bytes"] = path.stat().st_size
    if isinstance(payload, dict):
        for key in ("schema_version", "galdr_version", "module", "created_at"):
            if payload.get(key) is not None:
                entry[key] = payload[key]
        if isinstance(payload.get("source"), dict):
            entry["source_ref"] = payload["source"]
    return entry


def _source(kind: str, *, label: str | None = None, url: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    source: dict[str, Any] = {"kind": kind}
    if label:
        source["label"] = label
    if url:
        source["url"] = url
    if payload:
        for key in (
            "found",
            "confidence",
            "use_in_prompt",
            "candidate_title",
            "candidate_artist",
            "match_score",
            "match_reasons",
            "source",
        ):
            if payload.get(key) is not None:
                source[key] = payload[key]
        if payload.get("title") and not label:
            source["label"] = payload["title"]
        if payload.get("url") and not url:
            source["url"] = payload["url"]
    return source


def _build_subject(slug: str, context: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    report = analysis.get("report") or {}
    title = context.get("title") or report.get("title")
    artist = context.get("artist") or report.get("artist")
    subject: dict[str, Any] = {
        "kind": "track",
        "id": slug,
        "slug": slug,
    }
    if title:
        subject["title"] = title
    if artist:
        subject["artist"] = artist
    source_refs = []
    url = context.get("youtube_url") or context.get("source_url")
    if url:
        source_refs.append({"kind": "youtube", "url": url})
    audio_file = context.get("audio_file") or (context.get("download") or {}).get("audio_file")
    if audio_file:
        source_refs.append({"kind": "local_audio", "path": audio_file})
    if source_refs:
        subject["source_refs"] = source_refs
    return subject


def _build_artifacts(slug: str, analysis_dir: Path, analysis: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    track_dir = analysis_dir / slug
    artifacts: list[dict[str, Any]] = []
    for module in _ANALYSIS_MODULES:
        path = track_dir / f"{slug}_{module}.json"
        if path.exists() or analysis.get(module):
            artifacts.append(_artifact_entry(path, kind="analysis_json", role=module, payload=analysis.get(module)))

    stream_path = track_dir / f"{slug}_stream.json"
    stream_payload = _load_json(stream_path)
    if stream_path.exists():
        artifacts.append(_artifact_entry(stream_path, kind="analysis_json", role="listener_state_stream", payload=stream_payload))

    context_path = track_dir / "context.json"
    if context_path.exists() or context:
        artifacts.append(_artifact_entry(context_path, kind="context_json", role="context", payload=context))

    lyrics = context.get("lyrics") if isinstance(context.get("lyrics"), dict) else {}
    captions_file = lyrics.get("captions_file") or (context.get("download") or {}).get("captions_file")
    if captions_file:
        artifacts.append(_artifact_entry(Path(captions_file), kind="text", role="captions"))
    audio_file = context.get("audio_file") or (context.get("download") or {}).get("audio_file")
    if audio_file:
        artifacts.append(_artifact_entry(Path(audio_file), kind="audio", role="source_audio"))
    return artifacts


def _build_observations(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    report = analysis.get("report") or {}
    perception = analysis.get("perception") or {}
    harmony = analysis.get("harmony") or {}
    melody = analysis.get("melody") or {}
    overtone = analysis.get("overtone") or {}

    metric_map = [
        ("duration_seconds", report.get("duration_seconds") or perception.get("duration"), "seconds", "report"),
        ("felt_pulse_bpm", report.get("felt_pulse_bpm") or report.get("tempo_bpm") or perception.get("tempo"), "bpm", "report"),
        ("body", report.get("body"), "unit", "report"),
        ("weight", report.get("weight"), "unit", "report"),
        ("metric_tension", report.get("metric_tension"), "unit", "report"),
        ("mean_harmonic_pull", harmony.get("mean_harmonic_pull"), "unit", "harmony"),
        ("mean_tonal_anchor", harmony.get("mean_tonal_anchor"), "unit", "harmony"),
        ("mean_chroma_motion", harmony.get("mean_chroma_motion"), "unit", "harmony"),
        ("mean_foreground_line", melody.get("mean_foreground_line"), "unit", "melody"),
        ("mean_overtone_fit", overtone.get("mean_overtone_fit"), "unit", "overtone"),
    ]
    for name, value, unit, source in metric_map:
        rounded = _round(value)
        if rounded is not None:
            observations.append({
                "kind": "metric",
                "name": name,
                "value": rounded,
                "unit": unit,
                "source_ref": source,
            })

    summary = perception.get("summary") or {}
    for name in (
        "mean_attention",
        "mean_pattern",
        "pressure_building_pct",
        "pressure_releasing_pct",
        "pressure_sustaining_pct",
        "total_silence_sec",
        "pattern_break_count",
    ):
        rounded = _round(summary.get(name))
        if rounded is not None:
            observations.append({
                "kind": "metric",
                "name": name,
                "value": rounded,
                "source_ref": "perception.summary",
            })

    stream = perception.get("stream") or []
    if stream:
        scales = derive_arc_scales(stream)
        selected_scale, reason = select_arc_scale(scales)
        observations.append({
            "kind": "arc_scale_selection",
            "name": "selected_arc_scale",
            "value": selected_scale,
            "reason": reason,
            "scale_counts": {name: len(spans) for name, spans in scales.items()},
            "source_ref": "perception.stream",
        })
    return observations


def _span_timeline_item(span: dict[str, Any], *, scale: str) -> dict[str, Any]:
    return {
        "kind": "arc_span",
        "source_ref": "perception.stream",
        "scale": scale,
        "start": span.get("start"),
        "end": span.get("end"),
        "label": span.get("label"),
        "confidence": "derived",
        "values": {
            key: span[key]
            for key in (
                "frame_count",
                "mean_attention",
                "mean_pattern",
                "mean_pressure",
                "mean_body",
                "mean_weight",
                "silence_ratio",
            )
            if key in span
        },
    }


def _section_arc_timeline_item(event: dict[str, Any]) -> dict[str, Any]:
    source = event.get("source")
    kind = {
        "acoustic_boundary": "boundary_candidate",
        "reset_point": "reset_point",
    }.get(source, "arc_span")
    values = event.get("values")
    return {
        "kind": kind,
        "source_ref": "perception.stream",
        "scale": event.get("scale"),
        "start": event.get("start"),
        "end": event.get("end"),
        "label": event.get("label"),
        "confidence": event.get("confidence", "derived"),
        "values": values if isinstance(values, dict) else {},
    }


def _build_timeline(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    perception = analysis.get("perception") or {}
    stream = perception.get("stream") or []
    timeline: list[dict[str, Any]] = []

    if stream:
        section_arc = derive_section_arc_events(stream)
        for event in (
            *(section_arc.get("arc_spans") or []),
            *(section_arc.get("acoustic_boundaries") or []),
            *(section_arc.get("reset_points") or []),
        ):
            timeline.append(_section_arc_timeline_item(event))

        for frame in stream:
            event = frame.get("event")
            if event and event != "pattern_breaks":
                timeline.append({
                    "kind": "stream_event",
                    "source_ref": "perception.stream",
                    "start": frame.get("t", frame.get("time")),
                    "end": frame.get("t", frame.get("time")),
                    "label": event,
                    "values": {k: frame[k] for k in ("attention", "pattern", "pressure", "body", "weight") if k in frame},
                })

    for item in perception.get("pattern_breaks") or []:
        start = item.get("time", item.get("start"))
        timeline.append({
            "kind": item.get("type", "pattern_break"),
            "source_ref": "perception.pattern_breaks",
            "start": start,
            "end": item.get("end", start),
            "label": item.get("description") or item.get("type", "pattern_break"),
            "values": {k: item[k] for k in ("duration", "depth_db", "intensity", "reentry_shape", "boundary_position") if k in item},
        })

    def sort_key(item: dict[str, Any]) -> tuple[float, str]:
        start = _round(item.get("start"), 6)
        return (start if start is not None else 0.0, str(item.get("kind", "")))

    return sorted(timeline, key=sort_key)


def _build_sources(context: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if context.get("youtube_url") or context.get("source_url"):
        sources.append(_source("youtube", url=context.get("youtube_url") or context.get("source_url")))
    download = context.get("download") if isinstance(context.get("download"), dict) else {}
    if download:
        sources.append({"kind": "download", **{k: v for k, v in download.items() if _is_present(v)}})
    lyrics = context.get("lyrics") if isinstance(context.get("lyrics"), dict) else {}
    if lyrics:
        sources.append(_source("lyrics", url=lyrics.get("genius_url"), payload=lyrics))
    for key, kind in (("artist_context", "artist_context"), ("song_context", "track_context")):
        value = context.get(key)
        if isinstance(value, dict):
            sources.append(_source(kind, payload=value))
    return sources


def _build_claims(context: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for key, subject in (("artist_context", "artist"), ("song_context", "track")):
        value = context.get(key)
        if not isinstance(value, dict) or not value.get("extract"):
            continue
        claims.append({
            "kind": "context_extract",
            "subject": subject,
            "text": value.get("extract"),
            "source_ref": key,
            "confidence": value.get("confidence", "unknown"),
            "use_in_prompt": value.get("use_in_prompt"),
        })
    lyrics = context.get("lyrics") if isinstance(context.get("lyrics"), dict) else {}
    if lyrics:
        claims.append({
            "kind": "lyrics_availability",
            "subject": "lyrics",
            "text": "Lyrics or captions are available." if _lyrics_text(lyrics) else "Lyrics are missing or empty.",
            "source_ref": "lyrics",
            "confidence": lyrics.get("confidence", "unknown"),
            "use_in_prompt": bool(_lyrics_text(lyrics)),
        })
    return claims


def _lyrics_text(lyrics: dict[str, Any]) -> str:
    text = (lyrics.get("full_text") or lyrics.get("genius_text") or "").strip()
    if text:
        return text
    timed_lines = lyrics.get("timed_lines") or []
    return "\n".join(
        str(line.get("text") or "").strip()
        for line in timed_lines
        if isinstance(line, dict) and str(line.get("text") or "").strip()
    ).strip()


def _lyrics_timing_surface(lyrics: dict[str, Any]) -> dict[str, Any]:
    timed_lines = lyrics.get("timed_lines") or []
    caption_lines = lyrics.get("caption_lines") or []
    source = lyrics.get("source")
    timing: dict[str, Any] = {
        "kind": "none",
        "confidence": "missing",
        "line_count": 0,
    }
    if timed_lines:
        timing = {
            "kind": "provider_timed_lyrics",
            "surface": "timed_lines",
            "confidence": "provider",
            "line_count": len(timed_lines),
        }
        timed_source = lyrics.get("timed_lyrics_source")
        if isinstance(timed_source, dict):
            if timed_source.get("provider_source"):
                timing["provider_source"] = timed_source["provider_source"]
            if timed_source.get("lyrics_browse_id"):
                timing["provider_ref"] = timed_source["lyrics_browse_id"]
        return timing
    if caption_lines:
        kind = "caption_timing"
        confidence = "coarse"
        if source == "youtube-auto-captions":
            kind = "youtube_autocaption_timing"
            confidence = "coarse_asr"
        elif source == "local-vtt-captions":
            kind = "local_caption_timing"
        return {
            "kind": kind,
            "surface": "caption_lines",
            "confidence": confidence,
            "line_count": len(caption_lines),
        }
    return timing


def _build_collections(context: dict[str, Any]) -> dict[str, Any]:
    collections: dict[str, Any] = {}
    lyrics = context.get("lyrics") if isinstance(context.get("lyrics"), dict) else {}
    if lyrics:
        text = _lyrics_text(lyrics)
        status = "missing"
        if text:
            confidence = str(lyrics.get("confidence", "")).lower()
            status = "verified" if confidence == "high" or lyrics.get("source") == "youtube-auto-captions" else "weak"
        collections["lyrics"] = {
            "status": status,
            "source_ref": "lyrics",
            "timing": _lyrics_timing_surface(lyrics),
            "items": [
                {
                    "kind": "text",
                    "text": text,
                    "line_count": len([line for line in text.splitlines() if line.strip()]),
                }
            ] if text else [],
        }
        if lyrics.get("timed_lines"):
            collections["lyrics"]["timed_lines"] = lyrics["timed_lines"]
        if lyrics.get("caption_lines"):
            collections["lyrics"]["caption_lines"] = lyrics["caption_lines"]

    background_items = []
    for key, label in (("artist_context", "artist"), ("song_context", "track")):
        value = context.get(key)
        if isinstance(value, dict) and value.get("extract"):
            background_items.append({
                "kind": label,
                "source_ref": key,
                "text": value.get("extract"),
                "confidence": value.get("confidence", "unknown"),
                "use_in_prompt": value.get("use_in_prompt"),
            })
    if background_items:
        collections["background"] = {"items": background_items}
    return collections


def _build_warnings(analysis: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    perception = analysis.get("perception") or {}
    if not perception.get("stream"):
        warnings.append({"kind": "missing_data", "message": "No perception stream available; timeline will be incomplete."})
    lyrics = context.get("lyrics") if isinstance(context.get("lyrics"), dict) else None
    if not lyrics or not _lyrics_text(lyrics):
        warnings.append({"kind": "missing_data", "message": "No lyric or caption text available."})
    elif lyrics.get("confidence") and lyrics.get("confidence") != "high":
        warnings.append({
            "kind": "low_confidence_source",
            "message": "Lyrics are available but not high confidence.",
            "source_ref": "lyrics",
            "confidence": lyrics.get("confidence"),
        })
    for key in ("artist_context", "song_context"):
        value = context.get(key)
        if isinstance(value, dict) and value.get("found") and value.get("use_in_prompt") is False:
            warnings.append({
                "kind": "low_confidence_source",
                "message": f"{key} was fetched but marked unsafe for prompt use.",
                "source_ref": key,
                "confidence": value.get("confidence"),
            })
    return warnings


def build_packet(slug: str, analysis: dict[str, Any], context: dict[str, Any], *, analysis_dir: Path) -> dict[str, Any]:
    """Build a generic evidence packet from loaded galdr analysis/context."""
    return {
        "metadata": {
            "schema_version": PACKET_SCHEMA_VERSION,
            "created_at": utc_now_iso(),
            "generator": "galdr.packet",
        },
        "subject": _build_subject(slug, context, analysis),
        "artifacts": _build_artifacts(slug, analysis_dir, analysis, context),
        "observations": _build_observations(analysis),
        "timeline": _build_timeline(analysis),
        "sources": _build_sources(context),
        "claims": _build_claims(context),
        "collections": _build_collections(context),
        "views": {},
        "warnings": _build_warnings(analysis, context),
    }


def build_packet_from_disk(slug: str, analysis_dir: str | Path = "analysis") -> dict[str, Any]:
    """Load a track from disk and return its generic evidence packet."""
    analysis_root = Path(analysis_dir)
    analysis = load_analysis(slug, analysis_root)
    context = load_context(slug, analysis_root)
    return build_packet(slug, analysis, context, analysis_dir=analysis_root)
