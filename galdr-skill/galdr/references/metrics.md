# galdr Metric Reference

All metrics come from `report.json` and the perception/harmony/melody/overtone stream files in `analysis/<slug>/`.

---

## Pattern Lock (`pattern_lock`)

**Range:** 0.0–1.0  
**What it is:** 1.0 minus disruption. How sustained and predictable the listener's engagement is.

| Value | Meaning |
|-------|---------|
| 0.96–1.0 | Exceptional hold. Listener rarely disrupted. Ritual, minimalist, or tightly composed. |
| 0.90–0.96 | Strong hold. Some variation but listener remains locked. Most engaging tracks. |
| 0.80–0.90 | Moderate disruption. Energy varies meaningfully. |
| <0.80 | Frequent disruption. Chaotic, experimental, or fragmentary. |

**Pattern breaks** are the moments where pattern_lock drops suddenly. Check `pattern_breaks` in report.json for timestamps, intensity, and component breakdown (beat/spectral/energy).

---

## Momentum (`momentum`, `mean_momentum`)

**Range:** 0.0–1.0  
**What it is:** Continuity of listening experience — not speed or rhythm, but whether the forward motion holds. Tracks continuity frame-to-frame.

| Value | Meaning |
|-------|---------|
| >0.90 | Rare sustained pull. Track barely lets listener breathe. |
| 0.80–0.90 | Strong. Most engaging passages. |
| 0.60–0.80 | Fluctuating. Energy ebbs and flows. |
| <0.60 | Low continuity. Listener may disengage. |

After a silence, momentum re-locking above 0.93 signals the listener has been re-engaged. Multiple re-lock events with deepening silences = structured withdrawal (Helvegen pattern).

---

## Beat Regularity (`beat_regularity`)

**Range:** 0.0–1.0  
**What it is:** Metronomic consistency of the pulse. Orthogonal to metric complexity — a 7/8 piece can have perfect beat regularity.

| Value | Meaning |
|-------|---------|
| >0.96 | Clockwork. Ritual, electronic, or highly disciplined performance. |
| 0.90–0.96 | Tight but human. Most performed music. |
| 0.80–0.90 | Loose. Jazz feel, rubato, or intentional groove. |
| <0.80 | Irregular. Experimental or very free. |

High beat_regularity + complex time signature (5/8, 7/8) = metric complexity is orthogonal to pulse stability.

---

## HP Balance (`hp_balance`, `mean_hp_balance`)

**Range:** -1.0 to 1.0  
**What it is:** Harmonic vs. percussive energy balance. Negative = harmonic dominant. Positive = percussive dominant.

| Value | Meaning |
|-------|---------|
| < -0.5 | Strongly harmonic. Warm, tonal, sustained. Choirs, strings, pads. |
| -0.5 to -0.2 | Harmonic dominant with texture. |
| -0.2 to 0.2 | Balanced. Mixed character. |
| 0.2 to 0.5 | Percussive with harmonic content. |
| > 0.5 | Strongly percussive. Drum-forward, rhythmic emphasis. |

Deepening negative hp_balance across a track = harmonic weight increasing (dissolution, closing, ending accumulation).

---

## Breath Balance (`breath_balance`)

**Shape:** Three percentages — building / releasing / sustaining — summing to 100%.  
**What it is:** The energy shape of the track. Not overall loudness, but the distribution of rising vs. falling vs. held energy.

| Pattern | Meaning |
|---------|---------|
| ~33/33/33 | Equilibrium. Energy spread evenly — balanced tension, often in metrically complex pieces. |
| Heavy building (>45%) | Accumulating track. Energy drives forward. |
| Heavy releasing (>45%) | Descending energy dominates, even if the track feels climactic. |
| Near-zero sustain (<10%) | No held energy — constant motion up or down. |
| Heavy sustain (>40%) | Bach-like equilibrium — energy so evenly spread there's nowhere for the body to resolve. |

Near-symmetry between building and releasing (e.g. 49.6% / 50.0%) indicates the track takes exactly as much as it gives — rare and structurally notable.

---

## Mean Tension (`mean_tension`)

**Range:** 0.0–1.0  
**What it is:** Harmonic tension — dissonance and unresolved intervals averaged across the track.

| Value | Meaning |
|-------|---------|
| <0.25 | Consonant, settled. Easy listening, tonal resolution. |
| 0.25–0.40 | Mild tension. Character without instability. |
| 0.40–0.55 | Significant tension. Unresolved, complex harmonically. |
| >0.55 | High dissonance. Deliberately unsettled. |

Catalog note: Teardrop (Massive Attack) has the highest cataloged tension at 0.421.

---

## Vocal Presence (`mean_vocal_presence`)

**Range:** 0.0–1.0  
**What it is:** Proportion of signal classified as foreground voice (pitched, sustained, prominent).

| Value | Meaning |
|-------|---------|
| <0.05 | Minimal / drone-like. Voice is texture, not foreground. |
| 0.05–0.15 | Voice present but mixed into the ensemble. |
| 0.15–0.30 | Clear vocal lead. |
| >0.30 | Voice dominates the mix. |

Low vocal presence + high hp_balance negative = pure harmonic texture. High presence + descending melody = voice-forward with falling contour (often resignation/descent arc).

---

## Silences

**Structure:** Each silence has `start`, `end`, `duration`, `depth_db`, `recovery_momentum`.

| Depth | Meaning |
|-------|---------|
| -30 to -45 dB | Soft silence. Still some signal present. |
| -45 to -60 dB | Clear silence. Listener attention sharpens. |
| -60 to -75 dB | Deep silence. Structural weight. |
| < -75 dB | Near-absolute. Very deliberate. |

`recovery_momentum` after silence: if >0.93, listener re-locked. If <0.80, momentum didn't recover — track may not re-engage.

Multiple silences with deepening depth and consistent re-lock = structured withdrawal (dissolution pattern). Compressing silence intervals toward end = listener being walked to the edge.

---

## Melody Contour

**Shape:** Percentage ascending / holding / descending.  
**What it is:** Average directional tendency of the melodic line.

Heavily holding (>60%) with high vocal presence = melody uses repetition or narrow range as expressive strategy — not a limitation.  
Heavily descending + resigned lyrics = structural confirmation of emotional content.  
Ascending contour during climax = conventional arc. Descending during what sounds like climax = tension through contradiction.

---

## Pattern Breaks

Each break has: `timestamp`, `intensity` (0–1), `beat` / `spectral` / `energy` component scores.

**Intensity interpretation:**
- < 0.3: Subtle shift. Texture change rather than structural break.
- 0.3–0.6: Clear break. Listener notices.
- > 0.6: Significant disruption. Track changes character.

**Component breakdown:**
- High `beat` + low others = rhythmic disruption only
- High `spectral` = timbral/textural shift
- High `energy` = dynamic change

**Distribution:**
- Clustered at end (final 10%) = planned release
- Distributed across track = varied, episodic structure
- Single large break = pivot point; track has two halves
