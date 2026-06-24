#!/usr/bin/env python3
"""Private section/arc event composer for 0.4 experiments."""

from __future__ import annotations

from typing import Any

from .arc import derive_arc_scales, select_arc_scale
from .boundary import build_section_boundary_report, derive_boundary_candidates, rank_reset_candidates


def _unwrap_stream_payload(stream_payload: list[dict] | dict) -> tuple[list[dict], float | None]:
    if isinstance(stream_payload, dict):
        stream = stream_payload.get("stream")
        hop_sec = stream_payload.get("stream_hop_sec")
        return (stream if isinstance(stream, list) else []), hop_sec
    return stream_payload, None


def _arc_event(span: dict[str, Any], *, scale: str) -> dict[str, Any]:
    return {
        "kind": "arc_span",
        "source": "arc_span",
        "scale": scale,
        "start": span.get("start"),
        "end": span.get("end"),
        "label": span.get("label"),
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


def _boundary_event(candidate: dict[str, Any], *, source: str) -> dict[str, Any]:
    return {
        "kind": source,
        "source": source,
        "start": candidate.get("start"),
        "end": candidate.get("end"),
        "label": candidate.get("kind"),
        "confidence": candidate.get("confidence"),
        "values": {
            key: candidate[key]
            for key in (
                "duration",
                "reset_strength",
                "reentry_strength",
                "state_reset",
                "acoustic_reset",
                "pressure_turn",
                "weight_release",
                "rank_score",
            )
            if key in candidate
        },
    }


def _event_start(event: dict[str, Any]) -> float:
    try:
        return float(event.get("start", 0.0))
    except (TypeError, ValueError):
        return 0.0


def derive_section_arc_events(
    stream_payload: list[dict] | dict,
    declared_sections: list[dict] | None = None,
    *,
    include_reset_points: bool = True,
    max_events: int = 24,
) -> dict[str, Any]:
    """Compose section/arc evidence without collapsing sources into labels.

    This helper is intentionally private and conservative. It keeps listener-state
    arc spans, silence/interlude boundary candidates, non-silent reset points, and
    declared-section alignment as separate evidence lanes.
    """
    stream, hop_sec = _unwrap_stream_payload(stream_payload)
    if max_events < 1:
        max_events = 1

    scales = derive_arc_scales(stream)
    selected_scale, scale_reason = select_arc_scale(scales)
    arc_spans = [_arc_event(span, scale=selected_scale) for span in scales.get(selected_scale, [])]

    boundary_candidates = derive_boundary_candidates(stream_payload, hop_sec=hop_sec, include_reset_points=False)
    acoustic_boundaries = [
        _boundary_event(candidate, source="acoustic_boundary")
        for candidate in boundary_candidates
        if candidate.get("kind") not in {"opening_gap", "ending_gap"}
    ]

    reset_points: list[dict[str, Any]] = []
    if include_reset_points:
        candidates_with_resets = derive_boundary_candidates(
            stream_payload,
            hop_sec=hop_sec,
            include_reset_points=True,
        )
        reset_points = [
            _boundary_event(candidate, source="reset_point")
            for candidate in rank_reset_candidates(candidates_with_resets, top_n=max_events)
        ]

    declared_alignment = None
    if declared_sections:
        declared_alignment = build_section_boundary_report(boundary_candidates, declared_sections)

    timeline = sorted(
        [*arc_spans, *acoustic_boundaries, *reset_points],
        key=lambda event: (_event_start(event), str(event.get("kind", ""))),
    )[:max_events]

    return {
        "selected_arc_scale": selected_scale,
        "arc_scale_reason": scale_reason,
        "arc_spans": arc_spans,
        "acoustic_boundaries": acoustic_boundaries,
        "reset_points": reset_points,
        "declared_alignment": declared_alignment,
        "timeline": timeline,
    }
