#!/bin/bash
# Covers, round 5 (hanamaru_hareru, 2026-10-22): run2.sh for the speakers in $SPEAKERS; like run.sh, but a song whose off vocal keeps the chorus (so original - off vocal is the
# lead alone) skips the karaoke models, which would only nick the lead.
#   ./run2.sh song...    (each covers/<song>/ holds orig.* and inst.*)
set -euo pipefail
C=/root/autodl-tmp/covers
R=/root/autodl-tmp/DDSP-SVC
E=/root/autodl-tmp/conda_envs
STEP=${STEP:-40000}  # model_<STEP>.pt, also in the output names; hanamaru_hareru uses 40000 (2026-10-22)
SONGS="$*"   # a song counts as lead alone when its backing (vocals - lead) is 18 dB or more below the lead
cd "$R"
IN="$C/_in5"; W="$C/_work5"; WP="$C/_work5p"; INP="$C/_in5p"
rm -rf "$IN" "$INP"; mkdir -p "$IN" "$INP" "$C/out"
echo "=== phase $(date +%T)"
for s in $SONGS; do
    o=$(ls "$C/$s"/orig.* | head -1); i=$(ls "$C/$s"/inst.* | head -1)
    [ -f "$C/$s/phase/vocal.wav" ] || "$E/ddsp/bin/python" tools/offvocal.py "$o" "$i" -o "$C/$s/phase" > /dev/null
    grep -h -E '"depth_best3s_db"|"verdict"' "$C/$s/phase/offvocal.json" | tr -d '\n '; echo " $s"
    ln -sf "$C/$s/phase/vocal.wav" "$IN/$s.wav"
done
echo "=== separation $(date +%T)"
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$IN" -w "$W" --model-dir pretrain/uvr --steps vocals,karaoke,dereverb
echo "=== chorus check $(date +%T)"
PURE=$("$E/ddsp/bin/python" - "$W" $SONGS <<'EOF'
import sys
import numpy as np
import soundfile as sf
w, songs = sys.argv[1], sys.argv[2:]
pure = []
for s in songs:
    v, sr = sf.read(f'{w}/1_vocals/{s}.wav', always_2d=True)
    l, _ = sf.read(f'{w}/2_karaoke/{s}.wav', always_2d=True)
    n = min(len(v), len(l))
    v, l = v[:n].mean(1), l[:n].mean(1)
    b = v - l
    frames = [(b[i:i + sr], l[i:i + sr]) for i in range(0, n - sr, sr)]
    act = [(x, y) for x, y in frames if np.sqrt(np.mean(y ** 2)) > 0.01]
    ratio = 10 * np.log10(np.mean([np.mean(x ** 2) for x, _ in act]) / np.mean([np.mean(y ** 2) for _, y in act]))
    print(f'{s}: backing {ratio:.1f} dB against the lead', file=sys.stderr)
    if ratio <= -18:
        pure.append(s)
print(' '.join(pure))
EOF
)
echo "lead alone (karaoke skipped): ${PURE:-none}"
if [ -n "$PURE" ]; then
    for s in $PURE; do ln -sf "$C/$s/phase/vocal.wav" "$INP/$s.wav"; done
    "$E/uvr/bin/python" tools/prepare_dataset.py -i "$INP" -w "$WP" --model-dir pretrain/uvr --steps vocals,dereverb
fi
echo "=== conversion $(date +%T)"
for s in $SONGS; do
    if [[ " $PURE " == *" $s "* ]]; then
        voc="$WP/1_vocals/$s.wav"; lead="$voc"; dry="$WP/3_dereverb/$s.wav"
    else
        voc="$W/1_vocals/$s.wav"; lead="$W/2_karaoke/$s.wav"; dry="$W/3_dereverb/$s.wav"
    fi
    for spk in ${SPEAKERS:-hanamaru_hareru}; do
        out="$C/out/${s}_${spk}_${STEP}"
        [ -f "$out.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$dry" \
            -m "/root/autodl-tmp/speakers/$spk/exp_all/model_${STEP}.pt" -o "$out.wav" -k 0 -id 1 2>&1 | tail -1
        [ -f "${out}_mix.wav" ] || "$E/ddsp/bin/python" tools/cover_mix.py --inst "$C/$s/phase/inst.wav" --source "$C/$s/phase/vocal.wav" \
            --vocals "$voc" --lead "$lead" --dry "$dry" --conv "$out.wav" -o "${out}_mix.wav"
    done
    mkdir -p "$C/pack/stems/$s"
    cp "$C/$s/phase/vocal.wav" "$C/pack/stems/$s/source.wav"  # float: original - off vocal can peak over 1
    for f in "$C/$s/phase/inst.wav:inst" "$voc:vocals" "$lead:lead" "$dry:dry" \
             $(for spk in ${SPEAKERS:-hanamaru_hareru}; do echo "$C/out/${s}_${spk}_${STEP}.wav:conv_${spk}_${STEP}"; done); do
        ffmpeg -v error -y -i "${f%%:*}" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$C/pack/stems/$s/${f##*:}.flac"
    done
done
echo "=== done $(date +%T)"
