"""
The original vocal of a song by phase cancellation: the official off vocal (instrumental) of the same release is
aligned to the original to a fraction of a sample, scaled, and subtracted. When both come from the same master
this leaves the vocal far more cleanly than a separation model, and the aligned off vocal is the backing track
of the cover.

    python tools/offvocal.py <original> <off vocal> -o <dir> [--sr 44100]

Inputs are anything ffmpeg reads (FLAC, WAV, Opus/WebM, M4A). Writes, as float WAV at --sr:
    <dir>/vocal.wav   original minus off vocal
    <dir>/inst.wav    the off vocal as aligned and scaled
and <dir>/offvocal.json with what it prints:
- each file's codec and where its spectrum is cut off (lossy encoders stop at about 16 to 20 kHz)
- the off vocal's delay and gain. The delay is measured every STEP seconds and followed through the song, since
  re-encoded uploads often run a few samples apart by the end (one of them resampled along the way); its spread
  is printed. A jump of more than a few samples means a different edit, not a speed difference.
- cancellation depth: where the original has no vocal, how far the difference lies below the off vocal: the
  10th percentile of 100 ms frames, and the best 3 s stretch (an intro or a break; songs sung throughout have
  fewer than 10% of frames without vocal). The verdict goes by the best stretch. Same master, lossless files:
  -50 dB or deeper. Same master, lossy files (YouTube, Bilibili): roughly -20 to -40 dB, as the codec noise of
  the two files does not cancel. A different mix or master: above -15 dB, and the "vocal" still holds the
  accompaniment.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.fft import next_fast_len

FRAME = 0.1       # seconds per frame of the cancellation measure
QUIET_SHARE = 0.2  # share of frames, lowest difference first, that refit the gain (the parts without vocal)
STEP = 4.0         # seconds between delay measurements along the song
MIN_NCC = 0.3      # weakest normalized correlation of a window whose delay is trusted


def ffmpeg_exe():
    exe = shutil.which('ffmpeg')
    if exe:
        return exe
    import imageio_ffmpeg  # Windows: D:\svc-mv\.venv has it
    return imageio_ffmpeg.get_ffmpeg_exe()


def decode(path, sr):
    """(stereo float64 samples at sr, ffmpeg's description of the audio stream)."""
    ff = ffmpeg_exe()
    info = subprocess.run([ff, '-hide_banner', '-i', str(path)], capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stderr
    stream = next((ln.split('Audio:', 1)[1].strip() for ln in info.splitlines() if 'Audio:' in ln), '?')
    raw = subprocess.run([ff, '-v', 'error', '-i', str(path), '-vn', '-f', 'f32le', '-ac', '2', '-ar', str(sr), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64), stream


def cutoff(x, sr):
    """Frequency (Hz) of the steepest fall of the long-term spectrum above 10 kHz when it falls more than 20 dB
    within 600 Hz, the mark of a lossy encoder; None when there is no such cliff."""
    f, p = signal.welch(x.mean(1), sr, nperseg=8192)
    db = 10 * np.log10(p + 1e-20)
    w = max(1, int(round(600 / (f[1] - f[0]))))
    best, at = 0.0, None
    for k in range(np.searchsorted(f, 10000), len(f) - w):
        drop = db[k - w:k].mean() - db[k:k + w].mean()
        if drop > best:
            best, at = drop, f[k]
    return float(at) if best > 20 else None


def coarse_lag(a, b, sr, rate=4000):
    """Samples by which b must be delayed to line up with a (mono), found at about `rate` Hz."""
    q = max(1, sr // rate)
    a2 = signal.resample_poly(a, 1, q)
    b2 = signal.resample_poly(b, 1, q)
    c = signal.correlate(a2, b2, mode='full', method='fft')
    return (int(np.argmax(np.abs(c))) - (len(b2) - 1)) * q


def fine_lag(a, b, lag, sr, center, span, half=10.0):
    """(delay of b near `lag` to a fraction of a sample, normalized correlation at it) from a 2*half second
    window of a around `center`; None when the window does not fit."""
    lo = int(max(span + max(lag, 0) + 1, center - half * sr))
    hi = int(min(len(a), len(b) + lag - span - 1, center + half * sr))
    if hi - lo < sr:
        return None
    ks = np.arange(lag - span, lag + span + 1)
    seg = a[lo:hi]
    c = np.array([np.dot(seg, b[lo - k:hi - k]) for k in ks])
    j = int(np.argmax(np.abs(c)))
    other = b[lo - ks[j]:hi - ks[j]]
    ncc = abs(c[j]) / max(np.sqrt(np.dot(seg, seg) * np.dot(other, other)), 1e-20)
    if 0 < j < len(c) - 1:  # parabola through the peak and its neighbours
        y0, y1, y2 = np.abs(c[j - 1:j + 2])
        den = y0 - 2 * y1 + y2
        return float(ks[j] + (0.5 * (y0 - y2) / den if den else 0.0)), float(ncc)
    return float(ks[j]), float(ncc)


def lag_curve(a, b, lag, sr):
    """(centers, delays) in samples of a: the delay of b every STEP seconds over windows of 2*STEP, from the
    windows that correlate well, with a running median of 5 against stray windows."""
    centers, lags = [], []
    for c in np.arange(STEP, len(a) / sr - STEP / 2, STEP) * sr:
        got = fine_lag(a, b, int(round(lag)), sr, c, span=48, half=STEP)
        if got and got[1] >= MIN_NCC:
            centers.append(c)
            lags.append(got[0])
    if len(lags) < 3:
        return np.array([0.0]), np.array([lag])
    lags = np.array(lags)
    smooth = np.array([np.median(lags[max(0, i - 2):i + 3]) for i in range(len(lags))])
    return np.array(centers), smooth


def warp(x, centers, lags, n, sr, chunk=1.0):
    """x (samples x channels) delayed by the delay curve, n samples long: Hann-windowed chunks of `chunk`
    seconds overlap by half, each delayed (fractionally, by FFT) by the curve's value at its middle."""
    hop = int(chunk * sr / 2)
    win = np.hanning(2 * hop + 1)[:-1, None]  # periodic Hann: halves overlap-add to 1
    pad = 64
    size = next_fast_len(2 * hop + 2 * pad)
    freqs = np.fft.rfftfreq(size)
    out = np.zeros((n + 4 * hop, x.shape[1]))
    for start in range(-hop, n, hop):
        tau = float(np.interp(start + hop, centers, lags))
        it = int(np.floor(tau))
        lo = start - it - pad  # x[lo:lo+size] shifted by frac covers out[start:start+2*hop] after the pad
        seg = np.zeros((size, x.shape[1]))
        s0, s1 = max(lo, 0), min(lo + size, len(x))
        if s1 > s0:
            seg[s0 - lo:s1 - lo] = x[s0:s1]
        spec = np.fft.rfft(seg, axis=0) * np.exp(-2j * np.pi * freqs * (tau - it))[:, None]
        y = np.fft.irfft(spec, size, axis=0)[pad:pad + 2 * hop] * win
        o0 = start + hop  # out is offset by hop so that start = -hop lands at 0
        out[o0:o0 + 2 * hop] += y
    return out[hop:hop + n]


def frame_energy(x, sr):
    n = int(FRAME * sr)
    m = len(x) // n
    return (x[:m * n] ** 2).reshape(m, n, -1).sum(axis=(1, 2))


def fit_gain(o, i, sr, keep=None):
    """Per-channel least-squares gain of i onto o, over the frames in `keep` (all when None)."""
    n = int(FRAME * sr)
    m = min(len(o), len(i)) // n
    oo, ii = o[:m * n].reshape(m, n, 2), i[:m * n].reshape(m, n, 2)
    if keep is not None:
        oo, ii = oo[keep], ii[keep]
    return (oo * ii).sum(axis=(0, 1)) / np.maximum((ii * ii).sum(axis=(0, 1)), 1e-20)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('original')
    ap.add_argument('offvocal')
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--sr', type=int, default=44100)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sr = args.sr

    orig, orig_fmt = decode(args.original, sr)
    inst, inst_fmt = decode(args.offvocal, sr)
    a, b = orig.mean(1), inst.mean(1)
    lag0 = coarse_lag(a, b, sr)
    got = fine_lag(a, b, lag0, sr, len(a) / 2, span=max(16, sr // 4000 * 2), half=30.0)
    if got is None:
        raise SystemExit('the two files hardly overlap; is the off vocal of this song?')
    lag = got[0]
    centers, lags = lag_curve(a, b, lag, sr)
    shifted = warp(inst, centers, lags, len(orig), sr)

    gain = fit_gain(orig, shifted, sr)
    for _ in range(2):  # refit on the frames that cancel best, the parts without vocal
        ratio = frame_energy(orig - shifted * gain, sr) / np.maximum(frame_energy(shifted * gain, sr), 1e-20)
        keep = np.argsort(ratio)[:max(10, int(QUIET_SHARE * len(ratio)))]
        gain = fit_gain(orig, shifted, sr, keep)
    backing = shifted * gain
    vocal = orig - backing

    e_back, e_voc = frame_energy(backing, sr), frame_energy(vocal, sr)
    loud = e_back > e_back.max() * 1e-5  # frames where the backing plays
    depth = 10 * np.log10(np.maximum(e_voc[loud], 1e-20) / e_back[loud])
    p10, p50 = (float(np.percentile(depth, q)) for q in (10, 50))
    # the best 3 s where the backing plays: an intro or a break without vocal, which songs sung throughout
    # still have although under 10% of their frames
    w = int(round(3 / FRAME))
    sb, sv = (np.convolve(e, np.ones(w), 'valid') for e in (e_back, e_voc))
    ok = sb > sb.max() * 1e-3
    best = float(10 * np.log10(max((sv[ok] / sb[ok]).min(), 1e-20))) if ok.any() else 0.0
    verdict = ('cancels like the same master, lossless' if best <= -50 else
               'same master, limited by lossy coding' if best <= -20 else
               'does not cancel: a different mix or master')
    report = dict(
        original=dict(file=str(args.original), stream=orig_fmt, seconds=round(len(orig) / sr, 2),
                      cutoff_hz=cutoff(orig, sr)),
        offvocal=dict(file=str(args.offvocal), stream=inst_fmt, seconds=round(len(inst) / sr, 2),
                      cutoff_hz=cutoff(inst, sr)),
        delay_samples=round(lag, 3), delay_ms=round(1000 * lag / sr, 3),
        delay_curve=dict(points=len(lags), first=round(float(lags[0]), 2), last=round(float(lags[-1]), 2),
                         spread=round(float(lags.max() - lags.min()), 2),
                         largest_step=round(float(np.abs(np.diff(lags)).max()), 2) if len(lags) > 1 else 0.0),
        gain_db=[round(float(20 * np.log10(abs(g))), 3) for g in gain], polarity=[int(np.sign(g)) for g in gain],
        depth_p10_db=round(p10, 1), depth_p50_db=round(p50, 1), depth_best3s_db=round(best, 1), verdict=verdict)
    sf.write(str(out / 'vocal.wav'), vocal.astype(np.float32), sr, subtype='FLOAT')
    sf.write(str(out / 'inst.wav'), backing.astype(np.float32), sr, subtype='FLOAT')
    (out / 'offvocal.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    for k, v in report.items():
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
