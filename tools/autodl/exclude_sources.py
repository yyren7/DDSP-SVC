"""
Leave whole songs out before the separation when the original has heavy reverb or loud BGM (2026-10-21,
the listener: "先剔除一些混响太大，bgm太吵的曲子"). The measurements come from the frames of eval_lines.py
made on the earlier chain (vocals -> dereverb -> karaoke), whose mix and separated vocals are those of the
current chain too, so they run before the lines job redoes those frames:

    drr_db  direct-to-reverberant ratio inside the lines: 10 log10(sum P_derev / sum (P_voc - P_derev)),
            i.e. against what that dereverb step took out of the separated vocals; lower = wetter
    bgm_db  median over sung frames of the mix minus the separated vocals: accompaniment against the voice

On the songs the listener named (2026-10-20) drr_db put "原曲混响太大" 31st and "混响开太大，应剔除" 74th
of 362, bgm_db put "原曲 BGM 太吵" 1st, and the song "背景和混响大，但还能用" 274th and 160th.

    python tools/autodl/exclude_sources.py [--apply] <speaker dir>...

Songs among the wettest REVERB_PCT % or the loudest BGM_PCT % of all speakers given are listed with their
measurements in <speaker>/raw_songs_excluded/_excluded.tsv; --apply also moves their files from raw_songs/
there (outside raw_songs, which prepare_dataset.py reads recursively). Moving a file back restores the song.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

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
        if 'chain' in z.files or 'E_derev' not in z.files:
            continue  # made on the current chain already: its dereverb input is no longer the separated vocals
        ev, ed, em = (z[k].astype(np.float64) for k in ('E_voc', 'E_derev', 'E_mix'))
        pv, pd = 10 ** (ev / 10), 10 ** (ed / 10)
        inside = np.zeros(len(ev), bool)
        for m in lines.get(f.stem, []):
            inside[int(m['start'] * FPS):int(m['end'] * FPS)] = True
        sung = z['f0_kar'].astype(np.float32) > 0
        if inside.sum() < 300 or sung.sum() < 300:
            continue
        rows[f.stem] = {'drr_db': float(10 * np.log10(pd[inside].sum() / max((pv - pd)[inside].clip(0).sum(), 1e-12))),
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
        sys.exit('no frames of the earlier chain left to measure')
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
        left = sum(r['sung_h'] for s, r in rs.items() if s not in out)
        print(f'{spk.name}: {len(out)} of {len(rs)} songs out ({sum(r["sung_h"] for r in out.values()):.1f} h), '
              f'{left:.1f} h of sung lines left; {moved} files moved to {dest}', flush=True)


if __name__ == '__main__':
    main()
