# galdr Metric Reference

All metrics come from `report.json` and the perception/harmony/melody/overtone stream files in `analysis/<slug>/`.

---

## Pattern Lock (`pattern_lock`)

**Range:** 0.0–1.0
**What it is:** How reliably the music keeps its pattern intact. High pattern_lock means the listener can trust the structure: the pulse, texture, and energy are not suddenly breaking away.

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
**What it is:** How strongly attention is being carried forward by the track. Not speed, loudness, or quality — grip. High momentum means the music keeps the listener coupled even through quiet or sparse passages.

| Value | Meaning |
|-------|---------|
| >0.90 | Rare sustained pull. Track barely lets listener breathe. |
| 0.80–0.90 | Strong. Most engaging passages. |
| 0.60–0.80 | Fluctuating. Energy ebbs and flows. |
| <0.60 | Low continuity. Listener may disengage. |

After a silence, momentum re-locking above 0.93 signals the listener has been re-engaged. Multiple re-lock events with deepening silences = structured withdrawal (Helvegen pattern).

---

## Pulse Stability (`pulse_stability`)

**Range:** 0.0–1.0
**What it is:** How steady the underlying pulse feels. Orthogonal to metric complexity — a 7/8 piece can have perfect pulse stability if the body can still trust where the beat lives.

| Value | Meaning |
|-------|---------|
| >0.96 | Clockwork. Ritual, electronic, or highly disciplined performance. |
| 0.90–0.96 | Tight but human. Most performed music. |
| 0.80–0.90 | Loose. Jazz feel, rubato, or intentional groove. |
| <0.80 | Irregular. Experimental or very free. |

High pulse_stability + complex time signature (5/8, 7/8) = metric complexity is orthogonal to pulse stability.

---

## Texture Balance (`texture_balance`, `mean_texture_balance`)

**Range:** -1.0 to 1.0
**What it is:** Where the track's weight sits between sustained harmonic sound and percussive impact. Negative values feel more tonal, vocal, droning, or atmospheric; positive values feel more struck, rhythmic, attack-heavy, or drum-forward.

| Value | Meaning |
|-------|---------|
| < -0.5 | Strongly harmonic. Warm, tonal, sustained. Choirs, strings, pads. |
| -0.5 to -0.2 | Harmonic dominant with texture. |
| -0.2 to 0.2 | Balanced. Mixed character. |
| 0.2 to 0.5 | Percussive with harmonic content. |
| > 0.5 | Strongly percussive. Drum-forward, rhythmic emphasis. |

Deepening negative texture_balance across a track = harmonic weight increasing (dissolution, closing, ending accumulation).

---

## Breath / Heard Pressure (`breath`, `pressure_state`, `breath_balance`)

**Shape:** Stream fields plus three summary percentages — building / releasing / sustaining — summing to 100%.
**What it is:** The heard-pressure shape of the track. As of v0.2.1, breath is derived from short-term LUFS rather than raw RMS energy so it tracks whether pressure comes forward, holds, or withdraws.

Stream fields:
- `breath` — normalized pressure movement; positive builds, negative releases, near-zero sustains
- `pressure_state` — `building`, `releasing`, `sustaining`, or `silence`
- `loudness_lufs` — short-term loudness evidence; use for debugging/comparison, not prose
- `breath_lufs_delta` — short-term pressure delta evidence
- `loudness_silence` — loudness-floor silence marker

| Pattern | Meaning |
|---------|---------|
| ~33/33/33 | Equilibrium. Pressure gives and takes evenly. |
| Heavy building (>45%) | Accumulating track. Pressure keeps coming forward. |
| Heavy releasing (>45%) | Withdrawal dominates, even if the track still feels held. |
| Near-zero sustain (<10%) | No held pressure — constant motion up or down. |
| Heavy sustain (>40%) | Stable hold. The music keeps the listener coupled instead of continually climbing or falling. |

Translation rule: do not write raw LUFS values in experience prose. Write what they mean: pressure comes forward, fills the room, holds, loosens, drops away, empties, or stops carrying attention. LUFS belongs in regression notes and debugging.

Near-symmetry between building and releasing indicates the track takes exactly as much as it gives — rare and structurally notable.

---

## Tuning Alignment (`mean_tuning_alignment`)

**Range:** 0.0–1.0
**What it is:** How cleanly the harmony sits inside familiar equal-tempered pitch space. Higher values feel centered, resolved, and conventionally tuned; lower values can feel bent, smeared, folk-natural, microtonal, or intentionally outside the grid.

Do not read low tuning_alignment as a defect by itself. Some traditions deliberately live between the standard pitch bins. Treat it as evidence about tuning world, not as a quality score.

---

## Harmonic Series Consonance (`mean_harmonic_series_consonance`)

**Range:** 0.0–1.0
**What it is:** How concentrated the pitch content is around simple, stable harmonic relationships. Higher values feel fused, settled, and easy for the ear to organize; lower values feel more spread, complex, or harmonically ambiguous.

This is harmony-side evidence. It describes pitch-class organization, not the raw overtone spectrum.

---

## Harmonic Tension (`mean_harmonic_tension`)

**Range:** 0.0–1.0
**What it is:** How much the harmony is pulling, shifting, or refusing to settle over time. High values feel like motion, pressure, searching, or harmonic unease; low values feel anchored, suspended, static, or resolved.

| Value | Meaning |
|-------|---------|
| <0.25 | Consonant, settled. Easy listening, tonal resolution. |
| 0.25–0.40 | Mild tension. Character without instability. |
| 0.40–0.55 | Significant tension. Unresolved, complex harmonically. |
| >0.55 | High dissonance. Deliberately unsettled. |

Catalog note: Teardrop (Massive Attack) has the highest cataloged tension at 0.421.

---

## Chroma Flux (`mean_chroma_flux`)

**Range:** 0.0–1.0
**What it is:** How quickly the harmonic color changes from one moment to the next. High values mean the harmonic surface is restless or actively turning; low values mean the color is steady, droning, or slowly evolving.

---

## Tonal Stability (`mean_tonal_stability`)

**Range:** 0.0–1.0
**What it is:** How strongly the current window stays anchored to its tonal center. High values feel grounded or centered; low values feel wandering, suspended, or harmonically diffuse.

---

## Major/Minor Balance (`mean_major_minor`)

**Range:** -1.0 to 1.0
**What it is:** Whether the harmony leans dark/minor, bright/major, or stays between them. Negative values lean minor; positive values lean major; near-zero can mean modal ambiguity, mixture, or neither color dominating.

---

## Harmonic Series Fit (`mean_harmonic_series_fit`)

**Range:** 0.0–1.0
**What it is:** How strongly the sound itself locks onto natural overtone relationships. High values feel pure, fused, bell-like, vocal, or resonant; low values feel noisier, rougher, more inharmonic, or more textural.

This is overtone-side evidence. It describes spectral structure around the detected fundamental, not the chord progression.

---

## Overtone Richness (`mean_overtone_richness`)

**Range:** 0.0–1.0
**What it is:** How many upper harmonics are present in the sound. High richness feels dense, bright, saturated, or full of upper partials; low richness feels simpler, darker, hollower, or more sine-like.

---

## Inharmonicity (`mean_inharmonicity`)

**Unit:** cents
**What it is:** How far the overtones drift from ideal harmonic positions. Higher values feel rougher, noisier, more metallic, more bell-like in the unstable sense, or more textural. Lower values feel cleaner and more tonally fused.

---

## Vocal Presence (`mean_vocal_presence`)

**Range:** 0.0–1.0
**What it is:** How much foreground pitched voice is carrying the track. High values mean voice or lead pitch is structurally present; low values mean the voice is absent, textural, buried, or not the main carrier.

| Value | Meaning |
|-------|---------|
| <0.05 | Minimal / drone-like. Voice is texture, not foreground. |
| 0.05–0.15 | Voice present but mixed into the ensemble. |
| 0.15–0.30 | Clear vocal lead. |
| >0.30 | Voice dominates the mix. |

Low vocal presence + high texture_balance negative = pure harmonic texture. High presence + descending melody = voice-forward with falling contour (often resignation/descent arc).

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
**What it is:** The average shape of the foreground pitched line: whether it rises, falls, or holds its ground over time.

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
