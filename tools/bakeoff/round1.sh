#!/bin/bash
# Round 1 of the bake-off (README.md): the zero-shot candidates convert the whole set (convert.py), one after the
# other on the GPU, then the machine scores of every system in out/ (score.py lines, songs). Ends with "round1 done".
#   cd /root/autodl-tmp/DDSP-SVC && nohup bash tools/bakeoff/round1.sh > /root/autodl-tmp/bakeoff/round1.log 2>&1 &
set -u
cd /root/autodl-tmp/DDSP-SVC
export HF_HOME=/root/autodl-tmp/.cache/huggingface HF_HUB_OFFLINE=1
for m in ${MODELS:-seedvc yingmusic soulx}; do
    # the Whisper feature extractor warns on every call that it was not told the rate (it is given 16 kHz)
    /root/autodl-tmp/conda_envs/bk/bin/python tools/bakeoff/convert.py $m 2>&1 | grep -v 'sampling_rate\|^RTF\|it/s\]'
    [ ${PIPESTATUS[0]} -eq 0 ] || echo "$m failed"
done
E=/root/autodl-tmp/conda_envs/evalq/bin/python
$E tools/bakeoff/score.py lines
$E tools/bakeoff/score.py songs
echo "round1 done"
