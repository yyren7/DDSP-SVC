#!/bin/bash
# The re-singing test of the bake-off (README.md, svs.py): one of her Chinese songs separated like her training data
# (prepare_dataset.py vocals, karaoke, dereverb) into the dry vocal the prompt is cut from, then 两人份的幸福 and 爱你
# sung from their transcriptions. Fits beside the fine-tuning on the GPU (under 5 GB). Ends with "svs done".
# PROMPT_SONG: the download to take the prompt from. Not 那些年 (0711): she sings it in Japanese, and the recogniser
# made noise of it; 学猫叫 is Chinese for sure and easy to check (喵).
#   cd /root/autodl-tmp/DDSP-SVC && nohup bash tools/bakeoff/svs.sh > /root/autodl-tmp/bakeoff/svs.log 2>&1 &
set -u
cd /root/autodl-tmp/DDSP-SVC
export HF_HOME=/root/autodl-tmp/.cache/huggingface HF_HUB_OFFLINE=1
S=/root/autodl-tmp/bakeoff/svs
PROMPT_SONG=${PROMPT_SONG:-学猫叫.1110}; NAME=${PROMPT_NAME:-xuemaojiao}
mkdir -p $S/sep/in
ln -sf "/root/autodl-tmp/speakers/hanamaru_hareru/downloads/树妖斯卡尔 - $PROMPT_SONG.mp3" $S/sep/in/$NAME.mp3
[ -f $S/sep/3_dereverb/$NAME.wav ] || /root/autodl-tmp/conda_envs/uvr/bin/python tools/prepare_dataset.py \
    -i $S/sep/in -w $S/sep --model-dir pretrain/uvr --steps vocals,karaoke,dereverb < /dev/null
P=/root/autodl-tmp/conda_envs/bk/bin/python
$P tools/bakeoff/svs.py prompt $S/sep/3_dereverb/$NAME.wav && $P tools/bakeoff/svs.py sing liangrenfen aini
echo "svs done"
