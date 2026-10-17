#!/bin/bash
# Predefined jobs started by runner.sh: setup | uvr | features | train | infer
# Extra arguments come from tools/autodl/plan.txt (UVR_ARGS, KEY, SPK_ID, WORKERS).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

JOB="$1"
expdir() { grep -E '^\s*expdir:' "$CONFIG" | head -1 | awk '{print $2}'; }
noproxy() { env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY "$@"; }

fetch() {  # dest md5 url... -> download unless dest already has that md5; each url direct, then via AutoDL's academic proxy
    local dest="$1" md5="$2"; shift 2
    [ -f "$dest" ] && [ "$(md5sum < "$dest" | cut -d' ' -f1)" = "$md5" ] && return 0
    for url in "$@"; do
        for mode in direct turbo; do
            echo "== fetching $(basename "$dest") ($mode) from $url"
            if [ "$mode" = direct ]; then
                noproxy curl -fL --connect-timeout 20 --speed-limit 200000 --speed-time 60 -sS -o "$dest.part" "$url"
            else
                [ -f /etc/network_turbo ] && (source /etc/network_turbo >/dev/null 2>&1
                    curl -fL --connect-timeout 20 --speed-limit 200000 --speed-time 60 -sS -o "$dest.part" "$url")
            fi && [ "$(md5sum < "$dest.part" | cut -d' ' -f1)" = "$md5" ] && { mv "$dest.part" "$dest"; return 0; }
        done
    done
    rm -f "$dest.part"; echo "FAILED to fetch $(basename "$dest")"; return 1
}

# Separation, feature extraction, training and inference crawl on CPU, so fail fast when the
# instance was started without a GPU (AutoDL "no-card mode"). ALLOW_CPU=1 overrides.
require_gpu() {
    # no-card mode keeps an nvidia-smi that exits 0 but lists nothing, so look for an actual GPU
    nvidia-smi -L 2>/dev/null | grep -q '^GPU ' && return 0
    [ "${ALLOW_CPU:-0}" = 1 ] && { echo "no GPU, running on CPU (ALLOW_CPU=1)"; return 0; }
    echo "no GPU found: this instance runs in no-card mode. Restart it with a GPU; the runner resumes this job."
    exit 3
}
case "$JOB" in uvr|features|train|infer) require_gpu ;; esac

case "$JOB" in
setup)
    bash tools/autodl/setup.sh
    ;;
download)
    # Audio of every video in a Bilibili space whose title matches DL_MATCH, into $DATA_ROOT/$DL_DIR.
    # DL_URL may also be a list file in the repo with one video URL per line (e.g. tools/autodl/lists/).
    # Kept outside the repo as cold storage; copy the songs you want into raw_songs/ yourself.
    # Resumable: finished videos are listed in _archive.txt and skipped on the next run.
    [ -n "${DL_URL:-}" ] && [ -n "${DL_DIR:-}" ] || { echo "set DL_URL and DL_DIR in plan.txt"; exit 2; }
    if [ -f "$DL_URL" ]; then src=(--batch-file "$DL_URL"); else src=("$DL_URL"); fi
    conda activate "$ENV_ROOT/uvr"
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY python -m pip install -q -U yt-dlp
    dest="$DATA_ROOT/$DL_DIR"; mkdir -p "$dest"
    cookies=(); [ -f "$STATE_DIR/bilibili_cookies.txt" ] && cookies=(--cookies "$STATE_DIR/bilibili_cookies.txt")
    # Bilibili is reached directly from AutoDL; the academic proxy would only slow it down.
    ytdlp() { env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY yt-dlp "${cookies[@]}" \
        --sleep-requests 1 --retries 10 --fragment-retries 10 "$@"; }
    if [ -f "$DL_URL" ]; then
        echo "== $(grep -c '^http' "$DL_URL") videos listed in $DL_URL"
    else
        echo "== listing $DL_URL"
        ytdlp --flat-playlist --print "%(id)s	%(duration)s	%(title)s" "$DL_URL" > "$dest/_all_videos.tsv"
        echo "$(wc -l < "$dest/_all_videos.tsv") videos, $(grep -cP "${DL_MATCH:-.}" "$dest/_all_videos.tsv" || true) matching '${DL_MATCH:-}'"
    fi
    echo "== downloading audio"
    # Multi-part videos (分P) come down as one file per part. The original audio stream is kept
    # without re-encoding. The info json keeps the comments, where fans post song timestamps (道标).
    ytdlp --yes-playlist --ignore-errors --no-overwrites --sleep-interval 2 --max-sleep-interval 5 \
        --match-filter "title~='${DL_MATCH:-.}'" -f 'bestaudio/best' -x \
        --write-info-json --write-comments \
        --download-archive "$dest/_archive.txt" \
        -o "$dest/%(upload_date)s %(title).120B [%(id)s].%(ext)s" "${src[@]}" || true
    n=$(find "$dest" -maxdepth 1 -type f ! -name '_*' | wc -l)
    echo "$n audio files in $dest ($(du -sh "$dest" | cut -f1))"
    [ "$n" -gt 0 ]
    ;;
songsplit)
    # Song-stream recordings in $DATA_ROOT/$DL_DIR -> one file per song in $DATA_ROOT/$SONG_DIR,
    # without the talk between songs. Also runs on CPU, only slower; see tools/split_songs.py.
    [ -n "${DL_DIR:-}" ] && [ -n "${SONG_DIR:-}" ] || { echo "set DL_DIR and SONG_DIR in plan.txt"; exit 2; }
    conda activate "$ENV_ROOT/uvr"
    python -c "import panns_inference" 2>/dev/null \
        || noproxy python -m pip install -q -c "$TORCH_CONSTRAINTS" panns-inference
    mkdir -p pretrain/panns
    fetch pretrain/panns/class_labels_indices.csv 68c0b5c199d6cc789852b144cc3ab500 \
        https://raw.githubusercontent.com/qiuqiangkong/audioset_tagging_cnn/master/metadata/class_labels_indices.csv
    # the md5 is the one zenodo lists for the official file; the HuggingFace copy is much faster from AutoDL
    fetch pretrain/panns/Cnn14_DecisionLevelMax.pth 70539c43c18b6a289b3199c503a82c5a \
        'https://hf-mirror.com/niobures/PANNs/resolve/main/models/checkpoints/Cnn14_DecisionLevelMax_mAP%3D0.385.pth' \
        'https://zenodo.org/records/3987831/files/Cnn14_DecisionLevelMax_mAP%3D0.385.pth?download=1'
    # shellcheck disable=SC2086
    python tools/split_songs.py -i "$DATA_ROOT/$DL_DIR" -o "$DATA_ROOT/$SONG_DIR" \
        --model-dir pretrain/panns ${SPLIT_ARGS:-}
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
