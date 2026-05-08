# LUFS pressure language check

## Purpose

Verify that the v0.2.1 loudness/breath change improves listening evidence without leaking meter readings into experience prose.

LUFS is an implementation detail. The listener-facing language is pressure: comes forward, holds, releases, empties.

## Test track

AURORA — Runaway, re-analyzed with galdr 0.2.1 in `analysis-021-test/aurora-runaway-021-test/`.

## Observed difference

The old RMS breath read over-reported release through the body of the track. The LUFS-backed pressure model reads more of the track as sustained hold, with the real release concentrated at the ending collapse.

Old pressure split: building/releasing/sustaining = 37.0 / 40.2 / 22.8.

New pressure split: building/releasing/sustaining = 36.6 / 20.0 / 43.4.

The important result is not the percentages themselves. The important result is the changed reading: Runaway is mostly sustained pressure and entrainment, not constant release.

## Language rule

Bad experience prose:

> Loudness rises from -27 LUFS to -20 LUFS.

Better experience prose:

> The pressure comes forward. Not a burst, not a hit. The room becomes occupied.

Bad experience prose:

> The track reaches -11 LUFS and remains there.

Better experience prose:

> The song holds the listener in a high, stable state. It is almost all grip here.

Bad experience prose:

> Loudness falls through -48 LUFS into silence.

Better experience prose:

> The structure drops away. Silence takes over.

## Acceptance

- Raw LUFS values may appear in JSON, tests, implementation comments, and regression notes.
- Raw LUFS values should not appear in generated listening-experience prose.
- `pressure_state`, `breath`, and loudness deltas should be translated as build, hold, release, or emptying.
- If a write-up needs exact numbers, label it as debug/regression analysis, not experience prose.
