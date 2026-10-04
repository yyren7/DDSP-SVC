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

export PYTHONUNBUFFERED=1
mkdir -p "$RAW_DIR" "$TEST_DIR" "$STATE_DIR"
