from galdr.assemble import assemble_prompt


def minimal_analysis():
    return {
        "report": {
            "duration_seconds": 180.0,
            "detected_pulse_bpm": 92.0,
            "felt_pulse_bpm": 92.0,
        },
        "perception": {
            "summary": {"mean_attention": 0.8, "mean_pattern": 0.85},
            "stream": [
                {
                    "t": 0.0,
                    "attention": 0.8,
                    "pattern": 0.85,
                    "pressure": 0.5,
                    "body": 0.6,
                }
            ],
        },
    }


def test_meaning_is_a_standalone_prompt_contract():
    prompt = assemble_prompt(minimal_analysis(), mode="full", lens="meaning")

    assert "# Meaning Lens" in prompt
    assert "# ARC Prompt Family Base" not in prompt
    assert "post-listen interpretation, not a chronological companion page" in prompt
    assert "Do **not** walk the song in time order" in prompt
    assert "Do not include timestamps" in prompt
    assert "one governing claim" in prompt
    assert "## Galdr Analysis" in prompt


def test_structure_is_a_standalone_prompt_contract():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="structure")

    assert "# Structure Lens" in prompt
    assert "# ARC Prompt Family Base" not in prompt
    assert "Headings and bullets are explicitly allowed here" in prompt
    assert "This map is not continuous Arc prose" in prompt
    assert "hearing-stream evidence may confirm an entrance" in prompt
    assert "do not use headings or bullets" not in prompt
    assert "## Galdr Analysis" in prompt


def test_read_along_lenses_still_use_the_family_base():
    for lens in ("default", "sound", "dance", "classical", "ritual"):
        prompt = assemble_prompt(minimal_analysis(), mode="blind", lens=lens)
        assert "# ARC Prompt Family Base" in prompt


def test_classical_suppresses_unearned_groove_language():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="classical")

    assert "Prefer phrase, register, voicing, articulation" in prompt
    assert "repeated figuration is not automatically a groove" in prompt


def test_ritual_has_one_public_output_contract():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="ritual")

    assert "Write a public ritual reading" in prompt
    assert "Build the exploratory ritual analysis privately" in prompt
    assert "This is not the final prose voice" not in prompt
    assert "Return a compact boundary reading" in prompt
