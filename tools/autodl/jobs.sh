#!/bin/bash
# Predefined jobs started by runner.sh: setup | download | songsplit | uvr | compare | features | train | infer | migrate
# Every job except setup works on the folders of SPEAKER (speakers/<name>/, see config.sh).
# Extra arguments come from tools/autodl/plan.txt (UVR_ARGS, KEY, SPK_ID, WORKERS, ...).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$REPO_DIR"

JOB="$1"
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

fetch_models() {  # UVR models of prepare_dataset.py: Hugging Face via hf-mirror.com, GitHub direct, then via the proxy
    noproxy python tools/autodl/fetch_uvr_models.py --model-dir "$UVR_MODEL_DIR" "$@" && return 0
    [ -f /etc/network_turbo ] && (source /etc/network_turbo >/dev/null 2>&1
        python tools/autodl/fetch_uvr_models.py --model-dir "$UVR_MODEL_DIR" "$@")
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
case "$JOB" in uvr|compare|features|train|infer) require_gpu ;; esac

if [ "$JOB" != setup ] && [ -z "$SPK_DIR" ]; then
    echo "set SPEAKER in plan.txt (letters, digits, _ and - only), e.g. SPEAKER=sakura_shunka"; exit 2
fi
echo "speaker: $SPEAKER ($SPK_DIR)"

# BASE_CONFIG (or configs/speakers/<speaker>.yaml) with this speaker's data and experiment folders.
write_config() {
    local base="$BASE_CONFIG"
    [ -f "configs/speakers/$SPEAKER.yaml" ] && base="configs/speakers/$SPEAKER.yaml"
    sed -E "s#^(\s*train_path:).*#\1 $DATA_DIR/train#; s#^(\s*valid_path:).*#\1 $DATA_DIR/val#; s#^(\s*expdir:).*#\1 $EXP_DIR#" \
        "$base" > "$SPK_CONFIG"
    echo "config: $base -> $SPK_CONFIG"
}
case "$JOB" in features|train|infer) write_config ;; esac

case "$JOB" in
setup)
    bash tools/autodl/setup.sh
    ;;
download)
    # Audio of every video in a Bilibili space whose title matches DL_MATCH, into the speaker's downloads/.
    # DL_URL may also be a list file in the repo with one video URL per line (e.g. tools/autodl/lists/).
    # Cold storage; songsplit turns song-stream recordings into songs/, copy the songs you want into raw_songs/.
    # Resumable: finished videos are listed in _archive.txt and skipped on the next run.
    [ -n "${DL_URL:-}" ] || { echo "set DL_URL in plan.txt"; exit 2; }
    if [ -f "$DL_URL" ]; then src=(--batch-file "$DL_URL"); else src=("$DL_URL"); fi
    conda activate "$ENV_ROOT/uvr"
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY python -m pip install -q -U yt-dlp
    dest="$DL_DIR"; mkdir -p "$dest"
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
    # DL_MAX caps how many new videos one run fetches (a space lists the newest first)
    limit=(); [ -n "${DL_MAX:-}" ] && limit=(--max-downloads "$DL_MAX")
    ytdlp --yes-playlist --ignore-errors --no-overwrites --sleep-interval 2 --max-sleep-interval 5 "${limit[@]}" \
        --match-filter "title~='${DL_MATCH:-.}'${DL_FILTER:+ & $DL_FILTER}" -f 'bestaudio/best' -x \
        --write-info-json --write-comments \
        --download-archive "$dest/_archive.txt" \
        -o "$dest/%(upload_date)s %(title).120B [%(id)s].%(ext)s" "${src[@]}" || true
    n=$(find "$dest" -maxdepth 1 -type f ! -name '_*' | wc -l)
    echo "$n audio files in $dest ($(du -sh "$dest" | cut -f1))"
    [ "$n" -gt 0 ]
    ;;
songsplit)
    # Song-stream recordings in downloads/ -> one file per song in songs/, without the talk between
    # songs. Also runs on CPU, only slower; see tools/split_songs.py.
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
    # Each speaker sings and talks differently: tools/autodl/split/<speaker>.args holds the settings
    # tuned for them (comments allowed), SPLIT_ARGS in plan.txt comes after it for experiments.
    args_file="tools/autodl/split/$SPEAKER.args"
    spk_args="$([ -f "$args_file" ] && sed 's/#.*$//' "$args_file" | tr '\n' ' ' | sed 's/^ *//; s/ *$//' || true)"
    echo "split settings: ${spk_args:-(defaults)} ${SPLIT_ARGS:-}"
    # shellcheck disable=SC2086
    python tools/split_songs.py -i "$DL_DIR" -o "$SONG_DIR" \
        --model-dir pretrain/panns $spk_args ${SPLIT_ARGS:-}
    ;;
uvr)
    # Raw songs -> separated, de-reverbed, de-harmonised, sliced clips in data/
    conda activate "$ENV_ROOT/uvr"
    fetch_models
    # shellcheck disable=SC2086
    python tools/prepare_dataset.py -i "$RAW_DIR" -o "$DATA_DIR" -w "$WORK_DIR" \
        --model-dir "$UVR_MODEL_DIR" ${UVR_ARGS:-}
    ;;
compare)
    # 40 s excerpts of a few songs through several UVR model chains, side by side on the review page
    conda activate "$ENV_ROOT/uvr"
    fetch_models
    python tools/autodl/compare_uvr.py --speaker-dir "$SPK_DIR" --model-dir "$UVR_MODEL_DIR"
    ;;
features)
    conda activate "$ENV_ROOT/ddsp"
    python preprocess.py -c "$SPK_CONFIG" -j "${WORKERS:-4}"
    ;;
train)
    conda activate "$ENV_ROOT/ddsp"
    export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
    python train_reflow.py -c "$SPK_CONFIG"
    ;;
infer)
    # Convert every song in test_songs/ with the newest checkpoint.
    ckpt=$(ls -t "$EXP_DIR"/model_*.pt 2>/dev/null | grep -v 'model_0.pt' | head -1 || true)
    [ -n "$ckpt" ] || { echo "no checkpoint in $EXP_DIR yet"; exit 1; }
    echo "checkpoint: $ckpt"
    conda activate "$ENV_ROOT/uvr"
    # shellcheck disable=SC2086
    python tools/prepare_dataset.py -i "$TEST_DIR" -w "$TEST_WORK_DIR" --model-dir "$UVR_MODEL_DIR" \
        --steps vocals,dereverb,karaoke ${UVR_ARGS:-}
    conda deactivate
    conda activate "$ENV_ROOT/ddsp"
    out="$INFER_DIR/$(basename "$ckpt" .pt)_key${KEY:-0}"
    mkdir -p "$out"
    for f in "$TEST_WORK_DIR"/3_karaoke/*.wav; do
        [ -e "$f" ] || continue
        echo "converting $(basename "$f")"
        python main_reflow.py -i "$f" -m "$ckpt" -o "$out/$(basename "$f")" \
            -k "${KEY:-0}" -id "${SPK_ID:-1}"
    done
    echo "results in $out"
    ;;
migrate)
    # One-off move from the single-speaker layout (until 2026-10-18) to speakers/<name>/:
    #   <data disk>/<name>_raw_songs, <name>_songs  -> speakers/<name>/downloads, songs
    #   raw_songs, preprocess_work, data, exp, ... in the repo  -> speakers/$SPEAKER/...
    # Nothing is overwritten: a target that already holds files stops the job. Safe to run again.
    move() {  # src dst
        [ -e "$1" ] || return 0
        if [ -d "$2" ] && [ -n "$(ls -A "$2")" ]; then
            echo "STOP: both $1 and $2 hold files, merge them by hand"; exit 1
        fi
        # -T renames onto an empty target folder in one step (the runner creates raw_songs/ and
        # test_songs/ for the speaker meanwhile) instead of moving src inside it
        mkdir -p "$(dirname "$2")"
        mv -T "$1" "$2" && echo "moved $1 -> $2"
    }
    move_contents() {  # src dst: everything in src but the .gitignore files the repo tracks there
        [ -d "$1" ] || return 0
        [ -n "$(find "$1" -mindepth 1 -maxdepth 1 ! -name .gitignore -print -quit)" ] || return 0
        mkdir -p "$2"
        while IFS= read -r -d '' f; do
            if [ -e "$2/$(basename "$f")" ]; then echo "STOP: $2/$(basename "$f") exists already"; exit 1; fi
            mv "$f" "$2/"
        done < <(find "$1" -mindepth 1 -maxdepth 1 ! -name .gitignore -print0)
        echo "moved the contents of $1 -> $2"
    }
    shopt -s nullglob
    for d in "$DATA_ROOT"/*_raw_songs; do
        n="$(basename "$d" _raw_songs)"; move "$d" "$SPEAKERS_DIR/$n/downloads"
    done
    for d in "$DATA_ROOT"/*_songs; do
        n="$(basename "$d" _songs)"; move "$d" "$SPEAKERS_DIR/$n/songs"
    done
    move raw_songs "$RAW_DIR"
    move test_songs "$TEST_DIR"
    move preprocess_work "$WORK_DIR"
    move preprocess_work_test "$TEST_WORK_DIR"
    move infer_out "$INFER_DIR"
    for split in train val; do
        for f in data/$split/*; do  # features from preprocess.py (units/, f0/, ...) when it has run
            [ "$(basename "$f")" = audio ] || move "$f" "$DATA_DIR/$split/$(basename "$f")"
        done
        move_contents "data/$split/audio" "$DATA_DIR/$split/audio"
    done
    move_contents exp/reflow-test "$EXP_DIR"
    rmdir exp/reflow-test 2>/dev/null || true
    echo "== speakers"
    for s in "$SPEAKERS_DIR"/*/; do
        echo "$(basename "$s"): $(for d in "$s"*/; do echo -n "$(basename "$d")($(find "$d" -type f | wc -l)) "; done)"
    done
    ;;
*)
    echo "unknown job: $JOB"; exit 2
    ;;
esac
