#!/usr/bin/env python3
"""
Compare original and converted JSON files to measure conversion accuracy.

This script compares the musical content of two VexFlow JSON files,
analyzing differences in notes, timing, measures, and other attributes.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def load_json_file(filepath):
    """Load and parse a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def extract_notes(json_data):
    """Extract all notes from measures into a flat list."""
    notes = []
    for measure_idx, measure in enumerate(json_data.get('measures', [])):
        for note in measure:
            notes.append({
                'measure': measure_idx,
                'name': note.get('name', ''),
                'clef': note.get('clef', ''),
                'duration': note.get('duration', ''),
                'isRest': note.get('isRest', False),
            })
    return notes


def parse_note_name(name):
    """Parse note name into individual notes (handles chords)."""
    if not name:
        return []
    if name.startswith('(') and name.endswith(')'):
        # Chord: "(C4 E4 G4)" -> ["C4", "E4", "G4"]
        return name[1:-1].split()
    return [name]


def note_to_midi(note_name):
    """Convert note name to MIDI number for comparison."""
    note_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    
    if not note_name or len(note_name) < 2:
        return None
    
    # Handle sharps and flats
    note = note_name[0]
    octave_start = 1
    
    if len(note_name) > 2:
        if note_name[1] == '#':
            modifier = 1
            octave_start = 2
        elif note_name[1] == 'b':
            modifier = -1
            octave_start = 2
        else:
            modifier = 0
    else:
        modifier = 0
    
    try:
        octave = int(note_name[octave_start:])
        midi_num = note_map.get(note, 0) + modifier + (octave + 1) * 12
        return midi_num
    except (ValueError, IndexError):
        return None


def duration_to_beats(duration):
    """Convert duration symbol to beats."""
    duration_map = {
        'w': 4.0, 'h': 2.0, 'q': 1.0, '8': 0.5, '16': 0.25, '32': 0.125,
        'w.': 6.0, 'h.': 3.0, 'q.': 1.5, '8.': 0.75, '16.': 0.375,
    }
    return duration_map.get(duration, 1.0)


def compare_metadata(original, converted):
    """Compare metadata (tempo, key signature, time signature)."""
    print("=" * 70)
    print("METADATA COMPARISON")
    print("=" * 70)
    
    metadata_fields = ['keySignature', 'tempo', 'instrument']
    matches = 0
    total = len(metadata_fields)
    
    for field in metadata_fields:
        orig_val = original.get(field, 'N/A')
        conv_val = converted.get(field, 'N/A')
        match = "✓" if orig_val == conv_val else "✗"
        print(f"{match} {field:20} Original: {orig_val:15} Converted: {conv_val}")
        if orig_val == conv_val:
            matches += 1
    
    # Time signature
    orig_ts = original.get('timeSignature', {})
    conv_ts = converted.get('timeSignature', {})
    ts_match = (orig_ts.get('numerator') == conv_ts.get('numerator') and 
                orig_ts.get('denominator') == conv_ts.get('denominator'))
    match = "✓" if ts_match else "✗"
    print(f"{match} {'timeSignature':20} Original: {orig_ts.get('numerator')}/{orig_ts.get('denominator'):15} "
          f"Converted: {conv_ts.get('numerator')}/{conv_ts.get('denominator')}")
    if ts_match:
        matches += 1
    total += 1
    
    print(f"\nMetadata Accuracy: {matches}/{total} ({100*matches/total:.1f}%)")
    return matches, total


def compare_measures(original, converted):
    """Compare measure structure."""
    print("\n" + "=" * 70)
    print("MEASURE STRUCTURE")
    print("=" * 70)
    
    orig_measures = len(original.get('measures', []))
    conv_measures = len(converted.get('measures', []))
    
    print(f"Original measures:  {orig_measures}")
    print(f"Converted measures: {conv_measures}")
    
    return orig_measures, conv_measures


def compare_notes(original, converted):
    """Compare note content in detail."""
    print("\n" + "=" * 70)
    print("NOTE COMPARISON")
    print("=" * 70)
    
    orig_notes = extract_notes(original)
    conv_notes = extract_notes(converted)
    
    # Count total notes (including chord notes)
    orig_note_count = 0
    conv_note_count = 0
    orig_rest_count = 0
    conv_rest_count = 0
    
    for note in orig_notes:
        if note['isRest']:
            orig_rest_count += 1
        else:
            orig_note_count += len(parse_note_name(note['name']))
    
    for note in conv_notes:
        if note['isRest']:
            conv_rest_count += 1
        else:
            conv_note_count += len(parse_note_name(note['name']))
    
    print(f"Original notes:     {orig_note_count} (rests: {orig_rest_count})")
    print(f"Converted notes:    {conv_note_count} (rests: {conv_rest_count})")
    print(f"Note preservation:  {100*min(orig_note_count, conv_note_count)/max(orig_note_count, conv_note_count):.1f}%")
    
    # Collect all pitches
    orig_pitches = []
    conv_pitches = []
    
    for note in orig_notes:
        if not note['isRest']:
            for note_name in parse_note_name(note['name']):
                midi_num = note_to_midi(note_name)
                if midi_num:
                    orig_pitches.append(midi_num)
    
    for note in conv_notes:
        if not note['isRest']:
            for note_name in parse_note_name(note['name']):
                midi_num = note_to_midi(note_name)
                if midi_num:
                    conv_pitches.append(midi_num)
    
    # Count matching pitches
    orig_pitch_counts = defaultdict(int)
    conv_pitch_counts = defaultdict(int)
    
    for pitch in orig_pitches:
        orig_pitch_counts[pitch] += 1
    for pitch in conv_pitches:
        conv_pitch_counts[pitch] += 1
    
    matching_pitches = 0
    for pitch, count in orig_pitch_counts.items():
        matching_pitches += min(count, conv_pitch_counts.get(pitch, 0))
    
    pitch_accuracy = 100 * matching_pitches / max(len(orig_pitches), 1)
    print(f"Pitch accuracy:     {pitch_accuracy:.1f}%")
    
    # Duration analysis
    orig_total_beats = sum(duration_to_beats(n['duration']) for n in orig_notes if not n['isRest'])
    conv_total_beats = sum(duration_to_beats(n['duration']) for n in conv_notes if not n['isRest'])
    
    print(f"\nOriginal duration:  {orig_total_beats:.2f} beats")
    print(f"Converted duration: {conv_total_beats:.2f} beats")
    duration_accuracy = 100 * min(orig_total_beats, conv_total_beats) / max(orig_total_beats, conv_total_beats)
    print(f"Duration accuracy:  {duration_accuracy:.1f}%")
    
    # Clef distribution
    orig_clef_counts = defaultdict(int)
    conv_clef_counts = defaultdict(int)
    
    for note in orig_notes:
        if not note['isRest']:
            orig_clef_counts[note['clef']] += 1
    for note in conv_notes:
        if not note['isRest']:
            conv_clef_counts[note['clef']] += 1
    
    print(f"\nClef distribution:")
    print(f"  Original:  Treble={orig_clef_counts.get('treble', 0)}, Bass={orig_clef_counts.get('bass', 0)}")
    print(f"  Converted: Treble={conv_clef_counts.get('treble', 0)}, Bass={conv_clef_counts.get('bass', 0)}")
    
    return pitch_accuracy, duration_accuracy, orig_note_count, conv_note_count


def calculate_overall_accuracy(pitch_acc, duration_acc, metadata_matches, metadata_total):
    """Report weighted overall accuracy without interpreting it."""
    print("\n" + "=" * 70)
    print("OVERALL ACCURACY")
    print("=" * 70)

    # Weighted average: pitches, durations, and metadata
    pitch_weight = 0.5
    duration_weight = 0.3
    metadata_weight = 0.2

    metadata_acc = 100 * metadata_matches / metadata_total

    overall = (pitch_acc * pitch_weight +
               duration_acc * duration_weight +
               metadata_acc * metadata_weight)

    print(f"Pitch accuracy:     {pitch_acc:.1f}% (weight: {pitch_weight*100:.0f}%)")
    print(f"Duration accuracy:  {duration_acc:.1f}% (weight: {duration_weight*100:.0f}%)")
    print(f"Metadata accuracy:  {metadata_acc:.1f}% (weight: {metadata_weight*100:.0f}%)")
    print(f"\n{'='*70}")
    print(f"OVERALL ACCURACY:   {overall:.1f}%")
    print(f"{'='*70}")

    return overall


def main():
    """Main comparison function."""
    if len(sys.argv) != 3:
        print("Usage: python compare_json.py <original.json> <converted.json>")
        sys.exit(1)
    
    original_file = Path(sys.argv[1])
    converted_file = Path(sys.argv[2])
    
    if not original_file.exists():
        print(f"Error: Original file '{original_file}' not found")
        sys.exit(1)
    
    if not converted_file.exists():
        print(f"Error: Converted file '{converted_file}' not found")
        sys.exit(1)
    
    print(f"\nComparing JSON files:")
    print(f"  Original:  {original_file}")
    print(f"  Converted: {converted_file}\n")
    
    # Load files
    original = load_json_file(original_file)
    converted = load_json_file(converted_file)
    
    # Perform comparisons
    metadata_matches, metadata_total = compare_metadata(original, converted)
    compare_measures(original, converted)
    pitch_acc, duration_acc, orig_notes, conv_notes = compare_notes(original, converted)
    
    # Calculate overall accuracy
    overall_acc = calculate_overall_accuracy(pitch_acc, duration_acc, 
                                            metadata_matches, metadata_total)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Overall accuracy: {overall_acc:.1f}%")
    print("See sections above for detailed differences in metadata, notes, and measures.")


if __name__ == '__main__':
    main()
