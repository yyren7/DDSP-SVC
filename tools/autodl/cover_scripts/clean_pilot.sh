#!/bin/bash
# The clean-input pilot (tools/clean_stems.md): does a clean input make the conversion sound clean? For each song in
# /root/autodl-tmp/clean_pilot/<song>/ (lead.flac, inst.flac, mix.mp3, prep.json made by clean_pilot_prep.py from a
# multitrack), the raw lead vocal and the lead that the cover pipeline's three steps (vocals, karaoke, dereverb)
# separate from the official mix are converted by the same model (key 0, as for covers) and mixed the same way over
# the instrumental. The results go to the speaker's infer_out/clean_pilot/<song>/ for the review page.
#   SPK=hanamaru_hareru STEP=40000 ID=1 ./clean_pilot.sh [song ...]
set -euo pipefail
R=/root/autodl-tmp/DDSP-SVC; P=/root/autodl-tmp/clean_pilot; E=/root/autodl-tmp/conda_envs
SPK=${SPK:-hanamaru_hareru}; STEP=${STEP:-40000}; ID=${ID:-1}
MODEL=/root/autodl-tmp/speakers/$SPK/exp_all/model_$STEP.pt
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$R"
flac() { ffmpeg -nostdin -v error -y -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$2"; }
songs=("$@"); [ ${#songs[@]} -gt 0 ] || songs=($(ls "$P"))
for s in "${songs[@]}"; do
    d=$P/$s; W=$d/sep
    mkdir -p "$W/in"; ln -sf "$d/mix.mp3" "$W/in/$s.mp3"
    [ -f "$W/3_dereverb/$s.wav" ] || "$E/uvr/bin/python" tools/prepare_dataset.py -i "$W/in" -w "$W" \
        --model-dir pretrain/uvr --steps vocals,karaoke,dereverb < /dev/null
    O=/root/autodl-tmp/speakers/$SPK/infer_out/clean_pilot/$s; mkdir -p "$O"
    for v in "clean:$d/lead.flac" "sep:$W/3_dereverb/$s.wav"; do
        name=${v%%:*}; in=${v#*:}; out=$d/conv_${name}_${SPK}_${STEP}
        [ -f "$out.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$in" -m "$MODEL" -o "$out.wav" -k 0 -id "$ID" < /dev/null 2>&1 | tail -1
        "$E/ddsp/bin/python" "$HERE/clean_pilot_mix.py" "$d/inst.flac" "$d/lead.flac" "$d/prep.json" "$out.wav" "${out}_mix.wav" < /dev/null
    done
    # what the review page plays, in the order to listen to
    flac "$d/mix.mp3" "$O/0_原曲混音（官方）.flac"
    flac "$d/lead.flac" "$O/1_原唱干声（多轨原始轨，干净输入）.flac"
    flac "$W/3_dereverb/$s.wav" "$O/2_从原曲分离出的干声（现在的做法）.flac"
    flac "$d/conv_clean_${SPK}_${STEP}.wav" "$O/3_干净输入→转换_干声.flac"
    flac "$d/conv_sep_${SPK}_${STEP}.wav" "$O/4_分离输入→转换_干声.flac"
    flac "$d/conv_clean_${SPK}_${STEP}_mix.wav" "$O/5_干净输入→转换_混音.flac"
    flac "$d/conv_sep_${SPK}_${STEP}_mix.wav" "$O/6_分离输入→转换_混音.flac"
    ls "$O"
done
