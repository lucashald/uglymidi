#!/usr/bin/env python3
"""
VexFlow JSON to MIDI Converter

Converts VexFlow-style JSON music notation to MIDI files using pretty_midi.

Usage:
    python ugly_midi.py input.json output.mid
"""

import argparse
import json
import sys
from pathlib import Path
import pretty_midi

# Duration mappings from VexFlow notation to beats
DURATION_TO_BEATS = {
    'w': 4.0,  # whole note
    'h': 2.0,  # half note  
    'q': 1.0,  # quarter note
    '8': 0.5,  # eighth note
    '16': 0.25,  # sixteenth note
    '32': 0.125,  # thirty-second note
    'w.': 6.0,  # dotted whole (6 beats)
    'h.': 3.0,  # dotted half (3 beats)
    'q.': 1.5,  # dotted quarter (1.5 beats)
    '8.': 0.75,  # dotted eighth (0.75 beats)
    '16.': 0.375,  # dotted sixteenth (0.375 beats)
}


def parse_note_name(name):
    """
    Parse a VexFlow note name into MIDI note numbers.

    Args:
        name (str): Note name like "C4" or "(C4 E4 G4)"

    Returns:
        list: List of MIDI note numbers
    """
    if name.startswith('(') and name.endswith(')'):
        # Chord notation: "(C4 E4 G4)"
        note_names = name[1:-1].split()
        return [pretty_midi.note_name_to_number(note) for note in note_names]
    else:
        # Single note: "C4"
        return [pretty_midi.note_name_to_number(name)]


def beats_to_seconds(beats, tempo):
    """
    Convert beats to seconds based on tempo.

    Args:
        beats (float): Duration in beats
        tempo (int): Beats per minute

    Returns:
        float: Duration in seconds
    """
    return (beats * 60.0) / tempo


def calculate_note_timing(note_data, measure_start_times, tempo):
    """
    Calculate the absolute start time for a note.

    Args:
        note_data (dict): Note information
        measure_start_times (list): Start time of each measure in seconds
        tempo (int): Tempo in BPM

    Returns:
        float: Start time in seconds
    """
    measure_num = note_data['measure']
    measure_start = measure_start_times[measure_num]

    # For now, we'll calculate position within measure based on order
    # A more sophisticated approach would track beat positions
    return measure_start


def process_measures(measures, tempo, time_signature):
    """
    Process all measures and calculate timing.

    Args:
        measures (list): List of measure arrays
        tempo (int): Tempo in BPM
        time_signature (dict): Time signature with numerator/denominator

    Returns:
        tuple: (notes_by_clef, measure_durations)
    """
    notes_by_clef = {'treble': [], 'bass': []}
    measure_durations = []

    # Calculate measure duration based on time signature
    beats_per_measure = time_signature['numerator']
    beat_unit = time_signature['denominator']

    # Convert to quarter note beats (pretty_midi works in quarter note beats)
    measure_duration_beats = beats_per_measure * (4.0 / beat_unit)

    for measure_idx, measure in enumerate(measures):
        measure_duration_seconds = beats_to_seconds(measure_duration_beats,
                                                    tempo)
        measure_durations.append(measure_duration_seconds)

        # Group notes by clef and track their position within the measure
        clef_positions = {'treble': 0.0, 'bass': 0.0}

        # Sort notes by their ID timestamp to maintain order
        measure_notes = sorted(measure, key=lambda x: x.get('id', ''))

        for note_data in measure_notes:
            if note_data.get('isRest', False):
                # For rests, just advance the position
                duration_beats = DURATION_TO_BEATS.get(note_data['duration'],
                                                       1.0)
                clef_positions[note_data['clef']] += duration_beats
                continue

            clef = note_data['clef']

            # Calculate absolute start time
            measure_start = sum(measure_durations[:measure_idx])
            beat_offset = clef_positions[clef]
            start_time = measure_start + beats_to_seconds(beat_offset, tempo)

            # Calculate duration
            duration_beats = DURATION_TO_BEATS.get(note_data['duration'], 1.0)
            duration_seconds = beats_to_seconds(duration_beats, tempo)

            # Parse note names to MIDI numbers
            try:
                midi_notes = parse_note_name(note_data['name'])
            except Exception as e:
                print(
                    f"Warning: Could not parse note '{note_data['name']}': {e}"
                )
                continue

            # Create note data
            for midi_note in midi_notes:
                note_info = {
                    'start_time': start_time,
                    'end_time': start_time + duration_seconds,
                    'midi_note': midi_note,
                    'velocity': 80,  # Default velocity
                    'original_data': note_data
                }
                notes_by_clef[clef].append(note_info)

            # Advance position for this clef
            clef_positions[clef] += duration_beats

    return notes_by_clef, measure_durations


def get_instrument_program(instrument_name):
    """
    Map instrument names to MIDI program numbers.

    Args:
        instrument_name (str): Instrument name

    Returns:
        int: MIDI program number
    """
    instrument_map = {
        'piano': 'Acoustic Grand Piano',
        'guitar': 'Acoustic Guitar (nylon)',
        'cello': 'Cello',
        'violin': 'Violin',
        'sax': 'Alto Sax',
        'saxophone': 'Alto Sax',
        'drums': 'Acoustic Grand Piano',  # Will be handled specially
    }

    instrument_display_name = instrument_map.get(instrument_name.lower(),
                                                 'Acoustic Grand Piano')

    try:
        return pretty_midi.instrument_name_to_program(instrument_display_name)
    except (ValueError, KeyError):
        # Fallback to piano if instrument not found
        return pretty_midi.instrument_name_to_program('Acoustic Grand Piano')


def create_midi_from_multiple_json(json_files_data, output_tempo=None):
    """
    Convert multiple VexFlow JSON objects to a single PrettyMIDI object.
    Each JSON represents a separate instrument part.

    Args:
        json_files_data (list): List of parsed JSON data objects
        output_tempo (int, optional): Override tempo for all parts

    Returns:
        pretty_midi.PrettyMIDI: Generated MIDI object with multiple instruments
    """
    if not json_files_data:
        raise ValueError("No JSON data provided")

    # Use tempo from first file or override
    tempo = output_tempo or json_files_data[0].get('tempo', 120)

    # Use time signature from first file (could be made more sophisticated)
    time_signature = json_files_data[0].get('timeSignature', {
        'numerator': 4,
        'denominator': 4
    })

    # Use key signature from first file
    key_signature = json_files_data[0].get('keySignature', 'C')

    # Create PrettyMIDI object
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    # Add time signature if not 4/4
    if time_signature['numerator'] != 4 or time_signature['denominator'] != 4:
        time_sig = pretty_midi.TimeSignature(time_signature['numerator'],
                                             time_signature['denominator'], 0)
        pm.time_signature_changes.append(time_sig)

    # Add key signature if not C major
    if key_signature != 'C':
        try:
            key_number = pretty_midi.key_name_to_key_number(key_signature)
            key_sig = pretty_midi.KeySignature(key_number, 0)
            pm.key_signature_changes.append(key_sig)
        except (ValueError, AttributeError):
            print(f"Warning: Could not set key signature '{key_signature}'")

    used_channels = set()

    # Process each JSON file as a separate instrument
    for file_idx, json_data in enumerate(json_files_data):
        instrument_name = json_data.get('instrument',
                                        f'instrument_{file_idx + 1}')
        requested_channel = int(json_data.get('midiChannel', str(file_idx)))
        measures = json_data.get('measures', [])

        # Auto-assign channel if already used
        channel = requested_channel
        while channel in used_channels:
            channel += 1
            if channel >= 16:  # MIDI only has 16 channels
                print(
                    "Warning: Too many instruments, wrapping channel assignments"
                )
                channel = 0
                break
        used_channels.add(channel)

        if channel != requested_channel:
            print(
                f"Channel {requested_channel} already used, assigned channel {channel} to {instrument_name}"
            )

        # Process measures for this instrument
        notes_by_clef, _ = process_measures(measures, tempo, time_signature)

        # Get instrument program number
        program = get_instrument_program(instrument_name)

        # Create instruments for each clef that has notes
        for clef, notes in notes_by_clef.items():
            if not notes:
                continue

            # Create unique instrument name
            if len(notes_by_clef) > 1 and any(notes_by_clef.values()):
                instrument_display_name = f'{instrument_name.title()} ({clef.title()})'
            else:
                instrument_display_name = instrument_name.title()

            # Create instrument
            instrument = pretty_midi.Instrument(program=program,
                                                name=instrument_display_name)

            # Add notes to instrument
            for note_info in notes:
                note = pretty_midi.Note(velocity=note_info['velocity'],
                                        pitch=note_info['midi_note'],
                                        start=note_info['start_time'],
                                        end=note_info['end_time'])
                instrument.notes.append(note)

            # Add instrument to MIDI
            pm.instruments.append(instrument)

    return pm


def create_midi_from_json(json_data):
    """
    Convert single VexFlow JSON to a PrettyMIDI object.
    Wrapper around create_midi_from_multiple_json for backwards compatibility.

    Args:
        json_data (dict): Parsed JSON data

    Returns:
        pretty_midi.PrettyMIDI: Generated MIDI object
    """
    return create_midi_from_multiple_json([json_data])


def beats_to_duration_symbol(beats):
    """
    Convert beats to the closest VexFlow duration symbol.

    Args:
        beats (float): Duration in beats

    Returns:
        str: VexFlow duration symbol
    """
    # Find the closest duration
    closest_duration = 'q'  # Default to quarter note
    closest_diff = float('inf')

    for symbol, duration_beats in DURATION_TO_BEATS.items():
        diff = abs(beats - duration_beats)
        if diff < closest_diff:
            closest_diff = diff
            closest_duration = symbol

    return closest_duration


def midi_notes_to_name(midi_notes):
    """
    Convert MIDI note numbers to VexFlow note name format.

    Args:
        midi_notes (list): List of MIDI note numbers

    Returns:
        str: VexFlow note name (single note or chord)
    """
    if not midi_notes:
        return ""

    note_names = []
    for midi_note in sorted(midi_notes):
        try:
            note_name = pretty_midi.note_number_to_name(midi_note)
            note_names.append(note_name)
        except (ValueError, IndexError):
            continue

    if len(note_names) == 1:
        return note_names[0]
    elif len(note_names) > 1:
        return f"({' '.join(note_names)})"
    else:
        return ""


def determine_clef(midi_note):
    """
    Determine appropriate clef based on MIDI note number.

    Args:
        midi_note (int): MIDI note number

    Returns:
        str: 'treble' or 'bass'
    """
    # Middle C (60) is the dividing line
    # Notes 60 and above go to treble, below 60 go to bass
    return 'treble' if midi_note >= 60 else 'bass'


def create_json_from_midi(midi_file_path, quantize_resolution=0.25):
    """
    Convert a MIDI file to VexFlow JSON format using pretty_midi.

    Args:
        midi_file_path (str): Path to MIDI file
        quantize_resolution (float): Quantization resolution in beats (0.25 = sixteenth note)

    Returns:
        dict: VexFlow JSON data
    """
    # Load MIDI file
    try:
        pm = pretty_midi.PrettyMIDI(midi_file_path)
    except Exception as e:
        raise ValueError(f"Could not load MIDI file: {e}")

    if not pm.instruments:
        raise ValueError("MIDI file contains no instruments")

    # Extract basic metadata
    tempo = pm.estimate_tempo() if pm.estimate_tempo() > 0 else 120

    # Get key signature (use first one, default to C)
    key_signature = 'C'
    if pm.key_signature_changes:
        try:
            key_number = pm.key_signature_changes[0].key_number
            key_signature = pretty_midi.key_number_to_key_name(key_number)
        except (IndexError, ValueError, AttributeError):
            pass

    # Get time signature (use first one, default to 4/4)
    time_signature = {'numerator': 4, 'denominator': 4}
    if pm.time_signature_changes:
        ts = pm.time_signature_changes[0]
        time_signature = {
            'numerator': ts.numerator,
            'denominator': ts.denominator
        }

    # Determine instrument (use first non-drum instrument)
    instrument_name = 'piano'
    main_instrument = None
    for inst in pm.instruments:
        if not inst.is_drum:
            main_instrument = inst
            break

    if main_instrument:
        try:
            program_name = pretty_midi.program_to_instrument_name(
                main_instrument.program)
            # Map back to our simplified names
            instrument_map = {
                'Acoustic Grand Piano': 'piano',
                'Acoustic Guitar (nylon)': 'guitar',
                'Acoustic Guitar (steel)': 'guitar',
                'Electric Guitar (clean)': 'guitar',
                'Cello': 'cello',
                'Violin': 'violin',
                'Alto Sax': 'sax',
            }
            instrument_name = instrument_map.get(program_name, 'piano')
        except (ValueError, AttributeError):
            pass

    # Calculate measure duration in seconds
    beats_per_measure = time_signature['numerator'] * (
        4.0 / time_signature['denominator'])
    measure_duration = (beats_per_measure * 60.0) / tempo

    # Collect all notes from all non-drum instruments
    all_notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue

        for note in inst.notes:
            # Determine clef based on pitch
            clef = determine_clef(note.pitch)

            # Calculate measure and position within measure
            measure_num = int(note.start / measure_duration)

            # Calculate duration in beats
            duration_seconds = note.end - note.start
            duration_beats = (duration_seconds * tempo) / 60.0

            all_notes.append({
                'start_time': note.start,
                'end_time': note.end,
                'measure': measure_num,
                'clef': clef,
                'midi_note': note.pitch,
                'velocity': note.velocity,
                'duration_beats': duration_beats
            })

    # Sort notes by time
    all_notes.sort(key=lambda x: (x['measure'], x['start_time']))

    # Group notes into measures
    measures = []
    if all_notes:
        max_measure = max(note['measure'] for note in all_notes)

        for measure_idx in range(max_measure + 1):
            measure_notes = [
                n for n in all_notes if n['measure'] == measure_idx
            ]

            # Group simultaneous notes (chords)
            chord_groups = []
            current_group = []
            current_time = None

            for note in measure_notes:
                # If this note starts at roughly the same time as the current group, add it
                if current_time is None or abs(note['start_time'] -
                                               current_time) < 0.1:
                    current_group.append(note)
                    current_time = note[
                        'start_time'] if current_time is None else current_time
                else:
                    # Start a new group
                    if current_group:
                        chord_groups.append(current_group)
                    current_group = [note]
                    current_time = note['start_time']

            # Don't forget the last group
            if current_group:
                chord_groups.append(current_group)

            # Convert chord groups to VexFlow format
            measure_data = []
            note_id_counter = 1

            for group in chord_groups:
                # Group by clef
                clef_groups = {}
                for note in group:
                    clef = note['clef']
                    if clef not in clef_groups:
                        clef_groups[clef] = []
                    clef_groups[clef].append(note)

                # Create note objects for each clef
                for clef, clef_notes in clef_groups.items():
                    midi_notes = [n['midi_note'] for n in clef_notes]
                    note_name = midi_notes_to_name(midi_notes)

                    # Use average duration for the chord
                    avg_duration = sum(n['duration_beats']
                                       for n in clef_notes) / len(clef_notes)
                    duration_symbol = beats_to_duration_symbol(avg_duration)

                    note_data = {
                        'id': f'converted-{measure_idx}-{note_id_counter}',
                        'name': note_name,
                        'clef': clef,
                        'duration': duration_symbol,
                        'measure': measure_idx,
                        'isRest': False
                    }

                    measure_data.append(note_data)
                    note_id_counter += 1

            measures.append(measure_data)

    # Build final JSON structure
    json_data = {
        'keySignature': key_signature,
        'tempo': int(tempo),
        'timeSignature': time_signature,
        'instrument': instrument_name,
        'midiChannel': '0',
        'measures': measures
    }

    return json_data


def create_json_from_midi_file(midi_file_path, output_json_path):
    """
    Convert MIDI file to JSON and save to file.

    Args:
        midi_file_path (str): Path to input MIDI file
        output_json_path (str): Path to save JSON file

    Returns:
        dict: VexFlow JSON data
    """
    json_data = create_json_from_midi(midi_file_path)

    with open(output_json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"Successfully saved JSON to '{output_json_path}'")

    return json_data


def main():
    """Main command line interface."""
    parser = argparse.ArgumentParser(
        description='Convert between VexFlow JSON and MIDI files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # JSON to MIDI (single instrument)
    python ugly_midi.py song.json --output song.mid

    # JSON to MIDI (multiple instruments/symphony)
    python ugly_midi.py piano.json guitar.json --output ensemble.mid

    # MIDI to JSON
    python ugly_midi.py song.mid --to-json song.json
    python ugly_midi.py song.mid --to-json  # prints to stdout
        """)
    parser.add_argument('inputs',
                        nargs='+',
                        help='Input file(s) - JSON or MIDI')
    parser.add_argument('output',
                        nargs='?',
                        help='Output file (for single input files)')
    parser.add_argument('--output',
                        '-o',
                        dest='output_flag',
                        help='Output file')
    parser.add_argument(
        '--to-json',
        dest='to_json',
        nargs='?',
        const=True,
        help='Convert MIDI to JSON (optionally specify output file)')
    parser.add_argument('--tempo',
                        type=int,
                        help='Override tempo (BPM) for all instruments')
    parser.add_argument('--verbose',
                        '-v',
                        action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Determine conversion direction
    if args.to_json:
        # MIDI to JSON conversion
        if len(args.inputs) != 1:
            print(
                "Error: MIDI to JSON conversion requires exactly one input file"
            )
            sys.exit(1)

        midi_file = args.inputs[0]
        if not Path(midi_file).exists():
            print(f"Error: MIDI file '{midi_file}' not found")
            sys.exit(1)

        try:
            json_data = create_json_from_midi(midi_file)

            if args.to_json is True:
                # Print to stdout
                print(json.dumps(json_data, indent=2))
            else:
                # Save to specified file
                with open(args.to_json, 'w') as f:
                    json.dump(json_data, f, indent=2)
                print(f"Successfully converted MIDI to JSON: '{args.to_json}'")

        except Exception as e:
            print(f"Error converting MIDI to JSON: {e}")
            sys.exit(1)

        return

    # JSON to MIDI conversion (original functionality)
    # Handle output file argument
    if len(args.inputs) == 1 and not args.output_flag:
        # Single file mode: python script.py input.json output.mid
        if args.output:
            input_files = [args.inputs[0]]
            output_file = args.output
        else:
            # Single file mode with --output flag
            input_files = [args.inputs[0]]
            output_file = args.output_flag
            if not output_file:
                print(
                    "Error: Output file required. Use: python script.py input.json --output output.mid"
                )
                sys.exit(1)
    else:
        # Multiple file mode: python script.py file1.json file2.json --output out.mid
        input_files = args.inputs
        output_file = args.output_flag or args.output
        if not output_file:
            print("Error: --output required when using multiple input files")
            sys.exit(1)

    # Validate input files
    json_data_list = []
    for input_file in input_files:
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"Error: Input file '{input_file}' not found")
            sys.exit(1)

        # Load JSON data
        try:
            with open(input_path, 'r') as f:
                json_data = json.load(f)
            json_data_list.append(json_data)
            if args.verbose:
                instrument = json_data.get('instrument', 'unknown')
                measures = len(json_data.get('measures', []))
                print(
                    f"Loaded {input_file}: {instrument} ({measures} measures)")
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in '{input_file}': {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading '{input_file}': {e}")
            sys.exit(1)

    if args.verbose:
        print(f"Processing {len(json_data_list)} instrument(s)")

    # Convert to MIDI
    try:
        pm = create_midi_from_multiple_json(json_data_list, args.tempo)
        if args.verbose:
            print(f"Created MIDI with {len(pm.instruments)} instrument tracks")
            total_notes = sum(len(inst.notes) for inst in pm.instruments)
            print(f"Total notes: {total_notes}")
            print("Instruments:")
            for i, inst in enumerate(pm.instruments):
                print(f"  {i+1}. {inst.name} ({len(inst.notes)} notes)")
    except Exception as e:
        print(f"Error converting JSON to MIDI: {e}")
        sys.exit(1)

    # Save MIDI file
    try:
        pm.write(output_file)
        if len(json_data_list) > 1:
            print(f"Successfully saved symphony MIDI to '{output_file}'")
        else:
            print(f"Successfully saved MIDI to '{output_file}'")
    except Exception as e:
        print(f"Error saving MIDI file: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
