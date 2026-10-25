# hanamaru_hareru's allconv backing against her original backing in 6 s windows where it is sung: the old one
# (converted after dereverb, run6.sh) and v2 (before dereverb, run9.sh), as cover_mix.voice() levels them
import sys
import numpy as np
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import cover_mix as cm
C, SPK, STEP = '/root/autodl-tmp/covers', 'hanamaru_hareru', 40000
for s in sys.argv[1:]:
    P, WB, out = f'{C}/{s}/phase', f'{C}/_work6b', f'{C}/out/{s}_{SPK}_{STEP}'
    bk, sr = cm.load(f'{P}/backing.wav')
    rd = lambda p: cm.fit(cm.load(p)[0], len(bk))
    hw, hd = rd(f'{WB}/1_vocals/{s}.wav'), rd(f'{WB}/3_dereverb/{s}.wav')
    hg = cm.restore(bk, hw)
    orig = hg * hw
    w = 6 * sr
    def st(x):
        y = (cm.kweight(x, sr) ** 2).sum(axis=1)
        m = len(y) // w
        return -0.691 + 10 * np.log10(np.maximum(y[:m * w].reshape(m, w).mean(axis=1), 1e-20))
    so = st(orig)
    act = so > cm.loudness(orig, sr) - 12
    print(f'{s}: dereverb took {np.median((so - st(hg * hd))[act]):.1f} dB of the backing (median of {act.sum()} sung windows)')
    for name, conv, dry in (('old', f'{out}_harm.wav', hg * hd), ('v2 ', f'{out}_harmwet.wav', orig)):
        x = sum(cm.voice(rd(conv), dry, orig, sr, seed=1)[:2])
        gap = (st(x) - so)[act]
        print(f'   {name} conv - orig: median {np.median(gap):+5.1f}, 10%..90% {np.quantile(gap,.1):+5.1f}..{np.quantile(gap,.9):+5.1f} dB,'
              f' 6+ dB short {np.mean(gap < -6):4.0%}, 6+ dB over {np.mean(gap > 6):4.0%}', flush=True)
