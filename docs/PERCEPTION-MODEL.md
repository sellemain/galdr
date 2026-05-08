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
Direction of heard pressure change. Positive = building. Negative = releasing. Near zero = sustaining.

As of v0.2.1, breath is derived from short-term LUFS rather than raw RMS energy. That makes it closer to perceived pressure: whether the music comes forward, withdraws, or holds its place in the listener's attention.

LUFS is implementation evidence, not listening language. In prose, translate it:

- rising loudness → pressure comes forward, gathers, fills the room
- falling loudness → pressure releases, loosens, drops away
- stable loudness → pressure holds, sustains, keeps the listener coupled
- loudness floor / silence → the structure empties, departs, or stops carrying attention

Do not write "LUFS rises from -27 to -20" in experience prose. That belongs in debugging or regression notes. A high-momentum track with negative breath is exhaling — resonance is still locked. Negative breath is not failure.

---

### `texture_balance`
Where the track's weight sits between sustained harmonic sound and percussive impact. Negative = harmonic/vocal dominant. Positive = percussive dominant.

Deep negative values often feel like voice, drone, strings, choir, or tonal atmosphere taking over the room. Strong positive values feel like strike, groove, attack, or drum-forward physicality. The deepest negative values typically occur when only a single voice remains.

---

### `pattern_lock`
How reliably the music keeps its pattern intact. `pattern_lock = 1.0 - disruption`. High = steady pulse, stable texture, and few structural surprises. Low = irregular pulse, sudden break, or sharp textural reorientation.

High pattern_lock is not rigidity. In ritual and ceremonial music, extreme regularity is intentional — it allows the listener to stop tracking the beat and go somewhere else. High mean_pattern_lock across a track doesn't mean boring; it may mean the music is consistent enough to allow depth.

---

### `tuning_alignment`
How cleanly the harmony sits inside familiar equal-tempered pitch space. High values feel centered, resolved, and conventionally tuned. Low values can feel smeared, bent, folk-natural, microtonal, or intentionally outside the grid.

Low tuning_alignment is not out-of-tune. Folk traditions, overtone singing, and ritual music frequently sit here by design. Often co-occurs with deeply negative texture_balance.

---

### `harmonic_series_consonance`
How concentrated the pitch content is around simple, stable harmonic relationships. High values feel fused, settled, and easy for the ear to organize. Low values feel more spread, harmonically complex, or ambiguous.

This is harmony-side evidence: it looks at pitch-class organization, not the raw overtone spectrum.

---

### `harmonic_tension`
How much the harmony is pulling, shifting, or refusing to settle over time. High values mean the tonal field is moving quickly or uneasily; low values mean it is anchored, suspended, or staying in one harmonic place.

Tension is not automatically negative. A track can use harmonic tension as propulsion, unease, color, or release preparation.

---

### `harmonic_series_fit`
How strongly the sound itself locks onto natural overtone relationships. High values feel pure, fused, bell-like, vocal, or resonant. Low values feel noisier, rougher, more inharmonic, or more textural.

This is overtone-side evidence: it looks at the spectrum around the detected fundamental, not the chord progression.

---

### Silences
Detected periods of significant silence with start time, duration, and depth in dB. `-80dB` = true silence. `-40dB` = perceptually quiet but not empty.

Multiple silences clustering at a track's end, getting progressively longer and deeper, are a specific gesture — the music departing in stages. If momentum re-establishes after each silence (returning to `0.9+`), the listener is still held even as the music withdraws. Departure and grip happening simultaneously.

---

### `weight_arc`
The track divided into segments with mean and peak energy per segment — the macro shape of where the music puts its weight. Independent from momentum: low-energy sections can maintain full resonance.

---

## Interpretation

Reading galdr output is translating metrics into what is happening in the listener's body and attention.

**Mechanical readout:**
> "momentum: 0.974 (high), pattern_lock: 0.964 (high), texture_balance: -0.518 (harmonic dominant), pressure_state: sustaining"

**Perceptual description:**
> "The track is fully locked — resonance has been running near-maximum for over five minutes without degrading. The rhythm is extremely metronomic, but this isn't rigidity — it's the steadiness of ritual, a pulse the listener can surrender to rather than track. The music is voice and harmony dominant throughout. The pressure holds rather than climbing or collapsing; the listener knows exactly where they are."

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
