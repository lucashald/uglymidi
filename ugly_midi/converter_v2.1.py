#!/usr/bin/env python3
"""Simplified, beat-accurate JSON <-> MIDI conversion (v2).

Goals:
- JSON -> MIDI: trust JSON durations, measures, and clefs; no extras.
- MIDI -> JSON: quantize to a beat grid, assign clefs by pitch split, no
  measure splitting or clef balancing.

This is intentionally simpler than the original converter and is meant
for correctness and predictability, not layout optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Optional, Set

import pretty_midi


# VexFlow-style duration symbols to beats (4/4 quarter-note beats)
DURATION_TO_BEATS: Dict[str, float] = {
    "w": 4.0,
    "h": 2.0,
    "q": 1.0,
    "8": 0.5,
    "16": 0.25,
    "32": 0.125,
    "w.": 6.0,
    "h.": 3.0,
    "q.": 1.5,
    "8.": 0.75,
    "16.": 0.375,
}

# Inverse map helper: beats -> closest duration symbol
BEATS_TO_DURATION_SYMBOLS: List[Tuple[str, float]] = list(DURATION_TO_BEATS.items())


def beats_to_duration_symbol_simple(beats: float) -> str:
    """Return the duration symbol whose beat value is closest to ``beats``.

    No "too many ticks" safety, just nearest neighbor.
    """
    best_sym = "q"
    best_diff = float("inf")
    for sym, val in BEATS_TO_DURATION_SYMBOLS:
        diff = abs(val - beats)
        if diff < best_diff:
            best_diff = diff
            best_sym = sym
    return best_sym


@dataclass
class TimeSignature:
    numerator: int
    denominator: int

    @property
    def beats_per_measure(self) -> float:
        # Convert time signature to quarter-note beats per measure
        return self.numerator * (4.0 / self.denominator)


def beats_to_seconds(beats: float, tempo: float) -> float:
    return beats * 60.0 / tempo


def seconds_to_beats(seconds: float, tempo: float) -> float:
    return seconds * tempo / 60.0


def parse_note_name(name: str) -> List[int]:
    """Parse a VexFlow name or chord to MIDI pitches.

    "C4" -> [60]
    "(C4 E4 G4)" -> [60, 64, 67]
    """
    if not name:
        return []
    if name.startswith("(") and name.endswith(")"):
        parts = name[1:-1].split()
    else:
        parts = [name]
    return [pretty_midi.note_name_to_number(p) for p in parts]


def midi_notes_to_name(midi_notes: Sequence[int]) -> str:
    """Convert MIDI pitches to a single-note or chord name."""
    if not midi_notes:
        return ""
    names = [pretty_midi.note_number_to_name(p) for p in sorted(midi_notes)]
    if len(names) == 1:
        return names[0]
    return f"({' '.join(names)})"


def determine_clef_from_pitch(pitch: int) -> str:
    """Simple pitch split: >=60 treble, else bass."""
    return "treble" if pitch >= 60 else "bass"


def _accumulate_tied_duration(note: Dict, note_lookup: Dict[str, Dict], skip_ids: Set[str]) -> float:
    """Sum durations for tied notes starting at ``note`` and mark followers to skip.

    Returns the extra beats contributed by tied followers. Only activates when this
    note's ``id`` matches the tie's ``startNoteId``. Followers are recorded in
    ``skip_ids`` so they do not emit duplicate MIDI notes later.
    """
    tie = note.get("tie")
    note_id = note.get("id")
    if not tie or not note_id or note_id != tie.get("startNoteId"):
        return 0.0

    extra_beats = 0.0
    next_id = tie.get("endNoteId")
    visited: Set[str] = set()

    while next_id and next_id not in visited:
        visited.add(next_id)
        follower = note_lookup.get(next_id)
        if not follower:
            break
        duration_symbol = follower.get("duration", "q")
        extra_beats += DURATION_TO_BEATS.get(duration_symbol, 1.0)
        skip_ids.add(next_id)

        follower_tie = follower.get("tie")
        if not follower_tie or next_id != follower_tie.get("startNoteId"):
            break
        next_id = follower_tie.get("endNoteId")

    return extra_beats


# ---------------------------------------------------------------------------
# JSON -> MIDI (v2)
# ---------------------------------------------------------------------------


def create_midi_from_json_v2(json_data: Dict, tempo_override: Optional[int] = None) -> pretty_midi.PrettyMIDI:
    """Convert a single VexFlow-style JSON object to PrettyMIDI.

    - Uses JSON tempo unless ``tempo_override`` is provided.
    - Respects given clefs and measures.
    - Does not attempt measure splitting or clef balancing.
    """
    tempo = tempo_override or int(json_data.get("tempo", 120))
    ts_data = json_data.get("timeSignature", {"numerator": 4, "denominator": 4})
    ts = TimeSignature(ts_data.get("numerator", 4), ts_data.get("denominator", 4))

    instrument_name = json_data.get("instrument", "piano")
    program = pretty_midi.instrument_name_to_program("Acoustic Grand Piano")
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    inst = pretty_midi.Instrument(program=program, name=instrument_name)

    beats_per_measure = ts.beats_per_measure

    measures = json_data.get("measures", [])

    note_lookup: Dict[str, Dict] = {}
    for measure in measures:
        for note in measure:
            note_id = note.get("id")
            if note_id:
                note_lookup[note_id] = note

    skip_note_ids: Set[str] = set()

    for m_idx, measure in enumerate(measures):
        # Track beat offset per clef within this measure
        clef_positions: Dict[str, float] = {"treble": 0.0, "bass": 0.0}

        # Preserve given order
        for note in measure:
            duration_symbol = note.get("duration", "q")
            duration_beats = DURATION_TO_BEATS.get(duration_symbol, 1.0)
            clef = note.get("clef", "treble")

            if note.get("isRest", False):
                clef_positions[clef] += duration_beats
                continue

            note_id = note.get("id")
            if note_id and note_id in skip_note_ids:
                clef_positions[clef] += duration_beats
                continue

            extra_tied_beats = _accumulate_tied_duration(note, note_lookup, skip_note_ids)
            effective_beats = duration_beats + extra_tied_beats

            beat_start = m_idx * beats_per_measure + clef_positions[clef]
            clef_positions[clef] += duration_beats

            start_s = beats_to_seconds(beat_start, tempo)
            end_s = beats_to_seconds(beat_start + effective_beats, tempo)

            pitches = parse_note_name(note.get("name", ""))
            for pitch in pitches:
                inst.notes.append(
                    pretty_midi.Note(velocity=int(note.get("velocity", 100)),
                                     pitch=pitch,
                                     start=start_s,
                                     end=end_s)
                )

    pm.instruments.append(inst)
    return pm


# ---------------------------------------------------------------------------
# MIDI -> JSON (v2)
# ---------------------------------------------------------------------------


def _extract_notes_from_midi(pm: pretty_midi.PrettyMIDI, tempo: float) -> List[Dict]:
    """Flatten all non-drum notes from a PrettyMIDI into beat-based dicts.

    Each returned dict has: pitch, start_beats, end_beats, velocity.
    """
    notes: List[Dict] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            start_beats = seconds_to_beats(n.start, tempo)
            end_beats = seconds_to_beats(n.end, tempo)
            notes.append({
                "pitch": n.pitch,
                "start_beats": start_beats,
                "end_beats": end_beats,
                "velocity": n.velocity,  # Preserve velocity
            })
    return notes


def midi_to_json_v2(
    midi_file_path: str,
    manual_tempo: Optional[int] = None,
    quantize_resolution: float = 0.25,
) -> Dict:
    """Convert a MIDI file to VexFlow-style JSON using simple rules.

    - Uses ``manual_tempo`` if provided; otherwise uses first tempo from MIDI
      or defaults to 120.
    - Quantizes to ``quantize_resolution`` in beats (e.g., 0.25 = sixteenth).
    - Clefs are assigned by a simple pitch split.
    - No measure splitting or clef load balancing.
    """
    try:
        pm = pretty_midi.PrettyMIDI(midi_file_path)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Could not load MIDI file: {exc}") from exc

    # Tempo
    if manual_tempo is not None:
        tempo = float(manual_tempo)
    else:
        # pretty_midi estimated tempo or default
        try:
            tempo = float(pm.estimate_tempo())
        except Exception:
            tempo = 120.0

    # Time signature: use first, else 4/4
    if pm.time_signature_changes:
        ts0 = pm.time_signature_changes[0]
        ts = TimeSignature(ts0.numerator, ts0.denominator)
    else:
        ts = TimeSignature(4, 4)

    beats_per_measure = ts.beats_per_measure

    raw_notes = _extract_notes_from_midi(pm, tempo)
    if not raw_notes:
        raise ValueError("MIDI file contains no notes")

    # Quantize and group
    quantized_notes: List[Dict] = []
    for n in raw_notes:
        start_q = round(n["start_beats"] / quantize_resolution) * quantize_resolution
        end_q = round(n["end_beats"] / quantize_resolution) * quantize_resolution
        if end_q <= start_q:
            end_q = start_q + quantize_resolution
        dur_beats = end_q - start_q
        measure_idx = int(start_q // beats_per_measure)
        offset = start_q - measure_idx * beats_per_measure
        quantized_notes.append({
            "pitch": n["pitch"],
            "start_beats": start_q,
            "duration_beats": dur_beats,
            "measure": measure_idx,
            "offset": offset,
            "velocity": n.get("velocity", 100),
        })

    # Group per-measure, per-clef, per-(offset,duration) to form chords
    measures: Dict[int, List[Dict]] = {}
    for qn in quantized_notes:
        measure_idx = qn["measure"]
        measures.setdefault(measure_idx, []).append(qn)

    max_measure = max(measures.keys())
    result_measures: List[List[Dict]] = [[] for _ in range(max_measure + 1)]

    for measure_idx, note_list in measures.items():
        # group key: (clef, offset, duration_beats)
        groups: Dict[Tuple[str, float, float], Dict[str, object]] = {}
        for n in note_list:
            clef = determine_clef_from_pitch(n["pitch"])
            key = (clef, round(n["offset"], 6), round(n["duration_beats"], 6))
            if key not in groups:
                groups[key] = {"pitches": [], "velocity": n.get("velocity", 100)}
            groups[key]["pitches"].append(n["pitch"])

        # Emit notes in stable order: by offset, clef
        for (clef, offset, dur), data in sorted(groups.items(), key=lambda k: (k[0][1], k[0][0])):
            name = midi_notes_to_name(data["pitches"])
            duration_symbol = beats_to_duration_symbol_simple(dur)
            result_measures[measure_idx].append({
                "id": f"m{measure_idx}-{clef}-{int(offset * 1000)}",  # deterministic but arbitrary
                "name": name,
                "clef": clef,
                "duration": duration_symbol,
                "measure": measure_idx,
                "isRest": False,
                "velocity": int(data["velocity"]),
            })

    json_data: Dict = {
        "keySignature": "C",  # unknown from MIDI without extra analysis
        "tempo": int(tempo),
        "timeSignature": {"numerator": ts.numerator, "denominator": ts.denominator},
        "instrument": "piano",  # simplified
        "midiChannel": "0",
        "measures": result_measures,
    }

    return json_data
