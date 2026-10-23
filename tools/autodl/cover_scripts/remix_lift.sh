#!/bin/bash
# hanamaru_hareru's 4 allconv mixes of model_40000 with the vocals lifted 2 and 4 dB over the original's balance,
# next to the +0 dB ones, in infer_out/covers_40000_lift/
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; MIX=/root/autodl-tmp/DDSP-SVC/tools/cover_mix.py
W=$C/_work5; WB=$C/_work6b; SPK=hanamaru_hareru; STEP=40000
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_${STEP}_lift; mkdir -p "$D"
flac() { ffmpeg -nostdin -v error -y -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$2"; }
cd /root/autodl-tmp/DDSP-SVC
for p in "aini|爱你（王心凌）" "idol|アイドル（YOASOBI）" "liangrenfen|两人份的幸福（王心凌）" "haohaode|我会好好的（王心凌）"; do
    s=${p%%|*}; name=${p##*|}; out=$C/out/${s}_${SPK}_${STEP}; P=$C/$s/phase

    for lift in 0 2 4; do
        nice "$E/ddsp/bin/python" $MIX --inst $P/inst.wav --source $P/vocal.wav --vocals $W/1_vocals/$s.wav \
            --lead $W/2_karaoke/$s.wav --dry $W/3_dereverb/$s.wav --conv $out.wav --harm-conv ${out}_harm.wav \
            --harm-source $P/backing.wav --harm-dry $WB/3_dereverb/$s.wav --harm-wet $WB/1_vocals/$s.wav --no-backing \
            --lift $lift -o ${out}_eq_lift${lift}_allconv_mix.wav
        flac ${out}_eq_lift${lift}_allconv_mix.wav "$D/${name}_全转换_+${lift}dB.flac"
    done
done
ls "$D"
