"""
What changed in a song between a git revision and the working tree (or between two revisions), note by note.

    python review.py <song> [REV [REV2]] [--musicdiff]

REV defaults to HEAD; with REV2 the two revisions are compared. Notes are matched by part and onset: a note at the
same place with another pitch is a pitch change, the same pitch with another length, velocity or articulation is
a change of those, anything else was added or removed. Chords, the form and song.yaml are compared too. Positions
are given as section, bar and beat, and as song bars, so they can be found in the roll (build.py) and the text.

--musicdiff also builds both versions' MusicXML and prints musicdiff's notation diff (python -m musicdiff -o text).
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from score import HERE, Song, fmt_num

REPO = HERE.parents[1]


def export(song_dir, rev, dest):
    """The song folder as it was at rev, into dest."""
    rel = song_dir.resolve().relative_to(REPO).as_posix()
    files = subprocess.run(['git', '-C', str(REPO), 'ls-tree', '-r', '--name-only', rev, rel + '/'],
                           capture_output=True, text=True, check=True).stdout.split()
    if not files:
        sys.exit(f'{rel} does not exist at {rev}')
    for f in files:
        data = subprocess.run(['git', '-C', str(REPO), 'show', f'{rev}:{f}'], capture_output=True, check=True).stdout
        out = dest / Path(f).relative_to(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
    return dest


def table(song):
    """{(part, step): {midi: Note}} and the sections by step, for matching."""
    t = {}
    for part in song.parts:
        for step, n, sec in song.events(part):
            t.setdefault((part, step), {})[n.midi] = (n, sec)
    return t


def describe(song, n, sec):
    return song.where(sec, n.bar, n.slot)


def compare(old, new):
    lines = []
    if old.meta.get('form') != new.meta.get('form'):
        lines.append(f'form: {old.meta.get("form")} -> {new.meta.get("form")}')
    for k in ('tempo', 'meter', 'key', 'steps_per_beat'):
        if old.meta.get(k) != new.meta.get(k):
            lines.append(f'{k}: {old.meta.get(k)} -> {new.meta.get(k)}')
    for part in sorted(set(old.parts) | set(new.parts)):
        a, b = old.parts.get(part), new.parts.get(part)
        if a != b:
            lines.append(f'part {part}: {a} -> {b}')
    oc = {(s, c.symbol) for s, c, sec in old.chord_events()}
    nc = {(s, c.symbol) for s, c, sec in new.chord_events()}
    bar = lambda s: f'song bar {s // new.steps_per_bar + 1} slot {fmt_num(s % new.steps_per_bar + 1)}'
    for s, sym in sorted(oc - nc):
        lines.append(f'chords: - {sym} at {bar(s)}')
    for s, sym in sorted(nc - oc):
        lines.append(f'chords: + {sym} at {bar(s)}')

    ot, nt = table(old), table(new)
    for key in sorted(set(ot) | set(nt), key=lambda k: (k[1], k[0])):
        part, step = key
        was, now = ot.get(key, {}), nt.get(key, {})
        gone = sorted(set(was) - set(now))
        came = sorted(set(now) - set(was))
        for m in sorted(set(was) & set(now)):
            (n0, s0), (n1, s1) = was[m], now[m]
            diffs = [f'{k} {getattr(n0, k)} -> {getattr(n1, k)}' for k in ('dur', 'vel', 'art')
                     if getattr(n0, k) != getattr(n1, k)]
            if diffs:
                lines.append(f'{part} {describe(new, n1, s1)}: {n1.pitch} ' + ', '.join(
                    d.replace('dur ', 'length ').replace('vel ', 'velocity ') for d in diffs) + f'  [{n1.src}]')
        while gone and came:  # pair them up as pitch changes, nearest first
            g = gone.pop(0)
            c = min(came, key=lambda c: abs(c - g))
            came.remove(c)
            (n0, s0), (n1, s1) = was[g], now[c]
            extra = [f'{k} {getattr(n0, k)} -> {getattr(n1, k)}' for k in ('dur', 'vel', 'art')
                     if getattr(n0, k) != getattr(n1, k)]
            lines.append(f'{part} {describe(new, n1, s1)}: {n0.pitch} -> {n1.pitch}'
                         + (', ' + ', '.join(extra) if extra else '') + f'  [{n1.src}]')
        for g in gone:
            n0, s0 = was[g]
            lines.append(f'{part} {describe(old, n0, s0)}: - {n0.line()}  [{n0.src}]')
        for c in came:
            n1, s1 = now[c]
            lines.append(f'{part} {describe(new, n1, s1)}: + {n1.line()}  [{n1.src}]')
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('song')
    ap.add_argument('rev', nargs='?', default='HEAD')
    ap.add_argument('rev2', nargs='?')
    ap.add_argument('--musicdiff', action='store_true')
    a = ap.parse_args()
    current = Song(a.song)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        old = Song(export(current.folder, a.rev, tmp / 'old' / current.name))
        new = Song(export(current.folder, a.rev2, tmp / 'new' / current.name)) if a.rev2 else current
        lines = compare(old, new)
        label = f'{a.rev}..{a.rev2 or "working tree"}'
        print(f'{current.name} {label}: {len(lines)} changes' + (':' if lines else ''))
        for ln in lines:
            print('  ' + ln)
        if a.musicdiff:
            from build import musicxml
            fa, fb = tmp / 'old.musicxml', tmp / 'new.musicxml'
            musicxml(old, fa)
            musicxml(new, fb)
            print('\nmusicdiff:')
            r = subprocess.run([sys.executable, '-m', 'musicdiff', '-o', 'text', str(fa), str(fb)],
                               capture_output=True, text=True)
            print(r.stdout.strip() or r.stderr.strip() or '(no notation differences)')


if __name__ == '__main__':
    main()
