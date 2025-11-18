#!/usr/bin/env python3
"""
Version 3

Simplified, beat-accurate JSON <-> MIDI conversion (v2).

Goals:
- JSON -> MIDI: trust JSON durations, measures, and clefs; no extras.
- MIDI -> JSON: quantize to a beat grid, assign clefs by pitch split, no
  measure splitting or clef balancing.

This is intentionally simpler than the original converter and is meant
for correctness and predictability, not layout optimization.
"""

from __future__ import annotations

import json
from bisect import bisect_right
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


@dataclass
class TempoSegment:
    """Represents a contiguous span with constant tempo/time signature."""

    start_time: float
    end_time: float
    tempo: float
    time_signature: TimeSignature
    start_beats: float
    end_beats: float


@dataclass
class MeasureInterval:
    """Metadata about a single measure in the song timeline."""

    index: int
    start_time: float
    end_time: float
    start_beats: float
    end_beats: float
    time_signature: TimeSignature

    @property
    def beats_per_measure(self) -> float:
        return self.time_signature.beats_per_measure


@dataclass
class MeasureEvent:
    """Intermediate representation of a note/rest inside a specific measure."""

    measure_index: int
    start_offset: float  # beats relative to measure start
    duration_beats: float
    pitches: List[int]
    velocity: int
    clef: str
    is_rest: bool = False
    event_id: Optional[str] = None
    group_id: Optional[str] = None
    chunk_index: Optional[int] = None
    tie_to: Optional[str] = None
    moved_from: Optional[str] = None
    chunk_keys: List[Tuple[str, int, str]] | None = None


BEAT_TOLERANCE = 1e-6


def _canonicalize_tempo_events(pm: pretty_midi.PrettyMIDI, manual_tempo: Optional[float]) -> List[Tuple[float, float]]:
    if manual_tempo is not None:
        return [(0.0, float(manual_tempo))]

    tempo_times, tempo_values = pm.get_tempo_changes()
    if len(tempo_values) == 0:
        estimated = pm.estimate_tempo() or 120.0
        return [(0.0, float(estimated))]

    events = [(float(t), float(v)) for t, v in zip(tempo_times.tolist(), tempo_values.tolist())]
    events.sort(key=lambda x: x[0])
    if events[0][0] > 0.0:
        events.insert(0, (0.0, events[0][1]))
    return events


def _canonicalize_time_signature_events(pm: pretty_midi.PrettyMIDI) -> List[Tuple[float, TimeSignature]]:
    if pm.time_signature_changes:
        events = [(float(ts.time), TimeSignature(ts.numerator, ts.denominator)) for ts in pm.time_signature_changes]
    else:
        events = [(0.0, TimeSignature(4, 4))]
    events.sort(key=lambda x: x[0])
    if events[0][0] > 0.0:
        events.insert(0, (0.0, events[0][1]))
    return events


def _build_tempo_segments(
    tempo_events: List[Tuple[float, float]],
    ts_events: List[Tuple[float, TimeSignature]],
    song_end: float,
) -> List[TempoSegment]:
    event_times = {0.0, float(song_end)}
    event_times.update(t for t, _ in tempo_events)
    event_times.update(t for t, _ in ts_events)
    ordered_times = sorted(event_times)

    tempo_idx = 0
    ts_idx = 0
    total_beats = 0.0
    segments: List[TempoSegment] = []

    for idx in range(len(ordered_times) - 1):
        start = ordered_times[idx]
        end = ordered_times[idx + 1]
        if end - start <= BEAT_TOLERANCE:
            continue

        while tempo_idx + 1 < len(tempo_events) and tempo_events[tempo_idx + 1][0] <= start + BEAT_TOLERANCE:
            tempo_idx += 1
        while ts_idx + 1 < len(ts_events) and ts_events[ts_idx + 1][0] <= start + BEAT_TOLERANCE:
            ts_idx += 1

        tempo = tempo_events[tempo_idx][1]
        ts = ts_events[ts_idx][1]
        beats = (end - start) * tempo / 60.0
        segments.append(TempoSegment(start, end, tempo, ts, total_beats, total_beats + beats))
        total_beats += beats

    return segments


def _build_measure_intervals(segments: List[TempoSegment]) -> List[MeasureInterval]:
    measures: List[MeasureInterval] = []
    measure_index = 0

    for seg in segments:
        seconds_per_beat = 60.0 / seg.tempo
        cursor_time = seg.start_time
        cursor_beats = seg.start_beats

        while cursor_time + BEAT_TOLERANCE < seg.end_time:
            beats_per_measure = seg.time_signature.beats_per_measure
            measure_seconds = beats_per_measure * seconds_per_beat
            measure_end_time = min(cursor_time + measure_seconds, seg.end_time)
            actual_beats = (measure_end_time - cursor_time) * seg.tempo / 60.0
            measures.append(
                MeasureInterval(
                    index=measure_index,
                    start_time=cursor_time,
                    end_time=measure_end_time,
                    start_beats=cursor_beats,
                    end_beats=cursor_beats + actual_beats,
                    time_signature=seg.time_signature,
                )
            )
            cursor_time = measure_end_time
            cursor_beats += actual_beats
            measure_index += 1

    return measures


def _beats_from_seconds(time_value: float, segments: List[TempoSegment]) -> float:
    for seg in segments:
        if seg.start_time - BEAT_TOLERANCE <= time_value <= seg.end_time + BEAT_TOLERANCE:
            return seg.start_beats + (time_value - seg.start_time) * seg.tempo / 60.0
    # If beyond last segment due to rounding, clamp to end
    if segments:
        return segments[-1].end_beats
    return 0.0


def _quantize_beats(beats: float, resolution: float) -> float:
    if resolution <= 0:
        return beats
    return round(beats / resolution) * resolution


def _extract_quantized_groups(
    pm: pretty_midi.PrettyMIDI,
    segments: List[TempoSegment],
    quantize_resolution: float,
) -> List[Dict[str, object]]:
    groups: Dict[Tuple[float, float], List[Dict[str, int]]] = {}

    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            start_beats = _beats_from_seconds(note.start, segments)
            end_beats = _beats_from_seconds(note.end, segments)
            start_q = _quantize_beats(start_beats, quantize_resolution)
            end_q = _quantize_beats(end_beats, quantize_resolution)
            if end_q <= start_q:
                end_q = start_q + quantize_resolution
            key = (round(start_q, 6), round(end_q, 6))
            groups.setdefault(key, []).append({
                "pitch": note.pitch,
                "velocity": note.velocity,
            })

    quantized_groups: List[Dict[str, object]] = []
    for idx, ((start, end), notes) in enumerate(sorted(groups.items(), key=lambda item: item[0])):
        quantized_groups.append({
            "group_id": f"grp{idx}",
            "start_beats": start,
            "end_beats": end,
            "notes": notes,
        })

    return quantized_groups


def _chunk_group_into_measures(
    group: Dict[str, object],
    measures: List[MeasureInterval],
    measure_start_beats: List[float],
) -> List[Dict[str, object]]:
    chunks: List[Dict[str, object]] = []
    start = float(group["start_beats"])
    end = float(group["end_beats"])
    chunk_idx = 0

    while start + BEAT_TOLERANCE < end and measures:
        measure_pos = bisect_right(measure_start_beats, start) - 1
        measure_pos = max(0, min(measure_pos, len(measures) - 1))
        measure = measures[measure_pos]
        chunk_end = min(end, measure.end_beats)
        duration = max(chunk_end - start, BEAT_TOLERANCE)
        start_offset = max(start - measure.start_beats, 0.0)
        chunks.append({
            "measure_index": measure.index,
            "start_offset": round(start_offset, 6),
            "duration_beats": round(duration, 6),
            "chunk_index": chunk_idx,
            "continues": chunk_end + BEAT_TOLERANCE < end,
        })
        start = chunk_end
        chunk_idx += 1

    if not chunks:
        # Edge case: extremely short note, force into first measure
        measure = measures[0]
        chunks.append({
            "measure_index": measure.index,
            "start_offset": 0.0,
            "duration_beats": round(max(end - start, BEAT_TOLERANCE), 6),
            "chunk_index": 0,
            "continues": False,
        })

    return chunks


class MeasureAssembler:
    """Handles clef balancing and rest insertion for a single measure.
    
    Implements the full v3 strategy:
    1. Strict clef splitting by C4.
    2. Cross-clef placement when preferred clef overflows.
    3. Tie-to-next-measure when both clefs are full.
    4. Rest insertion with cross-clef awareness.
    """

    def __init__(self, interval: MeasureInterval):
        self.interval = interval
        self.events_by_clef: Dict[str, List[MeasureEvent]] = {
            "treble": [],
            "bass": [],
        }
        self.usage_by_clef = {"treble": 0.0, "bass": 0.0}
        self.ties_to_next: List[MeasureEvent] = []  # Events that overflow both clefs

    def add_event(self, event: MeasureEvent, preferred_clef: str) -> tuple[MeasureEvent, bool]:
        """Add event to measure, attempting placement in preferred clef first.
        
        Returns: (placed_event, was_tied_to_next)
            - placed_event: the event (merged if combined with existing)
            - was_tied_to_next: True if event exceeded both clefs and was deferred to next measure
        """
        limit = self.interval.beats_per_measure
        other_clef = "treble" if preferred_clef == "bass" else "bass"

        # Try preferred clef first
        if self._clef_can_accept(preferred_clef, event.duration_beats, limit):
            event.clef = preferred_clef
            stored = self._merge_or_append(preferred_clef, event)
            self.usage_by_clef[preferred_clef] += event.duration_beats
            event.event_id = stored.event_id or event.event_id
            self._update_chunk_keys(stored, event)
            return stored, False

        # Try other clef (cross-clef recovery)
        if self._clef_can_accept(other_clef, event.duration_beats, limit):
            event.moved_from = preferred_clef
            event.clef = other_clef
            stored = self._merge_or_append(other_clef, event)
            self.usage_by_clef[other_clef] += event.duration_beats
            event.event_id = stored.event_id or event.event_id
            self._update_chunk_keys(stored, event)
            return stored, False

        # Both clefs full: tie to next measure
        event.clef = preferred_clef  # Mark intended clef
        event.tie_to = f"{event.group_id}-{event.chunk_index + 1}-{preferred_clef}"
        self.ties_to_next.append(event)
        return event, True

    def finalize(self) -> List[MeasureEvent]:
        """Finalize timeline: sort, insert rests, merge chords."""
        treble_notes = sorted(self.events_by_clef["treble"], key=lambda e: (round(e.start_offset, 6), e.is_rest))
        bass_notes = sorted(self.events_by_clef["bass"], key=lambda e: (round(e.start_offset, 6), e.is_rest))

        treble_timeline = self._timeline_with_rests("treble", treble_notes)
        bass_timeline = self._timeline_with_rests("bass", bass_notes)

        combined = treble_timeline + bass_timeline
        combined.sort(key=lambda e: (round(e.start_offset, 6), 0 if e.clef == "bass" else 1, 1 if e.is_rest else 0))
        return combined

    def get_ties_to_next(self) -> List[MeasureEvent]:
        """Return events that overflowed both clefs and need tying to next measure."""
        return self.ties_to_next

    def _clef_can_accept(self, clef: str, duration: float, limit: float) -> bool:
        return self.usage_by_clef[clef] + duration <= limit + BEAT_TOLERANCE

    def _update_chunk_keys(self, stored: MeasureEvent, event: MeasureEvent) -> None:
        """Propagate chunk keys from event to stored if merged."""
        if event.chunk_keys and stored is not event:
            if stored.chunk_keys is None:
                stored.chunk_keys = []
            stored.chunk_keys.extend(event.chunk_keys)

    def _merge_or_append(self, clef: str, event: MeasureEvent) -> MeasureEvent:
        """Merge event into existing chord if same time/duration, else append."""
        for existing in self.events_by_clef[clef]:
            if existing.is_rest != event.is_rest:
                continue
            if abs(existing.start_offset - event.start_offset) <= BEAT_TOLERANCE and abs(existing.duration_beats - event.duration_beats) <= BEAT_TOLERANCE:
                if not event.is_rest:
                    existing.pitches.extend(event.pitches)
                    existing.pitches = sorted(set(existing.pitches))
                    existing.velocity = max(existing.velocity, event.velocity)
                return existing
        self.events_by_clef[clef].append(event)
        return event

    def _timeline_with_rests(
        self,
        clef: str,
        events: List[MeasureEvent],
    ) -> List[MeasureEvent]:
        """Build timeline with rest insertion.

        Always pads the clef to the measure limit so that silent spans become
        explicit rests, ensuring downstream consumers see the missing beats.
        """
        timeline: List[MeasureEvent] = []
        cursor = 0.0

        for event in events:
            gap = event.start_offset - cursor
            if gap > BEAT_TOLERANCE:
                rest = MeasureEvent(
                    measure_index=self.interval.index,
                    start_offset=cursor,
                    duration_beats=gap,
                    pitches=[],
                    velocity=0,
                    clef=clef,
                    is_rest=True,
                )
                timeline.append(rest)
                cursor = event.start_offset
            cursor = max(cursor, event.start_offset)
            timeline.append(event)
            cursor = max(cursor, event.start_offset + event.duration_beats)

        limit = self.interval.beats_per_measure
        remaining = limit - cursor
        if remaining > BEAT_TOLERANCE:
            rest = MeasureEvent(
                measure_index=self.interval.index,
                start_offset=cursor,
                duration_beats=remaining,
                pitches=[],
                velocity=0,
                clef=clef,
                is_rest=True,
            )
            timeline.append(rest)

        return timeline


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


REST_MARKER_KEY = "ugly_midi_rest_v2"


def _encode_rest_marker(note: Dict, clef: str, start_beats: float, duration_beats: float) -> str:
    payload = {
        "marker": REST_MARKER_KEY,
        "clef": clef,
        "start_beats": start_beats,
        "duration_beats": duration_beats,
        "id": note.get("id"),
        "name": note.get("name"),
    }
    return json.dumps(payload, separators=(",", ":"))


def _decode_rest_marker(text: str) -> Optional[Dict[str, object]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if payload.get("marker") != REST_MARKER_KEY:
        return None
    return payload


def check_measure_capacity(json_data: Dict, tolerance: float = 1e-6) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Return (issues, details) describing clef loads per measure.

    Helps detect "too many ticks" errors when rendering in VexFlow.
    """
    ts_data = json_data.get("timeSignature", {"numerator": 4, "denominator": 4})
    ts = TimeSignature(ts_data.get("numerator", 4), ts_data.get("denominator", 4))
    beats_per_measure = ts.beats_per_measure

    issues: List[Dict[str, object]] = []
    details: List[Dict[str, object]] = []
    measures = json_data.get("measures", [])
    for idx, measure in enumerate(measures):
        clef_loads: Dict[str, float] = {}
        for note in measure:
            duration_symbol = note.get("duration", "q")
            beats = DURATION_TO_BEATS.get(duration_symbol, 1.0)
            clef = note.get("clef", "treble")
            clef_loads[clef] = clef_loads.get(clef, 0.0) + beats

        clef_entries: List[Dict[str, object]] = []
        for clef, load in clef_loads.items():
            rounded = round(load, 4)
            over = load > beats_per_measure + tolerance
            clef_entries.append({
                "clef": clef,
                "beats": rounded,
                "limit": beats_per_measure,
                "over_limit": over,
            })
            if over:
                issues.append({
                    "measure": idx,
                    "clef": clef,
                    "beats": rounded,
                    "limit": beats_per_measure,
                })

        details.append({
            "measure": idx,
            "limit": beats_per_measure,
            "clefs": clef_entries,
        })

    return issues, details


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


def _extract_rest_markers(pm: pretty_midi.PrettyMIDI, tempo: float) -> List[Dict[str, object]]:
    markers: List[Dict[str, object]] = []
    for lyric in getattr(pm, "lyrics", []):
        payload = _decode_rest_marker(lyric.text)
        if not payload:
            continue
        duration_beats = float(payload.get("duration_beats", 0.0))
        if duration_beats <= 0:
            continue
        if "start_beats" in payload:
            start_beats = float(payload["start_beats"])
        else:
            start_beats = seconds_to_beats(lyric.time, tempo)
        markers.append({
            "start_beats": start_beats,
            "duration_beats": duration_beats,
            "clef": payload.get("clef", "treble"),
            "name": payload.get("name", "rest"),
            "id": payload.get("id"),
        })
    return markers


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
                start_beats = m_idx * beats_per_measure + clef_positions[clef]
                marker_text = _encode_rest_marker(note, clef, start_beats, duration_beats)
                pm.lyrics.append(
                    pretty_midi.Lyric(text=marker_text, time=beats_to_seconds(start_beats, tempo))
                )
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

    rest_events_by_measure: Dict[int, List[Dict]] = {}
    for marker in _extract_rest_markers(pm, tempo):
        start_beats = float(marker["start_beats"])
        measure_idx = int(start_beats // beats_per_measure)
        if measure_idx < 0:
            continue
        offset = start_beats - measure_idx * beats_per_measure
        rest_events_by_measure.setdefault(measure_idx, []).append({
            "offset": round(offset, 6),
            "duration_beats": float(marker["duration_beats"]),
            "clef": marker["clef"],
            "name": marker.get("name") or "rest",
            "id": marker.get("id"),
        })

    all_measure_indices = set(measures.keys()) | set(rest_events_by_measure.keys())
    max_measure = max(all_measure_indices) if all_measure_indices else 0
    result_measures: List[List[Dict]] = [[] for _ in range(max_measure + 1)]

    for measure_idx in range(max_measure + 1):
        note_list = measures.get(measure_idx, [])
        rest_list = rest_events_by_measure.get(measure_idx, [])
        # group key: (clef, offset, duration_beats)
        groups: Dict[Tuple[str, float, float], Dict[str, object]] = {}
        for n in note_list:
            clef = determine_clef_from_pitch(n["pitch"])
            key = (clef, round(n["offset"], 6), round(n["duration_beats"], 6))
            if key not in groups:
                groups[key] = {"pitches": [], "velocity": n.get("velocity", 100)}
            groups[key]["pitches"].append(n["pitch"])

        timeline_entries: List[Dict[str, object]] = []

        for (clef, offset, dur), data in groups.items():
            timeline_entries.append({
                "offset": offset,
                "clef": clef,
                "duration_beats": dur,
                "isRest": False,
                "name": midi_notes_to_name(data["pitches"]),
                "velocity": int(data["velocity"]),
            })

        for rest in rest_list:
            timeline_entries.append({
                "offset": rest["offset"],
                "clef": rest["clef"],
                "duration_beats": rest["duration_beats"],
                "isRest": True,
                "name": rest.get("name") or "rest",
                "id": rest.get("id"),
            })

        for event in sorted(timeline_entries, key=lambda e: (round(float(e["offset"]), 6), e["clef"], 1 if e["isRest"] else 0)):
            duration_symbol = beats_to_duration_symbol_simple(event["duration_beats"])
            entry_id = event.get("id")
            if not entry_id:
                entry_id = f"m{measure_idx}-{event['clef']}-{int(event['offset'] * 1000)}"
                if event["isRest"]:
                    entry_id += "-rest"
            base_entry = {
                "id": entry_id,
                "name": event["name"],
                "clef": event["clef"],
                "duration": duration_symbol,
                "measure": measure_idx,
                "isRest": event["isRest"],
            }
            if event["isRest"]:
                result_measures[measure_idx].append(base_entry)
            else:
                base_entry["velocity"] = event["velocity"]
                result_measures[measure_idx].append(base_entry)

    json_data: Dict = {
        "keySignature": "C",  # unknown from MIDI without extra analysis
        "tempo": int(tempo),
        "timeSignature": {"numerator": ts.numerator, "denominator": ts.denominator},
        "instrument": "piano",  # simplified
        "midiChannel": "0",
        "measures": result_measures,
    }

    issues, details = check_measure_capacity(json_data)
    for detail in details:
        print(f"[ugly_midi] Measure {detail['measure']} (limit {detail['limit']} beats):")
        for clef_entry in detail["clefs"]:
            status = "OVER" if clef_entry["over_limit"] else "OK"
            print(
                f"  {clef_entry['clef']}: {clef_entry['beats']} beats ({status})"
            )
    if issues:
        print("[ugly_midi] Measure overflow detected above; review OVER entries.")
    else:
        print("[ugly_midi] All measures within limit.")

    return json_data


def midi_to_json_v3(
    midi_file_path: str,
    manual_tempo: Optional[int] = None,
    quantize_resolution: float = 0.125,
) -> Dict:
    """Convert MIDI to JSON with explicit measure timing and clef-aware balancing."""

    try:
        pm = pretty_midi.PrettyMIDI(midi_file_path)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Could not load MIDI file: {exc}") from exc

    tempo_events = _canonicalize_tempo_events(pm, manual_tempo)
    ts_events = _canonicalize_time_signature_events(pm)
    song_end = pm.get_end_time()
    segments = _build_tempo_segments(tempo_events, ts_events, song_end)
    measures = _build_measure_intervals(segments)

    if not measures:
        raise ValueError("Unable to derive measures from MIDI data")

    measure_start_beats = [m.start_beats for m in measures]
    quantized_groups = _extract_quantized_groups(pm, segments, quantize_resolution)
    if not quantized_groups:
        raise ValueError("MIDI file contains no pitched notes")

    assemblers = {m.index: MeasureAssembler(m) for m in measures}
    tie_links: List[Tuple[Tuple[str, int, str], Tuple[str, int, str]]] = []
    overflow_events: List[Tuple[int, MeasureEvent]] = []  # (from_measure_idx, event) pairs

    for group in quantized_groups:
        group_id = group["group_id"]
        notes = group["notes"]
        bass_notes = [n for n in notes if n["pitch"] < 60]
        treble_notes = [n for n in notes if n["pitch"] >= 60]

        chunks = _chunk_group_into_measures(group, measures, measure_start_beats)

        for chunk in chunks:
            measure_idx = chunk["measure_index"]
            start_offset = chunk["start_offset"]
            duration_beats = chunk["duration_beats"]
            chunk_index = chunk["chunk_index"]
            assembler = assemblers[measure_idx]

            for clef, note_subset in (("bass", bass_notes), ("treble", treble_notes)):
                if not note_subset:
                    continue
                event = MeasureEvent(
                    measure_index=measure_idx,
                    start_offset=start_offset,
                    duration_beats=duration_beats,
                    pitches=[n["pitch"] for n in note_subset],
                    velocity=int(sum(n["velocity"] for n in note_subset) / len(note_subset)),
                    clef=clef,
                    is_rest=False,
                    group_id=group_id,
                    chunk_index=chunk_index,
                    chunk_keys=[(group_id, chunk_index, clef)],
                )
                event.event_id = f"{group_id}-{chunk_index}-{clef}"

                placed_event, was_tied = assembler.add_event(event, clef)
                
                # Handle ties within same measure
                if chunk["continues"]:
                    tie_links.append(
                        ((group_id, chunk_index, clef), (group_id, chunk_index + 1, clef))
                    )
                
                # Handle overflow to next measure
                if was_tied and measure_idx + 1 < len(measures):
                    overflow_events.append((measure_idx, placed_event))
    
    # Process overflow events: inject them as new chunks in next measures
    for from_measure_idx, overflow_event in overflow_events:
        # The overflowed event should start at beat 0 of the next measure
        overflow_event.measure_index = from_measure_idx + 1
        overflow_event.start_offset = 0.0
        next_assembler = assemblers[from_measure_idx + 1]
        placed_event, was_tied_again = next_assembler.add_event(overflow_event, overflow_event.clef)
        
        # Link the tie
        tie_links.append(
            ((overflow_event.group_id, overflow_event.chunk_index, overflow_event.clef),
             (placed_event.group_id or overflow_event.group_id, 
              placed_event.chunk_index or overflow_event.chunk_index,
              overflow_event.clef))
        )

    measure_payloads: List[List[Dict]] = [[] for _ in measures]
    event_lookup: Dict[str, Dict] = {}
    chunk_to_event: Dict[Tuple[str, int, str], str] = {}

    for measure in measures:
        timeline = assemblers[measure.index].finalize()
        seconds_per_beat = (measure.end_time - measure.start_time) / max(
            measure.end_beats - measure.start_beats, BEAT_TOLERANCE
        )

        for idx, event in enumerate(timeline):
            event_id = event.event_id or f"m{measure.index}-{event.clef}-{idx}"
            event.event_id = event_id

            duration_symbol = beats_to_duration_symbol_simple(event.duration_beats)
            entry = {
                "id": event_id,
                "clef": event.clef,
                "duration": duration_symbol,
                "measure": measure.index,
                "isRest": event.is_rest,
            }

            if event.is_rest:
                entry["name"] = "D3" if event.clef == "bass" else "B4"
            else:
                entry["name"] = midi_notes_to_name(event.pitches)
                entry["velocity"] = event.velocity
                entry["chordName"] = entry["name"]

            event_lookup[event_id] = entry

            if event.chunk_keys:
                for chunk_key in event.chunk_keys:
                    chunk_to_event[chunk_key] = event_id

            measure_payloads[measure.index].append(entry)

    for start_key, end_key in tie_links:
        start_id = chunk_to_event.get(start_key)
        end_id = chunk_to_event.get(end_key)
        if not start_id or not end_id:
            continue
        tie_payload = {
            "type": "tie",
            "startNoteId": start_id,
            "endNoteId": end_id,
        }
        event_lookup[start_id]["tie"] = tie_payload
        event_lookup[end_id]["tie"] = tie_payload

    measure_meta = [
        {
            "index": m.index,
            "startBeats": round(m.start_beats, 6),
            "endBeats": round(m.end_beats, 6),
            "startSeconds": round(m.start_time, 6),
            "endSeconds": round(m.end_time, 6),
            "timeSignature": {
                "numerator": m.time_signature.numerator,
                "denominator": m.time_signature.denominator,
            },
        }
        for m in measures
    ]

    json_data: Dict[str, object] = {
        "keySignature": "C",
        "tempo": int(tempo_events[0][1]),
        "timeSignature": {
            "numerator": measures[0].time_signature.numerator,
            "denominator": measures[0].time_signature.denominator,
        },
        "instrument": "piano",
        "midiChannel": "0",
        "measures": measure_payloads,
        "measureTimings": measure_meta,
        "tempoMap": [
            {"time": round(time, 6), "bpm": round(bpm, 3)} for time, bpm in tempo_events
        ],
    }

    issues, details = check_measure_capacity(json_data)
    for detail in details:
        print(f"[ugly_midi] Measure {detail['measure']} (limit {detail['limit']} beats):")
        for clef_entry in detail["clefs"]:
            status = "OVER" if clef_entry["over_limit"] else "OK"
            print(f"  {clef_entry['clef']}: {clef_entry['beats']} beats ({status})")
    if issues:
        print("[ugly_midi] Measure overflow detected above; review OVER entries.")
    else:
        print("[ugly_midi] All measures within limit.")

    return json_data
