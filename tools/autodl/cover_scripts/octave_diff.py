# Per octave: original dry lead minus converted lead (dB), shape only (energy-weighted mean removed)
import sys
import numpy as np
sys.path.insert(0, 'tools')
import cover_mix as cm
C = '/root/autodl-tmp/covers'
rows = [('haru', '_work5p'), ('yuusha', '_work5p'), ('haohaode', '_work5'), ('aini', '_work5'), ('idol', '_work5'),
        ('liangrenfen', '_work5'), ('aini harm', '_work6b'), ('idol harm', '_work6b'), ('liangrenfen harm', '_work6b')]
print('band Hz      ' + ' '.join(f'{int(c):>6d}' for c in cm.OCTAVES))
for name, w in rows:
    s = name.split()[0]
    dry, sr = cm.load(f'{C}/{w}/3_dereverb/{s}.wav')
    conv = cm.fit(cm.load(f'{C}/out/{s}_hanamaru_hareru_40000{"_harm" if "harm" in name else ""}.wav')[0], len(dry))
    pd, pc = cm.octaves(dry, sr), cm.octaves(conv, sr)
    d = 10 * np.log10(pd / pc)
    d -= 10 * np.log10(np.sum(pc * 10 ** (d / 10)) / np.sum(pc))  # keep conv's total energy
    print(f'{name:12s} ' + ' '.join(f'{x:6.1f}' for x in d))
