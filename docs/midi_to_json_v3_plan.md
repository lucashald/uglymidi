# midi_to_json_v3 Planning Notes

- Add explicit calculation of each measure's start/end times using the tempo map and the active time signature at that instant.
1. **Tempo map**: sequence of `(time_seconds, bpm)` from `pretty_midi.PrettyMIDI.get_tempo_changes()`.
2. **Time-signature map**: sequence of `(time_seconds, numerator, denominator)` from `pretty_midi.PrettyMIDI.time_signature_changes` with a default of `4/4` at `t=0` if the file omits events.
## High-Level Flow
1. **Load MIDI** with PrettyMIDI.
2. Determine tempo and time signature.
3. Determine number of measures based on tempo and time signatures.
4. Determine the start time and end time of every measure
5. iterate through all the notes in the midi file like version 2 does.
6. now that we know exactly where each measure starts and ends, we can determine which measure a note belongs to.
7. Quantize all notes to the beat grid (v2 already does this).
8. **Group notes by simultaneity**: Identify all notes with the same (start_time, end_time) to form potential chords.
9. **Strict clef splitting**: Split each simultaneity by the C4 boundary. Notes < C4 → bass chord, notes ≥ C4 → treble chord. Keep separate for now.
10. **Overflow check & cross-clef merging**: For each chord in a clef, check if it fits in the available beats for that clef in that measure.
    - If it fits, keep it in that clef.
    - If it overflows, check the other clef: does the other clef have room at this time-slot? If yes, move the overflowed chord to the other clef and merge it with any existing chord there.
    - If the other clef is also full, tie the overflowed chord to the next measure.
11. **Rest insertion with cross-clef awareness**: Fill gaps in each clef with rests, but skip rest insertion if the other clef has a note occupying that time-slot (don't add rest when the gap is already filled).
12. **Emit final JSON**: Output measures with properly balanced clefs, ties, and rest markers.

## Clef Assignment & Chord Merging Strategy

**Pass 1: Strict Clef Splitting**
- Split every simultaneity by C4 (MIDI 60): notes < C4 → bass, notes ≥ C4 → treble.
- Example: `[C2, E3, D4, G4]` becomes two separate chords: bass `[C2, E3]` and treble `[D4, G4]`.

**Pass 2: Overflow & Cross-Clef Recovery**
- For each chord, check if it fits in its assigned clef's available beats in the current measure.
- If overflow: check if the other clef has room at the *same time-slot*.
  - If yes: move the overflowed chord to the other clef, merging it with any existing chord there.
    - Example: treble `[D4]` overflows, but bass `[C2, E3]` has room → result is bass `[C2, E3, D4]`.
  - If no: tie the entire chord to the next measure (all notes in the chord are tied together).

**Pass 3: Rest Insertion with Awareness**
- When inserting rests to fill gaps in a clef, check the other clef for simultaneous notes.
- If the other clef occupies that time-slot, don't insert a rest (the space is already "filled" by the note in the other clef).

**Outcome:**
- Notes naturally gravitate back to form complete chords when there's room.
- Clefs remain balanced (each respects the measure beat limit).
- Ties remain synchronized (whole chords split together).

