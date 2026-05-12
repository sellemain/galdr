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


def _simple_ratio_distance(a: float, b: float) -> float:
    """Return closeness to common simple metric ratios, 0=exact/simple, 1=not simple."""
    if a <= 0 or b <= 0:
        return 1.0
    ratio = max(a, b) / min(a, b)
    simple_ratios = (1.0, 1.5, 2.0, 3.0)
    best = min(abs(ratio - r) / r for r in simple_ratios)
    return float(np.clip(best / 0.18, 0.0, 1.0))


def estimate_metric_tension(*, pulse: float, pulse_confidence: float | None, tempo_candidates: list[dict]) -> dict:
    """Estimate cross-rhythm / metric tension from competing tempo grids.

    This is intentionally conservative. It looks for the Meshuggah-shaped case:
    a strong primary pulse that remains stable while weaker periodicities imply
    another grid or accent cycle fighting the barline. Simple half/double tempo
    relationships are treated as low tension; non-simple or 3:2-like candidates
    raise tension when the main pulse is trusted.
    """
    pulse_score = float(np.clip(pulse, 0.0, 1.0))
    confidence = 0.5 if pulse_confidence is None else float(np.clip(pulse_confidence, 0.0, 1.0))
    if not tempo_candidates:
        return {
            "metric_tension": 0.0,
            "metric_tension_state": "absent",
            "metric_tension_note": "no alternate metric evidence detected",
        }

    primary = tempo_candidates[0]
    primary_bpm = float(primary.get("bpm") or 0.0)
    primary_support = max(1.0, float(primary.get("support") or 1.0))

    secondary_scores: list[tuple[float, float, float]] = []
    for candidate in tempo_candidates[1:]:
        bpm = float(candidate.get("bpm") or 0.0)
        if bpm <= 0 or primary_bpm <= 0:
            continue
        support = max(1.0, float(candidate.get("support") or 1.0))
        support_ratio = min(1.0, support / primary_support)
        sparse_alternate_bonus = 0.35 if support <= 2 and support_ratio < 0.35 else 0.0
        support_weight = max(support_ratio, sparse_alternate_bonus)
        ratio_distance = _simple_ratio_distance(primary_bpm, bpm)
        # 3:2 / 2:3 relationships are musically simple but cross-metric, so
        # keep them audible instead of collapsing them to "no tension".
        ratio = max(primary_bpm, bpm) / min(primary_bpm, bpm)
        hemiola_bonus = 0.35 if abs(ratio - 1.5) / 1.5 <= 0.04 else 0.0
        score = support_weight * max(ratio_distance, hemiola_bonus)
        secondary_scores.append((score, bpm, ratio))

    alternate_pressure = max((s for s, _, _ in secondary_scores), default=0.0)
    density_pressure = min(1.0, len(secondary_scores) / 4.0) * 0.25
    score = float(np.clip(pulse_score * confidence * (0.75 * alternate_pressure + density_pressure), 0.0, 1.0))

    if score >= 0.55:
        state = "high"
        note = "stable pulse with strong competing metric evidence"
    elif score >= 0.30:
        state = "present"
        note = "stable pulse with audible alternate metric pressure"
    elif score >= 0.12:
        state = "trace"
        note = "weak alternate metric evidence under the pulse"
    else:
        state = "absent"
        note = "no meaningful cross-rhythm pressure detected"

    return {
        "metric_tension": round(score, 3),
        "metric_tension_state": state,
        "metric_tension_note": note,
    }


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

    candidate_dicts = [
        {"bpm": c.bpm, "support": c.support, "source": c.source} for c in candidates
    ]
    return {
        "detected_pulse_bpm": round(detected, 1) if detected else 0.0,
        "felt_pulse_bpm": selected.bpm,
        "tempo_candidates": candidate_dicts,
        "pulse_confidence": round(confidence, 2),
        "pulse_ambiguous": ambiguous,
        "pulse_note": note,
        **estimate_metric_tension(
            pulse=1.0 if detected else 0.0,
            pulse_confidence=confidence,
            tempo_candidates=candidate_dicts,
        ),
    }
