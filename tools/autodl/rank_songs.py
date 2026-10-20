"""
Rank a speaker's dry vocals from best to worst by the measurements of eval_vocals.py
(<speaker>/eval/metrics.jsonl), with the problems of each song spelled out. The review page shows the
ranking; run this to print it.

    python tools/autodl/rank_songs.py /root/autodl-tmp/speakers/pheebie

Each problem gets a badness from 0 (none) to 1 (as bad as it gets) and a weight; the score is
100 - 100 * weighted badness / 6, at least 0. Only measured problems count: listening decides.
"""
import json
import sys
from pathlib import Path


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def get(m, key, default=0.0):
    v = m.get(key)
    return default if v is None else v


def problems(m):
    """[(weight, badness, label)] of one song's measurements (labels in Chinese for the review page)."""
    sung = max(get(m, 'voiced_sec'), 1.0)
    out = []
    holes = get(m, 'holes_kar_pm')
    out.append((3.0, clip(holes / 20), f'去和声把主唱切出断口 {holes:.0f} 次/分钟'))
    cut = get(m, 'cut_kar_tonal_sec') + get(m, 'cut_dr_tonal_sec')
    out.append((2.0, clip(cut / sung / 0.1), f'整段被去掉 {cut:.0f} 秒（去和声 {get(m, "cut_kar_tonal_sec"):.0f}、'
                                             f'去混响 {get(m, "cut_dr_tonal_sec"):.0f}）'))
    live_level = get(m, 'gap_live_rel_dry', -100.0)
    loud = clip((live_level + 60) / 30)
    out.append((2.0, clip((get(m, 'ghost_corr', -1.0) - 0.2) / 0.5) * clip(get(m, 'gap_live_sec') / 10) * loud,
                f'停顿里有伴奏残影（比歌声低 {-live_level:.0f} dB）'))
    p90 = get(m, 'gap_p90_rel_dry', -100.0)
    out.append((1.5, clip((p90 + 50) / 25), f'停顿里残留较响（比歌声低 {-p90:.0f} dB）'))
    out.append((1.5, (1 - get(m, 'gap_silent_frac', 1.0)) * clip((live_level + 60) / 20),
                f'底噪（{100 * (1 - get(m, "gap_silent_frac", 1.0)):.0f}% 的停顿，比歌声低 {-live_level:.0f} dB）'))
    tail = get(m, 'tail350_dry', -100.0)
    out.append((1.5, clip((tail + 45) / 25), f'混响偏重（乐句结束 0.35 秒后只降了 {max(0.0, -tail):.0f} dB）'))
    hvr = get(m, 'hvr1_dry', 30.0)
    out.append((1.5, clip((15 - hvr) / 10), f'嗓音发虚、杂音多（1.5–4 kHz 谐波只比间隙高 {hvr:.0f} dB）'))
    dr_holes = get(m, 'holes_dr_pm')
    out.append((1.0, clip(dr_holes / 10), f'去混响切出断口 {dr_holes:.0f} 次/分钟'))
    cliff = (m.get('cut_mix') or [None, None])[1]
    out.append((0.5, 1.0 if cliff and cliff < 16000 else 0.0, f'音源高频只到 {(cliff or 0) / 1000:.1f} kHz'))
    out.append((1.0, clip((90 - sung) / 60), f'有效歌声只有 {sung:.0f} 秒'))
    return out


def rank(rows):
    """[(score, name, [labels of the problems that count, worst first], measurements)], best first;
    songs at score 0 keep their order by how bad they are."""
    ranked = []
    for m in rows:
        if 'error' in m or 'skip' in m:
            continue
        ps = problems(m)
        bad = sum(w * b for w, b, _ in ps)
        labels = [label for w, b, label in sorted(ps, key=lambda p: -p[0] * p[1]) if w * b >= 0.3]
        ranked.append((bad, m['name'], labels, m))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [(max(0.0, 100 - 100 * bad / 6), name, labels, m) for bad, name, labels, m in ranked]


def load(speaker_dir):
    path = Path(speaker_dir) / 'eval' / 'metrics.jsonl'
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def main():
    for d in sys.argv[1:]:
        ranked = rank(load(d))
        print(f'== {Path(d).name}: {len(ranked)} songs')
        for k, (score, name, labels, _) in enumerate(ranked, 1):
            print(f'{k:4d} {score:5.1f}  {name}  {"；".join(labels)}')


if __name__ == '__main__':
    main()
