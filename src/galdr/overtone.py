#!/usr/bin/env python3
"""Overtone analysis — the harmonic series made visible.

Tracks which overtones are present in a signal and how they change over time.

Two kinds of consonance:
1. Temperament consonance (harmony.py): does this fit major/minor/dim templates?
2. Harmonic series consonance (this module): are these frequencies integer
   multiples of a common fundamental?
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
from scipy.signal import find_peaks

from .constants import (
    OVERTONE_MAX_HARMONIC, OVERTONE_TOLERANCE_CENTS,
    OVERTONE_FMIN, OVERTONE_FMAX,
    OVERTONE_N_PEAKS, OVERTONE_MIN_HEIGHT_DB,
    OVERTONE_PEAK_DISTANCE, OVERTONE_PEAK_PROMINENCE,
    OVERTONE_N_FFT, OVERTONE_FREQ_CEILING,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


def hz_to_cents(f1, f2):
    """Difference between two frequencies in cents."""
    if f1 <= 0 or f2 <= 0:
        return float("inf")
    return 1200.0 * np.log2(f2 / f1)


def find_spectral_peaks(spectrum, freqs, n_peaks=OVERTONE_N_PEAKS,
                        min_height_db=OVERTONE_MIN_HEIGHT_DB):
    """Find prominent peaks in a magnitude spectrum."""
    spectrum_db = librosa.amplitude_to_db(spectrum, ref=np.max(spectrum))

    peaks, properties = find_peaks(
        spectrum_db,
        height=min_height_db,
        distance=OVERTONE_PEAK_DISTANCE,
        prominence=OVERTONE_PEAK_PROMINENCE,
    )

    if len(peaks) == 0:
        return np.array([]), np.array([])

    peak_freqs = freqs[peaks]
    peak_mags = spectrum[peaks]

    sort_idx = np.argsort(-peak_mags)[:n_peaks]
    return peak_freqs[sort_idx], peak_mags[sort_idx]


def match_harmonics(f0, peak_freqs, peak_mags,
                    max_harmonic=OVERTONE_MAX_HARMONIC,
                    tolerance_cents=OVERTONE_TOLERANCE_CENTS):
    """Given a fundamental f0, find which harmonics are present in the peaks."""
    if f0 <= 0 or len(peak_freqs) == 0:
        return {}, 0.0, 0.0, 0.0

    harmonics = {}
    deviations = []

    for n in range(1, max_harmonic + 1):
        ideal_freq = f0 * n

        if ideal_freq > OVERTONE_FREQ_CEILING:
            break

        if len(peak_freqs) == 0:
            continue

        distances_cents = np.abs(np.array([hz_to_cents(ideal_freq, pf) for pf in peak_freqs]))
        closest_idx = np.argmin(distances_cents)
        closest_cents = distances_cents[closest_idx]

        if closest_cents <= tolerance_cents:
            harmonics[n] = {
                "freq": round(float(peak_freqs[closest_idx]), 1),
                "ideal_freq": round(float(ideal_freq), 1),
                "magnitude": round(float(peak_mags[closest_idx]), 6),
                "deviation_cents": round(float(closest_cents), 1),
            }
            deviations.append(closest_cents)

    max_possible = min(max_harmonic, int(OVERTONE_FREQ_CEILING / max(f0, 1)))
    richness = len(harmonics) / max(1, max_possible)
    inharmonicity = float(np.mean(deviations)) if deviations else 0.0

    if max_possible > 0 and len(deviations) > 0:
        closeness = 1.0 - (np.mean(deviations) / tolerance_cents)
        series_fit = richness * max(0, closeness)
    else:
        series_fit = 0.0

    return harmonics, round(series_fit, 4), round(inharmonicity, 1), round(richness, 3)


def compute_overtone_stream(audio_path, sr=22050, n_fft=OVERTONE_N_FFT):
    """Compute per-frame overtone analysis."""
    hop_length = 512

    y, sr = librosa.load(audio_path, sr=sr, mono=True)

    print("  Tracking fundamental (pyin)...")
    f0_full, voiced_full, voiced_probs_full = librosa.pyin(
        y, sr=sr, hop_length=hop_length,
        fmin=OVERTONE_FMIN, fmax=OVERTONE_FMAX,
        fill_na=np.nan
    )
    f0_times_full = librosa.frames_to_time(np.arange(len(f0_full)), sr=sr, hop_length=hop_length)

    print("  Computing high-resolution STFT...")
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    subsample_step = max(1, int(0.5 / (hop_length / sr)))
    n_frames_full = min(len(f0_full), S.shape[1])
    frame_indices = np.arange(0, n_frames_full, subsample_step)

    f0 = f0_full[frame_indices]
    f0_times = f0_times_full[frame_indices]
    n_frames = len(frame_indices)

    print(f"  Matching harmonics across {n_frames} frames (subsampled from {n_frames_full})...")
    stream = []
    all_fits = []
    all_richness = []
    all_inharm = []

    for idx_pos, frame_idx in enumerate(frame_indices):
        t = float(f0_times[idx_pos])
        current_f0 = float(f0[idx_pos]) if not np.isnan(f0[idx_pos]) else 0.0

        if current_f0 <= 0:
            stream.append({
                "t": round(t, 2),
                "f0": None,
                "harmonics": {},
                "series_fit": 0.0,
                "inharmonicity": 0.0,
                "richness": 0.0,
                "dominant_harmonic": None,
            })
            continue

        spectrum = S[:, frame_idx]
        peak_freqs, peak_mags = find_spectral_peaks(spectrum, freqs)

        harmonics, series_fit, inharm, richness = match_harmonics(
            current_f0, peak_freqs, peak_mags
        )

        dominant = None
        max_mag = 0
        for n, h in harmonics.items():
            if n > 1 and h["magnitude"] > max_mag:
                max_mag = h["magnitude"]
                dominant = n

        stream.append({
            "t": round(t, 2),
            "f0": round(current_f0, 1),
            "harmonics": {str(k): v for k, v in harmonics.items()},
            "series_fit": series_fit,
            "inharmonicity": inharm,
            "richness": richness,
            "dominant_harmonic": dominant,
        })

        all_fits.append(series_fit)
        all_richness.append(richness)
        all_inharm.append(inharm)

    return f0_times[:n_frames], stream, f0[:n_frames], {
        "mean_series_fit": round(float(np.mean(all_fits)), 4) if all_fits else 0.0,
        "mean_richness": round(float(np.mean(all_richness)), 3) if all_richness else 0.0,
        "mean_inharmonicity": round(float(np.mean(all_inharm)), 1) if all_inharm else 0.0,
        "max_series_fit": round(float(np.max(all_fits)), 4) if all_fits else 0.0,
        "voiced_frames": sum(1 for s in stream if s["f0"] is not None),
        "total_frames": n_frames,
    }


def analyze_overtones(audio_path, output_dir, track_name):
    """Full overtone analysis pipeline.

    Returns (summary_dict, stream_list).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing overtones: {audio_path}...")

    times, stream, f0, summary_stats = compute_overtone_stream(audio_path)
    duration = times[-1] if len(times) > 0 else 0

    # ===== AGGREGATE ANALYSIS =====
    harmonic_counts = {}
    harmonic_mean_mag = {}
    for frame in stream:
        for n_str, h in frame["harmonics"].items():
            n = int(n_str)
            harmonic_counts[n] = harmonic_counts.get(n, 0) + 1
            if n not in harmonic_mean_mag:
                harmonic_mean_mag[n] = []
            harmonic_mean_mag[n].append(h["magnitude"])

    harmonic_profile = {}
    for n in sorted(harmonic_counts.keys()):
        harmonic_profile[n] = {
            "presence_pct": round(100 * harmonic_counts[n] / max(1, summary_stats["voiced_frames"]), 1),
            "mean_magnitude": round(float(np.mean(harmonic_mean_mag[n])), 6),
        }

    dominant_counts = {}
    for frame in stream:
        d = frame["dominant_harmonic"]
        if d is not None:
            dominant_counts[d] = dominant_counts.get(d, 0) + 1

    fit_times = [s["t"] for s in stream if s["f0"] is not None]
    fit_values = [s["series_fit"] for s in stream if s["f0"] is not None]
    richness_values = [s["richness"] for s in stream if s["f0"] is not None]

    # ===== SUMMARY =====
    summary = {
        "track": track_name,
        "duration": round(duration, 1),
        **summary_stats,
        "harmonic_profile": harmonic_profile,
        "dominant_harmonic_histogram": dict(sorted(dominant_counts.items())),
        "stream_length": len(stream),
    }

    # ===== SAVE =====
    stream_path = out / f"{track_name}_overtone_stream.json"
    with open(stream_path, "w") as f:
        json.dump(stream, f)
    print(f"  Overtone stream saved: {stream_path} ({len(stream)} entries)")

    summary_path = out / f"{track_name}_overtone.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Overtone summary saved: {summary_path}")

    # ===== VISUALIZATION =====
    print("  Generating overtone plots...")

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)

    if fit_times:
        axes[0].plot(fit_times, fit_values, color="#2ecc71", linewidth=1, alpha=0.8)
        axes[0].fill_between(fit_times, fit_values, alpha=0.3, color="#2ecc71")
    axes[0].set_ylabel("Series Fit")
    axes[0].set_ylim(0, 1)
    axes[0].set_title(f"{track_name} — Overtone Series Analysis", fontsize=13)

    if fit_times:
        axes[1].plot(fit_times, richness_values, color="#9b59b6", linewidth=1, alpha=0.8)
        axes[1].fill_between(fit_times, richness_values, alpha=0.3, color="#9b59b6")
    axes[1].set_ylabel("Richness")
    axes[1].set_ylim(0, 1)
    axes[1].set_title("Overtone Richness (fraction of harmonics present)", fontsize=13)

    max_h = max(harmonic_counts.keys()) if harmonic_counts else OVERTONE_MAX_HARMONIC
    max_h = min(max_h, OVERTONE_MAX_HARMONIC)
    voiced_frames = [s for s in stream if s["f0"] is not None]
    if voiced_frames:
        heatmap = np.zeros((max_h, len(voiced_frames)))
        heat_times = [s["t"] for s in voiced_frames]
        for j, frame in enumerate(voiced_frames):
            for n_str, h in frame["harmonics"].items():
                n = int(n_str)
                if 1 <= n <= max_h:
                    heatmap[n - 1, j] = h["magnitude"]

        for row in range(max_h):
            row_max = np.max(heatmap[row])
            if row_max > 0:
                heatmap[row] /= row_max

        im = axes[2].imshow(
            heatmap, aspect='auto', origin='lower', cmap='magma',
            extent=[heat_times[0], heat_times[-1], 0.5, max_h + 0.5],
            interpolation='nearest',
        )
        axes[2].set_ylabel("Harmonic #")
        axes[2].set_yticks(range(1, max_h + 1))
        axes[2].set_xlabel("Time (s)")
        axes[2].set_title("Harmonic Presence (normalized per harmonic)", fontsize=13)
        plt.colorbar(im, ax=axes[2], label="Relative Magnitude")

    plt.tight_layout()
    plt.savefig(out / f"{track_name}_overtone.png", dpi=150)
    plt.close()
    print(f"  Overtone plot saved.")

    if harmonic_profile:
        fig, ax = plt.subplots(figsize=(10, 5))
        harmonics_sorted = sorted(harmonic_profile.keys())
        presence = [harmonic_profile[n]["presence_pct"] for n in harmonics_sorted]
        colors = ['#2ecc71' if p > 50 else '#f39c12' if p > 25 else '#e74c3c' for p in presence]
        ax.bar([str(n) for n in harmonics_sorted], presence, color=colors, alpha=0.8)
        ax.set_xlabel("Harmonic Number")
        ax.set_ylabel("Presence (%)")
        ax.set_title(f"{track_name} — Harmonic Profile (% of voiced frames)", fontsize=13)
        ax.set_ylim(0, 105)
        plt.tight_layout()
        plt.savefig(out / f"{track_name}_harmonic_profile.png", dpi=150)
        plt.close()
        print(f"  Harmonic profile plot saved.")

    return summary, stream
