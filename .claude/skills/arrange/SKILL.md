---
name: arrange
description: Compose, edit, re-orchestrate, splice or render music in tools/arrange/ (the score is text in git, one note to a line). Use whenever the user asks for melodies, fragments in some key or mode, harmony, orchestration, changes to particular notes or instruments, joining fragments, or a rendered audio file.
---

# Arranging in tools/arrange/

The user wants control of every note and every sound, and to see exactly what each change did. The text under
`tools/arrange/songs/<song>/` is the only source; MIDI, MusicXML, stems and mixes in `build/` are made from it and
never edited. Formats and tools are documented at the top of each script; read `score.py` first.

Run everything with `tools/arrange/.venv/Scripts/python` from `tools/arrange/` (create it with
`python -m venv .venv` and `pip install -r requirements.txt` if missing).

## Working order

1. Form and harmony first: `song.yaml` form, then `chords.txt` per section. Vary the harmonic rhythm (validate.py
   warns when every bar changes chord the same way).
2. Then the melody (role: melody), then the bass (role: bass), then the inner parts and accompaniment patterns,
   then counter-lines and fills.
3. One note to a line, `bar slot dur pitch vel [art]`, slots of 1/steps_per_beat beat; keep lines sorted
   (`build.py <song> --fmt`). Use articulation names from `score.ARTICULATIONS` only; library_map/ translates them.
4. Generate long regular patterns (arpeggios, drum grooves) with a short one-off script that writes explicit
   lines, then treat the result as text like any other. Transform fragments with `frag.py` (transpose, steps along
   a mode, remode, invert, retro, stretch, shift, bars), which records the source in the file's header.
5. Splicing fragments: work out the outgoing chord and last note of A and the incoming ones of B, find a pivot
   chord or a secondary dominant, and write 1-4 bars of transition. Offer the user two or three versions; this is
   the weakest step for an LLM.

## After every change

- `build.py <song>`: fix every error; read the warnings and fix those that are real (they are in musical terms).
- Look at `build/<song>/roll.png` (Read the image) for texture and register.
- `review.py <song>` (and `--musicdiff`) lists the change note by note against HEAD: check that it says exactly
  what was asked and nothing else, and show it to the user.
- `render.py <song>` re-renders only the stems whose part changed; the mix is `build/<song>/<song>.wav`.
- One change, one commit (identity: see the git-identity memory), message saying what changed musically.

## Sounds

`library_map/<library>.yaml` maps each sound to a plugin, its saved state, its range and its articulations
(keyswitch, cc or program). Changing a part's instrument or library is a change to `song.yaml` `sound:`, not to
the notes. A new sound needs its state captured once: `render.py --capture <library>/<sound>` opens the plugin's
window for the user to load the patch. Commercial plugins render on this Windows PC only; AutoDL is for the
vocal pipeline. Rendered stems must not be used to train any model (NI and Spitfire licences).
