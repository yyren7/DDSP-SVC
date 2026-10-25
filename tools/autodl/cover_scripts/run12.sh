#!/bin/bash
# Covers, round 12 (2026-10-24): liangrenfen's stereo allconv (run10.sh, its two faulty spots from seed 4, run11.sh)
# with the converted backing 3 and 6 dB quieter (cover_mix.py --harm-gain), the lead as it was: quieter, the
# faults the conversion left in the backing stand out less. Mixing only, no GPU.
#   MIX=/tmp/cover_mix_stereo.py ./run12.sh
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; R=/root/autodl-tmp/DDSP-SVC
W=$C/_work5; WB=$C/_work6b; SPK=hanamaru_hareru; STEP=${STEP:-40000}; MIX=${MIX:-$R/tools/cover_mix.py}
s=liangrenfen; name=两人份的幸福（王心凌）; lift=2
out=$C/out/${s}_${SPK}_${STEP}; P=$C/$s/phase; hw=$WB/1_vocals/$s.wav
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_${STEP}_v2
cd "$R"
for hgain in -3 -6; do
    m=${out}_eq_lift${lift}_allconv_v2s_harm${hgain}_mix.wav
    nice "$E/ddsp/bin/python" "$MIX" --inst "$P/inst.wav" --source "$P/vocal.wav" \
        --vocals "$W/1_vocals/$s.wav" --lead "$W/2_karaoke/$s.wav" --dry "$W/3_dereverb/$s.wav" --conv "$out.wav" \
        --harm-conv "${out}_harmwet_LR.wav" --harm-stereo --harm-gain "$hgain" --harm-source "$P/backing.wav" \
        --harm-dry "$hw" --harm-wet "$hw" --no-backing --lift "$lift" -o "$m" | sed 's/.*: stems/  stems/'
    ffmpeg -nostdin -v error -y -i "$m" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$D/${name}_全转换v2立体声_+2dB_和声${hgain}dB.flac"
done
ls "$D"
