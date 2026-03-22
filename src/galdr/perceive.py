#!/usr/bin/env python3
"""Perception layer — what the music DOES to the listener.

Concepts:
- Momentum: a rolling measure of rhythmic consistency. High = the listener
  is locked in, tracking confidently.
- Surprise: where expectations break. A beat that should land and doesn't.
- Breath: the rate of energy change. Building, sustaining, releasing.
- Silence: not just low energy. Actual nothing.
"""

import json
import warnings
from pathlib import Path

import librosa
import librosa.display
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import uniform_filter1d

from .constants import (
    MOMENTUM_WINDOW_SEC, MOMENTUM_HOP_SEC, MOMENTUM_MIN_BEATS,
    DISRUPTION_WEIGHT_BEAT, DISRUPTION_WEIGHT_SPECTRAL, DISRUPTION_WEIGHT_ENERGY,
    DISRUPTION_BEAT_LOOKBACK_SEC, DISRUPTION_BEAT_ABSENCE_THRESHOLD_SEC,
    DISRUPTION_BEAT_ABSENCE_MAX_SEC, DISRUPTION_SPECTRAL_SMOOTH_FRAMES,
    DISRUPTION_ENERGY_SMOOTH_FRAMES,
    BREATH_SMOOTH_FRAMES,
    SILENCE_THRESHOLD_DB, SILENCE_MIN_DURATION_SEC,
    HP_BALANCE_MIN_ENERGY, HP_SMOOTH_FRAMES,
    EVENT_MOMENTUM_LOCKED, EVENT_MOMENTUM_FLOATING,
    EVENT_DISRUPTION_BREAK, EVENT_BREATH_BUILDING, EVENT_BREATH_RELEASING,
    PATTERN_BREAK_MIN_DISRUPTION, MOMENTUM_SHIFT_THRESHOLD, TOP_DISRUPTION_COUNT,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


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

    if spectral_flux.max() > 0:
        spectral_flux_norm = spectral_flux / spectral_flux.max()
    else:
        spectral_flux_norm = spectral_flux

    local_avg = uniform_filter1d(spectral_flux_norm, size=DISRUPTION_SPECTRAL_SMOOTH_FRAMES)
    spectral_disruption_raw = np.maximum(0, spectral_flux_norm - local_avg)
    disruption_spectral = np.interp(times, flux_times, spectral_disruption_raw)

    # --- Energy disruption ---
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    if len(rms) > 1:
        energy_diff = np.abs(np.diff(rms))
        energy_diff = np.append(energy_diff, 0)
        local_trend = uniform_filter1d(energy_diff, size=DISRUPTION_ENERGY_SMOOTH_FRAMES)
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


def compute_breath(y, sr, duration, hop_sec=MOMENTUM_HOP_SEC):
    """The rate of energy change — building, sustaining, or releasing.

    Returns (times, breath) where:
    - Positive = building (energy increasing)
    - Zero = sustaining (stable)
    - Negative = releasing (energy decreasing)
    """
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    smoothed = uniform_filter1d(rms, size=BREATH_SMOOTH_FRAMES)

    if len(smoothed) > 1:
        breath_raw = np.gradient(smoothed)
        max_abs = np.max(np.abs(breath_raw))
        if max_abs > 0:
            breath_raw = breath_raw / max_abs
    else:
        breath_raw = np.zeros_like(smoothed)

    times = np.arange(0, duration, hop_sec)
    breath = np.interp(times, rms_times, breath_raw)

    return times, breath


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

    rms_h_smooth = uniform_filter1d(rms_h, size=HP_SMOOTH_FRAMES)
    rms_p_smooth = uniform_filter1d(rms_p, size=HP_SMOOTH_FRAMES)

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


def generate_perception_stream(audio_path, output_dir, track_name):
    """Generate a second-by-second perception stream.

    This is the core output: a temporal narrative of what the music
    does to perception as it unfolds through time.

    Returns (report_dict, stream_list) where report_dict contains
    summary statistics and stream_list is the per-timestep data.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Perceiving {audio_path}...")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    if duration <= 0:
        raise ValueError("Audio too short to analyze")

    # Beat tracking
    print("  Tracking beats...")
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0]) if len(tempo) > 0 else 0.0

    # RMS energy (for context)
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    # Compute perception dimensions
    print("  Computing momentum...")
    m_times, momentum = compute_momentum(beat_times, duration)

    print("  Computing pattern lock...")
    s_times, disruption, d_beat, d_spectral, d_energy = compute_disruption(
        y, sr, beat_times, duration
    )

    print("  Computing breath...")
    b_times, breath = compute_breath(y, sr, duration)

    print("  Detecting silences...")
    silences = detect_silences(y, sr)

    print("  Computing harmonic/percussive balance...")
    hp_times, h_energy, p_energy, hp_balance = compute_harmonic_percussive_momentum(
        y, sr, duration
    )

    # Energy interpolated to our time grid
    energy = np.interp(m_times, rms_times, rms)

    # ===== BUILD PERCEPTION STREAM =====
    stream = []
    for i, t in enumerate(m_times):
        entry = {
            "t": round(float(t), 1),
            "energy": round(float(energy[i]), 4),
            "momentum": round(float(momentum[i]), 3),
            "pattern_lock": round(1.0 - float(disruption[i]), 3),
            "breath": round(float(breath[i]), 3),
            "hp_balance": round(float(hp_balance[i]), 3),
            "h_energy": round(float(h_energy[i]), 4),
            "p_energy": round(float(p_energy[i]), 4),
        }

        # Mark if we're in a silence
        for s in silences:
            if s["start"] <= t <= s["end"]:
                entry["silence"] = True
                entry["silence_depth_db"] = s["depth_db"]
                break

        # Narrative flags (for experience write-ups)
        if momentum[i] > EVENT_MOMENTUM_LOCKED and (i == 0 or momentum[i-1] <= EVENT_MOMENTUM_LOCKED):
            entry["event"] = "listener_locked"
        elif momentum[i] < EVENT_MOMENTUM_FLOATING and i > 0 and momentum[i-1] >= EVENT_MOMENTUM_FLOATING:
            entry["event"] = "listener_floating"
        elif disruption[i] > EVENT_DISRUPTION_BREAK:
            entry["event"] = "pattern_break"
        elif breath[i] > EVENT_BREATH_BUILDING and (i == 0 or breath[i-1] <= EVENT_BREATH_BUILDING):
            entry["event"] = "building"
        elif breath[i] < EVENT_BREATH_RELEASING and (i == 0 or breath[i-1] >= EVENT_BREATH_RELEASING):
            entry["event"] = "releasing"

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
        pattern_breaks.append({
            "time": s["start"],
            "type": "silence",
            "duration": s["duration"],
            "depth_db": s["depth_db"],
        })

    # Sort pattern breaks chronologically
    pattern_breaks.sort(key=lambda m: m["time"])

    # ===== PERCEPTION REPORT =====
    report = {
        "track": track_name,
        "duration": round(duration, 1),
        "tempo": round(tempo, 1),
        "silences": silences,
        "pattern_breaks": pattern_breaks,
        "summary": {
            "mean_momentum": round(float(np.mean(momentum)), 3),
            "mean_pattern_lock": round(1.0 - float(np.mean(disruption)), 3),
            "momentum_range": [round(float(np.min(momentum)), 3), round(float(np.max(momentum)), 3)],
            "total_silence_sec": round(sum(s["duration"] for s in silences), 1),
            "pattern_break_count": len(pattern_breaks),
            "breath_positive_pct": round(float(np.mean(breath > 0.05)) * 100, 1),
            "breath_negative_pct": round(float(np.mean(breath < -0.05)) * 100, 1),
            "breath_sustain_pct": round(float(np.mean(np.abs(breath) <= 0.05)) * 100, 1),
        },
        "stream_hop_sec": 0.5,
        "stream_length": len(stream),
    }

    # Save stream (separate file — it's large)
    stream_path = out / f"{track_name}_stream.json"
    with open(stream_path, "w") as f:
        json.dump(stream, f)
    print(f"  Stream saved: {stream_path} ({len(stream)} entries)")

    # Save report
    report_path = out / f"{track_name}_perception.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Perception report saved: {report_path}")

    # ===== VISUALIZATIONS =====
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
    # Mark silences
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
    axes[2].set_title("Breath (energy direction)", fontsize=13)
    axes[2].legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    plt.savefig(out / f"{track_name}_perception.png", dpi=150)
    plt.close()
    print(f"  Perception plot saved.")

    # 2. HP Balance over time
    print("  Generating HP balance plot...")
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

    return report, stream
