#!/bin/bash
# The re-singing test of the bake-off (README.md): SoulX-Singer's SVS model, and the parts of its preprocessing that
# turn a Chinese dry vocal into its metadata (F0 by RMVPE, lyrics with word times by Paraformer, notes by ROSVOT), in
# the bk venv of setup.sh. numpy and transformers stay at the versions the conversion candidates run with.
#   bash tools/bakeoff/setup_svs.sh
set -e
R=/root/autodl-tmp/bakeoff/repos/SoulX-Singer; ENV=/root/autodl-tmp/conda_envs/bk
C=/root/autodl-tmp/DDSP-SVC/tools/autodl/torch-constraints.txt
export PIP_CACHE_DIR=/root/autodl-tmp/.cache/pip HF_HOME=/root/autodl-tmp/.cache/huggingface HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_ETAG_TIMEOUT=60 HF_HUB_DOWNLOAD_TIMEOUT=60
$ENV/bin/pip install -c $C -c <(printf 'numpy==1.26.4\ntransformers==4.46.3\n') funasr==1.3.0 ToJyutping g2pM \
    g2p_en mido pretty_midi praat-parselmouth webrtcvad ml_collections loralib beartype rotary_embedding_torch
cd $R
$ENV/bin/python - <<'EOF'
from huggingface_hub import hf_hub_download, snapshot_download
print(hf_hub_download('Soul-AILab/SoulX-Singer', 'model.pt', local_dir='pretrained_models/SoulX-Singer'))
print(snapshot_download('Soul-AILab/SoulX-Singer-Preprocess', local_dir='pretrained_models/SoulX-Singer-Preprocess',
                        allow_patterns=['rosvot/*', 'speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/*.*']))
EOF
$ENV/bin/python -c "import funasr, g2pM, ToJyutping, mido; print('svs ok')"
du -sh pretrained_models/*
