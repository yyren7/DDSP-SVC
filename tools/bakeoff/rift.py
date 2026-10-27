"""
RIFT-SVC's fine-tuned checkpoints (finetune_rift.sh) on the clean inputs (clean_set.py), for the user to hear beside
her DDSP-SVC 40k on the review page.

    /root/autodl-tmp/conda_envs/rift/bin/python tools/bakeoff/rift.py [--speaker S] <step>...

Each checkpoint converts every item of set/manifest_clean.json with infer.py's defaults (32 steps, key 0) into
out/clean_rift<step>/ (another speaker than hanamaru_hareru: out/clean_rift_<speaker><step>/), matched in loudness to
the input, and is put into the speaker's 转换结果 infer_out/clean/<song>/ as 2_RIFT<step>步.flac, next to 0_输入
(written when missing) and, for hanamaru_hareru, 1_DDSP4万步. A step whose checkpoint is not saved yet is waited for.

The conversion is rift_patch.py's (the input brought to -18 LUFS and cut at -40 dB: infer.py's own -30 dB on the
input as it is dropped whole phrases of a quiet recording, the user heard the output stop for a second or two).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_set import match_level, mono  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rift_patch  # noqa: E402

B = Path('/root/autodl-tmp/bakeoff')


def convert(step, speaker=rift_patch.SPEAKER):
    ckpt = rift_patch.checkpoint(speaker, step)
    while not ckpt.exists():
        time.sleep(60)
    time.sleep(60)  # the file appears when the save starts
    tag = f'clean_rift{step}' if speaker == rift_patch.SPEAKER else f'clean_rift_{speaker}{step}'
    out = B / 'out' / tag
    out.mkdir(parents=True, exist_ok=True)
    show = Path('/root/autodl-tmp/speakers') / speaker / 'infer_out' / 'clean'
    items = json.loads((B / 'set' / 'manifest_clean.json').read_text(encoding='utf-8'))['items']
    for it in items:
        song = show / it['src_spk']
        song.mkdir(parents=True, exist_ok=True)
        if not (song / '0_输入.flac').exists():
            sf.write(str(song / '0_输入.flac'), *mono(it['input']), subtype='PCM_24')
        raw = out / f'{it["name"]}.raw.wav'
        t = time.time()
        rift_patch.convert(it['input'], raw, ckpt=ckpt, speaker=speaker)
        y, sr = mono(raw)
        y = match_level(y, sr, it['input'])
        sf.write(str(out / f'{it["name"]}.wav'), y, sr, subtype='PCM_16')
        sf.write(str(song / f'2_RIFT{step}步.flac'), y, sr, subtype='PCM_24')
        raw.unlink()
        print(f'{tag}: {it["name"]} {len(y) / sr:.0f} s in {time.time() - t:.0f} s', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--speaker', default=rift_patch.SPEAKER)
    p.add_argument('steps', nargs='+', type=int)
    args = p.parse_args()
    for s in args.steps:
        convert(s, args.speaker)
