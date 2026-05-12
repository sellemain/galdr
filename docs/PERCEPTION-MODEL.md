# The Galdr Perception Model

Galdr models a listener's perceptual state as music plays — not the audio file as a static object, but how attention moves through time. How engagement builds, holds, breaks, and dissolves.

Galdr does not run an LLM during analysis. It is the deterministic listening front-end: it turns audio into listener-state traces that downstream AI agents, scripts, or humans can interpret.

---

## The Listener

The central model is a listener who starts outside the music, gets pulled in, holds attention, and eventually releases. Attention behaves like a resonant system: it takes time to reach full amplitude, sustains efficiently once coupled, and rings down slowly when excitation stops. The music either finds the listener's frequency, or it doesn't.

Every metric galdr emits describes some aspect of this resonance.

---

## Metric Vocabulary

Galdr keeps three layers separate:

| Field | Display name | Prose meaning |
|---|---|---|
| `attention` | Attention | the music has hold of attention |
| `pattern` | Pattern | the music keeps carried time intact |
| `pulse` | Pulse | the measured pulse is stable |
| `body` | Body | the pulse takes the body, not just the ear |
| `body_capture` | Body capture | the rhythm seizes motor attention, comfortable or not |
| `body_comfort` | Body comfort | the captured body can settle into the pulse |
| `groove_comfort` | Groove comfort | the pulse gives the body a usable seat |
| `accent_phase_drift` | Accent phase drift | local attacks lean around the beat grid |
| `metric_tension` | Metric tension | a stable pulse is pressured by competing grids |
| `expectation_debt` | Expectation debt | unresolved local tension is being carried forward |
| `release_force` | Release force | accumulated pressure is being paid back or opened |
| `section_gravity` | Section gravity | the moment feels like an anchor rather than passage material |
| `surface_density` | Surface density | local event-load/detail is high or sparse |
| `weight` | Weight | weight, drag, suspension, or room-pressure arrives |
| `weight_arc` | Weight arc | where the track puts macro weight over time |
| `pressure` | Pressure | pressure builds, releases, sustains, or empties |
| `texture` | Texture | weight sits in sustained tone or percussive attack |
| `harmonic_pull` | Harmonic pull | the tonal field moves, pulls, or refuses to settle |
| `chroma_motion` | Chroma motion | harmonic color changes over time |
| `tonal_anchor` | Tonal anchor | the local key center holds or loosens |
| `pitch_grid` | Pitch grid | pitch sits inside or outside equal-tempered grid space |
| `interval_coherence` | Interval coherence | pitch classes organize into stable relations |
| `overtone_fit` | Overtone fit | the sound locks onto natural overtone relationships |
| `overtone_density` | Overtone density | the overtone surface is dense, bright, or sparse |
| `foreground_line` | Foreground line | a foreground pitched line is trackable |

Field names are schema. Display names are UI and documentation. Prose meaning is what an agent should write instead of reciting fields.

---

## Core Metrics

### `attention`
Current resonance depth. `0.0` = not yet resonating. `1.0` = fully locked.

Implementation evidence: rolling beat regularity and beat density over an 8-second window. Regular intervals with enough beat evidence produce high attention; missing, sparse, or irregular beat evidence lowers it.

Not a quality judgment. High attention measures the grip, not the value of what's gripping. Holds through short silences (<~2s); falls and requires re-entry after sustained silence or structural breakdown.

---

### `pressure`
Direction of heard pressure change. Positive = building. Negative = releasing. Near zero = sustaining.

Implementation evidence: short-term EBU R128/LUFS loudness, smoothed over 20 seconds, then differenced into a normalized pressure-motion curve. That makes it closer to perceived pressure than raw RMS energy: whether the music comes forward, withdraws, or holds its place in the listener's attention.

LUFS is implementation evidence, not listening language. In prose, translate it:

- rising loudness → pressure comes forward, gathers, fills the room
- falling loudness → pressure releases, loosens, drops away
- stable loudness → pressure holds, sustains, keeps the listener coupled
- loudness floor / silence → the structure empties, departs, or stops carrying attention

Do not write "LUFS rises from -27 to -20" in experience prose. That belongs in debugging or regression notes. A high-attention track with negative pressure is exhaling — resonance is still locked. Negative pressure is not failure.

---

### `texture`
Display name: **Texture**. Where the track's weight sits between sustained harmonic sound and percussive impact. Negative = harmonic/vocal dominant. Positive = percussive dominant.

Implementation evidence: harmonic/percussive source separation energy, smoothed at the perception-stream hop. Very low total energy is treated as neutral rather than forcing a false texture claim.

Deep negative values often feel like voice, drone, strings, choir, or tonal atmosphere taking over the room. Strong positive values feel like strike, groove, attack, or drum-forward physicality. The deepest negative values typically occur when only a single voice remains.

---

### `body_capture`, `body_comfort`, and `groove_comfort`
`body_capture` and `body_comfort` split two things that used to collapse into one Body reading.

`body_capture` measures whether the rhythm has seized motor attention. It can be high in dance music, funk, metal, minimalism, ritual music, or anything where the pulse takes the body. It does not mean the listener is comfortable.

`body_comfort` measures whether the captured body can settle. A pocket groove can have high capture and high comfort. Punishing, stiff, pressurized, or hostile music can have high capture and low comfort. That distinction matters: Meshuggah and James Brown may both seize the body, but they do not give the body the same kind of seat.

`groove_comfort` is the local stream form of that comfort reading. It blends body-lock and pattern, then reduces comfort when pressure and accent drift make the groove harder to inhabit.

In prose, use capture language for seizure and motor grip; use comfort language for pocket, ease, seat, bracing, or withheld comfort.

---

### `accent_phase_drift` and `metric_tension`
`accent_phase_drift` measures how much local attacks spread around the beat grid instead of landing in one stable phase. High drift can mean accents are leaning, walking around the barline, or creating local grid friction. It is not proof of a notated polyrhythm.

`metric_tension` is a track-level estimate of competing metric pressure. It looks for alternate tempo or periodicity evidence that does not collapse into simple half-time or double-time readings. Strong values mean the listener can feel the grid while another cycle leans against it.

This is deliberately conservative language. `metric_tension` is not a full polyrhythm detector. Treat it as cross-rhythm pressure evidence. If the dominant experience is body/pressure lock, the prompt may keep metric tension as a technical underlayer rather than making it the headline.

---

### `expectation_debt` and `release_force`
`expectation_debt` is a listener-state accumulator. It rises when disruption, pressure, accent drift, or low groove comfort carry unresolved tension forward. It falls when release behavior pays some of that debt back.

`release_force` measures how consequential a local drop, exhale, or opening is, based on negative pressure and the immediately prior debt. A quieting moment with little prior debt may be audible but low-release; a drop after prolonged pressure can feel earned.

These are not claims about composer intent. They are evidence about whether the listener is being asked to keep carrying expectation, and whether a release has enough prior pressure behind it to matter.

---

### `section_gravity` and `surface_density`
`section_gravity` measures whether a moment feels like an anchor rather than passage material. It combines local pattern, attention, body-lock, and beat-grid stability. High section gravity is not automatically a chorus or formal section; it means the listener has a floor.

`surface_density` measures local detail-load independent of raw loudness. High density means busy, particulate, detailed, or texturally loaded. Low density means sparse, smooth, sustained, or wall-like. Density is not heaviness: a loud sustained wall can be low-density, and a quiet texture can be dense.

---

### `pattern`
How reliably the music keeps its pattern intact. `pattern = 1.0 - disruption`. High = steady pulse, stable texture, and few structural surprises. Low = irregular pulse, sudden break, or sharp textural reorientation.

`disruption` is a weighted blend of three expectation failures:

- **Beat disruption** (`40%`) — recent beat timing predicts the next beat, but the beat arrives late/early or does not arrive.
- **Spectral disruption** (`35%`) — spectral flux rises above its local average; the timbral surface changes faster than the surrounding context.
- **Energy disruption** (`25%`) — RMS energy jumps or drops faster than its local trend.

The component scores are exposed on pattern-break events as `beat`, `spectral`, and `energy`, so a break can be read as rhythmic, textural, dynamic, or compound.

High pattern is not rigidity. In ritual and ceremonial music, extreme regularity is intentional — it allows the listener to stop tracking the beat and go somewhere else. High mean_pattern across a track doesn't mean boring; it may mean the music is consistent enough to allow depth.

---

### `pitch_grid`
How cleanly the harmony sits inside familiar equal-tempered pitch space. High values feel centered, resolved, and conventionally tuned. Low values can feel smeared, bent, folk-natural, microtonal, or intentionally outside the grid.

Implementation evidence: concentration of chroma energy across pitch classes. This is an equal-tempered chroma measure, so use care with modal, folk-natural, microtonal, or noisy material.

Low pitch_grid is not out-of-tune. Folk traditions, overtone singing, and ritual music frequently sit here by design. Often co-occurs with deeply negative texture.

---

### `interval_coherence`
How concentrated the pitch content is around simple, stable harmonic relationships. High values feel fused, settled, and easy for the ear to organize. Low values feel more spread, harmonically complex, or ambiguous.

Implementation evidence: active chroma pitch-class pairs are scored against simple just-intonation interval relationships, weighted by chroma energy. This is harmony-side evidence: it looks at pitch-class organization, not the raw overtone spectrum.

---

### `harmonic_pull`
How much the harmony is pulling, shifting, or refusing to settle over time. High values mean the tonal field is moving quickly or uneasily; low values mean it is anchored, suspended, or staying in one harmonic place.

Implementation evidence: velocity through smoothed tonnetz space, normalized across the track. It measures harmonic motion/pull, not emotional distress.

Tension is not automatically negative. A track can use harmonic pull as propulsion, unease, color, or release preparation.

---

### `overtone_fit`
How strongly the sound itself locks onto natural overtone relationships. High values feel pure, fused, bell-like, vocal, or resonant. Low values feel noisier, rougher, more inharmonic, or more textural.

Implementation evidence: overtone analysis around detected fundamentals, comparing observed partials to ideal harmonic positions and energy. This is overtone-side evidence: it looks at the spectrum around the detected fundamental, not the chord progression.

---

### Silences
Detected periods of significant silence with start time, duration, and depth in dB. `-80dB` = true silence. `-40dB` = perceptually quiet but not empty.

Multiple silences clustering at a track's end, getting progressively longer and deeper, are a specific gesture — the music departing in stages. If attention re-establishes after each silence (returning to `0.9+`), the listener is still held even as the music withdraws. Departure and grip happening simultaneously.

---

### `weight_arc`
Display name: **Weight arc**. The track divided into segments with mean and peak energy per segment — the macro shape of where the music puts its weight. Independent from attention: low-energy sections can maintain full resonance.

---

## Metric Evidence Summary

| Metric | Primary evidence | Listener-state reading |
|---|---|---|
| `attention` | Beat regularity × beat density in rolling windows | How strongly attention is carried forward |
| `pressure` / `pressure_state` | Short-term LUFS movement | Whether pressure builds, releases, sustains, or empties |
| `pattern` | `1.0 - disruption`; disruption = beat + spectral + energy expectation failures | How intact the musical pattern feels |
| `body_capture` | Local body-lock before comfort penalties | Whether rhythm seizes motor attention |
| `body_comfort` / `groove_comfort` | Body capture reduced by pressure and accent phase drift | Whether the captured body can settle into the pulse |
| `accent_phase_drift` | Circular phase dispersion of onsets against beat positions | Whether attacks sit on the grid or lean around it |
| `metric_tension` | Trusted pulse plus competing non-simple tempo/grid evidence | Whether the pulse is being pressured by another metric layer |
| `expectation_debt` | Accumulated disruption, pressure, drift, and low comfort | Whether unresolved expectation is being carried forward |
| `release_force` | Negative pressure weighted by prior debt | Whether a drop or opening pays back accumulated pressure |
| `section_gravity` | Attention, pattern, body-lock, and grid stability | Whether a moment feels like a local anchor |
| `surface_density` | Onset density plus spectral/energy surface motion | How busy or sparse the surface feels |
| `texture` / Texture | Harmonic/percussive separated energy | Whether weight sits in sustained tone or attack |
| `pitch_grid` | Chroma concentration in equal-tempered pitch classes | How centered or outside-the-grid the pitch world feels |
| `interval_coherence` | Chroma interval relationships weighted by energy | How easily pitch classes organize into stable relations |
| `harmonic_pull` | Tonnetz velocity | How much the harmonic field pulls or turns |
| `chroma_motion` | Cosine distance between adjacent chroma frames | How quickly harmonic color changes |
| `tonal_anchor` | Dominance of detected tonic pitch class | How anchored the local key center feels |
| `overtone_fit` | Overtone partial alignment around detected fundamentals | How fused or inharmonic the sound itself feels |
| `overtone_density` | Upper-partial energy | How dense or bright the overtone surface is |
| `foreground_line` | pYIN voiced probability over time | How strongly a foreground pitched line is present |
| `silences` | dB-floor intervals plus recovery attention | Where the structure truly empties and whether it re-locks |

---

## How to Read the Data

Galdr writes two kinds of evidence: **summary values** and **stream values**.

Summary values (`mean_attention`, `mean_pattern`, `mean_harmonic_pull`, and similar `mean_*` fields) describe the track's overall tendency. They are useful for comparison, cataloging, and first-pass orientation. They are not the listening experience by themselves. A track can have a high mean value because it stays there for six minutes, or because it repeatedly surges and collapses. The mean tells you where to look; the stream tells you what happened.

Stream values are time-indexed listener-state samples. Read them as motion:

- **rising `attention`** → the listener is being pulled into the structure
- **stable high `attention`** → attention is locked and being carried
- **falling `attention`** → the structure is losing its grip or entering a real gap
- **high `pattern`** → expectation is being honored; the pattern is intact
- **low `pattern`** → rhythm, texture, or energy has violated expectation
- **positive `pressure`** → pressure is coming forward
- **negative `pressure`** → pressure is releasing
- **negative `texture`** → sustained tone, voice, drone, or harmony dominates
- **positive `texture`** → strike, groove, attack, or percussion dominates

Events are narrative anchors derived from the stream. Macro events (`attention_arrives`, `body_lock_arrives`, `surface_hardens`, `weight_arrives`) describe major state changes. Phrase events (`phrase_lift`, `phrase_drop`, `ornamental_flash`) describe smaller local gestures inside a stable state. Events are not a checklist to recite. They are signposts for where prose should slow down and listen more closely.

The right reading order is:

1. **Start with the summary** — what kind of track is this overall?
2. **Read the stream around changes** — when does the listener lock, release, harden, or re-enter?
3. **Use events as anchors** — which moments deserve language?
4. **Translate relationships, not fields** — meaning comes from combinations.

Examples:

- High `attention` + high `pattern` + steady `pressure` = the track has the listener and is holding them without strain.
- High `attention` + low `pattern` = the listener is still gripped, but the surface is unstable or disruptive.
- Negative `texture` + high `overtone_fit` = sustained pitched material is carrying the experience through resonance rather than impact.
- Falling `pressure` + high `attention` = the pressure is releasing, but attention has not let go.
- Silence + fast attention recovery = the music empties briefly, then reclaims the listener.

Treat field names as implementation labels. In public prose, do not write that a track has “high `mean_foreground_line`” or “a `phrase_drop` event.” Write what those fields are evidence for: a foreground line appears; the phrase falls away; the body of the sound arrives; the pattern breaks.

---

## Interpretation

Reading galdr output is translating metrics into what is happening in the listener's body and attention.

**Mechanical readout:**
> "attention: 0.974 (high), pattern: 0.964 (high), texture: -0.518 (harmonic dominant), pressure_state: sustaining"

**Perceptual description:**
> "The track is fully locked — resonance has been running near-maximum for over five minutes without degrading. The rhythm is extremely metronomic, but this isn't rigidity — it's the steadiness of ritual, a pulse the listener can surrender to rather than track. The music is voice and harmony dominant throughout. The pressure holds rather than climbing or collapsing; the listener knows exactly where they are."

Meaning lives in the relationships between metrics, not individual values.

---

## Advisory Salience Guide

`galdr assemble` may include a **Perceptual salience guide**. This is not another analysis pass and it does not hide data. It is an advisory layer that asks: given all the measured evidence, which forces should probably lead the listening prose?

The guide has four parts:

- **Listening contract** — a compact description of the dominant listener state, such as `settled_pocket_or_groove`, `coercive_heavy_lock`, `suspended_texture_or_ambient_space`, `metric_grid_pressure`, `sparse_hook_or_minimal_grid`, or `sustained_pattern_hold`.
- **Headline forces** — the forces most likely to deserve narrative emphasis.
- **Supporting forces** — secondary evidence that shapes the read but may not be the first thing a listener feels.
- **Technical underlayer / low-confidence metrics** — real measurements that should stay visible, but should not automatically dominate the prose.

This matters because technically interesting structure is not always the felt face of the music. A track can contain metric tension while the dominant experience is heavy body capture. Ambient music can produce suspicious metric readings from weak pulse evidence; those readings should be named as low-confidence rather than turned into false claims. Conversely, groove music may be technically simple and still perceptually strong because the body is fully settled.

Use the salience guide to choose emphasis. Do not treat it as censorship. The raw metrics remain the evidence, and a downstream reader can disagree with the advisory ranking.

---

## Worked Example: Helvegen — Wardruna

7 minutes 6 seconds. The track opens with 7 seconds of true silence. When sound arrives, attention stays at `0.000` for 30 seconds — typical tracks lock in 4–7 seconds. Helvegen takes thirty. Then between t=30s and t=60s, resonance locks: attention jumps from `0.000` to `0.974` and holds between 0.96–0.98 for five and a half minutes.

At the end, seven silences cluster. Each longer and deeper: `1.0s → 1.2s → 0.5s → 0.5s → 1.5s → 1.5s → 9.5s`, descending from -60dB to -80dB. After each silence, the voice returns. Resonance re-establishes — attention returns above 0.93 each time. The listener keeps re-engaging because the music keeps coming back at full conviction. Until the seventh silence, when the voice doesn't return.

The road to Hel is not a fall. It is a series of departures and returns where the departures gradually win.

---

## The Question

**What is this music doing to the listener, and how does the music accomplish that?**

The metrics are evidence. The answer is a description of attention, body, and time.
