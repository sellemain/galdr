"""Galdr constants — named thresholds and configuration values.

Every magic number that affects listener behavior lives here.
When tuning galdr's sensitivity, this is the file to edit.
"""

# ============================================================
# Pitch & Harmony
# ============================================================

PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Krumhansl-Kessler key profiles (from Krumhansl, 1990)
# Empirically measured "fit" ratings for each pitch class in context of a key.
# Higher value = pitch class is more characteristic of that key.
KK_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
KK_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


# ============================================================
# Perception — Momentum
# ============================================================

# Rolling window for rhythmic momentum calculation (seconds)
MOMENTUM_WINDOW_SEC = 8.0

# Time step between momentum samples (seconds)
MOMENTUM_HOP_SEC = 0.5

# Minimum beats required in a window to compute momentum
MOMENTUM_MIN_BEATS = 3


# ============================================================
# Perception — Disruption / Pattern Lock
# ============================================================

# Weights for combining disruption sources into total disruption.
# Inverted (1.0 - disruption) to get pattern_lock.
DISRUPTION_WEIGHT_BEAT = 0.4
DISRUPTION_WEIGHT_SPECTRAL = 0.35
DISRUPTION_WEIGHT_ENERGY = 0.25

# Lookback window for beat prediction (seconds)
DISRUPTION_BEAT_LOOKBACK_SEC = 5.0

# When no recent beats exist, how long since last beat before we
# start reporting disruption (seconds)
DISRUPTION_BEAT_ABSENCE_THRESHOLD_SEC = 1.5

# Maximum time since last beat that maps to disruption=1.0
DISRUPTION_BEAT_ABSENCE_MAX_SEC = 5.0

# Spectral flux smoothing window (frames)
DISRUPTION_SPECTRAL_SMOOTH_FRAMES = 20

# Energy disruption smoothing window (frames)
DISRUPTION_ENERGY_SMOOTH_FRAMES = 20


# ============================================================
# Perception — Breath
# ============================================================

# RMS smoothing window for breath calculation (frames)
BREATH_SMOOTH_FRAMES = 40


# ============================================================
# Perception — Silence Detection
# ============================================================

# dB below peak to consider as silence
SILENCE_THRESHOLD_DB = -40

# Minimum duration to count as a silence event (seconds)
SILENCE_MIN_DURATION_SEC = 0.5


# ============================================================
# Perception — Harmonic-Percussive Balance
# ============================================================

# Minimum total energy to compute HP balance (below this = 0.0)
HP_BALANCE_MIN_ENERGY = 0.005

# Smoothing window for HP energy curves (frames)
HP_SMOOTH_FRAMES = 20


# ============================================================
# Perception — Stream Event Thresholds
# ============================================================

# Momentum thresholds for listener_locked / listener_floating events
EVENT_MOMENTUM_LOCKED = 0.8
EVENT_MOMENTUM_FLOATING = 0.2

# Disruption threshold for pattern_break event
EVENT_DISRUPTION_BREAK = 0.5

# Breath thresholds for building/releasing events
EVENT_BREATH_BUILDING = 0.3
EVENT_BREATH_RELEASING = -0.3

# Minimum disruption to include in pattern_breaks list
PATTERN_BREAK_MIN_DISRUPTION = 0.2

# Momentum delta threshold for shift detection
MOMENTUM_SHIFT_THRESHOLD = 0.3

# Number of top disruption moments to report
TOP_DISRUPTION_COUNT = 5


# ============================================================
# Harmony — Consonance
# ============================================================

# Chroma smoothing window (frames)
CHROMA_SMOOTH_FRAMES = 8

# Just-intonation interval consonance weights.
# Used by harmonic series consonance calculation.
JI_CONSONANCE = {
    0: 1.0,    # unison
    7: 0.95,   # perfect fifth (3:2)
    5: 0.90,   # perfect fourth (4:3)
    4: 0.80,   # major third (5:4)
    3: 0.75,   # minor third (6:5)
    9: 0.70,   # major sixth (5:3)
    8: 0.65,   # minor sixth (8:5)
    2: 0.50,   # major second (9:8)
    10: 0.50,  # minor seventh (16:9)
    11: 0.40,  # major seventh (15:8)
    1: 0.30,   # minor second (16:15)
    6: 0.25,   # tritone (45:32)
}

# Minimum chroma energy to compute consonance (below = silence)
CONSONANCE_MIN_ENERGY = 0.001

# Threshold for "active" pitch class in series consonance (fraction of max)
CONSONANCE_ACTIVE_THRESHOLD = 0.1


# ============================================================
# Harmony — Tonal Center (KK Key Detection)
# ============================================================

# Window size for tonal center tracking (frames)
TONAL_CENTER_WINDOW_FRAMES = 50

# Minimum chroma profile energy for key detection
TONAL_CENTER_MIN_ENERGY = 0.001


# ============================================================
# Harmony — Tension (Tonnetz)
# ============================================================

# Smoothing window for tonnetz features (frames)
TENSION_SMOOTH_FRAMES = 8

# Smoothing window for tension velocity (frames)
TENSION_VELOCITY_SMOOTH = 10


# ============================================================
# Harmony — Chroma Flux (replaces chord-based harmonic rhythm)
# ============================================================

# Window for computing rate of harmonic change (seconds)
CHROMA_FLUX_WINDOW_SEC = 8.0

# Hop for chroma flux output (seconds)
CHROMA_FLUX_HOP_SEC = 0.5


# ============================================================
# Melody
# ============================================================

# Pitch tracking range (Hz) — pyin
MELODY_FMIN = 60
MELODY_FMAX = 2000

# Direction slope window (seconds)
MELODY_DIRECTION_WINDOW_SEC = 2.0

# Pitch range window (seconds)
MELODY_RANGE_WINDOW_SEC = 4.0

# Vocal presence window (seconds)
MELODY_PRESENCE_WINDOW_SEC = 2.0

# Minimum vocal presence to count direction stats
MELODY_DIRECTION_MIN_PRESENCE = 0.3

# Direction thresholds (semitones/sec)
MELODY_ASCENDING_THRESHOLD = 0.5
MELODY_DESCENDING_THRESHOLD = -0.5


# ============================================================
# Overtone
# ============================================================

# Maximum harmonic number to track
OVERTONE_MAX_HARMONIC = 16

# How close a spectral peak must be to an ideal harmonic (cents)
OVERTONE_TOLERANCE_CENTS = 50

# Pitch tracking range for overtone fundamental (Hz)
OVERTONE_FMIN = 50
OVERTONE_FMAX = 500

# Spectral peak detection
OVERTONE_N_PEAKS = 30
OVERTONE_MIN_HEIGHT_DB = -60
OVERTONE_PEAK_DISTANCE = 3
OVERTONE_PEAK_PROMINENCE = 3.0

# FFT size for high-resolution overtone analysis
OVERTONE_N_FFT = 8192

# Frequency ceiling for harmonic matching (Hz)
OVERTONE_FREQ_CEILING = 10000


# ============================================================
# Structural Segmentation (analyze.py)
# ============================================================

# Minimum time between structural boundaries (seconds)
SEGMENT_MIN_GAP_SEC = 10.0

# Minimum duration for trailing segment (seconds)
SEGMENT_MIN_TAIL_SEC = 5.0

# Number of segments for legacy energy arc
ENERGY_ARC_SEGMENTS = 10
