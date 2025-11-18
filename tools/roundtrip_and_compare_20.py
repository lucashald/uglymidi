#!/usr/bin/env python3
"""Round-trip convert `my-song (20).json` -> MIDI -> JSON and run the comparator."""
from __future__ import annotations

import pathlib
import json
import sys

import ugly_midi

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests" / "test_files"
INPUT = TEST_DIR / "my-song (20).json"
MIDOUT = TEST_DIR / "my-song (20).mid"
JSONOUT = TEST_DIR / "my-song (20)-v3.json"


def main() -> int:
    if not INPUT.exists():
        print("Input file not found:", INPUT)
        return 2

    print(f"Loading JSON from {INPUT}")
    json_data = ugly_midi.load_json_file(str(INPUT))

    print("Converting JSON->MIDI")
    midi = ugly_midi.json_to_midi(json_data)

    print(f"Writing MIDI to {MIDOUT}")
    ugly_midi.save_midi(midi, str(MIDOUT))

    print("Converting MIDI->JSON")
    json_round = ugly_midi.midi_to_json(str(MIDOUT), manual_tempo=json_data.get('tempo', 120))

    print(f"Writing JSON to {JSONOUT}")
    ugly_midi.save_json_file(json_round, str(JSONOUT))

    print("Running comparator")
    import subprocess

    subprocess.run([sys.executable, str(ROOT / 'tools' / 'compare_json_roundtrip.py'), str(INPUT), str(JSONOUT)])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
