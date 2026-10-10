#!/bin/bash
# Create the two conda environments and download every pretrained model.
# Everything large goes to the data disk (see config.sh). Safe to re-run: finished steps are skipped.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

# No global proxy here: pip/conda use AutoDL's domestic mirrors directly, and model downloads
# below pick between a direct connection and the academic proxy per attempt, because the proxy
# intermittently answers 503 for both GitHub and HuggingFace.
with_net() {  # direct|turbo cmd... -> run cmd without proxy, or through AutoDL's academic proxy
    local mode="$1"; shift
    if [ "$mode" = direct ]; then
        env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY "$@"
    else
        [ -f /etc/network_turbo ] || return 1
        (source /etc/network_turbo >/dev/null 2>&1; "$@")
    fi
}

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
# audio-separator refuses to start without an ffmpeg binary, which the AutoDL image lacks.
if ! command -v ffmpeg >/dev/null; then
    echo "== installing ffmpeg"
    (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg) \
        || conda install -y -p "$ENV_ROOT/uvr" -c conda-forge ffmpeg
fi
ffmpeg -version | head -1
conda deactivate

download() {  # dest min_bytes url... -> try every url, direct then proxy, a few rounds
    local dest="$1" min="$2"; shift 2
    if [ -s "$dest" ] && [ "$(stat -c %s "$dest")" -ge "$min" ]; then echo "exists: $dest"; return 0; fi
    mkdir -p "$(dirname "$dest")"
    for round in 1 2 3; do
        for url in "$@"; do
            for mode in direct turbo; do
                echo "== [$round] $mode $url"
                if with_net "$mode" curl -fL --connect-timeout 20 --retry 1 -sS -o "$dest.part" "$url" \
                        && [ "$(stat -c %s "$dest.part")" -ge "$min" ]; then
                    mv "$dest.part" "$dest"; echo "ok: $dest"; return 0
                fi
            done
        done
        sleep $((round * 20))
    done
    rm -f "$dest.part"; echo "FAILED: $dest"; return 1
}

HF_FILE=lengyue233/content-vec-best/resolve/main/pytorch_model.bin
download pretrain/contentvec/pytorch_model.bin 300000000 \
    "https://hf-mirror.com/$HF_FILE" "https://huggingface.co/$HF_FILE"

if [ "$(stat -c %s pretrain/nsf_hifigan/model 2>/dev/null || echo 0)" -lt 50000000 ]; then
    download "$STATE_DIR/nsf_hifigan.zip" 50000000 \
        https://github.com/openvpi/vocoders/releases/download/pc-nsf-hifigan-44.1k-hop512-128bin-2025.02/pc_nsf_hifigan_44.1k_hop512_128bin_2025.02.zip
    unzip -o -j "$STATE_DIR/nsf_hifigan.zip" '*/model.ckpt' '*/config.json' -d pretrain/nsf_hifigan
    mv pretrain/nsf_hifigan/model.ckpt pretrain/nsf_hifigan/model
    rm -f "$STATE_DIR/nsf_hifigan.zip"
fi

if [ "$(stat -c %s pretrain/rmvpe/model.pt 2>/dev/null || echo 0)" -lt 300000000 ]; then
    download "$STATE_DIR/rmvpe.zip" 300000000 https://github.com/yxlllc/RMVPE/releases/download/230917/rmvpe.zip
    unzip -o "$STATE_DIR/rmvpe.zip" model.pt -d pretrain/rmvpe
    rm -f "$STATE_DIR/rmvpe.zip"
fi

# UVR models for the uvr job, fetched now so that job never touches the network.
conda activate "$ENV_ROOT/uvr"
uvr_ok=""
for round in 1 2 3; do
    for mode in direct turbo; do
        echo "== [$round] UVR models via $mode"
        if with_net "$mode" python tools/autodl/fetch_uvr_models.py --model-dir "$UVR_MODEL_DIR"; then
            uvr_ok=1; break 2
        fi
    done
    sleep $((round * 20))
done
conda deactivate
[ -n "$uvr_ok" ] || { echo "FAILED: UVR models"; exit 1; }

# Everything is installed; the download caches only take space on the data disk now.
conda clean -y --all >/dev/null 2>&1 || true
rm -rf "$PIP_CACHE_DIR"

nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader || true
df -h / "$DATA_ROOT" | tail -2
echo "setup finished"
