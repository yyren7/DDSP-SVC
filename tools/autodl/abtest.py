"""
A/B listening of the models one speaker was trained into from different training sets (build_clips.py
datasets, exp_<dataset>/): every model converts the same clips, the validation clips of every speaker
(their lines of the held-out songs, never trained on). Her own clips test the resynthesis (how close to her
real voice), the other speakers' clips the conversion (the real use). The review page plays them blind (ab).

    python tools/autodl/abtest.py convert [--name <x>] <speaker dir> <set>...   (ddsp env, GPU, from the repo root)
    python tools/autodl/abtest.py score [--name <x>] <speaker dir>              (evalq env, GPU)

A set is a dataset, or <dataset>@<step> for one checkpoint of it (e.g. all@10000 all@40000 compares two
points of one training). --name keeps the experiment apart in abtest_<x>/ (review page ab?x=<x>), so that
an earlier one and the listener's choices on it stay as they are.

convert: the checkpoints at the latest step every dataset reached (equal steps), the settings of
main_reflow.py's defaults (RMVPE, key 0, the config's sampler), each result matched in loudness to its input
(louder sounds better in a blind test). Writes <speaker>/abtest/<dataset>/<source speaker>__<clip>.wav, the
inputs as abtest/_source/<source speaker>__<clip>.wav and abtest/manifest.json.
score: score_lines.py's learned scores of every result and input (SingMOS-Pro, Audiobox Aesthetics,
DNSMOS), the WavLM speaker cosine to her real voice (her validation clips, without the clip itself) and the
pitch error of the result against its input (RMVPE, cents), into abtest/scores.jsonl.
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

SOURCE = '_source'
AB_LEN = 8.0  # seconds: long enough to judge a voice, short enough to compare three in a row


def checkpoints(spk, sets):
    """(step, {set: checkpoint}). A set is a dataset (its model in exp_<dataset>/) or <dataset>@<step> for that
    step's checkpoint; the plain datasets take the latest step every one of them saved. step is that step, or
    the steps of the sets joined by '/' when they differ."""
    found, picked = {}, {}
    for s in sets:
        d, _, at = s.partition('@')
        found[s] = {}
        for f in (spk / f'exp_{d}').glob('model_*.pt'):
            m = re.fullmatch(r'model_(\d+)\.pt', f.name)
            if m and int(m.group(1)) > 0:
                found[s][int(m.group(1))] = f
        if at:
            if int(at) not in found[s]:
                sys.exit(f'{spk.name}: no model_{at}.pt in exp_{d}')
            picked[s] = found[s][int(at)]
    plain = [s for s in sets if s not in picked]
    if plain:
        common = set.intersection(*(set(found[s]) for s in plain))
        if not common:
            sys.exit(f'{spk.name}: no checkpoint of the same step in ' + ', '.join(f'exp_{s}' for s in plain))
        picked.update({s: found[s][max(common)] for s in plain})
    steps = [int(picked[s].stem.split('_')[1]) for s in sets]
    return (steps[0] if len(set(steps)) == 1 else ' / '.join(map(str, steps))), {s: picked[s] for s in sets}


def sources(spk, dataset):
    """[(source speaker, clip)]: the validation clips of every speaker with this dataset, hers first; each
    speaker's clips nearest AB_LEN seconds first, since the A/B page asks for the first few only."""
    spks = [spk] + sorted(d for d in spk.parent.iterdir()
                          if d != spk and (d / f'data_{dataset}' / 'val' / 'audio').is_dir())
    out = []
    for s in spks:
        clips = sorted((s / f'data_{dataset}' / 'val' / 'audio').glob('*.wav'))
        out += [(s.name, f) for f in sorted(clips, key=lambda f: abs(sf.info(str(f)).duration - AB_LEN))]
    return out


def active_rms(x, sr):
    """RMS over the 50 ms frames within 30 dB of the loudest, i.e. of the singing, not of the pauses."""
    n = int(0.05 * sr)
    frames = x[:len(x) // n * n].reshape(-1, n)
    p = (frames.astype(np.float64) ** 2).mean(1)
    if not len(p) or p.max() <= 0:
        return 0.0
    return float(np.sqrt(p[p >= p.max() * 1e-3].mean()))


def convert(spk, datasets, root):
    import librosa
    import torch
    import yaml
    from ddsp.core import upsample
    from ddsp.vocoder import F0_Extractor, Units_Encoder, Volume_Extractor
    from main_reflow import cross_fade, split
    from reflow.vocoder import DotDict, load_model_vocoder

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    step, ckpts = checkpoints(spk, datasets)
    # the inputs are prepared once for all models, so the models must agree on how inputs are read
    cfgs = {d: DotDict(yaml.safe_load((c.parent / 'config.yaml').read_text(encoding='utf-8'))) for d, c in ckpts.items()}
    args = cfgs[datasets[0]]
    for d, c in cfgs.items():
        for k in ('sampling_rate', 'block_size', 'volume_smooth_size', 'encoder', 'encoder_ckpt'):
            if c.data[k] != args.data[k]:
                sys.exit(f'{spk.name}: exp_{d} reads its input with data.{k} {c.data[k]}, '
                         f'exp_{datasets[0]} with {args.data[k]}')
    first = datasets[0].partition('@')[0]
    items = sources(spk, first)  # the validation clips are the same in every dataset (build_clips.py)
    if not items:
        sys.exit(f'{spk.name}: no validation clips in data_{first}/val/audio')
    if root.exists():
        shutil.rmtree(root)  # results of other checkpoints
    (root / SOURCE).mkdir(parents=True)
    t0 = time.time()
    with torch.no_grad():
        units_encoder = Units_Encoder(args.data.encoder, args.data.encoder_ckpt, args.data.encoder_sample_rate,
                                      args.data.encoder_hop_size, device=device,
                                      cnhubertsoft_gate=args.data.cnhubertsoft_gate or 10)
        prepared = []
        for src_spk, f in items:
            # main_reflow.py's defaults: RMVPE from 50 to 1100 Hz, volume threshold -60 dB
            audio, sr = librosa.load(str(f), sr=None)
            hop = args.data.block_size * sr / args.data.sampling_rate
            win = args.data.volume_smooth_size * sr / args.data.sampling_rate
            f0 = F0_Extractor('rmvpe', sr, hop, 50, 1100).extract(audio, uv_interp=True, device=device)
            volume = Volume_Extractor(hop, win).extract(audio)
            mask = torch.from_numpy((volume > 10 ** (-60 / 20)).astype('float')).float().to(device)
            segs = [(start, units_encoder.encode(torch.from_numpy(x).float().unsqueeze(0).to(device), sr, hop))
                    for start, x in split(audio, sr, hop)]
            name = f'{src_spk}__{f.stem}'
            sf.write(str(root / SOURCE / f'{name}.wav'), audio, sr, subtype='PCM_16')
            prepared.append({'name': name, 'src_spk': src_spk, 'clip': f.stem, 'dur': round(len(audio) / sr, 2),
                             'rms': active_rms(audio, sr), 'segs': segs,
                             'f0': torch.from_numpy(f0).float().to(device).unsqueeze(-1).unsqueeze(0),
                             'volume': torch.from_numpy(volume).float().to(device).unsqueeze(-1).unsqueeze(0),
                             'mask': upsample(mask.unsqueeze(-1).unsqueeze(0), args.data.block_size).squeeze(-1)})
        del units_encoder
        print(f'{spk.name}: {len(prepared)} clips prepared in {time.time() - t0:.0f} s', flush=True)
        for d, ckpt in ckpts.items():
            model, vocoder, args = load_model_vocoder(str(ckpt), device=device)
            block, out_sr = args.data.block_size, args.data.sampling_rate
            t_start = float(args.model.t_start) if args.model.t_start is not None else 0.0
            spk_id = torch.LongTensor(np.array([[1]])).to(device)
            shift = torch.zeros(1, 1, device=device)
            (root / d).mkdir()
            t1 = time.time()
            for p in prepared:
                result, cur = np.zeros(0), 0
                for start, units in p['segs']:  # main_reflow.py, key 0
                    n = units.size(1)
                    f0 = p['f0'][:, start:start + n, :]
                    mel = model(units, f0, p['volume'][:, start:start + n, :], spk_id=spk_id, spk_mix_dict=None,
                                aug_shift=shift, vocoder=vocoder, infer_step=args.infer.infer_step,
                                method=args.infer.method, t_start=t_start, use_tqdm=False)
                    out = vocoder.infer(mel, f0) * p['mask'][:, start * block:(start + n) * block]
                    out = out.squeeze().cpu().numpy()
                    silent = round(start * block) - cur
                    if silent >= 0:
                        result = np.concatenate([result, np.zeros(silent), out])
                    else:
                        result = cross_fade(result, out, cur + silent)
                    cur += silent + len(out)
                rms = active_rms(result, out_sr)
                if rms > 0 and p['rms'] > 0:
                    result = result * (p['rms'] / rms)
                peak = np.abs(result).max(initial=0)
                if peak > 0.99:
                    result *= 0.99 / peak
                sf.write(str(root / d / f'{p["name"]}.wav'), result.astype(np.float32), out_sr, subtype='PCM_16')
            print(f'{spk.name} {d}: {len(prepared)} clips converted with {ckpt.name} in {time.time() - t1:.0f} s',
                  flush=True)
            del model, vocoder
            torch.cuda.empty_cache()
    manifest = {'datasets': datasets, 'step': step, 'checkpoints': {d: str(c) for d, c in ckpts.items()},
                'made': time.strftime('%F %T'),
                'items': [{k: p[k] for k in ('name', 'src_spk', 'clip', 'dur')} for p in prepared]}
    (root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')


def score(spk, root):
    import score_lines
    from scipy.signal import resample_poly

    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    models = score_lines.load_models()

    def load16(f):
        x, sr = sf.read(str(f), dtype='float32', always_2d=True)
        return resample_poly(x.mean(1), score_lines.SR // 100, sr // 100).astype(np.float32)

    items = {it['name']: it for it in manifest['items']}
    rows = {}
    for d in [SOURCE] + manifest['datasets']:
        for name, r in zip(items, score_lines.score_clips(models, [load16(root / d / f'{n}.wav') for n in items])):
            rows[(d, name)] = r
    models['dns_pool'].shutdown()
    # her real voice: the embeddings of her own validation clips, without the clip that is being compared
    ref = {n: rows[(SOURCE, n)]['_emb'] for n, it in items.items() if it['src_spk'] == spk.name}
    out = []
    for (d, name), r in rows.items():
        it = items[name]
        others = [e for n, e in ref.items() if n != name]
        centroid = np.mean(others, 0) if others else np.zeros_like(r['_emb'])
        centroid /= max(np.linalg.norm(centroid), 1e-9)
        f0_in, f0_out = rows[(SOURCE, name)]['_f0'], r['_f0']
        n = min(len(f0_in), len(f0_out))
        a, b = f0_in[:n].astype(np.float64), f0_out[:n].astype(np.float64)
        both, either = (a > 0) & (b > 0), (a > 0) | (b > 0)
        cents = 1200 * np.log2(b[both] / a[both]) if both.any() else np.zeros(0)
        row = {'dataset': d, 'name': name, 'src_spk': it['src_spk'], 'self': it['src_spk'] == spk.name,
               **{k: v for k, v in r.items() if not k.startswith('_')}, 'spk_cos': float(r['_emb'] @ centroid)}
        if d != SOURCE:
            row['f0_rmse_cents'] = float(np.sqrt(np.mean(cents ** 2))) if len(cents) else None
            row['f0_vdis'] = float(((a > 0) ^ (b > 0)).sum() / either.sum()) if either.any() else 0.0
        out.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})
    (root / 'scores.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out), encoding='utf-8')
    keys = ('singmos', 'aes_pq', 'aes_ce', 'dns_ovrl', 'spk_cos', 'f0_rmse_cents')
    for d in [SOURCE] + manifest['datasets']:
        for own_voice in (True, False):
            sel = [r for r in out if r['dataset'] == d and r['self'] == own_voice]
            if sel:
                means = ', '.join(f'{k} {np.mean([r[k] for r in sel if r.get(k) is not None]):.3f}'
                                  for k in keys if any(r.get(k) is not None for r in sel))
                print(f'{spk.name} {d:8s} {"her clips" if own_voice else "others":9s} ({len(sel)}): {means}', flush=True)


def main():
    cmd, args, name = sys.argv[1], sys.argv[2:], None
    if args[:1] == ['--name']:
        name, args = args[1], args[2:]
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            sys.exit(f'--name {name}: letters, digits, _ and - only')
    spk = Path(args[0])
    root = spk / (f'abtest_{name}' if name else 'abtest')
    if cmd == 'convert':
        convert(spk, args[1:] or ['all', 'clean'], root)
    elif cmd == 'score':
        score(spk, root)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
