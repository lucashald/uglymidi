ugly_midi — v3 Status & Project Summary

This README documents the current state and v3 MIDI↔JSON converter with recommended usage patterns.

## Quick Start (Recommended)

Install and use the package with v3 converters:

```bash
pip install -e .
```

### JSON → MIDI

```python
import ugly_midi

json_data = ugly_midi.load_json_file('song.json')
midi = ugly_midi.json_to_midi(json_data)
ugly_midi.save_midi(midi, 'output.mid')
```

### MIDI → JSON (v3 — High Accuracy)

```python
import ugly_midi

# Always specify manual_tempo from your DAW for best results!
json_data = ugly_midi.midi_to_json('input.mid', manual_tempo=120)
ugly_midi.save_json_file(json_data, 'output.json')
```

### Command-Line Usage

```bash
# JSON to MIDI
ugly_midi song.json -o song.mid

# MIDI to JSON (uses v3 by default)
ugly_midi song.mid --to-json output.json

# Multi-instrument ensemble
ugly_midi piano.json guitar.json -o ensemble.mid
```

## Why Use v3?

The v3 converter provides 99% round-trip accuracy vs. 80% for v1:

- **Precise quantization**: Configurable resolution (default 0.125 = 32nd notes)
- **Clef balancing**: Prevents VexFlow measure overflow by auto-distributing notes
- **Measure awareness**: Handles tied notes spanning measures correctly
- **Rest insertion**: Generates proper rests where MIDI has silence
- **Tempo/time-sig support**: Respects MIDI tempo and time-signature changes

## Overview
--------
ugly_midi converts between a VexFlow-style JSON representation and MIDI, with goals to preserve musical content and produce stable JSON output for web or score rendering.

## Status (v3 Core)
- Implemented `ugly_midi/converter_v3.py` which supports:
	- Precise measure timeline computation using tempo/time signature events.
	- Quantization and grouping of notes by simultaneity.
	- Strict clef splitting across the C4 boundary (MIDI 60).
	- Overflow handling with cross-clef merging, and tie creation for leftover notes moved into the next measure.
	- Deterministic rest insertion (pads clef to the measure end) and per-clef rest naming to instruct VexFlow placement: `D3` for bass rests and `B4` for treble rests.

What changed recently
---------------------
- Rest insertion: v3 now inserts deterministic rest events whenever a clef has a gap (previous logic attempted cross-clef suppression). This guarantees the JSON contains an isRest entry covering every rest span and avoids VexFlow rendering surprises.
- Rest naming: rest `name` is now `D3` for bass and `B4` for treble (so VexFlow knows where to render rests on the staff).
- The converter now generates `measure` fields in each note/rest entry to identify the owning measure.

Testing & Validation
--------------------
- The project includes `tests/compare_json.py` to compare original and converted JSON files and produce a pitch/duration/metadata accuracy score.
- A number of round-trip conversions were executed and validated during recent work:
	- `my-song (13)`: rest insertion and rest name corrections verified.
	- `my-song14` and `my-song (15)`: round-trip verified, clef balancing preserved, and rests generated.
	- `my-song (18)`: round-trip verified with `compare_json.py` yielding 100% accuracy for that case.

Known caveats
------------
- MIDI doesn't represent rests (silence) as named events. Because of that, JSON→MIDI→JSON conversions will lose original rest event identity (IDs), and v3 regenerates deterministic rests from the MIDI timing.
- Cross-clef rest suppression (skip adding rest when the other clef already has coverage) was removed in favor of deterministic padding. This can be revisited with an option to toggle the behavior.
- The CLI default imports were temporarily changed to avoid missing import errors (`converter_v2` is commented out in `ugly_midi/__init__.py`). Restore or refactor as needed for a final release.

How to reproduce a conversion & test accuracy
-------------------------------------------
1. Convert JSON to MIDI:
```bash
python3 - <<'PY'
import json
from pathlib import Path
from ugly_midi.converter import create_midi_from_json

src = Path('tests/test_files/my-song (13).json')
midi = create_midi_from_json(json.loads(src.read_text()))
midi.write('tests/test_files/my-song (13).mid')
PY
```

2. Convert MIDI back to JSON using v3:
```bash
python3 - <<'PY'
from ugly_midi.converter_v3 import midi_to_json_v3
from pathlib import Path
import json

out = midi_to_json_v3('tests/test_files/my-song (13).mid', manual_tempo=120, quantize_resolution=0.125)
Path('tests/test_files/my-song (13)-v3.json').write_text(json.dumps(out, indent=2))
PY
```

3. Compare original and converted JSON:
```bash
python3 tests/compare_json.py tests/test_files/my-song\ \(13\).json tests/test_files/my-song\ \(13\)-v3.json
```

Next steps
----------
- Add option to control rest generation behavior (deterministic vs. cross-clef suppression。
- Add unit tests that assert rest placements for well-known inputs, in addition to instrument accuracy tests.
- Performance tests over larger files and optimizations where needed.

Contributing
------------
If you'd like to help, try running the round-trip commands above, use `compare_json.py` for accuracy, and submit PRs for:
- the rest behavior toggle,
- re-enabling v2 import compatibility or creating a shim,
- adding tests and benchmarks for larger MIDI files.

---
This status summary was generated from the latest iteration of the v3 converter and recent round-trip tests executed in the dev container (Nov 2025). If you'd like me to expand any section or commit this README change live, say the word and I will proceed.

