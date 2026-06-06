#!/usr/bin/env python3
"""Internal arc helpers for early 0.4 experimentation.

This module stays intentionally small and private for now.
It normalizes mixed stream shapes into a few coarse listener-state axes,
then derives broad arc spans from local continuity rather than genre labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class ArcFrame:
    t: float
    attention: float
    pattern: float
    pressure: float
    body: float
    weight: float
    silence: float


def _clamp(value: float | int | None) -> float:
    if value is None:
        return 0.0
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _legacy_body(frame: dict) -> float:
    momentum = _clamp(frame.get("momentum"))
    pattern = _clamp(frame.get("pattern_lock"))
    return _clamp(0.6 * momentum + 0.4 * pattern)


def _legacy_weight(frame: dict) -> float:
    harmonic = _clamp(frame.get("h_energy"))
    percussive = _clamp(frame.get("p_energy"))
    energy = _clamp(frame.get("energy"))
    return _clamp(0.5 * harmonic + 0.3 * energy + 0.2 * (1.0 - percussive))


def _infer_silence(frame: dict, attention: float | int | None, pattern: float | int | None) -> float:
    """Infer silence without treating old streams as silent by default."""
    silence = frame.get("silence")
    if isinstance(silence, bool):
        return 1.0 if silence else 0.0
    if silence is not None:
        return _clamp(silence)

    loudness_silence = frame.get("loudness_silence")
    if isinstance(loudness_silence, bool):
        return 1.0 if loudness_silence else 0.0

    loudness = frame.get("loudness_lufs")
    if loudness is not None:
        try:
            return 1.0 if float(loudness) <= -70.0 else 0.0
        except (TypeError, ValueError):
            return 0.0

    energy = _clamp(frame.get("rms_energy", frame.get("energy")))
    harmonic = _clamp(frame.get("h_energy"))
    percussive = _clamp(frame.get("p_energy"))
    if energy <= 0.00001 and harmonic <= 0.00001 and percussive <= 0.00001:
        if _clamp(attention) < 0.1 and _clamp(pattern) < 0.2:
            return 1.0
    return 0.0


def normalize_stream(stream: list[dict]) -> list[ArcFrame]:
    """Project mixed galdr stream rows into one coarse internal shape."""
    normalized: list[ArcFrame] = []
    for index, frame in enumerate(stream):
        t = frame.get("t", frame.get("time", index))
        attention = frame.get("attention")
        if attention is None:
            attention = frame.get("momentum", frame.get("pattern_lock", 0.0))

        pattern = frame.get("pattern")
        if pattern is None:
            pattern = frame.get("pattern_lock", 0.0)

        pressure = frame.get("pressure")
        if pressure is None:
            pressure = frame.get("breath", 0.0)
        try:
            pressure = float(pressure)
        except (TypeError, ValueError):
            pressure = 0.0
        if pressure < -1.0:
            pressure = -1.0
        if pressure > 1.0:
            pressure = 1.0

        body = frame.get("body")
        if body is None:
            body = _legacy_body(frame)

        weight = frame.get("weight")
        if weight is None:
            weight = _legacy_weight(frame)

        silence = _infer_silence(frame, attention, pattern)

        normalized.append(
            ArcFrame(
                t=float(t),
                attention=_clamp(attention),
                pattern=_clamp(pattern),
                pressure=pressure,
                body=_clamp(body),
                weight=_clamp(weight),
                silence=_clamp(silence),
            )
        )
    return normalized


def _classify_frame(frame: ArcFrame) -> str:
    if frame.silence >= 0.85:
        return "emptying"
    if frame.pressure <= -0.22:
        return "releasing"
    if frame.pressure >= 0.22:
        return "building"
    if frame.attention < 0.28 and frame.pattern < 0.35:
        return "ruptured"
    if frame.body >= 0.62 and frame.pattern >= 0.62 and abs(frame.pressure) < 0.18:
        return "held"
    if frame.weight >= 0.62 and frame.body < 0.45:
        return "suspended"
    return "returning"


def _pressure_pivot(left: ArcFrame, right: ArcFrame) -> str | None:
    """Name one-frame pressure turns before coarse state labels erase them."""
    if left.silence >= 0.85 or right.silence >= 0.85:
        return None
    if left.pressure >= 0.22 and right.pressure <= -0.22:
        return "pressure_peak_release"
    if left.pressure <= -0.22 and right.pressure >= 0.22:
        return "pressure_rebound"
    return None


def derive_arc_spans(stream: list[dict], *, min_span_frames: int = 2) -> list[dict]:
    """Collapse normalized frames into coarse contiguous arc spans."""
    frames = normalize_stream(stream)
    if not frames:
        return []

    labels = [_classify_frame(frame) for frame in frames]
    for i in range(1, len(frames)):
        pivot = _pressure_pivot(frames[i - 1], frames[i])
        if pivot is not None:
            labels[i] = pivot

    spans: list[dict] = []
    start = 0

    def emit(end_index: int) -> None:
        nonlocal start
        label = labels[start]
        span_frames = frames[start : end_index + 1]
        span = {
            "label": label,
            "start": span_frames[0].t,
            "end": span_frames[-1].t,
            "frame_count": len(span_frames),
            "mean_attention": round(sum(f.attention for f in span_frames) / len(span_frames), 3),
            "mean_pattern": round(sum(f.pattern for f in span_frames) / len(span_frames), 3),
            "mean_pressure": round(sum(f.pressure for f in span_frames) / len(span_frames), 3),
            "mean_body": round(sum(f.body for f in span_frames) / len(span_frames), 3),
            "mean_weight": round(sum(f.weight for f in span_frames) / len(span_frames), 3),
            "silence_ratio": round(sum(f.silence for f in span_frames) / len(span_frames), 3),
        }
        spans.append(span)
        start = end_index + 1

    for i in range(1, len(frames)):
        if labels[i] != labels[start] and (i - start) >= min_span_frames:
            emit(i - 1)

    emit(len(frames) - 1)
    return spans


def _span_delta(left: dict, right: dict) -> float:
    """Estimate how strong the listener-state boundary is between two spans."""
    keys = ["mean_attention", "mean_pattern", "mean_pressure", "mean_body", "mean_weight", "silence_ratio"]
    return max(abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0))) for key in keys)


def _merged_span(spans: list[dict], label: str) -> dict:
    frame_count = sum(span["frame_count"] for span in spans)
    if frame_count <= 0:
        frame_count = 1

    merged = {
        "label": label,
        "start": spans[0]["start"],
        "end": spans[-1]["end"],
        "frame_count": frame_count,
    }
    for key in ["mean_attention", "mean_pattern", "mean_pressure", "mean_body", "mean_weight", "silence_ratio"]:
        merged[key] = round(sum(span[key] * span["frame_count"] for span in spans) / frame_count, 3)
    return merged


def _dominant_label(spans: list[dict]) -> str:
    counts: dict[str, int] = {}
    for span in spans:
        counts[span["label"]] = counts.get(span["label"], 0) + span["frame_count"]
    return max(counts.items(), key=lambda item: item[1])[0]


def _preserve_arc_boundary(left: dict, right: dict) -> bool:
    """Keep perceptually hard boundaries visible while coalescing chatter."""
    return max(float(left.get("silence_ratio", 0.0)), float(right.get("silence_ratio", 0.0))) >= 0.85


def coalesce_arc_spans(spans: list[dict], *, min_frames: int, weak_delta: float) -> list[dict]:
    """Merge shallow or very short adjacent arc spans into a coarser pattern scale."""
    if not spans:
        return []

    groups: list[list[dict]] = [[spans[0]]]
    for span in spans[1:]:
        previous = groups[-1][-1]
        preserve_boundary = _preserve_arc_boundary(previous, span)
        short_boundary = previous["frame_count"] < min_frames or span["frame_count"] < min_frames
        shallow_boundary = _span_delta(previous, span) < weak_delta
        if not preserve_boundary and (short_boundary or shallow_boundary):
            groups[-1].append(span)
        else:
            groups.append([span])

    changed = True
    while changed and len(groups) > 1:
        changed = False
        next_groups: list[list[dict]] = []
        i = 0
        while i < len(groups):
            group = groups[i]
            frames = sum(span["frame_count"] for span in group)
            if frames < min_frames and next_groups and not _preserve_arc_boundary(next_groups[-1][-1], group[0]):
                next_groups[-1].extend(group)
                changed = True
            elif frames < min_frames and i + 1 < len(groups) and not _preserve_arc_boundary(group[-1], groups[i + 1][0]):
                groups[i + 1] = group + groups[i + 1]
                changed = True
            else:
                next_groups.append(group)
            i += 1
        groups = next_groups

    return [_merged_span(group, _dominant_label(group)) for group in groups]


def derive_arc_scales(stream: list[dict]) -> dict[str, list[dict]]:
    """Return detail, standard, and macro arc-pattern scales over the same stream."""
    detail = derive_arc_spans(stream)
    standard = coalesce_arc_spans(detail, min_frames=6, weak_delta=0.12)
    macro = coalesce_arc_spans(standard, min_frames=18, weak_delta=0.20)
    return {"detail": detail, "standard": standard, "macro": macro}


def select_arc_scale(scales: dict[str, list[dict]]) -> tuple[str, str]:
    """Choose the prompt-facing arc scale without discarding the other views."""
    detail = scales.get("detail", [])
    if not detail:
        return "detail", "no arc spans were detected"

    total = sum(span["frame_count"] for span in detail)
    if total <= 0:
        return "detail", "no usable arc frames were detected"

    span_count = len(detail)
    transition_density = max(0, span_count - 1) / total
    median_span = median(span["frame_count"] for span in detail)
    longest_ratio = max(span["frame_count"] for span in detail) / total
    label_counts: dict[str, int] = {}
    for span in detail:
        label_counts[span["label"]] = label_counts.get(span["label"], 0) + span["frame_count"]
    dominant_ratio = max(label_counts.values()) / total

    boundary_deltas = [_span_delta(left, right) for left, right in zip(detail, detail[1:])]
    median_delta = median(boundary_deltas) if boundary_deltas else 0.0

    if span_count >= 120 and transition_density >= 0.15 and median_span <= 3 and median_delta >= 0.18:
        return "standard", "extreme detail volume would flood the prompt; the standard view keeps real boundary contrast"
    if transition_density >= 0.35 and median_span <= 2 and longest_ratio <= 0.08:
        return "macro", "very dense two-frame alternation suggests classifier chatter, not structural form"
    if transition_density >= 0.10 and median_span <= 5 and median_delta < 0.18:
        return "macro", "frequent shallow label alternation suggests micro-chatter, not structural form"
    if span_count >= 80 and transition_density < 0.22 and median_span >= 4 and longest_ratio < 0.10:
        return "macro", "diffuse micro-variation is spread across the whole form; the macro view preserves the real arc"
    if span_count >= 40 and median_span <= 8 and median_delta < 0.20:
        return "macro", "many short shallow spans collapse better into whole-form movement"
    if dominant_ratio >= 0.80 or longest_ratio >= 0.35:
        return "macro", "one listener-state dominates the track; the macro view best preserves the form"
    if transition_density >= 0.08 and median_delta >= 0.18:
        return "detail", "frequent transitions have enough state contrast to matter as local pattern"
    return "standard", "moderate movement: enough structure for sections without promoting every micro-shift"
