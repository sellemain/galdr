# The Galdr Perception Model

Galdr models a listener's perceptual state as music plays. It is not analyzing the audio file as a static object. It is tracking how attention moves through time — how engagement builds, holds, breaks, and dissolves.

---

## The Listener

The central model is a listener. Not a microphone, not a signal analyzer — a listener who starts outside the music, gets pulled in, holds attention, and eventually releases.

This listener's attention behaves like a flywheel: slow to start, resistant to change once spinning, slow to stop. It doesn't snap to a beat or lock to a melody instantly. It builds. Once built, it holds through gaps, silences, and variations. It dissipates slowly.

Every metric galdr emits describes some aspect of this flywheel — how fast it's spinning, how it's changing, what the music is made of, and how the listener is positioned relative to what's being heard.

**In the output:** the flywheel's spin rate is the `momentum` field (0.0–1.0). The events `listener_locked` (momentum crosses above 0.8) and `listener_floating` (momentum drops below 0.2) mark the threshold moments when the flywheel engages or releases.

---

## Core Metrics

### `momentum`
The flywheel's current spin rate. 0.0 = not yet engaged. 1.0 = fully locked.

- `0.000` — pre-engagement, or the track has ended
- `0.400–0.600` — building, or recovering after a structural break
- `0.850–0.979` — locked in; the flywheel is sustaining

**What it does not mean:** high momentum is not a quality judgment. It measures the grip, not the value of what's gripping. Music can hold attention and be dull, transcendent, uncomfortable, or beautiful — momentum doesn't distinguish.

Momentum holds through short silences (under ~2 seconds) and dips but recovers through medium ones. Only sustained silence or structural breakdown causes it to fall and require re-engagement.

---

### `breath`
The direction of energy change at each moment. Positive = expanding (louder, brighter, more energetic). Negative = contracting. Near zero = sustained.

Breath oscillating between positive and negative means the music is pulsing, not collapsing. A high-momentum track with negative breath is exhaling — the flywheel is still locked. Negative breath is not bad.

---

### `hp_balance`
The ratio of harmonic to percussive energy at each moment. Negative = harmonic/vocal dominant. Positive = percussive dominant.

Track how hp_balance moves through time. A track with consistently deep negative values (-0.7 to -0.9) is voice- or melody-dominated throughout. The deepest negative values often occur in moments when only a single voice remains.

---

### `pattern_lock`
How metronomically regular the rhythmic pattern has been over recent time. High = very consistent pulse. Low = free, rubato, or rhythmically complex.

**What it does not mean:** high pattern_lock does not mean the music is mechanical or rigid. In ritual and ceremonial music, extreme regularity is intentional and load-bearing — it is what allows the listener to stop tracking the beat and go somewhere else. A drum machine and a ceremonial circle drum can both produce pattern_lock > 0.90. Context determines which.

---

### `temperament_alignment`
How closely the pitches align with equal temperament (standard 12-tone Western scale). High = standard equal temperament. Low = closer to the harmonic series (just intonation, natural tuning).

**What it does not mean:** low temperament_alignment does not mean the music is out of tune. Folk traditions, overtone singing, and ancient ritual music frequently sit at low temperament_alignment. This is a feature, not a flaw — the music uses natural frequency relationships rather than the convention of the equal-tempered scale.

Low temperament_alignment often co-occurs with deeply negative hp_balance. Voice-dominated music that uses natural tuning will show both.

---

### `disruption` / `pattern_lock`
Moment-to-moment deviation from the predicted next state. Low disruption = the music is doing what the listener expects. High disruption = structural break, sudden shift, or unexpected event. pattern_lock = 1.0 - disruption: high pattern_lock means expectations are consistently met.

High mean_pattern_lock across a whole track is not "boring" — it may mean the music is extremely consistent and the listener always knows where they are. This is what enables deep engagement in ritual and meditative music. The consistency is what makes the depth possible.

---

### Silences
Detected periods of significant silence with start time, duration, and depth in dB. -80dB is true silence. -40dB is perceptually very quiet but not empty.

**Dissolution patterns:** multiple silences clustered at the end of a track, getting progressively longer and deeper, are a specific gesture — the music is departing in stages. Watch the momentum *between* the silences: if the flywheel re-locks after each one (momentum returns to 0.9+), the music is still holding the listener even as it withdraws. The departure and the grip are happening simultaneously.

---

## Energy Arc

The `energy_arc` field divides the track into segments and shows mean and peak energy per segment. This is the macro shape of the track — where the music puts its weight.

Pair it with momentum: a track can have low-energy sections that maintain full listener engagement. The two axes are independent.

---

## What Good Interpretation Looks Like

Reading galdr output is not narrating numbers. It is translating the metrics into a description of what is happening in the listener's body and attention.

**Mechanical readout:**
> "momentum: 0.974 (high), pattern_lock: 0.964 (high), hp_balance: -0.518 (harmonic dominant)"

**Perceptual description:**
> "The track is fully locked — the flywheel has been running at near-maximum for over five minutes without degrading. The rhythm is extremely metronomic, but this isn't rigidity — it's the steadiness of ritual, a pulse the listener can surrender to rather than track. The music is voice and harmony dominant throughout. What little disruption exists is background noise; the listener knows exactly where they are."

The difference: the second version interprets. It situates the numbers in listening experience.

---

## Worked Example: Helvegen — Wardruna

*7 minutes 6 seconds. The track opens with 7 seconds of true silence. When sound arrives, momentum stays at 0.000 for the first 30 seconds of actual music — typical tracks lock in 4–7 seconds. Helvegen takes thirty. Then between t=30s and t=60s, the flywheel locks: momentum jumps from 0.000 to 0.974 and holds there, between 0.96–0.98, for five and a half minutes.*

*At the end, seven silences cluster. Each one longer and deeper than the last: 1.0s → 1.2s → 0.5s → 0.5s → 1.5s → 1.5s → 9.5s, descending from -60dB to -80dB. After each silence, the voice returns. And the flywheel re-locks — momentum returns above 0.93 each time. The listener keeps re-engaging because the music keeps coming back at full conviction. Until the seventh silence, when the voice doesn't return.*

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
