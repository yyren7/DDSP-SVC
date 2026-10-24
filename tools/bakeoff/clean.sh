#!/bin/bash
# The clean inputs of the bake-off (README.md, clean_set.py): once Opencpop's archive is downloaded into clean/dl/,
# the inputs made, then converted by her DDSP-SVC 40k and by YingMusic whole and a phrase at a time, and put on the
# review page under their names. Ends with "clean done".
#   cd /root/autodl-tmp/DDSP-SVC && nohup bash tools/bakeoff/clean.sh > /root/autodl-tmp/bakeoff/clean.log 2>&1 &
set -u
cd /root/autodl-tmp/DDSP-SVC
export HF_HOME=/root/autodl-tmp/.cache/huggingface
E=/root/autodl-tmp/conda_envs; B=/root/autodl-tmp/bakeoff; M=$B/set/manifest_clean.json
A=$B/clean/dl/Opencpop.tar.gz; SIZE=6958106328  # the archive's size on Saaaxman/Opencpop
until [ "$(stat -c %s $A 2>/dev/null)" = $SIZE ]; do sleep 30; done
$E/ddsp/bin/python tools/bakeoff/clean_set.py prep || { echo "prep failed"; exit 1; }
$E/ddsp/bin/python tools/bakeoff/clean_set.py ddsp 2>&1 | grep --line-buffered -a "^clean_ddsp40k\|Error\|Traceback"
[ ${PIPESTATUS[0]} -eq 0 ] || echo "ddsp failed"
for v in "clean_yingmusic:" "clean_yingmusic_phr:--split"; do
    HF_HUB_OFFLINE=1 $E/bk/bin/python tools/bakeoff/convert.py yingmusic --manifest $M --system ${v%%:*} ${v#*:} 2>&1 |
        grep --line-buffered -a "^clean_\|Error\|Traceback"
    [ ${PIPESTATUS[0]} -eq 0 ] || echo "${v%%:*} failed"
done
$E/ddsp/bin/python tools/bakeoff/clean_set.py show
echo "clean done"
