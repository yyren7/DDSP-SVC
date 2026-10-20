"""
Learned quality scores for every line of eval_lines.py (needs a GPU; run in the evalq env from the repo
root, see /root/autodl-tmp/setup_evalq.sh):
    SingMOS-Pro   singing naturalness MOS 1-5, wav2vec2-large (ICASSP 2026; SingNet keeps > 3.0)
    DNSMOS P.835  speech quality: SIG, BAK (background noise), OVRL 1-5 (filters often keep OVRL >= 3.0)
    Audiobox Aesthetics  production quality PQ, complexity PC, enjoyment CE, usefulness CU, 1-10
    speaker       WavLM-base-plus-sv embedding; cosine to the speaker's centroid of clean lines
    pitch         RMVPE, the f0 extractor DDSP-SVC trains with (configs/*.yaml), against the Praat pitch of
                  eval_lines.py: where they disagree, training sees a wrong pitch for that line
Lines are cut from the dry vocals (3_karaoke) with 0.1 s around them and resampled to 16 kHz.

    python tools/autodl/score_lines.py [--limit n] <speaker dir>...

Writes <speaker>/eval/lines_learned.jsonl, one line per (song, k) of lines.jsonl; --limit n scores the
first n songs of each speaker and only prints them (a test).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

SR = 16000
PAD = 0.1
FPS = 100  # eval_lines.py frames and RMVPE: 10 ms
F0_MAX = 800  # f0_max of configs/reflow.yaml
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'


def load_models():
    models = {}
    t0 = time.time()
    models['singmos'] = torch.hub.load('South-Twilight/SingMOS:v1.1.2', 'singmos_pro', trust_repo=True).to(DEVICE).eval()
    from speechmos import dnsmos
    models['dnsmos'] = dnsmos
    from audiobox_aesthetics.infer import initialize_predictor
    models['aes'] = initialize_predictor()
    from transformers import AutoFeatureExtractor, WavLMForXVector
    models['spk_fe'] = AutoFeatureExtractor.from_pretrained('microsoft/wavlm-base-plus-sv')
    models['spk'] = WavLMForXVector.from_pretrained('microsoft/wavlm-base-plus-sv').to(DEVICE).eval()
    from encoder.rmvpe import RMVPE
    models['rmvpe'] = RMVPE(str(REPO / 'pretrain' / 'rmvpe' / 'model.pt'), hop_length=160)
    print(f'models loaded in {time.time() - t0:.0f} s on {DEVICE}', flush=True)
    return models


@torch.no_grad()
def score_clips(models, clips):
    """clips: list of 16 kHz float32 arrays -> list of score dicts (plus '_emb' and '_f0')."""
    out = [{} for _ in clips]
    # SingMOS-Pro, one clip at a time (lengths differ a lot; padding would change the scores)
    for d, x in zip(out, clips):
        w = torch.from_numpy(x).unsqueeze(0).to(DEVICE)
        d['singmos'] = float(models['singmos'](w, torch.tensor([w.shape[1]], device=DEVICE)).item())
    for d, x in zip(out, clips):
        r = models['dnsmos'].run(x, sr=SR)
        d['dns_ovrl'], d['dns_sig'], d['dns_bak'] = float(r['ovrl_mos']), float(r['sig_mos']), float(r['bak_mos'])
    res = models['aes'].forward([{'path': torch.from_numpy(x).unsqueeze(0), 'sample_rate': SR} for x in clips])
    for d, r in zip(out, res):
        for k in ('PQ', 'PC', 'CE', 'CU'):
            d[f'aes_{k.lower()}'] = float(r[k])
    for d, x in zip(out, clips):
        feats = models['spk_fe'](x, sampling_rate=SR, return_tensors='pt').to(DEVICE)
        emb = models['spk'](**feats).embeddings[0]
        d['_emb'] = torch.nn.functional.normalize(emb, dim=-1).cpu().numpy()
        d['_f0'] = models['rmvpe'].infer_from_audio(x, SR, device=DEVICE, thred=0.03)
    return out


def pitch_check(rmvpe, praat):
    """RMVPE against Praat over the same 10 ms frames of a line (0 = unvoiced in both)."""
    n = min(len(rmvpe), len(praat))
    r, p = rmvpe[:n].astype(np.float64), praat[:n].astype(np.float64)
    vr, vp = r > 0, p > 0
    both, either = vr & vp, vr | vp
    cents = 1200 * np.log2(r[both] / p[both])
    pair = vr[1:] & vr[:-1]  # consecutive frames both voiced by RMVPE
    jumps = np.abs(1200 * np.log2(r[1:][pair] / r[:-1][pair]))
    return {
        'rmvpe_voiced': float(vr.mean()) if n else 0.0,
        'f0_agree': float((np.abs(cents) < 50).mean()) if both.any() else 0.0,      # within half a semitone
        'f0_octave': float((np.abs(np.abs(cents) - 1200) < 100).mean()) if both.any() else 0.0,
        'f0_vdis': float((vr ^ vp).sum() / either.sum()) if either.any() else 0.0,  # voiced in only one
        'f0_jump': float((jumps > 200).mean()) if len(jumps) else 0.0,  # > 2 semitones in 10 ms
        'f0_high': float((r[vr] > F0_MAX).mean()) if vr.any() else 0.0,
    }


def score_speaker(models, spk, limit=None):
    lines = [json.loads(x) for x in (spk / 'eval' / 'lines.jsonl').read_text(encoding='utf-8').splitlines()]
    by_song = {}
    for m in lines:
        by_song.setdefault(m['song'], []).append(m)
    songs = sorted(by_song.items())[:limit]
    results, t0 = [], time.time()
    for i, (song, ms) in enumerate(songs, 1):
        x, sr = sf.read(str(spk / 'work' / '3_karaoke' / f'{song}.wav'), dtype='float32', always_2d=True)
        x = resample_poly(x.mean(1), SR // 100, sr // 100).astype(np.float32)
        praat = np.load(spk / 'eval' / 'frames' / f'{song}.npz')['f0_kar'].astype(np.float32)
        spans = [(max(0.0, m['start'] - PAD), m['end'] + PAD) for m in ms]
        clips = [x[int(s * SR):int(e * SR)] for s, e in spans]
        for m, (s, e), d in zip(ms, spans, score_clips(models, clips)):
            # the line itself, without the padding: RMVPE frame j of the clip is at s + j / FPS
            a, b = int(round((m['start'] - s) * FPS)), int(round((m['end'] - s) * FPS))
            d.update(pitch_check(d.pop('_f0')[a:b], praat[int(round(m['start'] * FPS)):int(round(m['end'] * FPS))]))
            d.update(song=song, k=m['k'])
            results.append(d)
        if i % 10 == 0 or limit:
            print(f'{spk.name}: {i}/{len(songs)} songs, {time.time() - t0:.0f} s', flush=True)
    # speaker centroid from the lines that look clean on both the signal and the learned side
    emb = np.stack([r['_emb'] for r in results])
    sig = {(m['song'], m['k']): m['score'] for m in lines}
    clean = [j for j, r in enumerate(results) if sig[(r['song'], r['k'])] >= 80 and r['singmos'] >= 3.0]
    centroid = emb[clean or list(range(len(results)))].mean(0)
    centroid /= np.linalg.norm(centroid)
    for r, c in zip(results, emb @ centroid):
        r.pop('_emb')
        r['spk_cos'] = float(c)
    rows = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in results]
    print(f'{spk.name}: {len(rows)} lines scored in {time.time() - t0:.0f} s, centroid from {len(clean)} lines',
          flush=True)
    return rows


def main():
    args = sys.argv[1:]
    limit = None
    if args and args[0] == '--limit':
        limit, args = int(args[1]), args[2:]
    models = load_models()
    for d in args:
        spk = Path(d)
        rows = score_speaker(models, spk, limit)
        if limit:
            for r in rows[:20]:
                print(json.dumps(r, ensure_ascii=False))
            continue
        path = spk / 'eval' / 'lines_learned.jsonl'
        tmp = path.with_suffix('.part')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)


if __name__ == '__main__':
    main()
