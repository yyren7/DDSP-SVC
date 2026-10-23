# The clean-input pilot's mixes (clean_pilot.sh): a converted lead over the instrumental of the multitrack, as loud
# (BS.1770) as the raw lead was in the official mix, with the same synthetic room for every version, through
# cover_mix.py's limiter. Every version gets exactly this, so the mixes differ only in the converted lead.
#   python clean_pilot_mix.py <inst.flac> <lead.flac> <prep.json> <converted lead> <out.wav>   (from the repo root)
import json, sys
import numpy as np, soundfile as sf
from scipy import signal
sys.path.insert(0, 'tools')
import cover_mix as cm

inst_p, lead_p, prep_p, conv_p, out_p = sys.argv[1:6]
inst, sr = cm.load(inst_p)
lead, r = cm.load(lead_p)
conv, rc = cm.load(conv_p)
if rc != sr:
    g = np.gcd(rc, sr)
    conv = signal.resample_poly(conv, sr // g, rc // g, axis=0)
lead = cm.fit(lead, len(inst)) * json.load(open(prep_p, encoding='utf-8'))['lead_gain']
conv = cm.fit(conv.mean(axis=1, keepdims=True).repeat(2, axis=1), len(inst))
ratio = np.full(len(cm.OCTAVES), 10 ** (-14 / 10))  # a modest room, 14 dB under the voice, less in the lowest band
ratio[0] = 10 ** (-24 / 10)
ir = cm.room(sr, ratio, seed=0)
wet = np.stack([signal.fftconvolve(conv[:, c], ir[:, c])[:len(conv)] for c in range(2)], axis=1)
k = 10 ** ((cm.loudness(lead, sr) - cm.loudness(conv + wet, sr)) / 20)
mix, fixed, deepest = cm.limit(inst + k * (conv + wet), sr)
sf.write(out_p, np.clip(mix, -1, 1).astype(np.float32), sr, subtype='PCM_24')
print(f'{out_p}: lead {20 * np.log10(k):+.1f} dB to the raw lead\'s level, mix {20 * np.log10(fixed):+.1f} dB, '
      f'limiter at most {20 * np.log10(deepest):.1f} dB')
