"""
Training set of one speaker made from the lines of eval_lines.py instead of the slice step: the chosen
lines of each song, joined where they follow each other, become clips of MIN_LEN to MAX_LEN seconds.

    python tools/autodl/build_clips.py <speaker dir> <dataset>

dataset (which lines go in):
    all    every line, i.e. the dry vocals as they are (the baseline of an A/B run)
    sig75  lines with a signal score (eval_lines.py) of at least 75
    clean  lines that the model fitted to the listener's marks keeps (eval/line_model.json, fit_lines.py),
           in songs where it keeps at least SONG_KEEP_MIN of the sung time: when it leaves out most of a
           song, the song itself is the problem (heavy reverb or loud BGM in the original, talk), and its
           remaining lines go too

Writes <speaker>/data_<dataset>/train/audio and val/audio (config.sh: DATASET=<dataset>). A few songs are
held out of every dataset (eval/holdout.json, drawn once): their lines that look good to the signal score
and to the listener's model are the validation set, the same for all datasets so that runs compare, and
the input of the A/B listening (abtest.py).
"""
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stages import DRY  # noqa: E402

MIN_LEN, MAX_LEN = 2.5, 15.0  # seconds; DDSP-SVC trains on 2 s crops (data.duration)
MAX_GAP = 1.0                 # lines further apart stay in separate clips
MARGIN = 0.05                 # seconds kept before and after a clip's lines
HOLDOUT_SONGS = 4
HOLDOUT_GOOD = 0.8            # held-out songs: share of their lines that must look good (see holdout)
SONG_KEEP_MIN = 0.5           # dataset clean: share of a song's sung time the model must keep
VAL_CLIPS = 12


def load_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []


def listener_keeps(spk):
    """{(song, k)} of the lines the model fitted to the listener's marks keeps (fit_lines.py), None before the fit."""
    if not (spk / 'eval' / 'line_model.json').exists():
        return None
    import fit_lines  # next to this file
    return fit_lines.keep_set(spk)


def holdout(spk, lines, keep):
    """Songs kept out of training, drawn once among songs whose lines are mostly good: at least HOLDOUT_GOOD
    of their lines with a signal score of 75, and once it is fitted, kept by the listener's model (the signal
    score alone hardly agrees with the listener: AUC 0.52 on the marks of 2026-10-20)."""
    path = spk / 'eval' / 'holdout.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    by_song = {}
    for m in lines:
        by_song.setdefault(m['song'], []).append(m)
    good = sorted(s for s, ms in by_song.items()
                  if len(ms) >= 10 and np.mean([m['score'] >= 75 for m in ms]) >= HOLDOUT_GOOD)
    if keep is not None:
        liked = [s for s in good if np.mean([(m['song'], m['k']) in keep for m in by_song[s]]) >= HOLDOUT_GOOD]
        good = liked if len(liked) >= HOLDOUT_SONGS else good
    songs = sorted(random.Random(spk.name).sample(good, min(HOLDOUT_SONGS, len(good))))
    path.write_text(json.dumps(songs, ensure_ascii=False), encoding='utf-8')
    return songs


def chosen(spk, dataset, lines, keep):
    """{(song, k)} of the lines that go into this dataset."""
    if dataset == 'all':
        return {(m['song'], m['k']) for m in lines}
    if dataset == 'sig75':
        return {(m['song'], m['k']) for m in lines if m['score'] >= 75}
    if dataset == 'clean':
        if keep is None:
            sys.exit(f'{spk.name}: no eval/line_model.json yet; run fitlines first')
        total, kept = {}, {}
        for m in lines:
            total[m['song']] = total.get(m['song'], 0.0) + m['dur']
            if (m['song'], m['k']) in keep:
                kept[m['song']] = kept.get(m['song'], 0.0) + m['dur']
        bad = {s for s in total if kept.get(s, 0.0) < SONG_KEEP_MIN * total[s]}
        print(f'{spk.name}: {len(bad)} of {len(total)} songs left out whole (under {SONG_KEEP_MIN:.0%} kept): '
              + ', '.join(sorted(bad)[:20]) + (' ...' if len(bad) > 20 else ''), flush=True)
        return {key for key in keep if key[0] not in bad}
    sys.exit(f'unknown dataset {dataset}')


def clips_of(song_lines, keep):
    """[(start, end, k of the first line)] joining kept lines that follow each other."""
    out, cur = [], None
    for m in sorted(song_lines, key=lambda m: m['start']):
        if (m['song'], m['k']) not in keep:
            if cur:
                out.append(cur)
            cur = None
            continue
        if cur and m['start'] - cur[1] <= MAX_GAP and m['end'] - cur[0] <= MAX_LEN:
            cur = (cur[0], m['end'], cur[2])
        else:
            if cur:
                out.append(cur)
            cur = (m['start'], m['end'], m['k'])
    if cur:
        out.append(cur)
    return [c for c in out if c[1] - c[0] >= MIN_LEN]


def write_clips(spk, song, spans, folder):
    x, sr = sf.read(str(spk / 'work' / DRY / f'{song}.wav'), dtype='float32', always_2d=True)
    x = x.mean(1)
    for s, e, k in spans:
        a, b = max(0, int((s - MARGIN) * sr)), min(len(x), int((e + MARGIN) * sr))
        sf.write(str(folder / f'{song}_{k:03d}.wav'), x[a:b], sr, subtype='PCM_16')
    return sum(e - s for s, e, _ in spans)


def main():
    spk, dataset = Path(sys.argv[1]), sys.argv[2]
    out = spk / f'data_{dataset}'
    train, val = out / 'train' / 'audio', out / 'val' / 'audio'
    if any(p.exists() and any(p.iterdir()) for p in (train, val)):
        sys.exit(f'{out} holds clips already; move it away to build it again')
    train.mkdir(parents=True, exist_ok=True)
    val.mkdir(parents=True, exist_ok=True)
    lines = load_jsonl(spk / 'eval' / 'lines.jsonl')
    liked = listener_keeps(spk)
    held = set(holdout(spk, lines, liked))
    keep = chosen(spk, dataset, lines, liked)
    by_song = {}
    for m in lines:
        by_song.setdefault(m['song'], []).append(m)
    total, n = 0.0, 0
    for song, ms in sorted(by_song.items()):
        if song in held:
            continue
        spans = clips_of(ms, keep)
        total += write_clips(spk, song, spans, train)
        n += len(spans)
    # validation: lines of the held-out songs with a signal score of 75 that the listener's model keeps, the
    # same for every dataset; tools/autodl/abtest.py converts them for the A/B listening. A dataset built
    # earlier lends its validation clips as they are, since the model may have been fitted again since.
    earlier = next((d for d in [spk / 'data_all' / 'val' / 'audio'] + sorted(spk.glob('data_*/val/audio'))
                    if d.is_dir() and d != val and any(d.glob('*.wav'))), None)
    if earlier:
        spans = [shutil.copy(f, val / f.name) for f in sorted(earlier.glob('*.wav'))]
        print(f'{spk.name} {dataset}: validation clips copied from {earlier.parent.parent.name}', flush=True)
    else:
        best = {(m['song'], m['k']) for m in lines if m['song'] in held and m['score'] >= 75
                and (liked is None or (m['song'], m['k']) in liked)}
        spans = sorted(((song, c) for song in sorted(held) for c in clips_of(by_song[song], best)),
                       key=lambda t: (t[0], t[1][0]))
        spans = random.Random(spk.name).sample(spans, min(VAL_CLIPS, len(spans)))
        for song in held:
            write_clips(spk, song, [c for s, c in spans if s == song], val)
    print(f'{spk.name} {dataset}: {n} training clips, {total / 3600:.2f} h from {len(keep)} of {len(lines)} lines; '
          f'{len(spans)} validation clips from the held-out songs {sorted(held)}', flush=True)


if __name__ == '__main__':
    main()
