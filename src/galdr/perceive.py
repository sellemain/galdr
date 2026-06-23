#!/usr/bin/env python3
"""Perception layer — what the music DOES to the listener.

Concepts:
- Attention: a rolling measure of rhythmic consistency. High = the listener
  is locked in, tracking confidently.
- Surprise: where expectations break. A beat that should land and doesn't.
- Pressure: heard-pressure change. Building, sustaining, releasing, or silence.
- Silence: not just low energy. Actual nothing.
"""

import json
import warnings
from pathlib import Path

import librosa
import librosa.display
import pyloudnorm as pyln
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import uniform_filter1d

from .analyze import compute_body, compute_weight
from .audio_context import AudioContext, load_audio_context
from .provenance import SCHEMA_VERSION, artifact_metadata
from .surface import compute_surface_feature_bank, surface_snapshot
from .constants import (
    ATTENTION_WINDOW_SEC, ATTENTION_HOP_SEC, ATTENTION_MIN_BEATS,
    DISRUPTION_WEIGHT_BEAT, DISRUPTION_WEIGHT_SPECTRAL, DISRUPTION_WEIGHT_ENERGY,
    DISRUPTION_BEAT_LOOKBACK_SEC, DISRUPTION_BEAT_ABSENCE_THRESHOLD_SEC,
    DISRUPTION_BEAT_ABSENCE_MAX_SEC, DISRUPTION_SPECTRAL_SMOOTH_SEC,
    DISRUPTION_ENERGY_SMOOTH_SEC,
    PRESSURE_SMOOTH_SEC,
    SILENCE_THRESHOLD_DB, SILENCE_MIN_DURATION_SEC,
    HP_BALANCE_MIN_ENERGY, HP_SMOOTH_SEC,
    EVENT_ATTENTION_LOCKED, EVENT_ATTENTION_LOCK_RESET,
    EVENT_ATTENTION_FLOATING, EVENT_ATTENTION_FLOAT_RESET, EVENT_ATTENTION_MIN_GAP_SEC,
    EVENT_BODY_LOCK_DWELL_SEC, EVENT_BODY_UNLOCK_DWELL_SEC,
    EVENT_DISRUPTION_BREAK, EVENT_PRESSURE_BUILDING, EVENT_PRESSURE_RELEASING,
    EVENT_PRESSURE_BUILD_RESET, EVENT_PRESSURE_RELEASE_RESET, EVENT_PRESSURE_MIN_GAP_SEC,
    EVENT_WDS_SLOPE_WINDOW_SEC, EVENT_WDS_MIN_DELTA, EVENT_WDS_SILENCE_LUFS_CEILING,
    EVENT_WDS_PHRASE_WINDOW_SEC, EVENT_WDS_PHRASE_BODY_DELTA_MAX,
    EVENT_WDS_PHRASE_TEXTURE_DELTA_MAX, EVENT_WDS_PHRASE_LOUDNESS_DELTA_MAX,
    EVENT_SURFACE_WINDOW_SEC, EVENT_SURFACE_LOUDNESS_RISE_LUFS,
    EVENT_SURFACE_TEXTURE_RISE, EVENT_SURFACE_CURRENT_TEXTURE_MIN,
    EVENT_SURFACE_CURRENT_PERCUSSIVE_MIN, EVENT_SURFACE_PERCUSSIVE_RISE_RATIO,
    EVENT_SURFACE_BODY_HOLD_MIN,
    EVENT_SURFACE_PATTERN_HOLD_MIN,
    EVENT_SURFACE_COOLDOWN_SEC,
    EVENT_PHRASE_WINDOW_SEC, EVENT_PHRASE_MIN_GAP_SEC, EVENT_PHRASE_MACRO_SUPPRESS_SEC,
    EVENT_PHRASE_LIFT_LUFS, EVENT_PHRASE_DROP_LUFS, EVENT_PHRASE_ENERGY_SURGE,
    EVENT_PHRASE_SPECTRAL_FLASH, EVENT_PHRASE_TURN_DISRUPTION, EVENT_PHRASE_RETURN_LOCK,
    PATTERN_BREAK_MIN_DISRUPTION, ATTENTION_SHIFT_THRESHOLD, TOP_DISRUPTION_COUNT,
    ACTIVE_FRAME_SILENCE_PCT_THRESHOLD,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


def _duration_to_frames(duration_sec: float, frame_step_sec: float, max_len: int = None) -> int:
    """Convert a real-time duration to a positive filter width in frames."""
    if frame_step_sec <= 0:
        raise ValueError("frame_step_sec must be positive")
    frames = max(1, int(round(duration_sec / frame_step_sec)))
    if max_len is not None:
        frames = min(frames, max(1, int(max_len)))
    return frames


def _series_from_stream(stream: list[dict], field: str) -> list[float]:
    values = []
    for entry in stream:
        value = entry.get(field)
        if value is None:
            values.append(np.nan)
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            values.append(np.nan)
    return values


def _surface_series_from_stream(stream: list[dict], field: str) -> list[float]:
    values = []
    for entry in stream:
        evidence = entry.get("surface_evidence") or {}
        value = evidence.get(field)
        if value is None:
            values.append(np.nan)
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            values.append(np.nan)
    return values


def _time_extent(times: list[float], fallback_step: float = 1.0) -> tuple[float, float]:
    if not times:
        return 0.0, fallback_step
    if len(times) == 1:
        return times[0], times[0] + fallback_step
    step = max(fallback_step, float(np.median(np.diff(times))))
    return times[0], times[-1] + step


def _shade_silences(axes, silences: list[dict]) -> None:
    for ax in np.ravel(axes):
        for silence in silences:
            ax.axvspan(silence["start"], silence["end"], alpha=0.18, color="#7f8c8d")


def _plot_listener_state_metrics(stream: list[dict], silences: list[dict], out: Path, track_name: str) -> None:
    """Plot stream-derived listener-state metrics that are otherwise JSON-only."""
    if not stream:
        return

    times = [float(entry["t"]) for entry in stream]
    fig, axes = plt.subplots(4, 1, figsize=(16, 11), sharex=True)

    groups = (
        (
            "Body relation",
            (
                ("body_capture", "Body capture", "#e74c3c"),
                ("body_comfort", "Body comfort", "#2ecc71"),
                ("groove_comfort", "Groove comfort", "#3498db"),
            ),
        ),
        (
            "Grid and section hold",
            (
                ("accent_phase_drift", "Accent phase drift", "#9b59b6"),
                ("section_gravity", "Section gravity", "#f39c12"),
                ("surface_density", "Surface density", "#16a085"),
            ),
        ),
        (
            "Debt and release",
            (
                ("expectation_debt", "Expectation debt", "#c0392b"),
                ("release_force", "Release force", "#27ae60"),
            ),
        ),
        (
            "Weight and pressure",
            (
                ("weight", "Weight", "#34495e"),
                ("pressure", "Pressure", "#d35400"),
            ),
        ),
    )

    for ax, (title, fields) in zip(axes, groups):
        for field, label, color in fields:
            ax.plot(times, _series_from_stream(stream, field), label=label, color=color, linewidth=1.0)
        ax.axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
        ax.set_ylabel("Score")
        ax.set_ylim(-1.05 if title == "Weight and pressure" else -0.05, 1.05)
        ax.set_title(title, fontsize=12)
        ax.legend(loc="upper right", fontsize=9, ncol=3)

    _shade_silences(axes, silences)
    axes[-1].set_xlabel("Time (s)")
    plt.suptitle(f"{track_name} — Listener-state metrics", fontsize=14, y=0.995)
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_listener_state.png", dpi=150)
    plt.close()


def _plot_surface_evidence_metrics(stream: list[dict], silences: list[dict], out: Path, track_name: str) -> None:
    """Plot the newer surface evidence bank as a compact heatmap."""
    if not stream or not any(entry.get("surface_evidence") for entry in stream):
        return

    times = [float(entry["t"]) for entry in stream]
    fields = (
        ("roughness", "roughness"),
        ("noise_density", "noise density"),
        ("surface_motion", "surface motion"),
        ("brightness_tilt", "brightness tilt"),
        ("transient_attack", "transient attack"),
        ("punch", "punch"),
        ("sustain_drone", "sustain / drone"),
        ("band_pressure", "band pressure"),
        ("bass_weight", "bass weight"),
        ("body_weight", "body weight"),
        ("presence_weight", "presence weight"),
        ("air_weight", "air weight"),
        ("percussive_ratio", "percussive ratio"),
    )
    matrix = np.asarray([_surface_series_from_stream(stream, field) for field, _ in fields], dtype=float)
    start, end = _time_extent(times)

    fig, ax = plt.subplots(figsize=(16, 7))
    image = ax.imshow(
        matrix,
        aspect="auto",
        origin="lower",
        cmap="magma",
        vmin=0,
        vmax=1,
        extent=[start, end, -0.5, len(fields) - 0.5],
        interpolation="nearest",
    )
    for silence in silences:
        ax.axvspan(silence["start"], silence["end"], alpha=0.16, color="#7f8c8d")
    ax.set_yticks(range(len(fields)))
    ax.set_yticklabels([label for _, label in fields])
    ax.set_xlabel("Time (s)")
    ax.set_title(f"{track_name} — Surface evidence heatmap", fontsize=14)
    plt.colorbar(image, ax=ax, label="Score")
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_surface_evidence.png", dpi=150)
    plt.close()


def _plot_reading_map(
    y: np.ndarray,
    sr: int,
    stream: list[dict],
    hp_times,
    hp_balance,
    silences: list[dict],
    out: Path,
    track_name: str,
) -> None:
    """Plot a compact human reading map: spectrogram, surface balance, and metric strips."""
    if not stream:
        return

    times = [float(entry["t"]) for entry in stream]
    fig, axes = plt.subplots(
        5,
        1,
        figsize=(16, 12),
        sharex=True,
        gridspec_kw={"height_ratios": [3.0, 0.7, 0.9, 0.9, 0.9]},
    )

    s = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=96, fmax=min(10000, sr / 2))
    s_db = librosa.power_to_db(s, ref=np.max)
    librosa.display.specshow(s_db, sr=sr, x_axis="time", y_axis="mel", ax=axes[0], cmap="magma")
    axes[0].set_title(f"{track_name} — Reading map", fontsize=14)
    axes[0].set_xlabel("")

    axes[1].fill_between(hp_times, hp_balance, where=hp_balance < 0, alpha=0.55, color="#2ecc71", label="harmonic")
    axes[1].fill_between(hp_times, hp_balance, where=hp_balance > 0, alpha=0.55, color="#e67e22", label="percussive")
    axes[1].axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
    axes[1].set_ylabel("surface")
    axes[1].set_ylim(-1.05, 1.05)
    axes[1].legend(loc="upper right", fontsize=8, ncol=2)

    strip_groups = (
        (
            axes[2],
            (
                ("attention", "attention", "#27ae60"),
                ("pattern", "pattern", "#2980b9"),
                ("section_gravity", "section", "#f39c12"),
            ),
            "hold",
        ),
        (
            axes[3],
            (
                ("body_capture", "capture", "#e74c3c"),
                ("body_comfort", "comfort", "#2ecc71"),
                ("weight", "weight", "#34495e"),
            ),
            "body",
        ),
        (
            axes[4],
            (
                ("expectation_debt", "debt", "#c0392b"),
                ("release_force", "release", "#27ae60"),
                ("surface_density", "density", "#16a085"),
            ),
            "motion",
        ),
    )
    for ax, fields, ylabel in strip_groups:
        for field, label, color in fields:
            ax.plot(times, _series_from_stream(stream, field), label=label, color=color, linewidth=1.0)
        ax.set_ylabel(ylabel)
        ax.set_ylim(-0.05, 1.05)
        ax.legend(loc="upper right", fontsize=8, ncol=3)

    _shade_silences(axes, silences)
    axes[-1].set_xlabel("Time (s)")
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_reading_map.png", dpi=150)
    plt.close()


def compute_attention(beat_times, duration,
                     window_sec=ATTENTION_WINDOW_SEC,
                     hop_sec=ATTENTION_HOP_SEC):
    """Rolling rhythmic attention — how locked-in the beat is right now.

    Returns (times, attention) where attention is 0-1.
    1.0 = perfectly regular beats in the window (listener locked).
    0.0 = no beats in the window (listener holding/lost).
    """
    times = np.arange(0, duration, hop_sec)
    attention = np.zeros_like(times)

    for i, t in enumerate(times):
        # Find beats within the window centered on t
        window_beats = beat_times[
            (beat_times >= t - window_sec / 2) & (beat_times < t + window_sec / 2)
        ]
        if len(window_beats) < ATTENTION_MIN_BEATS:
            attention[i] = 0.0
            continue

        intervals = np.diff(window_beats)
        mean_interval = np.mean(intervals)
        if mean_interval == 0:
            attention[i] = 0.0
            continue

        # Regularity: low variance = high attention
        cv = np.std(intervals) / mean_interval  # coefficient of variation
        regularity = max(0, 1.0 - cv)

        # Density: how many beats vs expected at the track's average tempo
        expected_beats = window_sec / mean_interval
        density = min(1.0, len(window_beats) / max(1, expected_beats))

        attention[i] = regularity * density

    return times, attention


def compute_disruption(y, sr, beat_times, duration, hop_sec=ATTENTION_HOP_SEC):
    """Where the pattern breaks — how much expectations deviate from what arrives.

    Three components:
    1. Beat disruption: a beat was predicted but didn't arrive on time
    2. Spectral disruption: the frequency content shifted suddenly
    3. Energy disruption: the loudness jumped or dropped faster than the local trend

    Returns (times, disruption_total, disruption_beat, disruption_spectral, disruption_energy)
    Invert (1.0 - disruption) to get pattern.
    """
    times = np.arange(0, duration, hop_sec)

    # --- Beat disruption ---
    disruption_beat = np.zeros_like(times)
    if len(beat_times) > 2:
        for i, t in enumerate(times):
            recent = beat_times[(beat_times >= t - DISRUPTION_BEAT_LOOKBACK_SEC) & (beat_times < t)]
            if len(recent) < 2:
                prior = beat_times[beat_times < t]
                if len(prior) > 3:
                    time_since_last = t - prior[-1] if len(prior) > 0 else 0
                    if time_since_last > DISRUPTION_BEAT_ABSENCE_THRESHOLD_SEC:
                        disruption_beat[i] = min(1.0, time_since_last / DISRUPTION_BEAT_ABSENCE_MAX_SEC)
                continue

            recent_intervals = np.diff(recent)
            expected_interval = np.mean(recent_intervals)
            if expected_interval > 0:
                expected_next = recent[-1] + expected_interval
                future = beat_times[(beat_times >= t) & (beat_times < t + expected_interval * 2)]
                if len(future) > 0:
                    actual_next = future[0]
                    timing_error = abs(actual_next - expected_next) / expected_interval
                    disruption_beat[i] = min(1.0, timing_error)
                else:
                    disruption_beat[i] = 0.5

    # --- Spectral disruption (spectral flux) ---
    # onset_strength computes a mel-aggregated spectral flux envelope directly,
    # so we never materialise the full complex magnitude STFT. On long tracks
    # this is the difference between a 128-bin mel matrix and a ~1k-bin STFT,
    # roughly an order of magnitude less peak memory.
    spectral_flux = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
    flux_times = librosa.times_like(spectral_flux, sr=sr, hop_length=512)
    flux_step_sec = 512 / sr

    if spectral_flux.max() > 0:
        spectral_flux_norm = spectral_flux / spectral_flux.max()
    else:
        spectral_flux_norm = spectral_flux

    spectral_smooth_frames = _duration_to_frames(
        DISRUPTION_SPECTRAL_SMOOTH_SEC,
        flux_step_sec,
        max_len=len(spectral_flux_norm),
    )
    local_avg = uniform_filter1d(spectral_flux_norm, size=spectral_smooth_frames)
    spectral_disruption_raw = np.maximum(0, spectral_flux_norm - local_avg)
    disruption_spectral = np.interp(times, flux_times, spectral_disruption_raw)

    # --- Energy disruption ---
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    rms_step_sec = 512 / sr

    if len(rms) > 1:
        energy_diff = np.abs(np.diff(rms))
        energy_diff = np.append(energy_diff, 0)
        energy_smooth_frames = _duration_to_frames(
            DISRUPTION_ENERGY_SMOOTH_SEC,
            rms_step_sec,
            max_len=len(energy_diff),
        )
        local_trend = uniform_filter1d(energy_diff, size=energy_smooth_frames)
        energy_disruption_raw = np.maximum(0, energy_diff - local_trend)
        if energy_disruption_raw.max() > 0:
            energy_disruption_raw = energy_disruption_raw / energy_disruption_raw.max()
    else:
        energy_disruption_raw = np.zeros_like(rms)

    disruption_energy = np.interp(times, rms_times, energy_disruption_raw)

    # Total disruption: weighted combination
    disruption_total = (
        DISRUPTION_WEIGHT_BEAT * disruption_beat +
        DISRUPTION_WEIGHT_SPECTRAL * disruption_spectral +
        DISRUPTION_WEIGHT_ENERGY * disruption_energy
    )

    return times, disruption_total, disruption_beat, disruption_spectral, disruption_energy


def compute_loudness(y, sr, duration, hop_sec=ATTENTION_HOP_SEC):
    """EBU R128 loudness curve for heard pressure.

    Returns a dict with integrated LUFS plus a silence-aware short-term curve
    aligned to the perception stream. Non-finite/near-floor windows are carried
    as silence rather than coerced into bogus numeric motion.
    """
    meter = pyln.Meter(sr)
    y64 = np.asarray(y, dtype=np.float64)
    try:
        integrated = float(meter.integrated_loudness(y64))
    except ValueError:
        integrated = float("-inf")
    integrated_lufs = None if not np.isfinite(integrated) else round(integrated, 2)

    times = np.arange(0, duration, hop_sec)
    window_sec = 3.0
    floor_lufs = -70.0
    curve = np.full(len(times), np.nan, dtype=float)
    silence_mask = np.zeros(len(times), dtype=bool)

    for i, t in enumerate(times):
        start = int(max(0, (t - window_sec / 2) * sr))
        end = int(min(len(y64), (t + window_sec / 2) * sr))
        segment = y64[start:end]
        if len(segment) == 0 or float(np.sqrt(np.mean(segment ** 2))) < 1e-7:
            silence_mask[i] = True
            continue

        try:
            value = float(meter.integrated_loudness(segment))
        except ValueError:
            value = float("-inf")
        if not np.isfinite(value) or value <= floor_lufs:
            silence_mask[i] = True
        else:
            curve[i] = value

    active = curve[~silence_mask & np.isfinite(curve)]
    if len(active) == 0:
        filled = np.full(len(curve), floor_lufs, dtype=float)
    else:
        filled = curve.copy()
        valid_idx = np.flatnonzero(np.isfinite(filled))
        filled[~np.isfinite(filled)] = np.interp(
            np.flatnonzero(~np.isfinite(filled)), valid_idx, filled[valid_idx]
        )

    pressure_smooth_frames = _duration_to_frames(PRESSURE_SMOOTH_SEC, hop_sec, max_len=len(filled))
    smoothed = uniform_filter1d(filled, size=pressure_smooth_frames)
    if len(smoothed) > 1:
        delta = np.gradient(smoothed)
        delta[silence_mask] = 0.0
        # Ignore sub-audible numerical flutter in steady material. LUFS pressure
        # should describe real pressure, not floating point dust.
        delta[np.abs(delta) < 0.05] = 0.0
        max_abs = np.max(np.abs(delta))
        pressure = delta / max_abs if max_abs > 0 else np.zeros_like(delta)
    else:
        delta = np.zeros_like(smoothed)
        pressure = np.zeros_like(smoothed)

    return {
        "times": times,
        "integrated_lufs": integrated_lufs,
        "short_term_lufs": curve,
        "smoothed_lufs": smoothed,
        "loudness_delta": delta,
        "pressure": pressure,
        "silence_mask": silence_mask,
        "floor_lufs": floor_lufs,
    }


def compute_pressure(y, sr, duration, hop_sec=ATTENTION_HOP_SEC):
    """Heard-pressure — building, sustaining, or releasing.

    Returns (times, pressure) where:
    - Positive = building (perceived pressure increasing)
    - Zero = sustaining (stable or silence-aware)
    - Negative = releasing (perceived pressure decreasing)
    """
    loudness = compute_loudness(y, sr, duration, hop_sec=hop_sec)
    return loudness["times"], loudness["pressure"]


def detect_silences(y, sr, threshold_db=SILENCE_THRESHOLD_DB,
                    min_duration_sec=SILENCE_MIN_DURATION_SEC):
    """Find actual silences — not just quiet parts, but nothing.

    Returns list of dicts with start, end, duration, depth_db.
    """
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=256)
    rms_db = librosa.amplitude_to_db(rms, ref=np.max(rms))

    silences = []
    in_silence = False
    start = 0
    min_db = 0

    for i, db in enumerate(rms_db):
        if db < threshold_db:
            if not in_silence:
                in_silence = True
                start = rms_times[i]
                min_db = db
            else:
                min_db = min(min_db, db)
        else:
            if in_silence:
                end = rms_times[i]
                if end - start >= min_duration_sec:
                    silences.append({
                        "start": round(float(start), 2),
                        "end": round(float(end), 2),
                        "duration": round(float(end - start), 2),
                        "depth_db": round(float(min_db), 1),
                    })
                in_silence = False

    # Handle silence at end of track
    if in_silence:
        end = rms_times[-1]
        if end - start >= min_duration_sec:
            silences.append({
                "start": round(float(start), 2),
                "end": round(float(end), 2),
                "duration": round(float(end - start), 2),
                "depth_db": round(float(min_db), 1),
            })

    return silences


def _window_mean(values, times, start, end):
    """Mean over a time window; returns None for empty/non-finite windows."""
    mask = (times >= start) & (times <= end)
    if not np.any(mask):
        return None
    window = np.asarray(values)[mask]
    window = window[np.isfinite(window)]
    if window.size == 0:
        return None
    return float(np.mean(window))


def _silence_boundary_position(silence, duration, boundary_sec=2.0, closing_sec=3.0):
    """Classify whether silence belongs to track boundary context."""
    start = float(silence["start"])
    end = float(silence["end"])
    if start <= boundary_sec:
        return "opening"
    if end >= max(duration - closing_sec, 0):
        return "closing"
    return "internal"


def _classify_reentry(pre_attention, post_attention, pre_pressure, post_pressure, silence, duration):
    """Classify what the return after silence does to listener state."""
    boundary_position = _silence_boundary_position(silence, duration)
    if boundary_position == "opening":
        return "entry_preparation"
    if boundary_position == "closing" or post_attention is None:
        return "terminal_decay"

    pre_m = 0.0 if pre_attention is None else pre_attention
    post_m = 0.0 if post_attention is None else post_attention
    pre_p = 0.0 if pre_pressure is None else pre_pressure
    post_p = 0.0 if post_pressure is None else post_pressure

    attention_delta = post_m - pre_m
    pressure_delta = post_p - pre_p

    if post_m >= 0.75 and abs(attention_delta) <= 0.20 and pressure_delta >= -0.15:
        return "continuation"
    if attention_delta >= 0.25 or pressure_delta >= 0.25:
        return "rupture"
    if pre_m < 0.45 and post_m >= 0.60:
        return "reset"
    if post_m < 0.45 or pressure_delta <= -0.30:
        return "withdrawal"
    return "continuation"


def compute_silence_reentries(silences, times, attention, pressure, loudness_delta, duration,
                              short_window_sec=1.5, recovery_threshold=0.85,
                              max_recovery_sec=8.0):
    """Measure return behavior after detected silences.

    Silence itself is only half the gesture.  This records what happens
    immediately after the gap: how forcefully pressure returns, how long
    listener attention takes to recover, and whether the return behaves like
    continuation, rupture, reset, withdrawal, entry preparation, or terminal
    decay.
    """
    events = []
    if not silences:
        return events

    times = np.asarray(times)
    attention = np.asarray(attention)
    pressure = np.asarray(pressure)
    loudness_delta = np.asarray(loudness_delta)

    for silence in silences:
        start = float(silence["start"])
        end = float(silence["end"])
        pre_start = max(0.0, start - short_window_sec)
        post_end = min(duration, end + short_window_sec)

        pre_attention = _window_mean(attention, times, pre_start, start)
        post_attention = _window_mean(attention, times, end, post_end)
        pre_pressure = _window_mean(pressure, times, pre_start, start)
        post_pressure = _window_mean(pressure, times, end, post_end)
        post_loudness_delta = _window_mean(loudness_delta, times, end, post_end)

        baseline = pre_attention if pre_attention is not None else None
        recovery_time = None
        recovered = False
        if baseline is not None and end < duration:
            target = min(max(baseline * recovery_threshold, 0.35), 0.9)
            recovery_mask = (times >= end) & (times <= min(duration, end + max_recovery_sec))
            candidates = np.where(recovery_mask & (attention >= target))[0]
            if candidates.size:
                recovery_time = round(float(times[candidates[0]] - end), 2)
                recovered = True

        pre_p = 0.0 if pre_pressure is None else pre_pressure
        post_p = 0.0 if post_pressure is None else post_pressure
        post_m = 0.0 if post_attention is None else post_attention
        pre_m = 0.0 if pre_attention is None else pre_attention
        force = max(0.0, (post_m - pre_m) * 0.55 + max(0.0, post_p - pre_p) * 0.45)
        if post_loudness_delta is not None:
            force += max(0.0, post_loudness_delta) * 0.15

        boundary_position = _silence_boundary_position(silence, duration)
        shape = _classify_reentry(pre_attention, post_attention, pre_pressure, post_pressure, silence, duration)

        events.append({
            "silence_start": round(start, 2),
            "silence_end": round(end, 2),
            "boundary_position": boundary_position,
            "silence_duration": silence["duration"],
            "reentry_time": None if end >= duration else round(end, 2),
            "reentry_shape": shape,
            "reentry_force": round(float(min(force, 1.0)), 3),
            "recovery_time_sec": recovery_time,
            "recovered": recovered,
            "pre_attention": None if pre_attention is None else round(float(pre_attention), 3),
            "post_attention": None if post_attention is None else round(float(post_attention), 3),
            "pre_pressure": None if pre_pressure is None else round(float(pre_pressure), 3),
            "post_pressure": None if post_pressure is None else round(float(post_pressure), 3),
        })

    return events


def compute_harmonic_percussive_attention(y, sr, duration,
                                         hop_sec=ATTENTION_HOP_SEC):
    """Track which channel is carrying the energy over time.

    Returns (times, h_energy, p_energy, balance) where balance is
    -1 (pure harmonic) to +1 (pure percussive), 0 = balanced.
    """
    y_h, y_p = librosa.effects.hpss(y)

    rms_h = librosa.feature.rms(y=y_h)[0]
    rms_p = librosa.feature.rms(y=y_p)[0]
    # Full-resolution HPSS output is huge for long tracks (two buffers each the
    # size of y). Drop it immediately — only the RMS envelopes are used below.
    del y_h, y_p
    rms_times = librosa.frames_to_time(np.arange(len(rms_h)), sr=sr)
    hp_step_sec = 512 / sr

    hp_smooth_frames = _duration_to_frames(HP_SMOOTH_SEC, hp_step_sec, max_len=len(rms_h))
    rms_h_smooth = uniform_filter1d(rms_h, size=hp_smooth_frames)
    rms_p_smooth = uniform_filter1d(rms_p, size=hp_smooth_frames)

    total = rms_h_smooth + rms_p_smooth
    with np.errstate(divide='ignore', invalid='ignore'):
        balance_raw = np.where(
            total > HP_BALANCE_MIN_ENERGY,
            (rms_p_smooth - rms_h_smooth) / total,
            0.0
        )

    times = np.arange(0, duration, hop_sec)
    h_energy = np.interp(times, rms_times, rms_h_smooth)
    p_energy = np.interp(times, rms_times, rms_p_smooth)
    balance = np.interp(times, rms_times, balance_raw)

    return times, h_energy, p_energy, balance


def compute_perception(y: np.ndarray, sr: int, track_name: str, hop_sec: float = ATTENTION_HOP_SEC) -> dict:
    """Compute perception stream and report from audio array. No file I/O, no plots.

    Calls the existing pure DSP functions (compute_attention, compute_disruption,
    compute_pressure, detect_silences, compute_harmonic_percussive_attention),
    assembles the stream, builds the report, and embeds stream under report["stream"].

    Args:
        y: audio time series (mono, float32)
        sr: sample rate
        track_name: track identifier used in report fields
        hop_sec: seconds between listener-state stream samples

    Returns:
        report dict with "stream" key embedded
    """
    if hop_sec <= 0:
        raise ValueError("hop_sec must be positive")

    duration = librosa.get_duration(y=y, sr=sr)

    if duration <= 0:
        raise ValueError("Audio too short to analyze")

    # Beat tracking
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0]) if len(tempo) > 0 else 0.0

    onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # RMS energy (for context)
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    # Compute perception dimensions
    m_times, attention = compute_attention(beat_times, duration, hop_sec=hop_sec)

    s_times, disruption, d_beat, d_spectral, d_energy = compute_disruption(
        y, sr, beat_times, duration, hop_sec=hop_sec
    )

    loudness = compute_loudness(y, sr, duration, hop_sec=hop_sec)
    p_times = loudness["times"]
    pressure = loudness["pressure"]

    silences = detect_silences(y, sr)

    hp_times, h_energy, p_energy, hp_balance = compute_harmonic_percussive_attention(
        y, sr, duration, hop_sec=hop_sec
    )
    surface_bank = compute_surface_feature_bank(y, sr, hop_sec=hop_sec)

    silence_reentries = compute_silence_reentries(
        silences, m_times, attention, pressure, loudness["loudness_delta"], duration
    )
    reentries_by_start = {r["silence_start"]: r for r in silence_reentries}

    # RMS energy interpolated to our time grid. Keep this separate from the
    # public `weight` metric, which now means physical hold.
    rms_energy = np.interp(m_times, rms_times, rms)

    def _local_body_and_weight(t: float, idx: int) -> tuple[dict, dict]:
        """Compute local body-lock and weight for the current listening window."""
        half_window = ATTENTION_WINDOW_SEC / 2.0
        start = max(0.0, t - half_window)
        end = min(duration, t + half_window)
        window_duration = max(end - start, hop_sec)

        local_beats = beat_times[(beat_times >= start) & (beat_times < end)]
        if len(local_beats) > 2:
            intervals = np.diff(local_beats)
            mean_interval = float(np.mean(intervals))
            pulse = max(0.0, 1.0 - (float(np.std(intervals)) / mean_interval)) if mean_interval > 0 else 0.0
            expected_beats = window_duration / mean_interval if mean_interval > 0 else 0.0
            pulse_confidence = float(np.clip(len(local_beats) / max(expected_beats, 1.0), 0.0, 1.0))
        else:
            pulse = 0.0
            pulse_confidence = 0.0

        local_onsets = onset_times[(onset_times >= start) & (onset_times < end)]
        onsets_per_second = len(local_onsets) / window_duration

        frame_mask = (m_times >= start) & (m_times < end)
        if not frame_mask.any():
            frame_mask[idx] = True

        local_harmonic = float(np.mean(h_energy[frame_mask]))
        local_percussive = float(np.mean(p_energy[frame_mask]))
        total_texture = local_harmonic + local_percussive
        surface_balance = local_percussive / total_texture if total_texture > HP_BALANCE_MIN_ENERGY else 0.0

        rms_mask = (rms_times >= start) & (rms_times < end)
        local_rms = rms[rms_mask]
        positive_rms = local_rms[local_rms > 0]
        dynamic_range_ratio = float(np.max(positive_rms) / np.min(positive_rms)) if len(positive_rms) > 1 else 1.0

        body = compute_body(
            duration=window_duration,
            beat_count=len(local_beats),
            pulse=pulse,
            pulse_confidence=pulse_confidence,
            pulse_ambiguous=False,
            surface_balance=surface_balance,
            onsets_per_second=onsets_per_second,
        )
        weight = compute_weight(
            pulse=pulse,
            pulse_confidence=pulse_confidence,
            body=body["body"],
            surface_balance=surface_balance,
            onsets_per_second=onsets_per_second,
            harmonic_weight=local_harmonic,
            percussive_weight=local_percussive,
            dynamic_range_ratio=dynamic_range_ratio,
        )
        return body, weight

    def _local_surface_density(t: float, idx: int) -> float:
        """Estimate local event/detail load independent of simple loudness."""
        half_window = ATTENTION_WINDOW_SEC / 2.0
        start = max(0.0, t - half_window)
        end = min(duration, t + half_window)
        window_duration = max(end - start, hop_sec)

        local_onsets = onset_times[(onset_times >= start) & (onset_times < end)]
        onset_density = float(np.clip((len(local_onsets) / window_duration) / 4.0, 0.0, 1.0))
        spectral_motion = float(np.clip(d_spectral[idx], 0.0, 1.0))
        energy_motion = float(np.clip(d_energy[idx], 0.0, 1.0))
        texture_detail = float(np.clip(abs(hp_balance[idx]), 0.0, 1.0))
        return round(float(np.clip(
            onset_density * 0.45 + spectral_motion * 0.30 + energy_motion * 0.15 + texture_detail * 0.10,
            0.0,
            1.0,
        )), 3)

    def _local_accent_phase_drift(t: float) -> float:
        """Estimate how much local attacks wander around the beat grid."""
        half_window = ATTENTION_WINDOW_SEC / 2.0
        start = max(0.0, t - half_window)
        end = min(duration, t + half_window)
        local_onsets = onset_times[(onset_times >= start) & (onset_times < end)]
        if len(local_onsets) < 4 or len(beat_times) < 3:
            return 0.0

        phases = []
        for onset in local_onsets:
            beat_idx = int(np.searchsorted(beat_times, onset) - 1)
            if beat_idx < 0 or beat_idx + 1 >= len(beat_times):
                continue
            interval = float(beat_times[beat_idx + 1] - beat_times[beat_idx])
            if interval <= 0:
                continue
            phases.append(((float(onset) - float(beat_times[beat_idx])) / interval) % 1.0)

        if len(phases) < 4:
            return 0.0
        angles = np.asarray(phases) * 2.0 * np.pi
        concentration = float(abs(np.mean(np.exp(1j * angles))))
        density_gate = min(1.0, len(phases) / 10.0)
        return round(float(np.clip((1.0 - concentration) * density_gate, 0.0, 1.0)), 3)

    def _groove_comfort(body: float, pattern: float, pressure_now: float, accent_drift: float) -> float:
        """How easily the body can settle into the local pulse.

        Accent phase spread is not automatically discomfort: funk pockets,
        swung dance grids, and sparse programmed beats often feel good because
        the body has a strong stable pulse under the off-grid attacks. Penalize
        drift less when pulse/body/pattern are already high, and let stable
        entrainment recover some comfort.
        """
        stable_pocket = body * pattern
        drift_penalty = 0.45 * accent_drift * (1.0 - 0.35 * stable_pocket)
        pressure_penalty = 0.16 * abs(pressure_now)
        comfort = stable_pocket * (1.0 - drift_penalty) * (1.0 - pressure_penalty)
        comfort += max(0.0, stable_pocket - 0.62) * 0.12
        return round(float(np.clip(comfort, 0.0, 1.0)), 3)

    def _section_gravity(attention_now: float, pattern_now: float, body_now: float, accent_drift: float) -> float:
        """How much this moment feels like an anchor rather than passage material."""
        gravity = (
            pattern_now * 0.38
            + attention_now * 0.27
            + body_now * 0.20
            + (1.0 - accent_drift) * 0.15
        )
        return round(float(np.clip(gravity, 0.0, 1.0)), 3)

    def _mark_event(entry: dict, event: str, note: str) -> None:
        """Attach a controlled listening-event label plus a short readable gloss."""
        entry["event"] = event
        entry["event_note"] = note

    def _stable_phrase_motion(entry: dict) -> bool:
        """Return true when WDS movement is phrase-internal, not a new event."""
        t = float(entry["t"])
        phrase = [
            e for e in stream
            if t - EVENT_WDS_PHRASE_WINDOW_SEC <= float(e["t"]) < t
        ]
        if len(phrase) < 3:
            return False

        body_vals = [float(e["body"]) for e in phrase]
        surface_balance_vals = [float(e["surface_balance"]) for e in phrase]
        loudness_vals = [float(e["loudness_lufs"]) for e in phrase if e.get("loudness_lufs") is not None]
        if not loudness_vals:
            return False

        body_range = max(body_vals) - min(body_vals)
        surface_balance_range = max(surface_balance_vals) - min(surface_balance_vals)
        loudness_range = max(loudness_vals) - min(loudness_vals)

        return (
            body_range <= EVENT_WDS_PHRASE_BODY_DELTA_MAX
            and surface_balance_range <= EVENT_WDS_PHRASE_TEXTURE_DELTA_MAX
            and loudness_range <= EVENT_WDS_PHRASE_LOUDNESS_DELTA_MAX
        )

    def _wds_slope_event(entry: dict, idx: int, direction: str) -> bool:
        """Gate WDS prose events by felt movement, not label-boundary chatter."""
        current = float(entry["weight"])
        t = float(entry["t"])
        lookback = np.where(m_times <= t - EVENT_WDS_SLOPE_WINDOW_SEC)[0]
        if len(lookback) == 0:
            return False

        prior = stream[int(lookback[-1])]
        previous = float(prior["weight"])
        delta = current - previous
        entry["weight_delta"] = round(delta, 3)

        loudness_lufs = entry.get("loudness_lufs")
        if entry.get("silence") or (loudness_lufs is not None and loudness_lufs <= EVENT_WDS_SILENCE_LUFS_CEILING):
            return False
        if _stable_phrase_motion(entry):
            entry["weight_motion"] = "phrase_internal"
            return False

        if direction == "arrives":
            return delta >= EVENT_WDS_MIN_DELTA
        if direction == "lifts":
            return delta <= -EVENT_WDS_MIN_DELTA
        return False

    def _surface_hardens(entry: dict) -> bool:
        """Detect a surface-impact switch while the rhythmic body still holds."""
        t = float(entry["t"])
        lookback = [
            e for e in stream
            if t - EVENT_SURFACE_WINDOW_SEC <= float(e["t"]) < t
            and e.get("loudness_lufs") is not None
        ]
        if len(lookback) < 3 or entry.get("loudness_lufs") is None:
            return False

        baseline = lookback[: max(3, len(lookback) // 2)]
        base_loudness = float(np.mean([float(e["loudness_lufs"]) for e in baseline]))
        base_surface_balance = float(np.mean([float(e["surface_balance"]) for e in baseline]))
        base_percussive = float(np.mean([float(e["percussive_weight"]) for e in baseline]))

        loudness_rise = float(entry["loudness_lufs"]) - base_loudness
        surface_balance_rise = float(entry["surface_balance"]) - base_surface_balance
        percussive_ratio = float(entry["percussive_weight"]) / max(base_percussive, 1e-6)

        body_holds = float(entry["body"]) >= EVENT_SURFACE_BODY_HOLD_MIN
        pattern_holds = float(entry["pattern"]) >= EVENT_SURFACE_PATTERN_HOLD_MIN
        hardens = (
            loudness_rise >= EVENT_SURFACE_LOUDNESS_RISE_LUFS
            and surface_balance_rise >= EVENT_SURFACE_TEXTURE_RISE
            and float(entry["surface_balance"]) >= EVENT_SURFACE_CURRENT_TEXTURE_MIN
            and float(entry["percussive_weight"]) >= EVENT_SURFACE_CURRENT_PERCUSSIVE_MIN
            and percussive_ratio >= EVENT_SURFACE_PERCUSSIVE_RISE_RATIO
            and body_holds
            and pattern_holds
        )

        if hardens:
            entry["surface_loudness_rise_lufs"] = round(loudness_rise, 2)
            entry["surface_balance_rise"] = round(surface_balance_rise, 3)
            entry["surface_percussive_ratio"] = round(percussive_ratio, 2)
        return hardens

    def _phrase_dynamic_event(entry: dict, last_macro_event_t: float) -> tuple[str | None, str | None]:
        """Detect local phrase gestures that macro body/pressure gates intentionally miss."""
        t = float(entry["t"])
        if t - last_macro_event_t <= EVENT_PHRASE_MACRO_SUPPRESS_SEC:
            return None, None
        if entry.get("silence") or entry.get("loudness_lufs") is None:
            return None, None

        phrase = [
            e for e in stream
            if t - EVENT_PHRASE_WINDOW_SEC <= float(e["t"]) < t
            and e.get("loudness_lufs") is not None
            and not e.get("silence")
        ]
        if len(phrase) < 3:
            return None, None

        half = max(1, len(phrase) // 2)
        baseline = phrase[:half]
        recent = phrase[half:]
        base_loudness = float(np.mean([float(e["loudness_lufs"]) for e in baseline]))
        recent_loudness = float(np.mean([float(e["loudness_lufs"]) for e in recent]))
        base_energy = float(np.mean([float(e["rms_energy"]) for e in baseline]))
        recent_energy = float(np.mean([float(e["rms_energy"]) for e in recent]))
        base_surface_balance = float(np.mean([float(e["surface_balance"]) for e in baseline]))
        recent_surface_balance = float(np.mean([float(e["surface_balance"]) for e in recent]))
        recent_pattern = float(np.mean([float(e["pattern"]) for e in recent]))

        loudness_delta = float(entry["loudness_lufs"]) - base_loudness
        recent_loudness_delta = recent_loudness - base_loudness
        energy_delta = float(entry["rms_energy"]) - base_energy
        surface_balance_delta = float(entry["surface_balance"]) - base_surface_balance
        disruption_now = 1.0 - float(entry["pattern"])

        entry["phrase_loudness_delta_lufs"] = round(loudness_delta, 2)
        entry["phrase_energy_delta"] = round(energy_delta, 4)
        entry["phrase_surface_balance_delta"] = round(surface_balance_delta, 3)

        if (
            loudness_delta >= EVENT_PHRASE_LIFT_LUFS
            and energy_delta >= EVENT_PHRASE_ENERGY_SURGE
            and surface_balance_delta >= EVENT_PHRASE_SPECTRAL_FLASH
        ):
            return "ornamental_flash", "bright local flash inside the phrase"
        if loudness_delta >= EVENT_PHRASE_LIFT_LUFS and energy_delta >= EVENT_PHRASE_ENERGY_SURGE:
            return "phrase_lifts", "phrase lifts"
        if recent_loudness_delta <= EVENT_PHRASE_DROP_LUFS and float(entry["pattern"]) >= EVENT_PHRASE_RETURN_LOCK:
            return "phrase_drops", "phrase drops back"
        if disruption_now >= EVENT_PHRASE_TURN_DISRUPTION and recent_pattern >= EVENT_PHRASE_RETURN_LOCK:
            return "section_turns", "phrase turns while the larger pattern holds"
        return None, None

    # ===== BUILD PERCEPTION STREAM =====
    stream = []
    previous_weight_state = None
    last_surface_event_t = -float("inf")
    pressure_ready_to_build = True
    pressure_ready_to_release = True
    last_pressure_event_t = -float("inf")
    attention_ready_to_grip = True
    attention_ready_to_release = False
    last_attention_event_t = -float("inf")
    body_lock_active = False
    body_lock_since = None
    body_unlock_since = None
    last_macro_event_t = -float("inf")
    last_phrase_event_t = -float("inf")
    expectation_debt = 0.0
    for i, t in enumerate(m_times):
        local_body, local_weight = _local_body_and_weight(float(t), i)
        local_body_state = local_body["body_state"]
        local_weight_state = local_weight["weight_state"]
        local_pattern = 1.0 - float(disruption[i])
        accent_phase_drift = _local_accent_phase_drift(float(t))
        surface_density = _local_surface_density(float(t), i)
        groove_comfort = _groove_comfort(
            float(local_body["body"]),
            local_pattern,
            float(pressure[i]),
            accent_phase_drift,
        )
        section_gravity = _section_gravity(
            float(attention[i]),
            local_pattern,
            float(local_body["body"]),
            accent_phase_drift,
        )
        prior_expectation_debt = expectation_debt
        release_force = float(np.clip(max(0.0, -float(pressure[i])) * (0.45 + prior_expectation_debt), 0.0, 1.0))
        stable_pocket = float(local_body["body"]) * local_pattern
        drift_debt = accent_phase_drift * 0.025 * (1.0 - 0.45 * stable_pocket)
        pressure_debt = max(0.0, float(pressure[i])) * 0.035 * (1.0 - 0.30 * groove_comfort)
        comfort_debt = max(0.0, 0.42 - groove_comfort) * 0.018
        disruption_debt = float(disruption[i]) * 0.075
        debt_input = disruption_debt + pressure_debt + drift_debt + comfort_debt
        debt_decay = 0.968 - min(0.018, release_force * 0.010)
        expectation_debt = float(np.clip(expectation_debt * debt_decay + debt_input - release_force * 0.24, 0.0, 1.0))
        surface_evidence = surface_snapshot(surface_bank, i)
        entry = {
            "t": round(float(t), 3),
            "rms_energy": round(float(rms_energy[i]), 4),
            "attention": round(float(attention[i]), 3),
            "pattern": round(local_pattern, 3),
            "pressure": round(float(pressure[i]), 3),
            "body_capture": local_body["body"],
            "body_comfort": groove_comfort,
            "groove_comfort": groove_comfort,
            "accent_phase_drift": accent_phase_drift,
            "expectation_debt": round(expectation_debt, 3),
            "release_force": round(release_force, 3),
            "section_gravity": section_gravity,
            "surface_density": surface_density,
            "body": local_body["body"],
            "body_state": local_body_state,
            "weight": local_weight["weight"],
            "weight_state": local_weight_state,
            "loudness_lufs": (
                None if not np.isfinite(loudness["short_term_lufs"][i])
                else round(float(loudness["short_term_lufs"][i]), 2)
            ),
            "pressure_lufs_delta": round(float(loudness["loudness_delta"][i]), 3),
            "pressure_state": (
                "silence" if loudness["silence_mask"][i]
                else "building" if pressure[i] > EVENT_PRESSURE_BUILDING
                else "releasing" if pressure[i] < EVENT_PRESSURE_RELEASING
                else "sustaining"
            ),
            "loudness_silence": bool(loudness["silence_mask"][i]),
            "surface_balance": round(float(hp_balance[i]), 3),
            "harmonic_weight": round(float(h_energy[i]), 4),
            "percussive_weight": round(float(p_energy[i]), 4),
            "surface_evidence": surface_evidence,
        }

        # Mark if we're in a silence, or just after one.
        for s in silences:
            if s["start"] <= t <= s["end"]:
                entry["silence"] = True
                entry["silence_depth_db"] = s["depth_db"]
                break
            if s["end"] < t <= s["end"] + 1.0:
                reentry = reentries_by_start.get(round(float(s["start"]), 2))
                if reentry:
                    entry["post_silence_reentry"] = reentry["reentry_shape"]
                    entry["boundary_position"] = reentry["boundary_position"]
                    entry["reentry_force"] = reentry["reentry_force"]
                break

        body_is_locked = local_body_state in {"emerging", "locked"}
        body_is_unlocked = local_body_state in {"absent", "weak"}
        if body_is_locked:
            if body_lock_since is None:
                body_lock_since = float(t)
            body_unlock_since = None
        elif body_is_unlocked:
            if body_unlock_since is None:
                body_unlock_since = float(t)
            body_lock_since = None

        body_lock_arrives = (
            not body_lock_active
            and body_lock_since is not None
            and float(t) - body_lock_since >= EVENT_BODY_LOCK_DWELL_SEC
        )
        body_lock_recedes = (
            body_lock_active
            and body_unlock_since is not None
            and float(t) - body_unlock_since >= EVENT_BODY_UNLOCK_DWELL_SEC
        )

        # Narrative flags (for experience write-ups).  Surface-transform events
        # get first claim when the whole surface hardens while the body current
        # remains continuous. Then local body/WDS changes describe felt carriage.
        if _surface_hardens(entry) and float(t) - last_surface_event_t >= EVENT_SURFACE_COOLDOWN_SEC:
            _mark_event(entry, "surface_hardens", "surface hardens while the body current holds")
            last_surface_event_t = float(t)
            last_macro_event_t = float(t)
        elif body_lock_arrives:
            note = (
                "body finds the pulse under weight"
                if local_weight_state in {"suspended", "heavy"}
                else "body finds the pulse"
            )
            _mark_event(entry, "body_lock_arrives", note)
            body_lock_active = True
            last_macro_event_t = float(t)
        elif body_lock_recedes:
            _mark_event(entry, "body_lock_recedes", "body lock loosens")
            body_lock_active = False
            last_macro_event_t = float(t)
        elif (
            local_weight_state in {"present", "suspended", "heavy"}
            and previous_weight_state in {None, "light"}
            and _wds_slope_event(entry, i, "arrives")
        ):
            note = (
                "weight gathers under the moving pulse"
                if local_body_state in {"emerging", "locked"}
                else "weight gathers"
            )
            _mark_event(entry, "weight_arrives", note)
            last_macro_event_t = float(t)
        elif (
            local_weight_state == "light"
            and previous_weight_state in {"present", "suspended", "heavy"}
            and _wds_slope_event(entry, i, "lifts")
        ):
            _mark_event(entry, "weight_lifts", "weight lifts")
            last_macro_event_t = float(t)
        elif (
            attention[i] > EVENT_ATTENTION_LOCKED
            and attention_ready_to_grip
            and float(t) - last_attention_event_t >= EVENT_ATTENTION_MIN_GAP_SEC
        ):
            _mark_event(entry, "attention_arrives", "motion settles into a reliable pattern")
            attention_ready_to_grip = False
            attention_ready_to_release = True
            last_attention_event_t = float(t)
            last_macro_event_t = float(t)
        elif (
            attention[i] < EVENT_ATTENTION_FLOATING
            and attention_ready_to_release
            and float(t) - last_attention_event_t >= EVENT_ATTENTION_MIN_GAP_SEC
        ):
            _mark_event(entry, "attention_releases", "motion loses its hold")
            attention_ready_to_release = False
            attention_ready_to_grip = True
            last_attention_event_t = float(t)
            last_macro_event_t = float(t)
        elif disruption[i] > EVENT_DISRUPTION_BREAK:
            _mark_event(entry, "pattern_breaks", "pattern breaks")
            last_macro_event_t = float(t)
        elif (
            pressure[i] > EVENT_PRESSURE_BUILDING
            and pressure_ready_to_build
            and float(t) - last_pressure_event_t >= EVENT_PRESSURE_MIN_GAP_SEC
        ):
            _mark_event(entry, "pressure_builds", "pressure builds")
            pressure_ready_to_build = False
            pressure_ready_to_release = True
            last_pressure_event_t = float(t)
            last_macro_event_t = float(t)
        elif (
            pressure[i] < EVENT_PRESSURE_RELEASING
            and pressure_ready_to_release
            and float(t) - last_pressure_event_t >= EVENT_PRESSURE_MIN_GAP_SEC
        ):
            _mark_event(entry, "pressure_releases", "pressure releases")
            pressure_ready_to_release = False
            pressure_ready_to_build = True
            last_pressure_event_t = float(t)
            last_macro_event_t = float(t)
        elif float(t) - last_phrase_event_t >= EVENT_PHRASE_MIN_GAP_SEC:
            phrase_event, phrase_note = _phrase_dynamic_event(entry, last_macro_event_t)
            if phrase_event and phrase_note:
                _mark_event(entry, phrase_event, phrase_note)
                last_phrase_event_t = float(t)

        if pressure[i] <= EVENT_PRESSURE_BUILD_RESET:
            pressure_ready_to_build = True
        if pressure[i] >= EVENT_PRESSURE_RELEASE_RESET:
            pressure_ready_to_release = True
        if attention[i] <= EVENT_ATTENTION_LOCK_RESET:
            attention_ready_to_grip = True
        if attention[i] >= EVENT_ATTENTION_FLOAT_RESET:
            attention_ready_to_release = True

        previous_weight_state = local_weight_state
        stream.append(entry)

    # ===== SYNTHESIZE SUSTAINED-STATE SPANS =====
    def _dominant_span_label(frames: list[dict]) -> tuple[str | None, str | None]:
        """Name long stable listener states that point-events under-describe."""
        if not frames:
            return None, None
        mean_pattern = float(np.mean([float(e.get("pattern", 0.0)) for e in frames]))
        mean_attention = float(np.mean([float(e.get("attention", 0.0)) for e in frames]))
        mean_debt = float(np.mean([float(e.get("expectation_debt", 0.0)) for e in frames]))
        peak_debt = float(np.max([float(e.get("expectation_debt", 0.0)) for e in frames]))
        mean_drift = float(np.mean([float(e.get("accent_phase_drift", 0.0)) for e in frames]))
        peak_drift = float(np.max([float(e.get("accent_phase_drift", 0.0)) for e in frames]))
        mean_body_capture = float(np.mean([float(e.get("body_capture", e.get("body", 0.0))) for e in frames]))
        mean_body_comfort = float(np.mean([float(e.get("body_comfort", e.get("groove_comfort", 0.0))) for e in frames]))
        mean_release = float(np.mean([float(e.get("release_force", 0.0)) for e in frames]))

        if mean_release >= 0.18:
            return "release_span", "release force active"

        if mean_pattern >= 0.90 and mean_attention >= 0.80 and mean_body_comfort >= 0.58 and mean_debt <= 0.55:
            return "stable_runway", "stable runway; grid settled; debt low"

        if mean_pattern >= 0.90 and mean_body_capture >= 0.70 and mean_body_comfort >= 0.38 and mean_debt <= 0.72:
            return "pocket_groove", "body captured by a settled pocket"

        if mean_pattern >= 0.90 and mean_attention >= 0.82 and mean_body_capture >= 0.65 and mean_body_comfort >= 0.34 and mean_drift <= 0.68:
            return "warped_groove", "stable groove with active surface deformation"

        if mean_pattern >= 0.90 and mean_attention >= 0.82 and mean_body_capture >= 0.68 and mean_drift >= 0.62 and mean_debt <= 0.82:
            return "lattice_engine", "interlocking grid; body held by precision"

        if mean_pattern >= 0.90 and mean_attention >= 0.80 and mean_body_capture >= 0.55 and peak_debt >= 0.78:
            details = ["locked engine"]
            if mean_debt >= 0.62:
                details.append("expectation debt accumulating")
            if peak_drift >= 0.70 or mean_drift >= 0.25:
                details.append("accent phase drift active")
            if mean_body_capture >= 0.55 and mean_body_comfort <= mean_body_capture - 0.18:
                details.append("body captured but braced")
            return "locked_engine", "; ".join(details)

        return None, None

    span_boundaries = {0.0, round(float(duration), 3)}
    for e in stream:
        if e.get("event"):
            span_boundaries.add(round(float(e["t"]), 3))
    for s in silences:
        span_boundaries.add(round(float(s["start"]), 3))
        span_boundaries.add(round(float(s["end"]), 3))
    span_points = sorted(span_boundaries)
    sustained_state_spans = []
    min_span_sec = 12.0
    for start, end in zip(span_points, span_points[1:]):
        if end - start < min_span_sec:
            continue
        frames = [e for e in stream if start <= float(e["t"]) < end and not e.get("silence")]
        if len(frames) < 4:
            continue
        label, note = _dominant_span_label(frames)
        if not label or not note:
            continue
        sustained_state_spans.append({
            "start": round(float(start), 1),
            "end": round(float(end), 1),
            "duration": round(float(end - start), 1),
            "type": label,
            "description": note,
            "mean_pattern": round(float(np.mean([float(e["pattern"]) for e in frames])), 3),
            "mean_attention": round(float(np.mean([float(e["attention"]) for e in frames])), 3),
            "mean_expectation_debt": round(float(np.mean([float(e["expectation_debt"]) for e in frames])), 3),
            "peak_expectation_debt": round(float(np.max([float(e["expectation_debt"]) for e in frames])), 3),
            "peak_accent_phase_drift": round(float(np.max([float(e["accent_phase_drift"]) for e in frames])), 3),
            "mean_body_capture": round(float(np.mean([float(e["body_capture"]) for e in frames])), 3),
            "mean_body_comfort": round(float(np.mean([float(e["body_comfort"]) for e in frames])), 3),
        })

    # ===== FIND KEY MOMENTS (pattern breaks) =====
    pattern_breaks = []

    # Highest disruption moments (pattern breaks)
    top_disruptions = np.argsort(-disruption)[:TOP_DISRUPTION_COUNT]
    for idx in top_disruptions:
        if disruption[idx] > PATTERN_BREAK_MIN_DISRUPTION:
            pattern_breaks.append({
                "time": round(float(m_times[idx]), 1),
                "type": "pattern_break",
                "intensity": round(float(disruption[idx]), 3),
                "description": f"pattern break at {m_times[idx]:.0f}s "
                    f"(beat:{d_beat[idx]:.2f} spectral:{d_spectral[idx]:.2f} energy:{d_energy[idx]:.2f})"
            })

    # Attention shifts
    attention_diff = np.diff(attention)
    big_drops = np.where(attention_diff < -ATTENTION_SHIFT_THRESHOLD)[0]
    for idx in big_drops:
        pattern_breaks.append({
            "time": round(float(m_times[idx]), 1),
            "type": "attention_drop",
            "from": round(float(attention[idx]), 3),
            "to": round(float(attention[idx + 1]), 3),
        })

    big_gains = np.where(attention_diff > ATTENTION_SHIFT_THRESHOLD)[0]
    for idx in big_gains:
        pattern_breaks.append({
            "time": round(float(m_times[idx]), 1),
            "type": "attention_gain",
            "from": round(float(attention[idx]), 3),
            "to": round(float(attention[idx + 1]), 3),
        })

    # Silences
    for s in silences:
        reentry = reentries_by_start.get(round(float(s["start"]), 2), {})
        event = {
            "time": s["start"],
            "type": "silence",
            "duration": s["duration"],
            "depth_db": s["depth_db"],
        }
        if reentry:
            event.update({
                "reentry_shape": reentry["reentry_shape"],
                "boundary_position": reentry["boundary_position"],
                "reentry_force": reentry["reentry_force"],
                "recovery_time_sec": reentry["recovery_time_sec"],
                "recovered": reentry["recovered"],
            })
        pattern_breaks.append(event)

    # Sort pattern breaks chronologically
    # Terminal silence can make the beat-grid detector report repeated
    # non-musical breaks after the track has functionally ended. Collapse
    # those into the silence event instead of listing chatter.
    terminal_silence_start = None
    for s in silences:
        if duration > 0 and s.get("end", 0) >= duration - 0.25:
            terminal_silence_start = float(s["start"])
            break
    if terminal_silence_start is not None:
        pattern_breaks = [
            pb for pb in pattern_breaks
            if not (pb.get("type") == "pattern_break" and float(pb.get("time", 0.0)) >= terminal_silence_start)
        ]

    pattern_breaks.sort(key=lambda m: m["time"])

    # ===== ACTIVE-FRAME STATISTICS =====
    # Identify which stream indices are silent (inside a detected silence window).
    # Active frames are everything else — this lets us report clean stats
    # for tracks that use silence intentionally (Helvegen, Feldman, etc.)
    # without contaminating attention/pattern with flat-line silence frames.
    silent_mask = np.zeros(len(m_times), dtype=bool)
    for s in silences:
        silent_mask |= (m_times >= s["start"]) & (m_times <= s["end"])
    active_mask = ~silent_mask

    total_silence_sec = round(sum(s["duration"] for s in silences), 1)
    active_duration_sec = round(duration - total_silence_sec, 1)
    silence_pct = round(total_silence_sec / duration * 100, 1) if duration > 0 else 0.0

    # Active-frame attention and pattern (only meaningful if there's significant silence)
    if active_mask.any():
        active_attention = attention[active_mask]
        active_disruption = disruption[active_mask]
        mean_attention_active = round(float(np.mean(active_attention)), 3)
        mean_pattern_active = round(1.0 - float(np.mean(active_disruption)), 3)
        attention_range_active = [
            round(float(np.min(active_attention)), 3),
            round(float(np.max(active_attention)), 3),
        ]
    else:
        mean_attention_active = round(float(np.mean(attention)), 3)
        mean_pattern_active = round(1.0 - float(np.mean(disruption)), 3)
        attention_range_active = [round(float(np.min(attention)), 3), round(float(np.max(attention)), 3)]

    stream_metric_fields = (
        "groove_comfort",
        "accent_phase_drift",
        "expectation_debt",
        "release_force",
        "section_gravity",
        "body_capture",
        "body_comfort",
        "surface_density",
    )
    surface_metric_fields = (
        "roughness",
        "noise_density",
        "transient_attack",
        "sustain_drone",
        "band_pressure",
        "surface_motion",
        "punch",
        "bass_weight",
        "body_weight",
        "presence_weight",
        "air_weight",
        "brightness_tilt",
    )
    stream_metric_means = {
        f"mean_{field}": round(float(np.mean([float(e[field]) for e in stream])), 3)
        for field in stream_metric_fields
        if stream
    }
    stream_metric_peaks = {
        f"peak_{field}": round(float(np.max([float(e[field]) for e in stream])), 3)
        for field in stream_metric_fields
        if stream
    }
    surface_metric_means = {
        f"mean_surface_{field}": round(float(np.mean([
            float(e["surface_evidence"][field]) for e in stream
        ])), 3)
        for field in surface_metric_fields
        if stream
    }
    surface_metric_peaks = {
        f"peak_surface_{field}": round(float(np.max([
            float(e["surface_evidence"][field]) for e in stream
        ])), 3)
        for field in surface_metric_fields
        if stream
    }

    # ===== PERCEPTION REPORT =====
    summary = {
        "mean_attention": round(float(np.mean(attention)), 3),
        "mean_pattern": round(1.0 - float(np.mean(disruption)), 3),
        "attention_range": [round(float(np.min(attention)), 3), round(float(np.max(attention)), 3)],
        "total_silence_sec": total_silence_sec,
        "pattern_break_count": len(pattern_breaks),
        "pressure_building_pct": round(float(np.mean(pressure > 0.05)) * 100, 1),
        "pressure_releasing_pct": round(float(np.mean(pressure < -0.05)) * 100, 1),
        "pressure_sustaining_pct": round(float(np.mean(np.abs(pressure) <= 0.05)) * 100, 1),
        "integrated_lufs": loudness["integrated_lufs"],
        "loudness_floor_lufs": loudness["floor_lufs"],
        "loudness_silence_pct": round(float(np.mean(loudness["silence_mask"])) * 100, 1),
        # Active-frame stats
        "active_duration_sec": active_duration_sec,
        "silent_duration_sec": total_silence_sec,
        "silence_pct": silence_pct,
        "mean_attention_active": mean_attention_active,
        "mean_pattern_active": mean_pattern_active,
        "attention_range_active": attention_range_active,
        "silence_reentry_count": len(silence_reentries),
        "silence_reentry_shapes": {
            shape: sum(1 for r in silence_reentries if r["reentry_shape"] == shape)
            for shape in (
                "entry_preparation", "continuation", "rupture", "reset",
                "withdrawal", "terminal_decay"
            )
        },
        "silence_boundary_positions": {
            position: sum(1 for r in silence_reentries if r["boundary_position"] == position)
            for position in ("opening", "internal", "closing")
        },
        **stream_metric_means,
        **stream_metric_peaks,
        **surface_metric_means,
        **surface_metric_peaks,
    }

    # Count pattern_breaks by type
    pb_types = ["pattern_break", "attention_drop", "attention_gain", "silence"]
    pb_counts = {t: sum(1 for pb in pattern_breaks if pb["type"] == t) for t in pb_types}
    summary["pattern_break_counts"] = pb_counts

    metadata = artifact_metadata(module="perception", stream_schema=SCHEMA_VERSION, audio_path=None)

    report = {
        "track": track_name,
        "galdr_version": metadata["galdr_version"],
        "schema_version": metadata["schema_version"],
        "created_at": metadata["created_at"],
        "module": metadata["module"],
        "duration": round(duration, 1),
        "tempo": round(tempo, 1),
        "silences": silences,
        "silence_reentries": silence_reentries,
        "pattern_breaks": pattern_breaks,
        "sustained_state_spans": sustained_state_spans,
        "summary": summary,
        "stream_hop_sec": round(float(hop_sec), 3),
        "stream_length": len(stream),
    }

    report["stream"] = stream

    # Stash the DSP arrays so the file-writing wrapper can draw plots without
    # rerunning the STFT/HPSS/loudness passes. Keys are popped before disk
    # serialization (see generate_perception_stream).
    report["_viz_m_times"] = m_times
    report["_viz_attention"] = attention
    report["_viz_s_times"] = s_times
    report["_viz_disruption"] = disruption
    report["_viz_d_beat"] = d_beat
    report["_viz_d_spectral"] = d_spectral
    report["_viz_d_energy"] = d_energy
    report["_viz_p_times"] = p_times
    report["_viz_pressure"] = pressure
    report["_viz_hp_times"] = hp_times
    report["_viz_hp_balance"] = hp_balance

    return report


def generate_perception_stream(audio_path, output_dir, track_name, hop_sec: float = ATTENTION_HOP_SEC, audio: AudioContext | None = None):
    """Generate a second-by-second perception stream.

    This is the core output: a temporal narrative of what the music
    does to perception as it unfolds through time.

    Thin wrapper: loads audio, calls compute_perception(), saves files,
    generates plots, returns the report dict with embedded stream.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Perceiving {audio_path}...")
    ctx = audio or load_audio_context(audio_path)
    y, sr = ctx.y, ctx.sr

    print("  Tracking beats...")
    print("  Computing attention...")
    print("  Computing pattern...")
    print("  Computing pressure...")
    print("  Detecting silences...")
    print("  Computing harmonic/percussive balance...")

    report = compute_perception(y, sr, track_name, hop_sec=hop_sec)
    metadata = artifact_metadata(module="perception", stream_schema=SCHEMA_VERSION, audio_path=audio_path)
    report.update(metadata)
    stream = report.get("stream", [])
    silences = report.get("silences", [])
    duration = report.get("duration", librosa.get_duration(y=y, sr=sr))

    # Reuse DSP arrays from compute_perception. Falling back to a recompute
    # would do a second full-track STFT and HPSS pass — multi-GB on long
    # tracks and the single biggest savings in the perception pipeline.
    m_times = report.pop("_viz_m_times")
    attention = report.pop("_viz_attention")
    s_times = report.pop("_viz_s_times")
    disruption = report.pop("_viz_disruption")
    d_beat = report.pop("_viz_d_beat")
    d_spectral = report.pop("_viz_d_spectral")
    d_energy = report.pop("_viz_d_energy")
    p_times = report.pop("_viz_p_times")
    pressure = report.pop("_viz_pressure")
    hp_times = report.pop("_viz_hp_times")
    hp_balance = report.pop("_viz_hp_balance")

    # Save stream (separate file — it's large)
    stream_path = out / f"{track_name}_stream.json"
    stream_payload = {
        "galdr_version": report.get("galdr_version"),
        "schema_version": report.get("schema_version"),
        "created_at": report.get("created_at"),
        "module": "perception_stream",
        "source": report.get("source"),
        "stream_hop_sec": report.get("stream_hop_sec"),
        "stream_length": len(stream),
        "stream": stream,
    }
    with open(stream_path, "w") as f:
        json.dump(stream_payload, f)
    print(f"  Stream saved: {stream_path} ({len(stream)} entries)")

    # Save report (without stream or internal viz arrays)
    report_for_disk = {
        k: v for k, v in report.items()
        if k != "stream" and not k.startswith("_")
    }
    report_path = out / f"{track_name}_perception.json"
    with open(report_path, "w") as f:
        json.dump(report_for_disk, f, indent=2)
    print(f"  Perception report saved: {report_path}")

    # ===== VISUALIZATIONS =====
    if m_times is not None and attention is not None:
        fig_w, fig_h = 16, 3

        # 1. Attention + Surprise (the listener plot)
        print("  Generating perception plot...")
        fig, axes = plt.subplots(3, 1, figsize=(fig_w, fig_h * 3), sharex=True)

        # Attention
        axes[0].fill_between(m_times, attention, alpha=0.4, color="#2ecc71")
        axes[0].plot(m_times, attention, color="#27ae60", linewidth=1)
        axes[0].set_ylabel("Attention")
        axes[0].set_ylim(-0.05, 1.05)
        axes[0].set_title(f"{track_name} — Rhythmic Attention (listener)", fontsize=13)
        for s in silences:
            axes[0].axvspan(s["start"], s["end"], alpha=0.3, color="#e74c3c", label="silence")

        # Pattern (inverted disruption: high = locked in)
        pattern_total = 1.0 - disruption
        pattern_beat = 1.0 - d_beat
        pattern_spectral = 1.0 - d_spectral
        pattern_energy = 1.0 - d_energy
        axes[1].fill_between(s_times, pattern_total, alpha=0.3, color="#2980b9")
        axes[1].plot(s_times, pattern_beat, color="#e67e22", linewidth=0.8, alpha=0.7, label="beat")
        axes[1].plot(s_times, pattern_spectral, color="#9b59b6", linewidth=0.8, alpha=0.7, label="spectral")
        axes[1].plot(s_times, pattern_energy, color="#3498db", linewidth=0.8, alpha=0.7, label="energy")
        axes[1].set_ylabel("Pattern")
        axes[1].set_ylim(-0.05, 1.05)
        axes[1].set_title("Pattern (prediction accuracy)", fontsize=13)
        axes[1].legend(loc="lower right", fontsize=9)

        # Pressure
        axes[2].fill_between(p_times, pressure, where=pressure > 0, alpha=0.4, color="#2ecc71", label="building")
        axes[2].fill_between(p_times, pressure, where=pressure < 0, alpha=0.4, color="#e74c3c", label="releasing")
        axes[2].axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
        axes[2].set_ylabel("Pressure")
        axes[2].set_ylim(-1.05, 1.05)
        axes[2].set_xlabel("Time (s)")
        axes[2].set_title("Pressure (heard pressure direction)", fontsize=13)
        axes[2].legend(loc="upper right", fontsize=9)

        plt.tight_layout()
        plt.savefig(out / f"{track_name}_perception.png", dpi=150)
        plt.close()
        print(f"  Perception plot saved.")

        # 2. HP Balance over time
        print("  Generating surface balance plot...")
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.fill_between(hp_times, hp_balance, where=hp_balance < 0, alpha=0.4,
                        color="#2ecc71", label="harmonic dominant")
        ax.fill_between(hp_times, hp_balance, where=hp_balance > 0, alpha=0.4,
                        color="#e67e22", label="percussive dominant")
        ax.axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
        ax.set_ylabel("<- harmonic | percussive ->")
        ax.set_xlabel("Time (s)")
        ax.set_ylim(-1.05, 1.05)
        ax.set_title(f"{track_name} — Voice vs Drums (who's carrying?)", fontsize=13)
        ax.legend(loc="upper right", fontsize=9)
        for s in silences:
            ax.axvspan(s["start"], s["end"], alpha=0.3, color="#e74c3c")
        plt.tight_layout()
        plt.savefig(out / f"{track_name}_hp_balance.png", dpi=150)
        plt.close()

        print("  Generating listener-state metric plot...")
        _plot_listener_state_metrics(stream, silences, out, track_name)
        print("  Listener-state metric plot saved.")

        print("  Generating surface evidence plot...")
        _plot_surface_evidence_metrics(stream, silences, out, track_name)
        print("  Surface evidence plot saved.")

        print("  Generating reading map plot...")
        _plot_reading_map(y, sr, stream, hp_times, hp_balance, silences, out, track_name)
        print("  Reading map plot saved.")

    return report
