#!/usr/bin/env python3
"""Audio perception pipeline — base audio analysis.

For each track: load audio, extract tempo/beat, spectral features,
generate visualizations (spectrogram, beat grid, energy curve),
and output a structured perception report.
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
    SEGMENT_MIN_GAP_SEC, SEGMENT_MIN_TAIL_SEC,
    ENERGY_ARC_SEGMENTS,
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


def analyze_track(audio_path: str, output_dir: str, track_name: str) -> dict:
    """Full audio analysis of a single track."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading {audio_path}...")
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    print(f"  Duration: {duration:.1f}s, Sample rate: {sr}")

    if duration <= 0:
        raise ValueError("Audio too short to analyze")

    # --- Tempo and beat tracking ---
    print("  Beat tracking...")
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    # tempo may be an array in newer librosa
    if hasattr(tempo, '__len__'):
        tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
    else:
        tempo = float(tempo)

    # Beat intervals for rhythm analysis
    if len(beat_times) > 1:
        beat_intervals = np.diff(beat_times)
        beat_regularity = max(0.0, 1.0 - (np.std(beat_intervals) / np.mean(beat_intervals)))
    else:
        beat_intervals = np.array([])
        beat_regularity = 0.0

    # --- Spectral features ---
    print("  Spectral analysis...")
    # Mel spectrogram
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
    S_dB = librosa.power_to_db(S, ref=np.max)

    # Spectral centroid (brightness)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]

    # --- Chroma (harmonic content) ---
    print("  Chroma analysis...")
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # --- Energy / RMS ---
    print("  Energy analysis...")
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    # Energy arc: split into segments and track the build
    n_segments = ENERGY_ARC_SEGMENTS
    seg_len = len(rms) // n_segments
    if seg_len == 0:
        # Audio too short to split into n_segments — treat as a single segment
        n_segments = 1
        seg_len = len(rms)
    energy_arc = []
    for i in range(n_segments):
        seg = rms[i * seg_len : (i + 1) * seg_len]
        if len(seg) == 0:
            seg = rms  # fallback: use the whole array
        energy_arc.append({
            "segment": i + 1,
            "time_range": f"{rms_times[i * seg_len]:.0f}s-{rms_times[min((i+1)*seg_len, len(rms_times)-1)]:.0f}s",
            "mean_energy": float(np.mean(seg)),
            "peak_energy": float(np.max(seg)),
        })

    # --- Onset detection (percussive events) ---
    print("  Onset detection...")
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # --- Harmonic-percussive separation ---
    print("  Harmonic-percussive separation...")
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    perc_energy = float(np.mean(librosa.feature.rms(y=y_percussive)[0]))
    harm_energy = float(np.mean(librosa.feature.rms(y=y_harmonic)[0]))
    perc_ratio = perc_energy / (perc_energy + harm_energy) if (perc_energy + harm_energy) > 0 else 0

    # --- Zero crossing rate (texture) ---
    zcr = librosa.feature.zero_crossing_rate(y)[0]

    # --- Dynamics ---
    dynamic_range = float(np.max(rms) / np.min(rms[rms > 0])) if np.any(rms > 0) else 0

    # ===== VISUALIZATIONS =====

    fig_w, fig_h = 16, 4

    # 1. Mel spectrogram
    print("  Generating spectrogram...")
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    librosa.display.specshow(S_dB, sr=sr, x_axis="time", y_axis="mel", ax=ax, cmap="magma")
    ax.set_title(f"{track_name} — Mel Spectrogram", fontsize=14)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    plt.colorbar(ax.collections[0], ax=ax, format="%+2.0f dB")
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_spectrogram.png", dpi=150)
    plt.close()

    # 2. Energy + beats
    print("  Generating energy + beat plot...")
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.plot(rms_times, rms, color="#e74c3c", linewidth=0.8, label="Energy (RMS)")
    for bt in beat_times:
        ax.axvline(x=bt, color="#3498db", alpha=0.15, linewidth=0.5)
    ax.set_title(f"{track_name} — Energy & Beats (tempo: {tempo:.0f} BPM)", fontsize=14)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Energy")
    ax.legend()
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_energy_beats.png", dpi=150)
    plt.close()

    # 3. Chroma
    print("  Generating chroma plot...")
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    librosa.display.specshow(chroma, sr=sr, x_axis="time", y_axis="chroma", ax=ax, cmap="coolwarm")
    ax.set_title(f"{track_name} — Chromagram (harmonic content)", fontsize=14)
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_chroma.png", dpi=150)
    plt.close()

    # 4. Spectral centroid (brightness over time)
    print("  Generating brightness plot...")
    cent_times = librosa.frames_to_time(np.arange(len(centroid)), sr=sr)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.plot(cent_times, centroid, color="#9b59b6", linewidth=0.8)
    ax.fill_between(cent_times, centroid, alpha=0.2, color="#9b59b6")
    ax.set_title(f"{track_name} — Spectral Centroid (brightness)", fontsize=14)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Hz")
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_brightness.png", dpi=150)
    plt.close()

    # 5. Percussive vs harmonic waveform comparison
    print("  Generating harmonic/percussive plot...")
    fig, axes = plt.subplots(2, 1, figsize=(fig_w, fig_h * 1.5), sharex=True)
    t = np.linspace(0, duration, len(y_harmonic))
    # Downsample for plotting
    step = max(1, len(t) // 10000)
    axes[0].plot(t[::step], y_harmonic[::step], color="#2ecc71", linewidth=0.3)
    axes[0].set_title("Harmonic (voices, strings, sustained tones)")
    axes[0].set_ylabel("Amplitude")
    axes[1].plot(t[::step], y_percussive[::step], color="#e67e22", linewidth=0.3)
    axes[1].set_title("Percussive (drums, impacts, transients)")
    axes[1].set_ylabel("Amplitude")
    axes[1].set_xlabel("Time (s)")
    plt.suptitle(f"{track_name} — Harmonic vs Percussive", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(out / f"{track_name}_harm_perc.png", dpi=150)
    plt.close()

    # --- Novelty-based segmentation ---
    print("  Computing structural segments...")
    # Use spectral novelty to find natural section boundaries
    # instead of arbitrary 10-segment split
    # Recurrence matrix → novelty curve
    try:
        # Chroma-based novelty for structural boundaries
        bound_frames = librosa.segment.agglomerative(chroma, k=None)
        # Filter: keep boundaries with at least 10 seconds between them
        bound_times_raw = librosa.frames_to_time(bound_frames, sr=sr)
        structural_boundaries = [0.0]
        for bt in bound_times_raw:
            if bt - structural_boundaries[-1] >= SEGMENT_MIN_GAP_SEC:
                structural_boundaries.append(round(float(bt), 1))
        if duration - structural_boundaries[-1] > SEGMENT_MIN_TAIL_SEC:
            structural_boundaries.append(round(duration, 1))

        # Build segments from boundaries
        structural_segments = []
        for i in range(len(structural_boundaries) - 1):
            start_t = structural_boundaries[i]
            end_t = structural_boundaries[i + 1]
            # Find RMS frames within this segment
            seg_mask = (rms_times >= start_t) & (rms_times < end_t)
            seg_rms = rms[seg_mask]
            if len(seg_rms) > 0:
                structural_segments.append({
                    "segment": i + 1,
                    "start": start_t,
                    "end": end_t,
                    "duration": round(end_t - start_t, 1),
                    "mean_energy": round(float(np.mean(seg_rms)), 6),
                    "peak_energy": round(float(np.max(seg_rms)), 6),
                })
    except Exception:
        # Fallback: use fixed segments if novelty detection fails
        structural_boundaries = []
        structural_segments = []

    # --- Build perception report ---
    report = {
        "track": track_name,
        "duration_seconds": round(duration, 1),
        "tempo_bpm": round(tempo, 1),
        "beat_count": len(beat_times),
        "beat_regularity": round(beat_regularity, 3),  # 1.0 = perfectly regular
        "rhythm_description": (
            "very regular/metronomic" if beat_regularity > 0.9
            else "steady" if beat_regularity > 0.7
            else "organic/fluid" if beat_regularity > 0.5
            else "free/rubato"
        ),
        "percussion_ratio": round(perc_ratio, 3),  # 0=all harmonic, 1=all percussive
        "harmonic_energy": round(harm_energy, 6),
        "percussive_energy": round(perc_energy, 6),
        "character": (
            "heavily percussive" if perc_ratio > 0.6
            else "percussive" if perc_ratio > 0.45
            else "balanced" if perc_ratio > 0.35
            else "harmonic/vocal dominant" if perc_ratio > 0.2
            else "pure harmonic/vocal"
        ),
        "spectral_centroid_mean_hz": round(float(np.mean(centroid)), 1),
        "brightness": (
            "very bright" if np.mean(centroid) > 3000
            else "bright" if np.mean(centroid) > 2000
            else "warm" if np.mean(centroid) > 1200
            else "dark/deep"
        ),
        "dynamic_range_ratio": round(dynamic_range, 1),
        "dynamics": (
            "very dynamic" if dynamic_range > 50
            else "dynamic" if dynamic_range > 20
            else "moderate dynamics" if dynamic_range > 5
            else "compressed/steady"
        ),
        "onset_count": len(onset_times),
        "onsets_per_second": round(len(onset_times) / duration, 2),
        "texture": (
            "dense/busy" if len(onset_times) / duration > 5
            else "moderate texture" if len(onset_times) / duration > 2
            else "sparse/spacious" if len(onset_times) / duration > 0.5
            else "very sparse/ambient"
        ),
        "energy_arc": energy_arc,
        "structural_segments": structural_segments,
        "structural_boundaries": structural_boundaries,
        "mean_zcr": round(float(np.mean(zcr)), 6),
        "dominant_chroma": list(
            np.array(PITCH_NAMES)[np.argsort(-np.mean(chroma, axis=1))[:3]]
        ),
        "visualizations": [
            f"{track_name}_spectrogram.png",
            f"{track_name}_energy_beats.png",
            f"{track_name}_chroma.png",
            f"{track_name}_brightness.png",
            f"{track_name}_harm_perc.png",
        ],
    }

    # Save report
    report_path = out / f"{track_name}_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved: {report_path}")

    return report
