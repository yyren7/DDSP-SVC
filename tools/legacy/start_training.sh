#!/bin/bash

# Go to the project directory
cd /home/yyren/DDSP-SVC

# Activate the virtual environment
source .venv/bin/activate

# Set the CUDA allocation environment variable
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Run the training script
python train_reflow.py -c configs/reflow.yaml 