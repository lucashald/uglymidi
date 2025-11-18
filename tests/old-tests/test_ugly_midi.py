#!/usr/bin/env python3
"""
Automated Test Suite for VexFlow-MIDI Converter

Run this test whenever you update the main converter file to ensure
all functionality works correctly.

Usage:
    python test_ugly_midi.py
    python test_ugly_midi.py --verbose
    python test_ugly_midi.py --module-name ugly_midi  # if you rename the main file
"""

import unittest
import json
import tempfile
import os
import sys
from pathlib import Path
import importlib.util
import argparse
from unittest.mock import patch, MagicMock

# Try to import pretty_midi for validation
try:
    import pretty_midi
    HAS_PRETTY_MIDI = True
except ImportError:
    HAS_PRETTY_MIDI = False
    print("Warning: pretty_midi not installed. Some tests will be skipped.")


class TestVexFlowMIDIConverter(unittest.TestCase):
    """Test suite for the VexFlow-MIDI converter."""

    @classmethod
    def setUpClass(cls):
        """Set up test class by importing the converter module."""
        # Import the converter module dynamically
        module_name = getattr(cls, 'module_name', 'ugly_midi')
        module_path = f"{module_name}.py"

        if not os.path.exists(module_path):
            raise FileNotFoundError(
                f"Converter module '{module_path}' not found")

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        cls.converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.converter)

        # Create temporary directory for test files
        cls.temp_dir = tempfile.mkdtemp()
        print(f"Using temporary directory: {cls.temp_dir}")

    def setUp(self):
        """Set up individual test."""
        # Sample VexFlow JSON data for testing
        self.sample_json = {
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
            "measures": [[{
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
            }],
                         [{
                             "id": "test-2-1",
                             "name": "(C4 E4 G4)",
                             "clef": "treble",
                             "duration": "h",
                             "measure": 1,
                             "isRest": False
                         }]]
        }

        self.sample_chord_json = {
            "keySignature":
            "G",
            "tempo":
            100,
            "timeSignature": {
                "numerator": 3,
                "denominator": 4
            },
            "instrument":
            "guitar",
            "midiChannel":
            "1",
            "measures": [[{
                "id": "chord-1",
                "name": "(C4 E4 G4 C5)",
                "clef": "treble",
                "duration": "w.",
                "measure": 0,
                "isRest": False
            }]]
        }

    def test_duration_mappings(self):
        """Test that all duration mappings are correct."""
        expected_durations = {
            'w': 4.0,
            'h': 2.0,
            'q': 1.0,
            '8': 0.5,
            '16': 0.25,
            '32': 0.125,
            'w.': 6.0,
            'h.': 3.0,
            'q.': 1.5,
            '8.': 0.75,
            '16.': 0.375
        }

        for duration, expected_beats in expected_durations.items():
            self.assertEqual(
                self.converter.DURATION_TO_BEATS[duration], expected_beats,
                f"Duration {duration} should map to {expected_beats} beats")

    def test_parse_note_name_single(self):
        """Test parsing single note names."""
        if not HAS_PRETTY_MIDI:
            self.skipTest("pretty_midi not available")

        # Test single notes
        result = self.converter.parse_note_name("C4")
        self.assertEqual(result, [60])  # Middle C

        result = self.converter.parse_note_name("A4")
        self.assertEqual(result, [69])  # A above middle C

    def test_parse_note_name_chord(self):
        """Test parsing chord notation."""
        if not HAS_PRETTY_MIDI:
            self.skipTest("pretty_midi not available")

        # Test chord notation
        result = self.converter.parse_note_name("(C4 E4 G4)")
        expected = [60, 64, 67]  # C major chord
        self.assertEqual(result, expected)

    def test_beats_to_seconds(self):
        """Test beat to seconds conversion."""
        # At 120 BPM, quarter note = 0.5 seconds
        result = self.converter.beats_to_seconds(1.0, 120)
        self.assertEqual(result, 0.5)

        # At 60 BPM, quarter note = 1.0 second
        result = self.converter.beats_to_seconds(1.0, 60)
        self.assertEqual(result, 1.0)

        # Test half note at 120 BPM
        result = self.converter.beats_to_seconds(2.0, 120)
        self.assertEqual(result, 1.0)

    def test_get_instrument_program(self):
        """Test instrument name to MIDI program mapping."""
        if not HAS_PRETTY_MIDI:
            self.skipTest("pretty_midi not available")

        # Test known instruments
        piano_program = self.converter.get_instrument_program("piano")
        self.assertEqual(piano_program, 0)  # Acoustic Grand Piano

        # Test unknown instrument (should default to piano)
        unknown_program = self.converter.get_instrument_program(
            "unknown_instrument")
        self.assertEqual(unknown_program, 0)

    @unittest.skipUnless(HAS_PRETTY_MIDI, "pretty_midi not available")
    def test_create_midi_from_json(self):
        """Test creating MIDI from JSON data."""
        pm = self.converter.create_midi_from_json(self.sample_json)

        # Check basic properties
        self.assertIsInstance(pm, pretty_midi.PrettyMIDI)
        self.assertGreater(len(pm.instruments), 0)

        # Check that notes were created
        total_notes = sum(len(inst.notes) for inst in pm.instruments)
        self.assertGreater(total_notes, 0)

    @unittest.skipUnless(HAS_PRETTY_MIDI, "pretty_midi not available")
    def test_create_midi_from_multiple_json(self):
        """Test creating MIDI from multiple JSON files (ensemble)."""
        json_list = [self.sample_json, self.sample_chord_json]
        pm = self.converter.create_midi_from_multiple_json(json_list)

        # Should have instruments from both JSON files
        self.assertGreaterEqual(len(pm.instruments), 2)

        # Check that tempo is set (get_tempo_changes returns array of [time, tempo])
        tempo_changes = pm.get_tempo_changes()
        self.assertGreater(len(tempo_changes), 0)
        # First tempo change should have a positive tempo value
        if len(tempo_changes[0]) > 1:
            self.assertGreater(tempo_changes[0][1], 0)
        else:
            # Alternative: check initial tempo directly
            self.assertGreater(pm.estimate_tempo(), 0)

    def test_determine_clef(self):
        """Test clef determination based on pitch."""
        # Middle C (60) and above should be treble
        self.assertEqual(self.converter.determine_clef(60), 'treble')
        self.assertEqual(self.converter.determine_clef(72), 'treble')

        # Below middle C should be bass
        self.assertEqual(self.converter.determine_clef(48), 'bass')
        self.assertEqual(self.converter.determine_clef(59), 'bass')

    def test_beats_to_duration_symbol(self):
        """Test conversion from beats back to duration symbols."""
        # Test exact matches
        self.assertEqual(self.converter.beats_to_duration_symbol(1.0), 'q')
        self.assertEqual(self.converter.beats_to_duration_symbol(2.0), 'h')
        self.assertEqual(self.converter.beats_to_duration_symbol(4.0), 'w')

        # Test closest match (should find nearest)
        result = self.converter.beats_to_duration_symbol(1.1)
        self.assertIn(result, self.converter.DURATION_TO_BEATS.keys())

    def test_midi_notes_to_name(self):
        """Test conversion from MIDI notes back to name format."""
        if not HAS_PRETTY_MIDI:
            self.skipTest("pretty_midi not available")

        # Test single note
        result = self.converter.midi_notes_to_name([60])
        self.assertEqual(result, "C4")

        # Test chord
        result = self.converter.midi_notes_to_name([60, 64, 67])
        self.assertEqual(result, "(C4 E4 G4)")

        # Test empty list
        result = self.converter.midi_notes_to_name([])
        self.assertEqual(result, "")

    def test_json_validation(self):
        """Test that JSON data validation works correctly."""
        # Test with minimal valid JSON
        minimal_json = {
            "measures": [[{
                "id": "test-1",
                "name": "C4",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }]]
        }

        if HAS_PRETTY_MIDI:
            # Should not raise an exception
            pm = self.converter.create_midi_from_json(minimal_json)
            self.assertIsInstance(pm, pretty_midi.PrettyMIDI)

    def test_rest_handling(self):
        """Test that rests are handled correctly."""
        json_with_rest = {
            "measures": [[{
                "id": "rest-1",
                "name": "",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": True
            }, {
                "id": "note-1",
                "name": "C4",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }]]
        }

        if HAS_PRETTY_MIDI:
            pm = self.converter.create_midi_from_json(json_with_rest)
            # Should only have one note (rest should be skipped)
            total_notes = sum(len(inst.notes) for inst in pm.instruments)
            self.assertEqual(total_notes, 1)

    def test_file_operations(self):
        """Test file reading and writing operations."""
        if not HAS_PRETTY_MIDI:
            self.skipTest("pretty_midi not available")

        # Create temporary JSON file
        json_file = os.path.join(self.temp_dir, "test.json")
        with open(json_file, 'w') as f:
            json.dump(self.sample_json, f)

        # Create temporary MIDI file
        midi_file = os.path.join(self.temp_dir, "test.mid")

        # Convert JSON to MIDI
        with open(json_file, 'r') as f:
            json_data = json.load(f)

        pm = self.converter.create_midi_from_json(json_data)
        pm.write(midi_file)

        # Verify MIDI file was created
        self.assertTrue(os.path.exists(midi_file))
        self.assertGreater(os.path.getsize(midi_file), 0)

    @unittest.skipUnless(HAS_PRETTY_MIDI, "pretty_midi not available")
    def test_round_trip_conversion(self):
        """Test converting JSON to MIDI and back to JSON."""
        # Convert to MIDI
        pm = self.converter.create_midi_from_json(self.sample_json)

        # Save to temporary file
        midi_file = os.path.join(self.temp_dir, "roundtrip.mid")
        pm.write(midi_file)

        # Convert back to JSON
        json_result = self.converter.create_json_from_midi(midi_file)

        # Verify structure
        self.assertIn('measures', json_result)
        self.assertIn('tempo', json_result)
        self.assertIn('instrument', json_result)
        self.assertIsInstance(json_result['measures'], list)

    def test_error_handling(self):
        """Test that errors are handled gracefully."""
        # Test with invalid note name
        invalid_json = {
            "measures": [[{
                "id": "invalid-1",
                "name": "INVALID_NOTE",
                "clef": "treble",
                "duration": "q",
                "measure": 0,
                "isRest": False
            }]]
        }

        if HAS_PRETTY_MIDI:
            # Should not crash, but should handle the error
            pm = self.converter.create_midi_from_json(invalid_json)
            # Should still create a MIDI object
            self.assertIsInstance(pm, pretty_midi.PrettyMIDI)

    def test_command_line_interface(self):
        """Test the command line interface functions."""
        # This is a basic test to ensure the main function exists and can be called
        self.assertTrue(hasattr(self.converter, 'main'))
        self.assertTrue(callable(self.converter.main))

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary files."""
        import shutil
        try:
            shutil.rmtree(cls.temp_dir)
            print(f"Cleaned up temporary directory: {cls.temp_dir}")
        except Exception as e:
            print(f"Warning: Could not clean up temp directory: {e}")


class TestRunner:
    """Custom test runner with detailed output."""

    def __init__(self, module_name='ugly_midi', verbose=False):
        self.module_name = module_name
        self.verbose = verbose

    def run_tests(self):
        """Run all tests and return results."""
        # Set the module name on the test class
        TestVexFlowMIDIConverter.module_name = self.module_name

        # Create test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestVexFlowMIDIConverter)

        # Run tests
        runner = unittest.TextTestRunner(verbosity=2 if self.verbose else 1,
                                         stream=sys.stdout)

        print(f"Running tests for module: {self.module_name}")
        print(f"Pretty MIDI available: {HAS_PRETTY_MIDI}")
        print("-" * 60)

        result = runner.run(suite)

        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(
            f"Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}"
        )

        if result.failures:
            print("\nFAILURES:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")

        if result.errors:
            print("\nERRORS:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")

        success = len(result.failures) == 0 and len(result.errors) == 0
        print(f"\nOverall result: {'PASS' if success else 'FAIL'}")

        return success


def main():
    """Main function for running tests."""
    parser = argparse.ArgumentParser(
        description='Run automated tests for VexFlow-MIDI converter')
    parser.add_argument(
        '--module-name',
        default='ugly_midi',
        help='Name of the converter module to test (default: ugly_midi)')
    parser.add_argument('--verbose',
                        '-v',
                        action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Check if module file exists
    module_path = f"{args.module_name}.py"
    if not os.path.exists(module_path):
        print(f"Error: Module file '{module_path}' not found!")
        sys.exit(1)

    # Run tests
    test_runner = TestRunner(args.module_name, args.verbose)
    success = test_runner.run_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
