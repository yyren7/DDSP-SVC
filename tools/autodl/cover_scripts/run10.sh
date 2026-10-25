#!/bin/bash
# Covers, round 10 (2026-10-24, a trial on hanamaru_hareru's liangrenfen): allconv v2 with the backing kept in
# stereo. run9.sh's converted backing sits in the middle with the lead (L/R correlation 1.00, the original's 0.21),
# so here the left and the right channel of the backing (before dereverb, as in run9.sh) are converted one by one
# and mixed back with cover_mix.py --harm-stereo, as run9.sh mixes; at +2 dB, the lift of its final mix.
#   ./run10.sh    (MIX: a cover_mix.py with --harm-stereo; DEV)
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; R=/root/autodl-tmp/DDSP-SVC
W=$C/_work5; WB=$C/_work6b; SPK=hanamaru_hareru; STEP=${STEP:-40000}; DEV=${DEV:-cuda}; MIX=${MIX:-$R/tools/cover_mix.py}
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_${STEP}_v2; IN=$C/_in10
mkdir -p "$D" "$IN"
cd "$R"
for p in "liangrenfen|两人份的幸福（王心凌）|2"; do
    IFS='|' read -r s name lifts <<< "$p"
    out=$C/out/${s}_${SPK}_${STEP}; P=$C/$s/phase; hw=$WB/1_vocals/$s.wav
    echo "=== $s $(date +%T)"
    "$E/ddsp/bin/python" - "$hw" "$IN/${s}_L.wav" "$IN/${s}_R.wav" <<'PY'
import sys
import soundfile as sf
x, sr = sf.read(sys.argv[1], always_2d=True)
for c, path in enumerate(sys.argv[2:]):
    sf.write(path, x[:, min(c, x.shape[1] - 1)], sr, subtype='FLOAT')
PY
    for ch in L R; do
        [ -f "${out}_harmwet_$ch.wav" ] && continue
        if ! "$E/ddsp/bin/python" main_reflow.py -i "$IN/${s}_$ch.wav" -d "$DEV" -k 0 -id 1 -o "${out}_harmwet_$ch.wav" \
                -m "/root/autodl-tmp/speakers/$SPK/exp_all/model_${STEP}.pt" > "${out}_harmwet_$ch.log" 2>&1; then
            tr '\r' '\n' < "${out}_harmwet_$ch.log" | grep -v '%|' | tail -5
            exit 1
        fi
    done
    "$E/ddsp/bin/python" - "${out}_harmwet_L.wav" "${out}_harmwet_R.wav" "${out}_harmwet_LR.wav" <<'PY'
import sys
import numpy as np
import soundfile as sf
(l, sr), (r, _) = (sf.read(p) for p in sys.argv[1:3])
n = max(len(l), len(r))
sf.write(sys.argv[3], np.stack([np.pad(l, (0, n - len(l))), np.pad(r, (0, n - len(r)))], axis=1), sr, subtype='FLOAT')
PY
    for lift in $lifts; do
        nice "$E/ddsp/bin/python" "$MIX" --inst "$P/inst.wav" --source "$P/vocal.wav" \
            --vocals "$W/1_vocals/$s.wav" --lead "$W/2_karaoke/$s.wav" --dry "$W/3_dereverb/$s.wav" --conv "$out.wav" \
            --harm-conv "${out}_harmwet_LR.wav" --harm-stereo --harm-source "$P/backing.wav" --harm-dry "$hw" \
            --harm-wet "$hw" --no-backing --lift "$lift" -o "${out}_eq_lift${lift}_allconv_v2s_mix.wav"
        ffmpeg -nostdin -v error -y -i "${out}_eq_lift${lift}_allconv_v2s_mix.wav" -c:a flac -sample_fmt s32 \
            -bits_per_raw_sample 24 "$D/${name}_全转换v2立体声_+${lift}dB.flac"
    done
done
ls "$D"
echo "=== done $(date +%T)"
