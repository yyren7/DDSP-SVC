"""
One candidate of the bake-off (README.md) converts every item of set/manifest.json into hanamaru_hareru's voice,
without moving the key (as the covers' -k 0), into out/<system>/<name>.wav, matched in loudness to its input
(make_set.match_level); out/<system>/info.json keeps the settings and the time it took.

    /root/autodl-tmp/conda_envs/bk/bin/python tools/bakeoff/convert.py <model> [--system <name>] [--steps N]
        [--cfg X] [--ref <wav>] [--checkpoint <pt> --config <yml>] [--only line|song] [--items <names>] [--split]

<model>:
  seedvc     Seed-VC's 44.1 kHz singing model (Whisper-small content, F0 conditioned, BigVGAN); --checkpoint and
             --config take a fine-tuned one (its train.py) instead of the released one
  yingmusic  YingMusic-SVC-full: the same architecture after continued training and Flow-GRPO
  soulx      SoulX-Singer-SVC (24 kHz, Whisper-base content, F0 from its own RMVPE)
The zero-shot models take the timbre from --ref (default set/ref/ref.wav, her own lines). --system names the output
folder (default the model). Steps and guidance default to what each project recommends for singing.
The candidates load and save audio through torchaudio, whose 2.9 needs TorchCodec and FFmpeg's libraries; soundfile
stands in for them, and YingMusic's accompaniment remix (torchaudio.sox_effects, gone in 2.9) is never imported.
"""
import argparse
import atexit
import json
import os
import shutil
import sys
import tempfile
import time
import types
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_set import match_level  # noqa: E402
from slicer import Slicer  # noqa: E402  (DDSP-SVC's, on the path through make_set's abtest)

B = Path('/root/autodl-tmp/bakeoff')
R = B / 'repos'
DEFAULTS = {'seedvc': (50, 0.7), 'yingmusic': (100, 0.7), 'soulx': (32, 3.0)}  # (diffusion steps, guidance)


def sf_load(path, *a, **k):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return torch.from_numpy(x.T.copy()), sr


def sf_save(path, wav, sr, *a, **k):
    sf.write(str(path), wav.detach().cpu().float().numpy().T, sr)


torchaudio.load, torchaudio.save = sf_load, sf_save


def enter(repo):
    """Run from the candidate's folder, its modules first. abtest.py (through make_set) put the DDSP-SVC root on the
    path, whose preprocess.py would win over SoulX-Singer's preprocess/ (a folder without __init__.py loses to a
    module anywhere on the path)."""
    os.chdir(R / repo)
    root = Path(__file__).resolve().parents[2]
    sys.path[:] = [str(R / repo)] + [p for p in sys.path if p and Path(p).resolve() != root]


def scratch(prefix):
    """A folder for the candidate's own output files, removed when the run ends."""
    tmp = tempfile.mkdtemp(prefix=prefix, dir=B)
    atexit.register(shutil.rmtree, tmp, True)
    return tmp


def hf_file(repo, name):
    """A file downloaded by setup.sh into ./checkpoints (the cache of Seed-VC's hf_utils.py)."""
    found = sorted(Path('checkpoints').glob(f'models--{repo.replace("/", "--")}/snapshots/*/{name}'))
    if not found:
        sys.exit(f'{name} of {repo} is not in {Path.cwd()}/checkpoints: run tools/bakeoff/setup.sh')
    return str(found[-1])


def seed_args(args, steps, cfg, tmp, checkpoint, config):
    return argparse.Namespace(source=None, target=args.ref, output=tmp, diffusion_steps=steps, length_adjust=1.0,
                              inference_cfg_rate=cfg, f0_condition=True, auto_f0_adjust=False, semi_tone_shift=0,
                              checkpoint=checkpoint, config=config, fp16=True, expname='bk', cuda='0', accompany=None)


def seedvc(args, steps, cfg):
    """(load time, convert(input) -> (mono wave, sample rate)) of Seed-VC: its inference.main per input, the models
    loaded once."""
    enter('seed-vc')
    import inference as sv
    tmp = scratch('seedvc_')
    a = seed_args(args, steps, cfg, tmp, args.checkpoint, args.config)
    if not a.checkpoint:  # the released singing model, as inference.py picks it with --f0-condition
        a.checkpoint = hf_file('Plachta/Seed-VC', 'DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth')
        a.config = hf_file('Plachta/Seed-VC', 'config_dit_mel_seed_uvit_whisper_base_f0_44k.yml')
    bundle = sv.load_models(a)
    sv.load_models = lambda _: bundle

    def convert(path):
        for f in Path(tmp).glob('*.wav'):
            f.unlink()
        a.source = path
        sv.main(a)
        (out,) = Path(tmp).glob('*.wav')
        return sf_mono(out)
    return convert


def yingmusic(args, steps, cfg):
    enter('YingMusic-SVC')
    remix = types.ModuleType('Remix')
    remix.auger = types.SimpleNamespace(echo_then_reverb_save=None)
    sys.modules['Remix'], sys.modules['Remix.auger'] = remix, remix.auger
    import my_inference as ym
    tmp = scratch('yingmusic_')
    a = seed_args(args, steps, cfg, tmp, args.checkpoint or hf_file('GiantAILab/YingMusic-SVC', 'YingMusic-SVC-full.pt'),
                  args.config or './configs/YingMusic-SVC.yml')
    device = torch.device('cuda')
    bundle = ym.load_models_api(a, device=device)

    def convert(path):
        a.source = path
        out = Path(ym.run_inference(a, bundle, device=device))
        try:
            return sf_mono(out)
        finally:
            out.unlink()
    return convert


def soulx(args, steps, cfg):
    enter('SoulX-Singer')
    from cli.inference_svc import build_model
    from preprocess.tools.f0_extraction import F0Extractor
    from soulxsinger.utils.audio_utils import load_wav
    from soulxsinger.utils.file_utils import load_config
    config = load_config('soulxsinger/config/soulxsinger.yaml')
    sr = config.audio.sample_rate
    model = build_model(args.checkpoint or 'pretrained_models/SoulX-Singer/model-svc.pt', config, 'cuda', use_fp16=True)
    fx = F0Extractor('pretrained_models/SoulX-Singer-Preprocess/rmvpe/rmvpe.pt', device='cuda', verbose=False)

    def f0(path):
        return torch.from_numpy(fx.process(str(path))).float().unsqueeze(0).cuda()
    pt_wav, pt_f0 = load_wav(args.ref, sr).cuda(), f0(args.ref)

    def convert(path):
        with torch.no_grad():
            y, _ = model.infer(pt_wav=pt_wav, gt_wav=load_wav(path, sr).cuda(), pt_f0=pt_f0, gt_f0=f0(path),
                               auto_shift=False, pitch_shift=0, n_steps=steps, cfg=cfg, use_fp16=True)
        return y.squeeze().float().cpu().numpy(), sr
    return convert


def sf_mono(path):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return x.mean(1), sr


def by_phrase(convert):
    """convert of a whole input a phrase at a time. Seed-VC and YingMusic see 30 s at once, the reference
    included, so a song goes through in windows of about 13 s (with the 16.6 s reference), each generated alone
    and joined with 0.19 s of crossfade wherever the window ends: the user heard YingMusic 断. The input is cut
    at its pauses instead (DDSP-SVC's slicer as main_reflow.py uses it, but at pauses of 150 ms: nearly every
    phrase of the 5 songs then fits in one window), each phrase converted alone and put back at its time."""
    tmp = scratch('phrase_')

    def whole(path):
        x, sr = sf_mono(path)
        pieces, out_sr = [], None
        for v in Slicer(sr=sr, threshold=-40., min_length=5000, min_interval=150).slice(x).values():
            a, b = (int(t) for t in v['split_time'].split(','))
            if v['slice'] or b <= a:  # a pause
                continue
            sf.write(f'{tmp}/phrase.wav', x[a:b], sr, subtype='FLOAT')
            y, out_sr = convert(f'{tmp}/phrase.wav')
            pieces.append((a / sr, y))
        out = np.zeros(round(len(x) / sr * out_sr), np.float32)
        for t, y in pieces:
            i = round(t * out_sr)
            y = y[:len(out) - i].copy()
            ramp = np.linspace(0, 1, min(round(0.01 * out_sr), len(y) // 2))  # no click at the cuts
            y[:len(ramp)] *= ramp
            y[len(y) - len(ramp):] *= ramp[::-1]
            out[i:i + len(y)] += y
        return out, out_sr
    return whole


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('model', choices=sorted(DEFAULTS))
    p.add_argument('--system')
    p.add_argument('--steps', type=int)
    p.add_argument('--cfg', type=float)
    p.add_argument('--ref', default=str(B / 'set' / 'ref' / 'ref.wav'))
    p.add_argument('--checkpoint')
    p.add_argument('--config')
    p.add_argument('--only', choices=('line', 'song'))
    p.add_argument('--items', help='comma-separated names of the manifest, e.g. song__aini: only these')
    p.add_argument('--split', action='store_true', help='a phrase at a time, cut at the pauses (by_phrase)')
    args = p.parse_args()
    steps, cfg = args.steps or DEFAULTS[args.model][0], args.cfg or DEFAULTS[args.model][1]
    args.ref = str(Path(args.ref).resolve())
    system = args.system or args.model
    man = json.loads((B / 'set' / 'manifest.json').read_text(encoding='utf-8'))
    items = [it for it in man['items'] if (not args.only or it['kind'] == args.only)
             and (not args.items or it['name'] in args.items.split(','))]
    out = B / 'out' / system
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    convert = globals()[args.model](args, steps, cfg)
    if args.split:
        convert = by_phrase(convert)
    load_s, done, audio_s = time.time() - t0, [], 0.0
    t1 = time.time()
    for it in items:
        t = time.time()
        y, sr = convert(it['input'])
        sf.write(str(out / f'{it["name"]}.wav'), match_level(y, sr, it['input']), sr, subtype='PCM_16')
        audio_s += len(y) / sr
        done.append({'name': it['name'], 'seconds': round(time.time() - t, 1)})
        print(f'{system}: {it["name"]} {len(y) / sr:.1f} s of audio in {time.time() - t:.1f} s', flush=True)
    info = {'model': args.model, 'system': system, 'steps': steps, 'cfg': cfg, 'ref': args.ref,
            'checkpoint': args.checkpoint, 'config': args.config, 'key': 0, 'split': args.split,
            'made': time.strftime('%F %T'),
            'load_s': round(load_s, 1), 'convert_s': round(time.time() - t1, 1),
            'rtf': round((time.time() - t1) / max(audio_s, 1e-9), 3), 'items': done}
    (out / 'info.json').write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{system}: {len(done)} items, {audio_s / 60:.1f} min of audio in {time.time() - t1:.0f} s '
          f'(RTF {info["rtf"]}), models loaded in {load_s:.0f} s', flush=True)


if __name__ == '__main__':
    main()
