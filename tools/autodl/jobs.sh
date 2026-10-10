#!/bin/bash
# Predefined jobs started by runner.sh: setup | uvr | features | train | infer
# Extra arguments come from tools/autodl/plan.txt (UVR_ARGS, KEY, SPK_ID, WORKERS).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

JOB="$1"
expdir() { grep -E '^\s*expdir:' "$CONFIG" | head -1 | awk '{print $2}'; }

# Separation, feature extraction, training and inference crawl on CPU, so fail fast when the
# instance was started without a GPU (AutoDL "no-card mode"). ALLOW_CPU=1 overrides.
require_gpu() {
    nvidia-smi -L >/dev/null 2>&1 && return 0
    [ "${ALLOW_CPU:-0}" = 1 ] && { echo "no GPU, running on CPU (ALLOW_CPU=1)"; return 0; }
    echo "no GPU found: this instance runs in no-card mode. Restart it with a GPU; the runner resumes this job."
    exit 3
}
case "$JOB" in uvr|features|train|infer) require_gpu ;; esac

case "$JOB" in
setup)
    bash tools/autodl/setup.sh
    ;;
uvr)
    # Raw songs -> separated, de-harmonised, de-reverbed, denoised, sliced clips in data/
    conda activate "$ENV_ROOT/uvr"
    # shellcheck disable=SC2086
    python tools/prepare_dataset.py -i "$RAW_DIR" -o data -w "$WORK_DIR" \
        --model-dir "$UVR_MODEL_DIR" ${UVR_ARGS:-}
    ;;
features)
    conda activate "$ENV_ROOT/ddsp"
    python preprocess.py -c "$CONFIG" -j "${WORKERS:-4}"
    ;;
train)
    conda activate "$ENV_ROOT/ddsp"
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    python train_reflow.py -c "$CONFIG"
    ;;
infer)
    # Convert every song in test_songs/ with the newest checkpoint.
    ckpt=$(ls -t "$(expdir)"/model_*.pt 2>/dev/null | grep -v 'model_0.pt' | head -1 || true)
    [ -n "$ckpt" ] || { echo "no checkpoint in $(expdir) yet"; exit 1; }
    echo "checkpoint: $ckpt"
    conda activate "$ENV_ROOT/uvr"
    # shellcheck disable=SC2086
    python tools/prepare_dataset.py -i "$TEST_DIR" -w "$TEST_WORK_DIR" --model-dir "$UVR_MODEL_DIR" \
        --steps vocals,karaoke,dereverb,denoise ${UVR_ARGS:-}
    conda deactivate
    conda activate "$ENV_ROOT/ddsp"
    out="$INFER_DIR/$(basename "$ckpt" .pt)_key${KEY:-0}"
    mkdir -p "$out"
    for f in "$TEST_WORK_DIR"/4_denoise/*.wav; do
        [ -e "$f" ] || continue
        echo "converting $(basename "$f")"
        python main_reflow.py -i "$f" -m "$ckpt" -o "$out/$(basename "$f")" \
            -k "${KEY:-0}" -id "${SPK_ID:-1}"
    done
    echo "results in $out"
    ;;
*)
    echo "unknown job: $JOB"; exit 2
    ;;
esac
