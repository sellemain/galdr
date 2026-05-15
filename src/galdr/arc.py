#!/usr/bin/env python3
"""Internal arc helpers for early 0.4 experimentation.

This module stays intentionally small and private for now.
It normalizes mixed stream shapes into a few coarse listener-state axes,
then derives broad arc spans from local continuity rather than genre labels.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def derive_arc_spans(stream: list[dict], *, min_span_frames: int = 2) -> list[dict]:
    """Collapse normalized frames into coarse contiguous arc spans."""
    frames = normalize_stream(stream)
    if not frames:
        return []

    labels = [_classify_frame(frame) for frame in frames]
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
