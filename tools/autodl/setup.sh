#!/bin/bash
# Create the two conda environments and download every pretrained model.
# Everything large goes to the data disk (see config.sh). Safe to re-run: finished steps are skipped.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

# AutoDL academic acceleration for GitHub / HuggingFace downloads.
[ -f /etc/network_turbo ] && source /etc/network_turbo || true

mkdir -p "$ENV_ROOT" "$PIP_CACHE_DIR" "$CONDA_PKGS_DIRS"

# ---- free the system disk from earlier runs that installed there ----
if [ -d /root/.cache/pip ] && [ ! -L /root/.cache/pip ]; then
    echo "== moving old pip cache to the data disk (keeps already downloaded wheels)"
    cp -a /root/.cache/pip/. "$PIP_CACHE_DIR"/ && rm -rf /root/.cache/pip
fi
for env in ddsp uvr; do
    if [ -d "$CONDA_BASE/envs/$env" ]; then
        echo "== removing old $env env from the system disk"
        conda env remove -y -n "$env" || rm -rf "$CONDA_BASE/envs/$env"
    fi
done
conda clean -y --all >/dev/null 2>&1 || true

pip_install() { pip install -c "$TORCH_CONSTRAINTS" "$@"; }

# ---- ddsp: training / inference ----
if [ ! -x "$ENV_ROOT/ddsp/bin/python" ]; then
    echo "== creating env: ddsp"
    conda create -y -p "$ENV_ROOT/ddsp" python=3.11
fi
conda activate "$ENV_ROOT/ddsp"
pip_install torch torchaudio
pip_install -r requirements.txt
python -c "import torch; print('ddsp env: torch', torch.__version__, 'cuda', torch.cuda.is_available())"
conda deactivate

# ---- uvr: audio-separator for vocal separation / de-reverb / denoise ----
if [ ! -x "$ENV_ROOT/uvr/bin/python" ]; then
    echo "== creating env: uvr"
    conda create -y -p "$ENV_ROOT/uvr" python=3.11
fi
conda activate "$ENV_ROOT/uvr"
pip_install torch torchaudio torchvision
pip_install "audio-separator[gpu]"
python -c "import torch, onnxruntime as ort; print('uvr env: torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'ort', ort.get_available_providers())"
conda deactivate

download() {  # url dest
    if [ -s "$2" ]; then echo "exists: $2"; return; fi
    echo "== downloading $2"
    mkdir -p "$(dirname "$2")"
    curl -fL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

download https://huggingface.co/lengyue233/content-vec-best/resolve/main/pytorch_model.bin \
    pretrain/contentvec/pytorch_model.bin

if [ ! -s pretrain/nsf_hifigan/model ]; then
    download https://github.com/openvpi/vocoders/releases/download/pc-nsf-hifigan-44.1k-hop512-128bin-2025.02/pc_nsf_hifigan_44.1k_hop512_128bin_2025.02.zip \
        "$STATE_DIR/nsf_hifigan.zip"
    unzip -o -j "$STATE_DIR/nsf_hifigan.zip" '*/model.ckpt' '*/config.json' -d pretrain/nsf_hifigan
    mv pretrain/nsf_hifigan/model.ckpt pretrain/nsf_hifigan/model
    rm -f "$STATE_DIR/nsf_hifigan.zip"
fi

if [ ! -s pretrain/rmvpe/model.pt ]; then
    download https://github.com/yxlllc/RMVPE/releases/download/230917/rmvpe.zip "$STATE_DIR/rmvpe.zip"
    unzip -o "$STATE_DIR/rmvpe.zip" model.pt -d pretrain/rmvpe
    rm -f "$STATE_DIR/rmvpe.zip"
fi

nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
df -h / "$DATA_ROOT" | tail -2
echo "setup finished"
