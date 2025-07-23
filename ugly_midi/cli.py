#!/usr/bin/env python3
"""
Command-line interface for ugly_midi package.

This module provides the command-line interface that was originally
part of the main script, now separated for cleaner package structure.
"""

import argparse
import json
import sys
from pathlib import Path

# Import the converter functions
from .converter import (create_midi_from_multiple_json, create_json_from_midi,
                        create_json_from_midi_file)


def main():
    """Main command line interface."""
    parser = argparse.ArgumentParser(
        description='Convert between VexFlow JSON and MIDI files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # JSON to MIDI (single instrument)
    ugly_midi song.json --output song.mid

    # JSON to MIDI (multiple instruments/symphony)
    ugly_midi piano.json guitar.json --output ensemble.mid

    # MIDI to JSON
    ugly_midi song.mid --to-json song.json
    ugly_midi song.mid --to-json  # prints to stdout
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
        # Single file mode: ugly_midi input.json output.mid
        if args.output:
            input_files = [args.inputs[0]]
            output_file = args.output
        else:
            # Single file mode with --output flag
            input_files = [args.inputs[0]]
            output_file = args.output_flag
            if not output_file:
                print(
                    "Error: Output file required. Use: ugly_midi input.json --output output.mid"
                )
                sys.exit(1)
    else:
        # Multiple file mode: ugly_midi file1.json file2.json --output out.mid
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
