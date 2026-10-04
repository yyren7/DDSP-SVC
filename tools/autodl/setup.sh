#!/bin/bash
# Create the two conda environments and download every pretrained model.
# Safe to re-run: finished steps are skipped.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

# AutoDL academic acceleration for GitHub / HuggingFace downloads.
[ -f /etc/network_turbo ] && source /etc/network_turbo || true

TORCH_PIN="torch==2.9.1 torchaudio==2.9.1"

if ! conda env list | grep -qE '^ddsp\s'; then
    echo "== creating env: ddsp"
    conda create -y -n ddsp python=3.11
fi
conda activate ddsp
python -c "import torch, torchaudio" 2>/dev/null || pip install $TORCH_PIN
pip install -r requirements.txt
python -c "import torch; print('ddsp env: torch', torch.__version__, 'cuda', torch.cuda.is_available())"
conda deactivate

if ! conda env list | grep -qE '^uvr\s'; then
    echo "== creating env: uvr"
    conda create -y -n uvr python=3.11
fi
conda activate uvr
# Install the same torch first so audio-separator does not pull a build the driver cannot run.
python -c "import torch" 2>/dev/null || pip install $TORCH_PIN
pip install "audio-separator[gpu]"
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
df -h "$REPO_DIR" | tail -1
echo "setup finished"
