# ugly_midi Project Instructions

## Project Overview
`ugly_midi` is a bidirectional converter between VexFlow-style JSON music notation and MIDI files. Built as both a Python package and CLI tool, it enables web applications using VexFlow to export/import MIDI, and helps convert MIDI compositions to web-playable JSON format.

## Architecture

### Core Components
- **`ugly_midi/converter.py`**: All conversion logic (JSON↔MIDI). This is the heart of the system (~1000 lines).
- **`ugly_midi/cli.py`**: Command-line interface wrapper around converter functions.
- **`ugly_midi/__init__.py`**: Public API exports with convenience aliases (`json_to_midi`, `midi_to_json`, `create_ensemble`).
- **`ugly_midi.py`**: Legacy standalone script (kept for backwards compatibility).

### Data Flow
1. **JSON → MIDI**: VexFlow JSON → `create_midi_from_json()` → PrettyMIDI object → `.mid` file
2. **MIDI → JSON**: `.mid` file → `create_json_from_midi()` → VexFlow JSON with quantization and clef balancing
3. **Multi-instrument**: Multiple JSON files → `create_midi_from_multiple_json()` → Single MIDI with separate channels

## VexFlow JSON Format

The project uses a custom JSON schema representing musical notation:

```json
{
  "keySignature": "C",
  "tempo": 120,
  "timeSignature": {"numerator": 4, "denominator": 4},
  "instrument": "piano",
  "midiChannel": "0",
  "measures": [
    [
      {
        "id": "note-1-1",
        "name": "C4",           // Single note or "(C4 E4 G4)" for chords
        "clef": "treble",       // "treble" or "bass"
        "duration": "q",        // "w", "h", "q", "8", "16", "32", or dotted versions
        "measure": 0,
        "isRest": false
      }
    ]
  ]
}
```

**Critical patterns**:
- Measures are arrays of note arrays (one per measure)
- Chords use parentheses: `"(C4 E4 G4)"`
- Duration symbols: `w` (whole), `h` (half), `q` (quarter), `8` (eighth), etc. Dotted: `q.`, `h.`
- Notes are grouped by measure index, then by clef within each measure

## Key Algorithms

### VexFlow "Too Many Ticks" Prevention
**Problem**: VexFlow has a measure capacity limit. Dense MIDI can overflow individual clefs.

**Solution** (in `create_json_from_midi()`):
- `process_measure_with_clef_balancing()` analyzes note density per clef
- When a clef exceeds `beats_per_clef_limit`, the measure is split into multiple measures
- Uses `beats_to_duration_symbol_vexflow_safe()` to cap durations conservatively
- Clef assignment uses `determine_clef_with_load_balancing()` to distribute notes intelligently

### Quantization Strategy
MIDI → JSON requires quantization since MIDI has sub-millisecond timing:
- Default resolution: `0.125` beats (32nd notes) for high accuracy
- `quantize_time()` rounds timestamps to nearest grid position
- `calculate_duration_with_quantization()` ensures durations snap correctly
- Configurable via `quantize_resolution` parameter (lower = finer, higher = simpler)

### Clef Determination
- Middle C (MIDI 60) is the pivot point
- Notes ≥60 → treble, <60 → bass
- `determine_clef_pianotour_safe()` provides alternative split logic
- Load balancing prevents one clef from becoming overloaded

## Development Workflows

### Running Tests
```bash
# Run all tests with coverage
pytest

# Run specific test file
python tests/test_ugly_midi.py
python tests/test_library_usage.py

# Run with verbose output
pytest -v --cov=ugly_midi --cov-report=term-missing
```

### Installing for Development
```bash
# Install package in editable mode with all extras
pip install -e ".[dev,web,all]"

# Or use requirements.txt
pip install -r requirements.txt
```

### CLI Usage Examples
```bash
# JSON to MIDI (single instrument)
ugly_midi song.json song.mid

# Multiple instruments to ensemble
ugly_midi piano.json guitar.json -o ensemble.mid

# MIDI to JSON (critical: specify manual_tempo for accuracy)
ugly_midi song.mid --to-json song.json
ugly_midi song.mid --to-json  # prints to stdout

# Override tempo
ugly_midi song.json -o output.mid --tempo 140
```

### Library Usage
```python
import ugly_midi

# JSON to MIDI
midi = ugly_midi.json_to_midi(json_data)
midi.write('output.mid')

# MIDI to JSON (always use manual_tempo from your DAW for precision)
json_data = ugly_midi.midi_to_json('input.mid', manual_tempo=142)

# Multi-instrument ensemble
ensemble = ugly_midi.create_ensemble([piano_json, guitar_json], output_tempo=120)
ugly_midi.save_midi(ensemble, 'ensemble.mid')
```

## Project-Specific Conventions

### Naming Patterns
- Helper functions use descriptive verb phrases: `parse_note_name()`, `beats_to_seconds()`
- Public API uses simple aliases: `json_to_midi()`, `midi_to_json()`
- Internal functions may have qualifiers: `beats_to_duration_symbol_vexflow_safe()`

### Duration Constants
The `DURATION_TO_BEATS` dictionary maps VexFlow symbols to beat values. When adding support for new note durations, update this dictionary first.

### Error Handling
- Functions raise `ValueError` for invalid input data
- MIDI file loading errors are caught and re-raised with context
- Warnings (via `print()`) for non-critical issues like unknown instruments or clef overloading

### Testing Philosophy
- `test_ugly_midi.py`: Unit tests with `unittest` framework, tests individual functions
- `test_library_usage.py`: Integration tests demonstrating real-world usage patterns
- Test files use descriptive JSON samples that exercise all features (chords, rests, multiple clefs)

## Common Pitfalls

1. **MIDI → JSON tempo**: Always specify `manual_tempo` parameter with your DAW's tempo. MIDI tempo changes can be unreliable.

2. **Clef overload**: When converting dense MIDI, measures may auto-split. This is intentional to prevent VexFlow errors.

3. **Channel assignment**: In multi-instrument JSON→MIDI, channels are auto-assigned if conflicts exist. Check console output for warnings.

4. **Package vs. standalone**: `ugly_midi.py` exists for backwards compatibility. New features go in `ugly_midi/converter.py`.

5. **Quantization artifacts**: Lower `quantize_resolution` values (e.g., 0.0625) capture more detail but may produce complex notation.

## Dependencies
- **pretty_midi**: Core MIDI manipulation (handles PrettyMIDI objects, note conversion)
- **numpy**: Required by pretty_midi for timing calculations
- **flask**: Optional, for web API (`tests/flask/main.py`)
- **pytest**: Testing framework with coverage reporting

## File Organization
- Package code: `ugly_midi/`
- Tests: `tests/` (includes Flask example in `tests/flask/`)
- Config: `pyproject.toml` (main), `setup.py` (legacy compatibility)
- Legacy: `ugly_midi.py` (standalone version, mirrors package functionality)
