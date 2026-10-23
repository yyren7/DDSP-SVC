#!/bin/bash
# Candidate conversions of hanamaru_hareru's 6 cover leads for the diction check: model_40000 with seeds 1 and 2,
# and the 50k, 30k, 60k checkpoints, next to the existing 40k (default seed) and 80k ones, in covers/cand/<song>/
set -euo pipefail
C=/root/autodl-tmp/covers; E=/root/autodl-tmp/conda_envs; X=/root/autodl-tmp/speakers/hanamaru_hareru/exp_all
cd /root/autodl-tmp/DDSP-SVC
conv() {  # seed ckpt_step dry out
    "$E/ddsp/bin/python" -c "import sys, runpy, torch; torch.manual_seed(int(sys.argv[1])); sys.argv = ['main_reflow.py'] + sys.argv[2:]; runpy.run_path('main_reflow.py', run_name='__main__')" \
        "$1" -i "$3" -m "$X/model_$2.pt" -o "$4" -k 0 -id 1 2>&1 | tail -1
}
for s in haru yuusha haohaode aini idol liangrenfen; do
    case $s in haru|yuusha) dry=$C/_work5p/3_dereverb/$s.wav;; *) dry=$C/_work5/3_dereverb/$s.wav;; esac
    D=$C/cand/$s; mkdir -p $D
    ln -sf $C/out/${s}_hanamaru_hareru_40000.wav $D/0_40k.wav
    [ -f $D/1_40k_s1.wav ] || conv 1 40000 $dry $D/1_40k_s1.wav
    [ -f $D/2_40k_s2.wav ] || conv 2 40000 $dry $D/2_40k_s2.wav
    [ -f $D/3_50k.wav ] || conv 0 50000 $dry $D/3_50k.wav
    [ -f $D/4_30k.wav ] || conv 0 30000 $dry $D/4_30k.wav
    [ -f $D/5_60k.wav ] || conv 0 60000 $dry $D/5_60k.wav
    ln -sf $C/out/${s}_hanamaru_hareru_80000.wav $D/6_80k.wav
    ln -sf $dry $D/dry.wav
done
ls -la $C/cand/*/ | grep -c wav
