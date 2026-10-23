#!/bin/bash
# The round-5/6 mixes of model_<STEP>.pt as FLAC under hanamaru_hareru's infer_out/covers_<STEP>/ (the review page's 转换结果)
#   ./infer_pack.sh [STEP]    (default 40000)
set -euo pipefail
C=/root/autodl-tmp/covers; STEP=${1:-40000}; SPK=hanamaru_hareru
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_$STEP; mkdir -p "$D"
flac() { ffmpeg -nostdin -v error -y -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$2"; }
while IFS='|' read -r s name allconv; do
    o="$C/out/${s}_${SPK}_${STEP}"
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
ls -la "$D"
