#!/bin/bash
# (2026-10-23 version, kept for remaking mix/ and mix2/; remix.sh now writes best/)
# Every cover mixed again from the packed stems (_stems/<song>/ as run2.sh, run3.sh and pack.sh on AutoDL write
# them) with tools/cover_mix.py (or $MIX), here on the CPU: round 1 into mix/, rounds 2 and 3 into mix2/. Each song
# in two versions (2026-10-23): the original singer's backing as sung, and allconv v2, where that backing is
# converted too, from before dereverb (run7.sh, run8.sh: harm_source.wav, harm_vocals.flac,
# conv_harmwet_<speaker>.flac), over the off vocal without the chorus (plain.flac where there is one).
#   ./remix.sh [song...]
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-/d/svc-mv/.venv/Scripts/python.exe}
MIX=${MIX:-../tools/cover_mix.py}
ROUND1="akunohana colors hitomi phoenix sakura yuukyou"
NOBACKING="akunohana yuukyou"  # their backing (vocals - lead) still holds a double of the lead
SONGS="${*:-$ROUND1 akatsuki xiaoxingyun tyw_yachiyo wim_yachiyo rokutousei brave kimishira togetsukyo}"
for s in $SONGS; do
    d=_stems/$s
    stems=(--source "$d/source.wav" --vocals "$d/vocals.flac" --lead "$d/lead.flac" --dry "$d/dry.flac")
    plain=$d/inst.flac; [ -f "$d/plain.flac" ] && plain=$d/plain.flac
    if [[ " $ROUND1 " == *" $s "* ]]; then out=mix/$s; tail=; else out=mix2/$s; tail=_mix; fi
    for spk in pheebie sakura_shunka; do
        "$PY" "$MIX" --inst "$d/inst.flac" "${stems[@]}" --conv "$d/conv_$spk.flac" -o "${out}_$spk$tail.wav"
        if [[ " $NOBACKING " == *" $s "* ]]; then
            "$PY" "$MIX" --inst "$d/inst.flac" "${stems[@]}" --conv "$d/conv_$spk.flac" --no-backing \
                -o "${out}_${spk}_nobacking$tail.wav"
        fi
        # rokutousei has no backing of the singer's own outside its off vocal, so no allconv either
        if [ -f "$d/conv_harmwet_$spk.flac" ]; then
            "$PY" "$MIX" --inst "$plain" "${stems[@]}" --conv "$d/conv_$spk.flac" \
                --harm-conv "$d/conv_harmwet_$spk.flac" --harm-source "$d/harm_source.wav" \
                --harm-dry "$d/harm_vocals.flac" --harm-wet "$d/harm_vocals.flac" --no-backing \
                -o "${out}_${spk}_allconv_v2$tail.wav"
        fi
    done
done
