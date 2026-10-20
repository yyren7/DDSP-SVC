"""
The worst part of each line: Audiobox Aesthetics and DNSMOS on 3 s windows, 1.5 s apart, of every line of
eval_lines.py. A problem the listener hears often lasts a second or two of a longer line ("at 4-5 s the
voice turns thin", "at 10 s the accompaniment comes in"), and the whole-line scores of score_lines.py
average it away.

    python tools/autodl/score_windows.py [--stage voc|kar] [--calib] <speaker dir>...   # evalq env, GPU

Writes <speaker>/eval/lines_windows.jsonl: per (song, k) of lines.jsonl the lowest window score of each of
aes_ce, aes_pq, aes_cu, dns_sig, dns_bak, dns_ovrl, as w_<name>. Lines shorter than a window are one window.
--stage scores the same lines after an earlier step (lines_windows_<stage>.jsonl), to find the step where
a line turns thin ("like through a walkie-talkie"); --calib only the lines of the calibration page.
"""
import json
import multiprocessing
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_lines import DNS_WORKERS, SR, dns_init, dns_score  # noqa: E402
from stages import DIRS, DRY_KEY  # noqa: E402

WIN, HOP = 3.0, 1.5
STAGE_DIRS = {k: v for k, v in DIRS.items() if k != 'mix'}


def windows(n):
    """[(a, b)] sample ranges of the windows of a line n samples long."""
    w, h = int(WIN * SR), int(HOP * SR)
    if n <= w:
        return [(0, n)]
    starts = list(range(0, n - w + 1, h))
    if starts[-1] + w < n:
        starts.append(n - w)
    return [(s, s + w) for s in starts]


@torch.no_grad()
def main():
    torch.set_num_threads(8)
    from audiobox_aesthetics.infer import initialize_predictor
    aes = initialize_predictor()
    pool = ProcessPoolExecutor(DNS_WORKERS, mp_context=multiprocessing.get_context('spawn'), initializer=dns_init)
    args, stage, calib = sys.argv[1:], DRY_KEY, False
    while args and args[0].startswith('--'):
        if args[0] == '--stage':
            stage, args = args[1], args[2:]
        else:
            calib, args = args[0] == '--calib', args[1:]
    for d in args:
        spk, t0 = Path(d), time.time()
        lines = [json.loads(x) for x in (spk / 'eval' / 'lines.jsonl').read_text(encoding='utf-8').splitlines()]
        if calib:
            sample = json.loads((spk / 'eval' / 'calib.json').read_text(encoding='utf-8'))
            picked = {(c['song'], c['k']) for c in sample}
            lines = [m for m in lines if (m['song'], m['k']) in picked]
        by_song = {}
        for m in lines:
            by_song.setdefault(m['song'], []).append(m)
        rows = []
        for i, (song, ms) in enumerate(sorted(by_song.items()), 1):
            x, sr = sf.read(str(spk / 'work' / STAGE_DIRS[stage] / f'{song}.wav'), dtype='float32', always_2d=True)
            x = resample_poly(x.mean(1), SR // 100, sr // 100).astype(np.float32)
            clips, owner = [], []
            for j, m in enumerate(ms):
                line = x[int(m['start'] * SR):int(m['end'] * SR)]
                for a, b in windows(len(line)):
                    clips.append(line[a:b])
                    owner.append(j)
            dns = [pool.submit(dns_score, c) for c in clips]
            res = aes.forward([{'path': torch.from_numpy(c).unsqueeze(0), 'sample_rate': SR} for c in clips])
            scores = [{} for _ in ms]
            for j, r, f in zip(owner, res, dns):
                ovrl, sig, bak = f.result()
                w = {'aes_ce': r['CE'], 'aes_pq': r['PQ'], 'aes_cu': r['CU'], 'dns_sig': sig, 'dns_bak': bak,
                     'dns_ovrl': ovrl}
                for k, v in w.items():
                    scores[j][k] = min(scores[j].get(k, np.inf), float(v))
            for m, s in zip(ms, scores):
                rows.append({'song': song, 'k': m['k'], **{f'w_{k}': round(v, 4) for k, v in s.items()}})
            if i % 25 == 0:
                print(f'{spk.name}: {i}/{len(by_song)} songs, {time.time() - t0:.0f} s', flush=True)
        name = 'lines_windows' + ('' if stage == DRY_KEY else f'_{stage}') + ('_calib' if calib else '')
        path = spk / 'eval' / f'{name}.jsonl'
        tmp = path.with_suffix('.part')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        print(f'{spk.name}: {len(rows)} lines in {time.time() - t0:.0f} s', flush=True)
    pool.shutdown()


if __name__ == '__main__':
    main()
