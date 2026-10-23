# Learned scores of the clean-input pilot's dry vocals (clean_pilot.sh): the raw lead, the lead separated from the
# official mix, and the two conversions of them, on the same 8 s windows where the raw lead sings (score_lines.py's
# SingMOS-Pro, Audiobox Aesthetics, DNSMOS; WavLM cosine to the speaker's own validation clips)
#   HF_HUB_OFFLINE=1 /root/autodl-tmp/conda_envs/evalq/bin/python clean_pilot_score.py <song dir> <speaker> <step>
import glob, os, sys
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
sys.path.insert(0, '/root/autodl-tmp/DDSP-SVC/tools/autodl')
import score_lines as sl

def load16(path):
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    return resample_poly(x.mean(1), sl.SR // 100, sr // 100).astype(np.float32)


def main():
    d, spk, step = sys.argv[1], sys.argv[2], sys.argv[3]
    s = os.path.basename(d.rstrip('/'))
    versions = {'原唱干声（干净输入）': f'{d}/lead.flac', '分离出的干声': f'{d}/sep/3_dereverb/{s}.wav',
                '干净输入→转换': f'{d}/conv_clean_{spk}_{step}.wav', '分离输入→转换': f'{d}/conv_sep_{spk}_{step}.wav'}
    audio = {k: load16(p) for k, p in versions.items()}
    n = min(len(x) for x in audio.values())
    lead = audio['原唱干声（干净输入）'][:n]
    win, hop = 8 * sl.SR, sl.SR // 100
    db = 20 * np.log10(np.sqrt(np.mean(lead[:n // hop * hop].reshape(-1, hop) ** 2, 1)) + 1e-9)
    active = db > np.percentile(db, 99) - 35
    starts = [i for i in range(0, n - win, win) if active[i // hop:(i + win) // hop].mean() > 0.6]
    print(f'{s}: {len(starts)} windows of 8 s where the raw lead sings')
    models = sl.load_models()

    def score(clips, k=4):
        # a few clips at a time: the GPU may be shared (another project's ComfyUI batches)
        return [r for i in range(0, len(clips), k) for r in sl.score_clips(models, clips[i:i + k])]

    ref = [load16(f) for f in sorted(glob.glob(f'/root/autodl-tmp/speakers/{spk}/data_all/val/audio/*.wav'))]
    centroid = np.mean([r['_emb'] for r in score(ref)], 0)
    centroid /= np.linalg.norm(centroid)
    keys = ('singmos', 'aes_pq', 'aes_ce', 'dns_sig', 'dns_bak', 'dns_ovrl')
    print(f'{"":20s} ' + ' '.join(f'{k:>8s}' for k in keys) + f' {"像" + spk:>10s}')
    for k, x in audio.items():
        rows = score([x[i:i + win] for i in starts])
        means = [np.mean([r[q] for r in rows]) for q in keys]
        cos = np.mean([float(r['_emb'] @ centroid) for r in rows])
        print(f'{k:20s} ' + ' '.join(f'{m:8.3f}' for m in means) + f' {cos:10.3f}', flush=True)
    models['dns_pool'].shutdown()


if __name__ == '__main__':  # the DNSMOS worker processes import this file again
    main()
