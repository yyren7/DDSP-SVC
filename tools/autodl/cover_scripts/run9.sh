#!/bin/bash
# Covers, round 9 (2026-10-24): allconv v2 for hanamaru_hareru's songs with a backing of her own (run6.sh's
# _work6b): the backing as the vocals step left it, no dereverb (run7.sh), converted with model_<STEP>.pt on the
# GPU (DEV; when the GPU is shared, start it through run9_wait.sh), and mixed as remix_eq.sh mixes the
# allconv, with that backing as its own --harm-dry so that no synthetic reverb goes on top; at +0 dB, liangrenfen
# also at +2 dB, the lift of its final mix. Into infer_out/covers_<STEP>_v2/ as <歌名>_全转换v2[_+2dB].flac.
#   ./run9.sh
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; R=/root/autodl-tmp/DDSP-SVC
W=$C/_work5; WB=$C/_work6b; SPK=hanamaru_hareru; STEP=${STEP:-40000}; DEV=${DEV:-cuda}
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_${STEP}_v2; mkdir -p "$D"
flac() { ffmpeg -nostdin -v error -y -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$2"; }
cd "$R"
for p in "haohaode|我会好好的（王心凌）|0" "aini|爱你（王心凌）|0" "idol|アイドル（YOASOBI）|0" "liangrenfen|两人份的幸福（王心凌）|0 2"; do
    IFS='|' read -r s name lifts <<< "$p"
    out=$C/out/${s}_${SPK}_${STEP}; P=$C/$s/phase; hw=$WB/1_vocals/$s.wav
    echo "=== $s $(date +%T)"
    # the whole output kept in <out>_harmwet.log: a run squeezed out by the GPU's other users ends without a line
    if [ ! -f "${out}_harmwet.wav" ]; then
        if ! nice "$E/ddsp/bin/python" main_reflow.py -i "$hw" -d "$DEV" -k 0 -id 1 -o "${out}_harmwet.wav" \
                -m "/root/autodl-tmp/speakers/$SPK/exp_all/model_${STEP}.pt" > "${out}_harmwet.log" 2>&1; then
            tr '\r' '\n' < "${out}_harmwet.log" | grep -v '%|' | tail -5
            exit 1
        fi
    fi
    for lift in $lifts; do
        tag=; [ "$lift" != 0 ] && tag=_+${lift}dB
        [ -f "$D/${name}_全转换v2$tag.flac" ] && continue
        nice "$E/ddsp/bin/python" tools/cover_mix.py --inst "$P/inst.wav" --source "$P/vocal.wav" \
            --vocals "$W/1_vocals/$s.wav" --lead "$W/2_karaoke/$s.wav" --dry "$W/3_dereverb/$s.wav" --conv "$out.wav" \
            --harm-conv "${out}_harmwet.wav" --harm-source "$P/backing.wav" --harm-dry "$hw" --harm-wet "$hw" \
            --no-backing --lift "$lift" -o "${out}_eq_lift${lift}_allconv_v2_mix.wav"
        flac "${out}_eq_lift${lift}_allconv_v2_mix.wav" "$D/${name}_全转换v2$tag.flac"
    done
done
ls "$D"
echo "=== done $(date +%T)"
