#!/usr/bin/env python3
"""Basic round-trip accuracy test using the library API.

This test is diagnostic: the product goal is one-way accuracy, but
round-trip helps surface lost notes or gross timing errors.
"""

import json
from pathlib import Path

import ugly_midi


def load_json(path: Path):
    with path.open("r") as f:
        return json.load(f)


def count_notes(json_data):
    count = 0
    for measure in json_data.get("measures", []):
        for note in measure:
            if note.get("isRest"):
                continue
            name = note.get("name", "")
            if name.startswith("(") and name.endswith(")"):
                count += len(name[1:-1].split())
            elif name:
                count += 1
    return count


def test_basic_roundtrip_my_song(tmp_path):
    """JSON -> MIDI -> JSON should preserve pitch count for my-song."""
    original_path = Path("tests/test_files/my-song.json")
    assert original_path.exists()

    original_json = load_json(original_path)
    original_note_count = count_notes(original_json)

    # JSON -> MIDI
    midi_obj = ugly_midi.json_to_midi(original_json)
    midi_path = tmp_path / "my-song.mid"
    midi_obj.write(str(midi_path))
    assert midi_path.exists()

    # MIDI -> JSON (using library helper)
    converted_json = ugly_midi.midi_to_json(str(midi_path))
    converted_note_count = count_notes(converted_json)

    # Diagnostic assertion: we at least expect to not lose notes.
    # This can be tightened over time as the converter improves.
    assert converted_note_count == original_note_count
