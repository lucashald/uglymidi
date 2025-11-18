# Round-Trip JSON Comparison

Use `tools/compare_json_roundtrip.py` to spot differences between an original VexFlow JSON file and the file that was exported after a JSON→MIDI→JSON conversion. The script reports high-level divergences and flags individual measures whose beat totals drift.

## Usage

```bash
cd /workspaces/uglymidi
python tools/compare_json_roundtrip.py tests/test_files/my-song\ \(19\).json tests/test_files/my-song\ \(19\)-v3.json
```

### Options

- `--tolerance <float>`: Absolute tolerance (in beats) when comparing measure totals. Default is `0.001` beats.
- `--show-measures`: Print every measure/clef row even when everything matches (helpful for manual auditing).

## Output Breakdown

- **Note/Rest/Measure counts**: Quick parity check between the reference and candidate files.
- **Per-measure table**: For each clef present in a measure, displays the beat total in both files, whether each file satisfies the time-signature capacity, and whether both files agree within the given tolerance.
- **Issues section**: Missing or unknown duration symbols are surfaced so you can inspect problematic notes immediately.
