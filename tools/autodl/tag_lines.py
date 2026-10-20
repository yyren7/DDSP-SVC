"""
Per line of eval_lines.py: is it sung or spoken, and does an instrument sound in it. Calibration showed
the signal scores missing both (2026-10-20: lines of talk between the singing, accompaniment left in).

    python tools/autodl/tag_lines.py <speaker dir>...   # uvr env (panns_inference), GPU

Writes <speaker>/eval/lines_tags.jsonl, one line per (song, k) of lines.jsonl:
    p_sing, p_speech, p_music, p_instr  PANNs (Cnn14_DecisionLevelMax, AudioSet) clip probabilities of the
                                        dry vocals of the line: singing, speech, music, and the most likely
                                        instrument (any instrument there is accompaniment left in)
    long_voiced   share of the line in voiced runs of 0.3 s or more (Praat pitch of eval_lines.py frames)
    pitch_steady  share of voiced frames whose pitch moves less than 15 cents in 10 ms
Sung notes are held; speech glides through short syllables, so both are lower for talk.
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
sys.path.insert(0, str(REPO / 'tools'))
import split_songs  # noqa: E402  (PANNs loading, class names)

SR = split_songs.SR  # 32 kHz
FPS = 100
INSTR = ['Musical instrument', 'Plucked string instrument', 'Guitar', 'Electric guitar', 'Bass guitar',
         'Acoustic guitar', 'Keyboard (musical)', 'Piano', 'Electric piano', 'Organ', 'Synthesizer', 'Percussion',
         'Drum kit', 'Drum machine', 'Drum', 'Snare drum', 'Bass drum', 'Cymbal', 'Hi-hat', 'Brass instrument',
         'Bowed string instrument', 'String section', 'Violin, fiddle', 'Wind instrument, woodwind instrument',
         'Flute']


def pitch_shape(f0):
    v = f0 > 0
    edges = np.flatnonzero(np.diff(np.r_[0, v.astype(np.int8), 0]))
    runs = edges[1::2] - edges[::2]
    pair = v[1:] & v[:-1]
    cents = np.abs(1200 * np.log2(f0[1:][pair] / f0[:-1][pair])) if pair.any() else np.array([])
    return {'long_voiced': float(runs[runs >= 0.3 * FPS].sum() / max(1, len(f0))),
            'pitch_steady': float((cents < 15).mean()) if len(cents) else 0.0}


@torch.no_grad()
def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model, labels = split_songs.load_model(REPO / 'pretrain' / 'panns', device)
    idx = {name: labels.index(name) for name in split_songs.SING + split_songs.SPEECH + split_songs.MUSIC + INSTR}
    for d in sys.argv[1:]:
        spk, t0 = Path(d), time.time()
        lines = [json.loads(x) for x in (spk / 'eval' / 'lines.jsonl').read_text(encoding='utf-8').splitlines()]
        by_song = {}
        for m in lines:
            by_song.setdefault(m['song'], []).append(m)
        rows = []
        for i, (song, ms) in enumerate(sorted(by_song.items()), 1):
            x, sr = sf.read(str(spk / 'work' / '3_karaoke' / f'{song}.wav'), dtype='float32', always_2d=True)
            x = resample_poly(x.mean(1), SR // 100, sr // 100).astype(np.float32)
            f0 = np.load(spk / 'eval' / 'frames' / f'{song}.npz')['f0_kar'].astype(np.float32)
            for m in ms:
                clip = x[int(m['start'] * SR):int(m['end'] * SR)]
                clip = np.pad(clip, (0, max(0, SR - len(clip))))  # at least 1 s for the CNN's pooling
                p = model(torch.from_numpy(clip)[None].to(device))['clipwise_output'][0].cpu().numpy()
                r = {'song': song, 'k': m['k'],
                     'p_sing': float(max(p[idx[c]] for c in split_songs.SING)),
                     'p_speech': float(max(p[idx[c]] for c in split_songs.SPEECH)),
                     'p_music': float(p[idx['Music']]),
                     'p_instr': float(max(p[idx[c]] for c in INSTR))}
                r.update(pitch_shape(f0[int(round(m['start'] * FPS)):int(round(m['end'] * FPS))]))
                rows.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
            if i % 50 == 0:
                print(f'{spk.name}: {i}/{len(by_song)} songs, {time.time() - t0:.0f} s', flush=True)
        path = spk / 'eval' / 'lines_tags.jsonl'
        tmp = path.with_suffix('.part')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        print(f'{spk.name}: {len(rows)} lines tagged in {time.time() - t0:.0f} s', flush=True)


if __name__ == '__main__':
    main()
