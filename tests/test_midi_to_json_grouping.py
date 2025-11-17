#!/usr/bin/env python3
"""Regression tests for MIDI->JSON grouping and clef handling."""

from pathlib import Path
import json

import ugly_midi


def _find_notes_by_name(measures, name, clef=None):
    results = []
    for m_idx, measure in enumerate(measures):
        for note in measure:
            if note.get("isRest"):
                continue
            if note.get("name") == name and (clef is None or note.get("clef") == clef):
                results.append((m_idx, note))
    return results


def test_no_cross_clef_chord_for_d3_b4(tmp_path):
    """Ensure D3 (bass) and B4 (treble) are not merged into one chord."""
    original_path = Path("tests/test_files/my-song.json")
    assert original_path.exists()

    with original_path.open("r") as f:
        original_json = json.load(f)

    # JSON -> MIDI
    midi = ugly_midi.json_to_midi(original_json)
    midi_path = tmp_path / "my-song.mid"
    midi.write(str(midi_path))
    assert midi_path.exists()

    # MIDI -> JSON
    converted = ugly_midi.midi_to_json(str(midi_path))
    measures = converted.get("measures", [])

    # D3 should appear in bass clef, B4 in treble clef.
    d3_bass = _find_notes_by_name(measures, "D3", clef="bass")
    b4_treble = _find_notes_by_name(measures, "B4", clef="treble")
    assert d3_bass, "D3 in bass clef not found in converted JSON"
    assert b4_treble, "B4 in treble clef not found in converted JSON"

    # There must not be a cross-clef chord (D3 B4) in a single clef.
    bad_chord_names = ["(D3 B4)", "(B4 D3)"]
    for m_idx, measure in enumerate(measures):
        for note in measure:
            if note.get("isRest"):
                continue
            assert note.get("name") not in bad_chord_names, (
                f"Found invalid cross-clef chord {note.get('name')} in measure {m_idx}"
            )
