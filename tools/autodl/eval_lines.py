"""
Line-level check of the dry vocals. The final dry vocals (stages.DRY, 3_dereverb since 2026-10-20) are
split into lines at the pauses between them, and every line is measured against the earlier stages, so
that a song with a few bad lines keeps its good ones. Training clips are later made from runs of good lines.

    python tools/autodl/eval_lines.py frames [--shard k/n] <speaker dir>...   # slow: ~0.1 x real time; k = 0 .. n-1
    python tools/autodl/eval_lines.py lines <speaker dir>...                   # seconds, from the frames

frames: per song, frame features (10 ms) of the mix and every stage of the chain (stages.py) and the
pitch of the dry vocals, in <speaker>/eval/frames/<song>.npz (resumable; a file made on another chain is
made again). Runs in the ddsp env.
lines: <speaker>/eval/lines.jsonl, one line per sung line with its time span, measurements and problems.
Besides what the steps did, two measurements of the song as it came in, for lines to leave out rather than
to clean (the listener, 2026-10-20: loud BGM and heavy reverb in the original): bgm_db, how far the mix is
above the separated vocals while she sings, and tail_src, the reverb tail before the dereverb step.
"""
import fcntl
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_vocals as ev  # noqa: E402
from stages import CHAIN, CHAIN_ID, DRY_KEY, INPUT  # noqa: E402

FPS = ev.FPS
STAGE_KEYS = ['mix'] + [k for k, _ in CHAIN]


# ---------- frames ----------

def frames(work, name):
    sig = {}
    for k in STAGE_KEYS:
        stage = ev.STAGES[k]
        x = ev.load(next((work / stage).glob(f'{ev.glob_escape(name)}.*')) if k == 'mix'
                    else work / stage / f'{name}.wav')
        sig[k] = x.mean(1)
        del x
    n = 1 + min(len(x) for x in sig.values()) // ev.HOP
    f0 = ev.pitch(sig[DRY_KEY])[:n]
    F = ev.features(sig, f0, f0 > 0, n)
    out = {'chain': np.array(CHAIN_ID), 'f0_dry': f0.astype(np.float16),
           'flat_dry': F[DRY_KEY]['flat'].astype(np.float16)}
    for k in STAGE_KEYS:
        out[f'E_{k}'] = ev.dB(F[k]['bands'].sum(1)).astype(np.float16)
    for k, name in ((DRY_KEY, 'dry'), ('mix', 'mix')):
        out[f'hp_{name}'] = ev.dB(np.nan_to_num(F[k]['hp'], nan=0.0)).astype(np.float16)
        out[f'hv_{name}'] = ev.dB(np.nan_to_num(F[k]['hv'], nan=0.0)).astype(np.float16)
    out['hf_dry'] = ev.dB(ev.band_power(F[DRY_KEY]['bands'], 4000, 12000)).astype(np.float16)
    return out


def current(path):
    """The frames file exists and was made on this chain."""
    if not path.exists():
        return False
    try:
        with np.load(path) as z:
            return 'chain' in z.files and str(z['chain']) == CHAIN_ID
    except (OSError, ValueError):
        return False


def run_frames(args):
    k, n = 0, 1
    if args and args[0] == '--shard':
        k, n = map(int, args[1].split('/'))
        args = args[2:]
        if not 0 <= k < n:  # 1 .. n would skip the first song of the list
            sys.exit(f'--shard {k}/{n}: k runs from 0 to {n - 1}')
    todo = []
    for d in args:
        spk = Path(d)
        out = spk / 'eval' / 'frames'
        out.mkdir(parents=True, exist_ok=True)
        names = sorted(f.stem for f in (spk / 'work' / ev.STAGES['dry']).glob('*.wav'))
        todo += [(spk, out, x) for x in names if not current(out / f'{x}.npz')]
        print(f'{spk.name}: {len(names)} songs, {sum(t[0] == spk for t in todo)} to do', flush=True)
    random.Random(0).shuffle(todo)
    todo = todo[k::n]
    for i, (spk, out, name) in enumerate(todo, 1):
        t0 = time.time()
        try:
            arrays = frames(spk / 'work', name)
            tmp = out / f'{name}.part.npz'
            np.savez_compressed(tmp, **arrays)
            tmp.replace(out / f'{name}.npz')
            msg = f'{time.time() - t0:.1f}'
        except Exception as e:  # keep going
            msg = repr(e)
        print(f'{i}/{len(todo)} {spk.name} {name} {msg}', flush=True)


# ---------- lines ----------

MIN_LINE, MAX_LINE, JOIN_GAP, PAD = 0.8, 15.0, 0.25, 0.1  # seconds


def split_long(a, b, E):
    """[a, b) frames -> pieces of at most MAX_LINE, cut at the quietest frame in the middle part."""
    if (b - a) / FPS <= MAX_LINE:
        return [(a, b)]
    lo, hi = a + int((b - a) * 0.3), a + int((b - a) * 0.7)
    cut = lo + int(np.argmin(E[lo:hi]))
    return split_long(a, cut, E) + split_long(cut, b, E)


def segment(E, f0):
    """Lines as (start, end) frames: frames within 30 dB of the singing, gaps under JOIN_GAP joined,
    at least MIN_LINE long, longer than MAX_LINE split."""
    level = np.median(E[f0 > 0]) if (f0 > 0).sum() > 100 else np.percentile(E, 90)
    active = E > level - 30
    runs = ev.runs(active, 1)
    joined = []
    for s, e in runs:
        if joined and (s - joined[-1][1]) / FPS < JOIN_GAP:
            joined[-1] = (joined[-1][0], e)
        else:
            joined.append((s, e))
    lines = []
    for s, e in joined:
        if (e - s) / FPS >= MIN_LINE:
            lines += split_long(s, e, E)
    return lines, float(level)


def med(x):
    x = np.asarray(x, np.float64)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else None


def measure(z, s, e, level, n, next_start):
    """Measurements of the line [s, e) in frames; next_start is where the next line starts."""
    E = {k: z[f'E_{k}'].astype(np.float32) for k in STAGE_KEYS}
    dry = E[DRY_KEY]
    f0 = z['f0_dry'].astype(np.float32)
    sl = slice(s, e)
    voiced = f0[sl] > 0
    m = {'start': round(s / FPS, 2), 'end': round(e / FPS, 2), 'dur': round((e - s) / FPS, 2)}
    m['voiced'] = float(voiced.mean())
    m['level'] = med(dry[sl][voiced]) - level if voiced.any() else med(dry[sl]) - level
    # karaoke: how far below its input the line is, on frames where the input is loud
    kin = INPUT['kar']
    loud = E[kin][sl] > level - 25
    d = (E['kar'][sl] - E[kin][sl])[loud]
    m['kar_drop'] = med(d) if len(d) else 0.0
    # holes: frames the karaoke step took more than 10 dB out of AND left weak (taking out a harmony
    # leaves the lead at its level, so that does not count)
    holes = (d < -10) & (E['kar'][sl][loud] < level - 15)
    m['kar_cut'] = float(np.mean(holes)) if len(d) else 0.0
    # dereverb: how far below its input, on frames where the input is loud
    din = INPUT['derev']
    loud_i = E[din][sl] > level - 25
    d2 = (E['derev'][sl] - E[din][sl])[loud_i]
    m['dr_drop'] = med(d2) if len(d2) else 0.0
    # the song as it came in: how far the mix is above the separated vocals while she sings (accompaniment
    # loud against the voice), and the reverb tail before the dereverb step (a wet original)
    if voiced.any():
        m['bgm_db'] = med((E['mix'][sl] - E['voc'][sl])[voiced])
    if e + 50 <= min(n, next_start):
        p_in = 10 ** (E[din] / 10)
        m['tail_src'] = float(ev.dB(p_in[e + 15:e + 35].mean()) - ev.dB(p_in[max(s, e - 10):e].mean()))
    # while singing: harmonic-to-valley ratio and the valleys against the mix (accompaniment under the voice)
    hp, hv, hvm = (z[k].astype(np.float32)[sl][voiced] for k in ('hp_dry', 'hv_dry', 'hv_mix'))
    if voiced.sum() >= 20:
        m['hvr_mid'] = med(hp[:, 1] - hv[:, 1])
        m['hvr_low'] = med(hp[:, 0] - hv[:, 0])
        m['vleak_low'] = med(hv[:, 0] - hvm[:, 0])
        m['vleak_mid'] = med(hv[:, 1] - hvm[:, 1])
    # unpitched sound inside the line (talking, noise, other voices), excluding the edges
    inner = np.zeros(e - s, bool)
    inner[int(0.15 * FPS):max(0, e - s - int(0.15 * FPS))] = True
    unp = inner & ~voiced & (dry[sl] > level - 20)
    m['unpitched'] = float(unp.mean())
    # reverb left in the dry vocals: after the line, when the next line starts at least 0.5 s later
    if e + 50 <= min(n, next_start):
        p = 10 ** (dry / 10)
        m['tail'] = float(ev.dB(p[e + 15:e + 35].mean()) - ev.dB(p[max(s, e - 10):e].mean()))
    m['f0'] = med(f0[sl][voiced])
    return m


# problem name, weight, badness from the measurements, label (for the review page)
def problems(m):
    clip = lambda x: max(0.0, min(1.0, x))  # noqa: E731
    g = lambda k, d=0.0: d if m.get(k) is None else m[k]  # noqa: E731
    return [
        (3.0, clip((-g('kar_drop') - 3) / 9), f'主唱被去和声削弱（比去和声前低 {-g("kar_drop"):.0f} dB）'),
        (2.0, clip((g('kar_cut') - 0.05) / 0.35), f'去和声切出断口（{100 * g("kar_cut"):.0f}% 的帧）'),
        (2.0, clip((-g('dr_drop') - 4) / 8), f'被去混响削弱（比去混响前低 {-g("dr_drop"):.0f} dB）'),
        (2.0, clip((g('bgm_db', 0) - 6) / 8), f'原曲伴奏很响（比人声高 {g("bgm_db", 0):.0f} dB）'),
        (1.5, clip((g('tail_src', -60) + 30) / 20), f'原曲混响重（去混响前句尾只降了 {max(0.0, -g("tail_src", -60)):.0f} dB）'),
        (2.0, clip((g('vleak_low', -40) + 18) / 10), f'唱歌时底下有伴奏残留（谐波间隙只比原曲低 {-g("vleak_low", -40):.0f} dB）'),
        (1.5, clip((14 - g('hvr_mid', 30)) / 8), f'嗓音杂音多（1.5–4 kHz 谐波只比间隙高 {g("hvr_mid", 30):.0f} dB）'),
        (1.5, clip((g('unpitched') - 0.15) / 0.3), f'有不像唱歌的声音（{100 * g("unpitched"):.0f}% 的帧没有音高）'),
        (1.0, clip((g('tail', -60) + 40) / 20), f'尾音混响偏重（0.15–0.35 秒后只降了 {max(0.0, -g("tail", -60)):.0f} dB）'),
        (1.5, clip((-g('level') - 12) / 10), f'音量很弱（比整首的歌声低 {-g("level"):.0f} dB），可能是残片'),
        (1.0, clip((0.6 - g('voiced')) / 0.4), f'有音高的部分只占 {100 * g("voiced"):.0f}%'),
    ]


def score(m):
    ps = problems(m)
    bad = sum(w * b for w, b, _ in ps)
    labels = [label for w, b, label in sorted(ps, key=lambda p: -p[0] * p[1]) if w * b >= 0.3]
    return max(0.0, 100 - 100 * bad / 4), labels


def run_lines(args):
    for d in args:
        spk = Path(d)
        fdir = spk / 'eval' / 'frames'
        out = []
        for f in sorted(fdir.glob('*.npz')):
            if f.name.endswith('.part.npz') or not current(f):
                continue
            z = np.load(f)
            E, f0 = z[f'E_{DRY_KEY}'].astype(np.float32), z['f0_dry'].astype(np.float32)
            lines, level = segment(E, f0)
            for k, (s, e) in enumerate(lines):
                next_start = lines[k + 1][0] if k + 1 < len(lines) else len(E)
                m = measure(z, s, e, level, len(E), next_start)
                m['song'], m['k'] = f.stem, k
                m['score'], m['problems'] = score(m)
                m['score'] = round(m['score'], 1)
                out.append(m)
        path = spk / 'eval' / 'lines.jsonl'
        tmp = path.with_suffix('.part')
        with open(tmp, 'w', encoding='utf-8') as fp:
            fcntl.flock(fp, fcntl.LOCK_EX)
            for m in out:
                fp.write(json.dumps(m, ensure_ascii=False) + '\n')
        tmp.replace(path)
        total = sum(m['dur'] for m in out)
        good = sum(m['dur'] for m in out if m['score'] >= 75)
        print(f'{spk.name}: {len(out)} lines in {len(list(fdir.glob("*.npz")))} songs, {total / 3600:.2f} h; '
              f'score >= 75: {good / 3600:.2f} h', flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] not in ('frames', 'lines'):
        sys.exit(__doc__)
    (run_frames if sys.argv[1] == 'frames' else run_lines)(sys.argv[2:])
