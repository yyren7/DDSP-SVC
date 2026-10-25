#!/bin/bash
# RIFT-SVC V3 768-12 fine-tuned on hanamaru_hareru's clips (setup_rift.sh), with its README's settings for one
# speaker: lr 5e-5, batch 64, lognorm time schedule, adaLN and time embedding frozen, no speaker dropout; a checkpoint
# every SAVE steps in ckpts/$RUN/model-step=<n>.ckpt, all kept. Logs to TensorBoard (logs/), not wandb.
#   cd /root/autodl-tmp/DDSP-SVC && nohup bash tools/bakeoff/finetune_rift.sh > /root/autodl-tmp/rift/train.log 2>&1 &
set -euo pipefail
R=/root/autodl-tmp/rift/RIFT-SVC; ENV=/root/autodl-tmp/conda_envs/rift
STEPS=${STEPS:-30000}; SAVE=${SAVE:-1000}; RUN=${RUN:-hanamaru_768-12}
cd $R
HF_HUB_OFFLINE=1 $ENV/bin/python train.py --config-name finetune model=dit-768-12 \
    training.run_name=$RUN +training.pretrained_path=pretrained/pretrain-v3_dit-768-12.ckpt \
    training.learning_rate=5e-5 training.weight_decay=0.01 training.max_steps=$STEPS \
    training.batch_size_per_gpu=64 training.save_per_steps=$SAVE training.test_per_steps=$SAVE \
    training.time_schedule=lognorm +training.freeze_adaln_and_tembed=true training.drop_spk_prob=0.0 \
    training.logger=tensorboard
