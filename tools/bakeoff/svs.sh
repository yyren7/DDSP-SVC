#!/bin/bash
# The re-singing test of the bake-off (README.md, svs.py): her Chinese 那些年 (0711) separated like her training data
# (prepare_dataset.py vocals, karaoke, dereverb) into the dry vocal the prompt is cut from, then 两人份的幸福 and 爱你
# sung from their transcriptions. Fits beside the fine-tuning on the GPU (under 5 GB). Ends with "svs done".
#   cd /root/autodl-tmp/DDSP-SVC && nohup bash tools/bakeoff/svs.sh > /root/autodl-tmp/bakeoff/svs.log 2>&1 &
set -u
cd /root/autodl-tmp/DDSP-SVC
export HF_HOME=/root/autodl-tmp/.cache/huggingface HF_HUB_OFFLINE=1
S=/root/autodl-tmp/bakeoff/svs
SRC="/root/autodl-tmp/speakers/hanamaru_hareru/downloads/树妖斯卡尔 - 那些年.0711.mp3"
mkdir -p $S/sep/in
ln -sf "$SRC" $S/sep/in/nxn.mp3
[ -f $S/sep/3_dereverb/nxn.wav ] || /root/autodl-tmp/conda_envs/uvr/bin/python tools/prepare_dataset.py -i $S/sep/in \
    -w $S/sep --model-dir pretrain/uvr --steps vocals,karaoke,dereverb < /dev/null
P=/root/autodl-tmp/conda_envs/bk/bin/python
$P tools/bakeoff/svs.py prompt $S/sep/3_dereverb/nxn.wav && $P tools/bakeoff/svs.py sing liangrenfen aini
echo "svs done"
