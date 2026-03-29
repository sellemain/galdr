# Silence-Aware Metrics — Design Spec

**Branch:** `feature/silence-aware-metrics`  
**Status:** Design / not yet released  
**Target:** galdr 0.2.0

---

## Problem

When a track contains significant silence (mid-track gaps, leading/trailing silence, extended pauses), galdr's summary metrics are contaminated:

- **Momentum** averaged across silent frames is artificially deflated
- **Pattern Lock** inflates toward 1.000 during silence (nothing deviating = perfect lock)
- **Catalog ranking** compares contaminated averages against tracks with no silence — unfair comparison

Additionally, a fully null/zero audio input produces misleading output:
- Character labeled "pure harmonic/vocal" (math artifact from 0/0 ratio)
- Pattern Lock = 1.000 (technically correct, semantically wrong)
- Indexed in catalog as a real track

---

## Design

### 1. Null signal guard (early exit)

In `analyze_track()` and `listen()`, compute RMS before any module runs:

```python
SILENCE_THRESHOLD = 1e-6  # configurable constant

rms = np.sqrt(np.mean(samples**2))
if rms < SILENCE_THRESHOLD:
    return NullSignalResult(
        duration=duration,
        rms=float(rms),
        reason="null_signal"
    )
```

`NullSignalResult` is a distinct return type (not a `TrackAnalysis`). It:
- Does not write to the analysis directory
- Does not index in the catalog
- Prints a clear message: `null signal detected (RMS < threshold), no analysis performed`

### 2. Active-frame statistics in perception summary

The perception stream already marks silence frames via `pattern_break:silence` events. Use these to split frames into `active` and `silent` sets.

**New summary fields (additive — existing fields unchanged for compatibility):**

```json
{
  "active_duration_sec": 240.0,
  "silent_duration_sec": 120.0,
  "silence_pct": 33.3,
  "mean_momentum_active": 0.74,
  "mean_pattern_lock_active": 0.89,
  "momentum_range_active": [0.41, 0.97]
}
```

The existing `mean_momentum`, `mean_pattern_lock`, `momentum_range` fields are **kept unchanged** — they remain whole-track averages. Active-frame variants are additive new fields.

### 3. Catalog ranking

When indexing:
- If `active_duration_sec` is present and `silence_pct > 10%`, use `mean_momentum_active` and `mean_pattern_lock_active` for catalog ranking
- Add `silence_pct` as a new catalog dimension
- Add `silent_duration_sec` as a catalog dimension

This lets queries like "tracks with >30% silence" work, and prevents long-silence tracks from ranking artificially low on momentum.

### 4. Edge cases

| Case | Behavior |
|------|----------|
| Fully null audio | NullSignalResult, no catalog entry |
| >90% silence | Warn, but still analyze and catalog |
| Silence at start/end only | Active-frame stats exclude leading/trailing silence |
| Multiple mid-track gaps | All silent frames excluded from active stats |
| Very short track (<5s) | No change — silence detection may not fire, handle gracefully |

---

## Files affected

- `constants.py` — add `SILENCE_THRESHOLD`
- `perceive.py` — compute `active_duration_sec`, `silent_duration_sec`, active-frame variants in `_compute_perception()`
- `analyze.py` — add null signal guard, return `NullSignalResult`
- `catalog.py` — add silence dimensions, prefer active-frame stats when available
- `cli.py` — handle `NullSignalResult` output gracefully

---

## What this enables

- Morton Feldman vs. Sigur Rós vs. Helvegen silence comparison — *how* they use silence, not just *when*
- Silence percentage as a catalog axis
- Accurate momentum/pattern lock for tracks that use silence intentionally
- Clean behavior on degenerate inputs

---

## Not in scope

- Changing the existing `mean_momentum` / `mean_pattern_lock` fields (backward compat)
- Sub-silence analysis (what happens below the threshold)
- Loudness normalization (separate concern)
