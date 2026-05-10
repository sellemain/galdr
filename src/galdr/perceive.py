#!/usr/bin/env python3
"""Perception layer — what the music DOES to the listener.

Concepts:
- Momentum: a rolling measure of rhythmic consistency. High = the listener
  is locked in, tracking confidently.
- Surprise: where expectations break. A beat that should land and doesn't.
- Breath: heard-pressure change. Building, sustaining, releasing, or silence.
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

from .analyze import compute_body_entrainment, compute_weight_drag_sway
from .constants import (
    MOMENTUM_WINDOW_SEC, MOMENTUM_HOP_SEC, MOMENTUM_MIN_BEATS,
    DISRUPTION_WEIGHT_BEAT, DISRUPTION_WEIGHT_SPECTRAL, DISRUPTION_WEIGHT_ENERGY,
    DISRUPTION_BEAT_LOOKBACK_SEC, DISRUPTION_BEAT_ABSENCE_THRESHOLD_SEC,
    DISRUPTION_BEAT_ABSENCE_MAX_SEC, DISRUPTION_SPECTRAL_SMOOTH_SEC,
    DISRUPTION_ENERGY_SMOOTH_SEC,
    BREATH_SMOOTH_SEC,
    SILENCE_THRESHOLD_DB, SILENCE_MIN_DURATION_SEC,
    HP_BALANCE_MIN_ENERGY, HP_SMOOTH_SEC,
    EVENT_MOMENTUM_LOCKED, EVENT_MOMENTUM_LOCK_RESET,
    EVENT_MOMENTUM_FLOATING, EVENT_MOMENTUM_FLOAT_RESET, EVENT_MOMENTUM_MIN_GAP_SEC,
    EVENT_BODY_LOCK_DWELL_SEC, EVENT_BODY_UNLOCK_DWELL_SEC,
    EVENT_DISRUPTION_BREAK, EVENT_BREATH_BUILDING, EVENT_BREATH_RELEASING,
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
    PATTERN_BREAK_MIN_DISRUPTION, MOMENTUM_SHIFT_THRESHOLD, TOP_DISRUPTION_COUNT,
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


def compute_momentum(beat_times, duration,
                     window_sec=MOMENTUM_WINDOW_SEC,
                     hop_sec=MOMENTUM_HOP_SEC):
    """Rolling rhythmic momentum — how locked-in the beat is right now.

    Returns (times, momentum) where momentum is 0-1.
    1.0 = perfectly regular beats in the window (listener locked).
    0.0 = no beats in the window (listener holding/lost).
    """
    times = np.arange(0, duration, hop_sec)
    momentum = np.zeros_like(times)

    for i, t in enumerate(times):
        # Find beats within the window centered on t
        window_beats = beat_times[
            (beat_times >= t - window_sec / 2) & (beat_times < t + window_sec / 2)
        ]
        if len(window_beats) < MOMENTUM_MIN_BEATS:
            momentum[i] = 0.0
            continue

        intervals = np.diff(window_beats)
        mean_interval = np.mean(intervals)
        if mean_interval == 0:
            momentum[i] = 0.0
            continue

        # Regularity: low variance = high momentum
        cv = np.std(intervals) / mean_interval  # coefficient of variation
        regularity = max(0, 1.0 - cv)

        # Density: how many beats vs expected at the track's average tempo
        expected_beats = window_sec / mean_interval
        density = min(1.0, len(window_beats) / max(1, expected_beats))

        momentum[i] = regularity * density

    return times, momentum


def compute_disruption(y, sr, beat_times, duration, hop_sec=MOMENTUM_HOP_SEC):
    """Where the pattern breaks — how much expectations deviate from what arrives.

    Three components:
    1. Beat disruption: a beat was predicted but didn't arrive on time
    2. Spectral disruption: the frequency content shifted suddenly
    3. Energy disruption: the loudness jumped or dropped faster than the local trend

    Returns (times, disruption_total, disruption_beat, disruption_spectral, disruption_energy)
    Invert (1.0 - disruption) to get pattern_lock.
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
    S = np.abs(librosa.stft(y))
    spectral_flux = np.sqrt(np.mean(np.diff(S, axis=1) ** 2, axis=0))
    flux_times = librosa.frames_to_time(np.arange(len(spectral_flux)), sr=sr)
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


def compute_loudness(y, sr, duration, hop_sec=MOMENTUM_HOP_SEC):
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

    breath_smooth_frames = _duration_to_frames(BREATH_SMOOTH_SEC, hop_sec, max_len=len(filled))
    smoothed = uniform_filter1d(filled, size=breath_smooth_frames)
    if len(smoothed) > 1:
        delta = np.gradient(smoothed)
        delta[silence_mask] = 0.0
        # Ignore sub-audible numerical flutter in steady material. LUFS breath
        # should describe real pressure motion, not floating point dust.
        delta[np.abs(delta) < 0.05] = 0.0
        max_abs = np.max(np.abs(delta))
        breath = delta / max_abs if max_abs > 0 else np.zeros_like(delta)
    else:
        delta = np.zeros_like(smoothed)
        breath = np.zeros_like(smoothed)

    return {
        "times": times,
        "integrated_lufs": integrated_lufs,
        "short_term_lufs": curve,
        "smoothed_lufs": smoothed,
        "loudness_delta": delta,
        "breath": breath,
        "silence_mask": silence_mask,
        "floor_lufs": floor_lufs,
    }


def compute_breath(y, sr, duration, hop_sec=MOMENTUM_HOP_SEC):
    """Heard-pressure breath — building, sustaining, or releasing.

    Returns (times, breath) where:
    - Positive = building (perceived pressure increasing)
    - Zero = sustaining (stable or silence-aware)
    - Negative = releasing (perceived pressure decreasing)
    """
    loudness = compute_loudness(y, sr, duration, hop_sec=hop_sec)
    return loudness["times"], loudness["breath"]


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


def _classify_reentry(pre_momentum, post_momentum, pre_pressure, post_pressure, silence, duration):
    """Classify what the return after silence does to listener state."""
    boundary_position = _silence_boundary_position(silence, duration)
    if boundary_position == "opening":
        return "entry_preparation"
    if boundary_position == "closing" or post_momentum is None:
        return "terminal_decay"

    pre_m = 0.0 if pre_momentum is None else pre_momentum
    post_m = 0.0 if post_momentum is None else post_momentum
    pre_p = 0.0 if pre_pressure is None else pre_pressure
    post_p = 0.0 if post_pressure is None else post_pressure

    momentum_delta = post_m - pre_m
    pressure_delta = post_p - pre_p

    if post_m >= 0.75 and abs(momentum_delta) <= 0.20 and pressure_delta >= -0.15:
        return "continuation"
    if momentum_delta >= 0.25 or pressure_delta >= 0.25:
        return "rupture"
    if pre_m < 0.45 and post_m >= 0.60:
        return "reset"
    if post_m < 0.45 or pressure_delta <= -0.30:
        return "withdrawal"
    return "continuation"


def compute_silence_reentries(silences, times, momentum, breath, loudness_delta, duration,
                              short_window_sec=1.5, recovery_threshold=0.85,
                              max_recovery_sec=8.0):
    """Measure return behavior after detected silences.

    Silence itself is only half the gesture.  This records what happens
    immediately after the gap: how forcefully pressure returns, how long
    listener momentum takes to recover, and whether the return behaves like
    continuation, rupture, reset, withdrawal, entry preparation, or terminal
    decay.
    """
    events = []
    if not silences:
        return events

    times = np.asarray(times)
    momentum = np.asarray(momentum)
    breath = np.asarray(breath)
    loudness_delta = np.asarray(loudness_delta)

    for silence in silences:
        start = float(silence["start"])
        end = float(silence["end"])
        pre_start = max(0.0, start - short_window_sec)
        post_end = min(duration, end + short_window_sec)

        pre_momentum = _window_mean(momentum, times, pre_start, start)
        post_momentum = _window_mean(momentum, times, end, post_end)
        pre_pressure = _window_mean(breath, times, pre_start, start)
        post_pressure = _window_mean(breath, times, end, post_end)
        post_loudness_delta = _window_mean(loudness_delta, times, end, post_end)

        baseline = pre_momentum if pre_momentum is not None else None
        recovery_time = None
        recovered = False
        if baseline is not None and end < duration:
            target = min(max(baseline * recovery_threshold, 0.35), 0.9)
            recovery_mask = (times >= end) & (times <= min(duration, end + max_recovery_sec))
            candidates = np.where(recovery_mask & (momentum >= target))[0]
            if candidates.size:
                recovery_time = round(float(times[candidates[0]] - end), 2)
                recovered = True

        pre_p = 0.0 if pre_pressure is None else pre_pressure
        post_p = 0.0 if post_pressure is None else post_pressure
        post_m = 0.0 if post_momentum is None else post_momentum
        pre_m = 0.0 if pre_momentum is None else pre_momentum
        force = max(0.0, (post_m - pre_m) * 0.55 + max(0.0, post_p - pre_p) * 0.45)
        if post_loudness_delta is not None:
            force += max(0.0, post_loudness_delta) * 0.15

        boundary_position = _silence_boundary_position(silence, duration)
        shape = _classify_reentry(pre_momentum, post_momentum, pre_pressure, post_pressure, silence, duration)

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
            "pre_momentum": None if pre_momentum is None else round(float(pre_momentum), 3),
            "post_momentum": None if post_momentum is None else round(float(post_momentum), 3),
            "pre_pressure": None if pre_pressure is None else round(float(pre_pressure), 3),
            "post_pressure": None if post_pressure is None else round(float(post_pressure), 3),
        })

    return events


def compute_harmonic_percussive_momentum(y, sr, duration,
                                         hop_sec=MOMENTUM_HOP_SEC):
    """Track which channel is carrying the energy over time.

    Returns (times, h_energy, p_energy, balance) where balance is
    -1 (pure harmonic) to +1 (pure percussive), 0 = balanced.
    """
    y_h, y_p = librosa.effects.hpss(y)

    rms_h = librosa.feature.rms(y=y_h)[0]
    rms_p = librosa.feature.rms(y=y_p)[0]
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


def compute_perception(y: np.ndarray, sr: int, track_name: str, hop_sec: float = MOMENTUM_HOP_SEC) -> dict:
    """Compute perception stream and report from audio array. No file I/O, no plots.

    Calls the existing pure DSP functions (compute_momentum, compute_disruption,
    compute_breath, detect_silences, compute_harmonic_percussive_momentum),
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
    m_times, momentum = compute_momentum(beat_times, duration, hop_sec=hop_sec)

    s_times, disruption, d_beat, d_spectral, d_energy = compute_disruption(
        y, sr, beat_times, duration, hop_sec=hop_sec
    )

    loudness = compute_loudness(y, sr, duration, hop_sec=hop_sec)
    b_times = loudness["times"]
    breath = loudness["breath"]

    silences = detect_silences(y, sr)

    hp_times, h_energy, p_energy, hp_balance = compute_harmonic_percussive_momentum(
        y, sr, duration, hop_sec=hop_sec
    )

    silence_reentries = compute_silence_reentries(
        silences, m_times, momentum, breath, loudness["loudness_delta"], duration
    )
    reentries_by_start = {r["silence_start"]: r for r in silence_reentries}

    # Energy interpolated to our time grid
    energy = np.interp(m_times, rms_times, rms)

    def _local_body_and_weight(t: float, idx: int) -> tuple[dict, dict]:
        """Compute local body-lock and weight/drag/sway for the current listening window."""
        half_window = MOMENTUM_WINDOW_SEC / 2.0
        start = max(0.0, t - half_window)
        end = min(duration, t + half_window)
        window_duration = max(end - start, hop_sec)

        local_beats = beat_times[(beat_times >= start) & (beat_times < end)]
        if len(local_beats) > 2:
            intervals = np.diff(local_beats)
            mean_interval = float(np.mean(intervals))
            pulse_stability = max(0.0, 1.0 - (float(np.std(intervals)) / mean_interval)) if mean_interval > 0 else 0.0
            expected_beats = window_duration / mean_interval if mean_interval > 0 else 0.0
            pulse_confidence = float(np.clip(len(local_beats) / max(expected_beats, 1.0), 0.0, 1.0))
        else:
            pulse_stability = 0.0
            pulse_confidence = 0.0

        local_onsets = onset_times[(onset_times >= start) & (onset_times < end)]
        onsets_per_second = len(local_onsets) / window_duration

        frame_mask = (m_times >= start) & (m_times < end)
        if not frame_mask.any():
            frame_mask[idx] = True

        local_harmonic = float(np.mean(h_energy[frame_mask]))
        local_percussive = float(np.mean(p_energy[frame_mask]))
        total_texture = local_harmonic + local_percussive
        texture_balance = local_percussive / total_texture if total_texture > HP_BALANCE_MIN_ENERGY else 0.0

        rms_mask = (rms_times >= start) & (rms_times < end)
        local_rms = rms[rms_mask]
        positive_rms = local_rms[local_rms > 0]
        dynamic_range_ratio = float(np.max(positive_rms) / np.min(positive_rms)) if len(positive_rms) > 1 else 1.0

        body = compute_body_entrainment(
            duration=window_duration,
            beat_count=len(local_beats),
            pulse_stability=pulse_stability,
            pulse_confidence=pulse_confidence,
            pulse_ambiguous=False,
            texture_balance=texture_balance,
            onsets_per_second=onsets_per_second,
        )
        weight = compute_weight_drag_sway(
            pulse_stability=pulse_stability,
            pulse_confidence=pulse_confidence,
            body_entrainment=body["body_entrainment"],
            texture_balance=texture_balance,
            onsets_per_second=onsets_per_second,
            harmonic_weight=local_harmonic,
            percussive_weight=local_percussive,
            dynamic_range_ratio=dynamic_range_ratio,
        )
        return body, weight

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

        body_vals = [float(e["body_entrainment"]) for e in phrase]
        texture_vals = [float(e["texture_balance"]) for e in phrase]
        loudness_vals = [float(e["loudness_lufs"]) for e in phrase if e.get("loudness_lufs") is not None]
        if not loudness_vals:
            return False

        body_range = max(body_vals) - min(body_vals)
        texture_range = max(texture_vals) - min(texture_vals)
        loudness_range = max(loudness_vals) - min(loudness_vals)

        return (
            body_range <= EVENT_WDS_PHRASE_BODY_DELTA_MAX
            and texture_range <= EVENT_WDS_PHRASE_TEXTURE_DELTA_MAX
            and loudness_range <= EVENT_WDS_PHRASE_LOUDNESS_DELTA_MAX
        )

    def _wds_slope_event(entry: dict, idx: int, direction: str) -> bool:
        """Gate WDS prose events by felt movement, not label-boundary chatter."""
        current = float(entry["weight_drag_sway"])
        t = float(entry["t"])
        lookback = np.where(m_times <= t - EVENT_WDS_SLOPE_WINDOW_SEC)[0]
        if len(lookback) == 0:
            return False

        prior = stream[int(lookback[-1])]
        previous = float(prior["weight_drag_sway"])
        delta = current - previous
        entry["weight_drag_sway_delta"] = round(delta, 3)

        loudness_lufs = entry.get("loudness_lufs")
        if entry.get("silence") or (loudness_lufs is not None and loudness_lufs <= EVENT_WDS_SILENCE_LUFS_CEILING):
            return False
        if _stable_phrase_motion(entry):
            entry["weight_drag_sway_motion"] = "phrase_internal"
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
        base_texture = float(np.mean([float(e["texture_balance"]) for e in baseline]))
        base_percussive = float(np.mean([float(e["percussive_weight"]) for e in baseline]))

        loudness_rise = float(entry["loudness_lufs"]) - base_loudness
        texture_rise = float(entry["texture_balance"]) - base_texture
        percussive_ratio = float(entry["percussive_weight"]) / max(base_percussive, 1e-6)

        body_holds = float(entry["body_entrainment"]) >= EVENT_SURFACE_BODY_HOLD_MIN
        pattern_holds = float(entry["pattern_lock"]) >= EVENT_SURFACE_PATTERN_HOLD_MIN
        hardens = (
            loudness_rise >= EVENT_SURFACE_LOUDNESS_RISE_LUFS
            and texture_rise >= EVENT_SURFACE_TEXTURE_RISE
            and float(entry["texture_balance"]) >= EVENT_SURFACE_CURRENT_TEXTURE_MIN
            and float(entry["percussive_weight"]) >= EVENT_SURFACE_CURRENT_PERCUSSIVE_MIN
            and percussive_ratio >= EVENT_SURFACE_PERCUSSIVE_RISE_RATIO
            and body_holds
            and pattern_holds
        )

        if hardens:
            entry["surface_loudness_rise_lufs"] = round(loudness_rise, 2)
            entry["surface_texture_rise"] = round(texture_rise, 3)
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
        base_weight = float(np.mean([float(e["weight"]) for e in baseline]))
        recent_weight = float(np.mean([float(e["weight"]) for e in recent]))
        base_texture = float(np.mean([float(e["texture_balance"]) for e in baseline]))
        recent_texture = float(np.mean([float(e["texture_balance"]) for e in recent]))
        recent_pattern = float(np.mean([float(e["pattern_lock"]) for e in recent]))

        loudness_delta = float(entry["loudness_lufs"]) - base_loudness
        recent_loudness_delta = recent_loudness - base_loudness
        weight_delta = float(entry["weight"]) - base_weight
        texture_delta = float(entry["texture_balance"]) - base_texture
        disruption_now = 1.0 - float(entry["pattern_lock"])

        entry["phrase_loudness_delta_lufs"] = round(loudness_delta, 2)
        entry["phrase_weight_delta"] = round(weight_delta, 4)
        entry["phrase_texture_delta"] = round(texture_delta, 3)

        if (
            loudness_delta >= EVENT_PHRASE_LIFT_LUFS
            and weight_delta >= EVENT_PHRASE_ENERGY_SURGE
            and texture_delta >= EVENT_PHRASE_SPECTRAL_FLASH
        ):
            return "ornamental_flash", "bright local flash inside the phrase"
        if loudness_delta >= EVENT_PHRASE_LIFT_LUFS and weight_delta >= EVENT_PHRASE_ENERGY_SURGE:
            return "phrase_lifts", "phrase lifts"
        if recent_loudness_delta <= EVENT_PHRASE_DROP_LUFS and float(entry["pattern_lock"]) >= EVENT_PHRASE_RETURN_LOCK:
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
    momentum_ready_to_lock = True
    momentum_ready_to_unmoor = False
    last_momentum_event_t = -float("inf")
    body_lock_active = False
    body_lock_since = None
    body_unlock_since = None
    last_macro_event_t = -float("inf")
    last_phrase_event_t = -float("inf")
    for i, t in enumerate(m_times):
        local_body, local_weight = _local_body_and_weight(float(t), i)
        local_body_state = local_body["body_entrainment_state"]
        local_weight_state = local_weight["weight_drag_sway_state"]
        entry = {
            "t": round(float(t), 3),
            "weight": round(float(energy[i]), 4),
            "momentum": round(float(momentum[i]), 3),
            "pattern_lock": round(1.0 - float(disruption[i]), 3),
            "breath": round(float(breath[i]), 3),
            "body_entrainment": local_body["body_entrainment"],
            "body_entrainment_state": local_body_state,
            "weight_drag_sway": local_weight["weight_drag_sway"],
            "weight_drag_sway_state": local_weight_state,
            "loudness_lufs": (
                None if not np.isfinite(loudness["short_term_lufs"][i])
                else round(float(loudness["short_term_lufs"][i]), 2)
            ),
            "breath_lufs_delta": round(float(loudness["loudness_delta"][i]), 3),
            "pressure_state": (
                "silence" if loudness["silence_mask"][i]
                else "building" if breath[i] > EVENT_BREATH_BUILDING
                else "releasing" if breath[i] < EVENT_BREATH_RELEASING
                else "sustaining"
            ),
            "loudness_silence": bool(loudness["silence_mask"][i]),
            "texture_balance": round(float(hp_balance[i]), 3),
            "harmonic_weight": round(float(h_energy[i]), 4),
            "percussive_weight": round(float(p_energy[i]), 4),
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
            momentum[i] > EVENT_MOMENTUM_LOCKED
            and momentum_ready_to_lock
            and float(t) - last_momentum_event_t >= EVENT_MOMENTUM_MIN_GAP_SEC
        ):
            _mark_event(entry, "momentum_locks", "motion settles into a reliable pattern")
            momentum_ready_to_lock = False
            momentum_ready_to_unmoor = True
            last_momentum_event_t = float(t)
            last_macro_event_t = float(t)
        elif (
            momentum[i] < EVENT_MOMENTUM_FLOATING
            and momentum_ready_to_unmoor
            and float(t) - last_momentum_event_t >= EVENT_MOMENTUM_MIN_GAP_SEC
        ):
            _mark_event(entry, "momentum_unmoors", "motion loses its hold")
            momentum_ready_to_unmoor = False
            momentum_ready_to_lock = True
            last_momentum_event_t = float(t)
            last_macro_event_t = float(t)
        elif disruption[i] > EVENT_DISRUPTION_BREAK:
            _mark_event(entry, "pattern_breaks", "pattern breaks")
            last_macro_event_t = float(t)
        elif (
            breath[i] > EVENT_BREATH_BUILDING
            and pressure_ready_to_build
            and float(t) - last_pressure_event_t >= EVENT_PRESSURE_MIN_GAP_SEC
        ):
            _mark_event(entry, "pressure_builds", "pressure builds")
            pressure_ready_to_build = False
            pressure_ready_to_release = True
            last_pressure_event_t = float(t)
            last_macro_event_t = float(t)
        elif (
            breath[i] < EVENT_BREATH_RELEASING
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

        if breath[i] <= EVENT_PRESSURE_BUILD_RESET:
            pressure_ready_to_build = True
        if breath[i] >= EVENT_PRESSURE_RELEASE_RESET:
            pressure_ready_to_release = True
        if momentum[i] <= EVENT_MOMENTUM_LOCK_RESET:
            momentum_ready_to_lock = True
        if momentum[i] >= EVENT_MOMENTUM_FLOAT_RESET:
            momentum_ready_to_unmoor = True

        previous_weight_state = local_weight_state
        stream.append(entry)

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

    # Momentum shifts
    momentum_diff = np.diff(momentum)
    big_drops = np.where(momentum_diff < -MOMENTUM_SHIFT_THRESHOLD)[0]
    for idx in big_drops:
        pattern_breaks.append({
            "time": round(float(m_times[idx]), 1),
            "type": "momentum_drop",
            "from": round(float(momentum[idx]), 3),
            "to": round(float(momentum[idx + 1]), 3),
        })

    big_gains = np.where(momentum_diff > MOMENTUM_SHIFT_THRESHOLD)[0]
    for idx in big_gains:
        pattern_breaks.append({
            "time": round(float(m_times[idx]), 1),
            "type": "momentum_gain",
            "from": round(float(momentum[idx]), 3),
            "to": round(float(momentum[idx + 1]), 3),
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
    pattern_breaks.sort(key=lambda m: m["time"])

    # ===== ACTIVE-FRAME STATISTICS =====
    # Identify which stream indices are silent (inside a detected silence window).
    # Active frames are everything else — this lets us report clean stats
    # for tracks that use silence intentionally (Helvegen, Feldman, etc.)
    # without contaminating momentum/pattern_lock with flat-line silence frames.
    silent_mask = np.zeros(len(m_times), dtype=bool)
    for s in silences:
        silent_mask |= (m_times >= s["start"]) & (m_times <= s["end"])
    active_mask = ~silent_mask

    total_silence_sec = round(sum(s["duration"] for s in silences), 1)
    active_duration_sec = round(duration - total_silence_sec, 1)
    silence_pct = round(total_silence_sec / duration * 100, 1) if duration > 0 else 0.0

    # Active-frame momentum and pattern_lock (only meaningful if there's significant silence)
    if active_mask.any():
        active_momentum = momentum[active_mask]
        active_disruption = disruption[active_mask]
        mean_momentum_active = round(float(np.mean(active_momentum)), 3)
        mean_pattern_lock_active = round(1.0 - float(np.mean(active_disruption)), 3)
        momentum_range_active = [
            round(float(np.min(active_momentum)), 3),
            round(float(np.max(active_momentum)), 3),
        ]
    else:
        mean_momentum_active = round(float(np.mean(momentum)), 3)
        mean_pattern_lock_active = round(1.0 - float(np.mean(disruption)), 3)
        momentum_range_active = [round(float(np.min(momentum)), 3), round(float(np.max(momentum)), 3)]

    # ===== PERCEPTION REPORT =====
    summary = {
        "mean_momentum": round(float(np.mean(momentum)), 3),
        "mean_pattern_lock": round(1.0 - float(np.mean(disruption)), 3),
        "momentum_range": [round(float(np.min(momentum)), 3), round(float(np.max(momentum)), 3)],
        "total_silence_sec": total_silence_sec,
        "pattern_break_count": len(pattern_breaks),
        "breath_positive_pct": round(float(np.mean(breath > 0.05)) * 100, 1),
        "breath_negative_pct": round(float(np.mean(breath < -0.05)) * 100, 1),
        "breath_sustain_pct": round(float(np.mean(np.abs(breath) <= 0.05)) * 100, 1),
        "integrated_lufs": loudness["integrated_lufs"],
        "loudness_floor_lufs": loudness["floor_lufs"],
        "loudness_silence_pct": round(float(np.mean(loudness["silence_mask"])) * 100, 1),
        # Active-frame stats
        "active_duration_sec": active_duration_sec,
        "silent_duration_sec": total_silence_sec,
        "silence_pct": silence_pct,
        "mean_momentum_active": mean_momentum_active,
        "mean_pattern_lock_active": mean_pattern_lock_active,
        "momentum_range_active": momentum_range_active,
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
    }

    # Count pattern_breaks by type
    pb_types = ["pattern_break", "momentum_drop", "momentum_gain", "silence"]
    pb_counts = {t: sum(1 for pb in pattern_breaks if pb["type"] == t) for t in pb_types}
    summary["pattern_break_counts"] = pb_counts

    report = {
        "track": track_name,
        "duration": round(duration, 1),
        "tempo": round(tempo, 1),
        "silences": silences,
        "silence_reentries": silence_reentries,
        "pattern_breaks": pattern_breaks,
        "summary": summary,
        "stream_hop_sec": round(float(hop_sec), 3),
        "stream_length": len(stream),
    }

    report["stream"] = stream
    return report


def generate_perception_stream(audio_path, output_dir, track_name, hop_sec: float = MOMENTUM_HOP_SEC):
    """Generate a second-by-second perception stream.

    This is the core output: a temporal narrative of what the music
    does to perception as it unfolds through time.

    Thin wrapper: loads audio, calls compute_perception(), saves files,
    generates plots, returns the report dict with embedded stream.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Perceiving {audio_path}...")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)

    print("  Tracking beats...")
    print("  Computing momentum...")
    print("  Computing pattern lock...")
    print("  Computing breath...")
    print("  Detecting silences...")
    print("  Computing harmonic/percussive balance...")

    report = compute_perception(y, sr, track_name, hop_sec=hop_sec)
    stream = report.get("stream", [])
    silences = report.get("silences", [])
    duration = report.get("duration", librosa.get_duration(y=y, sr=sr))

    # Recompute DSP arrays for visualizations
    tempo_val = report.get("tempo", 0)
    _, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times_viz = librosa.frames_to_time(beats, sr=sr)
    m_times, momentum = compute_momentum(beat_times_viz, duration, hop_sec=hop_sec)
    s_times, disruption, d_beat, d_spectral, d_energy = compute_disruption(
        y, sr, beat_times_viz, duration, hop_sec=hop_sec
    )
    b_times, breath = compute_breath(y, sr, duration, hop_sec=hop_sec)
    hp_times, h_energy_viz, p_energy_viz, hp_balance = compute_harmonic_percussive_momentum(
        y, sr, duration, hop_sec=hop_sec
    )

    # Save stream (separate file — it's large)
    stream_path = out / f"{track_name}_stream.json"
    with open(stream_path, "w") as f:
        json.dump(stream, f)
    print(f"  Stream saved: {stream_path} ({len(stream)} entries)")

    # Save report (without stream to keep file manageable)
    report_for_disk = {k: v for k, v in report.items() if k != "stream"}
    report_path = out / f"{track_name}_perception.json"
    with open(report_path, "w") as f:
        json.dump(report_for_disk, f, indent=2)
    print(f"  Perception report saved: {report_path}")

    # ===== VISUALIZATIONS =====
    if m_times is not None and momentum is not None:
        fig_w, fig_h = 16, 3

        # 1. Momentum + Surprise (the listener plot)
        print("  Generating perception plot...")
        fig, axes = plt.subplots(3, 1, figsize=(fig_w, fig_h * 3), sharex=True)

        # Momentum
        axes[0].fill_between(m_times, momentum, alpha=0.4, color="#2ecc71")
        axes[0].plot(m_times, momentum, color="#27ae60", linewidth=1)
        axes[0].set_ylabel("Momentum")
        axes[0].set_ylim(-0.05, 1.05)
        axes[0].set_title(f"{track_name} — Rhythmic Momentum (listener)", fontsize=13)
        for s in silences:
            axes[0].axvspan(s["start"], s["end"], alpha=0.3, color="#e74c3c", label="silence")

        # Pattern Lock (inverted disruption: high = locked in)
        pattern_lock_total = 1.0 - disruption
        pattern_lock_beat = 1.0 - d_beat
        pattern_lock_spectral = 1.0 - d_spectral
        pattern_lock_energy = 1.0 - d_energy
        axes[1].fill_between(s_times, pattern_lock_total, alpha=0.3, color="#2980b9")
        axes[1].plot(s_times, pattern_lock_beat, color="#e67e22", linewidth=0.8, alpha=0.7, label="beat")
        axes[1].plot(s_times, pattern_lock_spectral, color="#9b59b6", linewidth=0.8, alpha=0.7, label="spectral")
        axes[1].plot(s_times, pattern_lock_energy, color="#3498db", linewidth=0.8, alpha=0.7, label="energy")
        axes[1].set_ylabel("Pattern Lock")
        axes[1].set_ylim(-0.05, 1.05)
        axes[1].set_title("Pattern Lock (prediction accuracy)", fontsize=13)
        axes[1].legend(loc="lower right", fontsize=9)

        # Breath
        axes[2].fill_between(b_times, breath, where=breath > 0, alpha=0.4, color="#2ecc71", label="building")
        axes[2].fill_between(b_times, breath, where=breath < 0, alpha=0.4, color="#e74c3c", label="releasing")
        axes[2].axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
        axes[2].set_ylabel("Breath")
        axes[2].set_ylim(-1.05, 1.05)
        axes[2].set_xlabel("Time (s)")
        axes[2].set_title("Breath (heard pressure direction)", fontsize=13)
        axes[2].legend(loc="upper right", fontsize=9)

        plt.tight_layout()
        plt.savefig(out / f"{track_name}_perception.png", dpi=150)
        plt.close()
        print(f"  Perception plot saved.")

        # 2. HP Balance over time
        print("  Generating texture balance plot...")
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

    return report
