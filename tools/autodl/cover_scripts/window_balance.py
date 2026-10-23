# Per 3 s window with the vocal active: (vocal - off vocal) in the cover minus the same in the original (dB, K-weighted
# energy), the off vocal's gain in the cover fitted per window (the limiter); percentiles, and how the difference
# goes with the original vocal's level (loud sections buried?)
import sys
import numpy as np
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import cover_mix as cm
C = '/root/autodl-tmp/covers'
for s in sys.argv[1:]:
    inst, sr = cm.load(f'{C}/{s}/phase/inst.wav')
    voc = cm.fit(cm.load(f'{C}/{s}/phase/vocal.wav')[0], len(inst))
    mix = cm.fit(cm.load(f'{C}/out/{s}_hanamaru_hareru_40000_eq_allconv_mix.wav')[0], len(inst))
    ki, kv, km = (cm.kweight(x, sr) for x in (inst, voc, mix))
    n = 3 * sr
    rows = []
    for i in range(0, len(inst) - n, n):
        I, V, M = ki[i:i + n], kv[i:i + n], km[i:i + n]
        g = np.sum(M * I) / max(np.sum(I * I), 1e-20)
        cv = M - g * I
        e = lambda x: 10 * np.log10(np.mean(x ** 2) + 1e-20)
        rows.append((e(V), e(V) - e(I), e(cv) - e(g * I)))
    r = np.array(rows)
    r = r[r[:, 0] > r[:, 0].max() - 20]  # windows where the original vocal is within 20 dB of its loudest
    d = r[:, 2] - r[:, 1]
    loud = r[:, 0] > np.median(r[:, 0])
    print(f'{s:12s} n={len(d):3d}  diff p10 {np.percentile(d, 10):+5.1f}  median {np.median(d):+5.1f}  p90 {np.percentile(d, 90):+5.1f}'
          f'  | louder half {np.median(d[loud]):+5.1f}  quieter half {np.median(d[~loud]):+5.1f}'
          f'  | orig vocal-inst median {np.median(r[:, 1]):+5.1f}')
