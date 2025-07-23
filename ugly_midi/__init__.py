#!/usr/bin/env python3
"""
ugly_midi - A bidirectional converter between VexFlow-style JSON music notation and MIDI files.

This package provides functions to convert between VexFlow JSON format and MIDI files,
making it easy to work with music notation data in web applications and Python scripts.

Basic Usage:
    import ugly_midi

    # Convert JSON to MIDI
    midi_data = ugly_midi.json_to_midi(json_data)
    ugly_midi.save_midi(midi_data, "output.mid")

    # Convert MIDI to JSON
    json_data = ugly_midi.midi_to_json("input.mid")

    # Work with multiple instruments
    ensemble_midi = ugly_midi.create_ensemble([piano_json, guitar_json])
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"
__license__ = "MIT"

# Import main functions for easy access
from .converter import (
    # Core conversion functions
    create_midi_from_json,
    create_midi_from_multiple_json,
    create_json_from_midi,
    create_json_from_midi_file,

    # Helper functions
    parse_note_name,
    beats_to_seconds,
    get_instrument_program,
    determine_clef,
    midi_notes_to_name,
    beats_to_duration_symbol,

    # Constants
    DURATION_TO_BEATS,
)


# Convenient aliases for common operations
def json_to_midi(json_data, tempo_override=None):
    """
    Convert VexFlow JSON to MIDI data.

    Args:
        json_data (dict): VexFlow JSON data
        tempo_override (int, optional): Override tempo in BPM

    Returns:
        pretty_midi.PrettyMIDI: MIDI data object

    Example:
        >>> midi = ugly_midi.json_to_midi(my_json_data)
        >>> midi.write('output.mid')
    """
    if tempo_override:
        return create_midi_from_multiple_json([json_data], tempo_override)
    return create_midi_from_json(json_data)


def midi_to_json(midi_file_path, quantize_resolution=0.25):
    """
    Convert MIDI file to VexFlow JSON format.

    Args:
        midi_file_path (str): Path to MIDI file
        quantize_resolution (float): Quantization resolution in beats

    Returns:
        dict: VexFlow JSON data

    Example:
        >>> json_data = ugly_midi.midi_to_json('input.mid')
        >>> print(json_data['tempo'])
    """
    return create_json_from_midi(midi_file_path, quantize_resolution)


def create_ensemble(json_data_list, output_tempo=None):
    """
    Create a multi-instrument MIDI from multiple JSON files.

    Args:
        json_data_list (list): List of VexFlow JSON data objects
        output_tempo (int, optional): Override tempo for all instruments

    Returns:
        pretty_midi.PrettyMIDI: MIDI data object with multiple instruments

    Example:
        >>> piano_json = {...}
        >>> guitar_json = {...}
        >>> ensemble = ugly_midi.create_ensemble([piano_json, guitar_json])
        >>> ensemble.write('band.mid')
    """
    return create_midi_from_multiple_json(json_data_list, output_tempo)


def save_midi(midi_data, output_path):
    """
    Save MIDI data to file.

    Args:
        midi_data (pretty_midi.PrettyMIDI): MIDI data object
        output_path (str): Output file path

    Example:
        >>> midi = ugly_midi.json_to_midi(json_data)
        >>> ugly_midi.save_midi(midi, 'song.mid')
    """
    midi_data.write(output_path)


def load_json_file(json_file_path):
    """
    Load VexFlow JSON from file.

    Args:
        json_file_path (str): Path to JSON file

    Returns:
        dict: VexFlow JSON data

    Example:
        >>> json_data = ugly_midi.load_json_file('song.json')
        >>> midi = ugly_midi.json_to_midi(json_data)
    """
    import json
    with open(json_file_path, 'r') as f:
        return json.load(f)


def save_json_file(json_data, output_path):
    """
    Save VexFlow JSON to file.

    Args:
        json_data (dict): VexFlow JSON data
        output_path (str): Output file path

    Example:
        >>> json_data = ugly_midi.midi_to_json('input.mid')
        >>> ugly_midi.save_json_file(json_data, 'output.json')
    """
    import json
    with open(output_path, 'w') as f:
        json.dump(json_data, f, indent=2)


# Make commonly used constants available
__all__ = [
    # Main conversion functions
    'json_to_midi',
    'midi_to_json',
    'create_ensemble',

    # File operations
    'save_midi',
    'load_json_file',
    'save_json_file',

    # Advanced functions (from converter module)
    'create_midi_from_json',
    'create_midi_from_multiple_json',
    'create_json_from_midi',
    'create_json_from_midi_file',

    # Utility functions
    'parse_note_name',
    'beats_to_seconds',
    'get_instrument_program',
    'determine_clef',
    'midi_notes_to_name',
    'beats_to_duration_symbol',

    # Constants
    'DURATION_TO_BEATS',

    # Package info
    '__version__',
    '__author__',
    '__email__',
    '__license__'
]
