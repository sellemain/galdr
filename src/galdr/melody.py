#!/usr/bin/env python3
"""Melodic contour tracking — where the voice/melody goes over time.

Uses pyin for fundamental frequency estimation, then tracks:
- Pitch center: the dominant frequency at each moment
- Contour direction: ascending, descending, or holding
- Pitch range: how wide the melody spans in a window
- Vocal presence: confidence that a pitched signal is present
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

from .constants import (
    PITCH_NAMES,
    MELODY_FMIN, MELODY_FMAX,
    MELODY_DIRECTION_WINDOW_SEC, MELODY_RANGE_WINDOW_SEC,
    MELODY_PRESENCE_WINDOW_SEC, MELODY_DIRECTION_MIN_PRESENCE,
    MELODY_ASCENDING_THRESHOLD, MELODY_DESCENDING_THRESHOLD,
    MOMENTUM_HOP_SEC,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


def hz_to_note_name(hz):
    """Convert frequency in Hz to note name with octave."""
    if hz <= 0 or np.isnan(hz):
        return "?"
    midi = librosa.hz_to_midi(hz)
    note_idx = int(round(midi)) % 12
    octave = int(round(midi)) // 12 - 1
    return f"{PITCH_NAMES[note_idx]}{octave}"


def compute_pitch_contour(y, sr, hop_length=512, fmin=MELODY_FMIN, fmax=MELODY_FMAX):
    """Track fundamental frequency over time using pyin."""
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, sr=sr, hop_length=hop_length,
        fmin=fmin, fmax=fmax,
        fill_na=np.nan
    )

    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)
    return times, f0, voiced_flag, voiced_probs


def compute_contour_direction(f0, times, window_sec=MELODY_DIRECTION_WINDOW_SEC,
                              hop_sec=MOMENTUM_HOP_SEC):
    """Measure whether the melody is ascending, descending, or holding."""
    f0_midi = np.where(np.isnan(f0), np.nan, librosa.hz_to_midi(np.maximum(f0, 1e-6)))

    out_times = np.arange(0, times[-1] if len(times) > 0 else 0, hop_sec)
    direction = np.zeros_like(out_times)

    for i, t in enumerate(out_times):
        mask = (times >= t - window_sec / 2) & (times < t + window_sec / 2)
        window_midi = f0_midi[mask]
        window_times = times[mask]

        valid = ~np.isnan(window_midi)
        if np.sum(valid) < 3:
            direction[i] = 0.0
            continue

        x = window_times[valid] - t
        y = window_midi[valid]
        slope = np.polyfit(x, y, 1)[0]

        direction[i] = float(slope)

    return out_times, direction


def compute_pitch_range(f0, times, window_sec=MELODY_RANGE_WINDOW_SEC,
                        hop_sec=MOMENTUM_HOP_SEC):
    """Measure the pitch range (in semitones) within sliding windows."""
    f0_midi = np.where(np.isnan(f0), np.nan, librosa.hz_to_midi(np.maximum(f0, 1e-6)))

    out_times = np.arange(0, times[-1] if len(times) > 0 else 0, hop_sec)
    pitch_range = np.zeros_like(out_times)
    pitch_center = np.full_like(out_times, np.nan)

    for i, t in enumerate(out_times):
        mask = (times >= t - window_sec / 2) & (times < t + window_sec / 2)
        window_midi = f0_midi[mask]
        valid = window_midi[~np.isnan(window_midi)]

        if len(valid) < 2:
            pitch_range[i] = 0.0
            continue

        pitch_range[i] = float(np.max(valid) - np.min(valid))
        pitch_center[i] = float(np.median(valid))

    return out_times, pitch_range, pitch_center


def compute_vocal_presence(voiced_probs, times,
                           window_sec=MELODY_PRESENCE_WINDOW_SEC,
                           hop_sec=MOMENTUM_HOP_SEC):
    """Rolling measure of how much pitched content is present."""
    out_times = np.arange(0, times[-1] if len(times) > 0 else 0, hop_sec)
    presence = np.zeros_like(out_times)

    for i, t in enumerate(out_times):
        mask = (times >= t - window_sec / 2) & (times < t + window_sec / 2)
        window_probs = voiced_probs[mask]
        if len(window_probs) == 0:
            presence[i] = 0.0
        else:
            presence[i] = float(np.mean(window_probs))

    return out_times, presence


def analyze_melody(audio_path, output_dir, track_name,
                    hop_sec=MOMENTUM_HOP_SEC, use_harmonic=True):
    """Full melodic contour analysis.

    Returns (summary_dict, stream_list).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing melody: {audio_path}...")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    if use_harmonic:
        print("  Separating harmonic component...")
        y_analysis, _ = librosa.effects.hpss(y)
    else:
        y_analysis = y

    hop_length = 512

    print("  Tracking pitch (pyin)...")
    pitch_times, f0, voiced, voiced_probs = compute_pitch_contour(
        y_analysis, sr, hop_length=hop_length
    )

    print("  Computing contour direction...")
    dir_times, direction = compute_contour_direction(f0, pitch_times, hop_sec=hop_sec)

    print("  Computing pitch range...")
    range_times, pitch_range, pitch_center = compute_pitch_range(f0, pitch_times, hop_sec=hop_sec)

    print("  Computing vocal presence...")
    pres_times, vocal_presence = compute_vocal_presence(voiced_probs, pitch_times, hop_sec=hop_sec)

    # ===== BUILD MELODY STREAM =====
    stream_times = np.arange(0, duration, hop_sec)
    stream = []

    direction_interp = np.interp(stream_times, dir_times, direction) if len(dir_times) > 0 else np.zeros_like(stream_times)
    range_interp = np.interp(stream_times, range_times, pitch_range) if len(range_times) > 0 else np.zeros_like(stream_times)
    if len(range_times) > 0:
        valid_center = ~np.isnan(pitch_center)
        if np.any(valid_center):
            center_interp = np.interp(stream_times, range_times[valid_center], pitch_center[valid_center])
        else:
            center_interp = np.full_like(stream_times, np.nan)
    else:
        center_interp = np.full_like(stream_times, np.nan)
    presence_interp = np.interp(stream_times, pres_times, vocal_presence) if len(pres_times) > 0 else np.zeros_like(stream_times)

    # Interpolate voiced probability to stream times for unvoiced frame detection
    voiced_interp = np.interp(stream_times, pitch_times, voiced_probs) if len(pitch_times) > 0 else np.zeros_like(stream_times)

    for i, t in enumerate(stream_times):
        pitch_idx = np.searchsorted(pitch_times, t, side="right") - 1
        pitch_idx = max(0, min(pitch_idx, len(f0) - 1))
        current_f0 = float(f0[pitch_idx]) if not np.isnan(f0[pitch_idx]) else None
        current_note = hz_to_note_name(current_f0) if current_f0 else None

        is_voiced = voiced_interp[i] > 0.5

        entry = {
            "t": round(float(t), 1),
            "f0_hz": round(current_f0, 1) if current_f0 and is_voiced else None,
            "note": current_note if is_voiced else None,
            "direction": round(float(direction_interp[i]), 3) if is_voiced else None,
            "pitch_range_st": round(float(range_interp[i]), 1),
            "pitch_center_midi": round(float(center_interp[i]), 1) if is_voiced and not np.isnan(center_interp[i]) else None,
            "vocal_presence": round(float(presence_interp[i]), 3),
        }
        stream.append(entry)

    # ===== SUMMARY =====
    valid_f0 = f0[~np.isnan(f0)]
    if len(valid_f0) > 0:
        overall_range_st = float(librosa.hz_to_midi(np.max(valid_f0)) - librosa.hz_to_midi(np.min(valid_f0)))
        overall_center_hz = float(np.median(valid_f0))
        overall_center_note = hz_to_note_name(overall_center_hz)
        overall_low = hz_to_note_name(float(np.min(valid_f0)))
        overall_high = hz_to_note_name(float(np.max(valid_f0)))
    else:
        overall_range_st = 0
        overall_center_hz = 0
        overall_center_note = "?"
        overall_low = "?"
        overall_high = "?"

    voiced_direction = direction_interp[presence_interp > MELODY_DIRECTION_MIN_PRESENCE]
    if len(voiced_direction) > 0:
        pct_ascending = float(np.mean(voiced_direction > MELODY_ASCENDING_THRESHOLD)) * 100
        pct_descending = float(np.mean(voiced_direction < MELODY_DESCENDING_THRESHOLD)) * 100
        pct_holding = 100.0 - pct_ascending - pct_descending
    else:
        pct_ascending = pct_descending = pct_holding = 0

    summary = {
        "track": track_name,
        "duration": round(duration, 1),
        "overall_range_semitones": round(overall_range_st, 1),
        "overall_center_hz": round(overall_center_hz, 1),
        "overall_center_note": overall_center_note,
        "range_low": overall_low,
        "range_high": overall_high,
        "mean_vocal_presence": round(float(np.mean(vocal_presence)), 3),
        "contour_ascending_pct": round(pct_ascending, 1),
        "contour_descending_pct": round(pct_descending, 1),
        "contour_holding_pct": round(pct_holding, 1),
        "mean_direction": round(float(np.mean(direction)), 3),
        "stream_length": len(stream),
    }

    # ===== SAVE =====
    stream_path = out / f"{track_name}_melody_stream.json"
    with open(stream_path, "w") as f:
        json.dump(stream, f)
    print(f"  Melody stream saved: {stream_path} ({len(stream)} entries)")

    summary_path = out / f"{track_name}_melody.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Melody summary saved: {summary_path}")

    # ===== VISUALIZATION =====
    print("  Generating melody plot...")
    fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=True)

    valid_mask = ~np.isnan(f0)
    f0_midi_plot = np.where(valid_mask, librosa.hz_to_midi(np.maximum(f0, 1e-6)), np.nan)
    axes[0].scatter(pitch_times[valid_mask], f0_midi_plot[valid_mask],
                    s=1, c="#2ecc71", alpha=0.5)
    axes[0].set_ylabel("Pitch (MIDI)")
    axes[0].set_title(f"{track_name} — Melodic Contour", fontsize=13)

    axes[1].fill_between(dir_times, direction, where=direction > 0,
                         alpha=0.4, color="#e67e22", label="ascending")
    axes[1].fill_between(dir_times, direction, where=direction < 0,
                         alpha=0.4, color="#3498db", label="descending")
    axes[1].axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
    axes[1].set_ylabel("Direction (st/s)")
    axes[1].set_ylim(-10, 10)
    axes[1].legend(loc="upper right", fontsize=9)

    axes[2].plot(range_times, pitch_range, color="#9b59b6", linewidth=1)
    axes[2].fill_between(range_times, pitch_range, alpha=0.3, color="#9b59b6")
    axes[2].set_ylabel("Range (semitones)")

    axes[3].fill_between(pres_times, vocal_presence, alpha=0.4, color="#2ecc71")
    axes[3].set_ylabel("Vocal Presence")
    axes[3].set_xlabel("Time (s)")
    axes[3].set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(out / f"{track_name}_melody.png", dpi=150)
    plt.close()
    print(f"  Melody plot saved.")

    summary["stream"] = stream
    return summary
