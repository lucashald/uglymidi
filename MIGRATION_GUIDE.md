# ugly_midi v3 Migration Guide

## Overview

The `ugly_midi` package has been updated to use the v3 MIDI↔JSON converter by default. This provides 99% round-trip accuracy compared to 80% with v1, thanks to:

- **Precise quantization** (configurable, default 32nd notes = 0.125 beats)
- **Clef balancing** (prevents VexFlow measure overflow)
- **Proper tie handling** (notes spanning measures)
- **Deterministic rest insertion**
- **Tempo/time-signature awareness**

## What Changed

### ✅ Automatic (No Code Changes Needed)

The public API already uses v3:

```python
import ugly_midi

# This now uses v3 internally:
json_data = ugly_midi.midi_to_json('input.mid', manual_tempo=120)
```

### ⚠️  Affected Code (Update Required)

**Direct imports from `converter` module:**

```python
# ❌ OLD (v1 MIDI→JSON, 80% accuracy)
from ugly_midi.converter import create_json_from_midi
json_data = create_json_from_midi('input.mid')

# ✅ NEW (v3 MIDI→JSON, 99% accuracy)
from ugly_midi import midi_to_json
json_data = midi_to_json('input.mid', manual_tempo=120)
```

### 🚨 Deprecated but Maintained

**Legacy root script `ugly_midi.py`:**

- Kept for backwards compatibility only
- Contains old v1 logic (no clef balancing, basic quantization)
- **Do not use for new projects**
- Added deprecation notice at the top of the file

**Test files in `tests/old-tests/`:**

- Still use package API (which defaults to v3)
- Can be safely left as-is unless you need v1 behavior
- If you need to test v1, import directly from `converter.py`

## CLI Updates

The command-line tool now uses v3 by default:

```bash
# MIDI to JSON (now uses v3 converter)
ugly_midi input.mid --to-json output.json

# Specify tempo (critical for accuracy!)
ugly_midi input.mid --to-json output.json --tempo 120

# JSON to MIDI (unchanged)
ugly_midi input.json -o output.mid
```

## Key API Differences (v1 vs v3)

### MIDI → JSON

| Feature | v1 | v3 |
|---------|----|----|
| Quantization | Basic (0.25 beats) | Configurable (default 0.125) |
| Clef balancing | None | Yes, prevents measure overflow |
| Tied notes | Not handled | Preserved across measures |
| Rests | Minimal | Deterministic & well-placed |
| Measure overflow handling | Causes errors | Auto-splits measures |
| Tempo support | Limited | Full tempo map |

### JSON → MIDI

Both versions use the same `create_midi_from_json()` — no changes needed.

## Migration Checklist

- [ ] Update imports: `from ugly_midi import midi_to_json` instead of `from ugly_midi.converter import create_json_from_midi`
- [ ] Add `manual_tempo` parameter to `midi_to_json()` calls (use your DAW's tempo)
- [ ] Test round-trip accuracy with `tools/compare_json_roundtrip.py`:
  ```bash
  python tools/compare_json_roundtrip.py original.json roundtrip.json
  ```
- [ ] If you need v1 behavior for any reason, you can still import directly:
  ```python
  from ugly_midi.converter import create_json_from_midi  # v1
  # or use converter_v3 for explicit v3:
  from ugly_midi.converter_v3 import midi_to_json_v3  # v3
  ```

## Testing Your Migration

### Round-Trip Test

```python
import ugly_midi

# Start with JSON
original_json = ugly_midi.load_json_file('song.json')

# Convert JSON → MIDI → JSON
midi = ugly_midi.json_to_midi(original_json)
ugly_midi.save_midi(midi, 'temp.mid')

roundtrip_json = ugly_midi.midi_to_json('temp.mid', manual_tempo=120)
ugly_midi.save_json_file(roundtrip_json, 'roundtrip.json')

# Compare accuracy
# (use tools/compare_json_roundtrip.py or custom validation)
```

### CLI Test

```bash
# Test JSON → MIDI → JSON
ugly_midi tests/test_files/my-song\ \(20\).json -o /tmp/test.mid
ugly_midi /tmp/test.mid --to-json /tmp/test.json

# Check accuracy
python tools/compare_json_roundtrip.py \
  tests/test_files/my-song\ \(20\).json \
  /tmp/test.json
```

## Common Issues

### ❌ Error: "cannot access local variable 'json_data'"

**Cause:** Using old code that references undefined variables  
**Fix:** Use the public API wrapper functions in `__init__.py`

### ❌ Tempo seems wrong in output

**Cause:** Not specifying `manual_tempo` parameter  
**Fix:** Always pass your DAW's tempo:
```python
json_data = ugly_midi.midi_to_json('input.mid', manual_tempo=120)
```

### ❌ Still getting measure overflow errors

**Cause:** Using v1 converter or old code path  
**Fix:** Ensure you're importing from `ugly_midi` package, not `converter` module directly

## See Also

- **Installation:** See main `README.md`
- **API Documentation:** See docstrings in `ugly_midi/__init__.py`
- **v3 Internals:** See `ugly_midi/converter_v3.py`
- **Round-Trip Testing:** See `tools/compare_json_roundtrip.py`
