"""
Clean inputs for the bake-off (README.md, 「干净输入」): studio recordings of singing with nothing else in them, in
place of the vocals separated from a mix that set/songs mostly holds. The user asked for them on 2026-10-25, after
hearing the separated inputs. Nothing here is aligned to an accompaniment; it tests the conversion alone.

    /root/autodl-tmp/conda_envs/ddsp/bin/python tools/bakeoff/clean_set.py prep|ddsp|show

prep: set/clean/<song>.wav and set/manifest_clean.json (for convert.py --manifest), from
  - Opencpop (one professional Mandarin female singer, 100 pop songs recorded whole in a studio, 44.1 kHz; the
    license is unverified, tools/clean_stems.md): the songs of OPENCPOP, from the archive in clean/dl/
  - GTSinger's JA-Soprano-1 (a Japanese female soprano, studio): the phrases of the Control_Group (normal singing)
    of the songs of GTSINGER, in order, joined by GAP s of silence, up to MAX_S
  - Moni Blue「April Blues」: the raw lead of its multitrack, as in set/songs
ddsp: her DDSP-SVC 40k for each (main_reflow.py, key 0 as the covers), matched in loudness to the input, into
      out/clean_ddsp40k/
show: her 转换结果 infer_out/clean/<song>/ for the review page, under their names (not blind, as the user asked):
      the input, then each system of SHOW that has it
"""
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_set import match_level, mono  # noqa: E402

B = Path('/root/autodl-tmp/bakeoff')
C = B / 'clean'
SET = B / 'set' / 'clean'
SPK = Path('/root/autodl-tmp/speakers/hanamaru_hareru')
REPO = Path(__file__).resolve().parents[2]
MODEL, SPK_ID = SPK / 'exp_all' / 'model_40000.pt', '1'
OPENCPOP = ('2001', '2044', '2086')  # song ids of the archive
GTSINGER = ('Breathy/心做し', 'Mixed_Voice_and_Falsetto/いつも何度でも')  # under Japanese/JA-Soprano-1/
GT_URL = 'https://hf-mirror.com/datasets/GTSinger/GTSinger/resolve/main/'
GT_API = 'https://hf-mirror.com/api/datasets/GTSinger/GTSinger/tree/main/'
GAP, MAX_S = 0.5, 180.0  # seconds
SHOW = (('1_DDSP4万步', 'clean_ddsp40k'), ('2_YingMusic整首转', 'clean_yingmusic'),
        ('3_YingMusic分句转', 'clean_yingmusic_phr'))


def fetch(url, timeout=60):
    """hf-mirror refuses Python's own user agent."""
    req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.81.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def opencpop():
    """{song: wav} of the whole songs of OPENCPOP, out of the archive."""
    want = {f'Opencpop/raw/wavs/{s}.wav': s for s in OPENCPOP}
    out = {}
    with tarfile.open(C / 'dl' / 'Opencpop.tar.gz') as tar:
        for m in tar:
            if m.name in want:
                dst = C / 'opencpop' / f'{want[m.name]}.wav'
                dst.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as f:
                    dst.write_bytes(f.read())
                out[f'opencpop_{want[m.name]}'] = dst
                if len(out) == len(want):
                    break
    missing = set(want.values()) - {k.split('_')[1] for k in out}
    if missing:
        sys.exit(f'not in the archive: {sorted(missing)}')
    return out


def gtsinger():
    """{song: wav} of the GTSINGER songs: their Control_Group phrases joined, downloaded once into clean/gtsinger/."""
    out = {}
    for path in GTSINGER:
        song = path.split('/')[-1]
        d = C / 'gtsinger' / song
        d.mkdir(parents=True, exist_ok=True)
        group = f'Japanese/JA-Soprano-1/{path}/Control_Group'
        names = sorted(f['path'].rsplit('/', 1)[-1] for f in json.loads(fetch(GT_API + urllib.parse.quote(group)))
                       if f['path'].endswith('.wav'))
        parts, sr, total = [], None, 0.0
        for n in names:
            if not (d / n).exists():
                (d / n).write_bytes(fetch(GT_URL + urllib.parse.quote(f'{group}/{n}'), 300))
            x, sr = sf.read(str(d / n), dtype='float32', always_2d=True)
            parts += [x.mean(1), np.zeros(int(GAP * sr), np.float32)]
            total += len(x) / sr + GAP
            if total >= MAX_S:
                break
        dst = d / f'{song}.wav'
        sf.write(str(dst), np.concatenate(parts), sr, subtype='PCM_16')
        out[song] = dst
    return out


def prep():
    SET.mkdir(parents=True, exist_ok=True)
    srcs = {**opencpop(), **gtsinger(), 'april_blues': Path('/root/autodl-tmp/clean_pilot/april_blues/lead.flac')}
    items = []
    for song, src in srcs.items():
        x, sr = mono(src)
        dst = SET / f'{song}.wav'
        sf.write(str(dst), x, sr, subtype='PCM_16')
        items.append({'name': f'song__{song}', 'kind': 'song', 'src_spk': song, 'input': str(dst)})
        print(f'{song}: {len(x) / sr:.0f} s from {src}')
    (B / 'set' / 'manifest_clean.json').write_text(json.dumps({'items': items}, ensure_ascii=False, indent=1),
                                                   encoding='utf-8')


def items():
    return json.loads((B / 'set' / 'manifest_clean.json').read_text(encoding='utf-8'))['items']


def ddsp():
    out = B / 'out' / 'clean_ddsp40k'
    out.mkdir(parents=True, exist_ok=True)
    for it in items():
        raw = out / f'{it["name"]}.raw.wav'
        subprocess.run([sys.executable, 'main_reflow.py', '-i', it['input'], '-m', str(MODEL), '-o', str(raw),
                        '-k', '0', '-id', SPK_ID], cwd=REPO, check=True, stdin=subprocess.DEVNULL)
        y, sr = mono(raw)
        sf.write(str(out / f'{it["name"]}.wav'), match_level(y, sr, it['input']), sr, subtype='PCM_16')
        raw.unlink()
        print(f'clean_ddsp40k: {it["name"]}', flush=True)


def show():
    root = SPK / 'infer_out' / 'clean'
    if root.exists():
        shutil.rmtree(root)
    for it in items():
        d = root / it['src_spk']
        d.mkdir(parents=True)
        x, sr = mono(it['input'])
        sf.write(str(d / '0_输入.flac'), x, sr, subtype='PCM_24')
        for label, system in SHOW:
            f = B / 'out' / system / f'{it["name"]}.wav'
            if f.exists():
                y, sr = mono(f)
                sf.write(str(d / f'{label}.flac'), y, sr, subtype='PCM_24')
        print(d, sorted(p.name for p in d.iterdir()))


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('prep', 'ddsp', 'show'):
        sys.exit(__doc__)
    {'prep': prep, 'ddsp': ddsp, 'show': show}[sys.argv[1]]()
