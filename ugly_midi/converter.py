#!/usr/bin/env python3
"""
Core conversion functions for ugly_midi package.

This module contains all the main conversion logic between VexFlow JSON
and MIDI formats, without the command-line interface.
"""

import json
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


def quantize_time(time_seconds, quantize_resolution, tempo):
    """
    Quantize a time value to the nearest quantization resolution.
    
    Args:
        time_seconds (float): Time in seconds
        quantize_resolution (float): Quantization resolution in beats (e.g., 0.25 for sixteenth notes)
        tempo (int): Tempo in BPM
    
    Returns:
        float: Quantized time in seconds
    """
    # Convert time to beats
    beats = (time_seconds * tempo) / 60.0
    
    # Quantize to nearest resolution
    quantized_beats = round(beats / quantize_resolution) * quantize_resolution
    
    # Convert back to seconds
    return (quantized_beats * 60.0) / tempo


def calculate_duration_with_quantization(start_time, end_time, tempo, quantize_resolution=0.25):
    """
    Calculate note duration with proper quantization.
    
    Args:
        start_time (float): Note start time in seconds
        end_time (float): Note end time in seconds
        tempo (int): Tempo in BPM
        quantize_resolution (float): Quantization resolution in beats
    
    Returns:
        float: Duration in beats (quantized)
    """
    # Quantize start and end times
    quantized_start = quantize_time(start_time, quantize_resolution, tempo)
    quantized_end = quantize_time(end_time, quantize_resolution, tempo)
    
    # Calculate duration in seconds
    duration_seconds = quantized_end - quantized_start
    
    # Convert to beats
    duration_beats = (duration_seconds * tempo) / 60.0
    
    # Ensure minimum duration (don't allow zero or negative durations)
    return max(duration_beats, quantize_resolution)


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


def beats_to_duration_symbol_improved(beats, allow_compound=True):
    """
    Convert beats to VexFlow duration symbol with better logic.
    
    Args:
        beats (float): Duration in beats
        allow_compound (bool): Whether to allow compound durations like dotted notes
    
    Returns:
        str: VexFlow duration symbol
    """
    # Handle exact matches first
    for symbol, duration_beats in DURATION_TO_BEATS.items():
        if abs(beats - duration_beats) < 0.001:  # Very small tolerance for floating point
            return symbol
    
    # If no exact match, find closest
    closest_duration = 'q'  # Default to quarter note
    closest_diff = float('inf')
    
    # Prioritize simple durations over dotted ones if allow_compound is False
    duration_items = list(DURATION_TO_BEATS.items())
    if not allow_compound:
        duration_items = [(k, v) for k, v in duration_items if '.' not in k]
    
    for symbol, duration_beats in duration_items:
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


def determine_instrument_name(pm):
    """Helper function to determine instrument name from PrettyMIDI object."""
    for inst in pm.instruments:
        if not inst.is_drum:
            try:
                program_name = pretty_midi.program_to_instrument_name(inst.program)
                instrument_map = {
                    'Acoustic Grand Piano': 'piano',
                    'Acoustic Guitar (nylon)': 'guitar',
                    'Acoustic Guitar (steel)': 'guitar',
                    'Electric Guitar (clean)': 'guitar',
                    'Cello': 'cello',
                    'Violin': 'violin',
                    'Alto Sax': 'sax',
                }
                return instrument_map.get(program_name, 'piano')
            except (ValueError, AttributeError):
                pass
    return 'piano'

def analyze_measure_clef_distribution(time_groups):
    """
    Analyze how notes would be distributed across clefs to prevent overloading.
    """
    clef_loads = {'treble': 0, 'bass': 0}
    clef_complexity = {'treble': 0, 'bass': 0}
    
    for start_time, time_group in time_groups.items():
        for duration_beats, duration_group in time_group.items():
            for note in duration_group:
                # Count notes per clef
                default_clef = 'treble' if note['midi_note'] >= 60 else 'bass'
                clef_loads[default_clef] += 1
                
                # Count complexity (chords = more complex)
                if len(duration_group) > 1:
                    clef_complexity[default_clef] += len(duration_group)
    
    return clef_loads, clef_complexity


def determine_clef_with_load_balancing(note_group, measure_context):
    """
    Determine clef considering both note range and measure load balancing.
    """
    if not note_group:
        return 'treble'
    
    note_group.sort(key=lambda x: x['midi_note'])
    lowest_note = note_group[0]['midi_note']
    highest_note = note_group[-1]['midi_note']
    
    # Get current clef loads from measure context
    treble_load = measure_context.get('treble_load', 0)
    bass_load = measure_context.get('bass_load', 0)
    
    # Clear cases - no balancing needed
    if highest_note < 57:  # Below A3 = definitely bass
        return 'bass'
    elif lowest_note >= 67:  # Above G4 = definitely treble
        return 'treble'
    
    # Borderline cases (A3 to G4) - use load balancing
    
    # If one clef is significantly overloaded, prefer the other
    load_difference = treble_load - bass_load
    
    if load_difference > 3:  # Treble overloaded
        return 'bass'
    elif load_difference < -3:  # Bass overloaded
        return 'treble'
    
    # For borderline notes, use musical logic
    if lowest_note < 60:  # Contains notes below C4
        if highest_note <= 65:  # Up to F4 - could be bass
            return 'bass'
        else:  # Spans too high - treble
            return 'treble'
    else:  # All notes C4 and above
        return 'treble'


def split_complex_chord_across_clefs(note_group):
    """
    Split a complex chord across treble and bass clefs if needed.
    """
    if len(note_group) <= 3:
        return None  # Don't split simple chords
    
    note_group.sort(key=lambda x: x['midi_note'])
    
    # Split point around C4 (MIDI 60)
    bass_notes = [n for n in note_group if n['midi_note'] < 62]  # Below D4
    treble_notes = [n for n in note_group if n['midi_note'] >= 58]  # Above A#3
    
    # Only split if both parts have reasonable notes
    if len(bass_notes) >= 2 and len(treble_notes) >= 2:
        return {
            'bass_part': bass_notes,
            'treble_part': treble_notes
        }
    
    return None


def create_json_from_midi(midi_file_path, quantize_resolution=0.125, manual_tempo=142):
    """
    MIDI to JSON with smart clef balancing to prevent VexFlow "too many ticks".
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_file_path)
    except Exception as e:
        raise ValueError(f"Could not load MIDI file: {e}")

    if not pm.instruments:
        raise ValueError("MIDI file contains no instruments")

    tempo = manual_tempo
    print(f"Using precise tempo: {tempo} BPM")

    # Get metadata
    key_signature = 'C'
    if pm.key_signature_changes:
        try:
            key_number = pm.key_signature_changes[0].key_number
            key_signature = pretty_midi.key_number_to_key_name(key_number)
        except (IndexError, ValueError, AttributeError):
            pass

    time_signature = {'numerator': 4, 'denominator': 4}
    if pm.time_signature_changes:
        ts = pm.time_signature_changes[0]
        time_signature = {'numerator': ts.numerator, 'denominator': ts.denominator}

    measure_duration_seconds = (4.0 * 60.0) / tempo

    # Process notes
    all_notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue

        for note in inst.notes:
            quantized_start = quantize_time(note.start, quantize_resolution, tempo)
            measure_num = int(quantized_start // measure_duration_seconds)
            duration_beats = calculate_duration_with_quantization(
                note.start, note.end, tempo, quantize_resolution
            )
            
            all_notes.append({
                'start_time': quantized_start,
                'measure': measure_num,
                'midi_note': note.pitch,
                'duration_beats': duration_beats,
                'note_name': pretty_midi.note_number_to_name(note.pitch),
                'original_start': note.start,
                'original_end': note.end
            })

    all_notes.sort(key=lambda x: (x['measure'], x['start_time'], x['midi_note']))

    # Group into measures with smart clef balancing
    measures = []
    
    if all_notes:
        max_measure = max(note['measure'] for note in all_notes)

        for measure_idx in range(max_measure + 1):
            measure_notes = [n for n in all_notes if n['measure'] == measure_idx]
            measure_data = []
            note_id_counter = 1
            
            # Track clef loads for this measure
            measure_context = {'treble_load': 0, 'bass_load': 0}

            if not measure_notes:
                measures.append([])
                continue

            print(f"\nProcessing measure {measure_idx} with {len(measure_notes)} notes")

            # Group by start time
            time_groups = {}
            for note in measure_notes:
                start_key = round(note['start_time'], 2)
                if start_key not in time_groups:
                    time_groups[start_key] = []
                time_groups[start_key].append(note)

            # Process each time group with load balancing
            for start_time in sorted(time_groups.keys()):
                time_group = time_groups[start_time]
                
                # Group by duration
                duration_groups = {}
                for note in time_group:
                    duration_key = round(note['duration_beats'], 2)
                    if duration_key not in duration_groups:
                        duration_groups[duration_key] = []
                    duration_groups[duration_key].append(note)

                # Process duration groups with smart clef assignment
                for duration_beats in sorted(duration_groups.keys()):
                    duration_group = duration_groups[duration_beats]
                    safe_duration = beats_to_duration_symbol_vexflow_safe(duration_beats, 4.0)
                    
                    if len(duration_group) == 1:
                        # Single note - use load balancing
                        note = duration_group[0]
                        clef = determine_clef_with_load_balancing([note], measure_context)
                        
                        measure_data.append({
                            'id': f'converted-{measure_idx}-{note_id_counter}',
                            'name': note['note_name'],
                            'clef': clef,
                            'duration': safe_duration,
                            'measure': measure_idx,
                            'isRest': False
                        })
                        
                        # Update load tracking
                        measure_context[f'{clef}_load'] += 1
                        note_id_counter += 1
                    
                    else:
                        # Complex chord - try splitting if needed
                        chord_split = split_complex_chord_across_clefs(duration_group)
                        
                        if chord_split:
                            # Split across clefs
                            print(f"    Splitting complex chord across clefs")
                            
                            # Bass part
                            bass_names = [n['note_name'] for n in sorted(chord_split['bass_part'], key=lambda x: x['midi_note'])]
                            bass_chord_name = f"({' '.join(bass_names)})" if len(bass_names) > 1 else bass_names[0]
                            
                            measure_data.append({
                                'id': f'converted-{measure_idx}-{note_id_counter}',
                                'name': bass_chord_name,
                                'clef': 'bass',
                                'duration': safe_duration,
                                'measure': measure_idx,
                                'isRest': False
                            })
                            note_id_counter += 1
                            measure_context['bass_load'] += len(chord_split['bass_part'])
                            
                            # Treble part
                            treble_names = [n['note_name'] for n in sorted(chord_split['treble_part'], key=lambda x: x['midi_note'])]
                            treble_chord_name = f"({' '.join(treble_names)})" if len(treble_names) > 1 else treble_names[0]
                            
                            measure_data.append({
                                'id': f'converted-{measure_idx}-{note_id_counter}',
                                'name': treble_chord_name,
                                'clef': 'treble',
                                'duration': safe_duration,
                                'measure': measure_idx,
                                'isRest': False
                            })
                            note_id_counter += 1
                            measure_context['treble_load'] += len(chord_split['treble_part'])
                            
                        else:
                            # Regular chord - use balanced clef assignment
                            clef = determine_clef_with_load_balancing(duration_group, measure_context)
                            
                            note_names = [n['note_name'] for n in sorted(duration_group, key=lambda x: x['midi_note'])]
                            chord_name = f"({' '.join(note_names)})" if len(note_names) > 1 else note_names[0]
                            
                            measure_data.append({
                                'id': f'converted-{measure_idx}-{note_id_counter}',
                                'name': chord_name,
                                'clef': clef,
                                'duration': safe_duration,
                                'measure': measure_idx,
                                'isRest': False
                            })
                            
                            measure_context[f'{clef}_load'] += len(duration_group)
                            note_id_counter += 1

            # Log final clef distribution
            print(f"  Measure {measure_idx} clef loads: treble={measure_context['treble_load']}, bass={measure_context['bass_load']}")
            
            measures.append(measure_data)

    # Build final JSON
    json_data = {
        'keySignature': key_signature,
        'tempo': int(tempo),
        'timeSignature': time_signature,
        'instrument': determine_instrument_name(pm),
        'midiChannel': '0',
        'measures': measures
    }

    print(f"\nSmart clef balancing complete: {len(measures)} measures")
    return json_data
    try:
        pm = pretty_midi.PrettyMIDI(midi_file_path)
    except Exception as e:
        raise ValueError(f"Could not load MIDI file: {e}")

    if not pm.instruments:
        raise ValueError("MIDI file contains no instruments")

    tempo = manual_tempo
    print(f"Using precise tempo: {tempo} BPM")

    measure_duration_seconds = (4.0 * 60.0) / tempo
    
    # Use finer quantization for better timing accuracy
    fine_quantization = 0.125  # 32nd note resolution instead of 16th
    print(f"Using fine quantization: {fine_quantization} beats (32nd notes)")

    # Process notes with maximum precision
    all_notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue

        for note in inst.notes:
            # Use finer quantization
            quantized_start = quantize_time(note.start, fine_quantization, tempo)
            measure_num = int(quantized_start // measure_duration_seconds)
            
            # More precise duration calculation
            duration_beats = calculate_duration_with_quantization(
                note.start, note.end, tempo, fine_quantization
            )
            
            all_notes.append({
                'start_time': quantized_start,
                'measure': measure_num,
                'midi_note': note.pitch,
                'duration_beats': duration_beats,
                'note_name': pretty_midi.note_number_to_name(note.pitch),
                'original_start': note.start,  # Keep for debugging
                'original_end': note.end
            })

    all_notes.sort(key=lambda x: (x['measure'], x['start_time'], x['midi_note']))

    # Group with ultra-strict timing tolerance
    measures = []
    
    if all_notes:
        max_measure = max(note['measure'] for note in all_notes)

        for measure_idx in range(max_measure + 1):
            measure_notes = [n for n in all_notes if n['measure'] == measure_idx]
            measure_data = []
            note_id_counter = 1

            if not measure_notes:
                measures.append([])
                continue

            # Ultra-strict timing grouping (0.001s tolerance)
            time_groups = {}
            for note in measure_notes:
                # Round to millisecond precision
                start_key = round(note['start_time'] * 1000) / 1000
                if start_key not in time_groups:
                    time_groups[start_key] = []
                time_groups[start_key].append(note)

            # Process each time group
            for start_time in sorted(time_groups.keys()):
                time_group = time_groups[start_time]
                
                # Group by duration with high precision
                duration_groups = {}
                for note in time_group:
                    # Round to hundredth of a beat
                    duration_key = round(note['duration_beats'] * 100) / 100
                    if duration_key not in duration_groups:
                        duration_groups[duration_key] = []
                    duration_groups[duration_key].append(note)

                # Process duration groups
                for duration_beats in sorted(duration_groups.keys()):
                    duration_group = duration_groups[duration_beats]
                    
                    if len(duration_group) == 1:
                        # Single note
                        note = duration_group[0]
                        clef = 'treble' if note['midi_note'] >= 60 else 'bass'
                        duration_symbol = beats_to_duration_symbol_improved(duration_beats)
                        
                        measure_data.append({
                            'id': f'converted-{measure_idx}-{note_id_counter}',
                            'name': note['note_name'],
                            'clef': clef,
                            'duration': duration_symbol,
                            'measure': measure_idx,
                            'isRest': False
                        })
                        note_id_counter += 1
                    
                    else:
                        # Chord - same logic but preserve precise durations
                        duration_group.sort(key=lambda x: x['midi_note'])
                        
                        lowest_note = duration_group[0]['midi_note']
                        highest_note = duration_group[-1]['midi_note']
                        
                        if lowest_note < 60 and (highest_note - lowest_note) <= 12:
                            clef = 'bass'
                        elif lowest_note >= 60:
                            clef = 'treble'
                        else:
                            treble_count = sum(1 for n in duration_group if n['midi_note'] >= 60)
                            clef = 'treble' if treble_count >= len(duration_group)/2 else 'bass'
                        
                        note_names = [n['note_name'] for n in duration_group]
                        chord_name = f"({' '.join(note_names)})" if len(note_names) > 1 else note_names[0]
                        duration_symbol = beats_to_duration_symbol_improved(duration_beats)
                        
                        measure_data.append({
                            'id': f'converted-{measure_idx}-{note_id_counter}',
                            'name': chord_name,
                            'clef': clef,
                            'duration': duration_symbol,
                            'measure': measure_idx,
                            'isRest': False
                        })
                        note_id_counter += 1

            measures.append(measure_data)

    # Build JSON with precise tempo
    json_data = {
        'keySignature': 'C',
        'tempo': int(tempo),
        'timeSignature': {'numerator': 4, 'denominator': 4},
        'instrument': 'piano',  # Force single instrument type
        'midiChannel': '0',
        'measures': measures
    }

    return json_data

def beats_to_duration_symbol_vexflow_safe(beats, max_beats_per_measure=4.0):
    """
    Convert beats to VexFlow duration symbol with aggressive safety checks.
    Prevents VexFlow "too many ticks" errors.
    """
    # Clamp beats to reasonable range
    beats = max(0.125, min(beats, max_beats_per_measure))
    
    # Safe duration mappings (NO dotted whole notes - VexFlow hates them)
    SAFE_DURATIONS = {
        'w': 4.0,     # whole note
        'h.': 3.0,    # dotted half (safe)
        'h': 2.0,     # half note
        'q.': 1.5,    # dotted quarter
        'q': 1.0,     # quarter note
        '8.': 0.75,   # dotted eighth
        '8': 0.5,     # eighth note
        '16.': 0.375, # dotted sixteenth  
        '16': 0.25,   # sixteenth note
        '32': 0.125   # thirty-second note
    }
    
    # NEVER allow dotted whole notes or anything >= 6 beats
    if beats >= 6.0:
        return 'w'  # Convert to regular whole note
    
    # Find closest safe duration
    closest_duration = 'q'  # Safe default
    closest_diff = float('inf')
    
    for symbol, duration_beats in SAFE_DURATIONS.items():
        diff = abs(beats - duration_beats)
        if diff < closest_diff:
            closest_diff = diff
            closest_duration = symbol
    
    return closest_duration


def determine_clef_pianotour_safe(midi_note):
    """
    Determine clef for PianoTour compatibility.
    C4 (MIDI 60) and above = treble, below C4 = bass.
    """
    return 'treble' if midi_note >= 60 else 'bass'


def determine_chord_clef_pianotour_safe(note_group):
    """
    Determine clef for a chord group with PianoTour-specific logic.
    """
    if not note_group:
        return 'treble'
    
    note_group.sort(key=lambda x: x['midi_note'])
    lowest_note = note_group[0]['midi_note']
    highest_note = note_group[-1]['midi_note']
    
    # More conservative clef assignment for PianoTour
    if highest_note < 60:  # All notes below C4 = bass
        return 'bass'
    elif lowest_note >= 60:  # All notes C4 and above = treble  
        return 'treble'
    else:
        # Mixed range - check if it's a typical bass chord pattern
        if lowest_note < 55 and len(note_group) <= 3:  # Root below G3, small chord
            return 'bass'
        else:
            return 'treble'  # Default to treble for PianoTour compatibility


def validate_measure_for_vexflow(measure_data, time_signature):
    """
    Validate that a measure won't cause VexFlow "too many ticks" errors.
    """
    max_beats = (time_signature['numerator'] * 4.0) / time_signature['denominator']
    
    total_beats = 0
    for note in measure_data:
        duration_beats = DURATION_TO_BEATS.get(note['duration'], 1.0)
        total_beats += duration_beats
    
    is_valid = total_beats <= max_beats + 0.01  # Small tolerance for floating point
    
    return {
        'isValid': is_valid,
        'totalBeats': total_beats,
        'maxBeats': max_beats,
        'overflow': max(0, total_beats - max_beats)
    }