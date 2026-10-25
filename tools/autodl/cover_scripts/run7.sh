#!/bin/bash
# Covers, round 7: the backing vocals of akatsuki and tyw_yachiyo converted again, this time without dereverb.
# The dereverb model took their stacked backing for reverb, 15-24 dB of it in the choruses (3 dB in the
# verses), so the converted backing was missing there and the whole-song loudness match then pushed the verses
# 11 dB over the original. Here the backing as the vocals step left it (harm_vocals.flac from the local pack,
# copied up to _in7/<song>.flac) is converted, reverb and all; cover_mix.py then gets it as --harm-dry too, so
# that no synthetic reverb is added on top.
#   ./run7.sh
set -euo pipefail
C=/root/autodl-tmp/covers
R=/root/autodl-tmp/DDSP-SVC
E=/root/autodl-tmp/conda_envs
cd "$R"
for s in akatsuki tyw_yachiyo; do
    for spk in pheebie sakura_shunka; do
        out="$C/out/${s}_${spk}_harmwet.wav"
        [ -f "$out" ] || "$E/ddsp/bin/python" main_reflow.py -i "$C/_in7/$s.flac" \
            -m "/root/autodl-tmp/speakers/$spk/exp_all/model_80000.pt" -o "$out" -k 0 -id 1 2>&1 | tail -1
        ffmpeg -nostdin -v error -y -i "$out" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$C/_in7/conv_harmwet_${spk}_$s.flac"
    done
done
echo "=== done $(date +%T)"
