"""
Machine scores of the bake-off (README.md), and the blind A/B of one candidate against the baseline.

    HF_HUB_OFFLINE=1 /root/autodl-tmp/conda_envs/evalq/bin/python tools/bakeoff/score.py lines|songs|ab <system>...

lines: the 36 clips through abtest.py's score (SingMOS-Pro, Audiobox Aesthetics, DNSMOS, the WavLM cosine to her
       own validation clips, the pitch error against the input) for every system in out/ that has all of them
       and the inputs, in the experiment folder bakeoff/lines_ab/ (scores.jsonl there, means printed by system).
songs: the whole songs on the same 8 s windows where the input sings (as cover_scripts/clean_pilot_score.py),
       into bakeoff/scores_songs.jsonl, means printed by song and system.
ab <system>: hanamaru_hareru's A/B experiment bk_<system> for the review page (「A/B 盲听」, ?x=bk_<system>): the
       baseline ddsp40k against <system> on the 36 clips, hard links of the files, the machine scores of lines.
blind <folder> [<system>...]: the whole songs under neutral names in her 转换结果 (infer_out/<folder>/), the key
       in bakeoff/<folder>.json.
Only systems given on the command line, or all in out/ when none are.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'autodl'))
import abtest  # noqa: E402

B = Path('/root/autodl-tmp/bakeoff')
SPK = Path('/root/autodl-tmp/speakers/hanamaru_hareru')
BASE = 'ddsp40k'
WIN = 8  # seconds
BLIND = '甲乙丙丁戊己庚辛'  # neutral names of the systems in the blind song folders
KEYS = ('singmos', 'aes_pq', 'aes_ce', 'dns_ovrl', 'spk_cos', 'f0_rmse_cents')


def manifest():
    return json.loads((B / 'set' / 'manifest.json').read_text(encoding='utf-8'))


def systems(names, items):
    have = [d.name for d in sorted((B / 'out').iterdir()) if d.is_dir()
            and all((d / f'{it["name"]}.wav').exists() for it in items)]
    return [s for s in names if s in have] if names else [BASE] + [s for s in have if s != BASE]


def lines(names):
    items = [it for it in manifest()['items'] if it['kind'] == 'line']
    sys_ = systems(names, items)
    root = B / 'lines_ab'
    if root.exists():
        shutil.rmtree(root)
    for d in [abtest.SOURCE] + sys_:
        (root / d).mkdir(parents=True)
        for it in items:
            src = Path(it['input']) if d == abtest.SOURCE else B / 'out' / d / f'{it["name"]}.wav'
            (root / d / f'{it["name"]}.wav').symlink_to(src.resolve())
    (root / 'manifest.json').write_text(json.dumps(
        {'datasets': sys_, 'step': 'bakeoff', 'spk_id': 1,
         'items': [{'name': it['name'], 'src_spk': it['src_spk'], 'clip': it['name'].split('__', 1)[1],
                    'dur': it['dur']} for it in items]}, ensure_ascii=False, indent=1), encoding='utf-8')
    abtest.score(SPK, root)


def load16(path, sr16):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return resample_poly(x.mean(1), sr16 // 100, sr // 100).astype(np.float32)


def songs(names):
    import score_lines as sl
    items = [it for it in manifest()['items'] if it['kind'] == 'song']
    sys_ = systems(names, items)
    models = sl.load_models()

    def score(clips, k=4):  # a few at a time: the GPU may be shared
        return [r for i in range(0, len(clips), k) for r in sl.score_clips(models, clips[i:i + k])]

    hers = [it for it in manifest()['items'] if it['kind'] == 'line' and it['src_spk'] == SPK.name]
    centroid = np.mean([r['_emb'] for r in score([load16(it['input'], sl.SR) for it in hers])], 0)
    centroid /= np.linalg.norm(centroid)
    rows = []
    for it in items:
        audio = {'_source': load16(it['input'], sl.SR)}
        audio.update({s: load16(B / 'out' / s / f'{it["name"]}.wav', sl.SR) for s in sys_})
        n = min(len(x) for x in audio.values())
        win, hop = WIN * sl.SR, sl.SR // 100
        x = audio['_source'][:n // hop * hop]
        db = 20 * np.log10(np.sqrt(np.mean(x.reshape(-1, hop) ** 2, 1)) + 1e-9)
        active = db > np.percentile(db, 99) - 35
        starts = [i for i in range(0, n - win, win) if active[i // hop:(i + win) // hop].mean() > 0.6]
        res = {s: score([a[i:i + win] for i in starts]) for s, a in audio.items()}
        for s, rs in res.items():
            for i, r in zip(starts, rs):
                row = {'song': it['src_spk'], 'system': s, 'start': round(i / sl.SR, 2),
                       **{k: v for k, v in r.items() if not k.startswith('_')}, 'spk_cos': float(r['_emb'] @ centroid)}
                if s != '_source':
                    a = res['_source'][starts.index(i)]['_f0'].astype(np.float64)
                    b = r['_f0'].astype(np.float64)
                    m = min(len(a), len(b))
                    both = (a[:m] > 0) & (b[:m] > 0)
                    if both.any():
                        row['f0_rmse_cents'] = float(np.sqrt(np.mean((1200 * np.log2(b[:m][both] / a[:m][both])) ** 2)))
                rows.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()})
        print(f'{it["src_spk"]}: {len(starts)} windows of {WIN} s', flush=True)
    models['dns_pool'].shutdown()
    (B / 'scores_songs.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                                          encoding='utf-8')
    for song in [it['src_spk'] for it in items] + [None]:
        print(f'== {song or "all songs"}')
        for s in ['_source'] + sys_:
            sel = [r for r in rows if r['system'] == s and (song is None or r['song'] == song)]
            print(f'{s:12s} ' + ', '.join(f'{k} {np.mean([r[k] for r in sel if r.get(k) is not None]):.3f}'
                                          for k in KEYS if any(r.get(k) is not None for r in sel)), flush=True)


def ab(names):
    src = B / 'lines_ab'
    man = json.loads((src / 'manifest.json').read_text(encoding='utf-8'))
    scores = [json.loads(x) for x in (src / 'scores.jsonl').read_text(encoding='utf-8').splitlines() if x]
    for s in names:
        if s not in man['datasets']:
            sys.exit(f'{s}: not scored in lines_ab/ (run score.py lines first)')
        root = SPK / f'abtest_bk_{s}'
        if root.exists():
            shutil.rmtree(root)
        for d in (abtest.SOURCE, BASE, s):
            (root / d).mkdir(parents=True)
            for it in man['items']:
                os.link((src / d / f'{it["name"]}.wav').resolve(), root / d / f'{it["name"]}.wav')
        (root / 'manifest.json').write_text(json.dumps({**man, 'datasets': [BASE, s]}, ensure_ascii=False, indent=1),
                                            encoding='utf-8')
        (root / 'scores.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in scores
                                                   if r['dataset'] in (abtest.SOURCE, BASE, s)), encoding='utf-8')
        print(f'{root}: {BASE} against {s}, {len(man["items"])} clips; review page ab?x=bk_{s}')


def blind(args):
    """The whole songs for listening on the review page, hanamaru_hareru's 转换结果 infer_out/<folder>/<song>/: the
    input as 0_输入.flac, every system under a neutral name in an order drawn per song; which is which only in
    bakeoff/<folder>.json, outside what the page serves."""
    import random
    folder, names = args[0], args[1:]
    items = [it for it in manifest()['items'] if it['kind'] == 'song']
    sys_ = systems(names, items)
    root = SPK / 'infer_out' / folder
    if root.exists():
        shutil.rmtree(root)
    key = {}
    for it in items:
        song = it['src_spk']
        (root / song).mkdir(parents=True)
        order = list(sys_)
        random.Random(f'{folder}|{song}').shuffle(order)
        x, sr = sf.read(it['input'], dtype='float32', always_2d=True)
        sf.write(str(root / song / '0_输入.flac'), x.mean(1), sr, subtype='PCM_24')
        key[song] = {}
        for label, s in zip(BLIND, order):
            y, sr = sf.read(str(B / 'out' / s / f'{it["name"]}.wav'), dtype='float32')
            sf.write(str(root / song / f'{label}.flac'), y, sr, subtype='PCM_24')
            key[song][label] = s
    (B / f'{folder}.json').write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{root}: {len(items)} songs, {len(sys_)} systems each; the key in {B / folder}.json')



def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('lines', 'songs', 'ab', 'blind'):
        sys.exit(__doc__)
    {'lines': lines, 'songs': songs, 'ab': ab, 'blind': blind}[sys.argv[1]](sys.argv[2:])


if __name__ == '__main__':
    main()
