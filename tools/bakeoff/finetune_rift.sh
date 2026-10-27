#!/bin/bash
# RIFT-SVC V3 768-12 fine-tuned on SPEAKER's clips (setup_rift.sh; default hanamaru_hareru), with its README's settings for one
# speaker: lr 5e-5, batch 64 (BATCH x ACCUM), lognorm time schedule, adaLN and time embedding frozen, no speaker dropout; a checkpoint
# every SAVE steps in ckpts/$RUN/model-step=<n>.ckpt, all kept; RUN is <first part of SPEAKER>_768-12 (hanamaru_768-12,
# sakura_768-12). Logs to TensorBoard (logs/), not wandb.
#   cd /root/autodl-tmp/DDSP-SVC && SPEAKER=pheebie SAVE=5000 nohup bash tools/bakeoff/finetune_rift.sh > /root/autodl-tmp/rift/train_pheebie.log 2>&1 &
set -euo pipefail
R=/root/autodl-tmp/rift/RIFT-SVC; ENV=/root/autodl-tmp/conda_envs/rift
SPEAKER=${SPEAKER:-hanamaru_hareru}; STEPS=${STEPS:-30000}; SAVE=${SAVE:-1000}; RUN=${RUN:-${SPEAKER%%_*}_768-12}
D=data/finetune; [ $SPEAKER = hanamaru_hareru ] || D=data/finetune_$SPEAKER
# batch 64 takes ~17 GB; the GPU is shared (the PV renders), so 32 with 2 steps of gradient accumulation by default
BATCH=${BATCH:-32}; ACCUM=${ACCUM:-2}
cd $R
HF_HUB_OFFLINE=1 $ENV/bin/python train.py --config-name finetune model=dit-768-12 dataset.data_dir=$D dataset.meta_info_path=$D/meta_info.json \
    training.run_name=$RUN +training.pretrained_path=pretrained/pretrain-v3_dit-768-12.ckpt \
    training.learning_rate=5e-5 training.weight_decay=0.01 training.max_steps=$STEPS \
    training.batch_size_per_gpu=$BATCH training.grad_accumulation_steps=$ACCUM training.save_per_steps=$SAVE training.test_per_steps=$SAVE \
    training.time_schedule=lognorm +training.freeze_adaln_and_tembed=true training.drop_spk_prob=0.0 \
    training.logger=tensorboard
