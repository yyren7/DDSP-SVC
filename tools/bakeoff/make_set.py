"""
The bake-off's test set (README.md), into /root/autodl-tmp/bakeoff/:

    set/lines/   the 36 clips of hanamaru_hareru's 40k/80k blind test (abtest_steps80/_source): her own 12 lines of
                 the held-out songs (resynthesis) and 12 each of pheebie and sakura_shunka (conversion)
    set/songs/   whole dry leads: the multitrack raw leads of the clean pilot (English, clean input) and the dry leads
                 of two of her covers (Japanese, Chinese), as song__<name>.<ext>
    set/ref/     the reference of the zero-shot models: her cleanest lines of the songs she was trained on, one per
                 song, about REF_LEN seconds joined with short gaps (ref.wav, the lines in ref.json)
    out/ddsp40k/ the baseline, her DDSP-SVC 40k model, from the results made before (abtest, clean pilot, covers/cand)
    set/manifest.json

Every result of the bake-off is matched in loudness to its input (match_level), as abtest.py does: louder sounds better.
    /root/autodl-tmp/conda_envs/ddsp/bin/python tools/bakeoff/make_set.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'autodl'))
from abtest import active_rms  # noqa: E402

DATA = Path('/root/autodl-tmp')
B = DATA / 'bakeoff'
SPK = DATA / 'speakers' / 'hanamaru_hareru'
AB = SPK / 'abtest_steps80'
SONGS = {  # name: (dry lead, the DDSP-SVC 40k conversion of it)
    'april_blues': (DATA / 'clean_pilot/april_blues/lead.flac',
                    DATA / 'clean_pilot/april_blues/conv_clean_hanamaru_hareru_40000.wav'),
    'carousel_ride': (DATA / 'clean_pilot/carousel_ride/lead.flac',
                      DATA / 'clean_pilot/carousel_ride/conv_clean_hanamaru_hareru_40000.wav'),
    'haru': (DATA / 'covers/cand/haru/dry.wav', DATA / 'covers/cand/haru/0_40k.wav'),
    'liangrenfen': (DATA / 'covers/cand/liangrenfen/dry.wav', DATA / 'covers/cand/liangrenfen/0_40k.wav'),
}
REF_LEN = 15.0       # seconds of reference: Seed-VC's 30 s window holds the reference and the source chunk together
REF_GAP = 0.2        # seconds of silence between the lines of the reference
REF_MIN_SCORE = 90   # eval_lines.py's line score (0-100)
FADE = 0.01


def mono(path):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return x.mean(1), sr


def match_level(y, sr, ref_path):
    """y scaled to the active RMS of the input it was converted from, its peak kept under 0.99."""
    x, xsr = mono(ref_path)
    a, b = active_rms(y, sr), active_rms(x, xsr)
    if a > 0 and b > 0:
        y = y * (b / a)
    peak = np.abs(y).max(initial=0)
    return y * (0.99 / peak) if peak > 0.99 else y


def link(src, dst):
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.symlink_to(src)


def reference():
    holdout = set(json.loads((SPK / 'eval' / 'holdout.json').read_text(encoding='utf-8')))
    lines = [json.loads(x) for x in (SPK / 'eval' / 'lines.jsonl').read_text(encoding='utf-8').splitlines() if x]
    best = {}
    for m in lines:
        if (m['song'] not in holdout and m['score'] >= REF_MIN_SCORE and 4 <= m['dur'] <= 10 and m['voiced'] >= 0.85
                and (m['song'] not in best or m['score'] > best[m['song']]['score'])):
            best[m['song']] = m
    picked, total = [], 0.0
    for m in sorted(best.values(), key=lambda m: (-m['score'], -m['voiced'])):
        if total >= REF_LEN:
            break
        picked.append(m)
        total += m['dur']
    parts, sr = [], None
    for m in picked:
        x, sr = mono(SPK / 'work' / '3_dereverb' / f'{m["song"]}.wav')
        seg = x[int(m['start'] * sr):int(m['end'] * sr)].copy()
        n = int(FADE * sr)
        seg[:n] *= np.linspace(0, 1, n)
        seg[-n:] *= np.linspace(1, 0, n)
        parts += [seg, np.zeros(int(REF_GAP * sr), np.float32)]
    (B / 'set' / 'ref').mkdir(parents=True, exist_ok=True)
    sf.write(str(B / 'set' / 'ref' / 'ref.wav'), np.concatenate(parts[:-1]), sr, subtype='PCM_16')
    (B / 'set' / 'ref' / 'ref.json').write_text(json.dumps(
        [{k: m[k] for k in ('song', 'k', 'start', 'end', 'dur', 'score', 'voiced')} for m in picked],
        ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'reference: {len(picked)} lines, {total:.1f} s: ' + ', '.join(m['song'] for m in picked))


def main():
    man = json.loads((AB / 'manifest.json').read_text(encoding='utf-8'))
    for d in ('set/lines', 'set/songs', 'out/ddsp40k'):
        (B / d).mkdir(parents=True, exist_ok=True)
    items = []
    for it in man['items']:
        src = AB / '_source' / f'{it["name"]}.wav'
        link(src, B / 'set' / 'lines' / src.name)
        items.append({'name': it['name'], 'kind': 'line', 'src_spk': it['src_spk'], 'dur': it['dur'],
                      'input': str(B / 'set' / 'lines' / src.name)})
        y, sr = mono(AB / 'all@40000' / src.name)
        sf.write(str(B / 'out' / 'ddsp40k' / src.name), match_level(y, sr, src), sr, subtype='PCM_16')
    for song, (dry, conv) in SONGS.items():
        name = f'song__{song}'
        inp = B / 'set' / 'songs' / f'{name}{dry.suffix}'
        link(dry, inp)
        items.append({'name': name, 'kind': 'song', 'src_spk': song, 'dur': round(sf.info(str(dry)).duration, 2),
                      'input': str(inp)})
        y, sr = mono(conv)
        sf.write(str(B / 'out' / 'ddsp40k' / f'{name}.wav'), match_level(y, sr, dry), sr, subtype='PCM_16')
    reference()
    (B / 'set' / 'manifest.json').write_text(json.dumps(
        {'made': time.strftime('%F %T'), 'speaker': SPK.name, 'ref': str(B / 'set' / 'ref' / 'ref.wav'),
         'items': items}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(items)} items: {sum(i["kind"] == "line" for i in items)} lines, '
          f'{sum(i["kind"] == "song" for i in items)} songs; baseline in out/ddsp40k/')


if __name__ == '__main__':
    main()
