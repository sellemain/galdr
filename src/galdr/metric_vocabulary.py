"""Canonical metric vocabulary for galdr public names and field names."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricVocabulary:
    """Human-readable metadata for a galdr metric."""

    field: str
    display: str
    definition: str
    evidence: str
    listener_reading: str
    prose_language: str
    caveat: str


METRICS: tuple[MetricVocabulary, ...] = (
    MetricVocabulary(
        "attention",
        "Attention",
        "How strongly the music carries attention forward.",
        "Beat regularity and beat density in rolling windows.",
        "High attention means the musical motion is easy to stay with; low attention means the track loosens, empties, or stops carrying the listener.",
        "attention gathers, holds, releases, falls away, returns, locks in, lets go",
        "Do not read this as subjective interest, quality, or liking. It is evidence about carried attention, not whether a listener enjoys the track.",
    ),
    MetricVocabulary(
        "pattern",
        "Pattern",
        "How intact the musical pattern feels over time.",
        "Inverted disruption from beat, spectral, and energy expectation failures.",
        "High pattern means the track keeps its carried time and surface logic intact; low pattern means expectation is being disrupted.",
        "pattern holds, breaks, re-forms, keeps its shape, violates expectation",
        "High pattern is not boredom or rigidity. Ritual, drone, and ceremonial music may be high-pattern because consistency is the point.",
    ),
    MetricVocabulary(
        "pulse",
        "Pulse",
        "How steady the measured pulse is when a pulse is available.",
        "Beat-interval regularity from detected beat positions.",
        "High pulse means the beat grid is stable; low pulse means the pulse is absent, ambiguous, or deliberately fluid.",
        "steady pulse, metronomic grid, organic drift, unstable pulse, no reliable pulse",
        "Low pulse is not a flaw. Some music is unpulsed, rubato, ambient, or organized by breath and surface balance instead of beat.",
    ),
    MetricVocabulary(
        "body",
        "Body",
        "Whether the pulse takes the body, not just the ear.",
        "Pulse, pulse confidence, onset density, and percussive weight.",
        "High body means the music invites motor coupling; low body means the pulse may be weak, withheld, textural, or only lightly offered.",
        "body-lock, motor pull, bodily coupling, groove arrives, pulse offered but not seized",
        "Do not equate body with tempo. Fast music can have low body; slow music can have strong body if its weight and pulse are embodied.",
    ),
    MetricVocabulary(
        "metric_tension",
        "Metric tension",
        "How much a stable pulse is being pressured by competing metric grids or accent cycles.",
        "Primary pulse confidence plus secondary tempo/periodicity candidates that do not collapse into simple half/double readings.",
        "High metric tension means the listener can feel the grid, but another cycle is leaning against it; low metric tension means the pulse is simple, absent, or uncontested.",
        "cross-rhythm pressure, hostile precision, grid conflict, accent cycle fighting the barline, stable pulse under tension",
        "This is not a full polyrhythm detector yet. It is a first-pass cross-rhythm pressure signal; confirm against musical evidence before making strong claims.",
    ),
    MetricVocabulary(
        "groove_comfort",
        "Groove comfort",
        "How easily the local pulse lets the body settle into it.",
        "Local body-lock and pattern reduced by pressure and accent phase drift.",
        "High groove comfort means the rhythm gives the body a usable seat; low comfort means the body may brace, hover, or be captured without ease.",
        "body can settle, groove seat, nervous bracing, hostile body-lock, comfort withheld",
        "This is not the same as body intensity. A track can seize the body while remaining uncomfortable.",
    ),
    MetricVocabulary(
        "body_capture",
        "Body capture",
        "How strongly the local rhythm seizes motor attention.",
        "Local body-lock score before comfort penalties.",
        "High body capture means the rhythm has the body, even if the listener is bracing rather than relaxing into it.",
        "body captured, seized pulse, motor grip, trapped in the rhythm",
        "Capture is not comfort. Hostile or punishing music can score high here while remaining hard to inhabit.",
    ),
    MetricVocabulary(
        "body_comfort",
        "Body comfort",
        "How comfortably the captured body can settle into the pulse.",
        "Body capture reduced by pressure and accent phase drift; currently mirrors groove_comfort.",
        "High body comfort means the rhythm gives the listener somewhere usable to sit; low comfort means the body is held in tension.",
        "comfortable groove, body can sit, braced body, comfort withheld",
        "Comfort is not intensity. Low comfort can be the point of the track, not an analysis failure.",
    ),
    MetricVocabulary(
        "accent_phase_drift",
        "Accent phase drift",
        "How much local attacks spread around the beat grid instead of landing in one stable phase.",
        "Circular phase dispersion of onsets between adjacent beat positions.",
        "High accent phase drift means attacks lean across or around the beat; low drift means attacks sit in a stable beat position.",
        "accents walk around the barline, attacks lean, phase drift, grid friction, off-axis strikes",
        "This is a local onset/beat-grid signal, not proof of a notated polyrhythm.",
    ),
    MetricVocabulary(
        "expectation_debt",
        "Expectation debt",
        "How much unresolved local tension has accumulated before being paid back or transformed.",
        "Accumulated disruption, pressure, accent drift, and low groove comfort, reduced by release force.",
        "High expectation debt means the track has borrowed against the listener's expectation; release, cadence, or reset may feel earned when it arrives.",
        "withholding, borrowed expectation, unresolved pull, delayed payoff, tension carried forward",
        "This is a heuristic listener-state accumulator, not a claim about composer intent.",
    ),
    MetricVocabulary(
        "release_force",
        "Release force",
        "How strongly the current moment releases accumulated pressure or expectation debt.",
        "Negative pressure weighted by the immediately prior expectation debt.",
        "High release force means a local drop, exhale, or opening has enough prior pressure behind it to feel consequential.",
        "release hits, pressure opens, earned exhale, drop pays back, tension clears",
        "A quieting moment without prior debt may have low release force even if it is perceptible.",
    ),
    MetricVocabulary(
        "section_gravity",
        "Section gravity",
        "How strongly the moment feels like an anchor rather than passage material.",
        "Local pattern, attention, body-lock, and low accent drift.",
        "High section gravity means the moment feels like a stable floor or home base; low gravity means transition, instability, or drift.",
        "section locks, home base, anchor, floor arrives, passage material, transition state",
        "A high-gravity section is not automatically a chorus or formal section; it is a local stability signal.",
    ),
    MetricVocabulary(
        "surface_density",
        "Surface density",
        "How much local detail or event-load is present independent of raw loudness.",
        "Onset density, spectral motion, energy motion, and harmonic/percussive surface detail.",
        "High surface density means the moment is busy, detailed, or texturally loaded; low density means sparse, smooth, or sustained surface.",
        "busy surface, detail load, particulate motion, sparse surface, smooth wall, dense shimmer",
        "Density is not heaviness. A loud sustained wall can be low-density; a quiet surface balance can be dense.",
    ),
    MetricVocabulary(
        "weight",
        "Weight",
        "How much the sound feels held, dragged, suspended, or physically weighted.",
        "Harmonic mass, dynamic pressure, sparse density, and drag without motor lock.",
        "High weight means the sound has weight even when it is not dance-like; low weight means the surface is light, thin, or mostly motor-driven.",
        "weight arrives, suspension, drag, pressure in the room, held body, gravity",
        "Weight is not loudness alone. Quiet drones, voices, and sustained tones can carry weight; loud percussion may still be light if it does not hold.",
    ),
    MetricVocabulary(
        "weight_arc",
        "Weight arc",
        "Where the music puts its macro weight over time.",
        "Segment-level energy placement across the track.",
        "The weight arc shows whether force gathers early, late, steadily, or in repeated waves.",
        "weight gathers, weight shifts, the track leans into or away from force",
        "This is a track-shape reading, not a momentary metric. Use it to orient the whole arc before making local claims.",
    ),
    MetricVocabulary(
        "pressure",
        "Pressure",
        "Whether heard pressure comes forward, withdraws, or holds.",
        "Silence-aware short-term loudness movement smoothed into build/release/sustain direction.",
        "Positive pressure means the room is filling or coming forward; negative pressure means release, withdrawal, or emptying; near zero means held pressure.",
        "pressure builds, releases, holds, empties, fills the room, exhales",
        "Pressure is motion in heard loudness, not emotional drama by itself. Compression and mastering can affect it.",
    ),
    MetricVocabulary(
        "surface_balance",
        "Surface balance",
        "Whether sonic weight sits in sustained tone or percussive attack.",
        "Harmonic/percussive separated energy balance.",
        "Negative surface balance means sustained tone, voice, drone, or harmony dominates; positive surface balance means strike, groove, attack, or percussion dominates.",
        "harmonic warmth, percussive edge, strike, drone, tonal atmosphere, surface hardens",
        "Surface balance depends on source separation quality. Treat it as evidence about the surface, not proof of instrumentation.",
    ),
    MetricVocabulary(
        "surface_motion",
        "Surface motion",
        "How quickly the timbral surface changes from moment to moment.",
        "Short-window spectral flux from adjacent magnitude spectra.",
        "High surface motion means the surface is flickering, turning, or actively changing; low surface motion means it is sustained or stable.",
        "surface flickers, timbre turns, restless skin, stable surface, slow-moving wall",
        "Surface motion is not section detection. It is local change-rate evidence, not a label for musical form.",
    ),
    MetricVocabulary(
        "punch",
        "Punch",
        "How sharply the waveform peaks above its local body.",
        "Local crest factor from peak amplitude over RMS energy.",
        "High punch means impact or transient snap rises above the average body; low punch means the sound is more even, compressed, or sustained.",
        "punch lands, sharp impact, transient snap, flattened wall, even pressure",
        "Punch is not loudness. A quiet click can be punchy; a loud wall can have little crest left.",
    ),
    MetricVocabulary(
        "bass_weight",
        "Bass weight",
        "How much local energy sits in the low band.",
        "Relative power from roughly 20-160 Hz.",
        "High bass weight means the surface is grounded low; low bass weight means the bottom is withheld or carried elsewhere.",
        "low floor, bass weight, grounded body, bottom drops out",
        "Band splits are coarse. Use as color/weight evidence, not exact instrumentation.",
    ),
    MetricVocabulary(
        "body_weight",
        "Body-band weight",
        "How much local energy sits in the low-mid body band.",
        "Relative power from roughly 160-800 Hz.",
        "High body-band weight means warmth, chest, or mid-body mass is carrying the surface.",
        "body band, chest weight, warm mass, low-mid pressure",
        "Band splits are coarse and mix fundamentals, overtones, and production choices.",
    ),
    MetricVocabulary(
        "presence_weight",
        "Presence weight",
        "How much local energy sits in the presence band.",
        "Relative power from roughly 800-4000 Hz.",
        "High presence weight means the surface presses forward, speaks, bites, or occupies the perceptual front.",
        "presence bite, forward surface, voice edge, glare, pressed mids",
        "Presence does not prove vocals or lead instruments. It is frequency-placement evidence.",
    ),
    MetricVocabulary(
        "air_weight",
        "Air weight",
        "How much local energy sits in the upper air band.",
        "Relative power above roughly 4000 Hz.",
        "High air weight means hiss, shimmer, brightness, cymbal air, or upper edge is prominent.",
        "air, shimmer, hiss, upper edge, sparkle, brittle top",
        "Air can come from noise, cymbals, distortion, mastering, or artifacts. Do not over-name the source.",
    ),
    MetricVocabulary(
        "brightness_tilt",
        "Brightness tilt",
        "Whether the local surface leans dark/low or bright/high.",
        "Blend of high-band energy share and spectral centroid brightness.",
        "High brightness tilt means the surface leans upward, bright, sharp, or airy; low brightness tilt means it leans dark, low, or covered.",
        "bright tilt, dark tilt, upper glare, covered tone, air opens",
        "Brightness tilt is not emotional brightness. It is spectral placement.",
    ),
    MetricVocabulary(
        "harmonic_pull",
        "Harmonic pull",
        "How much the harmonic field pulls, turns, or refuses to settle.",
        "Velocity through smoothed tonnetz space.",
        "High harmonic pull means the tonal field is moving or leaning; low pull means harmonic stasis, drone, or stable centering.",
        "tonal restlessness, harmonic drift, pull, preparation, refusal to settle",
        "Low harmonic pull is not weak harmony. Drone and ritual music may deliberately keep harmonic motion minimal.",
    ),
    MetricVocabulary(
        "chroma_motion",
        "Chroma motion",
        "How much the pitch-class fingerprint changes over time.",
        "Cosine distance between adjacent chroma frames, where chroma means the twelve pitch classes ignoring octave.",
        "High chroma motion means the chord or pitch-class surface keeps changing; low chroma motion means the harmonic color stays stable.",
        "chroma turns, harmonic surface shifts, pitch-color moves, chord brightness changes",
        "This is not timbre or orchestration color. It tracks pitch-class movement, not whether the instruments sound warm, bright, or dark.",
    ),
    MetricVocabulary(
        "tonal_anchor",
        "Tonal anchor",
        "How strongly a local key center holds.",
        "Dominance of the detected tonic pitch class.",
        "High tonal anchor means the track has a strong sense of home; low anchor means the center is weak, wandering, modal, or intentionally ambiguous.",
        "center, home, tonal floor, loosened anchor, key center holds",
        "Low tonal anchor is not wrong notes. Modal, folk, chromatic, and drone-based music may resist a single key center.",
    ),
    MetricVocabulary(
        "pitch_grid",
        "Pitch grid",
        "How much pitch energy sits inside equal-tempered pitch-class bins.",
        "Concentration of chroma energy inside equal-tempered pitch classes.",
        "High pitch grid means the pitch world is centered in standard bins; low pitch grid means bends, smear, microtonal behavior, or folk-natural tuning may be present.",
        "centered pitch grid, bent pitch world, smeared tuning, folk-natural pitch",
        "This has Western/equal-tempered bias. Low pitch grid is evidence about tuning world, not a defect.",
    ),
    MetricVocabulary(
        "interval_coherence",
        "Interval coherence",
        "How easily pitch classes organize into stable interval relations.",
        "Pitch-class relationships weighted by simple interval consonance.",
        "High interval coherence means the pitch field forms stable relations; low coherence means the interval field is complex, ambiguous, or noisy.",
        "settled interval field, fused relation, complex harmony, ambiguous pitch field",
        "This is a simplified consonance model. Do not use it to judge harmonic sophistication or cultural value.",
    ),
    MetricVocabulary(
        "overtone_fit",
        "Overtone fit",
        "How strongly the sound locks onto natural overtone relationships.",
        "Observed partial alignment around detected fundamentals.",
        "High overtone fit means the sound appears fused around harmonic partials; low fit means inharmonicity, noise, or weak pitch tracking.",
        "pure resonance, fused sound, bell-like or vocal fit, rough inharmonicity",
        "This depends on fundamental detection and spectral clarity. Low fit can mean noisy beauty, not failure.",
    ),
    MetricVocabulary(
        "overtone_density",
        "Overtone density",
        "How dense or bright the upper-partial surface is.",
        "Upper-partial energy around detected fundamentals.",
        "High overtone density means the sound has a rich upper-partial surface; low density means the resonance is sparse, dark, or softly voiced.",
        "bright upper partials, dense shimmer, sparse overtone surface, dark resonance",
        "Density is not quality. Sparse overtone surfaces can be intimate, restrained, or deliberately dark.",
    ),
    MetricVocabulary(
        "foreground_line",
        "Foreground line",
        "How strongly a foreground pitched line is trackable.",
        "pYIN voiced probability over time.",
        "High foreground line means a pitched voice or lead thread is structurally trackable; low foreground line means it may be absent, buried, unpitched, textural, or not captured by pitch tracking.",
        "foreground line, pitch thread, voice-like contour, lead contour, sung line emerges",
        "Do not read this as proof of literal vocals. It is pitch-extraction evidence, and it can miss obvious human vocal presence.",
    ),
)

METRIC_BY_FIELD = {metric.field: metric for metric in METRICS}


def vocabulary(field: str) -> MetricVocabulary:
    """Return the glossary entry for a metric field."""
    return METRIC_BY_FIELD[field]


def display_name(field: str) -> str:
    """Return the public display name for a metric field."""
    return vocabulary(field).display


def glossary_lines(fields: list[str] | tuple[str, ...] | None = None) -> list[str]:
    """Return compact glossary lines for LLM prompt/context assembly."""
    metrics = METRICS if fields is None else tuple(vocabulary(field) for field in fields)
    return [
        f"- `{metric.field}` ({metric.display}): {metric.definition} Evidence: {metric.evidence} Caveat: {metric.caveat}"
        for metric in metrics
    ]
