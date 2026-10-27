#!/bin/bash
# RIFT-SVC V3 for the bake-off (README.md, 「RIFT-SVC」): its code in /root/autodl-tmp/rift/RIFT-SVC, a venv on top
# of the ddsp env (torch 2.9.1, as RIFT-SVC asks), its feature and vocoder modules and the 768-12 pretrained model
# through hf-mirror.com, and SPEAKER's training clips (data_all/train/audio, the set her DDSP-SVC model was trained
# on) copied into data/finetune/ (hanamaru_hareru, the first) or data/finetune_<SPEAKER>/ and prepared as its README
# says. Safe to run again: done steps are skipped. Ends with "setup done".
#   cd /root/autodl-tmp/DDSP-SVC && SPEAKER=pheebie nohup bash tools/bakeoff/setup_rift.sh > /root/autodl-tmp/rift/setup_pheebie.log 2>&1 &
set -e
W=/root/autodl-tmp/rift; R=$W/RIFT-SVC; ENV=/root/autodl-tmp/conda_envs/rift
C=/root/autodl-tmp/DDSP-SVC/tools/autodl/torch-constraints.txt
SPEAKER=${SPEAKER:-hanamaru_hareru}; SRC=/root/autodl-tmp/speakers/$SPEAKER/data_all/train/audio
D=data/finetune; [ $SPEAKER = hanamaru_hareru ] || D=data/finetune_$SPEAKER
export PIP_CACHE_DIR=/root/autodl-tmp/.cache/pip HF_HOME=/root/autodl-tmp/.cache/huggingface HF_ENDPOINT=https://hf-mirror.com
mkdir -p $W && cd $W
[ -d RIFT-SVC ] || git clone --depth 1 https://github.com/Pur1zumu/RIFT-SVC.git
cd $R

# its pyproject.toml without gradio (the web UI); torch, torchaudio and transformers come from the ddsp env
[ -x $ENV/bin/python ] || /root/autodl-tmp/conda_envs/ddsp/bin/python -m venv --system-site-packages $ENV
$ENV/bin/pip install -q -c $C click einops hydra-core jaxtyping lightning pytorch-lightning omegaconf \
    praat-parselmouth pyloudnorm pyworld resampy schedulefree tensorboardx thop torchdiffeq x-transformers wandb
# torchaudio 2.9 reads and writes through TorchCodec and FFmpeg's libraries; soundfile stands in for both
SP=$($ENV/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
cat > $SP/sitecustomize.py <<'EOF'
import soundfile as sf
import torch
import torchaudio


def _load(path, *a, **k):
    x, sr = sf.read(str(path), dtype='float32', always_2d=True)
    return torch.from_numpy(x.T.copy()), sr


def _save(path, wav, sr, *a, **k):
    sf.write(str(path), wav.detach().cpu().float().numpy().T, sr)


torchaudio.load, torchaudio.save = _load, _save
EOF

$ENV/bin/python - <<'EOF'
from huggingface_hub import hf_hub_download, snapshot_download
snapshot_download('Pur1zumu/RIFT-SVC-modules', local_dir='pretrained', ignore_patterns=['*.git*'])
print(hf_hub_download('Pur1zumu/RIFT-SVC-pretrained', 'pretrain-v3_dit-768-12.ckpt', local_dir='pretrained'))
EOF

# a copy, as resample_normalize_audios.py rewrites the files in place (44.1 kHz, -18 LUFS)
if [ ! -f $D/meta_info.json ]; then
    rm -rf $D/$SPEAKER && mkdir -p $D/$SPEAKER && cp $SRC/*.wav $D/$SPEAKER/
    $ENV/bin/python scripts/resample_normalize_audios.py --src $D
    $ENV/bin/python scripts/prepare_data_meta.py --data-dir $D
fi
# the README's four features (its prepare.sh is out of date: Whisper features, options and a script since removed)
for s in mel rms f0 cvec; do $ENV/bin/python scripts/prepare_$s.py --data-dir $D --num-workers 4; done
echo "setup done"
