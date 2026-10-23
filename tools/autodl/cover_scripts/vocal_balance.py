# Vocal against off vocal in the original (vocal.wav vs inst.wav) and in each cover mix (mix - inst vs inst):
# BS.1770 loudness, and energy in 1-4 kHz (presence), over the frames where the original vocal is active.
import sys
import numpy as np
from scipy import signal
sys.path.insert(0, 'tools')
import cover_mix as cm

C = '/root/autodl-tmp/covers'
SONGS = [('haru', 0), ('yuusha', 0), ('haohaode', 1), ('aini', 1), ('idol', 1), ('liangrenfen', 1)]


def band(x, sr, lo, hi):
    sos = signal.butter(4, [lo, hi], btype='band', fs=sr, output='sos')
    return signal.sosfiltfilt(sos, x, axis=0)


def db(x):
    return 10 * np.log10(np.mean(x ** 2) + 1e-20)


print(f'{"song":28s} {"LUFS 原曲":>9s} {"翻唱":>6s} {"差":>5s} | {"1-4k 原曲":>9s} {"翻唱":>6s} {"差":>5s} | g')
for s, allconv in SONGS:
    inst, sr = cm.load(f'{C}/{s}/phase/inst.wav')
    voc = cm.fit(cm.load(f'{C}/{s}/phase/vocal.wav')[0], len(inst))
    n = sr // 2
    env = np.array([np.sqrt(np.mean(voc[i:i + n] ** 2)) for i in range(0, len(voc) - n, n)])
    act = np.repeat(env > 0.05 * env.max(), n)
    act = np.concatenate([act, np.zeros(len(inst) - len(act), bool)])
    for kind in (['mix', 'allconv_mix'] if allconv else ['mix']):
        mix = cm.fit(cm.load(f'{C}/out/{s}_hanamaru_hareru_40000{sys.argv[1] if len(sys.argv) > 1 else ""}_{kind}.wav')[0], len(inst))
        g = np.sum(mix[act] * inst[act]) / np.sum(inst[act] ** 2)  # limiter's average gain on the off vocal
        cv = mix - g * inst
        lo = cm.loudness(voc[act], sr) - cm.loudness(inst[act], sr)
        lc = cm.loudness(cv[act], sr) - cm.loudness(g * inst[act], sr)
        bi, bv, bc = (band(x[act], sr, 1000, 4000) for x in (inst, voc, cv))
        po, pc = db(bv) - db(bi), db(bc) - db(g * bi)
        print(f'{s + " " + kind:28s} {lo:9.1f} {lc:6.1f} {lc - lo:+5.1f} | {po:9.1f} {pc:6.1f} {pc - po:+5.1f} | {g:.2f}')
