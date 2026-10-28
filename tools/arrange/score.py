"""
The score as text: what Claude writes and edits, and what build.py, validate.py, frag.py and render.py read.

A song is a folder songs/<song>/ with song.yaml (tempo, meter, key, parts, form, mix) and one folder per section,
songs/<song>/<section>/, holding

    <part>.notes   one note to a line: bar slot dur pitch vel [art]
    <part>.cc      controller points:  bar slot cc<n> value     (linear ramp to the next point of the same cc)
    chords.txt     the harmony:        bar slot chord           (music21 chord symbols: Dm7, G7/B, Cmaj9 ...)
    section.yaml   optional: key: when the section is in another key than the song (E dorian)

bar counts from 1 at the start of the section, slot from 1 at the start of the bar in steps of 1/steps_per_beat of
a beat (16ths at the default 4), so in 4/4 slots 1, 5, 9 and 13 are the beats; dur is in slots. Every note carries
its own onset, so changing one note's length moves no other note, and a one-note edit is a one-line diff. slot and
dur may be fractions (3/2) for triplets and grace timing. pitch is scientific (C4 = MIDI 60, F#3, Bb5) or, in a
drum part, a name from the sound's drum map (kick, snare ...). vel is 1-127; art an articulation name from
ARTICULATIONS (the part's default when left out). # starts a comment (at the start of a line or after a space,
so F#4 stays a pitch). Lines are kept sorted by (bar, slot, pitch):
build.py --fmt rewrites the files so.

A section is a fragment: the form lists sections in order with their length in bars, and the same section may come
back several times. A part with no file in a section rests there.
"""
import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SONGS = HERE / 'songs'
LIBRARY_MAP = HERE / 'library_map'
BUILD = HERE / 'build'

# The articulation vocabulary the scores use, library independent; library_map/<library>.yaml says how each
# one is played on each sound. A sound without the articulation falls back along this chain.
ARTICULATIONS = {
    'sus': [],                   # sustained, plain
    'vib': ['sus'],              # sustained with vibrato
    'leg': ['sus'],              # legato: joined to the next note
    'stac': ['spic', 'sus'],     # staccato
    'spic': ['stac', 'sus'],     # spiccato (strings)
    'marc': ['stac', 'sus'],     # marcato
    'pizz': ['stac', 'sus'],     # pizzicato
    'trem': ['sus'],             # tremolo
    'exp': ['vib', 'sus'],       # expressive sustain (swell)
    'hit': [],                   # drums and percussion
}

# Scales as semitones above the tonic; a key is '<tonic> <mode>' (D dorian, F# minor, Bb lydian ...).
MODES = {
    'major': [0, 2, 4, 5, 7, 9, 11], 'ionian': [0, 2, 4, 5, 7, 9, 11],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'phrygian': [0, 1, 3, 5, 7, 8, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'minor': [0, 2, 3, 5, 7, 8, 10], 'aeolian': [0, 2, 3, 5, 7, 8, 10],
    'locrian': [0, 1, 3, 5, 6, 8, 10],
    'harmonic_minor': [0, 2, 3, 5, 7, 8, 11],
    'melodic_minor': [0, 2, 3, 5, 7, 9, 11],
    'major_pentatonic': [0, 2, 4, 7, 9],
    'minor_pentatonic': [0, 3, 5, 7, 10],
    'blues': [0, 3, 5, 6, 7, 10],
    'whole_tone': [0, 2, 4, 6, 8, 10],
}

COMMENT_RE = re.compile(r'(^|\s)#.*$')  # a # that starts a word: F#4 is a pitch
NOTE_RE = re.compile(r'^([A-Ga-g])(#{1,2}|b{1,2})?(-?\d+)$')
STEP = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
SHARP_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']


class ScoreError(Exception):
    pass


def pitch_to_midi(name):
    m = NOTE_RE.match(name)
    if not m:
        raise ValueError(f'not a pitch: {name!r}')
    letter, acc, octave = m.groups()
    acc = acc or ''
    return 12 * (int(octave) + 1) + STEP[letter.upper()] + acc.count('#') - acc.count('b')


def midi_to_pitch(n, flats=False):
    return (FLAT_NAMES if flats else SHARP_NAMES)[n % 12] + str(n // 12 - 1)


def parse_key(key):
    """'D dorian' -> (2, [0, 2, 3, 5, 7, 9, 10]): the tonic's pitch class and the mode's intervals."""
    tonic, mode = key.split(None, 1)
    mode = mode.strip().lower().replace(' ', '_')
    if mode not in MODES:
        raise ScoreError(f'unknown mode {mode!r} in key {key!r} (score.MODES)')
    return pitch_to_midi(tonic + '0') % 12, MODES[mode]


def key_pitch_classes(key):
    tonic, mode = parse_key(key)
    return {(tonic + i) % 12 for i in mode}


def chord_symbol(symbol):
    """A music21 ChordSymbol from the usual spelling: music21 writes flats as '-' (B-maj7, D/G-)."""
    from music21 import harmony
    return harmony.ChordSymbol(re.sub(r'(^|/)([A-G])b', r'\1\2-', symbol))


def num(s):
    """An int, a decimal or a fraction a/b, as a Fraction."""
    return Fraction(s)


def fmt_num(x):
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f'{x.numerator}/{x.denominator}'


@dataclass
class Note:
    bar: int
    slot: Fraction
    dur: Fraction
    pitch: str
    vel: int
    art: str | None = None
    src: str = ''          # file:line, for messages
    midi: int = 0          # MIDI note number (resolved from pitch, or from the drum map)

    def line(self):
        f = [str(self.bar), fmt_num(self.slot), fmt_num(self.dur), self.pitch, str(self.vel)]
        if self.art:
            f.append(self.art)
        return ' '.join(f)


@dataclass
class CCPoint:
    bar: int
    slot: Fraction
    cc: int
    value: int
    src: str = ''


@dataclass
class Chord:
    bar: int
    slot: Fraction
    symbol: str
    src: str = ''


@dataclass
class Section:
    name: str
    bars: int
    start_bar: int                                  # bar of the song (from 1) where this occurrence starts
    key: str | None = None                          # <section>/section.yaml key:, else the song's
    notes: dict = field(default_factory=dict)       # part -> [Note]
    cc: dict = field(default_factory=dict)          # part -> [CCPoint]
    chords: list = field(default_factory=list)


def _lines(path):
    for i, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        text = COMMENT_RE.sub('', raw).strip()
        if text:
            yield i, text.split()


def read_notes(path, drum_map=None):
    notes = []
    for i, f in _lines(path):
        src = f'{path.parent.name}/{path.name}:{i}'
        if len(f) not in (5, 6):
            raise ScoreError(f'{src}: expected "bar slot dur pitch vel [art]", got {" ".join(f)!r}')
        try:
            n = Note(int(f[0]), num(f[1]), num(f[2]), f[3], int(f[4]), f[5] if len(f) == 6 else None, src)
        except ValueError as e:
            raise ScoreError(f'{src}: {e}') from None
        if drum_map is not None and n.pitch in drum_map:
            n.midi = pitch_to_midi(drum_map[n.pitch])
        else:
            try:
                n.midi = pitch_to_midi(n.pitch)
            except ValueError:
                raise ScoreError(f'{src}: {n.pitch!r} is neither a pitch nor in the drum map') from None
        notes.append(n)
    return notes


def read_cc(path):
    points = []
    for i, f in _lines(path):
        src = f'{path.parent.name}/{path.name}:{i}'
        if len(f) != 4 or not f[2].startswith('cc'):
            raise ScoreError(f'{src}: expected "bar slot cc<n> value", got {" ".join(f)!r}')
        points.append(CCPoint(int(f[0]), num(f[1]), int(f[2][2:]), int(f[3]), src))
    return points


def read_chords(path):
    chords = []
    for i, f in _lines(path):
        src = f'{path.parent.name}/{path.name}:{i}'
        if len(f) != 3:
            raise ScoreError(f'{src}: expected "bar slot chord", got {" ".join(f)!r}')
        chords.append(Chord(int(f[0]), num(f[1]), f[2], src))
    return chords


def write_notes(path, notes, header=None):
    """Writes notes sorted by (bar, slot, pitch), keeping a leading comment block."""
    if header is None and path.exists():
        header = []
        for raw in path.read_text(encoding='utf-8').splitlines():
            if not raw.startswith('#'):
                break
            header.append(raw)
    lines = list(header or [])
    lines += [n.line() for n in sorted(notes, key=lambda n: (n.bar, n.slot, n.midi))]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


class Song:
    def __init__(self, folder):
        self.folder = Path(folder)
        if not (self.folder / 'song.yaml').exists() and (SONGS / folder / 'song.yaml').exists():
            self.folder = SONGS / folder
        self.name = self.folder.name
        self.meta = yaml.safe_load((self.folder / 'song.yaml').read_text(encoding='utf-8'))
        m = self.meta
        self.tempo = float(m['tempo'])
        self.beats_per_bar, self.beat_unit = (int(x) for x in str(m.get('meter', '4/4')).split('/'))
        self.steps_per_beat = int(m.get('steps_per_beat', 4))
        self.steps_per_bar = self.beats_per_bar * self.steps_per_beat
        self.key = m.get('key')
        self.parts = m['parts']                         # part -> {name, sound, range, program, ...}
        self.libraries = {}
        self.sections = []
        bar = 1
        for entry in m['form']:
            (name, bars), = entry.items()
            d = self.folder / name
            if not d.is_dir():
                raise ScoreError(f'form names section {name!r}, but there is no folder {d}')
            local = {}
            if (d / 'section.yaml').exists():
                local = yaml.safe_load((d / 'section.yaml').read_text(encoding='utf-8')) or {}
            sec = Section(name, int(bars), bar, local.get('key', self.key))
            for part, spec in self.parts.items():
                p = d / f'{part}.notes'
                if p.exists():
                    sec.notes[part] = read_notes(p, self.sound(part).get('drums'))
                p = d / f'{part}.cc'
                if p.exists():
                    sec.cc[part] = read_cc(p)
            unknown = {p.stem for p in d.glob('*.notes')} - set(self.parts)
            if unknown:
                raise ScoreError(f'{name}/: notes for parts not in song.yaml: {", ".join(sorted(unknown))}')
            if (d / 'chords.txt').exists():
                sec.chords = read_chords(d / 'chords.txt')
            self.sections.append(sec)
            bar += sec.bars
        self.bars = bar - 1

    def library(self, lib):
        if lib not in self.libraries:
            self.libraries[lib] = yaml.safe_load((LIBRARY_MAP / f'{lib}.yaml').read_text(encoding='utf-8'))
        return self.libraries[lib]

    def sound(self, part):
        """The library map entry of a part's sound ('<library>/<sound>' in song.yaml), {} when it has none."""
        ref = self.parts[part].get('sound')
        if not ref:
            return {}
        lib, snd = ref.split('/', 1)
        sounds = self.library(lib)['sounds']
        if snd not in sounds:
            raise ScoreError(f'part {part}: library_map/{lib}.yaml has no sound {snd!r}')
        return sounds[snd]

    def step(self, sec, bar, slot):
        """Absolute position in steps from the start of the song."""
        return (sec.start_bar + bar - 2) * self.steps_per_bar + (slot - 1)

    def seconds(self, steps):
        return float(steps) * 60.0 / (self.tempo * self.steps_per_beat)

    def where(self, sec, bar, slot):
        """'chorus bar 3 beat 2' (+ '.3' for the 3rd step in the beat), for messages."""
        s = slot - 1
        beat, sub = divmod(s, self.steps_per_beat)
        pos = f'beat {int(beat) + 1}' + (f' +{fmt_num(sub)}/{self.steps_per_beat}' if sub else '')
        return f'{sec.name} (song bar {sec.start_bar + bar - 1}) bar {bar} {pos}'

    def events(self, part):
        """Every note of a part over the whole form: (start_step, Note, Section), in order."""
        out = []
        for sec in self.sections:
            for n in sec.notes.get(part, []):
                out.append((self.step(sec, n.bar, n.slot), n, sec))
        out.sort(key=lambda e: (e[0], e[1].midi))
        return out

    def cc_events(self, part):
        out = []
        for sec in self.sections:
            for c in sec.cc.get(part, []):
                out.append((self.step(sec, c.bar, c.slot), c, sec))
        out.sort(key=lambda e: (e[1].cc, e[0]))
        return out

    def chord_events(self):
        out = []
        for sec in self.sections:
            for c in sec.chords:
                out.append((self.step(sec, c.bar, c.slot), c, sec))
        out.sort(key=lambda e: e[0])
        return out

    @property
    def length_steps(self):
        return self.bars * self.steps_per_bar

    def note_files(self):
        seen = set()
        for sec in self.sections:
            for part in self.parts:
                p = self.folder / sec.name / f'{part}.notes'
                if p.exists() and p not in seen:
                    seen.add(p)
                    yield p, part
