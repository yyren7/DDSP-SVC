#!/bin/bash
# Round 2 of the bake-off (README.md): once finetune_seedvc.sh has saved the checkpoint of step UNTIL, the training
# is stopped (the GPU has no room for it and a conversion at once) and every kept checkpoint converts the whole set
# as system seedvc_ft<step> (same reference and settings as the zero-shot seedvc), then the machine scores of every
# system in out/. Ends with "round2 done".
#   cd /root/autodl-tmp/DDSP-SVC && UNTIL=10000 nohup bash tools/bakeoff/round2.sh > /root/autodl-tmp/bakeoff/round2.log 2>&1 &
set -u
cd /root/autodl-tmp/DDSP-SVC
KEEP=/root/autodl-tmp/bakeoff/ft/seedvc; UNTIL=${UNTIL:-10000}
export HF_HOME=/root/autodl-tmp/.cache/huggingface HF_HUB_OFFLINE=1
last=$(printf 'step_%05d.pth' $UNTIL)
until ls $KEEP/*_$last >/dev/null 2>&1; do sleep 60; done
sleep 120  # the link appears when torch.save starts writing
pkill -f '[t]rain.py --config' && echo "training stopped after step $UNTIL"
sleep 10
for ckpt in $(ls $KEEP/DiT_epoch_*_step_*.pth | sort -t_ -k5); do
    step=$(basename $ckpt .pth | sed 's/.*_step_0*//')
    /root/autodl-tmp/conda_envs/bk/bin/python tools/bakeoff/convert.py seedvc --system seedvc_ft$step \
        --checkpoint $ckpt --config $KEEP/config.yml 2>&1 | grep --line-buffered -v 'sampling_rate\|^RTF\|it/s\]'
    [ ${PIPESTATUS[0]} -eq 0 ] || echo "seedvc_ft$step failed"
done
E=/root/autodl-tmp/conda_envs/evalq/bin/python
$E tools/bakeoff/score.py lines
$E tools/bakeoff/score.py songs
echo "round2 done"
