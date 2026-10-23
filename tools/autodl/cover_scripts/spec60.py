# Spectrograms 54-66 s of liangrenfen's stems, and the 40-250 Hz level of each in 50 ms frames
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools')
import cover_mix as cm
C = '/root/autodl-tmp/covers'; s = 'liangrenfen'; o = f'{C}/out/{s}_hanamaru_hareru_40000'
paths = [('original - off vocal', f'{C}/{s}/phase/vocal.wav'), ('off vocal', f'{C}/{s}/phase/inst.wav'),
         ('1_vocals', f'{C}/_work5/1_vocals/{s}.wav'), ('lead (karaoke)', f'{C}/_work5/2_karaoke/{s}.wav'),
         ('dry lead', f'{C}/_work5/3_dereverb/{s}.wav'), ('backing.wav', f'{C}/{s}/phase/backing.wav'),
         ('backing dry', f'{C}/_work6b/3_dereverb/{s}.wav'), ('conv lead', f'{o}.wav'), ('conv backing', f'{o}_harm.wav'),
         ('mix allconv +4', f'{o}_eq_lift4_allconv_mix.wav')]
a, b = 54.0, 66.0
fig, axes = plt.subplots(len(paths), 1, figsize=(14, 2.0 * len(paths)), sharex=True)
for ax, (name, p) in zip(axes, paths):
    x, sr = cm.load(p)
    x = x[int(a * sr):int(b * sr)].mean(axis=1)
    f, t, Z = __import__('scipy.signal', fromlist=['stft']).stft(x, sr, nperseg=4096, noverlap=4096 - 512)
    db = 20 * np.log10(np.abs(Z) + 1e-9)
    ax.pcolormesh(t + a, f, db, vmin=db.max() - 70, vmax=db.max(), shading='auto', cmap='magma')
    ax.set_yscale('symlog', linthresh=200); ax.set_ylim(30, 8000); ax.set_ylabel(name, fontsize=8)
    band = np.abs(Z[(f >= 40) & (f <= 250)]) ** 2
    lo = 10 * np.log10(band.sum(axis=0) + 1e-12)
    print(f'{name:22s} 40-250 Hz: median {np.median(lo):6.1f} dB, max {lo.max():6.1f} dB, max-median {lo.max() - np.median(lo):5.1f}')
axes[-1].set_xlabel('s')
plt.tight_layout(); plt.savefig('/tmp/spec60.png', dpi=60)
