# aini: per 3 s window, level (dB, K-weighted) of each stage, to see where the vocal goes missing
import sys
import numpy as np
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import cover_mix as cm
C = '/root/autodl-tmp/covers'; s = 'aini'
inst, sr = cm.load(f'{C}/{s}/phase/inst.wav')
paths = {'vocal.wav': f'{C}/{s}/phase/vocal.wav', '1_vocals': f'{C}/_work5/1_vocals/{s}.wav',
         'lead': f'{C}/_work5/2_karaoke/{s}.wav', 'dry': f'{C}/_work5/3_dereverb/{s}.wav',
         'conv': f'{C}/out/{s}_hanamaru_hareru_40000.wav', 'harm': f'{C}/out/{s}_hanamaru_hareru_40000_harm.wav',
         'mix': f'{C}/out/{s}_hanamaru_hareru_40000_eq_allconv_mix.wav'}
x = {k: cm.kweight(cm.fit(cm.load(p)[0], len(inst)), sr) for k, p in paths.items()}
ki = cm.kweight(inst, sr)
e = lambda a: 10 * np.log10(np.mean(a ** 2) + 1e-20)
n = 3 * sr
vmax = max(e(x['vocal.wav'][i:i + n]) for i in range(0, len(inst) - n, n))
print('  time ' + ' '.join(f'{k:>9s}' for k in list(paths) + ['mix-inst']))
for i in range(0, len(inst) - n, n):
    v = e(x['vocal.wav'][i:i + n])
    if v < vmax - 20:
        continue
    M, I = x['mix'][i:i + n], ki[i:i + n]
    g = np.sum(M * I) / np.sum(I * I)
    row = [e(x[k][i:i + n]) for k in paths] + [e(M - g * I)]
    flag = ' <<' if row[-1] < row[0] - 10 else ''
    print(f'{i // sr // 60:2d}:{i // sr % 60:02d} ' + ' '.join(f'{r:9.1f}' for r in row) + flag)
