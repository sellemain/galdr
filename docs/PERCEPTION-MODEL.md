# The Galdr Perception Model

Galdr models a listener's perceptual state as music plays. It is not analyzing the audio file as a static object. It is tracking how attention moves through time — how engagement builds, holds, breaks, and dissolves.

---

## The Listener

The central model is a listener. Not a microphone, not a signal analyzer — a listener who starts outside the music, gets pulled in, holds attention, and eventually releases.

This listener's attention behaves like a resonant system. It takes time to reach full amplitude — you can't force it to ring. Once resonating, it sustains efficiently: small gaps, brief silences, and slight variations don't break the coupling. When excitation stops, it rings down slowly. The music either finds the listener's frequency, or it doesn't.

Every metric galdr emits describes some aspect of this resonance — how deeply the listener is ringing, how stable the coupling is, what the music is made of, and how the listener is positioned relative to what's being heard.

**In the output:** resonance depth is the `momentum` field (0.0–1.0). The events `listener_locked` (momentum crosses above 0.8) and `listener_floating` (momentum drops below 0.2) mark the threshold moments when resonance engages or releases.

---

## Core Metrics

### `momentum`
The listener's current resonance depth. 0.0 = not yet resonating. 1.0 = fully locked.

- `0.000` — pre-resonance, or the track has ended
- `0.400–0.600` — building, or recovering after a structural break
- `0.850–0.979` — locked in; resonance is sustaining

**What it does not mean:** high momentum is not a quality judgment. It measures the grip, not the value of what's gripping. Music can hold attention and be dull, transcendent, uncomfortable, or beautiful — momentum doesn't distinguish.

Momentum holds through short silences (under ~2 seconds) and dips but recovers through medium ones. Only sustained silence or structural breakdown causes it to fall and require the listener to find the frequency again.

---

### `breath`
The direction of energy change at each moment. Positive = expanding (louder, brighter, more energetic). Negative = contracting. Near zero = sustained.

Breath oscillating between positive and negative means the music is pulsing, not collapsing. A high-momentum track with negative breath is exhaling — the resonance is still locked. Negative breath is not bad.

---

### `hp_balance`
The ratio of harmonic to percussive energy at each moment. Negative = harmonic/vocal dominant. Positive = percussive dominant.

Track how hp_balance moves through time. A track with consistently deep negative values (-0.7 to -0.9) is voice- or melody-dominated throughout. The deepest negative values often occur in moments when only a single voice remains.

---

### `pattern_lock`
Two things at once: how metronomically regular the rhythmic pulse has been, and how consistently the music has met the listener's expectations. `pattern_lock = 1.0 - disruption` — high pattern_lock means both a steady beat and no structural surprises. Low pattern_lock means either an irregular pulse (rubato, free time) or a sudden structural break.

**What it does not mean:** high pattern_lock is not rigidity. In ritual and ceremonial music, extreme regularity is intentional and load-bearing — it is what allows the listener to stop tracking the beat and go somewhere else. A drum machine and a ceremonial circle drum can both produce pattern_lock > 0.90. Context determines which.

High mean_pattern_lock across a whole track is not "boring." It may mean the music is so consistent that the listener never has to reorient — and that consistency is what makes depth possible.

---

### `temperament_alignment`
How closely the pitches align with equal temperament (standard 12-tone Western scale). High = standard equal temperament. Low = closer to the harmonic series (just intonation, natural tuning).

**What it does not mean:** low temperament_alignment does not mean the music is out of tune. Folk traditions, overtone singing, and ancient ritual music frequently sit at low temperament_alignment. This is a feature, not a flaw — the music uses natural frequency relationships rather than the convention of the equal-tempered scale.

Low temperament_alignment often co-occurs with deeply negative hp_balance. Voice-dominated music that uses natural tuning will show both.

---

### Silences
Detected periods of significant silence with start time, duration, and depth in dB. -80dB is true silence. -40dB is perceptually very quiet but not empty.

**Dissolution patterns:** multiple silences clustered at the end of a track, getting progressively longer and deeper, are a specific gesture — the music is departing in stages. Watch the momentum *between* the silences: if resonance re-establishes after each one (momentum returns to 0.9+), the music is still holding the listener even as it withdraws. The departure and the grip are happening simultaneously.

---

## Energy Arc

The `energy_arc` field divides the track into segments and shows mean and peak energy per segment. This is the macro shape of the track — where the music puts its weight.

Pair it with momentum: a track can have low-energy sections that maintain full listener resonance. The two axes are independent.

---

## What Good Interpretation Looks Like

Reading galdr output is not narrating numbers. It is translating the metrics into a description of what is happening in the listener's body and attention.

**Mechanical readout:**
> "momentum: 0.974 (high), pattern_lock: 0.964 (high), hp_balance: -0.518 (harmonic dominant)"

**Perceptual description:**
> "The track is fully locked — resonance has been running near-maximum for over five minutes without degrading. The rhythm is extremely metronomic, but this isn't rigidity — it's the steadiness of ritual, a pulse the listener can surrender to rather than track. The music is voice and harmony dominant throughout. What little disruption exists is background noise; the listener knows exactly where they are."

The difference: the second version interprets. It situates the numbers in listening experience.

---

## Worked Example: Helvegen — Wardruna

*7 minutes 6 seconds. The track opens with 7 seconds of true silence. When sound arrives, momentum stays at 0.000 for the first 30 seconds of actual music — typical tracks lock in 4–7 seconds. Helvegen takes thirty. Then between t=30s and t=60s, resonance locks: momentum jumps from 0.000 to 0.974 and holds there, between 0.96–0.98, for five and a half minutes.*

*At the end, seven silences cluster. Each one longer and deeper than the last: 1.0s → 1.2s → 0.5s → 0.5s → 1.5s → 1.5s → 9.5s, descending from -60dB to -80dB. After each silence, the voice returns. And resonance re-establishes — momentum returns above 0.93 each time. The listener keeps re-engaging because the music keeps coming back at full conviction. Until the seventh silence, when the voice doesn't return.*

*The road to Hel is not a fall. It is a series of departures and returns where the departures gradually win.*

---

## Anti-Patterns

**Don't narrate the metrics.** "momentum: 0.974 (high), pattern_lock: 0.964 (high)" is not analysis.

**Don't treat high pattern_lock as rigidity.** High pattern_lock means consistent rhythm. In ritual music, that consistency is the point.

**Don't treat low temperament_alignment as deficiency.** It means a different tuning system, not a flawed one.

**Don't treat negative breath as failure.** A track breathing out is exhaling. Check momentum first.

**Don't assign absolute quality to any single metric.** Meaning lives in the relationships between metrics, not in individual values.

---

## The Question to Ask

After reading any galdr output:

**What is this music doing to the listener, and how does the music accomplish that?**

The metrics are evidence. The answer is a description of attention, body, and time.
