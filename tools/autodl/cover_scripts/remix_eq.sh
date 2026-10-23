#!/bin/bash
# hanamaru_hareru's 9 mixes of model_40000 again with the EQ / balance / fixed-gain limiter version of tools/cover_mix.py, as <...>_eq*.wav
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; MIX=/root/autodl-tmp/DDSP-SVC/tools/cover_mix.py
W=$C/_work5; WP=$C/_work5p; WB=$C/_work6b; SPK=hanamaru_hareru; STEP=40000
cd /root/autodl-tmp/DDSP-SVC
for s in haru yuusha haohaode aini idol liangrenfen; do
    case $s in haru|yuusha) voc=$WP/1_vocals/$s.wav; lead=$voc; dry=$WP/3_dereverb/$s.wav;;
               *) voc=$W/1_vocals/$s.wav; lead=$W/2_karaoke/$s.wav; dry=$W/3_dereverb/$s.wav;; esac
    out=$C/out/${s}_${SPK}_${STEP}; P=$C/$s/phase
    nice "$E/ddsp/bin/python" $MIX --inst $P/inst.wav --source $P/vocal.wav --vocals $voc --lead $lead --dry $dry \
        --conv $out.wav -o ${out}_eq_mix.wav
    case $s in aini|idol|liangrenfen)
        nice "$E/ddsp/bin/python" $MIX --inst $P/inst.wav --source $P/vocal.wav --vocals $voc --lead $lead --dry $dry \
            --conv $out.wav --harm-conv ${out}_harm.wav --harm-source $P/backing.wav --harm-dry $WB/3_dereverb/$s.wav \
            --harm-wet $WB/1_vocals/$s.wav --no-backing -o ${out}_eq_allconv_mix.wav;; esac
done
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_${STEP}_eq; mkdir -p "$D"
flac() { ffmpeg -nostdin -v error -y -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$2"; }
while IFS='|' read -r s name allconv; do
    o="$C/out/${s}_${SPK}_${STEP}_eq"
    if [ "$allconv" = 1 ]; then
        flac "${o}_mix.wav" "$D/${name}_和声保留原唱.flac"; flac "${o}_allconv_mix.wav" "$D/${name}_全转换.flac"
    else
        flac "${o}_mix.wav" "$D/${name}.flac"
    fi
done <<'LIST'
haru|晴る（ヨルシカ）|0
yuusha|勇者（YOASOBI）|0
haohaode|我会好好的（王心凌）|0
aini|爱你（王心凌）|1
idol|アイドル（YOASOBI）|1
liangrenfen|两人份的幸福（王心凌）|1
LIST
ls "$D" | wc -l
