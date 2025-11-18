#!/usr/bin/env python3
"""Compare two VexFlow-style JSON files produced by ugly_midi round-trips."""
from __future__ import annotations

import argparse
import json
import math
import pathlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

try:  # Prefer the canonical mapping from the converter module.
    from ugly_midi.converter import DURATION_TO_BEATS
except Exception:  # pragma: no cover - fallback for ad-hoc invocations.
    DURATION_TO_BEATS: Dict[str, float] = {
        "w": 4.0,
        "h": 2.0,
        "q": 1.0,
        "8": 0.5,
        "16": 0.25,
        "32": 0.125,
    }

EPSILON_DEFAULT = 1e-3


@dataclass
class FileStats:
    path: pathlib.Path
    note_count: int
    rest_count: int
    measure_count: int
    measure_beats: List[Dict[str, float]]
    beats_per_measure: float
    issues: List[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two ugly_midi JSON files for round-trip fidelity. "
            "Checks note/rest counts, measure counts, and beat totals."
        )
    )
    parser.add_argument("reference", type=pathlib.Path, help="Original JSON file (pre-conversion)")
    parser.add_argument("candidate", type=pathlib.Path, help="JSON file produced after round-trip")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=EPSILON_DEFAULT,
        help="Allowed beat difference when comparing measures (default: %(default)s)",
    )
    parser.add_argument(
        "--show-measures",
        action="store_true",
        help="Print per-measure beat comparisons even when they match",
    )
    return parser.parse_args()


def load_json(path: pathlib.Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def duration_symbol_to_beats(symbol: str) -> Optional[float]:
    if symbol in DURATION_TO_BEATS:
        return DURATION_TO_BEATS[symbol]
    if symbol.endswith('.') and symbol[:-1] in DURATION_TO_BEATS:
        base = DURATION_TO_BEATS[symbol[:-1]]
        return base * 1.5
    if symbol.startswith('d') and symbol[1:] in DURATION_TO_BEATS:  # rare dotted prefix
        return DURATION_TO_BEATS[symbol[1:]] * 1.5
    return None


def iter_measure_notes(measure: Iterable) -> Iterable[Dict]:
    for entry in measure:
        if isinstance(entry, dict):
            yield entry
        elif isinstance(entry, list):
            for nested in entry:
                if isinstance(nested, dict):
                    yield nested


def beats_capacity(time_signature: Dict[str, int]) -> float:
    numerator = time_signature.get("numerator", 4)
    denominator = time_signature.get("denominator", 4)
    return numerator * (4.0 / denominator)


def collect_stats(path: pathlib.Path, data: Dict) -> FileStats:
    measures = data.get("measures", [])
    time_sig = data.get("timeSignature", {"numerator": 4, "denominator": 4})
    beats_per_measure = beats_capacity(time_sig)

    note_count = 0
    rest_count = 0
    measure_beats: List[Dict[str, float]] = []
    issues: List[str] = []

    for idx, measure in enumerate(measures):
        clef_totals: Dict[str, float] = {}
        for note in iter_measure_notes(measure):
            is_rest = note.get("isRest", False)
            if is_rest:
                rest_count += 1
            else:
                note_count += 1

            symbol = note.get("duration")
            if symbol is None:
                issues.append(f"Measure {idx}: missing duration for note id={note.get('id')}")
                continue
            beats = duration_symbol_to_beats(str(symbol))
            if beats is None:
                issues.append(
                    f"Measure {idx}: unknown duration '{symbol}' for note id={note.get('id')}"
                )
                continue
            clef = note.get("clef", "unknown")
            clef_totals[clef] = clef_totals.get(clef, 0.0) + beats
        measure_beats.append(clef_totals)

    return FileStats(
        path=path,
        note_count=note_count,
        rest_count=rest_count,
        measure_count=len(measures),
        measure_beats=measure_beats,
        beats_per_measure=beats_per_measure,
        issues=issues,
    )


def compare_counts(label: str, lhs: int, rhs: int) -> str:
    status = "MATCH" if lhs == rhs else "DIFF"
    return f"{label:>13}: {lhs:5} vs {rhs:5} -> {status}"


def compare_measures(
    stats_a: FileStats, stats_b: FileStats, tolerance: float, show_all: bool
) -> List[str]:
    lines: List[str] = []
    header = "Measure  Clef    RefBeats  CandBeats  RefOK  CandOK  Status"
    lines.append(header)
    max_len = max(len(stats_a.measure_beats), len(stats_b.measure_beats))
    for idx in range(max_len):
        ref = stats_a.measure_beats[idx] if idx < len(stats_a.measure_beats) else {}
        cand = stats_b.measure_beats[idx] if idx < len(stats_b.measure_beats) else {}
        clefs = sorted(set(ref.keys()) | set(cand.keys())) or ["-"]
        for clef in clefs:
            ref_val = ref.get(clef)
            cand_val = cand.get(clef)
            ref_ok = ref_val is not None and math.isclose(
                ref_val, stats_a.beats_per_measure, abs_tol=tolerance
            )
            cand_ok = cand_val is not None and math.isclose(
                cand_val, stats_b.beats_per_measure, abs_tol=tolerance
            )
            diff_ok = (
                ref_val is not None
                and cand_val is not None
                and math.isclose(ref_val, cand_val, abs_tol=tolerance)
            )
            if not show_all and ref_ok and cand_ok and diff_ok:
                continue
            lines.append(
                f"{idx:>6}  {clef:<5}  {ref_val if ref_val is not None else '-':>8}  "
                f"{cand_val if cand_val is not None else '-':>9}  {str(ref_ok):>5}  "
                f"{str(cand_ok):>7}  {'MATCH' if diff_ok else 'DIFF'}"
            )
    if len(lines) == 1 and not show_all:
        lines.append("All measures match within tolerance.")
    return lines


def main() -> None:
    args = parse_args()

    ref_data = load_json(args.reference)
    cand_data = load_json(args.candidate)

    ref_stats = collect_stats(args.reference, ref_data)
    cand_stats = collect_stats(args.candidate, cand_data)

    print("Reference:", args.reference)
    print("Candidate:", args.candidate)
    print(compare_counts("Note count", ref_stats.note_count, cand_stats.note_count))
    print(compare_counts("Rest count", ref_stats.rest_count, cand_stats.rest_count))
    print(compare_counts("Measure cnt", ref_stats.measure_count, cand_stats.measure_count))

    if ref_stats.issues:
        print("\nReference issues:")
        for issue in ref_stats.issues:
            print(" -", issue)
    if cand_stats.issues:
        print("\nCandidate issues:")
        for issue in cand_stats.issues:
            print(" -", issue)

    print("\nPer-measure beat comparison (tolerance =", args.tolerance, "):")
    for line in compare_measures(ref_stats, cand_stats, args.tolerance, args.show_measures):
        print(line)


if __name__ == "__main__":
    main()
