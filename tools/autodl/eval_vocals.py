"""
Acoustic check of the dry vocals: every song through the uvr stages (mix, vocals, dereverb, karaoke),
measured on the same frames, so each problem can be pinned on the step that made it. One JSON line per
song in <speaker>/eval/metrics.jsonl (resumable); rank_songs.py turns them into the ranking on the
review page. Runs in the ddsp env (parselmouth) and fits the 0.5 CPU core and 2 GB of no-GPU mode,
at about 0.1 x real time; --shard k/n runs every n-th song, for parallel runs on a GPU instance.

    python tools/autodl/eval_vocals.py [--shard k/n] /root/autodl-tmp/speakers/pheebie ...

What is measured, per song: pitch (Praat) of the dry vocals marks the sung frames; on those, level,
harmonic-to-valley ratio and its leftovers against the mix, what each step takes out (whole passages,
dropouts inside phrases), fast flutter on steady notes, long-term spectrum and bandwidth, sibilants and
breaths kept, 50-150 Hz leakage; in pauses while the mix plays, the residual level and how much it
looks like the accompaniment; reverb tails after phrase ends; stereo width.

'dry' is the final output and 'kar' the karaoke stage, which are the same folder since the denoise
step went (2026-10-20); the 'dn' figures (denoise) are then 0.
"""
import fcntl
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import parselmouth
import scipy.fft
import soundfile as sf
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import binary_dilation, binary_erosion, label
from scipy.signal import resample_poly, butter, sosfiltfilt

SR, NFFT, HOP = 44100, 2048, 441  # 10 ms frames, same step as the pitch track
FPS = SR / HOP
STAGES = {'mix': '0_input', 'voc': '1_vocals', 'derev': '2_dereverb', 'kar': '3_karaoke', 'dry': '3_karaoke'}
FREQS = np.fft.rfftfreq(NFFT, 1 / SR)
WIN = np.hanning(NFFT + 1)[:-1].astype(np.float32)
SCALE = 2.0 / (NFFT * NFFT * np.mean(WIN.astype(np.float64) ** 2))  # sum over bins = mean square (dBFS)
EDGES = np.geomspace(50, SR / 2, 49)  # 48 log bands; the lowest few hold no FFT bin
BAND_OF_BIN = np.clip(np.digitize(FREQS, EDGES) - 1, 0, 47)
BAND_MAT = np.zeros((len(FREQS), 48), np.float32)
BAND_MAT[np.arange(len(FREQS)), BAND_OF_BIN] = 1
BAND_MAT[FREQS < 50] = 0
EMPTY_BANDS = BAND_MAT.sum(0) == 0
HBANDS = [(0, 1500), (1500, 4000), (4000, 8000)]  # harmonic / valley bands
K8 = int(np.searchsorted(FREQS, HBANDS[-1][1]))  # the masks only need the bins below 8 kHz
INB = np.stack([(FREQS[:K8] >= lo) & (FREQS[:K8] < hi) for lo, hi in HBANDS], 1)
FLAT_BINS = (FREQS >= 100) & (FREQS <= 8000)
COARSE = [(50, 300), (300, 1000), (1000, 2000), (2000, 4000), (4000, 6000), (6000, 8000),
          (8000, 12000), (12000, 16000), (16000, 22050)]
HP15 = butter(4, 15, 'highpass', fs=FPS, output='sos')


def dB(p):
    return 10 * np.log10(np.maximum(p, 1e-12))


def load(path):
    if path.suffix.lower() != '.wav':  # the mixes in 0_input are the downloaded m4a files
        raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '2',
                              '-ar', str(SR), '-'], capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.float32).reshape(-1, 2)
    else:
        x, sr = sf.read(str(path), dtype='float32', always_2d=True)
        assert sr == SR, (path, sr)
    fd = os.open(path, os.O_RDONLY)  # the 2 GB limit counts page cache
    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    os.close(fd)
    return x


def pitch(xm):
    x8 = resample_poly(xm, 80, 441).astype(np.float64)  # 8 kHz is plenty for f0 up to 1100 Hz
    p = parselmouth.Sound(x8, 8000).to_pitch_ac(time_step=0.01, pitch_floor=100.0, pitch_ceiling=1100.0)
    f0, t = p.selected_array['frequency'], p.xs()
    n = 1 + len(xm) // HOP
    j = np.round((np.arange(n) / FPS - t[0]) / 0.01).astype(int)
    out = np.where((j >= 0) & (j < len(f0)), f0[np.clip(j, 0, len(f0) - 1)], 0.0)
    return out.astype(np.float32)


def features(sig, f0, vmask, n):
    """sig: stage -> mono signal. Per stage and frame: 48 band powers, harmonic peak / valley power
    density in HBANDS at f0, flatness; long-term spectrum over all frames and over vmask frames.
    The peak / valley masks depend only on f0, so they are built once for all stages. Empties sig."""
    pads = {k: np.pad(sig.pop(k)[:(n - 1) * HOP + 1], NFFT // 2, mode='reflect') for k in list(sig)}  # frees sig
    F = {k: dict(bands=np.zeros((n, 48), np.float32), hp=np.full((n, 3), np.nan, np.float32),
                 hv=np.full((n, 3), np.nan, np.float32), flat=np.zeros(n, np.float32),
                 ltas_all=np.zeros(len(FREQS)), ltas_v=np.zeros(len(FREQS))) for k in pads}
    for i0 in range(0, n, 512):
        i1 = min(n, i0 + 512)
        g = f0[i0:i1] > 0
        if g.any():
            fg = f0[i0:i1][g][:, None]
            h = FREQS[None, :K8] / fg
            frac = np.abs(h - np.round(h))
            ok = h >= 0.5
            peak = ((frac <= 0.1 + 22 / fg) & ok)[:, :, None] & INB[None]
            valley = ((frac >= 0.35) & ok)[:, :, None] & INB[None]
            pk = peak.astype(np.float32) / np.maximum(peak.sum(1, keepdims=True), 1)
            vl = valley.astype(np.float32) / np.maximum(valley.sum(1, keepdims=True), 1)
            idx = np.nonzero(g)[0] + i0
        vm = vmask[i0:i1]
        for k, xp in pads.items():
            seg = xp[i0 * HOP:(i1 - 1) * HOP + NFFT]
            fr = sliding_window_view(seg, NFFT)[::HOP][:i1 - i0] * WIN
            P = (np.abs(scipy.fft.rfft(fr, axis=1)) ** 2).astype(np.float32) * np.float32(SCALE)
            f = F[k]
            f['bands'][i0:i1] = P @ BAND_MAT
            f['flat'][i0:i1] = np.exp(np.log(P[:, FLAT_BINS] + 1e-14).mean(1)) / (P[:, FLAT_BINS].mean(1) + 1e-14)
            f['ltas_all'] += P.sum(0)
            f['ltas_v'] += P[vm].sum(0)
            if g.any():
                Pg = P[g, :K8]
                f['hp'][idx] = np.einsum('tk,tkb->tb', Pg, pk)
                f['hv'][idx] = np.einsum('tk,tkb->tb', Pg, vl)
    return F


def band_power(b, lo, hi):
    sel = (EDGES[:-1] >= lo * 0.999) & (EDGES[1:] <= hi * 1.001)
    return b[..., sel].sum(-1)


def glob_escape(name):
    return ''.join(f'[{c}]' if c in '*?[' else c for c in name)


def runs(mask, min_len):
    lab, k = label(mask)
    if not k:
        return []
    ends = np.nonzero(np.diff(np.r_[0, mask.astype(np.int8), 0]))[0]
    return [(s, e) for s, e in zip(ends[::2], ends[1::2]) if e - s >= min_len]


def med(x):
    x = np.asarray(x, np.float64)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if len(x) else None


def pct(x, q):
    x = np.asarray(x, np.float64)
    x = x[np.isfinite(x)]
    return float(np.percentile(x, q)) if len(x) else None


def stereo_stats(x):
    """L/R correlation and side/mid energy (dB), in float64 chunks to keep memory flat."""
    if x.shape[1] < 2:
        return 1.0, None
    lr = ll = rr = side = mid = 0.0
    for i in range(0, len(x), 1 << 20):
        L, R = x[i:i + (1 << 20), 0].astype(np.float64), x[i:i + (1 << 20), 1].astype(np.float64)
        lr, ll, rr = lr + L @ R, ll + L @ L, rr + R @ R
        side, mid = side + (L - R) @ (L - R), mid + (L + R) @ (L + R)
    return float(lr / np.sqrt(ll * rr + 1e-20)), float(10 * np.log10(max(side / max(mid, 1e-20), 1e-12)))


def ltas_cut(ltas):
    """long-term spectrum (dB re 1-2 kHz): highest frequency within 60 dB, and a codec-like cliff above
    8 kHz (more than 20 dB down within 1 kHz)."""
    L = dB(np.convolve(ltas / max(ltas.sum(), 1e-20), np.ones(9) / 9, mode='same'))
    L = L - L[(FREQS >= 1000) & (FREQS < 2000)].mean()
    above = np.nonzero(L > -60)[0]
    f60 = float(FREQS[above[-1]]) if len(above) else None
    step = int(round(1000 / FREQS[1]))
    cliff = next((float(FREQS[k]) for k in np.nonzero(FREQS >= 8000)[0]
                  if k + step < len(L) and L[k] - L[k + step] > 20), None)
    return f60, cliff


def analyse(work, name):
    t0 = time.time()
    m = {'name': name}
    sig = {}
    for k in ['dry', 'derev', 'mix', 'voc', 'kar']:
        if k != 'dry' and STAGES[k] == STAGES['dry']:
            sig[k] = sig['dry']
            continue
        x = load(next((work / STAGES[k]).glob(f'{glob_escape(name)}.*')) if k == 'mix'
                 else work / STAGES[k] / f'{name}.wav')
        if k == 'dry':
            peak = max(float(x.max()), -float(x.min()))
            m['dry_peak_db'] = float(dB(peak ** 2))
            m['dry_clip'] = int(sum((np.abs(x[i:i + (1 << 20)]) >= 0.999).sum() for i in range(0, len(x), 1 << 20)))
        if k in ('dry', 'voc'):
            m[f'{k}_corr'], m[f'{k}_side_db'] = stereo_stats(x)
        sig[k] = x.mean(1)
        del x
    n = 1 + min(len(x) for x in sig.values()) // HOP
    fd, fr = pitch(sig['dry'])[:n], pitch(sig['derev'])[:n]
    vd, vr = fd > 0, fr > 0  # the dry pitch marks the sung frames every stage is measured on
    F = features(sig, fd, vd, n)
    del sig
    E = {k: dB(F[k]['bands'].sum(1)) for k in F}
    m['sec'] = n / FPS
    m['voiced_sec'] = float(vd.sum() / FPS)
    if vd.sum() < 500:
        m['skip'] = 'under 5 s sung'
        return m
    vmin = vd.sum() / FPS / 60

    # level and voice profile
    m['dry_level'] = med(E['dry'][vd])
    m['f0_p5'], m['f0_p50'], m['f0_p95'] = (pct(fd[vd], q) for q in (5, 50, 95))
    midi = np.round(69 + 12 * np.log2(fd[vd] / 440)).astype(int)
    m['midi_hist'] = {int(k): int(c) for k, c in zip(*np.unique(midi, return_counts=True))}
    bd = F['dry']['bands']
    cent_f = np.sqrt(EDGES[:-1] * EDGES[1:])
    m['centroid'] = med((bd[vd] * cent_f).sum(1) / np.maximum(bd[vd].sum(1), 1e-20))
    m['bright_db'] = med(dB(band_power(bd[vd], 2000, 5000)) - dB(band_power(bd[vd], 50, 2000)))

    # gaps: no singing within 0.35 s while the mix plays
    active = E['mix'] > np.percentile(E['mix'], 99) - 50
    gap = ~binary_dilation(vd, np.ones(71, bool)) & active
    m['gap_sec'] = float(gap.sum() / FPS)
    if gap.sum() >= 100:
        for k in F:
            m[f'gap_rel_{k}'] = med(E[k][gap]) - med(E[k][vd])
            if k != 'mix':
                m[f'leak_{k}'] = med(E[k][gap] - E['mix'][gap])
        m['gap_abs_dry'] = med(E['dry'][gap])
        m['gap_p90_rel_dry'] = pct(E['dry'][gap], 90) - m['dry_level']
        m['gap_silent_frac'] = float(np.mean(E['dry'][gap] < -90))
        sel = (EDGES[:-1] >= 100) & (EDGES[1:] <= 8000)
        live = gap & (E['dry'] > -90)
        m['gap_live_sec'] = float(live.sum() / FPS)
        if live.sum() >= 50:
            a = np.log(F['dry']['bands'][live][:, sel] + 1e-14)
            b = np.log(F['mix']['bands'][live][:, sel] + 1e-14)
            a, b = a - a.mean(1, keepdims=True), b - b.mean(1, keepdims=True)
            m['ghost_corr'] = med((a * b).sum(1) / np.sqrt((a * a).sum(1) * (b * b).sum(1) + 1e-20))
            m['gap_flat_dry'] = med(F['dry']['flat'][live])
            m['gap_live_rel_dry'] = med(E['dry'][live]) - m['dry_level']

    # while singing: harmonic-to-valley ratio (accompaniment, harmonies, reverb and noise fill the
    # valleys), and how far the valleys are below the mix's (what is left of the accompaniment there)
    for k in F:
        for b in range(3):
            m[f'hvr{b}_{k}'] = med(dB(F[k]['hp'][vd, b]) - dB(F[k]['hv'][vd, b]))
            if k != 'mix':
                m[f'vleak{b}_{k}'] = med(dB(F[k]['hv'][vd, b]) - dB(F['mix']['hv'][vd, b]))

    # drums under the voice: the accompaniment's 8-16 kHz attacks (hi-hat, snare; accompaniment = mix
    # minus vocals, per band) on sung frames, and how much stronger a stage's own 8-16 kHz attacks are on
    # those frames than on the other sung frames (1 = not at all). Bass / kick: her f0 is above 180 Hz,
    # so 50-150 Hz in a vocal stage while singing is mostly leakage.
    def flux(p):
        h = dB(p)
        return np.maximum(np.diff(h, prepend=h[0]), 0)
    hf8 = {k: band_power(F[k]['bands'], 8000, 16000) for k in F}
    acc = np.maximum(hf8['mix'] - hf8['voc'], 0)
    fa = flux(acc + 1e-10)
    sel = vd & (dB(acc) > E['mix'] - 40)
    if sel.sum() >= 500:
        hits = sel & (fa >= np.percentile(fa[sel], 95)) & (fa > 6)
        m['drum_hits'] = int(hits.sum())
        if hits.sum() >= 30:
            for k in ['voc', 'derev', 'kar', 'dry']:
                fk = flux(hf8[k])
                m[f'drum_follow_{k}'] = float(fk[hits].mean() / max(fk[sel & ~hits].mean(), 1e-6))
    for k in ['voc', 'derev', 'kar', 'dry']:
        lo = dB(band_power(F[k]['bands'], 50, 150))
        m[f'low_leak_{k}'] = med(lo[vd] - dB(band_power(F['mix']['bands'], 50, 150))[vd])
        m[f'low_rel_{k}'] = med(lo[vd] - E[k][vd])

    # what each step removes from sung frames (pitch of the dereverbed vocals, before harmonies go)
    loud = vr & (E['derev'] > med(E['derev'][vr]) - 25)
    d_kar = E['kar'][loud] - E['derev'][loud]
    m['kar_removed'] = float(np.mean(d_kar < -12))
    hi = fr[loud] > 650
    m['hi_frac'] = float(np.mean(hi))
    m['kar_removed_hi'] = float(np.mean(d_kar[hi] < -12)) if hi.sum() >= 100 else None
    m['kar_removed_lo'] = float(np.mean(d_kar[~hi] < -12)) if (~hi).sum() >= 100 else None
    keep = loud.copy()
    keep[loud] = d_kar >= -12
    d_dn = E['dry'][keep] - E['kar'][keep]
    m['dn_removed'] = float(np.mean(d_dn < -10))
    m['dn_gain'] = med(d_dn)
    m['dr_gain'] = med(E['derev'][loud] - E['voc'][loud])
    m['dr_removed'] = float(np.mean(E['derev'][loud] - E['voc'][loud] < -12))
    m['kar_gain'] = med(d_kar)

    # whole passages a step takes out: loud in its input (within 15 dB of the singing), 20 dB down in
    # its output; 'tonal' when the input there is harmonic (low flatness), i.e. likely voice
    for a, b, tag in [('voc', 'derev', 'dr'), ('derev', 'kar', 'kar'), ('kar', 'dry', 'dn')]:
        inp = E[a] > med(E[a][vd]) - 15
        cut = inp & (E[b] < E[a] - 20)
        tonal = cut & (F[a]['flat'] < 0.05)
        m[f'cut_{tag}_sec'] = float(cut.sum() / FPS)
        m[f'cut_{tag}_tonal_sec'] = float(tonal.sum() / FPS)
        m[f'in_{tag}_sec'] = float(inp.sum() / FPS)
        long = runs(binary_dilation(tonal, np.ones(21, bool)), 50)  # passages, bridging 0.1 s gaps
        m[f'cut_{tag}_at'] = [[round(s0 / FPS, 1), round((e0 - s0) / FPS, 1)]
                              for s0, e0 in sorted(long, key=lambda r: r[0] - r[1])[:5]]

    # dropouts inside phrases, per step
    phr = runs(vr, 30)
    for a, b, tag in [('derev', 'voc', 'dr'), ('kar', 'derev', 'kar'), ('dry', 'kar', 'dn')]:
        holes = 0
        for s, e in phr:
            r = E[a][s:e] - E[b][s:e]
            holes += label(r < np.median(r) - 10)[1]
        m[f'holes_{tag}_pm'] = holes / vmin

    # fast flutter of the harmonics on steady notes (vibrato is 5-7 Hz; above 15 Hz is processing or
    # roughness), on frames away from note changes
    st = 12 * np.log2(np.maximum(fd, 1) / 440)
    steady = vd.copy()
    steady[2:-2] &= np.abs(st[4:] - st[:-4]) < 1.0
    steady = binary_erosion(steady, np.ones(7, bool))
    sus = runs(steady, 35)
    m['steady_sec'] = float(sum(e - s for s, e in sus) / FPS)
    for k in F:
        for b, tag in [(1, 'mid'), (2, 'hf')]:
            vals, wts = [], []
            for s, e in sus:
                h = dB(F[k]['hp'][s:e, b].astype(np.float64))
                if np.isfinite(h).all():
                    vals.append(np.sqrt(np.mean(sosfiltfilt(HP15, h - h.mean()) ** 2)))
                    wts.append(e - s)
            m[f'flutter_{tag}_{k}'] = float(np.average(vals, weights=wts)) if vals else None

    # long-term spectrum of the sung frames, dB re 1-2 kHz
    for k in F:
        b = F[k]['bands'][vd].sum(0)
        ref = band_power(b, 1000, 2000)
        m[f'ltas_{k}'] = [None if e else round(float(v), 1) for v, e in zip(dB(b) - dB(ref), EMPTY_BANDS)]
        m[f'coarse_{k}'] = [round(float(dB(band_power(b, lo, hi)) - dB(ref)), 1) for lo, hi in COARSE]
    m['cut_mix'] = ltas_cut(F['mix']['ltas_all'])
    m['cut_voc'] = ltas_cut(F['voc']['ltas_v'])
    m['cut_dry'] = ltas_cut(F['dry']['ltas_v'])

    # sibilants (s, sh, ts): unvoiced, near singing, mostly 4-12 kHz, in the karaoke output
    near = binary_dilation(vr, np.ones(61, bool)) & ~vr
    hf = {k: band_power(F[k]['bands'], 4000, 12000) for k in F}
    S = near & (hf['kar'] / np.maximum(F['kar']['bands'].sum(1), 1e-20) > 0.5) & (E['kar'] > med(E['kar'][vr]) - 35)
    m['sib_sec_pm'] = float(S.sum() / FPS / vmin)
    if S.sum() >= 30:
        m['sib_keep_dn'] = med(dB(hf['dry'][S]) - dB(hf['kar'][S]))
        m['sib_keep_kar'] = med(dB(hf['kar'][S]) - dB(hf['derev'][S]))
        m['sib_keep_dr'] = med(dB(hf['derev'][S]) - dB(hf['voc'][S]))
        m['sib_rel_dry'] = med(dB(hf['dry'][S])) - m['dry_level']

    # breaths: unvoiced frames 60-350 ms before a phrase that follows a pause
    B = np.zeros(n, bool)
    for s, e in phr:
        if s >= 35 and not vr[s - 25:s].any():
            B[s - 35:s - 6] = True
    B &= ~vr & (E['kar'] > med(E['kar'][vr]) - 40)
    m['breath_sec_pm'] = float(B.sum() / FPS / vmin)
    if B.sum() >= 30:
        m['breath_keep_dn'] = med(E['dry'][B] - E['kar'][B])
        m['breath_keep_kar'] = med(E['kar'][B] - E['derev'][B])
        m['breath_keep_dr'] = med(E['derev'][B] - E['voc'][B])
        m['breath_rel_dry'] = med(E['dry'][B]) - m['dry_level']

    # reverb tails after phrase ends followed by 0.6 s of pause
    ends = [e for s, e in phr if e + 60 <= n and not vr[e:e + 60].any() and not vd[e:e + 60].any()]
    m['n_ends'] = len(ends)
    if len(ends) >= 5:
        for k in ['voc', 'derev', 'kar', 'dry']:
            p = F[k]['bands'].sum(1)
            m[f'tail150_{k}'] = med([dB(p[e + 10:e + 20].mean()) - dB(p[e - 10:e].mean()) for e in ends])
            m[f'tail350_{k}'] = med([dB(p[e + 30:e + 40].mean()) - dB(p[e - 10:e].mean()) for e in ends])
    m['secs'] = round(time.time() - t0, 1)
    return m


def read_done(path):
    done = set()
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                done.add(json.loads(line)['name'])
            except (ValueError, KeyError):  # a line cut off by a shutdown: that song is redone
                pass
    return done


def main():
    """eval_vocals.py [--shard k/n] <speaker dir>... : shard k of n runs every n-th song (parallel runs)."""
    args = sys.argv[1:]
    k, n = 0, 1
    if args and args[0] == '--shard':
        k, n = map(int, args[1].split('/'))
        args = args[2:]
    todo = []
    for d in args:
        spk = Path(d)
        (spk / 'eval').mkdir(exist_ok=True)
        path = spk / 'eval' / 'metrics.jsonl'
        done = read_done(path)
        names = sorted(f.stem for f in (spk / 'work' / STAGES['dry']).glob('*.wav'))
        print(f'{spk.name}: {len(done)} done, {len(names) - len(done)} to do', flush=True)
        todo += [(spk, path, x) for x in names if x not in done]
    random.Random(0).shuffle(todo)  # both speakers, spread over the song lists: partial results stay fair
    todo = todo[k::n]
    for i, (spk, path, name) in enumerate(todo, 1):
        try:
            m = analyse(spk / 'work', name)
        except Exception as e:  # keep going; the line says what failed
            m = {'name': name, 'error': repr(e)}
        line = json.dumps(m, ensure_ascii=False) + '\n'
        with open(path, 'a', encoding='utf-8') as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # parallel shards append to the same file
            f.write(line)
        print(f'{i}/{len(todo)} {spk.name} {name} {m.get("secs", m.get("error"))}', flush=True)


if __name__ == '__main__':
    main()
