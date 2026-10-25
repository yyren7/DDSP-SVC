"""
RIFT-SVC's fine-tuned checkpoints (finetune_rift.sh) on the clean inputs (clean_set.py), for the user to hear beside
her DDSP-SVC 40k on the review page.

    /root/autodl-tmp/conda_envs/rift/bin/python tools/bakeoff/rift.py <step>...

Each checkpoint converts every item of set/manifest_clean.json with infer.py's defaults (32 steps, key 0) into
out/clean_rift<step>/, matched in loudness to the input, and is put into her 转换结果 infer_out/clean/<song>/ as
2_RIFT<step>步.flac, next to 0_输入 and 1_DDSP4万步. A step whose checkpoint is not saved yet is waited for.

infer.py cuts its input at pauses with an absolute threshold (-30 dB) on the input as it is, and leaves out what it
takes for silence: Opencpop's 2001, recorded quietly, lost whole sung phrases (27 gaps of up to 2 s; the user heard
the output stop for a second or two). So the input is first brought to -18 LUFS, the loudness RIFT-SVC is trained
at, and cut at -40 dB.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
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
        raw, src = out / f'{it["name"]}.raw.wav', out / f'{it["name"]}.in.wav'
        t = time.time()
        x, sr = mono(it['input'])
        x = pyln.normalize.loudness(x, pyln.Meter(sr).integrated_loudness(x), -18.0)
        sf.write(str(src), x / max(1.0, np.abs(x).max() / 0.99), sr, subtype='FLOAT')
        subprocess.run([sys.executable, 'infer.py', '--model', str(ckpt), '--input', str(src), '--output', str(raw),
                        '--speaker', 'hanamaru_hareru', '--key-shift', '0', '--slicer-threshold', '-40'],
                       cwd=R, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        src.unlink()
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
