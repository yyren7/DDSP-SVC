# liangrenfen 56-66 s: (1) the limiter's gain on the off vocal per 20 ms in each mix, (2) low-band thumps of the
# converted lead that the dry lead does not have
import sys
import numpy as np
from scipy import signal
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import cover_mix as cm
C = '/root/autodl-tmp/covers'; s = 'liangrenfen'; o = f'{C}/out/{s}_hanamaru_hareru_40000'
a, b = 56.0, 66.0
inst, sr = cm.load(f'{C}/{s}/phase/inst.wav')
seg = lambda x: x[int(a * sr):int(b * sr)].mean(axis=1)
I = seg(inst)
n = int(0.02 * sr)
for name in ('eq_allconv_mix', 'eq_lift2_allconv_mix', 'eq_lift4_allconv_mix'):
    M = seg(cm.fit(cm.load(f'{o}_{name}.wav')[0], len(inst)))
    g = []
    for i in range(0, len(I) - n, n):
        ii, mm = I[i:i + n], M[i:i + n]
        g.append(np.sum(ii * mm) / max(np.sum(ii * ii), 1e-12))
    g = 20 * np.log10(np.clip(g, 1e-3, None))
    t = a + np.arange(len(g)) * 0.02
    pre, post = g[t < 61], g[t >= 61]
    print(f'{name:22s} off-vocal gain dB: before 61 s median {np.median(pre):+.1f} min {pre.min():+.1f} | '
          f'after: median {np.median(post):+.1f} min {post.min():+.1f}, frames under -3 dB {np.mean(post < -3) * 100:.0f}%')
sos = signal.butter(4, [40, 150], btype='band', fs=sr, output='sos')
lowdb = lambda x: 10 * np.log10(np.array([np.mean(x[i:i + n] ** 2) for i in range(0, len(x) - n, n)]) + 1e-14)
dry = lowdb(signal.sosfilt(sos, seg(cm.fit(cm.load(f'{C}/_work5/3_dereverb/{s}.wav')[0], len(inst)))))
conv = lowdb(signal.sosfilt(sos, seg(cm.fit(cm.load(f'{o}.wav')[0], len(inst)))))
ins = lowdb(signal.sosfilt(sos, I))
hot = np.where((conv - dry > 10) & (conv > ins - 15))[0]
print(f'converted lead 40-150 Hz: {len(hot)} frames of 20 ms over the dry lead by 10 dB and within 15 dB of the off vocal;'
      f' at {[round(a + i * 0.02, 2) for i in hot[:20]]}')
print(f'converted lead 40-150 Hz vs off vocal around 60-62 s: max {np.max((conv - ins)[(np.arange(len(conv)) * 0.02 + a >= 59.5) & (np.arange(len(conv)) * 0.02 + a < 62.5)]):+.1f} dB')
