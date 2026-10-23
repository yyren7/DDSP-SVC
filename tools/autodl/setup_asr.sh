#!/bin/bash
# asr: the ddsp env plus Qwen3-ASR (lyrics recognition) for the diction check of covers (tools/diction.py), and
# pypinyin / pykakasi for its sung units; torch pinned to the ddsp build. qwen-asr goes in without its demo
# dependencies (gradio, flask), whose resolver search against this env runs for hours. Models into HF_HOME of
# config.sh, through hf-mirror.com.
set -e
ENV=/root/autodl-tmp/conda_envs/asr
export HF_HOME=/root/autodl-tmp/.cache/huggingface PIP_CACHE_DIR=/root/autodl-tmp/.cache/pip
[ -x $ENV/bin/python ] || /root/autodl-tmp/conda_envs/ddsp/bin/python -m venv --system-site-packages $ENV
C=/root/autodl-tmp/DDSP-SVC/tools/autodl/torch-constraints.txt
$ENV/bin/pip install -c $C --no-deps qwen-asr==0.0.6
$ENV/bin/pip install -c $C transformers==4.57.6 accelerate==1.12.0 nagisa==0.2.11 soynlp==0.0.493 qwen-omni-utils \
    sox pytz pypinyin pykakasi
for m in Qwen/Qwen3-ASR-1.7B pymaster/VocalParse; do
    HF_ENDPOINT=https://hf-mirror.com $ENV/bin/python -c "import sys; from huggingface_hub import snapshot_download; print(snapshot_download(sys.argv[1]))" "$m"
done
$ENV/bin/python -c "import torch, qwen_asr, pypinyin, pykakasi; print('asr ok', torch.__version__, torch.cuda.is_available())"
