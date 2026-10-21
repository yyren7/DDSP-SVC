"""
Leave whole songs out when the original has heavy reverb or loud BGM (2026-10-21, the listener: "先剔除一些
混响太大，bgm太吵的曲子"). The measurements come from the frames of eval_lines.py:

    drr_db  direct-to-reverberant ratio inside the lines: 10 log10(sum P_derev / sum (P_in - P_derev)),
            i.e. against what the dereverb step took out of its input, lower = wetter: the separated vocals
            on the earlier chain (vocals -> dereverb -> karaoke), the lead on the current one (stages.py)
    bgm_db  median over sung frames of the mix minus the separated vocals: accompaniment against the voice

pheebie and sakura_shunka were measured on the earlier chain and left out before the current one ran;
hanamaru_hareru (2026-10-22) on the current chain, so --apply also moves the separated stages and frames of
her songs that are out, which the lines job and build_clips.py would otherwise still take.

On the songs the listener named (2026-10-20) drr_db put "原曲混响太大" 31st and "混响开太大，应剔除" 74th
of 362, bgm_db put "原曲 BGM 太吵" 1st, and the song "背景和混响大，但还能用" 274th and 160th.

    python tools/autodl/exclude_sources.py [--apply] <speaker dir>...

Songs among the wettest REVERB_PCT % or the loudest BGM_PCT % of all speakers given are listed with their
measurements in <speaker>/raw_songs_excluded/_excluded.tsv; --apply also moves their files from raw_songs/
there (outside raw_songs, which prepare_dataset.py reads recursively), and their stage outputs and frames
to raw_songs_excluded/_separated/. Moving the files back restores the song.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stages import DIRS, INPUT  # noqa: E402

REVERB_PCT, BGM_PCT = 20, 5  # with these about 7 h of sung lines stay per speaker (DDSP-SVC asks for ~1000 clips)
FPS = 100
AUDIO_EXTS = {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.opus', '.aac', '.wma'}


def song_name(f):
    return re.sub(r'\s+', '_', f.stem)  # prepare_dataset.unique_names, for names that are unique already


def measure(spk):
    lines = {}
    for l in (spk / 'eval' / 'lines.jsonl').read_text(encoding='utf-8').splitlines():
        m = json.loads(l)
        lines.setdefault(m['song'], []).append(m)
    rows = {}
    for f in sorted((spk / 'eval' / 'frames').glob('*.npz')):
        z = np.load(f)
        if 'E_derev' not in z.files:
            continue
        # the current chain stamps itself into the file; the earlier one dereverbed the separated vocals and
        # took the pitch of its last step, the karaoke output
        current = 'chain' in z.files
        ein, ed, ev, em = (z[k].astype(np.float64) for k in
                           (f'E_{INPUT["derev"]}' if current else 'E_voc', 'E_derev', 'E_voc', 'E_mix'))
        pi, pd = 10 ** (ein / 10), 10 ** (ed / 10)
        inside = np.zeros(len(ev), bool)
        for m in lines.get(f.stem, []):
            inside[int(m['start'] * FPS):int(m['end'] * FPS)] = True
        sung = z['f0_dry' if current else 'f0_kar'].astype(np.float32) > 0
        if inside.sum() < 300 or sung.sum() < 300:
            continue
        rows[f.stem] = {'drr_db': float(10 * np.log10(pd[inside].sum() / max((pi - pd)[inside].clip(0).sum(), 1e-12))),
                        'bgm_db': float(np.median((em - ev)[sung])),
                        'sung_h': sum(m['dur'] for m in lines.get(f.stem, [])) / 3600}
    return rows


def main():
    args = sys.argv[1:]
    apply = bool(args) and args[0] == '--apply'
    spks = [Path(d) for d in (args[1:] if apply else args)]
    rows = {spk: measure(spk) for spk in spks}
    drr = [r['drr_db'] for rs in rows.values() for r in rs.values()]
    bgm = [r['bgm_db'] for rs in rows.values() for r in rs.values()]
    if not drr:
        sys.exit('no frames to measure')
    d_cut, b_cut = np.percentile(drr, REVERB_PCT), np.percentile(bgm, 100 - BGM_PCT)
    print(f'{len(drr)} songs; out: drr_db < {d_cut:.1f} dB (wettest {REVERB_PCT} %) or bgm_db > {b_cut:.1f} dB '
          f'(loudest {BGM_PCT} %)', flush=True)
    for spk, rs in rows.items():
        out = {s: r for s, r in rs.items() if r['drr_db'] < d_cut or r['bgm_db'] > b_cut}
        dest = spk / 'raw_songs_excluded'
        dest.mkdir(exist_ok=True)
        with open(dest / '_excluded.tsv', 'w', encoding='utf-8') as fp:
            fp.write('song\tdrr_db\tbgm_db\treason\n')
            for s, r in sorted(out.items()):
                why = '，'.join(([f'原曲混响重（直达/混响比 {r["drr_db"]:.1f} dB）'] if r['drr_db'] < d_cut else [])
                               + ([f'原曲 BGM 响（比人声高 {r["bgm_db"]:.1f} dB）'] if r['bgm_db'] > b_cut else []))
                fp.write(f'{s}\t{r["drr_db"]:.2f}\t{r["bgm_db"]:.2f}\t{why}\n')
        moved = 0
        if apply:
            for f in sorted((spk / 'raw_songs').rglob('*')):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTS and song_name(f) in out:
                    shutil.move(str(f), str(dest / f.name))
                    moved += 1
            done = [(spk / 'work' / d, '*') for d in DIRS.values()] + [(spk / 'eval' / 'frames', '*.npz')]
            for folder, pattern in done:
                for f in sorted(folder.glob(pattern)):
                    if f.stem in out:
                        (dest / '_separated' / folder.name).mkdir(parents=True, exist_ok=True)
                        shutil.move(str(f), str(dest / '_separated' / folder.name / f.name))
        left = sum(r['sung_h'] for s, r in rs.items() if s not in out)
        print(f'{spk.name}: {len(out)} of {len(rs)} songs out ({sum(r["sung_h"] for r in out.values()):.1f} h), '
              f'{left:.1f} h of sung lines left; {moved} files moved to {dest}', flush=True)


if __name__ == '__main__':
    main()
