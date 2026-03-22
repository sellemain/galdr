# The Galdr Perception Model

Galdr models a listener's perceptual state as music plays — not the audio file as a static object, but how attention moves through time. How engagement builds, holds, breaks, and dissolves.

---

## The Listener

The central model is a listener who starts outside the music, gets pulled in, holds attention, and eventually releases. Attention behaves like a resonant system: it takes time to reach full amplitude, sustains efficiently once coupled, and rings down slowly when excitation stops. The music either finds the listener's frequency, or it doesn't.

Every metric galdr emits describes some aspect of this resonance.

---

## Core Metrics

### `momentum`
Current resonance depth. `0.0` = not yet resonating. `1.0` = fully locked.

Not a quality judgment. High momentum measures the grip, not the value of what's gripping. Holds through short silences (<~2s); falls and requires re-entry after sustained silence or structural breakdown.

---

### `breath`
Direction of energy change. Positive = expanding. Negative = contracting. Near zero = sustained.

A high-momentum track with negative breath is exhaling — resonance is still locked. Negative breath is not failure.

---

### `hp_balance`
Ratio of harmonic to percussive energy. Negative = harmonic/vocal dominant. Positive = percussive dominant.

The deepest negative values typically occur when only a single voice remains.

---

### `pattern_lock`
Two things simultaneously: rhythmic regularity and structural predictability. `pattern_lock = 1.0 - disruption`. High = steady beat, no structural surprises. Low = irregular pulse or sudden break.

High pattern_lock is not rigidity. In ritual and ceremonial music, extreme regularity is intentional — it allows the listener to stop tracking the beat and go somewhere else. High mean_pattern_lock across a track doesn't mean boring; it may mean the music is consistent enough to allow depth.

---

### `temperament_alignment`
How closely pitches align with equal temperament. Low = closer to the harmonic series (just intonation, natural tuning).

Low temperament_alignment is not out-of-tune. Folk traditions, overtone singing, and ritual music frequently sit here by design. Often co-occurs with deeply negative hp_balance.

---

### Silences
Detected periods of significant silence with start time, duration, and depth in dB. `-80dB` = true silence. `-40dB` = perceptually quiet but not empty.

Multiple silences clustering at a track's end, getting progressively longer and deeper, are a specific gesture — the music departing in stages. If momentum re-establishes after each silence (returning to `0.9+`), the listener is still held even as the music withdraws. Departure and grip happening simultaneously.

---

### `energy_arc`
The track divided into segments with mean and peak energy per segment — the macro shape of where the music puts its weight. Independent from momentum: low-energy sections can maintain full resonance.

---

## Interpretation

Reading galdr output is translating metrics into what is happening in the listener's body and attention.

**Mechanical readout:**
> "momentum: 0.974 (high), pattern_lock: 0.964 (high), hp_balance: -0.518 (harmonic dominant)"

**Perceptual description:**
> "The track is fully locked — resonance has been running near-maximum for over five minutes without degrading. The rhythm is extremely metronomic, but this isn't rigidity — it's the steadiness of ritual, a pulse the listener can surrender to rather than track. The music is voice and harmony dominant throughout. What little disruption exists is background noise; the listener knows exactly where they are."

Meaning lives in the relationships between metrics, not individual values.

---

## Worked Example: Helvegen — Wardruna

7 minutes 6 seconds. The track opens with 7 seconds of true silence. When sound arrives, momentum stays at `0.000` for 30 seconds — typical tracks lock in 4–7 seconds. Helvegen takes thirty. Then between t=30s and t=60s, resonance locks: momentum jumps from `0.000` to `0.974` and holds between 0.96–0.98 for five and a half minutes.

At the end, seven silences cluster. Each longer and deeper: `1.0s → 1.2s → 0.5s → 0.5s → 1.5s → 1.5s → 9.5s`, descending from -60dB to -80dB. After each silence, the voice returns. Resonance re-establishes — momentum returns above 0.93 each time. The listener keeps re-engaging because the music keeps coming back at full conviction. Until the seventh silence, when the voice doesn't return.

The road to Hel is not a fall. It is a series of departures and returns where the departures gradually win.

---

## The Question

**What is this music doing to the listener, and how does the music accomplish that?**

The metrics are evidence. The answer is a description of attention, body, and time.
