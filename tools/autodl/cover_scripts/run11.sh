#!/bin/bash
# Covers, round 11 (2026-10-24): two spots of run10.sh's stereo backing of liangrenfen, a noise burst at 1:08 and a
# pitch jumping in steps at 2:08, converted again with other seeds (torch.manual_seed before main_reflow.py, as
# diction.py cand does). Each seed's take is spliced into the current backing between the quietest points around
# the spot (20 ms equal-power crossfades), mixed as run10.sh mixes, and cut to 9 s around each spot for listening,
# next to the current take: infer_out/covers_<STEP>_v2/<歌名>_换种子/<1分08|2分08>_<现在|种子N>.flac.
#   MIX=/tmp/cover_mix_stereo.py nohup ./gpu_wait.sh ./run11.sh > run11.log 2>&1 &
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; R=/root/autodl-tmp/DDSP-SVC
W=$C/_work5; WB=$C/_work6b; SPK=hanamaru_hareru; STEP=${STEP:-40000}; DEV=${DEV:-cuda}; MIX=${MIX:-$R/tools/cover_mix.py}
SEEDS=${SEEDS:-1 2 3 4}
s=liangrenfen; name=两人份的幸福（王心凌）; lift=2
out=$C/out/${s}_${SPK}_${STEP}; P=$C/$s/phase; hw=$WB/1_vocals/$s.wav; IN=$C/_in10; K=$C/_work11
D=/root/autodl-tmp/speakers/$SPK/infer_out/covers_${STEP}_v2/${name}_换种子
mkdir -p "$K" "$D"
cd "$R"
echo "=== conversion $(date +%T)"
for seed in $SEEDS; do
    for ch in L R; do
        o=$K/${s}_harmwet_${ch}_s$seed.wav
        [ -f "$o" ] && continue
        if ! "$E/ddsp/bin/python" -c "import sys, runpy, torch; torch.manual_seed(int(sys.argv[1])); sys.argv = ['main_reflow.py'] + sys.argv[2:]; runpy.run_path('main_reflow.py', run_name='__main__')" \
                "$seed" -i "$IN/${s}_$ch.wav" -d "$DEV" -k 0 -id 1 -o "$o" \
                -m "/root/autodl-tmp/speakers/$SPK/exp_all/model_${STEP}.pt" > "${o%.wav}.log" 2>&1; then
            tr '\r' '\n' < "${o%.wav}.log" | grep -v '%|' | tail -5
            exit 1
        fi
    done
done
echo "=== splice $(date +%T)"
"$E/ddsp/bin/python" - "$hw" "${out}_harmwet_LR.wav" "$K" "$s" $SEEDS <<'PY'
import sys
import numpy as np
import soundfile as sf
hw_path, base_path, K, s, *seeds = sys.argv[1:]
hw, sr = sf.read(hw_path, always_2d=True)
base, _ = sf.read(base_path, always_2d=True)
e = (hw ** 2).sum(axis=1)
n = int(0.02 * sr)
fr = e[:len(e) // n * n].reshape(-1, n).mean(axis=1)
def quiet(a, b):  # the quietest 20 ms frame between a and b seconds, as a sample index
    i, j = int(a * sr) // n, int(b * sr) // n
    return (i + int(np.argmin(fr[i:j]))) * n
spans = [(quiet(65.0, 66.2), quiet(69.2, 70.2)), (quiet(127.2, 128.0), quiet(129.4, 131.5))]
print('spans', ', '.join(f'{a / sr:.2f}-{b / sr:.2f} s' for a, b in spans))
x = int(0.02 * sr)
up = np.sin(np.linspace(0, np.pi / 2, x)) [:, None]
for seed in seeds:
    take = np.stack([sf.read(f'{K}/{s}_harmwet_{ch}_s{seed}.wav')[0] for ch in 'LR'], axis=1)
    take = np.pad(take, ((0, max(0, len(base) - len(take))), (0, 0)))[:len(base)]
    y = base.copy()
    for a, b in spans:
        y[a:b] = take[a:b]
        y[a - x:a] = base[a - x:a] * up[::-1] + take[a - x:a] * up  # into the take
        y[b:b + x] = take[b:b + x] * up[::-1] + base[b:b + x] * up  # back to the current one
    sf.write(f'{K}/{s}_harmwet_LR_s{seed}.wav', y, sr, subtype='FLOAT')
PY
echo "=== mix $(date +%T)"
cut() {  # cut <mix> <tag>: 9 s around each spot
    ffmpeg -nostdin -v error -y -ss 64 -t 9 -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$D/1分08_$2.flac"
    ffmpeg -nostdin -v error -y -ss 124 -t 9 -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$D/2分08_$2.flac"
}
cut "${out}_eq_lift${lift}_allconv_v2s_mix.wav" 现在
for seed in $SEEDS; do
    m=$K/${s}_eq_lift${lift}_allconv_v2s_s${seed}_mix.wav
    [ -f "$m" ] || nice "$E/ddsp/bin/python" "$MIX" --inst "$P/inst.wav" --source "$P/vocal.wav" \
        --vocals "$W/1_vocals/$s.wav" --lead "$W/2_karaoke/$s.wav" --dry "$W/3_dereverb/$s.wav" --conv "$out.wav" \
        --harm-conv "$K/${s}_harmwet_LR_s$seed.wav" --harm-stereo --harm-source "$P/backing.wav" --harm-dry "$hw" \
        --harm-wet "$hw" --no-backing --lift "$lift" -o "$m" | sed 's/.*: stems/  stems/'
    cut "$m" "种子$seed"
done
ls "$D"
echo "=== done $(date +%T)"
