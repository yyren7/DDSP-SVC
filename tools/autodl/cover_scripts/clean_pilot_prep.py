# One song of a multitrack for the clean-input pilot: the raw lead vocal as it was recorded (lossless), and an
# instrumental of the other tracks at the levels of the official mix. Each track's gain is fitted to the mix by
# least squares on 100 ms band energies (the mix bus processing is not modelled), after aligning the
# tracks to the mix.
#   python clean_pilot_prep.py <track dir> <official mix> <lead track name> <out dir> [track to leave out ...]
import json, os, sys, glob
import numpy as np, soundfile as sf
from scipy import signal, optimize

track_dir, mix_path, lead_name, out_dir = sys.argv[1:5]
drop = set(sys.argv[5:])
SR = 44100
BANDS = [(lo, lo * 2) for lo in (45, 90, 180, 360, 720, 1440, 2880, 5760, 11520)]

def load(path):
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    if sr != SR:
        g = np.gcd(sr, SR)
        x = signal.resample_poly(x, SR // g, sr // g, axis=0).astype(np.float32)
    return x

def energies(x, hop=int(0.1 * SR)):
    m = x.mean(1)
    f, t, z = signal.stft(m, SR, nperseg=4096, noverlap=4096 - hop)
    p = np.abs(z) ** 2
    return np.stack([p[(f >= lo) & (f < hi)].sum(0) for lo, hi in BANDS])

paths = sorted(p for p in glob.glob(os.path.join(track_dir, '*.wav')) if os.path.basename(p) not in drop)
tracks = {os.path.basename(p): load(p) for p in paths}
n = max(len(x) for x in tracks.values())
tracks = {k: np.pad(x, ((0, n - len(x)), (0, 0))) for k, x in tracks.items()}
mix = load(mix_path)

# align: the sum of the raw tracks against the mix, by cross-correlating 10 ms envelopes, then the samples
raw = sum(x.mean(1) for x in tracks.values())
def env(m, hop=441):
    k = len(m) // hop
    return np.sqrt(np.mean(m[:k * hop].reshape(k, hop) ** 2, 1))
ea, eb = env(raw), env(mix.mean(1))
c = signal.correlate(eb - eb.mean(), ea - ea.mean(), mode='full')
lag = (int(np.argmax(c)) - (len(ea) - 1)) * 441  # mix sample = track sample + lag
w = slice(max(0, lag) + SR * 20, max(0, lag) + SR * 50)
seg_mix = mix.mean(1)[w]
seg_raw = raw[w.start - lag:w.stop - lag]
c2 = signal.correlate(seg_mix, seg_raw, mode='full', method='fft')
lag += int(np.argmax(c2)) - (len(seg_raw) - 1)
print(f'tracks start {lag / SR:+.3f} s into the mix')

def shift(x):
    if lag >= 0:
        y = np.concatenate([np.zeros((lag, x.shape[1]), np.float32), x])
    else:
        y = x[-lag:]
    return np.pad(y, ((0, max(0, len(mix) - len(y))), (0, 0)))[:len(mix)]
tracks = {k: shift(x) for k, x in tracks.items()}

E = {k: energies(x) for k, x in tracks.items()}
M = energies(mix)
scale = M.mean(1, keepdims=True) + 1e-12          # every band counts the same
A = np.stack([(E[k] / scale).ravel() for k in tracks], 1).astype(np.float64)
b = (M / scale).ravel().astype(np.float64)
wts, _ = optimize.nnls(A, b)
# a track that the others already cover (a kick mic under the overheads and the room) would get nothing: every track
# keeps at least a tenth of the median weight (10 dB under the median gain)
floor = 0.1 * np.median(wts[wts > 0])
wts = optimize.lsq_linear(A, b, bounds=(np.full(len(wts), floor), np.inf)).x
gains = {k: float(np.sqrt(w)) for k, w in zip(tracks, wts)}
fit = A @ wts
r = np.corrcoef(np.log(fit + 1e-9), np.log(b + 1e-9))[0, 1]
for k in tracks:
    print(f'  {k:40s} gain {20 * np.log10(gains[k] + 1e-9):+6.1f} dB')
print(f'fit of the band energies to the mix: r = {r:.3f} (log)')

os.makedirs(out_dir, exist_ok=True)
lead = tracks[lead_name]
inst = sum(gains[k] * (x if x.shape[1] == 2 else np.repeat(x, 2, 1)) for k, x in tracks.items() if k != lead_name)
peak = max(np.abs(inst).max(), 1e-9)
norm = min(1.0, 0.89 / peak)                       # the instrumental at most -1 dBFS
sf.write(os.path.join(out_dir, 'lead.flac'), lead.mean(1), SR, subtype='PCM_24')
sf.write(os.path.join(out_dir, 'inst.flac'), inst * norm, SR, subtype='PCM_16')
json.dump({'lag_s': lag / SR, 'gains_db': {k: float(20 * np.log10(g + 1e-9)) for k, g in gains.items()}, 'lead': lead_name,
           'lead_gain': float(gains[lead_name] * norm), 'inst_norm': float(norm), 'fit_r': float(r)},
          open(os.path.join(out_dir, 'prep.json'), 'w', encoding='utf-8'), indent=1)
print('written', out_dir)
