"""
RIFT-SVC's fine-tuned checkpoints (finetune_rift.sh) on the clean inputs (clean_set.py), for the user to hear beside
her DDSP-SVC 40k on the review page.

    /root/autodl-tmp/conda_envs/rift/bin/python tools/bakeoff/rift.py <step>...

Each checkpoint converts every item of set/manifest_clean.json with infer.py's defaults (32 steps, key 0) into
out/clean_rift<step>/, matched in loudness to the input, and is put into her 转换结果 infer_out/clean/<song>/ as
2_RIFT<step>步.flac, next to 0_输入 and 1_DDSP4万步. A step whose checkpoint is not saved yet is waited for.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_set import match_level, mono  # noqa: E402

B = Path('/root/autodl-tmp/bakeoff')
R = Path('/root/autodl-tmp/rift/RIFT-SVC')
RUN = 'hanamaru_768-12'
SHOW = Path('/root/autodl-tmp/speakers/hanamaru_hareru/infer_out/clean')


def convert(step):
    ckpt = R / 'ckpts' / RUN / f'model-step={step}.ckpt'
    while not ckpt.exists():
        time.sleep(60)
    time.sleep(60)  # the file appears when the save starts
    out = B / 'out' / f'clean_rift{step}'
    out.mkdir(parents=True, exist_ok=True)
    items = json.loads((B / 'set' / 'manifest_clean.json').read_text(encoding='utf-8'))['items']
    for it in items:
        raw = out / f'{it["name"]}.raw.wav'
        t = time.time()
        subprocess.run([sys.executable, 'infer.py', '--model', str(ckpt), '--input', it['input'], '--output', str(raw),
                        '--speaker', 'hanamaru_hareru', '--key-shift', '0'],
                       cwd=R, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        y, sr = mono(raw)
        y = match_level(y, sr, it['input'])
        sf.write(str(out / f'{it["name"]}.wav'), y, sr, subtype='PCM_16')
        sf.write(str(SHOW / it['src_spk'] / f'2_RIFT{step}步.flac'), y, sr, subtype='PCM_24')
        raw.unlink()
        print(f'clean_rift{step}: {it["name"]} {len(y) / sr:.0f} s in {time.time() - t:.0f} s', flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for s in sys.argv[1:]:
        convert(int(s))
