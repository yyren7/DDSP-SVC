# Shared settings for the AutoDL scripts. Sourced by runner.sh, setup.sh and jobs/*.sh.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRANCH="${BRANCH:-claude/amazing-sagan-49ux44}"
LOG_BRANCH="${LOG_BRANCH:-autodl-logs}"
GITHUB_REPO="${GITHUB_REPO:-yyren7/DDSP-SVC}"

RAW_DIR="$REPO_DIR/raw_songs"          # songs to build the training set from (you upload these)
TEST_DIR="$REPO_DIR/test_songs"        # songs to convert with the latest checkpoint (you upload these)
WORK_DIR="$REPO_DIR/preprocess_work"   # UVR stage outputs for training songs
TEST_WORK_DIR="$REPO_DIR/preprocess_work_test"
INFER_DIR="$REPO_DIR/infer_out"        # conversion results, one folder per checkpoint
STATE_DIR="$REPO_DIR/.autodl"          # job logs, status, feedback
UVR_MODEL_DIR="$REPO_DIR/pretrain/uvr"
CONFIG="${CONFIG:-configs/reflow.yaml}"

REVIEW_PORT="${REVIEW_PORT:-6008}"     # AutoDL "custom service" port (6006 is left for TensorBoard)

CONDA_BASE="$(conda info --base 2>/dev/null || echo /root/miniconda3)"
# shellcheck disable=SC1091
source "$CONDA_BASE/etc/profile.d/conda.sh"

# The system disk on AutoDL is only ~30 GB, so environments and download caches live on the
# data disk next to the repository (/root/autodl-tmp).
DATA_ROOT="$(dirname "$REPO_DIR")"
ENV_ROOT="$DATA_ROOT/conda_envs"       # conda activate "$ENV_ROOT/ddsp" | "$ENV_ROOT/uvr"
export PIP_CACHE_DIR="$DATA_ROOT/.cache/pip"
export CONDA_PKGS_DIRS="$DATA_ROOT/.cache/conda_pkgs"
export HF_HOME="$DATA_ROOT/.cache/huggingface"
export TORCH_HOME="$DATA_ROOT/.cache/torch"
# torch is pinned in both environments so no dependency can swap it for another CUDA build.
TORCH_CONSTRAINTS="$REPO_DIR/tools/autodl/torch-constraints.txt"

export PYTHONUNBUFFERED=1
mkdir -p "$RAW_DIR" "$TEST_DIR" "$STATE_DIR"
