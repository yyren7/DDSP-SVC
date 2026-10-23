#!/bin/bash
# Covers: phase-cancelled vocal -> vocals / karaoke / dereverb -> DDSP-SVC 80k conversion -> mix
set -euo pipefail
C=/root/autodl-tmp/covers
R=/root/autodl-tmp/DDSP-SVC
E=/root/autodl-tmp/conda_envs
SONGS="colors hitomi akunohana sakura phoenix yuukyou"
cd "$R"
mkdir -p "$C/_in" "$C/out"
echo "=== phase $(date +%T)"
for s in $SONGS; do
    if [ ! -f "$C/$s/phase/vocal.wav" ]; then
        "$E/ddsp/bin/python" tools/offvocal.py "$C/$s/orig.m4a" "$C/$s/inst.m4a" -o "$C/$s/phase" | grep -E 'depth_best3s|verdict' | tr '\n' ' '
        echo "$s"
    fi
    ln -sf "$C/$s/phase/vocal.wav" "$C/_in/$s.wav"
done
echo "=== separation $(date +%T)"
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$C/_in" -w "$C/_work" --model-dir pretrain/uvr --steps vocals,karaoke,dereverb
echo "=== conversion $(date +%T)"
for s in $SONGS; do
    for spk in pheebie sakura_shunka; do
        out="$C/out/${s}_${spk}"
        [ -f "$out.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$C/_work/3_dereverb/$s.wav" \
            -m "/root/autodl-tmp/speakers/$spk/exp_all/model_80000.pt" -o "$out.wav" -k 0 -id 1 2>&1 | tail -2
        "$E/ddsp/bin/python" tools/cover_mix.py --inst "$C/$s/phase/inst.wav" --source "$C/$s/phase/vocal.wav" --vocals "$C/_work/1_vocals/$s.wav" \
            --lead "$C/_work/2_karaoke/$s.wav" --dry "$C/_work/3_dereverb/$s.wav" --conv "$out.wav" -o "${out}_mix.wav"
    done
done
echo "=== done $(date +%T)"
