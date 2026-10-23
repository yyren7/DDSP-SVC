# For an allconv song: loudness of the original vocal parts that cover_mix.py aligns to, against vocal.wav
import sys
import numpy as np
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import cover_mix as cm
C = '/root/autodl-tmp/covers'
for s in sys.argv[1:]:
    P, W, WB = f'{C}/{s}/phase', f'{C}/_work5', f'{C}/_work6b'
    inst, sr = cm.load(f'{P}/inst.wav')
    L = lambda x: cm.loudness(x, sr)
    rd = lambda p: cm.fit(cm.load(p)[0], len(inst))
    src, v, l, bk, hw = (rd(p) for p in (f'{P}/vocal.wav', f'{W}/1_vocals/{s}.wav', f'{W}/2_karaoke/{s}.wav',
                                         f'{P}/backing.wav', f'{WB}/1_vocals/{s}.wav'))
    g = cm.restore(src, v); hg = cm.restore(bk, hw)
    print(f'{s}: g {20*np.log10(g):+.1f} hg {20*np.log10(hg):+.1f} | vocal.wav {L(src):.1f}  g*v {L(g*v):.1f}  '
          f'g*l {L(g*l):.1f}  backing.wav {L(bk):.1f}  hg*hwet {L(hg*hw):.1f}  ref g*l+hg*hwet {L(g*l+hg*hw):.1f}')
    for kind in ('eq_mix', 'eq_allconv_mix'):
        mix = rd(f'{C}/out/{s}_hanamaru_hareru_40000_{kind}.wav')
        print(f'   {kind}: mix-inst {L(mix - inst):.1f}')
    corr = np.sum(g*l*bk) / np.sqrt(np.sum((g*l)**2) * np.sum(bk**2))
    print(f'   corr(lead, backing.wav) {corr:+.2f}')
