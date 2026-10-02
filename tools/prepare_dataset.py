"""
One-click dataset preparation for DDSP-SVC, built on UVR5 models via python-audio-separator.

Pipeline (each stage loads its model once and processes every file):
    1. vocals   : separate vocals from accompaniment
    2. karaoke  : keep lead vocal, remove backing vocals / harmonies
    3. dereverb : remove reverb and echo
    4. denoise  : remove residual noise
    5. slice    : cut on silence, resample to mono, drop clips that are too short
    6. split    : write clips to <out>/train/audio and pick a few for <out>/val/audio

Every stage writes to its own folder under --work and skips files that are already done,
so an interrupted run can be resumed by running the same command again.

Example:
    python tools/prepare_dataset.py -i raw_songs -o data
    python tools/prepare_dataset.py -i dry_vocals -o data --steps dereverb,denoise,slice,split
"""
import argparse
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import torchaudio  # noqa: F401
except ImportError:
    # slicer.py imports torchaudio at module level, but the Slicer class does not use it.
    import types
    sys.modules['torchaudio'] = types.ModuleType('torchaudio')
from slicer import Slicer  # noqa: E402

AUDIO_EXTS = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.opus', '.aac', '.wma'}

UVR_STEPS = ['vocals', 'karaoke', 'dereverb', 'denoise']
ALL_STEPS = UVR_STEPS + ['slice', 'split']

DEFAULT_MODELS = {
    'vocals': 'mel_band_roformer_vocals_fv4_gabox.ckpt',
    'karaoke': 'mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt',
    'dereverb': 'UVR-DeEcho-DeReverb.pth',
    'denoise': 'denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt',
}

# Stem names (lower case) that hold the part we want to keep after each UVR stage.
KEEP_STEMS = {
    'vocals': {'vocals'},
    'karaoke': {'vocals'},
    'dereverb': {'no reverb', 'noreverb', 'no echo', 'dry'},
    'denoise': {'dry', 'no noise'},
}

STEM_RE = re.compile(r'_\(([^)]+)\)_')


def parse_args():
    p = argparse.ArgumentParser(description='Prepare DDSP-SVC training data with UVR5 models')
    p.add_argument('-i', '--input', required=True, help='folder with raw songs / vocals (searched recursively)')
    p.add_argument('-o', '--output', default='data', help='DDSP-SVC data folder (train/ and val/ are created inside)')
    p.add_argument('-w', '--work', default='preprocess_work', help='folder for intermediate results')
    p.add_argument('--steps', default=','.join(ALL_STEPS),
                   help=f'comma separated subset of: {",".join(ALL_STEPS)}')
    p.add_argument('--model-dir', default='pretrain/uvr', help='where UVR models are downloaded to')
    for step in UVR_STEPS:
        p.add_argument(f'--{step}-model', default=DEFAULT_MODELS[step], help=f'UVR model for the {step} stage')
    p.add_argument('--overlap', type=int, default=None,
                   help='Roformer/MDXC overlap; smaller is faster (try 2 on CPU), default uses the model setting')
    p.add_argument('--batch-size', type=int, default=None, help='Roformer/MDXC batch size (raise on large GPUs)')
    p.add_argument('--sr', type=int, default=44100, help='sample rate of the final clips')
    p.add_argument('--db-thresh', type=float, default=-40., help='silence threshold for slicing (dB)')
    p.add_argument('--min-len', type=float, default=3., help='drop clips shorter than this (s); must exceed duration in the yaml')
    p.add_argument('--max-len', type=float, default=15., help='split clips longer than this (s)')
    p.add_argument('--n-val', type=int, default=10, help='number of clips moved to the validation set')
    p.add_argument('--spk', default=None, help='speaker id folder (e.g. 1) for multi-speaker training')
    p.add_argument('--seed', type=int, default=1234)
    return p.parse_args()


def list_audio(folder):
    return sorted(f for f in Path(folder).rglob('*') if f.is_file() and f.suffix.lower() in AUDIO_EXTS)


def unique_names(files):
    names, used = {}, set()
    for f in files:
        base = re.sub(r'\s+', '_', f.stem)
        name, k = base, 2
        while name in used:
            name, k = f'{base}_{k}', k + 1
        used.add(name)
        names[f] = name
    return names


def run_uvr_stage(step, model, files, out_dir, args):
    from audio_separator.separator import Separator

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = out_dir / '_tmp'
    todo = [f for f in files if not (out_dir / f'{f.stem}.wav').exists()]
    print(f'[{step}] {model}: {len(files) - len(todo)} done, {len(todo)} to process')
    if not todo:
        return
    mdxc_params = {'segment_size': 256, 'override_model_segment_size': False,
                   'batch_size': args.batch_size, 'overlap': args.overlap, 'pitch_shift': 0}
    separator = Separator(output_dir=str(tmp_dir), model_file_dir=args.model_dir,
                          output_format='WAV', mdxc_params=mdxc_params, log_level=30)
    separator.load_model(model_filename=model)
    keep = KEEP_STEMS[step]
    for n, f in enumerate(todo, 1):
        t0 = time.time()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True)
        outputs = [tmp_dir / Path(o).name for o in separator.separate(str(f))]
        stems = {STEM_RE.search(o.name).group(1).lower(): o for o in outputs if STEM_RE.search(o.name)}
        picked = [o for s, o in stems.items() if s in keep]
        if len(picked) != 1:
            raise RuntimeError(f'[{step}] cannot tell which stem to keep from {list(stems)}; '
                               f'expected one of {sorted(keep)}')
        shutil.move(str(picked[0]), str(out_dir / f'{f.stem}.wav'))
        print(f'[{step}] {n}/{len(todo)} {f.name} ({time.time() - t0:.1f}s)')
    shutil.rmtree(tmp_dir, ignore_errors=True)


def slice_stage(files, out_dir, args):
    out_dir.mkdir(parents=True, exist_ok=True)
    min_len, max_len = int(args.min_len * args.sr), int(args.max_len * args.sr)
    slicer = Slicer(sr=args.sr, threshold=args.db_thresh, min_length=5000, min_interval=300,
                    hop_size=10, max_sil_kept=500)
    total, dropped = 0, 0
    for f in files:
        if any(out_dir.glob(f'{f.stem}_*.wav')):
            continue
        audio, _ = librosa.load(str(f), sr=args.sr, mono=True)
        k = 0
        for chunk in slicer.slice(audio).values():
            if chunk['slice']:
                continue
            begin, end = map(int, chunk['split_time'].split(','))
            seg = audio[begin:end]
            pieces = max(1, int(np.ceil(len(seg) / max_len)))
            for piece in np.array_split(seg, pieces):
                if len(piece) < min_len:
                    dropped += 1
                    continue
                sf.write(str(out_dir / f'{f.stem}_{k:04d}.wav'), piece, args.sr, subtype='PCM_16')
                k += 1
        total += k
        print(f'[slice] {f.name}: {k} clips')
    print(f'[slice] {total} new clips, {dropped} dropped as shorter than {args.min_len}s')


def split_stage(clips, args):
    spk = [args.spk] if args.spk else []
    train_dir = Path(args.output, 'train', 'audio', *spk)
    val_dir = Path(args.output, 'val', 'audio', *spk)
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    clips = sorted(clips)
    n_val = min(args.n_val, max(0, len(clips) - 1))
    val = set(rng.sample(clips, n_val))
    for c in clips:
        dst, other = (val_dir, train_dir) if c in val else (train_dir, val_dir)
        shutil.copy2(c, dst / c.name)
        (other / c.name).unlink(missing_ok=True)  # a re-run may move a clip between the two sets
    print(f'[split] {len(clips) - n_val} clips -> {train_dir}, {n_val} clips -> {val_dir}')


def main():
    args = parse_args()
    steps = [s.strip() for s in args.steps.split(',') if s.strip()]
    unknown = set(steps) - set(ALL_STEPS)
    if unknown:
        sys.exit(f'unknown steps: {sorted(unknown)}')
    work = Path(args.work)

    raw = list_audio(args.input)
    if not raw:
        sys.exit(f'no audio found in {args.input}')
    # Give every input a unique, space-free name so later stages can key on file stems.
    staged = work / '0_input'
    staged.mkdir(parents=True, exist_ok=True)
    for f, name in unique_names(raw).items():
        dst = staged / f'{name}{f.suffix.lower()}'
        if dst.exists():
            continue
        if os.stat(f).st_dev == os.stat(staged).st_dev:
            os.link(f, dst)  # hard link: no extra disk space for large song collections
        else:
            shutil.copy2(f, dst)
    files = list_audio(staged)
    print(f'{len(files)} input files')

    for idx, step in enumerate(UVR_STEPS, 1):
        if step in steps:
            out_dir = work / f'{idx}_{step}'
            run_uvr_stage(step, getattr(args, f'{step}_model'), files, out_dir, args)
            files = [out_dir / f'{f.stem}.wav' for f in files]

    clips_dir = work / '5_slices'
    if 'slice' in steps:
        slice_stage(files, clips_dir, args)
    if 'split' in steps:
        clips = list_audio(clips_dir) if 'slice' in steps or clips_dir.exists() else files
        split_stage(clips, args)


if __name__ == '__main__':
    main()
