"""Tempo validation helpers for galdr.

Librosa's single beat-tracking estimate can lock to an alternate pulse. These helpers keep
the detected pulse, then add a small candidate/felt-pulse layer backed by
windowed cross-checks.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Iterable

import librosa
import numpy as np

MIN_TEMPO_BPM = 50.0
MAX_TEMPO_BPM = 220.0
CLUSTER_TOLERANCE_BPM = 4.0
WINDOW_SECONDS = 30.0
WINDOW_HOP_SECONDS = 15.0
MIN_WINDOW_SECONDS = 12.0


@dataclass(frozen=True)
class TempoCandidate:
    bpm: float
    support: int
    source: str


def normalize_tempo_scalar(value) -> float:
    """Return a finite float from librosa tempo output, or 0.0."""
    if value is None:
        return 0.0
    try:
        arr = np.asarray(value).reshape(-1)
        if arr.size == 0:
            return 0.0
        value = float(arr[0])
    except (TypeError, ValueError):
        return 0.0
    return value if isfinite(value) and value > 0 else 0.0


def _bounded_tempo(value: float) -> float | None:
    tempo = normalize_tempo_scalar(value)
    while tempo and tempo < MIN_TEMPO_BPM:
        tempo *= 2.0
    while tempo > MAX_TEMPO_BPM:
        tempo /= 2.0
    if MIN_TEMPO_BPM <= tempo <= MAX_TEMPO_BPM:
        return tempo
    return None


def _cluster_tempos(values: Iterable[tuple[float, str]]) -> list[TempoCandidate]:
    clusters: list[dict] = []
    for raw_bpm, source in values:
        bpm = _bounded_tempo(raw_bpm)
        if bpm is None:
            continue
        for cluster in clusters:
            if abs(bpm - cluster["mean"]) <= CLUSTER_TOLERANCE_BPM:
                cluster["values"].append(bpm)
                cluster["sources"].append(source)
                cluster["mean"] = float(np.mean(cluster["values"]))
                break
        else:
            clusters.append({"mean": bpm, "values": [bpm], "sources": [source]})

    candidates = []
    for cluster in clusters:
        source_counts = defaultdict(int)
        for source in cluster["sources"]:
            source_counts[source] += 1
        source = "+".join(f"{name}:{count}" for name, count in sorted(source_counts.items()))
        candidates.append(
            TempoCandidate(
                bpm=round(float(np.median(cluster["values"])), 1),
                support=len(cluster["values"]),
                source=source,
            )
        )
    return sorted(candidates, key=lambda c: (-c.support, c.bpm))


def windowed_beat_tempos(
    y: np.ndarray,
    sr: int,
    *,
    window_seconds: float = WINDOW_SECONDS,
    hop_seconds: float = WINDOW_HOP_SECONDS,
    min_window_seconds: float = MIN_WINDOW_SECONDS,
) -> list[float]:
    """Estimate tempos on overlapping windows for alternate-pulse cross-checks."""
    duration = librosa.get_duration(y=y, sr=sr)
    if duration < min_window_seconds:
        return []

    window_samples = max(1, int(window_seconds * sr))
    hop_samples = max(1, int(hop_seconds * sr))
    min_samples = max(1, int(min_window_seconds * sr))

    tempos: list[float] = []
    starts = list(range(0, max(1, len(y) - min_samples + 1), hop_samples))
    if starts and starts[-1] + window_samples < len(y):
        starts.append(max(0, len(y) - window_samples))

    for start in starts:
        segment = y[start : min(len(y), start + window_samples)]
        if len(segment) < min_samples:
            continue
        tempo, beats = librosa.beat.beat_track(y=segment, sr=sr)
        tempo = normalize_tempo_scalar(tempo)
        if tempo and len(beats) >= 4:
            tempos.append(tempo)
    return tempos


def estimate_tempo_profile(
    detected_tempo_bpm: float,
    *,
    window_tempos: Iterable[float] | None = None,
) -> dict:
    """Build additive tempo validation fields from detected and windowed candidates.

    `detected_pulse_bpm` remains the raw beat-tracker estimate. `felt_pulse_bpm` may
    differ when repeated window evidence favors an alternate pulse, in which case the
    profile is marked ambiguous/suspect rather than presenting the raw pulse as plain truth.
    """
    detected = normalize_tempo_scalar(detected_tempo_bpm)
    values: list[tuple[float, str]] = []
    if detected:
        values.append((detected, "detected"))
        # Keep common metrical alternatives visible, but low-support unless windows agree.
        for multiple in (0.5, 1.5, 2.0):
            values.append((detected * multiple, "alternate"))
    for tempo in window_tempos or []:
        values.append((tempo, "window"))

    candidates = _cluster_tempos(values)
    if not candidates:
        return {
            "detected_pulse_bpm": round(detected, 1) if detected else 0.0,
            "felt_pulse_bpm": round(detected, 1) if detected else 0.0,
            "tempo_candidates": [],
            "pulse_confidence": 0.0,
            "pulse_ambiguous": True,
            "pulse_note": "tempo could not be validated",
        }

    detected_candidate = min(candidates, key=lambda c: abs(c.bpm - detected)) if detected else None
    window_candidates = [c for c in candidates if "window:" in c.source]
    strongest_window = window_candidates[0] if window_candidates else None

    selected = detected_candidate or candidates[0]
    ambiguous = False
    note = "tempo validated by detected pulse"

    if strongest_window and strongest_window.support >= 2:
        if not detected_candidate or strongest_window.support > detected_candidate.support:
            selected = strongest_window
        if detected and abs(strongest_window.bpm - detected) > CLUSTER_TOLERANCE_BPM:
            ambiguous = True
            note = (
                "detected pulse conflicts with repeated windowed beat tracking; "
                "felt pulse uses stronger alternate-pulse evidence"
            )
        else:
            note = "tempo supported by repeated windowed beat tracking"
    elif len(candidates) > 1:
        ambiguous = True
        note = "tempo has plausible alternate pulse candidates"

    total_support = max(1, sum(c.support for c in candidates))
    confidence = min(0.99, max(0.1, selected.support / total_support))
    if ambiguous:
        confidence = min(confidence, 0.74)

    return {
        "detected_pulse_bpm": round(detected, 1) if detected else 0.0,
        "felt_pulse_bpm": selected.bpm,
        "tempo_candidates": [
            {"bpm": c.bpm, "support": c.support, "source": c.source} for c in candidates
        ],
        "pulse_confidence": round(confidence, 2),
        "pulse_ambiguous": ambiguous,
        "pulse_note": note,
    }
