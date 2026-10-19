"""
Run a few excerpts of a speaker's songs through several UVR model chains, for comparing them by ear
on the review page (compare/<version>/<excerpt>.wav under the speaker folder).

    python tools/autodl/compare_uvr.py --speaker-dir /root/autodl-tmp/speakers/pheebie --model-dir pretrain/uvr

Excerpts: 40 s from the middle of 3 covers (recordings that are not live streams) and 3 stream songs,
spread over the song list. Versions that share their first stages share that work.
"""
import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prepare_dataset import run_uvr_stage  # noqa: E402

OLD = [('vocals', 'mel_band_roformer_vocals_fv4_gabox.ckpt'),
       ('karaoke', 'mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt'),
       ('dereverb', 'UVR-DeEcho-DeReverb.pth'),
       ('denoise', 'denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt')]
NEW = [('vocals', 'bs_leap_xe_voc.ckpt'),
       ('dereverb', 'dereverb_bs_roformer_anvuew_sdr_22.5050.ckpt'),
       ('karaoke', 'karaoke_bs_roformer_anvuew.ckpt'),
       ('denoise', 'denoise_mel_band_roformer_aufr33_aggr_sdr_27.9768.ckpt')]
VERSIONS = {
    'A 原来的四步（FV4→去和声→去混响→去噪）': OLD,
    'B 新的四步（Leap Xe→去混响→去和声→去噪）': NEW,
    'C 新的三步（B 去掉去噪）': NEW[:3],
    'D 两步（直接在原曲上去和声→去混响）': [NEW[2], NEW[1]],
}
ORIGINAL = '0 原曲'


def pick_songs(songs_dir, per_kind=3):
    """3 covers (the only song cut from their recording) and 3 stream songs (from recordings with several),
    spread over each list, from _songs.tsv (file, source, ...)."""
    rows = [line.split('\t') for line in (songs_dir / '_songs.tsv').read_text(encoding='utf-8').splitlines()[1:]]
    rows = [r for r in rows if (songs_dir / r[0]).exists()]
    per_source = {}
    for r in rows:
        per_source[r[1]] = per_source.get(r[1], 0) + 1
    kinds = ([r for r in rows if per_source[r[1]] == 1], [r for r in rows if per_source[r[1]] > 1])
    picked = []
    for kind in kinds:
        step = max(1, len(kind) // per_kind)
        picked += [songs_dir / r[0] for r in kind[step // 2::step][:per_kind]]
    return picked


def excerpt(src, dst, seconds):
    length = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0',
                                   str(src)], capture_output=True, text=True, check=True).stdout)
    start = max(0.0, length / 2 - seconds / 2)
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-ss', f'{start:.1f}', '-t', str(seconds),
                    '-i', str(src), '-ac', '2', '-ar', '44100', str(dst)], check=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--speaker-dir', required=True)
    p.add_argument('--model-dir', default='pretrain/uvr')
    p.add_argument('--seconds', type=int, default=40)
    args = p.parse_args()
    spk = Path(args.speaker_dir)
    out = spk / 'compare'
    shutil.rmtree(out, ignore_errors=True)
    (out / ORIGINAL).mkdir(parents=True)
    inputs = []
    for k, song in enumerate(pick_songs(spk / 'songs'), 1):
        dst = out / ORIGINAL / f'{k} {song.stem}.wav'
        excerpt(song, dst, args.seconds)
        inputs.append(dst)
        print(f'excerpt {dst.name}', flush=True)

    uvr_args = SimpleNamespace(model_dir=args.model_dir, batch_size=None, overlap=None)
    for version, chain in VERSIONS.items():
        print(f'== {version}', flush=True)
        files, made_by = inputs, ''
        for step, model in chain:
            made_by += f'{step}={model}\n'
            # the work folder is named after the chain so far, so versions starting alike share it
            stage = out / '_work' / hashlib.md5(made_by.encode()).hexdigest()[:10]
            run_uvr_stage(step, model, files, stage, uvr_args, made_by)
            files = [stage / f'{f.stem}.wav' for f in files]
        (out / version).mkdir()
        for f in files:
            shutil.copy2(f, out / version / f.name)
    shutil.rmtree(out / '_work')
    print(f'{len(inputs)} excerpts x {len(VERSIONS)} versions in {out}', flush=True)


if __name__ == '__main__':
    main()
