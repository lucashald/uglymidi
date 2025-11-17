#!/usr/bin/env python3
"""Run a JSON -> MIDI -> JSON round-trip and persist the artifacts.

This is for manual inspection, not as an automated test.
"""

import json
from pathlib import Path

import ugly_midi


def main():
    base = Path("tests/test_files")
    original_json_path = base / "my-song.json"
    midi_path = base / "my-song-roundtrip.mid"
    converted_json_path = base / "my-song-roundtrip.json"

    if not original_json_path.exists():
        raise SystemExit(f"Original JSON not found: {original_json_path}")

    with original_json_path.open("r") as f:
        original = json.load(f)

    # JSON -> MIDI
    midi_obj = ugly_midi.json_to_midi(original)
    midi_obj.write(str(midi_path))
    print(f"Wrote MIDI: {midi_path}")

    # MIDI -> JSON
    converted = ugly_midi.midi_to_json(str(midi_path))
    with converted_json_path.open("w") as f:
        json.dump(converted, f, indent=2)
    print(f"Wrote converted JSON: {converted_json_path}")


if __name__ == "__main__":
    main()
