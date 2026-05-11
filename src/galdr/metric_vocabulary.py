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
        "Low pulse is not a flaw. Some music is unpulsed, rubato, ambient, or organized by breath and texture instead of beat.",
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
        "texture",
        "Texture",
        "Whether sonic weight sits in sustained tone or percussive attack.",
        "Harmonic/percussive separated energy balance.",
        "Negative texture means sustained tone, voice, drone, or harmony dominates; positive texture means strike, groove, attack, or percussion dominates.",
        "harmonic warmth, percussive edge, strike, drone, tonal atmosphere, surface hardens",
        "Texture depends on source separation quality. Treat it as evidence about the surface, not proof of instrumentation.",
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
