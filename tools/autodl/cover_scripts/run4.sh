#!/bin/bash
# Covers, round 4: Tell Your World (yachiyo) again. Its "和声版" off vocal carries a copy of the lead at about
# -9 dB (correlation 0.91 with the lead), so original - that off vocal held only 0.64 of the lead, and the mix
# over that off vocal kept the original singer 5 dB under the converted one. Here the song goes the regular way
# with the plain off vocal: original - plain -> vocals, karaoke, dereverb -> conversion; for the allconv mix the
# karaoke models' backing (vocals - lead) goes through vocals, dereverb and conversion like the lead.
#   ./run4.sh
set -euo pipefail
C=/root/autodl-tmp/covers
R=/root/autodl-tmp/DDSP-SVC
E=/root/autodl-tmp/conda_envs
s=tyw_yachiyo
cd "$R"
P="$C/$s/plainphase"; IN="$C/_in4"; W="$C/_work4"; INB="$C/_in4b"; WB="$C/_work4b"
o=$(ls "$C/$s"/orig.* | head -1); p=$(ls "$C/$s"/plain.* | head -1)
echo "=== phase $(date +%T)"
[ -f "$P/vocal.wav" ] || "$E/ddsp/bin/python" tools/offvocal.py "$o" "$p" -o "$P" > /dev/null
grep -h -E '"depth_best3s_db"|"verdict"' "$P/offvocal.json" | tr -d '\n '; echo
rm -rf "$IN" "$INB"; mkdir -p "$IN" "$INB"
ln -sf "$P/vocal.wav" "$IN/$s.wav"
echo "=== separation $(date +%T)"
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$IN" -w "$W" --model-dir pretrain/uvr --steps vocals,karaoke,dereverb
# the backing at the level it has in the original (the stems brought back as cover_mix.py does), as a float file
"$E/ddsp/bin/python" - "$P/vocal.wav" "$W/1_vocals/$s.wav" "$W/2_karaoke/$s.wav" "$P/backing.wav" <<'EOF'
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
print(f'backing: stems {20 * np.log10(g):+.1f} dB back to the source, {cm.loudness(g * (v - l), sr) - cm.loudness(g * l, sr):.1f} dB against the lead')
EOF
ln -sf "$P/backing.wav" "$INB/$s.wav"
"$E/uvr/bin/python" tools/prepare_dataset.py -i "$INB" -w "$WB" --model-dir pretrain/uvr --steps vocals,dereverb
echo "=== conversion $(date +%T)"
S="$C/pack/stems/$s"
mkdir -p "$S"
for spk in pheebie sakura_shunka; do
    m="/root/autodl-tmp/speakers/$spk/exp_all/model_80000.pt"
    out="$C/out/${s}_plain_${spk}"
    [ -f "$out.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$W/3_dereverb/$s.wav" -m "$m" -o "$out.wav" -k 0 -id 1 2>&1 | tail -1
    [ -f "${out}_harm.wav" ] || "$E/ddsp/bin/python" main_reflow.py -i "$WB/3_dereverb/$s.wav" -m "$m" -o "${out}_harm.wav" -k 0 -id 1 2>&1 | tail -1
    lead=(--inst "$P/inst.wav" --source "$P/vocal.wav" --vocals "$W/1_vocals/$s.wav" --lead "$W/2_karaoke/$s.wav"
          --dry "$W/3_dereverb/$s.wav" --conv "$out.wav")
    "$E/ddsp/bin/python" tools/cover_mix.py "${lead[@]}" -o "$C/out/${s}_${spk}_mix.wav"
    "$E/ddsp/bin/python" tools/cover_mix.py "${lead[@]}" --harm-conv "${out}_harm.wav" --harm-source "$P/backing.wav" \
        --harm-dry "$WB/3_dereverb/$s.wav" --harm-wet "$WB/1_vocals/$s.wav" --no-backing -o "$C/out/${s}_${spk}_allconv_mix.wav"
    ffmpeg -v error -y -i "$out.wav" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$S/conv_${spk}.flac"
    ffmpeg -v error -y -i "${out}_harm.wav" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$S/conv_harm_${spk}.flac"
done
# the pack in the layout of the other songs: inst and plain are both the plain off vocal here
for f in "$P/inst.wav:inst" "$P/inst.wav:plain" "$W/1_vocals/$s.wav:vocals" "$W/2_karaoke/$s.wav:lead" "$W/3_dereverb/$s.wav:dry" \
         "$WB/1_vocals/$s.wav:harm_vocals" "$WB/3_dereverb/$s.wav:harm_dry"; do
    ffmpeg -v error -y -i "${f%%:*}" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$S/${f##*:}.flac"
done
cp "$P/vocal.wav" "$S/source.wav"; cp "$P/backing.wav" "$S/harm_source.wav"
echo "=== done $(date +%T)"
