# Perception-First Roadmap

galdr should measure what changes listener state, not what a theorist can label.

This document is the working control surface for the next analysis pass. It is not a wish list. Each slice should either sharpen perceptual honesty or get demoted.

## Core rule

> Prefer perceptual truth over analytical cleverness.
>
> If a field sounds authoritative but does not track what a listener actually experiences, demote it, relabel it, or hide it.

## Why this exists

The current stack already finds real things: pattern lock, momentum, breaks, breath direction, silence, broad harmonic stability. But it also still overstates some claims:

- tempo can silently lock onto the wrong pulse
- energy can confuse RMS intensity with heard loudness
- silence is detected, but re-entry and recovery are under-described
- harmony and melody can drift toward theory labels that sound stronger than the evidence
- summaries can flatten stream truth into clean language that sounds more certain than the track warrants

The roadmap is meant to keep implementation honest: perception first, labels second.

## Working principles

1. **Stream truth beats summary truth.** The second-by-second trace is primary evidence.
2. **Listener-state fields first.** Prefer measures that describe pressure, release, rupture, suspension, return, lock, drift, and pull.
3. **Labels are optional.** Keys, tempos, and other names are useful only when confidence is honest.
4. **Silence matters as structure.** Quiet, absence, withdrawal, and re-entry are first-class events.
5. **Comparison over intuition.** Every meaningful change should have a before/after listening-test artifact.
6. **Demotion is success.** A misleading metric removed from the surface is progress, not failure.

## Near-term implementation order

### 0. Harness and baseline discipline

Before deeper metric changes, keep the comparison lane simple and reusable.

Required artifacts:
- `docs/listening-tests/template.md`
- one baseline comparison plan per implementation slice
- before/after note structure that references a real track, the observed mismatch, the metric change, and the result

### 1. Tempo validation and ambiguity

Problem: galdr can report a technically detected pulse that is not the tempo people hear.

Known failure:
- CIPHER THEY KNEW: galdr reported `92.3 BPM`
- independent windowed beat tracking repeatedly found roughly `140.6 BPM`
- external claim was `142.3 BPM`
- conclusion: alternate-pulse selection can be wrong while sounding precise

Needed changes:
- emit candidate tempos, not just a single asserted BPM
- distinguish **detected pulse** from **perceived tempo candidate** when they diverge
- attach confidence / ambiguity markers
- avoid writing a naked BPM as plain truth when confidence is poor
- add a regression artifact for the CIPHER failure

Follow-on task: SM-305.

### 2. Loudness / breath honesty

Problem: RMS energy is not the same thing as heard pressure.

Needed changes:
- bring LUFS or short-term loudness into the breath / pressure model
- separate quiet-but-intense from simply loud
- improve handling of compression, impact, and weight

Follow-on task: SM-306.

### 3. Silence recovery and re-entry

Problem: silence events exist, but the system under-describes what happens after the gap.

Needed changes:
- measure re-entry force, recovery time, and whether the return feels like reset, rupture, continuation, or withdrawal
- make silence structure visible in assembled output without decorative language

Follow-on task: SM-307.

### 4. Perception-purity audit

Problem: some exposed fields feel more like theorist artifacts than listener-state evidence.

Needed changes:
- inventory current fields across report / perception / harmony / melody / overtone / assembly
- classify each as: first-class perceptual state, internal evidence, or suspect label
- keep, demote, rename, hide

Follow-on task: SM-308.

### 5. Rhythm as body entrainment

Problem: beat regularity is narrower than what the body actually locks to.

Needed changes:
- explore pulse certainty, groove stability, withholding, off-center pull, syncopation, swing, rubato-to-lock, and half/double-time ambiguity
- treat body entrainment as a separate perceptual lane from pure beat detection

Follow-on task: SM-309.

## Later lanes

These are real, but not first.

- harmony demotion / honesty pass
- foreground pitch honesty in dense or polyphonic sections
- texture / density / grain metrics
- corpus-context comparison fields that help explain what is unusually pure, ruptured, compressed, suspended, or relentless relative to prior listens

## Comparison workflow

Each metric change should produce a listening-test note under `docs/listening-tests/`.

Minimum workflow:
1. Name one concrete failure or perceptual mismatch.
2. Capture the current baseline output.
3. State what metric or reporting change is being made.
4. Re-run on the same track or track pair.
5. Write what improved, what stayed wrong, and what new risk appeared.

Do not let implementation changes hide behind aggregate “seems better” claims.

## Success condition for this roadmap

This roadmap is doing its job if future galdr work starts producing:
- fewer false-certainty labels
- better before/after listening artifacts
- clearer separation between evidence and interpretation
- metric additions that sound more like listening and less like report cosplay
