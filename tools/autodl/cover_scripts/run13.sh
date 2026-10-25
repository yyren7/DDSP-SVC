#!/bin/bash
# Covers, round 13 (2026-10-25): the backing of every song of rounds 1-3 converted in stereo for both speakers, as
# run10.sh tried on liangrenfen: the backing before dereverb (harm_vocals.flac of the local pack, copied up to
# _in13/<song>.flac), its left and right channel converted one by one with model_80000.pt and put back together,
# for cover_mix.py --harm-stereo. Conversion only, the mixing is local (remix.sh). Results in _out13/ as
# conv_harmwet_LR_<speaker>_<song>.flac.
#   nohup ./gpu_wait.sh ./run13.sh > run13.log 2>&1 &
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; R=/root/autodl-tmp/DDSP-SVC
DEV=${DEV:-cuda}; STEP=${STEP:-80000}; IN=$C/_in13; K=$C/_work13; O=$C/_out13
mkdir -p "$K" "$O"
cd "$R"
for f in "$IN"/*.flac; do
    s=$(basename "$f" .flac)
    echo "=== $s $(date +%T)"
    [ -f "$K/${s}_R.wav" ] || "$E/ddsp/bin/python" - "$f" "$K/${s}_L.wav" "$K/${s}_R.wav" <<'PY'
import sys
import soundfile as sf
x, sr = sf.read(sys.argv[1], always_2d=True)
for c, path in enumerate(sys.argv[2:]):
    sf.write(path, x[:, min(c, x.shape[1] - 1)], sr, subtype='FLOAT')
PY
    for spk in sakura_shunka pheebie; do
        [ -f "$O/conv_harmwet_LR_${spk}_$s.flac" ] && continue
        for ch in L R; do
            o=$K/${s}_${spk}_$ch.wav
            [ -f "$o" ] && continue
            if ! "$E/ddsp/bin/python" main_reflow.py -i "$K/${s}_$ch.wav" -d "$DEV" -k 0 -id 1 -o "$o" \
                    -m "/root/autodl-tmp/speakers/$spk/exp_all/model_${STEP}.pt" > "${o%.wav}.log" 2>&1; then
                tr '\r' '\n' < "${o%.wav}.log" | grep -v '%|' | tail -5
                rm -f "$o"
                exit 1
            fi
        done
        "$E/ddsp/bin/python" - "$K/${s}_${spk}_L.wav" "$K/${s}_${spk}_R.wav" "$O/conv_harmwet_LR_${spk}_$s.flac" <<'PY'
import sys
import numpy as np
import soundfile as sf
(l, sr), (r, _) = (sf.read(p) for p in sys.argv[1:3])
n = max(len(l), len(r))
sf.write(sys.argv[3], np.stack([np.pad(l, (0, n - len(l))), np.pad(r, (0, n - len(r)))], axis=1), sr, subtype='PCM_24')
PY
    done
done
ls "$O" | wc -l
echo "=== done $(date +%T)"
