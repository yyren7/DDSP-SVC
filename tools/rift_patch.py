"""
DDSP-SVC for the timbre, RIFT-SVC where DDSP-SVC breaks a word (the user's call on 2026-10-26, after the bake-off in
tools/bakeoff/README.md: DDSP-SVC sounds more like her, RIFT-SVC rarely cracks a word). The RIFT-SVC conversion of
a song's dry lead is one more candidate of diction.py (README.md, 咬字修补), which puts the phrases the user picks
back into the DDSP-SVC vocal: both convert the same dry vocal without moving it in time.

    /root/autodl-tmp/conda_envs/rift/bin/python tools/rift_patch.py cand <covers/cand/song>... [--key K] [--step N]
    /root/autodl-tmp/conda_envs/rift/bin/python tools/rift_patch.py convert <dry.wav> <out.wav> [--match <wav>]

cand:    each folder's dry.wav through her RIFT-SVC into <n>_rift<step/1000>k.wav (n the next free number, as
         diction.py cand names its candidates), at the loudness of the folder's first candidate, the vocal in use
         (diction.py splices without touching the level). Skipped when that step is there already.
convert: one dry vocal, at the loudness of --match (default: of the input).
The checkpoint is the 25000-step one by default, the best of the last on its validation set. infer.py cuts its input
at pauses with an absolute -30 dB and leaves out what it takes for silence, which dropped whole phrases of a quiet
recording; so the input is first brought to -18 LUFS (RIFT-SVC's training loudness) and cut at -40 dB.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

R = Path('/root/autodl-tmp/rift/RIFT-SVC')
CKPT = R / 'ckpts' / 'hanamaru_768-12' / 'model-step={}.ckpt'
SPEAKER, STEP = 'hanamaru_hareru', 25000


def mono(path):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return x.mean(1), sr


def lufs(x, sr):
    return pyln.Meter(sr).integrated_loudness(x)


def write(path, y, sr):
    sf.write(str(path), y / max(1.0, np.abs(y).max() / 0.99), sr, subtype='FLOAT')


def convert(src, dst, key=0, step=STEP, ckpt=None, match=None):
    """src through RIFT-SVC into dst, at the loudness of match (default src)."""
    x, sr = mono(src)
    target = lufs(*mono(match)) if match else lufs(x, sr)
    with tempfile.TemporaryDirectory() as tmp:
        write(f'{tmp}/in.wav', pyln.normalize.loudness(x, lufs(x, sr), -18.0), sr)
        subprocess.run([sys.executable, 'infer.py', '--model', str(ckpt or str(CKPT).format(step)),
                        '--input', f'{tmp}/in.wav', '--output', f'{tmp}/out.wav', '--speaker', SPEAKER,
                        '--key-shift', str(key), '--slicer-threshold', '-40'],
                       cwd=R, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        y, ysr = mono(f'{tmp}/out.wav')
    write(dst, pyln.normalize.loudness(y, lufs(y, ysr), target), ysr)
    return dst


def cand(folder, key=0, step=STEP):
    folder = Path(folder)
    have = sorted(f for f in folder.glob('*.wav') if f.name != 'dry.wav')
    tag = f'rift{step / 1000:g}k'
    if any(f.stem.endswith('_' + tag) for f in have):
        print(f'{folder}: {tag} is there already')
        return
    n = 1 + max((int(m.group(1)) for f in have if (m := re.match(r'(\d+)_', f.stem))), default=-1)
    dst = convert(folder / 'dry.wav', folder / f'{n}_{tag}.wav', key, step, match=have[0] if have else None)
    print(f'{dst} (loudness of {have[0].name if have else "dry.wav"})')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('cand')
    c.add_argument('folders', nargs='+')
    v = sub.add_parser('convert')
    v.add_argument('src')
    v.add_argument('dst')
    v.add_argument('--match')
    for q in (c, v):
        q.add_argument('--key', type=int, default=0)
        q.add_argument('--step', type=int, default=STEP)
    args = p.parse_args()
    if args.cmd == 'cand':
        for f in args.folders:
            cand(f, args.key, args.step)
    else:
        convert(args.src, args.dst, args.key, args.step, match=args.match)


if __name__ == '__main__':
    main()
