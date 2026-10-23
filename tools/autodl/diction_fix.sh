#!/bin/bash
# Diction fixes of a cover on the instance (tools/diction.py, see tools/README.md), with the folders of
# cover_scripts/: covers/<song>/ holds the song's fix list diction_fixes.tsv and its mix settings mix.args,
# covers/cand/<song>/ the dry lead (dry.wav) and its conversions (0_40k.wav the one in the mix, cand.sh).
#   diction_fix.sh clips <song> <title>          spans of the new lines, and every line's clips on the review page
#   diction_fix.sh cand <song> <step> <seed>...  more candidates: model_<step>.pt with these seeds (needs the GPU)
#   diction_fix.sh apply <song> <title>          the chosen takes spliced in and the cover mixed again with mix.args,
#                                                as infer_out/covers_final/<title>_咬字修补.flac
# <song> is the folder under covers/ (liangrenfen), <title> the song's name on the review page (两人份的幸福（王心凌）).
# SPK is the voice (default hanamaru_hareru, models in its exp_all/), STEP the step in the output's name (40000).
set -euo pipefail
source "$(dirname "$0")/config.sh"
SPK=${SPK:-hanamaru_hareru}; STEP=${STEP:-40000}
C="$DATA_ROOT/covers"; PY="$ENV_ROOT/ddsp/bin/python"; DICTION="$REPO_DIR/tools/diction.py"
[ $# -ge 3 ] || { sed -n 2,10p "$0"; exit 1; }
cmd=$1; s=$2; shift 2
CAND="$C/cand/$s"; FIXES="$C/$s/diction_fixes.tsv"
case $cmd in
clips)
    [ -f "$FIXES" ] || { echo "no $FIXES: one line per report, time<TAB>heard<TAB>want"; exit 1; }
    "$PY" "$DICTION" clips --cand "$CAND" --fixes "$FIXES" -o "$SPEAKERS_DIR/$SPK/diction/$1";;
cand)
    step=$1; shift
    "$PY" "$DICTION" cand --cand "$CAND" --model "$SPEAKERS_DIR/$SPK/exp_all/model_$step.pt" --seed "$@";;
apply)
    [ -f "$C/$s/mix.args" ] || { echo "no $C/$s/mix.args: the song's cover_mix.py settings (tools/README.md)"; exit 1; }
    out="$C/out/${s}_${SPK}_${STEP}_fixed"; F="$SPEAKERS_DIR/$SPK/infer_out/covers_final"
    "$PY" "$DICTION" apply --cand "$CAND" --fixes "$FIXES" -o "$out.wav"
    "$PY" "$REPO_DIR/tools/cover_mix.py" "@$C/$s/mix.args" --conv "$out.wav" -o "${out}_mix.wav"
    mkdir -p "$F"
    ffmpeg -nostdin -v error -y -i "${out}_mix.wav" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$F/${1}_咬字修补.flac"
    echo "$F/${1}_咬字修补.flac";;
*) sed -n 2,10p "$0"; exit 1;;
esac
