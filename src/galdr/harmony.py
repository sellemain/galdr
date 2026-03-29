#!/usr/bin/env python3
"""Harmonic function analysis — what the music means harmonically over time.

Tracks:
- Consonance/dissonance: how settled or tense the harmony is (dual measure)
- Chroma flux: rate of harmonic change (replaces chord-based harmonic rhythm)
- Tonal center stability: does the key drift or hold (Krumhansl-Kessler profiles)
- Tension arc: distance from perceived tonic over time
- Major/minor balance: is the current passage in a major or minor context

Does NOT track named chords. Chord labels (F major, Am, etc.) are analytical
constructs that listeners don't perceive directly. This module measures the
harmonic qualities that listeners actually feel: tension, consonance,
stability, and the rate of harmonic change.
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
    PITCH_NAMES,
    KK_MAJOR_PROFILE, KK_MINOR_PROFILE,
    CHROMA_SMOOTH_FRAMES,
    JI_CONSONANCE,
    CONSONANCE_MIN_ENERGY, CONSONANCE_ACTIVE_THRESHOLD,
    TONAL_CENTER_WINDOW_FRAMES, TONAL_CENTER_MIN_ENERGY,
    TENSION_SMOOTH_FRAMES, TENSION_VELOCITY_SMOOTH,
    CHROMA_FLUX_WINDOW_SEC, CHROMA_FLUX_HOP_SEC,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ============================================================
# Key Detection — Krumhansl-Kessler
# ============================================================

def _build_kk_profiles():
    """Build all 24 key profiles (12 major + 12 minor) by rotating
    the Krumhansl-Kessler template profiles.

    Returns dict mapping key name (e.g. 'C major', 'A minor') to
    (root_index, mode, profile_array).
    """
    profiles = {}
    major = np.array(KK_MAJOR_PROFILE)
    minor = np.array(KK_MINOR_PROFILE)

    for root in range(12):
        name = PITCH_NAMES[root]
        # Rotate profile so index 0 = the root pitch class
        maj_rotated = np.roll(major, root)
        min_rotated = np.roll(minor, root)

        profiles[f"{name} major"] = (root, "major", maj_rotated)
        profiles[f"{name}m"] = (root, "minor", min_rotated)

    return profiles


KK_PROFILES = _build_kk_profiles()


def detect_key_kk(chroma_profile):
    """Detect key from a chroma distribution using Krumhansl-Kessler profiles.

    Args:
        chroma_profile: 12-element array of pitch class energies.

    Returns:
        (key_name, mode, root_index, confidence) where confidence is the
        Pearson correlation with the best-matching profile.
    """
    total = np.sum(chroma_profile)
    if total < TONAL_CENTER_MIN_ENERGY:
        return "?", "?", 0, 0.0

    best_corr = -2.0
    best_key = "?"
    best_mode = "?"
    best_root = 0

    for key_name, (root, mode, profile) in KK_PROFILES.items():
        corr = float(np.corrcoef(chroma_profile, profile)[0, 1])
        if corr > best_corr:
            best_corr = corr
            best_key = key_name
            best_mode = mode
            best_root = root

    return best_key, best_mode, best_root, round(max(0.0, best_corr), 4)


# ============================================================
# Consonance
# ============================================================

def compute_consonance(chroma, sr, hop_length=512, smooth_frames=CHROMA_SMOOTH_FRAMES):
    """Measure harmonic consonance over time — TWO measures.

    1. Temperament consonance: chroma entropy — how concentrated the
       pitch energy is. High = few pitch classes active (consonant).
    2. Harmonic series consonance: do active pitch classes form
       relationships consistent with the natural harmonic series?

    Returns (times, consonance_temperament, consonance_series).
    """
    chroma_smooth = uniform_filter1d(chroma, size=smooth_frames, axis=1)
    n_frames = chroma_smooth.shape[1]
    consonance_temp = np.zeros(n_frames)
    consonance_series = np.zeros(n_frames)

    for i in range(n_frames):
        frame = chroma_smooth[:, i]
        total = np.sum(frame)
        if total < CONSONANCE_MIN_ENERGY:
            consonance_temp[i] = 0.0
            consonance_series[i] = 0.0
            continue

        # --- Temperament consonance (entropy-based) ---
        p = frame / total
        entropy = -np.sum(p * np.log2(p + 1e-10))
        max_entropy = np.log2(12)
        consonance_temp[i] = max(0, 1.0 - entropy / max_entropy)

        # --- Harmonic series consonance ---
        threshold = CONSONANCE_ACTIVE_THRESHOLD * np.max(frame)
        active = np.where(frame > threshold)[0]

        if len(active) < 2:
            consonance_series[i] = 1.0 if len(active) == 1 else 0.0
            continue

        pair_scores = []
        pair_weights = []
        for a_idx in range(len(active)):
            for b_idx in range(a_idx + 1, len(active)):
                a, b = active[a_idx], active[b_idx]
                interval = (b - a) % 12
                score = JI_CONSONANCE.get(interval, 0.25)
                weight = frame[a] * frame[b]
                pair_scores.append(score)
                pair_weights.append(weight)

        if pair_weights:
            total_weight = sum(pair_weights)
            if total_weight > 0:
                consonance_series[i] = sum(
                    s * w for s, w in zip(pair_scores, pair_weights)
                ) / total_weight
            else:
                consonance_series[i] = 0.0
        else:
            consonance_series[i] = 0.0

    times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)
    return times, consonance_temp, consonance_series


# ============================================================
# Chroma Flux — rate of harmonic change
# ============================================================

def compute_chroma_flux(chroma, sr, hop_length=512,
                        smooth_frames=CHROMA_SMOOTH_FRAMES,
                        window_sec=CHROMA_FLUX_WINDOW_SEC,
                        hop_sec=CHROMA_FLUX_HOP_SEC):
    """Measure rate of harmonic change over time using chroma cosine distance.

    Instead of counting chord label transitions (which requires naming chords),
    this measures how quickly the pitch-class distribution is changing. High
    values = rapid harmonic movement. Low values = harmonic stasis.

    Returns (times, chroma_flux) where chroma_flux is 0-1 normalized.
    """
    chroma_smooth = uniform_filter1d(chroma, size=smooth_frames, axis=1)
    n_frames = chroma_smooth.shape[1]
    frame_times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)

    # Frame-level cosine distance between adjacent chroma vectors
    frame_flux = np.zeros(n_frames)
    for i in range(1, n_frames):
        a = chroma_smooth[:, i - 1]
        b = chroma_smooth[:, i]
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a > 1e-6 and norm_b > 1e-6:
            cos_sim = np.dot(a, b) / (norm_a * norm_b)
            frame_flux[i] = max(0.0, 1.0 - cos_sim)
        else:
            frame_flux[i] = 0.0

    # Compute windowed average flux rate
    duration = frame_times[-1] if len(frame_times) > 0 else 0
    out_times = np.arange(0, duration, hop_sec)
    flux_rate = np.zeros_like(out_times)

    for i, t in enumerate(out_times):
        mask = (frame_times >= t - window_sec / 2) & (frame_times < t + window_sec / 2)
        window_flux = frame_flux[mask]
        if len(window_flux) > 0:
            flux_rate[i] = float(np.mean(window_flux))

    # Normalize to 0-1
    max_flux = np.max(flux_rate)
    if max_flux > 0:
        flux_rate = flux_rate / max_flux

    return out_times, flux_rate


# ============================================================
# Tonal Center — Krumhansl-Kessler key tracking
# ============================================================

def compute_tonal_center(chroma, sr, hop_length=512,
                         window_frames=TONAL_CENTER_WINDOW_FRAMES):
    """Track the tonal center (key) over time using KK profile correlation.

    Returns (times, key_names, modes, stability, major_minor, confidence).
    """
    n_frames = chroma.shape[1]
    hop_windows = max(1, window_frames // 2)
    n_windows = max(1, (n_frames - window_frames) // hop_windows + 1)

    times = np.zeros(n_windows)
    key_names = []
    modes = []
    stability = np.zeros(n_windows)
    major_minor = np.zeros(n_windows)
    confidence = np.zeros(n_windows)

    for i in range(n_windows):
        start = i * hop_windows
        end = min(start + window_frames, n_frames)
        window = chroma[:, start:end]

        profile = np.mean(window, axis=1)
        total = np.sum(profile)
        ts_frame = min(start + window_frames // 2, n_frames - 1)
        times[i] = librosa.frames_to_time(ts_frame, sr=sr, hop_length=hop_length)

        if total < TONAL_CENTER_MIN_ENERGY:
            key_names.append("?")
            modes.append("?")
            stability[i] = 0.0
            major_minor[i] = 0.0
            confidence[i] = 0.0
            continue

        # KK key detection
        key_name, mode, root, corr = detect_key_kk(profile)
        key_names.append(key_name)
        modes.append(mode)
        confidence[i] = corr

        # Stability: how dominant is the tonic pitch class
        profile_norm = profile / total
        stability[i] = float(profile_norm[root])

        # Major/minor balance from the chroma profile directly
        major_third = profile_norm[(root + 4) % 12]
        minor_third = profile_norm[(root + 3) % 12]
        major_minor[i] = float(major_third - minor_third)

    return times, key_names, modes, stability, major_minor, confidence


# ============================================================
# Tension
# ============================================================

def compute_tension(chroma, sr, hop_length=512,
                    smooth_frames=TENSION_SMOOTH_FRAMES):
    """Track harmonic tension — rate of movement in tonnetz space.

    Uses tonnetz features for a geometrically meaningful representation
    of harmonic relationships. Higher velocity = more harmonic tension.

    Returns (times, tension, tonnetz_features).
    """
    tonnetz = librosa.feature.tonnetz(chroma=chroma, sr=sr)
    tonnetz_smooth = uniform_filter1d(tonnetz, size=smooth_frames, axis=1)

    if tonnetz_smooth.shape[1] > 1:
        tonnetz_diff = np.diff(tonnetz_smooth, axis=1)
        tonnetz_velocity = np.sqrt(np.sum(tonnetz_diff ** 2, axis=0))
        tonnetz_velocity = np.append(tonnetz_velocity, 0)
    else:
        tonnetz_velocity = np.zeros(tonnetz_smooth.shape[1])

    tension_raw = uniform_filter1d(tonnetz_velocity, size=TENSION_VELOCITY_SMOOTH)

    if tension_raw.max() > 0:
        tension = tension_raw / tension_raw.max()
    else:
        tension = tension_raw

    times = librosa.frames_to_time(np.arange(len(tension)), sr=sr, hop_length=hop_length)
    return times, tension, tonnetz_smooth


# ============================================================
# Full Pipeline
# ============================================================

def analyze_harmony(audio_path, output_dir, track_name, hop_sec=0.5):
    """Full harmonic analysis pipeline.

    Returns (summary_dict, stream_list).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing harmony: {audio_path}...")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    hop_length = 512

    print("  Computing chroma (CQT)...")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)

    print("  Computing consonance (temperament + series)...")
    cons_times, consonance_temp, consonance_series = compute_consonance(
        chroma, sr, hop_length=hop_length
    )

    print("  Computing chroma flux (harmonic change rate)...")
    cf_times, chroma_flux = compute_chroma_flux(
        chroma, sr, hop_length=hop_length
    )

    print("  Tracking tonal center (Krumhansl-Kessler)...")
    tc_times, tc_key_names, tc_modes, tc_stability, tc_major_minor, tc_confidence = (
        compute_tonal_center(chroma, sr, hop_length=hop_length)
    )

    print("  Computing tension arc...")
    tens_times, tension, tonnetz = compute_tension(
        chroma, sr, hop_length=hop_length
    )

    # ===== BUILD HARMONIC STREAM =====
    stream_times = np.arange(0, duration, hop_sec)
    stream = []

    consonance_interp = np.interp(stream_times, cons_times, consonance_temp)
    consonance_series_interp = np.interp(stream_times, cons_times, consonance_series)
    tension_interp = np.interp(stream_times, tens_times, tension)
    chroma_flux_interp = np.interp(stream_times, cf_times, chroma_flux)
    tc_stability_interp = np.interp(stream_times, tc_times, tc_stability)
    tc_mm_interp = np.interp(stream_times, tc_times, tc_major_minor)
    tc_confidence_interp = np.interp(stream_times, tc_times, tc_confidence)

    for i, t in enumerate(stream_times):
        # Find nearest tonal center window
        tc_idx = np.searchsorted(tc_times, t, side="right") - 1
        tc_idx = max(0, min(tc_idx, len(tc_key_names) - 1))
        tonal_center = tc_key_names[tc_idx] if tc_idx < len(tc_key_names) else "?"

        entry = {
            "t": round(float(t), 1),
            "temperament_alignment": round(float(consonance_interp[i]), 3),
            "consonance_series": round(float(consonance_series_interp[i]), 3),
            "tension": round(float(tension_interp[i]), 3),
            "chroma_flux": round(float(chroma_flux_interp[i]), 3),
            "tonal_center": tonal_center,
            "tonal_stability": round(float(tc_stability_interp[i]), 3),
            "key_confidence": round(float(tc_confidence_interp[i]), 3),
            "major_minor": round(float(tc_mm_interp[i]), 3),
        }
        stream.append(entry)

    # ===== OVERALL KEY DETECTION =====
    # Use the full-track chroma profile for global key
    overall_profile = np.mean(chroma, axis=1)
    global_key, global_mode, _, global_confidence = detect_key_kk(overall_profile)

    # ===== SUMMARY =====
    summary = {
        "track": track_name,
        "duration": round(duration, 1),
        "detected_key": global_key,
        "detected_mode": global_mode,
        "key_confidence": global_confidence,
        "mean_temperament_alignment": round(float(np.mean(consonance_temp)), 3),
        "mean_consonance_series": round(float(np.mean(consonance_series)), 3),
        "mean_tension": round(float(np.mean(tension)), 3),
        "mean_chroma_flux": round(float(np.mean(chroma_flux)), 3),
        "mean_tonal_stability": round(float(np.mean(tc_stability)), 3),
        "mean_major_minor": round(float(np.mean(tc_major_minor)), 3),
        "temperament_alignment_range": [
            round(float(np.min(consonance_temp)), 3),
            round(float(np.max(consonance_temp)), 3),
        ],
        "consonance_series_range": [
            round(float(np.min(consonance_series)), 3),
            round(float(np.max(consonance_series)), 3),
        ],
        "tension_range": [
            round(float(np.min(tension)), 3),
            round(float(np.max(tension)), 3),
        ],
        "chroma_flux_range": [
            round(float(np.min(chroma_flux)), 3),
            round(float(np.max(chroma_flux)), 3),
        ],
        "stream_length": len(stream),
    }

    # ===== SAVE =====
    stream_path = out / f"{track_name}_harmony_stream.json"
    with open(stream_path, "w") as f:
        json.dump(stream, f)
    print(f"  Harmony stream saved: {stream_path} ({len(stream)} entries)")

    summary_path = out / f"{track_name}_harmony.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Harmony summary saved: {summary_path}")

    # ===== VISUALIZATION =====
    print("  Generating harmony plot...")
    fig, axes = plt.subplots(5, 1, figsize=(16, 15), sharex=True)

    # Consonance (both measures)
    axes[0].plot(cons_times, consonance_temp, color="#2ecc71", linewidth=1,
                 label="temperament alignment", alpha=0.8)
    axes[0].fill_between(cons_times, consonance_temp, alpha=0.2, color="#2ecc71")
    axes[0].plot(cons_times, consonance_series, color="#3498db", linewidth=1,
                 label="series (JI)", alpha=0.8)
    axes[0].fill_between(cons_times, consonance_series, alpha=0.2, color="#3498db")
    axes[0].set_ylabel("Alignment / Consonance")
    axes[0].set_ylim(0, 1)
    axes[0].set_title(
        f"{track_name} — Harmonic Function "
        f"(key: {global_key}, confidence: {global_confidence})",
        fontsize=13,
    )
    axes[0].legend(loc="upper right", fontsize=9)

    # Tension
    axes[1].plot(tens_times, tension, color="#e74c3c", linewidth=1)
    axes[1].fill_between(tens_times, tension, alpha=0.3, color="#e74c3c")
    axes[1].set_ylabel("Tension")
    axes[1].set_ylim(0, 1)

    # Chroma flux
    axes[2].plot(cf_times, chroma_flux, color="#e67e22", linewidth=1)
    axes[2].fill_between(cf_times, chroma_flux, alpha=0.3, color="#e67e22")
    axes[2].set_ylabel("Chroma Flux")
    axes[2].set_ylim(0, 1)
    axes[2].set_title("Harmonic Change Rate (chroma cosine distance)", fontsize=11)

    # Major/minor balance
    axes[3].fill_between(tc_times, tc_major_minor,
                         where=np.array(tc_major_minor) > 0,
                         alpha=0.4, color="#f39c12", label="major")
    axes[3].fill_between(tc_times, tc_major_minor,
                         where=np.array(tc_major_minor) < 0,
                         alpha=0.4, color="#8e44ad", label="minor")
    axes[3].axhline(y=0, color="#7f8c8d", linewidth=0.5, linestyle="--")
    axes[3].set_ylabel("<- minor | major ->")
    axes[3].set_ylim(-0.3, 0.3)
    axes[3].legend(loc="upper right", fontsize=9)

    # Tonal stability + key confidence
    axes[4].plot(tc_times, tc_stability, color="#3498db", linewidth=1,
                 label="tonal stability")
    axes[4].fill_between(tc_times, tc_stability, alpha=0.2, color="#3498db")
    axes[4].plot(tc_times, tc_confidence, color="#2ecc71", linewidth=1,
                 alpha=0.7, label="key confidence")
    axes[4].set_ylabel("Stability / Confidence")
    axes[4].set_xlabel("Time (s)")
    axes[4].set_ylim(0, 1)
    axes[4].legend(loc="upper right", fontsize=9)

    plt.tight_layout()
    plt.savefig(out / f"{track_name}_harmony.png", dpi=150)
    plt.close()
    print(f"  Harmony plot saved.")

    summary["stream"] = stream
    return summary
