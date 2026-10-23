#!/bin/bash
# FLAC copies of the mixes and of the stems that cover_mix.py needs, for listening and remixing elsewhere
set -euo pipefail
C=/root/autodl-tmp/covers
P=$C/pack
mkdir -p "$P/stems"
flac() { ffmpeg -v error -y -i "$1" -c:a flac -sample_fmt s32 -bits_per_raw_sample 24 "$2"; }
for s in colors hitomi akunohana sakura phoenix yuukyou; do
    mkdir -p "$P/stems/$s"
    flac "$C/$s/phase/inst.wav" "$P/stems/$s/inst.flac"
    cp "$C/$s/phase/vocal.wav" "$P/stems/$s/source.wav"  # float: original - off vocal can peak over 1
    flac "$C/_work/1_vocals/$s.wav" "$P/stems/$s/vocals.flac"
    flac "$C/_work/2_karaoke/$s.wav" "$P/stems/$s/lead.flac"
    flac "$C/_work/3_dereverb/$s.wav" "$P/stems/$s/dry.flac"
    for spk in pheebie sakura_shunka; do
        flac "$C/out/${s}_${spk}.wav" "$P/stems/$s/conv_${spk}.flac"
    done
done
du -sh "$P/stems"
