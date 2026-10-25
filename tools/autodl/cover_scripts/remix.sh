#!/bin/bash
# Every cover of rounds 1-3 mixed again from the packed stems (_stems/<song>/) with tools/cover_mix.py (or $MIX),
# here on the CPU, into $OUT (best/) as <歌名>_<旬夏|菲比>_<版本>.flac, with the settings chosen on hanamaru_hareru's
# 两人份的幸福 (2026-10-24): EQ at its default and the vocals LIFT dB over the original's. Each song in two versions:
# the original singer's backing as sung (保留原唱和声), and allconv (全转换), where that backing is converted too,
# from before dereverb and channel by channel (run13.sh: conv_harmwet_LR_<speaker>.flac), HGAIN dB against the
# original's, over the off vocal without the chorus (plain.flac where there is one). akunohana and yuukyou also
# without backing (不要和声): theirs holds a double of the lead. rokutousei has no backing of its own: one version.
# CENTER_BACKING songs keep their backing in the middle as the original has it (left/right correlation 0.71-0.90):
# converted as one (conv_harmwet_<speaker>.flac of run7.sh/run8.sh), since the two channels converted one by one
# come out unrelated (correlation 0) and turn a backing in the middle into a wide double.
# The previous scheme (mix/, mix2/) is remix_1023.sh.
#   ./remix.sh [song...]    PARTS="mix allconv" picks the versions; several at once: xargs -P 4 -n 1 ./remix.sh
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-/d/svc-mv/.venv/Scripts/python.exe}
MIX=${MIX:-../tools/cover_mix.py}
LIFT=${LIFT:-2}; HGAIN=${HGAIN:-0}; OUT=${OUT:-best}; PARTS=${PARTS:-mix allconv}
NOBACKING="akunohana yuukyou"
CENTER_BACKING="akunohana yuukyou sakura kimishira wim_yachiyo brave"
declare -A TITLE=([akunohana]=わが﨟たし悪の華 [colors]=COLORS [hitomi]=瞳ノ翼 [phoenix]="PHOENIX PRAYER"
                  [sakura]=sakura [yuukyou]=勇侠青春謳 [akatsuki]=暁の車 [xiaoxingyun]=小幸运
                  [tyw_yachiyo]="Tell Your World" [wim_yachiyo]="World is Mine" [rokutousei]=六等星の夜
                  [brave]="Brave Song" [kimishira]=君の知らない物語 [togetsukyo]=渡月橋)
declare -A NAME=([sakura_shunka]=旬夏 [pheebie]=菲比)
SONGS="${*:-akunohana colors hitomi phoenix sakura yuukyou akatsuki xiaoxingyun tyw_yachiyo wim_yachiyo rokutousei brave kimishira togetsukyo}"
mkdir -p "$OUT"
for s in $SONGS; do
    d=_stems/$s
    stems=(--source "$d/source.wav" --vocals "$d/vocals.flac" --lead "$d/lead.flac" --dry "$d/dry.flac" --lift "$LIFT")
    plain=$d/inst.flac; [ -f "$d/plain.flac" ] && plain=$d/plain.flac
    for spk in sakura_shunka pheebie; do
        o="$OUT/${TITLE[$s]}_${NAME[$spk]}"
        if [[ " $PARTS " == *" mix "* ]]; then
            "$PY" "$MIX" --inst "$d/inst.flac" "${stems[@]}" --conv "$d/conv_$spk.flac" -o "${o}_保留原唱和声.flac"
            if [[ " $NOBACKING " == *" $s "* ]]; then
                "$PY" "$MIX" --inst "$d/inst.flac" "${stems[@]}" --conv "$d/conv_$spk.flac" --no-backing \
                    -o "${o}_不要和声.flac"
            fi
        fi
        harm=(--harm-conv "$d/conv_harmwet_LR_$spk.flac" --harm-stereo)
        [[ " $CENTER_BACKING " == *" $s "* ]] && harm=(--harm-conv "$d/conv_harmwet_$spk.flac")
        if [[ " $PARTS " == *" allconv "* ]] && [ -f "${harm[1]}" ]; then
            "$PY" "$MIX" --inst "$plain" "${stems[@]}" --conv "$d/conv_$spk.flac" "${harm[@]}" --harm-gain "$HGAIN" \
                --harm-source "$d/harm_source.wav" --harm-dry "$d/harm_vocals.flac" --harm-wet "$d/harm_vocals.flac" \
                --no-backing -o "${o}_全转换.flac"
        fi
    done
done
