"""
DDSP-SVC for the timbre, RIFT-SVC where DDSP-SVC breaks a word (the user's call on 2026-10-26, after the bake-off in
tools/bakeoff/README.md: DDSP-SVC sounds more like her, RIFT-SVC rarely cracks a word). The RIFT-SVC conversion of
a song's dry lead is one more candidate of diction.py (README.md, 咬字修补), which puts the phrases the user picks
back into the DDSP-SVC vocal: both convert the same dry vocal without moving it in time.

    /root/autodl-tmp/conda_envs/rift/bin/python tools/rift_patch.py cand <covers/cand/song>... [--speaker S] [--key K] [--step N...]
    /root/autodl-tmp/conda_envs/rift/bin/python tools/rift_patch.py convert <dry.wav> <out.wav> [--speaker S] [--match <wav>]

cand:    each folder's dry.wav through the speaker's RIFT-SVC into <n>_rift<step/1000>k.wav for every step (n the next
         free number, as diction.py cand names its candidates), at the loudness of the folder's first candidate, the
         vocal in use (diction.py splices without touching the level). A step that is there already is skipped.
convert: one dry vocal, at the loudness of --match (default: of the input).
--speaker picks the fine-tuned model, ckpts/<first part of the name>_768-12/ (bakeoff/finetune_rift.sh): hanamaru_hareru
(the default; 1000 to 30000 steps), pheebie and sakura_shunka (5000 to 30000, every 5000; 2026-10-27).
The checkpoint is the 25000-step one by default, the best of hanamaru_hareru's last ones on its validation set.
infer.py cuts its input at pauses with an absolute -30 dB and leaves out what it takes for silence, which dropped whole
phrases of a quiet recording; so the input is first brought to -18 LUFS (RIFT-SVC's training loudness), cut at -40 dB.
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
SPEAKER, STEP = 'hanamaru_hareru', 25000


def checkpoint(speaker, step):
    return R / 'ckpts' / f'{speaker.split("_")[0]}_768-12' / f'model-step={step}.ckpt'


def mono(path):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return x.mean(1), sr


def lufs(x, sr):
    return pyln.Meter(sr).integrated_loudness(x)


def write(path, y, sr):
    sf.write(str(path), y / max(1.0, np.abs(y).max() / 0.99), sr, subtype='FLOAT')


def convert(src, dst, key=0, step=STEP, ckpt=None, match=None, speaker=SPEAKER):
    """src through RIFT-SVC into dst, at the loudness of match (default src)."""
    x, sr = mono(src)
    target = lufs(*mono(match)) if match else lufs(x, sr)
    with tempfile.TemporaryDirectory() as tmp:
        write(f'{tmp}/in.wav', pyln.normalize.loudness(x, lufs(x, sr), -18.0), sr)
        subprocess.run([sys.executable, 'infer.py', '--model', str(ckpt or checkpoint(speaker, step)),
                        '--input', f'{tmp}/in.wav', '--output', f'{tmp}/out.wav', '--speaker', speaker,
                        '--key-shift', str(key), '--slicer-threshold', '-40'],
                       cwd=R, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        y, ysr = mono(f'{tmp}/out.wav')
    write(dst, pyln.normalize.loudness(y, lufs(y, ysr), target), ysr)
    return dst


def cand(folder, key=0, step=STEP, speaker=SPEAKER):
    folder = Path(folder)
    have = sorted(f for f in folder.glob('*.wav') if f.name != 'dry.wav')
    tag = f'rift{step / 1000:g}k'
    if any(f.stem.endswith('_' + tag) for f in have):
        print(f'{folder}: {tag} is there already')
        return
    n = 1 + max((int(m.group(1)) for f in have if (m := re.match(r'(\d+)_', f.stem))), default=-1)
    dst = convert(folder / 'dry.wav', folder / f'{n}_{tag}.wav', key, step, match=have[0] if have else None,
                  speaker=speaker)
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
        q.add_argument('--speaker', default=SPEAKER)
    c.add_argument('--step', type=int, nargs='+', default=[STEP])
    v.add_argument('--step', type=int, default=STEP)
    args = p.parse_args()
    if args.cmd == 'cand':
        for f in args.folders:
            for step in args.step:
                cand(f, args.key, step, args.speaker)
    else:
        convert(args.src, args.dst, args.key, args.step, match=args.match, speaker=args.speaker)


if __name__ == '__main__':
    main()
