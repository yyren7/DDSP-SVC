#!/bin/bash
# Covers, round 3: songs with an off vocal that keeps the chorus (inst.*) and one without it (plain.*), both of
# the original's master. Their difference is the backing vocals alone: cleaned (vocals) and dried (dereverb),
# converted like the lead, and mixed with the converted lead over the plain off vocal, so that every voice in
# the "allconv" mix is the converted singer.
#   ./run3.sh song...   (after run2.sh, which made covers/<song>/phase/ and the converted lead)
set -euo pipefail
C=/root/autodl-tmp/covers
R=/root/autodl-tmp/DDSP-SVC
E=/root/autodl-tmp/conda_envs
SONGS="$*"
cd "$R"
IN="$C/_in3"; W="$C/_work3"
rm -rf "$IN"; mkdir -p "$IN"
echo "=== backing $(date +%T)"
for s in $SONGS; do
    p=$(ls "$C/$s"/plain.* | head -1)
    # the chorus off vocal as run2 aligned it to the original, minus the plain one: the backing vocals on the
    # original's timeline; harm/inst.wav is the plain off vocal on that timeline
    [ -f "$C/$s/harm/vocal.wav" ] || "$E/ddsp/bin/python" tools/offvocal.py "$C/$s/phase/inst.wav" "$p" -o "$C/$s/harm" > /dev/null
    grep -h -E '"depth_best3s_db"' "$C/$s/harm/offvocal.json" | tr -d '\n '; echo " $s"
    ln -sf "$C/$s/harm/vocal.wav" "$IN/$s.wav"
done
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$IN" -w "$W" --model-dir pretrain/uvr --steps vocals,dereverb
echo "=== conversion $(date +%T)"
for s in $SONGS; do
    if [ -f "$C/_work2p/1_vocals/$s.wav" ]; then
        voc="$C/_work2p/1_vocals/$s.wav"; lead="$voc"; dry="$C/_work2p/3_dereverb/$s.wav"
    else
        voc="$C/_work2/1_vocals/$s.wav"; lead="$C/_work2/2_karaoke/$s.wav"; dry="$C/_work2/3_dereverb/$s.wav"
    fi
    for spk in pheebie sakura_shunka; do
        out="$C/out/${s}_${spk}"
        [ -f "${out}_harm.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$W/3_dereverb/$s.wav" \
            -m "/root/autodl-tmp/speakers/$spk/exp_all/model_80000.pt" -o "${out}_harm.wav" -k 0 -id 1 2>&1 | tail -1
        [ -f "${out}_allconv_mix.wav" ] || "$E/ddsp/bin/python" tools/cover_mix.py --inst "$C/$s/harm/inst.wav" --source "$C/$s/phase/vocal.wav" \
            --vocals "$voc" --lead "$lead" --dry "$dry" --conv "$out.wav" --harm-conv "${out}_harm.wav" \
            --harm-source "$C/$s/harm/vocal.wav" --harm-dry "$W/3_dereverb/$s.wav" --harm-wet "$W/1_vocals/$s.wav" \
            -o "${out}_allconv_mix.wav"
    done
    cp "$C/$s/harm/vocal.wav" "$C/pack/stems/$s/harm_source.wav"
    for f in "$C/$s/harm/inst.wav:plain" "$W/1_vocals/$s.wav:harm_vocals" "$W/3_dereverb/$s.wav:harm_dry" \
             "$C/out/${s}_pheebie_harm.wav:conv_harm_pheebie" "$C/out/${s}_sakura_shunka_harm.wav:conv_harm_sakura_shunka"; do
        ffmpeg -v error -y -i "${f%%:*}" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$C/pack/stems/$s/${f##*:}.flac"
    done
done
echo "=== done $(date +%T)"
