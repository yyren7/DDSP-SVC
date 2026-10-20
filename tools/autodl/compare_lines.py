"""
The lines of the calibration page through other orders and models, to find a chain that does not leave
the voice thin ("like through a walkie-talkie"). The listener heard that thinness come from the dereverb
step, which also took part of the lead voice where the vocal separation had left some of the
accompaniment's voices in (2026-10-20).

    python tools/autodl/compare_lines.py run <speaker dir>... [--model-dir pretrain/uvr] [--sel spk:n,n;spk:n]
    python tools/autodl/compare_lines.py score <speaker dir>...

run (uvr env, GPU): every calibration line with 5 s of the input song around it goes through each chain
of VERSIONS; the outputs, cut to the line (0.1 s before, 0.4 s after for the reverb tail), are in
<speaker>/compare/_lines/<version>/<n>.wav, n the line's number on the calibration page. The steps of
every chain are kept in compare/_lines/_work (_work_sel for --sel), so chains added later reuse them.
score (evalq env, GPU): per version and line the worst 3 s window of Audiobox CE / PQ and DNSMOS SIG /
OVRL (as in score_windows.py) and the reverb tail (level 0.15-0.35 s after the line against the line, dB,
where the next line starts later), into <speaker>/compare/_lines/scores.jsonl.

Candidates, the state of the art that can be downloaded as of 2026-10-20 (the MVSEP Team's own models
score higher on every step but run only on mvsep.com):
    vocals    BS-Roformer Leap Xe (unwa): Multisong vocals SDR 11.79, the best downloadable single model
    dereverb  DeReverb stereo BS-Roformer (anvuew): 8.80 SDR on MVSEP's 2026.07 vocal dereverb set, 2nd
              after the MVSEP Team's 9.81 and the best downloadable;
              DeEffect v1 beta BS-Roformer (gilliaan, 2026-09): the newest dry-vocal model (reverb, delay),
              not on that table yet
    karaoke   BS-Roformer Karaoke (anvuew): lead SDR 10.23 (13th on MVSEP's lead/back leaderboard);
              the average of it, Gabox's BS karaoke IS and becruily/frazer's BS karaoke: lead SDR 10.43,
              the best entry made only of downloadable models
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf

CONTEXT = 5.0          # seconds of the song before and after a line that the models see
BEFORE, AFTER = 0.1, 0.4
VOC = ('vocals', 'bs_leap_xe_voc.ckpt')
DEREVERB = ('dereverb', 'dereverb_bs_roformer_anvuew_sdr_22.5050.ckpt')
DEEFFECT = ('dereverb', 'gilliaan_bsroformer_deeffect_v1beta.ckpt')
KARAOKE = ('karaoke', 'karaoke_bs_roformer_anvuew.ckpt')
KARAOKE3 = ('karaoke', ('karaoke_bs_roformer_anvuew.ckpt', 'bs_roformer_karaoke_frazer_becruily.ckpt',
                        'bs_karaoke_gabox_IS.ckpt'))  # outputs averaged, as MVSEP's "(AVG)" ensembles
VERSIONS = {
    'A 现在（分离人声→去混响→去和声）': [VOC, DEREVERB, KARAOKE],
    'B 换顺序（分离人声→去和声→去混响）': [VOC, KARAOKE, DEREVERB],
    'C DeEffect（分离人声→DeEffect→去和声）': [VOC, DEEFFECT, KARAOKE],
    'D 换顺序加DeEffect（分离人声→去和声→DeEffect）': [VOC, KARAOKE, DEEFFECT],
    'E 三模型去和声（分离人声→去混响→三模型去和声）': [VOC, DEREVERB, KARAOKE3],
    'F 换顺序加三模型去和声（分离人声→三模型去和声→去混响）': [VOC, KARAOKE3, DEREVERB],
}
ORIGINAL = '0 原曲'


def calib_lines(spk):
    """[(n, line)] of the calibration page, with the start of the next line of the song."""
    lines = [json.loads(x) for x in (spk / 'eval' / 'lines.jsonl').read_text(encoding='utf-8').splitlines()]
    nxt = {}
    by_song = {}
    for m in lines:
        by_song.setdefault(m['song'], []).append(m)
    for ms in by_song.values():
        ms.sort(key=lambda m: m['start'])
        for a, b in zip(ms, ms[1:]):
            nxt[(a['song'], a['k'])] = b['start']
    sample = json.loads((spk / 'eval' / 'calib.json').read_text(encoding='utf-8'))
    return [(n, {**c, 'next': nxt.get((c['song'], c['k']))}) for n, c in enumerate(sample, 1)]


def cut(src, dst, start, end):
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-ss', f'{start:.3f}', '-t', f'{end - start:.3f}',
                    '-i', str(src), '-ac', '2', '-ar', '44100', str(dst)], check=True)


def run_step(step, model, files, work, made_by, uvr_args, run_uvr_stage):
    """One step of a chain: model is a checkpoint, or a tuple of them whose outputs are averaged.
    Returns (outputs, made_by); the stage folder is named after the chain so far, so chains that start
    alike share it."""
    if isinstance(model, str):
        made_by += f'{step}={model}\n'
        stage = work / hashlib.md5(made_by.encode()).hexdigest()[:10]
        run_uvr_stage(step, model, files, stage, uvr_args, made_by)
        return [stage / f'{f.stem}.wav' for f in files], made_by
    parts = [run_step(step, m, files, work, made_by, uvr_args, run_uvr_stage)[0] for m in model]
    made_by += f'{step}=avg({",".join(model)})\n'
    stage = work / hashlib.md5(made_by.encode()).hexdigest()[:10]
    stage.mkdir(parents=True, exist_ok=True)
    out = []
    for i, f in enumerate(files):
        dst = stage / f'{f.stem}.wav'
        if not dst.exists():
            xs = [sf.read(str(p[i]), dtype='float32', always_2d=True) for p in parts]
            n = min(len(x) for x, _ in xs)
            sf.write(str(dst), np.mean([x[:n] for x, _ in xs], axis=0), xs[0][1], subtype='FLOAT')
        out.append(dst)
    print(f'[{step}] average of {len(model)} models: {len(files)} files', flush=True)
    return out, made_by


def run(spks, model_dir, sel=None):
    """sel: {speaker: {n}} to run only those lines (the ones to listen to, ahead of the rest)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from prepare_dataset import run_uvr_stage
    uvr_args = SimpleNamespace(model_dir=model_dir, batch_size=None, overlap=None)
    for spk in spks:
        if sel is not None and spk.name not in sel:
            continue
        out = spk / 'compare' / '_lines'
        work = out / ('_work_sel' if sel is not None else '_work')
        (work / 'input').mkdir(parents=True, exist_ok=True)
        inputs, spans = [], {}
        for n, m in calib_lines(spk):
            if sel is not None and n not in sel[spk.name]:
                continue
            src = next(f for f in (spk / 'work' / '0_input').iterdir() if f.stem == m['song'])
            a = max(0.0, m['start'] - CONTEXT)
            dst = work / 'input' / f'{n}.wav'
            if not dst.exists():
                cut(src, dst, a, m['end'] + CONTEXT)
            inputs.append(dst)
            spans[n] = (m['start'] - a - BEFORE, m['end'] - a + AFTER)
        versions = {ORIGINAL: []} | VERSIONS
        for version, chain in versions.items():
            print(f'== {spk.name}: {version}', flush=True)
            files, made_by = inputs, ''
            for step, model in chain:
                files, made_by = run_step(step, model, files, work, made_by, uvr_args, run_uvr_stage)
            (out / version).mkdir(parents=True, exist_ok=True)
            for f in files:
                x, sr = sf.read(str(f), always_2d=True)
                a, b = spans[int(f.stem)]
                sf.write(str(out / version / f.name), x[max(0, int(a * sr)):int(b * sr)], sr, subtype='PCM_16')
        print(f'{spk.name}: {len(inputs)} lines x {len(VERSIONS)} versions in {out}', flush=True)


def score(spks):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    import torch
    from scipy.signal import resample_poly
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from score_lines import DNS_WORKERS, SR, dns_init, dns_score
    from score_windows import windows
    from audiobox_aesthetics.infer import initialize_predictor
    torch.set_num_threads(8)
    aes = initialize_predictor()
    pool = ProcessPoolExecutor(DNS_WORKERS, mp_context=multiprocessing.get_context('spawn'), initializer=dns_init)
    for spk in spks:
        out = spk / 'compare' / '_lines'
        rows = []
        for n, m in calib_lines(spk):
            dur = m['end'] - m['start']
            for version in [ORIGINAL] + list(VERSIONS):
                x, sr = sf.read(str(out / version / f'{n}.wav'), dtype='float32', always_2d=True)
                x = x.mean(1)
                line = x[int(BEFORE * sr):int((BEFORE + dur) * sr)]
                r = {'n': n, 'version': version}
                if m['next'] is None or m['next'] >= m['end'] + AFTER:
                    t = x[int((BEFORE + dur + 0.15) * sr):int((BEFORE + dur + 0.35) * sr)]
                    r['tail'] = float(10 * np.log10((np.mean(t ** 2) + 1e-12) / (np.mean(line ** 2) + 1e-12)))
                y = resample_poly(line, SR // 100, sr // 100).astype(np.float32)
                clips = [y[a:b] for a, b in windows(len(y))]
                dns = [pool.submit(dns_score, c) for c in clips]
                res = aes.forward([{'path': torch.from_numpy(c).unsqueeze(0), 'sample_rate': SR} for c in clips])
                r['w_aes_ce'] = min(float(q['CE']) for q in res)
                r['w_aes_pq'] = min(float(q['PQ']) for q in res)
                d = [f.result() for f in dns]
                r['w_dns_ovrl'] = min(v[0] for v in d)
                r['w_dns_sig'] = min(v[1] for v in d)
                rows.append({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
        (out / 'scores.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                                          encoding='utf-8')
        print(f'{spk.name}: {len(rows)} scores in {out / "scores.jsonl"}', flush=True)
    pool.shutdown()


def main():
    args = sys.argv[1:]
    opts = {}
    for name in ('--model-dir', '--sel'):  # --sel <speaker>:<n>,<n>;<speaker>:<n> as on the lcmp page
        if name in args:
            i = args.index(name)
            opts[name], args = args[i + 1], args[:i] + args[i + 2:]
    sel = None
    if '--sel' in opts:
        sel = {}
        for part in opts['--sel'].split(';'):
            spk, _, nums = part.partition(':')
            sel[spk] = {int(n) for n in nums.split(',') if n.strip().isdigit()}
    spks = [Path(d) for d in args[1:]]
    run(spks, opts.get('--model-dir', 'pretrain/uvr'), sel) if args[0] == 'run' else score(spks)


if __name__ == '__main__':
    main()
