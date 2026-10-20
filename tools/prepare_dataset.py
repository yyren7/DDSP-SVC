"""
One-click dataset preparation for DDSP-SVC, built on UVR5 models via python-audio-separator.

Pipeline (each stage loads its model once and processes every file):
    1. vocals   : separate vocals from accompaniment
    2. karaoke  : keep lead vocal, remove backing vocals / harmonies
    3. dereverb : remove reverb and echo
    4. slice    : cut on silence, resample to mono, drop clips that are too short
    5. split    : write clips to <out>/train/audio and pick a few for <out>/val/audio

Every stage writes to its own folder under --work and skips files that are already done,
so an interrupted run can be resumed by running the same command again. A stage records the
models that made its files (_models.txt); when they change, the stage starts over.

Example:
    python tools/prepare_dataset.py -i raw_songs -o data
    python tools/prepare_dataset.py -i dry_vocals -o data --steps dereverb,slice,split
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

# Backing vocals come off before the reverb since 2026-10-20 (until then, as in the AI Hub RVC dataset
# guide, the other way round): where the vocal separation leaves some of the accompaniment's voices in,
# the dereverb model also took part of the lead, which turned thin "like through a walkie-talkie". On the
# 119 calibration lines (compare_lines.py) this order scored higher on Audiobox CE / PQ and DNSMOS SIG,
# left 3 dB less reverb tail, and won the blind listening. No denoise step since 2026-10-20 either:
# after the other steps, aufr33's aggressive denoise model changed its input by only -47 to -52 dB.
UVR_STEPS = ['vocals', 'karaoke', 'dereverb']
ALL_STEPS = UVR_STEPS + ['slice', 'split']
SLICES_DIR = f'{len(UVR_STEPS) + 1}_slices'

# The best models that can be downloaded, as of 2026-10-20 (MVSEP's own models score higher on every
# step but only run on mvsep.com):
#   vocals   BS-Roformer Leap Xe by unwa: vocals SDR 11.79, the best single downloadable model on the
#            MVSEP Multisong leaderboard
#   karaoke  the average of three BS-Roformer karaoke models (anvuew; becruily & frazer; Gabox "IS"):
#            lead SDR 10.43 on MVSEP's lead/back leaderboard, the best entry made of downloadable models
#            (anvuew's alone: 10.23); "a+b+c" averages the models' outputs
#   dereverb DeReverb stereo BS-Roformer by anvuew: SDR 8.80 on MVSEP's 2026.07 vocal dereverb set, the
#            best downloadable, after the MVSEP Team's 9.81
DEFAULT_MODELS = {
    'vocals': 'bs_leap_xe_voc.ckpt',
    'karaoke': 'karaoke_bs_roformer_anvuew.ckpt+bs_roformer_karaoke_frazer_becruily.ckpt+bs_karaoke_gabox_IS.ckpt',
    'dereverb': 'dereverb_bs_roformer_anvuew_sdr_22.5050.ckpt',
}

# Models audio-separator does not list, published on Hugging Face as a checkpoint and a yaml for
# ZFTurbo's Music-Source-Separation-Training, whose Roformer configs audio-separator reads too.
# filename -> (repo, checkpoint, yaml); fetch_uvr_models.py downloads them, the yaml as <stem>.yaml.
EXTRA_MODELS = {
    'bs_leap_xe_voc.ckpt': ('pcunwa/BS-Roformer-Leap', 'Xe/bs_leap_xe_voc.ckpt', 'Xe/leap_xe_config_voc.yaml'),
    'dereverb_bs_roformer_anvuew_sdr_22.5050.ckpt':
        ('anvuew/dereverb_bs_roformer', 'dereverb_bs_roformer_anvuew_sdr_22.5050.ckpt', 'config.yaml'),
    'karaoke_bs_roformer_anvuew.ckpt':
        ('anvuew/karaoke_bs_roformer', 'karaoke_bs_roformer_anvuew.ckpt', 'karaoke_bs_roformer_anvuew.yaml'),
    # candidates of 2026-10-20 (compare_lines.py): the newest dry-vocal model, and the two other karaoke
    # models of the best downloadable ensemble on MVSEP's lead/back leaderboard (with anvuew's, lead SDR 10.43)
    'gilliaan_bsroformer_deeffect_v1beta.ckpt':
        ('gilliaan/Stem-Separation-Models', 'DeEffect/BandSplitRoformer/gilliaan_bsroformer_deeffect_v1beta.ckpt',
         'DeEffect/BandSplitRoformer/gilliaan_bsroformer_deeffect_v1beta.yaml'),
    'bs_roformer_karaoke_frazer_becruily.ckpt':
        ('becruily/bs-roformer-karaoke', 'bs_roformer_karaoke_frazer_becruily.ckpt', 'config_karaoke_frazer_becruily.yaml'),
    'bs_karaoke_gabox_IS.ckpt':
        ('GaboxR67/MelBandRoformers', 'bsroformers/bs_karaoke_gabox_IS.ckpt', 'bsroformers/karaoke_bs_roformer.yaml'),
}


def extra_yaml(model):
    return Path(model).stem + '.yaml'


def register_extra_models(separator_cls):
    """Add EXTRA_MODELS to audio-separator's list of models, so load_model() takes them (from --model-dir)."""
    listed = separator_cls.list_supported_model_files
    if getattr(listed, 'with_extra_models', False):
        return

    def with_extra(self):
        models = listed(self)
        for model, (repo, _, _) in EXTRA_MODELS.items():
            models.setdefault('MDXC', {})[f'{model} ({repo})'] = {
                'filename': model, 'scores': {}, 'stems': [], 'target_stem': None,
                'download_files': [model, extra_yaml(model)]}
        return models
    with_extra.with_extra_models = True
    separator_cls.list_supported_model_files = with_extra

# Stem names (lower case) that hold the part we want to keep after each UVR stage (denoise: for the
# model chains compare_uvr.py still compares).
KEEP_STEMS = {
    'vocals': {'vocals'},
    'karaoke': {'vocals'},
    'dereverb': {'no reverb', 'noreverb', 'no echo', 'dry', 'vocals'},  # vocals: gilliaan's DeEffect
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
        p.add_argument(f'--{step}-model', default=DEFAULT_MODELS[step],
                       help=f'UVR model for the {step} stage; a+b+c averages several')
    p.add_argument('--overlap', type=int, default=None,
                   help='Roformer/MDXC overlap; smaller is faster (try 2 on CPU), default uses the model setting')
    p.add_argument('--batch-size', type=int, default=None, help='Roformer/MDXC batch size (raise on large GPUs)')
    # Mixed precision and compiled RoFormer blocks: a 60 s excerpt through anvuew's karaoke model on a 4090D
    # took 14.8 s in fp32, 8.5 s with autocast, 4.4 s with both, and the output stays 72 dB above its
    # difference from the fp32 output (2026-10-21)
    p.add_argument('--no-autocast', dest='autocast', action='store_false', help='run the models in fp32')
    p.add_argument('--no-compile', dest='torch_compile', action='store_false', help='do not torch.compile them')
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


def fresh_stage(out_dir, made_by):
    """Create out_dir for files made by `made_by` (models and settings); empty it when another set made them."""
    stamp = out_dir / '_models.txt'
    if out_dir.exists() and (not stamp.exists() or stamp.read_text(encoding='utf-8') != made_by):
        print(f'{out_dir.name}: made by other models or settings, starting it over')
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp.write_text(made_by, encoding='utf-8')


def run_uvr_stage(step, model, files, out_dir, args, made_by):
    """model: a checkpoint name, or several joined by '+', whose outputs are averaged (an ensemble, as the
    "(AVG)" entries of MVSEP's leaderboards). All of them stay loaded and each file goes through every
    one before the next file, so no full set of per-model outputs piles up on the disk."""
    from audio_separator.separator import Separator
    register_extra_models(Separator)

    fresh_stage(out_dir, made_by)
    tmp_dir = out_dir / '_tmp'
    todo = [f for f in files if not (out_dir / f'{f.stem}.wav').exists()]
    print(f'[{step}] {model}: {len(files) - len(todo)} done, {len(todo)} to process')
    if not todo:
        return
    mdxc_params = {'segment_size': 256, 'override_model_segment_size': False,
                   'batch_size': args.batch_size, 'overlap': args.overlap, 'pitch_shift': 0}
    models = model.split('+')
    separators = []
    for k, name in enumerate(models):
        sep = Separator(output_dir=str(tmp_dir / str(k)), model_file_dir=args.model_dir,
                        output_format='WAV', mdxc_params=mdxc_params, log_level=30,
                        use_autocast=getattr(args, 'autocast', True),
                        use_torch_compile=getattr(args, 'torch_compile', True))
        sep.load_model(model_filename=name)
        separators.append(sep)
    keep = KEEP_STEMS[step]
    for n, f in enumerate(todo, 1):
        t0 = time.time()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        picked = []
        for k, sep in enumerate(separators):
            (tmp_dir / str(k)).mkdir(parents=True)
            outputs = [tmp_dir / str(k) / Path(o).name for o in sep.separate(str(f))]
            stems = {STEM_RE.search(o.name).group(1).lower(): o for o in outputs if STEM_RE.search(o.name)}
            kept = [o for s, o in stems.items() if s in keep]
            if len(kept) != 1:
                raise RuntimeError(f'[{step}] {models[k]}: cannot tell which stem to keep from {list(stems)}; '
                                   f'expected one of {sorted(keep)}')
            picked.append(kept[0])
        if len(picked) == 1:
            shutil.move(str(picked[0]), str(out_dir / f'{f.stem}.wav'))
        else:
            xs = [sf.read(str(p), dtype='float32', always_2d=True) for p in picked]
            length = min(len(x) for x, _ in xs)
            mean = np.mean([x[:length] for x, _ in xs], axis=0)
            part = out_dir / f'{f.stem}.part.wav'
            sf.write(str(part), mean, xs[0][1], subtype='PCM_16')
            part.replace(out_dir / f'{f.stem}.wav')
        print(f'[{step}] {n}/{len(todo)} {f.name} ({time.time() - t0:.1f}s)')
    shutil.rmtree(tmp_dir, ignore_errors=True)


def slice_stage(files, out_dir, args, made_by):
    fresh_stage(out_dir, f'{made_by}\nslice sr={args.sr} db={args.db_thresh} len={args.min_len}-{args.max_len}')
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
    # clips of songs taken out of the input since an earlier run
    names = {c.name for c in clips}
    stale = [f for d in (train_dir, val_dir) for f in list_audio(d) if f.name not in names]
    for f in stale:
        f.unlink()
    print(f'[split] {len(clips) - n_val} clips -> {train_dir}, {n_val} clips -> {val_dir}'
          + (f', removed {len(stale)} clips of songs no longer in the input' if stale else ''))


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
    files = []
    for f, name in unique_names(raw).items():
        dst = staged / f'{name}{f.suffix.lower()}'
        if not dst.exists():
            if os.stat(f).st_dev == os.stat(staged).st_dev:
                os.link(f, dst)  # hard link: no extra disk space for large song collections
            else:
                shutil.copy2(f, dst)
        files.append(dst)
    # Inputs staged by an earlier run but no longer in the input folder must not be processed again.
    stale = [f for f in list_audio(staged) if f not in set(files)]
    for f in stale:
        f.unlink()
    if stale:
        print(f'removed {len(stale)} staged inputs that are no longer in {args.input}')
    files = sorted(files)
    print(f'{len(files)} input files')

    # Stage folders of an older stage order (e.g. 2_karaoke before 2_dereverb) hold outdated results.
    layout = {f'{idx}_{step}' for idx, step in enumerate(UVR_STEPS, 1)} | {'0_input', SLICES_DIR}
    for d in work.iterdir():
        if d.is_dir() and re.fullmatch(r'\d_[a-z]+', d.name) and d.name not in layout:
            print(f'removing {d.name}, a stage folder of an older stage order')
            shutil.rmtree(d)

    made_by = ''  # the models that made `files`, one "step=model" line per stage
    for idx, step in enumerate(UVR_STEPS, 1):
        if step in steps:
            out_dir = work / f'{idx}_{step}'
            model = getattr(args, f'{step}_model')
            made_by += f'{step}={model}\n'
            run_uvr_stage(step, model, files, out_dir, args, made_by)
            files = [out_dir / f'{f.stem}.wav' for f in files]

    clips_dir = work / SLICES_DIR
    if 'slice' in steps:
        slice_stage(files, clips_dir, args, made_by)
    if 'split' in steps:
        if 'slice' in steps or clips_dir.exists():
            stems = {f.stem for f in files}  # only clips cut from this run's inputs
            clips = [c for c in list_audio(clips_dir) if c.stem.rsplit('_', 1)[0] in stems]
        else:
            clips = files
        split_stage(clips, args)


if __name__ == '__main__':
    main()
