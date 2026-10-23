#!/bin/bash
# hanamaru_hareru's final model is model_40000.pt (2026-10-22): run5.sh/run6.sh take STEP, the old outputs get _80000
set -euo pipefail
C=/root/autodl-tmp/covers; cd "$C"
cp -n run5.sh run5.sh.bak80k; cp -n run6.sh run6.sh.bak80k
sed -i 's|^E=/root/autodl-tmp/conda_envs$|E=/root/autodl-tmp/conda_envs\nSTEP=${STEP:-40000}  # model_<STEP>.pt, also in the output names; hanamaru_hareru uses 40000 (2026-10-22)|' run5.sh
sed -i 's|out="$C/out/${s}_${spk}"$|out="$C/out/${s}_${spk}_${STEP}"|; s|model_80000\.pt|model_${STEP}.pt|; s|"$C/out/${s}_${spk}.wav:conv_${spk}"|"$C/out/${s}_${spk}_${STEP}.wav:conv_${spk}_${STEP}"|' run5.sh
sed -i 's|SPK=${SPEAKERS:-hanamaru_hareru}$|SPK=${SPEAKERS:-hanamaru_hareru}; STEP=${STEP:-40000}  # model_<STEP>.pt, also in the output names|; s|model_80000\.pt"; out="$C/out/${s}_${spk}"|model_${STEP}.pt"; out="$C/out/${s}_${spk}_${STEP}"|; s|-o "$C/out/${s}_${spk}_allconv_mix.wav"|-o "${out}_allconv_mix.wav"|' run6.sh
diff run5.sh.bak80k run5.sh || true; diff run6.sh.bak80k run6.sh || true
for f in out/*_hanamaru_hareru.wav out/*_hanamaru_hareru_*.wav; do
    case "$f" in *_hanamaru_hareru_[0-9]*) continue;; esac
    mv -n "$f" "${f/_hanamaru_hareru/_hanamaru_hareru_80000}"
done
for d in haru idol yuusha aini haohaode liangrenfen; do
    [ -f pack/stems/$d/conv_hanamaru_hareru.flac ] && mv -n pack/stems/$d/conv_hanamaru_hareru.flac pack/stems/$d/conv_hanamaru_hareru_80000.flac
done
ls out | grep hanamaru
