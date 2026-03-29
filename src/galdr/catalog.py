#!/usr/bin/env python3
"""Catalog state — cross-track accumulated statistics.

The stateful listener needs memory. This module maintains a catalog index
that tracks running statistics across all analyzed tracks, so each new
analysis can compute relative metrics.

The catalog index is stored as catalog_state.json. Default location is
~/.galdr/ (XDG-style), overridable via catalog_dir parameter.
"""

import json
from pathlib import Path
from collections import OrderedDict

import numpy as np


def _default_catalog_dir():
    """Return the default catalog directory (~/.galdr/)."""
    return Path.home() / ".galdr"


class CatalogState:
    """Persistent catalog state for cross-track analysis."""

    def __init__(self, analysis_dir="analysis", catalog_dir=None):
        self.analysis_dir = Path(analysis_dir)
        if catalog_dir is not None:
            self.catalog_dir = Path(catalog_dir)
        else:
            self.catalog_dir = _default_catalog_dir()
        self.state_path = self.catalog_dir / "catalog_state.json"
        self.tracks = OrderedDict()  # track_name -> summary metrics
        self.stats = {}  # metric_name -> {mean, std, min, max, values}

    def load(self):
        """Load existing catalog state from disk.

        Checks both the catalog_dir location and the legacy
        analysis_dir/catalog_state.json location for backward compat.
        """
        loaded = False

        if self.state_path.exists():
            with open(self.state_path) as f:
                data = json.load(f)
            self.tracks = OrderedDict(data.get("tracks", {}))
            self._migrate_keys()
            self._recompute_stats()
            print(f"Catalog loaded: {len(self.tracks)} tracks")
            loaded = True

        if not loaded:
            # Check legacy location
            legacy_path = self.analysis_dir / "catalog_state.json"
            if legacy_path.exists():
                with open(legacy_path) as f:
                    data = json.load(f)
                self.tracks = OrderedDict(data.get("tracks", {}))
                self._migrate_keys()
                self._recompute_stats()
                print(f"Catalog loaded from legacy location: {len(self.tracks)} tracks")
                print(f"  Will save to {self.state_path} on next save")
                loaded = True

        if not loaded:
            print("No existing catalog state -- starting fresh")

    def _migrate_keys(self):
        """Migrate old metric names to new names in loaded track data."""
        for t in self.tracks.values():
            # moment_count -> pattern_break_count (legacy)
            if "pattern_break_count" not in t and "moment_count" in t:
                t["pattern_break_count"] = t.pop("moment_count")
            elif "moment_count" in t:
                del t["moment_count"]
            # consonance -> temperament_alignment (legacy)
            if "mean_temperament_alignment" not in t and "mean_consonance" in t and t["mean_consonance"] is not None:
                t["mean_temperament_alignment"] = t.pop("mean_consonance")
            elif "mean_consonance" in t:
                del t["mean_consonance"]
            # Remove chord-related fields (no longer produced)
            for old_key in ["top_chords", "primary_tonal_center", "mean_harmonic_rhythm"]:
                t.pop(old_key, None)

    def save(self):
        """Save catalog state to disk."""
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "tracks": dict(self.tracks),
            "stats": {k: {kk: vv for kk, vv in v.items() if kk != "values"}
                      for k, v in self.stats.items()},
            "track_count": len(self.tracks),
        }
        with open(self.state_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Catalog saved: {len(self.tracks)} tracks")

    def index_track(self, track_name, perception=None, harmony=None, melody=None, overtone=None, report=None):
        """Add or update a track's metrics in the catalog."""
        metrics = {"track": track_name}

        if perception:
            s = perception.get("summary", perception)
            # mean_surprise was renamed to mean_pattern_lock in the disruption refactor
            val = s.get("mean_pattern_lock")
            pattern_lock = val if val is not None else s.get("mean_surprise")
            metrics.update({
                "mean_momentum": s.get("mean_momentum"),
                "mean_pattern_lock": pattern_lock,
                "total_silence_sec": s.get("total_silence_sec"),
                "pattern_break_count": s.get("pattern_break_count"),
                "breath_positive_pct": s.get("breath_positive_pct"),
                "breath_negative_pct": s.get("breath_negative_pct"),
                "breath_sustain_pct": s.get("breath_sustain_pct"),
            })

        if harmony:
            metrics.update({
                "mean_temperament_alignment": harmony.get("mean_temperament_alignment"),
                "mean_consonance_series": harmony.get("mean_consonance_series"),
                "mean_tension": harmony.get("mean_tension"),
                "mean_chroma_flux": harmony.get("mean_chroma_flux"),
                "mean_tonal_stability": harmony.get("mean_tonal_stability"),
                "mean_major_minor": harmony.get("mean_major_minor"),
                "detected_key": harmony.get("detected_key"),
                "detected_mode": harmony.get("detected_mode"),
                "key_confidence": harmony.get("key_confidence"),
            })

        if melody:
            metrics.update({
                "overall_range_semitones": melody.get("overall_range_semitones"),
                "overall_center_note": melody.get("overall_center_note"),
                "mean_vocal_presence": melody.get("mean_vocal_presence"),
                "contour_ascending_pct": melody.get("contour_ascending_pct"),
                "contour_descending_pct": melody.get("contour_descending_pct"),
                "mean_direction": melody.get("mean_direction"),
            })

        if overtone:
            metrics.update({
                "mean_series_fit": overtone.get("mean_series_fit"),
                "mean_richness": overtone.get("mean_richness"),
                "mean_inharmonicity": overtone.get("mean_inharmonicity"),
            })

        if report:
            metrics.update({
                "duration_seconds": report.get("duration_seconds"),
                "tempo_bpm": report.get("tempo_bpm"),
                "beat_regularity": report.get("beat_regularity"),
                "percussion_ratio": report.get("percussion_ratio"),
                "spectral_centroid_mean_hz": report.get("spectral_centroid_mean_hz"),
            })

        self.tracks[track_name] = metrics
        self._recompute_stats()

    def _recompute_stats(self):
        """Recompute aggregate statistics across all tracks."""
        numeric_keys = set()
        for t in self.tracks.values():
            for k, v in t.items():
                if isinstance(v, (int, float)) and v is not None:
                    numeric_keys.add(k)

        self.stats = {}
        for key in sorted(numeric_keys):
            values = [t[key] for t in self.tracks.values()
                      if key in t and t[key] is not None and isinstance(t[key], (int, float))]
            if len(values) < 2:
                continue
            arr = np.array(values)
            self.stats[key] = {
                "mean": round(float(np.mean(arr)), 4),
                "std": round(float(np.std(arr)), 4),
                "min": round(float(np.min(arr)), 4),
                "max": round(float(np.max(arr)), 4),
                "median": round(float(np.median(arr)), 4),
                "count": len(values),
                "values": values,  # kept in memory, not saved
            }

    def rank(self, metric, value):
        """Get the rank and relative position of a value within the catalog."""
        if metric not in self.stats:
            return None

        s = self.stats[metric]
        values = sorted(s["values"])
        rank = sum(1 for v in values if v < value) + 1
        n = len(values)

        z_score = (value - s["mean"]) / s["std"] if s["std"] > 0 else 0.0

        return {
            "value": round(value, 4),
            "rank": rank,
            "of": n,
            "percentile": round((rank - 1) / max(1, n - 1) * 100, 1),
            "z_score": round(z_score, 2),
            "catalog_mean": s["mean"],
            "catalog_std": s["std"],
            "catalog_min": s["min"],
            "catalog_max": s["max"],
        }

    def extremes(self, metric, n=3):
        """Get the n highest and lowest tracks for a metric."""
        entries = [(name, t[metric]) for name, t in self.tracks.items()
                   if metric in t and t[metric] is not None]
        if not entries:
            return {"lowest": [], "highest": []}

        sorted_asc = sorted(entries, key=lambda x: x[1])
        return {
            "lowest": [(name, round(val, 4)) for name, val in sorted_asc[:n]],
            "highest": [(name, round(val, 4)) for name, val in sorted_asc[-n:][::-1]],
        }

    def summary_card(self, track_name):
        """Generate a summary card showing where a track sits in the catalog."""
        if track_name not in self.tracks:
            return f"Track '{track_name}' not in catalog"

        t = self.tracks[track_name]
        lines = [f"=== {track_name} -- Catalog Position ===\n"]

        key_metrics = [
            ("mean_pattern_lock", "Pattern Lock", "higher = stronger pattern lock"),
            ("mean_momentum", "Momentum", "higher = more locked in"),
            ("mean_temperament_alignment", "Temperament Alignment", "higher = more aligned with equal temperament"),
            ("mean_consonance_series", "Series Consonance", "higher = closer to harmonic series (JI)"),
            ("mean_tension", "Tension", "higher = more harmonic movement"),
            ("mean_chroma_flux", "Chroma Flux", "higher = faster harmonic change"),
            ("overall_range_semitones", "Melodic Range", "semitones"),
            ("mean_vocal_presence", "Vocal Presence", "0-1"),
            ("mean_series_fit", "Overtone Fit", "higher = purer harmonic series"),
            ("mean_richness", "Overtone Richness", "fraction of harmonics present"),
            ("beat_regularity", "Beat Regularity", "1.0 = metronomic"),
            ("key_confidence", "Key Confidence", "KK profile correlation"),
            ("tempo_bpm", "Tempo", "BPM"),
        ]

        for metric, label, desc in key_metrics:
            if metric in t and t[metric] is not None:
                r = self.rank(metric, t[metric])
                if r:
                    lines.append(
                        f"  {label}: {t[metric]:.3f} "
                        f"(rank {r['rank']}/{r['of']}, z={r['z_score']:+.1f}) -- {desc}"
                    )
                else:
                    lines.append(f"  {label}: {t[metric]:.3f} -- {desc}")

        return "\n".join(lines)

    def rebuild_from_files(self):
        """Rebuild catalog state by scanning all analysis directories."""
        print(f"Rebuilding catalog from {self.analysis_dir}...")
        count = 0

        for track_dir in sorted(self.analysis_dir.iterdir()):
            if not track_dir.is_dir():
                continue

            track_name = track_dir.name
            perception = harmony = melody = overtone = report = None

            for pattern, target in [
                (f"{track_name}_perception.json", "perception"),
                (f"{track_name}_harmony.json", "harmony"),
                (f"{track_name}_melody.json", "melody"),
                (f"{track_name}_overtone.json", "overtone"),
                (f"{track_name}_report.json", "report"),
            ]:
                path = track_dir / pattern
                if path.exists():
                    with open(path) as f:
                        data = json.load(f)
                    if target == "perception":
                        perception = data
                    elif target == "harmony":
                        harmony = data
                    elif target == "melody":
                        melody = data
                    elif target == "overtone":
                        overtone = data
                    elif target == "report":
                        report = data

            if any([perception, harmony, melody, overtone, report]):
                self.index_track(track_name, perception, harmony, melody, overtone, report)
                count += 1

        print(f"  Indexed {count} tracks")
        self.save()
        return count
