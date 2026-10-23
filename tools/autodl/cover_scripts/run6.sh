#!/bin/bash
# Covers, round 6 (hanamaru_hareru, 2026-10-22): the allconv mix of round-5 songs whose sung backing is loud
# (run5.sh mixed the original singer's backing in): the karaoke models' backing (vocals - lead, at the level it has
# in the original) goes through vocals and dereverb and is converted like the lead, as in run4.sh.
#   ./run6.sh song...    (songs already through run5.sh)
set -euo pipefail
C=/root/autodl-tmp/covers; R=/root/autodl-tmp/DDSP-SVC; E=/root/autodl-tmp/conda_envs
W="$C/_work5"; INB="$C/_in6b"; WB="$C/_work6b"; SPK=${SPEAKERS:-hanamaru_hareru}; STEP=${STEP:-40000}  # model_<STEP>.pt, also in the output names
cd "$R"; rm -rf "$INB"; mkdir -p "$INB"
for s in "$@"; do
    P="$C/$s/phase"
    "$E/ddsp/bin/python" - "$P/vocal.wav" "$W/1_vocals/$s.wav" "$W/2_karaoke/$s.wav" "$P/backing.wav" <<'EOF2'
import sys
import numpy as np
import soundfile as sf
sys.path.insert(0, 'tools')
import cover_mix as cm
src, voc, lead, out = sys.argv[1:]
s, sr = cm.load(src)
v, l = (cm.fit(cm.load(f)[0], len(s)) for f in (voc, lead))
g = cm.restore(s, v)
sf.write(out, g * (v - l), sr, subtype='FLOAT')
print(f'{out}: backing {cm.loudness(g * (v - l), sr) - cm.loudness(g * l, sr):.1f} dB against the lead')
EOF2
    ln -sf "$P/backing.wav" "$INB/$s.wav"
done
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$INB" -w "$WB" --model-dir pretrain/uvr --steps vocals,dereverb
for s in "$@"; do
    P="$C/$s/phase"
    for spk in $SPK; do
        m="/root/autodl-tmp/speakers/$spk/exp_all/model_${STEP}.pt"; out="$C/out/${s}_${spk}_${STEP}"
        [ -f "${out}_harm.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$WB/3_dereverb/$s.wav" -m "$m" -o "${out}_harm.wav" -k 0 -id 1 2>&1 | tail -1
        "$E/ddsp/bin/python" tools/cover_mix.py --inst "$P/inst.wav" --source "$P/vocal.wav" --vocals "$W/1_vocals/$s.wav" \
            --lead "$W/2_karaoke/$s.wav" --dry "$W/3_dereverb/$s.wav" --conv "$out.wav" \
            --harm-conv "${out}_harm.wav" --harm-source "$P/backing.wav" --harm-dry "$WB/3_dereverb/$s.wav" \
            --harm-wet "$WB/1_vocals/$s.wav" --no-backing -o "${out}_allconv_mix.wav"
    done
done
echo "=== done $(date +%T)"
