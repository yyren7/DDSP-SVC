#!/bin/bash
# Round 2 of the bake-off (README.md): Seed-VC's released singing model (44.1 kHz, F0 conditioned) fine-tuned on
# hanamaru_hareru's training clips, data_all/train/audio (build_clips.py all: 2593 clips, 7.15 h, the set her DDSP-SVC
# model was trained on). train.py keeps only its two latest checkpoints, so every checkpoint it saves is hard-linked
# into bakeoff/ft/seedvc/ (KEEP) as it appears, to compare steps later (convert.py seedvc --checkpoint <pth> --config
# <yml>). The final model (ft_model.pth, the weights of step STEPS, which has no checkpoint of its own) is kept beside
# them as DiT_epoch_final_step_<STEPS>.pth.
#   STEPS=10000 BATCH=8 SAVE=2000 bash tools/bakeoff/finetune_seedvc.sh
#   KEEP=/root/autodl-tmp/bakeoff/ft/seedvc5k RUN=hanamaru_5k STEPS=5000 BATCH=4 SAVE=1000 bash tools/bakeoff/finetune_seedvc.sh
set -euo pipefail
R=/root/autodl-tmp/bakeoff/repos/seed-vc; ENV=/root/autodl-tmp/conda_envs/bk
DATA=/root/autodl-tmp/speakers/hanamaru_hareru/data_all/train/audio
KEEP=${KEEP:-/root/autodl-tmp/bakeoff/ft/seedvc}; RUN=${RUN:-hanamaru_hareru}
STEPS=${STEPS:-10000}; BATCH=${BATCH:-8}; SAVE=${SAVE:-2000}
cd $R
CKPT=$(ls checkpoints/models--Plachta--Seed-VC/snapshots/*/DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth | tail -1)
CFG=$(ls checkpoints/models--Plachta--Seed-VC/snapshots/*/config_dit_mel_seed_uvit_whisper_base_f0_44k.yml | tail -1)
mkdir -p $KEEP
# the released config logs to ./runs/run_dit_mel_seed_uvit_whisper_base_f0_44k/, not to the ./runs of the repo's
# presets: trained with a copy set to ./runs, so that runs/$RUN is where the checkpoints are (on 10-23 none were
# kept for missing this, and train.py deleted all but the last two)
sed 's|^log_dir:.*|log_dir: "./runs"|' $CFG > $KEEP/config.yml
CFG=$KEEP/config.yml
keep() { for f in runs/$RUN/*.pth; do [ -e "$f" ] && [ ! -e "$KEEP/${f##*/}" ] && ln "$f" "$KEEP/" || true; done; }
( while sleep 30; do keep; done ) &
watcher=$!
final=$KEEP/$(printf 'DiT_epoch_final_step_%05d.pth' $STEPS)
trap 'kill $watcher; keep; [ ! -e $KEEP/ft_model.pth ] || mv $KEEP/ft_model.pth $final' EXIT
HF_HUB_OFFLINE=1 $ENV/bin/python train.py --config $CFG --pretrained-ckpt $CKPT --dataset-dir $DATA --run-name $RUN \
    --batch-size $BATCH --max-steps $STEPS --max-epochs 1000 --save-every $SAVE --num-workers 4
