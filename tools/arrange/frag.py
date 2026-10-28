"""
Transformations of a fragment (a .notes file), written out as a new .notes file: the result is plain notes like
any other, to read, diff and edit by hand, with a header saying what it was made from.

    python frag.py <src.notes> -o <dst.notes> [operations, applied in the order given]

    --transpose N             N semitones
    --steps N KEY             N steps along the scale of KEY ('D dorian'); a note outside the scale keeps its
                              distance from the scale note below it
    --remode KEY1 KEY2        each note to the same degree of KEY2 (D dorian -> D phrygian, D dorian -> E dorian);
                              the two scales need as many notes
    --invert AXIS KEY         mirrored along the scale of KEY around the pitch AXIS
    --retro                   backwards in time, over the bars the fragment spans
    --stretch F               onsets and lengths times F (2 augments, 1/2 diminishes)
    --shift BARS              BARS later (earlier if negative)
    --bars A-B                only bars A to B, renumbered from 1 (notes starting there)
    --vel +N | xF             velocities N more, or F times
    --art NAME | -            every note's articulation set (- clears it, so the part's default plays)

--spb (16) is slots per bar, for --retro, --stretch and --shift: 16 for 4/4 at 16ths. Pitches come out with
sharps or flats as most of the source's were spelled.
"""
import argparse
import math
from fractions import Fraction
from pathlib import Path

from score import ScoreError, midi_to_pitch, parse_key, pitch_to_midi, read_notes, write_notes


def degree(m, key):
    """(scale degree counted from the tonic in octave -1, chromatic offset above it) of MIDI note m."""
    tonic, mode = parse_key(key)
    r = (m - tonic) % 12
    k = max(i for i, iv in enumerate(mode) if iv <= r)
    octave = (m - tonic - r) // 12
    return octave * len(mode) + k, r - mode[k]


def from_degree(d, chroma, key):
    tonic, mode = parse_key(key)
    octave, k = divmod(d, len(mode))
    return tonic + 12 * octave + mode[k] + chroma


def op_transpose(notes, n, **_):
    for x in notes:
        x.midi += int(n)


def op_steps(notes, n, key, **_):
    for x in notes:
        d, c = degree(x.midi, key)
        x.midi = from_degree(d + int(n), c, key)


def op_remode(notes, k1, k2, **_):
    if len(parse_key(k1)[1]) != len(parse_key(k2)[1]):
        raise ScoreError(f'{k1} and {k2} have scales of different sizes')
    for x in notes:
        d, c = degree(x.midi, k1)
        x.midi = from_degree(d, c, k2)


def op_invert(notes, axis, key, **_):
    da, _ = degree(pitch_to_midi(axis), key)
    for x in notes:
        d, c = degree(x.midi, key)
        x.midi = from_degree(2 * da - d, 0, key) - c  # a note c above a degree mirrors to c below its mirror


def _abs(x, spb):
    return (x.bar - 1) * spb + (x.slot - 1)


def _place(x, a, spb):
    bar, slot = divmod(a, spb)
    x.bar, x.slot = int(bar) + 1, slot + 1


def op_retro(notes, spb, **_):
    if not notes:
        return
    span = math.ceil(max(_abs(x, spb) + x.dur for x in notes) / spb) * spb
    for x in notes:
        _place(x, span - (_abs(x, spb) + x.dur), spb)


def op_stretch(notes, f, spb, **_):
    f = Fraction(f)
    for x in notes:
        _place(x, _abs(x, spb) * f, spb)
        x.dur *= f


def op_shift(notes, bars, **_):
    for x in notes:
        x.bar += int(bars)


def op_bars(notes, rng, **_):
    a, b = (int(v) for v in rng.split('-'))
    keep = [x for x in notes if a <= x.bar <= b]
    for x in keep:
        x.bar -= a - 1
    notes[:] = keep


def op_vel(notes, v, **_):
    for x in notes:
        x.vel = round(x.vel * float(v[1:])) if v[0] in 'x*' else x.vel + int(v)
        x.vel = max(1, min(127, x.vel))


def op_art(notes, name, **_):
    for x in notes:
        x.art = None if name == '-' else name


OPS = {'transpose': (op_transpose, 1), 'steps': (op_steps, 2), 'remode': (op_remode, 2), 'invert': (op_invert, 2),
       'retro': (op_retro, 0), 'stretch': (op_stretch, 1), 'shift': (op_shift, 1), 'bars': (op_bars, 1),
       'vel': (op_vel, 1), 'art': (op_art, 1)}


class Op(argparse.Action):
    def __call__(self, parser, ns, values, option_string=None):
        ns.ops = (ns.ops or []) + [(self.dest, values or [])]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--spb', type=int, default=16)
    for name, (fn, n) in OPS.items():
        ap.add_argument(f'--{name}', nargs=n, action=Op, dest=name, metavar='ARG')
    ap.set_defaults(ops=[])
    a = ap.parse_args()
    src = Path(a.src)
    notes = read_notes(src)
    flats = sum(x.pitch.count('b') for x in notes) > sum(x.pitch.count('#') for x in notes)
    for name, args in a.ops:
        OPS[name][0](notes, *args, spb=a.spb)
    for x in notes:
        x.pitch = midi_to_pitch(x.midi, flats)
    desc = ' '.join(f'--{n} ' + ' '.join(f'"{v}"' if ' ' in v else v for v in args) for n, args in a.ops)
    header = [f'# from {src.parent.name}/{src.name}: {desc.strip()}']
    write_notes(Path(a.out), notes, header)
    print(f'{len(notes)} notes -> {a.out}')


if __name__ == '__main__':
    main()
