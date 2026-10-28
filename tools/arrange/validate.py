"""
Checks of a score, in musical terms, so that what is wrong can be fixed in the text it points to.

    python validate.py <song>        (also run by build.py)

Errors stop the build: a note outside its section's bars, a length of 0, a velocity outside 1-127, a part playing
outside its range (the part's range: in song.yaml, else the sound's), the same pitch struck again in a part while
it still sounds, an articulation not in score.ARTICULATIONS, a chord symbol music21 cannot read.

Warnings do not: notes ringing past the end of their section, an articulation the sound cannot play (and what it
falls back to), lines out of order (build.py --fmt sorts them), notes of the melody (role: melody) outside the
section's key, bass notes (role: bass) at a chord change that are neither its root nor its slash bass, parallel
fifths and octaves between the parts listed in song.yaml voice_leading:, and the textures that LLM scores fall
into (Libretto, arXiv 2606.22708): the same harmonic rhythm bar after bar, a melody that only moves by step, a
melody with a single note length.
"""
import sys
from collections import Counter

from perform import resolve_art
from score import (ARTICULATIONS, ScoreError, Song, chord_symbol, fmt_num, key_pitch_classes, midi_to_pitch,
                   pitch_to_midi, read_notes)

PARALLEL = {0: 'octaves', 7: 'fifths'}


def chord_at(chords, step):
    cur = None
    for s, c, sec in chords:
        if s > step:
            break
        cur = (s, c, sec)
    return cur


def chord_pcs(symbol):
    cs = chord_symbol(symbol)
    return {p.pitchClass for p in cs.pitches}, cs.root().pitchClass, cs.bass().pitchClass


def check(song):
    errors, warnings = [], []
    E, W = errors.append, warnings.append

    # chords
    chords = song.chord_events()
    parsed = {}
    for step, c, sec in chords:
        try:
            parsed[c.symbol] = chord_pcs(c.symbol)
        except Exception as e:  # music21 raises several kinds
            E(f'{c.src}: chord {c.symbol!r} cannot be read ({e})')

    for path, part in song.note_files():
        keys = [(n.bar, n.slot, n.midi) for n in read_notes(path, song.sound(part).get('drums'))]
        if keys != sorted(keys):
            W(f'{path.parent.name}/{path.name}: lines out of order (python build.py {song.name} --fmt)')

    for part, spec in song.parts.items():
        sound = song.sound(part)
        rng = spec.get('range') or sound.get('range')
        lo, hi = (pitch_to_midi(rng[0]), pitch_to_midi(rng[1])) if rng else (0, 127)
        arts = sound.get('articulations', {})
        default = spec.get('art') or sound.get('default')
        sounding = {}  # midi -> end step
        told = set()
        for step, n, sec in song.events(part):
            at = f'{n.src} ({song.where(sec, n.bar, n.slot)})'
            if not 1 <= n.bar <= sec.bars or not 1 <= n.slot < song.steps_per_bar + 1:
                E(f'{at}: outside the section, which has {sec.bars} bars of {song.steps_per_bar} slots')
            if n.dur <= 0:
                E(f'{at}: length {fmt_num(n.dur)}')
            if not 1 <= n.vel <= 127:
                E(f'{at}: velocity {n.vel}')
            if not spec.get('drums') and not lo <= n.midi <= hi:
                E(f'{at}: {n.pitch} is outside the {part} range {rng[0]}-{rng[1]}')
            end_sec = song.step(sec, sec.bars + 1, 1)
            if step + n.dur > end_sec:
                W(f'{at}: {n.pitch} rings {fmt_num(step + n.dur - end_sec)} slots past the end of {sec.name}')
            if n.midi in sounding and sounding[n.midi] > step:
                E(f'{at}: {n.pitch} struck again while the previous {n.pitch} still sounds')
            sounding[n.midi] = step + n.dur
            art = n.art or default
            if n.art and n.art not in ARTICULATIONS:
                E(f'{at}: unknown articulation {n.art!r}')
            elif arts and art and (part, art) not in told:
                played = resolve_art(art, arts)
                if played != art:
                    W(f'{part}: {spec.get("sound")} has no {art!r}, plays {played!r}' if played else
                      f'{part}: {spec.get("sound")} has no {art!r} nor a fallback; plays its default patch')
                    told.add((part, art))

    # harmony and melody
    for part, spec in song.parts.items():
        role = spec.get('role')
        evs = song.events(part)
        if role == 'melody':
            out = [(n, sec) for s, n, sec in evs if sec.key and n.midi % 12 not in key_pitch_classes(sec.key)]
            for n, sec in out[:12]:
                W(f'{n.src} ({song.where(sec, n.bar, n.slot)}): melody {n.pitch} is outside {sec.key}')
            if len(out) > 12:
                W(f'{part}: {len(out) - 12} more melody notes outside the key')
            mono = [n for s, n, sec in evs]
            if len(mono) > 8:
                moves = [abs(b.midi - a.midi) for a, b in zip(mono, mono[1:]) if b.midi != a.midi]
                steps = sum(1 for m in moves if m <= 2)
                if moves and steps / len(moves) > 0.85:
                    W(f'{part}: {steps}/{len(moves)} melodic moves are steps; the line may sound like a scale '
                      f'(add leaps, especially a leap at the phrase peak)')
                durs = Counter(n.dur for n in mono)
                if len(durs) == 1:
                    W(f'{part}: every melody note is {fmt_num(mono[0].dur)} slots long; vary the rhythm')
        if role == 'bass':
            for s, c, sec in chords:
                if c.symbol not in parsed:
                    continue
                pcs, root, bass = parsed[c.symbol]
                hit = [n for st, n, sc in evs if st == s]
                if hit and min(hit, key=lambda n: n.midi).midi % 12 not in (root, bass):
                    low = min(hit, key=lambda n: n.midi)
                    W(f'{low.src} ({song.where(sec, low.bar, low.slot)}): bass {low.pitch} under {c.symbol} is '
                      f'neither its root nor its bass')

    # harmonic rhythm: the same chord placement in every bar for 8 bars or more
    per_bar = {}
    for s, c, sec in chords:
        bar, slot = divmod(s, song.steps_per_bar)
        per_bar.setdefault(int(bar), []).append(slot)
    run, prev, longest = 0, None, 0
    for b in range(song.bars):
        pat = tuple(per_bar.get(b, ()))
        run = run + 1 if pat == prev and pat else 1
        prev = pat
        longest = max(longest, run)
    if longest >= 8:
        W(f'chords: the same harmonic rhythm {longest} bars running; vary where the chords change '
          f'(hold one for two bars, push one ahead of the beat)')

    # parallel fifths and octaves between voice_leading parts: the top note of each at shared onsets
    vl = song.meta.get('voice_leading') or []
    tops = {}
    for part in vl:
        d = {}
        for s, n, sec in song.events(part):
            d[s] = max(d.get(s, (None, -1)), (n, n.midi), key=lambda x: x[1])
        tops[part] = d
    for i, a in enumerate(vl):
        for b in vl[i + 1:]:
            shared = sorted(set(tops[a]) & set(tops[b]))
            for s1, s2 in zip(shared, shared[1:]):
                (na1, a1), (na2, a2) = tops[a][s1], tops[a][s2]
                (nb1, b1), (nb2, b2) = tops[b][s1], tops[b][s2]
                if a1 == a2 or b1 == b2 or (a2 - a1 > 0) != (b2 - b1 > 0):
                    continue
                i1, i2 = abs(a1 - b1) % 12, abs(a2 - b2) % 12
                if i1 == i2 and i1 in PARALLEL:
                    sec = next(sc for st, n, sc in song.events(a) if st == s2)
                    W(f'{na2.src}: parallel {PARALLEL[i1]} {a}/{b}, {midi_to_pitch(a1)}-{midi_to_pitch(b1)} to '
                      f'{midi_to_pitch(a2)}-{midi_to_pitch(b2)} ({song.where(sec, na2.bar, na2.slot)})')
    return errors, warnings


def main():
    try:
        song = Song(sys.argv[1])
        errors, warnings = check(song)
    except ScoreError as e:
        print(f'error: {e}')
        sys.exit(1)
    for w in warnings:
        print('warning:', w)
    for e in errors:
        print('error:', e)
    print(f'{song.name}: {len(errors)} errors, {len(warnings)} warnings')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
