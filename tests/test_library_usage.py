#!/usr/bin/env python3
"""
Test script to demonstrate ugly_midi library usage.

This script creates a test JSON file, converts it to MIDI using the ugly_midi
library, then converts it back to JSON to test the round-trip conversion.
"""

import ugly_midi
import json
import os
import tempfile
from pathlib import Path


def create_test_json():
    """Create a sample VexFlow JSON for testing."""
    test_json = {
        "keySignature":
        "C",
        "tempo":
        120,
        "timeSignature": {
            "numerator": 4,
            "denominator": 4
        },
        "instrument":
        "piano",
        "midiChannel":
        "0",
        "measures": [
            # Measure 1: Simple melody
            [{
                "id": "test-1-1",
                "name": "C4",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }, {
                "id": "test-1-2",
                "name": "D4",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }, {
                "id": "test-1-3",
                "name": "E4",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }, {
                "id": "test-1-4",
                "name": "F4",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }],
            # Measure 2: Chord and rest
            [{
                "id": "test-2-1",
                "name": "(C4 E4 G4)",
                "clef": "treble",
                "duration": "h",
                "measure": 1,
                "isRest": False
            }, {
                "id": "test-2-2",
                "name": "",
                "clef": "treble",
                "duration": "h",
                "measure": 1,
                "isRest": True
            }],
            # Measure 3: Bass clef notes
            [{
                "id": "test-3-1",
                "name": "C3",
                "clef": "bass",
                "duration": "q",
                "measure": 2,
                "isRest": False
            }, {
                "id": "test-3-2",
                "name": "G3",
                "clef": "bass",
                "duration": "q",
                "measure": 2,
                "isRest": False
            }, {
                "id": "test-3-3",
                "name": "C4",
                "clef": "treble",
                "duration": "h",
                "measure": 2,
                "isRest": False
            }]
        ]
    }
    return test_json


def create_ensemble_test_json():
    """Create multiple JSON files to test ensemble functionality."""
    piano_json = {
        "keySignature":
        "C",
        "tempo":
        100,
        "timeSignature": {
            "numerator": 4,
            "denominator": 4
        },
        "instrument":
        "piano",
        "midiChannel":
        "0",
        "measures": [[{
            "id": "piano-1-1",
            "name": "(C4 E4 G4)",
            "clef": "treble",
            "duration": "w",
            "measure": 0,
            "isRest": False
        }]]
    }

    guitar_json = {
        "keySignature":
        "C",
        "tempo":
        100,
        "timeSignature": {
            "numerator": 4,
            "denominator": 4
        },
        "instrument":
        "guitar",
        "midiChannel":
        "1",
        "measures": [[{
            "id": "guitar-1-1",
            "name": "C3",
            "clef": "bass",
            "duration": "q",
            "measure": 0,
            "isRest": False
        }, {
            "id": "guitar-1-2",
            "name": "G3",
            "clef": "bass",
            "duration": "q",
            "measure": 0,
            "isRest": False
        }, {
            "id": "guitar-1-3",
            "name": "C3",
            "clef": "bass",
            "duration": "h",
            "measure": 0,
            "isRest": False
        }]]
    }

    return piano_json, guitar_json


def test_basic_conversion():
    """Test basic JSON to MIDI to JSON conversion."""
    print("=" * 60)
    print("TESTING BASIC CONVERSION")
    print("=" * 60)

    # Create test data
    original_json = create_test_json()
    print(
        f"✓ Created test JSON with {len(original_json['measures'])} measures")

    # Convert JSON to MIDI using library
    print("\n1. Converting JSON to MIDI...")
    try:
        midi_data = ugly_midi.json_to_midi(original_json)
        print(
            f"✓ Successfully created MIDI with {len(midi_data.instruments)} instruments"
        )

        # Show some details
        total_notes = sum(len(inst.notes) for inst in midi_data.instruments)
        print(f"  - Total notes: {total_notes}")
        for i, inst in enumerate(midi_data.instruments):
            print(
                f"  - Instrument {i+1}: {inst.name} ({len(inst.notes)} notes)")

    except Exception as e:
        print(f"✗ Error converting JSON to MIDI: {e}")
        return False

    # Save MIDI to temporary file
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as temp_midi:
        temp_midi_path = temp_midi.name

    try:
        ugly_midi.save_midi(midi_data, temp_midi_path)
        print(f"✓ Saved MIDI to temporary file: {temp_midi_path}")
    except Exception as e:
        print(f"✗ Error saving MIDI: {e}")
        return False

    # Convert MIDI back to JSON
    print("\n2. Converting MIDI back to JSON...")
    try:
        converted_json = ugly_midi.midi_to_json(temp_midi_path)
        print(f"✓ Successfully converted MIDI back to JSON")
        print(f"  - Tempo: {converted_json.get('tempo', 'unknown')}")
        print(f"  - Key: {converted_json.get('keySignature', 'unknown')}")
        print(f"  - Instrument: {converted_json.get('instrument', 'unknown')}")
        print(f"  - Measures: {len(converted_json.get('measures', []))}")

    except Exception as e:
        print(f"✗ Error converting MIDI to JSON: {e}")
        return False
    finally:
        # Clean up temporary file
        if os.path.exists(temp_midi_path):
            os.unlink(temp_midi_path)

    # Save files for inspection
    print("\n3. Saving test files...")
    ugly_midi.save_json_file(original_json, "test_original.json")
    ugly_midi.save_json_file(converted_json, "test_converted.json")
    print("✓ Saved test_original.json and test_converted.json for comparison")

    return True


def test_ensemble_conversion():
    """Test multi-instrument ensemble conversion."""
    print("\n" + "=" * 60)
    print("TESTING ENSEMBLE CONVERSION")
    print("=" * 60)

    # Create ensemble test data
    piano_json, guitar_json = create_ensemble_test_json()
    print("✓ Created piano and guitar JSON data")

    # Convert to ensemble MIDI
    print("\n1. Creating ensemble MIDI...")
    try:
        ensemble_midi = ugly_midi.create_ensemble([piano_json, guitar_json])
        print(
            f"✓ Created ensemble with {len(ensemble_midi.instruments)} instruments"
        )

        for i, inst in enumerate(ensemble_midi.instruments):
            print(f"  - {inst.name}: {len(inst.notes)} notes")

    except Exception as e:
        print(f"✗ Error creating ensemble: {e}")
        return False

    # Save ensemble
    try:
        ugly_midi.save_midi(ensemble_midi, "test_ensemble.mid")
        print("✓ Saved test_ensemble.mid")
    except Exception as e:
        print(f"✗ Error saving ensemble: {e}")
        return False

    return True


def test_file_operations():
    """Test file loading and saving operations."""
    print("\n" + "=" * 60)
    print("TESTING FILE OPERATIONS")
    print("=" * 60)

    # Create and save a test JSON file
    test_data = create_test_json()
    test_json_path = "test_input.json"

    print("1. Testing file save/load...")
    try:
        ugly_midi.save_json_file(test_data, test_json_path)
        print(f"✓ Saved {test_json_path}")

        loaded_data = ugly_midi.load_json_file(test_json_path)
        print(f"✓ Loaded {test_json_path}")

        # Verify data matches
        if loaded_data == test_data:
            print("✓ Loaded data matches original data")
        else:
            print("✗ Loaded data doesn't match original")
            return False

    except Exception as e:
        print(f"✗ Error with file operations: {e}")
        return False

    # Test conversion from file
    print("\n2. Testing conversion from file...")
    try:
        midi_from_file = ugly_midi.json_to_midi(loaded_data)
        ugly_midi.save_midi(midi_from_file, "test_from_file.mid")
        print("✓ Successfully converted loaded JSON to MIDI")

    except Exception as e:
        print(f"✗ Error converting from file: {e}")
        return False

    return True


def test_advanced_features():
    """Test advanced converter features."""
    print("\n" + "=" * 60)
    print("TESTING ADVANCED FEATURES")
    print("=" * 60)

    test_json = create_test_json()

    # Test tempo override
    print("1. Testing tempo override...")
    try:
        midi_120 = ugly_midi.json_to_midi(test_json)  # Original tempo
        midi_200 = ugly_midi.json_to_midi(test_json, tempo_override=200)

        print("✓ Created MIDI with different tempos")
        ugly_midi.save_midi(midi_120, "test_tempo_120.mid")
        ugly_midi.save_midi(midi_200, "test_tempo_200.mid")
        print("✓ Saved test_tempo_120.mid and test_tempo_200.mid")

    except Exception as e:
        print(f"✗ Error testing tempo override: {e}")
        return False

    # Test direct converter functions
    print("\n2. Testing direct converter functions...")
    try:
        from ugly_midi.converter import (parse_note_name, beats_to_seconds,
                                         determine_clef, DURATION_TO_BEATS)

        # Test note parsing
        single_note = parse_note_name("C4")
        chord_notes = parse_note_name("(C4 E4 G4)")
        print(f"✓ Parsed C4: {single_note}")
        print(f"✓ Parsed chord: {chord_notes}")

        # Test timing
        quarter_note_seconds = beats_to_seconds(1.0, 120)  # 1 beat at 120 BPM
        print(f"✓ Quarter note at 120 BPM: {quarter_note_seconds} seconds")

        # Test clef determination
        treble_clef = determine_clef(60)  # Middle C
        bass_clef = determine_clef(48)  # C below middle C
        print(f"✓ Middle C clef: {treble_clef}")
        print(f"✓ Low C clef: {bass_clef}")

        # Show duration mapping
        print(
            f"✓ Duration mappings available: {list(DURATION_TO_BEATS.keys())}")

    except Exception as e:
        print(f"✗ Error testing direct functions: {e}")
        return False

    return True


def main():
    """Run all tests."""
    print("UGLY_MIDI LIBRARY TEST SUITE")
    print("Testing ugly_midi package as a Python library...")

    # Show package info
    print(f"\nPackage version: {ugly_midi.__version__}")
    print(f"Package author: {ugly_midi.__author__}")

    tests = [("Basic Conversion", test_basic_conversion),
             ("Ensemble Conversion", test_ensemble_conversion),
             ("File Operations", test_file_operations),
             ("Advanced Features", test_advanced_features)]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print(
            "🎉 All tests passed! The ugly_midi library is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    # List generated files
    generated_files = [
        "test_original.json", "test_converted.json", "test_ensemble.mid",
        "test_input.json", "test_from_file.mid", "test_tempo_120.mid",
        "test_tempo_200.mid"
    ]

    existing_files = [f for f in generated_files if os.path.exists(f)]
    if existing_files:
        print(f"\nGenerated test files: {', '.join(existing_files)}")
        print(
            "You can examine these files to verify the conversions worked correctly."
        )


if __name__ == "__main__":
    main()
