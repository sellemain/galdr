"""Smoke tests for galdr package — verify imports and basic structures."""

import pytest


def test_import_galdr():
    """Package imports without error."""
    import galdr
    assert hasattr(galdr, "__version__")
    assert isinstance(galdr.__version__, str)
    assert galdr.__version__ != ""


def test_import_analyze():
    """analyze module loads and exposes analyze_track."""
    from galdr.analyze import analyze_track
    assert callable(analyze_track)


def test_import_perceive():
    """perceive module loads and exposes key functions."""
    from galdr.perceive import generate_perception_stream, compute_attention
    assert callable(generate_perception_stream)
    assert callable(compute_attention)


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


def test_templates_declared_as_package_data():
    """Prompt templates should be included in built distributions."""
    from pathlib import Path

    pyproject = Path("pyproject.toml").read_text()
    assert 'galdr = ["templates/*.md"]' in pyproject


def test_arc_family_templates_exist():
    """Bundled prompt-family templates should be available in source checkouts."""
    from pathlib import Path

    templates = Path("src/galdr/templates")
    for name in [
        "ARC-FAMILY-BASE.md",
        "ARC-LENS-DEFAULT.md",
        "ARC-LENS-SOUND.md",
        "ARC-LENS-DANCE.md",
        "ARC-LENS-STRUCTURE.md",
        "ARC-LENS-MEANING.md",
        "ARC-LENS-LYRICS-STUDY.md",
        "ARC-LENS-CLASSICAL.md",
        "ARC-LENS-RITUAL.md",
    ]:
        assert (templates / name).exists()


def test_skill_bundle_declared_in_sdist_manifest():
    """The canonical agent skill bundle should ship in source distributions."""
    from pathlib import Path

    manifest = Path("MANIFEST.in").read_text()
    assert "recursive-include galdr-skill *.md *.skill" in manifest


def test_only_one_skill_markdown_in_repo():
    """Avoid multiple discoverable SKILL.md files with unclear authority."""
    from pathlib import Path

    skill_files = [p.as_posix() for p in Path(".").glob("**/SKILL.md") if ".git" not in p.parts]
    assert skill_files == ["galdr-skill/galdr/SKILL.md"]


def test_yt_dlp_dependency_includes_reliability_extras():
    """Fetch reliability depends on yt-dlp's default and curl-cffi extras."""
    from pathlib import Path

    pyproject = Path("pyproject.toml").read_text()
    assert '"yt-dlp[default,curl-cffi]>=2026.3.17"' in pyproject
    assert '"ytmusicapi>=1.12.1"' in pyproject


def test_yt_dlp_reliability_extras_importable():
    """The synced environment should include yt-dlp's EJS and impersonation helpers."""
    import importlib.util

    assert importlib.util.find_spec("curl_cffi") is not None
    assert importlib.util.find_spec("yt_dlp_ejs") is not None
