#!/bin/bash
# The conversion-model bake-off's environment (tools/bakeoff/README.md): the candidates' code in bakeoff/repos/, one
# venv on top of the ddsp env for all of them (its torch 2.9.1 + CUDA 12.8, not the old torch they pin), and their
# weights through hf-mirror.com, each where its own code looks for it. Safe to run again: done steps are skipped.
#   bash tools/bakeoff/setup.sh
set -e
B=/root/autodl-tmp/bakeoff; R=$B/repos; ENV=/root/autodl-tmp/conda_envs/bk
C=/root/autodl-tmp/DDSP-SVC/tools/autodl/torch-constraints.txt
export PIP_CACHE_DIR=/root/autodl-tmp/.cache/pip HF_HOME=/root/autodl-tmp/.cache/huggingface HF_ENDPOINT=https://hf-mirror.com
mkdir -p $R
cd $R
for r in Plachtaa/seed-vc GiantAILab/YingMusic-SVC Soul-AILab/SoulX-Singer; do
    [ -d ${r#*/} ] || git clone --depth 1 https://github.com/$r.git ${r#*/}
done

# Seed-VC and YingMusic-SVC import dac only for its VectorQuantize; SoulX-Singer's inference needs omegaconf and
# accelerate. transformers 4.46.3 as Seed-VC pins it: the ddsp env's 5.x changed the Whisper encoder they call.
[ -x $ENV/bin/python ] || /root/autodl-tmp/conda_envs/ddsp/bin/python -m venv --system-site-packages $ENV
$ENV/bin/pip install -c $C transformers==4.46.3 munch==4.0.0 einops==0.8.0 descript-audio-codec==1.0.0 pydub \
    accelerate omegaconf pyworld

# Seed-VC's hf_utils.py downloads into ./checkpoints of the working directory, transformers and BigVGAN into
# HF_HUB_CACHE=./checkpoints/hf_cache (inference.py sets it); YingMusic-SVC has the same code, so its checkpoints/
# is a link to Seed-VC's. Only the files the code opens: BigVGAN's repo also holds a 1.5 GB discriminator.
mkdir -p seed-vc/checkpoints
[ -e YingMusic-SVC/checkpoints ] || ln -s $R/seed-vc/checkpoints YingMusic-SVC/checkpoints
(cd seed-vc && HF_HUB_CACHE=./checkpoints/hf_cache $ENV/bin/python - <<'EOF'
from huggingface_hub import hf_hub_download, snapshot_download
for repo, f in [('Plachta/Seed-VC', 'DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema_v2.pth'),
                ('Plachta/Seed-VC', 'config_dit_mel_seed_uvit_whisper_base_f0_44k.yml'),
                ('lj1995/VoiceConversionWebUI', 'rmvpe.pt'), ('funasr/campplus', 'campplus_cn_common.bin'),
                ('GiantAILab/YingMusic-SVC', 'YingMusic-SVC-full.pt')]:
    print(hf_hub_download(repo, f, cache_dir='./checkpoints'))
for f in ('config.json', 'bigvgan_generator.pt'):
    print(hf_hub_download('nvidia/bigvgan_v2_44khz_128band_512x', f))
print(snapshot_download('openai/whisper-small', allow_patterns=['*.json', 'model.safetensors']))
EOF
)
# SoulX-Singer: the SVC model (2.8 GB; model.pt, the SVS one, only when the re-singing test needs it) and, of the
# preprocessing models, only RMVPE for the F0 it takes; Whisper-base from the default cache (HF_HOME above)
(cd SoulX-Singer && $ENV/bin/python - <<'EOF'
from huggingface_hub import hf_hub_download, snapshot_download
for f in ('config.yaml', 'model-svc.pt'):
    print(hf_hub_download('Soul-AILab/SoulX-Singer', f, local_dir='pretrained_models/SoulX-Singer'))
print(hf_hub_download('Soul-AILab/SoulX-Singer-Preprocess', 'rmvpe/rmvpe.pt',
                      local_dir='pretrained_models/SoulX-Singer-Preprocess'))
print(snapshot_download('openai/whisper-base', allow_patterns=['*.json', 'model.safetensors']))
EOF
)
$ENV/bin/python -c "import torch, transformers, dac, omegaconf; print('bk ok', torch.__version__, transformers.__version__, torch.cuda.is_available())"
du -sh $R/*/checkpoints/ $R/SoulX-Singer/pretrained_models
