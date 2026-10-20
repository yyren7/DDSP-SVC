# Shared settings for the AutoDL scripts. Sourced by runner.sh, setup.sh and jobs.sh.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRANCH="${BRANCH:-master}"
LOG_BRANCH="${LOG_BRANCH:-autodl-logs}"
GITHUB_REPO="${GITHUB_REPO:-yyren7/DDSP-SVC}"

STATE_DIR="$REPO_DIR/.autodl"          # job logs, status, feedback
UVR_MODEL_DIR="$REPO_DIR/pretrain/uvr"
BASE_CONFIG="configs/reflow.yaml"      # configs/speakers/<speaker>.yaml replaces it for that speaker

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

plan_value() {  # key -> value from plan.txt (plain KEY=VALUE lines, never executed)
    grep -E "^$1=" "$REPO_DIR/tools/autodl/plan.txt" 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//; s/^"//; s/"$//'
}

# Every speaker keeps their own data, model and results under speakers/<name>/ on the data disk,
# so switching SPEAKER in plan.txt never touches another speaker's files.
SPEAKERS_DIR="$DATA_ROOT/speakers"
use_speaker() {  # name -> the per-speaker folders below; all empty when the name is missing or invalid
    SPEAKER="$1"
    if [[ ! "$SPEAKER" =~ ^[A-Za-z0-9_-]+$ ]]; then
        SPEAKER=""; SPK_DIR=""; DL_DIR=""; SONG_DIR=""; RAW_DIR=""; WORK_DIR=""; DATA_DIR=""
        EXP_DIR=""; SPK_CONFIG=""; TEST_DIR=""; TEST_WORK_DIR=""; INFER_DIR=""
        return 1
    fi
    SPK_DIR="$SPEAKERS_DIR/$SPEAKER"
    DL_DIR="$SPK_DIR/downloads"        # download job output: recordings and videos (cold storage)
    SONG_DIR="$SPK_DIR/songs"          # songsplit job output: one file per song
    RAW_DIR="$SPK_DIR/raw_songs"       # songs to build the training set from (copied from songs/ or uploaded)
    WORK_DIR="$SPK_DIR/work"           # UVR stage outputs for training songs
    DATA_DIR="$SPK_DIR/data"           # DDSP-SVC train/ and val/
    EXP_DIR="$SPK_DIR/exp"             # checkpoints and training logs
    SPK_CONFIG="$SPK_DIR/reflow.yaml"  # BASE_CONFIG with the paths above, written by jobs.sh
    TEST_DIR="$SPK_DIR/test_songs"     # songs to convert with the latest checkpoint (you upload these)
    TEST_WORK_DIR="$SPK_DIR/work_test"
    INFER_DIR="$SPK_DIR/infer_out"     # conversion results, one folder per checkpoint
    # DATASET=<name> (chain item job@speaker:<name>): another training set of the same speaker, made by
    # build_clips.py, with its own features, model and results, e.g. for A/B runs of two line selections
    if [[ "${DATASET:-}" =~ ^[A-Za-z0-9_-]+$ ]]; then
        DATA_DIR="$SPK_DIR/data_$DATASET"; EXP_DIR="$SPK_DIR/exp_$DATASET"
        SPK_CONFIG="$SPK_DIR/reflow_$DATASET.yaml"; INFER_DIR="$SPK_DIR/infer_out_$DATASET"
    fi
}
use_speaker "${SPEAKER:-$(plan_value SPEAKER)}" || true

export PYTHONUNBUFFERED=1
mkdir -p "$STATE_DIR"
if [ -n "$SPK_DIR" ]; then mkdir -p "$RAW_DIR" "$TEST_DIR"; fi
