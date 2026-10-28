"""
Builds a song from its text into what can be heard and looked at, after validate.py's checks.

    python build.py <song> [--fmt] [--no-roll]

writes, into build/<song>/ (not under git: everything there comes from songs/<song>/),
    <song>.mid          General MIDI, one track per part: for listening in any player and for importing in a DAW
    render/<part>.mid   the part as its sound plays it (keyswitches, controllers): what render.py renders
    <song>.musicxml     the score, for MuseScore, Verovio and musicdiff (review.py)
    roll.png            a piano roll, one lane per part, bars and sections marked, chords on top

--fmt first rewrites every .notes file in (bar, slot, pitch) order. Errors from validate.py stop the build.
"""
import argparse
import re
import sys
from fractions import Fraction

from score import BUILD, ScoreError, Song, chord_symbol, read_notes, write_notes
import perform
import validate


def fmt(song):
    for path, part in song.note_files():
        notes = read_notes(path, song.sound(part).get('drums'))
        before = path.read_text(encoding='utf-8')
        write_notes(path, notes)
        if path.read_text(encoding='utf-8') != before:
            print('sorted', path.relative_to(song.folder))


def musicxml(song, path):
    from music21 import chord, instrument, key, meter, note, stream, tempo
    score = stream.Score(id=song.name)
    ql = Fraction(4, song.beat_unit) / song.steps_per_beat  # quarter lengths per step
    first = True
    for part, spec in song.parts.items():
        if spec.get('drums'):
            continue
        p = stream.Part(id=part)
        p.partName = spec.get('name', part)
        inst = instrument.instrumentFromMidiProgram(spec.get('program', 0))
        inst.partName = p.partName
        p.insert(0, inst)
        p.insert(0, meter.TimeSignature(f'{song.beats_per_bar}/{song.beat_unit}'))
        if song.key:
            tonic, mode = song.key.split(None, 1)
            p.insert(0, key.Key(tonic, mode.strip().lower()))
        if first:
            p.insert(0, tempo.MetronomeMark(number=song.tempo))
        groups = {}
        for step, n, sec in song.events(part):
            groups.setdefault((step, n.dur), []).append(n)
        for (step, dur), ns in groups.items():
            el = note.Note(ns[0].midi) if len(ns) == 1 else chord.Chord([n.midi for n in ns])
            el.quarterLength = float(dur * ql)
            el.volume.velocity = ns[0].vel
            p.insert(float(step * ql), el)
        end = float(song.length_steps * ql)
        if p.highestTime < end:
            r = note.Rest(quarterLength=end - p.highestTime)
            p.insert(p.highestTime, r)
        p = p.chordify() if any(len(v) for v in groups.values()) else p
        p.id = part
        if first:
            for step, c, sec in song.chord_events():
                p.insert(float(step * ql), chord_symbol(c.symbol))
        first = False
        score.insert(0, p)
    out = score.write('musicxml', fp=str(path))
    # music21 numbers parts and instruments with random ids on every export: make them stable for diffs
    text = path.read_text(encoding='utf-8')
    for prefix in 'PI':
        ids = list(dict.fromkeys(re.findall(rf'id="({prefix}[0-9a-f]{{8,}})"', text)))
        for i, k in enumerate(ids, 1):
            text = text.replace(k, f'{prefix}{i}')
    text = re.sub(r'<encoding-date>[^<]*</encoding-date>', '', text)
    path.write_text(text, encoding='utf-8')
    return out


def roll(song, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    lanes = [(part, song.events(part)) for part in song.parts]
    lanes = [(p, e) for p, e in lanes if e]
    spans = []
    for part, evs in lanes:
        lo, hi = min(n.midi for s, n, sec in evs), max(n.midi for s, n, sec in evs)
        spans.append((lo - 1, hi + 1))
    heights = [max(6, hi - lo) for lo, hi in spans]
    fig, axes = plt.subplots(len(lanes), 1, figsize=(max(12, song.bars * 0.9), 1.2 + 0.12 * sum(heights)),
                             gridspec_kw={'height_ratios': heights}, sharex=True, squeeze=False)
    spb = song.steps_per_bar
    for ax, (part, evs), (lo, hi) in zip(axes[:, 0], lanes, spans):
        for s, n, sec in evs:
            x = float(s) / spb + 1
            ax.add_patch(Rectangle((x, n.midi - 0.4), float(n.dur) / spb, 0.8, color='C0',
                                   alpha=0.35 + 0.65 * n.vel / 127, lw=0))
        ax.set_ylim(lo, hi)
        ax.set_ylabel(part, rotation=0, ha='right', va='center')
        ticks = [m for m in range(lo + 1, hi) if m % 12 == 0] or [lo + 1]
        ax.set_yticks(ticks, [f'C{m // 12 - 1}' for m in ticks], fontsize=7)
        for b in range(1, song.bars + 2):
            ax.axvline(b, color='0.85', lw=0.5, zorder=0)
        for sec in song.sections:
            ax.axvline(sec.start_bar, color='0.3', lw=1.2, zorder=0)
    top = axes[0, 0]
    for sec in song.sections:
        top.text(sec.start_bar + 0.05, 1.18, sec.name, transform=top.get_xaxis_transform(), fontsize=9,
                 weight='bold')
    for s, c, sec in song.chord_events():
        top.text(float(s) / spb + 1, 1.03, c.symbol, transform=top.get_xaxis_transform(), fontsize=7)
    axes[-1, 0].set_xlim(1, song.bars + 1)
    axes[-1, 0].set_xticks(range(1, song.bars + 1))
    axes[-1, 0].set_xlabel('bar')
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('song')
    ap.add_argument('--fmt', action='store_true')
    ap.add_argument('--no-roll', action='store_true')
    a = ap.parse_args()
    try:
        song = Song(a.song)
        if a.fmt:
            fmt(song)
            song = Song(a.song)
        errors, warnings = validate.check(song)
    except ScoreError as e:
        print(f'error: {e}')
        sys.exit(1)
    for w in warnings:
        print('warning:', w)
    for e in errors:
        print('error:', e)
    if errors:
        print(f'{song.name}: {len(errors)} errors, not built')
        sys.exit(1)
    out = BUILD / song.name
    out.mkdir(parents=True, exist_ok=True)
    perform.write_midi(song, out / f'{song.name}.mid')
    for part in song.parts:
        if song.parts[part].get('sound') and song.events(part):
            perform.write_midi(song, out / 'render' / f'{part}.mid', [part], for_sound=True)
    musicxml(song, out / f'{song.name}.musicxml')
    if not a.no_roll:
        roll(song, out / 'roll.png')
    n = sum(len(song.events(p)) for p in song.parts)
    print(f'{song.name}: {song.bars} bars, {len(song.parts)} parts, {n} notes, {len(warnings)} warnings -> {out}')


if __name__ == '__main__':
    main()
