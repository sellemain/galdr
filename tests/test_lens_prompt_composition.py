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
    assert "Every section heading must begin with a source-bound timestamp or range" in prompt
    assert "do not emit an untimestamped section heading" in prompt
    assert "hearing-stream evidence may suggest or confirm an entrance" in prompt
    assert "sampled timestamps are neighborhoods rather than automatic onsets" in prompt
    assert "do not use headings or bullets" not in prompt
    assert "## Galdr Analysis" in prompt


def test_read_along_lenses_still_use_the_family_base():
    for lens in ("default", "sound", "dance", "classical", "ritual"):
        prompt = assemble_prompt(minimal_analysis(), mode="blind", lens=lens)
        assert "# ARC Prompt Family Base" in prompt


def test_broad_lenses_reject_reusable_band_keeps_contrast():
    for lens in ("default", "sound", "structure", "meaning"):
        prompt = assemble_prompt(minimal_analysis(), mode="blind", lens=lens)
        assert "generic ensemble-stability" in prompt
        assert "*keep*, *hold*, or *carry*" in prompt
        assert "floor, road, ground, pulse, frame, or motion" in prompt


def test_read_along_lenses_require_a_final_specificity_pass():
    for lens in ("default", "sound"):
        prompt = assemble_prompt(minimal_analysis(), mode="blind", lens=lens)
        assert "Search the draft for generic ensemble-stability constructions" in prompt
        assert "delete the sentence instead of merely swapping synonyms" in prompt


def test_read_along_lenses_vary_response_shape_without_a_quota():
    for lens in ("default", "sound"):
        prompt = assemble_prompt(minimal_analysis(), mode="blind", lens=lens)
        assert "One observation may need one plain sentence" in prompt
        assert "A real unfolding may earn three or more" in prompt
        assert "not a sequence or quota" in prompt
        assert "Do not make neighboring paragraphs run the same rhetorical program" in prompt
        assert "synonym replacement alone is not variety" in prompt


def test_lyric_relationship_is_selective_not_a_required_template():
    prompt = assemble_prompt(minimal_analysis(), mode="full", lens="default")

    assert "Most lyric passages do not need one" in prompt
    assert "already musical evidence" in prompt
    assert "the prose must not imply that the band was expected to react" in prompt
    assert "Never append an unchanged-band clause" in prompt
    assert "return only when its audible function changes" in prompt


def test_meaning_varies_argument_shape_without_forcing_length():
    prompt = assemble_prompt(minimal_analysis(), mode="full", lens="meaning")

    assert "One thought may stand in one plain sentence" in prompt
    assert "a layered reading may earn three or more" in prompt
    assert "These are options, not a quota" in prompt
    assert "same internal argument pattern" in prompt


def test_sound_sync_is_standalone_timed_audio_only_contract():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="sound-sync")

    assert "# Sound Sync Lens" in prompt
    assert "# ARC Prompt Family Base" not in prompt
    assert "Timed lyrics may be supplied as private vocal-alignment evidence" in prompt
    assert "do not quote, paraphrase, summarize, or interpret the words" in prompt
    assert "No lyric quotations or semantic references" in prompt
    assert '"lens": "sound-sync"' in prompt
    assert '"musicalAnchorMs"' in prompt
    assert '"targetStartMs"' in prompt
    assert "Cue count and spoken density are outcomes of the music, not targets" in prompt
    assert "genre history, genre labels" in prompt
    assert "Adjacent target starts must leave obvious room" in prompt
    assert "For any gap around 20 seconds or longer" in prompt
    assert "A gap around 40 seconds or longer requires an explicit review decision" in prompt
    assert "Do not let minute-scale gaps happen accidentally" in prompt
    assert "This is a continuity audit, not a density quota" in prompt
    assert "Treat dramatic transition language as an evidence claim" in prompt
    assert "both an abrupt audible boundary and a large local contrast" in prompt
    assert "before state, the boundary, the after state" in prompt
    assert "general swell or thicker texture does not prove drums" in prompt
    assert "This is a proof threshold, not a ban" in prompt
    assert "Do not flatten a genuine rupture" in prompt
    assert "hearing-stream timestamps as observation samples" in prompt
    assert "useful neighborhoods to inspect" in prompt
    assert "focused local-window ear pass" in prompt
    assert "where the change becomes clearly audible" in prompt
    assert "Do not wrap it in Markdown fences" in prompt
    assert "Does this sentence help the listener hear the active moment" in prompt
    assert "requires an explicit review decision, not an automatic cue" in prompt


def test_classical_suppresses_unearned_groove_language():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="classical")

    assert "Prefer phrase, register, voicing, articulation" in prompt
    assert "repeated figuration is not automatically a groove" in prompt
    assert "why memory changes how that recurrence is heard" in prompt
    assert "Perceptual salience guide" not in prompt
    assert "### Arc structure" not in prompt
    assert "### Metric glossary" not in prompt
    assert "### How to read galdr" not in prompt


def test_ritual_has_one_public_output_contract():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="ritual")

    assert "Write a public ritual reading" in prompt
    assert "Build the exploratory ritual analysis privately" in prompt
    assert "This is not the final prose voice" not in prompt
    assert "the full Ritual lens is not earned" in prompt
    assert "not a ritual manual or a catalogue" in prompt
    assert "Meaning can say what the song signifies" in prompt
    assert "Return a compact boundary reading" in prompt


def test_default_arc_requires_sparse_musical_time_anchors():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="default")

    assert "include 2–4 natural inline timestamps" in prompt
    assert "Attach each clock to the audible event that earns it" in prompt
    assert "do not use timestamps as paragraph furniture" in prompt


def test_family_public_hygiene_carries_quote_metric_and_intent_guards():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="default")

    assert "never publish `/` as a lyric line separator" in prompt
    assert "format every exact lyric fragment with italics alone" in prompt
    assert "do not wrap italic lyric fragments in quotation marks" in prompt
    assert "leave paraphrases in ordinary unquoted prose" in prompt
    assert "Named Galdr concepts are part of the listening vocabulary" in prompt
    assert "A numeric score, metric-family name, snake-case event label" in prompt
    assert "motor hold" in prompt
    assert "Repetition is the failure, not use" in prompt
    assert "without inventing intention" in prompt
    assert "require supplied, track-specific evidence of intent" in prompt
    assert "Treat dramatic transition language as an evidence claim" in prompt
    assert "both an abrupt audible boundary and a large local contrast" in prompt
    assert "general swell or thicker texture does not prove" in prompt
    assert "This is a proof threshold, not a ban" in prompt


def test_default_lens_carries_quote_ceiling_and_ending_choices():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="default")

    assert "hard ceiling of four quote spans or 35 quoted words" in prompt
    assert "no added closer because the final musical sentence already finished the page" in prompt
    assert 'Do not automatically append a "what remains,"' in prompt


def test_standalone_structure_carries_intent_metric_and_quote_guards():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="structure")

    assert "without inventing authorial intent" in prompt
    assert "require supplied, track-specific evidence of intent" in prompt
    assert "Named Galdr concepts such as motor hold" in prompt
    assert "Do not copy snake-case event labels" in prompt
    assert "never publish `/` as a lyric line separator" in prompt
    assert "Treat dramatic transition language as an evidence claim" in prompt
    assert "both an abrupt audible boundary and a large local contrast" in prompt
    assert "This is a proof threshold, not a ban" in prompt


def test_standalone_meaning_carries_public_quote_formatting():
    prompt = assemble_prompt(minimal_analysis(), mode="blind", lens="meaning")

    assert "Format every exact lyric fragment with italics alone" in prompt
    assert "Leave paraphrases unquoted" in prompt
    assert "never publish `/` as a line separator" in prompt
    assert "Scale musical intensity language the same way" in prompt
    assert "require an abrupt audible boundary plus a large local contrast" in prompt
    assert "This is a proof threshold, not a ban" in prompt
