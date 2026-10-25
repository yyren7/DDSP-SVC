"""
Mix of a cover: the off vocal as aligned by tools/offvocal.py, the converted lead vocal, and the original's
backing vocals, with the lead's reverb rebuilt at the level the original had.

    python tools/cover_mix.py --inst inst.wav --source vocal.wav --vocals 1_vocals/x.wav --lead 2_karaoke/x.wav \
        --dry 3_dereverb/x.wav --conv converted.wav -o mix.wav [--no-backing]

--source is offvocal.py's vocal.wav, --vocals the vocal separated from it (lead and backing), --lead what the
karaoke models keep of it, --dry the lead after dereverb, --conv the dry lead converted by main_reflow.py. The
separator scales a file whose peak is over 0.9 down to 0.9 before it separates it, and original - off vocal
often peaks over 1, so the stems are first brought back to the level they have in --source. The converted lead
is EQ'd to the spectral balance of the dry lead, octave by octave (a conversion comes out darker than the
singer it stands in for, 2-5 dB less at 2-4 kHz, and at the same loudness sinks into the off vocal), and gets a
synthetic room of REVERB_T60 seconds, as loud against it, octave by octave, as the dereverb step's removal
(lead - dry) was against the dry lead; the two together take the loudness (BS.1770) of the lead. The backing
(vocals - lead) stays as sung, and the converted parts then take one more common gain, so that the vocals of the
mix are as loud as the original's vocals they stand in for: a backing that doubles the lead adds up louder with
the original lead than with the converted one. The sum comes down by a fixed gain and goes through a peak limiter
at -1 dBFS (limit). All files at the same sample rate.

With --harm-conv (and --harm-source, --harm-dry, --harm-wet) the backing vocals are converted too: when an off
vocal with the chorus and one without it are both official, their difference is the backing vocals alone
(offvocal.py), which go through dereverb and conversion like the lead. --inst is then the off vocal without the
chorus; backing that was in neither off vocal (vocals - lead) is still added as sung unless --no-backing. A
converted voice is put in the middle, where the lead is; stacked backing is mostly spread wide (left and right
holding different voices), so with --harm-stereo --harm-conv is the left and the right channel converted one by
one, and stays where they were.

@file reads arguments from a file, any number to a line (no spaces inside a path): the settings chosen by ear
for a song are kept that way, as covers/<song>/mix.args, to mix it again the same (tools/README.md).
"""
import argparse

import numpy as np
import soundfile as sf
from scipy import signal

REVERB_T60 = 1.4  # seconds
PREDELAY = 0.02   # seconds
OCTAVES = 125 * 2 ** np.arange(8)  # band centres in Hz, 125 Hz to 16 kHz, over which the reverb follows the original's
MATCH_MAX = 6.0  # dB: the most the match EQ moves an octave of the converted voice
PEAK = 10 ** (-1 / 20)  # ceiling of the limiter: -1 dBFS
LIMIT_RELEASE = 0.05    # seconds over which the limiter's gain goes down before a peak and back up after it
LIMIT_SHARE = 0.01      # share of 20 ms frames the limiter may still pull down by more than 1 dB after the fixed gain


def load(path):
    x, sr = sf.read(str(path), dtype='float64', always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], sr


def fit(x, n):
    return x[:n] if len(x) >= n else np.pad(x, ((0, n - len(x)), (0, 0)))


def kweight(x, sr):
    """The K filter of ITU-R BS.1770: a +4 dB shelf above about 1.5 kHz, then a high-pass at 38 Hz."""
    A, w = 10 ** (4 / 40), 2 * np.pi * 1500 / sr
    c, r = np.cos(w), 2 * np.sqrt(A) * np.sin(w) / np.sqrt(2)  # r = 2 sqrt(A) alpha, Q = 1/sqrt(2)
    shelf = ([A * ((A + 1) + (A - 1) * c + r), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - r)],
             [(A + 1) - (A - 1) * c + r, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - r])
    w = 2 * np.pi * 38 / sr
    al, c = np.sin(w), np.cos(w)
    highpass = ([(1 + c) / 2, -(1 + c), (1 + c) / 2], [1 + al, -2 * c, 1 - al])
    for b, a in (shelf, highpass):
        x = signal.lfilter(b, a, x, axis=0)
    return x


def loudness(x, sr):
    """Integrated loudness (LUFS) after ITU-R BS.1770: K-weighted 400 ms blocks every 100 ms, gated at -70 LUFS
    and then 10 LU under their mean, so that pauses do not count and a darker voice is not taken for a louder one
    as plain RMS would; -inf when nothing is over the gate."""
    y = kweight(x, sr) ** 2
    cs = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y, axis=0)])
    w, h = int(0.4 * sr), int(0.1 * sr)
    s = np.arange(0, len(y) - w + 1, h)
    e = ((cs[s + w] - cs[s]) / w).sum(axis=1)
    e = e[e > 10 ** ((-70 + 0.691) / 10)]
    if not len(e):
        return -np.inf
    e = e[e > e.mean() / 10]
    return float(-0.691 + 10 * np.log10(e.mean()))


def limit(x, sr):
    """(x under PEAK, the fixed gain, the limiter's deepest gain): the off vocal is mastered to full scale
    already, and in a dense passage the vocals on top push every beat over it; a limiter alone would then duck
    the whole mix on every beat, which is heard as thumping. So the mix first comes down by the fixed gain that
    leaves only LIMIT_SHARE of its 20 ms frames needing more than 1 dB from the limiter. The limiter: the gain
    each sample needs to stay under PEAK, held as a minimum over 2*LIMIT_RELEASE and then averaged over
    LIMIT_RELEASE, which keeps it under the need at every peak while it glides down before the peak and back up
    after it."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    raw = PEAK / np.maximum(np.abs(x).max(axis=1), 1e-12)
    n = int(0.02 * sr)
    frames = raw[:len(raw) // n * n].reshape(-1, n).min(axis=1)
    fixed = min(1.0, float(np.quantile(frames, LIMIT_SHARE)) * 10 ** (1 / 20))
    need = np.minimum(1.0, raw / fixed)
    r = max(1, int(LIMIT_RELEASE * sr))
    gain = uniform_filter1d(minimum_filter1d(need, size=2 * r + 1), size=r)
    return x * (fixed * gain)[:, None], fixed, float(gain.min())


def restore(source, stem):
    """The gain that brings a stem back to its level inside the file it was separated from: least squares over
    the whole song, as what the separation took out of `source` is uncorrelated with what it kept."""
    s, t = source.mean(axis=1), stem.mean(axis=1)
    return float((s * t).sum() / max((t * t).sum(), 1e-20))


def octaves(x, sr):
    """Energy of a stereo signal in each band of OCTAVES (Welch)."""
    f, p = signal.welch(x, sr, nperseg=8192, axis=0)
    p = p.sum(axis=1)
    return np.array([p[(f >= c / np.sqrt(2)) & (f < c * np.sqrt(2))].sum() for c in OCTAVES])


def match(x, ref, sr, most=MATCH_MAX):
    """(x EQ'd so that its balance follows `ref` octave by octave, the gains in dB): its overall energy stays, each
    octave moves at most `most` dB (0: no EQ), and the lowest and highest only go down, as there `ref` holds rumble,
    bleed and the lossy source's cutoff more than voice. Linear phase, no delay."""
    if most <= 0:
        return x, np.zeros(len(OCTAVES))
    px = octaves(x, sr)
    db = 10 * np.log10(np.maximum(octaves(ref, sr), 1e-30) / np.maximum(px, 1e-30))
    db -= 10 * np.log10((px * 10 ** (db / 10)).sum() / max(px.sum(), 1e-30))
    db[[0, -1]] = np.minimum(db[[0, -1]], 0)
    db = np.clip(db, -most, most)
    n = 8193
    f = np.fft.rfftfreq(n, 1 / sr)
    gain = 10 ** (np.interp(np.log2(np.maximum(f, 1)), np.log2(OCTAVES), db) / 20)
    h = np.roll(np.fft.irfft(gain, n), n // 2) * np.hanning(n)
    return signal.fftconvolve(x, h[:, None], mode='same', axes=0), db


def balance(conv, kept, ref, sr, lift=0.0):
    """The gain on the converted parts `conv` that makes them, with what stays as sung (`kept`), `lift` dB louder
    (BS.1770) than `ref`, the original parts they stand in for: bisection over +-12 dB."""
    target, lo, hi = loudness(ref, sr) + lift, -12.0, 12.0
    for _ in range(16):
        mid = (lo + hi) / 2
        if loudness(10 ** (mid / 20) * conv + kept, sr) < target:
            lo = mid
        else:
            hi = mid
    return 10 ** ((lo + hi) / 40)


def room(sr, ratio, seed=0):
    """Stereo impulse response: decorrelated noise decaying 60 dB in REVERB_T60, after PREDELAY, with as much
    energy in each band of OCTAVES as `ratio` says, so that a voice through it comes out that much weaker there."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(1.5 * REVERB_T60 * sr)) / sr
    ir = rng.standard_normal((len(t), 2)) * (10 ** (-3 * t / REVERB_T60))[:, None]
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True))  # white at unit energy: as loud as the voice in every band
    f = np.fft.rfftfreq(len(ir), 1 / sr)
    db = np.interp(np.log2(np.maximum(f, 1)), np.log2(OCTAVES), 10 * np.log10(ratio))
    ir = np.fft.irfft(np.fft.rfft(ir, axis=0) * 10 ** (db / 20)[:, None], n=len(ir), axis=0)
    return np.concatenate([np.zeros((int(PREDELAY * sr), 2)), ir])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 fromfile_prefix_chars='@')
    ap.convert_arg_line_to_args = str.split
    for name in ('inst', 'source', 'vocals', 'lead', 'dry', 'conv'):
        ap.add_argument(f'--{name}', required=True)
    ap.add_argument('-o', '--out', required=True)
    ap.add_argument('--no-backing', action='store_true', help="leave out the original singer's backing vocals")
    ap.add_argument('--lift', type=float, default=0.0,
                    help='dB the vocals of the mix sit above the original\'s against the off vocal (a converted voice '
                         'cuts through less than the singer it stands in for)')
    ap.add_argument('--eq-max', type=float, default=MATCH_MAX,
                    help=f'dB the match EQ may move an octave of a converted voice (default {MATCH_MAX:g}; 0: no EQ)')
    ap.add_argument('--harm-conv', help='the backing vocals converted as well (they then replace the original ones)')
    ap.add_argument('--harm-source', help="the backing vocals as offvocal.py wrote them, which --harm-wet was "
                                          "separated from")
    ap.add_argument('--harm-dry', help='the backing vocals after dereverb, for the level of their reverb')
    ap.add_argument('--harm-wet', help='the backing vocals before dereverb, whose loudness --harm-conv and its '
                                       'reverb take')
    ap.add_argument('--harm-stereo', action='store_true',
                    help="--harm-conv holds each channel converted on its own: kept as it is, not put in the middle")
    ap.add_argument('--harm-gain', type=float, default=0.0,
                    help="dB on the converted backing against the original's (negative: quieter, which also hides "
                         "where its conversion went wrong); the lead keeps its level")
    args = ap.parse_args()
    if args.harm_conv and not (args.harm_source and args.harm_dry and args.harm_wet):
        raise SystemExit('--harm-conv needs --harm-source, --harm-dry and --harm-wet')

    inst, sr = load(args.inst)

    def read(names):
        parts = []
        for name in names:
            x, r = load(getattr(args, name))
            if r != sr:
                raise SystemExit(f'{getattr(args, name)}: {r} Hz, the off vocal has {sr}')
            parts.append(fit(x, len(inst)))
        return parts

    source, vocals, lead, dry, conv = read(('source', 'vocals', 'lead', 'dry', 'conv'))
    g = restore(source, vocals)
    vocals, lead, dry = g * vocals, g * lead, g * dry

    conv, wet, wet_level, eq = voice(conv, dry, lead, sr, seed=0, eq_max=args.eq_max)
    kept = np.zeros_like(inst) if args.no_backing else vocals - lead  # the original singer's backing, as sung
    ref = lead + kept  # the original parts that the vocals of the mix stand in for
    if args.harm_conv:
        hsource, hconv, hdry, hwet = read(('harm_source', 'harm_conv', 'harm_dry', 'harm_wet'))
        hg = restore(hsource, hwet)
        hk = 10 ** (args.harm_gain / 20)  # also on the original backing that the balance aims at, so the lead stays
        ref, what = ref + hk * hg * hwet, 'converted'
        hconv, hwet, _, _ = voice(hconv, hg * hdry, hg * hwet, sr, seed=1, eq_max=args.eq_max, stereo=args.harm_stereo)
        hconv, hwet = hk * hconv, hk * hwet
        # whatever backing the karaoke models still found next to the lead was in neither off vocal: it stays
        # as sung (nothing when original - chorus off vocal was the lead alone)
    else:
        hconv = hwet = np.zeros_like(inst)
        what = 'off' if args.no_backing else 'as sung'
    k = balance(conv + wet + hconv + hwet, kept, ref, sr, args.lift)
    conv, wet, backing = k * conv, k * wet, k * (hconv + hwet) + kept

    mix, fixed, deepest = limit(inst + conv + wet + backing, sr)
    sf.write(args.out, np.clip(mix, -1, 1).astype(np.float32), sr, subtype='PCM_24')
    level = loudness(backing, sr) - loudness(conv, sr)
    print(f'{args.out}: stems {20 * np.log10(g):+.1f} dB back to the source'
          f'{f" (backing {20 * np.log10(hg):+.1f} dB)" if args.harm_conv else ""}, '
          f'EQ {"/".join(f"{x:+.0f}" for x in eq)} dB, reverb {wet_level:.1f} dB against the lead, '
          f'backing {what}{f" {level:.1f} dB" if what != "off" else ""}, '
          f'vocals {20 * np.log10(k):+.1f} dB to {f"{args.lift:+g} dB over " if args.lift else ""}the original\'s, '
          f'mix {20 * np.log10(fixed):+.1f} dB, then the limiter at most {20 * np.log10(deepest):.1f} dB')


def voice(conv, dry, wet_ref, sr, seed, eq_max=MATCH_MAX, stereo=False):
    """(converted voice in the middle, or where its channels have it with `stereo`, its synthetic reverb, the
    reverb's loudness against the voice in dB, the voice's EQ in dB): the voice EQ'd to the balance of `dry` (match, at most eq_max dB an octave), the two together as loud (BS.1770) as the
    voice was before dereverb (`wet_ref`), the reverb as loud against the voice, octave by octave, as the dereverb
    step's removal (wet_ref - dry) was against `dry`, but never louder than the voice. Original reverbs are mostly
    cut low and bright, a plain room would muddy the voice; of stacked backing vocals a dereverb model takes out
    much of the voices themselves, 10 dB and more, which the cap keeps from turning into reverb. In the lowest band
    the removal is rumble and bleed more than reverb, so it takes no more than the next."""
    conv, eq = match(conv if stereo else conv.mean(axis=1, keepdims=True).repeat(2, axis=1), dry, sr, eq_max)
    ratio = np.minimum(octaves(wet_ref - dry, sr) / np.maximum(octaves(dry, sr), 1e-30), 1.0)
    ratio[0] = min(ratio[0], ratio[1])
    ir = room(sr, np.maximum(ratio, 1e-6), seed)
    wet = np.stack([signal.fftconvolve(conv[:, c], ir[:, c])[:len(conv)] for c in range(2)], axis=1)
    k = 10 ** ((loudness(wet_ref, sr) - loudness(conv + wet, sr)) / 20)
    return k * conv, k * wet, loudness(wet, sr) - loudness(conv, sr), eq


if __name__ == '__main__':
    main()
