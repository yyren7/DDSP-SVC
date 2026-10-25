#!/bin/bash
# Covers, round 8 (2026-10-23): an allconv v2 mix for every song of rounds 1-3, as run7.sh did for akatsuki and
# tyw_yachiyo. The original singer's backing that the plain off vocal lacks (vocals - lead; for wim_yachiyo that
# plus the chorus difference), made from the local pack and sent up at half level as _in8/<song>.flac, goes
# through the vocals step only, no dereverb, and is converted; xiaoxingyun's chorus difference is through the
# vocals step already (_in8x/). Results in _out8/: harm_vocals_<song>.flac, conv_harmwet_<speaker>_<song>.flac.
#   ./run8.sh
set -euo pipefail
C=/root/autodl-tmp/covers; R=/root/autodl-tmp/DDSP-SVC; E=/root/autodl-tmp/conda_envs
W="$C/_work8"; O="$C/_out8"
cd "$R"; mkdir -p "$O"
echo "=== vocals $(date +%T)"
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$C/_in8" -w "$W" --model-dir pretrain/uvr --steps vocals
echo "=== conversion $(date +%T)"
for f in "$W"/1_vocals/*.wav "$C"/_in8x/*.flac; do
    s=$(basename "${f%.*}")
    if [[ $f == *.wav ]]; then
        ffmpeg -nostdin -v error -y -i "$f" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$O/harm_vocals_$s.flac"
    fi
    for spk in pheebie sakura_shunka; do
        out="$O/${s}_${spk}.wav"
        [ -f "$out" ] || "$E/ddsp/bin/python" main_reflow.py -i "$f" \
            -m "/root/autodl-tmp/speakers/$spk/exp_all/model_80000.pt" -o "$out" -k 0 -id 1 2>&1 | tail -1
        ffmpeg -nostdin -v error -y -i "$out" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$O/conv_harmwet_${spk}_$s.flac"
    done
done
echo "=== done $(date +%T)"
