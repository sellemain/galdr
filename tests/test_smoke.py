"""Smoke tests for galdr package — verify imports and basic structures."""

import pytest


def test_import_galdr():
    """Package imports without error."""
    import galdr
    assert hasattr(galdr, "__version__")
    assert galdr.__version__ == "0.1.0"


def test_import_analyze():
    """analyze module loads and exposes analyze_track."""
    from galdr.analyze import analyze_track
    assert callable(analyze_track)


def test_import_perceive():
    """perceive module loads and exposes key functions."""
    from galdr.perceive import generate_perception_stream, compute_momentum
    assert callable(generate_perception_stream)
    assert callable(compute_momentum)


def test_import_harmony():
    """harmony module loads and exposes key functions."""
    from galdr.harmony import analyze_harmony, compute_consonance
    assert callable(analyze_harmony)
    assert callable(compute_consonance)


def test_import_melody():
    """melody module loads and exposes key functions."""
    from galdr.melody import analyze_melody, hz_to_note_name
    assert callable(analyze_melody)
    assert hz_to_note_name(440.0) == "A4"


def test_import_overtone():
    """overtone module loads and exposes key functions."""
    from galdr.overtone import analyze_overtones, hz_to_cents, match_harmonics
    assert callable(analyze_overtones)
    assert callable(match_harmonics)
    # 1 octave = 1200 cents
    assert abs(hz_to_cents(220, 440) - 1200.0) < 0.1


def test_import_compare():
    """compare module loads and exposes compare_tracks."""
    from galdr.compare import compare_tracks, flatten_metrics
    assert callable(compare_tracks)
    assert callable(flatten_metrics)


def test_import_catalog():
    """catalog module loads and CatalogState is constructable."""
    from galdr.catalog import CatalogState
    cat = CatalogState(analysis_dir="/tmp/galdr-test-nonexistent")
    assert cat.tracks == {}
    assert cat.stats == {}


def test_import_cli():
    """cli module loads and main is callable."""
    from galdr.cli import main
    assert callable(main)


def test_catalog_default_dir():
    """CatalogState defaults to ~/.galdr/ for state storage."""
    from galdr.catalog import CatalogState, _default_catalog_dir
    from pathlib import Path

    cat = CatalogState()
    expected = Path.home() / ".galdr" / "catalog_state.json"
    assert cat.state_path == expected


def test_catalog_custom_dir():
    """CatalogState respects custom catalog_dir."""
    from galdr.catalog import CatalogState
    from pathlib import Path

    cat = CatalogState(catalog_dir="/tmp/my-catalog")
    assert cat.state_path == Path("/tmp/my-catalog/catalog_state.json")


def test_public_api_exports():
    """__init__.py exports match __all__."""
    import galdr
    for name in galdr.__all__:
        assert hasattr(galdr, name), f"Missing export: {name}"
