"""Canonical metric vocabulary for galdr public names and field names."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricVocabulary:
    """Human-readable metadata for a galdr metric."""

    field: str
    display: str
    evidence: str
    listener_reading: str
    prose_language: str


METRICS: tuple[MetricVocabulary, ...] = (
    MetricVocabulary(
        "attention_grip",
        "Attention grip",
        "Beat regularity and beat density in rolling windows",
        "How strongly the music carries attention forward",
        "grip, pull, carried attention, locking in, letting go",
    ),
    MetricVocabulary(
        "pattern_integrity",
        "Pattern integrity",
        "Inverted disruption from beat, spectral, and energy expectation failures",
        "How intact the musical pattern feels",
        "keeps carried time intact, breaks expectation, holds its shape",
    ),
    MetricVocabulary(
        "pulse_steadiness",
        "Pulse steadiness",
        "Measured beat-interval regularity",
        "How stable the pulse feels when a pulse is available",
        "steady pulse, metronomic grid, organic drift, unstable pulse",
    ),
    MetricVocabulary(
        "body_grip",
        "Body grip",
        "Pulse steadiness, pulse confidence, onset density, and percussive weight",
        "Whether the pulse takes the body or merely offers itself",
        "body-lock, motor pull, bodily coupling, pulse offered but not seized",
    ),
    MetricVocabulary(
        "physical_hold",
        "Physical hold",
        "Harmonic mass, dynamic pressure, sparse density, and drag without motor lock",
        "How much the sound feels held, dragged, suspended, or weighted",
        "weight arrives, suspension, drag, pressure in the room, held body",
    ),
    MetricVocabulary(
        "weight_arc",
        "Weight arc",
        "Segment-level energy placement across the track",
        "Where the music puts its macro weight over time",
        "weight gathers, weight shifts, the track leans into or away from force",
    ),
    MetricVocabulary(
        "pressure_motion",
        "Pressure motion",
        "Silence-aware LUFS movement smoothed into build/release/sustain direction",
        "Whether heard pressure comes forward, withdraws, or holds",
        "pressure builds, releases, holds, empties, fills the room",
    ),
    MetricVocabulary(
        "texture_weight",
        "Texture weight",
        "Harmonic/percussive separated energy balance",
        "Whether weight sits in sustained tone or attack",
        "harmonic warmth, percussive edge, strike, drone, tonal atmosphere",
    ),
    MetricVocabulary(
        "harmonic_pull",
        "Harmonic pull",
        "Velocity through smoothed tonnetz space",
        "How much the harmonic field pulls, turns, or refuses to settle",
        "tonal restlessness, harmonic drift, pull, preparation, refusal to settle",
    ),
    MetricVocabulary(
        "harmonic_color_motion",
        "Harmonic color motion",
        "Cosine distance between adjacent chroma frames",
        "How quickly harmonic color changes",
        "color turns, harmonic surface shifts, tonal light changes",
    ),
    MetricVocabulary(
        "tonal_anchor",
        "Tonal anchor",
        "Dominance of the detected tonic pitch class",
        "How anchored the local key center feels",
        "center, home, tonal floor, loosened anchor",
    ),
    MetricVocabulary(
        "pitch_grid_alignment",
        "Pitch-grid alignment",
        "Concentration of chroma energy inside equal-tempered pitch classes",
        "How centered or outside-the-grid the pitch world feels",
        "centered pitch grid, bent pitch world, smeared or folk-natural tuning",
    ),
    MetricVocabulary(
        "interval_coherence",
        "Interval coherence",
        "Pitch-class relationships weighted by simple interval consonance",
        "How easily pitch classes organize into stable relations",
        "settled interval field, fused relation, complex or ambiguous harmony",
    ),
    MetricVocabulary(
        "overtone_fit",
        "Overtone fit",
        "Observed partial alignment around detected fundamentals",
        "How strongly the sound locks onto natural overtone relationships",
        "pure resonance, fused sound, bell-like or vocal fit, rough inharmonicity",
    ),
    MetricVocabulary(
        "overtone_density",
        "Overtone density",
        "Upper-partial energy around detected fundamentals",
        "How dense or bright the overtone surface is",
        "bright upper partials, dense shimmer, sparse overtone surface",
    ),
    MetricVocabulary(
        "foreground_line_evidence",
        "Foreground line evidence",
        "pYIN voiced probability over time",
        "How strongly a foreground pitched line is trackable",
        "foreground line, pitch thread, voice-like contour without claiming vocals",
    ),
)

METRIC_BY_FIELD = {metric.field: metric for metric in METRICS}


def display_name(field: str) -> str:
    """Return the public display name for a metric field."""
    return METRIC_BY_FIELD[field].display
