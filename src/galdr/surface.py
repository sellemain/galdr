"""Surface feature bank for listener-state evidence.

These helpers keep low-level MIR measurements separate from the prose-facing
perception model. They are deliberately small and dependency-light: no source
separation, no trained classifier, no claims about exact instruments. The goal
is to expose enough surface evidence for higher layers to describe what the
sound feels like without turning galdr into a dashboard.
"""

from __future__ import annotations

import numpy as np
import librosa


def _safe_mean(values: np.ndarray) -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return 0.0
    return float(np.mean(finite))


def _normalize(value: float, scale: float) -> float:
    if scale <= 0 or not np.isfinite(value):
        return 0.0
    return float(np.clip(value / scale, 0.0, 1.0))


def _state(score: float, *, low: float, high: float, labels: tuple[str, str, str]) -> str:
    if score >= high:
        return labels[2]
    if score >= low:
        return labels[1]
    return labels[0]


def compute_surface_feature_bank(y: np.ndarray, sr: int, *, hop_sec: float = 1.0) -> dict:
    """Compute per-window surface evidence aligned to a listener-state hop.

    Returns a dict with ``times`` and one value list per measured/derived field.
    Derived fields are bounded 0-1 perceptual cues, not genre or instrument
    labels. They are evidence for voice/band/body writing, not final prose.
    """
    if hop_sec <= 0:
        raise ValueError("hop_sec must be positive")

    y = np.asarray(y, dtype=np.float32)
    duration = float(librosa.get_duration(y=y, sr=sr))
    if duration <= 0:
        raise ValueError("Audio too short to analyze")

    times = np.arange(0, duration, hop_sec)
    if times.size == 0:
        times = np.asarray([0.0])

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    flatness = librosa.feature.spectral_flatness(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    rms = librosa.feature.rms(y=y)[0]
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    y_h, y_p = librosa.effects.hpss(y)
    harmonic_rms = librosa.feature.rms(y=y_h)[0]
    percussive_rms = librosa.feature.rms(y=y_p)[0]
    del y_h, y_p

    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    onset_times = librosa.times_like(onset, sr=sr)

    fields = {
        "mfcc_std": [],
        "spectral_centroid": [],
        "spectral_bandwidth": [],
        "spectral_rolloff": [],
        "spectral_flatness": [],
        "zero_crossing_rate": [],
        "rms": [],
        "spectral_contrast": [],
        "onset_strength": [],
        "harmonic_rms": [],
        "percussive_rms": [],
        "percussive_ratio": [],
        "roughness": [],
        "noise_density": [],
        "transient_attack": [],
        "sustain_drone": [],
        "band_pressure": [],
    }

    half = hop_sec / 2.0
    for t in times:
        start = max(0.0, float(t) - half)
        end = min(duration, float(t) + half)
        if end <= start:
            end = min(duration, start + hop_sec)

        mask = (frame_times >= start) & (frame_times < end)
        if not mask.any():
            idx = int(np.clip(np.searchsorted(frame_times, t), 0, len(frame_times) - 1))
            mask[idx] = True

        onset_mask = (onset_times >= start) & (onset_times < end)
        if not onset_mask.any() and len(onset_times) > 0:
            idx = int(np.clip(np.searchsorted(onset_times, t), 0, len(onset_times) - 1))
            onset_mask[idx] = True

        mfcc_std = _safe_mean(np.std(mfcc[:, mask], axis=1))
        centroid_mean = _safe_mean(centroid[mask])
        bandwidth_mean = _safe_mean(bandwidth[mask])
        rolloff_mean = _safe_mean(rolloff[mask])
        flatness_mean = _safe_mean(flatness[mask])
        zcr_mean = _safe_mean(zcr[mask])
        rms_mean = _safe_mean(rms[mask])
        harmonic_rms_mean = _safe_mean(harmonic_rms[mask])
        percussive_rms_mean = _safe_mean(percussive_rms[mask])
        hp_total = harmonic_rms_mean + percussive_rms_mean
        percussive_ratio = percussive_rms_mean / hp_total if hp_total > 1e-9 else 0.0
        contrast_mean = _safe_mean(contrast[:, mask])
        onset_mean = _safe_mean(onset[onset_mask]) if len(onset) else 0.0

        mfcc_motion = _normalize(mfcc_std, 80.0)
        brightness = _normalize(centroid_mean, sr / 2.0)
        spread = _normalize(bandwidth_mean, sr / 2.0)
        edge = _normalize(zcr_mean, 0.22)
        noisiness = _normalize(flatness_mean, 0.40)
        attack = _normalize(onset_mean, 4.0)
        body_floor = _normalize(rms_mean, 0.08)
        tonal_coherence = 1.0 - noisiness

        roughness = float(np.clip(
            0.30 * noisiness + 0.25 * edge + 0.20 * spread + 0.15 * mfcc_motion + 0.10 * brightness,
            0.0,
            1.0,
        ))
        noise_density = float(np.clip(0.55 * noisiness + 0.25 * spread + 0.20 * edge, 0.0, 1.0))
        transient_attack = float(np.clip(0.70 * attack + 0.30 * edge, 0.0, 1.0))
        sustain_drone = float(np.clip(tonal_coherence * body_floor * (1.0 - min(1.0, attack)), 0.0, 1.0))
        band_pressure = float(np.clip(0.45 * body_floor + 0.25 * roughness + 0.20 * spread + 0.10 * attack, 0.0, 1.0))

        fields["mfcc_std"].append(round(mfcc_std, 3))
        fields["spectral_centroid"].append(round(centroid_mean, 3))
        fields["spectral_bandwidth"].append(round(bandwidth_mean, 3))
        fields["spectral_rolloff"].append(round(rolloff_mean, 3))
        fields["spectral_flatness"].append(round(flatness_mean, 5))
        fields["zero_crossing_rate"].append(round(zcr_mean, 5))
        fields["rms"].append(round(rms_mean, 5))
        fields["spectral_contrast"].append(round(contrast_mean, 3))
        fields["onset_strength"].append(round(onset_mean, 3))
        fields["harmonic_rms"].append(round(harmonic_rms_mean, 5))
        fields["percussive_rms"].append(round(percussive_rms_mean, 5))
        fields["percussive_ratio"].append(round(float(np.clip(percussive_ratio, 0.0, 1.0)), 3))
        fields["roughness"].append(round(roughness, 3))
        fields["noise_density"].append(round(noise_density, 3))
        fields["transient_attack"].append(round(transient_attack, 3))
        fields["sustain_drone"].append(round(sustain_drone, 3))
        fields["band_pressure"].append(round(band_pressure, 3))

    return {
        "times": [round(float(t), 3) for t in times],
        "hop_sec": round(float(hop_sec), 3),
        **fields,
    }


def surface_snapshot(bank: dict, index: int) -> dict:
    """Return one compact, prose-facing surface evidence row."""
    return {
        "roughness": bank["roughness"][index],
        "noise_density": bank["noise_density"][index],
        "transient_attack": bank["transient_attack"][index],
        "sustain_drone": bank["sustain_drone"][index],
        "band_pressure": bank["band_pressure"][index],
        "percussive_ratio": bank["percussive_ratio"][index],
        "roughness_state": _state(
            float(bank["roughness"][index]),
            low=0.32,
            high=0.62,
            labels=("smooth", "grained", "abrasive"),
        ),
        "motion_state": _state(
            float(bank["transient_attack"][index]),
            low=0.25,
            high=0.55,
            labels=("sustained", "moving", "striking"),
        ),
        "pressure_state": _state(
            float(bank["band_pressure"][index]),
            low=0.25,
            high=0.55,
            labels=("thin", "held", "pressurized"),
        ),
    }
